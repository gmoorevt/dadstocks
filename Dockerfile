# Use Python 3.9 slim image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        python3-dev \
        curl \
        sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create directory for SQLite database
RUN mkdir -p /app/instance && \
    chmod 777 /app/instance

# Create volume for database
VOLUME ["/app/instance"]

# Expose port
EXPOSE 5001

# Set default command (can be overridden by docker-compose)
CMD ["python", "app.py"] 