# 📜 CHANGELOG

All notable changes to this project will be documented in this file.

This project follows [Semantic Versioning](https://semver.org/) and uses the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.

## [v1.7.4] - 2024-03-16
### Added
- Enhanced public dashboard with advanced filtering capabilities:
  * Real-time search functionality for services
  * Dynamic sorting options (Name A-Z/Z-A, Status, Last Updated)
  * Status-based filtering (All, Up, Down, Degraded)
  * Responsive grid layout for service cards
- Improved service card design:
  * Status indicators with appropriate colors
  * Last update timestamps
  * Service descriptions
  * Hover effects and transitions

### Changed
- Reorganized template structure:
  * Moved public dashboard to dedicated `public/` directory
  * Removed legacy template files
  * Improved template hierarchy
- Enhanced route handling for public dashboard:
  * Added proper filter parameter support
  * Optimized database queries for filtered results

### Fixed
- Resolved template precedence issues
- Fixed public dashboard filter functionality
- Improved template organization for better maintainability

## [v1.7.3] - 2024-03-15
### Fixed
- Fixed Docker container detection in Ports dashboard
  * Added proper Docker socket permissions handling
  * Container now uses host's Docker group ID for secure access
  * Improved error logging for Docker operations
- Enhanced container security
  * Removed unnecessary root group access
  * Implemented least-privilege principle for Docker socket access
  * Added fallback group ID handling for different environments

### Security
- Improved Docker socket permission handling
  * Container now runs with host's Docker group permissions
  * Removed direct socket chmod operations
  * Added documentation for secure Docker socket mounting

## [v1.7.2] - 2024-03-15
### Added
- Enhanced port scanning functionality with three distinct sections:
  - Host Machine Ports (External Services)
  - Docker Containers (Container Services)
  - Container System Services (Internal Services)
- Secure host port scanning capability
  - Scans common service ports (SSH, HTTP, databases, etc.)
  - Shows port status (open/closed/unknown)
  - Service type detection
  - Error handling and reporting
- Improved UI for port display
  - Color-coded status indicators
  - Service-specific icons
  - Detailed port information
  - Better section organization

### Security
- Implemented secure host port scanning
  - Limited to common service ports
  - Timeout-based scanning
  - No elevated privileges required
  - Container-based perspective

## [v1.7.1] - 2025-05-15
### Fixed
- Fixed Docker configuration issues with proper environment variable handling
- Resolved URL routing errors in admin dashboard for sync operations
- Fixed endpoint naming consistency between routes and templates
- Improved Docker Compose configurations with clearer separation:
  * `docker-compose.yml`: Base configuration
  * `docker-compose.dev.yml`: Development settings
  * `docker-compose.prod.yml`: Production configuration with Gunicorn
  * `docker-compose.simple.yml`: Simple deployment with pre-built image
- Updated documentation for different deployment scenarios
- Fixed template caching issues affecting UI updates

### Changed
- Reorganized Docker Compose files for better clarity
- Improved error handling in sync operations
- Enhanced deployment documentation in README

## [v1.7.0] - 2025-05-13
### Added
- Comprehensive theme system with light/dark mode support
- Theme persistence using localStorage
- Collapsible sidebar navigation
- Reusable component system with metric cards and service rows
- Modern card-based layout across all pages

### Changed
- Complete UI redesign with consistent styling
- Enhanced color scheme for better accessibility
- Improved status indicators for up/down/degraded states
- Better form styling and input fields
- Modernized table layouts with proper spacing
- Refined hover and focus states
- Smoother transitions between states

### Fixed
- Sidebar collapse behavior and text overlap
- Theme consistency across all pages
- Proper color contrast in both themes
- Mobile responsiveness issues

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
