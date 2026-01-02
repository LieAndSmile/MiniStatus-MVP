from flask import Blueprint, render_template, flash, redirect, url_for, request
from app.models import Service
from app.services.sync_service import ServiceSync
from app.utils.decorators import admin_required
from app.extensions import db

remote_bp = Blueprint('remote', __name__)

@remote_bp.route('/remote')
@admin_required
def remote_dashboard():
    """Display remote hosts monitoring dashboard"""
    services = Service.query.filter(
        Service.host.isnot(None),
        Service.port.isnot(None),
        Service.is_remote == True
    ).all()
    return render_template('remote.html', services=services)

@remote_bp.route('/remote/sync')
@admin_required
def sync_remote():
    """Trigger remote host sync"""
    updated_services, error = ServiceSync.sync_remote_hosts()
    if error:
        flash(error, 'error')
        return redirect(url_for('remote.remote_dashboard'))
    
    flash(f'Successfully updated {len(updated_services)} remote services', 'success')
    return redirect(url_for('remote.remote_dashboard'))

@remote_bp.route('/remote/add', methods=['POST'])
@admin_required
def add_host():
    """Add a new remote host to monitor"""
    name = request.form.get('name')
    host = request.form.get('host')
    port = request.form.get('port')
    description = request.form.get('description')

    try:
        service = Service(
            name=name,
            host=host,
            port=int(port),
            description=description,
            is_remote=True
        )
        db.session.add(service)
        db.session.commit()
        flash(f'Added new service: {name}', 'success')
    except Exception as e:
        flash(f'Error adding service: {str(e)}', 'error')
        db.session.rollback()

    return redirect(url_for('remote.remote_dashboard'))

@remote_bp.route('/remote/delete/<int:service_id>', methods=['POST'])
@admin_required
def delete_host(service_id):
    """Delete a remote host"""
    service = Service.query.get_or_404(service_id)
    try:
        db.session.delete(service)
        db.session.commit()
        flash(f'Deleted service: {service.name}', 'success')
    except Exception as e:
        flash(f'Error deleting service: {str(e)}', 'error')
        db.session.rollback()

    return redirect(url_for('remote.remote_dashboard'))

# Add some example hosts for testing
@remote_bp.route('/remote/add-examples')
@admin_required
def add_example_hosts():
    """Add example hosts for testing"""
    example_hosts = [
        {
            'name': 'Google HTTPS',
            'host': 'google.com',
            'port': 443,
            'description': 'Google web server (HTTPS)'
        },
        {
            'name': 'GitHub SSH',
            'host': 'github.com',
            'port': 22,
            'description': 'GitHub SSH server'
        },
        {
            'name': 'CloudFlare DNS',
            'host': '1.1.1.1',
            'port': 53,
            'description': 'CloudFlare DNS server'
        }
    ]

    for host in example_hosts:
        if not Service.query.filter_by(name=host['name']).first():
            service = Service(**host, is_remote=True)
            db.session.add(service)
    
    try:
        db.session.commit()
        flash('Added example hosts', 'success')
    except Exception as e:
        flash(f'Error adding example hosts: {str(e)}', 'error')
        db.session.rollback()

    return redirect(url_for('remote.remote_dashboard')) 