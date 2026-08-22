"""
Rakshak AI Engine — Preprocessing Pipeline
=============================================
Normalization, windowing, label generation, and train/val/test
splitting for all model types.
"""

import numpy as np
import pandas as pd
import joblib
import os
import logging
from typing import List, Optional, Tuple, Dict

from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.utils.class_weight import compute_class_weight

from config import (
    RAW_SENSOR_COLUMNS,
    LABEL_COL,
    TIMESTAMP_COL,
    SCENARIO_COL,
    DATA_CONFIG,
    FEATURE_CONFIG,
    FAILURE_CONFIG,
    FAULT_CLASSES,
    CHECKPOINT_DIR,
)
from data.feature_engineer import get_feature_columns

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# NORMALIZATION
# ═══════════════════════════════════════════════════════════════════

class FeatureNormalizer:
    """
    Fits and applies StandardScaler to feature columns.
    Saves/loads scaler state for inference consistency.
    """

    def __init__(self):
        self.scaler = StandardScaler()
        self.feature_columns: List[str] = []
        self.is_fitted = False

    def fit(self, df: pd.DataFrame, feature_columns: List[str]) -> "FeatureNormalizer":
        """Fit the scaler on training data."""
        self.feature_columns = feature_columns
        self.scaler.fit(df[feature_columns].values)
        self.is_fitted = True
        logger.info(f"Fitted normalizer on {len(feature_columns)} features, "
                     f"{len(df)} samples")
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply normalization to a DataFrame."""
        assert self.is_fitted, "Normalizer must be fitted before transform"
        result = df.copy()
        result[self.feature_columns] = self.scaler.transform(
            df[self.feature_columns].values
        )
        return result

    def fit_transform(self, df: pd.DataFrame, feature_columns: List[str]) -> pd.DataFrame:
        """Fit and transform in one step."""
        self.fit(df, feature_columns)
        return self.transform(df)

    def save(self, path: str):
        """Save scaler and column info to disk."""
        joblib.dump({
            "scaler": self.scaler,
            "feature_columns": self.feature_columns,
        }, path)
        logger.info(f"Saved normalizer to {path}")

    def load(self, path: str) -> "FeatureNormalizer":
        """Load scaler and column info from disk."""
        state = joblib.load(path)
        self.scaler = state["scaler"]
        self.feature_columns = state["feature_columns"]
        self.is_fitted = True
        logger.info(f"Loaded normalizer from {path}")
        return self


# ═══════════════════════════════════════════════════════════════════
# WINDOWING
# ═══════════════════════════════════════════════════════════════════

def create_sliding_windows(
    data: np.ndarray,
    window_size: int = DATA_CONFIG.window_size,
    stride: int = DATA_CONFIG.window_stride,
) -> np.ndarray:
    """
    Create sliding windows from a 2D array using stride tricks.

    Args:
        data: Shape (T, F) — time steps × features
        window_size: Length of each window
        stride: Step size between windows

    Returns:
        Shape (N, W, F) — num_windows × window_size × features
    """
    T, F = data.shape
    if T < window_size:
        return np.empty((0, window_size, F), dtype=data.dtype)

    num_windows = (T - window_size) // stride + 1
    windows = np.zeros((num_windows, window_size, F), dtype=data.dtype)

    for i in range(num_windows):
        start = i * stride
        windows[i] = data[start:start + window_size]

    return windows


def create_windows_with_labels(
    features: np.ndarray,
    labels: np.ndarray,
    window_size: int = DATA_CONFIG.window_size,
    stride: int = DATA_CONFIG.window_stride,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Create sliding windows and corresponding labels.

    Label for each window is the label of the LAST timestep
    (for causal predictions — we predict the state at the end of the window).

    Args:
        features: Shape (T, F)
        labels: Shape (T,)

    Returns:
        (windows, window_labels): shapes (N, W, F) and (N,)
    """
    windows = create_sliding_windows(features, window_size, stride)
    N = windows.shape[0]

    window_labels = np.zeros(N, dtype=labels.dtype)
    for i in range(N):
        end_idx = i * stride + window_size - 1
        window_labels[i] = labels[end_idx]

    return windows, window_labels


# ═══════════════════════════════════════════════════════════════════
# FAILURE PREDICTION LABEL GENERATION
# ═══════════════════════════════════════════════════════════════════

def generate_failure_labels(
    anomaly_series: np.ndarray,
    horizons: Dict[str, int] = None,
) -> Dict[str, np.ndarray]:
    """
    Generate multi-horizon failure prediction labels.

    For each timestep t, the label for horizon h is:
        1 if there exists an anomaly at any time in [t+1, t+h]
        0 otherwise

    This creates a "will a failure occur within the next h steps?" target.

    Args:
        anomaly_series: Binary array (T,) — 1 = anomaly, 0 = normal
        horizons: Dict mapping horizon name to number of steps

    Returns:
        Dict mapping horizon name to binary label array (T,)
    """
    if horizons is None:
        horizons = FAILURE_CONFIG.horizon_thresholds

    T = len(anomaly_series)
    labels = {}

    for name, h in horizons.items():
        horizon_labels = np.zeros(T, dtype=np.float32)

        # Use cumulative sum trick for efficiency
        # For each position, check if any anomaly exists in [t+1, t+h]
        cum_anomaly = np.cumsum(anomaly_series)

        for t in range(T):
            end = min(t + h, T - 1)
            future_anomalies = cum_anomaly[end] - cum_anomaly[t]
            horizon_labels[t] = 1.0 if future_anomalies > 0 else 0.0

        labels[name] = horizon_labels

    return labels


def generate_failure_windows(
    features: np.ndarray,
    anomaly_labels: np.ndarray,
    window_size: int = DATA_CONFIG.window_size,
    stride: int = DATA_CONFIG.window_stride,
    horizons: Dict[str, int] = None,
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """
    Create windowed features and multi-horizon failure labels.

    Returns:
        (windows, horizon_labels): windows shape (N, W, F),
        horizon_labels is dict of (N,) arrays
    """
    windows = create_sliding_windows(features, window_size, stride)
    N = windows.shape[0]

    # Generate full-length failure labels first
    full_labels = generate_failure_labels(anomaly_labels, horizons)

    # Extract label for each window (label of last timestep)
    horizon_window_labels = {}
    for name, full_label in full_labels.items():
        window_labels = np.zeros(N, dtype=np.float32)
        for i in range(N):
            end_idx = i * stride + window_size - 1
            if end_idx < len(full_label):
                window_labels[i] = full_label[end_idx]
        horizon_window_labels[name] = window_labels

    return windows, horizon_window_labels


# ═══════════════════════════════════════════════════════════════════
# FAULT CLASSIFICATION LABEL ENCODING
# ═══════════════════════════════════════════════════════════════════

class FaultLabelEncoder:
    """
    Encodes fault type strings to integer labels.
    Uses the canonical FAULT_CLASSES list for consistent ordering.
    """

    def __init__(self):
        self.classes = sorted(FAULT_CLASSES)
        self.class_to_idx = {c: i for i, c in enumerate(self.classes)}
        self.idx_to_class = {i: c for c, i in self.class_to_idx.items()}
        self.num_classes = len(self.classes)

    def encode(self, fault_types: np.ndarray) -> np.ndarray:
        """Convert fault type strings to integer labels."""
        return np.array([
            self.class_to_idx.get(ft, self.class_to_idx.get("unknown", 0))
            for ft in fault_types
        ], dtype=np.int64)

    def decode(self, labels: np.ndarray) -> List[str]:
        """Convert integer labels back to fault type strings."""
        return [self.idx_to_class.get(int(l), "unknown") for l in labels]

    def save(self, path: str):
        """Save encoder state."""
        joblib.dump({
            "classes": self.classes,
            "class_to_idx": self.class_to_idx,
        }, path)

    def load(self, path: str) -> "FaultLabelEncoder":
        """Load encoder state."""
        state = joblib.load(path)
        self.classes = state["classes"]
        self.class_to_idx = state["class_to_idx"]
        self.idx_to_class = {i: c for c, i in self.class_to_idx.items()}
        self.num_classes = len(self.classes)
        return self


# ═══════════════════════════════════════════════════════════════════
# CLASS WEIGHTS FOR IMBALANCED DATA
# ═══════════════════════════════════════════════════════════════════

def compute_anomaly_class_weights(labels: np.ndarray) -> Dict[int, float]:
    """Compute class weights for binary anomaly detection."""
    unique = np.unique(labels)
    weights = compute_class_weight("balanced", classes=unique, y=labels)
    return {int(c): float(w) for c, w in zip(unique, weights)}


def compute_fault_class_weights(
    fault_labels: np.ndarray,
    num_classes: int,
) -> np.ndarray:
    """
    Compute class weights for multi-class fault classification.
    Returns a weight tensor suitable for CrossEntropyLoss.
    """
    unique = np.unique(fault_labels)
    weights = compute_class_weight("balanced", classes=unique, y=fault_labels)

    # Create full weight array (some classes may not appear in this split)
    full_weights = np.ones(num_classes, dtype=np.float32)
    for c, w in zip(unique, weights):
        full_weights[int(c)] = float(w)

    return full_weights


# ═══════════════════════════════════════════════════════════════════
# CHUNKED PREPROCESSING PIPELINE
# ═══════════════════════════════════════════════════════════════════

def preprocess_chunk_for_vae(
    df: pd.DataFrame,
    normalizer: Optional[FeatureNormalizer] = None,
    fit: bool = False,
) -> Tuple[np.ndarray, np.ndarray, Optional[FeatureNormalizer]]:
    """
    Preprocess a data chunk for the VAE model.

    VAE uses raw sensor features only (no engineered features).

    Returns:
        (windows, labels, normalizer)
    """
    feature_cols = RAW_SENSOR_COLUMNS

    if normalizer is None:
        normalizer = FeatureNormalizer()

    if fit:
        normalizer.fit(df, feature_cols)

    df_norm = normalizer.transform(df)
    features = df_norm[feature_cols].values.astype(np.float32)
    labels = df[LABEL_COL].values.astype(np.float32)

    windows, window_labels = create_windows_with_labels(features, labels)

    return windows, window_labels, normalizer


def preprocess_chunk_for_failure(
    df: pd.DataFrame,
    feature_columns: List[str],
    normalizer: Optional[FeatureNormalizer] = None,
    fit: bool = False,
) -> Tuple[np.ndarray, Dict[str, np.ndarray], Optional[FeatureNormalizer]]:
    """
    Preprocess a data chunk for the failure prediction model.

    Uses full engineered features and generates multi-horizon labels.

    Returns:
        (windows, horizon_labels, normalizer)
    """
    if normalizer is None:
        normalizer = FeatureNormalizer()

    if fit:
        normalizer.fit(df, feature_columns)

    df_norm = normalizer.transform(df)
    features = df_norm[feature_columns].values.astype(np.float32)
    anomaly_labels = df[LABEL_COL].values.astype(np.float32)

    windows, horizon_labels = generate_failure_windows(features, anomaly_labels)

    return windows, horizon_labels, normalizer


def preprocess_chunk_for_classifier(
    df: pd.DataFrame,
    feature_columns: List[str],
    fault_encoder: FaultLabelEncoder,
    normalizer: Optional[FeatureNormalizer] = None,
    fit: bool = False,
) -> Tuple[np.ndarray, np.ndarray, Optional[FeatureNormalizer]]:
    """
    Preprocess a data chunk for the fault classifier.

    Only processes anomalous samples (fault classification is only
    relevant when an anomaly has been detected).

    Returns:
        (windows, fault_labels, normalizer)
    """
    # Filter to anomalous samples only
    df_anomaly = df[df[LABEL_COL] == 1].copy()

    if len(df_anomaly) == 0:
        return (
            np.empty((0, DATA_CONFIG.window_size, len(feature_columns)), dtype=np.float32),
            np.empty((0,), dtype=np.int64),
            normalizer,
        )

    if normalizer is None:
        normalizer = FeatureNormalizer()

    if fit:
        normalizer.fit(df_anomaly, feature_columns)

    df_norm = normalizer.transform(df_anomaly)
    features = df_norm[feature_columns].values.astype(np.float32)
    fault_types = df_anomaly["fault_type"].values
    fault_labels = fault_encoder.encode(fault_types)

    windows, window_labels = create_windows_with_labels(features, fault_labels)

    return windows, window_labels, normalizer
