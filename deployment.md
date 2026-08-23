# Rakshak — Deployment Guide (Docker + CI/CD GitHub Actions)

> Yeh guide tujhe step-by-step batayegi ki Rakshak ko Docker se locally test karna hai,
> GitHub Actions se CI/CD pipeline set karna hai, aur Render pe deploy karna hai.
> **Ek bhi step skip nahi kiya gaya hai** — bilkul beginner-friendly hai.

---

## Table of Contents

1. [Prerequisites — Pehle Yeh Install Karo](#1-prerequisites--pehle-yeh-install-karo)
2. [Local Docker Setup — Apne Computer Pe Test Karo](#2-local-docker-setup--apne-computer-pe-test-karo)
3. [GitHub Repository Setup](#3-github-repository-setup)
4. [Supabase/PostgreSQL Database Setup](#4-supabasepostgresql-database-setup)
5. [Render Pe Deploy Karo](#5-render-pe-deploy-karo)
6. [GitHub Actions CI/CD Pipeline](#6-github-actions-cicd-pipeline)
7. [Seed Data — Demo Data Dalo](#7-seed-data--demo-data-dalo)
8. [Verification — Check Karo Sab Chal Raha Hai](#8-verification--check-karo-sab-chal-raha-hai)
9. [Troubleshooting — Agar Kuch Gadbad Ho](#9-troubleshooting--agar-kuch-gadbad-ho)

---

## 1. Prerequisites — Pehle Yeh Install Karo

### 1.1 Docker Desktop Install Karo

1. **Browser kholo** aur jao: https://www.docker.com/products/docker-desktop/
2. **"Download for Windows"** button pe click karo
3. Downloaded `.exe` file pe **double-click** karke install karo
4. Installation ke baad **computer restart karo** (yeh zaroori hai!)
5. Restart ke baad **Docker Desktop** apne aap khul jayega — neeche right me whale icon dikhega taskbar me
6. **Verify karo** ki Docker chal raha hai — terminal kholo aur type karo:

```bash
docker --version
```

Output aayega kuch aisa:
```
Docker version 27.x.x, build xxxxxxx
```

7. Yeh bhi check karo:

```bash
docker compose version
```

Output:
```
Docker Compose version v2.x.x
```

> **Agar error aaye:** Docker Desktop ko start karo (Start Menu se search karo "Docker Desktop"), 
> wait karo jab tak taskbar me whale icon green/stable ho jaye.

### 1.2 Git Install Karo (Agar Pehle Se Nahi Hai)

1. Jao: https://git-scm.com/download/win
2. Download aur install karo (sab default options rakhne do)
3. Verify karo:

```bash
git --version
```

### 1.3 GitHub Account

1. Agar account nahi hai toh jao: https://github.com aur sign up karo
2. Apna repo `Rakshak` GitHub pe push karo (agar nahi kiya hai toh):

```bash
cd d:\Rakshak
git remote add origin https://github.com/TERA-USERNAME/Rakshak.git
git push -u origin main
```

> **Note:** `TERA-USERNAME` ki jagah apna actual GitHub username dalna!

### 1.4 Render Account

1. Jao: https://render.com
2. **"Get Started for Free"** pe click karo
3. **GitHub se sign in karo** (yeh baad me linking easy kar dega)

---

## 2. Local Docker Setup — Apne Computer Pe Test Karo

> Pehle locally test karo ki Docker image sahi ban rahi hai. Production pe deploy karne
> se pehle yeh step zaroor karo.

### 2.1 `.env` File Banao (Agar Nahi Hai)

Project root (`d:\Rakshak\`) me `.env` file banao ya edit karo:

```bash
# d:\Rakshak\.env

SECRET_KEY=rakshak-local-dev-secret-key-change-in-production
DEBUG=True
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DB_NAME?sslmode=require
```

> **`DATABASE_URL`** me apni actual Supabase/PostgreSQL credentials dalna.
> Local testing ke liye SQLite bhi chal jayega — `DATABASE_URL` line hata do toh 
> automatically SQLite use hoga.

### 2.2 Docker Image Build Karo

Terminal kholo, project root pe jao:

```bash
cd d:\Rakshak
```

Ab Docker image build karo:

```bash
docker build -t rakshak .
```

**Kya hoga:**
- Docker `python:3.11-slim` image download karega (pehli baar me ~200MB)
- `requirements.txt` se sab packages install honge
- `collectstatic` run hoga (CSS/JS files collect honge)
- Sab kuch sahi gaya toh last me dikhega: `Successfully built ...`

> **Pehli baar me 5-10 minute lag sakte hain** — internet speed pe depend karta hai.
> Doosri baar build bahut fast hoga (Docker cache use karta hai).

### 2.3 Docker Container Run Karo

```bash
docker run --rm -p 8000:8000 --env-file .env rakshak
```

**Kya hoga:**
- Container start hoga
- Migrations run hongi (terminal me dikhega: `Running migrations...`)
- Gunicorn server start hoga port 8000 pe

**Test karo:** Browser me jao: http://localhost:8000

> Dashboard load ho raha hai? CSS/JS sahi dikh raha hai? Toh Docker setup sahi hai!

### 2.4 Container Band Karo

Terminal me `Ctrl+C` press karo — container band ho jayega.

---

## 3. GitHub Repository Setup

### 3.1 Sabhi Changes Commit Karo

```bash
cd d:\Rakshak

# Sab new aur moved files stage karo
git add -A

# Commit karo
git commit -m "feat: Docker + Render deployment setup, file reorganization"

# Push karo
git push origin main
```

### 3.2 Verify Karo GitHub Pe

1. Browser me jao: `https://github.com/TERA-USERNAME/Rakshak`
2. Check karo ki yeh files dikh rahi hain:
   - `Dockerfile`
   - `docker-entrypoint.sh`
   - `.dockerignore`
   - `render.yaml`
   - `docs/` folder (with moved files)
   - `non_prod/` folder (with moved files)

---

## 4. Supabase/PostgreSQL Database Setup

> Production ke liye PostgreSQL zaroori hai. SQLite Render pe kaam nahi karega 
> kyunki Render ka filesystem ephemeral hai (har redeploy pe data ud jayega).

### 4.1 Supabase Pe Free Database Banao

1. Jao: https://supabase.com
2. **Sign up / Login** karo (GitHub se sign in kar sakte ho)
3. **"New Project"** pe click karo
4. Details bharo:
   - **Name:** `rakshak-db`
   - **Database Password:** Ek strong password dalo aur **yaad rakhna / save karo!**
   - **Region:** Mumbai ya closest region select karo
   - **Plan:** Free tier
5. **"Create new project"** pe click karo
6. 2-3 minute wait karo database banne me

### 4.2 Connection String Lo

1. Supabase dashboard me jao → left sidebar me **"Project Settings"** (gear icon)
2. **"Database"** tab pe click karo
3. **"Connection string"** section me **"URI"** tab select karo
4. Connection string copy karo — kuch aisa dikhega:

```
postgresql://postgres.xxxx:PASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
```

5. `PASSWORD` ki jagah **apna actual database password** dalna jo tune Step 4.1 me set kiya tha
6. End me `?sslmode=require` add karo:

```
postgresql://postgres.xxxx:TERA-PASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require
```

> **Yeh connection string save karke rakh** — Render me bhi yahi dalni hai.

---

## 5. Render Pe Deploy Karo

### 5.1 Naya Web Service Banao

1. https://dashboard.render.com pe jao
2. **"New +"** button pe click karo (top right)
3. **"Web Service"** select karo
4. **"Connect a repository"** me apna GitHub repo `Rakshak` search karo aur **"Connect"** karo

> Agar repo nahi dikh raha toh **"Configure account"** pe click karo aur GitHub pe 
> Render ko apne repo ka access do.

### 5.2 Service Settings Configure Karo

Yeh settings fill karo:

| Setting | Value |
|---------|-------|
| **Name** | `rakshak` |
| **Region** | Singapore ya closest |
| **Branch** | `main` |
| **Runtime** | `Docker` |
| **Dockerfile Path** | `./Dockerfile` |
| **Plan** | `Free` |

### 5.3 Environment Variables Set Karo

Scroll down karke **"Environment Variables"** section me jao. Yeh variables add karo:

| Key | Value | Notes |
|-----|-------|-------|
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(50))"` ka output | Terminal me yeh command run karo aur jo output aaye woh paste karo |
| `DEBUG` | `False` | Production me hamesha False |
| `DATABASE_URL` | Supabase connection string (Step 4.2 se) | Password replace karna mat bhoolna |
| `DATABASE_CONN_MAX_AGE` | `60` | Connection pooling |
| `GEMINI_API_KEY` | Teri Gemini API key (optional) | Sirf agar AI simulation use karna hai |

**SECRET_KEY generate karne ke liye** — apne terminal me yeh run karo:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Jo output aaye (random string), woh copy karke Render me `SECRET_KEY` value me paste karo.

> **IMPORTANT:** `ALLOWED_HOSTS` aur `CSRF_TRUSTED_ORIGINS` manually set karne ki zaroorat 
> nahi hai — humne `settings.py` me `RENDER_EXTERNAL_HOSTNAME` auto-detect ka code likh diya hai.
> Render apne aap `RENDER_EXTERNAL_HOSTNAME` inject karta hai.

### 5.4 Deploy Karo

1. Sab settings check karo ek baar
2. **"Create Web Service"** button pe click karo
3. Render ab Docker image build karega — **yeh 5-10 minute le sakta hai pehli baar**
4. Build logs me dekho:
   - `pip install` chal raha hai
   - `collectstatic` chal raha hai
   - `Running migrations...` dikhega
   - `Starting gunicorn...` dikhega
5. Jab deploy ho jaye, Render tujhe URL dega: `https://rakshak-xxxx.onrender.com`

### 5.5 Test Karo

Browser me jao: `https://rakshak-xxxx.onrender.com`

- Dashboard load ho raha hai? ✅
- CSS/JS sahi dikh raha hai? ✅
- Login page kaam kar raha hai? ✅

---

## 6. GitHub Actions CI/CD Pipeline

> Ab CI/CD set karenge — jab bhi tu `main` branch pe code push karega, 
> **automatically** Docker image build hogi, tests chalenge, aur Render pe deploy ho jayega.

### 6.1 GitHub Actions Workflow File Banao

Apne project me yeh folder structure banao:

```
d:\Rakshak\.github\workflows\deploy.yml
```

### 6.2 Workflow File Ka Content

`.github/workflows/deploy.yml` me yeh dalo:

```yaml
name: CI/CD — Build, Test & Deploy Rakshak

# Kab chalega: main branch pe push ya PR hone pe
on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  # ──────────────────────────────────────────────
  # Job 1: Build aur Test
  # ──────────────────────────────────────────────
  build-and-test:
    runs-on: ubuntu-latest

    steps:
      # Step 1: Code checkout karo
      - name: Checkout code
        uses: actions/checkout@v4

      # Step 2: Python setup karo
      - name: Setup Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      # Step 3: Dependencies install karo
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      # Step 4: Django checks chala ke verify karo
      - name: Run Django system checks
        run: |
          cd backend
          python manage.py check --deploy
        env:
          SECRET_KEY: 'ci-test-secret-key-not-for-production'
          DEBUG: 'False'
          ALLOWED_HOSTS: 'localhost,127.0.0.1'

      # Step 5: Collectstatic test karo
      - name: Test collectstatic
        run: |
          cd backend
          python manage.py collectstatic --noinput
        env:
          SECRET_KEY: 'ci-test-secret-key-not-for-production'
          DEBUG: 'False'

      # Step 6: Docker image build test karo
      - name: Build Docker image
        run: docker build -t rakshak-test .

  # ──────────────────────────────────────────────
  # Job 2: Render pe Deploy (sirf main branch push pe)
  # ──────────────────────────────────────────────
  deploy:
    runs-on: ubuntu-latest
    needs: build-and-test  # Pehle build-and-test pass hona chahiye
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'

    steps:
      - name: Trigger Render Deploy
        run: |
          curl -X POST "${{ secrets.RENDER_DEPLOY_HOOK_URL }}"
        env:
          RENDER_DEPLOY_HOOK_URL: ${{ secrets.RENDER_DEPLOY_HOOK_URL }}
```

### 6.3 Render Deploy Hook URL Lo

1. Render dashboard pe jao → apni `rakshak` service kholo
2. Left sidebar me **"Settings"** pe click karo
3. Scroll down karke **"Deploy Hook"** section dhundho
4. **"Create Deploy Hook"** pe click karo (agar already nahi hai)
5. Ek URL milegi kuch aisi:

```
https://api.render.com/deploy/srv-xxxxxxxxxxxx?key=xxxxxxxxxxxx
```

6. **Yeh URL copy karo**

### 6.4 GitHub Secrets Me Deploy Hook URL Daalo

1. GitHub pe apne repo pe jao: `https://github.com/TERA-USERNAME/Rakshak`
2. **"Settings"** tab pe click karo (repo settings, profile settings nahi)
3. Left sidebar me **"Secrets and variables"** pe click karo → **"Actions"** select karo
4. **"New repository secret"** pe click karo
5. Details bharo:
   - **Name:** `RENDER_DEPLOY_HOOK_URL`
   - **Secret:** Render se copied deploy hook URL paste karo
6. **"Add secret"** pe click karo

### 6.5 Workflow File Commit Aur Push Karo

```bash
cd d:\Rakshak

# Workflow file add karo
git add .github/workflows/deploy.yml

# Commit karo
git commit -m "ci: add GitHub Actions CI/CD pipeline for Docker + Render"

# Push karo
git push origin main
```

### 6.6 GitHub Actions Check Karo

1. GitHub pe apne repo pe jao
2. **"Actions"** tab pe click karo
3. Tujhe ek running workflow dikhega — us pe click karo
4. Dono jobs dekhna:
   - **build-and-test** — green ✅ hona chahiye
   - **deploy** — green ✅ hona chahiye (yeh Render pe deploy trigger karega)

> Ab se jab bhi tu `main` pe push karega, **automatically** CI/CD pipeline chalega!

---

## 7. Seed Data — Demo Data Dalo

> Pehli baar deploy karne ke baad ek baar seed commands run karne padenge.
> Yeh demo data database me dalte hain.

### 7.1 Render Shell Kholo

1. Render dashboard pe jao → apni `rakshak` service kholo
2. Top me **"Shell"** tab pe click karo
3. Ek terminal khulega — yeh tera container ke andar ka terminal hai

### 7.2 Seed Commands Run Karo (ORDER MATTER KARTA HAI!)

Ek ek karke yeh commands run karo — **isi order me**:

```bash
cd backend
python manage.py seed_master_data
python manage.py seed_routes
python manage.py seed_sensors
python manage.py seed_demo_data
python manage.py seed_readiness_data
python manage.py seed_users
```

Har command ke baad kuch output aayega — errors nahi aane chahiye.

> **Important:** Agar koi command fail ho jaye toh age wale commands mat run karo.
> Pehle us error ko fix karo, phir dubara us command se start karo.

---

## 8. Verification — Check Karo Sab Chal Raha Hai

Yeh checklist follow karo:

| # | Check | Kaise Verify Karein | Expected Result |
|---|-------|---------------------|-----------------|
| 1 | Build successful | Render dashboard → Deploy logs | `Successfully built` dikhna chahiye |
| 2 | Migrations ran | Deploy logs me dekho | `Applying ...` messages dikhenge |
| 3 | Dashboard loads | Browser: `https://TERI-APP.onrender.com/` | Dashboard page dikhna chahiye |
| 4 | CSS/JS working | Dashboard pe styling sahi hai? | Sab styled hona chahiye (WhiteNoise kaam kar raha hai) |
| 5 | Login works | Login page pe jao, credentials dalo | Login ho jana chahiye, CSRF 403 nahi aana chahiye |
| 6 | Admin panel | Browser: `https://TERI-APP.onrender.com/admin/` | Django admin dikhna chahiye |
| 7 | DEBUG off | Galat URL try karo (e.g. `/xyz123`) | Generic 404 page, Django traceback NAHI |
| 8 | Demo data | Dashboard pe data dikh raha hai? | Seed data ke baad demo data dikhna chahiye |
| 9 | AI models | API call karo ya dashboard pe predict feature use karo | `.pkl` files load ho rahi hain, error nahi aa raha |
| 10 | CI/CD working | Koi chhota change push karo `main` pe | GitHub Actions me workflow trigger hona chahiye |

---

## 9. Troubleshooting — Agar Kuch Gadbad Ho

### "Module not found" error build ke time

**Problem:** Koi Python package requirements.txt me nahi hai.

**Fix:**
```bash
pip freeze > requirements.txt
# ya manually missing package add karo requirements.txt me
git add requirements.txt
git commit -m "fix: add missing dependency"
git push origin main
```

### "collectstatic failed" build ke time

**Problem:** Static files ka path galat hai.

**Fix:** Check karo ki `frontend/static/` folder exist karta hai aur `settings.py` me 
`STATICFILES_DIRS` sahi path pe point kar raha hai.

### CSRF 403 Error login pe

**Problem:** `CSRF_TRUSTED_ORIGINS` sahi set nahi hai.

**Fix:** Render dashboard me Environment Variables me yeh add karo:
```
CSRF_TRUSTED_ORIGINS=https://TERI-APP.onrender.com
```

### "DisallowedHost" error

**Problem:** `ALLOWED_HOSTS` me tera domain nahi hai.

**Fix:** `RENDER_EXTERNAL_HOSTNAME` automatically set hota hai Render pe. Agar phir bhi 
error aa raha hai toh manually set karo:
```
ALLOWED_HOSTS=TERI-APP.onrender.com
```

### Database errors / "relation does not exist"

**Problem:** Migrations nahi chali ya `DATABASE_URL` galat hai.

**Fix:**
1. Render dashboard me `DATABASE_URL` check karo — sahi connection string hai?
2. `?sslmode=require` end me hai?
3. Render Shell me manually migration chala ke dekho:
```bash
cd backend
python manage.py migrate --noinput
```

### Data disappear after redeploy

**Problem:** SQLite use ho raha hai (ephemeral filesystem).

**Fix:** `DATABASE_URL` set karo Render me → Supabase/PostgreSQL connection string.
SQLite Render pe use mat karo!

### Docker build me "no space left on device"

**Problem:** Docker cache bahut bhari ho gayi hai.

**Fix:**
```bash
docker system prune -a
```

### GitHub Actions fail ho raha hai

1. GitHub repo → **"Actions"** tab → failed workflow pe click karo
2. Failed step ka log padho — usually error message clear hota hai
3. Common fix: `RENDER_DEPLOY_HOOK_URL` secret check karo (Step 6.4)

---

## Quick Reference Card

```
LOCAL TESTING:
  docker build -t rakshak .
  docker run --rm -p 8000:8000 --env-file .env rakshak
  → http://localhost:8000

DEPLOY:
  git add -A && git commit -m "your message" && git push origin main
  → GitHub Actions automatically build + deploy karega

LOGS:
  Render Dashboard → apni service → "Logs" tab

SHELL:
  Render Dashboard → apni service → "Shell" tab
  cd backend && python manage.py <command>

KEY FILES:
  Dockerfile              → Docker image kaise bane
  docker-entrypoint.sh    → Container start hone pe kya chale
  .dockerignore           → Docker build me kya exclude ho
  render.yaml             → Render ko kya settings chahiye
  .github/workflows/deploy.yml → CI/CD pipeline
  backend/rakshak_project/settings.py → Django settings
```

---

> **Congratulations!** Tera Rakshak ab Docker me containerized hai, GitHub Actions se 
> automatically test hota hai, aur Render pe live deployed hai. 
> Jab bhi `main` branch pe push karega — sab kuch apne aap ho jayega!
