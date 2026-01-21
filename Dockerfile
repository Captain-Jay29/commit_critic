# Build stage
FROM python:3.12-slim as builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy project files (flat layout)
COPY pyproject.toml .
COPY __init__.py .
COPY cli.py .
COPY config.py .
COPY agents/ agents/
COPY vcs/ vcs/
COPY memory/ memory/
COPY output/ output/

# Create venv and install dependencies
RUN uv venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
RUN uv pip install --no-cache .

# Production stage
FROM python:3.12-slim as runtime

# Install git (required for GitPython)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash critic
USER critic

# Set working directory
WORKDIR /home/critic

# Copy virtual environment from builder
COPY --from=builder /app/.venv /home/critic/.venv

# Set environment
ENV PATH="/home/critic/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create data directory
RUN mkdir -p /home/critic/.commit-critic

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD critic version || exit 1

# Default command
ENTRYPOINT ["critic"]
CMD ["--help"]
