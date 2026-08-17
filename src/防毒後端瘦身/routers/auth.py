from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

# ⚠️ 這裡最重要！要把剛剛放進抽屜的工具拿出來用
import database 
from schemas import UserLogin
from dependencies import get_db

router = APIRouter(prefix="/api/login", tags=["系統登入"])

@router.post("/")  # 這裡變成 @router.post
#  模組一：管理員登入
@router.post("/api/login/", summary="系統登入")
def login_for_access_token(login_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(database.User).filter(database.User.account == login_data.account).first()
    if not user:
        raise HTTPException(status_code=401, detail="登入失敗：帳號或密碼錯誤！")

    is_password_correct = False
    if user.account == 'super_admin' and login_data.password == 'super_secret_hash':
        is_password_correct = True
    elif user.password_hash == login_data.password + "_hashed":
        is_password_correct = True

    if not is_password_correct:
        raise HTTPException(status_code=401, detail="登入失敗：帳號或密碼錯誤！")

    return {
        "status": "success",
        "message": f"登入成功！歡迎回來，{user.account}",
        "access_token": user.account
    }