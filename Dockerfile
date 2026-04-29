FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_STAGE=production \
    PORT=7860 \
    STORAGE_DIR=/data/ascent-storage

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt

RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY backend ./backend

RUN mkdir -p /tmp/ascent-storage

EXPOSE 7860

CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1"]
