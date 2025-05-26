# syntax=docker/dockerfile:1
FROM python:3.13-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv (https://github.com/astral-sh/uv)
RUN pip install --no-cache-dir uv

# Set workdir
WORKDIR /app

# Copy project files
COPY . .

# Install Python dependencies
RUN uv pip install --system --no-cache-dir -r pyproject.toml

# Copy entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose FastAPI client port
EXPOSE 8001

# Entrypoint
ENTRYPOINT ["/docker-entrypoint.sh"] 