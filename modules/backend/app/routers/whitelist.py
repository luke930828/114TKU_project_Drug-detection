from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from sqlalchemy.orm import Session
import database
from schemas import WhitelistCreate
from dependencies import get_db, verify_admin, verify_super_admin, log_audit_action

router = APIRouter(tags=["白名單維護"])

# 模組六：白名單維護管理

@router.get("/api/whitelist/", summary="查看白名單清單 (限管理員)")
def list_whitelist(
    db: Session = Depends(get_db),
    current_admin: database.User = Depends(verify_admin),
    q: Optional[str] = Query(None, description="關鍵字搜尋：網址、標題或原因"),
):
    query = db.query(database.WhitelistWebsite)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            database.WhitelistWebsite.url.like(like)
            | database.WhitelistWebsite.title.like(like)
            | database.WhitelistWebsite.reason.like(like)
        )
    return query.order_by(database.WhitelistWebsite.created_at.desc()).all()

# 👇 這裡把 verify_super_admin 換成了 verify_admin
@router.post("/api/whitelist/", summary="管理員：新增白名單")
def add_whitelist(data: WhitelistCreate, admin: database.User = Depends(verify_admin), db: Session = Depends(get_db)):
    existing = db.query(database.WhitelistWebsite).filter(database.WhitelistWebsite.url == data.url).first()
    if existing:
        raise HTTPException(status_code=400, detail="該網址已存在於白名單中。")
        
    new_white = database.WhitelistWebsite(
        url=data.url, title=data.title, reason=data.reason,
        added_by=admin.account, source=data.source or "一般新增")
    db.add(new_white)
    db.commit()
    
    log_audit_action(
        db=db,
        user_id=admin.user_id,          
        action_type="新增白名單",
        details=f"將網址 {data.url} 加入白名單"
    )
    
    return {"status": "success", "message": f"成功由管理員 {admin.account} 新增白名單。"}

# 👇 這裡的刪除也一併把 verify_super_admin 換成了 verify_admin
@router.delete("/api/whitelist/{id}", summary="管理員：刪除白名單")
def delete_whitelist(id: int, admin: database.User = Depends(verify_admin), db: Session = Depends(get_db)):
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