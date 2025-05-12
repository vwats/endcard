import os
import logging
from datetime import datetime
from app import db

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class User(db.Model):
    """User model for tracking users and their credits"""
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    endcards = db.relationship('Endcard', backref='user', lazy='dynamic')
    credits = db.relationship('UserCredit', backref='user', uselist=False)

    def __repr__(self):
        return f'<User {self.id}>'

class Endcard(db.Model):
    """Endcard model for storing conversion data"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Portrait file data
    portrait_created = db.Column(db.Boolean, default=False)
    portrait_filename = db.Column(db.String(255))
    portrait_file_type = db.Column(db.String(20))  # 'image' or 'video'
    portrait_file_size = db.Column(db.Integer)  # Size in bytes
    portrait_data_url = db.Column(db.Text)  # Base64 encoded data URL
    
    # Landscape file data
    landscape_created = db.Column(db.Boolean, default=False)
    landscape_filename = db.Column(db.String(255))
    landscape_file_type = db.Column(db.String(20))  # 'image' or 'video'
    landscape_file_size = db.Column(db.Integer)  # Size in bytes
    landscape_data_url = db.Column(db.Text)  # Base64 encoded data URL

    def __repr__(self):
        return f'<Endcard {self.id}>'

    @property
    def is_video(self):
        """Determine if this endcard contains video content"""
        return self.portrait_file_type == 'video' or self.landscape_file_type == 'video'

class UserCredit(db.Model):
    """User credits model for tracking available credits"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    credits = db.Column(db.Integer, default=3)  # Default 3 free credits for new users
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<UserCredit {self.id} - User {self.user_id} - Credits {self.credits}>'

    def deduct_credit(self):
        """Deduct one credit and return True if successful, False if not enough credits"""
        if self.credits > 0:
            self.credits -= 1
            self.last_updated = datetime.utcnow()
            return True
        return False

    def add_credits(self, amount):
        """Add credits to user account"""
        self.credits += amount
        self.last_updated = datetime.utcnow()