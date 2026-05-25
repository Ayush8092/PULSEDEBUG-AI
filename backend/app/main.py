"""
PulseDebug AI — Backend Entry Point
=====================================
File: backend/app/main.py
Purpose:
    FastAPI application factory and root configuration.
    Registers all API routers, configures CORS for the Next.js frontend,
    initialises the SQLite database on startup, and starts the background
    log-simulator so the dashboard has live data from the moment the
    server boots.

    Routers registered:
        /api/health        — liveness + system status
        /api/logs          — log queries + SSE stream
        /api/incidents     — incident CRUD
        /api/deployments   — deployment events
        /api/ai            — Gemini analysis
        /api/ingest        — real external telemetry ingestion  (NEW)
        /api/analyzer      — upload-based project analyzer      (NEW)

Author: PulseDebug AI Hackathon Team
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import logs, incidents, deployments, ai_analysis, health
from app.api import ingest, analyzer
from app.core.database import init_db
from app.services.simulator import LogSimulator


simulator_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise database and start background simulator on startup."""
    global simulator_task
    init_db()
    simulator = LogSimulator()
    simulator_task = asyncio.create_task(simulator.run())
    yield
    if simulator_task:
        simulator_task.cancel()
        try:
            await simulator_task
        except asyncio.CancelledError:
            pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="PulseDebug AI",
        description=(
            "AI-powered API incident triage assistant. "
            "Detects anomalies, clusters failures, correlates deployments, "
            "provides Gemini-powered debugging guidance, accepts real external "
            "telemetry, and analyses uploaded project files."
        ),
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "https://*.vercel.app",
            "*",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router,       prefix="/api",              tags=["Health"])
    app.include_router(logs.router,         prefix="/api/logs",         tags=["Logs"])
    app.include_router(incidents.router,    prefix="/api/incidents",    tags=["Incidents"])
    app.include_router(deployments.router,  prefix="/api/deployments",  tags=["Deployments"])
    app.include_router(ai_analysis.router,  prefix="/api/ai",           tags=["AI Analysis"])
    app.include_router(ingest.router,       prefix="/api/ingest",       tags=["Ingest"])
    app.include_router(analyzer.router,     prefix="/api/analyzer",     tags=["Analyzer"])

    return app


app = create_app()
