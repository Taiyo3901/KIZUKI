# Build from the repository root:  docker build -f services/analyzer/Dockerfile -t analyzer .
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1
COPY services/analyzer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared ./shared
COPY services/analyzer/app ./app
COPY services/analyzer/pipeline ./pipeline
# Cloud Run provides $PORT
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
