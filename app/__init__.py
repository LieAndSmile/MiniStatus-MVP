from flask import Flask
from dotenv import load_dotenv
import os
from app.extensions import db
from app.routes.admin import ensure_default_tags
from app.utils.password import hash_password, migrate_password_in_env

def create_app():
    # Auto-create .env file if it doesn't exist
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if not os.path.exists(env_path):
        import secrets
        # Hash the default password
        default_password = 'admin123'
        hashed_password = hash_password(default_password)
        default_env = f"""# Flask config
FLASK_APP=run.py
FLASK_ENV=production
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=False

# Security
SECRET_KEY={secrets.token_hex(32)}

# Admin auth - CHANGE THESE!
# Note: ADMIN_PASSWORD is stored as a bcrypt hash for security
ADMIN_USERNAME=admin
ADMIN_PASSWORD={hashed_password}

# API
API_KEY=supersecret
"""
        with open(env_path, 'w') as f:
            f.write(default_env)
    else:
        # Migrate existing plain text password to hashed password
        migrate_password_in_env(env_path)
    
    # Load environment variables from .env file
    load_dotenv()

    app = Flask(__name__, instance_relative_config=True)

    # Basic config
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ministatus.db'
    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "devkey")

    # Init DB with app
    db.init_app(app)

    with app.app_context():
        # Import routes here to avoid circular imports
        from app.routes.admin import admin_bp
        from app.routes.sync import sync_bp
        from app.routes.remote import remote_bp
        from app.routes.ports import ports_bp
        from app.routes.public import public_bp
        from app.routes.api import api_bp

        # Register blueprints - public routes first
        app.register_blueprint(public_bp)  # For public routes
        app.register_blueprint(admin_bp)  # Admin routes (no prefix, handled in blueprint)
        app.register_blueprint(sync_bp)
        app.register_blueprint(remote_bp)
        app.register_blueprint(ports_bp)
        app.register_blueprint(api_bp)  # API routes

        # Create database tables
        db.create_all()

        ensure_default_tags()

    return app
