#!/usr/bin/env bash
# ============================================================
# 一鍵啟動（macOS / Linux）
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

echo "多模態毒品防制系統 —— 啟動中"
echo "============================================"

# ---------- 1. 檢查 Docker ----------
if ! command -v docker >/dev/null 2>&1; then
  echo "❌ 找不到 Docker。"
  echo "   請先安裝 Docker Desktop：https://www.docker.com/products/docker-desktop/"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "❌ Docker 沒有在執行。請打開 Docker Desktop 等它啟動完成後再試一次。"
  exit 1
fi

# ---------- 2. 第一次執行就自動產生 .env ----------
# 重點：密碼是在「使用者自己的電腦上」隨機產生的，
# 不是我們預先寫死一組放進壓縮檔——那等於全世界下載到的都是同一組密碼。
if [ ! -f .env ]; then
  echo "🔑 第一次啟動，正在產生隨機密碼..."
  gen() { openssl rand -hex 24 2>/dev/null || head -c 32 /dev/urandom | base64 | tr -d '/+=' ; }
  cat > .env <<EOF
DB_USER=root
DB_PASSWORD=$(gen)
DB_NAME=drug_prevention_db
INTERNAL_API_TOKEN=$(gen)
HTTP_TIMEOUT=10
WEB_PORT=8080
EOF
  chmod 600 .env
  echo "   已寫入 .env（請勿分享這個檔案）"
fi

# ---------- 3. 有沒有 GPU 與權重 ----------
PROFILES=""
if [ -f models/best.pt ]; then
  if docker info 2>/dev/null | grep -qi nvidia; then
    PROFILES="--profile gpu"
    echo "✅ 偵測到 GPU 與模型權重，將啟用 YOLO 影像辨識"
  else
    echo "⚠️  找到模型權重但沒偵測到 NVIDIA GPU，YOLO 模組將不啟動"
    echo "   （其他功能不受影響，網址與文字分析仍可正常使用）"
  fi
else
  echo "ℹ️  models/best.pt 不存在，YOLO 影像辨識將不啟動"
  echo "   需要的話請到 Release 頁面下載 weights.zip 解壓到 models/"
fi

# ---------- 4. 拉 image 並啟動 ----------
echo ""
echo "📦 下載元件中（第一次約 5-15 分鐘，之後只要幾秒）..."
docker compose pull

echo "🚀 啟動服務..."
# shellcheck disable=SC2086
docker compose $PROFILES up -d

# ---------- 5. 等到真的可以用了才叫使用者開瀏覽器 ----------
echo -n "⏳ 等待系統就緒"
WEB_PORT=$(grep -E '^WEB_PORT=' .env | cut -d= -f2)
for _ in $(seq 1 60); do
  if curl -sf "http://localhost:${WEB_PORT}/" >/dev/null 2>&1; then
    echo ""
    echo ""
    echo "============================================"
    echo "✅ 啟動完成！請開啟：http://localhost:${WEB_PORT}"
    echo "   API 文件：http://localhost:${WEB_PORT}/api/docs"
    echo ""
    echo "   停止：./stop.sh"
    echo "   看紀錄：docker compose logs -f"
    echo "============================================"
    exit 0
  fi
  echo -n "."
  sleep 2
done

echo ""
echo "⚠️  等了兩分鐘還沒起來。用這個指令看看哪裡卡住："
echo "   docker compose logs"
exit 1
