# app/routes/ports.py

from flask import Blueprint, render_template
from app.models import Service

ports_bp = Blueprint("ports", __name__)

@ports_bp.route("/ports")
def ports_dashboard():
    services = Service.query.filter(Service.host != None, Service.port != None).all()
    return render_template("ports.html", services=services)
