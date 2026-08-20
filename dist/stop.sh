#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
echo "停止系統中..."
docker compose --profile gpu down
echo "✅ 已停止。資料保留在 Docker volume 裡，下次啟動會接著用。"
echo "   要連資料一起清掉：docker compose down -v"
