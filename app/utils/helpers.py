# app/utils/helpers.py

def interpret_docker_status(raw_status):
    raw = raw_status.lower()

    if "up" in raw:
        return "up"
    elif "exited" in raw or "dead" in raw:
        return "down"
    else:
        return "degraded"
