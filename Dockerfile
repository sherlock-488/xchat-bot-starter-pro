# xchat-bot-starter-pro — multi-stage Docker build
# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy lock file + manifest first for layer caching
COPY pyproject.toml uv.lock ./
# Create a minimal package stub so uv sync can resolve the local package
RUN mkdir -p src/xchat_bot && touch src/xchat_bot/__init__.py

# Install production dependencies from the lock file (reproducible)
RUN uv sync --no-dev --frozen

# Stage 2: Runtime
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ /app/src/
COPY pyproject.toml README.md /app/

# Install the package itself
RUN pip install --no-cache-dir -e . --no-deps

# Create non-root user
RUN useradd --create-home --shell /bin/bash xchat
USER xchat

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/healthz', timeout=3).raise_for_status()" || exit 1

# Default: run webhook transport with the built-in echo bot.
# Override the bot with: docker run ... xchat run --bot xchat_bot.examples.echo_bot:EchoBot
# To use a custom bot mounted at /app/bots/my_bot.py:
#   docker run -v ./bots:/app/bots ... xchat run --bot bots.my_bot:MyBot
CMD ["xchat", "run", "--transport", "webhook", "--bot", "xchat_bot.examples.echo_bot:EchoBot"]

EXPOSE 8080
