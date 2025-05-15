from flask import Blueprint, request, jsonify
from app.models import Service
from app import db
from datetime import datetime
import os
from app.utils.ports import scan_ports

api_bp = Blueprint("api", __name__, url_prefix='/api')

@api_bp.route("/report", methods=["POST"])
def report_status():
    api_key = request.headers.get("X-API-Key")
    expected_key = os.getenv("API_KEY", "supersecret")

    if api_key != expected_key:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json() or request.form
    name = data.get("name")
    status = data.get("status")
    description = data.get("description", "Reported via webhook")

    if not name or not status:
        return jsonify({"error": "Missing required fields"}), 400

    service = Service.query.filter_by(name=name).first()
    if service:
        service.status = status
        service.last_updated = datetime.utcnow()
        service.description = description
    else:
        service = Service(
            name=name,
            status=status,
            description=description,
            last_updated=datetime.utcnow()
        )
        db.session.add(service)

    db.session.commit()
    return jsonify({"message": f"Service '{name}' updated to '{status}'"})

@api_bp.route('/ports/scan')
def scan_ports_api():
    """API endpoint to scan ports and return results as JSON"""
    try:
        ports = scan_ports()
        return jsonify({
            'status': 'success',
            'ports': ports
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
