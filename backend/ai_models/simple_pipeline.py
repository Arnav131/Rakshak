"""
Rakshak AI — Simple Inference Pipeline
=========================================
This file is used by the backend to run inference using the trained models.
Copy this file + the simple_models/ directory to your backend.

Usage (standalone test):
    python simple_pipeline.py

Usage (from backend):
    from ai_models.simple_pipeline import SimpleRakshakInferencePipeline
    
    pipeline = SimpleRakshakInferencePipeline(model_dir="path/to/ai_models")
    result = pipeline.predict(
        ambient_temp=42.0,
        humidity=40.0,
        vibration_rms=4.8,
        gauge_width=1689.0,
    )
    print(result)
"""

import json
import logging
import os
import pickle
import time
from pathlib import Path
from typing import Dict, Optional

import numpy as np

logger = logging.getLogger("rakshak.ai.pipeline")

# Standard gauge width (mm) for Indian Railways broad gauge
STANDARD_GAUGE_MM = 1676.0


# ---------------------------------------------------------------------------
# Rule Layer — transparent safety rules
# ---------------------------------------------------------------------------
class RuleLayer:
    """
    Transparent rule-based safety checks.
    
    These rules override or boost model predictions when sensor values
    clearly indicate a known risk pattern. This ensures the system
    never misses obvious danger signs even if the model is uncertain.
    """
    
    @staticmethod
    def apply(features: dict, risk_result: dict, fault_result: dict) -> dict:
        """
        Apply safety rules on top of model predictions.
        
        Returns modified risk_result and fault_result plus explanation strings.
        """
        explanations = []
        rule_triggers = []
        
        gauge_dev = features.get("gauge_deviation_max", 0.0)
        vibration = features.get("vibration_rms_max", 0.0)
        temp = features.get("ambient_temp_max", 0.0)
        humidity = features.get("humidity_max", 0.0)
        
        # Rule 1: Extreme gauge deviation → force critical + gauge_widening
        if gauge_dev > 15.0:
            risk_result["alert_level"] = "critical"
            risk_result["anomaly_score"] = max(risk_result.get("anomaly_score", 0.0), 0.95)
            fault_result["fault_type"] = "gauge_widening"
            fault_result["fault_confidence"] = max(fault_result.get("fault_confidence", 0.0), 0.90)
            explanations.append(
                f"CRITICAL: Gauge deviation {gauge_dev:.1f}mm exceeds 15mm safety limit. "
                f"Immediate inspection required."
            )
            rule_triggers.append("gauge_deviation_critical")
        
        # Rule 2: High gauge deviation → at least warning
        elif gauge_dev > 10.0:
            if risk_result.get("alert_level") == "none":
                risk_result["alert_level"] = "warning"
                risk_result["anomaly_score"] = max(risk_result.get("anomaly_score", 0.0), 0.70)
            explanations.append(
                f"WARNING: Gauge deviation {gauge_dev:.1f}mm exceeds 10mm threshold. "
                f"Track gauge widening detected."
            )
            rule_triggers.append("gauge_deviation_warning")
        
        # Rule 3: Extreme vibration → boost rail_fracture
        if vibration > 9.0:
            risk_result["alert_level"] = "critical"
            risk_result["anomaly_score"] = max(risk_result.get("anomaly_score", 0.0), 0.92)
            if fault_result.get("fault_type") in ("normal", None):
                fault_result["fault_type"] = "rail_fracture"
                fault_result["fault_confidence"] = max(fault_result.get("fault_confidence", 0.0), 0.85)
            explanations.append(
                f"CRITICAL: Vibration {vibration:.1f} RMS exceeds emergency threshold. "
                f"Possible rail fracture or severe joint wear."
            )
            rule_triggers.append("vibration_critical")
        
        elif vibration > 5.0:
            if risk_result.get("alert_level") == "none":
                risk_result["alert_level"] = "warning"
                risk_result["anomaly_score"] = max(risk_result.get("anomaly_score", 0.0), 0.68)
            explanations.append(
                f"WARNING: Elevated vibration {vibration:.1f} RMS detected. "
                f"Monitor for potential joint wear or track defect."
            )
            rule_triggers.append("vibration_warning")
        
        # Rule 4: High temperature + gauge deviation → thermal buckle
        if temp > 50.0 and gauge_dev > 5.0:
            if risk_result.get("alert_level") != "critical":
                risk_result["alert_level"] = "warning"
            risk_result["anomaly_score"] = max(risk_result.get("anomaly_score", 0.0), 0.80)
            fault_result["fault_type"] = "thermal_buckle"
            fault_result["fault_confidence"] = max(fault_result.get("fault_confidence", 0.0), 0.80)
            explanations.append(
                f"WARNING: High temperature ({temp:.1f}°C) combined with gauge deviation "
                f"({gauge_dev:.1f}mm). Risk of thermal buckling."
            )
            rule_triggers.append("thermal_buckle_risk")
        
        elif temp > 55.0:
            risk_result["alert_level"] = "critical"
            risk_result["anomaly_score"] = max(risk_result.get("anomaly_score", 0.0), 0.88)
            explanations.append(
                f"CRITICAL: Extreme temperature {temp:.1f}°C. "
                f"Rail stress monitoring required."
            )
            rule_triggers.append("temperature_critical")
        
        # Rule 5: Normal reading explanation
        if not explanations:
            if risk_result.get("alert_level") == "none":
                explanations.append(
                    f"All sensor readings within normal parameters. "
                    f"Temp: {temp:.1f}°C, Vibration: {vibration:.1f} RMS, "
                    f"Gauge deviation: {gauge_dev:.1f}mm."
                )
            else:
                explanations.append(
                    f"AI model detected elevated risk. "
                    f"Temp: {temp:.1f}°C, Vibration: {vibration:.1f} RMS, "
                    f"Gauge deviation: {gauge_dev:.1f}mm."
                )
        
        return {
            "risk": risk_result,
            "fault": fault_result,
            "explanations": explanations,
            "rule_triggers": rule_triggers,
        }


# ---------------------------------------------------------------------------
# Inference Pipeline
# ---------------------------------------------------------------------------
class SimpleRakshakInferencePipeline:
    """
    Simple inference pipeline for Rakshak railway monitoring.
    
    Loads PyTorch MLP models from pickle files and runs inference.
    Falls back to pure rule-based predictions if model files are missing.
    
    Args:
        model_dir: Path to directory containing model pickle files and config.
    """
    
    def __init__(self, model_dir: str = None):
        if model_dir is None:
            model_dir = os.path.join(os.path.dirname(__file__), "simple_models")
        
        self.model_dir = Path(model_dir)
        self.risk_model = None
        self.risk_artifact = None
        self.fault_model = None
        self.fault_artifact = None
        self.config = None
        self.models_loaded = False
        self.rule_layer = RuleLayer()
        
        self._load_models()
    
    def _load_models(self):
        """Load model files. Gracefully handle missing files."""
        try:
            import torch
            import torch.nn as nn
            self._torch = torch
            self._nn = nn
        except ImportError:
            logger.warning("PyTorch not available. Using rule-based fallback only.")
            return
        
        # Load config
        config_path = self.model_dir / "model_config.json"
        if config_path.exists():
            with open(config_path, "r") as f:
                self.config = json.load(f)
            logger.info(f"Loaded model config v{self.config.get('version', 'unknown')}")
        
        # Load risk model
        risk_path = self.model_dir / "anomaly_model.pkl"
        if risk_path.exists():
            try:
                with open(risk_path, "rb") as f:
                    self.risk_artifact = pickle.load(f)
                in_channels = self.risk_artifact.get("in_channels", 4)
                num_classes = self.risk_artifact.get("num_classes", 3)
                self.risk_model = self._build_model(in_channels, num_classes)
                self.risk_model.load_state_dict(self.risk_artifact["model_state_dict"])
                self.risk_model.eval()
                logger.info("Risk model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load risk model: {e}")
                self.risk_model = None
        else:
            logger.warning(f"Risk model not found at {risk_path}. Using rules only.")
        
        # Load fault model
        fault_path = self.model_dir / "fault_model.pkl"
        if fault_path.exists():
            try:
                with open(fault_path, "rb") as f:
                    self.fault_artifact = pickle.load(f)
                in_channels = self.fault_artifact.get("in_channels", 4)
                num_classes = self.fault_artifact.get("num_classes", len(self.fault_artifact.get("class_names", [])))
                self.fault_model = self._build_model(in_channels, num_classes)
                self.fault_model.load_state_dict(self.fault_artifact["model_state_dict"])
                self.fault_model.eval()
                logger.info("Fault model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load fault model: {e}")
                self.fault_model = None
        else:
            logger.warning(f"Fault model not found at {fault_path}. Using rules only.")
        
        self.models_loaded = (self.risk_model is not None)
    
    def _build_model(self, in_channels: int, num_classes: int):
        """Build the CNN1D architecture (matches trained weights)."""
        nn = self._nn
        
        class CNN1D(nn.Module):
            def __init__(self):
                super().__init__()
                self.conv = nn.Sequential(
                    nn.Conv1d(in_channels, 16, kernel_size=3, padding=1),
                    nn.BatchNorm1d(16),
                    nn.ReLU(),
                    nn.Conv1d(16, 32, kernel_size=3, padding=1),
                    nn.BatchNorm1d(32),
                    nn.ReLU(),
                )
                self.pool = nn.AdaptiveAvgPool1d(1)
                self.head = nn.Sequential(
                    nn.Flatten(),
                    nn.Linear(32, 32),
                    nn.ReLU(),
                    nn.Dropout(0.2),
                    nn.Linear(32, num_classes),
                )
            
            def forward(self, x):
                return self.head(self.pool(self.conv(x)))
        
        return CNN1D()
    
    def _build_features(
        self,
        ambient_temp: float,
        humidity: float,
        vibration_rms: float,
        gauge_width: float,
    ) -> dict:
        """Build feature dict from a single sensor reading."""
        gauge_dev = abs(gauge_width - STANDARD_GAUGE_MM)
        
        return {
            "ambient_temp": float(ambient_temp),
            "humidity": float(humidity),
            "vibration_rms": float(vibration_rms),
            "gauge_width": float(gauge_width),
            "ambient_temp_mean": float(ambient_temp),
            "ambient_temp_max": float(ambient_temp),
            "ambient_temp_min": float(ambient_temp),
            "ambient_temp_std": 0.0,
            "humidity_mean": float(humidity),
            "humidity_max": float(humidity),
            "humidity_min": float(humidity),
            "humidity_std": 0.0,
            "vibration_rms_mean": float(vibration_rms),
            "vibration_rms_max": float(vibration_rms),
            "vibration_rms_min": float(vibration_rms),
            "vibration_rms_std": 0.0,
            "gauge_width_mean": float(gauge_width),
            "gauge_width_max": float(gauge_width),
            "gauge_width_min": float(gauge_width),
            "gauge_width_std": 0.0,
            "gauge_deviation_mean": float(gauge_dev),
            "gauge_deviation_max": float(gauge_dev),
            "temperature_risk_flag": 1.0 if ambient_temp > 48.0 else 0.0,
            "vibration_risk_flag": 1.0 if vibration_rms > 5.0 else 0.0,
            "gauge_risk_flag": 1.0 if gauge_dev > 10.0 else 0.0,
            "humidity_risk_flag": 1.0 if humidity > 85.0 else 0.0,
        }
    
    def _model_predict(self, model, artifact, features: dict) -> dict:
        """Run CNN1D model inference on features."""
        torch = self._torch
        feature_order = artifact.get("feature_order", ["ambient_temp", "humidity", "vibration_rms", "gauge_width"])
        window_size = artifact.get("window_size", 16)
        
        raw_vals = np.array([features.get(col, 0.0) for col in feature_order], dtype=np.float32)
        
        channel_mean = np.array(artifact.get("channel_mean", [30.0, 50.0, 1.5, 1676.0]), dtype=np.float32)
        channel_std = np.array(artifact.get("channel_std", [10.0, 20.0, 2.0, 5.0]), dtype=np.float32)
        channel_std = np.where(channel_std == 0, 1.0, channel_std)
        
        norm_vals = (raw_vals - channel_mean) / channel_std
        # Shape: (1, in_channels, window_size)
        seq_tensor = np.tile(norm_vals[:, np.newaxis], (1, window_size))
        x_tensor = torch.tensor(seq_tensor, dtype=torch.float32).unsqueeze(0)
        
        with torch.no_grad():
            output = model(x_tensor)
            probs = torch.softmax(output, dim=-1).numpy()[0]
            pred_class = int(np.argmax(probs))
        
        class_names = artifact.get("class_names", [str(i) for i in range(len(probs))])
        label = class_names[pred_class] if pred_class < len(class_names) else "unknown"
        
        return {
            "predicted_class": pred_class,
            "predicted_label": label,
            "confidence": float(probs[pred_class]),
            "probabilities": {
                name: float(probs[i]) for i, name in enumerate(class_names) if i < len(probs)
            },
        }
    
    def _rule_only_predict(self, features: dict) -> dict:
        """Pure rule-based prediction when models are unavailable."""
        gauge_dev = features.get("gauge_deviation_max", 0.0)
        vibration = features.get("vibration_rms_max", 0.0)
        temp = features.get("ambient_temp_max", 0.0)
        
        # Determine alert level
        if gauge_dev > 15 or vibration > 9 or temp > 55:
            alert_level = "critical"
            anomaly_score = 0.95
        elif gauge_dev > 10 or vibration > 5 or temp > 50:
            alert_level = "warning"
            anomaly_score = 0.75
        else:
            alert_level = "none"
            anomaly_score = 0.15
        
        # Determine fault type
        if gauge_dev > 10:
            fault_type = "gauge_widening"
        elif temp > 50 and gauge_dev > 5:
            fault_type = "thermal_buckle"
        elif vibration > 7:
            fault_type = "rail_fracture"
        else:
            fault_type = "normal"
        
        return {
            "anomaly_score": anomaly_score,
            "alert_level": alert_level,
            "is_anomaly": alert_level != "none",
            "fault_type": fault_type,
            "fault_confidence": 0.70 if fault_type != "normal" else 0.90,
            "explanation": "Rule-based prediction (models not loaded).",
            "model_used": "rules_only",
        }
    
    def predict(
        self,
        ambient_temp: float,
        humidity: float,
        vibration_rms: float,
        gauge_width: float,
    ) -> dict:
        """
        Run inference on sensor readings.
        
        Args:
            ambient_temp: Ambient temperature in °C
            humidity: Relative humidity in %
            vibration_rms: Vibration RMS value
            gauge_width: Track gauge width in mm
        
        Returns:
            Dict with keys:
                - anomaly_score: 0.0 to 1.0
                - is_anomaly: bool
                - alert_level: "none" | "warning" | "critical"
                - fault_type: string
                - fault_confidence: 0.0 to 1.0
                - explanation: human-readable string
                - processing_time_ms: float
                - model_used: string
                - top_features: dict of contributing features
        """
        t0 = time.time()
        
        # Build features
        features = self._build_features(ambient_temp, humidity, vibration_rms, gauge_width)
        
        # If models not loaded → pure rule fallback
        if not self.models_loaded:
            result = self._rule_only_predict(features)
            result["processing_time_ms"] = round((time.time() - t0) * 1000, 2)
            return result
        
        # Model-based prediction
        risk_pred = self._model_predict(self.risk_model, self.risk_artifact, features)
        
        # Convert risk prediction to result format
        risk_result = {
            "alert_level": risk_pred["predicted_label"],
            "anomaly_score": 1.0 - risk_pred["probabilities"].get("none", 0.0),
        }
        
        # Fault prediction
        fault_result = {}
        if self.fault_model is not None:
            fault_pred = self._model_predict(self.fault_model, self.fault_artifact, features)
            fault_result = {
                "fault_type": fault_pred["predicted_label"],
                "fault_confidence": fault_pred["confidence"],
                "fault_top_k": dict(
                    sorted(fault_pred["probabilities"].items(), key=lambda x: -x[1])[:3]
                ),
            }
        else:
            fault_result = {"fault_type": "unknown", "fault_confidence": 0.0}
        
        # Apply rule layer (safety overrides)
        ruled = self.rule_layer.apply(features, risk_result, fault_result)
        risk_result = ruled["risk"]
        fault_result = ruled["fault"]
        
        # Build final result
        result = {
            "anomaly_score": round(risk_result["anomaly_score"], 4),
            "is_anomaly": risk_result["alert_level"] != "none",
            "alert_level": risk_result["alert_level"],
            "fault_type": fault_result.get("fault_type", "unknown"),
            "fault_confidence": round(fault_result.get("fault_confidence", 0.0), 4),
            "fault_top_k": fault_result.get("fault_top_k", {}),
            "explanation": " | ".join(ruled["explanations"]),
            "rule_triggers": ruled["rule_triggers"],
            "processing_time_ms": round((time.time() - t0) * 1000, 2),
            "model_used": "pytorch_mlp",
            "top_features": {
                "ambient_temp": ambient_temp,
                "humidity": humidity,
                "vibration_rms": vibration_rms,
                "gauge_width": gauge_width,
                "gauge_deviation": abs(gauge_width - STANDARD_GAUGE_MM),
            },
        }
        
        return result
    
    def health_check(self) -> dict:
        """Return pipeline health status."""
        return {
            "status": "ok" if self.models_loaded else "fallback",
            "risk_model_loaded": self.risk_model is not None,
            "fault_model_loaded": self.fault_model is not None,
            "config_loaded": self.config is not None,
            "model_version": self.config.get("version", "unknown") if self.config else "n/a",
            "mode": "pytorch_mlp" if self.models_loaded else "rules_only",
        }


# ---------------------------------------------------------------------------
# Standalone Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("  Rakshak AI — Simple Pipeline Test")
    print("=" * 60)
    
    pipeline = SimpleRakshakInferencePipeline()
    
    print(f"\nHealth check: {pipeline.health_check()}")
    
    test_cases = [
        ("Normal Track",          {"ambient_temp": 34,  "humidity": 55, "vibration_rms": 1.2,  "gauge_width": 1676}),
        ("Gauge Widening Risk",   {"ambient_temp": 42,  "humidity": 40, "vibration_rms": 4.8,  "gauge_width": 1689}),
        ("Thermal Buckle Risk",   {"ambient_temp": 53,  "humidity": 25, "vibration_rms": 3.5,  "gauge_width": 1684}),
        ("Rail Fracture Risk",    {"ambient_temp": 29,  "humidity": 50, "vibration_rms": 10.5, "gauge_width": 1677}),
    ]
    
    for name, params in test_cases:
        print(f"\n--- {name} ---")
        result = pipeline.predict(**params)
        for k, v in result.items():
            print(f"  {k}: {v}")
