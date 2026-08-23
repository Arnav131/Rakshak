"""
Rakshak AI Engine — Model Export
===================================
Serializes all trained models to portable formats
for deployment in the Django backend.

Export formats:
- PyTorch models → .pt (state_dict)
- Sklearn/LightGBM → .joblib
- Scalers → .joblib
- Config/metadata → .json
"""

import os
import json
import shutil
import logging
import numpy as np
import torch
import joblib
from datetime import datetime
from typing import Dict, Optional

from config import (
    CHECKPOINT_DIR, EXPORT_DIR, INFERENCE_CONFIG,
    VAE_CONFIG, FAILURE_CONFIG, FAULT_CONFIG,
    IFOREST_CONFIG, META_CONFIG,
    FAULT_CLASSES, RAW_SENSOR_COLUMNS,
    FEATURE_CONFIG,
)
from data.feature_engineer import get_feature_columns

logger = logging.getLogger(__name__)


def export_all_models(
    checkpoint_dir: str = CHECKPOINT_DIR,
    export_dir: str = EXPORT_DIR,
    evaluation_metrics: Optional[Dict] = None,
    anomaly_threshold: Optional[float] = None,
) -> str:
    """
    Export all trained models to the deployment directory.

    This creates a self-contained directory that can be copied
    to `ai_engin/trained_models/` for backend integration.

    Args:
        checkpoint_dir: Where training checkpoints are saved
        export_dir: Where to export production models
        evaluation_metrics: Optional dict of final eval metrics
        anomaly_threshold: Optimal anomaly detection threshold

    Returns:
        Path to the export directory
    """
    os.makedirs(export_dir, exist_ok=True)

    logger.info(f"Exporting models to {export_dir}")
    exported = []

    # ─── 1. VAE Anomaly Detector ───
    vae_ckpt_path = os.path.join(checkpoint_dir, "vae_best.pt")
    if os.path.exists(vae_ckpt_path):
        vae_export = os.path.join(export_dir, INFERENCE_CONFIG.vae_model_file)

        # Load checkpoint and extract only state_dict
        checkpoint = torch.load(vae_ckpt_path, map_location="cpu")
        torch.save({
            "model_state_dict": checkpoint["model_state_dict"],
            "config": {
                "input_channels": VAE_CONFIG.input_channels,
                "sequence_length": VAE_CONFIG.sequence_length,
                "encoder_channels": VAE_CONFIG.encoder_channels,
                "encoder_kernel_sizes": VAE_CONFIG.encoder_kernel_sizes,
                "latent_dim": VAE_CONFIG.latent_dim,
            },
            "metrics": checkpoint.get("metrics", {}),
            "epoch": checkpoint.get("epoch", -1),
        }, vae_export)
        exported.append(("VAE Anomaly Detector", INFERENCE_CONFIG.vae_model_file))
        logger.info(f"  ✓ VAE exported → {INFERENCE_CONFIG.vae_model_file}")

    # Copy VAE scaler if exists
    vae_scaler_src = os.path.join(checkpoint_dir, "vae_scaler.joblib")
    if os.path.exists(vae_scaler_src):
        shutil.copy2(vae_scaler_src, os.path.join(export_dir, INFERENCE_CONFIG.vae_scaler_file))
        exported.append(("VAE Scaler", INFERENCE_CONFIG.vae_scaler_file))

    # ─── 2. Failure Predictor ───
    fp_ckpt_path = os.path.join(checkpoint_dir, "failure_predictor_best.pt")
    if os.path.exists(fp_ckpt_path):
        fp_export = os.path.join(export_dir, INFERENCE_CONFIG.failure_model_file)
        checkpoint = torch.load(fp_ckpt_path, map_location="cpu")
        torch.save({
            "model_state_dict": checkpoint["model_state_dict"],
            "config": {
                "num_features": FAILURE_CONFIG.num_features,
                "sequence_length": FAILURE_CONFIG.sequence_length,
                "tcn_channels": FAILURE_CONFIG.tcn_channels,
                "tcn_dilations": FAILURE_CONFIG.tcn_dilations,
                "transformer_d_model": FAILURE_CONFIG.transformer_d_model,
                "transformer_nhead": FAILURE_CONFIG.transformer_nhead,
                "transformer_num_layers": FAILURE_CONFIG.transformer_num_layers,
                "lstm_hidden_size": FAILURE_CONFIG.lstm_hidden_size,
                "prediction_horizons": FAILURE_CONFIG.prediction_horizons,
            },
            "metrics": checkpoint.get("metrics", {}),
            "epoch": checkpoint.get("epoch", -1),
        }, fp_export)
        exported.append(("Failure Predictor", INFERENCE_CONFIG.failure_model_file))
        logger.info(f"  ✓ Failure Predictor exported → {INFERENCE_CONFIG.failure_model_file}")

    # Copy failure scaler
    fp_scaler_src = os.path.join(checkpoint_dir, "failure_scaler.joblib")
    if os.path.exists(fp_scaler_src):
        shutil.copy2(fp_scaler_src, os.path.join(export_dir, INFERENCE_CONFIG.failure_scaler_file))
        exported.append(("Failure Scaler", INFERENCE_CONFIG.failure_scaler_file))

    # ─── 3. Fault Classifier ───
    fc_ckpt_path = os.path.join(checkpoint_dir, "fault_classifier_best.pt")
    if os.path.exists(fc_ckpt_path):
        fc_export = os.path.join(export_dir, INFERENCE_CONFIG.classifier_model_file)
        checkpoint = torch.load(fc_ckpt_path, map_location="cpu")
        torch.save({
            "model_state_dict": checkpoint["model_state_dict"],
            "config": {
                "num_features": FAULT_CONFIG.num_features,
                "sequence_length": FAULT_CONFIG.sequence_length,
                "initial_channels": FAULT_CONFIG.initial_channels,
                "block_channels": FAULT_CONFIG.block_channels,
                "blocks_per_stage": FAULT_CONFIG.blocks_per_stage,
                "num_classes": FAULT_CONFIG.num_classes,
            },
            "metrics": checkpoint.get("metrics", {}),
            "epoch": checkpoint.get("epoch", -1),
        }, fc_export)
        exported.append(("Fault Classifier", INFERENCE_CONFIG.classifier_model_file))
        logger.info(f"  ✓ Fault Classifier exported → {INFERENCE_CONFIG.classifier_model_file}")

    # Copy classifier scaler
    fc_scaler_src = os.path.join(checkpoint_dir, "classifier_scaler.joblib")
    if os.path.exists(fc_scaler_src):
        shutil.copy2(fc_scaler_src, os.path.join(export_dir, INFERENCE_CONFIG.classifier_scaler_file))

    # ─── 4. Isolation Forest ───
    iso_src = os.path.join(checkpoint_dir, "isolation_forest.joblib")
    if os.path.exists(iso_src):
        shutil.copy2(iso_src, os.path.join(export_dir, INFERENCE_CONFIG.iforest_model_file))
        exported.append(("Isolation Forest", INFERENCE_CONFIG.iforest_model_file))
        logger.info(f"  ✓ Isolation Forest exported → {INFERENCE_CONFIG.iforest_model_file}")

    # ─── 5. Meta-Classifier ───
    meta_src = os.path.join(checkpoint_dir, "meta_classifier.joblib")
    if os.path.exists(meta_src):
        shutil.copy2(meta_src, os.path.join(export_dir, INFERENCE_CONFIG.meta_model_file))
        exported.append(("Meta-Classifier", INFERENCE_CONFIG.meta_model_file))
        logger.info(f"  ✓ Meta-Classifier exported → {INFERENCE_CONFIG.meta_model_file}")

    # Copy meta scaler
    meta_scaler_src = os.path.join(checkpoint_dir, "meta_scaler.joblib")
    if os.path.exists(meta_scaler_src):
        shutil.copy2(meta_scaler_src, os.path.join(export_dir, INFERENCE_CONFIG.meta_scaler_file))

    # ─── 6. Statistical detector ───
    stat_src = os.path.join(checkpoint_dir, "stat_detector.joblib")
    if os.path.exists(stat_src):
        shutil.copy2(stat_src, os.path.join(export_dir, "stat_detector.joblib"))
        exported.append(("Statistical Detector", "stat_detector.joblib"))

    # ─── 7. Fault label encoder ───
    encoder_src = os.path.join(checkpoint_dir, "fault_label_encoder.joblib")
    if os.path.exists(encoder_src):
        shutil.copy2(encoder_src, os.path.join(export_dir, "fault_label_encoder.joblib"))
        exported.append(("Fault Label Encoder", "fault_label_encoder.joblib"))

    # ─── 8. Model Configuration JSON ───
    config = {
        "version": "1.0.0",
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "models": {item[0]: item[1] for item in exported},
        "feature_columns": {
            "raw_sensors": RAW_SENSOR_COLUMNS,
            "engineered": get_feature_columns(),
        },
        "fault_classes": sorted(FAULT_CLASSES),
        "anomaly_threshold": anomaly_threshold or INFERENCE_CONFIG.anomaly_threshold,
        "prediction_horizons": FAILURE_CONFIG.prediction_horizons,
        "window_size": VAE_CONFIG.sequence_length,
        "evaluation_metrics": evaluation_metrics or {},
        "configs": {
            "vae": {
                "input_channels": VAE_CONFIG.input_channels,
                "latent_dim": VAE_CONFIG.latent_dim,
                "sequence_length": VAE_CONFIG.sequence_length,
            },
            "failure": {
                "num_features": FAILURE_CONFIG.num_features,
                "sequence_length": FAILURE_CONFIG.sequence_length,
                "prediction_horizons": FAILURE_CONFIG.prediction_horizons,
            },
            "classifier": {
                "num_features": FAULT_CONFIG.num_features,
                "num_classes": FAULT_CONFIG.num_classes,
                "sequence_length": FAULT_CONFIG.sequence_length,
            },
        },
    }

    config_path = os.path.join(export_dir, INFERENCE_CONFIG.config_file)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2, default=str)
    logger.info(f"  ✓ Config exported → {INFERENCE_CONFIG.config_file}")

    # ─── Summary ───
    total_size = sum(
        os.path.getsize(os.path.join(export_dir, f))
        for f in os.listdir(export_dir)
        if os.path.isfile(os.path.join(export_dir, f))
    )

    logger.info(f"\n{'='*50}")
    logger.info(f"EXPORT COMPLETE")
    logger.info(f"  Directory: {export_dir}")
    logger.info(f"  Models exported: {len(exported)}")
    logger.info(f"  Total size: {total_size / 1024 / 1024:.1f} MB")
    logger.info(f"{'='*50}")

    for name, fname in exported:
        size = os.path.getsize(os.path.join(export_dir, fname))
        logger.info(f"  {name:30s} → {fname:40s} ({size/1024:.0f} KB)")

    return export_dir
