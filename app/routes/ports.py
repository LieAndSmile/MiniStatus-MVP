from flask import Blueprint, render_template
from app.models import Service
from app.utils.ports import get_local_listening_ports

ports_bp = Blueprint("ports", __name__)

PORT_LABELS = {
    22: "SSH",
    80: "HTTP",
    443: "HTTPS",
    3306: "MySQL",
    5432: "PostgreSQL",
    6379: "Redis",
    1883: "MQTT",
    9100: "node_exporter",
}

@ports_bp.route("/ports")
def ports_dashboard():
    """Display local ports dashboard"""
    local_ports = get_local_listening_ports()
    return render_template("ports.html", local_ports=local_ports, port_labels=PORT_LABELS)
