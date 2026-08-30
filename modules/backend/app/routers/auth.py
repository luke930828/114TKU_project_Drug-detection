from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import database
from schemas import UserLogin
import jwt
import os
from dependencies import get_db, get_current_user, log_audit_action, SECRET_KEY, ALGORITHM
from password import hash_password, verify_password

# token 有效時數。以前沒有 exp，簽出去的 token 永久有效：
# 改密碼、停權、刪帳號通通讓它失效不了，外洩一次就是永久通行證。
TOKEN_TTL_HOURS = int(os.getenv("JWT_TTL_HOURS", "8"))

router = APIRouter(tags=["系統登入"])

@router.post("/api/login/", summary="系統登入")
def login_for_access_token(login_data: UserLogin, db: Session = Depends(get_db)):
    
    user = db.query(database.User).filter(database.User.account == login_data.account).first()
    
    # 第一道鎖：帳號不存在
    if not user:
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")

    # 第二道鎖：帳號已被軟刪除 (註銷)
    if user.is_deleted:
        raise HTTPException(status_code=401, detail="此帳號已被註銷，無法登入")

    # 第三道鎖：帳號被凍結
    if not user.is_active:
        raise HTTPException(status_code=401, detail="此帳號目前已被凍結，請聯繫管理員")

    # 第四道鎖：密碼驗證失敗
    ok, needs_rehash = verify_password(login_data.password, user.password_hash)
    if not ok:
        # 失敗的嘗試也要留痕，不然看不出有沒有人在猜密碼。
        # 注意：帳號不存在的那種失敗記不了——audit_logs.user_id 是
        # nullable=False 的外鍵，沒有對應的使用者就寫不進去。
        log_audit_action(db, user.user_id, "登入失敗", f"帳號 {user.account} 密碼錯誤")
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
        
    # 通過所有考驗，發放通行證 (Token)
    # PyJWT 解碼時只要 payload 裡有 exp 就會自動驗，不用另外寫檢查。
    now = datetime.now(timezone.utc)
    token_payload = {
        "sub": user.account,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=TOKEN_TTL_HOURS)).timestamp()),
    }
    encrypted_token = jwt.encode(token_payload, SECRET_KEY, algorithm=ALGORITHM)

    # 舊帳號還是無鹽 SHA-256。趁這次登入（手上正好有明文）換成 bcrypt，
    # 使用者無感，不需要請所有人重設密碼。
    if needs_rehash:
        user.password_hash = hash_password(login_data.password)
        db.commit()
        log_audit_action(db, user.user_id, "密碼雜湊升級",
                         f"帳號 {user.account} 的密碼已從 SHA-256 轉為 bcrypt")

    log_audit_action(db, user.user_id, "登入", f"帳號 {user.account} 登入系統")

    return {
        "status": "success",
        "message": f"登入成功！{user.account}",
        "access_token": encrypted_token 
    }

@router.post("/api/logout/", summary="系統登出")
def logout(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    token 是無狀態的，這個端點不會讓它失效——單純是為了在稽核軌跡上
    留下「這個人什麼時候結束操作」。前端呼叫完再自己清掉 token。
    """
    log_audit_action(db, current_user.user_id, "登出", f"帳號 {current_user.account} 登出系統")
    return {"status": "success", "message": "已登出"}
