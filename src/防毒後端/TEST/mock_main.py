from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import time

# 建立測試用的 API 伺服器
app = FastAPI(title="純前端對接測試用後端")

# 開啟 CORS，讓前端可以順利連線
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 定義前端傳過來的資料格式
class FrontendScanRequest(BaseModel):
    url: str

@app.post("/api/scan_target/")
def scan_target_mock(request_data: FrontendScanRequest):
    target_url = request_data.url
    
    # 在終端機印出前端傳來的網址，證明你收到了！
    print("=" * 50)
    print(f"📥 成功收到前端傳來的網址啦：{target_url}")
    print("🤖 (測試模式) 假裝正在派發給爬蟲... 但其實沒有！")
    print("=" * 50)

    # 稍微等 2 秒，讓前端可以測到「轉圈圈」的 Loading 動畫
    time.sleep(2)

    # 直接回傳「測試假資料」給前端，完全不經過爬蟲與資料庫
    return {
        "status": "success",
        "source": "crawler",
        "message": "【測試模式】連線完美通暢！這是一筆測試用假資料。",
        "data": {
            "id": 999,
            "url": target_url,
            "yolo_details": "【測試】白色粉末, 夾鏈袋, 電子秤",
            "nlp_details": "【測試】大麻, THC 94%, 線上購買",
            "risk_score": 850,
            "risk_level": "極高風險"
        }
    }

if __name__ == "__main__":
    # 直接在檔案內啟動，前端寫的 port 是 8002
    uvicorn.run("mock_main:app", host="0.0.0.0", port=8002, reload=True)