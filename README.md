# 🚆 Rakshak

### AI-Assisted Predictive Railway Maintenance & Safety Monitoring Platform

![Python](https://img.shields.io/badge/Python-3.x-blue.svg)
![Django](https://img.shields.io/badge/Django-4.2-092E20.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Ready-336791.svg)

An AI-assisted predictive railway maintenance and safety monitoring platform prototype designed to demonstrate how railway infrastructure data, anomaly detection, maintenance alerts, simulation, patrol inspections, and operational readiness checks can be brought together in a unified system.

> **Note:** This repository is a prototype/demonstration system. The AI inference, telemetry data, and some operational mechanics are simulated for demonstration purposes.

---

## 📖 Overview

Railway maintenance is complex and requires monitoring infrastructure conditions, analyzing sensor readings for anomalies, tracking maintenance tickets, conducting ground patrols, and verifying safety before major operations.

Rakshak brings these elements together into a single web-based dashboard. It demonstrates how a modern Django application can manage railway assets, visualize track data on a map, simulate synthetic AI telemetry, and enforce operational safety gates before clearing trains for departure. 

---

## ✨ Key Features

- **Dashboard:** Centralized view of system health, active alerts, and maintenance KPIs.
- **Railway Map:** Interactive Leaflet map displaying stations, routes, active trains, and infrastructure alerts.
- **Alerts & Tickets:** Management interface for tracking infrastructure anomalies and assigning maintenance workers.
- **Simulation Engine:** Synthetic IoT telemetry generation using an LLM fallback chain (Gemini, Grok, Anthropic, OpenAI, Ollama, Physics engine).
- **AI Prediction:** Provider-agnostic AI integration layer (currently using threshold-based stubs for demo purposes).
- **Patrol System:** Workflow for field workers to conduct track inspections with unique patrol codes.
- **Operational Readiness:** Safety gate system that evaluates checklist completion and live telemetry before authorizing train movements.
- **Database-Backed Infrastructure:** Robust relational modeling for railway zones, divisions, stations, and track sections.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    U[User] --> F[Django Templates + JavaScript]
    F --> V[Django Views / APIs]
    V --> S[Application Services]
    S --> DB[(PostgreSQL / Supabase)]
    
    V --> AI[AI Prediction Service]
    S --> AI
    AI --> M[Local / Simulated Model]
    
    V --> SIM[Simulation Engine]
    SIM --> LLM[LLM Providers]
    SIM --> RNG[Physics / Synthetic Fallback]
```

---

## ⚙️ How Rakshak Works

1. A user logs into the **Django Web Interface**.
2. The user interacts with the dashboard, map, or patrol interfaces.
3. The **Backend Views & APIs** process requests and enforce business rules (e.g., readiness safety checks).
4. Data is read from or written to the **PostgreSQL Database**.
5. When live telemetry is needed, the **Simulation Engine** requests synthetic data from an LLM or physics fallback.
6. When evaluating sensor data, the **AI Prediction Service** processes the readings (via a local model or stub) to determine anomaly confidence.
7. The results are aggregated and presented back to the user via **JavaScript** (Chart.js / Leaflet).

---

## 🛠️ Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Backend** | Django 4.2 | Core web application and API framework |
| **Language** | Python 3.x | Application logic and services |
| **Database** | PostgreSQL / SQLite | Persistent data storage |
| **Frontend** | Django Templates + Vanilla JS | User interface rendering and interactivity |
| **Maps** | Leaflet.js | Railway map visualization |
| **Charts** | Chart.js | Telemetry and KPI visualization |
| **AI / Sim** | LLM APIs / Local Stubs | Synthetic telemetry generation and prediction |

---

## 📂 Project Structure

```text
Rakshak/
├── backend/
│   ├── rakshak_project/    # Django project settings and root URLs
│   ├── railway/            # Core domain models (Zones, Divisions, Stations, Tracks)
│   ├── sensors/            # Dashboard and AI prediction endpoints
│   ├── alerts/             # Alert management views
│   ├── tickets/            # Maintenance ticketing system
│   ├── map_view/           # Interactive railway map and geospatial APIs
│   ├── simulation/         # Synthetic telemetry generation pipeline
│   ├── patrol/             # Worker inspection workflow
│   ├── readiness/          # Operational safety clearance system
│   ├── ai_integration/     # Provider-agnostic AI abstraction layer
│   └── manage.py           # Django management script
├── frontend/               
│   ├── templates/          # HTML templates
│   └── static/             # CSS and JavaScript assets
├── ai_engin/               # Model artifacts and training notebooks (Stubs)
├── .env.example            # Environment variables template
├── requirements.txt        # Python dependencies
└── README.md               # Project documentation
```

---

## 📋 Prerequisites

**Required:**
- Git
- Python 3.8+ 
- pip (Python package manager)
- PostgreSQL (if running in production or connecting to Supabase)

**Optional:**
- API keys for LLM providers (Google Gemini, OpenAI, Anthropic, xAI Grok) for advanced simulation generation.

---

## 🚀 Quick Start

### Windows (PowerShell)

```powershell
# 1. Clone the repository
git clone https://github.com/Aryan966-1/Rakshak.git
cd Rakshak

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up the database (see Database Setup section)
cd backend
python manage.py migrate

# 5. Seed the database with demo data (run in this exact order)
python manage.py seed_master_data
python manage.py seed_routes
python manage.py seed_sensors
python manage.py seed_demo_data
python manage.py seed_readiness_data
python manage.py seed_users

# 6. Run the application
python manage.py runserver
```

### macOS / Linux

```bash
# 1. Clone the repository
git clone https://github.com/Aryan966-1/Rakshak.git
cd Rakshak

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up the database (see Database Setup section)
cd backend
python manage.py migrate

# 5. Seed the database with demo data (run in this exact order)
python manage.py seed_master_data
python manage.py seed_routes
python manage.py seed_sensors
python manage.py seed_demo_data
python manage.py seed_readiness_data
python manage.py seed_users

# 6. Run the application
python manage.py runserver
```

Open your browser and navigate to: **http://127.0.0.1:8000/**

---

## 🗄️ Database Setup

By default, Rakshak will use a local SQLite database (`db.sqlite3`), which is sufficient for local development and testing. 

To use PostgreSQL (e.g., Supabase):
1. Copy `.env.example` to `.env` in the root directory.
2. Edit `.env` and set the `DATABASE_URL` to your PostgreSQL connection string.
3. Apply migrations using `python manage.py migrate`.

---

## 🔐 Environment Variables

Create a `.env` file in the root directory. Use `.env.example` as a template.

| Variable | Required? | Purpose | Example |
|----------|-----------|---------|---------|
| `SECRET_KEY` | Yes (Prod) | Django cryptographic secret | `<generate-secret>` |
| `DEBUG` | Dev only | Enables debug mode | `True` |
| `ALLOWED_HOSTS` | Prod | Allowed hostnames | `127.0.0.1,localhost` |
| `DATABASE_URL` | Optional | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |
| `DB_SSLMODE` | Optional | PostgreSQL SSL mode requirement | `require` |
| `GEMINI_API_KEY` | Optional | Gemini simulation provider | `<your-key>` |

> **Security Warning:** Never commit `.env` to version control. Never expose your API keys, database passwords, or the production `SECRET_KEY`.

---

## 🌱 Seed / Demo Data

Rakshak includes management commands to populate the database with realistic synthetic data. **Run them in the following order:**

1. `seed_master_data`: Generates railway zones, divisions, and stations.
2. `seed_routes`: Generates the geographical track sections connecting the stations.
3. `seed_sensors`: Generates historical sensor reading data.
4. `seed_demo_data`: Generates active anomalies, alerts, and maintenance tickets.
5. `seed_readiness_data`: Generates sample operational readiness cases and checklist items.
6. `seed_users`: Creates demo user accounts for testing authentication.

---

## 🧩 Application Modules

| Module | Purpose |
|--------|---------|
| **Dashboard** | Visualizes system health, active alerts, and KPIs. |
| **Alerts** | Lists and filters infrastructure anomalies detected by the system. |
| **Tickets** | Maintenance task tracking and assignment interface. |
| **Railway Map** | Real-time geospatial view of tracks, stations, alerts, and simulated trains. |
| **Sensors** | Raw and aggregated telemetry data visualization. |
| **Simulation** | Generates synthetic telemetry using LLMs or a physics engine. |
| **Patrol** | Field worker application to generate inspection reports with unique patrol codes. |
| **Readiness** | Operational control center evaluating checklists and telemetry before dispatching trains. |

---

## 🧠 AI & Simulation

**Important:** The AI predictions in this prototype are **simulated**.
- **AI Integration:** The repository features a robust provider-agnostic abstraction (`PredictionService`), but it currently utilizes a `StubPipeline` fallback. This means predictions (like anomaly confidence) are generated using logical thresholds rather than a production-trained neural network.
- **Simulation Engine:** The live telemetry data (e.g., train speeds, temperatures) is synthetic. The `simulation` app attempts to use an LLM provider (Gemini, Anthropic, etc., via API keys in `.env`) to generate this data. If no API keys are provided or the APIs fail, it falls back to a local physics-based random generator.

---

## 🚦 Safety / Readiness System

The operational readiness system prevents trains from departing until safety criteria are met. 
Before a major operational action is approved, Rakshak evaluates:

1. **Checklist items** (e.g., physical track inspection verified).
2. **Live telemetry** (e.g., sensor readings must be within safe operational limits).

The system then evaluates these conditions and yields a decision (Ready, Conditionally Ready, or Not Ready). *Note: This is a prototype safety gate and should not be used to control real-world railway dispatch operations.*

---

## 🔌 API Overview

While the application primarily uses Django server-side rendered templates, it exposes several JSON endpoints used by the frontend JavaScript (like the Map and Dashboard):

| Endpoint | Method | Authentication | Purpose |
|----------|--------|----------------|---------|
| `/api/stations/` | GET | Required | Fetches station coordinates for the map. |
| `/api/routes/` | GET | Required | Fetches track section geometry. |
| `/api/trains/` | GET | Required | Fetches simulated real-time train positions. |
| `/api/alerts/` | GET | Required | Fetches map-based alert locations. |
| `/api/predict/` | POST | Required | Accepts sensor payload and returns an anomaly prediction. |
| `/simulation/api/run/` | POST | Required | Triggers the simulation engine to generate synthetic telemetry. |
| `/patrol/api/start/` | POST | Required | Initializes a new worker patrol session. |

---

## 🧪 Testing and Validation

Currently, the project relies on Django's built-in system checks to validate application health and routing configuration. 

To verify your setup:
```bash
python manage.py check
python manage.py makemigrations --check
```
*(An automated test suite via pytest-django is planned for the future).*

---

## 🛠️ Development Workflow

1. Clone the repository and create a feature branch (`git checkout -b feature/my-feature`).
2. Create and activate a virtual environment.
3. Install dependencies (`pip install -r requirements.txt`).
4. Configure your local `.env`.
5. Run migrations and seed data.
6. Run the development server (`python manage.py runserver`).
7. Make changes, ensure the server runs without errors.
8. Commit your changes and open a Pull Request.

---

## 🚑 Troubleshooting

- **`ModuleNotFoundError: No module named 'dj_database_url'`** (or similar)  
  *Solution:* Make sure you have activated your virtual environment and run `pip install -r requirements.txt`.
- **Database connection error**  
  *Solution:* If using Supabase/PostgreSQL, verify your `.env` contains the correct `DATABASE_URL` and that `DB_SSLMODE=require` is set if connecting to a cloud provider. If you want to use SQLite, ensure no `DB_` variables are set in `.env`.
- **PowerShell cannot run virtual environment activation script**  
  *Solution:* You may need to bypass execution policies temporarily: `Set-ExecutionPolicy Unrestricted -Scope Process`, then run `.venv\Scripts\Activate.ps1`.
- **Missing database tables (OperationalError)**  
  *Solution:* Ensure you have applied database migrations: `python manage.py migrate`.

---

## 🔒 Security Notes

- **Secret Key:** The `SECRET_KEY` provided in `.env.example` is for development only. Generate a secure, unique key for production deployment.
- **Allowed Hosts:** In production, do not use `ALLOWED_HOSTS=*`. Set this explicitly to your domain name.
- **Debug Mode:** Always set `DEBUG=False` in production environments.

---

## 🚧 Current Limitations

- **Synthetic Telemetry:** Telemetry data is generated synthetically; it does not connect to physical IoT railway sensors.
- **Simulated AI Inference:** Anomaly detection relies on a threshold-based stub rather than a production-grade machine learning model.
- **Security:** Prototype configuration; requires hardening (secure cookies, HTTPS enforcement, CSRF secure flags) before any production deployment.
- **Test Coverage:** Lacks an automated unit/integration test suite.

---

## 🗺️ Roadmap

### Completed
- Core dashboard and database-backed infrastructure modeling
- Alert, Ticket, and Railway Map interfaces
- Simulation system and fallback logic
- Patrol worker workflow and readiness gates

### In Progress
- Production environment hardening
- Implementation of automated test coverage

### Future
- Integration with real physical sensor networks
- Training and integration of production ML anomaly detection models
- CI/CD pipeline implementation

---

## 🤝 Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/amazing-feature`).
3. Make your changes and test locally.
4. Run Django checks (`python manage.py check`).
5. Commit your changes (`git commit -m "feat: amazing feature"`).
6. Open a Pull Request.

---

## 📄 License

A license has not yet been specified for this repository.

---

## ⚠️ Disclaimer

**Disclaimer:** Rakshak is a prototype and demonstration system. It uses simulated and/or synthetic data in several workflows and is strictly an experimental platform. **It is not intended to directly control real railway infrastructure, train operations, signaling systems, or safety-critical equipment.** Use at your own risk.
