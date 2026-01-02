# Importing necessary Flask tools and modules
from flask import Blueprint, render_template, redirect, url_for, session, flash, request
from functools import wraps

# Importing your SQLAlchemy model and database instance
from app.models import Service
from app.extensions import db

# Importing datetime to track when services were updated
from datetime import datetime

# Allows running shell commands like "systemctl"
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
    
    # Calculate summary statistics
    total = len(updated_services)
    new_services = len([s for s in updated_services if 'Added' in s])
    updated_count = total - new_services
    
    # Create a user-friendly summary message
    if total == 0:
        flash('No systemd services found or updated.', 'info')
    else:
        summary_parts = []
        if new_services > 0:
            summary_parts.append(f"{new_services} new")
        if updated_count > 0:
            summary_parts.append(f"{updated_count} updated")
        
        summary = f"Synced {total} systemd service{'s' if total != 1 else ''}"
        if summary_parts:
            summary += f" ({', '.join(summary_parts)})"
        
        if no_auto_tag:
            summary += " • Auto-tagging was skipped"
        
        flash(summary, 'success')
    
    # Redirect back to dashboard instead of showing full list
    return redirect(url_for('admin.dashboard'))

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
    
    # Calculate summary
    total = len(updated_services)
    if total == 0:
        flash('No ports found or updated.', 'info')
    else:
        summary = f"Synced {total} port{'s' if total != 1 else ''}"
        if no_auto_tag:
            summary += " • Auto-tagging was skipped"
        flash(summary, 'success')
    
    return redirect(url_for('ports.ports_dashboard'))

@sync_bp.route("/sync-all")
@admin_required
def sync_all():
    results = ServiceSync.sync_all()
    
    all_updates = []
    has_errors = False
    summaries = []
    
    for service_type, (updates, error) in results.items():
        if error:
            flash(f"{service_type}: {error}", 'error')
            has_errors = True
        else:
            count = len(updates)
            if count > 0:
                summaries.append(f"{service_type}: {count}")
        all_updates.extend(updates)
    
    if has_errors:
        return redirect(url_for('admin.dashboard'))
    
    # Show summary instead of full list
    if summaries:
        flash(f"Synced all services ({', '.join(summaries)})", 'success')
    else:
        flash('No services updated.', 'info')
    
    return redirect(url_for('admin.dashboard'))

