FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (mainly for OpenCV rendering/fonts if needed, though headless is used)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure data directories exist for cloud deployment (ephemeral)
RUN mkdir -p uploads processed

# Expose port (Cloud providers inject PORT env var, defaults to 8000)
ENV PORT=8000
EXPOSE $PORT

# Start FastAPI via uvicorn
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
