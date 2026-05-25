"""
PulseDebug AI — Upload-Based Project Analyzer
===============================================
File: backend/app/api/analyzer.py
Purpose:
    Accepts uploaded files (.zip, .log, .json, .txt) for resilience and
    log analysis. Uses the multi-provider AI service for all completions
    so failover is completely transparent.

    All AI calls go through run_analyzer_prompt() which handles
    Gemini → Groq failover silently with no user-visible errors.

Endpoints:
    POST /api/analyzer/upload
    GET  /api/analyzer/results/{job_id}
    GET  /api/analyzer/jobs

Author: PulseDebug AI Hackathon Team
"""

import io
import json
import re
import uuid
import zipfile
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks

from app.services.ai_service import run_analyzer_prompt
from app.core.config import settings

router = APIRouter()

_jobs: dict = {}

MAX_FILE_SIZE_MB    = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


# ---------------------------------------------------------------------------
# Log file parser
# ---------------------------------------------------------------------------

_STATUS_RE   = re.compile(r'\b([1-5]\d{2})\b')
_LATENCY_RE  = re.compile(r'\b(\d{1,6})\s*ms\b', re.IGNORECASE)
_ERROR_RE    = re.compile(
    r'\b(TIMEOUT|DB_TIMEOUT|JWT_MISMATCH|RATE_LIMITED|INTERNAL_ERROR|'
    r'UPSTREAM_UNAVAILABLE|MALFORMED_PAYLOAD|CONNECTION_REFUSED|'
    r'NULL_POINTER|SOCKET_HANG_UP|ECONNREFUSED|500|503|504|401|429)\b',
    re.IGNORECASE,
)
_RETRY_RE    = re.compile(r'\b(retry|retrying|attempt \d+|retried)\b', re.IGNORECASE)
_ENDPOINT_RE = re.compile(r'(GET|POST|PUT|DELETE|PATCH)\s+(/[\w/\-\.]+)', re.IGNORECASE)


def _parse_log_text(text: str) -> dict:
    lines      = text.splitlines()
    statuses   = _STATUS_RE.findall(text)
    latencies  = [int(x) for x in _LATENCY_RE.findall(text)]
    errors     = _ERROR_RE.findall(text)
    retries    = _RETRY_RE.findall(text)
    endpoints  = _ENDPOINT_RE.findall(text)

    status_counts  = Counter(int(s) for s in statuses)
    error_counts   = Counter(e.upper() for e in errors)
    endpoint_hits  = Counter(f"{m} {p}" for m, p in endpoints)

    error_total    = sum(v for k, v in status_counts.items() if k >= 400)
    total_requests = sum(status_counts.values()) or 1

    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    max_latency = max(latencies) if latencies else 0
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0

    retry_storm = len(retries) > 10

    clusters = []
    for sig, count in error_counts.most_common(5):
        if count >= 2:
            clusters.append({
                "error_signature":  sig,
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
        "patterns":        [r'timeout\s*[=:]\s*\d+', r'TIMEOUT\s*=\s*\d+', r'connect_timeout'],
        "risk_if_missing": "No timeout enforcement found — services may hang indefinitely under upstream slowness.",
    },
    "retry_backoff": {
        "patterns":        [r'backoff', r'exponential', r'retry_delay', r'wait_fixed', r'RETRY_DELAY'],
        "risk_if_missing": "No retry backoff strategy detected — retry storms possible under upstream latency spikes.",
    },
    "circuit_breaker": {
        "patterns":        [r'circuit.?breaker', r'CircuitBreaker', r'pybreaker', r'opossum', r'hystrix'],
        "risk_if_missing": "No circuit breaker pattern found — cascading failures not protected against.",
    },
    "db_pool_config": {
        "patterns":        [r'pool_size', r'max_overflow', r'connection_pool', r'POOL_SIZE', r'DB_POOL'],
        "risk_if_missing": "No database connection pool configuration found — DB exhaustion risk under load.",
    },
    "smtp_fallback": {
        "patterns":        [r'SMTP_FALLBACK', r'smtp_fallback', r'MAIL_BACKUP', r'fallback.*smtp', r'smtp.*fallback'],
        "risk_if_missing": "No SMTP fallback provider configured — email notification outage risk during DNS failures.",
    },
    "auth_secret_rotation": {
        "patterns":        [r'JWT_SECRET', r'SECRET_KEY', r'AUTH_SECRET', r'TOKEN_SECRET'],
        "risk_if_missing": "No JWT/auth secret configuration found — auth configuration may be undocumented.",
    },
    "rate_limiting": {
        "patterns":        [r'rate.?limit', r'RateLimiter', r'slowapi', r'express-rate-limit', r'throttle'],
        "risk_if_missing": "No rate limiting configuration found — API may be vulnerable to traffic bursts.",
    },
    "health_check": {
        "patterns":        [r'/health', r'/ping', r'healthcheck', r'health_check'],
        "risk_if_missing": "No health check endpoint detected — load balancers cannot detect service degradation.",
    },
}

_SENSITIVE_FILE_PATTERNS = [
    r'\.env$', r'secret', r'password', r'private.key', r'credentials',
]


def _inspect_zip(content: bytes) -> dict:
    findings   = {}
    risks      = []
    file_list  = []
    text_corpus = ""

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            names     = zf.namelist()
            file_list = names[:100]

            for name in names:
                info = zf.getinfo(name)
                if info.file_size > 200_000:
                    continue
                if any(name.endswith(ext) for ext in
                       ('.png', '.jpg', '.gif', '.ico', '.woff', '.ttf', '.zip', '.gz')):
                    continue
                try:
                    text = zf.read(name).decode("utf-8", errors="ignore")
                    text_corpus += f"\n\n# FILE: {name}\n{text}"
                except Exception:
                    pass

    except zipfile.BadZipFile:
        return {"error": "Invalid ZIP file — could not open archive."}

    for check_name, check in _RESILIENCE_CHECKS.items():
        found = any(
            re.search(p, text_corpus, re.IGNORECASE)
            for p in check["patterns"]
        )
        findings[check_name] = found
        risks.append({
            "check":   check_name,
            "risk":    check["risk_if_missing"] if not found else None,
            "present": found,
        })

    extensions = Counter(
        n.rsplit(".", 1)[-1].lower() for n in file_list if "." in n
    )

    sensitive_files = [
        n for n in file_list
        if any(re.search(p, n, re.IGNORECASE) for p in _SENSITIVE_FILE_PATTERNS)
    ]

    weights = {
        "timeout_config": 15,
        "retry_backoff": 15,
        "circuit_breaker": 15,
        "db_pool_config": 15,
        "smtp_fallback": 10,
        "auth_secret_rotation": 10,
        "rate_limiting": 10,
        "health_check": 10,
    }

    max_score = sum(weights.values())

    earned = sum(
        weights[r["check"]]
        for r in risks
        if r["present"]
    )

    resilience_score = (
        int((earned / max_score) * 100)
        if earned > 0 else 0
    )

    return {
        "total_files":           len(file_list),
        "file_types":            dict(extensions.most_common(10)),
        "resilience_score":      resilience_score,
        "checks":                risks,
        "sensitive_files_found": sensitive_files,
        "risks_detected":        [r for r in risks if not r["present"]],
        "text_sample":           text_corpus[:1700],
    }

def _build_log_prompt(stats: dict) -> str:
    return f"""
Analyse these API log statistics and return ONLY valid JSON.

Required JSON schema:

{{
  "incident_summary": "<clear incident summary>",
  "impact": "<production impact explanation>",
  "likely_cause": "<root cause analysis>",
  "recommended_actions": [
    "<action 1>",
    "<action 2>",
    "<action 3>",
    "<action 4>"
  ]
}}

Requirements:

- Professional observability language
- Explain likely production failure patterns
- Mention correlated latency / status anomalies
- Be concise but technically specific
- No markdown
- Return ONLY JSON

Log statistics:
{json.dumps(stats, indent=2)}
""".strip()
# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_zip_prompt(inspection: dict) -> str:
    risks = [r for r in inspection.get("checks", []) if not r["present"]]

    return f"""
Analyse this backend project resilience inspection.

Return ONLY valid JSON.

Required schema:

{{
  "overall_verdict": "<Strong | Moderate Risk | Critical Risk>",
  "summary": "<clear resilience assessment summary>",
  "deployment_risks": "<production impact explanation>",

  "risk_findings": [
    {{
      "check": "<missing control>",
      "severity": "<critical|warning|investigate|low>",
      "risk_description": "<why this matters>",
      "recommended_fix": "<specific fix>"
    }}
  ]
}}

Rules:

- Professional SRE language
- Explain operational consequences
- Use concise technical language
- Severity must be:
  critical / warning / investigate / low
- No markdown
- Return ONLY JSON

Missing checks:
{json.dumps(risks, indent=2)}

Project sample:
{inspection.get("text_sample", "")[:1700]}
""".strip()


# ---------------------------------------------------------------------------
# Background analysis job
# ---------------------------------------------------------------------------

async def _run_analysis_job(
    job_id: str,
    file_type: str,
    content: bytes,
    filename: str,
) -> None:
    try:
        _jobs[job_id]["status"] = "processing"

        if file_type == "zip":
            inspection = _inspect_zip(content)
            if "error" in inspection:
                _jobs[job_id] = {"status": "error", "error": inspection["error"]}
                return

            prompt  = _build_zip_prompt(inspection)
            raw_ai  = await run_analyzer_prompt(prompt)

            ai_result = None
            if raw_ai:
                try:
                    cleaned   = re.sub(r"```(?:json)?", "", raw_ai).strip().rstrip("`").strip()
                    ai_result = json.loads(cleaned)
                except Exception:
                    ai_result = {"summary": raw_ai[:500], "parse_error": True}

            _jobs[job_id] = {
                "status":       "complete",
                "type":         "zip_inspection",
                "filename":     filename,
                "inspection":   inspection,
                "ai_analysis":  ai_result,
                "ai_available": ai_result is not None,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }

        else:
            try:
                text = content.decode("utf-8", errors="ignore")
            except Exception:
                text = ""

            if not text.strip():
                _jobs[job_id] = {
                    "status": "error",
                    "error":  "File appears to be empty or unreadable.",
                }
                return

            stats   = _parse_log_text(text)
            prompt  = _build_log_prompt(stats)
            raw_ai  = await run_analyzer_prompt(prompt)

            ai_result = None
            if raw_ai:
                try:
                    cleaned   = re.sub(r"```(?:json)?", "", raw_ai).strip().rstrip("`").strip()
                    ai_result = json.loads(cleaned)
                except Exception:
                    ai_result = {"summary": raw_ai[:500], "parse_error": True}

            _jobs[job_id] = {
                "status":       "complete",
                "type":         "log_analysis",
                "filename":     filename,
                "statistics":   stats,
                "ai_analysis":  ai_result,
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
    filename  = file.filename or "unknown"
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    allowed = {"zip", "log", "json", "txt"}
    if extension not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{extension}'. Allowed: {', '.join(sorted(allowed))}",
        )

    content = await file.read()

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB.",
        )

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    job_id           = str(uuid.uuid4())
    _jobs[job_id]    = {
        "status":    "queued",
        "filename":  filename,
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }

    file_type = "zip" if extension == "zip" else "log"
    background_tasks.add_task(
        _run_analysis_job, job_id, file_type, content, filename
    )

    return {
        "job_id":   job_id,
        "filename": filename,
        "status":   "queued",
        "message":  "File received. Analysis started.",
    }


@router.get("/results/{job_id}")
def get_results(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _jobs[job_id]


@router.get("/jobs")
def list_jobs():
    jobs = [
        {"job_id": k, **{kk: vv for kk, vv in v.items() if kk != "text_sample"}}
        for k, v in _jobs.items()
    ]
    return jobs[-20:]