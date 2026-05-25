"""
PulseDebug AI — Upload-Based Project Analyzer
===============================================
File: backend/app/api/analyzer.py
Purpose:
    Accepts uploaded files (.zip, .log, .json, .txt) and performs two
    types of analysis:

    1. Log file analysis (.log / .txt / .json)
       Parses latency patterns, error signatures, retry storms, status
       code distributions, and recurring anomalies. Then calls Gemini to
       produce incident clusters and remediation guidance.

    2. ZIP project analysis (.zip)
       Performs lightweight static inspection of config files, dependency
       files, .env.example, timeout configs, retry policies, circuit
       breaker presence, database pooling, auth secret consistency, and
       SMTP fallback configs. Gemini explains resilience risks found.

Endpoints:
    POST /api/analyzer/upload   — upload a file for analysis
    GET  /api/analyzer/results/{job_id} — poll for async results

Author: PulseDebug AI Hackathon Team
"""

import io
import json
import re
import uuid
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from app.services.ai_service import analyse_incident, ai_status
from app.core.config import settings
import httpx

router = APIRouter()

# In-memory job store (sufficient for hackathon demo)
_jobs: dict = {}

MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


# ---------------------------------------------------------------------------
# Log file parser
# ---------------------------------------------------------------------------

# Patterns that match common log formats
_STATUS_RE   = re.compile(r'\b([1-5]\d{2})\b')
_LATENCY_RE  = re.compile(r'\b(\d{1,6})\s*ms\b', re.IGNORECASE)
_ERROR_RE    = re.compile(
    r'\b(TIMEOUT|DB_TIMEOUT|JWT_MISMATCH|RATE_LIMITED|INTERNAL_ERROR|'
    r'UPSTREAM_UNAVAILABLE|MALFORMED_PAYLOAD|CONNECTION_REFUSED|'
    r'NULL_POINTER|SOCKET_HANG_UP|ECONNREFUSED|500|503|504|401|429)\b',
    re.IGNORECASE
)
_RETRY_RE    = re.compile(r'\b(retry|retrying|attempt \d+|retried)\b', re.IGNORECASE)
_ENDPOINT_RE = re.compile(r'(GET|POST|PUT|DELETE|PATCH)\s+(/[\w/\-\.]+)', re.IGNORECASE)


def _parse_log_text(text: str) -> dict:
    """Extract structured statistics from free-form log text."""
    lines       = text.splitlines()
    statuses    = _STATUS_RE.findall(text)
    latencies   = [int(x) for x in _LATENCY_RE.findall(text)]
    errors      = _ERROR_RE.findall(text)
    retries     = _RETRY_RE.findall(text)
    endpoints   = _ENDPOINT_RE.findall(text)

    status_counts  = Counter(int(s) for s in statuses)
    error_counts   = Counter(e.upper() for e in errors)
    endpoint_hits  = Counter(f"{m} {p}" for m, p in endpoints)

    error_total    = sum(v for k, v in status_counts.items() if k >= 400)
    total_requests = sum(status_counts.values()) or 1

    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    max_latency = max(latencies) if latencies else 0
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0

    # Detect retry storm: many retry keywords in a short log burst
    retry_storm = len(retries) > 10

    # Build incident clusters from most-frequent errors
    clusters = []
    for sig, count in error_counts.most_common(5):
        if count >= 2:
            clusters.append({
                "error_signature": sig,
                "occurrence_count": count,
                "severity": "critical" if count > 10 else "warning",
            })

    return {
        "total_lines":      len(lines),
        "total_requests":   sum(status_counts.values()),
        "status_breakdown": dict(status_counts.most_common(10)),
        "error_rate":       round(error_total / total_requests, 3),
        "latency": {
            "avg_ms":  round(avg_latency, 1),
            "max_ms":  max_latency,
            "p95_ms":  p95_latency,
            "samples": len(latencies),
        },
        "top_error_signatures": dict(error_counts.most_common(8)),
        "top_endpoints":        dict(endpoint_hits.most_common(8)),
        "retry_storm_detected": retry_storm,
        "retry_count":          len(retries),
        "incident_clusters":    clusters,
    }


# ---------------------------------------------------------------------------
# ZIP project inspector
# ---------------------------------------------------------------------------

_RESILIENCE_CHECKS = {
    "timeout_config": {
        "patterns": [r'timeout\s*[=:]\s*\d+', r'TIMEOUT\s*=\s*\d+', r'connect_timeout'],
        "risk_if_missing": "No timeout enforcement found — services may hang indefinitely under upstream slowness.",
    },
    "retry_backoff": {
        "patterns": [r'backoff', r'exponential', r'retry_delay', r'wait_fixed', r'RETRY_DELAY'],
        "risk_if_missing": "No retry backoff strategy detected — retry storms possible under upstream latency spikes.",
    },
    "circuit_breaker": {
        "patterns": [r'circuit.?breaker', r'CircuitBreaker', r'pybreaker', r'opossum', r'hystrix'],
        "risk_if_missing": "No circuit breaker pattern found — cascading failures not protected against.",
    },
    "db_pool_config": {
        "patterns": [r'pool_size', r'max_overflow', r'connection_pool', r'POOL_SIZE', r'DB_POOL'],
        "risk_if_missing": "No database connection pool configuration found — DB exhaustion risk under load.",
    },
    "smtp_fallback": {
        "patterns": [r'SMTP_FALLBACK', r'smtp_fallback', r'MAIL_BACKUP', r'fallback.*smtp', r'smtp.*fallback'],
        "risk_if_missing": "No SMTP fallback provider configured — email notification outage risk during DNS failures.",
    },
    "auth_secret_rotation": {
        "patterns": [r'JWT_SECRET', r'SECRET_KEY', r'AUTH_SECRET', r'TOKEN_SECRET'],
        "risk_if_missing": "No JWT/auth secret configuration found in .env.example — auth configuration may be undocumented.",
    },
    "rate_limiting": {
        "patterns": [r'rate.?limit', r'RateLimiter', r'slowapi', r'express-rate-limit', r'throttle'],
        "risk_if_missing": "No rate limiting configuration found — API may be vulnerable to traffic bursts.",
    },
    "health_check": {
        "patterns": [r'/health', r'/ping', r'healthcheck', r'health_check'],
        "risk_if_missing": "No health check endpoint detected — load balancers cannot detect service degradation.",
    },
}

_SENSITIVE_FILE_PATTERNS = [
    r'\.env$',
    r'secret',
    r'password',
    r'private.key',
    r'credentials',
]


def _inspect_zip(content: bytes) -> dict:
    """Perform lightweight static resilience inspection on a ZIP archive."""
    findings    = {}
    risks       = []
    file_list   = []
    text_corpus = ""

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            names = zf.namelist()
            file_list = names[:100]   # cap for safety

            for name in names:
                # Skip binaries and huge files
                info = zf.getinfo(name)
                if info.file_size > 200_000:
                    continue
                if any(name.endswith(ext) for ext in
                       ('.png','.jpg','.gif','.ico','.woff','.ttf','.zip','.gz')):
                    continue

                try:
                    text = zf.read(name).decode("utf-8", errors="ignore")
                    text_corpus += f"\n\n# FILE: {name}\n{text}"
                except Exception:
                    pass

    except zipfile.BadZipFile:
        return {"error": "Invalid ZIP file — could not open archive."}

    # Run resilience checks against full corpus
    for check_name, check in _RESILIENCE_CHECKS.items():
        found = any(
            re.search(p, text_corpus, re.IGNORECASE)
            for p in check["patterns"]
        )
        findings[check_name] = found
        if not found:
            risks.append({
                "check":   check_name,
                "risk":    check["risk_if_missing"],
                "present": False,
            })
        else:
            risks.append({
                "check":   check_name,
                "risk":    None,
                "present": True,
            })

    # Count file types
    extensions = Counter(
        n.rsplit(".", 1)[-1].lower() for n in file_list if "." in n
    )

    # Check for accidentally committed secrets
    sensitive_files = [
        n for n in file_list
        if any(re.search(p, n, re.IGNORECASE) for p in _SENSITIVE_FILE_PATTERNS)
    ]

    resilience_score = int(
        sum(1 for r in risks if r["present"]) / len(risks) * 100
    ) if risks else 0

    return {
        "total_files":       len(file_list),
        "file_types":        dict(extensions.most_common(10)),
        "resilience_score":  resilience_score,
        "checks":            risks,
        "sensitive_files_found": sensitive_files,
        "risks_detected":    [r for r in risks if not r["present"]],
        "text_sample":       text_corpus[:3000],   # for Gemini prompt
    }


# ---------------------------------------------------------------------------
# Gemini prompt builders
# ---------------------------------------------------------------------------

async def _call_gemini_analysis(prompt: str) -> Optional[str]:
    """Call Gemini and return raw text response."""
    status = ai_status()
    if not status["available"]:
        return None

    model = status["active_model"]
    url = (
        f"{settings.GEMINI_API_URL}/{model}:generateContent"
        f"?key={settings.GEMINI_API_KEY}"
    )

    system = (
        "You are PulseDebug AI, an expert API reliability engineer. "
        "Analyse the data provided and return a JSON object only — "
        "no markdown fences, no preamble."
    )

    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents":           [{"parts": [{"text": prompt}]}],
        "generationConfig":   {"temperature": 0.3, "maxOutputTokens": 1500},
    }

    try:
        async with httpx.AsyncClient(timeout=40) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as exc:
        print(f"[Analyzer] Gemini call failed: {exc}")
        return None


def _build_log_prompt(stats: dict) -> str:
    return f"""
Analyse these API log statistics and return a JSON object with these exact keys:

{{
  "overall_health": "<Healthy | Degraded | Critical>",
  "summary": "<2-3 sentence summary of what the logs show>",
  "incident_clusters": [
    {{
      "title": "<incident name>",
      "likely_cause": "<root cause>",
      "severity": "<critical | warning | investigate>",
      "recommended_fix": "<actionable fix>"
    }}
  ],
  "top_risks": ["<risk 1>", "<risk 2>", "<risk 3>"],
  "remediation_steps": ["<step 1>", "<step 2>", "<step 3>", "<step 4>"]
}}

Log statistics:
{json.dumps(stats, indent=2)}
""".strip()


def _build_zip_prompt(inspection: dict) -> str:
    risks = [r for r in inspection.get("checks", []) if not r["present"]]
    return f"""
Analyse this backend project resilience inspection and return a JSON object with these exact keys:

{{
  "resilience_score": {inspection.get("resilience_score", 0)},
  "overall_verdict": "<Strong | Adequate | At Risk | Critical Risk>",
  "summary": "<2-3 sentence overall assessment>",
  "risk_findings": [
    {{
      "check": "<check name>",
      "risk_description": "<why this is a problem with a real-world failure scenario>",
      "recommended_fix": "<specific actionable fix with example>",
      "severity": "<critical | warning | low>"
    }}
  ],
  "quick_wins": ["<easiest fix 1>", "<easiest fix 2>", "<easiest fix 3>"],
  "deployment_risks": "<paragraph about deployment risk level>"
}}

Missing resilience checks:
{json.dumps(risks, indent=2)}

Project file sample (first 2000 chars):
{inspection.get("text_sample", "")[:2000]}
""".strip()


# ---------------------------------------------------------------------------
# Background analysis job
# ---------------------------------------------------------------------------

async def _run_analysis_job(job_id: str, file_type: str, content: bytes, filename: str):
    """Runs in the background. Updates _jobs[job_id] when complete."""
    try:
        _jobs[job_id]["status"] = "processing"

        if file_type == "zip":
            inspection = _inspect_zip(content)
            if "error" in inspection:
                _jobs[job_id] = {"status": "error", "error": inspection["error"]}
                return

            prompt = _build_zip_prompt(inspection)
            raw_ai = await _call_gemini_analysis(prompt)

            ai_result = None
            if raw_ai:
                try:
                    cleaned = re.sub(r"```(?:json)?", "", raw_ai).strip().rstrip("`").strip()
                    ai_result = json.loads(cleaned)
                except Exception:
                    ai_result = {"summary": raw_ai[:500], "parse_error": True}

            _jobs[job_id] = {
                "status":      "complete",
                "type":        "zip_inspection",
                "filename":    filename,
                "inspection":  inspection,
                "ai_analysis": ai_result,
                "ai_available": ai_result is not None,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }

        else:
            # Log / text / JSON file
            try:
                text = content.decode("utf-8", errors="ignore")
            except Exception:
                text = ""

            if not text.strip():
                _jobs[job_id] = {"status": "error", "error": "File appears to be empty or unreadable."}
                return

            stats = _parse_log_text(text)
            prompt = _build_log_prompt(stats)
            raw_ai = await _call_gemini_analysis(prompt)

            ai_result = None
            if raw_ai:
                try:
                    cleaned = re.sub(r"```(?:json)?", "", raw_ai).strip().rstrip("`").strip()
                    ai_result = json.loads(cleaned)
                except Exception:
                    ai_result = {"summary": raw_ai[:500], "parse_error": True}

            _jobs[job_id] = {
                "status":      "complete",
                "type":        "log_analysis",
                "filename":    filename,
                "statistics":  stats,
                "ai_analysis": ai_result,
                "ai_available": ai_result is not None,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }

    except Exception as exc:
        _jobs[job_id] = {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Accept a .zip, .log, .json, or .txt file.
    Returns a job_id immediately. Poll /results/{job_id} for the result.
    """
    filename  = file.filename or "unknown"
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    allowed = {"zip", "log", "json", "txt"}
    if extension not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{extension}'. Allowed: {', '.join(f'.{e}' for e in allowed)}"
        )

    content = await file.read()

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB."
        )

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status":      "queued",
        "filename":    filename,
        "queued_at":   datetime.now(timezone.utc).isoformat(),
    }

    file_type = "zip" if extension == "zip" else "log"
    background_tasks.add_task(_run_analysis_job, job_id, file_type, content, filename)

    return {
        "job_id":   job_id,
        "filename": filename,
        "status":   "queued",
        "message":  "File received. Analysis started. Poll /api/analyzer/results/{job_id} for results.",
    }


@router.get("/results/{job_id}")
def get_results(job_id: str):
    """Poll for analysis results by job ID."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _jobs[job_id]


@router.get("/jobs")
def list_jobs():
    """List all analysis jobs (newest first, capped at 20)."""
    jobs = [
        {"job_id": k, **{kk: vv for kk, vv in v.items() if kk != "text_sample"}}
        for k, v in _jobs.items()
    ]
    return jobs[-20:]
