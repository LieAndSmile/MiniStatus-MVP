# Importing necessary Flask tools and modules
from flask import Blueprint, render_template, redirect, url_for, session

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


# Creating a new Flask "blueprint" for grouping sync-related routes
sync_bp = Blueprint("sync", __name__)

# -------------------------------
# SYNC DOCKER SERVICES
# -------------------------------
@sync_bp.route("/sync", methods=["GET"])
def sync_docker_services():
    # Check if the user is logged in. If not, redirect to the login page
    if not session.get("authenticated"):
        return redirect(url_for("admin.login"))

    try:
        # Run a shell command to list all Docker containers and their status
        result = subprocess.check_output([
            "docker", "ps", "-a", "--format", "{{.Names}} {{.Status}}"
        ])
        # Decode output from bytes to string, split it into lines
        output = result.decode("utf-8").strip().split("\n")
    except Exception as e:
        # If the Docker command fails, return a 500 error with the message
        return f"Error running docker ps: {e}", 500

    updated_services = []

    # Process each container line
    for line in output:
        if not line.strip():
            continue  # Skip empty lines

        # Split line into: [name, status string]
        parts = line.split(" ", 1)
        name = parts[0]
        raw_status = parts[1].lower()

        # Use your helper function to interpret Docker's raw status
        status = interpret_docker_status(raw_status)

        # Look up if this service already exists in the DB
        svc = Service.query.filter_by(name=name).first()
        if svc:
            # Update its status and timestamp
            svc.status = status
            svc.last_updated = datetime.utcnow()
        else:
            # If it's a new service, create and add it
            svc = Service(
                name=name,
                status=status,
                description=f"Docker container '{name}'",
                last_updated=datetime.utcnow()
            )
            db.session.add(svc)

        # Keep track of updates to show in the template
        updated_services.append(f"{name} → {status}")

    # Save all changes to the database
    db.session.commit()

    # Render a confirmation page showing what was updated
    return render_template("sync.html", updated_services=updated_services)

# -------------------------------
# SYNC SYSTEMD SERVICES
# -------------------------------
@sync_bp.route("/sync-systemd")
def sync_systemd_services():
    # Same login check for protection
    if not session.get("authenticated"):
        return redirect(url_for("admin.login"))

    try:
        # Run shell command to list systemd services
        result = subprocess.check_output([
            "systemctl", "list-units", "--type=service", "--all", "--no-pager"
        ])
        output = result.decode("utf-8").strip().split("\n")
    except Exception as e:
        return f"Error running systemctl: {e}", 500

    updated_services = []

    # Process each service line
    for line in output:
        if ".service" not in line:
            continue  # Skip unrelated lines

        parts = line.split()
        if len(parts) < 4:
            continue  # Skip malformed lines

        unit_name = parts[0]       # e.g., nginx.service
        active_state = parts[2]    # e.g., active/inactive
        sub_state = parts[3]       # e.g., running/dead

        # Strip ".service" to keep a cleaner name
        name = unit_name.replace(".service", "")

        # Determine if the service is up or down
        status = "up" if active_state == "active" and sub_state == "running" else "down"

        # Same DB update logic as with Docker
        svc = Service.query.filter_by(name=name).first()
        if svc:
            svc.status = status
            svc.last_updated = datetime.utcnow()
        else:
            svc = Service(
                name=name,
                status=status,
                description=f"Systemd service: {unit_name}",
                last_updated=datetime.utcnow()
            )
            db.session.add(svc)

        updated_services.append(f"{name} → {status}")

    db.session.commit()
    return render_template("sync.html", updated_services=updated_services)
import socket  # add to the top if not already there

# -------------------------------
# PORTS CHECK
# -------------------------------
@sync_bp.route("/sync-ports")
def sync_ports():
    if not session.get("authenticated"):
        return redirect(url_for("admin.login"))

    services = Service.query.filter(Service.host != None, Service.port != None).all()
    updated = []

    for svc in services:
        try:
            # Try connecting to the host:port using a socket
            with socket.create_connection((svc.host, svc.port), timeout=3):
                svc.status = "up"
        except Exception:
            svc.status = "down"

        svc.last_updated = datetime.utcnow()
        updated.append(f"{svc.name} → {svc.status}")

    db.session.commit()
    return render_template("sync.html", updated_services=updated)

