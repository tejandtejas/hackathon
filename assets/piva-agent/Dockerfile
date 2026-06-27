# ── Stage 1: dependency builder ──────────────────────────────────────────────
FROM python:3.11-slim AS builder

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:0.6.16 /uv /usr/local/bin/uv

WORKDIR /app

# Copy only the requirements first so Docker can cache the layer
COPY requirements.txt ./

# Install into a virtualenv so we can copy just the venv to the runtime stage
RUN uv venv /opt/venv \
 && uv pip install --python /opt/venv/bin/python --no-cache -r requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user for security
RUN useradd --create-home --no-log-init appuser
USER appuser

WORKDIR /home/appuser/service

# Pull in the pre-built virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy the full application source
COPY --chown=appuser:appuser . .

# Default port (overridden at runtime by CF/Kyma PORT env var)
ENV PORT=5000
EXPOSE 5000

# Health-check: hit the A2A agent card endpoint
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD python -c "import urllib.request, os; urllib.request.urlopen('http://localhost:' + os.environ.get('PORT','5000') + '/.well-known/agent.json')"

# Start gunicorn with uvicorn worker (mirrors Procfile)
CMD gunicorn \
      --worker-class uvicorn.workers.UvicornWorker \
      --workers 2 \
      --bind "0.0.0.0:${PORT}" \
      --chdir app \
      main:application
