# Simple AI Migration Roadmap

Status: Draft SRS for hackathon pivot
Date: 2026-08-07
Owner: AI / Backend / Demo team

## Product Reframe

Original direction:

```text
Large multi-model agentic system
  -> many deep learning models
  -> many agents
  -> external infrastructure
  -> production-scale reliability
```

New hackathon direction:

```text
Small simple AI system
  -> one lightweight risk model
  -> optional lightweight fault classifier
  -> rule-based recommendations
  -> existing Django dashboard
  -> polished, reliable demo
```

The goal is not to prove the final production architecture. The goal is to show that Rakshak can take railway sensor data, detect risk, explain the likely cause, and trigger operational action.

## North Star Demo

The judge should be able to see this flow in under one minute:

```text
Sensor reading or uploaded sample
  -> simple AI detects railway track risk
  -> system explains the likely fault
  -> alert appears on dashboard/map
  -> ticket or recommended action is generated
```

Success is a working story, not a massive model stack.

## New AI Scope

### Must Have

- Use the existing Rakshak dataset, but in reduced/sampled form.
- Train or configure one lightweight model for anomaly/risk scoring.
- Optionally train one lightweight model for fault type classification.
- Run inference locally on CPU.
- Return a score, alert level, fault type, and explanation.
- Integrate with existing Django alerts and tickets.
- Provide a short demo script with normal, warning, and critical examples.

### Should Have

- Show top contributing features:
  - vibration
  - gauge deviation
  - temperature
  - humidity
- Store or display the model name/version.
- Keep simple fallback rules if model files are missing.
- Show a processing trace in the UI or API response.

### Will Not Have For Hackathon

- Full autonomous multi-agent orchestration.
- Training large neural networks.
- Real-time streaming infrastructure.
- Long-term memory.
- Online learning.
- Weather API integration.
- Graph neural networks.
- RAG over maintenance documents.
- Kubernetes deployment.

## Recommended Frameworks

Use at most two AI/data frameworks:

1. `scikit-learn`
   - Best default for hackathon.
   - Fast CPU training.
   - Easy `joblib` export.
   - Good for RandomForest, LogisticRegression, IsolationForest.

2. `PyTorch` only if needed
   - Use only for a tiny MLP or tiny 1D CNN.
   - Avoid LSTM/Transformer for the demo.
   - Do not mix PyTorch and TensorFlow.

Recommended path:

```text
Primary: scikit-learn
Optional: PyTorch tiny MLP
Avoid: full deep learning pipeline
```

If the team wants to honestly say "deep learning" in the demo, use a tiny PyTorch MLP as model 2. If reliability matters more, keep both models in scikit-learn.

## Dataset Strategy

Use the same Rakshak dataset, but do not train on everything.

Current uploaded dataset:

```text
ai_engin/rakshak_massive_dataset.zip
```

Observed structure:

```text
1000 parquet chunks
50 scenario groups
20 chunks per group
```

Recommended hackathon sample:

```text
Keep 10 chunks per group
Total: 500 chunks
Approximate compressed size: half of original
```

If disk/write permission blocks zip rewriting, training scripts should sample during reading instead:

```text
Read only chunk_0 to chunk_9 from every scenario group
Ignore chunk_10 to chunk_19
```

This gives the same practical benefit without modifying the zip.

## Labeling Plan

Use labels in the parquet files if present.

Expected useful columns may include:

- `ambient_temp`
- `humidity`
- `vibration_rms`
- `gauge_width`
- anomaly label column
- fault type column

If explicit labels are missing, derive weak labels from file names and rules.

Example file naming:

```text
NP_SUM_THERMALBUCKLE_002_chunk_10.parquet
HIM_WIN_RAILFRACTURE_032_chunk_12.parquet
CG_WIN_NORMAL_026_chunk_9.parquet
```

Derived labels:

```text
NORMAL -> anomaly = 0, fault_type = normal
THERMALBUCKLE -> anomaly = 1, fault_type = thermal_buckle
RAILFRACTURE -> anomaly = 1, fault_type = rail_fracture
GAUGEWIDEN -> anomaly = 1, fault_type = gauge_widening
BALLASTWASH -> anomaly = 1, fault_type = ballast_washout
ROCKFALL -> anomaly = 1, fault_type = rockfall
SNOWICE -> anomaly = 1, fault_type = snow_ice
```

This is acceptable for a hackathon prototype as long as the team describes it as a demo/weak-label approach.

## Feature Engineering

Do not feed raw massive sequences to complex models.

For each window or chunk, create a compact feature row:

```text
ambient_temp_mean
ambient_temp_max
humidity_mean
vibration_rms_mean
vibration_rms_max
vibration_rms_std
gauge_width_mean
gauge_width_max
gauge_width_min
gauge_deviation_mean = abs(gauge_width - 1676)
gauge_deviation_max
temperature_risk_flag
vibration_risk_flag
gauge_risk_flag
```

Recommended window size:

```text
8 to 16 readings
```

Reason:

- Fast enough for demo.
- Easier than a 64-reading requirement.
- Still lets us say the system considers recent trends.

## Model Design

### Model 1: Risk / Anomaly Model

Purpose:

```text
Predict whether a track section is normal, warning, or critical.
```

Recommended implementation:

```text
RandomForestClassifier
```

Alternative:

```text
IsolationForest + rules
```

Output:

```text
anomaly_score: 0.0 to 1.0
is_anomaly: boolean
alert_level: none | warning | critical
```

Thresholds:

```text
score < 0.65       -> none
0.65 <= score < .85 -> warning
score >= 0.85      -> critical
```

### Model 2: Fault Type Classifier

Purpose:

```text
Classify the likely reason for the anomaly.
```

Recommended implementation:

```text
RandomForestClassifier
```

Optional deep learning version:

```text
Tiny PyTorch MLP
Input: engineered feature vector
Hidden: 32 -> 16
Output: fault classes
```

Output:

```text
fault_type
fault_confidence
top_k
```

### Rule Layer

Keep a transparent rule layer even if a model exists.

Examples:

```text
if gauge deviation > 15 mm:
    force critical risk
    fault_type = gauge_widening

if ambient_temp > 50 and gauge deviation high:
    boost thermal_buckle

if vibration_rms very high:
    boost rail_fracture or joint_wear
```

Why:

- Safer for demos.
- Easier to explain.
- Prevents embarrassing model misses.

## Architecture

Target simple architecture:

```text
Dataset sampler
  -> feature builder
  -> train simple anomaly model
  -> train optional fault model
  -> export joblib files
  -> simple inference pipeline
  -> Django agent
  -> Alert / Ticket / Dashboard / Map
```

Recommended directory structure:

```text
ai_engin/
  simple_training/
    build_dataset.py
    train_simple_models.py
    evaluate_simple_models.py
  simple_models/
    anomaly_model.joblib
    fault_model.joblib
    simple_model_config.json
  inference/
    simple_pipeline.py
    factory.py
```

Backend integration:

```text
backend/
  agents/
    anomaly/anomaly_detection_agent.py
  rakshak_project/
    settings.py
  ai_api/                 # optional
    views.py
    urls.py
```

## Migration Map

| Current Multi-Model Item | Hackathon Replacement |
|---|---|
| VAE anomaly detector | RandomForest/IsolationForest risk model |
| Isolation Forest tier | Keep only if useful, not mandatory |
| Statistical tier | Keep as transparent rules |
| GBM meta-classifier | Remove; use score blending rules |
| HM-STT failure predictor | Remove; derive alert level from risk score |
| Fault deep classifier | RandomForest or tiny MLP classifier |
| GNN root cause model | Existing dictionary-based `RootCauseAgent` |
| RAG explanation | Simple feature-based explanation template |
| LangGraph orchestration | Direct Python call chain |
| Redis/Kafka streams | Django request/management command |
| MLflow registry | `simple_model_config.json` plus optional `MLModel` row |
| Kubernetes/TorchServe | Local Django process |

## Roadmap

### Phase 0: Architecture Freeze

Duration:

```text
0.5 day
```

Tasks:

- Confirm the simple AI scope.
- Set `AI_ENGINE_MODE=simple`.
- Decide model choice:
  - recommended: sklearn RandomForest for both risk and fault.
  - optional: PyTorch tiny MLP only for fault classification.
- Freeze feature columns.
- Freeze demo scenarios:
  - normal
  - thermal buckle risk
  - rail fracture risk
  - gauge widening risk

Deliverables:

- This roadmap.
- Backend compatibility audit.
- Final demo story.

### Phase 1: Dataset Sampling And Feature Builder

Duration:

```text
1 day
```

Tasks:

- Read parquet files from `rakshak_massive_dataset.zip`.
- Select only `chunk_0` to `chunk_9` for every scenario group.
- Extract only required columns.
- Create engineered feature rows.
- Create labels from dataset columns or file names.
- Save small training tables:

```text
ai_engin/simple_training/outputs/train_features.parquet
ai_engin/simple_training/outputs/test_features.parquet
```

Acceptance:

- Feature table builds in minutes, not hours.
- Each major scenario/fault class has samples.
- Normal and anomaly rows are both present.

### Phase 2: Train Simple Models

Duration:

```text
1 day
```

Tasks:

- Train anomaly/risk classifier.
- Train optional fault classifier.
- Evaluate with simple metrics:
  - accuracy
  - precision
  - recall
  - F1
  - confusion matrix
- Export models:

```text
ai_engin/simple_models/anomaly_model.joblib
ai_engin/simple_models/fault_model.joblib
ai_engin/simple_models/simple_model_config.json
```

Acceptance:

- Models load on CPU.
- Inference takes less than 100 ms for one request.
- Normal demo input returns low risk.
- Critical demo input returns high risk.

### Phase 3: Backend Adapter

Duration:

```text
1 day
```

Tasks:

- Add `SimpleRakshakInferencePipeline`.
- Add `build_inference_pipeline()` factory.
- Update `AnomalyDetectionAgent` to use the factory.
- Keep compatible `PredictionResult` output.
- Add fallback rules if model files are missing.
- Add smoke tests.

Acceptance:

- Django starts without legacy model files.
- Agent health check works.
- Simple pipeline returns compatible result objects.
- Alerts can be created by the simple AI path.

### Phase 4: Demo API And UI Hook

Duration:

```text
1 day
```

Tasks:

- Add `POST /api/ai/predict/`.
- Add a small demo form or button in the dashboard if time allows.
- Show:
  - score
  - fault type
  - alert level
  - explanation
  - created alert ID
- Make map/dashboard reflect created alerts.

Acceptance:

- A judge can trigger a normal reading and see no alert.
- A judge can trigger a risky reading and see alert creation.
- UI wording says "AI risk model" rather than overclaiming full autonomy.

### Phase 5: Demo Polish

Duration:

```text
1 day
```

Tasks:

- Add seeded demo scenarios.
- Add README instructions.
- Add screenshots or short video.
- Prepare a 60-second explanation:

```text
"We changed from a production-scale multi-agent architecture to a lean hackathon AI.
It uses the same Rakshak data, samples it, trains a lightweight risk model,
and plugs into the existing backend through a compatibility layer."
```

Acceptance:

- Demo runs from a clean checkout.
- No missing model crash.
- No 64-reading delay in the judge flow.
- The story is honest and convincing.

## Functional Requirements

FR-1:
The system shall accept railway sensor values for temperature, humidity, vibration, and gauge width.

FR-2:
The system shall produce an anomaly/risk score between 0 and 1.

FR-3:
The system shall classify risk as `none`, `warning`, or `critical`.

FR-4:
The system shall provide a likely fault type when risk is above threshold.

FR-5:
The system shall generate a human-readable explanation using feature contributions or rule triggers.

FR-6:
The backend shall create an `Alert` when risk is warning or critical and a track section is known.

FR-7:
The map and dashboard shall display alerts through existing APIs without schema changes.

FR-8:
The system shall run on CPU for the hackathon demo.

FR-9:
The system shall gracefully fall back to rules if model artifacts are missing.

FR-10:
The system shall support switching between `simple` and `legacy` AI modes by settings/env var.

## Non-Functional Requirements

NFR-1:
Single prediction latency should be under 100 ms on a normal laptop.

NFR-2:
The backend should start without GPU, Docker, Kafka, Redis, Neo4j, MLflow, or Kubernetes.

NFR-3:
The simple model package should be small enough to commit or provide locally for demo.

NFR-4:
The demo flow should require fewer than 10 sensor readings before showing an AI result.

NFR-5:
The system should explain outputs in plain English.

NFR-6:
All generated alerts should remain traceable through existing `AuditLog` or alert descriptions.

## Demo Scenarios

### Scenario A: Normal Track

Input:

```json
{
  "ambient_temp": 34,
  "humidity": 55,
  "vibration_rms": 1.2,
  "gauge_width": 1676
}
```

Expected:

```text
Risk: none
Fault: normal
No alert created
```

### Scenario B: Gauge Widening Risk

Input:

```json
{
  "ambient_temp": 42,
  "humidity": 40,
  "vibration_rms": 4.8,
  "gauge_width": 1689
}
```

Expected:

```text
Risk: warning or critical
Fault: gauge_widening
Alert created
Speed restriction suggested
```

### Scenario C: Thermal Buckle Risk

Input:

```json
{
  "ambient_temp": 53,
  "humidity": 25,
  "vibration_rms": 3.5,
  "gauge_width": 1684
}
```

Expected:

```text
Risk: warning or critical
Fault: thermal_buckle
Alert created
Maintenance recommendation shown
```

### Scenario D: Rail Fracture Risk

Input:

```json
{
  "ambient_temp": 29,
  "humidity": 50,
  "vibration_rms": 10.5,
  "gauge_width": 1677
}
```

Expected:

```text
Risk: critical
Fault: rail_fracture or joint_wear
Emergency-style recommendation shown
```

## Model Evaluation For Hackathon

Do not spend days building a production evaluation harness.

Use:

```text
train/test split
classification report
confusion matrix
5 to 10 hand-picked demo examples
```

Minimum acceptable result:

```text
The model behaves correctly on the curated demo scenarios.
The reported metrics are honest.
The fallback rules prevent obvious safety misses.
```

## Final Deliverables

- Backend compatibility layer.
- Simple AI training scripts.
- Exported simple model artifacts.
- Demo prediction endpoint.
- Three to four scripted demo scenarios.
- Updated README instructions.
- Existing dashboard/map showing AI-created alerts.

## Main Risks

Risk:
Dataset columns do not match expected sensor names.

Mitigation:
Build a column alias map and fallback file-name labels.

Risk:
Model training takes too long.

Mitigation:
Sample per scenario and use RandomForest with capped trees.

Risk:
Model gives weak predictions during demo.

Mitigation:
Use transparent safety rules blended with model output.

Risk:
Backend crashes when AI files are missing.

Mitigation:
Simple pipeline must support model-missing fallback mode.

Risk:
Team overbuilds the agent system again.

Mitigation:
Freeze scope: one risk model, optional fault model, existing rule agents.

## Final Recommendation

Build the simple path first:

```text
sklearn risk model
sklearn or tiny PyTorch fault model
rule explanations
Django alert integration
```

After the hackathon, the production architecture can be revisited. For now, the simple AI path is the fastest way to produce a reliable, judge-friendly Rakshak demo.

