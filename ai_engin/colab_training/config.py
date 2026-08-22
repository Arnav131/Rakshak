"""
Rakshak AI Engine — Central Configuration
==========================================
All hyperparameters, paths, model configs, and training constants
in one place. Modify this file to tune the entire training pipeline.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Tuple


# ═══════════════════════════════════════════════════════════════════
# PATH CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

# When running on Google Colab, the dataset ZIP is expected to be
# uploaded to Google Drive. Update DRIVE_MOUNT and DATASET_ZIP_PATH
# accordingly after mounting Drive.
DRIVE_MOUNT = "/content/drive/MyDrive"
PROJECT_DIR = os.path.join(DRIVE_MOUNT, "ai_engin")
DATASET_ZIP_PATH = os.path.join(PROJECT_DIR, "rakshak_massive_dataset.zip")
COLAB_WORK_DIR = "/content/rakshak_training"
EXTRACTED_DATA_DIR = os.path.join(COLAB_WORK_DIR, "data_parquet")
CHECKPOINT_DIR = os.path.join(COLAB_WORK_DIR, "checkpoints")
EXPORT_DIR = os.path.join(PROJECT_DIR, "trained_models")
LOG_DIR = os.path.join(COLAB_WORK_DIR, "logs")

# ═══════════════════════════════════════════════════════════════════
# DATASET CONSTANTS
# ═══════════════════════════════════════════════════════════════════

RAW_SENSOR_COLUMNS = ["ambient_temp", "humidity", "vibration_rms", "gauge_width"]
TIMESTAMP_COL = "timestamp"
SCENARIO_COL = "scenario_id"
LABEL_COL = "is_anomaly"

NUM_RAW_FEATURES = len(RAW_SENSOR_COLUMNS)  # 4

# 50 scenario types across 5 regions
REGIONS = ["NP", "CG", "DP", "HIM", "TD"]
SEASONS = ["SUM", "MON", "WIN", "SPR"]

# Fault type extraction from scenario_id (e.g., "DP_SUM_BUCKLEPRECUR_045" → "buckle_precursor")
FAULT_TYPE_MAP = {
    "NORMAL": "normal",
    "THERMALBUCKLE": "thermal_buckle",
    "BUCKLE": "thermal_buckle",
    "BUCKLEPRECUR": "buckle_precursor",
    "DENSEFOG": "dense_fog",
    "MODERATE": "moderate_degradation",
    "GAUGEWIDEN": "gauge_widening",
    "RAILJOINT": "rail_joint_defect",
    "BALLASTWASH": "ballast_washout",
    "SEVERHEAT": "severe_heat",
    "SANDINGRESS": "sand_ingress",
    "DIURNAL": "diurnal_stress",
    "FLASHFLOOD": "flash_flood",
    "RAILCREEP": "rail_creep",
    "WASHOUT": "track_washout",
    "HEAVYRAIN": "heavy_rain_damage",
    "SALINECORR": "saline_corrosion",
    "HIGHHUMID": "high_humidity_corrosion",
    "SUBGRADE": "subgrade_failure",
    "EMBANKSLIP": "embankment_slip",
    "COASTALWIND": "coastal_wind_damage",
    "RAILFRACTURE": "rail_fracture",
    "SNOWICE": "snow_ice_damage",
    "FROSTCRACK": "frost_crack",
    "SUBZERO": "subzero_damage",
    "ROCKFALL": "rockfall_damage",
    "THAW": "freeze_thaw_damage",
    "ROCKVIB": "rock_vibration",
    "BALLASTSOFT": "ballast_softening",
    "EMBANKSETTLE": "embankment_settlement",
    "TIEPLATE": "tie_plate_failure",
    "JUNCTIONSTRESS": "junction_stress",
}

# Unique fault classes for classification (excluding 'normal')
FAULT_CLASSES = sorted(set(FAULT_TYPE_MAP.values()))
NUM_FAULT_CLASSES = len(FAULT_CLASSES)


# ═══════════════════════════════════════════════════════════════════
# FEATURE ENGINEERING CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

@dataclass
class FeatureConfig:
    """Controls the feature engineering pipeline."""

    # Rolling window sizes for statistical features
    rolling_windows: List[int] = field(default_factory=lambda: [32, 64, 128])

    # Number of top Fourier frequency components to keep
    fourier_top_k: int = 5

    # Whether to compute cross-sensor interaction features
    compute_interactions: bool = True

    # Whether to compute rate-of-change (derivative) features
    compute_derivatives: bool = True

    # Whether to extract temporal features from timestamp
    compute_temporal: bool = True

    @property
    def num_engineered_features(self) -> int:
        """Calculate total number of features after engineering."""
        n = NUM_RAW_FEATURES  # 4 raw

        # Rolling stats: mean, std, min, max per window per feature
        n += NUM_RAW_FEATURES * len(self.rolling_windows) * 4

        # Derivatives (rate of change) per raw feature
        if self.compute_derivatives:
            n += NUM_RAW_FEATURES

        # Cross-sensor interactions (pairwise products): C(4,2) = 6
        if self.compute_interactions:
            n += 6

        # Temporal features: hour_sin, hour_cos, dow_sin, dow_cos, is_night
        if self.compute_temporal:
            n += 5

        # Fourier: top_k components for vibration_rms
        n += self.fourier_top_k * 2  # amplitude + phase

        return n


FEATURE_CONFIG = FeatureConfig()


# ═══════════════════════════════════════════════════════════════════
# DATA PIPELINE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

@dataclass
class DataConfig:
    """Controls data loading, splitting, and batching."""

    # Sliding window length for sequence models
    window_size: int = 64

    # Stride between windows (< window_size for overlap)
    window_stride: int = 32

    # Train / Validation / Test split ratios (by scenario, not by row)
    train_ratio: float = 0.70
    val_ratio: float = 0.15
    test_ratio: float = 0.15

    # Number of parquet files to load per batch during data prep
    # (keeps memory usage under ~4GB on Colab Free)
    files_per_chunk: int = 10

    # Max rows to sample per file for initial training
    # Set to None to use all rows (250K per file)
    max_rows_per_file: int = 50000

    # Weighted sampling to balance normal vs anomaly
    balance_classes: bool = True

    # Random seed for reproducibility
    seed: int = 42


DATA_CONFIG = DataConfig()


# ═══════════════════════════════════════════════════════════════════
# MODEL 1 — VAE ANOMALY DETECTOR
# ═══════════════════════════════════════════════════════════════════

@dataclass
class VAEConfig:
    """Variational Autoencoder for Tier-3 anomaly detection."""

    # Input dimensions
    input_channels: int = NUM_RAW_FEATURES  # 4
    sequence_length: int = 64               # window_size

    # Encoder architecture
    encoder_channels: List[int] = field(default_factory=lambda: [32, 64, 128])
    encoder_kernel_sizes: List[int] = field(default_factory=lambda: [7, 5, 3])

    # Latent space
    latent_dim: int = 32

    # Decoder mirrors encoder (reversed)

    # Training
    learning_rate: float = 1e-3
    weight_decay: float = 1e-5
    batch_size: int = 256
    max_epochs: int = 100
    early_stopping_patience: int = 10

    # Loss weighting
    kl_weight: float = 0.001          # β-VAE: low β for reconstruction focus
    kl_anneal_epochs: int = 20        # Linearly anneal KL weight over first N epochs

    # Anomaly threshold (calibrated on validation set)
    anomaly_percentile: float = 95.0  # Reconstruction error above this = anomaly


VAE_CONFIG = VAEConfig()


# ═══════════════════════════════════════════════════════════════════
# MODEL 2 — FAILURE PREDICTION (TCN + Transformer + BiLSTM)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class FailurePredictorConfig:
    """Hierarchical temporal model for failure prediction."""

    # Input
    num_features: int = FEATURE_CONFIG.num_engineered_features
    sequence_length: int = 64

    # TCN Backbone
    tcn_channels: List[int] = field(default_factory=lambda: [64, 64, 128, 128, 256])
    tcn_kernel_size: int = 3
    tcn_dilations: List[int] = field(default_factory=lambda: [1, 2, 4, 8, 16])
    tcn_dropout: float = 0.2

    # Transformer Fusion
    transformer_d_model: int = 256
    transformer_nhead: int = 8
    transformer_num_layers: int = 6
    transformer_dim_feedforward: int = 512
    transformer_dropout: float = 0.1

    # BiLSTM
    lstm_hidden_size: int = 256
    lstm_num_layers: int = 2
    lstm_dropout: float = 0.3

    # Multi-task prediction heads
    prediction_horizons: List[str] = field(default_factory=lambda: ["1h", "6h", "24h"])
    head_hidden_dims: List[int] = field(default_factory=lambda: [128, 64])
    head_dropout: float = 0.3

    # Monte Carlo Dropout for uncertainty
    mc_dropout_passes: int = 50

    # Training
    learning_rate: float = 5e-4
    weight_decay: float = 1e-4
    batch_size: int = 128
    max_epochs: int = 150
    early_stopping_patience: int = 15

    # Label generation: classify each window based on distance to nearest
    # anomaly transition in the future
    horizon_thresholds: Dict[str, int] = field(default_factory=lambda: {
        "1h": 720,     # 1 hour = 720 steps at 5-second intervals
        "6h": 4320,    # 6 hours
        "24h": 17280,  # 24 hours
    })


FAILURE_CONFIG = FailurePredictorConfig()


# ═══════════════════════════════════════════════════════════════════
# MODEL 3 — FAULT CLASSIFIER (ResNet-1D)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class FaultClassifierConfig:
    """ResNet-style 1D CNN for multi-class fault classification."""

    # Input
    num_features: int = FEATURE_CONFIG.num_engineered_features + 1  # +1 for anomaly_score
    sequence_length: int = 64

    # Architecture
    initial_channels: int = 64
    block_channels: List[int] = field(default_factory=lambda: [64, 128, 256, 512])
    blocks_per_stage: int = 2

    # Classification head
    num_classes: int = NUM_FAULT_CLASSES
    head_dropout: float = 0.4

    # Training
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    batch_size: int = 256
    max_epochs: int = 120
    early_stopping_patience: int = 12

    # Class weighting (computed from data distribution)
    use_class_weights: bool = True

    # Label smoothing
    label_smoothing: float = 0.1


FAULT_CONFIG = FaultClassifierConfig()


# ═══════════════════════════════════════════════════════════════════
# MODEL 4 — ISOLATION FOREST + GBM META-CLASSIFIER
# ═══════════════════════════════════════════════════════════════════

@dataclass
class IsolationForestConfig:
    """Tier-2 Isolation Forest for multivariate anomaly detection."""

    n_estimators: int = 200
    max_samples: int = 1024
    contamination: float = 0.1
    max_features: float = 1.0
    random_state: int = 42


@dataclass
class MetaClassifierConfig:
    """GBM meta-classifier combining all anomaly detection tiers."""

    # LightGBM parameters
    n_estimators: int = 500
    max_depth: int = 6
    learning_rate: float = 0.05
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    min_child_samples: int = 50
    reg_alpha: float = 0.1
    reg_lambda: float = 1.0
    random_state: int = 42

    # Meta features: tier1_zscore, tier1_iqr, tier2_iforest, tier3_vae_recon,
    #                raw_features (4), rolling_stats (subset)
    # Total meta features computed at runtime

    # Calibration
    calibrate: bool = True  # Apply Platt scaling for probability calibration


IFOREST_CONFIG = IsolationForestConfig()
META_CONFIG = MetaClassifierConfig()


# ═══════════════════════════════════════════════════════════════════
# TRAINING CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TrainingConfig:
    """Global training parameters."""

    # Mixed precision training (FP16) — huge speedup on T4/V100
    use_mixed_precision: bool = True

    # Gradient accumulation steps (simulates larger batch)
    gradient_accumulation_steps: int = 4

    # Gradient clipping
    max_grad_norm: float = 1.0

    # Learning rate scheduler
    scheduler: str = "cosine_annealing_warm_restarts"
    scheduler_T_0: int = 10
    scheduler_T_mult: int = 2
    warmup_epochs: int = 5

    # Logging
    log_every_n_steps: int = 100
    val_every_n_epochs: int = 1

    # Checkpointing
    save_top_k: int = 3

    # Reproducibility
    seed: int = 42

    # Device
    device: str = "cuda"  # Colab default


TRAINING_CONFIG = TrainingConfig()


# ═══════════════════════════════════════════════════════════════════
# INFERENCE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

@dataclass
class InferenceConfig:
    """Parameters for production inference pipeline."""

    # Anomaly detection thresholds
    tier1_zscore_threshold: float = 3.0
    tier1_iqr_multiplier: float = 1.5

    # Final anomaly decision threshold
    anomaly_threshold: float = 0.5

    # Failure prediction alert thresholds
    failure_alert_threshold: float = 0.7      # P(failure) > this → alert
    failure_critical_threshold: float = 0.9   # P(failure) > this → critical

    # Inference batch size (for bulk processing)
    batch_size: int = 512

    # Model file names
    vae_model_file: str = "vae_anomaly_detector.pt"
    vae_scaler_file: str = "vae_scaler.joblib"
    failure_model_file: str = "failure_predictor.pt"
    failure_scaler_file: str = "failure_scaler.joblib"
    classifier_model_file: str = "fault_classifier.pt"
    classifier_scaler_file: str = "classifier_scaler.joblib"
    iforest_model_file: str = "isolation_forest.joblib"
    meta_model_file: str = "meta_classifier.joblib"
    meta_scaler_file: str = "meta_scaler.joblib"
    config_file: str = "model_config.json"


INFERENCE_CONFIG = InferenceConfig()
