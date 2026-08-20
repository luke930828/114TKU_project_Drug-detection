# ============================================================
# backend 模組範本 —— 之後把 src/防毒後端瘦身/ 的內容搬進 modules/backend/app/ 時再填
#
# 照 README-docker.md 的建議：
#   - modules/backend/app/       ← main.py、database.py、routers/ ...
#   - modules/backend/requirements.txt
#   - modules/backend/app/config.py   ← 集中管理 DB 連線字串與各模組位址，
#     取代 database.py／utils.py／routers/scan.py 裡寫死的密碼和 100.x.x.x
# ============================================================
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -f http://localhost:8000/ || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
