
from app import app
import routes  # Import routes to register them with the app
from google_auth import google_auth  # Import the Google auth blueprint
from stripe_handler import stripe_blueprint  # Import the Stripe blueprint

# Register the blueprints
app.register_blueprint(google_auth, url_prefix='/auth')
app.register_blueprint(stripe_blueprint, url_prefix='/api/stripe')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
