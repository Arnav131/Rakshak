"""
Rakshak AI Engine — Failure Prediction Inference
===================================================
Multi-horizon failure prediction with uncertainty estimation.
"""

import numpy as np
import torch
import logging
from typing import Optional, Dict

from ai_engin.inference.utils import FailurePrediction

logger = logging.getLogger(__name__)


class FailurePredictor:
    """
    Failure prediction inference with Monte Carlo Dropout uncertainty.

    Predicts failure probability at 1h, 6h, and 24h horizons
    with calibrated uncertainty bounds.
    """

    def __init__(
        self,
        registry,
        alert_threshold: float = 0.7,
        critical_threshold: float = 0.9,
    ):
        self.registry = registry
        self.device = registry.device
        self.alert_threshold = alert_threshold
        self.critical_threshold = critical_threshold

    def _engineer_features(self, window: np.ndarray) -> np.ndarray:
        """
        Apply feature engineering to a raw sensor window.

        For inference, we compute a simplified feature set that
        matches the training pipeline.

        Args:
            window: (W, 4) raw sensors

        Returns:
            (W, F) engineered features
        """
        W, C = window.shape
        features = [window]  # Start with raw features

        # Rolling statistics (simplified for single window)
        for win_size in [8, 16, 32]:
            for col in range(C):
                col_data = window[:, col]
                roll_mean = np.convolve(col_data, np.ones(win_size)/win_size, mode='same')
                roll_std = np.array([
                    np.std(col_data[max(0, i-win_size):i+1])
                    for i in range(W)
                ])
                features.append(roll_mean.reshape(-1, 1))
                features.append(roll_std.reshape(-1, 1))

        # Derivatives
        for col in range(C):
            delta = np.diff(window[:, col], prepend=window[0, col])
            features.append(delta.reshape(-1, 1))

        # Temporal features (simple — assumes equispaced)
        t = np.linspace(0, 1, W)
        features.append(np.sin(2 * np.pi * t).reshape(-1, 1))
        features.append(np.cos(2 * np.pi * t).reshape(-1, 1))

        return np.concatenate(features, axis=1).astype(np.float32)

    def predict(
        self,
        window: np.ndarray,
        use_uncertainty: bool = False,
        n_mc_passes: int = 20,
    ) -> FailurePrediction:
        """
        Predict failure probability at multiple horizons.

        Args:
            window: (W, 4) raw sensor window
            use_uncertainty: Whether to run MC Dropout
            n_mc_passes: Number of MC forward passes

        Returns:
            FailurePrediction with probabilities and alert level
        """
        model = self.registry.get_failure_predictor()
        if model is None:
            return FailurePrediction(alert_level="unknown")

        # Engineer features
        feat_window = self._engineer_features(window)

        # Ensure feature count matches model
        expected_features = model.config.num_features
        actual_features = feat_window.shape[1]

        if actual_features < expected_features:
            # Pad with zeros
            pad = np.zeros((feat_window.shape[0], expected_features - actual_features), dtype=np.float32)
            feat_window = np.concatenate([feat_window, pad], axis=1)
        elif actual_features > expected_features:
            feat_window = feat_window[:, :expected_features]

        x = torch.from_numpy(feat_window).float().unsqueeze(0).to(self.device)

        if use_uncertainty:
            results = model.predict_with_uncertainty(x, n_passes=n_mc_passes)
            probabilities = {h: float(results[h]["mean"].cpu().item()) for h in model.horizons}
            uncertainty = {h: float(results[h]["std"].cpu().item()) for h in model.horizons}
        else:
            with torch.no_grad():
                preds = model(x)
                probabilities = {h: float(preds[h].cpu().item()) for h in model.horizons}
                uncertainty = {}

        # Determine alert level
        max_prob = max(probabilities.values()) if probabilities else 0
        if max_prob >= self.critical_threshold:
            alert_level = "critical"
        elif max_prob >= self.alert_threshold:
            alert_level = "warning"
        else:
            alert_level = "none"

        return FailurePrediction(
            probabilities=probabilities,
            uncertainty=uncertainty,
            alert_level=alert_level,
        )
