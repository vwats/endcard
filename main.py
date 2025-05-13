
from app import app
import routes  # Import routes to register them with the app
from google_auth import google_auth  # Import the Google auth blueprint

# Register the blueprints
app.register_blueprint(google_auth, url_prefix='')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
