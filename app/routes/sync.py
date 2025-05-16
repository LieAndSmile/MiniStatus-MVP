# Importing necessary Flask tools and modules
from flask import Blueprint, render_template, redirect, url_for, session, flash, request
from functools import wraps

# Importing a helper function that interprets raw Docker status strings
from app.utils.helpers import interpret_docker_status

# Importing your SQLAlchemy model and database instance
from app.models import Service
from app import db

# Importing datetime to track when services were updated
from datetime import datetime

# Allows running shell commands like "docker" or "systemctl"
import subprocess

# Importing a helper function to check open ports
from app.utils.ports import get_local_listening_ports

# Importing the ServiceSync class
from app.services.sync_service import ServiceSync


# Creating a new Flask "blueprint" for grouping sync-related routes
sync_bp = Blueprint("sync", __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated_function

# -------------------------------
# SYNC DOCKER SERVICES
# -------------------------------
@sync_bp.route("/sync-docker", methods=["GET"])
@admin_required
def sync_docker_services():
    no_auto_tag = request.args.get('no_auto_tag') == '1'
    updated_services, error = ServiceSync.sync_docker(no_auto_tag=no_auto_tag)
    if error:
        flash(error, 'error')
        return redirect(url_for('admin.dashboard'))
    note = "Auto-tagging was skipped." if no_auto_tag else None
    return render_template("sync.html", updated_services=updated_services, note=note)

# -------------------------------
# SYNC SYSTEMD SERVICES
# -------------------------------
@sync_bp.route("/sync-systemd")
@admin_required
def sync_systemd_services():
    no_auto_tag = request.args.get('no_auto_tag') == '1'
    updated_services, error = ServiceSync.sync_systemd(no_auto_tag=no_auto_tag)
    if error:
        flash(error, 'error')
        return redirect(url_for('admin.dashboard'))
    note = "Auto-tagging was skipped." if no_auto_tag else None
    return render_template("sync.html", updated_services=updated_services, note=note)

# -------------------------------
# PORTS CHECK
# -------------------------------
@sync_bp.route("/sync-ports")
@admin_required
def sync_ports():
    no_auto_tag = request.args.get('no_auto_tag') == '1'
    updated_services, error = ServiceSync.sync_ports(no_auto_tag=no_auto_tag)
    if error:
        flash(error, 'error')
        return redirect(url_for('ports.ports_dashboard'))
    session['show_ports_message'] = True
    flash('Successfully checked all ports!', 'success')
    note = "Auto-tagging was skipped." if no_auto_tag else None
    return render_template("sync.html", updated_services=updated_services, note=note)

@sync_bp.route("/sync-all")
@admin_required
def sync_all():
    results = ServiceSync.sync_all()
    
    all_updates = []
    has_errors = False
    
    for service_type, (updates, error) in results.items():
        if error:
            flash(f"{service_type}: {error}", 'error')
            has_errors = True
        all_updates.extend(updates)
    
    if has_errors:
        return redirect(url_for('admin.dashboard'))
        
    return render_template("sync.html", updated_services=all_updates)

