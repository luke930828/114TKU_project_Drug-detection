from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import uuid
import hashlib
import database
from routers import auth, scan, crawler, whitelist, ai_engine, export, users

# --- 密碼加密工具 (與你 users.py 保持一致) ---
def get_password_hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

# --- 初始化腳本區塊 ---
def init_default_admin(db):
    print("🌱 進入資料庫初始化檢查...")
    
    admin_user = db.query(database.User).filter(database.User.account == "admin").first()
    
    if not admin_user:
        print("⚠️ 未偵測到管理員帳號，正在自動建立預設管理員...")
        new_user_id = "U" + str(uuid.uuid4().hex)[:8].upper()
        
        new_admin = database.User(
            user_id=new_user_id,
            account="admin",
            password_hash=get_password_hash("password123"),
            # dependencies.py 的 verify_admin 檢查的是這個中文字串，"admin" 會直接被 403 擋掉
            role="系統管理員",
            department="系統管理部", 
            is_active=True
        )
        db.add(new_admin)
        db.commit()
        
        print("✅ 預設管理員建立完成！(帳號: admin / 密碼: password123)")
    else:
        print("✅ 預設管理員帳號已存在，跳過初始化。")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 伺服器啟動中，連線至資料庫...")
    # 注意：這裡假設你的 database.py 裡面是用 SessionLocal 來建立連線
    db = database.SessionLocal()
    try:
        init_default_admin(db)
    except Exception as e:
        print(f"❌ 初始化管理員失敗: {e}")
    finally:
        db.close()
    
    yield
    print("🛑 伺服器正在關閉...")

# --- 應用程式實例 ---
app = FastAPI(
    title="多模態毒品防制系統 API", 
    description="符合原始表與 AI 展示表分離架構",
    lifespan=lifespan  
)

# --- 中介軟體 (CORS) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 路由註冊 ---
app.include_router(auth.router)
app.include_router(scan.router)
app.include_router(crawler.router)
app.include_router(whitelist.router)
app.include_router(ai_engine.router)
app.include_router(export.router)
app.include_router(users.router)

# --- 根目錄與健康檢查 ---
@app.get("/")
def read_root():
    return {"message": "防制系統 API 正常運行中"}

@app.get("/health")
def health():
    return {"status": "ok"}