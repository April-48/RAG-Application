# Build from repository root (see docker-compose.yml build.context).
# Installs backend/ as editable package `app`, then middleware deps.
# backend/ is NOT a separate HTTP service — it is imported in-process.

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/ ./backend/
COPY middleware/ ./middleware/

WORKDIR /app/middleware

RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

WORKDIR /app

RUN mkdir -p backend/storage/uploads

EXPOSE 8000

CMD ["uvicorn", "middleware.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
