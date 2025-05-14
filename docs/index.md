# 📡 MiniStatus

**MiniStatus** is a self-hosted micro status page to monitor the health of services running in your homelab, VPS, or cloud setup.

## ✨ Features
- 🐳 Docker container health sync
- ⚙️ Systemd services scan
- 🔐 Password-protected admin panel
- 🌓 Dark/Light theme with persistent preference
- 📡 Local port & remote host monitoring
- 🎯 Reusable component system
- 🎨 Modern UI with responsive design
- 🗄️ SQLite-backed persistence

<div style="display: flex; gap: 20px; margin: 30px 0;">
  <div>
    <h4>🌙 Dark Theme</h4>
    <img src="./DarkTheme.png" width="100%" alt="Dark Theme" />
  </div>
  <div>
    <h4>☀️ Light Theme</h4>
    <img src="./LightTheme.png" width="100%" alt="Light Theme" />
  </div>
</div>

---

## 🚀 Getting Started

### 📦 Requirements
- Docker & Docker Compose
- Python 3.12+ (for local use)
- `.env` file with secrets

---

### ⚙️ Environment Setup

Create a `.env` file in the root of the project with:

```env
# Security
SECRET_KEY=your-secret-key-here
ADMIN_SECRET=your-admin-password-here
```

Quick setup:
```bash
cp env.template .env
```

Then edit the `.env` file with your secure values.

---

### 🐳 Docker Deployment Options

#### Quick Start (Pre-built Image)
```bash
# Pull the latest image
docker pull rilmay/ministatus:latest

# Create persistent storage
mkdir -p instance

# Run the container
docker run -d \
  --name ministatus \
  -p 5000:5000 \
  -v $(pwd)/instance:/app/instance \
  -e SECRET_KEY=your-secret-key \
  -e ADMIN_SECRET=your-admin-secret \
  --restart unless-stopped \
  rilmay/ministatus:latest
```

#### Using Docker Compose

1. **Production Mode**
```bash
# Using production configuration
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

2. **Development Mode**
```bash
# Using development configuration with live reload
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

3. **Stop and Cleanup**
```bash
# Stop containers
docker-compose down

# Remove persistent data (optional)
sudo rm -rf instance/
```

Access the app at: [http://localhost:5000](http://localhost:5000)

---

## 🛠️ Admin Panel

- Visit `/admin?auth=your-admin-password`
- Add, update, or delete services
- Sync Docker or systemd services
- Monitor local ports
- Track remote host status
- Toggle theme preference

---

## ⎈ Deploy to Kubernetes with Helm

### 📦 Install with Helm
```bash
helm install ministatus ./charts/ministatus
```

Customize values:
```bash
helm install ministatus ./charts/ministatus \
  --set env.SECRET_KEY="yoursecret" \
  --set env.ADMIN_SECRET="youradmin"
```

### 🔁 Upgrade
```bash
helm upgrade ministatus ./charts/ministatus --set image.tag=v1.7.0
```

### 🧼 Uninstall
```bash
helm uninstall ministatus
```

> The chart lives in: `charts/ministatus/`

---

## 🔜 Coming Soon (MiniStatus Pro)
- 📱 Telegram & Slack alerting
- 📝 Incident history & resolution notes
- 🏢 Multi-project dashboard
- 👥 Role-based access control
- 📊 JSON & CSV export
- 🔄 GitHub deploy webhook support
- 🎨 Custom theme support
- 🏷️ Service grouping & tags

---

## 📄 License

MIT © [LieAndSmile](https://github.com/LieAndSmile)
