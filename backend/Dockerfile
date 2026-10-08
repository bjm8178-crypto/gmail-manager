# Multi-stage build for Gmail Manager Backend
# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies for PostgreSQL and compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime image
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies (PostgreSQL client library)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY *.py ./
COPY postgres_schema.sql ./
COPY sqlite_schema.sql ./

# Create logs directory
RUN mkdir -p logs

# Make sure scripts are executable
ENV PATH=/root/.local/bin:$PATH

# Expose port 8000
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

# Run uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
