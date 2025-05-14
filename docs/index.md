# 📡 MiniStatus

**MiniStatus** is a self-hosted micro status page to monitor the health of services running in your homelab, VPS, or cloud setup.

It supports:
- 🐳 Docker container health sync
- ⚙️ Systemd services scan
- 🔐 Password-protected admin panel
- 🔄 Manual status override (Up / Degraded / Down)
- 🎨 Clean UI with TailwindCSS
- 🐘 SQLite-backed persistence

![MiniStatus Dashboard](./preview.png)

---

## 🚀 Getting Started

### 📦 Requirements
- Docker & Docker Compose
- Python 3.12+ (for local use)
- `.env` file with secrets

---

### ⚙️ Environment Setup

You must create a `.env` file in the root of the project with the following variables:

```env
# Flask config
FLASK_APP=run.py
FLASK_ENV=development

# Security
SECRET_KEY=your-secret-key-here

# Admin auth
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-admin-password-here
```

To start, just copy the template file:

```bash
cp env.template .env
```

Then edit the `.env` file to set your own secure values for `SECRET_KEY` and `ADMIN_PASSWORD`.

---

### 🐳 Run with Docker (Production)

```bash
docker-compose --env-file .env up --build -d
```

Access the app at: [http://localhost:5000](http://localhost:5000)

---

### 🧪 Run in Dev Mode

```bash
docker-compose -f docker-compose.dev.yml --env-file .env up --build
```

This uses volume mounts and Flask's dev server.

---

## 🛠️ Admin Panel

- Visit `/admin` or click the "Admin" link
- Log in with:
  - Username: `admin` (or your custom ADMIN_USERNAME)
  - Password: Your configured ADMIN_PASSWORD
- Add, update, or delete services
- Sync Docker or systemd services

---

## ⎈ Deploy to Kubernetes with Helm

MiniStatus includes a Helm chart for simple Kubernetes deployment.

### 📦 Install with Helm

```bash
helm install ministatus ./charts/ministatus
```

Customize it with your own values:

```bash
helm install ministatus ./charts/ministatus \
  --set env.SECRET_KEY="yoursecret" \
  --set env.ADMIN_USERNAME="admin" \
  --set env.ADMIN_PASSWORD="youradmin"
```

### 🔁 Upgrade

```bash
helm upgrade ministatus ./charts/ministatus --set image.tag=v1.0.0
```

### 🧼 Uninstall

```bash
helm uninstall ministatus
```

> The chart lives in: `charts/ministatus/`

---

## 📄 License

MIT © [LieAndSmile](https://github.com/LieAndSmile)
