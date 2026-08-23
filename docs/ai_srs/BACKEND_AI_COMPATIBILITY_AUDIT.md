# Backend AI Compatibility Audit

Status: Draft for hackathon pivot
Date: 2026-08-07
Owner: Backend / AI integration

## Executive Decision

The backend should not be rewritten. The current Django app already has useful domain models, alert pages, map APIs, ticket flow, and agent wrappers. The risky part is the current AI engine contract: it assumes a large multi-model pipeline with several exported model files and a 64-reading sequence buffer.

For the hackathon, keep the backend surface stable and replace the AI implementation behind a small compatibility layer.

Recommended target:

```text
Django backend
  -> AnomalyDetectionAgent
  -> SimpleAIService / SimpleRakshakInferencePipeline
  -> one lightweight anomaly/risk model
  -> optional lightweight fault classifier
  -> existing Alert / Ticket / Dashboard models
```

## Current Backend AI Shape

The current repo is built around a larger architecture:

- `backend/agents/anomaly/anomaly_detection_agent.py`
  - Imports `RakshakInferencePipeline` directly.
  - Expects `process_reading(...)` to return `None` while buffering.
  - Expects a result object with `anomaly`, `failure`, `fault`, and `processing_time_ms`.
  - Creates `Alert` records when anomaly is detected.
  - Creates predictive alerts when `result.failure.alert_level` is `warning` or `critical`.

- `ai_engin/inference/pipeline.py`
  - Loads `ModelRegistry`.
  - Runs anomaly detection, failure prediction, and fault classification.
  - Uses a default 64-reading sliding window.

- `ai_engin/inference/model_registry.py`
  - Expects multiple exported files:
    - `vae_anomaly_detector.pt`
    - `failure_predictor.pt`
    - `fault_classifier.pt`
    - `isolation_forest.joblib`
    - `meta_classifier.joblib`
    - `stat_detector.joblib`
    - `model_config.json`
  - Imports training-time model classes during inference.
  - Requires PyTorch, joblib, sklearn/LightGBM-adjacent artifacts, and matching configs.

- `ai_engin/inference/utils.py`
  - Defines the shape the backend already understands:
    - `SensorReading`
    - `AnomalyResult`
    - `FailurePrediction`
    - `FaultClassification`
    - `PredictionResult`
    - `ReadingBuffer`

- `backend/agents/root_cause/root_cause_agent.py`
  - Does not need deep learning to work.
  - Can consume a simple `fault_type`, `fault_confidence`, and `anomaly_score`.

- `backend/agents/dispatch/maintenance_dispatch_agent.py`
  - Can keep working if the simple AI produces a fault/urgency value.

- `backend/agents/speed_restriction/speed_restriction_agent.py`
  - Already uses rules and sensor values.
  - This is useful for the demo and should be retained.

- `backend/railway/models.py`
  - Already has `MLModel`, `MLModelRun`, and `AnomalyPrediction`.
  - No schema rewrite is needed for the hackathon MVP.

## Compatibility Problem

The backend is AI-compatible in concept, but the concrete inference contract is too heavy:

1. Backend startup can fail if `ai_engin/trained_models` is missing exported files.
2. Inference imports training architectures instead of a small deployment-only module.
3. The 64-reading buffer delays demo feedback and makes live demos awkward.
4. The current result object assumes three different ML tasks always exist.
5. `requirements.txt` only includes Django, while the AI path needs ML dependencies.
6. The public app pages do not expose a simple manual prediction endpoint for judges.
7. `AI_ENGINE_GUIDE.md` explains the production-style Colab training flow, not the new hackathon pivot.

## Backend Goal

Make the backend compatible with the new simple AI approach while preserving:

- Dashboard pages.
- Map APIs.
- Alert and ticket models.
- Agent class names where possible.
- Result fields already consumed by downstream agents.

The backend should support two modes:

```text
AI_ENGINE_MODE=legacy
  Uses current RakshakInferencePipeline.

AI_ENGINE_MODE=simple
  Uses a lightweight local simple pipeline.
```

Default for the hackathon should be:

```text
AI_ENGINE_MODE=simple
```

## Proposed Simple Backend Contract

The simple engine should mimic the existing `PredictionResult` enough that backend agents do not care which AI is behind it.

Input:

```python
process_reading(
    ambient_temp: float,
    humidity: float,
    vibration_rms: float,
    gauge_width: float,
    timestamp: str | None = None,
    sensor_id: str = "default",
) -> PredictionResult | None
```

Output:

```python
PredictionResult(
    anomaly=AnomalyResult(
        is_anomaly=True,
        anomaly_score=0.82,
        tier_scores={
            "simple_model": 0.82,
            "rules": 0.71,
        },
        threshold=0.65,
    ),
    failure=FailurePrediction(
        probabilities={
            "risk": 0.82,
            "24h": 0.58,
        },
        uncertainty={},
        alert_level="warning",
    ),
    fault=FaultClassification(
        fault_type="gauge_widening",
        confidence=0.76,
        top_k=[
            {"class": "gauge_widening", "probability": 0.76},
            {"class": "thermal_buckle", "probability": 0.14},
        ],
    ),
    processing_time_ms=12.5,
)
```

Important: the simple engine can return fake-compatible `failure` fields derived from the anomaly/risk score. It does not need a real separate failure predictor for the hackathon.

## Recommended Backend Changes

### 1. Add AI Mode Settings

File:

```text
backend/rakshak_project/settings.py
```

Add:

```python
AI_ENGINE_MODE = os.getenv("AI_ENGINE_MODE", "simple")
AI_MODEL_DIR = os.getenv(
    "AI_MODEL_DIR",
    str(BASE_DIR.parent / "ai_engin" / "trained_models"),
)
SIMPLE_AI_MODEL_DIR = os.getenv(
    "SIMPLE_AI_MODEL_DIR",
    str(BASE_DIR.parent / "ai_engin" / "simple_models"),
)
SIMPLE_AI_WINDOW_SIZE = int(os.getenv("SIMPLE_AI_WINDOW_SIZE", "8"))
SIMPLE_AI_ALERT_THRESHOLD = float(os.getenv("SIMPLE_AI_ALERT_THRESHOLD", "0.65"))
SIMPLE_AI_CRITICAL_THRESHOLD = float(os.getenv("SIMPLE_AI_CRITICAL_THRESHOLD", "0.85"))
```

Why:

- Enables switching without code edits.
- Allows demo mode to run without the old exported model bundle.
- Shrinks buffering from 64 readings to 8 readings.

### 2. Add A Simple Pipeline, Do Not Delete Legacy

New file:

```text
ai_engin/inference/simple_pipeline.py
```

Responsibilities:

- Use the existing dataclasses from `ai_engin/inference/utils.py`.
- Keep per-sensor `ReadingBuffer`, but default to `window_size=8`.
- Extract simple window features:
  - mean, std, min, max
  - latest reading
  - deltas over the window
  - gauge deviation from 1676 mm
  - temperature and vibration risk flags
- Load one optional `.joblib` model from `ai_engin/simple_models`.
- If the model is absent, use deterministic rules as fallback.
- Return a backend-compatible `PredictionResult`.

Suggested files:

```text
ai_engin/simple_models/
  anomaly_model.joblib
  fault_model.joblib
  simple_model_config.json
```

Fallback behavior must be built in. A missing model should produce a warning, not crash the backend demo.

### 3. Add A Pipeline Factory

New file:

```text
ai_engin/inference/factory.py
```

Suggested API:

```python
def build_inference_pipeline(config=None):
    mode = getattr(settings, "AI_ENGINE_MODE", "simple")
    if mode == "legacy":
        from ai_engin.inference.pipeline import RakshakInferencePipeline
        return RakshakInferencePipeline(model_dir=settings.AI_MODEL_DIR)

    from ai_engin.inference.simple_pipeline import SimpleRakshakInferencePipeline
    return SimpleRakshakInferencePipeline(
        model_dir=settings.SIMPLE_AI_MODEL_DIR,
        window_size=settings.SIMPLE_AI_WINDOW_SIZE,
        alert_threshold=settings.SIMPLE_AI_ALERT_THRESHOLD,
        critical_threshold=settings.SIMPLE_AI_CRITICAL_THRESHOLD,
    )
```

Why:

- Prevents agents from importing legacy pipeline directly.
- Makes the old and new AI paths swappable.

### 4. Update `AnomalyDetectionAgent`

File:

```text
backend/agents/anomaly/anomaly_detection_agent.py
```

Change `_ensure_pipeline()` from a direct legacy import to the factory:

```python
from ai_engin.inference.factory import build_inference_pipeline
self._pipeline = build_inference_pipeline(self.config)
```

Keep the rest of `process()` mostly unchanged because the simple pipeline will return compatible objects.

Also update user-facing text:

- Replace "3-tier anomaly detection triggered" with a mode-aware phrase.
- Example: "Simple AI risk model triggered".
- Preserve score, threshold, and tier_scores in the alert description.

### 5. Keep Downstream Agents As Rule-Based Demo Intelligence

Do not remove:

- `RootCauseAgent`
- `MaintenanceDispatchAgent`
- `SpeedRestrictionAgent`
- `NetworkHealthAgent`
- `ExplainabilityAgent`

For hackathon demo, these can act as deterministic expert agents:

```text
simple AI risk score
  -> root cause mapping
  -> ticket recommendation
  -> speed restriction recommendation
  -> explanation
```

This gives the appearance of an agentic system without building LangGraph, Redis Streams, Kafka, Neo4j, MLflow, or online learning.

### 6. Add A Manual Prediction API For Demo

New Django app code can live in `backend/sensors/views.py` or a new lightweight `backend/ai_api` app.

Recommended endpoint:

```text
POST /api/ai/predict/
```

Request:

```json
{
  "sensor_id": "demo-sensor-1",
  "track_section_id": 1,
  "ambient_temp": 48.5,
  "humidity": 32,
  "vibration_rms": 7.2,
  "gauge_width": 1689.0
}
```

Response:

```json
{
  "buffering": false,
  "anomaly_detected": true,
  "anomaly_score": 0.83,
  "alert_level": "warning",
  "fault_type": "gauge_widening",
  "fault_confidence": 0.76,
  "processing_time_ms": 14.2,
  "explanation": "Gauge deviation and vibration are above safe demo thresholds."
}
```

Why:

- Lets judges trigger the AI from the browser/Postman without waiting for sensor ingestion.
- Makes the AI change visible immediately.

### 7. Add Minimal Dependencies

Current `requirements.txt` only contains Django.

For simple AI, add only what the backend actually needs:

```text
numpy
joblib
scikit-learn
```

If using PyTorch for a tiny MLP, add it only to an optional AI requirements file:

```text
requirements-ai.txt
```

Recommended hackathon choice:

```text
Django app: requirements.txt
Simple model training: ai_engin/requirements_simple.txt
```

Do not force PyTorch into the core Django install unless the final simple model truly needs it.

### 8. Leave Database Schema Alone

No migration is required for the MVP.

Existing tables already support:

- `Alert`: visible output for AI findings.
- `Ticket`: maintenance action.
- `MLModel`: model registry.
- `MLModelRun`: model execution tracking.
- `AnomalyPrediction`: score, label, fault type, explanation.
- `AuditLog`: traceability.

Optional improvement:

- Seed an `MLModel` row:
  - `model_name="simple_risk_model"`
  - `model_version="0.1.0-hackathon"`
  - `model_type="sklearn_random_forest"` or `"rules_plus_sklearn"`
  - `performance_metrics={"demo_validated": true}`

### 9. Update Documentation And Naming

Current docs use production-sized language like:

- Multi-Agent Mesh
- HM-STT
- VAE
- GNN
- RAG
- Kafka
- Redis Streams
- MLflow
- Kubernetes

For hackathon docs, label that as "deferred production architecture" and present the simple AI path as the implementation target.

## Compatibility Matrix

| Area | Current State | Simple AI Change | Risk |
|---|---|---|---|
| Dashboard | Reads Alerts, TrackSections, SensorReadings | No change | Low |
| Map APIs | Reads Alerts/Tickets/Routes | No change | Low |
| Alert creation | Done in `AnomalyDetectionAgent` | Keep same flow | Low |
| AI import | Direct `RakshakInferencePipeline` import | Replace with factory | Medium |
| Model loading | Requires many heavy artifacts | One optional model plus rule fallback | Low |
| Buffering | 64 readings | 8 readings or immediate demo mode | Low |
| Failure prediction | Separate deep sequence model | Derive demo risk bucket from anomaly score | Medium |
| Fault classification | Separate deep classifier | Rule/classifier hybrid | Medium |
| Dependencies | Django only in root requirements | Add minimal AI dependencies | Low |
| Database | Already has ML tables | No migration required | Low |

## Implementation Order

1. Add `backend/rakshak_project/settings.py` AI mode settings.
2. Add `ai_engin/inference/simple_pipeline.py`.
3. Add `ai_engin/inference/factory.py`.
4. Update `backend/agents/anomaly/anomaly_detection_agent.py` to use the factory.
5. Add a manual `/api/ai/predict/` endpoint.
6. Add simple model training/export script under `ai_engin/simple_training/`.
7. Add `ai_engin/simple_models/simple_model_config.json`.
8. Add smoke tests for simple pipeline and prediction endpoint.
9. Update README/demo instructions.

## Testing Checklist

Backend:

- `python backend/manage.py check`
- Dashboard loads.
- `/api/stations/`, `/api/routes/`, `/api/alerts/`, `/api/tickets/`, `/api/summary/` still return JSON.
- `AnomalyDetectionAgent().health_check()` works.
- Simple pipeline initializes without old model files.
- Simple pipeline returns `None` only until the small buffer is ready.
- Simple pipeline returns `PredictionResult.to_dict()` after enough readings.
- An anomalous demo input creates an `Alert`.

AI:

- Training script can train on a small sampled dataset.
- Exported model files load on CPU.
- Missing model files trigger deterministic fallback.
- Scores are in `[0, 1]`.
- Fault type is one of the configured demo labels.

Demo:

- One normal scenario shows `healthy`.
- One warning scenario creates a warning alert.
- One critical scenario creates a critical alert and speed recommendation.
- The UI can explain what happened in plain English.

## Acceptance Criteria

The backend is considered simple-AI compatible when:

1. The app runs without the legacy multi-model trained bundle.
2. `AI_ENGINE_MODE=simple` is the default local/hackathon mode.
3. The anomaly agent can call the simple pipeline with the same method name as before.
4. A demo prediction can create an alert in the existing database.
5. Existing dashboard and map pages show the alert/ticket output without schema changes.
6. The code can still optionally use the legacy pipeline if `AI_ENGINE_MODE=legacy`.

## Deferred Until After Hackathon

Do not build these now:

- LangGraph orchestration.
- Redis/Kafka event bus.
- Full VAE plus meta-classifier stack.
- HM-STT failure prediction model.
- Graph neural network root cause model.
- RAG maintenance-history retrieval.
- Online learning or weekly fine-tuning.
- MLflow model registry.
- Kubernetes or model serving infrastructure.

These are valid production ideas, but they are not needed to win a hackathon demo.

