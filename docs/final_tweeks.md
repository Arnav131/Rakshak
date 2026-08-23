# Rakshak — Final Tweaks for Docker + Render Deployment

> Handoff doc. Repo already cloned & audited (files verified via grep for actual
> imports/usage — nothing listed below is a guess). Execute the sections in order.
> Section 1 = file reorg. Section 2 = Docker + Django production config.
> Section 3 = Render setup. Section 4 = verification checklist.

---

## 0. Target Operational Root Tree (after cleanup)

This is what the repo root should look like once non-operational files are moved out.
Everything in this tree is required for the app to actually run.

```
Rakshak/
├── backend/
│   ├── rakshak_project/     # settings.py, urls.py, wsgi.py, asgi.py
│   ├── core/
│   ├── railway/             # models, migrations, seed commands only
│   ├── sensors/
│   ├── alerts/
│   ├── tickets/
│   ├── map_view/
│   ├── simulation/
│   ├── patrol/
│   ├── readiness/
│   ├── ai_integration/
│   ├── agents/              # imported by ai_integration/alert_service.py — required
│   ├── ai_models/           # anomaly_model.pkl, fault_model.pkl, simple_pipeline.py
│   └── manage.py
├── frontend/
│   ├── templates/
│   └── static/
├── docs/
├── non_prod/
├── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile
├── .dockerignore
├── docker-entrypoint.sh
└── render.yaml
```

---

## 1. File Reorganization

Move the following. None of these are imported by any Django app, view, url, or
settings module (verified with `grep -rl` across the codebase) — moving them is safe
and will not break the app.

### 1.1 Move to `docs/` (merge into existing `docs/` folder)

```
AI-Powered-Predictive-Railway-Safety-System.pptx  -> docs/
Notes.md                                          -> docs/
Notes1.md                                         -> docs/
presentation/                                     -> docs/presentation/
"Helios dashboard UI mockups/"                    -> docs/helios-ui-mockups/
```

### 1.2 Move to `non_prod/` (create this new folder)

```
ai_engin/                                         -> non_prod/ai_engin/
notebooks/                                        -> non_prod/notebooks/
demo_assets/                                      -> non_prod/demo_assets/
check_all_py.py                                   -> non_prod/check_all_py.py

backend/check_templates.py                        -> non_prod/backend_scripts/check_templates.py
backend/smoke_test_predict.py                     -> non_prod/backend_scripts/smoke_test_predict.py
backend/smoke_test_render.py                      -> non_prod/backend_scripts/smoke_test_render.py
backend/test_queries.py                           -> non_prod/backend_scripts/test_queries.py
backend/validate_api.py                           -> non_prod/backend_scripts/validate_api.py
backend/verify_endpoints.py                       -> non_prod/backend_scripts/verify_endpoints.py

backend/railway/build_complete_india_osm_network.py    -> non_prod/railway_data_scripts/
backend/railway/build_railway_data.py                  -> non_prod/railway_data_scripts/
backend/railway/download_full_india_osm_railways.py    -> non_prod/railway_data_scripts/
backend/railway/extract_osm_test.py                    -> non_prod/railway_data_scripts/
backend/railway/fetch_real_india_railways.py            -> non_prod/railway_data_scripts/
backend/railway/generate_dense_india_railways.py        -> non_prod/railway_data_scripts/
backend/railway/generate_osm_railway_dataset.py          -> non_prod/railway_data_scripts/
backend/railway/test_grid_query.py                       -> non_prod/railway_data_scripts/
backend/railway/verify_final_map.py                      -> non_prod/railway_data_scripts/
```

### 1.3 Delete (unused, empty)

```
backend/package-lock.json   # contains only {"packages": {}} — no npm deps exist, dead file
```

**Do NOT move/touch:** anything under `backend/ai_models/` (the `.pkl` files are loaded
at runtime by `ai_integration.local_provider.LocalPickleProvider`, path is hardcoded
relative to `BASE_DIR` in `settings.py`).

---

## 2. Docker Setup

### 2.1 Add to `requirements.txt`

```
gunicorn>=21.2.0
whitenoise>=6.6.0
```

(Keep everything already in requirements.txt as-is — Django, dj-database-url,
python-dotenv, psycopg2-binary, requests are all fine.)

### 2.2 Patch `backend/rakshak_project/settings.py`

**a) Add whitenoise to `MIDDLEWARE`** — must sit directly after `SecurityMiddleware`:

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   # <-- ADD THIS LINE
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'railway.middleware.CurrentUserMiddleware',
]
```

**b) Add compressed static storage** — right after the existing static files block
(`STATIC_URL`, `STATICFILES_DIRS`, `STATIC_ROOT`):

```python
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

**c) Fix `ALLOWED_HOSTS` to auto-trust Render's domain** — replace the existing line:

```python
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')
```

with:

```python
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
```

**d) Add HTTPS/proxy + CSRF trust for Render** — add this block right below the
`ALLOWED_HOSTS` block above:

```python
CSRF_TRUSTED_ORIGINS = [
    f"https://{RENDER_EXTERNAL_HOSTNAME}"
] if RENDER_EXTERNAL_HOSTNAME else []

extra_csrf_origins = os.environ.get('CSRF_TRUSTED_ORIGINS')
if extra_csrf_origins:
    CSRF_TRUSTED_ORIGINS += extra_csrf_origins.split(',')

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

> Without `SECURE_PROXY_SSL_HEADER`, Django will think every request over Render's
> proxy is plain HTTP and CSRF/login will misbehave.

### 2.3 Create `Dockerfile` (repo root)

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for psycopg2-binary + general build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# collectstatic works fine at build time because SECRET_KEY/DEBUG have
# safe fallbacks in settings.py — no DB connection required for this step
RUN cd backend && python manage.py collectstatic --noinput

RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
```

### 2.4 Create `docker-entrypoint.sh` (repo root)

```bash
#!/bin/sh
set -e

cd backend

echo "Running migrations..."
python manage.py migrate --noinput

echo "Starting gunicorn..."
exec gunicorn rakshak_project.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 3 \
    --timeout 120
```

### 2.5 Create `.dockerignore` (repo root)

```
.git
.gitignore
.env
*.pyc
__pycache__/
*.egg-info/
venv/
.venv/
env/
docs/
non_prod/
backend/staticfiles/
backend/db.sqlite3
*.md
README.md
```

---

## 3. Render Setup

### 3.1 Create `render.yaml` (repo root) — for Render's Blueprint / Infrastructure-as-Code

```yaml
services:
  - type: web
    name: rakshak
    env: docker
    dockerfilePath: ./Dockerfile
    plan: free
    envVars:
      - key: SECRET_KEY
        generateValue: true
      - key: DEBUG
        value: "False"
      - key: ALLOWED_HOSTS
        value: ""
      - key: DATABASE_URL
        sync: false
      - key: DATABASE_CONN_MAX_AGE
        value: "60"
      - key: GEMINI_API_KEY
        sync: false
```

`sync: false` means: set that value manually in the Render dashboard (secrets should
never live in render.yaml / git).

### 3.2 Manual env vars to set in Render Dashboard (if not using render.yaml)

| Key | Value |
|---|---|
| `SECRET_KEY` | generate a new random 50-char string — do NOT reuse the prototype default |
| `DEBUG` | `False` |
| `DATABASE_URL` | Supabase/Render Postgres connection string, with `?sslmode=require` |
| `DATABASE_CONN_MAX_AGE` | `60` |
| `GEMINI_API_KEY` | optional, only if using Gemini simulation provider |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GROK_API_KEY` | optional fallback providers |

`ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` do **not** need manual setting — Render
auto-injects `RENDER_EXTERNAL_HOSTNAME`, which `settings.py` now reads automatically
(see 2.2c/2.2d above).

### 3.3 Render service config (if creating manually instead of via render.yaml)

- **Runtime:** Docker
- **Dockerfile path:** `./Dockerfile`
- **Docker context:** repo root
- Render auto-detects `EXPOSE 8000` and `$PORT` — no separate build/start command
  needed since the Dockerfile's `ENTRYPOINT` handles migrate + gunicorn start.

### 3.4 Seed data (run once after first deploy, via Render Shell)

```bash
cd backend
python manage.py seed_master_data
python manage.py seed_routes
python manage.py seed_sensors
python manage.py seed_demo_data
python manage.py seed_readiness_data
python manage.py seed_users
```

(Order matters — run exactly in this sequence, same as local setup.)

---

## 4. Verification Checklist (after deploy)

- [ ] Build succeeds, `collectstatic` runs with no errors during image build
- [ ] Container starts, migration logs show `Applying ...` then gunicorn boot log
- [ ] `https://<your-app>.onrender.com/` loads dashboard, CSS/JS load correctly (whitenoise working)
- [ ] Login page works, CSRF does not throw 403 (proxy header fix working)
- [ ] `/admin/` reachable
- [ ] `DEBUG=False` confirmed — visiting a broken URL shows generic 400/404, not a traceback
- [ ] `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` correctly picked up `RENDER_EXTERNAL_HOSTNAME`
- [ ] Seed commands run once, dashboard shows demo data
- [ ] `backend/ai_models/*.pkl` load correctly (check `/api/predict/` returns a real response, not an error)

---

## Notes

- This repo is explicitly a **prototype/demo system** per its own README — AI inference
  is a threshold-based stub, telemetry is synthetic. Deploying it makes it *reachable*,
  not production-grade. That's out of scope for this doc — this doc only gets it running
  cleanly on Render via Docker.
- SQLite fallback in `settings.py` will NOT persist on Render (ephemeral filesystem) —
  `DATABASE_URL` must always be set, or all data is lost on every redeploy/restart.
