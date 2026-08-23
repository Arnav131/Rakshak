"""
Rakshak AI Engine — Feature Engineering Pipeline
==================================================
Transforms 4 raw sensor columns into a rich feature set for
deep learning models. All transformations are designed to be
applied in a streaming fashion (per-chunk).
"""

import numpy as np
import pandas as pd
from typing import List, Optional, Tuple

from config import (
    RAW_SENSOR_COLUMNS,
    TIMESTAMP_COL,
    FEATURE_CONFIG,
    NUM_RAW_FEATURES,
)


# ═══════════════════════════════════════════════════════════════════
# CORE FEATURE ENGINEERING
# ═══════════════════════════════════════════════════════════════════

def compute_rolling_features(
    df: pd.DataFrame,
    columns: List[str] = RAW_SENSOR_COLUMNS,
    windows: List[int] = None,
) -> pd.DataFrame:
    """
    Compute rolling window statistics for each sensor column.

    For each column and each window size, computes:
    - Rolling mean
    - Rolling std
    - Rolling min
    - Rolling max

    Args:
        df: Input DataFrame (must be sorted by timestamp within each group)
        columns: Sensor columns to compute features for
        windows: Window sizes (default from config)

    Returns:
        DataFrame with new rolling feature columns appended
    """
    if windows is None:
        windows = FEATURE_CONFIG.rolling_windows

    result = df.copy()

    for col in columns:
        for w in windows:
            prefix = f"{col}_roll{w}"
            rolling = result[col].rolling(window=w, min_periods=1)
            result[f"{prefix}_mean"] = rolling.mean()
            result[f"{prefix}_std"] = rolling.std().fillna(0)
            result[f"{prefix}_min"] = rolling.min()
            result[f"{prefix}_max"] = rolling.max()

    return result


def compute_derivatives(
    df: pd.DataFrame,
    columns: List[str] = RAW_SENSOR_COLUMNS,
) -> pd.DataFrame:
    """
    Compute first-order derivatives (rate of change) for each sensor.

    Uses simple differencing: dx[t] = x[t] - x[t-1]
    """
    result = df.copy()

    for col in columns:
        result[f"{col}_delta"] = result[col].diff().fillna(0)

    return result


def compute_interactions(
    df: pd.DataFrame,
    columns: List[str] = RAW_SENSOR_COLUMNS,
) -> pd.DataFrame:
    """
    Compute pairwise interaction features between sensor columns.

    For 4 sensors, this produces C(4,2) = 6 interaction features.
    Uses normalized products to avoid scale issues.
    """
    result = df.copy()

    for i in range(len(columns)):
        for j in range(i + 1, len(columns)):
            col_a, col_b = columns[i], columns[j]
            name = f"interact_{col_a}_{col_b}"

            # Standardized product (z-score of each, then multiply)
            a_std = (result[col_a] - result[col_a].mean()) / (result[col_a].std() + 1e-8)
            b_std = (result[col_b] - result[col_b].mean()) / (result[col_b].std() + 1e-8)
            result[name] = a_std * b_std

    return result


def compute_temporal_features(
    df: pd.DataFrame,
    timestamp_col: str = TIMESTAMP_COL,
) -> pd.DataFrame:
    """
    Extract cyclical temporal features from timestamp.

    Produces:
    - hour_sin, hour_cos (captures time-of-day cyclically)
    - dow_sin, dow_cos (captures day-of-week cyclically)
    - is_night (boolean: 1 if hour ∈ [22, 6))
    """
    result = df.copy()

    ts = pd.to_datetime(result[timestamp_col])
    hour = ts.dt.hour + ts.dt.minute / 60.0
    dow = ts.dt.dayofweek

    # Cyclical encoding (avoids discontinuity at midnight / Sunday)
    result["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    result["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
    result["dow_sin"] = np.sin(2 * np.pi * dow / 7.0)
    result["dow_cos"] = np.cos(2 * np.pi * dow / 7.0)
    result["is_night"] = ((hour >= 22) | (hour < 6)).astype(np.float32)

    return result


def compute_fourier_features(
    df: pd.DataFrame,
    column: str = "vibration_rms",
    top_k: int = None,
    window_size: int = 64,
) -> pd.DataFrame:
    """
    Extract top-K Fourier frequency components from vibration signal.

    Applies FFT over a sliding window and extracts the dominant
    frequency amplitudes and phases. Useful for detecting periodic
    mechanical faults.

    Args:
        df: Input DataFrame
        column: Column to apply FFT on
        top_k: Number of top frequency components to keep
        window_size: FFT window size

    Returns:
        DataFrame with fourier feature columns appended
    """
    if top_k is None:
        top_k = FEATURE_CONFIG.fourier_top_k

    result = df.copy()
    signal = result[column].values

    # Initialize feature columns with zeros
    for k in range(top_k):
        result[f"fft_amp_{k}"] = 0.0
        result[f"fft_phase_{k}"] = 0.0

    # Compute FFT for each position using rolling window
    n = len(signal)
    for i in range(window_size, n):
        window = signal[i - window_size:i]
        fft_vals = np.fft.rfft(window)
        magnitudes = np.abs(fft_vals[1:])  # Skip DC component
        phases = np.angle(fft_vals[1:])

        # Get indices of top-K frequencies
        if len(magnitudes) >= top_k:
            top_indices = np.argsort(magnitudes)[-top_k:]
            for rank, idx in enumerate(sorted(top_indices)):
                result.iloc[i, result.columns.get_loc(f"fft_amp_{rank}")] = magnitudes[idx]
                result.iloc[i, result.columns.get_loc(f"fft_phase_{rank}")] = phases[idx]

    return result


def compute_fourier_features_vectorized(
    df: pd.DataFrame,
    column: str = "vibration_rms",
    top_k: int = None,
    window_size: int = 64,
) -> pd.DataFrame:
    """
    Vectorized version of Fourier feature extraction.
    Much faster than the row-by-row version — uses stride tricks.
    """
    if top_k is None:
        top_k = FEATURE_CONFIG.fourier_top_k

    result = df.copy()
    signal = result[column].values.astype(np.float64)
    n = len(signal)

    # Pre-allocate arrays
    amp_features = np.zeros((n, top_k), dtype=np.float32)
    phase_features = np.zeros((n, top_k), dtype=np.float32)

    if n >= window_size:
        # Create sliding windows using stride tricks
        shape = (n - window_size + 1, window_size)
        strides = (signal.strides[0], signal.strides[0])
        windows = np.lib.stride_tricks.as_strided(signal, shape=shape, strides=strides)

        # Batch FFT on all windows
        fft_all = np.fft.rfft(windows, axis=1)
        mags = np.abs(fft_all[:, 1:])
        phases = np.angle(fft_all[:, 1:])

        # For each window, get top-K frequencies
        for i in range(len(windows)):
            if mags.shape[1] >= top_k:
                top_idx = np.argpartition(mags[i], -top_k)[-top_k:]
                top_idx = top_idx[np.argsort(mags[i][top_idx])]
                amp_features[i + window_size - 1] = mags[i][top_idx]
                phase_features[i + window_size - 1] = phases[i][top_idx]

    # Add to DataFrame
    for k in range(top_k):
        result[f"fft_amp_{k}"] = amp_features[:, k]
        result[f"fft_phase_{k}"] = phase_features[:, k]

    return result


# ═══════════════════════════════════════════════════════════════════
# FULL FEATURE ENGINEERING PIPELINE
# ═══════════════════════════════════════════════════════════════════

def engineer_features(
    df: pd.DataFrame,
    config: object = FEATURE_CONFIG,
    use_vectorized_fft: bool = True,
) -> pd.DataFrame:
    """
    Apply the full feature engineering pipeline to a DataFrame.

    This is the main entry point. Call this on each data chunk.

    Args:
        df: Raw DataFrame with columns: timestamp, sensor columns, etc.
        config: FeatureConfig instance
        use_vectorized_fft: Use fast vectorized FFT (recommended)

    Returns:
        DataFrame with all engineered features added
    """
    result = df.copy()

    # 1. Rolling statistics
    result = compute_rolling_features(result, windows=config.rolling_windows)

    # 2. Derivatives (rate of change)
    if config.compute_derivatives:
        result = compute_derivatives(result)

    # 3. Cross-sensor interactions
    if config.compute_interactions:
        result = compute_interactions(result)

    # 4. Temporal features
    if config.compute_temporal:
        result = compute_temporal_features(result)

    # 5. Fourier features (from vibration signal)
    if use_vectorized_fft:
        result = compute_fourier_features_vectorized(
            result,
            column="vibration_rms",
            top_k=config.fourier_top_k,
        )
    else:
        result = compute_fourier_features(
            result,
            column="vibration_rms",
            top_k=config.fourier_top_k,
        )

    return result


def get_feature_columns(config: object = FEATURE_CONFIG) -> List[str]:
    """
    Get the ordered list of all feature column names after engineering.
    Useful for ensuring consistent column ordering across train/inference.
    """
    columns = list(RAW_SENSOR_COLUMNS)

    # Rolling features
    for col in RAW_SENSOR_COLUMNS:
        for w in config.rolling_windows:
            prefix = f"{col}_roll{w}"
            columns.extend([
                f"{prefix}_mean",
                f"{prefix}_std",
                f"{prefix}_min",
                f"{prefix}_max",
            ])

    # Derivatives
    if config.compute_derivatives:
        for col in RAW_SENSOR_COLUMNS:
            columns.append(f"{col}_delta")

    # Interactions
    if config.compute_interactions:
        for i in range(len(RAW_SENSOR_COLUMNS)):
            for j in range(i + 1, len(RAW_SENSOR_COLUMNS)):
                columns.append(f"interact_{RAW_SENSOR_COLUMNS[i]}_{RAW_SENSOR_COLUMNS[j]}")

    # Temporal
    if config.compute_temporal:
        columns.extend(["hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_night"])

    # Fourier
    for k in range(config.fourier_top_k):
        columns.extend([f"fft_amp_{k}", f"fft_phase_{k}"])

    return columns
