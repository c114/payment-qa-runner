FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libdbus-1-3 libxkbcommon0 libatspi2.0-0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt /app/backend-requirements.txt
COPY worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/backend-requirements.txt playwright==1.49.1 \
    && playwright install --with-deps chromium || playwright install chromium || true
COPY backend /app/backend
COPY worker /app/worker
COPY docs /app/docs
ENV PYTHONPATH=/app/backend:/app
ENV DATABASE_URL=sqlite:////data/payment_qa.db
ENV SCREENSHOT_DIR=/data/screenshots
ENV REPORT_DIR=/data/reports
ENV LOG_DIR=/data/logs
ENV SESSION_DIR=/data/sessions
ENV TRACE_DIR=/data/traces
ENV PLAYWRIGHT_MOCK=0
ENV LIVE_TESTING_ENABLED=true
ENV WORKER_HEARTBEAT_FILE=/data/logs/worker.heartbeat
ENV SANDBOX_BASE_URL=http://sandbox:8080
ENV APP_VERSION=2.0.0
WORKDIR /app
CMD ["python", "-m", "worker.runner"]
