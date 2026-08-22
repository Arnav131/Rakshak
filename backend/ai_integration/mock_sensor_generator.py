# backend/ai_integration/mock_sensor_generator.py
"""
Rakshak AI Integration — Mock Sensor Generator
===================================================
Generates realistic sequences of sensor readings for hackathon
demo / journey simulation.

This module is completely isolated from AI logic. It produces
raw sensor value dictionaries that can be fed into PredictionService.

AI TEAM NOTE:
    Purpose:     Generate realistic sensor sequences for demo without real hardware.
    How it works: Each scenario defines a trajectory (gradual drift) across 4 sensor
                  channels. Readings build on previous values with controlled noise.
    Why introduced: Hackathon demo requires journey simulation without physical sensors.
    Future LLM compatibility: An LLM provider would receive these same readings
                              through PredictionService — no changes needed here.

CHANGE SUMMARY:
    Reason: Hackathon demo requires simulated sensor data for journey simulation.
    Architecture impact: NONE — pure utility module, no imports from Django ORM or AI.
    Future migration notes: Replace with real sensor ingestion when hardware is available.
    Backward compatibility: N/A — new module, no existing callers.

# ---------------------------------------------------------------------------
# DATABASE MIGRATION NOTE
#
# This module has ZERO database interaction.
# It generates pure Python dictionaries.
# Current DB: PostgreSQL
# Future DB: None
# Whether this code is PostgreSQL compatible: YES (no DB interaction)
# Whether teammate needs to modify anything: NO
# Migration required: NO
# ---------------------------------------------------------------------------
"""

import random
from typing import Dict, List, Optional


# ===================================================================
# SCENARIO DEFINITIONS
# ===================================================================
# Each scenario defines base values and per-step deltas for the
# four sensor channels. The generator applies these progressively
# across the sequence window to simulate gradual degradation.
# ===================================================================

SCENARIOS = {
    "healthy": {
        "name": "Normal Journey",
        "description": "All sensors within normal operating range. No anomalies.",
        "base": {
            "ambient_temp": 35.0,
            "humidity": 50.0,
            "vibration_rms": 0.5,
            "gauge_width": 1676.0,
        },
        "delta_per_step": {
            "ambient_temp": 0.0,
            "humidity": 0.0,
            "vibration_rms": 0.0,
            "gauge_width": 0.0,
        },
        "noise_scale": {
            "ambient_temp": 0.5,
            "humidity": 1.0,
            "vibration_rms": 0.1,
            "gauge_width": 0.2,
        },
    },
    "gauge_widening": {
        "name": "Gauge Widening",
        "description": "Track gauge gradually widens beyond safe limits, indicating rail fastener degradation.",
        "base": {
            "ambient_temp": 38.0,
            "humidity": 45.0,
            "vibration_rms": 1.0,
            "gauge_width": 1676.0,
        },
        "delta_per_step": {
            "ambient_temp": 0.1,
            "humidity": -0.2,
            "vibration_rms": 0.15,
            "gauge_width": 1.2,
        },
        "noise_scale": {
            "ambient_temp": 0.3,
            "humidity": 0.5,
            "vibration_rms": 0.1,
            "gauge_width": 0.3,
        },
    },
    "vibration_increase": {
        "name": "Vibration Increase",
        "description": "RMS vibration ramps up sharply, suggesting ballast degradation or wheel flat.",
        "base": {
            "ambient_temp": 36.0,
            "humidity": 55.0,
            "vibration_rms": 0.5,
            "gauge_width": 1676.0,
        },
        "delta_per_step": {
            "ambient_temp": 0.0,
            "humidity": 0.0,
            "vibration_rms": 0.5,
            "gauge_width": 0.1,
        },
        "noise_scale": {
            "ambient_temp": 0.3,
            "humidity": 0.5,
            "vibration_rms": 0.2,
            "gauge_width": 0.2,
        },
    },
    "temperature_spike": {
        "name": "Temperature Spike",
        "description": "Ambient temperature rises rapidly, risk of thermal buckling.",
        "base": {
            "ambient_temp": 35.0,
            "humidity": 40.0,
            "vibration_rms": 0.8,
            "gauge_width": 1676.0,
        },
        "delta_per_step": {
            "ambient_temp": 1.5,
            "humidity": -1.0,
            "vibration_rms": 0.05,
            "gauge_width": 0.3,
        },
        "noise_scale": {
            "ambient_temp": 0.5,
            "humidity": 0.5,
            "vibration_rms": 0.1,
            "gauge_width": 0.2,
        },
    },
    "mixed_anomaly": {
        "name": "Mixed Anomaly",
        "description": "Multiple parameters degrade simultaneously — complex fault pattern.",
        "base": {
            "ambient_temp": 40.0,
            "humidity": 35.0,
            "vibration_rms": 1.5,
            "gauge_width": 1678.0,
        },
        "delta_per_step": {
            "ambient_temp": 0.8,
            "humidity": -0.5,
            "vibration_rms": 0.4,
            "gauge_width": 0.8,
        },
        "noise_scale": {
            "ambient_temp": 0.4,
            "humidity": 0.5,
            "vibration_rms": 0.15,
            "gauge_width": 0.25,
        },
    },
}


def generate_sequence(
    scenario: str = "healthy",
    window_size: int = 16,
    seed: Optional[int] = None,
) -> List[Dict[str, float]]:
    """
    Generate a sequence of realistic sensor readings for a given scenario.

    Each reading builds on the previous one with controlled drift and noise,
    producing a temporally coherent sequence suitable for sequence-based
    CNN models.

    Args:
        scenario:    Scenario key from SCENARIOS dict.
        window_size: Number of readings to generate (must match model's expected input).
        seed:        Optional random seed for reproducibility.

    Returns:
        List of dicts, each containing:
            ambient_temp, humidity, vibration_rms, gauge_width

    Raises:
        ValueError: If scenario is not recognized.
    """
    if scenario not in SCENARIOS:
        raise ValueError(
            f"Unknown scenario '{scenario}'. "
            f"Available: {list(SCENARIOS.keys())}"
        )

    config = SCENARIOS[scenario]
    base = config["base"]
    delta = config["delta_per_step"]
    noise = config["noise_scale"]

    if seed is not None:
        random.seed(seed)

    readings = []
    current = dict(base)

    for step in range(window_size):
        # Apply drift
        reading = {}
        for key in ["ambient_temp", "humidity", "vibration_rms", "gauge_width"]:
            # Progressive drift + Gaussian noise
            value = current[key] + delta[key] + random.gauss(0, noise[key])

            # Clamp to physically valid ranges
            if key == "ambient_temp":
                value = max(-50.0, min(80.0, value))
            elif key == "humidity":
                value = max(0.0, min(100.0, value))
            elif key == "vibration_rms":
                value = max(0.0, min(50.0, value))
            elif key == "gauge_width":
                value = max(1500.0, min(1800.0, value))

            reading[key] = round(value, 2)
            current[key] = value

        readings.append(reading)

    return readings


def list_scenarios() -> List[Dict[str, str]]:
    """
    List all available simulation scenarios.

    Returns:
        List of dicts with id, name, description for each scenario.
    """
    return [
        {
            "id": key,
            "name": config["name"],
            "description": config["description"],
        }
        for key, config in SCENARIOS.items()
    ]
