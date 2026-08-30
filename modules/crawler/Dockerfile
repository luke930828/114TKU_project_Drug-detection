# ============================================================
# crawler 模組 —— Playwright + Playwright-stealth 的爬蟲服務
#
# 用官方 Playwright image：已經內建對應版本的 Chromium + 系統依賴
# （libgl、字型等），不用自己在 slim image 上補一堆 apt 套件。
# tag 版本要跟 requirements.txt 的 playwright==1.42.0 對齊，
# 版本不一致 pip 會裝新版 playwright 但瀏覽器二進位還是舊的，跑不動。
# ============================================================
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/

# config.json 裡的 record_paths 預設寫到 Record/，模組重啟資料就不見，
# 建議在 docker-compose 幫這個服務掛一個 volume 到 /app/Record

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
