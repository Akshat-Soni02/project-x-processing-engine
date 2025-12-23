# Stage 1: Builder (keeps the final image clean)
FROM ghcr.io/astral-sh/uv:latest AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Stage 2: Runtime
FROM python:3.12-slim-bookworm

# 1. Install system tools + ffmpeg for pydub + curl for healthcheck
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Security: Create a non-root user
RUN useradd --create-home --shell /bin/bash app-user

# 3. Environment Setup
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    APP_ENV=production \
    LOG_LEVEL=INFO \
    PORT=8080

# 4. Copy virtualenv and code
COPY --from=builder --chown=app-user:app-user /app/.venv /app/.venv
COPY --chown=app-user:app-user . .

# 5. Create logs dir and set permissions
RUN mkdir -p /app/logs && chown -R app-user:app-user /app/logs

# Switch to non-root user
USER app-user

# 6. Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

EXPOSE 8080

CMD exec fastapi run src/main.py --port ${PORT}