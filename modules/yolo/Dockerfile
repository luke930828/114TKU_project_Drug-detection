FROM python:3.12-slim

# docker logs 抓到的也是導向管線的 stdout，一樣會被 Python 整段 buffer 住、看起來像卡住，
# 跟本機開發時遇到的問題一樣，容器也要設這個才能即時看到 log（main.py 裡也有做 line_buffering，這裡是雙保險）
ENV PYTHONUNBUFFERED=1

# opencv (cv2) 需要這兩個系統套件才能 import 成功，slim image 預設沒有，
# 沒裝的話 import cv2 會直接炸 libGL.so.1 找不到
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---- 第一層：torch + CUDA（4.5 GB，幾乎不會變）----
#
# 單獨一層的理由見 requirements-torch.txt。簡單說：GPU 版 torch 連帶的
# CUDA 函式庫有 4.5 GB，來源又慢（200～500 kB/s），跟其他套件混在同一個
# pip install 的話，requirements.txt 改一行就要重抓四小時。
#
# 不需要 nvidia/cuda 系列的 base image —— pip 裝 +cu128 wheel 時會自動帶進
# nvidia-cuda-runtime-cu12 等一整包 CUDA 執行期函式庫，真正的 GPU 驅動由
# nvidia-container-toolkit 在 container 啟動時注入，跟 base image 是哪個無關。
#
# --mount=type=cache 是第二道保險：就算這一層真的失效（換 torch 版本），
# 已經下載過的 wheel 還留在 BuildKit 的快取裡，不用再從 pypi.nvidia.com 拉。
# 用了 cache mount 就不要再加 --no-cache-dir，那兩個是互相抵消的。
COPY requirements-torch.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements-torch.txt \
        --extra-index-url https://download.pytorch.org/whl/cu128

# ---- 第二層：其餘套件（常改，但都很小）----
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt \
    # easyocr 會夾帶 opencv-python-headless，跟釘的 opencv-python 搶同一個 cv2
    # 命名空間，裝完後強制重裝一次指定版本，確保最後贏的是我們測過的那個
    # （見 requirements.txt 裡的說明）
    && pip install --force-reinstall --no-deps opencv-python==4.13.0.92

# ---- 第三層：把 EasyOCR 的模型先抓下來 ----
#
# EasyOCR 預設是「第一次用到才下載」，抓到 /root/.EasyOCR/（295 MB：
# chinese.pth 226 MB + craft_mlt_25k.pth 83 MB）。那個目錄沒有掛 volume，
# 所以每次重建容器都要重抓一次，而且下載發生在 import 階段、是同步的——
# 2026-09-03 實測，容器起來之後 /health 有整整 10 分鐘完全不回應，
# 從外面看就像服務掛了。沒網路的話 OCR 直接載入失敗。
#
# 改成 build 時就抓好。語言清單刻意從 ai_model/ocr.py 讀，不在這裡再寫一次
# ——寫兩份遲早會不一致，而不一致的下場是「build 時抓了 A、執行時要 B」，
# 又變回執行時下載。只複製 ocr.py 這一個檔案，避免整個 app/ 的改動
# 讓這 295 MB 的一層失效。
COPY app/ai_model/ocr.py /tmp/warm/ocr.py
RUN python -c "import sys; sys.path.insert(0, '/tmp/warm'); \
      from ocr import load_ocr_reader; load_ocr_reader(gpu=False)" \
    && rm -rf /tmp/warm

# app/ 底下的東西（main.py、ai_model/、models/）直接複製進 /app，
# 對應 main.py 用 __file__ 定位模型路徑的邏輯，最後會落在 /app/models/best.pt
COPY app/ .

EXPOSE 5000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
