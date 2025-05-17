# app/utils/helpers.py

import psutil
import platform
import socket
import os
from datetime import datetime, timedelta
import yaml


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
        "icon": "grafana"
    },
    {
        "name": "Pi-hole",
        "category": "Network",
        "url": "http://localhost:8080",
        "detect": {"port": 8080, "process": "pihole-FTL"},
        "icon": "pihole"
    },
    {
        "name": "Cockpit",
        "category": "Servers",
        "url": "https://localhost:9090",
        "detect": {"port": 9090, "process": "cockpit-ws"},
        "icon": "cockpit"
    },
    {
        "name": "Portainer",
        "category": "Applications",
        "url": "http://localhost:9443",
        "detect": {"port": 9443, "process": "portainer"},
        "icon": "portainer"
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

def get_detected_services():
    detected = []
    for svc in KNOWN_SERVICES:
        port = svc['detect'].get('port')
        process = svc['detect'].get('process')
        port_ok = is_port_open(port) if port else False
        proc_ok = is_process_running(process) if process else False
        if port_ok or proc_ok:
            detected.append(svc)
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
            merged.append(link)
    return merged
