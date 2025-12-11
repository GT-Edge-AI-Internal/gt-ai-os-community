# Control Panel Backend Dockerfile
FROM python:3.11-slim

# Build arg for dev dependencies (default: false for production)
ARG INSTALL_DEV=false

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements (dev requirements may not exist in production builds)
COPY requirements.txt .
COPY requirements-dev.tx[t] ./

# Install Python dependencies
# Dev dependencies only installed when INSTALL_DEV=true
RUN pip install --no-cache-dir -r requirements.txt && \
    if [ "$INSTALL_DEV" = "true" ] && [ -f requirements-dev.txt ]; then \
        pip install --no-cache-dir -r requirements-dev.txt; \
    fi

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run the application with multiple workers for production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]