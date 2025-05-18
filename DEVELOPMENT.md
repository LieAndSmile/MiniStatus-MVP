# 📊 MiniStatus Development Overview

## Project Summary

**MiniStatus** is a self-hosted, Flask-based status dashboard built for developers and homelab users. It provides real-time monitoring of service health through both manual and automated checks, displays local and remote port activity, and offers a clean admin interface with minimal dependencies.

## 🔧 Tech Stack

* **Backend**
  * Flask - Web framework
  * SQLAlchemy - ORM
  * SQLite - Database
  * Python Socket - Port monitoring
  * Docker SDK - Container monitoring (host only)
  * Systemd integration - Service monitoring

* **Frontend**
  * TailwindCSS (via CDN) - Styling
  * Dark theme UI
  * Responsive design

* **Deployment Options**
  * Standalone Python 
  
* **Authentication**
  * Environment-based admin credentials
  * X-API-Key for remote reporting

## 🏗️ Architecture

### Core Components

1. **Service Monitoring**
   * `ServiceSync` class for centralized monitoring
   * Docker container status tracking (host only)
   * Systemd service monitoring
   * Remote port availability checks

2. **Web Interface**
   * Public status dashboard (/)
   * Admin panel (/admin)
   * Ports dashboard (/ports)
   * API endpoint (/report)

3. **Database Schema**
   ```sql
   Service:
     - id: Integer (Primary Key)
     - name: String
     - status: String
     - description: String
     - last_updated: DateTime
     - host: String (Optional)
     - port: Integer (Optional)
   ```

## 📁 Key Files

| File                        | Purpose                                     |
|----------------------------|---------------------------------------------|
| `routes/admin.py`          | Admin panel and authentication              |
| `routes/ports.py`          | Port monitoring interface                   |
| `routes/sync.py`           | Service synchronization endpoints           |
| `services/sync_service.py` | Core monitoring functionality               |
| `utils/ports.py`          | Local port scanning utilities               |
| `utils/helpers.py`        | Common helper functions                     |
| `templates/ports.html`     | Port dashboard UI                          |
| `.env`                    | Configuration and secrets                   |

## ✅ Implemented Features

### Core Features
* Centralized service monitoring via `ServiceSync` class
* Authentication-protected admin interface
* API-based remote status reporting
* Bulk sync operations
* Comprehensive error handling

### Monitoring Features
* Docker container status tracking (host only)
* Systemd service monitoring
* Local port scanning
* Remote port availability checks
* Status indicators (🟢 UP, 🔴 DOWN, 🟡 DEGRADED)

### UI Features
* Dark theme interface
* Grouped service display
* Status icons and timestamps
* TCP/UDP port grouping
* Service type labeling (SSH, HTTP, etc.)

## 🎯 Development Goals

### Short-term Goals
- [ ] Implement `ServiceLog` model for uptime tracking
- [ ] Add automated sync scheduling via `apscheduler`
- [ ] Implement alert notifications system
- [ ] Add service management through web UI

### Medium-term Goals
- [ ] Implement Telegram/Discord notifications
- [ ] Add service dependency tracking
- [ ] Create detailed uptime reports
- [ ] Add service metrics collection

### Long-term Goals
- [ ] Multi-node monitoring support
- [ ] Custom plugin system
- [ ] API documentation
- [ ] Service health checks with custom parameters

## 🔄 Current Focus

We're currently enhancing the `/ports` dashboard with focus on:

1. **Uptime Tracking**
   - Implementing `ServiceLog` model
   - Adding historical status data
   - Creating uptime statistics

2. **Automation**
   - Scheduled status checks
   - Automated sync operations
   - Alert system integration

3. **UI Improvements**
   - Service management interface
   - Enhanced status visualization
   - Real-time updates

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Add tests if applicable
5. Submit a pull request

## 📚 Resources

* [Flask Documentation](https://flask.palletsprojects.com/)
* [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
* [TailwindCSS Documentation](https://tailwindcss.com/docs)

