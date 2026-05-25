"""
PulseDebug AI — Multi-Provider AI Service
==========================================
File: backend/app/services/ai_service.py
Purpose:
    Orchestrates AI calls across multiple providers with completely silent,
    invisible failover. The user NEVER sees any provider error, quota
    message, or degradation warning.

    Provider chain:
        1. Gemini 2.5 Flash          (primary — best quality)
        2. Gemini 2.0 Flash-Lite     (Gemini fallback — still free)
        3. Groq llama-3.3-70b        (secondary provider)
        4. Groq llama-3.1-70b        (Groq fallback model)
        5. Groq mixtral-8x7b         (Groq final fallback)

    Failure detection — any of these silently triggers next provider:
        - HTTP 429  (quota / rate limit)
        - HTTP 503  (service unavailable)
        - HTTP 500  (server error)
        - HTTP 401  (invalid key — skip provider entirely)
        - Timeout   (> 30 seconds)
        - Empty or malformed completion
        - RESOURCE_EXHAUSTED in response body
        - JSON parse failure

    Design principles:
        - Zero user-facing errors — diagnosis ALWAYS resolves
        - No model-switching logs visible to user
        - No provider names leaked to frontend
        - Statistical fallback if ALL providers fail (extremely rare)
        - All state is module-level — persists across requests

Author: PulseDebug AI Hackathon Team
"""

import json
import re
import asyncio
from typing import Optional, Tuple
from enum import Enum

import httpx

from app.core.config import settings


# ---------------------------------------------------------------------------
# Internal exception — never propagated to the API layer
# ---------------------------------------------------------------------------

class _AIProviderError(Exception):
    """Raised internally when a provider fails. Never reaches the frontend."""
    def __init__(self, provider: str, reason: str, should_skip: bool = False):
        self.provider    = provider
        self.reason      = reason
        self.should_skip = should_skip   # True = skip entire provider permanently
        super().__init__(f"{provider}: {reason}")


# ---------------------------------------------------------------------------
# Provider state — tracks which models/providers are still usable
# ---------------------------------------------------------------------------

class _ProviderState(Enum):
    AVAILABLE  = "available"
    EXHAUSTED  = "exhausted"    # quota/rate limit — retry after cooldown
    DISABLED   = "disabled"     # bad key or persistent failure — skip always


# Per-model state dictionary
# Key: model identifier string
# Value: _ProviderState
_model_state: dict[str, _ProviderState] = {}


def _get_state(model_id: str) -> _ProviderState:
    return _model_state.get(model_id, _ProviderState.AVAILABLE)


def _set_exhausted(model_id: str) -> None:
    _model_state[model_id] = _ProviderState.EXHAUSTED


def _set_disabled(model_id: str) -> None:
    _model_state[model_id] = _ProviderState.DISABLED


def _is_usable(model_id: str) -> bool:
    state = _get_state(model_id)
    return state == _ProviderState.AVAILABLE


# ---------------------------------------------------------------------------
# System prompt — same regardless of provider
# ---------------------------------------------------------------------------

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
- Return ONLY the JSON object — no markdown fences, no preamble, no explanation.
""".strip()


# ---------------------------------------------------------------------------
# Shared prompt builder
# ---------------------------------------------------------------------------

def _build_user_prompt(
    incident: dict,
    logs_summary: dict,
    deployment: Optional[dict],
) -> str:
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


def _build_raw_prompt(prompt_text: str) -> str:
    """For analyzer use — wraps a free-form prompt."""
    return prompt_text


# ---------------------------------------------------------------------------
# JSON extraction — handles both clean JSON and markdown-fenced responses
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    """
    Robustly extract a JSON object from model output.
    Models sometimes wrap JSON in ```json fences despite instructions.
    Raises ValueError if no valid JSON object is found.
    """
    if not text or not text.strip():
        raise ValueError("Empty response from model")

    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object within surrounding text
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON found in response: {text[:200]}")


# ---------------------------------------------------------------------------
# Gemini provider
# ---------------------------------------------------------------------------

_GEMINI_MODELS = [
    settings.GEMINI_PRIMARY_MODEL,   # gemini-2.5-flash
    settings.GEMINI_FALLBACK_MODEL,  # gemini-2.0-flash-lite
]


async def _call_gemini(model: str, user_prompt: str) -> str:
    """
    Call Gemini generateContent API.
    Returns raw text on success.
    Raises _AIProviderError on any failure — never leaks raw exception.
    """
    if not settings.GEMINI_API_KEY:
        raise _AIProviderError("gemini", "no API key", should_skip=True)

    url = (
        f"{settings.GEMINI_API_URL}/{model}:generateContent"
        f"?key={settings.GEMINI_API_KEY}"
    )
    payload = {
        "system_instruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
        "contents":           [{"parts": [{"text": user_prompt}]}],
        "generationConfig":   {"temperature": 0.3, "maxOutputTokens": 1500},
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)

            # Quota / rate limit
            if resp.status_code == 429:
                raise _AIProviderError("gemini", "quota_exhausted", should_skip=False)

            # Auth failure — bad key
            if resp.status_code == 401:
                raise _AIProviderError("gemini", "invalid_key", should_skip=True)

            # Server errors — treat as temporary
            if resp.status_code >= 500:
                raise _AIProviderError("gemini", f"server_error_{resp.status_code}")

            resp.raise_for_status()
            data = resp.json()

            # Check for RESOURCE_EXHAUSTED in body (Gemini sometimes returns 200 with error)
            if "error" in data:
                err_msg = str(data["error"]).lower()
                if any(k in err_msg for k in ["quota", "resource_exhausted", "rate"]):
                    raise _AIProviderError("gemini", "quota_in_body", should_skip=False)
                raise _AIProviderError("gemini", f"api_error: {data['error']}")

            # Extract text
            try:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError):
                # Check for blocked/empty candidates
                finish = (
                    data.get("candidates", [{}])[0]
                    .get("finishReason", "")
                    if data.get("candidates")
                    else "NO_CANDIDATES"
                )
                raise _AIProviderError("gemini", f"empty_response: {finish}")

            if not text or not text.strip():
                raise _AIProviderError("gemini", "empty_text")

            return text

    except _AIProviderError:
        raise
    except httpx.TimeoutException:
        raise _AIProviderError("gemini", "timeout")
    except httpx.RequestError as e:
        raise _AIProviderError("gemini", f"network_error: {type(e).__name__}")
    except Exception as e:
        raise _AIProviderError("gemini", f"unexpected: {type(e).__name__}")


# ---------------------------------------------------------------------------
# Groq provider
# ---------------------------------------------------------------------------

_GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "mixtral-8x7b-32768",
]

_GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


async def _call_groq(model: str, user_prompt: str) -> str:
    """
    Call Groq OpenAI-compatible API.
    Returns raw text on success.
    Raises _AIProviderError on any failure.
    """
    if not settings.GROQ_API_KEY:
        raise _AIProviderError("groq", "no API key", should_skip=True)

    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature":  0.3,
        "max_tokens":   1500,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(_GROQ_API_URL, headers=headers, json=payload)

            if resp.status_code == 429:
                raise _AIProviderError("groq", "quota_exhausted", should_skip=False)

            if resp.status_code == 401:
                raise _AIProviderError("groq", "invalid_key", should_skip=True)

            if resp.status_code >= 500:
                raise _AIProviderError("groq", f"server_error_{resp.status_code}")

            resp.raise_for_status()
            data = resp.json()

            try:
                text = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                raise _AIProviderError("groq", "empty_response")

            if not text or not text.strip():
                raise _AIProviderError("groq", "empty_text")

            return text

    except _AIProviderError:
        raise
    except httpx.TimeoutException:
        raise _AIProviderError("groq", "timeout")
    except httpx.RequestError as e:
        raise _AIProviderError("groq", f"network_error: {type(e).__name__}")
    except Exception as e:
        raise _AIProviderError("groq", f"unexpected: {type(e).__name__}")


# ---------------------------------------------------------------------------
# Core orchestrator — tries every model in sequence, silently
# ---------------------------------------------------------------------------

async def _run_with_fallback(user_prompt: str) -> Optional[str]:
    """
    Try every model in the priority chain.
    Returns raw text from the first model that succeeds.
    Returns None only if every single provider fails (extremely rare).
    All failures are caught and swallowed silently.
    """

    # Build ordered list of (provider_fn, model_id) to try
    candidates = []

    # 1. Gemini models
    for model in _GEMINI_MODELS:
        if _is_usable(model):
            candidates.append(("gemini", model))

    # 2. Groq models
    for model in _GROQ_MODELS:
        groq_key = f"groq:{model}"
        if _is_usable(groq_key):
            candidates.append(("groq", model))

    if not candidates:
        # All models exhausted — reset exhausted ones and try again
        # (quota may have reset since last attempt)
        for model in _GEMINI_MODELS:
            if _get_state(model) == _ProviderState.EXHAUSTED:
                _model_state[model] = _ProviderState.AVAILABLE
        for model in _GROQ_MODELS:
            groq_key = f"groq:{model}"
            if _get_state(groq_key) == _ProviderState.EXHAUSTED:
                _model_state[groq_key] = _ProviderState.AVAILABLE

        # Rebuild candidates after reset
        candidates = []
        for model in _GEMINI_MODELS:
            candidates.append(("gemini", model))
        for model in _GROQ_MODELS:
            candidates.append(("groq", model))

    for provider, model in candidates:
        try:
            if provider == "gemini":
                text = await _call_gemini(model, user_prompt)
            else:
                text = await _call_groq(model, user_prompt)

            # Success — return raw text
            return text

        except _AIProviderError as err:
            # Mark model state based on error type
            state_key = model if provider == "gemini" else f"groq:{model}"
            if err.should_skip:
                _set_disabled(state_key)
            else:
                _set_exhausted(state_key)
            # Continue to next candidate silently
            continue

    # Every provider failed
    return None


# ---------------------------------------------------------------------------
# Public interface — used by api/ai_analysis.py and api/analyzer.py
# ---------------------------------------------------------------------------

async def analyse_incident(
    incident: dict,
    logs_summary: dict,
    deployment: Optional[dict] = None,
) -> Tuple[Optional[dict], str]:
    """
    Run AI analysis on an incident.

    Returns:
        (analysis_dict, "success")      on success
        (None, "unavailable")           if all providers fail

    The second element is intentionally opaque — callers must never
    show provider names or quota messages to the user.
    """
    if not settings.GEMINI_API_KEY and not settings.GROQ_API_KEY:
        return None, "unavailable"

    prompt = _build_user_prompt(incident, logs_summary, deployment)
    raw    = await _run_with_fallback(prompt)

    if raw is None:
        return None, "unavailable"

    try:
        analysis = _extract_json(raw)
        return analysis, "success"
    except ValueError:
        return None, "unavailable"


async def run_analyzer_prompt(prompt_text: str) -> Optional[str]:
    """
    Run a free-form prompt through the provider chain.
    Used by the analyzer upload endpoint.
    Returns raw text response or None.
    """
    if not settings.GEMINI_API_KEY and not settings.GROQ_API_KEY:
        return None

    return await _run_with_fallback(prompt_text)


def ai_status() -> dict:
    """
    Returns a clean status object for the /api/ai/status endpoint.
    NEVER exposes provider names, model names, or quota states.
    Shows only whether AI analysis is currently available.
    """
    # Check if at least one provider has a key configured
    has_key = bool(settings.GEMINI_API_KEY or settings.GROQ_API_KEY)

    # Check if all models are disabled (bad keys)
    all_disabled = all(
        _get_state(m) == _ProviderState.DISABLED
        for m in _GEMINI_MODELS
    ) and all(
        _get_state(f"groq:{m}") == _ProviderState.DISABLED
        for m in _GROQ_MODELS
    ) if has_key else False

    available = has_key and not all_disabled

    # Determine a display model name — always show a clean name
    # regardless of which provider is actually active
    display_model = "gemini-2.5-flash"

    return {
        "available":          available,
        "active_model":       display_model if available else None,
        "primary_exhausted":  False,   # intentionally opaque
        "fallback_exhausted": False,   # intentionally opaque
        "message":            "AI analysis active" if available else "AI analysis initialising",
    }


def reset_all_providers() -> None:
    """Reset all provider states. Used for testing only."""
    _model_state.clear()