# backend/authentication/views.py
import json
import random
import logging
import requests
import sib_api_v3_sdk
from flask import current_app, request
from flask_login import current_user, login_user
from backend.app_factory import db
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import OperationalError
from backend.authentication.models import User
from sib_api_v3_sdk.rest import ApiException
from backend.logging_config import setup_logging
from oauthlib.oauth2 import WebApplicationClient

logger = setup_logging()


# Load Google Auth configuration
def load_google_auth_config():
    try:
        json_path = 'backend/google_auth_config.json'
        with open(json_path, 'r') as f:
            google_auth_config = json.load(f)
        return google_auth_config
    except FileNotFoundError:
        current_app.logger.error("Google auth configuration file not found.")
        return None
    except json.JSONDecodeError:
        current_app.logger.error("Error decoding the Google auth configuration file.")
        return None

google_auth_config = load_google_auth_config()

if google_auth_config:
    GOOGLE_CLIENT_ID = google_auth_config['google_client_id']
    GOOGLE_CLIENT_SECRET = google_auth_config['google_client_secret']
    GOOGLE_DISCOVERY_URL = google_auth_config['google_discovery_url']
else:
    GOOGLE_CLIENT_ID = None
    GOOGLE_CLIENT_SECRET = None
    GOOGLE_DISCOVERY_URL = None

# Create a Google OAuth client
google_client = WebApplicationClient(GOOGLE_CLIENT_ID) if GOOGLE_CLIENT_ID else None

# Function to get Google's provider configuration
def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()

# Function to handle Google login
def login_with_google():
    if not google_client:
        return None, "Google OAuth client is not configured."

    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    request_uri = google_client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],
    )
    return request_uri, None

# Function to handle Google login callback
def handle_google_callback():
    if not google_client:
        return None, "Google OAuth client is not configured."

    code = request.args.get("code")
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]

    token_url, headers, body = google_client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    google_client.parse_request_body_response(json.dumps(token_response.json()))

    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = google_client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)
    user_info = userinfo_response.json()

    if user_info.get("email_verified"):
        unique_id = user_info.get("sub")
        users_email = user_info.get("email")
        picture = user_info.get("picture")
        users_name = f"{user_info.get('given_name', '')} {user_info.get('family_name', '')}"
    else:
        return None, "User email not available or not verified by Google."

    # Check if user already exists
    user = User.query.filter_by(email=users_email).first()

    if not user:
        # Create a new user
        user = User(
            email=users_email, name=users_name, password=generate_password_hash(unique_id, method='pbkdf2:sha256')
        )
        db.session.add(user)
        db.session.commit()

    # Log in the user
    login_user(user)

    return user, None

def create_admin_users():
    try:
        # Load admin users details from JSON file
        json_path = 'backend/admin_user.json'
        with open(json_path, 'r') as f:
            admin_data = json.load(f)
        
        for admin_details in admin_data.get('admins', []):
            admin_user = User.query.filter_by(name=admin_details['name']).first()
            if admin_user is None:
                admin_user = User(
                    name=admin_details['name'],
                    email=admin_details['email'],
                    password=generate_password_hash(admin_details['password'], method='pbkdf2:sha256'),
                    is_admin=admin_details['is_admin']
                )
                db.session.add(admin_user)
                logger.info(f"Admin user '{admin_details['name']}' created successfully.")
            else:
                logging.info(f"Admin user '{admin_details['name']}' already exists.")
        
        db.session.commit()
    except FileNotFoundError:
        logger.error("Admin user JSON file not found.")
    except json.JSONDecodeError:
        logger.error("Error decoding the admin user JSON file.")
    except OperationalError as e:
        logger.error(f"OperationalError when creating admin users: {e}")

# Function to load email configuration
def load_email_config():
    try:
        json_path = 'backend/email_config.json'
        with open(json_path, 'r') as f:
            email_data = json.load(f)
            return email_data
    except FileNotFoundError:
        current_app.logger.error("Email configuration file not found.")
        return None
    except json.JSONDecodeError:
        current_app.logger.error("Error decoding the email configuration file.")
        return None

# Function to generate a 6-digit OTP
def generate_otp():
    return random.randint(100000, 999999)

# Function to send OTP to the user's email using Brevo
def send_otp_email(user, otp):
    email_config = load_email_config()
    if not email_config:
        return

    try:
        api_key = email_config.get('api_key')

        # Initialize Brevo API client
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = api_key
        api_client = sib_api_v3_sdk.ApiClient(configuration)
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(api_client)

        admin_users = User.query.filter_by(is_admin=True).all()

        sender_email = current_user.email
        sender_name = current_user.name

        for admin in admin_users:
            send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                to=[{"email": sender_email, "name": sender_name}],
                sender={"name": admin.name, "email": admin.email},
                subject="Your OTP for Password Reset",
                html_content=f"Dear {sender_name},<br>Your OTP for password reset is <strong>{otp}</strong>. This OTP is valid for 10 minutes.<br><br>Warm Regards,<br>The {admin.name} Team"
            )

            try:
                api_response = api_instance.send_transac_email(send_smtp_email)
                current_app.logger.info(f"OTP email sent successfully: {api_response}")
            except ApiException as e:
                current_app.logger.error(f"Exception when calling TransactionalEmailsApi->send_transac_email: {e}")

    except Exception as e:
        current_app.logger.error(f"Failed to send OTP email: {str(e)}")

# Function to save hashed OTP and timestamp in the user's record
def save_otp(user, otp):
    hashed_otp = generate_password_hash(str(otp), method='pbkdf2:sha256')
    user.otp = hashed_otp
    user.otp_created_at = datetime.utcnow()
    db.session.commit()

# Function to verify the hashed OTP
def verify_otp(user, otp):
    if user.otp and check_password_hash(user.otp, str(otp)):
        now = datetime.utcnow()
        otp_age = now - user.otp_created_at
        if otp_age <= timedelta(minutes=10):
            return True
    return False
