# app/routes/public.py

from flask import Blueprint, render_template, request
from app.models import Service

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
def index():
    """Main status page"""
    filter_status = request.args.get('filter', 'all')
    services = Service.query

    if filter_status in ['up', 'down', 'degraded']:
        services = services.filter(Service.status == filter_status)
    
    services = services.all()
    return render_template('public/index.html', services=services, filter=filter_status)
