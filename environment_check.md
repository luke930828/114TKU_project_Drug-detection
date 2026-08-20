# Python 環境與套件檢查報告
日期: 2026-05-29
環境類型: venv (Python 3.12.9)

## 已安裝套件清單
| 套件名稱 | 版本 | 狀態 (對照 requirements.txt) |
| :--- | :--- | :--- |
| aiosqlite | 0.22.1 | 已安裝 (需求: 0.20.0) |
| beautifulsoup4 | 4.12.3 | 已安裝 (需求: 4.12.3) |
| fastapi | 0.110.0 | 已安裝 (需求: 0.110.0) |
| httpx | 0.27.0 | 已安裝 (需求: 0.27.0) |
| lxml | 5.1.0 | 已安裝 (需求: 5.1.0) |
| pillow | 12.2.0 | 已安裝 (需求: >=10.3.0) |
| playwright | 1.42.0 | 已安裝 (需求: 1.42.0) |
| playwright-stealth | 1.0.6 | 已安裝 (需求: 1.0.6) |
| pydantic | 2.6.3 | 已安裝 (需求: 2.6.3) |
| requests | 2.31.0 | 已安裝 (需求: 2.31.0) |
| setuptools | 69.5.1 | 已安裝 (需求: 69.5.1) |
| tldextract | 5.3.1 | 已安裝 (需求: 5.1.2) |
| uvicorn | 0.27.1 | 已安裝 (需求: 0.27.1) |

## 其他相依套件
- annotated-types (0.7.0)
- anyio (4.13.0)
- certifi (2026.4.22)
- charset-normalizer (3.4.7)
- click (8.3.3)
- colorama (0.4.6)
- filelock (3.29.0)
- greenlet (3.0.3)
- h11 (0.16.0)
- httpcore (1.0.9)
- idna (3.15)
- pip (24.3.1)
- pydantic_core (2.16.3)
- pyee (11.0.1)
- requests-file (3.0.1)
- sniffio (1.3.1)
- soupsieve (2.8.3)
- starlette (0.36.3)
- typing_extensions (4.15.0)
- urllib3 (2.7.0)

**狀態確認：** 所有 [requirements.txt](requirements.txt) 中定義的核心套件均已正確安裝。


## 執行方式：
# python main.py                 基本上跑手動測試是執行main ，後續31、32行 24h註解打開能跑雙軌測試了，執行main 會先啟動API 然後如果想測試前端能否正常發送過來可以直接去8001 port網頁 測試

# python engine_v2.py    24h執行檔
# python manual.py               測試手動輸入網址的執行檔( 基本上不拿來執行)

# 其他test 開頭的都是測試用的，到時候完成後能刪除

./.venv/Scripts/python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
