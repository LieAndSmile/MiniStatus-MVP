# 📡 MiniStatus

**MiniStatus** is a lightweight, self-hosted service status dashboard built for developers, homelabs, and small teams.

Version: 1.1.0

- ✅ Track service health manually or via API
- 🔍 Advanced search and filtering capabilities
- 🔐 Admin panel with password protection
- 📡 Docker & systemd sync
- 🌓 Dark/Light theme with persistent preference
- 🎯 Built with Flask + SQLite, minimal resources

> No Prometheus. No Grafana. Just clean uptime visibility.

<p align="center">
  <img src="./docs/DarkTheme.png" width="120%" />
  <img src="./docs/LightTheme.png" width="120%" />
</p>

---

## 📖 Help: MiniStatus Dashboard Feature Documentation

### 1. Static GitHub Repos Panel
Display a list of favorite or important GitHub repositories on your dashboard.
- In `app/routes/public.py`, add your repos to the `github_repos` list.
- This list is passed to the template and rendered as a panel on the homepage.
- To add more repos, just add more dictionaries to the `github_repos` list.

### 2. Using YAML Files for Configuration
MiniStatus supports YAML files for configuration of certain features, making it easy to manage and version-control your dashboard settings.

> **All YAML config files should now be placed in the `config/` directory in your project root.**
> For example: `MiniStatus-MVP/config/auto_tag_rules.yaml`, `MiniStatus-MVP/config/quick_links.yaml`, etc.

#### a. Auto-Tag Rules (`auto_tag_rules.yaml`)
- **Purpose:** Automatically assign tags to services based on rules.
- **Location:** Place your YAML file at the root of your project or mount it in Docker as `/app/auto_tag_rules.yaml`.
- **Example format:**
  ```yaml
  rules:
    - match: "docker"
      tags: ["docker", "container"]
    - match: "nginx"
      tags: ["web", "reverse-proxy"]
    - match: "postgres"
      tags: ["database", "sql"]
  ```
- **How it works:** When a service name matches the `match` string, the listed tags are applied. You can manage these rules from the Admin UI at `/admin/auto-tag-rules` or by editing the YAML file directly.
- **Reference:** See [MiniStatus-MVP GitHub Repo](https://github.com/LieAndSmile/MiniStatus-MVP) for more details.

#### b. Services List (`services.yaml`)
- **Purpose:** Define and manage the list of services to be monitored.
- **Example format:**
  ```yaml
  services:
    - name: nginx
      description: "Web server"
      tags: ["web", "reverse-proxy"]
      url: "http://localhost"
      status: "up"
    - name: postgres
      description: "Database server"
      tags: ["database", "sql"]
      url: "localhost:5432"
      status: "down"
  ```
- **How it works:** Each service entry defines its name, description, tags, URL, and status. You can import or sync services from this file via the Admin UI or CLI.

#### c. Quick Links (`quick_links.yaml`)
- **Purpose:** Add custom quick links to the dashboard for easy access to tools and resources.
- **Example format:**
  ```yaml
  links:
    - name: Grafana
      url: "http://grafana.local"
      category: "Monitoring"
      icon_url: "/static/icons/grafana.svg"
    - name: GitLab
      url: "http://gitlab.local"
      category: "DevOps"
      icon_url: "/static/icons/gitlab.svg"
  ```
- **How it works:** Each link appears in the Quick Links panel, grouped by category.

### 3. How to Use These YAML Files
- Mount or place the YAML files in your project root or the appropriate config directory.
- For Docker: Mount them as volumes, e.g.:
  ```bash
  -v $(pwd)/auto_tag_rules.yaml:/app/auto_tag_rules.yaml:ro
  -v $(pwd)/services.yaml:/app/services.yaml:ro
  -v $(pwd)/quick_links.yaml:/app/quick_links.yaml:ro
  ```
- Edit and reload: Changes to YAML files are picked up automatically (or via a reload in the Admin UI).

Place all your YAML config files in the `config/` directory. For Docker, mount the entire config directory:
```bash
-v $(pwd)/config:/app/config:ro
```
Edit and reload: Changes to YAML files are picked up automatically (or via a reload in the Admin UI).

### 4. References
- [MiniStatus-MVP GitHub Repo](https://github.com/LieAndSmile/MiniStatus-MVP)
- See the repo's README for more advanced configuration and deployment options.

If you need sample files or want to automate the loading of these YAMLs, let the development team know!

---

## 🚀 Getting Started (Standalone)

### Quick Start

```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install required packages
sudo apt install -y git python3 python3-venv python3-pip

# 3. Clone the repository
git clone https://github.com/LieAndSmile/MiniStatus-MVP.git
cd MiniStatus-MVP

# 4. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 5. Install dependencies
pip install -r requirements.txt || pip install flask flask_sqlalchemy flask_migrate python-dotenv psutil PyYAML requests

# 6. Set up environment variables
cp .env.example .env
nano .env   # <-- set API_KEY and ADMIN_PASSWORD

# 7. Run the application
python run.py

```

- Edit `.env` to set your secrets and admin credentials.
- Place all YAML config files in the `config/` directory.
- Access the app at [http://localhost:5000](http://localhost:5000)

---

## 🔐 Admin Panel
- Visit `/admin` and log in with your configured ADMIN_USERNAME and ADMIN_PASSWORD (default: admin/admin123)
- Add, update, or delete services
- Sync Docker or systemd services
- Monitor local ports
- Track remote host status

---

## ⎈ Deploy to Kubernetes with Helm

### 📦 Install
```bash
helm install ministatus ./charts/ministatus
```
Customize:
```bash
helm install ministatus ./charts/ministatus \
  --set env.SECRET_KEY="yoursecret" \
  --set env.ADMIN_SECRET="youradmin"
```

### 🔁 Upgrade
```bash
helm upgrade ministatus ./charts/ministatus --set image.tag=v1.0.0
```

### 🧼 Uninstall
```bash
helm uninstall ministatus
```
Chart lives in: `charts/ministatus/`

---

## 📡 Features

| Feature                        | Status  |
|-------------------------------|----------|
| Manual service status updates | ✅ Done  |
| Docker & systemd sync         | ✅ Done  |
| `/report` API w/ key auth     | ✅ Done  |
| Admin panel (web UI)          | ✅ Done  |
| Dark/Light theme support      | ✅ Done  |
| Local port monitoring         | ✅ Done  |
| Remote host monitoring        | ✅ Done  |
| Collapsible sidebar          | ✅ Done  |
| Real-time search & filters    | ✅ Done  |
| Dynamic sorting              | ✅ Done  |

---

## 🔜 Roadmap (MiniStatus Pro)
- [ ] Telegram & Slack alerting
- [ ] Incident history & resolution notes
- [ ] Multi-project dashboard
- [ ] Role-based auth (`admin`, `viewer`)
- [ ] JSON & CSV export
- [ ] GitHub deploy webhook support
- [ ] Custom theme support
- [ ] Service grouping & tags

---

## 🏷️ Auto-Tag Rules (v1.1.0+)

You can customize how tags are automatically assigned to services:

- **YAML/JSON Config:**
  - Mount a config file (see above) for advanced or version-controlled rules.
  - Edit and reload as needed.
- **Admin UI:**
  - Manage auto-tag rules from the web dashboard at `/admin/auto-tag-rules`.
  - No restart required; changes take effect immediately.

If both are present, the config file takes precedence. Remove or rename it to use the UI/database rules only.

---

## ⭐ Support & Feedback
If you like the project, give it a ⭐ or open an issue for feedback or bugs.

> Found a bug or have a suggestion? Let us know via [Issues](https://github.com/yourproject/issues).

---

## 📄 License
MIT © [LieAndSmile](https://github.com/LieAndSmile)

## 🔐 Security Summary Widget

The Security Summary widget provides a quick overview of key security-related metrics on your system:

| Check                                | Description                                 |
| ------------------------------------- | ------------------------------------------- |
| ✅ Recent SSH logins                  | Shows the most recent successful SSH logins  |
| ⚠️ Failed SSH logins (24h)            | Counts failed SSH login attempts in 24 hours |
| ✅ Open ports (non-root scan)          | Lists open TCP/UDP ports using `ss`          |
| 👤 Users with shell access             | Lists users with valid login shells          |
| ⚠️ Suspicious users/groups             | Finds UID 0 users other than root            |
| 📁 World-writable dirs in `$HOME`      | Warns about insecure file permissions        |
| ⛔ Root login in /etc/passwd           | Shows if root login shell is enabled         |
| 📦 Outdated packages                   | Shows number of upgradable packages          |

**Example Output:**

```
SSH Logins: 5 recent
Failed SSH Logins (24h): 3
Open Ports: 25
Shell Users: 3 (root, lis61, service)
Suspicious UID 0 entries: none
World-writable dirs in home: 0
Root login in /etc/passwd: ✔️ (shell: /bin/bash)
Outdated packages: 2 package(s) need upgrade
```

- The widget is card-style and appears on the dashboard.
- Failed SSH logins in the last 24 hours are highlighted if present.
- Outdated packages can be expanded to show details.

---

