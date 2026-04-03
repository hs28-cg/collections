# ---- Base image ----
FROM python:3.11-slim AS base

# Prevents Python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE=1
# Ensures stdout/stderr are unbuffered
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# ---- System dependencies ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ---- Install dependencies ----
COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---- Copy application code ----
COPY . .

# ---- Create non-root user ----
RUN useradd --create-home appuser
USER appuser

# Azure provides PORT env variable dynamically
ENV PORT=8000

# ---- Expose port (for local runs) ----
EXPOSE 8000

# ---- Start server ----
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]