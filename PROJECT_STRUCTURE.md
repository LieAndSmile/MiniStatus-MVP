# MiniStatus-MVP — Project structure

Quick directory and file map. Polymarket integration reads from **polymarket-alerts** via `POLYMARKET_DATA_PATH` (see [CONTEXT.md](CONTEXT.md) and [docs/POLYMARKET_INTEGRATION.md](docs/POLYMARKET_INTEGRATION.md)).

## Directory tree (key paths only)

```
MiniStatus-MVP/
├── run.py                    # WSGI entry (e.g. gunicorn)
├── setup.py
├── gunicorn.conf.py
├── .env.example
├── CHANGELOG.md
├── README.md
├── CONTEXT.md                # VM workflow, paths, polymarket integration summary
│
├── app/
│   ├── __init__.py
│   ├── extensions.py        # Flask extensions (DB, limiter, etc.)
│   ├── models.py             # SQLite models
│   ├── version.py
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── admin.py          # Admin panel
│   │   ├── api.py            # REST API
│   │   ├── public.py         # Public status page
│   │   ├── polymarket.py     # Polymarket dashboard (Portfolio, Open Positions, Risky, Loss Lab, Analytics, Lifecycle, Loop/Dev)
│   │   ├── ports.py
│   │   ├── remote.py
│   │   ├── sync.py           # Systemd sync
│   │   ├── error_handlers.py
│   │   └── ...
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   └── sync_service.py    # Systemd service sync
│   │
│   ├── utils/
│   │   ├── polymarket.py     # Polymarket data loading (CSVs, analytics.json); STRATEGY_OPTIONS
│   │   ├── polymarket_health.py
│   │   ├── ports.py
│   │   ├── helpers.py
│   │   ├── decorators.py
│   │   ├── password.py
│   │   ├── auto_tag.py
│   │   └── system_check.py
│   │
│   └── templates/
│       ├── base.html
│       ├── login.html
│       ├── admin.html
│       ├── polymarket.html           # Portfolio
│       ├── polymarket_nav.html        # Polymarket sub-nav
│       ├── polymarket_positions.html  # Open Positions
│       ├── polymarket_risky.html
│       ├── polymarket_loss_lab.html
│       ├── polymarket_analytics.html
│       ├── polymarket_lifecycle.html
│       ├── polymarket_loop.html       # Loop/Dev
│       ├── polymarket_time_filter.html
│       ├── polymarket_tooltips.html
│       ├── public/
│       │   └── index.html    # Public status page
│       └── ...
│
├── docs/
│   ├── POLYMARKET_INTEGRATION.md
│   ├── MINISTATUS_INTEGRATION.md
│   └── CODE_REVIEW_POLYMARKET.md
│
├── scripts/
│   ├── install.sh
│   ├── restart.sh
│   ├── start.sh
│   └── ...
│
└── tests/
    ├── test_app_structure.py
    ├── test_polymarket_health.py
    └── test_polymarket_risky.py
```

## Polymarket data sources (read from polymarket-alerts)

Configured via `POLYMARKET_DATA_PATH` (e.g. `/home/ubuntu/polymarket-alerts`). Key files:

- `alerts_log.csv` — Portfolio, P/L, resolved
- `open_positions.csv` — Open Positions tab
- `debug_candidates.csv` — Loop/Dev
- `analytics.json` — Analytics tab (cohorts, drift, exit study)
- `lifecycle.json` — Lifecycle tab
- `execution_log.csv` — Execution/drift data for analytics
- Loss Lab exports (e.g. `loss_lab_*.json`)

See the **polymarket-alerts** repo: `docs/INTEGRATION_CONTRACT.md` and `docs/DATA_PATHS.md` for the full data contract.
