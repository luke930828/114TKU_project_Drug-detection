from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import database
from schemas import WhitelistCreate
from dependencies import get_db, verify_super_admin

# 宣告 router
router = APIRouter(tags=["白名單維護"])

# ... 下面接著放你的 @router.get("/api/whitelist/") 等等 ...
#  模組六：白名單維護管理
@router.get("/api/whitelist/", summary="查看白名單清單")
def list_whitelist(db: Session = Depends(get_db)):
    return db.query(database.WhitelistWebsite).all()

@router.post("/api/whitelist/", summary="最高權限：新增白名單")
def add_whitelist(data: WhitelistCreate, admin: database.User = Depends(verify_super_admin), db: Session = Depends(get_db)):
    existing = db.query(database.WhitelistWebsite).filter(database.WhitelistWebsite.url == data.url).first()
    if existing:
        raise HTTPException(status_code=400, detail="該網址已存在於白名單中。")
    new_white = database.WhitelistWebsite(url=data.url, title=data.title, reason=data.reason, added_by=admin.account)
    db.add(new_white); db.commit()
    return {"status": "success", "message": f"成功由總管理員 {admin.account} 新增白名單。"}

@router.delete("/api/whitelist/{id}", summary="最高權限：刪除白名單")
def delete_whitelist(id: int, admin: database.User = Depends(verify_super_admin), db: Session = Depends(get_db)):
    target = db.query(database.WhitelistWebsite).filter(database.WhitelistWebsite.id == id).first()
    if not target:
        raise HTTPException(status_code=404, detail="找不到該白名單項目。")
    db.delete(target); db.commit()
    return {"status": "success", "message": "已成功移除白名單項目。"}