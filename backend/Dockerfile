FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend /app/backend
# docs/ is tracked (at least README); ensure path exists for help/UI reference
RUN mkdir -p /app/docs/screenshots
COPY docs/ /app/docs/
ENV PYTHONPATH=/app/backend
ENV DATABASE_URL=sqlite:////data/payment_qa.db
ENV SCREENSHOT_DIR=/data/screenshots
ENV REPORT_DIR=/data/reports
ENV LOG_DIR=/data/logs
ENV PLAYWRIGHT_MOCK=0
ENV LIVE_TESTING_ENABLED=false
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
