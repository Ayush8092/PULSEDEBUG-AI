#  PulseDebug AI

**AI-Powered API Incident Triage and Resilience Analysis Platform**

**Live Demo → https://pulsedebug-ai.vercel.app**

PulseDebug AI is a real-time backend observability platform that detects abnormal API behavior, clusters recurring failures into clean incidents, correlates incidents with deployment events, and uses a multi-provider AI engine to generate root-cause analysis with actionable debugging guidance — all within seconds of a failure occurring.

The platform was designed to solve a real engineering problem: modern teams waste significant time manually correlating noisy alerts, raw logs, and deployment histories just to answer one question — *what broke and why?* PulseDebug answers that automatically.

---

## **Live Demo**

| Link | Description |
|------|-------------|
| **https://pulsedebug-ai.vercel.app** | Full live platform |
| **https://pulsedebug-ai.vercel.app/incidents** | External incident feed with sliding filters |
| **https://pulsedebug-ai.vercel.app/analyze** | Project resilience analyzer |
| **https://pulsedebug-ai.vercel.app/integrate** | SDK integration docs |

---

## **What This Project Demonstrates**

This project demonstrates end-to-end AI engineering across the full stack — from real-time data pipelines and deterministic ML detection algorithms to multi-provider LLM orchestration with automatic failover, confidence scoring, and structured AI output generation.

---

## **Key Features**

### **i. Multi-Provider AI Orchestration with Silent Failover**

The AI layer implements a production-grade provider chain with zero user-visible disruption.

- Primary: Google Gemini 2.5 Flash
- Secondary: Groq (llama-3.3-70b → llama-3.1-70b → mixtral-8x7b)
- If all providers fail: deterministic statistical fallback activates automatically
- Users never see quota errors, provider names, or fallback messages
- Confidence scores are computed from qualitative AI labels and visualized as animated progress bars

### **ii. Deterministic Anomaly Detection Engine**

The detection system operates fully offline — no AI dependency required.

- Rolling window latency spike detection using configurable multiplier thresholds
- Sliding window error-rate surge detection with per-endpoint statistics
- Request burst detection using temporal clustering within a 30-second window
- Status-code irregularity detection with pattern-aware 4xx grouping
- All detection runs in-process, zero external calls, works without internet

### **iii. Intelligent Incident Clustering**

Reduces alert noise by grouping repeated failures into deduplicated incident records.

- Clusters by service, endpoint, error signature, and temporal proximity
- Source tagging distinguishes demo traffic, external SDK traffic, and manual events
- Incident severity escalation based on weighted status-code mapping
- Automatic low-severity incident resolution creates natural count fluctuation

### **iv. Deployment Regression Detection**

Correlates incident spikes with deployment events using time-window heuristics.

- Tracks error counts 30 minutes before and after each deployment
- Flags regression when post-deployment error rate increases by more than 100%
- Calculates percentage increase and surfaces it in the incident detail panel
- Deployment version and notes displayed alongside AI root-cause analysis

### **v. Incident Timeline Replay**

Provides a chronological lifecycle view of every incident.

- Events logged at: anomaly detection, cluster formation, deployment link, AI analysis completion, escalation, resolution
- Timeline polls every 10 seconds for new events
- Color-coded event types with icons per event category
- Supports real-time streaming as incidents evolve

### **vi. Root-Cause Correlation Graph**

Automatically correlates related incidents to build causal chains.

- Temporal proximity correlation: incidents within 5 minutes on dependent services
- Error cascade pattern matching: known signature chains (DB_TIMEOUT → INTERNAL_ERROR → UPSTREAM_UNAVAILABLE)
- Deployment burst correlation: incidents sharing the same deployment event
- Graph rendered as visual node-edge chain in the incident detail panel

### **vii. AI-Generated Fix Commands**

Transforms textual remediation advice into immediately usable code.

- Generates Python, YAML, bash, and JavaScript snippets per incident
- Snippets are contextual — generated from the specific error signature and root cause
- Uses the existing AI pipeline with no additional API calls
- Copy button on every snippet for instant use

### **viii. Project Resilience Analyzer**

Upload any backend project ZIP or log file for an instant AI-powered audit.

- **Log files** (.log, .txt, .json): parses latency patterns, error signatures, retry storms, status distributions — produces incident summary, impact assessment, root cause, and numbered remediation steps
- **ZIP files**: static inspection across 8 resilience checks (timeout config, retry backoff, circuit breaker, DB pooling, SMTP fallback, auth secrets, rate limiting, health checks) — produces architecture health summary, operational risk impact, architectural weakness inference, and numbered improvement steps with library suggestions
- Weighted resilience scoring: starts at 100, deducts per missing safeguard, clamps minimum to 10
- Statistical fallback generates deterministic reports when AI providers are unavailable

### **ix. Real API Ingestion Pipeline**

Any external service can send real production telemetry to PulseDebug with a single endpoint.

- `POST /api/ingest` accepts service, endpoint, status, latency, error signature
- Events tagged with source=external and appear in the dedicated External Incidents Feed
- Anomaly detection and clustering run synchronously on ingested events
- AI RCA queued as a background task for critical external incidents
- SDK integration snippets provided for FastAPI, Flask, Django, Express.js, Node.js

### **x. True Real-Time Streaming**

The dashboard uses Server-Sent Events for zero-latency log streaming.

- SSE connection to `/api/logs/stream` pushes new events instantly as they are written
- Heartbeat every second keeps the connection alive through proxies
- Automatic reconnection on disconnect with 3-second backoff
- Replaces polling entirely for the live log feed

### **xi. External Incidents Feed with Sliding Filters**

A dedicated page separates external SDK telemetry from internal simulator traffic.

- Animated sliding pill-style toggle for Source (all / external / demo / manual)
- Animated sliding pill-style toggle for Severity (all / critical / warning / investigate)
- Toggle switch for AI-analyzed-only filtering
- Active filter summary with one-click clear
- Source badges distinguish incident origin on every card

---

## **System Modules**

| **Module** | **Description** |
|---|---|
| **Anomaly Detector** | Deterministic rule-based detection — latency spikes, error surges, burst patterns, status irregularities |
| **Incident Clusterer** | Groups anomalous events into deduplicated incidents by service, endpoint, error signature, and time window |
| **Deployment Correlator** | Matches incident timing against deployment events using configurable time-window heuristics |
| **Timeline Service** | Records and streams the full lifecycle of each incident from detection through resolution |
| **Correlation Engine** | Rule-based causal chain detection across incidents using temporal proximity and known cascade patterns |
| **AI Orchestration** | Multi-provider chain (Gemini → Groq) with silent failover, confidence scoring, and fix command generation |
| **Log Simulator** | Generates realistic synthetic API traffic and injects rotating failure scenarios for live demo |
| **Ingest Pipeline** | Accepts real external telemetry via REST, runs detection, clustering, and background AI analysis |
| **Project Analyzer** | Parses uploaded log files and ZIP archives to produce AI-generated resilience audit reports |
| **SSE Streaming** | Server-Sent Events endpoint pushes log events to the frontend in real time without polling |

---

## **Tech Stack**

| **Layer** | **Technology** | **Purpose** |
|---|---|---|
| **Backend Framework** | FastAPI | Async REST API, SSE streaming, background tasks |
| **Database** | SQLite | Zero-config persistent storage for logs, incidents, deployments, timelines |
| **Primary AI** | Google Gemini 2.5 Flash | Root-cause analysis, fix commands, resilience audit |
| **Fallback AI** | Groq (llama-3.3-70b, mixtral) | Silent failover when Gemini quota is exhausted |
| **Frontend Framework** | Next.js 14 (App Router) | React server/client components, file-based routing |
| **Styling** | Tailwind CSS | Utility-first dark observability theme |
| **Charts** | Recharts | Composable time-series metrics chart |
| **Icons** | Lucide React | Consistent iconography throughout dashboard |
| **HTTP Client** | httpx | Async AI provider calls with timeout handling |
| **File Parsing** | Python stdlib (zipfile, re) | ZIP inspection and log pattern extraction |
| **Frontend Hosting** | Vercel Free Tier | Automatic deploys from GitHub |
| **Backend Hosting** | Render Free Tier | Containerized FastAPI deployment |
| **Total Cost** | **$0** | Entirely free-tier infrastructure |

---

## **AI Engineering Highlights**

**Multi-provider orchestration** — The AI service layer implements a five-model fallback chain across two providers. Each model maintains independent state (available / exhausted / disabled). When a model fails due to quota exhaustion, rate limiting, timeout, or malformed response, it is marked exhausted and the next model is tried immediately — all within the same request cycle, invisibly to the user.

**Structured output generation** — All AI calls request strict JSON responses and implement robust extraction that handles markdown fences, surrounding text, and partial responses. A regex-based fallback attempts to recover valid JSON from malformed completions before declaring failure.

**Confidence scoring** — Qualitative AI labels (High Likelihood, Moderate Likelihood, Needs Investigation) are mapped to numeric confidence scores and rendered as animated CSS progress bars with per-label color coding.

**Statistical fallback** — When every AI provider is unavailable, deterministic algorithms generate human-readable incident summaries and architecture audit reports from the parsed statistics. The user experience is identical — only the source of the text changes.

**Contextual fix generation** — Fix command snippets are generated in a second AI call using the incident's specific error signature, service name, and root cause as prompt context. The same provider chain handles this call with the same failover guarantees.

---

## **API Reference**

| **Method** | **Endpoint** | **Description** |
|---|---|---|
| GET | `/api/status` | System KPIs and AI provider status |
| GET | `/api/logs/stream` | SSE stream of new log events |
| GET | `/api/logs/timeseries` | Per-minute bucketed metrics |
| GET | `/api/incidents` | List incidents with source/severity/AI filters |
| GET | `/api/incidents/{id}/timeline` | Lifecycle event timeline |
| GET | `/api/incidents/{id}/correlation` | Root-cause correlation graph |
| POST | `/api/incidents/{id}/resolve` | Resolve an incident |
| POST | `/api/ai/analyse/{id}` | Run AI RCA + fix command generation |
| POST | `/api/ingest` | Ingest real external telemetry |
| POST | `/api/analyzer/upload` | Upload ZIP or log file for analysis |
| GET | `/api/analyzer/results/{job_id}` | Poll analysis job results |
| GET | `/api/deployments/recent` | Recent deployment events |

---

## **Failure Scenarios Simulated**

| **Scenario** | **Service** | **Error** | **Pattern** |
|---|---|---|---|
| JWT Key Mismatch | Auth API | 401 JWT_MISMATCH | Burst of 8 events after key rotation deploy |
| Database Timeout Cascade | Orders API | 504 DB_TIMEOUT | 6 events after connection pool config change |
| Schema Validation Failure | Payment API | 400 MALFORMED_PAYLOAD | 10 events after SDK version mismatch deploy |
| Deployment Regression | Orders API | 500 INTERNAL_ERROR | 7 events after null pointer introduced in hotfix |
| SMTP Dependency Outage | Notification API | 503 UPSTREAM_UNAVAILABLE | 9 events after provider DNS migration |
| Consumer Retry Storm | Orders API | 429 RATE_LIMITED | 15 events after retry backoff removed |

---

## **Connect Your API**

Send real production telemetry to PulseDebug with one curl command:

```bash
curl -X POST https://pulsedebug-ai.onrender.com/api/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "service":         "Your Service Name",
    "endpoint":        "/your/endpoint",
    "status":          500,
    "latency":         4200,
    "error_signature": "DB_TIMEOUT",
    "method":          "POST"
 }
```

SDK middleware snippets for FastAPI, Flask, Django, Express.js, and Node.js are available at: https://pulsedebug-ai.vercel.app/integrate
Built with FastAPI · Next.js · Gemini · Groq · SQLite · Vercel · Render
