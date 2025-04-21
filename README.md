
# 📡 MiniStatus

**MiniStatus** is a self-hosted micro status page to monitor the health of services running in your homelab, VPS, or cloud setup.

It supports:
- 🐳 Docker container health sync
- ⚙️ Systemd services scan
- 🔐 Password-protected admin panel
- 🔄 Manual status override (Up / Degraded / Down)
- 🎨 Clean UI with TailwindCSS
- 🐘 SQLite-backed persistence

---

## 🚀 Getting Started

### 📦 Requirements
- Docker & Docker Compose
- Python 3.12+ (for local use)
- `.env` file with secrets

---

### ⚙️ Environment Setup

You must create a `.env` file in the root of the project:

```env
SECRET_KEY=your-random-secret-key
ADMIN_SECRET=your-admin-password
```

To start, just copy the example file:

```bash
cp .env.example .env
```

> Never commit `.env` with real secrets!

---

### 🐳 Run with Docker (Production)

```bash
docker-compose --env-file .env up --build -d
```

Access the app at: [http://localhost:5000](http://localhost:5000)

---

### 🧪 Run in Dev Mode

```bash
docker-compose -f docker-compose.dev.yml --env-file .env.dev up --build
```

This uses volume mounts and Flask's dev server.

---

## 🛠️ Admin Panel

- Visit `/admin?auth=your-admin-password`
- Add, update, or delete services
- Sync Docker or systemd services

---

## 🧪 CI/CD (Optional)

You can enable GitHub Actions to:
- Auto-build Docker images
- Push to Docker Hub

See: `.github/workflows/docker-build-push.yml`

---

## 📸 Screenshot

![MiniStatus Dashboard](./docs/preview.png)

---

## 📄 License

MIT © [LieAndSmile](https://github.com/LieAndSmile)
