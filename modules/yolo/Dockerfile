FROM python:3.12-slim

# opencv (cv2) 需要這兩個系統套件才能 import 成功，slim image 預設沒有，
# 沒裝的話 import cv2 會直接炸 libGL.so.1 找不到
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先只複製 requirements.txt 裝套件，程式碼改動不會讓這層快取失效，重build比較快
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# app/ 底下的東西（main.py、ai_model/、models/）直接複製進 /app，
# 對應 main.py 用 __file__ 定位模型路徑的邏輯，最後會落在 /app/models/best.pt
COPY app/ .

EXPOSE 5000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
