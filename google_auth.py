import json
import os
import logging
import requests
from flask import Blueprint, redirect, request, url_for, session, flash
from flask_login import login_user, logout_user, login_required, current_user
from oauthlib.oauth2 import WebApplicationClient
from app import app, db
from models import User, UserCredit

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# Setup the Blueprint
google_auth = Blueprint("google_auth", __name__)

# OAuth client setup with production configuration
client = WebApplicationClient(GOOGLE_CLIENT_ID)

# Logging setup
logger = logging.getLogger(__name__)

@google_auth.route("/google_login")
def login():
    """
    Google login route - redirects to Google's OAuth page
    """
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # Use request-based redirect URI for development and production
    if 'replit.dev' in request.host:
        redirect_uri = request.url_root.rstrip('/') + url_for('google_auth.callback')
    else:
        redirect_uri = "https://endcardconterer.com/auth/callback"

    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=redirect_uri,
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)

@google_auth.route("/callback")
def callback():
    """
    Google callback route - processes the response from Google
    """
    logger.info("Google callback received")

    # Get authorization code Google sent back
    code = request.args.get("code")

    # Find out what URL to hit to get tokens
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    token_endpoint = google_provider_cfg["token_endpoint"]

    # Use fixed production redirect URI
    redirect_uri = "https://endcardconterer.com/auth/callback"

    # Prepare and send request to get tokens
    authorization_response = f"https://endcardconterer.com{request.path}?{request.query_string.decode()}"
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=authorization_response,
        redirect_url=redirect_uri,
        code=code,
    )

    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    # Parse the tokens
    client.parse_request_body_response(json.dumps(token_response.json()))

    # Get user info from Google
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    # Verify the user's email is verified by Google
    if userinfo_response.json().get("email_verified"):
        google_id = userinfo_response.json()["sub"]
        users_email = userinfo_response.json()["email"]
        users_name = userinfo_response.json().get("given_name", users_email.split('@')[0])

        logger.info(f"Authenticated user: {users_email}")

        # Check if user exists
        user = User.query.filter_by(google_id=google_id).first()

        if not user:
            # Check if there's an existing anonymous user with the same session ID
            session_id = session.get('user_session_id')
            anonymous_user = None

            if session_id:
                anonymous_user = User.query.filter_by(session_id=session_id).first()

            if anonymous_user:
                # Update the anonymous user with Google info
                anonymous_user.google_id = google_id
                anonymous_user.email = users_email
                anonymous_user.username = users_name
                anonymous_user.is_authenticated = True
                user = anonymous_user
                logger.info(f"Updated anonymous user with Google info: {users_email}")
            else:
                # Create a new user
                user = User(
                    google_id=google_id,
                    email=users_email,
                    username=users_name,
                    is_authenticated=True
                )
                db.session.add(user)
                db.session.flush()

                # Initialize user credits - 3 free credits for new users
                user_credit = UserCredit(user_id=user.id, credits=3)
                db.session.add(user_credit)
                logger.info(f"Created new user: {users_email}")

            db.session.commit()

        # Log in the user
        login_user(user)

        # Update session
        session['user_id'] = user.id
        if user.credits:
            session['credits'] = user.credits.credits

        flash(f"Welcome, {user.username}!", "success")
        return redirect(url_for("index"))
    else:
        flash("Google authentication failed. Please ensure your Google account has a verified email.", "error")
        return redirect(url_for("index"))

@google_auth.route("/logout")
@login_required
def logout():
    """
    Logout route
    """
    logout_user()

    # Clear session, but keep some values
    user_session_id = session.get('user_session_id')

    # Clear session
    session.clear()

    # Restore anonymous session ID if it existed
    if user_session_id:
        session['user_session_id'] = user_session_id

    flash("You have been logged out.", "info")
    return redirect(url_for("index"))