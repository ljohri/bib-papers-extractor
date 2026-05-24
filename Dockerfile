# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# System deps. pymupdf and pdfplumber pull in MuPDF / pdfminer runtime libs;
# build-essential covers their wheels' build prerequisites if a wheel is missing.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        git \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install uv from the official Astral image's binary.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Resolve dependencies first for cache friendliness.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY docs ./docs

# Install the project itself now that source is present.
RUN uv sync --frozen --no-dev

ENV PYTHONPATH=/app/src

# Default mount points (override via -v on `docker run`).
VOLUME ["/data", "/cache"]

# stdio MCP server — Claude Desktop attaches over stdin/stdout.
ENTRYPOINT ["uv", "run", "--no-dev", "python", "-m", "bibpdf_mcp.server"]
