# app/utils/helpers.py

import psutil
import platform
import socket
import os
from datetime import datetime, timedelta


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
