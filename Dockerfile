FROM python:3.12-slim

WORKDIR /app

# Prevent .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system build deps (needed for some wheels)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy package files first for layer caching
COPY pyproject.toml README.md ./
COPY testweavex/ testweavex/

# Install with all optional LLM providers; postgres support is optional
RUN pip install --no-cache-dir ".[anthropic,openai,ollama]"

# Persistent data directory — mount a volume here in production
RUN mkdir -p /data/.testweavex
ENV DATABASE_URL=sqlite:////data/.testweavex/results.db

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/dashboard')" || exit 1

CMD ["tw", "serve", "--host", "0.0.0.0", "--port", "8080"]
