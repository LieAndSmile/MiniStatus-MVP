from flask import Flask
from dotenv import load_dotenv
import os
from app.extensions import csrf, limiter
from app.utils.password import hash_password, migrate_password_in_env


def create_app():
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if not os.path.exists(env_path):
        import secrets

        default_password = "admin123"
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
ADMIN_USERNAME=admin
ADMIN_PASSWORD={hashed_password}

# API
API_KEY=supersecret
"""
        with open(env_path, "w") as f:
            f.write(default_env)
    else:
        migrate_password_in_env(env_path)

    load_dotenv()

    app = Flask(__name__, instance_relative_config=True)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "devkey")
    app.config["WTF_CSRF_ENABLED"] = True
    app.config["WTF_CSRF_TIME_LIMIT"] = None
    app.config["RATELIMIT_STORAGE_URL"] = "memory://"
    app.config["RATELIMIT_HEADERS_ENABLED"] = True

    csrf.init_app(app)
    limiter.init_app(app)

    from app.utils.polymarket import STRATEGY_LABELS, STRATEGY_MODE, BLOCK_REASON_LABELS
    from app.utils.polymarket_constants import STRATEGY_SHORT_HELP

    app.jinja_env.globals["STRATEGY_LABELS"] = STRATEGY_LABELS
    app.jinja_env.globals["STRATEGY_MODE"] = STRATEGY_MODE
    app.jinja_env.globals["STRATEGY_SHORT_HELP"] = STRATEGY_SHORT_HELP
    app.jinja_env.globals["BLOCK_REASON_LABELS"] = BLOCK_REASON_LABELS

    @app.errorhandler(429)
    def ratelimit_handler(e):
        from flask import request, jsonify, render_template, flash, redirect, url_for

        if request.is_json or request.path.startswith("/api"):
            return (
                jsonify(
                    {
                        "error": "Rate limit exceeded",
                        "message": "Too many requests. Please try again later.",
                    }
                ),
                429,
            )
        flash("Too many requests. Please wait a minute before trying again.", "error")
        if request.path.startswith("/admin/login"):
            return render_template("login.html"), 429
        return "Too many requests. Please try again later.", 429

    with app.app_context():
        from app.routes.root import root_bp
        from app.routes.admin import admin_bp
        from app.routes.polymarket import polymarket_bp
        from app.routes.error_handlers import errors_bp

        app.register_blueprint(root_bp)
        app.register_blueprint(admin_bp)
        app.register_blueprint(errors_bp)
        app.register_blueprint(polymarket_bp)

    return app
