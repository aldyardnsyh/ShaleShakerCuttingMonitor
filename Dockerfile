# Multi-stage build: compile the Next.js static export, then bake it into the
# Python backend image which serves both the API and the static frontend.
# Build context = repo root.

# ---- Stage 1: frontend static export ----------------------------------------
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
ENV NEXT_PUBLIC_API_BASE=""
RUN npm run build   # emits /fe/out (output: 'export')

# ---- Stage 2: backend runtime -----------------------------------------------
FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    STATIC_DIR=/app/static \
    MODELS_DIR=/models \
    DATA_DIR=/data \
    SOURCE_VIDEOS_DIR=/app/source_videos \
    ORT_INTRA_OP_THREADS=2 \
    ORT_INTER_OP_THREADS=1

# OpenCV (headless) runtime libs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
# Bake the built frontend into the image's static dir.
COPY --from=frontend /fe/out ./static
# Bake pre-loaded source (demo) videos into the image so they survive
# deployment without needing a separate volume copy.
COPY data/source_videos/ ./source_videos/

EXPOSE 8000
# Single worker keeps memory low; the CPU inference is the bottleneck anyway.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
