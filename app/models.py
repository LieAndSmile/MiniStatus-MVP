from . import db
from datetime import datetime

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="up")  # up, degraded, down
    description = db.Column(db.String(128))
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

class Incident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    resolved = db.Column(db.Boolean, default=False)

    service = db.relationship('Service', backref=db.backref('incidents', lazy=True))
