# Google Colab Training Roadmap

Complete step-by-step guide to train the Rakshak AI models on Google Colab with a T4 GPU.

## Why Colab?

- **Free T4 GPU** — 16GB VRAM, much faster than CPU training
- **12GB RAM** — more than enough for our 250K-row dataset
- **Pre-installed PyTorch** — no need to download 2.4GB locally
- **Easy download** — trained models are saved as small .pkl files (~50KB each)

## Requirements

| Item | Details |
|------|---------|
| Google account | Free tier works fine |
| Runtime type | GPU → T4 (free tier) |
| Dataset | `rakshak_massive_dataset.zip` (~2.7GB) |
| Training time | ~2–3 minutes total |
| Output size | ~100KB (3 small files) |

---

## Step-by-Step Instructions

### Step 1: Upload Dataset to Google Drive

1. Go to [Google Drive](https://drive.google.com)
2. Upload `ai_engin/rakshak_massive_dataset.zip` to the **root** of your Google Drive
   - The file should be at: `My Drive/rakshak_massive_dataset.zip`
   - Upload will take a few minutes (file is ~2.7GB)

### Step 2: Open Google Colab

1. Go to [Google Colab](https://colab.research.google.com)
2. Click **File → New Notebook**
3. Set GPU runtime:
   - Click **Runtime → Change runtime type**
   - Select **T4 GPU** under Hardware accelerator
   - Click **Save**

### Step 3: Mount Google Drive

Paste this in the **first cell** and run it:

```python
from google.colab import drive
drive.mount('/content/drive')
```

Click "Allow" when prompted to give Colab access to your Drive.

### Step 4: Upload Training Script

**Option A — Upload the file:**

1. In the left sidebar of Colab, click the **Files** icon (folder)
2. Click the **Upload** button
3. Upload `ai_engin/colab_train.py` from your local project

Then run:

```python
%run /content/colab_train.py
```

**Option B — Copy-paste:**

1. Open `ai_engin/colab_train.py` in a text editor
2. Copy the entire contents
3. Paste into a single Colab cell
4. Run the cell

### Step 5: Monitor Training

The script will print progress for each step:

```
STEP 1: Building Dataset from Zip          (~2-3 minutes)
STEP 2: Training Risk / Anomaly Model      (~30 seconds)
STEP 3: Training Fault Type Classifier     (~30 seconds)
STEP 4: Demo Scenario Validation           (instant)
STEP 5: Export Trained Models              (instant)
```

You should see output like:

```
[risk] Epoch  50/50 | Loss: 0.2341 | Val Acc: 0.9234
[risk] Best val accuracy: 0.9285

[fault] Epoch  60/60 | Loss: 0.3421 | Val Acc: 0.8756
[fault] Best val accuracy: 0.8812
```

### Step 6: Download Trained Models

After training completes, the models are saved in two places:

**Option A — From Google Drive (recommended):**

The script automatically copies models to `My Drive/rakshak_trained_models/`. Download from Drive:
- `anomaly_model.pkl`
- `fault_model.pkl`
- `model_config.json`
- `rakshak_trained_models.zip` (all 3 files zipped)

**Option B — Direct download from Colab:**

Add this cell and run it:

```python
from google.colab import files
files.download('/content/rakshak_outputs/rakshak_trained_models.zip')
```

### Step 7: Place Model Files in Your Local Project

Extract the downloaded files to these locations:

```
PROTOTYPE_1.0/
├── ai_engin/
│   └── simple_models/           ← CREATE THIS FOLDER
│       ├── anomaly_model.pkl    ← PUT HERE
│       ├── fault_model.pkl      ← PUT HERE
│       └── model_config.json    ← PUT HERE
│
└── backend/
    └── ai_models/               ← CREATE THIS FOLDER
        ├── anomaly_model.pkl    ← COPY HERE (for backend)
        ├── fault_model.pkl      ← COPY HERE (for backend)
        ├── model_config.json    ← COPY HERE (for backend)
        └── simple_pipeline.py   ← COPY FROM ai_engin/simple_pipeline.py
```

**On Windows (PowerShell):**

```powershell
# Create directories
mkdir D:\PROTOTYPE_1.0\ai_engin\simple_models -Force
mkdir D:\PROTOTYPE_1.0\backend\ai_models -Force

# Extract the downloaded zip to ai_engin/simple_models/
Expand-Archive -Path "$HOME\Downloads\rakshak_trained_models.zip" -DestinationPath "D:\PROTOTYPE_1.0\ai_engin\simple_models" -Force

# Copy to backend
Copy-Item D:\PROTOTYPE_1.0\ai_engin\simple_models\* D:\PROTOTYPE_1.0\backend\ai_models\ -Force
Copy-Item D:\PROTOTYPE_1.0\ai_engin\simple_pipeline.py D:\PROTOTYPE_1.0\backend\ai_models\ -Force
```

---

## How the Backend Uses the Trained Models

### Backend Integration

The backend engineer imports the pipeline from `backend/ai_models/`:

```python
# In your Django view or agent
from ai_models.simple_pipeline import SimpleRakshakInferencePipeline

# Initialize once (loads models on startup)
pipeline = SimpleRakshakInferencePipeline(
    model_dir="path/to/backend/ai_models"
)

# Run inference on any sensor reading
result = pipeline.predict(
    ambient_temp=42.0,
    humidity=40.0,
    vibration_rms=4.8,
    gauge_width=1689.0,
)

# Result contains:
# {
#     "anomaly_score": 0.87,
#     "is_anomaly": True,
#     "alert_level": "critical",
#     "fault_type": "gauge_widening",
#     "fault_confidence": 0.92,
#     "explanation": "CRITICAL: Gauge deviation 13.0mm exceeds...",
#     "processing_time_ms": 2.3,
#     "model_used": "pytorch_mlp",
# }
```

### Fallback Mode

If model `.pkl` files are missing, the pipeline automatically falls back to rule-based predictions. No crash, no error — just slightly less accurate predictions.

```python
# This works even without .pkl files
pipeline = SimpleRakshakInferencePipeline(model_dir="/empty/dir")
result = pipeline.predict(ambient_temp=53, humidity=25, vibration_rms=3.5, gauge_width=1684)
# result["model_used"] == "rules_only"
```

---

## What Gets Trained

### Model 1: Risk / Anomaly Model

| Property | Value |
|----------|-------|
| Architecture | MLP (Input→64→32→3) |
| Output classes | `none`, `warning`, `critical` |
| Input features | 22 engineered features |
| File | `anomaly_model.pkl` (~40 KB) |

### Model 2: Fault Type Classifier

| Property | Value |
|----------|-------|
| Architecture | MLP (Input→64→32→7) |
| Output classes | `normal`, `thermal_buckle`, `rail_fracture`, `gauge_widening`, `ballast_washout`, `rockfall`, `snow_ice` |
| Input features | 22 engineered features |
| File | `fault_model.pkl` (~45 KB) |

### What's Inside the .pkl Files

Each pickle file contains a Python dict:

```python
{
    "model_state_dict": { ... },    # PyTorch model weights
    "scaler_mean": [22 floats],     # StandardScaler mean values
    "scaler_scale": [22 floats],    # StandardScaler scale values
    "input_size": 22,               # Number of input features
    "num_classes": 3 or 7,          # Number of output classes
    "class_names": [...],           # Human-readable class names
    "feature_columns": [...],       # Feature column names in order
}
```

---

## Troubleshooting

### "Dataset not found" error

Make sure `rakshak_massive_dataset.zip` is in the root of your Google Drive. If it's in a subfolder, edit the `ZIP_PATH` variable in the script:

```python
ZIP_PATH = "/content/drive/MyDrive/YOUR_FOLDER/rakshak_massive_dataset.zip"
```

### "Runtime disconnected" during training

Colab free tier has time limits. The training should complete in ~3 minutes, well withiReconnect runtime
2. Re-runn limits. If disconnected:
1.  all cells

### Low validation accuracy

This can happen due to randomness. Try:
- Increasing `NUM_EPOCHS_RISK` to 80 and `NUM_EPOCHS_FAULT` to 100
- The rule layer in `simple_pipeline.py` compensates for model weaknesses

### "Out of memory" error

Very unlikely with this small dataset, but if it happens:
- Reduce `BATCH_SIZE` to 128
- Reduce `MAX_CHUNK_INDEX` to 4 (uses 250 files instead of 500)

---

## Files Reference

| File | Location | Purpose |
|------|----------|---------|
| `colab_train.py` | `ai_engin/` | Single-file Colab training script |
| `build_dataset.py` | `ai_engin/` | Local dataset builder (alternative) |
| `train_models.py` | `ai_engin/` | Local training script (alternative) |
| `evaluate_models.py` | `ai_engin/` | Local evaluation script |
| `simple_pipeline.py` | `ai_engin/` | Inference pipeline (copy to backend) |
| `anomaly_model.pkl` | `simple_models/` | Trained risk model (after training) |
| `fault_model.pkl` | `simple_models/` | Trained fault model (after training) |
| `model_config.json` | `simple_models/` | Model metadata & config |
