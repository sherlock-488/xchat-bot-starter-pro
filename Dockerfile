# xchat-bot-starter-pro — multi-stage Docker build
# Stage 1: Build dependencies into a venv
FROM python:3.11-slim AS builder

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy everything needed for uv sync
COPY pyproject.toml uv.lock README.md ./
# Minimal package stub so uv can resolve the local package during dependency install
RUN mkdir -p src/xchat_bot && touch src/xchat_bot/__init__.py

# Install production dependencies into /app/.venv (reproducible, lock-file driven)
RUN uv sync --no-dev --frozen

# Stage 2: Runtime
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy the populated venv from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source and package metadata
COPY src/ /app/src/
COPY pyproject.toml README.md /app/

# Install uv in runtime stage so we can install the local package into the venv
RUN pip install --no-cache-dir uv && \
    uv pip install --python /app/.venv/bin/python -e . --no-deps && \
    pip uninstall -y uv

# Put the venv on PATH
ENV PATH="/app/.venv/bin:$PATH"

# Create non-root user
RUN useradd --create-home --shell /bin/bash xchat
USER xchat

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/healthz', timeout=3).raise_for_status()" || exit 1

# Default: run webhook transport with the built-in echo bot.
# Override with: docker run ... xchat run --bot xchat_bot.examples.echo_bot:EchoBot
CMD ["xchat", "run", "--transport", "webhook", "--bot", "xchat_bot.examples.echo_bot:EchoBot"]

EXPOSE 8080
