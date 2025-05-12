import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with the Base class
db = SQLAlchemy(model_class=Base)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "endcard_converter_dev_secret")

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///endcards.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 2.5 * 1024 * 1024  # 2.5MB max for each file
app.config["UPLOAD_FOLDER"] = "tmp_uploads"

# Initialize the app with SQLAlchemy
db.init_app(app)


# Create upload folder if it doesn't exist
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Create database tables
with app.app_context():
    # Import models here to make sure they're registered with SQLAlchemy
    from models import User, Endcard, UserCredit
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)