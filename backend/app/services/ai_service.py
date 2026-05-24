"""
PulseDebug AI — Gemini AI Analysis Service
============================================
File: backend/app/services/ai_service.py
Purpose:
    Orchestrates all calls to the Google Gemini API for incident explanation.

    Fallback chain:
        1. Gemini 2.5 Flash          (primary)
        2. Gemini 2.0 Flash-Lite     (fallback)
        3. Statistical summary only  (graceful degradation)

    Automatically detects HTTP 429 quota-exhaustion and promotes fallback.
    If fallback also exhausts, AI analysis is disabled and a clear message
    is returned — the dashboard never crashes.

Author: PulseDebug AI Hackathon Team
"""

import json
import re
import httpx
from typing import Optional, Tuple

from app.core.config import settings

# Module-level quota state
_primary_exhausted: bool = False
_fallback_exhausted: bool = False


def _active_model() -> Optional[str]:
    if not _primary_exhausted:
        return settings.GEMINI_PRIMARY_MODEL
    if not _fallback_exhausted:
        return settings.GEMINI_FALLBACK_MODEL
    return None


_SYSTEM_PROMPT = """
You are PulseDebug AI, an expert API incident triage assistant for engineering teams.
Analyse the incident data provided and return a JSON object with exactly these keys:

{
  "incident_summary": "<2-3 sentence plain-English summary of what happened>",
  "likely_cause": "<most probable root cause, 1-2 sentences>",
  "recommended_checks": ["<check 1>", "<check 2>", "<check 3>", "<check 4>"],
  "investigation_priority": "<Critical | High | Medium | Low>",
  "confidence_labels": {
    "likely_cause": "<High Likelihood | Moderate Likelihood | Needs Investigation>",
    "deployment_related": "<High Likelihood | Moderate Likelihood | Needs Investigation | Not Related>"
  },
  "debugging_steps": ["<step 1>", "<step 2>", "<step 3>"]
}

Rules:
- Do NOT invent percentage confidence scores.
- Use only the qualitative labels specified above.
- Keep every field concise and actionable.
- Think like a senior SRE, not a marketing copywriter.
- Return ONLY the JSON object — no markdown fences, no preamble.
""".strip()


def _build_prompt(incident: dict, logs_summary: dict, deployment: Optional[dict]) -> str:
    data = {
        "incident": {
            "title":              incident.get("title"),
            "service":            incident.get("service"),
            "endpoint":           incident.get("endpoint"),
            "error_signature":    incident.get("error_signature"),
            "severity":           incident.get("severity"),
            "occurrence_count":   incident.get("occurrence_count"),
            "first_detected":     incident.get("first_detected"),
            "last_seen":          incident.get("last_seen"),
            "deployment_related": bool(incident.get("deployment_related")),
        },
        "log_statistics":  logs_summary,
        "deployment_event": deployment,
    }
    return f"Incident data:\n{json.dumps(data, indent=2)}"


async def _call_gemini(model: str, prompt: str) -> dict:
    url = (
        f"{settings.GEMINI_API_URL}/{model}:generateContent"
        f"?key={settings.GEMINI_API_KEY}"
    )
    payload = {
        "system_instruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


def _extract_text(gemini_response: dict) -> str:
    try:
        return gemini_response["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Unexpected Gemini response shape: {e}") from e


def _parse_json_from_text(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    return json.loads(text)


async def analyse_incident(
    incident: dict,
    logs_summary: dict,
    deployment: Optional[dict] = None,
) -> Tuple[Optional[dict], str]:
    """
    Run AI analysis on an incident.
    Returns (analysis_dict, model_name) or (None, reason_string).
    """
    global _primary_exhausted, _fallback_exhausted

    if not settings.GEMINI_API_KEY:
        return None, "no_api_key"

    prompt = _build_prompt(incident, logs_summary, deployment)

    if _active_model() is None:
        return None, "quota_exhausted"

    for attempt in range(2):
        model = _active_model()
        if model is None:
            return None, "quota_exhausted"

        try:
            raw      = await _call_gemini(model, prompt)
            text     = _extract_text(raw)
            analysis = _parse_json_from_text(text)
            return analysis, model

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                if model == settings.GEMINI_PRIMARY_MODEL:
                    print("[AI] Primary quota exhausted — switching to fallback")
                    _primary_exhausted = True
                else:
                    print("[AI] Fallback quota exhausted — disabling AI")
                    _fallback_exhausted = True
                continue
            else:
                return None, f"error:{e.response.status_code}"

        except Exception as exc:
            return None, f"error:{str(exc)}"

    return None, "quota_exhausted"


def ai_status() -> dict:
    model = _active_model()
    return {
        "available":          model is not None,
        "active_model":       model,
        "primary_exhausted":  _primary_exhausted,
        "fallback_exhausted": _fallback_exhausted,
        "message": (
            "AI analysis active"
            if model
            else "AI quota reached. Showing statistical incident analysis only."
        ),
    }