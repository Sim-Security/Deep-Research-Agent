# Deep Research Agent - Production Dockerfile
# Multi-stage build optimized for GCP Cloud Run
#
# Build: docker build -t deep-research-agent .
# Run:   docker run -p 8080:8080 --env-file .env deep-research-agent

# ============================================================================
# Stage 1: Builder - Install dependencies
# ============================================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Copy project files needed for installation
COPY pyproject.toml ./
COPY src/ ./src/
COPY README.md ./

# Create virtual environment and install dependencies (production only)
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install --no-cache .

# ============================================================================
# Stage 2: Runtime - Minimal production image for Cloud Run
# ============================================================================
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /root/.cache

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY src/ ./src/
COPY app.py ./
COPY langgraph.json ./

# Create non-root user for security (Cloud Run best practice)
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# Cloud Run requires port 8080
ENV PORT=8080
EXPOSE 8080

# Health check for container orchestration
# Cloud Run uses HTTP health checks on $PORT
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/_stcore/health || exit 1

# Default command: Run Streamlit app on Cloud Run port
# --server.enableCORS=false and --server.enableXsrfProtection=false for Cloud Run proxy
CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false"]
