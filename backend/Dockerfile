# PulseDebug AI — Backend Dockerfile
# File: backend/Dockerfile
# Purpose:
#   Production-ready container for the FastAPI backend.
#   Uses Python 3.11 slim base to minimize image size.
#   Supports both SQLite (local dev) and PostgreSQL (production)
#   through environment variables — no code changes needed.

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed for psycopg2 (PostgreSQL driver)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching
# If requirements.txt hasn't changed, this layer is reused
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for SQLite fallback in local dev
RUN mkdir -p /app/data

# Expose backend port
EXPOSE 8000

# Run uvicorn in production mode
# Workers set to 1 for SQLite compatibility
# Increase to 4 when using PostgreSQL in production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]