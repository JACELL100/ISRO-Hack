# ─── ISRO Lunar Ice Explorer — Backend Docker Image ──────────────────────────
# Build context: ./backend   (set in docker-compose.yml and CI)
#
# Build:  docker build -t isro-backend ./backend
# Run:    docker run -p 8000:8000 isro-backend

FROM python:3.11-slim

# System deps for scipy/matplotlib/scikit-image (no GDAL — rasterio not used)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code + pre-built LOLA DEM (data/faustini_dem.npy ~1 MB)
COPY . .

ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV ISRO_SCENE_SIZE=256

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
