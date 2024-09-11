# backend/app_factory.py
from __future__ import print_function
from flask import Flask, jsonify
from flask_login import LoginManager
from sqlalchemy.exc import OperationalError
from backend.init_db import db
from backend.authentication.models import User
from backend.authentication.views import create_admin_users

def create_app(config_class='backend.config.Config'):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({'message': 'Unauthorized access. Please log in.'}), 401

    # Import and register blueprints
    from backend.authentication.routes import auth_bp as auth_blueprint
    app.register_blueprint(auth_blueprint)

    from backend.expense_tracker.routes import expense_tracker_bp as expense_tracker_blueprint
    app.register_blueprint(expense_tracker_blueprint, url_prefix='/expense-tracker')

    with app.app_context():
        try:
            db.create_all()
            create_admin_users()
        except OperationalError as e:
            app.logger.error(f"OperationalError during database initialization: {e}")

    return app
