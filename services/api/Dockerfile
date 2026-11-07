# Build from the repository root:  docker build -f services/api/Dockerfile -t api .
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1 BACKEND=gcp AUTH_MODE=firebase APP_CHECK=on
COPY services/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared ./shared
COPY services/api/app ./app
# Cloud Run provides $PORT
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
