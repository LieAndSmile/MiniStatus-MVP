# app/routes/public.py

from flask import Blueprint, render_template, request
from app.models import Service

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
def index():
    """Main status page"""
    services = Service.query.all()
    return render_template('index.html', services=services)
