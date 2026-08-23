# 🚆 Rakshak - Railway Maintenance Dashboard Prototype

Rakshak is a prototype Railway Maintenance Dashboard built using Django. It provides an interactive interface for monitoring railway assets, maintenance alerts, routes, sensors, and support tickets. The project is designed to simulate a railway infrastructure monitoring system using seeded demo data.

---

# Features

- Dashboard with railway maintenance overview
- Interactive railway route map
- Alert Management
- Ticket Management
- Sensor Monitoring
- PostgreSQL database support
- REST API backend
- Preloaded demo data for testing

---

# Tech Stack

- Python 3.10+
- Django 4.2+
- Supabase/PostgreSQL via required `DATABASE_URL`
- PyTorch 2.2+
- NumPy
- scikit-learn
- HTML
- CSS
- JavaScript
- Leaflet.js (Map)

---

# Project Structure

```
PROTOTYPE_1.0/
│
├── backend/
│   ├── railway/
│   ├── templates/
│   ├── static/
│   ├── manage.py
│   └── requirements.txt
│
├── README.md
├── Codebase.md
└── Tree.md
```

---

# Prerequisites

Make sure the following software is installed:

- Python 3.10 or above
- A Supabase project with a Postgres database
- Git
- pip

---

# Clone the Repository

```bash
git clone https://github.com/<your-username>/<repository-name>.git
cd <repository-name>/backend
```

---

# Create Virtual Environment (Recommended)

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

# Install Dependencies

The AI prediction feature is a core product capability, not an optional extra. Install the full ML stack before running the dashboard or simulation flows:

```bash
pip install -r requirements.txt
```

This includes Django, PostgreSQL driver support, NumPy, PyTorch, and scikit-learn so the local pickle-based prediction pipeline can load correctly.

---

# Supabase Database Setup

1. Create or open a Supabase project.
2. In Supabase, open **Connect** and copy the Postgres connection string.
3. For local Django development, prefer the **Session pooler** URL because it works on IPv4 networks.
4. Copy `.env.example` to `.env`.
5. Set `DATABASE_URL` in `.env`:
   `DATABASE_URL=postgresql://postgres.<PROJECT_REF>:<PASSWORD>@aws-<REGION>.pooler.supabase.com:5432/postgres?sslmode=require`

SQLite is intentionally disabled. If `DATABASE_URL` is missing or points to SQLite, Django raises a setup error before startup.

---

# Apply Database Migrations

```bash
python manage.py migrate
```

---

# Seed the Database

Run the following commands **in the given order**:


```bash
cd backend

```
```bash
python manage.py seed_master_data
```

```bash
python manage.py seed_routes
```

```bash
python manage.py seed_sensors
```

```bash
python manage.py seed_demo_data
```

```bash
python manage.py seed_users
```

These commands populate the database with sample railway assets, routes, sensors, alerts, and tickets.

---

# Run the Development Server

```bash
python manage.py runserver
```

The application will start at:

```
http://127.0.0.1:8000/
```

---

# Available Pages

- Dashboard
- Alerts
- Tickets
- Railway Map
- Simulation (staff-only — live synthetic IoT telemetry generator with Grok / Gemini / Anthropic / OpenAI / Physics RNG)
- Sensors

---

# Live Simulation & AI Generator Setup

The Simulation feature (`/simulation/`) generates a fresh 16-reading IoT sensor journey on demand and feeds it into the live Rakshak prediction pipeline.

To power scenario generation using **xAI Grok API**:
1. Obtain an API key from [xAI Console](https://console.x.ai/).
2. Add your key to `.env`:
   ```bash
   GROK_API_KEY=xai-your-key-here
   GROK_MODEL=grok-2-latest
   ```
3. Fallback support is built-in: if Grok is unreachable or unconfigured, the system seamlessly tries Gemini, Anthropic, OpenAI, Ollama, and finally the dynamic physics-based IoT RNG engine.

---

# Deployment

For production deployments, the application relies on environment variables.
Ensure the deployment platform provides at minimum:
- `DATABASE_URL`
- `SECRET_KEY`
- `DEBUG` (set to `False`)
- `ALLOWED_HOSTS`

---

# API

The project also exposes REST API endpoints through Django REST Framework for dashboard data and railway resources.

---

# Demo Data

The repository includes management commands that automatically generate realistic demo data for:

- Railway Routes
- Stations
- Sensors
- Maintenance Alerts
- Tickets
- Assets

No manual database setup is required after running the seed commands.

---

# Deployment

Set the following environment variables in production or local development:

```bash
export DATABASE_URL="postgresql://postgres.<PROJECT_REF>:<PASSWORD>@aws-<REGION>.pooler.supabase.com:5432/postgres?sslmode=require"
export SECRET_KEY="change-me-in-production"
export DEBUG="False"
export ALLOWED_HOSTS="localhost,127.0.0.1"
```

`DATABASE_URL` is required at runtime. `DEBUG` and `ALLOWED_HOSTS` are read from environment variables and fall back to local development defaults when unset.

---

# Development Workflow

Whenever database models are modified:

```bash
python manage.py makemigrations
python manage.py migrate
```

If demo data needs to be regenerated, rerun the seed commands:

```bash
python manage.py seed_master_data
python manage.py seed_routes
python manage.py seed_sensors
python manage.py seed_demo_data
python manage.py seed_users
```

---

# License

This project is intended as a prototype for demonstration and educational purposes.
