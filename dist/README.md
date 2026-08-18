# 多模態毒品防制系統

淡江大學 114 學年度專題。整合網路爬蟲、YOLO 影像辨識與 NLP 文字分析，
對可疑網站進行多模態風險評分。

---

## 需要準備什麼

只有一樣：**Docker Desktop**
https://www.docker.com/products/docker-desktop/

不需要安裝 Python、Node.js、MySQL——全部包在裡面了。

建議硬體：記憶體 8GB 以上、硬碟空間 15GB 以上。
YOLO 影像辨識需要 NVIDIA 顯卡，沒有的話其他功能照常可用。

---

## 怎麼啟動

**Windows**：點兩下 `start.bat`

**macOS / Linux**：
```bash
chmod +x start.sh stop.sh
./start.sh
```

第一次啟動要下載元件，視網速大約 5-15 分鐘。之後啟動只要幾秒。

跑完之後開瀏覽器：**http://localhost:8080**

停止系統：`stop.bat` 或 `./stop.sh`

---

## 資料夾裡有什麼

```
drug-detection/
├── start.bat / start.sh      啟動
├── stop.bat  / stop.sh       停止
├── docker-compose.yml        系統組成定義
├── .env                      你的密碼（第一次啟動自動產生，不要外流）
├── initdb/                   資料庫初始資料
└── models/                   放 YOLO 權重的地方（預設是空的）
```

---

## 啟用 YOLO 影像辨識

模型權重檔太大（幾百 MB），沒有包在這個壓縮檔裡。需要的話：

1. 到 Release 頁面下載 `weights.zip`
2. 解壓縮，把 `best.pt` 放進 `models/` 資料夾
3. 重新執行 `start.bat` / `./start.sh`

### 沒有 NVIDIA 顯卡怎麼辦

系統會自動跳過 YOLO 模組，網址查詢、文字分析、黑白名單管理、報表匯出
都能正常使用，只是影像辨識分數會是 0。

想在 CPU 上跑 YOLO 的話（會慢很多，一張圖數秒到數十秒），
編輯 `docker-compose.yml`，把 `yolo` 服務的 image 換成 `-cpu` 結尾那版，
並移除 `profiles: ["gpu"]` 那行。

---

## 常見問題

**「port is already allocated」**
8080 被其他程式佔用了。編輯 `.env`，把 `WEB_PORT=8080` 改成別的（例如 `8090`），
重新啟動。

**畫面打得開但沒有資料**
後端可能還在等資料庫。等 30 秒重新整理，或執行 `docker compose logs backend` 看狀況。

**想全部重來**
```bash
docker compose down -v
```
`-v` 會連資料庫的資料一起刪掉。

**想看系統在做什麼**
```bash
docker compose logs -f
```

---

## 資料與隱私

- 這個壓縮檔**不包含**任何實際蒐證資料或可疑網址清單，資料庫是空的
- 第一次啟動時產生的 `.env` 含有你這台電腦專屬的密碼，不要分享出去
- 系統爬取與分析的結果只存在你自己的電腦上（Docker volume 裡），不會回傳任何地方

---

## 使用範圍

本系統為學術研究與教學展示用途所開發，僅適用於公開網頁內容的分析。
風險評分為輔助參考，不構成法律認定；實際執法或處分應以主管機關程序為準。
使用者須自行遵守目標網站的服務條款、robots.txt 與相關法規。

---

## 問題回報

https://github.com/luke930828/114TKU_project_Drug-detection/issues
