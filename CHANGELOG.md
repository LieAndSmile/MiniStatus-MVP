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

## [1.1.0] - 2025-05-16
### Added
- **Customizable Auto-Tag Rules:**
  - Support for `auto_tag_rules.yaml` or `auto_tag_rules.json` in the project root for defining auto-tagging logic.
  - Rules can be edited and reloaded without code changes.
  - YAML/JSON config is optional; if not present, falls back to database/UI rules.
- **Admin UI for Auto-Tag Rules:**
  - Manage auto-tag rules from `/admin/auto-tag-rules` (add, edit, delete, enable/disable) with no restart required.
- **`--no-auto-tag` Flag:**
  - All sync endpoints and scripts accept a `?no_auto_tag=1` query parameter or argument to skip auto-tagging during sync.
- **Transparency:**
  - The admin dashboard now displays a note under each service showing which tags would be auto-assigned ("Auto-tagged as: ...").
  - Auto-tagging actions are logged to the console for auditability.
- **Docker Support:**
  - The app supports bind-mounting the config file for Docker deployments, or using the admin UI for all rule management.

### Changed
- Improved documentation and user experience for tag and rule management.
- Default tags and rules are now easier to extend and customize.

### Migration Notes
- If you want to use only the admin UI for rules, remove or ignore the YAML/JSON config file.
- For Docker, mount your config file or use the UI as needed.


