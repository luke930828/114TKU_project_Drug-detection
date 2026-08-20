# ============================================================
# YOLO 模組範本 —— 給負責 YOLO 的同學填
# ============================================================
# 選 base image 的規則：容器內的 CUDA 版本「可以比宿主機 driver 舊，不能比它新」。
# 先在要當主機的那台跑 nvidia-smi 看 CUDA Version，再挑對應的 tag。
#
# 只用 CPU 推論的話，把下面這行換成 FROM python:3.12-slim 就好，image 會小非常多
# （CUDA base 大概 6-8GB，slim 只有 150MB 左右）。

FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime

WORKDIR /app

# ultralytics 需要 libgl / libglib，slim 或 runtime image 預設沒有，缺了會出現
# "ImportError: libGL.so.1: cannot open shared object file"
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/

# ⚠️ 模型權重 (.pt) 不要 COPY 進 image，也不要進 git。
#    幾百 MB 的檔案會讓 image 肥掉、build 變慢、git repo 永久變大。
#    改用 volume 掛進來，路徑從環境變數讀：
ENV MODEL_PATH=/models/best.pt

EXPOSE 5000

HEALTHCHECK --interval=15s --timeout=5s --start-period=90s --retries=5 \
    CMD curl -f http://localhost:5000/health || exit 1

# start_period 要放長：載模型權重通常要 30-60 秒，太短會被判定不健康一直重啟

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
