from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from app.models import Service
from app.extensions import db
from app.utils.system_check import has_docker, has_systemctl
from functools import wraps
import os

admin_bp = Blueprint("admin", __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route("/")
def index():
    services = Service.query.all()
    return render_template("index.html", services=services)

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Debug print
        print(f"Login attempt - Username: {username}, Expected: {os.getenv('ADMIN_USERNAME')}")
        print(f"Password attempt - Password: {password}, Expected: {os.getenv('ADMIN_PASSWORD')}")
        
        if username == os.getenv('ADMIN_USERNAME') and password == os.getenv('ADMIN_PASSWORD'):
            session['authenticated'] = True
            flash('Successfully logged in!', 'success')
            return redirect(url_for('admin.dashboard'))
        flash('Invalid credentials. Please try again.', 'error')
    
    return render_template("login.html")

@admin_bp.route("/logout")
def logout():
    session.pop("authenticated", None)
    flash('Successfully logged out.', 'success')
    return redirect(url_for("admin.login"))

@admin_bp.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("authenticated"):
        return redirect(url_for("admin.login"))

    if request.method == "POST":
        name = request.form["name"]
        status = request.form["status"]
        description = request.form["description"]

        existing = Service.query.filter_by(name=name).first()
        if existing:
            flash("Service with that name already exists!", "warning")
        else:
            new_service = Service(
                name=name,
                status=status,
                description=description,
                last_updated=datetime.utcnow()
            )
            db.session.add(new_service)
            db.session.commit()
            flash("Service added!", "success")

        return redirect(url_for("admin.admin"))

    filter_status = request.args.get("status")
    query = Service.query
    if filter_status in ['up', 'down', 'degraded']:
        query = query.filter_by(status=filter_status)

    services = query.all()

    return render_template(
        "admin.html",
        services=services,
        has_docker=has_docker(),
        has_systemctl=has_systemctl(),
        current_filter=filter_status
    )

@admin_bp.route("/update/<int:service_id>", methods=["POST"])
def update_service(service_id):
    if not session.get("authenticated"):
        return redirect(url_for("admin.login"))

    new_status = request.form["status"]
    service = Service.query.get_or_404(service_id)
    service.status = new_status
    service.last_updated = datetime.utcnow()
    db.session.commit()
    flash(f"Updated status for {service.name}!", "success")
    return redirect(url_for("admin.admin"))

@admin_bp.route("/delete/<int:service_id>", methods=["POST"])
def delete_service(service_id):
    if not session.get("authenticated"):
        return redirect(url_for("admin.login"))

    service = Service.query.get_or_404(service_id)
    db.session.delete(service)
    db.session.commit()
    flash(f"Deleted service: {service.name}", "info")
    return redirect(url_for("admin.admin"))

@admin_bp.route('/admin/service/add', methods=['GET', 'POST'])
@admin_required
def add_service():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        host = request.form.get('host')
        port = request.form.get('port')
        
        service = Service(
            name=name,
            description=description,
            host=host,
            port=int(port) if port else None
        )
        
        try:
            db.session.add(service)
            db.session.commit()
            flash('Service added successfully', 'success')
            return redirect(url_for('admin.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding service: {str(e)}', 'error')
    
    return render_template('admin/service_form.html')

@admin_bp.route('/admin')
@admin_required
def dashboard():
    services = Service.query.all()
    return render_template('admin/dashboard.html', services=services)
