# 🚆 Rakshak - AI-Powered Railway Predictive Maintenance Platform

## Overview

Rakshak is an intelligent railway infrastructure monitoring and predictive maintenance platform designed to improve operational safety, reduce downtime, and streamline maintenance workflows.

The platform provides a unified ecosystem where sensor data, infrastructure assets, alerts, maintenance tickets, and geospatial information are brought together into a single operational dashboard.

By transforming infrastructure data into actionable insights, Rakshak helps railway authorities detect potential failures early, prioritize maintenance activities, and improve overall network reliability.

---

## Problem Statement

Railway infrastructure consists of thousands of interconnected assets including tracks, stations, signaling equipment, and monitoring sensors.

Traditional maintenance approaches are often:

* Reactive instead of preventive
* Difficult to monitor at scale
* Fragmented across multiple systems
* Lacking centralized visibility

Rakshak addresses these challenges through centralized monitoring, intelligent alerting, infrastructure mapping, and maintenance workflow management.

---

## Key Features

### 📊 Operational Dashboard

* Centralized system overview
* Infrastructure health visibility
* Sensor activity monitoring
* Operational status tracking

### 🚨 Alert Management

* Alert generation and monitoring
* Severity classification
* Escalation workflows
* Alert lifecycle tracking

### 🎫 Maintenance Ticketing

* Maintenance issue reporting
* Ticket assignment and tracking
* Status history logging
* Team-based workflow management

### 🗺️ Railway Network Mapping

* Interactive GIS visualization
* Station and route display
* Infrastructure monitoring view
* Alert and ticket geolocation

### 📡 Sensor Monitoring

* Sensor inventory management
* Calibration tracking
* Historical readings storage
* Asset-linked telemetry

### 🤖 Predictive Analytics Framework

* ML model registry
* Model execution tracking
* Anomaly prediction storage
* Future-ready AI integration architecture

### 📋 Audit & Traceability

* Operational audit logs
* Historical activity tracking
* Accountability and transparency

---

## System Architecture

```text
Sensors & Infrastructure
            │
            ▼
      Data Collection
            │
            ▼
       Railway Database
            │
 ┌──────────┼──────────┐
 ▼          ▼          ▼
Alerts   Analytics   Mapping
 ▼          ▼          ▼
Tickets  Predictions  GIS View
            │
            ▼
      Operational Dashboard
```

---

## Technology Stack

### Backend

* Python 3
* Django 4.2
* Django ORM

### Database

* SQLite (Current Prototype)
* PostgreSQL Ready Architecture

### Frontend

* Django Templates
* HTML5
* CSS3
* Vanilla JavaScript

### Mapping

* Leaflet.js

### Development Tools

* Git
* GitHub
* Python Virtual Environment (venv)

---

## Project Structure

```text
Rakshak/
│
├── backend/
│   ├── railway/
│   ├── sensors/
│   ├── alerts/
│   ├── tickets/
│   ├── map_view/
│   ├── agents/
│   └── rakshak_project/
│
├── frontend/
│   ├── static/
│   └── templates/
│
├── docs/
├── notebooks/
├── presentation/
├── demo_assets/
│
├── requirements.txt
└── db.sqlite3
```

---

## Core Modules

| Module   | Responsibility                          |
| -------- | --------------------------------------- |
| railway  | Core domain models and database schema  |
| sensors  | Sensor monitoring and dashboard views   |
| alerts   | Alert management workflows              |
| tickets  | Maintenance ticket lifecycle            |
| map_view | GIS visualization and APIs              |
| core     | Shared utilities and context processors |
| agents   | Future AI agent integration             |

---

## API Endpoints

| Endpoint         | Description          |
| ---------------- | -------------------- |
| `/api/stations/` | Railway station data |
| `/api/routes/`   | Route geometry data  |
| `/api/alerts/`   | Active alerts        |
| `/api/tickets/`  | Maintenance tickets  |
| `/api/trains/`   | Train position data  |
| `/api/summary/`  | Dashboard statistics |

---

## Database Highlights

The platform maintains a unified railway domain model covering:

* Railway Zones
* Divisions
* Stations
* Track Sections
* Infrastructure Assets
* Sensors
* Sensor Readings
* Alerts
* Escalations
* Maintenance Teams
* Tickets
* ML Models
* Predictions
* Audit Logs

---

## Installation

### 1. Clone Repository

```bash
git clone <repository-url>
cd Rakshak
```

### 2. Create Virtual Environment

```bash
python -m venv venv
```

### 3. Activate Environment

Windows:

```bash
venv\Scripts\activate
```

Linux/Mac:

```bash
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Apply Migrations

```bash
python backend/manage.py migrate
```

### 6. Run Development Server

```bash
python backend/manage.py runserver
```

---

## Future Roadmap

### Phase 2

* PostgreSQL migration
* Real-time data ingestion
* Advanced analytics pipeline
* Improved geospatial intelligence

### Phase 3

* Autonomous AI agents
* Predictive maintenance recommendations
* Real-time anomaly detection
* Large-scale railway deployment readiness

---

## Team Contributions

### Backend Development

* Database design
* API development
* Django architecture

### Frontend Development

* Dashboard UI
* Ticket management interface
* Mapping interface

### Data & Analytics

* Sensor data modeling
* Prediction framework
* Alert intelligence architecture

---

## Impact

Rakshak aims to improve railway safety, operational visibility, and maintenance efficiency by providing a centralized platform capable of supporting future AI-driven predictive maintenance systems.

---

## License

This project was developed as part of a hackathon/research prototype and is intended for demonstration and educational purposes.