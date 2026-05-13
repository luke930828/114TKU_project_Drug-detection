from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Any
import json
import requests

import database  # 引入你的資料庫設定

app = FastAPI(title="毒品防制系統核心 API", description="前端四宮格介面 + 爬蟲對接通道")

# 允許前端跨域連線
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 資料庫連線產生器 ---
def get_db():
    db = database.engine.connect()
    session = Session(bind=database.engine)
    try:
        yield session
    finally:
        session.close()

# --- 身分驗證警衛 ---
def verify_admin(x_token: str = Header(..., description="請輸入管理員帳號作為 Token"), db: Session = Depends(get_db)):
    user = db.query(database.User).filter(database.User.account == x_token).first()
    if not user:
        raise HTTPException(status_code=401, detail="身分驗證失敗：無效的憑證！")
    return user

# --- Pydantic 接收格式定義 ---
class UserLogin(BaseModel):
    account: str
    password: str

class FrontendScanRequest(BaseModel):
    url: str

class WebsiteReport(BaseModel):
    url: str
    title: str
    risk_level: str
    keywords_found: str
# 白名單新增時所需的格式
class WhitelistCreate(BaseModel):
    url: str
    title: str
    reason: str

# ==========================================
# 💻 前端 UI 專用 API (對應四宮格卡片)
# ==========================================

# 🔑 卡片 1：登入系統
@app.post("/api/login/", summary="系統登入")
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

# 🕵️ 卡片 2：輸入網址識別
@app.post("/api/scan_target/", summary="即時掃描單一網址")
def scan_target_url(request_data: FrontendScanRequest, db: Session = Depends(get_db)):
    target_url = request_data.url
    CRAWLER_API_URL = "http://127.0.0.1:8001/analyze"  # 爬蟲引擎的 API 位置
    
    try:
        response = requests.post(CRAWLER_API_URL, json={"url": target_url}, timeout=60)
        response.raise_for_status() 
        crawler_result = response.json()

        score_num = crawler_result.get("risk_score", 0)
        if score_num >= 800: level = "極高風險"
        elif score_num >= 600: level = "高風險"
        else: level = "中低風險"
            
        yolo_words = crawler_result.get("details", {}).get("yolo_objects", [])
        nlp_words = crawler_result.get("details", {}).get("nlp_keywords", [])
        all_keywords = ", ".join(yolo_words + nlp_words) if (yolo_words or nlp_words) else "無檢出關鍵字"

        new_record = database.SuspectWebsite(
            url=target_url,
            title="即時 AI 掃描", 
            risk_level=level,
            risk_score=score_num,
            keywords_found=all_keywords,
            reported_by="網頁即時觸發" 
        )
        db.add(new_record)
        db.commit()
        return {"status": "success", "message": "分析完成並已寫入資料庫", "risk_level": level}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"系統處理掃描時發生錯誤：{str(e)}")

# 📂 卡片 3：合併報表 / 批次匯入 JSON
@app.post("/api/upload_file/", summary="批次匯入 JSON 報表")
async def upload_crawler_json_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        content = await file.read()
        try:
            crawler_data_list = json.loads(content)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="檔案解析失敗，請上傳有效的 JSON 檔案！")

        success_count = 0
        skip_count = 0
        processed_urls = set() 
        
        for item in crawler_data_list:
            found_url = item.get("url")
            if not found_url or found_url in processed_urls: 
                skip_count += 1; continue
            
            if db.query(database.SuspectWebsite).filter(database.SuspectWebsite.url == found_url).first():
                skip_count += 1; continue
                
            processed_urls.add(found_url)
            score_num = item.get("risk_score", 0)
            
            if score_num >= 800: level = "極高風險"
            elif score_num >= 600: level = "高風險"
            else: level = "中低風險"

            yolo_words = item.get("details", {}).get("yolo_objects", [])
            nlp_words = item.get("details", {}).get("nlp_keywords", [])
            all_keywords = ", ".join(yolo_words + nlp_words) if (yolo_words or nlp_words) else "無檢出關鍵字"

            new_record = database.SuspectWebsite(
                url=found_url, title="批次合併報表", risk_level=level, risk_score=score_num,
                keywords_found=all_keywords, created_at=item.get("created_at", "未知時間"), reported_by="批次上傳匯入" 
            )
            db.add(new_record)
            success_count += 1
            
        db.commit()
        return {"status": "success", "message": f"成功匯入 {success_count} 筆新資料，攔截 {skip_count} 筆重複網址！"}

    except HTTPException: raise 
    except Exception as e:
        db.rollback(); raise HTTPException(status_code=500, detail=f"系統處理檔案時發生錯誤：{str(e)}")

# 📋 卡片 4：查詢已識別網站 (⚠️ 受權限保護，使用 GET)
@app.get("/api/crawler/report/", summary="獲取黑名單資料庫")
def get_suspect_websites(current_user: database.User = Depends(verify_admin), db: Session = Depends(get_db)):
    websites = db.query(database.SuspectWebsite).all()
    return {
        "status": "success", "message": "成功抓取可疑網站黑名單",
        "total_count": len(websites), "data": websites
    }
# 👑 總管理員專屬警衛 (只有帳號是 super_admin 的人能通過)
def verify_super_admin(current_user: database.User = Depends(verify_admin)):
    # 這裡鎖定只有 'super_admin' 帳號具備最高權限
    if current_user.account != "super_admin":
        raise HTTPException(
            status_code=403, 
            detail="權限不足：此操作僅限「總管理員」執行！"
        )
    return current_user

# ==========================================
# 🕷️ 隱藏版：爬蟲自動對接專用 API (免登入)
# ==========================================

# 🤖 爬蟲通道 1：舊版單筆回報 (使用 POST)
@app.post("/api/crawler/report/", summary="爬蟲專用：單筆情資回報")
def receive_crawler_data(report: WebsiteReport, db: Session = Depends(get_db)):
    existing_site = db.query(database.SuspectWebsite).filter(database.SuspectWebsite.url == report.url).first()
    if existing_site:
         return {"status": "ignored", "message": "這個網址已經在黑名單中了，無需重複通報。"}

    new_website = database.SuspectWebsite(
        url=report.url, title=report.title, risk_level=report.risk_level,
        keywords_found=report.keywords_found, reported_by="舊版爬蟲 API" 
    )
    db.add(new_website)
    db.commit()
    return {"status": "success", "message": f"成功接收情資！已將 {report.url} 列入黑名單。", "risk": report.risk_level}

# 🤖 爬蟲通道 2：巨量陣列 JSON 直接同步 (免存檔版)
@app.post("/api/sync_data/", summary="爬蟲專用：巨量陣列同步")
async def sync_crawler_data(data_list: List[Dict[str, Any]], db: Session = Depends(get_db)): 
    try:
        success_count = 0
        skip_count = 0
        processed_urls = set() 
        
        for item in data_list:
            found_url = item.get("url")
            if not found_url or found_url in processed_urls: 
                skip_count += 1; continue
                
            if db.query(database.SuspectWebsite).filter(database.SuspectWebsite.url == found_url).first():
                skip_count += 1; continue
                
            processed_urls.add(found_url)
            score_num = item.get("risk_score", 0)
            
            if score_num >= 800: level = "極高風險"
            elif score_num >= 600: level = "高風險"
            else: level = "中低風險"
            
            yolo_words = item.get("details", {}).get("yolo_objects", [])
            nlp_words = item.get("details", {}).get("nlp_keywords", [])
            all_keywords = ", ".join(yolo_words + nlp_words) if (yolo_words or nlp_words) else "無檢出關鍵字"
            
            new_record = database.SuspectWebsite(
                url=found_url, title="爬蟲 API 自動同步", risk_level=level, risk_score=score_num,
                keywords_found=all_keywords, created_at=item.get("created_at", "未知時間"), reported_by="Auto_Crawler" 
            )
            db.add(new_record)
            success_count += 1
            
        db.commit()
        return {"status": "success", "message": f"伺服器同步完畢！成功新增 {success_count} 筆，攔截 {skip_count} 筆重複！"}

    except Exception as e:
        db.rollback() 
        raise HTTPException(status_code=500, detail=f"系統處理同步資料時發生錯誤：{str(e)}")
    # ==========================================
# ⚪ 白名單管理 API (總管理員專屬)
# ==========================================

# 【功能 1】查看白名單：只要是登入的管理員/警員都能看
@app.get("/api/whitelist/", summary="查看白名單清單")
def get_whitelist(current_user: database.User = Depends(verify_admin), db: Session = Depends(get_db)):
    return db.query(database.WhitelistWebsite).all()

# 【功能 2】新增白名單：🔒 嚴格鎖定由總管理員操作
@app.post("/api/whitelist/", summary="由總管理員新增白名單")
def add_to_whitelist(data: WhitelistCreate, admin: database.User = Depends(verify_super_admin), db: Session = Depends(get_db)):
    # 檢查網址是否已經存在於白名單
    existing = db.query(database.WhitelistWebsite).filter(database.WhitelistWebsite.url == data.url).first()
    if existing:
        raise HTTPException(status_code=400, detail="此網址已在白名單中，不需重複新增。")
        
    new_white = database.WhitelistWebsite(
        url=data.url,
        title=data.title,
        reason=data.reason,
        added_by=admin.account # 自動記錄是哪個總管理員加的
    )
    db.add(new_white)
    db.commit()
    return {
        "status": "success", 
        "message": f"成功將 {data.url} 加入白名單",
        "operator": admin.account
    }

# 【功能 3】刪除白名單項目：🔒 嚴格鎖定由總管理員操作
@app.delete("/api/whitelist/{white_id}", summary="由總管理員刪除白名單項目")
def delete_whitelist(white_id: int, admin: database.User = Depends(verify_super_admin), db: Session = Depends(get_db)):
    target = db.query(database.WhitelistWebsite).filter(database.WhitelistWebsite.id == white_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="找不到該白名單編號，無法刪除。")
        
    db.delete(target)
    db.commit()
    return {
        "status": "success", 
        "message": "已成功移除白名單項目",
        "operator": admin.account
    }