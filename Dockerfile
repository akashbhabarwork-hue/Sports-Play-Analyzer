# Stage 1: Build the frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.12-slim
WORKDIR /app/backend

# Install system dependencies (ffmpeg, curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Pretrained detector (YOLOX-S, Apache-2.0) from the official release; the build fails if the
# checksum differs. Weights are never committed to git. See D-025.
ARG MODEL_URL=https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_s.onnx
ARG MODEL_SHA256=c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063
RUN mkdir -p /models \
    && curl -fsSL --retry 3 -o /models/yolox_s.onnx "$MODEL_URL" \
    && echo "$MODEL_SHA256  /models/yolox_s.onnx" | sha256sum -c -

# Install python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./

# Copy frontend build output to static directory
COPY --from=frontend-builder /build/dist ./static/

# Add non-root user and setup blob storage directory
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/blobs && \
    chown -R appuser:appuser /app

USER appuser
ENV BLOB_LOCAL_DIR=/app/blobs \
    STATIC_DIR=/app/backend/static \
    MODEL_PATH=/models/yolox_s.onnx

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "--factory", "app.entrypoints.api:create_app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
