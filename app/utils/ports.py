# app/utils/ports.py

import subprocess
import socket
import json
import re
import os

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
    "3000": "Grafana",
    "8086": "InfluxDB",
    "61208": "Glances",
    # Common additional ports
    "21": "FTP",
    "23": "Telnet",
    "25": "SMTP",
    "53": "DNS",
    "110": "POP3",
    "143": "IMAP",
    "389": "LDAP",
    "636": "LDAPS",
    "993": "IMAPS",
    "995": "POP3S",
    "1433": "MSSQL",
    "1521": "Oracle",
    "3389": "RDP",
    "5353": "mDNS",
    "5672": "AMQP",
    "5900": "VNC",
    "6379": "Redis",
    "8443": "HTTPS Alt",
    "27017": "MongoDB"
}

# Common ports to scan on host
HOST_SCAN_PORTS = [
    21,    # FTP
    22,    # SSH
    25,    # SMTP
    53,    # DNS
    80,    # HTTP
    110,   # POP3
    143,   # IMAP
    443,   # HTTPS
    465,   # SMTPS
    587,   # SMTP (Submission)
    993,   # IMAPS
    995,   # POP3S
    1433,  # MSSQL
    1521,  # Oracle
    3000,  # Common dev port (Grafana etc.)
    3306,  # MySQL
    3389,  # RDP
    5432,  # PostgreSQL
    5672,  # AMQP
    6379,  # Redis
    8080,  # HTTP Alternate
    8443,  # HTTPS Alternate
    27017  # MongoDB
]

def get_process_name(pid):
    """Get process name from PID"""
    try:
        result = subprocess.run(["ps", "-p", str(pid), "-o", "comm="], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    return None

def get_docker_container_ports():
    """Get ports from running Docker containers"""
    try:
        print("Starting Docker container port scan...")  # Debug log
        print("Checking Docker socket permissions...")
        try:
            with open('/var/run/docker.sock', 'r') as f:
                print("Docker socket is readable")
        except Exception as e:
            print(f"Error accessing Docker socket: {e}")

        # Get list of running containers
        print("Running 'docker ps' command...")
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.ID}}"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"Error getting container IDs: {result.stderr}")  # Debug log
            return []

        container_ids = result.stdout.strip().split('\n')
        print(f"Found containers: {container_ids}")  # Debug log
        ports = []

        for container_id in container_ids:
            if not container_id:
                continue

            print(f"Inspecting container: {container_id}")  # Debug log
            # Inspect container to get port mappings
            inspect_result = subprocess.run(
                ["docker", "inspect", container_id],
                capture_output=True,
                text=True
            )
            if inspect_result.returncode != 0:
                print(f"Error inspecting container {container_id}: {inspect_result.stderr}")  # Debug log
                continue

            try:
                container_info = json.loads(inspect_result.stdout)
            except json.JSONDecodeError as e:
                print(f"Error parsing container info: {e}")
                print(f"Raw output: {inspect_result.stdout}")
                continue

            if not container_info:
                print(f"No info found for container {container_id}")  # Debug log
                continue

            container = container_info[0]
            container_name = container.get('Name', '').strip('/')
            port_bindings = container.get('NetworkSettings', {}).get('Ports', {})
            print(f"Container {container_name} port bindings: {port_bindings}")

            for container_port, host_bindings in port_bindings.items():
                if not host_bindings:
                    continue

                proto = container_port.split('/')[-1]
                container_port_num = container_port.split('/')[0]

                for binding in host_bindings:
                    host_port = binding.get('HostPort', '')
                    host_ip = binding.get('HostIp', '0.0.0.0')

                    port_info = {
                        "protocol": proto,
                        "address": host_ip,
                        "port": host_port,
                        "container_port": container_port_num,
                        "container_name": container_name,
                        "label": PORT_LABELS.get(host_port, f"Docker: {container_name}"),
                        "type": "docker",
                        "status": "open"  # If we can see it in Docker, it's open
                    }
                    ports.append(port_info)
                    print(f"Added port info: {port_info}")  # Debug log

        print(f"Final ports list: {ports}")  # Debug log
        return ports
    except Exception as e:
        print(f"Error getting Docker ports: {e}")  # Debug log
        import traceback
        print(traceback.format_exc())  # Print full traceback
        return []

def get_service_info(port, proto):
    """Try to get service information for a port"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM if proto.lower() == 'tcp' else socket.SOCK_DGRAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('127.0.0.1', int(port)))
            status = "open" if result == 0 else "closed"
            
            service_name = ""
            try:
                service_name = socket.getservbyport(int(port), proto.lower())
            except:
                service_name = PORT_LABELS.get(str(port), "")
                
            return status, service_name
    except:
        return "unknown", ""

def get_ports_from_ss():
    """Get ports from ss command with enhanced information"""
    try:
        # Use ss with process info
        result = subprocess.run(["ss", "-tulnp"], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[1:]  # Skip header
            ports = []
            for line in lines:
                port_info = parse_port_line(line, 'ss')
                if port_info:
                    # Extract PID and process name from ss output
                    pid_match = re.search(r'pid=(\d+)', line)
                    if pid_match:
                        pid = pid_match.group(1)
                        process_name = get_process_name(pid)
                        if process_name:
                            port_info['process'] = process_name
                            port_info['pid'] = pid
                    ports.append(port_info)
            return ports
    except:
        pass
    return []

def get_ports_from_netstat():
    """Get ports from netstat command with enhanced information"""
    try:
        result = subprocess.run(["netstat", "-tulnp"], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[2:]  # Skip headers
            ports = []
            for line in lines:
                port_info = parse_port_line(line, 'netstat')
                if port_info:
                    # Extract process info from netstat output
                    process_match = re.search(r'\s(\d+)/(\S+)\s*$', line)
                    if process_match:
                        port_info['pid'] = process_match.group(1)
                        port_info['process'] = process_match.group(2)
                    ports.append(port_info)
            return ports
    except:
        pass
    return []

def parse_port_line(line, source='ss'):
    try:
        parts = line.split()
        if not parts:
            return None

        if source == 'ss':
            proto = parts[0].lower()
            local_address = parts[4]
        else:  # netstat
            proto = parts[0].lower()
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

        # Get service status and name
        status, service_name = get_service_info(port, proto)
        
        return {
            "protocol": proto,
            "address": addr,
            "port": port,
            "label": PORT_LABELS.get(port, service_name),
            "status": status,
            "type": "system",
            "service_name": service_name or "Unknown"
        }
    except:
        return None

def get_host_address():
    """Get the host machine's address from the container's perspective"""
    # First try to get the default gateway (host) address
    try:
        result = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True)
        if result.returncode == 0:
            match = re.search(r'default via (\d+\.\d+\.\d+\.\d+)', result.stdout)
            if match:
                return match.group(1)
    except:
        pass
    
    # Fallback to default Docker host
    return "host.docker.internal" if os.environ.get("DOCKER_HOST_INTERNAL") else "172.17.0.1"

def scan_host_port(host, port, protocol='tcp'):
    """Scan a specific port on the host"""
    try:
        sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM if protocol == 'tcp' else socket.SOCK_DGRAM
        )
        sock.settimeout(1)
        
        result = sock.connect_ex((host, port))
        status = "open" if result == 0 else "closed"
        
        if status == "open":
            try:
                service_name = socket.getservbyport(port, protocol)
            except:
                service_name = PORT_LABELS.get(str(port), "")
        else:
            service_name = PORT_LABELS.get(str(port), "")
        
        sock.close()
        return {
            "port": str(port),
            "protocol": protocol,
            "status": status,
            "address": host,
            "label": service_name or f"Port {port}",
            "service_name": service_name,
            "type": "host"
        }
    except Exception as e:
        return {
            "port": str(port),
            "protocol": protocol,
            "status": "unknown",
            "address": host,
            "label": PORT_LABELS.get(str(port), f"Port {port}"),
            "service_name": "Unknown",
            "type": "host",
            "error": str(e)
        }

def get_host_ports():
    """Scan common ports on the host machine"""
    host_address = get_host_address()
    host_ports = []
    
    print(f"Scanning host ports on {host_address}...")
    for port in HOST_SCAN_PORTS:
        port_info = scan_host_port(host_address, port)
        if port_info:
            host_ports.append(port_info)
    
    return host_ports

def get_local_listening_ports():
    print("Starting port scan...")  # Debug log
    ports_dict = {}  # Use dict to avoid duplicates

    # Get Docker container ports
    docker_ports = get_docker_container_ports()
    print(f"Docker ports found: {docker_ports}")  # Debug log
    for port_info in docker_ports:
        key = f"{port_info['port']}_{port_info['protocol']}"
        ports_dict[key] = port_info

    # Get host ports
    host_ports = get_host_ports()
    print(f"Host ports found: {host_ports}")  # Debug log
    for port_info in host_ports:
        key = f"{port_info['port']}_{port_info['protocol']}_host"  # Add _host to avoid conflicts
        ports_dict[key] = port_info

    # Try ss command first for container ports
    ss_lines = get_ports_from_ss()
    print(f"SS command lines: {ss_lines}")  # Debug log
    for port_info in ss_lines:
        if port_info:
            key = f"{port_info['port']}_{port_info['protocol']}"
            if key not in ports_dict:  # Don't override Docker ports
                ports_dict[key] = port_info

    # Try netstat as backup
    if not ss_lines:
        netstat_lines = get_ports_from_netstat()
        print(f"Netstat command lines: {netstat_lines}")  # Debug log
        for port_info in netstat_lines:
            if port_info:
                key = f"{port_info['port']}_{port_info['protocol']}"
                if key not in ports_dict:  # Don't override existing ports
                    ports_dict[key] = port_info

    # Convert dict to list and sort by port number
    ports = list(ports_dict.values())
    sorted_ports = sorted(ports, key=lambda x: int(x['port']))
    print(f"Final sorted ports: {sorted_ports}")  # Debug log
    return sorted_ports
