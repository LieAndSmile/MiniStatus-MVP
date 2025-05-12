from flask import Blueprint, render_template, redirect, url_for, session
from app.models import Service
from app import db
from datetime import datetime
import subprocess

sync_bp = Blueprint("sync", __name__)

@sync_bp.route("/sync", methods=["GET"])
def sync_docker_services():
    if not session.get("authenticated"):
        return redirect(url_for("admin.login"))

    try:
        result = subprocess.check_output(["docker", "ps", "-a", "--format", "{{.Names}} {{.Status}}"])
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

        status = "up" if "up" in raw_status else "down" if "exited" in raw_status or "dead" in raw_status else "degraded"

        svc = Service.query.filter_by(name=name).first()
        if svc:
            svc.status = status
            svc.last_updated = datetime.utcnow()
        else:
            svc = Service(name=name, status=status, description=f"Docker container '{name}'", last_updated=datetime.utcnow())
            db.session.add(svc)

        updated_services.append(f"{name} → {status}")

    db.session.commit()
    return render_template("sync.html", updated_services=updated_services)

@sync_bp.route("/sync-systemd")
def sync_systemd_services():
    if not session.get("authenticated"):
        return redirect(url_for("admin.login"))

    try:
        result = subprocess.check_output(["systemctl", "list-units", "--type=service", "--all", "--no-pager"])
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

        unit_name = parts[0]
        active_state = parts[2]
        sub_state = parts[3]

        name = unit_name.replace(".service", "")
        status = "up" if active_state == "active" and sub_state == "running" else "down"

        svc = Service.query.filter_by(name=name).first()
        if svc:
            svc.status = status
            svc.last_updated = datetime.utcnow()
        else:
            svc = Service(name=name, status=status, description=f"Systemd service: {unit_name}", last_updated=datetime.utcnow())
            db.session.add(svc)

        updated_services.append(f"{name} → {status}")

    db.session.commit()
    return render_template("sync.html", updated_services=updated_services)
