@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 停止系統中...
docker compose --profile gpu down
echo.
echo 已停止。資料保留在 Docker volume 裡，下次啟動會接著用。
echo 要連資料一起清掉，請執行： docker compose down -v
pause
