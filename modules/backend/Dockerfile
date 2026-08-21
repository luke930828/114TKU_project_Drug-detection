FROM python:3.11-slim

WORKDIR /app

# curl 給 HEALTHCHECK 用
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

# 啟動時自動建表（冪等，不會重複建），不用再手動 python database.py
CMD ["sh", "-c", "python -c \"import database; database.Base.metadata.create_all(bind=database.engine)\" && uvicorn main:app --host 0.0.0.0 --port 8000"]
