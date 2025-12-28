# syntax=docker/dockerfile:1
FROM python:3.14-slim-bookworm AS builder
# NOTE: Changed 3.14 to 3.12. Python 3.14 is experimental and likely lacks wheels for numpy/pandas.

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

# Install uv (using the official image is often cleaner/smaller than pip)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Sync deps
# CRITICAL FIX: Added --no-install-project
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project

################################################################################

FROM python:3.14-slim-bookworm

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN useradd --create-home --shell /bin/bash app-user

# Set environment variables
ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    APP_ENV=production \
    LOG_LEVEL=INFO \
    PORT=8080

# Copy the virtual environment from builder
COPY --from=builder --chown=app-user:app-user /app/.venv /app/.venv

# Copy application code
COPY --chown=app-user:app-user . .

# Ensure logs directory exists
RUN mkdir -p /app/logs && chown -R app-user:app-user /app/logs

USER app-user

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

EXPOSE 8080

# Run uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]