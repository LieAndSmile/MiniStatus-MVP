# app/utils/ports.py

import subprocess

PORT_LABELS = {
    "22": "SSH",
    "80": "HTTP",
    "443": "HTTPS",
    "3306": "MySQL",
    "5432": "PostgreSQL",
    "6379": "Redis",
    "5000": "Flask Dev Server"
}

def get_local_listening_ports():
    result = subprocess.run(["ss", "-tuln"], capture_output=True, text=True)
    lines = result.stdout.strip().split("\n")

    ports = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 5:
            continue

        proto = parts[0]
        local_address = parts[4]

        # handle IPv4 and IPv6 addresses
        if "[" in local_address:  # IPv6
            addr, port = local_address.rsplit("]:", 1)
            addr = addr.strip("[]")
        else:
            if ":" not in local_address:
                continue
            addr, port = local_address.rsplit(":", 1)

        label = PORT_LABELS.get(port)
        ports.append({
            "protocol": proto,
            "address": addr,
            "port": port,
            "label": label
        })

    return ports
