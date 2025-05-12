from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from app.models import Service
from app import db
from app.utils.system_check import has_docker, has_systemctl

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/")
def index():
    services = Service.query.all()
    return render_template("index.html", services=services)

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    import os
    if request.method == "POST":
        password = request.form.get("password")
        if password == os.getenv("ADMIN_SECRET"):
            session["authenticated"] = True
            return redirect(url_for("admin.admin"))
        else:
            flash("Wrong password", "danger")
    return render_template("login.html")

@admin_bp.route("/logout")
def logout():
    session.pop("authenticated", None)
    return redirect(url_for("admin.index"))

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
