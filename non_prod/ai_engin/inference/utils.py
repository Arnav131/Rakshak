"""
Rakshak AI Engine — Inference Utilities
==========================================
Shared utilities for the inference pipeline.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SensorReading:
    """Single sensor reading input."""
    ambient_temp: float
    humidity: float
    vibration_rms: float
    gauge_width: float
    timestamp: Optional[str] = None

    def to_array(self) -> np.ndarray:
        """Convert to numpy array in canonical feature order."""
        return np.array([
            self.ambient_temp,
            self.humidity,
            self.vibration_rms,
            self.gauge_width,
        ], dtype=np.float32)

    def to_dict(self) -> Dict:
        return {
            "ambient_temp": self.ambient_temp,
            "humidity": self.humidity,
            "vibration_rms": self.vibration_rms,
            "gauge_width": self.gauge_width,
            "timestamp": self.timestamp or datetime.utcnow().isoformat(),
        }


@dataclass
class AnomalyResult:
    """Result from the anomaly detection pipeline."""
    is_anomaly: bool
    anomaly_score: float
    tier_scores: Dict[str, float] = field(default_factory=dict)
    threshold: float = 0.5

    def to_dict(self) -> Dict:
        return {
            "is_anomaly": self.is_anomaly,
            "anomaly_score": round(self.anomaly_score, 4),
            "tier_scores": {k: round(v, 4) for k, v in self.tier_scores.items()},
            "threshold": self.threshold,
        }


@dataclass
class FailurePrediction:
    """Result from the failure prediction model."""
    probabilities: Dict[str, float] = field(default_factory=dict)
    uncertainty: Dict[str, float] = field(default_factory=dict)
    alert_level: str = "none"  # none, warning, critical

    def to_dict(self) -> Dict:
        return {
            "probabilities": {k: round(v, 4) for k, v in self.probabilities.items()},
            "uncertainty": {k: round(v, 4) for k, v in self.uncertainty.items()},
            "alert_level": self.alert_level,
        }


@dataclass
class FaultClassification:
    """Result from the fault classification model."""
    fault_type: str = "unknown"
    confidence: float = 0.0
    top_k: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "fault_type": self.fault_type,
            "confidence": round(self.confidence, 4),
            "top_k": [
                {"class": d["class"], "probability": round(d["probability"], 4)}
                for d in self.top_k
            ],
        }


@dataclass
class PredictionResult:
    """Complete prediction result from the full pipeline."""
    anomaly: AnomalyResult = field(default_factory=lambda: AnomalyResult(False, 0.0))
    failure: FailurePrediction = field(default_factory=FailurePrediction)
    fault: FaultClassification = field(default_factory=FaultClassification)
    processing_time_ms: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "anomaly": self.anomaly.to_dict(),
            "failure_prediction": self.failure.to_dict(),
            "fault_classification": self.fault.to_dict(),
            "processing_time_ms": round(self.processing_time_ms, 2),
        }

    @property
    def anomaly_score(self) -> float:
        return self.anomaly.anomaly_score

    @property
    def failure_probabilities(self) -> Dict[str, float]:
        return self.failure.probabilities

    @property
    def fault_type(self) -> str:
        return self.fault.fault_type

    @property
    def fault_confidence(self) -> float:
        return self.fault.confidence


class ReadingBuffer:
    """
    Sliding window buffer for accumulating sensor readings.

    Maintains a fixed-size buffer of the most recent readings.
    When the buffer is full, the pipeline can generate predictions.
    """

    def __init__(self, window_size: int = 64, num_features: int = 4):
        self.window_size = window_size
        self.num_features = num_features
        self.buffer = np.zeros((window_size, num_features), dtype=np.float32)
        self.count = 0
        self.timestamps: List[str] = []

    @property
    def is_ready(self) -> bool:
        """Whether the buffer has enough data for prediction."""
        return self.count >= self.window_size

    def add(self, reading: SensorReading):
        """Add a new reading to the buffer."""
        values = reading.to_array()

        if self.count < self.window_size:
            self.buffer[self.count] = values
        else:
            # Shift left and append
            self.buffer[:-1] = self.buffer[1:]
            self.buffer[-1] = values

        self.count += 1
        self.timestamps.append(reading.timestamp or datetime.utcnow().isoformat())

        # Keep timestamps bounded
        if len(self.timestamps) > self.window_size:
            self.timestamps = self.timestamps[-self.window_size:]

    def get_window(self) -> np.ndarray:
        """Get the current window as a numpy array (W, F)."""
        if self.count < self.window_size:
            return self.buffer[:self.count]
        return self.buffer.copy()

    def reset(self):
        """Clear the buffer."""
        self.buffer = np.zeros((self.window_size, self.num_features), dtype=np.float32)
        self.count = 0
        self.timestamps = []
