#!/usr/bin/env bash
# PulseDebug AI — Backend Dev Start Script
# File: backend/start.sh
# Purpose:
#   Convenience script to start the FastAPI backend locally.
#   Activates the virtual environment if one exists, then launches
#   uvicorn with hot-reload enabled for development.
#
# Usage:
#   chmod +x start.sh
#   ./start.sh

set -e

echo "🚀 Starting PulseDebug AI Backend..."

# Activate venv if it exists
if [ -d "venv" ]; then
  source venv/bin/activate
elif [ -d ".venv" ]; then
  source .venv/bin/activate
fi

# Load .env if present
if [ -f ".env" ]; then
  export $(grep -v '^#' .env | xargs)
  echo "✅ Loaded .env"
fi

# Check for API key
if [ -z "$GEMINI_API_KEY" ]; then
  echo "⚠️  WARNING: GEMINI_API_KEY not set — AI analysis will be disabled"
  echo "   Copy backend/.env.example to backend/.env and add your key."
fi

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000