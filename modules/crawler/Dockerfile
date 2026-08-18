# ============================================================
# 爬蟲模組範本 —— 給負責爬蟲的同學填
# ============================================================
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------------
# 如果爬蟲有用到 Selenium / Playwright（需要真的開瀏覽器），
# 上面那段換成下面這種，會省掉一堆「本機跑得動、容器裡跑不動」的問題：
#
#   FROM mcr.microsoft.com/playwright/python:v1.49.0-noble
#   RUN playwright install --with-deps chromium
#
# 純 requests + BeautifulSoup 的話就維持 slim 即可。
# ------------------------------------------------------------

COPY app/ /app/

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
