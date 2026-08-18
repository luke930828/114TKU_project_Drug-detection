@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo 多模態毒品防制系統 —— 啟動中
echo ============================================

REM ---------- 1. 檢查 Docker ----------
docker info >nul 2>&1
if errorlevel 1 (
    echo.
    echo [錯誤] Docker 沒有在執行。
    echo        請先安裝並開啟 Docker Desktop：
    echo        https://www.docker.com/products/docker-desktop/
    echo.
    pause
    exit /b 1
)

REM ---------- 2. 第一次執行產生 .env ----------
if not exist .env (
    echo [設定] 第一次啟動，正在產生隨機密碼...
    for /f %%i in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString('N')+[guid]::NewGuid().ToString('N')"') do set DBPW=%%i
    for /f %%i in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString('N')+[guid]::NewGuid().ToString('N')"') do set TOKEN=%%i
    (
        echo DB_USER=root
        echo DB_PASSWORD=!DBPW!
        echo DB_NAME=drug_prevention_db
        echo INTERNAL_API_TOKEN=!TOKEN!
        echo HTTP_TIMEOUT=10
        echo WEB_PORT=8080
    ) > .env
    echo        已寫入 .env（請勿分享這個檔案）
)

REM ---------- 3. 檢查權重 ----------
set PROFILES=
if exist models\best.pt (
    set PROFILES=--profile gpu
    echo [資訊] 找到模型權重，將嘗試啟用 YOLO 影像辨識
) else (
    echo [資訊] models\best.pt 不存在，YOLO 影像辨識不啟動
    echo        需要的話請到 Release 頁面下載 weights.zip 解壓到 models\
)

REM ---------- 4. 啟動 ----------
echo.
echo [下載] 取得元件中（第一次約 5-15 分鐘，之後只要幾秒）...
docker compose pull
if errorlevel 1 (
    echo [錯誤] 下載失敗，請檢查網路連線。
    pause
    exit /b 1
)

echo [啟動] 服務啟動中...
docker compose %PROFILES% up -d
if errorlevel 1 (
    echo [錯誤] 啟動失敗。執行 docker compose logs 查看原因。
    pause
    exit /b 1
)

echo.
echo ============================================
echo  啟動完成！
echo.
echo  系統畫面：http://localhost:8080
echo  API 文件：http://localhost:8080/api/docs
echo.
echo  停止系統：點兩下 stop.bat
echo  查看紀錄：docker compose logs -f
echo ============================================
echo.

timeout /t 5 >nul
start http://localhost:8080
pause
