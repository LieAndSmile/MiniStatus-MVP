# 📡 MiniStatus

**MiniStatus** is a lightweight, self-hosted service status dashboard built for developers, homelabs, and small teams.

Version: 1.1.0

- ✅ Track service health manually or via API
- 🔍 Advanced search and filtering capabilities
- 🔐 Admin panel with password protection
- 📡 Docker & systemd sync
- 🌓 Dark/Light theme with persistent preference
- 🎯 Built with Flask + SQLite, minimal resources
- 🐳 Easy to deploy (Docker, Kubernetes, or manually)

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

### 4. References
- [MiniStatus-MVP GitHub Repo](https://github.com/LieAndSmile/MiniStatus-MVP)
- See the repo's README for more advanced configuration and deployment options.

If you need sample files or want to automate the loading of these YAMLs, let the development team know!

---

## 🚀 Getting Started

### 📦 Requirements
- Docker & Docker Compose
- Python 3.12+ (for local use)
- `.env` file with secrets

### ⚙️ Environment Setup
Create a `.env` file in the root of the project:

```env
SECRET_KEY=supersecretkey123
ADMIN_SECRET=admin123
```

Or copy the example:
```bash
cp .env.example .env
```

---

### 🐳 Docker Deployment Options

#### Quick Start (using pre-built image)
```bash
# Pull the stable version
docker pull rilmay/ministatus:1.1.0

# Create a directory for persistent data
mkdir -p instance

# (Optional) Create or copy your auto_tag_rules.yaml for custom auto-tagging
# cp auto_tag_rules.yaml.example auto_tag_rules.yaml

# Run the container
docker run -d \
  --name ministatus \
  -p 5000:5000 \
  -v $(pwd)/instance:/app/instance \
  -v $(pwd)/auto_tag_rules.yaml:/app/auto_tag_rules.yaml:ro \
  -e SECRET_KEY=your-secret-key \
  -e ADMIN_SECRET=your-admin-secret \
  --restart unless-stopped \
  rilmay/ministatus:1.1.0

# If you do not mount auto_tag_rules.yaml, you can manage auto-tag rules from the admin UI at /admin/auto-tag-rules.

#### Using Docker Compose

We provide several Docker Compose configurations for different use cases:

1. **Simple Deployment** (recommended for most users)
```bash
# Using pre-built image with minimal configuration
docker-compose -f docker-compose.simple.yml up -d
```

2. **Development Mode**
```bash
# Using development configuration with live reload
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

3. **Production Mode**
```bash
# Using production configuration with Gunicorn
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

4. **Stop and Cleanup**
```bash
# Stop containers
docker-compose down

# Remove persistent data (optional)
sudo rm -rf instance/
```

The different configurations provide:
- `simple`: Pre-built image, minimal setup required
- `dev`: Live code reload, debugging enabled
- `prod`: Gunicorn server, optimized for production

Access the app at: [http://localhost:5000](http://localhost:5000)

---

### 🔐 Admin Panel
- Visit `/admin?auth=your-admin-password`
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

