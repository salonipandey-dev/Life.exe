# 12 Deployment guide

> Status: **not yet deployed.** Everything below except "Local development" is prepared but unverified in a real hosting environment. The Docker image was not built (no registry access where it was written).

## 1. Local development
Requirements: Python 3.12+ (tested 3.13), Node 22.
```bash
cd backend && pip install -r requirements-dev.txt && cd ..
cd frontend && npm install && npm run build && cd ..     # or: node frontend/scripts/build.mjs
cd backend && python -m lifeexe                           # http://127.0.0.1:8000
```
Frontend watch mode: `cd frontend && npm run dev` (rebuilds `dist/` on change; reload the browser).
Demo data: `cd backend && python scripts/seed_demo.py` then run with `LIFEEXE_DB_PATH=../data/demo.db python -m lifeexe` and sign in as `demo@lifeexe.local` / `demo passphrase 123`.

## 2. Configuration
All settings are environment variables; see `.env.example`. Production essentials:

| Variable | Production value |
|---|---|
| `LIFEEXE_ENV` | `production` (turns on Secure cookies and HSTS) |
| `LIFEEXE_DB_PATH` | path on a persistent volume, e.g. `/data/lifeexe.db` |
| `LIFEEXE_HOST` / `LIFEEXE_PORT` | `0.0.0.0` / platform port |
| `LIFEEXE_FRONTEND_DIST` | built SPA path |
| `LIFEEXE_ALLOWED_ORIGINS` | only if the UI is served from a different origin (not recommended) |

Run **one** worker: the SQLite write lock and the in-process rate limiter assume a single process.

## 3. Recommended hosting (single container + persistent disk)
Frontend and backend ship as one container (`docker/Dockerfile`), so the brief's "static frontend + managed Python service + managed PostgreSQL" split is not needed until the PostgreSQL driver lands (ADR-003). Choose a platform that offers:
- HTTPS termination with automatic certificates,
- a persistent volume (SQLite lives there),
- a free or low-cost tier that does not sleep the volume away.

Options to compare at deployment time (check current pricing and free-tier limits, which change often): Fly.io (volumes), Render (persistent disk on paid plans), Railway (volumes), or a small VM (e.g. a cloud free-tier instance) with Caddy for TLS.

```bash
docker compose up --build        # local production-like run on http://localhost:8000
```

## 4. Release steps
1. `./scripts/verify.sh` green on the release commit.
2. Bump version in `backend/lifeexe/__init__.py` and `frontend/package.json`; update `CHANGELOG.md`.
3. Back up the production database (below).
4. Deploy the new image; migrations apply automatically on start (checksummed, transactional).
5. Smoke test: `GET /api/v1/health`, sign in, open Command Center, complete a test quest on a test account.
6. Tag the commit `vX.Y.Z`.

## 5. Health, logs, monitoring
- Health: `GET /api/v1/health` → `{"status": "ok", "database": "ok", "version": ...}`; the Dockerfile defines a HEALTHCHECK.
- Logs: one JSON line per request (`request_id`, method, path, status, `duration_ms`) on stdout; errors include stack traces server-side only.
- Suggested alerts: health check failing, 5xx rate > 1%, p95 latency > 500 ms.

## 6. Backup and restore
```bash
# nightly (cron or platform scheduler)
sqlite3 /data/lifeexe.db ".backup '/data/backups/lifeexe-$(date +%F).db'"
find /data/backups -name 'lifeexe-*.db' -mtime +14 -delete
# verify
sqlite3 /data/backups/lifeexe-YYYY-MM-DD.db "PRAGMA integrity_check;"
# restore: stop app, copy backup over /data/lifeexe.db, start app
```
Copy backups off the host (object storage) at least weekly.

## 7. Moving to PostgreSQL (planned)
1. Install `psycopg[binary]`; implement a psycopg `Database` (placeholders `%s`, `RETURNING id`, per-user `SELECT ... FOR UPDATE` at the start of write use cases).
2. Apply `migrations/postgres/0001_initial.sql` to a managed instance with a migration role; run the app with a DML-only role.
3. Run the full integration suite against PostgreSQL.
4. Copy data table by table in dependency order (users → profiles → skills → quests → completions → xp_events → …), then reset identity sequences.
