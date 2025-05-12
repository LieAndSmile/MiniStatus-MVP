# 📜 CHANGELOG

All notable changes to this project will be documented in this file.

This project follows [Semantic Versioning](https://semver.org/) and uses the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.

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
