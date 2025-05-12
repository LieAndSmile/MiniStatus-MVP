from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import os

db = SQLAlchemy()

def create_app():
    # Load environment variables from .env file
    load_dotenv()

    app = Flask(__name__)

    # Basic config
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ministatus.db'
    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "devkey")

    # Init DB with app
    db.init_app(app)

    # Register all modular route blueprints
    from .routes import register_blueprints
    register_blueprints(app)

    return app
