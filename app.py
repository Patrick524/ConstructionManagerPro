import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create base class for SQLAlchemy models
class Base(DeclarativeBase):
    pass

# Initialize extensions
db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()

# Create the app
app = Flask(__name__)
app.config['FLASK_APP'] = 'main.py'
app.secret_key = os.environ.get("SESSION_SECRET", "temporary_secret_key_for_development")

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Session configuration
app.config["SESSION_COOKIE_SECURE"] = False  # Set to True in production
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = 3600  # Session expires after 1 hour

# Initialize extensions with the app
db.init_app(app)
login_manager.init_app(app)

# Initialize Flask-Migrate
from flask_migrate import Migrate
migrate = Migrate(app, db)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

with app.app_context():
    # Import models and routes after db is initialized to avoid circular imports
    import models
    import routes

    # Create database tables
    db.create_all()

    # Setup user loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        user = models.User.query.get(int(user_id))
        # Return None for inactive users to automatically log them out
        if user and not user.active:
            return None
        return user
