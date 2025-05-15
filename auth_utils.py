
import logging
from functools import wraps
from flask import session, flash, redirect, url_for
from flask_login import current_user
from app import db
from models import UserCredit

logger = logging.getLogger(__name__)

def get_current_user():
    """Get or create a user based on session ID or logged in status"""
    try:
        # If user is authenticated via Flask-Login in production
        if current_user.is_authenticated:
            # Make sure the user has a credit record
            if not hasattr(current_user, 'credits') or not current_user.credits:
                user_credit = UserCredit(user_id=current_user.id)
                db.session.add(user_credit)
                db.session.commit()

            # Store credits in session for easy access
            if hasattr(current_user, 'credits') and current_user.credits:
                session['credits'] = current_user.credits.credits

            return current_user
    except Exception as e:
        logger.error(f"Error in get_current_user: {str(e)}")
        db.session.rollback()
    return None

def manage_session(f):
    """Decorator to ensure consistent session management"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            user = get_current_user()
            if user and user.is_authenticated:
                # Ensure credits are always synced
                if hasattr(user, 'credits') and user.credits:
                    session['credits'] = user.credits.credits
                if 'user_id' not in session:
                    session['user_id'] = user.id
            else:
                # Clear sensitive session data if user is not authenticated
                session.pop('credits', None)
                session.pop('user_id', None)
            
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Session management error: {str(e)}")
            db.session.rollback()
            flash('An error occurred while managing your session', 'error')
            return redirect(url_for('index'))
    return decorated_function
