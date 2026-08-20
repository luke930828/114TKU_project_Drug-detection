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
    

    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="登入失敗：帳號或密碼錯誤！")
        
    if hasattr(user, 'is_active') and not user.is_active:
        raise HTTPException(status_code=403, detail="登入失敗：您的帳號已被停止使用！")

    token_payload = {"sub": user.account}
    encrypted_token = jwt.encode(token_payload, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "status": "success",
        "message": f"登入成功！{user.account}",
        "access_token": encrypted_token 
    }