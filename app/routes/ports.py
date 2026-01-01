from flask import Blueprint, render_template, session, request, jsonify
from app.models import Service, db
from app.utils.ports import get_local_listening_ports, get_host_ports, get_ports_from_ss
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import threading

ports_bp = Blueprint("ports", __name__)

# Thread-local storage for the executor
thread_local = threading.local()

def get_executor():
    if not hasattr(thread_local, "executor"):
        thread_local.executor = ThreadPoolExecutor(max_workers=3)
    return thread_local.executor

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

def get_cached_ports(section=None):
    """Get cached port scan results"""
    cached = session.get('cached_ports')
    if cached:
        try:
            cached_data = json.loads(cached)
            # Check if cache is still valid (less than 5 minutes old)
            if datetime.now().timestamp() - cached_data['timestamp'] < 300:
                if section:
                    return [p for p in cached_data['ports'] if p.get('type') == section]
                return cached_data['ports']
        except:
            pass
    return None

def cache_ports(ports, section=None):
    """Cache port scan results"""
    if section:
        # Update only the specific section in cache
        existing_ports = get_cached_ports() or []
        # Remove existing ports of this section
        existing_ports = [p for p in existing_ports if p.get('type') != section]
        # Add new ports of this section
        existing_ports.extend(ports)
        ports = existing_ports

    cache_data = {
        'timestamp': datetime.now().timestamp(),
        'ports': ports
    }
    session['cached_ports'] = json.dumps(cache_data)

@ports_bp.route("/ports")
def ports_dashboard():
    """Display local ports dashboard"""
    # Try to get cached results first
    local_ports = get_cached_ports()
    
    # If no cache, start with empty list
    if local_ports is None:
        local_ports = []
    
    # Get status filter from query parameters
    status_filter = request.args.get('filter', 'all')
    
    # Filter ports based on status if a filter is applied
    if status_filter != 'all' and local_ports:
        local_ports = [port for port in local_ports if port.get('status') == status_filter]
    
    return render_template(
        "ports.html",
        local_ports=local_ports,
        port_labels=PORT_LABELS,
        current_filter=status_filter,
        is_cached=bool(local_ports)
    )

def scan_section(section):
    """Scan a specific section of ports"""
    try:
        if section == 'host':
            return get_host_ports()
        elif section == 'system':
            return get_ports_from_ss()
        return []
    except Exception as e:
        print(f"Error scanning {section}: {str(e)}")
        return []

@ports_bp.route("/api/ports/scan")
def scan_ports():
    """Async port scanning endpoint"""
    section = request.args.get('section')
    
    try:
        if section:
            # Scan only requested section
            ports = scan_section(section)
            cache_ports(ports, section)
        else:
            # Scan all sections in parallel
            executor = get_executor()
            futures = {
                executor.submit(scan_section, 'host'): 'host',
                executor.submit(scan_section, 'system'): 'system'
            }
            
            all_ports = []
            for future in futures:
                try:
                    ports = future.result(timeout=10)  # 10 second timeout per section
                    all_ports.extend(ports)
                except Exception as e:
                    print(f"Error in {futures[future]}: {str(e)}")
            
            cache_ports(all_ports)
            ports = all_ports
            
        return jsonify({
            'status': 'success',
            'ports': ports
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
