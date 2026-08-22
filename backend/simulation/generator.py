# backend/simulation/generator.py
"""
Rakshak — Simulation Scenario & IoT Sensor Generator
=====================================================
Generates a realistic 16-reading sensor journey (ambient_temp, humidity,
vibration_rms, gauge_width) between a source and destination station,
streaming live into the Rakshak AI prediction pipeline.

Backends tried in order:
    1. xAI Grok API        (GROK_API_KEY or XAI_API_KEY env var)
    2. Google Gemini API   (GEMINI_API_KEY or GOOGLE_API_KEY env var)
    3. Anthropic API       (ANTHROPIC_API_KEY env var)
    4. OpenAI API          (OPENAI_API_KEY env var)
    5. Local Ollama LLM    (Ollama running at localhost:11434)
    6. Dynamic Physics-Based IoT RNG Engine (Always available, generates
       statistically & physically grounded healthy IoT telemetry)

Output is always a list of exactly WINDOW_SIZE dicts:
    [{"ambient_temp": .., "humidity": .., "vibration_rms": .., "gauge_width": ..}, ...]
"""

import json
import logging
import math
import os
import random
import re

import requests

logger = logging.getLogger("rakshak.simulation.generator")

WINDOW_SIZE = 16
STANDARD_GAUGE_MM = 1676.0

# Dataset-grounded typical ranges — used both as grounding context fed to the
# LLM and as physical constraints for the dynamic IoT RNG engine.
FEATURE_RANGES = {
    "ambient_temp": (15.0, 45.0),      # deg C (RDSO standard operating range)
    "humidity": (30.0, 85.0),          # %
    "vibration_rms": (0.4, 2.2),        # RMS mm/s (Safe threshold is < 2.5 mm/s)
    "gauge_width": (1674.5, 1677.5),   # mm (Broad Gauge standard 1676mm ±3mm)
}

# Scenario context for healthy track monitoring
NOMINAL_SCENARIOS = [
    ("optimal_track_health", "Continuous telemetry indicates smooth rail alignment, nominal temperature, and stable ballast across corridor."),
    ("routine_patrol_nominal", "Routine high-speed passenger run; all onboard accelerometer and gauge laser sensors reporting within safety envelopes."),
    ("high_speed_clearance", "Mainline corridor sensors indicate excellent ride index, steady 25kV OHE contact, and minimal dynamic rail deflection."),
]

# Anomalous/degraded scenarios (30% chance for patrol IoT generation)
ANOMALOUS_SCENARIOS = [
    ("gauge_widening", "Post-inspection gauge deviation detected — ballast settling causing progressive gauge widening."),
    ("thermal_buckle_risk", "Rail temperature rising beyond safe limits — potential thermal buckling on exposed section."),
    ("high_vibration", "Elevated vibration RMS — possible rail joint damage or wheel flat impact on corrugated rail."),
    ("bearing_wear", "Periodic vibration pattern suggesting bearing degradation in track-side equipment."),
]


def _pick_nominal_scenario(source: str, destination: str):
    """Picks a healthy operational scenario description."""
    seed_str = f"{source}-{destination}-{random.random()}"
    idx = abs(hash(seed_str)) % len(NOMINAL_SCENARIOS)
    return NOMINAL_SCENARIOS[idx]


# ---------------------------------------------------------------------------
# Dynamic Physics-Based IoT RNG Engine (Offline & Real-Time Fallback)
# ---------------------------------------------------------------------------
def _generate_physics_iot_rng(source: str, destination: str):
    """
    Generates high-fidelity stochastic time-series IoT readings simulating
    a train passing over track sections with good / nominal condition.

    Uses correlated Brownian bridge & micro-vibration noise modeling:
    - Ambient Temperature: Smooth diurnal & thermal drift (22°C - 32°C).
    - Humidity: Inverse atmospheric correlation (45% - 68%).
    - Gauge Width: Sub-millimeter broad gauge tolerances (1675.80 - 1676.35 mm).
    - Vibration RMS: Stochastic accelerometer noise (0.60 - 1.35 mm/s, well < 2.5 mm/s).
    """
    flavour_name, flavour_desc = _pick_nominal_scenario(source, destination)
    logger.info(f"[simulation] Using Dynamic Physics-Based IoT RNG Engine for {source} -> {destination}")

    # Random baseline conditions for this route
    base_temp = random.uniform(25.0, 31.0)
    base_hum = random.uniform(48.0, 64.0)
    base_gauge = STANDARD_GAUGE_MM + random.uniform(-0.35, 0.25)
    base_vib = random.uniform(0.70, 1.15)

    # Ambient thermal drift rate across the 16 timesteps
    temp_drift_rate = random.uniform(-0.08, 0.12)
    gauge_micro_variation = random.uniform(-0.015, 0.015)

    readings = []
    current_vib = base_vib
    current_gauge = base_gauge

    for t in range(WINDOW_SIZE):
        # Correlated Brownian step for gauge width (retains track smoothness)
        current_gauge += gauge_micro_variation + random.gauss(0, 0.04)
        # Keep gauge within tight safe broad-gauge limits (1675.6 - 1676.5 mm)
        current_gauge = max(1675.60, min(1676.50, current_gauge))

        # Vibration: baseline + slight sinusoidal track harmonic + micro-tremor
        harmonic = 0.12 * math.sin(t * 0.45 + random.uniform(0, 1))
        current_vib = max(0.45, min(1.85, base_vib + harmonic + random.gauss(0, 0.08)))

        # Ambient temperature with smooth drift
        temp = base_temp + (temp_drift_rate * t) + random.gauss(0, 0.15)
        temp = max(18.0, min(38.0, temp))

        # Humidity with inverse thermal variance
        hum = base_hum - (0.3 * (temp - base_temp)) + random.gauss(0, 0.8)
        hum = max(35.0, min(80.0, hum))

        reading = {
            "ambient_temp": round(temp, 2),
            "humidity": round(hum, 2),
            "vibration_rms": round(current_vib, 3),
            "gauge_width": round(current_gauge, 2),
        }
        readings.append(reading)

    return readings, flavour_name, flavour_desc


def _generate_anomalous_physics_iot_rng(source: str, destination: str, specific_flavour: str = None):
    """Generate IoT readings with elevated risk values for patrol/defect simulation."""
    if specific_flavour:
        matching = [s for s in ANOMALOUS_SCENARIOS if s[0] == specific_flavour]
        if matching:
            flavour_name, flavour_desc = matching[0]
        else:
            flavour_name, flavour_desc = specific_flavour, f"Simulated condition: {specific_flavour}"
    else:
        flavour_idx = random.randint(0, len(ANOMALOUS_SCENARIOS) - 1)
        flavour_name, flavour_desc = ANOMALOUS_SCENARIOS[flavour_idx]

    base_temp = random.uniform(30.0, 38.0)
    base_hum = random.uniform(50.0, 75.0)
    base_gauge = STANDARD_GAUGE_MM + random.uniform(0.5, 3.5)
    base_vib = random.uniform(1.8, 3.5)

    if flavour_name in ("thermal_buckle", "thermal_buckle_risk"):
        flavour_name = "thermal_buckle_risk"
        base_temp = random.uniform(43.0, 52.0)
        base_vib = random.uniform(1.2, 2.0)
        base_gauge = STANDARD_GAUGE_MM + random.uniform(-0.2, 0.5)
    elif flavour_name in ("high_vibration", "bearing_wear"):
        base_vib = random.uniform(3.2, 5.8)
        base_temp = random.uniform(25.0, 35.0)
        base_gauge = STANDARD_GAUGE_MM + random.uniform(-0.3, 0.3)
    elif flavour_name == "gauge_widening":
        base_gauge = STANDARD_GAUGE_MM + random.uniform(3.5, 6.5)
        base_vib = random.uniform(1.8, 3.2)

    readings = []
    for t in range(WINDOW_SIZE):
        gauge = base_gauge + random.gauss(0, 0.15)
        vib = max(0.5, base_vib + 0.15 * math.sin(t * 0.6) + random.gauss(0, 0.2))
        temp = base_temp + random.gauss(0, 0.3)
        hum = base_hum + random.gauss(0, 1.2)
        readings.append({
            "ambient_temp": round(temp, 2),
            "humidity": round(max(20.0, min(95.0, hum)), 2),
            "vibration_rms": round(vib, 3),
            "gauge_width": round(gauge, 2),
        })
    return readings, flavour_name, flavour_desc

# ---------------------------------------------------------------------------
# xAI Grok API backend
# ---------------------------------------------------------------------------
def _generate_grok(source: str, destination: str, api_key: str, model: str = None):
    flavour_name, flavour_desc = _pick_nominal_scenario(source, destination)
    prompt = _build_llm_prompt(source, destination, flavour_desc)

    model_name = model or os.environ.get("GROK_MODEL") or os.environ.get("XAI_MODEL") or "grok-3"

    resp = requests.post(
        "https://api.x.ai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a realistic railway IoT telemetry simulation generator. You must output only a valid JSON array of sensor readings as requested."
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.4,
        },
        timeout=20,
    )
    if resp.status_code != 200:
        logger.warning(f"[simulation] Grok API returned HTTP {resp.status_code}: {resp.text}")
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    readings = _parse_llm_json(text)
    return readings, flavour_name, flavour_desc


# ---------------------------------------------------------------------------
# Google Gemini API backend
# ---------------------------------------------------------------------------
def _generate_gemini(source: str, destination: str, api_key: str, model: str = None):
    flavour_name, flavour_desc = _pick_nominal_scenario(source, destination)
    prompt = _build_llm_prompt(source, destination, flavour_desc)

    model_name = model or os.environ.get("GEMINI_MODEL") or "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "application/json",
        },
    }

    resp = requests.post(url, json=payload, timeout=20)
    if resp.status_code != 200:
        logger.warning(f"[simulation] Gemini API returned HTTP {resp.status_code}: {resp.text}")
    resp.raise_for_status()
    data = resp.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError("No candidates returned from Gemini API")

    text = candidates[0]["content"]["parts"][0]["text"]
    readings = _parse_llm_json(text)
    return readings, flavour_name, flavour_desc


# ---------------------------------------------------------------------------
# Anthropic API backend
# ---------------------------------------------------------------------------
def _generate_anthropic(source: str, destination: str, api_key: str):
    flavour_name, flavour_desc = _pick_nominal_scenario(source, destination)
    prompt = _build_llm_prompt(source, destination, flavour_desc)

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    readings = _parse_llm_json(text)
    return readings, flavour_name, flavour_desc


# ---------------------------------------------------------------------------
# OpenAI-compatible backend (also covers local Ollama)
# ---------------------------------------------------------------------------
def _generate_openai_compatible(source: str, destination: str, api_key: str):
    flavour_name, flavour_desc = _pick_nominal_scenario(source, destination)
    prompt = _build_llm_prompt(source, destination, flavour_desc)

    base_url = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
    model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    resp = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    readings = _parse_llm_json(text)
    return readings, flavour_name, flavour_desc


# ---------------------------------------------------------------------------
# Shared LLM prompt + JSON parsing helpers
# ---------------------------------------------------------------------------
def _build_llm_prompt(source: str, destination: str, flavour_desc: str) -> str:
    return f"""You are simulating live onboard IoT track telemetry sensors for an Indian Railways passenger express route from "{source}" to "{destination}".
Generate exactly {WINDOW_SIZE} consecutive time-series sensor readings representing optimal, healthy track condition with zero defects.

Scenario: {flavour_desc}

Physical Sensor Ranges for GOOD/NOMINAL Track Condition:
    - ambient_temp: degrees Celsius (22.0 to 34.0 deg C, smooth continuous thermal curve)
    - humidity: relative humidity percentage (45.0 to 70.0%)
    - vibration_rms: track accelerometer RMS vibration (0.50 to 1.35 mm/s, well below safety limit 2.50 mm/s)
    - gauge_width: millimetres broad gauge (1675.80 to 1676.35 mm, centered around standard 1676.0 mm)

Respond ONLY with a valid JSON array containing exactly {WINDOW_SIZE} objects:
[
  {{"ambient_temp": 27.5, "humidity": 56.2, "vibration_rms": 0.88, "gauge_width": 1676.05}},
  ...
]
"""


def _parse_llm_json(text: str):
    """Extract a JSON array from LLM output, tolerating markdown fences."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON array found in LLM response")

    parsed = json.loads(match.group(0))
    if not isinstance(parsed, list) or len(parsed) == 0:
        raise ValueError("LLM response was not a non-empty JSON array")

    required = ["ambient_temp", "humidity", "vibration_rms", "gauge_width"]
    cleaned = []
    for item in parsed[:WINDOW_SIZE]:
        row = {}
        for key in required:
            row[key] = float(item[key])
        cleaned.append(row)

    # Pad if needed
    while len(cleaned) < WINDOW_SIZE:
        last = dict(cleaned[-1])
        for k in last:
            last[k] = round(last[k] + random.gauss(0, 0.02), 3)
        cleaned.append(last)

    return cleaned


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def generate_journey(source: str, destination: str, patrol_mode: bool = False, condition: str = "auto"):
    """
    Returns (readings, flavour_name, flavour_description, source_used).
    source_used is "grok", "gemini", "anthropic", "openai_compatible", "ollama", "physics_iot_rng",
    or "physics_iot_rng_anomalous".
    """
    condition = (condition or "auto").strip().lower()

    # If an explicit anomaly condition is requested
    if condition in ("thermal_buckle", "thermal_buckle_risk", "gauge_widening", "high_vibration", "bearing_wear", "anomaly"):
        flavour = None if condition == "anomaly" else condition
        readings, fn, fd = _generate_anomalous_physics_iot_rng(source, destination, specific_flavour=flavour)
        return readings, fn, fd, "physics_iot_rng_anomalous"

    # If explicit nominal is requested
    if condition == "nominal":
        readings, fn, fd = _generate_physics_iot_rng(source, destination)
        return readings, fn, fd, "physics_iot_rng"

    # In patrol mode, 30% chance of anomalous readings
    if patrol_mode and random.random() < 0.30:
        readings, fn, fd = _generate_anomalous_physics_iot_rng(source, destination)
        return readings, fn, fd, "physics_iot_rng_anomalous"

    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    grok_key = os.environ.get("GROK_API_KEY") or os.environ.get("XAI_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    if gemini_key:
        try:
            readings, flavour_name, flavour_desc = _generate_gemini(source, destination, gemini_key)
            return readings, flavour_name, flavour_desc, "gemini"
        except Exception as e:
            logger.warning(f"[simulation] Gemini generation failed, falling back: {e}")

    if grok_key:
        try:
            readings, flavour_name, flavour_desc = _generate_grok(source, destination, grok_key)
            return readings, flavour_name, flavour_desc, "grok"
        except Exception as e:
            logger.warning(f"[simulation] Grok generation failed, falling back: {e}")

    if anthropic_key:
        try:
            readings, flavour_name, flavour_desc = _generate_anthropic(source, destination, anthropic_key)
            return readings, flavour_name, flavour_desc, "anthropic"
        except Exception as e:
            logger.warning(f"[simulation] Anthropic generation failed, falling back: {e}")

    if openai_key:
        try:
            readings, flavour_name, flavour_desc = _generate_openai_compatible(source, destination, openai_key)
            return readings, flavour_name, flavour_desc, "openai_compatible"
        except Exception as e:
            logger.warning(f"[simulation] OpenAI-compatible generation failed, falling back: {e}")

    # Attempt local Ollama
    if os.environ.get("OPENAI_API_BASE") and "localhost" in os.environ.get("OPENAI_API_BASE", ""):
        try:
            readings, flavour_name, flavour_desc = _generate_openai_compatible(source, destination, "ollama")
            return readings, flavour_name, flavour_desc, "ollama"
        except Exception as e:
            logger.warning(f"[simulation] Ollama local LLM generation failed, falling back: {e}")

    # High-fidelity physics-based IoT RNG generator (always available offline)
    readings, flavour_name, flavour_desc = _generate_physics_iot_rng(source, destination)
    return readings, flavour_name, flavour_desc, "physics_iot_rng"

