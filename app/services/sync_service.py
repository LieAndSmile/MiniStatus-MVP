import subprocess
from datetime import datetime
import socket
import time
from app.extensions import db
from app.models import Service, Tag
from app.utils.helpers import interpret_docker_status
from app.utils.ports import get_local_listening_ports, get_docker_container_ports
from app.utils.auto_tag import auto_assign_tags

class ServiceSync:
    @staticmethod
    def sync_docker(no_auto_tag=False):
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
            # Always update tags unless no_auto_tag
            if not no_auto_tag:
                tag_names = auto_assign_tags({
                    'name': name,
                    'description': f"Docker container '{name}'",
                    'port': None,
                    'source': 'docker',
                    'host': None
                }, log=True)
                svc_tags = []
                for tag_name in tag_names:
                    tag = Tag.query.filter_by(name=tag_name).first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        db.session.add(tag)
                    svc_tags.append(tag)
            else:
                svc_tags = svc.tags if svc else []
            if svc:
                svc.status = status
                svc.last_updated = datetime.utcnow()
                svc.tags = svc_tags
            else:
                svc = Service(
                    name=name,
                    status=status,
                    description=f"Docker container '{name}'",
                    last_updated=datetime.utcnow(),
                    is_remote=True,
                    tags=svc_tags
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
    def sync_systemd(no_auto_tag=False):
        """Sync systemd service statuses"""
        try:
            result = subprocess.check_output([
                "systemctl", "list-units", "--type=service",
                "--all", "--no-pager", "--plain"
            ])
            output = result.decode("utf-8").strip().split("\n")
        except Exception as e:
            return [], f"Error running systemctl: {e}"

        updated_services = []

        for line in output:
            if not line.strip() or "UNIT" in line:  # Skip empty lines and header
                continue

            parts = line.split()
            if len(parts) < 3:
                continue

            name = parts[0].replace(".service", "")
            raw_status = parts[2].lower()

            # Map systemd status to our status format
            if "running" in raw_status:
                status = "up"
            elif "dead" in raw_status or "failed" in raw_status:
                status = "down"
            else:
                status = "degraded"

            svc = Service.query.filter_by(name=name).first()
            # Always update tags unless no_auto_tag
            if not no_auto_tag:
                tag_names = auto_assign_tags({
                    'name': name,
                    'description': f"Systemd service '{name}'",
                    'port': None,
                    'source': 'systemd',
                    'host': None
                }, log=True)
                svc_tags = []
                for tag_name in tag_names:
                    tag = Tag.query.filter_by(name=tag_name).first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        db.session.add(tag)
                    svc_tags.append(tag)
            else:
                svc_tags = svc.tags if svc else []
            if svc:
                svc.status = status
                svc.last_updated = datetime.utcnow()
                svc.tags = svc_tags
            else:
                svc = Service(
                    name=name,
                    status=status,
                    description=f"Systemd service '{name}'",
                    last_updated=datetime.utcnow(),
                    is_remote=True,
                    tags=svc_tags
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
    def sync_ports(no_auto_tag=False):
        """Sync port statuses including Docker container ports"""
        try:
            # Get all ports including Docker container ports
            ports = get_local_listening_ports()
            
            # Update services based on port status
            updated_services = []
            for port_info in ports:
                name = port_info.get('container_name', f"Port {port_info['port']}")
                status = "up"  # If we can see the port, it's up
                host = port_info.get('host')
                port = port_info['port']
                description = (
                    f"Docker container port {port}/{port_info['protocol']}"
                    if port_info.get('container_name')
                    else f"Port {port}/{port_info['protocol']}"
                )
                svc = Service.query.filter_by(name=name).first()
                if svc:
                    svc.status = status
                    svc.last_updated = datetime.utcnow()
                else:
                    svc = Service(
                        name=name,
                        status=status,
                        description=description,
                        last_updated=datetime.utcnow(),
                        host=host,
                        port=port,
                        is_remote=True
                    )
                    # Auto-tagging
                    if not no_auto_tag:
                        tag_names = auto_assign_tags({
                            'name': name,
                            'description': description,
                            'port': port,
                            'source': 'port',
                            'host': host
                        }, log=True)
                        svc.tags = []
                        for tag_name in tag_names:
                            tag = Tag.query.filter_by(name=tag_name).first()
                            if not tag:
                                tag = Tag(name=tag_name)
                                db.session.add(tag)
                            svc.tags.append(tag)
                    db.session.add(svc)
                updated_services.append(f"{name} → {status}")
            db.session.commit()
            return updated_services, None
        except Exception as e:
            db.session.rollback()
            return [], f"Error syncing ports: {e}"

    @staticmethod
    def sync_remote_hosts(timeout=3, retry_count=1):
        """Sync remote host statuses"""
        services = Service.query.filter(
            Service.host.isnot(None),
            Service.port.isnot(None)
        ).all()
        
        updated_services = []

        for svc in services:
            success = False
            for _ in range(retry_count):
                try:
                    with socket.create_connection((svc.host, svc.port), timeout=timeout):
                        success = True
                        break
                except:
                    time.sleep(1)  # Wait before retry
            svc.status = "up" if success else "down"
            svc.last_updated = datetime.utcnow()
            # Optionally update tags for remote hosts
            tag_names = auto_assign_tags({
                'name': svc.name,
                'description': svc.description,
                'port': svc.port,
                'source': 'remote',
                'host': svc.host
            })
            svc.tags = []
            for tag_name in tag_names:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                svc.tags.append(tag)
            updated_services.append(f"{svc.name} → {svc.status}")
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