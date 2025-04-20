from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session
from .models import Service, Incident
from . import db
from datetime import datetime
import os
import subprocess
import requests

main = Blueprint('main', __name__)

# Homepage
@main.route("/")
def index():
    services = Service.query.all()
    incidents = Incident.query.order_by(Incident.timestamp.desc()).all()
    now = datetime.utcnow()
    return render_template("index.html", services=services, incidents=incidents, now=now)

# Login form for session-based auth
@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == os.getenv("ADMIN_SECRET"):
            session["authenticated"] = True
            return redirect(url_for("main.admin"))
        else:
            flash("Wrong password", "danger")
    return render_template("login.html")

# Logout route
@main.route("/logout")
def logout():
    session.pop("authenticated", None)
    return redirect(url_for("main.index"))

# Admin dashboard
@main.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("authenticated"):
        return redirect(url_for("main.login"))

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

        return redirect(url_for("main.admin"))

    services = Service.query.all()
    return render_template("admin.html", services=services)

# Update service
@main.route("/update/<int:service_id>", methods=["POST"])
def update_service(service_id):
    if not session.get("authenticated"):
        return redirect(url_for("main.login"))

    new_status = request.form["status"]
    service = Service.query.get_or_404(service_id)
    service.status = new_status
    service.last_updated = datetime.utcnow()
    db.session.commit()
    flash(f"Updated status for {service.name}!", "success")
    return redirect(url_for("main.admin"))

# Delete service
@main.route("/delete/<int:service_id>", methods=["POST"])
def delete_service(service_id):
    if not session.get("authenticated"):
        return redirect(url_for("main.login"))

    service = Service.query.get_or_404(service_id)
    db.session.delete(service)
    db.session.commit()
    flash(f"Deleted service: {service.name}", "info")
    return redirect(url_for("main.admin"))

# Sync Docker containers
@main.route("/sync", methods=["GET"])
def sync_docker_services():
    if not session.get("authenticated"):
        return redirect(url_for("main.login"))

    try:
        result = subprocess.check_output([
            "docker", "ps", "-a", "--format", "{{.Names}} {{.Status}}"
        ])
        output = result.decode("utf-8").strip().split("\n")
    except Exception as e:
        return f"Error running docker ps: {e}", 500

    updated_services = []

    for line in output:
        if not line.strip():
            continue
        parts = line.split(" ", 1)
        name = parts[0]
        raw_status = parts[1].lower()

        if "up" in raw_status:
            status = "up"
        elif "exited" in raw_status or "dead" in raw_status:
            status = "down"
        else:
            status = "degraded"

        svc = Service.query.filter_by(name=name).first()
        if svc:
            svc.status = status
            svc.last_updated = datetime.utcnow()
        else:
            svc = Service(
                name=name,
                status=status,
                description=f"Docker container '{name}'",
                last_updated=datetime.utcnow()
            )
            db.session.add(svc)

        updated_services.append(f"{name} → {status}")

    db.session.commit()

    return render_template("sync.html", updated_services=updated_services)

# Custom 403 handler
@main.app_errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403
### Systemd service scanning
@main.route("/sync-systemd")
def sync_systemd_services():
    if not session.get("authenticated"):
        return redirect(url_for("main.login"))

    try:
        result = subprocess.check_output([
            "systemctl", "list-units", "--type=service", "--all", "--no-pager"
        ])
        output = result.decode("utf-8").strip().split("\n")
    except Exception as e:
        return f"Error running systemctl: {e}", 500

    updated_services = []

    for line in output:
        if ".service" not in line:
            continue

        parts = line.split()
        if len(parts) < 4:
            continue

        unit_name = parts[0]              # e.g., nginx.service
        load_state = parts[1]             # e.g., loaded
        active_state = parts[2]           # e.g., active / inactive
        sub_state = parts[3]              # e.g., running / exited / failed

        name = unit_name.replace(".service", "")
        status = "up" if active_state == "active" and sub_state == "running" else "down"

        existing = Service.query.filter_by(name=name).first()
        if existing:
            existing.status = status
            existing.last_updated = datetime.utcnow()
            updated_services.append(f"{name} → {status}")
        else:
            new_svc = Service(
                name=name,
                status=status,
                description=f"Systemd service: {unit_name}",
                last_updated=datetime.utcnow()
            )
            db.session.add(new_svc)
            updated_services.append(f"Added {name} → {status}")

    db.session.commit()
    return render_template("sync.html", updated_services=updated_services)

