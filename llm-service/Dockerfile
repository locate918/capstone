# ============================================================================
# Locate918 Python LLM Service - Dockerfile
# ============================================================================
# Runs the FastAPI service (Tully chat, smart search, normalize).

FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Railway sets PORT env var automatically
ENV PORT=8001

EXPOSE $PORT

# Run with uvicorn, binding to 0.0.0.0 on the PORT env var
CMD uvicorn main:app --host 0.0.0.0 --port $PORT