import subprocess
from datetime import datetime
import socket
import time
from app.extensions import db
from app.models import Service
from app.utils.helpers import interpret_docker_status
from app.utils.ports import get_local_listening_ports

class ServiceSync:
    @staticmethod
    def sync_docker():
        """Sync Docker container statuses"""
        try:
            result = subprocess.check_output([
                "docker", "ps", "-a", "--format", "{{.Names}} {{.Status}}"
            ])
            output = result.decode("utf-8").strip().split("\n")
        except Exception as e:
            return [], f"Error running docker ps: {e}"

        updated_services = []

        for line in output:
            if not line.strip():
                continue

            parts = line.split(" ", 1)
            name = parts[0]
            raw_status = parts[1].lower()
            status = interpret_docker_status(raw_status)

            svc = Service.query.filter_by(name=name).first()
            if svc:
                svc.status = status
                svc.last_updated = datetime.utcnow()
            else:
                svc = Service(
                    name=name,
                    status=status,
                    description=f"Docker container '{name}'",
                    last_updated=datetime.utcnow()
                )
                db.session.add(svc)

            updated_services.append(f"{name} → {status}")

        try:
            db.session.commit()
            return updated_services, None
        except Exception as e:
            db.session.rollback()
            return [], f"Error saving to database: {e}"

    @staticmethod
    def sync_systemd():
        """Sync systemd service statuses"""
        try:
            result = subprocess.check_output([
                "systemctl", "list-units", "--type=service", "--all", "--no-pager"
            ])
            output = result.decode("utf-8").strip().split("\n")
        except Exception as e:
            return [], f"Error running systemctl: {e}"

        updated_services = []

        for line in output:
            if ".service" not in line:
                continue

            parts = line.split()
            if len(parts) < 4:
                continue

            unit_name = parts[0]
            active_state = parts[2]
            sub_state = parts[3]
            name = unit_name.replace(".service", "")
            status = "up" if active_state == "active" and sub_state == "running" else "down"

            svc = Service.query.filter_by(name=name).first()
            if svc:
                svc.status = status
                svc.last_updated = datetime.utcnow()
            else:
                svc = Service(
                    name=name,
                    status=status,
                    description=f"Systemd service: {unit_name}",
                    last_updated=datetime.utcnow()
                )
                db.session.add(svc)

            updated_services.append(f"{name} → {status}")

        try:
            db.session.commit()
            return updated_services, None
        except Exception as e:
            db.session.rollback()
            return [], f"Error saving to database: {e}"

    @staticmethod
    def sync_ports():
        """Sync port statuses for monitored services"""
        services = Service.query.filter(
            Service.host.isnot(None),
            Service.port.isnot(None)
        ).all()
        
        updated_services = []

        for svc in services:
            try:
                with socket.create_connection((svc.host, svc.port), timeout=3):
                    svc.status = "up"
            except Exception:
                svc.status = "down"

            svc.last_updated = datetime.utcnow()
            updated_services.append(f"{svc.name} → {svc.status}")

        try:
            db.session.commit()
            return updated_services, None
        except Exception as e:
            db.session.rollback()
            return [], f"Error saving to database: {e}"

    @staticmethod
    def sync_remote_hosts(timeout=3, retry_count=1):
        """
        Sync remote host statuses with retry and latency measurement
        
        Args:
            timeout (int): Socket connection timeout in seconds
            retry_count (int): Number of retries before marking as down
        """
        services = Service.query.filter(
            Service.host.isnot(None),
            Service.port.isnot(None)
        ).all()
        
        updated_services = []
        
        for svc in services:
            latency = None
            error_msg = None
            is_up = False
            
            # Try connection with retry
            for attempt in range(retry_count + 1):
                try:
                    start_time = time.time()
                    with socket.create_connection((svc.host, svc.port), timeout=timeout) as conn:
                        latency = (time.time() - start_time) * 1000  # Convert to ms
                        is_up = True
                        break
                except socket.timeout:
                    error_msg = "Connection timed out"
                except ConnectionRefusedError:
                    error_msg = "Connection refused"
                except socket.gaierror:
                    error_msg = "DNS resolution failed"
                except Exception as e:
                    error_msg = str(e)
                
                # If not last attempt, wait briefly before retry
                if attempt < retry_count:
                    time.sleep(1)
            
            # Update service status
            if is_up:
                svc.status = "up"
                svc.description = f"Latency: {latency:.1f}ms"
            else:
                svc.status = "down"
                svc.description = f"Error: {error_msg}"
            
            svc.last_updated = datetime.utcnow()
            updated_services.append(f"{svc.name} ({svc.host}:{svc.port}) → {svc.status}")

        try:
            db.session.commit()
            return updated_services, None
        except Exception as e:
            db.session.rollback()
            return [], f"Error saving to database: {e}"

    @staticmethod
    def sync_all():
        """Sync all services (Docker, systemd, and ports)"""
        results = {
            'docker': ServiceSync.sync_docker(),
            'systemd': ServiceSync.sync_systemd(),
            'ports': ServiceSync.sync_ports(),
            'remote': ServiceSync.sync_remote_hosts()
        }
        return results 