
import logging
from flask import session
from flask_login import current_user
from app import db
from models import UserCredit

logger = logging.getLogger(__name__)

def get_current_user():
    """Get or create a user based on session ID or logged in status"""
    try:
        # If user is authenticated via Flask-Login
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

    # For unauthenticated users or errors, don't create session or credits
    return None
