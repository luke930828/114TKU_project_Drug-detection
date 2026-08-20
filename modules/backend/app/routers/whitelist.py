from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import database
from schemas import WhitelistCreate
from dependencies import get_db, verify_admin, verify_super_admin, log_audit_action

router = APIRouter(tags=["白名單維護"])

# 模組六：白名單維護管理

@router.get("/api/whitelist/", summary="查看白名單清單 (限管理員)")
def list_whitelist(db: Session = Depends(get_db), current_admin: database.User = Depends(verify_admin)):
    return db.query(database.WhitelistWebsite).all()

@router.post("/api/whitelist/", summary="最高權限：新增白名單")
def add_whitelist(data: WhitelistCreate, admin: database.User = Depends(verify_super_admin), db: Session = Depends(get_db)):
    existing = db.query(database.WhitelistWebsite).filter(database.WhitelistWebsite.url == data.url).first()
    if existing:
        raise HTTPException(status_code=400, detail="該網址已存在於白名單中。")
        
    new_white = database.WhitelistWebsite(url=data.url, title=data.title, reason=data.reason, added_by=admin.account)
    db.add(new_white)
    db.commit()
    
    log_audit_action(
        db=db,
        user_id=admin.user_id,          
        action_type="新增白名單",
        details=f"將網址 {data.url} 加入白名單"
    )
    
    return {"status": "success", "message": f"成功由總管理員 {admin.account} 新增白名單。"}

@router.delete("/api/whitelist/{id}", summary="最高權限：刪除白名單")
def delete_whitelist(id: int, admin: database.User = Depends(verify_super_admin), db: Session = Depends(get_db)):
    target = db.query(database.WhitelistWebsite).filter(database.WhitelistWebsite.id == id).first()
    if not target:
        raise HTTPException(status_code=404, detail="找不到該白名單項目。")
        
    url_to_log = target.url 
    db.delete(target)
    db.commit()
    
    log_audit_action(
        db=db,
        user_id=admin.user_id,
        action_type="刪除白名單",
        details=f"移除了網址 {url_to_log} 的白名單資格"
    )
    
    return {"status": "success", "message": "已成功移除白名單項目。"}