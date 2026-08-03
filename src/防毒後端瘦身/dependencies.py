from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
import database  

def get_db():
    session = Session(bind=database.engine)
    try:
        yield session
    finally:
        session.close()

def verify_admin(x_token: str = Header(...), db: Session = Depends(get_db)):
    user = db.query(database.User).filter(database.User.account == x_token).first()
    if not user:
        raise HTTPException(status_code=401, detail="身分驗證失敗：無效的憑證！")
    if user.role != "系統管理員":
        raise HTTPException(status_code=403, detail="權限不足：只有系統管理員可以執行此動作！")
    return user

def verify_super_admin(current_user: database.User = Depends(verify_admin)):
    if current_user.account != "super_admin":
        raise HTTPException(status_code=403, detail="權限不足：此操作僅限「總管理員」執行！")
    return current_user