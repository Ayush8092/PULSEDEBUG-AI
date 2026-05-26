"""
PulseDebug AI — Upload-Based Project Analyzer
===============================================
File: backend/app/api/analyzer.py
Purpose:
    Accepts uploaded files (.zip, .log, .json, .txt) and performs
    AI-powered analysis with full professional diagnosis output.

    Log file analysis produces:
        - metrics (requests, error rate, latency, retry detection)
        - incident_summary    — executive summary of what was detected
        - impact              — business/system impact explanation
        - likely_cause        — root cause reasoning from evidence
        - recommended_actions — ordered actionable remediation steps
        - raw_analysis        — original structured stats (collapsible)

    ZIP project analysis produces:
        - resilience_score              — weighted 10-100 (never 0)
        - files_scanned / risks / checks
        - architecture_health_summary   — executive technical assessment
        - operational_risk_impact       — production consequence analysis
        - architectural_weaknesses      — inferred design flaws
        - recommended_improvements      — numbered implementation actions
        - raw_findings                  — original check results (collapsible)

    All AI calls go through the multi-provider chain (Gemini then Groq).
    Failover is completely silent. User never sees provider names or errors.
    Statistical fallback is used if ALL AI providers fail.

Author: PulseDebug AI Hackathon Team
"""

import io
import json
import re
import uuid
import zipfile
from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks

from app.services.ai_service import run_analyzer_prompt

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
    r'NULL_POINTER|SOCKET_HANG_UP|ECONNREFUSED)\b',
    re.IGNORECASE,
)
_RETRY_RE    = re.compile(r'\b(retry|retrying|attempt \d+|retried)\b', re.IGNORECASE)
_ENDPOINT_RE = re.compile(r'(GET|POST|PUT|DELETE|PATCH)\s+(/[\w/\-\.]+)', re.IGNORECASE)
_SERVICE_RE  = re.compile(
    r'\b(Auth API|Payment API|Orders API|Inventory API|Notification API)\b',
    re.IGNORECASE,
)


def _parse_log_text(text: str) -> dict:
    lines     = text.splitlines()
    statuses  = _STATUS_RE.findall(text)
    latencies = [int(x) for x in _LATENCY_RE.findall(text)]
    errors    = _ERROR_RE.findall(text)
    retries   = _RETRY_RE.findall(text)
    endpoints = _ENDPOINT_RE.findall(text)
    services  = _SERVICE_RE.findall(text)

    status_counts = Counter(int(s) for s in statuses)
    error_counts  = Counter(e.upper() for e in errors)
    endpoint_hits = Counter(f"{m} {p}" for m, p in endpoints)
    service_hits  = Counter(s.title() for s in services)

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
        "total_lines":          len(lines),
        "total_requests":       sum(status_counts.values()),
        "status_breakdown":     dict(status_counts.most_common(10)),
        "error_rate":           round(error_total / total_requests, 3),
        "latency": {
            "avg_ms":  round(avg_latency, 1),
            "max_ms":  max_latency,
            "p95_ms":  p95_latency,
            "samples": len(latencies),
        },
        "top_error_signatures": dict(error_counts.most_common(8)),
        "top_endpoints":        dict(endpoint_hits.most_common(8)),
        "top_services":         dict(service_hits.most_common(5)),
        "retry_storm_detected": retry_storm,
        "retry_count":          len(retries),
        "incident_clusters":    clusters,
    }


# ---------------------------------------------------------------------------
# ZIP inspector — weighted resilience scoring (clamp min 10)
# ---------------------------------------------------------------------------

_RESILIENCE_WEIGHTS = {
    "timeout_config":       15,
    "retry_backoff":        15,
    "circuit_breaker":      15,
    "db_pool_config":       15,
    "smtp_fallback":        10,
    "auth_secret_rotation": 10,
    "rate_limiting":        10,
    "health_check":         10,
}

_RESILIENCE_CHECKS = {
    "timeout_config": {
        "patterns":        [r'timeout\s*[=:]\s*\d+', r'TIMEOUT\s*=\s*\d+', r'connect_timeout'],
        "risk_if_missing": "No timeout enforcement found — services may hang indefinitely under upstream slowness.",
    },
    "retry_backoff": {
        "patterns":        [r'backoff', r'exponential', r'retry_delay', r'wait_fixed', r'RETRY_DELAY', r'tenacity', r'wait_exponential'],
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
    risks       = []
    file_list   = []
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
        risks.append({
            "check":   check_name,
            "risk":    check["risk_if_missing"] if not found else None,
            "present": found,
        })

    # Weighted score — start 100, subtract missing, clamp to 10 minimum
    deductions = sum(
        _RESILIENCE_WEIGHTS.get(r["check"], 10)
        for r in risks if not r["present"]
    )
    resilience_score = max(10, 100 - deductions)

    extensions = Counter(
        n.rsplit(".", 1)[-1].lower() for n in file_list if "." in n
    )

    sensitive_files = [
        n for n in file_list
        if any(re.search(p, n, re.IGNORECASE) for p in _SENSITIVE_FILE_PATTERNS)
    ]

    return {
        "total_files":           len(file_list),
        "file_types":            dict(extensions.most_common(10)),
        "resilience_score":      resilience_score,
        "checks":                risks,
        "sensitive_files_found": sensitive_files,
        "risks_detected":        [r for r in risks if not r["present"]],
        "checks_passed":         sum(1 for r in risks if r["present"]),
        "text_sample":           text_corpus[:4000],
    }


# ---------------------------------------------------------------------------
# Log analysis AI prompt
# ---------------------------------------------------------------------------

_LOG_AI_PROMPT = """You are PulseDebug AI, a senior SRE incident triage system.
Analyse the log statistics below and return a JSON object with EXACTLY these keys.
Return ONLY the JSON object. No markdown fences. No preamble. No explanation.

{
  "incident_summary": "<2-3 sentence executive summary: mention affected service(s), severity, pattern type, operational status — professional incident-report tone>",
  "impact": "<2-3 sentences: user-facing impact, operational degradation, latency consequences, reliability risk>",
  "likely_cause": "<2-3 sentences: root cause reasoning from clustered evidence, repetition patterns, latency spikes, endpoint concentration — must feel like senior SRE diagnosis, not generic>",
  "recommended_actions": [
    { "step": "01", "title": "<short action title>", "detail": "<specific implementation-ready instruction>" },
    { "step": "02", "title": "<short action title>", "detail": "<specific implementation-ready instruction>" },
    { "step": "03", "title": "<short action title>", "detail": "<specific implementation-ready instruction>" },
    { "step": "04", "title": "<short action title>", "detail": "<specific implementation-ready instruction>" }
  ]
}

Log statistics:
STATS_JSON
"""


# ---------------------------------------------------------------------------
# ZIP analysis AI prompt
# ---------------------------------------------------------------------------

_ZIP_AI_PROMPT = """You are PulseDebug AI, a senior platform engineer performing an architecture resilience audit.
Analyse the static code inspection findings below and return a JSON object with EXACTLY these keys.
Return ONLY the JSON object. No markdown fences. No preamble. No explanation.

{
  "architecture_health_summary": "<2-3 sentence executive technical assessment: overall resilience posture, service maturity, system protection quality, production readiness — senior SRE audit tone>",
  "operational_risk_impact": "<2-3 sentences: likely production consequences under stress — cascading failures, dependency lockup, outage propagation, latency amplification, degraded recovery>",
  "architectural_weaknesses": "<2-3 sentences: REASON from evidence — infer design flaws, do not just list findings — e.g. missing timeout + no retries implies synchronous dependency coupling>",
  "recommended_improvements": [
    { "step": "01", "title": "<title>", "detail": "<why it matters + practical implementation guidance>", "library": "<suggested library or empty string>" },
    { "step": "02", "title": "<title>", "detail": "<why it matters + practical implementation guidance>", "library": "<suggested library or empty string>" },
    { "step": "03", "title": "<title>", "detail": "<why it matters + practical implementation guidance>", "library": "<suggested library or empty string>" },
    { "step": "04", "title": "<title>", "detail": "<why it matters + practical implementation guidance>", "library": "<suggested library or empty string>" },
    { "step": "05", "title": "<title>", "detail": "<why it matters + practical implementation guidance>", "library": "<suggested library or empty string>" }
  ]
}

Resilience score: SCORE/100
Checks passed: PASSED of TOTAL

Missing safeguards:
MISSING_JSON

Project source code sample:
CODE_SAMPLE
"""


# ---------------------------------------------------------------------------
# Statistical fallbacks — used when ALL AI providers fail
# ---------------------------------------------------------------------------

def _log_statistical_fallback(stats: dict) -> dict:
    error_rate  = stats.get("error_rate", 0)
    clusters    = stats.get("incident_clusters", [])
    top_errors  = stats.get("top_error_signatures", {})
    retries     = stats.get("retry_storm_detected", False)
    primary_err = list(top_errors.keys())[0] if top_errors else "unknown error pattern"
    severity    = "critical" if error_rate > 0.3 else "elevated" if error_rate > 0.1 else "low"

    return {
        "incident_summary": (
            f"PulseDebug detected {severity} service instability across the analysed log data. "
            f"Error analysis identified {len(clusters)} recurring failure cluster(s) with "
            f"{primary_err} as the dominant signature. "
            f"Overall error rate stands at {round(error_rate * 100, 1)}% of sampled traffic."
        ),
        "impact": (
            f"Approximately {round(error_rate * 100, 1)}% of requests are failing, "
            f"causing service degradation for affected endpoints. "
            f"Average response latency of {stats['latency']['avg_ms']}ms "
            f"{'exceeds normal operational thresholds' if stats['latency']['avg_ms'] > 500 else 'remains within acceptable range'}."
            + (" Retry storm activity detected, amplifying downstream load." if retries else "")
        ),
        "likely_cause": (
            f"Repeated occurrence of {primary_err} errors suggests a systemic configuration "
            f"or dependency failure rather than isolated request errors. "
            f"The clustering pattern and temporal concentration indicate a deployment-adjacent "
            f"or infrastructure-level trigger."
        ),
        "recommended_actions": [
            {"step": "01", "title": "Inspect error logs for root cause",
             "detail": f"Focus on {primary_err} occurrences and correlate with deployment events."},
            {"step": "02", "title": "Check dependent service health",
             "detail": "Verify all upstream dependencies are healthy and responding correctly."},
            {"step": "03", "title": "Review recent configuration changes",
             "detail": "Audit any configuration, secret, or environment changes made before the incident window."},
            {"step": "04", "title": "Monitor recovery metrics",
             "detail": "Watch error rate and p95 latency until they return to baseline before closing the incident."},
        ],
    }


def _zip_statistical_fallback(inspection: dict) -> dict:
    score         = inspection.get("resilience_score", 10)
    risks         = inspection.get("risks_detected", [])
    checks_passed = inspection.get("checks_passed", 0)
    total_checks  = len(inspection.get("checks", []))
    posture = "critical risk" if score < 30 else "at risk" if score < 60 else "adequate" if score < 80 else "strong"

    improvements = []
    library_map  = {
        "retry_backoff": "tenacity",
        "circuit_breaker": "pybreaker",
        "rate_limiting": "slowapi",
    }
    for i, risk in enumerate(risks[:5], 1):
        improvements.append({
            "step":    str(i).zfill(2),
            "title":   risk["check"].replace("_", " ").title(),
            "detail":  risk.get("risk", "Add this safeguard to improve reliability."),
            "library": library_map.get(risk["check"], ""),
        })

    return {
        "architecture_health_summary": (
            f"Architecture resilience audit completed with a score of {score}/100, "
            f"indicating a {posture} reliability posture. "
            f"{checks_passed} of {total_checks} safeguards are present. "
            f"{len(risks)} resilience gap(s) require remediation before production scaling."
        ),
        "operational_risk_impact": (
            "Under production load, missing safeguards create compounding failure risk. "
            "Absent circuit breakers and retry strategies leave the system vulnerable to "
            "cascading dependency failures, where a single upstream slowdown can exhaust "
            "request threads and cause full service unavailability."
        ),
        "architectural_weaknesses": (
            "Static analysis indicates the project lacks systematic fault isolation. "
            + ("Missing timeout enforcement combined with absent retry backoff creates synchronous dependency coupling. "
               if any(r["check"] in ("timeout_config", "retry_backoff") for r in risks)
               else "")
            + ("No circuit breaker pattern suggests no fault boundary strategy is in place. "
               if any(r["check"] == "circuit_breaker" for r in risks)
               else "")
            + "These gaps indicate the system was built for happy-path operation without resilience-first design."
        ),
        "recommended_improvements": improvements,
    }


# ---------------------------------------------------------------------------
# Background analysis jobs
# ---------------------------------------------------------------------------

async def _run_log_analysis_job(job_id: str, content: bytes, filename: str) -> None:
    try:
        _jobs[job_id]["status"] = "processing"

        try:
            text = content.decode("utf-8", errors="ignore")
        except Exception:
            text = ""

        if not text.strip():
            _jobs[job_id] = {"status": "error", "error": "File appears to be empty or unreadable."}
            return

        stats = _parse_log_text(text)

        prompt  = _LOG_AI_PROMPT.replace("STATS_JSON", json.dumps(stats, indent=2))
        raw_ai  = await run_analyzer_prompt(prompt)
        ai_result = None

        if raw_ai:
            try:
                cleaned   = re.sub(r"```(?:json)?", "", raw_ai).strip().rstrip("`").strip()
                ai_result = json.loads(cleaned)
            except Exception:
                pass

        if not ai_result:
            ai_result = _log_statistical_fallback(stats)

        _jobs[job_id] = {
            "status":               "complete",
            "type":                 "log_analysis",
            "filename":             filename,
            "metrics":              stats,
            "incident_summary":     ai_result.get("incident_summary", ""),
            "impact":               ai_result.get("impact", ""),
            "likely_cause":         ai_result.get("likely_cause", ""),
            "recommended_actions":  ai_result.get("recommended_actions", []),
            "raw_analysis":         stats,
            "ai_available":         raw_ai is not None,
            "completed_at":         datetime.now(timezone.utc).isoformat(),
        }

    except Exception as exc:
        _jobs[job_id] = {"status": "error", "error": str(exc)}


async def _run_zip_analysis_job(job_id: str, content: bytes, filename: str) -> None:
    try:
        _jobs[job_id]["status"] = "processing"

        inspection = _inspect_zip(content)

        if "error" in inspection:
            _jobs[job_id] = {"status": "error", "error": inspection["error"]}
            return

        risks         = inspection.get("risks_detected", [])
        checks_passed = inspection.get("checks_passed", 0)
        total_checks  = len(inspection.get("checks", []))

        prompt = (
            _ZIP_AI_PROMPT
            .replace("SCORE",        str(inspection["resilience_score"]))
            .replace("PASSED",       str(checks_passed))
            .replace("TOTAL",        str(total_checks))
            .replace("MISSING_JSON", json.dumps(risks, indent=2))
            .replace("CODE_SAMPLE",  inspection.get("text_sample", "")[:3000])
        )

        raw_ai    = await run_analyzer_prompt(prompt)
        ai_result = None

        if raw_ai:
            try:
                cleaned   = re.sub(r"```(?:json)?", "", raw_ai).strip().rstrip("`").strip()
                ai_result = json.loads(cleaned)
            except Exception:
                pass

        if not ai_result:
            ai_result = _zip_statistical_fallback(inspection)

        _jobs[job_id] = {
            "status":                       "complete",
            "type":                         "zip_inspection",
            "filename":                     filename,
            "resilience_score":             inspection["resilience_score"],
            "files_scanned":                inspection["total_files"],
            "risks_detected":               len(risks),
            "checks_passed":                checks_passed,
            "architecture_health_summary":  ai_result.get("architecture_health_summary", ""),
            "operational_risk_impact":      ai_result.get("operational_risk_impact", ""),
            "architectural_weaknesses":     ai_result.get("architectural_weaknesses", ""),
            "recommended_improvements":     ai_result.get("recommended_improvements", []),
            "raw_findings":                 {
                "checks":                inspection["checks"],
                "sensitive_files_found": inspection["sensitive_files_found"],
                "file_types":            inspection["file_types"],
                "resilience_score":      inspection["resilience_score"],
            },
            "ai_available":                 raw_ai is not None,
            "completed_at":                 datetime.now(timezone.utc).isoformat(),
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

    job_id        = str(uuid.uuid4())
    _jobs[job_id] = {
        "status":    "queued",
        "filename":  filename,
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }

    if extension == "zip":
        background_tasks.add_task(_run_zip_analysis_job, job_id, content, filename)
    else:
        background_tasks.add_task(_run_log_analysis_job, job_id, content, filename)

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
        {"job_id": k, **{kk: vv for kk, vv in v.items() if kk not in ("text_sample", "raw_findings", "raw_analysis")}}
        for k, v in _jobs.items()
    ]
    return jobs[-20:]