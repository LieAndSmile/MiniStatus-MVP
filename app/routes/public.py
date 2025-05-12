# app/routes/public.py

from flask import Blueprint, render_template, request
from app.models import Service

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
def public_dashboard():
    status_filter = request.args.get('filter')
    if status_filter in ['up', 'down', 'degraded']:
        services = Service.query.filter_by(status=status_filter).all()
    else:
        services = Service.query.all()

    status_counts = {
        'up': Service.query.filter_by(status='up').count(),
        'down': Service.query.filter_by(status='down').count(),
        'degraded': Service.query.filter_by(status='degraded').count()
    }

    return render_template('public/index.html', services=services, counts=status_counts)
