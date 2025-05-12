import os
import logging
import base64
import uuid
import mimetypes
from datetime import datetime
from io import BytesIO
from flask import (
    render_template, 
    request, 
    redirect, 
    url_for, 
    jsonify, 
    session, 
    send_file, 
    abort
)
from werkzeug.utils import secure_filename
from app import app, db
from models import User, Endcard, UserCredit

# Configure logging
logging.basicConfig(level=logging.DEBUG)

@app.route('/health')
def health_check():
    """Health check endpoint for deployment monitoring"""
    return '', 200

# Ensure upload folder exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Valid file types
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4'}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS.union(ALLOWED_VIDEO_EXTENSIONS)

# Maximum file size (in bytes) - 2.2MB
MAX_FILE_SIZE = 2.2 * 1024 * 1024

def get_current_user():
    """Get or create a user based on session ID"""
    if 'user_session_id' not in session:
        session['user_session_id'] = str(uuid.uuid4())

    user = User.query.filter_by(session_id=session['user_session_id']).first()

    if not user:
        # Create new user
        user = User(session_id=session['user_session_id'])
        db.session.add(user)
        db.session.flush()  # Flush to get the user ID

        # Initialize credits for new user
        user_credit = UserCredit(user_id=user.id)
        db.session.add(user_credit)
        db.session.commit()

    # Store credits in session for easy access
    if hasattr(user, 'credits') and user.credits:
        session['credits'] = user.credits.credits
    else:
        # Handle case where user doesn't have a credits record
        user_credit = UserCredit(user_id=user.id)
        db.session.add(user_credit)
        db.session.commit()
        session['credits'] = user_credit.credits

    return user

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

@app.route('/')
def index():
    """Home page route"""
    user = get_current_user()

    # Check if we're editing an existing endcard
    endcard_id = request.args.get('endcard_id')
    endcard = None
    if endcard_id and user:
        endcard = Endcard.query.filter_by(id=endcard_id, user_id=user.id).first()

    return render_template('index.html', endcard=endcard, user=user)

@app.route('/history')
def history():
    """View conversion history"""
    user = get_current_user()
    endcards = Endcard.query.filter_by(user_id=user.id).order_by(Endcard.created_at.desc()).all()
    return render_template('history.html', endcards=endcards)

@app.route('/upgrade')
def upgrade():
    """Upgrade page for purchasing credits"""
    get_current_user()  # Ensure user is created and credits are in session
    return render_template('upgrade.html')

@app.route('/process_upload', methods=['POST'])
def process_upload():
    """Process file upload and create HTML endcard"""
    user = get_current_user()

    # Check if editing existing endcard
    endcard_id = request.form.get('endcard_id')

    # Check if user has enough credits for a new conversion
    if not endcard_id and user.credits.credits <= 0:
        return jsonify({
            'success': False,
            'error': 'You have no credits remaining. Please upgrade to continue.'
        })

    # Get files from request
    portrait_file = request.files.get('portrait_file')
    landscape_file = request.files.get('landscape_file')

    # Validate both files are present
    if not portrait_file or not landscape_file:
        return jsonify({
            'success': False,
            'error': 'Both portrait and landscape files are required.'
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
        errors.append(f'Portrait file is too large. Maximum size: 2.2MB')

    if landscape_size > MAX_FILE_SIZE:
        errors.append(f'Landscape file is too large. Maximum size: 2.2MB')

    if errors:
        return jsonify({
            'success': False,
            'error': '\n'.join(errors)
        })

    # Process files
    try:
        # Secure filenames
        portrait_filename = secure_filename(portrait_file.filename)
        landscape_filename = secure_filename(landscape_file.filename)

        # Determine file types
        portrait_type = get_file_type(portrait_filename)
        landscape_type = get_file_type(landscape_filename)

        # Get MIME types
        portrait_mime = mimetypes.guess_type(portrait_filename)[0] or 'application/octet-stream'
        landscape_mime = mimetypes.guess_type(landscape_filename)[0] or 'application/octet-stream'

        # Convert files to data URLs
        portrait_data_url = file_to_data_url(portrait_file, portrait_mime)
        landscape_data_url = file_to_data_url(landscape_file, landscape_mime)

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
            if not user.credits.deduct_credit():
                return jsonify({
                    'success': False,
                    'error': 'You have no credits remaining. Please upgrade to continue.'
                })

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
        logging.error(f"Error processing upload: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'An error occurred while processing your files. Please try again.'
        })

@app.route('/download_template/<template_type>/<int:endcard_id>')
def download_template(template_type, endcard_id):
    """Download HTML template"""
    user = get_current_user()

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
def get_endcard_data(endcard_id):
    """API endpoint to get endcard data"""
    user = get_current_user()

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

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    """Simulate payment processing - in a real app this would connect to Stripe"""
    user = get_current_user()
    package = request.form.get('package', 'starter')

    # Define credit packages
    packages = {
        'starter': 10,
        'popular': 30,
        'pro': 60
    }

    credit_amount = packages.get(package, 10)

    # In a real application, this would redirect to Stripe payment
    # For demo purposes, we'll just add the credits directly
    user.credits.add_credits(credit_amount)
    db.session.commit()

    # Update session with new credit count
    session['credits'] = user.credits.credits

    return render_template('upgrade.html', success=True, credits_added=credit_amount)