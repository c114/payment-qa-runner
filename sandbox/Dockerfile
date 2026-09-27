FROM python:3.12-slim
WORKDIR /app
COPY sandbox/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY sandbox /app
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
