FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for MetaTrader5
RUN apt-get update && apt-get install -y --no-install-recommends \
    wine64 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import requests; r=requests.get('http://localhost:5000/health'); exit(0 if r.status_code==200 else 1)"

# Run with gunicorn
CMD ["gunicorn", "app:app", "--workers", "1", "--timeout", "120", "--bind", "0.0.0.0:5000", "--access-logfile", "-"]
