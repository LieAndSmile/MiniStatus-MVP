# app/routes/public.py

from flask import Blueprint, render_template, request, url_for
from app.models import Service, Tag, Incident
from app.extensions import db
from datetime import datetime
import os

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
def index():
    """Public status dashboard"""
    # Get public-facing tags only (with fallback for migration)
    try:
        public_tags = Tag.query.filter_by(is_public=True).all()
    except Exception:
        # Fallback if is_public column doesn't exist yet
        public_tags = []
    
    # Only get services that have at least one public tag
    public_tag_ids = [tag.id for tag in public_tags]
    if public_tag_ids:
        # Get services that have at least one public tag
        all_services = Service.query.join(Service.tags).filter(Tag.id.in_(public_tag_ids)).distinct().all()
    else:
        # No public tags configured yet - show empty
        all_services = []
    
    # Group services by public tags
    services_by_tag = {}
    
    for service in all_services:
        # Get only public tags for this service
        service_public_tags = [tag for tag in service.tags if getattr(tag, 'is_public', False)]
        for tag in service_public_tags:
            if tag.name not in services_by_tag:
                services_by_tag[tag.name] = []
            # Avoid duplicates if service has multiple public tags
            if service not in services_by_tag[tag.name]:
                services_by_tag[tag.name].append(service)
    
    # Calculate uptime percentage (only for public-facing services)
    total_services = len(all_services)
    up_services = len([s for s in all_services if s.status == 'up'])
    uptime_percentage = round((up_services / total_services * 100) if total_services > 0 else 100, 1)
    
    # Determine overall status
    if total_services == 0:
        overall_status = "No Services Configured"
        status_icon = "info"
    elif uptime_percentage >= 99.9:
        overall_status = "All Systems Operational"
        status_icon = "success"
    elif uptime_percentage >= 95:
        overall_status = "Some Services Degraded"
        status_icon = "warning"
    else:
        overall_status = "Service Disruption"
        status_icon = "error"
    
    # Get active incidents (unresolved)
    active_incidents = Incident.query.filter_by(resolved=False).order_by(Incident.timestamp.desc()).all()
    
    # Get region and environment from config
    region = os.getenv('PUBLIC_REGION', 'N/A')
    environment = os.getenv('PUBLIC_ENVIRONMENT', 'Production')
    
    # Calculate status counts per tag
    tag_status_counts = {}
    for tag_name, services in services_by_tag.items():
        total = len(services)
        up = len([s for s in services if s.status == 'up'])
        down = len([s for s in services if s.status == 'down'])
        degraded = len([s for s in services if s.status == 'degraded'])
        tag_status_counts[tag_name] = {
            'total': total,
            'up': up,
            'down': down,
            'degraded': degraded,
            'uptime_pct': round((up / total * 100) if total > 0 else 100, 1)
        }
    
    # Get last updated timestamp (only from public services)
    last_updated = max([s.last_updated for s in all_services], default=datetime.utcnow()) if all_services else None

    return render_template('public/index.html',
                           services=all_services,
                           services_by_tag=services_by_tag,
                           public_tags=public_tags,
                           tag_status_counts=tag_status_counts,
                           uptime_percentage=uptime_percentage,
                           overall_status=overall_status,
                           status_icon=status_icon,
                           active_incidents=active_incidents,
                           region=region,
                           environment=environment,
                           last_updated=last_updated)


@public_bp.route('/feed.xml')
def rss_feed():
    """RSS feed for public-facing incidents and status updates"""
    from flask import make_response
    
    # Get public-facing incidents (resolved and unresolved)
    incidents = Incident.query.order_by(Incident.timestamp.desc()).limit(50).all()
    
    # Get public-facing services
    public_tags = Tag.query.filter_by(is_public=True).all()
    public_tag_ids = [tag.id for tag in public_tags]
    public_services = Service.query.join(Service.tags).filter(Tag.id.in_(public_tag_ids)).distinct().all()
    
    # Build RSS XML
    rss_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Service Status Updates</title>
    <link>{request.url_root.rstrip('/')}</link>
    <description>Real-time status updates for all services</description>
    <language>en-us</language>
    <lastBuildDate>{datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')}</lastBuildDate>
    <atom:link href="{request.url_root.rstrip('/')}/feed.xml" rel="self" type="application/rss+xml"/>
'''
    
    # Add incidents as RSS items
    from html import escape
    for incident in incidents:
        status = "Resolved" if incident.resolved else "Active"
        pub_date = incident.timestamp.strftime('%a, %d %b %Y %H:%M:%S GMT')
        title = escape(f"{incident.title} - {incident.service.name} ({status})")
        details = escape(incident.details or incident.title)
        rss_xml += f'''    <item>
      <title>{title}</title>
      <link>{request.url_root.rstrip('/')}</link>
      <description><![CDATA[{details}]]></description>
      <pubDate>{pub_date}</pubDate>
      <guid isPermaLink="false">incident-{incident.id}</guid>
    </item>
'''
    
    rss_xml += '''  </channel>
</rss>'''
    
    response = make_response(rss_xml)
    response.headers['Content-Type'] = 'application/rss+xml; charset=utf-8'
    return response


@public_bp.route('/rss')
def rss_redirect():
    """Redirect /rss to /feed.xml"""
    from flask import redirect
    return redirect(url_for('public.rss_feed'), code=301)
