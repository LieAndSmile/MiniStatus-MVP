# 📜 CHANGELOG

All notable changes to this project will be documented in this file.

This project follows [Semantic Versioning](https://semver.org/) and uses the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.

## [v1.6.0] - 2025-05-13
### Changed
- Separated remote host monitoring from local port monitoring
- Improved UI organization by moving remote host monitoring exclusively to Remote Hosts tab
- Simplified Ports dashboard to focus solely on local listening ports
- Enhanced clarity of service monitoring by removing duplicate information

### Removed
- Remote ports section from Ports dashboard to avoid confusion with Remote Hosts monitoring
- Redundant service queries in ports route handler

## [v1.5.0] - 2025-05-13
### Added
- New `ServiceSync` class in `services/sync_service.py` for centralized monitoring
- Bulk sync operation via `/sync-all` endpoint
- Comprehensive error handling across all sync operations
- Transaction management for database operations

### Changed
- Refactored sync functionality into dedicated service class
- Improved code organization with new `services` directory
- Enhanced error reporting and user feedback
- Updated route handlers to use new ServiceSync class
- Improved session management in admin routes

### Fixed
- More robust port checking with proper timeout handling
- Better error handling for Docker and systemd command failures
- Enhanced database transaction management

## [v1.4.0] - 2025-05-12
### Added
- Redesigned /ports page with dark theme and grouped UI
- Status icons (🟢 🔴 🟡) for remote port checks
- Address scope (e.g. %lo) now stripped from local ports
- Grouped TCP/UDP ports, labeled services like SSH/HTTP/Flask

### Changed
- `ports.html` layout: card → table format for monitored services
- Icons added for common ports (SSH, HTTP, etc.)

### TODO
- Add uptime logging (ServiceLog model)
- Add auto-sync via scheduler
- Add alert notifications


## [1.3.0] - 2025-05-12
### Added
- New `/ports` dashboard tab to display services with host:port
- Port checker route `/sync-ports` using Python socket
- Updated Service model with `host` and `port` fields
- Visual display of scanned ports and status

---

## [1.1.0] – 2025-05-12
### Added
- Modularized route handling using Flask Blueprints
- Separated routes into `admin`, `api`, `sync`, and `error_handlers`
- Introduced clean Blueprint registration pattern

### Changed
- Removed the monolithic `routes.py` file
- Updated `app/__init__.py` to support modular Blueprints
- Improved maintainability and scalability

---

## [1.0.0] – 2025-04-30
### Added
- Initial MiniStatus MVP release
- `/report` API endpoint with X-API-Key auth
- Admin dashboard with password protection
- SQLite-based status tracking
- Docker & systemd sync features
- Basic environment setup and `.env` support
- Kubernetes Helm chart for deployment

## [1.2.0] - 2025-05-12
### Added
- New public-facing dashboard at `/`
- Separated logic and template from `/admin` panel
- Responsive layout with status filters and service cards
- Clear visual banner indicating "Public View"

### Changed
- Updated blueprint registration to isolate `/admin` under its own prefix
