"""
Gunicorn configuration for MiniStatus.
Loads FLASK_HOST and FLASK_PORT from .env (via app's load_dotenv on import).
"""
import os
import multiprocessing

# Load .env before reading config (run.py/app does this, but ensure it's loaded for bind)
from dotenv import load_dotenv
load_dotenv()

bind = f"{os.getenv('FLASK_HOST', '0.0.0.0')}:{os.getenv('FLASK_PORT', '5000')}"
workers = int(os.getenv('GUNICORN_WORKERS', '2'))
worker_class = 'sync'
threads = 1
timeout = 120
keepalive = 5

# Logging
accesslog = '-'
errorlog = '-'
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')

# Process naming
proc_name = 'ministatus'

# Preload disabled: SQLite + multiple workers can have connection issues when preloading
preload = False
