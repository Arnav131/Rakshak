"""
Rakshak Agent System — Sensor Ingestion Agent
================================================
Validates, normalises, and routes raw IoT sensor telemetry
into the Django ORM (SensorReading) and triggers downstream
processing.
"""

import logging
from decimal import Decimal
from datetime import datetime
from typing import Any, Dict, Optional

from django.utils import timezone
from django.db import transaction

from agents.shared.base_agent import BaseAgent
from agents.shared.events import SensorValidatedEvent

logger = logging.getLogger("rakshak.agents.ingestion")


class SensorIngestionAgent(BaseAgent):
    """
    Validates, normalises, and persists raw sensor data.

    Responsibilities:
    - Schema validation (range checks, null handling)
    - Unit normalisation
    - Quality scoring (detects drift, saturation, dropouts)
    - Persistence to SensorReading table
    - Emits SensorValidatedEvent for downstream agents

    From agents_README:
        Autonomy: Continuous
        Latency: Inline with ingestion (< 10ms per reading)
    """

    AGENT_NAME = "sensor_ingestion"
    AGENT_VERSION = "1.0.0"

    # Sensor value valid ranges (from domain knowledge)
    VALID_RANGES = {
        "ambient_temp": (-40.0, 80.0),       # °C — Indian Railways extreme range
        "humidity": (0.0, 100.0),              # %
        "vibration_rms": (0.0, 100.0),         # mm/s
        "gauge_width": (1600.0, 1800.0),       # mm (broad gauge nominal: 1676mm)
    }

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self._smoothing_window = self.config.get("smoothing_window", 5)
        self._recent_values: Dict[int, list] = {}  # sensor_id → recent readings

    def validate_reading(self, data: Dict) -> Dict:
        """
        Validate a sensor reading against schema and range constraints.

        Returns:
            Dict with is_valid, quality_score, errors, warnings
        """
        errors = []
        warnings = []
        quality = 1.0

        # Required fields
        required = ["sensor_id", "track_section_id", "recorded_at"]
        for field in required:
            if field not in data or data[field] is None:
                errors.append(f"Missing required field: {field}")

        if errors:
            return {"is_valid": False, "quality_score": 0.0, "errors": errors, "warnings": []}

        # Range validation for sensor values
        sensor_fields = {
            "ambient_temp": data.get("ambient_temp"),
            "humidity": data.get("humidity"),
            "vibration_rms": data.get("vibration_rms"),
            "gauge_width": data.get("gauge_width"),
        }

        valid_count = 0
        for field_name, value in sensor_fields.items():
            if value is None:
                warnings.append(f"{field_name} is null")
                quality -= 0.1
                continue

            valid_count += 1
            lo, hi = self.VALID_RANGES.get(field_name, (float("-inf"), float("inf")))

            if value < lo or value > hi:
                warnings.append(f"{field_name}={value} outside range [{lo}, {hi}]")
                quality -= 0.2

            # Saturation check (stuck at exact boundary)
            if value == lo or value == hi:
                warnings.append(f"{field_name}={value} saturated at boundary")
                quality -= 0.1

        # Stale data check
        recorded_at = data.get("recorded_at")
        if recorded_at:
            if isinstance(recorded_at, str):
                try:
                    recorded_at = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
                except ValueError:
                    errors.append(f"Invalid timestamp format: {recorded_at}")

            if isinstance(recorded_at, datetime):
                age_seconds = (timezone.now() - recorded_at).total_seconds() if recorded_at.tzinfo else 0
                if age_seconds > 300:  # > 5 minutes old
                    warnings.append(f"Stale reading: {age_seconds:.0f}s old")
                    quality -= 0.15

        quality = max(0.0, min(1.0, quality))

        return {
            "is_valid": len(errors) == 0 and valid_count >= 2,
            "quality_score": round(quality, 4),
            "errors": errors,
            "warnings": warnings,
        }

    def normalise_reading(self, data: Dict) -> Dict:
        """
        Apply moving-average smoothing to reduce sensor noise.

        Maintains a per-sensor buffer of recent values and returns
        the smoothed value alongside the raw value.
        """
        sensor_id = data.get("sensor_id")
        if sensor_id is None:
            return data

        if sensor_id not in self._recent_values:
            self._recent_values[sensor_id] = []

        # Store the primary value
        raw_value = data.get("vibration_rms", data.get("ambient_temp", 0))
        self._recent_values[sensor_id].append(float(raw_value))

        # Keep only last N values
        if len(self._recent_values[sensor_id]) > self._smoothing_window:
            self._recent_values[sensor_id] = self._recent_values[sensor_id][-self._smoothing_window:]

        # Compute smoothed value
        recent = self._recent_values[sensor_id]
        smoothed = sum(recent) / len(recent)

        result = data.copy()
        result["processed_value"] = round(smoothed, 4)
        return result

    def process(self, data: Any) -> Dict:
        """
        Process a raw sensor reading.

        Args:
            data: Dict with keys: sensor_id, track_section_id, recorded_at,
                  ambient_temp, humidity, vibration_rms, gauge_width

        Returns:
            Dict with: reading_id, quality_score, validation, event
        """
        # 1. Validate
        validation = self.validate_reading(data)
        if not validation["is_valid"]:
            logger.warning(
                f"[{self.AGENT_NAME}] Invalid reading from sensor {data.get('sensor_id')}: "
                f"{validation['errors']}"
            )
            return {
                "accepted": False,
                "validation": validation,
            }

        # 2. Normalise
        normalised = self.normalise_reading(data)

        # 3. Persist to database
        from railway.models import SensorReading, Sensor

        raw_value = normalised.get("vibration_rms", normalised.get("ambient_temp", 0))
        processed_value = normalised.get("processed_value")

        with transaction.atomic():
            reading = SensorReading.objects.create(
                sensor_id=normalised["sensor_id"],
                recorded_at=normalised["recorded_at"],
                raw_value=Decimal(str(raw_value)),
                processed_value=Decimal(str(processed_value)) if processed_value else None,
                quality_score=Decimal(str(validation["quality_score"])),
                extra_metrics={
                    "ambient_temp": normalised.get("ambient_temp"),
                    "humidity": normalised.get("humidity"),
                    "vibration_rms": normalised.get("vibration_rms"),
                    "gauge_width": normalised.get("gauge_width"),
                },
            )

        # 4. Emit validated event
        event = SensorValidatedEvent(
            sensor_id=normalised["sensor_id"],
            track_section_id=normalised["track_section_id"],
            reading_id=reading.pk,
            ambient_temp=normalised.get("ambient_temp", 0),
            humidity=normalised.get("humidity", 0),
            vibration_rms=normalised.get("vibration_rms", 0),
            gauge_width=normalised.get("gauge_width", 0),
            recorded_at=str(normalised["recorded_at"]),
            quality_score=validation["quality_score"],
        )

        logger.debug(f"[{self.AGENT_NAME}] Persisted reading {reading.pk} (q={validation['quality_score']})")

        return {
            "accepted": True,
            "reading_id": reading.pk,
            "quality_score": validation["quality_score"],
            "validation": validation,
            "event": event,
        }
