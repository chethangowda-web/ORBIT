# ==============================================================================
# ORBIT Backend: multi-stage build on python:3.11-slim, runs as a non-root user
# ==============================================================================

# Base image is configurable so builds can use a registry mirror when Docker Hub is
# unreachable: --build-arg PYTHON_IMAGE=mirror.gcr.io/library/python:3.11-slim
ARG PYTHON_IMAGE=python:3.11-slim

# ---- Stage 1: build dependencies into a virtualenv --------------------------
FROM ${PYTHON_IMAGE} AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: slim runtime --------------------------------------------------
FROM ${PYTHON_IMAGE} AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system --gid 1001 orbit \
    && adduser --system --uid 1001 --ingroup orbit orbit

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY --chown=orbit:orbit . .
RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /app/uploads && chown orbit:orbit /app/uploads

USER orbit
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Applies migrations (RULES.md 3.1), optionally seeds, then starts the API.
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
