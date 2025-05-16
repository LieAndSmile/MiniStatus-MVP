import re

AUTO_TAG_RULES = {
    'docker': lambda svc: svc.get('source') == 'docker',
    'systemd': lambda svc: svc.get('source') == 'systemd',
    'networking': lambda svc: str(svc.get('port')) in ['80','443','53','22','8080','8443'],
    'database': lambda svc: re.search(r"mysql|postgres|redis|mariadb|mongo|db", (svc.get('name','')+svc.get('description','')).lower()),
    'critical': lambda svc: svc.get('name','') in ['nginx','api','main-db'],
    'internal': lambda svc: re.match(r"^(10\\.|192\\.168\\.|172\\.(1[6-9]|2[0-9]|3[01])\\.)", svc.get('host') or ''),
    'external': lambda svc: svc.get('host') and not re.match(r"^(10\\.|192\\.168\\.|172\\.(1[6-9]|2[0-9]|3[01])\\.)", svc.get('host') or ''),
    'monitoring': lambda svc: re.search(r"prometheus|grafana|uptime", (svc.get('name','')+svc.get('description','')).lower()),
    'proxy': lambda svc: re.search(r"nginx|haproxy|traefik", (svc.get('name','')+svc.get('description','')).lower()),
}

def auto_assign_tags(service_data):
    tags = []
    for tag, rule in AUTO_TAG_RULES.items():
        if rule(service_data):
            tags.append(tag)
    return tags 