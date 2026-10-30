FROM python:3.11-slim

# av 自带 ffmpeg 库，无需 apt 装 ffmpeg
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=8756 \
    MCAP_DATA_ROOT=/data/mcap2mp4_jobs \
    JOB_TTL_HOURS=48 \
    JOB_MAX_KEEP=50 \
    MAX_UPLOAD_MB=8192

WORKDIR /app

# 先 copy requirements 利用 Docker 层缓存
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

RUN mkdir -p /data/mcap2mp4_jobs

EXPOSE 8756

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; \
    sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8756/api/health',timeout=3).status==200 else 1)"

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8756", "--proxy-headers"]
