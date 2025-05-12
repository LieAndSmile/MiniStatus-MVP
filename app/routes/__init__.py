from .admin import admin_bp
from .api import api_bp
from .sync import sync_bp
from .error_handlers import errors_bp

def register_blueprints(app):
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(sync_bp)
    app.register_blueprint(errors_bp)
