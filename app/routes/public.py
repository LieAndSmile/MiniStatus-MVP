# app/routes/public.py

from flask import Blueprint, render_template
from app.utils.helpers import get_system_stats, get_system_identity, get_all_quick_links

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
def index():
    """Homepage dashboard"""
    system_stats = get_system_stats()
    system_identity = get_system_identity()
    quick_links = get_all_quick_links()
    # Add more data for widgets as needed
    return render_template('public/home.html',
                           system_stats=system_stats,
                           system_identity=system_identity,
                           quick_links=quick_links)
