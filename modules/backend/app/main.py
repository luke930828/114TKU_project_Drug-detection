from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import os
import secrets
import uuid
import database
from routers import auth, scan, crawler, whitelist, ai_engine, export, users

from password import hash_password as get_password_hash


def _initial_admin_password() -> tuple[str, bool]:
    """
    第一個管理員的密碼從環境變數來；沒設就隨機產生。

    以前這裡寫死一組固定密碼。那等於帳密就放在原始碼裡、放在公開的 repo 上，
    任何看得到程式碼的人都有管理員權限——而且系統從來不要求改密。

    回傳 (密碼, 是否為隨機產生)。隨機產生的那組只會在建立當下印出來一次，
    之後再也拿不回來，所以正式環境請自己設 ADMIN_INITIAL_PASSWORD。
    """
    pw = os.getenv("ADMIN_INITIAL_PASSWORD", "").strip()
    if pw:
        return pw, False
    return secrets.token_urlsafe(18), True


# --- 初始化腳本區塊 ---
def init_default_admin(db):
    print("🌱 進入資料庫初始化檢查...")

    admin_user = db.query(database.User).filter(database.User.account == "admin").first()

    if not admin_user:
        print("⚠️ 未偵測到管理員帳號，正在自動建立預設管理員...")
        new_user_id = "U" + str(uuid.uuid4().hex)[:8].upper()
        password, generated = _initial_admin_password()

        new_admin = database.User(
            user_id=new_user_id,
            account="admin",
            password_hash=get_password_hash(password),
            # dependencies.py 的 verify_admin 檢查的是這個中文字串，"admin" 會直接被 403 擋掉
            role="系統管理員",
            department="系統管理部",
            is_active=True
        )
        db.add(new_admin)
        db.commit()

        print("✅ 預設管理員建立完成！帳號：admin")
        if generated:
            print("=" * 62)
            print("  這是隨機產生的初始密碼，只會出現這一次，請立刻登入並修改：")
            print(f"    {password}")
            print("  下次要指定密碼的話，啟動前設好 ADMIN_INITIAL_PASSWORD。")
            print("=" * 62)
        else:
            print("   密碼取自 ADMIN_INITIAL_PASSWORD，請登入後盡快修改。")
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