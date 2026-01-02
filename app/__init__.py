from flask import Flask
from dotenv import load_dotenv
import os
from app.extensions import db, csrf, limiter
from app.routes.admin import ensure_default_tags
from app.utils.password import hash_password, migrate_password_in_env

def migrate_database_schema():
    """Migrate database schema for new fields"""
    from sqlalchemy import text, inspect
    try:
        # Check if tag table exists
        result = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='tag'"))
        if result.fetchone():
            # Check if is_public column exists in Tag table
            result = db.session.execute(text("PRAGMA table_info(tag)"))
            columns = [row[1] for row in result]  # Column name is at index 1
            
            if 'is_public' not in columns:
                # Add is_public column to Tag table
                db.session.execute(text("ALTER TABLE tag ADD COLUMN is_public BOOLEAN DEFAULT 0"))
                db.session.commit()
                print("✓ Migrated Tag table: added is_public column")
            else:
                print("✓ Tag table already has is_public column")
    except Exception as e:
        # If migration fails, it might be because we're not using SQLite
        try:
            # Try alternative method for non-SQLite databases
            inspector = inspect(db.engine)
            if 'tag' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('tag')]
                if 'is_public' not in columns:
                    db.session.execute(text("ALTER TABLE tag ADD COLUMN is_public BOOLEAN DEFAULT 0"))
                    db.session.commit()
                    print("✓ Migrated Tag table: added is_public column")
        except Exception as e2:
            print(f"Migration note: {e2}")
        db.session.rollback()

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
    
    # CSRF Protection
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['WTF_CSRF_TIME_LIMIT'] = None  # No time limit on CSRF tokens
    
    # Rate Limiting Configuration
    app.config['RATELIMIT_STORAGE_URL'] = 'memory://'  # Use in-memory storage (simple, no Redis needed)
    app.config['RATELIMIT_HEADERS_ENABLED'] = True  # Include rate limit headers in responses

    # Init extensions with app
    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    
    # Custom error handler for rate limit exceeded
    @app.errorhandler(429)
    def ratelimit_handler(e):
        from flask import request, jsonify, render_template
        # Check if request expects JSON (API) or HTML (web)
        if request.is_json or request.path.startswith('/api'):
            return jsonify({
                'error': 'Rate limit exceeded',
                'message': 'Too many requests. Please try again later.'
            }), 429
        # For HTML requests (like login page), flash a message and redirect
        from flask import flash, redirect, url_for
        flash('Too many requests. Please wait a minute before trying again.', 'error')
        if request.path.startswith('/admin/login'):
            return render_template('login.html'), 429
        return 'Too many requests. Please try again later.', 429

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
        
        # Exempt API routes from CSRF (they use API keys instead)
        csrf.exempt(api_bp)

        # Create database tables
        db.create_all()

        # Migrate database schema if needed (must run before ensure_default_tags)
        migrate_database_schema()

        # Ensure default tags exist (after migration)
        ensure_default_tags()

    return app
