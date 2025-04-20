<details> <summary>Click to expand full markdown content to paste</summary>
markdown
Copy
Edit
# MiniStatus

A lightweight, self-hosted status dashboard built with Flask, SQLite, and Docker integration.

## 🔧 Features

- Real-time status updates
- Admin panel for adding/updating/deleting services
- Docker container discovery via `/sync`
- Session-based login system
- Dark mode UI with Tailwind CSS
- Floating navigation and custom 403 page

## 🚀 Quickstart

```bash
git clone https://github.com/LieAndSmile/MiniStatus-MVP.git
cd MiniStatus-MVP
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
Then open http://localhost:5000 in your browser.

📷 Screenshots
![image](https://github.com/user-attachments/assets/900a0171-4c0d-4458-8758-599167d6d710)

🧩 Tech Stack
Flask + Jinja2

SQLite + SQLAlchemy

Docker (optional sync)

Tailwind CSS

🤝 Made by
LieAndSmile

markdown
Copy
Edit

</details>

4. Save and exit (`CTRL+O`, `ENTER`, then `CTRL+X` in nano)

5. Then commit and push:
```bash
git add docs/index.md
git commit -m "Add GitHub Pages landing page"
git push
Go to your repo → Settings → Pages, and set:

Source: main

Folder: /docs

You’ll get a link like:
👉 https://lieandsmile.github.io/MiniStatus-MVP/
