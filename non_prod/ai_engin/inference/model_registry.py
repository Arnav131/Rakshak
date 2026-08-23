"""
Rakshak AI Engine — Model Registry
=====================================
Loads and manages serialized models for inference.
Handles versioning, lazy loading, and device management.
"""

import os
import json
import logging
import torch
import joblib
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ModelRegistry:
    """
    Central registry for all trained Rakshak models.

    Lazy-loads models on first access to minimize startup time.
    Handles CPU/GPU device placement automatically.
    """

    def __init__(
        self,
        model_dir: str,
        device: Optional[str] = None,
    ):
        """
        Args:
            model_dir: Directory containing exported model files
            device: 'cuda' or 'cpu'. Auto-detects if None.
        """
        self.model_dir = model_dir
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        # Loaded model cache
        self._models: Dict[str, Any] = {}
        self._config: Optional[Dict] = None

        # Verify directory exists
        if not os.path.isdir(model_dir):
            raise FileNotFoundError(
                f"Model directory not found: {model_dir}. "
                f"Please train models first and place exported files here."
            )

        logger.info(f"ModelRegistry initialized: {model_dir} (device={self.device})")

    @property
    def config(self) -> Dict:
        """Load and cache the model configuration JSON."""
        if self._config is None:
            config_path = os.path.join(self.model_dir, "model_config.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    self._config = json.load(f)
            else:
                self._config = {}
                logger.warning("model_config.json not found")
        return self._config

    def _load_pytorch_model(self, filename: str, model_class, config_override=None):
        """Load a PyTorch model from a .pt file."""
        path = os.path.join(self.model_dir, filename)
        if not os.path.exists(path):
            logger.warning(f"Model file not found: {path}")
            return None

        checkpoint = torch.load(path, map_location=self.device)
        saved_config = checkpoint.get("config", {})

        if config_override:
            model = model_class(config_override)
        else:
            model = model_class()

        model.load_state_dict(checkpoint["model_state_dict"])
        model = model.to(self.device).eval()

        logger.info(f"Loaded {filename} (epoch={checkpoint.get('epoch', '?')})")
        return model

    def _load_joblib_model(self, filename: str):
        """Load a joblib-serialized model."""
        path = os.path.join(self.model_dir, filename)
        if not os.path.exists(path):
            logger.warning(f"Model file not found: {path}")
            return None

        model = joblib.load(path)
        logger.info(f"Loaded {filename}")
        return model

    def get_vae(self):
        """Get the VAE anomaly detector model."""
        if "vae" not in self._models:
            from ai_engin.colab_training.models.vae_anomaly import VAEAnomalyDetector, VAE_CONFIG

            # Try to reconstruct config from saved metadata
            model_configs = self.config.get("configs", {}).get("vae", {})

            self._models["vae"] = self._load_pytorch_model(
                "vae_anomaly_detector.pt",
                lambda cfg=None: VAEAnomalyDetector(VAE_CONFIG),
            )
        return self._models["vae"]

    def get_failure_predictor(self):
        """Get the failure prediction model."""
        if "failure" not in self._models:
            from ai_engin.colab_training.models.failure_predictor import (
                FailurePredictionModel, FAILURE_CONFIG,
            )
            self._models["failure"] = self._load_pytorch_model(
                "failure_predictor.pt",
                lambda cfg=None: FailurePredictionModel(FAILURE_CONFIG),
            )
        return self._models["failure"]

    def get_fault_classifier(self):
        """Get the fault classification model."""
        if "classifier" not in self._models:
            from ai_engin.colab_training.models.fault_classifier import (
                FaultClassifier, FAULT_CONFIG,
            )
            self._models["classifier"] = self._load_pytorch_model(
                "fault_classifier.pt",
                lambda cfg=None: FaultClassifier(FAULT_CONFIG),
            )
        return self._models["classifier"]

    def get_isolation_forest(self):
        """Get the Isolation Forest model."""
        if "iforest" not in self._models:
            obj = self._load_joblib_model("isolation_forest.joblib")
            if obj is not None:
                from ai_engin.colab_training.models.isolation_forest import RakshakIsolationForest
                iforest = RakshakIsolationForest()
                iforest.model = obj["model"]
                iforest.scaler = obj["scaler"]
                iforest._score_min = obj["score_min"]
                iforest._score_max = obj["score_max"]
                iforest.is_fitted = True
                self._models["iforest"] = iforest
            else:
                self._models["iforest"] = None
        return self._models["iforest"]

    def get_meta_classifier(self):
        """Get the GBM meta-classifier."""
        if "meta" not in self._models:
            obj = self._load_joblib_model("meta_classifier.joblib")
            if obj is not None:
                from ai_engin.colab_training.models.meta_classifier import MetaClassifier
                meta = MetaClassifier()
                meta.model = obj["model"]
                meta.calibrated_model = obj["calibrated_model"]
                meta.feature_names = obj["feature_names"]
                meta.is_fitted = True
                self._models["meta"] = meta
            else:
                self._models["meta"] = None
        return self._models["meta"]

    def get_stat_detector(self):
        """Get the statistical anomaly detector."""
        if "stat" not in self._models:
            obj = self._load_joblib_model("stat_detector.joblib")
            if obj is not None:
                from ai_engin.colab_training.models.meta_classifier import StatisticalAnomalyDetector
                stat = StatisticalAnomalyDetector()
                stat.means = obj["means"]
                stat.stds = obj["stds"]
                stat.q1 = obj["q1"]
                stat.q3 = obj["q3"]
                stat.iqr = obj["iqr"]
                stat.is_fitted = True
                self._models["stat"] = stat
            else:
                self._models["stat"] = None
        return self._models["stat"]

    def get_scaler(self, name: str):
        """Get a feature scaler by name."""
        key = f"scaler_{name}"
        if key not in self._models:
            self._models[key] = self._load_joblib_model(f"{name}_scaler.joblib")
        return self._models[key]

    def get_fault_classes(self):
        """Get the list of fault class names."""
        return self.config.get("fault_classes", [])

    def get_anomaly_threshold(self) -> float:
        """Get the calibrated anomaly threshold."""
        return self.config.get("anomaly_threshold", 0.5)

    def list_available(self) -> Dict[str, bool]:
        """List which models are available in the directory."""
        files = os.listdir(self.model_dir) if os.path.isdir(self.model_dir) else []
        return {
            "vae": "vae_anomaly_detector.pt" in files,
            "failure_predictor": "failure_predictor.pt" in files,
            "fault_classifier": "fault_classifier.pt" in files,
            "isolation_forest": "isolation_forest.joblib" in files,
            "meta_classifier": "meta_classifier.joblib" in files,
            "stat_detector": "stat_detector.joblib" in files,
            "config": "model_config.json" in files,
        }
