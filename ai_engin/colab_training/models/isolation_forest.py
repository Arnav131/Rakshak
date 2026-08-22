"""
Rakshak AI Engine — Isolation Forest Wrapper
===============================================
Tier-2 multivariate anomaly detection using Isolation Forest.
200 trees, as specified in the agents_README.
"""

import numpy as np
import joblib
import logging
from typing import Optional, Tuple

from sklearn.ensemble import IsolationForest as SklearnIsolationForest
from sklearn.preprocessing import StandardScaler

from config import IFOREST_CONFIG

logger = logging.getLogger(__name__)


class RakshakIsolationForest:
    """
    Isolation Forest wrapper for Tier-2 anomaly detection.

    From agents_README:
        Tier 2: Isolation Forest (200 trees) (< 50 ms) → multivariate

    This wrapper:
    - Handles training on chunked data (partial_fit via retraining)
    - Produces calibrated anomaly scores in [0, 1]
    - Includes scaler for consistent normalization
    """

    def __init__(self, config=IFOREST_CONFIG):
        self.config = config
        self.model = SklearnIsolationForest(
            n_estimators=config.n_estimators,
            max_samples=config.max_samples,
            contamination=config.contamination,
            max_features=config.max_features,
            random_state=config.random_state,
            n_jobs=-1,
        )
        self.scaler = StandardScaler()
        self.is_fitted = False
        self._score_min = 0.0
        self._score_max = 1.0

    def fit(
        self,
        X: np.ndarray,
        subsample: Optional[int] = None,
    ) -> "RakshakIsolationForest":
        """
        Fit the Isolation Forest on training data.

        Args:
            X: Shape (N, F) — feature matrix (use window-level features,
               e.g., mean/std of each sensor over a window)
            subsample: Max training samples (for memory management)

        Returns:
            self
        """
        if subsample and len(X) > subsample:
            rng = np.random.RandomState(self.config.random_state)
            indices = rng.choice(len(X), subsample, replace=False)
            X = X[indices]

        logger.info(f"Fitting IsolationForest on {X.shape[0]} samples, "
                     f"{X.shape[1]} features")

        # Normalize
        X_scaled = self.scaler.fit_transform(X)

        # Fit
        self.model.fit(X_scaled)

        # Calibrate score range on training data
        raw_scores = self.model.decision_function(X_scaled)
        self._score_min = float(raw_scores.min())
        self._score_max = float(raw_scores.max())

        self.is_fitted = True
        logger.info(f"IsolationForest fitted. Score range: "
                     f"[{self._score_min:.4f}, {self._score_max:.4f}]")

        return self

    def predict_scores(self, X: np.ndarray) -> np.ndarray:
        """
        Compute anomaly scores in [0, 1].

        Higher score = more anomalous.

        Args:
            X: Shape (N, F)

        Returns:
            scores: Shape (N,) in [0, 1]
        """
        assert self.is_fitted, "Model must be fitted first"

        X_scaled = self.scaler.transform(X)
        raw_scores = self.model.decision_function(X_scaled)

        # Isolation Forest decision_function: lower = more anomalous
        # Invert and normalize to [0, 1]
        normalized = 1.0 - (raw_scores - self._score_min) / (
            self._score_max - self._score_min + 1e-8
        )
        return np.clip(normalized, 0, 1).astype(np.float32)

    def predict(self, X: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        """Binary anomaly prediction."""
        scores = self.predict_scores(X)
        return (scores >= threshold).astype(np.int32)

    def save(self, path: str):
        """Save model to disk."""
        joblib.dump({
            "model": self.model,
            "scaler": self.scaler,
            "score_min": self._score_min,
            "score_max": self._score_max,
            "config": self.config,
        }, path)
        logger.info(f"Saved IsolationForest to {path}")

    def load(self, path: str) -> "RakshakIsolationForest":
        """Load model from disk."""
        state = joblib.load(path)
        self.model = state["model"]
        self.scaler = state["scaler"]
        self._score_min = state["score_min"]
        self._score_max = state["score_max"]
        self.config = state["config"]
        self.is_fitted = True
        logger.info(f"Loaded IsolationForest from {path}")
        return self


def extract_window_features(windows: np.ndarray) -> np.ndarray:
    """
    Extract summary features from windows for Isolation Forest.

    IsoForest works on flat feature vectors, not sequences.
    We compute statistical summaries of each window.

    Args:
        windows: Shape (N, W, F) — N windows of W timesteps × F features

    Returns:
        features: Shape (N, F*6) — mean, std, min, max, skew, kurtosis per feature
    """
    N, W, F = windows.shape

    means = np.mean(windows, axis=1)      # (N, F)
    stds = np.std(windows, axis=1)        # (N, F)
    mins = np.min(windows, axis=1)        # (N, F)
    maxs = np.max(windows, axis=1)        # (N, F)

    # Range
    ranges = maxs - mins  # (N, F)

    # Rate of change (last - first)
    deltas = windows[:, -1, :] - windows[:, 0, :]  # (N, F)

    features = np.concatenate([means, stds, mins, maxs, ranges, deltas], axis=1)
    return features.astype(np.float32)
