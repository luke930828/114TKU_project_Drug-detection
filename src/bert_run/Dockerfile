# ── 基底映像：Python 3.12 精簡版 ─────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# ── 系統依賴 ──────────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# ── 安裝 Python 套件 ─────────────────────────────────────────────────────────
COPY src/bert_run/requirements-nlp.txt .
RUN pip install --no-cache-dir -r requirements-nlp.txt

# ── 複製程式碼 ────────────────────────────────────────────────────────────────
COPY src/bert_run/ ./src/bert_run/

# ── 模型資料夾由外部掛載（model.safetensors 太大不打包進 image）─────────────
# docker run 時加上 -v ./results/final_model:/app/results/final_model
# 或在 docker-compose.yml 的 volumes 設定

EXPOSE 8000

# ── 啟動 FastAPI ──────────────────────────────────────────────────────────────
CMD ["uvicorn", "src.bert_run.api:app", "--host", "0.0.0.0", "--port", "8000"]
