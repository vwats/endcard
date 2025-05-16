
import os
import logging
import base64
import uuid
import mimetypes
from functools import wraps
from io import BytesIO
from datetime import datetime
from flask import (
    render_template, 
    request, 
    redirect, 
    url_for, 
    jsonify, 
    session, 
    send_file, 
    abort,
    flash
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from app import app, db
from models import User, Endcard, UserCredit

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Ensure upload folder exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Valid file types
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4'}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS.union(ALLOWED_VIDEO_EXTENSIONS)

# Maximum file size (in bytes) - 4.5MB per file to allow some wiggle room
MAX_FILE_SIZE = 4.5 * 1024 * 1024

from auth_utils import get_current_user


def allowed_file(filename):
    """Check if file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    """Determine if file is image or video based on extension"""
    ext = filename.rsplit('.', 1)[1].lower()
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return 'image'
    elif ext in ALLOWED_VIDEO_EXTENSIONS:
        return 'video'
    return None

def file_to_data_url(file_stream, content_type):
    """Convert file to data URL format"""
    encoded_content = base64.b64encode(file_stream.read()).decode('utf-8')
    return f"data:{content_type};base64,{encoded_content}"

from auth_utils import manage_session

@app.route('/')
@manage_session
def index():
    """Home page route"""
    try:
        user = get_current_user()
        endcard_id = request.args.get('endcard_id')
        endcard = None
        
        if user and endcard_id:
            endcard = Endcard.query.filter_by(id=endcard_id, user_id=user.id).first()
            
        # Ensure session has credits key
        if 'credits' not in session:
            session['credits'] = 0
            
        # Flash message if user just logged in (message set in google_auth.py)
        messages = []
            
        return render_template('index.html', endcard=endcard, messages=messages)
            
    except Exception as e:
        logging.error(f"Error in index route: {str(e)}")
        db.session.rollback()
        flash('An error occurred', 'error')
        return redirect(url_for('index'))
    if session.get('show_welcome', False):
        messages.append('Welcome! You can now purchase credits and track your conversion history.')
        session.pop('show_welcome', None)

    return render_template('index.html', endcard=endcard, messages=messages)

@app.route('/history')
@login_required
@manage_session
def history():
    """View conversion history"""
    try:
        user = get_current_user()
        if not user or not user.is_authenticated:
            flash('Please sign in to view your conversion history', 'warning')
            return redirect(url_for('google_auth.login'))

        endcards = Endcard.query.filter_by(user_id=user.id).order_by(Endcard.created_at.desc()).all()
        return render_template('history.html', endcards=endcards)
    except Exception as e:
        logging.error(f"Error in history route: {str(e)}")
        db.session.rollback()
        flash('An error occurred while loading your history', 'error')
        return redirect(url_for('index'))

@app.route('/credits')
@app.route('/upgrade')
@login_required
@manage_session
def upgrade():
    """Credits management page for viewing and purchasing credits"""
    stripe_status = get_stripe_status()
    if not stripe_status['enabled']:
        flash('Stripe payment is not properly configured.', 'error')
        logging.error('Stripe payment system is not properly configured')
    return render_template('upgrade.html', 
                          stripe_public_key=stripe_status['publishable_key'])

def error_handler(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500
    return wrapper

def check_credits():
    """Helper to check if user has sufficient credits"""
    try:
        user = get_current_user()
        if not user or not user.is_authenticated:
            raise ValueError('Authentication required')

        credit_record = UserCredit.get_user_credits(user.id)
        if credit_record.credits <= 0:
            raise ValueError('Insufficient credits')

        return user, credit_record
    except Exception as e:
        logging.error(f"Error checking credits: {str(e)}")
        raise

@app.route('/process_upload', methods=['POST'])
@login_required
@manage_session
@error_handler
def process_upload():
    """Process file upload and create HTML endcard"""
    try:
        if not current_user.is_authenticated:
            return jsonify({
                'success': False,
                'error': 'Please sign in to convert your files.'
            })
            
        user, credit_record = check_credits()
        # Check if editing existing endcard
        endcard_id = request.form.get('endcard_id')

        # Get files from request
        portrait_file = request.files.get('portrait_file')
        landscape_file = request.files.get('landscape_file')

        # Ensure at least one file is present
        if not portrait_file and not landscape_file:
            return jsonify({
                'success': False,
                'error': 'Please upload at least one file.'
            })

        errors = []

        # Validate portrait file
        if not allowed_file(portrait_file.filename):
            errors.append('Portrait file: Unsupported file type. Allowed types: jpg, jpeg, png, mp4')

        # Validate landscape file
        if not allowed_file(landscape_file.filename):
            errors.append('Landscape file: Unsupported file type. Allowed types: jpg, jpeg, png, mp4')

        # Validate file sizes
        portrait_file.seek(0, os.SEEK_END)
        portrait_size = portrait_file.tell()
        portrait_file.seek(0)

        landscape_file.seek(0, os.SEEK_END)
        landscape_size = landscape_file.tell()
        landscape_file.seek(0)

        if portrait_size > MAX_FILE_SIZE:
            errors.append(f'Portrait file is too large. Maximum size: 4.5MB')

        if landscape_size > MAX_FILE_SIZE:
            errors.append(f'Landscape file is too large. Maximum size: 4.5MB')

        if errors:
            return jsonify({
                'success': False,
                'error': '\n'.join(errors)
            })

        # Log incoming request details
        logging.info(f"Processing upload - Portrait: {portrait_file.filename}, Landscape: {landscape_file.filename}")

        # Secure filenames
        portrait_filename = secure_filename(portrait_file.filename)
        landscape_filename = secure_filename(landscape_file.filename)

        # Determine file types
        portrait_type = get_file_type(portrait_filename)
        landscape_type = get_file_type(landscape_filename)

        if not portrait_type or not landscape_type:
            raise ValueError(f"Invalid file types - Portrait: {portrait_type}, Landscape: {landscape_type}")

        # Get MIME types
        portrait_mime = mimetypes.guess_type(portrait_filename)[0] or 'application/octet-stream'
        landscape_mime = mimetypes.guess_type(landscape_filename)[0] or 'application/octet-stream'

        logging.info(f"File types - Portrait: {portrait_mime}, Landscape: {landscape_mime}")

        # Convert files to data URLs
        try:
            portrait_data_url = file_to_data_url(portrait_file, portrait_mime)
            landscape_data_url = file_to_data_url(landscape_file, landscape_mime)
        except Exception as e:
            logging.error(f"Data URL conversion failed: {str(e)}")
            raise

        # Create or update endcard record
        if endcard_id:
            # Update existing endcard
            endcard = Endcard.query.filter_by(id=endcard_id, user_id=user.id).first()
            if not endcard:
                return jsonify({
                    'success': False,
                    'error': 'Endcard not found or you do not have permission to edit it.'
                })
        else:
            # Create new endcard and deduct credit
            #Credit deduction removed as per requirement

            endcard = Endcard(user_id=user.id)
            db.session.add(endcard)

        # Update endcard data
        endcard.portrait_created = True
        endcard.portrait_filename = portrait_filename
        endcard.portrait_file_type = portrait_type
        endcard.portrait_file_size = portrait_size
        endcard.portrait_data_url = portrait_data_url

        endcard.landscape_created = True
        endcard.landscape_filename = landscape_filename
        endcard.landscape_file_type = landscape_type
        endcard.landscape_file_size = landscape_size
        endcard.landscape_data_url = landscape_data_url

        db.session.commit()

        # Update session with new credit count
        session['credits'] = user.credits.credits

        return jsonify({
            'success': True,
            'endcard_id': endcard.id,
            'portrait_data_url': portrait_data_url,
            'landscape_data_url': landscape_data_url,
            'is_video': endcard.is_video
        })

    except Exception as e:
        error_msg = str(e)
        logging.error(f"Error processing upload: {error_msg}")
        logging.error(f"Error type: {type(e).__name__}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f"Error processing files: {error_msg}".strip()
        }), 500

@app.route('/download_template/<template_type>/<int:endcard_id>')
@login_required
@manage_session
def download_template(template_type, endcard_id):
    """Download HTML template"""
    try:
        user, credit_record = check_credits()

        # Verify ownership of the endcard and handle credit deduction in a transaction
        try:
            endcard = Endcard.query.filter_by(id=endcard_id, user_id=user.id).first()
            if not endcard:
                flash('Access denied: Endcard not found or unauthorized', 'error')
                return redirect(url_for('index'))

            # Deduct credit and sync session in the same transaction
            if not credit_record.deduct_credit():
                flash('Insufficient credits', 'error')
                return redirect(url_for('credits'))
                
            db.session.commit()
            session['credits'] = user.credits.credits
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error processing template download: {str(e)}")
            flash('An error occurred while processing your request', 'error')
            return redirect(url_for('index'))

    except Exception as e:
        logging.error(f"Error in credit check: {str(e)}")
        flash('An error occurred while processing your request', 'error')
        return redirect(url_for('index'))

    # Get the endcard
    endcard = Endcard.query.filter_by(id=endcard_id, user_id=user.id).first()
    if not endcard:
        abort(404)

    if template_type == 'rotatable':
        template = render_template(
            'endcard_templates/template_rotatable.html',
            portrait_data_url=endcard.portrait_data_url,
            landscape_data_url=endcard.landscape_data_url,
            is_video=endcard.is_video
        )
    elif template_type == 'portrait':
        template = render_template(
            'endcard_templates/template_portrait.html',
            data_url=endcard.portrait_data_url,
            is_video=endcard.portrait_file_type == 'video'
        )
    elif template_type == 'landscape':
        template = render_template(
            'endcard_templates/template_landscape.html',
            data_url=endcard.landscape_data_url,
            is_video=endcard.landscape_file_type == 'video'
        )
    else:
        abort(404)

    # Create in-memory file
    mem_file = BytesIO()
    mem_file.write(template.encode('utf-8'))
    mem_file.seek(0)

    # Generate filename
    filename = f"endcard_{template_type}_{endcard_id}.html"

    return send_file(
        mem_file,
        mimetype='text/html',
        as_attachment=True,
        download_name=filename
    )

@app.route('/api/endcard/<int:endcard_id>')
@login_required
def get_endcard_data(endcard_id):
    """API endpoint to get endcard data"""
    user = get_current_user()
    if not user or not user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401

    endcard = Endcard.query.filter_by(id=endcard_id, user_id=user.id).first()
    if not endcard:
        return jsonify({
            'success': False,
            'error': 'Endcard not found'
        })

    return jsonify({
        'success': True,
        'endcard': {
            'id': endcard.id,
            'portrait_filename': endcard.portrait_filename,
            'landscape_filename': endcard.landscape_filename,
            'is_video': endcard.is_video,
            'created_at': endcard.created_at.isoformat()
        }
    })

from stripe_handler import stripe, get_stripe_status

# Initialize package Stripe IDs
basic_package = {
    'stripe_price_id': os.environ.get('STRIPE_BASIC_PRICE_ID'),
    'stripe_product_id': os.environ.get('STRIPE_BASIC_PRODUCT_ID'),
    'credits': 10,
    'price': 1000
}

standard_package = {
    'stripe_price_id': os.environ.get('STRIPE_STANDARD_PRICE_ID'),
    'stripe_product_id': os.environ.get('STRIPE_STANDARD_PRODUCT_ID'),
    'credits': 30,
    'price': 2500
}

pro_package = {
    'stripe_price_id': os.environ.get('STRIPE_PRO_PRICE_ID'),
    'stripe_product_id': os.environ.get('STRIPE_PRO_PRODUCT_ID'),
    'credits': 60,
    'price': 4500
}



    except stripe.error.AuthenticationError as e:
    logging.error(f"Stripe authentication error: {str(e)}")
    return jsonify({'error': 'Invalid API key or authentication failed'}), 401
except stripe.error.StripeError as e:
    logging.error(f"Stripe error: {str(e)}")
    return jsonify({'error': 'Payment processing error'}), 400
except Exception as e:
    logging.error(f"Unexpected error in checkout: {str(e)}")
    return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/payment/success')
def payment_success():
    """Handle successful payment and credit allocation"""
    session_id = request.args.get('session_id')
    if not session_id:
        return redirect(url_for('upgrade'))

    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        if checkout_session.payment_status == 'paid':
            user = get_current_user()
            credits = int(checkout_session.metadata.get('credits', 0))
            user.credits.add_credits(credits)
            db.session.commit()
            session['credits'] = user.credits.credits
            return redirect(url_for('index'))
        else:
            return redirect(checkout_session.url)
    except stripe.error.StripeError as e:
        logging.error(f"Stripe API error: {str(e)}")
        flash('Payment processing error. Please try again or contact support.', 'error')
        return redirect(url_for('credits'))
    except Exception as e:
        logging.error(f"Unexpected error in payment processing: {str(e)}")
        flash('An unexpected error occurred. Please contact support.', 'error')
        return redirect(url_for('credits'))
