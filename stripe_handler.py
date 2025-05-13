
import os
import json
import logging
import stripe
from flask import Blueprint, request, jsonify, session, redirect, url_for
from app import app, db
from models import User, UserCredit

# Configure logging
logger = logging.getLogger(__name__)

# Configure Stripe API key
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
if not stripe.api_key:
    logger.error("STRIPE_SECRET_KEY is not properly configured")
    raise ValueError("Stripe secret key is not configured")

STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')

# Verify required keys are present
if not all([stripe.api_key, STRIPE_WEBHOOK_SECRET, STRIPE_PUBLISHABLE_KEY]):
    logger.error("Missing required Stripe configuration")
    raise ValueError("Missing required Stripe configuration")

# Test connection to Stripe
try:
    stripe.Account.retrieve()
    logger.info("Successfully connected to Stripe API")
except stripe.error.AuthenticationError as e:
    logger.error(f"Stripe authentication failed: {str(e)}")
    raise ValueError("Stripe authentication failed")
    
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')

if not STRIPE_WEBHOOK_SECRET:
    logger.warning("STRIPE_WEBHOOK_SECRET is not set. Webhook verification will fail.")
if not STRIPE_PUBLISHABLE_KEY:
    logger.warning("STRIPE_PUBLISHABLE_KEY is not set. Client-side Stripe integration will fail.")

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
        from routes import get_current_user
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
        data = json.loads(request.data)
        package = data.get('package', 'starter')

        if package not in CREDIT_PACKAGES:
            return jsonify({'error': 'Invalid package selected'}), 400

        # Get user information
        from routes import get_current_user
        user = get_current_user()

        # Get price ID based on package
        price_ids = {
            'starter': os.environ.get('STRIPE_BASIC_PRICE_ID'),
            'popular': os.environ.get('STRIPE_STANDARD_PRICE_ID'),
            'pro': os.environ.get('STRIPE_PRO_PRICE_ID')
        }

        price_id = price_ids.get(package)
        if not price_id:
            return jsonify({'error': 'Invalid package selected'}), 400

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1
            }],
            mode='subscription',
            success_url=request.host_url + 'payment/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.host_url + 'credits',
            metadata={
                'user_id': user.id,
                'package': package
            }
        )

        return jsonify({'sessionId': checkout_session.id})

    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        return jsonify({'error': str(e)}), 400
