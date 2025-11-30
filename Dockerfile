# TrendRadar AI Dockerfile
# Multi-stage build for optimized image size

FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir . && \
    pip install --no-cache-dir "crewai[anthropic]"

# Production image
FROM python:3.12-slim

# Create non-root user for security with home directory
RUN groupadd -r trendradar && \
    useradd -r -g trendradar -m -d /home/trendradar trendradar

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=trendradar:trendradar src/ ./src/
COPY --chown=trendradar:trendradar config/ ./config/
COPY --chown=trendradar:trendradar templates/ ./templates/

# Create output directory and set home
RUN mkdir -p /app/output && chown -R trendradar:trendradar /app/output
ENV HOME=/home/trendradar

# Switch to non-root user
USER trendradar

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose web UI port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/status')" || exit 1

# Default command - run web UI
CMD ["uvicorn", "src.web.app:create_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
