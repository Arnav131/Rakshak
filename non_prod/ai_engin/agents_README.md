# 🧠 RAKSHAK — AI Agent System

> **Phase 2 — Autonomous Predictive Intelligence Layer**
> Turning sensor telemetry into saved lives, automatically.

---

## Overview

The `agents/` module is the intelligence core of Rakshak. It transforms the Phase 1 operations dashboard from a passive display into an **autonomous decision engine** — one that perceives anomalies, predicts failures 72+ hours in advance, dispatches maintenance crews, recommends speed restrictions, and continuously learns from outcomes.

The architecture is a **Multi-Agent Mesh (MAM)**: ten specialised agents, each owning a distinct cognitive function, orchestrated by a LangGraph StateGraph and communicating over a Redis Streams message bus.

---

## Agent Roster

| Agent | Role | Autonomy |
|---|---|---|
| `SensorIngestionAgent` | Validates, normalises, and routes raw IoT telemetry | Continuous |
| `AnomalyDetectionAgent` | 3-tier detection: Z-score → Isolation Forest → VAE | Event-driven |
| `FailurePredictionAgent` | HM-STT neural network: 24h / 48h / 72h failure probability | Event-driven |
| `RootCauseAgent` | Graph Neural Net + RAG over maintenance history | Event-driven |
| `MaintenanceDispatchAgent` | OR-Tools constraint solver for crew allocation | Semi-auto / Full-auto |
| `SpeedRestrictionAgent` | Physics-informed TSR recommendation and enforcement | Semi-auto / Emergency |
| `NetworkHealthAgent` | Network-wide Track Health Index topology | Scheduled (5 min) |
| `ExplainabilityAgent` | SHAP attributions + NLG rationale for every decision | Event-driven |
| `LearningAgent` | Online fine-tuning with catastrophic forgetting prevention | Scheduled (weekly) |
| `OrchestratorAgent` | Scenario graph execution, HITL policy, circuit breakers | Always-on |

---

## Neural Network Architecture

The **FailurePredictionAgent** runs the Hierarchical Multi-Modal Spatio-Temporal Transformer (HM-STT) — a purpose-built architecture for the Indian Railways failure prediction problem.

```
Input Modalities
├── Vibration series    [B, 720, 3]   → 1D TCN (dilated: 1,2,4,8,16) → [B, T', 128]
├── Temperature series  [B, 720, 1]   → 1D TCN                        → [B, T', 128]
├── Gauge series        [B, 720, 1]   → 1D TCN                        → [B, T', 128]
├── Track metadata      [B, 32]       → MLP embedding                 → [B, 128]
├── Spatial graph       (N, E)        → Graph Attention Net (4 heads)  → [N, 128]
├── Weather forecast    [B, 72, 6]    → Lightweight Transformer        → [B, 128]
└── Maintenance history [B, 16, 64]   → Self-attention                 → [B, 128]
          │
          ▼
Cross-Modal Fusion Transformer (6 layers, temporal + cross-modal attention)
          │
          ▼
Graph Attention Network over track topology (3 layers, RGCN)
          │
          ▼
Bidirectional LSTM (2 layers, hidden=256)
          │
    ┌─────┼─────┐
    ▼     ▼     ▼
  24h   48h   72h   ← Multi-Task Prediction Heads (3-layer MLP + Dropout 0.3)
    │     │     │
    └─────┴─────┘
          │
   Monte Carlo Dropout (50 passes) → Calibrated uncertainty bounds
   Deep Ensemble (5 models)        → Epistemic + aleatoric uncertainty
```

The **AnomalyDetectionAgent** uses a 3-tier pipeline:

```
Sensor Packet
    │
    ├── Tier 1: 3-sigma Z-score + IQR  (< 5 ms)   → fast screen
    │
    ├── Tier 2: Isolation Forest (200 trees)       (< 50 ms)  → multivariate
    │
    ├── Tier 3: Variational Autoencoder            (< 150 ms) → deep reconstruction
    │           Conv1D(64) → Conv1D(128) → Latent(32)
    │           → Deconv1D(128) → Deconv1D(64) → Reconstruction error
    │
    └── Meta-classifier (GBM) combining all tier scores → C ∈ [0,1]
```

---

## Directory Structure

```
backend/agents/
│
├── __init__.py                     # Package init + agent registry
│
├── orchestrator/
│   ├── orchestrator_agent.py       # Master coordinator (LangGraph StateGraph host)
│   ├── scenario_graphs.py          # Monitoring, alert-triage, emergency graphs
│   ├── hitl_policy.py              # Human-in-the-loop escalation rules
│   └── circuit_breaker.py          # Agent health monitoring + fallback
│
├── ingestion/
│   ├── sensor_ingestion_agent.py   # Kafka consumer, schema validation, normalisation
│   ├── schema.py                   # Pydantic telemetry packet model
│   └── edge_preprocessor.py        # Delta compression, moving-average smoothing
│
├── anomaly/
│   ├── anomaly_detection_agent.py  # 3-tier detection pipeline
│   ├── isolation_forest.py         # Tier 2: Isolation Forest wrapper
│   ├── vae_model.py                # Tier 3: VAE architecture (PyTorch)
│   └── meta_classifier.py          # GBM meta-learner combining tier scores
│
├── prediction/
│   ├── failure_prediction_agent.py # HM-STT orchestration + event emission
│   ├── hm_stt_model.py             # Full neural architecture (PyTorch)
│   ├── uncertainty.py              # Monte Carlo Dropout + deep ensemble
│   └── weather_client.py           # OpenWeatherMap / IMD API adapter
│
├── root_cause/
│   ├── root_cause_agent.py         # HGNN + RAG causal inference
│   ├── hgnn_model.py               # Heterogeneous GNN (PyTorch Geometric)
│   ├── knowledge_graph.py          # Neo4j graph manager (CYPHER queries)
│   └── rag_client.py               # pgvector / Pinecone RAG retrieval
│
├── dispatch/
│   ├── maintenance_dispatch_agent.py
│   ├── constraint_solver.py        # Google OR-Tools allocation optimiser
│   ├── engineer_registry.py        # Reads engineer profiles from Django ORM
│   └── mobile_webhook.py           # FCM push + webhook delivery
│
├── speed_restriction/
│   ├── speed_restriction_agent.py
│   ├── physics_risk_model.py       # Temperature + gauge + traffic risk formula
│   └── tsr_generator.py            # Produces TSRAdvisory objects
│
├── network_health/
│   ├── network_health_agent.py
│   ├── thi_calculator.py           # Track Health Index per section
│   ├── geojson_builder.py          # GeoJSON overlay for Leaflet.js
│   └── cluster_detector.py         # Spatial-temporal anomaly clustering
│
├── explainability/
│   ├── explainability_agent.py
│   ├── shap_attributor.py          # SHAP TreeExplainer / GradientExplainer
│   ├── nlg_engine.py               # Mistral-7B NLG with prompt templates
│   └── audit_store.py              # Cryptographic audit log writer
│
├── learning/
│   ├── learning_agent.py
│   ├── online_fine_tuner.py        # Weekly OTA training job
│   ├── ewc_regulariser.py          # Elastic Weight Consolidation
│   ├── evaluation_harness.py       # Champion/challenger model gating
│   └── mlflow_client.py            # Model registry interface
│
├── shared/
│   ├── base_agent.py               # Abstract base class all agents inherit
│   ├── message_bus.py              # Redis Streams publish/subscribe wrapper
│   ├── context_store.py            # Redis working-memory wrapper (TTL-aware)
│   ├── events.py                   # Pydantic event schemas (all 12 event types)
│   └── logger.py                   # Structured JSON logging (OpenTelemetry)
│
├── configs/
│   ├── anomaly.yaml                # Thresholds, cooldown windows
│   ├── prediction.yaml             # Model paths, horizon configs, weather API key
│   ├── dispatch.yaml               # OR-Tools solver params, engineer SLA
│   ├── orchestrator.yaml           # Autonomy level, HITL risk thresholds
│   └── learning.yaml               # Training schedule, EWC lambda, MLflow URI
│
├── tests/
│   ├── unit/                       # Per-agent unit tests (pytest)
│   ├── integration/                # Multi-agent workflow integration tests
│   ├── fixtures/                   # Scenario replay fixtures (P0–P3 scenarios)
│   └── evaluation/                 # Model quality evaluation scripts
│
└── scripts/
    ├── train_fpm.py                # FPM training pipeline
    ├── train_ade.py                # ADE training pipeline
    ├── train_root_cause.py         # HGNN training pipeline
    ├── build_knowledge_graph.py    # Neo4j graph population from historical data
    ├── build_rag_corpus.py         # Vector store population from maintenance docs
    └── generate_synthetic_data.py  # Realistic sensor data synthesis for demo
```

---

## Autonomy Levels

The system operates at four autonomy levels, configurable per deployment environment:

| Level | Name | Behaviour |
|---|---|---|
| **L0** | Advisory | Generates recommendations only; all actions require human approval |
| **L1** | Semi-Autonomous | Auto-creates maintenance tickets; TSRs require supervisor sign-off |
| **L2** | Full Autonomous (Non-Safety) | Auto-dispatches crews, applies TSRs ≤ 50 km/h |
| **L3** | Emergency Override | Issues network-wide speed restrictions; always triggers HITL within 5 min |

> ⚠️ Emergency Response actions (TSR application) complete **before** HITL confirmation — safety precedes process.

---

## Event Flow

```
IoT Sensor Edge Device
        │  MQTT/TLS
        ▼
  Apache Kafka (rakshak.sensors.raw)
        │
        ▼
SensorIngestionAgent ──────────────────────► TimescaleDB (raw telemetry)
        │  rakshak.sensors.validated
        ▼
AnomalyDetectionAgent ─────────────────────► rakshak.events.anomaly
        │
        ▼
FailurePredictionAgent ─────────────────────► rakshak.events.prediction
        │
        ▼
RootCauseAgent ─────────────────────────────► RootCauseReport (enriches event)
        │
   ┌────┴────┐
   ▼         ▼
Dispatch  SpeedRestriction
Agent     Agent
   │         │
   └────┬────┘
        │  (gated by OrchestratorAgent HITL policy)
        ▼
  External Actions
  ├── Django API → Maintenance ticket, alert, map update
  ├── Mobile webhook → Field engineer push notification
  ├── SMS gateway → Emergency escalation
  └── TSR advisory → Operations control dashboard

        │  All events
        ▼
ExplainabilityAgent ────────────────────────► Audit Store (append-only, cryptographic)

        │  Ticket resolution feedback
        ▼
LearningAgent ──────────────────────────────► MLflow → Weekly model updates
```

---

## Key ML Quality Targets

| Component | Metric | Target |
|---|---|---|
| Anomaly Detection | F1 Score | ≥ 0.96 |
| Anomaly Detection | False Positive Rate | < 4% |
| Failure Prediction | AUROC | ≥ 0.95 |
| Failure Prediction | Time-to-failure MAE | ≤ 2.5 hours |
| Root Cause (GNN) | Top-1 Accuracy | ≥ 0.85 |
| Root Cause (GNN) | Top-5 Accuracy | ≥ 0.97 |
| Dispatch Optimiser | Engineer Utilisation | > 90% |
| Speed Restriction | False TSR Rate | < 2% |

---

## Technology Stack

| Layer | Technology |
|---|---|
| Agent Orchestration | LangGraph 0.2 + CrewAI 0.9 |
| LLM (Explainability NLG) | Mistral-7B-Instruct (self-hosted) |
| ML Framework | PyTorch 2.x |
| Model Serving | TorchServe / Triton Inference Server |
| Time-Series Database | TimescaleDB 2.x (PostgreSQL 16) |
| Vector Store (RAG) | pgvector → Pinecone (at scale) |
| Message Bus | Apache Kafka + Redis Streams |
| Knowledge Graph | Neo4j 5.x |
| MLOps | MLflow 2.x + DVC |
| Constraint Solver | Google OR-Tools |
| Stream Processing | Faust (Python Kafka) |
| Containerisation | Docker + Kubernetes |
| Monitoring | Prometheus + Grafana + OpenTelemetry |

---

## Performance Requirements

| Requirement | Target |
|---|---|
| End-to-end anomaly detection latency | < 200 ms (p99) |
| Failure prediction refresh interval | Every 5 minutes |
| Maintenance ticket auto-generation | < 60 s from confirmed event |
| Sensor event throughput | 500,000 events/s (full IR deployment) |
| Model inference latency (HM-STT) | < 80 ms per section |
| RAG query latency | < 50 ms at 10M+ documents |
| System uptime (safety-critical path) | 99.95% |

---

## Scenario Coverage

The agent system handles 10 defined scenario classes — from routine monitoring to network-wide emergency response. Full coverage matrix is in the SRS (Section 11).

| Priority | Scenario | Response |
|---|---|---|
| P0 — Life safety | Rail fracture imminent / Network extreme weather | L3 Emergency: instant TSR + HITL |
| P1 — Derailment risk | Gauge deviation > 10mm / Thermal buckling risk | L2 Auto-dispatch + TSR |
| P1 — Systemic | Correlated anomaly cluster across sections | Network health escalation |
| P2 — Operational | Missed scheduled maintenance / Sensor dropout | L1 Ticket + alert |
| P3 — Improvement | False positive feedback / New section onboarding | Learning agent signal |

---

## Integration with Phase 1

The agent system integrates with the existing Django backend without modifying Phase 1 URL contracts:

- **Alerts page** (`/alerts/`) — populated via `POST /api/v2/alerts/` from `AnomalyDetectionAgent`
- **Tickets page** (`/tickets/`) — populated via `POST /api/v2/tickets/` from `MaintenanceDispatchAgent`
- **Map page** (`/map/`) — GeoJSON overlays via `PUT /api/v2/map/geojson/` from `NetworkHealthAgent`
- **Dashboard KPIs** (`/`) — metrics via `PUT /api/v2/dashboard/kpis/` from `OrchestratorAgent`

---

## Running the Agent System (Phase 2)

```bash
# Prerequisites: Docker, Kubernetes (minikube for local), Redis, Kafka, TimescaleDB, Neo4j

# 1. Start infrastructure services
docker-compose -f infra/docker-compose.yml up -d

# 2. Populate knowledge graph and RAG corpus (first-time setup)
python agents/scripts/build_knowledge_graph.py
python agents/scripts/build_rag_corpus.py

# 3. Generate synthetic demo data (for hackathon demo)
python agents/scripts/generate_synthetic_data.py --scenario derailment_prevention --duration 72h

# 4. Start the agent mesh (via Kubernetes or local development)
# Kubernetes:
kubectl apply -f k8s/agents/

# Local development (runs all agents as subprocesses):
python -m agents.orchestrator.orchestrator_agent --mode dev --autonomy L1
```

---

## Explainability Example

Every FailurePredictionEvent produces a natural-language rationale like:

> **Section DLI-AGC-KM-42.3 — FAILURE ALERT (72h, P=0.87, HIGH CONFIDENCE)**
>
> Vibration RMS on sensor VIB-4231 has increased 340% above seasonal baseline over the past 18 hours, consistent with rail surface fatigue patterns observed in 14 analogous historical cases (highest similarity: incident DLI-2019-047, confirmed rail fracture). Ambient temperature is forecast to reach 52°C tomorrow, creating thermal stress that amplifies existing fatigue. Track last maintained 94 days ago (scheduled cycle: 60 days). Top contributing features: vibration trend (SHAP=0.41), days-since-maintenance (SHAP=0.28), temperature forecast (SHAP=0.19).
>
> **Recommended action:** Dispatch certified track inspector within 6 hours. Apply 60 km/h TSR as precautionary measure.

---

## Documentation

| Document | Description |
|---|---|
| `docs/ai/RAKSHAK_SRS_AI_Agent_System.docx` | Full Software Requirements Specification |
| `docs/ai/RAKSHAK_Agent_Architecture.docx` | System Architecture & Integration Guide |
| `agents/configs/*.yaml` | Per-agent configuration references |
| `agents/tests/fixtures/` | Scenario replay fixtures for all P0–P3 classes |

---

*Built for FAR AWAY 2026 — protecting 23 million daily rail passengers through autonomous AI.*
