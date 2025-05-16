import re
import os
import json
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

CONFIG_PATHS = [
    os.path.join(os.path.dirname(__file__), '../../auto_tag_rules.yaml'),
    os.path.join(os.path.dirname(__file__), '../../auto_tag_rules.json'),
]

# Default rules (Python lambdas)
DEFAULT_AUTO_TAG_RULES = {
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

# Rules loaded from config (if any)
AUTO_TAG_RULES = None

# Helper to parse config rules into lambdas
RULE_TYPE_MAP = {
    'source': lambda val: lambda svc: svc.get('source') == val,
    'port': lambda val: lambda svc: str(svc.get('port')) == str(val),
    'name_contains': lambda val: lambda svc: val.lower() in svc.get('name','').lower(),
    'description_contains': lambda val: lambda svc: val.lower() in svc.get('description','').lower(),
    'host_regex': lambda val: lambda svc: re.match(val, svc.get('host') or ''),
    'name_regex': lambda val: lambda svc: re.search(val, svc.get('name','')),
    'description_regex': lambda val: lambda svc: re.search(val, svc.get('description','')),
}

def load_auto_tag_rules():
    global AUTO_TAG_RULES
    for path in CONFIG_PATHS:
        if os.path.exists(path):
            with open(path, 'r') as f:
                if path.endswith('.yaml') or path.endswith('.yml'):
                    if not HAS_YAML:
                        raise ImportError('PyYAML is required for YAML config')
                    config = yaml.safe_load(f)
                else:
                    config = json.load(f)
            # Expecting: {tag: {type: ..., value: ...}, ...}
            rules = {}
            for tag, rule in config.items():
                rule_type = rule.get('type')
                rule_value = rule.get('value')
                if rule_type in RULE_TYPE_MAP:
                    rules[tag] = RULE_TYPE_MAP[rule_type](rule_value)
            AUTO_TAG_RULES = rules
            return
    # Fallback to default
    AUTO_TAG_RULES = DEFAULT_AUTO_TAG_RULES

# Initial load
load_auto_tag_rules()

def reload_auto_tag_rules():
    load_auto_tag_rules()

def auto_assign_tags(service_data, log=False):
    tags = []
    for tag, rule in AUTO_TAG_RULES.items():
        try:
            if rule(service_data):
                tags.append(tag)
        except Exception as e:
            if log:
                print(f"Auto-tag rule error for tag '{tag}': {e}")
    if log and tags:
        print(f"Auto-tagged as: {', '.join(tags)} for service: {service_data.get('name')}")
    return tags

def get_auto_tagged_for_service(service_data):
    return auto_assign_tags(service_data, log=False) 