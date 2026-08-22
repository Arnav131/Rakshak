# backend/simulation/generator.py
"""
Rakshak — Simulation Scenario Generator
===========================================
Generates a realistic 16-reading sensor journey (ambient_temp, humidity,
vibration_rms, gauge_width) between a source and destination station,
"in the style of" the real Rakshak massive dataset.

Three backends, tried in this order:
    1. Anthropic API        (ANTHROPIC_API_KEY env var set)
    2. OpenAI-compatible API (OPENAI_API_KEY env var set — this also
       covers a locally-running Llama 3 served via Ollama's OpenAI-
       compatible endpoint, e.g. OPENAI_API_BASE=http://localhost:11434/v1)
    3. Local rule-based fallback (no API key needed — always works,
       so the demo never breaks if there's no internet/API key at
       judging time)

Output is always a list of exactly WINDOW_SIZE dicts:
    [{"ambient_temp": .., "humidity": .., "vibration_rms": .., "gauge_width": ..}, ...]
"""

import json
import logging
import os
import random
import re

import requests

logger = logging.getLogger("rakshak.simulation.generator")

WINDOW_SIZE = 16
STANDARD_GAUGE_MM = 1676.0

# Dataset-grounded typical ranges — used both as a fallback generator AND
# as grounding context fed to the LLM so it stays "in distribution" instead
# of hallucinating physically implausible values.
FEATURE_RANGES = {
    "ambient_temp": (10.0, 50.0),      # deg C
    "humidity": (20.0, 100.0),          # %
    "vibration_rms": (0.1, 9.0),        # RMS
    "gauge_width": (1670.0, 1690.0),    # mm (standard gauge 1676mm)
}

# A handful of scenario "flavours" to bias the generated journey toward —
# picked (semi-)randomly per run so different demo runs look different.
SCENARIO_FLAVOURS = [
    ("normal", "Track conditions remain stable and within safe limits for the entire journey."),
    ("gauge_widening", "Gauge width gradually widens over the journey due to ballast degradation."),
    ("thermal_stress", "Ambient temperature climbs steadily, raising thermal buckling risk near the end."),
    ("vibration_spike", "Vibration RMS increases sharply partway through, suggesting a developing rail defect."),
    ("normal", "Track conditions remain stable and within safe limits for the entire journey."),
]


def _pick_flavour(source: str, destination: str):
    """Deterministic-ish pick based on station names + a random component,
    so results vary between runs but aren't pure noise."""
    seed_str = f"{source}-{destination}-{random.random()}"
    idx = abs(hash(seed_str)) % len(SCENARIO_FLAVOURS)
    return SCENARIO_FLAVOURS[idx]


# ---------------------------------------------------------------------------
# Fallback: local rule-based generator (always available, no dependencies)
# ---------------------------------------------------------------------------
def _generate_local(source: str, destination: str):
    flavour_name, flavour_desc = _pick_flavour(source, destination)
    logger.info(f"[simulation] Using LOCAL generator, flavour={flavour_name}")

    base_temp = random.uniform(22, 38)
    base_hum = random.uniform(35, 75)
    base_vib = random.uniform(0.3, 2.0)
    base_gauge = STANDARD_GAUGE_MM + random.uniform(-2, 2)

    temp_trend = vib_trend = gauge_trend = 0.0
    if flavour_name == "gauge_widening":
        gauge_trend = random.uniform(0.5, 1.1)
    elif flavour_name == "thermal_stress":
        temp_trend = random.uniform(0.8, 1.6)
        gauge_trend = random.uniform(0.1, 0.3)
    elif flavour_name == "vibration_spike":
        vib_trend = random.uniform(0.4, 0.9)

    readings = []
    for t in range(WINDOW_SIZE):
        reading = {
            "ambient_temp": round(base_temp + temp_trend * t + random.gauss(0, 0.6), 2),
            "humidity": round(min(100, max(0, base_hum + random.gauss(0, 3))), 2),
            "vibration_rms": round(max(0, base_vib + vib_trend * t + random.gauss(0, 0.25)), 3),
            "gauge_width": round(base_gauge + gauge_trend * t + random.gauss(0, 0.4), 2),
        }
        readings.append(reading)

    return readings, flavour_name, flavour_desc


# ---------------------------------------------------------------------------
# Anthropic API backend
# ---------------------------------------------------------------------------
def _generate_anthropic(source: str, destination: str, api_key: str):
    flavour_name, flavour_desc = _pick_flavour(source, destination)
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
        timeout=25,
    )
    resp.raise_for_status()
    data = resp.json()
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    readings = _parse_llm_json(text)
    return readings, flavour_name, flavour_desc


# ---------------------------------------------------------------------------
# OpenAI-compatible backend (also works for local Llama3 via Ollama)
# ---------------------------------------------------------------------------
def _generate_openai_compatible(source: str, destination: str, api_key: str):
    flavour_name, flavour_desc = _pick_flavour(source, destination)
    prompt = _build_llm_prompt(source, destination, flavour_desc)

    base_url = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
    model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    # For local Llama3 via Ollama, set:
    #   OPENAI_API_BASE=http://localhost:11434/v1
    #   OPENAI_API_KEY=ollama   (Ollama ignores the key but requests lib needs one)
    #   OPENAI_MODEL=llama3

    resp = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.8,
        },
        timeout=25,
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
    return f"""You are generating a SYNTHETIC railway sensor test dataset for a
hackathon demo. This is not real sensor data — it is a plausible simulation
"in the style of" a real dataset, used to test a prediction model.

A train is travelling from "{source}" to "{destination}". Generate exactly
{WINDOW_SIZE} consecutive sensor readings representing this journey, one
reading per timestep, in chronological order.

Scenario to simulate: {flavour_desc}

Each reading must have these 4 fields with realistic railway sensor values:
    ambient_temp   : degrees Celsius, realistic range 10 to 50
    humidity       : percent, realistic range 20 to 100
    vibration_rms  : RMS units, realistic range 0.1 to 9.0 (higher = rougher track)
    gauge_width    : millimetres, realistic range 1670 to 1690 (standard gauge is 1676mm)

Respond with ONLY a raw JSON array of exactly {WINDOW_SIZE} objects, no
markdown fences, no explanation, no extra text. Example format:
[{{"ambient_temp": 28.4, "humidity": 55.2, "vibration_rms": 1.1, "gauge_width": 1676.3}}, ...]
"""


def _parse_llm_json(text: str):
    """Extract a JSON array from LLM output, tolerating stray markdown fences
    or leading/trailing text."""
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

    # Pad if the LLM returned fewer than WINDOW_SIZE rows, by repeating the
    # last one with tiny jitter (keeps the pipeline's window size contract).
    while len(cleaned) < WINDOW_SIZE:
        last = dict(cleaned[-1])
        for k in last:
            last[k] = round(last[k] + random.gauss(0, 0.05), 3)
        cleaned.append(last)

    return cleaned


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def generate_journey(source: str, destination: str):
    """
    Returns (readings, flavour_name, flavour_description, source_used).
    source_used tells the caller/frontend which backend actually produced
    the data: "anthropic", "openai_compatible", "ollama", or "local".
    """
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

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

    # Attempt local LLM (llama3 via Ollama)
    try:
        # Override environment defaults for local Ollama just in case
        if not os.environ.get("OPENAI_API_BASE"):
            os.environ["OPENAI_API_BASE"] = "http://localhost:11434/v1"
        if not os.environ.get("OPENAI_MODEL"):
            os.environ["OPENAI_MODEL"] = "llama3"
            
        readings, flavour_name, flavour_desc = _generate_openai_compatible(source, destination, "ollama")
        return readings, flavour_name, flavour_desc, "ollama"
    except Exception as e:
        logger.warning(f"[simulation] Ollama local LLM generation failed, falling back: {e}")

    readings, flavour_name, flavour_desc = _generate_local(source, destination)
    return readings, flavour_name, flavour_desc, "local"
