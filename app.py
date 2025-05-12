
import os
import logging
from datetime import timedelta

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
# Suppress excessive logging
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logging.getLogger('gunicorn.error').setLevel(logging.WARNING)
logging.getLogger('gunicorn.access').setLevel(logging.WARNING)

class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with the Base class and production connection pool settings
db = SQLAlchemy(model_class=Base, engine_options={
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_timeout': 900,
    'pool_size': 20,
    'max_overflow': 5,
    'pool_use_lifo': True
})

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "endcard_converter_dev_secret")
# Session security settings
app.config['SESSION_COOKIE_SECURE'] = True  # Only send cookies over HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access to session cookie
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # Session expiry

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///endcards.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB total upload size (for both files + form data)
app.config["REQUEST_TIMEOUT"] = 120  # 2 minutes timeout for large uploads
app.config["UPLOAD_FOLDER"] = "tmp_uploads"

# Google OAuth config
app.config["GOOGLE_CLIENT_ID"] = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
app.config["GOOGLE_CLIENT_SECRET"] = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")

# Initialize the app with SQLAlchemy
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "google_auth.login"  # Redirect to google_login route when login is required

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Create upload folder if it doesn't exist
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Create database tables
with app.app_context():
    # Import models here to make sure they're registered with SQLAlchemy
    from models import User, Endcard, UserCredit
    db.create_all()
