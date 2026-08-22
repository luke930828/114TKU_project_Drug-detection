from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi import status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import database
import jwt
import hashlib
import os

def get_password_hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return get_password_hash(plain_password) == hashed_password


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login/")

# 必填，沒設就直接爆掉：這是 JWT 簽章密鑰，寫死在程式碼裡（或給預設值）等於任何看得到
# 原始碼的人都能自己簽發 super_admin 的 token，比洩漏資料庫密碼更嚴重。
# 這行已經被改回有預設值兩次了——本機測試請在 .env.local 設好 JWT_SECRET_KEY，
# 不要在這裡加預設值繞過去。
SECRET_KEY = os.environ["JWT_SECRET_KEY"]
ALGORITHM = "HS256"

def get_db():
    session = Session(bind=database.engine)
    try:
        yield session
    finally:
        session.close()

def log_audit_action(db: Session, user_id: str, action_type: str, details: str = ""):
    new_log = database.AuditLog(user_id=user_id, action_type=action_type, details=details)
    db.add(new_log)
    db.commit()

# JWT 解碼版
def get_current_user(x_token: str = Header(...), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(x_token, SECRET_KEY, algorithms=[ALGORITHM])
        account: str = payload.get("sub")
        
        if account is None:
            raise HTTPException(status_code=401, detail="憑證內容無效！")
            
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="身分驗證失敗：無效或偽造的憑證！")

    user = db.query(database.User).filter(database.User.account == account).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="身分驗證失敗：找不到該使用者！")
    
    if hasattr(user, 'is_active') and not user.is_active:
        raise HTTPException(status_code=403, detail="權限被拒絕：您的帳號已被停止使用！")
        
    return user

def verify_admin(current_user: database.User = Depends(get_current_user)):
    if current_user.role != "系統管理員":
        raise HTTPException(status_code=403, detail="權限不足：只有系統管理員可以執行此動作！")
    return current_user

def verify_super_admin(current_user: database.User = Depends(verify_admin)):
    if current_user.account != "super_admin":
        raise HTTPException(status_code=403, detail="權限不足：此操作僅限「總管理員」執行！")
    return current_user