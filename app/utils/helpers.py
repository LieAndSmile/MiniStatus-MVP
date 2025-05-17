# app/utils/helpers.py

import psutil
import platform
import socket
import os
from datetime import datetime, timedelta
import yaml
import calendar
import requests
import re


def interpret_docker_status(raw_status):
    raw = raw_status.lower()

    if "up" in raw:
        return "up"
    elif "exited" in raw or "dead" in raw:
        return "down"
    else:
        return "degraded"


def get_system_stats():
    """
    Returns a dict with CPU, RAM, Disk usage, and system uptime.
    """
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    return {
        'cpu': cpu,
        'ram': ram.percent,
        'disk': disk.percent,
        'uptime': uptime
    }


def get_system_identity():
    """
    Returns a dict with hostname, OS, and kernel version.
    """
    hostname = socket.gethostname()
    os_name = platform.system()
    os_version = platform.release()
    kernel = platform.version()
    return {
        'hostname': hostname,
        'os': f"{os_name} {os_version}",
        'kernel': kernel
    }

KNOWN_SERVICES = [
    {
        "name": "Grafana",
        "category": "Monitoring",
        "url": "http://localhost:3000",
        "detect": {"port": 3000, "process": "grafana-server"},
        "icon": "grafana",
        "icon_color": "#F46800"
    },
    {
        "name": "InfluxDB",
        "category": "Database",
        "url": "http://localhost:8086",
        "detect": {"port": 8086, "process": "influxd"},
        "icon": "influxdb",
        "icon_color": "#22ADF6"
    },
    {
        "name": "Glances",
        "category": "Monitoring",
        "url": "http://localhost:61208",
        "detect": {"port": 61208, "process": "glances"},
        "icon": None,
        "icon_color": "#4E9A06",
        "icon_url": "/static/icons/glances.svg"
    },
    {
        "name": "Prometheus",
        "category": "Monitoring",
        "url": "http://localhost:9090",
        "detect": {"port": 9090, "process": "prometheus"},
        "icon": "prometheussoftware",
        "icon_color": "#E6522C"
    },
    {
        "name": "Uptime Kuma",
        "category": "Monitoring",
        "url": "http://localhost:3001",
        "detect": {"port": 3001, "process": "uptime-kuma"},
        "icon": None,
        "icon_color": None
    },
    {
        "name": "Pi-hole",
        "category": "Network",
        "url": "http://localhost:8080",
        "detect": {"port": 8080, "process": "pihole-FTL"},
        "icon": "pihole",
        "icon_color": "#96060C"
    },
    {
        "name": "Cockpit",
        "category": "Servers",
        "url": "https://localhost:9090",
        "detect": {"port": 9090, "process": "cockpit-ws"},
        "icon": None,
        "icon_color": None
    },
    {
        "name": "Portainer",
        "category": "Applications",
        "url": "http://localhost:9443",
        "detect": {"port": 9443, "process": "portainer"},
        "icon": "portainer",
        "icon_color": "#13BEF9"
    },
]

def is_port_open(port, host="127.0.0.1"):
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except Exception:
        return False

def is_process_running(process_name):
    for proc in psutil.process_iter(['name']):
        try:
            if process_name.lower() in proc.info['name'].lower():
                return True
        except Exception:
            continue
    return False

def fetch_and_colorize_svg(icon_name, color):
    """Fetch SVG from Simple Icons CDN and set fill to the brand color."""
    url = f"https://cdn.jsdelivr.net/npm/simple-icons@v9/icons/{icon_name}.svg"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            svg = resp.text
            # Replace or add fill attribute in <svg>
            svg = re.sub(r'<svg([^>]*)>', f'<svg\\1 fill=\"{color}\">', svg, count=1)
            return svg
    except Exception:
        pass
    return None

def get_detected_services():
    detected = []
    for svc in KNOWN_SERVICES:
        port = svc['detect'].get('port')
        process = svc['detect'].get('process')
        port_ok = is_port_open(port) if port else False
        proc_ok = is_process_running(process) if process else False
        if port_ok or proc_ok:
            icon_name = svc.get('icon', '')
            icon_color = svc.get('icon_color')
            if icon_name and icon_color:
                icon_svg = fetch_and_colorize_svg(icon_name, icon_color)
            else:
                icon_svg = None
            if icon_name:
                icon_url = f"https://cdn.jsdelivr.net/npm/simple-icons@v9/icons/{icon_name}.svg"
            else:
                icon_url = "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/icons/app.svg"
            svc_with_icon = svc.copy()
            svc_with_icon['icon_url'] = icon_url
            svc_with_icon['icon_color'] = icon_color
            svc_with_icon['icon_svg'] = icon_svg
            detected.append(svc_with_icon)
    return detected

def load_manual_links(yaml_path="quick_links.yaml"):
    try:
        with open(yaml_path, 'r') as f:
            return yaml.safe_load(f) or []
    except Exception:
        return []

def get_all_quick_links():
    detected = get_detected_services()
    manual = load_manual_links()
    # Avoid duplicates by name+url
    seen = set((svc['name'], svc['url']) for svc in detected)
    merged = detected[:]
    for link in manual:
        if (link['name'], link['url']) not in seen:
            # Only show manual link if detected
            detect = link.get('detect')
            port_ok = is_port_open(detect.get('port')) if detect and detect.get('port') else False
            proc_ok = is_process_running(detect.get('process')) if detect and detect.get('process') else False
            if detect and (port_ok or proc_ok):
                # Add fallback icon_url for manual links if missing
                if not link.get('icon_url'):
                    link = link.copy()
                    link['icon_url'] = "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/icons/app.svg"
                merged.append(link)
            # If no detect field, skip (hide by default)
    return merged

def get_public_holidays(year, country_code):
    """
    Fetch public holidays for the given year and country code from Nager.Date API.
    Returns a set of date strings in 'YYYY-MM-DD' format.
    """
    try:
        url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country_code}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            holidays = resp.json()
            return set(h['date'] for h in holidays)
    except Exception:
        pass
    return set()

def generate_month_calendar(year, month, today, holidays):
    """
    Returns a list of weeks, each week is a list of dicts:
    { 'day': int, 'date': 'YYYY-MM-DD', 'is_today': bool, 'is_holiday': bool, 'in_month': bool }
    """
    cal = calendar.Calendar()
    weeks = []
    for week in cal.monthdatescalendar(year, month):
        week_row = []
        for d in week:
            date_str = d.strftime('%Y-%m-%d')
            week_row.append({
                'day': d.day,
                'date': date_str,
                'is_today': d == today,
                'is_holiday': date_str in holidays,
                'in_month': d.month == month
            })
        weeks.append(week_row)
    return weeks
