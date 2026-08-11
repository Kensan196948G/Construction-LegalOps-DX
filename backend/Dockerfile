# syntax=docker/dockerfile:1.7
# Multi-stage build for Construction-LegalOps-DX backend.
# Stage 1: builder — install dependencies into a virtualenv.
# Stage 2: runtime — slim image, non-root user, healthcheck, uvicorn.

ARG PYTHON_VERSION=3.12

# ---------------------------------------------------------------------------
# Stage 1: builder
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

# Build-time tools required for C extensions (cryptography, bcrypt, etc.).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv "${VIRTUAL_ENV}" \
    && pip install --upgrade pip wheel "setuptools>=78.1.1"   # CVE-2025-47273 fix

WORKDIR /build

# Copy only dependency manifests first for better layer caching.
# README.md lives in backend/ and is referenced by pyproject.toml (hatchling
# requires the readme path to be within the project directory).
COPY pyproject.toml README.md ./

# Install into the virtualenv. Hatchling needs the package to exist for the
# editable install, so we generate a minimal layout and install runtime deps.
COPY app ./app
RUN pip install .

# ---------------------------------------------------------------------------
# Stage 2: runtime
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    APP_HOME=/app \
    PORT=8000

# Runtime libs only (no compilers).
# `apt-get upgrade -y` patches base-image OS packages (gnutls/krb5 等) to the
# latest Debian 12 security releases (deb12u7/deb12u5) so the weekly Trivy
# container scan (security.yml) stays green. The base image ships these libs
# pre-installed, so upgrade BEFORE installing the extra runtime deps.
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        ca-certificates \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --home-dir "${APP_HOME}" --shell /sbin/nologin app

COPY --from=builder /opt/venv /opt/venv

WORKDIR ${APP_HOME}
COPY --chown=app:app app ./app
COPY --chown=app:app alembic.ini ./alembic.ini
# Alembic migration scripts are added by the migrations team in a separate
# layer; the directory is created here so non-root permissions hold.
RUN mkdir -p ${APP_HOME}/alembic && chown -R app:app ${APP_HOME}

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl --fail --silent --show-error http://127.0.0.1:${PORT}/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
