# app/utils/ports.py

import subprocess
import socket

PORT_LABELS = {
    "22": "SSH",
    "80": "HTTP",
    "443": "HTTPS",
    "3306": "MySQL",
    "5432": "PostgreSQL",
    "6379": "Redis",
    "5000": "Flask Dev Server",
    "8080": "HTTP Alternate",
    "1883": "MQTT",
    "9100": "Node Exporter",
    "9090": "Prometheus",
    "3000": "Grafana"
}

def get_ports_from_ss():
    try:
        result = subprocess.run(["ss", "-tuln"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip().split("\n")[1:]  # Skip header
    except:
        return []
    return []

def get_ports_from_netstat():
    try:
        result = subprocess.run(["netstat", "-tuln"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip().split("\n")[2:]  # Skip headers
    except:
        return []
    return []

def parse_port_line(line, source='ss'):
    try:
        parts = line.split()
        if not parts:
            return None

        if source == 'ss':
            proto = parts[0]
            local_address = parts[4]
        else:  # netstat
            proto = parts[0]
            local_address = parts[3]

        # handle IPv4 and IPv6 addresses
        if "[" in local_address:  # IPv6
            addr, port = local_address.rsplit("]:", 1)
            addr = addr.strip("[]")
        else:
            if ":" not in local_address:
                return None
            addr, port = local_address.rsplit(":", 1)

        # Skip if not a valid port number
        try:
            port_num = int(port)
            if port_num < 1 or port_num > 65535:
                return None
        except ValueError:
            return None

        return {
            "protocol": proto,
            "address": addr,
            "port": port,
            "label": PORT_LABELS.get(port)
        }
    except:
        return None

def get_local_listening_ports():
    ports_dict = {}  # Use dict to avoid duplicates

    # Try ss command first
    for line in get_ports_from_ss():
        port_info = parse_port_line(line, 'ss')
        if port_info:
            key = f"{port_info['port']}_{port_info['protocol']}"
            ports_dict[key] = port_info

    # Try netstat as backup
    for line in get_ports_from_netstat():
        port_info = parse_port_line(line, 'netstat')
        if port_info:
            key = f"{port_info['port']}_{port_info['protocol']}"
            if key not in ports_dict:
                ports_dict[key] = port_info

    # Convert dict to list and sort by port number
    ports = list(ports_dict.values())
    return sorted(ports, key=lambda x: int(x['port']))
