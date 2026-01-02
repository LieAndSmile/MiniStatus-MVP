from datetime import datetime
from app.extensions import db

service_tag = db.Table(
    'service_tag',
    db.Column('service_id', db.Integer, db.ForeignKey('service.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)
    color = db.Column(db.String(16), default='gray')
    is_public = db.Column(db.Boolean, default=False)  # Whether this tag should be shown on public dashboard

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='unknown')
    description = db.Column(db.String(200))
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    host = db.Column(db.String(100))
    port = db.Column(db.Integer)
    tags = db.relationship('Tag', secondary=service_tag, backref='services')
    is_remote = db.Column(db.Boolean, default=False)

class Incident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    resolved = db.Column(db.Boolean, default=False)
    service = db.relationship('Service', backref=db.backref('incidents', lazy=True))

class AutoTagRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tag_name = db.Column(db.String(32), nullable=False)
    rule_type = db.Column(db.String(32), nullable=False)  # e.g. source, port, name_regex, desc_regex, host_regex
    rule_value = db.Column(db.String(128), nullable=False)
    enabled = db.Column(db.Boolean, default=True)
