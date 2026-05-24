"""
PulseDebug AI — Anomaly Detector (Deterministic)
==================================================
File: backend/app/services/anomaly_detector.py
Purpose:
    Implements rule-based and statistical anomaly detection.
    This module NEVER calls an AI model — detection is fully offline
    and deterministic, ensuring the dashboard works even when Gemini
    quota is exhausted.

    Detection strategies:
        1. Latency spike   — rolling average per endpoint × multiplier
        2. Error-rate surge — sliding window error rate threshold
        3. Status-code irregularity — 5xx always flagged, 4xx pattern-based
        4. Burst detection — too many requests to one endpoint in short window

Author: PulseDebug AI Hackathon Team
"""

import sqlite3
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from typing import Dict, Deque

from app.core.config import settings


class _EndpointStats:
    """Maintains a rolling window of latency and status-code observations."""

    def __init__(self, window: int = 20):
        self.window = window
        self.latencies: Deque[int] = deque(maxlen=window)
        self.statuses: Deque[int] = deque(maxlen=window)

    def add(self, latency_ms: int, status_code: int):
        self.latencies.append(latency_ms)
        self.statuses.append(status_code)

    @property
    def avg_latency(self) -> float:
        return sum(self.latencies) / len(self.latencies) if self.latencies else 0

    @property
    def error_rate(self) -> float:
        if not self.statuses:
            return 0.0
        return sum(1 for s in self.statuses if s >= 400) / len(self.statuses)

    @property
    def has_enough_history(self) -> bool:
        return len(self.latencies) >= 5


_stats: Dict[str, _EndpointStats] = defaultdict(
    lambda: _EndpointStats(window=settings.STATS_WINDOW)
)
_burst_tracker: Dict[str, deque] = defaultdict(lambda: deque(maxlen=50))
BURST_WINDOW_SEC = 30
BURST_THRESHOLD = 8


class AnomalyDetector:
    """Stateful anomaly detector. Call evaluate() for each new log event."""

    def evaluate(self, conn: sqlite3.Connection, *, log_id: int, service: str,
                 endpoint: str, status_code: int, latency_ms: int) -> bool:
        """Evaluate a single event. Returns True if anomalous."""
        key = f"{service}:{endpoint}"
        stats = _stats[key]
        is_anomaly = False

        # 1. Status-code check
        if status_code >= 500:
            is_anomaly = True
        elif status_code >= 400:
            if stats.error_rate > 0.2 and stats.has_enough_history:
                is_anomaly = True

        # 2. Latency spike
        if (stats.has_enough_history
                and latency_ms > settings.LATENCY_SPIKE_FLOOR_MS
                and latency_ms > stats.avg_latency * settings.LATENCY_SPIKE_MULTIPLIER):
            is_anomaly = True

        # 3. Error-rate surge (update stats first)
        stats.add(latency_ms, status_code)
        if (stats.has_enough_history
                and stats.error_rate >= settings.ERROR_RATE_THRESHOLD):
            is_anomaly = True

        # 4. Burst detection
        now = datetime.now(timezone.utc)
        tracker = _burst_tracker[key]
        tracker.append(now)
        cutoff = now - timedelta(seconds=BURST_WINDOW_SEC)
        while tracker and tracker[0] < cutoff:
            tracker.popleft()
        if len(tracker) >= BURST_THRESHOLD:
            is_anomaly = True

        if is_anomaly:
            conn.execute(
                "UPDATE api_logs SET is_anomaly = 1 WHERE id = ?", (log_id,)
            )
            conn.commit()

        return is_anomaly

    def get_endpoint_stats(self) -> dict:
        return {
            key: {
                "avg_latency_ms": round(s.avg_latency, 1),
                "error_rate": round(s.error_rate, 3),
                "sample_count": len(s.latencies),
            }
            for key, s in _stats.items()
        }