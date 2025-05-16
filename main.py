
from app import app
from google_auth import google_auth  # Import the Google auth blueprint
import routes  # Import routes to register them with the app
from stripe_handler import stripe_blueprint  # Import the Stripe blueprint

# Register blueprints
app.register_blueprint(google_auth)
app.register_blueprint(stripe_blueprint)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
