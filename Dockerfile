FROM python:3.13-slim

WORKDIR /app

# Install system dependencies (minimal - psycopg2-binary is precompiled)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY data/analytics/features/ ./data/analytics/features/

# Set Python path to find the package
ENV PYTHONPATH=/app/src

# Expose port
EXPOSE 8000

# Health check (Fly.io handles this via fly.toml, but keep for Docker Compose)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)"

# Run the application
CMD ["uvicorn", "phish_setlist_maker.api:app", "--host", "0.0.0.0", "--port", "8000"]
