### 1. 📛 Project Title + One-liner

```markdown
# MiniStatus

A lightweight, self-hosted status dashboard for tracking your services — Docker-aware, dark-themed, and DevOps-friendly.
```

---

### 2. 🚀 Features (Bulleted list)

```markdown
## Features

- 🟢 Real-time status dashboard
- 🔐 Session-based login system
- 🛠 Admin panel to add/update/delete services
- 📦 Docker container discovery
- 🌓 Dark mode UI with Tailwind CSS
- 📡 Sync running containers with one click
- 🔧 Custom 403 error page
```

---

### 3. 📸 Screenshots 

```markdown
![MiniStatus Dashboard](./docs/preview.png)
 ```

### 4. ⚙️ Getting Started

```markdown
## Getting Started

1. Clone the repo:
   ```bash
   git clone https://github.com/LieAndSmile/MiniStatus-MVP.git
   cd MiniStatus-MVP
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up `.env`:
   ```bash
   cp .env.example .env  # or create it manually
   ```

5. Run the app:
   ```bash
   python run.py
   ```

6. Open your browser:
   ```
   http://127.0.0.1:5000/
   ```

- Login at `/login` with your password from `.env` (`ADMIN_SECRET`)
```
 ```
### 5. 🧩 Future Plans / TODO

```markdown
## Roadmap

- [ ] Add API endpoint `/status.json`
- [ ] Add Telegram alerting
- [ ] Docker Compose support
- [ ] Uptime tracking and incident timeline
```

---

### 6. 📜 License & Credits

```markdown
## License

MIT — use freely, improve freely.

## Made with ❤️ by [@LieAndSmile](https://github.com/LieAndSmile)
```
