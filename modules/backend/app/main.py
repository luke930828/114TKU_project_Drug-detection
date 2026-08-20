from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import database
from routers import auth, scan, crawler, whitelist, ai_engine, export,users

app = FastAPI(title="多模態毒品防制系統 API", description="符合原始表與 AI 展示表分離架構")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(scan.router)
app.include_router(crawler.router)
app.include_router(whitelist.router)
app.include_router(ai_engine.router)
app.include_router(export.router)
app.include_router(users.router)

@app.get("/")
def read_root():
    return {"message": "防制系統 API 正常運行中"}

@app.get("/health")
def health():
    return {"status": "ok"}