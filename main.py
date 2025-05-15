
from app import app
import routes  # Import routes to register them with the app
from google_auth import google_auth  # Import the Google auth blueprint
from stripe_handler import stripe_blueprint  # Import the Stripe blueprint

# Register blueprints
app.register_blueprint(google_auth, url_prefix='/auth')
app.register_blueprint(stripe_blueprint, url_prefix='/api/stripe')

# Check if environment variables are set and log status
import os
import logging

logger = logging.getLogger(__name__)

stripe_vars = [
    'STRIPE_SECRET_KEY', 'STRIPE_PUBLISHABLE_KEY', 'STRIPE_WEBHOOK_SECRET',
    'STRIPE_BASIC_PRICE_ID', 'STRIPE_STANDARD_PRICE_ID', 'STRIPE_PRO_PRICE_ID',
    'STRIPE_BASIC_PRODUCT_ID', 'STRIPE_STANDARD_PRODUCT_ID',
    'STRIPE_PRO_PRODUCT_ID'
]

for var in stripe_vars:
    if not os.environ.get(var):
        logger.warning(f"Environment variable {var} is not set")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
