# xchat-bot-starter-pro — multi-stage Docker build
# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv==0.4.0

# Copy dependency files
COPY pyproject.toml ./
# Create a minimal package structure for uv sync
RUN mkdir -p src/xchat_bot && touch src/xchat_bot/__init__.py

# Install production dependencies only
RUN uv sync --no-dev --frozen 2>/dev/null || uv pip install --system \
    fastapi \
    uvicorn[standard] \
    typer \
    httpx \
    pydantic \
    pydantic-settings \
    structlog \
    tenacity \
    cryptography \
    python-dotenv \
    rich \
    anyio

# Stage 2: Runtime
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ /app/src/
COPY bots/ /app/bots/
COPY pyproject.toml /app/

# Install the package itself
RUN pip install --no-cache-dir -e . --no-deps

# Create non-root user
RUN useradd --create-home --shell /bin/bash xchat
USER xchat

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/healthz', timeout=3).raise_for_status()" || exit 1

# Default: run webhook transport
# Override with: docker run ... xchat run --transport stream --bot bots.echo_bot:EchoBot
CMD ["xchat", "run", "--transport", "webhook", "--bot", "bots.echo_bot:EchoBot"]

EXPOSE 8080
