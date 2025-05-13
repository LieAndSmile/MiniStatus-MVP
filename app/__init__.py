from flask import Flask
from dotenv import load_dotenv
import os
from app.extensions import db

def create_app():
    # Load environment variables from .env file
    load_dotenv()

    app = Flask(__name__)

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

        # Register blueprints
        app.register_blueprint(admin_bp)
        app.register_blueprint(sync_bp)
        app.register_blueprint(remote_bp)
        app.register_blueprint(ports_bp)

        # Create database tables
        db.create_all()

    return app
