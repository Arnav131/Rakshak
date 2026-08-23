"""
Rakshak AI Engine — GBM Meta-Classifier
==========================================
Gradient Boosted Machine that combines scores from all three
anomaly detection tiers into a single calibrated probability.

From agents_README:
    Meta-classifier (GBM) combining all tier scores → C ∈ [0,1]
"""

import numpy as np
import joblib
import logging
from typing import Optional, Dict, Tuple

from sklearn.calibration import CalibratedClassifierCV
from config import META_CONFIG

logger = logging.getLogger(__name__)


class MetaClassifier:
    """
    GBM meta-classifier for the 3-tier anomaly detection pipeline.

    Combines:
    - Tier 1: Z-score + IQR (statistical, rule-based)
    - Tier 2: Isolation Forest score
    - Tier 3: VAE reconstruction error
    - Raw sensor features (for context)

    Into a single calibrated anomaly probability.

    Uses LightGBM for gradient boosting with optional Platt scaling
    for probability calibration.
    """

    def __init__(self, config=META_CONFIG):
        self.config = config
        self.model = None
        self.calibrated_model = None
        self.is_fitted = False
        self.feature_names = None
        self._use_lightgbm = True

    def _create_model(self):
        """Create the underlying GBM model."""
        try:
            import lightgbm as lgb
            self.model = lgb.LGBMClassifier(
                n_estimators=self.config.n_estimators,
                max_depth=self.config.max_depth,
                learning_rate=self.config.learning_rate,
                subsample=self.config.subsample,
                colsample_bytree=self.config.colsample_bytree,
                min_child_samples=self.config.min_child_samples,
                reg_alpha=self.config.reg_alpha,
                reg_lambda=self.config.reg_lambda,
                random_state=self.config.random_state,
                n_jobs=-1,
                verbose=-1,
            )
            self._use_lightgbm = True
        except ImportError:
            # Fallback to XGBoost
            from xgboost import XGBClassifier
            self.model = XGBClassifier(
                n_estimators=self.config.n_estimators,
                max_depth=self.config.max_depth,
                learning_rate=self.config.learning_rate,
                subsample=self.config.subsample,
                colsample_bytree=self.config.colsample_bytree,
                reg_alpha=self.config.reg_alpha,
                reg_lambda=self.config.reg_lambda,
                random_state=self.config.random_state,
                n_jobs=-1,
                use_label_encoder=False,
                eval_metric="logloss",
            )
            self._use_lightgbm = False

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[list] = None,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
    ) -> "MetaClassifier":
        """
        Fit the meta-classifier.

        Args:
            X: Meta-feature matrix (N, M) containing tier scores + raw features
            y: Binary labels (N,) — 1 = anomaly, 0 = normal
            feature_names: Names for each feature column
            X_val: Validation features for early stopping
            y_val: Validation labels

        Returns:
            self
        """
        self._create_model()
        self.feature_names = feature_names

        logger.info(f"Fitting meta-classifier on {X.shape[0]} samples, "
                     f"{X.shape[1]} features")

        fit_params = {}
        if X_val is not None and y_val is not None:
            if self._use_lightgbm:
                fit_params["eval_set"] = [(X_val, y_val)]
                fit_params["callbacks"] = [
                    __import__("lightgbm").early_stopping(50, verbose=True),
                    __import__("lightgbm").log_evaluation(100),
                ]
            else:
                fit_params["eval_set"] = [(X_val, y_val)]
                fit_params["early_stopping_rounds"] = 50
                fit_params["verbose"] = 100

        self.model.fit(X, y, **fit_params)

        # Calibrate probabilities using Platt scaling
        if self.config.calibrate:
            logger.info("Calibrating probabilities with Platt scaling...")
            cal_X = X_val if X_val is not None else X
            cal_y = y_val if y_val is not None else y

            self.calibrated_model = CalibratedClassifierCV(
                self.model,
                method="sigmoid",
                cv="prefit",
            )
            self.calibrated_model.fit(cal_X, cal_y)

        self.is_fitted = True
        logger.info("Meta-classifier training complete")

        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Get calibrated anomaly probability.

        Args:
            X: Meta-features (N, M)

        Returns:
            probabilities: (N,) in [0, 1]
        """
        assert self.is_fitted, "Model must be fitted first"

        if self.calibrated_model is not None:
            proba = self.calibrated_model.predict_proba(X)[:, 1]
        else:
            proba = self.model.predict_proba(X)[:, 1]

        return proba.astype(np.float32)

    def predict(self, X: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        """Binary prediction."""
        proba = self.predict_proba(X)
        return (proba >= threshold).astype(np.int32)

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores."""
        if not self.is_fitted:
            return {}

        importances = self.model.feature_importances_
        names = self.feature_names or [f"feature_{i}" for i in range(len(importances))]

        return dict(sorted(
            zip(names, importances),
            key=lambda x: x[1],
            reverse=True,
        ))

    def save(self, path: str):
        """Save meta-classifier to disk."""
        joblib.dump({
            "model": self.model,
            "calibrated_model": self.calibrated_model,
            "feature_names": self.feature_names,
            "config": self.config,
            "use_lightgbm": self._use_lightgbm,
        }, path)
        logger.info(f"Saved meta-classifier to {path}")

    def load(self, path: str) -> "MetaClassifier":
        """Load meta-classifier from disk."""
        state = joblib.load(path)
        self.model = state["model"]
        self.calibrated_model = state["calibrated_model"]
        self.feature_names = state["feature_names"]
        self.config = state["config"]
        self._use_lightgbm = state["use_lightgbm"]
        self.is_fitted = True
        logger.info(f"Loaded meta-classifier from {path}")
        return self


# ═══════════════════════════════════════════════════════════════════
# TIER 1: STATISTICAL ANOMALY DETECTION (RULE-BASED, NO TRAINING)
# ═══════════════════════════════════════════════════════════════════

class StatisticalAnomalyDetector:
    """
    Tier-1 statistical anomaly detection.

    From agents_README:
        Tier 1: 3-sigma Z-score + IQR (< 5 ms) → fast screen

    This is a pure rule-based detector — no ML training required.
    It serves as the first fast screen before the heavier models.
    """

    def __init__(
        self,
        zscore_threshold: float = 3.0,
        iqr_multiplier: float = 1.5,
    ):
        self.zscore_threshold = zscore_threshold
        self.iqr_multiplier = iqr_multiplier
        self.means = None
        self.stds = None
        self.q1 = None
        self.q3 = None
        self.iqr = None
        self.is_fitted = False

    def fit(self, X: np.ndarray) -> "StatisticalAnomalyDetector":
        """
        Compute statistics from normal training data.

        Args:
            X: (N, F) — feature matrix of NORMAL samples
        """
        self.means = np.mean(X, axis=0)
        self.stds = np.std(X, axis=0) + 1e-8
        self.q1 = np.percentile(X, 25, axis=0)
        self.q3 = np.percentile(X, 75, axis=0)
        self.iqr = self.q3 - self.q1
        self.is_fitted = True
        return self

    def compute_zscore(self, X: np.ndarray) -> np.ndarray:
        """Compute max absolute Z-score across features."""
        zscores = np.abs((X - self.means) / self.stds)
        return np.max(zscores, axis=1)  # Max z-score per sample

    def compute_iqr_score(self, X: np.ndarray) -> np.ndarray:
        """Compute IQR-based outlier score."""
        lower = self.q1 - self.iqr_multiplier * self.iqr
        upper = self.q3 + self.iqr_multiplier * self.iqr

        below = np.maximum(0, lower - X) / (self.iqr + 1e-8)
        above = np.maximum(0, X - upper) / (self.iqr + 1e-8)

        return np.max(below + above, axis=1)

    def predict_scores(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Returns:
            (zscore, iqr_score) — both shape (N,)
        """
        assert self.is_fitted
        return self.compute_zscore(X), self.compute_iqr_score(X)

    def save(self, path: str):
        joblib.dump({
            "means": self.means,
            "stds": self.stds,
            "q1": self.q1,
            "q3": self.q3,
            "iqr": self.iqr,
            "zscore_threshold": self.zscore_threshold,
            "iqr_multiplier": self.iqr_multiplier,
        }, path)

    def load(self, path: str) -> "StatisticalAnomalyDetector":
        state = joblib.load(path)
        self.means = state["means"]
        self.stds = state["stds"]
        self.q1 = state["q1"]
        self.q3 = state["q3"]
        self.iqr = state["iqr"]
        self.zscore_threshold = state["zscore_threshold"]
        self.iqr_multiplier = state["iqr_multiplier"]
        self.is_fitted = True
        return self


def build_meta_features(
    tier1_zscore: np.ndarray,
    tier1_iqr: np.ndarray,
    tier2_iforest: np.ndarray,
    tier3_vae_recon: np.ndarray,
    raw_features: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Combine all tier scores into a meta-feature matrix.

    Args:
        tier1_zscore: (N,) Z-score from Tier 1
        tier1_iqr: (N,) IQR score from Tier 1
        tier2_iforest: (N,) Isolation Forest score from Tier 2
        tier3_vae_recon: (N,) VAE reconstruction error from Tier 3
        raw_features: Optional (N, F) raw sensor features for context

    Returns:
        meta_features: (N, M) combined feature matrix
    """
    features = [
        tier1_zscore.reshape(-1, 1),
        tier1_iqr.reshape(-1, 1),
        tier2_iforest.reshape(-1, 1),
        tier3_vae_recon.reshape(-1, 1),
    ]

    if raw_features is not None:
        features.append(raw_features)

    return np.concatenate(features, axis=1).astype(np.float32)
