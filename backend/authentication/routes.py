# backend/authentication/routes.py
import re
from flask import Blueprint, jsonify, request, session, redirect, url_for, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user, AnonymousUserMixin
from backend.app_factory import db
from backend.logging_config import setup_logging
from backend.decorators import admin_required
from backend.authentication.models import User
from backend.authentication.views import send_otp_email, generate_otp, verify_otp, save_otp, login_with_google, handle_google_callback


auth_bp = Blueprint('auth', __name__)

# Setup logging
logger = setup_logging()


@auth_bp.route('/signup', methods=['POST'])
def signup_post():
    try:
        data = request.get_json()
        email = data.get('email')
        name = data.get('name')
        password = data.get('password')

        if not email or not name or not password:
            logger.warning("Signup attempt with missing fields.")
            return jsonify({'message': 'Please fill out all fields.'}), 400

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            logger.warning("Invalid email format during signup.")
            return jsonify({'message': 'Invalid email address.'}), 400

        if len(password) < 6:
            logger.warning("Password too short during signup.")
            return jsonify({'message': 'Password must be at least 6 characters long.'}), 400

        if not re.match(r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{6,}$', password):
            logger.warning("Password does not meet complexity requirements during signup.")
            return jsonify({'message': 'Password must contain letters, numbers, and symbols.'}), 400

        user = User.query.filter_by(email=email).first()

        if user:
            logger.warning(f"Signup attempt with existing email: {email}")
            return jsonify({'message': 'Email already exists'}), 400

        new_user = User(email=email, name=name, password=generate_password_hash(password, method='pbkdf2:sha256'))
        db.session.add(new_user)
        db.session.commit()

        logger.info(f"New user {email} signed up successfully.")
        return jsonify({'message': 'Signup successful! Please log in.'}), 201

    except Exception as e:
        logger.error(f"Error during signup: {e}")
        return jsonify({'message': 'An error occurred during signup.'}), 500

@auth_bp.route('/login', methods=['GET'])
def login_get():
    """Render the login page."""
    return render_template('login.html')

@auth_bp.route('/login', methods=['POST'])
def login_post():
    """Handle login form submission."""
    try:
        # Determine the content type
        if request.is_json:
            data = request.get_json()
            email = data.get('email')
            password = data.get('password')
            remember = data.get('remember', False)
        else:
            # Handle form data
            email = request.form.get('email')
            password = request.form.get('password')
            remember = True if request.form.get('remember') else False

        if not email or not password:
            logger.warning("Login attempt with missing fields.")
            if request.is_json:
                return jsonify({'message': 'Please fill out all fields.'}), 400
            else:
                return render_template('login.html', error='Please fill out all fields.')

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password, password):
            logger.warning(f"Failed login attempt for email: {email}")
            if request.is_json:
                return jsonify({'message': 'Please check your login details and try again.'}), 400
            else:
                return render_template('login.html', error='Invalid email or password.')

        login_user(user, remember=remember)
        logger.info(f"User {email} logged in successfully.")
        if request.is_json:
            return jsonify({'message': 'Login successful!'}), 200
        else:
            return redirect(url_for('auth.profile'))

    except Exception as e:
        logger.error(f"Error during login: {e}")
        if request.is_json:
            return jsonify({'message': 'An error occurred during login.'}), 500
        else:
            return render_template('login.html', error='An error occurred during login.')

@auth_bp.route('/login/google')
def google_login():
    request_uri, error = login_with_google()
    if error:
        return jsonify({'message': error}), 500
    return redirect(request_uri)

@auth_bp.route('/login/google/callback')
def google_callback():
    user, error = handle_google_callback()
    if error:
        return jsonify({'message': error}), 500
    return redirect(url_for('auth.profile'))

@auth_bp.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login_get'))

@auth_bp.route('/user_profile', methods=['GET'])
@login_required
def get_user_profile():
    try:
        user = current_user
        user_profile = {
            'id': user.id,
            'name': user.name,
            'email': user.email
        }
        logger.info(f"User profile fetched successfully for email: {user.email}")
        return jsonify(user_profile), 200

    except Exception as e:
        logger.error(f"Error fetching user profile: {e}")
        return jsonify({'message': 'An error occurred while fetching user profile.'}), 500

@auth_bp.route('/forgot_password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({'message': 'Email is required.'}), 400

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({'message': 'User not found.'}), 404

    otp = generate_otp()
    save_otp(user, otp)
    send_otp_email(user, otp)

    # Store the verified user ID in the session after OTP is sent
    session['otp_verified_user_id'] = user.id

    return jsonify({'message': 'OTP sent to your email address.'}), 200

@auth_bp.route('/verify_otp', methods=['POST'])
def verify_otp_route():
    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')

    if not email or not otp:
        return jsonify({'message': 'Email and OTP are required.'}), 400

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({'message': 'User not found.'}), 404

    if verify_otp(user, otp):
        # Store the verified user ID in the session after OTP verification
        session['otp_verified_user_id'] = user.id
        return jsonify({'message': 'OTP verified successfully.'}), 200
    else:
        return jsonify({'message': 'Invalid or expired OTP.'}), 400

@auth_bp.route('/reset_password', methods=['POST'])
def reset_password():
    data = request.get_json()
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')

    # Check if new_password and confirm_password match
    if not new_password or not confirm_password or new_password != confirm_password:
        return jsonify({'message': 'Passwords do not match or fields are empty.'}), 400

    # Validate password length
    if len(new_password) < 6:
        logger.warning("Password too short during password reset.")
        return jsonify({'message': 'Password must be at least 6 characters long.'}), 400

    # Validate password complexity
    if not re.match(r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{6,}$', new_password):
        logger.warning("Password does not meet complexity requirements during password reset.")
        return jsonify({'message': 'Password must contain letters, numbers, and symbols.'}), 400

    # Retrieve the user ID from the session
    user_id = session.get('otp_verified_user_id')

    if not user_id:
        return jsonify({'message': 'OTP not verified. Cannot reset password.'}), 403

    user = User.query.get(user_id)

    if not user:
        return jsonify({'message': 'User not found.'}), 404

    # Check if the new password is the same as the current password
    if check_password_hash(user.password, new_password):
        logger.warning("Attempt to reset password to the current password.")
        return jsonify({'message': 'New password cannot be the same as the current password.'}), 400

    # Reset the password and clear the OTP verification status
    user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
    db.session.commit()

    # Clear the session variable after password reset
    session.pop('otp_verified_user_id', None)

    return jsonify({'message': 'Password reset successfully.'}), 200

# @auth_bp.route('/logout', methods=['POST'])
# @login_required
# def logout():
#     try:
#         if not isinstance(current_user, AnonymousUserMixin):
#             logger.info(f"User {current_user.email} logged out successfully.")
#         else:
#             logger.info("Anonymous user logged out successfully.")
        
#         logout_user()
#         # return jsonify({'message': 'Logout successful!'}), 200
#         return redirect(url_for('auth.login'))
    
#     except Exception as e:
#         logger.error(f"Error during logout: {e}")
#         return jsonify({'message': 'An error occurred during logout.'}), 500

@auth_bp.route('/admin/users', methods=['GET'])
@login_required
@admin_required
def list_users():
    try:
        users = User.query.all()
        user_list = [{'id': user.id, 'name': user.name, 'email': user.email} for user in users]
        logger.info("Admin user listed all users.")
        return jsonify(user_list), 200

    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return jsonify({'message': 'An error occurred while listing users.'}), 500
