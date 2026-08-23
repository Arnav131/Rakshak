"""
Rakshak AI Engine — Anomaly Detection Inference
==================================================
3-tier anomaly detection pipeline for production use.

Tier 1: Z-score + IQR (< 5ms) → fast statistical screen
Tier 2: Isolation Forest (< 50ms) → multivariate
Tier 3: VAE reconstruction error (< 150ms) → deep learning
Meta:   GBM combining all tiers → calibrated probability
"""

import numpy as np
import torch
import logging
from typing import Optional, Dict, Tuple

from ai_engin.inference.utils import AnomalyResult

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    3-tier anomaly detection pipeline.

    Usage:
        detector = AnomalyDetector(registry)
        result = detector.detect(window)
    """

    def __init__(self, registry):
        """
        Args:
            registry: ModelRegistry instance with loaded models
        """
        self.registry = registry
        self.device = registry.device
        self.threshold = registry.get_anomaly_threshold()

    def _tier1_detect(self, features: np.ndarray) -> Tuple[float, float]:
        """
        Tier 1: Statistical detection (Z-score + IQR).
        Fastest tier — pure NumPy operations.

        Args:
            features: (F,) — window-level feature summary

        Returns:
            (zscore, iqr_score)
        """
        stat = self.registry.get_stat_detector()
        if stat is None:
            return 0.0, 0.0

        features_2d = features.reshape(1, -1)
        zscore, iqr = stat.predict_scores(features_2d)
        return float(zscore[0]), float(iqr[0])

    def _tier2_detect(self, features: np.ndarray) -> float:
        """
        Tier 2: Isolation Forest detection.

        Args:
            features: (F,) — window-level feature summary

        Returns:
            iforest_score in [0, 1]
        """
        iforest = self.registry.get_isolation_forest()
        if iforest is None:
            return 0.0

        features_2d = features.reshape(1, -1)
        scores = iforest.predict_scores(features_2d)
        return float(scores[0])

    def _tier3_detect(self, window: np.ndarray) -> float:
        """
        Tier 3: VAE reconstruction error.

        Args:
            window: (W, 4) — raw sensor window

        Returns:
            vae_score in [0, 1]
        """
        vae = self.registry.get_vae()
        if vae is None:
            return 0.0

        with torch.no_grad():
            x = torch.from_numpy(window).float().unsqueeze(0).to(self.device)
            score = vae.compute_anomaly_score(x)
            return float(score.cpu().item())

    def _meta_classify(
        self,
        tier1_zscore: float,
        tier1_iqr: float,
        tier2_score: float,
        tier3_score: float,
        raw_features: np.ndarray,
    ) -> float:
        """
        Meta-classifier: combines all tier scores.

        Returns:
            calibrated_probability in [0, 1]
        """
        meta = self.registry.get_meta_classifier()
        if meta is None:
            # Fallback: weighted average of tier scores
            return 0.3 * min(tier1_zscore / 5.0, 1.0) + 0.3 * tier2_score + 0.4 * tier3_score

        meta_features = np.array([[
            tier1_zscore, tier1_iqr, tier2_score, tier3_score,
            *raw_features[:4],  # Raw sensor means
        ]], dtype=np.float32)

        proba = meta.predict_proba(meta_features)
        return float(proba[0])

    def detect(self, window: np.ndarray) -> AnomalyResult:
        """
        Run the full 3-tier anomaly detection pipeline.

        Args:
            window: (W, 4) — raw sensor window (ambient_temp, humidity,
                    vibration_rms, gauge_width)

        Returns:
            AnomalyResult with scores from each tier and final decision
        """
        # Extract window-level features for Tier 1 & 2
        window_mean = np.mean(window, axis=0)
        window_std = np.std(window, axis=0)
        window_min = np.min(window, axis=0)
        window_max = np.max(window, axis=0)
        window_range = window_max - window_min
        window_delta = window[-1] - window[0]

        features = np.concatenate([
            window_mean, window_std, window_min,
            window_max, window_range, window_delta,
        ])

        # Run all tiers
        t1_zscore, t1_iqr = self._tier1_detect(features)
        t2_score = self._tier2_detect(features)
        t3_score = self._tier3_detect(window)

        # Meta-classifier
        meta_score = self._meta_classify(
            t1_zscore, t1_iqr, t2_score, t3_score, window_mean
        )

        return AnomalyResult(
            is_anomaly=meta_score >= self.threshold,
            anomaly_score=meta_score,
            tier_scores={
                "tier1_zscore": t1_zscore,
                "tier1_iqr": t1_iqr,
                "tier2_iforest": t2_score,
                "tier3_vae": t3_score,
                "meta": meta_score,
            },
            threshold=self.threshold,
        )
