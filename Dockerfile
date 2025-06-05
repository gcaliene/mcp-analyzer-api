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

# Expose FastAPI client port
EXPOSE 8001

# Default command: run the client
ENTRYPOINT ["python", "client.py"] 