"""
Rakshak AI Engine — Full Inference Pipeline
===============================================
The main entry point for the Django backend.

This module provides a clean, high-level API that:
1. Accepts raw sensor readings
2. Buffers them into sliding windows
3. Runs the full multi-model prediction pipeline
4. Returns structured results

Usage:
    from ai_engin.inference.pipeline import RakshakInferencePipeline

    pipeline = RakshakInferencePipeline(model_dir="ai_engin/trained_models/")

    # Single reading (accumulates into buffer)
    result = pipeline.process_reading(
        ambient_temp=42.5,
        humidity=22.0,
        vibration_rms=0.85,
        gauge_width=1676.3,
    )

    # Batch prediction on a window
    result = pipeline.predict_window(window_array)
"""

import time
import logging
import numpy as np
from typing import Optional, Dict, Union

from ai_engin.inference.model_registry import ModelRegistry
from ai_engin.inference.anomaly_detector import AnomalyDetector
from ai_engin.inference.failure_predictor import FailurePredictor
from ai_engin.inference.fault_classifier import FaultClassifier
from ai_engin.inference.utils import (
    SensorReading,
    PredictionResult,
    AnomalyResult,
    ReadingBuffer,
)

logger = logging.getLogger(__name__)


class RakshakInferencePipeline:
    """
    Complete AI inference pipeline for Rakshak.

    Integrates all 4 models:
    - 3-tier anomaly detection (Statistical + IsoForest + VAE + Meta)
    - Multi-horizon failure prediction (1h / 6h / 24h)
    - Fault type classification (15+ fault classes)

    Thread-safe for use in Django request handling.
    """

    def __init__(
        self,
        model_dir: str,
        device: Optional[str] = None,
        window_size: int = 64,
        alert_threshold: float = 0.7,
        critical_threshold: float = 0.9,
    ):
        """
        Initialize the pipeline and load all models.

        Args:
            model_dir: Path to the `trained_models/` directory
            device: 'cuda' or 'cpu' (auto-detects if None)
            window_size: Sliding window size for sequence models
            alert_threshold: Failure probability threshold for warnings
            critical_threshold: Failure probability threshold for critical alerts
        """
        self.model_dir = model_dir
        self.window_size = window_size

        # Model registry (lazy-loads models)
        self.registry = ModelRegistry(model_dir, device)

        # Sub-pipelines
        self.anomaly_detector = AnomalyDetector(self.registry)
        self.failure_predictor = FailurePredictor(
            self.registry,
            alert_threshold=alert_threshold,
            critical_threshold=critical_threshold,
        )
        self.fault_classifier = FaultClassifier(self.registry)

        # Per-sensor reading buffers (keyed by sensor_id)
        self._buffers: Dict[str, ReadingBuffer] = {}

        logger.info(
            f"RakshakInferencePipeline initialized\n"
            f"  Models: {self.registry.list_available()}\n"
            f"  Device: {self.registry.device}\n"
            f"  Window: {window_size}"
        )

    def _get_buffer(self, sensor_id: str = "default") -> ReadingBuffer:
        """Get or create a reading buffer for a sensor."""
        if sensor_id not in self._buffers:
            self._buffers[sensor_id] = ReadingBuffer(
                window_size=self.window_size,
                num_features=4,
            )
        return self._buffers[sensor_id]

    def process_reading(
        self,
        ambient_temp: float,
        humidity: float,
        vibration_rms: float,
        gauge_width: float,
        timestamp: Optional[str] = None,
        sensor_id: str = "default",
    ) -> Optional[PredictionResult]:
        """
        Process a single sensor reading.

        Adds the reading to the sliding window buffer. When the
        buffer is full, runs the full prediction pipeline.

        Args:
            ambient_temp: Ambient temperature (°C)
            humidity: Relative humidity (%)
            vibration_rms: RMS vibration (mm/s)
            gauge_width: Track gauge width (mm)
            timestamp: ISO timestamp string
            sensor_id: Sensor identifier (for multi-sensor support)

        Returns:
            PredictionResult if buffer is full, None if still accumulating
        """
        reading = SensorReading(
            ambient_temp=ambient_temp,
            humidity=humidity,
            vibration_rms=vibration_rms,
            gauge_width=gauge_width,
            timestamp=timestamp,
        )

        buffer = self._get_buffer(sensor_id)
        buffer.add(reading)

        if buffer.is_ready:
            window = buffer.get_window()
            return self.predict_window(window)

        return None

    def predict_window(
        self,
        window: np.ndarray,
        use_uncertainty: bool = False,
    ) -> PredictionResult:
        """
        Run the full prediction pipeline on a pre-formed window.

        Args:
            window: (W, 4) numpy array of sensor readings in order:
                    [ambient_temp, humidity, vibration_rms, gauge_width]
            use_uncertainty: Run MC Dropout for uncertainty estimation

        Returns:
            PredictionResult with anomaly, failure, and fault predictions
        """
        t0 = time.time()
        result = PredictionResult()

        # ─── Step 1: Anomaly Detection ───
        try:
            anomaly = self.anomaly_detector.detect(window)
            result.anomaly = anomaly
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            result.anomaly = AnomalyResult(is_anomaly=False, anomaly_score=0.0)

        # ─── Step 2: Failure Prediction (always runs) ───
        try:
            failure = self.failure_predictor.predict(
                window,
                use_uncertainty=use_uncertainty,
            )
            result.failure = failure
        except Exception as e:
            logger.error(f"Failure prediction failed: {e}")

        # ─── Step 3: Fault Classification (only if anomaly detected) ───
        if result.anomaly.is_anomaly:
            try:
                fault = self.fault_classifier.classify(
                    window,
                    anomaly_score=result.anomaly.anomaly_score,
                )
                result.fault = fault
            except Exception as e:
                logger.error(f"Fault classification failed: {e}")

        result.processing_time_ms = (time.time() - t0) * 1000

        return result

    def predict_batch(
        self,
        readings: list,
        sensor_id: str = "default",
    ) -> list:
        """
        Process a batch of readings and return all predictions.

        Args:
            readings: List of dicts with sensor values
            sensor_id: Sensor identifier

        Returns:
            List of PredictionResult (or None for buffering readings)
        """
        results = []
        for r in readings:
            result = self.process_reading(
                ambient_temp=r["ambient_temp"],
                humidity=r["humidity"],
                vibration_rms=r["vibration_rms"],
                gauge_width=r["gauge_width"],
                timestamp=r.get("timestamp"),
                sensor_id=sensor_id,
            )
            results.append(result)
        return results

    def health_check(self) -> Dict:
        """
        Check if the pipeline is ready for inference.

        Returns a status dict suitable for a health check endpoint.
        """
        available = self.registry.list_available()
        all_loaded = all(available.values())

        return {
            "status": "healthy" if all_loaded else "degraded",
            "models": available,
            "device": self.registry.device,
            "window_size": self.window_size,
            "active_buffers": len(self._buffers),
        }

    def reset_buffer(self, sensor_id: str = "default"):
        """Reset the reading buffer for a sensor."""
        if sensor_id in self._buffers:
            self._buffers[sensor_id].reset()

    def reset_all_buffers(self):
        """Reset all reading buffers."""
        self._buffers.clear()
