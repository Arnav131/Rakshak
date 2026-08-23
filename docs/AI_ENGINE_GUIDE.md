# Rakshak AI Engine Training And Backend Guide

This guide explains the full path:

1. Upload the AI engine and dataset to Google Drive.
2. Train the model in Google Colab using GPU.
3. Save/export the trained model files.
4. Copy the trained model files back into this project.
5. Use the trained model from the Django backend.

It is written very slowly and simply on purpose.

---

## 0. The Short Answer

Yes, your idea is correct.

You should train the AI models in Google Colab because Colab gives you GPU.

Then you should export the trained model files.

Then you should copy those exported files into:

```text
D:\Rakshak\ai_engin\trained_models\
```

Then the Django backend can load them using:

```python
from ai_engin.inference.pipeline import RakshakInferencePipeline
```

Important:

Do not use one random pickle file for everything.

This project already expects these file types:

```text
.pt      -> PyTorch neural network models
.joblib  -> sklearn / LightGBM / scaler models
.json    -> model configuration file
```

So your final model folder should contain files like:

```text
ai_engin/trained_models/
    vae_anomaly_detector.pt
    failure_predictor.pt
    fault_classifier.pt
    isolation_forest.joblib
    meta_classifier.joblib
    stat_detector.joblib
    model_config.json
```

Some extra `.joblib` scaler files may also be present. That is okay.

---

## 1. Understand The Project In Very Simple Words

Your project has two big parts.

Part 1 is the backend:

```text
backend/
```

This is the Django website/server.

Part 2 is the AI engine:

```text
ai_engin/
```

This contains the model training code and inference code.

Training means:

```text
The computer learns from data.
```

Inference means:

```text
The trained model is used to make predictions.
```

You train in Colab.

You infer in the backend.

That means:

```text
Google Colab GPU -> trains model -> saves trained files
Django backend   -> loads trained files -> predicts alerts/failures
```

---

## 2. What Not To Do

Do not train the large model on your normal laptop if you do not have GPU.

Do not put training code inside Django views.

Do not make users wait while the backend trains models.

Do not use `app.py` as the main backend for this project.

This project is a Django project, so the backend starts from:

```text
backend/manage.py
```

Use `app.py` only if you want a tiny personal test script.

For the real project, use Django and the existing AI pipeline.

---

## 3. Files You Need Before Starting

Before opening Google Colab, make sure these exist on your computer:

```text
D:\Rakshak\ai_engin\
D:\Rakshak\ai_engin\requirements_colab.txt
D:\Rakshak\ai_engin\rakshak_massive_dataset.zip
D:\Rakshak\ai_engin\colab_training\
D:\Rakshak\ai_engin\colab_training\train_all_models.ipynb
```

The dataset file is large:

```text
rakshak_massive_dataset.zip
```

This file is the training data.

Do not rename it.

The code expects this exact name:

```text
rakshak_massive_dataset.zip
```

---

## 4. Upload Files To Google Drive

Open your browser.

Go to:

```text
https://drive.google.com
```

Log in with the same Google account you will use in Colab.

Now create this folder in Google Drive:

```text
My Drive/ai_engin
```

The folder name must be:

```text
ai_engin
```

Do not write:

```text
AI_Engine
ai_engine
ai-engin
rakshak_ai
```

Use exactly:

```text
ai_engin
```

Now upload these items into that Google Drive folder:

```text
requirements_colab.txt
rakshak_massive_dataset.zip
colab_training/
```

After upload, your Google Drive should look like this:

```text
My Drive/
    ai_engin/
        requirements_colab.txt
        rakshak_massive_dataset.zip
        colab_training/
            train_all_models.ipynb
            config.py
            data/
            evaluation/
            export/
            models/
            training/
```

If the dataset upload is slow, wait.

Do not close the browser tab while upload is running.

When upload is complete, refresh Google Drive and check that the file is really there.

---

## 5. Open Google Colab

Go to:

```text
https://colab.research.google.com
```

Click:

```text
File -> Upload notebook
```

Select this file from your computer:

```text
D:\Rakshak\ai_engin\colab_training\train_all_models.ipynb
```

Wait for the notebook to open.

---

## 6. Turn On GPU In Colab

In Colab, click:

```text
Runtime -> Change runtime type
```

Set:

```text
Hardware accelerator = GPU
```

If Colab shows GPU type, choose:

```text
T4 GPU
```

Click:

```text
Save
```

Now check that GPU is working.

Create a new code cell or use the first setup area.

Run:

```python
!nvidia-smi
```

If GPU is working, you will see a table showing an NVIDIA GPU.

If you see an error, GPU is not attached.

In that case:

1. Click `Runtime`.
2. Click `Change runtime type`.
3. Choose `GPU`.
4. Click `Save`.
5. Run `!nvidia-smi` again.

---

## 7. Mount Google Drive In Colab

Run this code cell:

```python
from google.colab import drive
drive.mount('/content/drive')
```

Google will show a permission screen.

Click your Google account.

Allow access.

After that, Colab can read your Google Drive files.

Now check that your folder is visible:

```python
!ls -lah /content/drive/MyDrive/ai_engin
```

You should see:

```text
requirements_colab.txt
rakshak_massive_dataset.zip
colab_training
```

If you do not see these files, stop.

Fix your Google Drive folder first.

---

## 8. Install Colab Dependencies

In Colab, run:

```python
%cd /content/drive/MyDrive/ai_engin
!pip install -r requirements_colab.txt
```

This installs:

```text
torch
pandas
numpy
pyarrow
scikit-learn
lightgbm
xgboost
joblib
matplotlib
seaborn
tqdm
pyyaml
```

Wait until installation finishes.

If Colab asks to restart runtime, restart it.

If you restart runtime, you must mount Drive again:

```python
from google.colab import drive
drive.mount('/content/drive')
```

Then go back to the project folder again:

```python
%cd /content/drive/MyDrive/ai_engin
```

---

## 9. Set Python Path In Colab

The training code lives here:

```text
/content/drive/MyDrive/ai_engin/colab_training
```

Run:

```python
import sys
import os

DRIVE_PROJECT_DIR = "/content/drive/MyDrive/ai_engin"
COLAB_TRAINING_DIR = os.path.join(DRIVE_PROJECT_DIR, "colab_training")

sys.path.insert(0, COLAB_TRAINING_DIR)

print("Training code folder:", COLAB_TRAINING_DIR)
print("Folder exists:", os.path.exists(COLAB_TRAINING_DIR))
```

The output should say:

```text
Folder exists: True
```

If it says `False`, your Drive folder structure is wrong.

---

## 10. Make Safe Training Folders

Run this in Colab:

```python
import os

DRIVE_PROJECT_DIR = "/content/drive/MyDrive/ai_engin"

CHECKPOINT_DIR = os.path.join(DRIVE_PROJECT_DIR, "checkpoints")
EXPORT_DIR = os.path.join(DRIVE_PROJECT_DIR, "trained_models")
LOG_DIR = os.path.join(DRIVE_PROJECT_DIR, "logs")

os.makedirs(CHECKPOINT_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

print("Checkpoints:", CHECKPOINT_DIR)
print("Exports:", EXPORT_DIR)
print("Logs:", LOG_DIR)
```

This creates:

```text
My Drive/ai_engin/checkpoints
My Drive/ai_engin/trained_models
My Drive/ai_engin/logs
```

Why do this?

Because Google Colab can disconnect.

If you save checkpoints only inside `/content`, they can disappear after disconnect.

Saving checkpoints in Google Drive is safer.

---

## 11. Configure The Training Code To Use Google Drive

Run:

```python
import config

config.PROJECT_DIR = "/content/drive/MyDrive/ai_engin"
config.DATASET_ZIP_PATH = "/content/drive/MyDrive/ai_engin/rakshak_massive_dataset.zip"
config.CHECKPOINT_DIR = "/content/drive/MyDrive/ai_engin/checkpoints"
config.EXPORT_DIR = "/content/drive/MyDrive/ai_engin/trained_models"
config.LOG_DIR = "/content/drive/MyDrive/ai_engin/logs"

print("Dataset:", config.DATASET_ZIP_PATH)
print("Checkpoint folder:", config.CHECKPOINT_DIR)
print("Export folder:", config.EXPORT_DIR)
```

Now check that the dataset file exists:

```python
import os
print(os.path.exists(config.DATASET_ZIP_PATH))
```

The output must be:

```text
True
```

If it is `False`, Colab cannot find your dataset.

Fix the file location before training.

---

## 12. Load The Dataset

Run:

```python
from data.data_loader import ParquetStreamLoader, split_scenarios_by_type

loader = ParquetStreamLoader(zip_path=config.DATASET_ZIP_PATH)

print("Number of parquet files:", loader.num_files)
print("Number of scenarios:", loader.num_scenarios)
```

If this works, your ZIP file is readable.

If this fails, check:

1. Is `rakshak_massive_dataset.zip` uploaded?
2. Is it inside `My Drive/ai_engin/`?
3. Is the filename exactly `rakshak_massive_dataset.zip`?
4. Is the ZIP file corrupted?

---

## 13. Split Data Into Train, Validation, And Test

Run:

```python
train_files, val_files, test_files = split_scenarios_by_type(loader)

print("Train files:", len(train_files))
print("Validation files:", len(val_files))
print("Test files:", len(test_files))
```

Meaning:

```text
Train data      -> model learns from this
Validation data -> model checks itself during training
Test data       -> final checking after training
```

Do not train on test data.

Test data is for final checking only.

---

## 14. Prepare The Training Windows

The model does not read only one row.

It reads a small sequence of rows.

In this project, one sequence window is:

```text
64 readings
```

The four raw sensor columns are:

```text
ambient_temp
humidity
vibration_rms
gauge_width
```

Your training notebook already contains cells to prepare these windows.

Run the notebook cells in order.

Do not skip the data preparation cells.

When the cells finish, you should see shapes like:

```text
VAE train: (...)
Failure train: (...)
Classifier train: (...)
```

If the notebook crashes because RAM is full, reduce the number of rows per file.

Open:

```text
ai_engin/colab_training/config.py
```

Find:

```python
max_rows_per_file: int = 50000
```

Try a smaller number:

```python
max_rows_per_file: int = 10000
```

Then restart runtime and run again.

For first testing, small data is okay.

For final model, use more data.

---

## 15. Train Model 1: VAE Anomaly Detector

This model learns normal and abnormal patterns.

Run the notebook section that trains VAE.

It uses:

```python
from training.train_vae import VAETrainer
```

The best checkpoint should be saved as:

```text
My Drive/ai_engin/checkpoints/vae_best.pt
```

After training, check it:

```python
!ls -lah /content/drive/MyDrive/ai_engin/checkpoints
```

You should see:

```text
vae_best.pt
```

---

## 16. Train Model 2: Failure Predictor

This model predicts future failure probability.

Current horizons are:

```text
1h
6h
24h
```

Run the notebook section that trains the failure predictor.

It uses:

```python
from training.train_failure import FailurePredictorTrainer
```

The best checkpoint should be saved as:

```text
My Drive/ai_engin/checkpoints/failure_predictor_best.pt
```

Check it:

```python
!ls -lah /content/drive/MyDrive/ai_engin/checkpoints
```

You should see:

```text
failure_predictor_best.pt
```

---

## 17. Train Model 3: Fault Classifier

This model tells what kind of fault may be present.

Examples:

```text
rail_fracture
thermal_buckle
gauge_widening
ballast_washout
subgrade_failure
```

Run the notebook section that trains the fault classifier.

It uses:

```python
from training.train_classifier import FaultClassifierTrainer
```

The best checkpoint should be saved as:

```text
My Drive/ai_engin/checkpoints/fault_classifier_best.pt
```

Check it:

```python
!ls -lah /content/drive/MyDrive/ai_engin/checkpoints
```

You should see:

```text
fault_classifier_best.pt
```

---

## 18. Train Model 4: Ensemble Anomaly Models

This part trains:

```text
stat_detector.joblib
isolation_forest.joblib
meta_classifier.joblib
```

Run the notebook section that trains the ensemble.

It uses:

```python
from training.train_ensemble import EnsembleTrainer
```

The files should be saved in:

```text
My Drive/ai_engin/checkpoints/
```

Check them:

```python
!ls -lah /content/drive/MyDrive/ai_engin/checkpoints
```

You should see:

```text
stat_detector.joblib
isolation_forest.joblib
meta_classifier.joblib
```

---

## 19. Evaluate The Models

Evaluation means checking how good the model is.

Run the notebook evaluation section.

It uses:

```python
from evaluation.evaluate_all import run_full_evaluation
```

You want metrics like:

```text
accuracy
precision
recall
f1
auroc
```

If metrics are bad, do not use the model in the final backend yet.

Improve the data or train longer.

For a demo, a partially trained model can still be used, but you should be honest that it is a prototype.

---

## 20. Export The Trained Models

Training checkpoints are not the final deployment folder.

You must export them.

Run:

```python
from export.export_models import export_all_models

export_dir = export_all_models(
    checkpoint_dir=config.CHECKPOINT_DIR,
    export_dir=config.EXPORT_DIR,
)

print("Models exported to:", export_dir)
```

This creates the final backend-ready folder:

```text
My Drive/ai_engin/trained_models/
```

Now check it:

```python
!ls -lah /content/drive/MyDrive/ai_engin/trained_models
```

You should see these important files:

```text
vae_anomaly_detector.pt
failure_predictor.pt
fault_classifier.pt
isolation_forest.joblib
meta_classifier.joblib
stat_detector.joblib
model_config.json
```

If `model_config.json` is missing, do not continue.

The backend uses this file to know model settings.

---

## 21. Download The Exported Models To Your Computer

Open Google Drive in your browser:

```text
https://drive.google.com
```

Go to:

```text
My Drive/ai_engin/trained_models
```

Download the whole `trained_models` folder.

Google Drive may download it as:

```text
trained_models.zip
```

If it downloads as ZIP, extract it.

After extracting, you should have a folder named:

```text
trained_models
```

Inside that folder you should see:

```text
vae_anomaly_detector.pt
failure_predictor.pt
fault_classifier.pt
isolation_forest.joblib
meta_classifier.joblib
stat_detector.joblib
model_config.json
```

---

## 22. Put Trained Models Into The Local Project

Go to your local project:

```text
D:\Rakshak
```

Open this folder:

```text
D:\Rakshak\ai_engin\trained_models
```

Copy all downloaded model files into that folder.

Final local folder should look like:

```text
D:\Rakshak\ai_engin\trained_models\
    vae_anomaly_detector.pt
    failure_predictor.pt
    fault_classifier.pt
    isolation_forest.joblib
    meta_classifier.joblib
    stat_detector.joblib
    model_config.json
```

Do not put the files here:

```text
D:\Rakshak\trained_models
D:\Rakshak\backend\trained_models
D:\Rakshak\ai_engin\colab_training\trained_models
```

Use exactly:

```text
D:\Rakshak\ai_engin\trained_models
```

---

## 23. Install AI Dependencies On The Backend Computer

Your current root `requirements.txt` only installs Django.

That is enough for the website, but not enough for AI inference.

The backend computer must also have AI packages installed.

Open PowerShell.

Go to the project:

```powershell
cd D:\Rakshak
```

Activate virtual environment:

```powershell
venv\Scripts\activate
```

Install Django requirements:

```powershell
python -m pip install -r requirements.txt
```

Install CPU PyTorch for backend inference:

```powershell
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

Install the remaining AI packages:

```powershell
python -m pip install numpy pandas scipy scikit-learn lightgbm xgboost joblib pyarrow pyyaml matplotlib seaborn tqdm
```

Why CPU PyTorch?

Because your backend server can run predictions on CPU.

Training needs GPU.

Inference can run on CPU, especially for a demo or prototype.

---

## 24. Test That The Backend Can See The Models

In PowerShell, from:

```text
D:\Rakshak
```

Run:

```powershell
python -c "from ai_engin.inference.pipeline import RakshakInferencePipeline; p=RakshakInferencePipeline(model_dir='ai_engin/trained_models'); print(p.health_check())"
```

Good output should look like this:

```text
{
  'status': 'healthy',
  'models': {
    'vae': True,
    'failure_predictor': True,
    'fault_classifier': True,
    'isolation_forest': True,
    'meta_classifier': True,
    'stat_detector': True,
    'config': True
  },
  ...
}
```

If status is:

```text
degraded
```

then some model files are missing.

Check the folder again:

```text
D:\Rakshak\ai_engin\trained_models
```

---

## 25. Test One Prediction Manually

The AI pipeline needs 64 readings before it predicts.

Why?

Because the model looks at a sequence, not just one point.

Run this from `D:\Rakshak`:

```powershell
python -c "from ai_engin.inference.pipeline import RakshakInferencePipeline; p=RakshakInferencePipeline(model_dir='ai_engin/trained_models'); result=None; [p.process_reading(ambient_temp=38.0, humidity=45.0, vibration_rms=0.8, gauge_width=1676.0, sensor_id='test') for _ in range(63)]; result=p.process_reading(ambient_temp=50.0, humidity=30.0, vibration_rms=8.5, gauge_width=1689.0, sensor_id='test'); print(result.to_dict() if result else 'Still buffering')"
```

If everything works, you should see a dictionary with:

```text
anomaly
failure_prediction
fault_classification
processing_time_ms
```

If you see:

```text
Still buffering
```

run it again or make sure 64 readings were sent.

---

## 26. Use The Model In Django Backend

The real backend should use this existing class:

```python
from ai_engin.inference.pipeline import RakshakInferencePipeline
```

The project also has an agent wrapper:

```python
from agents.anomaly.anomaly_detection_agent import AnomalyDetectionAgent
```

The anomaly agent does this:

1. Loads the AI model pipeline.
2. Accepts sensor readings.
3. Runs anomaly detection.
4. Runs failure prediction.
5. Runs fault classification.
6. Creates Django `Alert` records if anomaly/failure is detected.

That means the best project flow is:

```text
sensor reading -> SensorIngestionAgent -> AnomalyDetectionAgent -> Alert/Ticket/Dashboard
```

---

## 27. Minimal Backend Test Using The Agent

From PowerShell:

```powershell
cd D:\Rakshak
venv\Scripts\activate
```

Run:

```powershell
python -c "import sys, os; sys.path.insert(0, 'backend'); os.environ.setdefault('DJANGO_SETTINGS_MODULE','rakshak_project.settings'); import django; django.setup(); from agents.anomaly.anomaly_detection_agent import AnomalyDetectionAgent; agent=AnomalyDetectionAgent(); print(agent.health_check())"
```

If this prints agent health, the agent imports correctly.

Now remember:

The agent needs real database IDs if you want it to create alerts.

These fields must exist in the database:

```text
sensor_id
track_section_id
reading_id
```

If you pass fake IDs, alert creation may fail.

---

## 28. Start The Django Backend

From PowerShell:

```powershell
cd D:\Rakshak
venv\Scripts\activate
```

Run migrations:

```powershell
python backend\manage.py migrate
```

If your database is empty, seed demo data:

```powershell
python backend\manage.py seed_master_data
python backend\manage.py seed_routes
python backend\manage.py seed_sensors
python backend\manage.py seed_demo_data
```

Now start the server:

```powershell
python backend\manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

---

## 29. Important Backend Reality Check

The AI model files can be loaded by the backend.

But the current project does not yet have a finished public AI API endpoint like:

```text
POST /api/v2/predict/
```

So you have two choices.

Choice A:

Use the AI through internal Django agents.

This is best for your current project.

Choice B:

Create a new Django API endpoint that accepts sensor values and calls:

```python
RakshakInferencePipeline
```

Do not create a separate Flask `app.py` unless it is only for testing.

Your real app is Django.

---

## 30. Simple Example Of How A Django View Would Use The Pipeline

This is only an example.

Do not paste blindly unless you are ready to create an API view.

```python
from django.http import JsonResponse
from ai_engin.inference.pipeline import RakshakInferencePipeline

pipeline = RakshakInferencePipeline(model_dir="ai_engin/trained_models")

def predict_sensor_reading(request):
    result = pipeline.process_reading(
        ambient_temp=42.5,
        humidity=22.0,
        vibration_rms=0.85,
        gauge_width=1676.3,
        sensor_id="sensor-1",
    )

    if result is None:
        return JsonResponse({
            "status": "buffering",
            "message": "Need 64 readings before prediction."
        })

    return JsonResponse(result.to_dict())
```

Again:

This is only the basic idea.

For your project, using `AnomalyDetectionAgent` is better because it also creates alerts.

---

## 31. What Each Exported File Does

```text
vae_anomaly_detector.pt
```

Deep learning anomaly detector.

```text
failure_predictor.pt
```

Predicts future failure risk.

```text
fault_classifier.pt
```

Classifies the fault type.

```text
isolation_forest.joblib
```

Traditional ML anomaly detector.

```text
meta_classifier.joblib
```

Combines anomaly scores from multiple detectors.

```text
stat_detector.joblib
```

Fast statistical detector.

```text
model_config.json
```

Tells the backend model settings, labels, thresholds, and feature information.

---

## 32. Common Mistakes And Fixes

Mistake:

```text
I trained in Colab but backend says model missing.
```

Fix:

Check that files are inside:

```text
D:\Rakshak\ai_engin\trained_models
```

Not somewhere else.

Mistake:

```text
I uploaded folder as ai_engine instead of ai_engin.
```

Fix:

Rename Google Drive folder to:

```text
ai_engin
```

Mistake:

```text
Colab says dataset not found.
```

Fix:

Make sure this file exists:

```text
/content/drive/MyDrive/ai_engin/rakshak_massive_dataset.zip
```

Mistake:

```text
Backend says ModuleNotFoundError: torch
```

Fix:

Install PyTorch:

```powershell
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

Mistake:

```text
Pipeline says Still buffering.
```

Fix:

Send 64 readings for the same `sensor_id`.

Mistake:

```text
I only copied one .pkl file.
```

Fix:

Use the exported model folder, not one random pickle file.

The backend expects several files.

---

## 33. Final Checklist

Before saying "AI is connected", check every item below.

```text
[ ] Google Drive has My Drive/ai_engin/
[ ] Dataset is uploaded as rakshak_massive_dataset.zip
[ ] Colab runtime is using GPU
[ ] Drive is mounted in Colab
[ ] Colab dependencies are installed
[ ] Dataset loads successfully
[ ] Train/validation/test split works
[ ] VAE training finishes
[ ] Failure predictor training finishes
[ ] Fault classifier training finishes
[ ] Ensemble training finishes
[ ] Export step finishes
[ ] model_config.json exists
[ ] trained_models folder is downloaded
[ ] trained_models files are copied into D:\Rakshak\ai_engin\trained_models
[ ] Backend AI dependencies are installed
[ ] Pipeline health check says healthy
[ ] Manual prediction test works
[ ] Django server starts
```

---

## 34. Recommended Workflow Every Time You Retrain

Use this same order every time:

```text
1. Upload latest dataset to Google Drive.
2. Open Colab.
3. Turn on GPU.
4. Mount Drive.
5. Install requirements.
6. Train models.
7. Export models.
8. Download trained_models folder.
9. Replace local ai_engin/trained_models files.
10. Run backend health check.
11. Start Django server.
12. Test prediction.
```

That is the full loop.

---

## 35. Final Simple Explanation

Think of it like this:

```text
Colab is the school.
The model is the student.
The dataset is the book.
Training is studying.
The exported model files are the educated student.
The Django backend is the job.
The trained model works inside Django after studying in Colab.
```

So your plan is right:

```text
Train separately in Colab.
Export model files.
Put model files into ai_engin/trained_models.
Use them from Django backend.
```

