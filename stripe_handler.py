import os
import json
import logging
import stripe
from flask import Blueprint, request, jsonify, session, redirect, url_for
from app import app, db
from models import User, UserCredit

# Configure logging
logger = logging.getLogger(__name__)

# Stripe configuration and state
stripe_enabled = False
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')

def init_stripe():
    """Initialize Stripe with graceful fallback"""
    global stripe_enabled

    if not STRIPE_SECRET_KEY:
        logger.warning("STRIPE_SECRET_KEY not set - payment features disabled")
        return False

    stripe.api_key = STRIPE_SECRET_KEY
    try:
        # Test the API key
        stripe.Account.retrieve()
        stripe_enabled = True
        logger.info("Stripe initialized successfully")
        return True
    except stripe.error.AuthenticationError as e:
        logger.error(f"Stripe authentication failed: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Stripe initialization error: {str(e)}")
        return False

if not STRIPE_WEBHOOK_SECRET:
    logger.warning("STRIPE_WEBHOOK_SECRET not set - webhook verification will fail")

# Initialize Stripe and check environment variables
init_stripe()

# Check if environment variables are set and log status
stripe_vars = [
    'STRIPE_SECRET_KEY', 'STRIPE_PUBLISHABLE_KEY', 'STRIPE_WEBHOOK_SECRET',
    'STRIPE_BASIC_PRICE_ID', 'STRIPE_STANDARD_PRICE_ID', 'STRIPE_PRO_PRICE_ID',
    'STRIPE_BASIC_PRODUCT_ID', 'STRIPE_STANDARD_PRODUCT_ID',
    'STRIPE_PRO_PRODUCT_ID'
]

for var in stripe_vars:
    if not os.environ.get(var):
        logger.warning(f"Environment variable {var} is not set")

def get_stripe_status():
    """Get current Stripe configuration status"""
    return {
        'enabled': stripe_enabled,
        'publishable_key': STRIPE_PUBLISHABLE_KEY
    }
    """Initialize and validate Stripe configuration"""
    if not stripe.api_key:
        logger.error("STRIPE_SECRET_KEY is not properly configured")
        return False

    try:
        # Test the API key by making a simple API call
        stripe.Account.retrieve()
        logger.info("Stripe API key verified successfully")
        return True
    except stripe.error.AuthenticationError as e:
        logger.error(f"Stripe authentication error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Stripe configuration error: {str(e)}")
        return False

# Create blueprint
stripe_blueprint = Blueprint('stripe_handler', __name__)

# Credit packages configuration
CREDIT_PACKAGES = {
    'starter': {'credits': 10, 'price': 1000, 'name': 'Starter Package'},  # $10
    'standard': {'credits': 35, 'price': 2500, 'name': 'Standard Package'},  # $25
    'pro': {'credits': 70, 'price': 4500, 'name': 'Pro Package'}       # $45
}

# Log configuration status
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')

if not stripe.api_key:
    logger.warning("STRIPE_SECRET_KEY is not set. API functionality will be limited.")
if not STRIPE_WEBHOOK_SECRET:
    logger.warning("STRIPE_WEBHOOK_SECRET is not set. Webhook verification will be limited.")
if not STRIPE_PUBLISHABLE_KEY:
    logger.warning("STRIPE_PUBLISHABLE_KEY is not set. Client-side integration will be limited.")

# Create blueprint
stripe_blueprint = Blueprint('stripe_handler', __name__)

# Credit packages configuration
CREDIT_PACKAGES = {
    'starter': {'credits': 10, 'price': 1000, 'name': 'Starter Package'},  # $10
    'standard': {'credits': 35, 'price': 2500, 'name': 'Standard Package'},  # $25
    'pro': {'credits': 70, 'price': 4500, 'name': 'Pro Package'}       # $45
}

@stripe_blueprint.route('/create-payment-intent', methods=['POST'])
def create_payment_intent():
    """Create a payment intent for Stripe Elements"""
    try:
        # Get user information
        from auth_utils import get_current_user
        user = get_current_user()

        # Get the selected package
        data = json.loads(request.data)
        package_id = data.get('package', 'starter')

        if package_id not in CREDIT_PACKAGES:
            return jsonify({
                'error': 'Invalid package selected'
            }), 400

        package = CREDIT_PACKAGES[package_id]

        # Create a new PaymentIntent
        intent = stripe.PaymentIntent.create(
            amount=package['price'],
            currency='usd',
            metadata={
                'user_id': user.id,
                'package_id': package_id,
                'credits': package['credits']
            },
            receipt_email=user.email if user.email else None,
            # Enable automatic payment confirmation
            automatic_payment_methods={
                'enabled': True,
            }
        )

        return jsonify({
            'clientSecret': intent.client_secret,
            'amount': package['price'],
            'id': intent.id
        })

    except Exception as e:
        logger.error(f"Error in create_payment_intent: {str(e)}")
        return jsonify({'error': str(e)}), 400

@stripe_blueprint.route('/webhook', methods=['POST'])
def webhook():
    """Handle Stripe webhook events"""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )

        # Handle the event
        if event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            handle_payment_success(payment_intent)
        elif event['type'] == 'payment_intent.payment_failed':
            payment_intent = event['data']['object']
            handle_payment_failure(payment_intent)

        return jsonify({'status': 'success'})

    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({'error': 'Webhook validation failed'}), 400

def handle_payment_success(payment_intent):
    """Process successful payment"""
    logger.info(f"Processing successful payment: {payment_intent.id}")

    try:
        # Extract user and credits from metadata
        user_id = payment_intent.metadata.get('user_id')
        credits = int(payment_intent.metadata.get('credits', 0))

        if not user_id or not credits:
            logger.error(f"Missing metadata in payment intent: {payment_intent.id}")
            return

        # Find the user
        user = User.query.get(user_id)
        if not user:
            logger.error(f"User not found for payment: {user_id}")
            return

        # Add credits to user account
        if hasattr(user, 'credits') and user.credits:
            user.credits.add_credits(credits)
        else:
            # Create new credit record if it doesn't exist
            user_credit = UserCredit(user_id=user.id, credits=credits)
            db.session.add(user_credit)

        db.session.commit()
        logger.info(f"Added {credits} credits to user {user_id}")

    except Exception as e:
        logger.error(f"Error processing payment success: {str(e)}")
        db.session.rollback()

def handle_payment_failure(payment_intent):
    """Process failed payment"""
    logger.info(f"Payment failed: {payment_intent.id}")
    logger.info(f"Failure reason: {payment_intent.last_payment_error}")

    # You could implement additional logic here, such as:
    # - Notifying admins of failed payments
    # - Logging detailed information about failures
    # - Sending email to the customer
    pass

@stripe_blueprint.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        package = request.form.get('package', 'starter')
        if package not in CREDIT_PACKAGES:
            return jsonify({'error': 'Invalid package selected'}), 400

        from auth_utils import get_current_user
        user = get_current_user()
        pkg = CREDIT_PACKAGES[package]

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': pkg['name'],
                        'description': f"One-time purchase of {pkg['credits']} credits"
                    },
                    'unit_amount': pkg['price']
                },
                'quantity': 1
            }],
            mode='payment',
            success_url=request.host_url + 'payment/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.host_url + 'credits',
            metadata={
                'user_id': user.id,
                'credits': pkg['credits']
            }
        )

        return jsonify({
            'id': checkout_session.id
        })
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        return jsonify({'error': str(e)}), 400