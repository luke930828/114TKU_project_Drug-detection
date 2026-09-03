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

# 先只複製 requirements.txt 裝套件，程式碼改動不會讓這層快取失效，重build比較快
#
# GPU 版：torch/torchvision 釘的是 +cu128，用 --extra-index-url 讓 pip 找得到這個 local
# version；其他套件（fastapi、numpy...）還是照舊從預設的 PyPI 裝，兩邊不衝突。
# 不需要 nvidia/cuda 系列的 base image —— pip 裝 +cu128 wheel 時會自動帶進
# nvidia-cuda-runtime-cu12 等一整包 CUDA 執行期函式庫，真正的 GPU 驅動由
# nvidia-container-toolkit 在 container 啟動時注入，跟 base image 是哪個無關。
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
        --extra-index-url https://download.pytorch.org/whl/cu128 \
    # easyocr 會夾帶 opencv-python-headless，跟上面釘的 opencv-python 搶同一個 cv2 命名空間，
    # 裝完後強制重裝一次指定版本，確保最後贏的是我們測過的那個（見 requirements.txt 裡的說明）
    && pip install --no-cache-dir --force-reinstall --no-deps opencv-python==4.13.0.92

# app/ 底下的東西（main.py、ai_model/、models/）直接複製進 /app，
# 對應 main.py 用 __file__ 定位模型路徑的邏輯，最後會落在 /app/models/best.pt
COPY app/ .

EXPOSE 5000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
