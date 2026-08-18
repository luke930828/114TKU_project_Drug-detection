# 組員交付清單

> 把這頁貼到群組就好。每個人只要照著做,不用懂 Docker。

---

## 你要做的事(約 30 分鐘)

### 1. 把程式放到對的位置

```
modules/<你的模組>/
├── app/                 ← 你的程式碼全部放這裡（main.py 當進入點）
├── requirements.txt     ← 你用到的套件
└── Dockerfile           ← 複製範本改一改
```

模組名稱用 `crawler` / `yolo` / `nlp` / `frontend` / `backend`,**全小寫英文**。

### 2. 產生乾淨的 requirements.txt

**不要**用 `pip freeze > requirements.txt`——那會把整個 venv 倒出來,
包含你其他作業裝的東西。後端那份就有 `yfinance`、`matplotlib`,
白白讓 image 大幾百 MB。

正確做法:

```bash
pip install pipreqs
pipreqs modules/<你的模組>/app --force
```

`pipreqs` 會掃你的 `import` 語句,只列真正用到的。產生後自己再看一遍。

⚠️ 如果你是在 PowerShell 產生的,檢查一下編碼。
PowerShell 的 `>` 會產生 UTF-16,Linux 容器裡讀會出事。
用 VS Code 右下角改成 UTF-8 存檔。

### 3. 加一個 /health 端點

```python
@app.get("/health")
def health():
    return {"status": "ok"}
```

Docker 靠這個判斷你的模組活了沒。沒有的話,別人的模組會在你還沒
載完模型時就打過來,然後整組炸掉。

### 4. 位址不要寫死

如果你的程式裡有 `http://100.x.x.x:8000` 這種:

```python
# 改成
import os
BACKEND_URL = os.getenv("BACKEND_BASE_URL", "http://backend:8000")
```

理由:同一份程式碼要能在「單機測試」和「跨機測試」兩種情境跑,
差別只在環境變數。寫死的話每次切換都要改程式、重推、重 build。

---

## 絕對不要推上去的東西

| 不要推 | 為什麼 |
|---|---|
| `.pt` / `.pth` / `.onnx` 權重 | git 會永久保存每一版,repo 瘦不回來。改用 Release |
| `__pycache__/`、`.venv/` | 沒意義,而且會跟別人的環境衝突 |
| 任何含密碼的檔案 | repo 是公開的,推上去就等於洩漏 |
| 爬到的資料、截圖、測試輸出 | 太大,而且可能含個資 |

`.gitignore` 已經設好了,照著結構放通常不會誤推。推之前跑一次
`git status` 確認一下。

---

## 模型權重怎麼交

**不要 commit 進 git。** 流程是:

1. 把 `best.pt` 給組長
2. 組長上傳到 GitHub Releases 的 Attach binaries
3. `sha256sum best.pt` 拿到雜湊值,填進 `models/MODELS.txt`
4. 之後任何人執行 `./scripts/download_models.sh` 就會自動抓下來

如果你的模型是**一整個資料夾**(例如微調過的 BERT),
建議推 Hugging Face Hub,程式裡用 `from_pretrained("帳號/模型名")` 載入,
比打包 tar 好管理。

---

## 寫不出 Dockerfile 怎麼辦

交這三行給組長,他能幫你寫:

```
1. 我用的 Python 版本：3.__
2. 我怎麼裝：pip install -r requirements.txt（有其他步驟請寫出來）
3. 我怎麼啟動：uvicorn main:app --port ____
4. 有沒有需要系統套件：例如 Chrome、ffmpeg、libgl（沒有就寫「沒有」）
```

第 4 點最容易漏。常見的:

- 用 Selenium / Playwright → 需要瀏覽器
- 用 opencv / ultralytics → 需要 `libgl1`、`libglib2.0-0`
- 處理影片 → 需要 `ffmpeg`

---

## 怎麼確認自己交的東西是對的

```bash
docker build -t test modules/<你的模組>
docker run --rm -p 9999:<你的port> test
curl http://localhost:9999/health
```

看到 `{"status":"ok"}` 就過關了,可以推上去。
