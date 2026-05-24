"""
PulseDebug AI — Configuration
================================
File: backend/app/core/config.py
Purpose:
    Centralised application settings loaded from environment variables.
    Uses python-dotenv to explicitly load the .env file from the backend
    directory so all keys are available before Settings is instantiated.
    This fixes the issue where GEMINI_API_KEY was not being picked up
    even though the .env file existed.

Author: PulseDebug AI Hackathon Team
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass

# ------------------------------------------------------------------
# Explicitly load the .env file
# Looks for .env in the backend/ directory (two levels up from this file)
# This file is at: backend/app/core/config.py
# So parent.parent.parent = backend/
# ------------------------------------------------------------------

_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

print(f"[Config] Loading .env from: {_env_path}")
print(f"[Config] .env file exists: {_env_path.exists()}")
print(f"[Config] GEMINI_API_KEY loaded: {'Yes' if os.getenv('GEMINI_API_KEY') else 'NO - KEY MISSING'}")


@dataclass
class Settings:
    # ------------------------------------------------------------------
    # Gemini / AI settings
    # ------------------------------------------------------------------
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    GEMINI_PRIMARY_MODEL: str = os.getenv(
        "GEMINI_PRIMARY_MODEL", "gemini-2.5-flash"
    )

    GEMINI_FALLBACK_MODEL: str = os.getenv(
        "GEMINI_FALLBACK_MODEL", "gemini-2.0-flash-lite"
    )

    GEMINI_API_URL: str = (
        "https://generativelanguage.googleapis.com/v1beta/models"
    )

    # ------------------------------------------------------------------
    # Anomaly detection thresholds
    # ------------------------------------------------------------------
    LATENCY_SPIKE_MULTIPLIER: float = float(
        os.getenv("LATENCY_SPIKE_MULTIPLIER", "3.0")
    )

    LATENCY_SPIKE_FLOOR_MS: int = int(
        os.getenv("LATENCY_SPIKE_FLOOR_MS", "500")
    )

    ERROR_RATE_THRESHOLD: float = float(
        os.getenv("ERROR_RATE_THRESHOLD", "0.3")
    )

    STATS_WINDOW: int = int(os.getenv("STATS_WINDOW", "20"))

    # ------------------------------------------------------------------
    # Clustering settings
    # ------------------------------------------------------------------
    CLUSTER_TIME_WINDOW_SEC: int = int(
        os.getenv("CLUSTER_TIME_WINDOW_SEC", "300")
    )

    CLUSTER_MIN_OCCURRENCES: int = int(
        os.getenv("CLUSTER_MIN_OCCURRENCES", "2")
    )

    # ------------------------------------------------------------------
    # Deployment correlation
    # ------------------------------------------------------------------
    DEPLOYMENT_CORRELATION_WINDOW_SEC: int = int(
        os.getenv("DEPLOYMENT_CORRELATION_WINDOW_SEC", "600")
    )

    # ------------------------------------------------------------------
    # Simulator settings
    # ------------------------------------------------------------------
    SIMULATOR_INTERVAL_SEC: float = float(
        os.getenv("SIMULATOR_INTERVAL_SEC", "2.0")
    )

    SCENARIO_INJECTION_INTERVAL_SEC: int = int(
        os.getenv("SCENARIO_INJECTION_INTERVAL_SEC", "60")
    )


settings = Settings()