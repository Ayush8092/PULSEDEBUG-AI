/**
 * PulseDebug AI — SDK Integration Docs Page
 * File: frontend/src/app/integrate/page.tsx
 * Purpose:
 *   Production-polish SDK integration docs. Changes from previous version:
 *   - All snippets use threading for non-blocking fire-and-forget monitoring
 *   - Production URL (https://pulsedebug-ai.onrender.com) not localhost
 *   - "Lightweight drop-in integration" replaces "No SDK to install"
 *   - "Start monitoring instantly" replaces "No account required"
 *   - "Asynchronously without affecting request latency" in step descriptions
 *   - TypeScript types written without angle-bracket generics
 *
 */

"use client";

import { useState } from "react";
import Link from "next/link";
import { Copy, Check, ArrowLeft, Zap } from "lucide-react";

const PROD_URL = "https://pulsedebug-ai.onrender.com";

// Types — no angle brackets to prevent HTML stripping in chat copy-paste


type SnippetEntry = {
  label: string;
  language: string;
  code: string;
};

type SnippetsMap = {
  [key: string]: SnippetEntry;
};

// Snippets — non-blocking threading pattern throughout


const SNIPPETS: SnippetsMap = {
  fastapi: {
    label: "FastAPI",
    language: "python",
    code: `# PulseDebug AI - FastAPI Middleware Integration
# Lightweight drop-in integration — add BEFORE route definitions.
# pip install requests

import time
import threading
import requests
from fastapi import FastAPI, Request

app = FastAPI()

PULSEDEBUG_URL = "${PROD_URL}/api/ingest"

def _send(payload: dict) -> None:
    """Fire-and-forget — runs in daemon thread, never blocks requests."""
    try:
        requests.post(PULSEDEBUG_URL, json=payload, timeout=2)
    except Exception:
        pass

@app.middleware("http")
async def pulsedebug_monitor(request: Request, call_next):
    start    = time.time()
    response = await call_next(request)
    latency  = int((time.time() - start) * 1000)

    threading.Thread(
        target=_send,
        args=({
            "service":  "My FastAPI Service",
            "endpoint": request.url.path,
            "status":   response.status_code,
            "latency":  latency,
            "method":   request.method,
        },),
        daemon=True,
    ).start()

    return response`,
  },

  flask: {
    label: "Flask",
    language: "python",
    code: `# PulseDebug AI - Flask Middleware Integration
# Lightweight drop-in integration — add to your app.py.
# pip install requests

import time
import threading
import requests
from flask import Flask, request, g

app = Flask(__name__)

PULSEDEBUG_URL = "${PROD_URL}/api/ingest"

def _send(payload: dict) -> None:
    try:
        requests.post(PULSEDEBUG_URL, json=payload, timeout=2)
    except Exception:
        pass

@app.before_request
def before_request():
    g.pulsedebug_start = time.time()

@app.after_request
def after_request(response):
    latency = int((time.time() - g.pulsedebug_start) * 1000)
    threading.Thread(
        target=_send,
        args=({
            "service":  "My Flask Service",
            "endpoint": request.path,
            "status":   response.status_code,
            "latency":  latency,
            "method":   request.method,
        },),
        daemon=True,
    ).start()
    return response`,
  },

  django: {
    label: "Django",
    language: "python",
    code: `# PulseDebug AI - Django Middleware Integration
# 1. Create file: myapp/middleware.py
# 2. Add to MIDDLEWARE in settings.py:
#    'myapp.middleware.PulseDebugMiddleware'
# pip install requests

import time
import threading
import requests

PULSEDEBUG_URL = "${PROD_URL}/api/ingest"

def _send(payload: dict) -> None:
    try:
        requests.post(PULSEDEBUG_URL, json=payload, timeout=2)
    except Exception:
        pass

class PulseDebugMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start    = time.time()
        response = self.get_response(request)
        latency  = int((time.time() - start) * 1000)
        threading.Thread(
            target=_send,
            args=({
                "service":  "My Django Service",
                "endpoint": request.path,
                "status":   response.status_code,
                "latency":  latency,
                "method":   request.method,
            },),
            daemon=True,
        ).start()
        return response`,
  },

  express: {
    label: "Express.js",
    language: "javascript",
    code: `// PulseDebug AI - Express.js Middleware Integration
// Lightweight drop-in integration — add BEFORE route definitions.
// npm install axios

const axios = require("axios");

const PULSEDEBUG_URL = "${PROD_URL}/api/ingest";

// Sends asynchronously without affecting request latency
function sendAsync(payload) {
  axios
    .post(PULSEDEBUG_URL, payload, { timeout: 2000 })
    .catch(() => {});
}

function pulseDebugMonitor(req, res, next) {
  const start = Date.now();
  res.on("finish", () => {
    sendAsync({
      service:  "My Express Service",
      endpoint: req.path,
      status:   res.statusCode,
      latency:  Date.now() - start,
      method:   req.method,
    });
  });
  next();
}

app.use(pulseDebugMonitor);`,
  },

  node: {
    label: "Node.js (http)",
    language: "javascript",
    code: `// PulseDebug AI - Node.js http Integration
// Works with plain http/https — no Express required.
// Sends asynchronously without affecting request latency.

const http  = require("http");
const https = require("https");

const PULSEDEBUG_URL = "${PROD_URL}/api/ingest";

function sendAsync(data) {
  try {
    const body    = JSON.stringify(data);
    const urlObj  = new URL(PULSEDEBUG_URL);
    const isHttps = urlObj.protocol === "https:";
    const options = {
      hostname: urlObj.hostname,
      port:     urlObj.port || (isHttps ? 443 : 80),
      path:     urlObj.pathname,
      method:   "POST",
      headers:  {
        "Content-Type":   "application/json",
        "Content-Length": Buffer.byteLength(body),
      },
      timeout: 2000,
    };
    const req = (isHttps ? https : http).request(options);
    req.on("error", () => {});
    req.write(body);
    req.end();
  } catch (_) {}
}

const server = http.createServer((req, res) => {
  const start = Date.now();
  res.on("finish", () => {
    sendAsync({
      service:  "My Node Service",
      endpoint: req.url,
      status:   res.statusCode,
      latency:  Date.now() - start,
      method:   req.method,
    });
  });
  // your handler logic here
});`,
  },
};

// Code block with copy button

function CodeBlock({ code, language }: { code: string; language: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative rounded-lg border border-[#30363d] overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-[#161b22] border-b border-[#30363d]">
        <span className="font-mono text-xs text-[#484f58]">{language}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-xs font-mono text-[#8b949e] hover:text-[#e6edf3] transition-colors"
        >
          {copied ? (
            <>
              <Check size={12} className="text-[#3fb950]" />
              <span className="text-[#3fb950]">Copied!</span>
            </>
          ) : (
            <>
              <Copy size={12} />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-4 overflow-x-auto bg-[#0d1117] text-xs font-mono text-[#c9d1d9] leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  );
}

// Main page

export default function IntegratePage() {
  const [activeTab, setActiveTab] = useState("fastapi");
  const snippet = SNIPPETS[activeTab];
  const tabKeys = Object.keys(SNIPPETS);

  return (
    <div className="min-h-screen bg-[#0d1117]">

      <header className="border-b border-[#30363d] bg-[#0d1117]/90 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 text-[#8b949e] hover:text-[#e6edf3] transition-colors">
            <ArrowLeft size={14} />
            <span className="text-sm font-mono">Back to Dashboard</span>
          </Link>
          <div className="flex items-center gap-2">
            <Zap size={14} className="text-[#00d4ff]" />
            <span className="font-display font-bold text-[#e6edf3]">PulseDebug</span>
            <span className="font-display font-bold text-[#00d4ff]">AI</span>
            <span className="font-mono text-xs text-[#484f58] ml-2">SDK Integration</span>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10 space-y-10">

        {/* Hero */}
        <div>
          <h1 className="font-display text-2xl font-bold text-[#e6edf3] mb-3">
            Connect Your API in 60 Seconds
          </h1>
          <p className="text-[#8b949e] text-sm leading-relaxed max-w-2xl">
            Lightweight drop-in integration for any backend. Start monitoring
            instantly — copy one snippet, restart your server, and real telemetry
            begins streaming into PulseDebug automatically.
          </p>
        </div>

        {/* Endpoint reference */}
        <div className="card p-5 space-y-4">
          <p className="section-header">Ingest Endpoint</p>
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-mono text-xs px-2 py-1 rounded bg-[#3fb950]/10 text-[#3fb950] border border-[#3fb950]/20">
              POST
            </span>
            <code className="font-mono text-sm text-[#00d4ff]">
              {PROD_URL}/api/ingest
            </code>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
            <div>
              <p className="text-xs font-mono text-[#484f58] mb-3">REQUIRED FIELDS</p>
              <div className="space-y-2 text-xs font-mono">
                {[
                  ["service",  "string",  "your service name"],
                  ["endpoint", "string",  "the route path"],
                  ["status",   "integer", "HTTP status code 100-599"],
                  ["latency",  "integer", "response time in ms"],
                ].map(([name, type, desc]) => (
                  <div key={name} className="flex gap-2">
                    <span className="text-[#00d4ff] w-20 flex-shrink-0">{name}</span>
                    <span className="text-[#484f58] w-14 flex-shrink-0">{type}</span>
                    <span className="text-[#8b949e]">{desc}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <p className="text-xs font-mono text-[#484f58] mb-3">OPTIONAL FIELDS</p>
              <div className="space-y-2 text-xs font-mono">
                {[
                  ["error_signature", "string", "e.g. DB_TIMEOUT"],
                  ["error_msg",       "string", "full error message"],
                  ["method",          "string", "GET / POST / etc"],
                ].map(([name, type, desc]) => (
                  <div key={name} className="flex gap-2">
                    <span className="text-[#a371f7] w-28 flex-shrink-0">{name}</span>
                    <span className="text-[#484f58] w-14 flex-shrink-0">{type}</span>
                    <span className="text-[#8b949e]">{desc}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Snippet tabs */}
        <div>
          <p className="section-header mb-4">Integration Snippets</p>
          <div className="flex gap-1 mb-4 flex-wrap">
            {tabKeys.map((key) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={
                  activeTab === key
                    ? "px-3 py-1.5 rounded text-xs font-mono bg-[#00d4ff]/10 text-[#00d4ff] border border-[#00d4ff]/30 transition-all duration-150"
                    : "px-3 py-1.5 rounded text-xs font-mono text-[#8b949e] hover:text-[#e6edf3] hover:bg-[#21262d] border border-transparent transition-all duration-150"
                }
              >
                {SNIPPETS[key].label}
              </button>
            ))}
          </div>
          {snippet && <CodeBlock code={snippet.code} language={snippet.language} />}
        </div>

        {/* What happens next */}
        <div className="card p-5">
          <p className="section-header mb-4">What Happens After You Connect</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                step: "01", color: "#00d4ff",
                title: "Events Stream In",
                desc: "Every API call is reported asynchronously without affecting request latency.",
              },
              {
                step: "02", color: "#a371f7",
                title: "Anomalies Detected",
                desc: "Latency spikes, error bursts, and status irregularities are flagged automatically.",
              },
              {
                step: "03", color: "#3fb950",
                title: "AI Explains Incidents",
                desc: "When failures cluster, Gemini generates root-cause analysis and debugging steps.",
              },
            ].map((item) => (
              <div key={item.step} className="space-y-2">
                <div className="font-mono text-xs" style={{ color: item.color }}>STEP {item.step}</div>
                <p className="font-medium text-sm text-[#e6edf3]">{item.title}</p>
                <p className="text-xs text-[#8b949e] leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Quick test */}
        <div className="card p-5">
          <p className="section-header mb-3">Test the Endpoint Right Now</p>
          <p className="text-xs text-[#8b949e] mb-3">
            Run this curl command to send a test event immediately:
          </p>
          <CodeBlock
            language="bash"
            code={`curl -X POST ${PROD_URL}/api/ingest \\
  -H "Content-Type: application/json" \\
  -d '{
    "service":         "My Test Service",
    "endpoint":        "/api/test",
    "status":          500,
    "latency":         4200,
    "error_signature": "DB_TIMEOUT",
    "error_msg":       "Connection pool exhausted after 4200ms",
    "method":          "POST"
  }'`}
          />
          <p className="text-xs text-[#484f58] mt-3 font-mono">
            Then open the dashboard — watch the incident appear in the feed within seconds.
          </p>
        </div>

      </main>
    </div>
  );
}