"""
Rakshak AI Engine — Ensemble Training (IsoForest + Meta-Classifier)
=====================================================================
Trains the Isolation Forest (Tier-2) and GBM Meta-Classifier
that combines all anomaly detection tiers.
"""

import os
import logging
import numpy as np
import torch
from typing import Dict, Optional, Tuple

from config import (
    IFOREST_CONFIG, META_CONFIG, DATA_CONFIG,
    RAW_SENSOR_COLUMNS, LABEL_COL, CHECKPOINT_DIR,
)
from models.isolation_forest import RakshakIsolationForest, extract_window_features
from models.meta_classifier import (
    MetaClassifier,
    StatisticalAnomalyDetector,
    build_meta_features,
)
from models.vae_anomaly import VAEAnomalyDetector
from training.metrics import compute_binary_metrics, find_optimal_threshold

logger = logging.getLogger(__name__)


class EnsembleTrainer:
    """
    Trains the full 3-tier anomaly detection ensemble:

    1. Tier 1: StatisticalAnomalyDetector (Z-score + IQR) — fit on normal data
    2. Tier 2: IsolationForest — fit on all data (unsupervised)
    3. Tier 3: VAE scores — computed from pre-trained VAE
    4. Meta-Classifier: GBM combining all tier scores — supervised

    Requires a pre-trained VAE model for Tier 3 scores.
    """

    def __init__(
        self,
        vae_model: VAEAnomalyDetector,
        device: str = "cuda",
    ):
        self.vae_model = vae_model
        self.device = device if torch.cuda.is_available() else "cpu"
        self.vae_model = self.vae_model.to(self.device).eval()

        self.stat_detector = StatisticalAnomalyDetector()
        self.iso_forest = RakshakIsolationForest()
        self.meta_classifier = MetaClassifier()

    def compute_vae_scores(
        self,
        windows: np.ndarray,
        batch_size: int = 512,
    ) -> np.ndarray:
        """Compute VAE reconstruction error scores for windows."""
        scores = []
        N = len(windows)

        for i in range(0, N, batch_size):
            batch = torch.from_numpy(windows[i:i + batch_size]).float().to(self.device)
            batch_scores = self.vae_model.compute_anomaly_score(batch)
            scores.append(batch_scores.cpu().numpy())

        all_scores = np.concatenate(scores)

        # Normalize to [0, 1]
        s_min, s_max = all_scores.min(), all_scores.max()
        if s_max > s_min:
            all_scores = (all_scores - s_min) / (s_max - s_min)

        return all_scores.astype(np.float32)

    def train(
        self,
        train_windows: np.ndarray,
        train_labels: np.ndarray,
        val_windows: np.ndarray,
        val_labels: np.ndarray,
        checkpoint_dir: str = None,
    ) -> Dict[str, float]:
        """
        Train the full ensemble pipeline.

        Args:
            train_windows: (N_train, W, F) — raw sensor windows (4 features)
            train_labels: (N_train,) — binary labels
            val_windows: (N_val, W, F)
            val_labels: (N_val,)
            checkpoint_dir: Where to save models

        Returns:
            Dict of evaluation metrics
        """
        checkpoint_dir = checkpoint_dir or CHECKPOINT_DIR
        os.makedirs(checkpoint_dir, exist_ok=True)

        # ─── Step 1: Extract window-level features for IsoForest ───
        logger.info("Step 1/4: Extracting window features...")
        train_window_features = extract_window_features(train_windows)
        val_window_features = extract_window_features(val_windows)

        # ─── Step 2: Train Tier 1 (Statistical) on normal data ───
        logger.info("Step 2/4: Training Tier 1 (Statistical Detector)...")
        normal_mask = train_labels == 0
        if normal_mask.sum() > 0:
            self.stat_detector.fit(train_window_features[normal_mask])
        else:
            # If no normal samples, fit on all data
            self.stat_detector.fit(train_window_features)

        # Compute Tier 1 scores
        train_t1_zscore, train_t1_iqr = self.stat_detector.predict_scores(train_window_features)
        val_t1_zscore, val_t1_iqr = self.stat_detector.predict_scores(val_window_features)
        logger.info(f"  Tier 1 done. Train Z-score range: [{train_t1_zscore.min():.2f}, {train_t1_zscore.max():.2f}]")

        # ─── Step 3: Train Tier 2 (Isolation Forest) ───
        logger.info("Step 3/4: Training Tier 2 (Isolation Forest)...")
        self.iso_forest.fit(train_window_features, subsample=500000)

        train_t2_scores = self.iso_forest.predict_scores(train_window_features)
        val_t2_scores = self.iso_forest.predict_scores(val_window_features)

        # Evaluate Tier 2 standalone
        t2_metrics = compute_binary_metrics(val_labels, val_t2_scores, prefix="tier2_")
        logger.info(f"  Tier 2 standalone — AUROC: {t2_metrics.get('tier2_auroc', 0):.4f}, "
                     f"F1: {t2_metrics.get('tier2_f1', 0):.4f}")

        # ─── Step 4: Compute Tier 3 (VAE) scores ───
        logger.info("Computing Tier 3 (VAE) scores...")
        train_t3_scores = self.compute_vae_scores(train_windows)
        val_t3_scores = self.compute_vae_scores(val_windows)

        # ─── Step 5: Build meta-features and train meta-classifier ───
        logger.info("Step 4/4: Training Meta-Classifier (GBM)...")

        train_meta = build_meta_features(
            train_t1_zscore, train_t1_iqr,
            train_t2_scores, train_t3_scores,
            raw_features=train_window_features[:, :len(RAW_SENSOR_COLUMNS)],
        )
        val_meta = build_meta_features(
            val_t1_zscore, val_t1_iqr,
            val_t2_scores, val_t3_scores,
            raw_features=val_window_features[:, :len(RAW_SENSOR_COLUMNS)],
        )

        meta_feature_names = (
            ["tier1_zscore", "tier1_iqr", "tier2_iforest", "tier3_vae"]
            + [f"raw_{c}" for c in RAW_SENSOR_COLUMNS]
        )

        self.meta_classifier.fit(
            train_meta, train_labels,
            feature_names=meta_feature_names,
            X_val=val_meta,
            y_val=val_labels,
        )

        # ─── Evaluate ensemble ───
        logger.info("Evaluating full ensemble...")
        val_meta_probs = self.meta_classifier.predict_proba(val_meta)
        ensemble_metrics = compute_binary_metrics(
            val_labels, val_meta_probs, prefix="ensemble_"
        )

        # Find optimal threshold
        opt_thresh, opt_f1 = find_optimal_threshold(val_labels, val_meta_probs)
        ensemble_metrics["optimal_threshold"] = opt_thresh
        ensemble_metrics["optimal_f1"] = opt_f1

        # Feature importance
        importance = self.meta_classifier.get_feature_importance()
        logger.info("Meta-classifier feature importance:")
        for name, imp in list(importance.items())[:10]:
            logger.info(f"  {name}: {imp:.4f}")

        logger.info(
            f"\n{'='*50}\n"
            f"ENSEMBLE RESULTS:\n"
            f"  AUROC: {ensemble_metrics.get('ensemble_auroc', 0):.4f}\n"
            f"  F1: {ensemble_metrics.get('ensemble_f1', 0):.4f}\n"
            f"  FPR: {ensemble_metrics.get('ensemble_fpr', 0):.4f}\n"
            f"  Optimal threshold: {opt_thresh:.3f} (F1={opt_f1:.4f})\n"
            f"{'='*50}"
        )

        # ─── Save all models ───
        self.stat_detector.save(os.path.join(checkpoint_dir, "stat_detector.joblib"))
        self.iso_forest.save(os.path.join(checkpoint_dir, "isolation_forest.joblib"))
        self.meta_classifier.save(os.path.join(checkpoint_dir, "meta_classifier.joblib"))

        logger.info("All ensemble models saved.")

        return ensemble_metrics
