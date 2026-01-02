from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from app.models import Service, Tag, AutoTagRule
from app.extensions import db
from app.utils.system_check import has_systemctl
from app.utils.password import verify_password, update_password_in_env
from functools import wraps
import os
from dotenv import load_dotenv
from app.utils.auto_tag import get_auto_tagged_for_service

admin_bp = Blueprint("admin", __name__, url_prefix='/admin')

DEFAULT_TAGS = [
    {"name": "networking", "color": "#6366f1"},
    {"name": "database", "color": "#10b981"},
    {"name": "internal", "color": "#64748b"},
    {"name": "external", "color": "#f59e42"},
    {"name": "critical", "color": "#ef4444"},
    {"name": "n8n", "color": "#ff7300"},
    {"name": "optional", "color": "#a3e635"},
]

def ensure_default_tags():
    from app.models import Tag
    for tag in DEFAULT_TAGS:
        if not Tag.query.filter_by(name=tag["name"]).first():
            db.session.add(Tag(name=tag["name"], color=tag["color"]))
    db.session.commit()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route("/")
@admin_required
def dashboard():
    """Admin dashboard"""
    ensure_default_tags()
    filter_status = request.args.get('filter')
    tag_ids = request.args.getlist('tag')
    no_tags = request.args.get('no_tags') == '1'
    services = Service.query

    if filter_status in ['up', 'down', 'degraded']:
        services = services.filter(Service.status == filter_status)

    if tag_ids:
        services = services.join(Service.tags).filter(Tag.id.in_(tag_ids)).distinct()
    elif no_tags:
        services = services.filter(~Service.tags.any())

    services = services.all()
    tags = Tag.query.all()
    # Determine auto-tagged info for each service
    auto_tagged_map = {}
    for svc in services:
        svc_data = {
            'name': svc.name,
            'description': svc.description,
            'port': svc.port,
            'source': getattr(svc, 'source', None),
            'host': svc.host
        }
        auto_tags = get_auto_tagged_for_service(svc_data)
        auto_tagged_map[svc.id] = auto_tags
    return render_template("admin.html",
                         services=services,
                         tags=tags,
                         selected_tag_ids=tag_ids,
                         no_tags=no_tags,
                         has_systemctl=has_systemctl(),
                         auto_tagged_map=auto_tagged_map)

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')
        
        stored_username = os.getenv('ADMIN_USERNAME')
        stored_password = os.getenv('ADMIN_PASSWORD')
        
        # Verify username and password (password is hashed)
        if username == stored_username and stored_password and verify_password(password, stored_password):
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

@admin_bp.route("/service/add", methods=['GET', 'POST'])
@admin_required
def add_service():
    tags = Tag.query.all()
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        host = request.form.get('host')
        port = request.form.get('port')
        tag_ids = request.form.getlist('tags')
        service = Service(
            name=name,
            description=description,
            host=host,
            port=int(port) if port else None,
            status='unknown',
            is_remote=False
        )
        if tag_ids:
            service.tags = Tag.query.filter(Tag.id.in_(tag_ids)).all()
        try:
            db.session.add(service)
            db.session.commit()
            flash('Service added successfully', 'success')
            return redirect(url_for('admin.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('Error adding service: ' + str(e), 'danger')
    return render_template('admin/service_form.html', tags=tags, edit_mode=False)

@admin_bp.route("/service/update/<int:service_id>", methods=["POST"])
@admin_required
def update_service(service_id):
    new_status = request.form["status"]
    service = Service.query.get_or_404(service_id)
    service.status = new_status
    service.last_updated = datetime.utcnow()
    db.session.commit()
    flash(f"Updated status for {service.name}!", "success")
    return redirect(url_for("admin.dashboard"))

@admin_bp.route("/service/delete/<int:service_id>", methods=["POST"])
@admin_required
def delete_service(service_id):
    service = Service.query.get_or_404(service_id)
    db.session.delete(service)
    db.session.commit()
    flash(f"Deleted service: {service.name}", "info")
    return redirect(url_for("admin.dashboard"))

@admin_bp.route("/service/edit/<int:service_id>", methods=["GET", "POST"])
@admin_required
def edit_service(service_id):
    service = Service.query.get_or_404(service_id)
    tags = Tag.query.all()
    if request.method == 'POST':
        service.name = request.form.get('name')
        service.description = request.form.get('description')
        service.host = request.form.get('host')
        service.port = int(request.form.get('port')) if request.form.get('port') else None
        tag_ids = request.form.getlist('tags')
        service.tags = Tag.query.filter(Tag.id.in_(tag_ids)).all() if tag_ids else []
        service.is_remote = False
        try:
            db.session.commit()
            flash('Service updated successfully', 'success')
            return redirect(url_for('admin.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('Error updating service: ' + str(e), 'danger')
    return render_template('admin/service_form.html', service=service, tags=tags, edit_mode=True)

@admin_bp.route('/tags', methods=['GET', 'POST'])
@admin_required
def manage_tags():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        color = request.form.get('color', 'gray').strip()
        if not name or len(name) > 32 or not name.isalnum():
            flash('Invalid tag name.', 'danger')
        elif Tag.query.filter_by(name=name).first():
            flash('Tag already exists.', 'danger')
        else:
            tag = Tag(name=name, color=color)
            db.session.add(tag)
            db.session.commit()
            flash('Tag added.', 'success')
        return redirect(url_for('admin.manage_tags'))
    tags = Tag.query.all()
    return render_template('admin/manage_tags.html', tags=tags)

@admin_bp.route('/tags/delete/<int:tag_id>', methods=['POST'])
@admin_required
def delete_tag(tag_id):
    tag = Tag.query.get_or_404(tag_id)
    if tag.services:
        flash('Cannot delete tag in use.', 'danger')
    else:
        db.session.delete(tag)
        db.session.commit()
        flash('Tag deleted.', 'success')
    return redirect(url_for('admin.manage_tags'))

@admin_bp.route('/auto-tag-rules', methods=['GET', 'POST'])
@admin_required
def manage_auto_tag_rules():
    if request.method == 'POST':
        tag_name = request.form.get('tag_name', '').strip()
        rule_type = request.form.get('rule_type', '').strip()
        rule_value = request.form.get('rule_value', '').strip()
        enabled = bool(request.form.get('enabled'))
        if tag_name and rule_type and rule_value:
            rule = AutoTagRule(tag_name=tag_name, rule_type=rule_type, rule_value=rule_value, enabled=enabled)
            db.session.add(rule)
            db.session.commit()
            flash('Auto-tag rule added.', 'success')
        return redirect(url_for('admin.manage_auto_tag_rules'))
    rules = AutoTagRule.query.order_by(AutoTagRule.id.desc()).all()
    return render_template('admin/manage_auto_tag_rules.html', rules=rules)

@admin_bp.route('/auto-tag-rules/edit/<int:rule_id>', methods=['GET', 'POST'])
@admin_required
def edit_auto_tag_rule(rule_id):
    rule = AutoTagRule.query.get_or_404(rule_id)
    if request.method == 'POST':
        rule.tag_name = request.form.get('tag_name', '').strip()
        rule.rule_type = request.form.get('rule_type', '').strip()
        rule.rule_value = request.form.get('rule_value', '').strip()
        rule.enabled = bool(request.form.get('enabled'))
        db.session.commit()
        flash('Auto-tag rule updated.', 'success')
        return redirect(url_for('admin.manage_auto_tag_rules'))
    return render_template('admin/edit_auto_tag_rule.html', rule=rule)

@admin_bp.route('/auto-tag-rules/delete/<int:rule_id>', methods=['POST'])
@admin_required
def delete_auto_tag_rule(rule_id):
    rule = AutoTagRule.query.get_or_404(rule_id)
    db.session.delete(rule)
    db.session.commit()
    flash('Auto-tag rule deleted.', 'success')
    return redirect(url_for('admin.manage_auto_tag_rules'))

@admin_bp.route('/auto-tag-rules/toggle/<int:rule_id>', methods=['POST'])
@admin_required
def toggle_auto_tag_rule(rule_id):
    rule = AutoTagRule.query.get_or_404(rule_id)
    rule.enabled = not rule.enabled
    db.session.commit()
    flash('Auto-tag rule status updated.', 'success')
    return redirect(url_for('admin.manage_auto_tag_rules'))

@admin_bp.route('/help')
@admin_required
def help_page():
    return render_template('admin/help.html')

@admin_bp.route('/change-password', methods=['GET', 'POST'])
@admin_required
def change_password():
    """Change admin password"""
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate inputs
        if not current_password or not new_password or not confirm_password:
            flash('All fields are required.', 'error')
            return render_template('admin/change_password.html')
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return render_template('admin/change_password.html')
        
        if len(new_password) < 6:
            flash('New password must be at least 6 characters long.', 'error')
            return render_template('admin/change_password.html')
        
        # Verify current password
        stored_password = os.getenv('ADMIN_PASSWORD')
        if not stored_password or not verify_password(current_password, stored_password):
            flash('Current password is incorrect.', 'error')
            return render_template('admin/change_password.html')
        
        # Update password in .env file
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
        if update_password_in_env(env_path, new_password):
            # Reload environment variables to make the change take effect immediately
            load_dotenv(override=True)
            flash('Password changed successfully!', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Failed to update password. Please check file permissions.', 'error')
    
    return render_template('admin/change_password.html')
