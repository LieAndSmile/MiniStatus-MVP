
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

Awesome — thanks for sharing the original `README.md`. It looks great already — well-structured and clear.

So instead of **overwriting**, the best approach is to **append the Helm deployment section** to the bottom, keeping your structure intact ✅

---

## ✅ Updated Plan

We’ll **add a new section like this** at the end of your current README:

```markdown
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

> The chart lives in: `charts/ministatus/`
```

---

## 🛠 Let’s Do It

You can either:

### 🔹 Manually paste that section at the end  
– OR –

### 🔹 I can generate a clean `README-merged.md` for you to download and commit. Want that?

Let me know!


## 📄 License

MIT © [LieAndSmile](https://github.com/LieAndSmile)


