from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import database

# 引入你剛剛分好的 routers 抽屜
from routers import auth, scan, crawler, whitelist, ai_engine, export

app = FastAPI(title="多模態毒品防制系統 API", description="符合原始表與 AI 展示表分離架構")

# CORS 設定保持不變
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🚀 把各個抽屜掛載到系統大廳上
app.include_router(auth.router)
app.include_router(scan.router)
app.include_router(crawler.router)
app.include_router(whitelist.router)
app.include_router(ai_engine.router)
app.include_router(export.router)

@app.get("/")
def read_root():
    return {"message": "防制系統 API 正常運行中"}