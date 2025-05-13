        import os
        import logging
        from datetime import datetime
        from app import db
        from flask_login import UserMixin

        # Configure logging
        logging.basicConfig(level=logging.DEBUG)

        class User(UserMixin, db.Model):
            """User model for tracking users and their credits"""
            id = db.Column(db.Integer, primary_key=True)
            session_id = db.Column(db.String(64), unique=True, nullable=True)
            email = db.Column(db.String(120), unique=True, nullable=True)
            username = db.Column(db.String(64), nullable=True)
            google_id = db.Column(db.String(64), unique=True, nullable=True)
            is_authenticated = db.Column(db.Boolean, default=False)
            created_at = db.Column(db.DateTime, default=datetime.utcnow)
            endcards = db.relationship('Endcard', backref='user', lazy='dynamic')
            credits = db.relationship('UserCredit', backref='user', uselist=False)

            def __repr__(self):
                if self.email:
                    return f'<User {self.id}: {self.email}>'
                return f'<User {self.id}>'

            # Required for Flask-Login
            def get_id(self):
                return str(self.id)

            @property
            def is_active(self):
                return True

            @property
            def is_anonymous(self):
                return not self.is_authenticated

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
            credits = db.Column(db.Integer, default=0)  
            last_updated = db.Column(db.DateTime, default=datetime.utcnow)

            def __repr__(self):
                return f'<UserCredit {self.id} - User {self.user_id} - Credits {self.credits}>'

            @classmethod
            def get_user_credits(cls, user_id):
                """Get user's credit record, creating if necessary"""
                try:
                    credit_record = cls.query.filter_by(user_id=user_id).first()
                    if not credit_record:
                        credit_record = cls(user_id=user_id, credits=0)
                        db.session.add(credit_record)
                        db.session.commit()
                    return credit_record
                except Exception as e:
                    logging.error(f"Error getting user credits: {str(e)}")
                    db.session.rollback()
                    raise

            def deduct_credit(self):
                """Deduct one credit with proper error handling"""
                from flask import session
                try:
                    if self.credits > 0:
                        self.credits -= 1
                        self.last_updated = datetime.utcnow()
                        db.session.commit()
                        session['credits'] = self.credits
                        return True
                    return False
                except Exception as e:
                    logging.error(f"Error deducting credit: {str(e)}")
                    db.session.rollback()
                    raise

            def add_credits(self, amount):
                """Add credits with proper error handling"""
                from flask import session
                try:
                    self.credits += amount
                    self.last_updated = datetime.utcnow()
                    db.session.commit()
                    session['credits'] = self.credits
                    return True
                except Exception as e:
                    logging.error(f"Error adding credits: {str(e)}")
                    db.session.rollback()
                    raise

            def sync_session_credits(self):
                """Synchronize session credits with database"""
                from flask import session
                session['credits'] = self.credits

        class SubscriptionTier(db.Model):
            """Subscription tier model"""
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(50), unique=True, nullable=False)
            price = db.Column(db.Float, nullable=False)
            monthly_conversions = db.Column(db.Integer, nullable=False)
            max_resolution = db.Column(db.String(20), nullable=False)
            has_api_access = db.Column(db.Boolean, default=False)
            has_priority_support = db.Column(db.Boolean, default=False)
            stripe_product_id = db.Column(db.String(100), unique=True)
            stripe_price_id = db.Column(db.String(100), unique=True)

            @staticmethod
            def get_basic_tier():
                return {
                    'name': 'Basic',
                    'price': 10.0,
                    'monthly_conversions': 5,  # 5 credits
                    'max_resolution': '720p',
                    'has_api_access': False,
                    'has_priority_support': False,
                    'stripe_price_id': None,  # Will need to be updated with actual Stripe price ID
                    'stripe_product_id': None #Will need to be updated with actual Stripe product ID

                }

            @staticmethod
            def get_standard_tier():
                return {
                    'name': 'Standard',
                    'price': 25.0,
                    'monthly_conversions': 20,  # 20 credits
                    'max_resolution': '1080p',
                    'has_api_access': True,
                    'has_priority_support': False,
                    'stripe_price_id': None,  # Will need to be updated with actual Stripe price ID
                    'stripe_product_id': None #Will need to be updated with actual Stripe product ID
                }

            @staticmethod
            def get_pro_tier():
                return {
                    'name': 'Pro',
                    'price': 45.0,
                    'monthly_conversions': 50,  # 50 credits
                    'max_resolution': '4K',
                    'has_api_access': True,
                    'has_priority_support': True,
                    'stripe_price_id': None,  # Will need to be updated with actual Stripe price ID
                    'stripe_product_id': None #Will need to be updated with actual Stripe product ID
                }