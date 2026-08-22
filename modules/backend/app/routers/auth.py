from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import database 
from schemas import UserLogin
import jwt 
import hashlib 
from dependencies import get_db, SECRET_KEY, ALGORITHM 

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hashlib.sha256(plain_password.encode("utf-8")).hexdigest() == hashed_password

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
    if not verify_password(login_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
        
    # 通過所有考驗，發放通行證 (Token)
    token_payload = {"sub": user.account}
    encrypted_token = jwt.encode(token_payload, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "status": "success",
        "message": f"登入成功！{user.account}",
        "access_token": encrypted_token 
    }