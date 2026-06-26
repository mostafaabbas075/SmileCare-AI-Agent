# ── Base ──────────────────────────────────────────────────────────────────────
# Use Python 3.11 to match the local development environment (venv)
# and ensure dependency compatibility.
FROM python:3.11-slim AS base

# Optimize Python behavior inside the container.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install only the required system packages.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install project dependencies separately to leverage Docker layer caching.
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy the application source code after installing dependencies.
# This prevents reinstalling packages when only the source code changes.
COPY . .

# ── Development ───────────────────────────────────────────────────────────────
FROM base AS development

# Install development dependencies (pytest, ruff, etc.).
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt

EXPOSE 8000

# docker-compose will override this command if needed.
# This serves as the default fallback command.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Production ────────────────────────────────────────────────────────────────
FROM base AS production

# Create and use a non-root user for improved security.
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

EXPOSE 8000

# Run the application with Gunicorn using Uvicorn workers for production.
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120"]