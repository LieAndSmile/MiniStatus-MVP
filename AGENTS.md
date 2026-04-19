# Agent rules for MiniStatus-MVP

Read this **before** doing anything in this repo. These rules exist because real
mistakes were made and we don't want to repeat them.

---

## 1. Never commit env / secret files

Anything matching the following patterns is forbidden in commits:

- `.env`, `.env.*` (any extension — `.local`, `.dev`, `.bak`, `.prod`, …)
  Exception: **`.env.example`** is the documented template and is safe.
- `*.bak`, `*.swp`, `*.swo`, `*~` (editor / sed backups)
- `cookies.txt`, `secrets.json`, `credentials.json`, `*.pem`, `*.key`,
  `*.pfx`, `id_rsa`, `id_ed25519`

A pre-commit hook in `.githooks/pre-commit` enforces this. It is enabled
automatically by `scripts/install.sh`. If you're working in a fresh clone,
turn it on once with:

```bash
git config core.hooksPath .githooks
```

If the hook ever blocks something you genuinely need to commit, **rename the
file**. Do not bypass with `--no-verify`.

## 2. Editing files: prefer in-place tools, never `sed -i.bak`

- ✅ `StrReplace`, `Write`, `EditNotebook` — they don't leave backup files.
- ✅ `sed -i 's/.../.../'` (no extension) — true in-place, no backup.
- ❌ `sed -i.bak '...'` — leaves `<file>.bak` next to the original. This is
  exactly how secrets leaked into git on commit `a3653da`.

If you must use `sed` for a bulk transform, immediately delete the `.bak`
artifact in the same shell call, or use `sed -i ''` (BSD) / `sed -i` (GNU)
without an extension.

## 3. `git add -A` requires deliberation

Before running `git add -A` or `git add .`:

1. Run `git status --short` and **read every line**.
2. If any path looks like an env / backup / secret file, stop and remove it.
3. Only then stage and commit.

Better: stage explicit paths (`git add file1 file2 …`) when only a few files
changed.

## 4. Pushes to `main`

- Normal forward pushes are fine.
- **Force pushes to `main` require explicit human consent.** Even after a
  secret leak, the agent must stop and ask before `git push --force`. The user
  may prefer to leave history alone and rotate secrets instead.

## 5. Service / deploy facts

- Production runs as a systemd service (`ministatus.service`) using
  `.venv/bin/gunicorn`. **Not Docker, not `scripts/venv/`.** If you see
  references to `scripts/venv/` or a `Dockerfile`, they are stale.
- Reload after backend changes: `sudo systemctl restart ministatus`.
- Tests: `.venv/bin/pytest -q`.
- Workspace lives directly on the VM — there is no separate deploy step.

## 6. Useful repo conventions

- Templates: Jinja2 in `app/templates/`. Shared partials in
  `app/templates/_partials/`. Always `{% include %}` / `{% from … import %}`,
  no inlining of the same block twice.
- Polymarket data is read-only from `POLYMARKET_DATA_PATH` (the
  polymarket-alerts repo). MiniStatus never writes there.
- Schema is shared via `tests/fixtures/alerts_log_header.json` and the
  matching producer copy. Don't change column names without updating both.

## 7. CHANGELOG

Add a short bullet under the current `[1.7.x]` section (or bump the version
if your change warrants it) for any user-visible change. Keep entries
specific to the change, not narratives.
