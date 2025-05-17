# 📜 CHANGELOG

All notable changes to this project will be documented in this file.

This project follows [Semantic Versioning](https://semver.org/) and uses the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.

## [1.0.0] - 2024-03-20
### Added
- Initial stable release of MiniStatus
- Core Features:
  * Service status tracking with manual and API updates
  * Admin dashboard with password protection
  * Docker & systemd service sync
  * Public status dashboard with filtering
  * Dark/Light theme support
  * Local port monitoring
  * Remote host monitoring
  * Real-time search & filtering
  * Dynamic sorting
  * Responsive design
  * Advanced filtering capabilities
  * Status indicators with colors
  * Service descriptions
  * Collapsible sidebar
- Deployment Options:
  * Docker container with pre-built images
  * Docker Compose configurations
  * Kubernetes Helm chart
- Security Features:
  * Admin authentication
  * API key authentication
  * Secure Docker socket handling
  * Proper Docker socket permissions
  * Least-privilege principle implementation
- Documentation:
  * Installation guides
  * Configuration options
  * API documentation
  * Security best practices
  * Deployment scenarios

## [1.1.0] - 2025-05-17
### Added
- **Redesigned Public Homepage:**
  - Modern, compact cards for System Health, System Identity, and Calendar widgets.
  - Responsive layout and improved dark theme.
- **Dynamic Quick Links Panel:**
  - Auto-detects known services (Grafana, Pi-hole, Cockpit, Portainer, etc.).
  - Supports manual additions via `quick_links.yaml` (YAML format).
  - Displays app icons and categories in a responsive grid.
- **Calendar Widget:**
  - Integrated FullCalendar with country selector.
  - Fetches and displays public holidays using the Nager.Date API.
  - Compact, visually consistent with other cards.
- **Backend Enhancements:**
  - Utilities for system stats, identity, and service detection using `psutil` and `PyYAML`.
- **UI/UX Improvements:**
  - Sidebar label hiding when collapsed (using `.nav-label`).
  - Main content area adapts to sidebar state.
  - Improved card styling, spacing, and responsiveness.
- **Documentation:**
  - Updated README for v1.1.0 features and usage.
- **Requirements:**
  - Added `psutil` and `PyYAML` to `requirements.txt`.

### Changed
- Improved documentation and user experience for tag and rule management.
- Default tags and rules are now easier to extend and customize.

### Migration Notes
- If you want to use only the admin UI for rules, remove or ignore the YAML/JSON config file.
- For Docker, mount your config file or use the UI as needed.



