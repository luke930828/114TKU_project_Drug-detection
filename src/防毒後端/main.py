from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Any, Optional 
import requests
import json     
import database  
from sqlalchemy.exc import IntegrityError # 
app = FastAPI(title="多模態毒品防制系統 API", description="符合原始表與 AI 展示表分離架構")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

class UserLogin(BaseModel):
    account: str
    password: str

class FrontendScanRequest(BaseModel):
    url: str

class WhitelistCreate(BaseModel):
    url: str
    title: str
    reason: str

class WebsiteReport(BaseModel):
    url: str
    title: str
    risk_level: str
    keywords_found: str
    html_content: Optional[str] = None
    images: Optional[List[str]] = None  

class YOLOAnalysisReport(BaseModel):
    url: str
    risk_score: int
    yolo_objects: List[str] = []
    processed_images: Optional[List[str]] = []

class NLPAnalysisReport(BaseModel):
    url: str
    risk_score: int
    nlp_keywords: List[str] = []
#  系統派報生：精準分發資料給 AI 引擎（各取所需版）
def dispatch_to_ai_engines(url: str, html_content: str, images: list):
    YOLO_API_URL = "https://你的YOLO同學網址.ngrok-free.app/analyze"
    NLP_API_URL = "https://你的NLP同學網址.ngrok-free.app/analyze"
    
    try:
        yolo_payload = {
            "url": url,
            "images": images if images else []
        }
        print(f"📸 [背景任務] 正在將圖片派發給 YOLO 視覺引擎...")
        requests.post(YOLO_API_URL, json=yolo_payload, timeout=5) 
    except Exception as e:
        print(f" YOLO 視覺引擎連線失敗或無回應：{e}")

    try:
        nlp_payload = {
            "url": url,
            "html_content": html_content if html_content else ""
        }
        print(f" [背景任務] 正在將網頁 HTML 派發給 NLP 語意引擎...")
        requests.post(NLP_API_URL, json=nlp_payload, timeout=5)
    except Exception as e:
        print(f" NLP 語意引擎連線失敗或無回應：{e}")
#  模組一：管理員登入 (左上角卡片)
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


#  模組二：輸入網址識別 (右上角卡片) -> 僅操作 AIAnalysisResult 表
@app.post("/api/scan_target/", summary="即時掃描單一網址（優先對照歷史展示表，無紀錄才派發爬蟲）")
def scan_target_url(request_data: FrontendScanRequest, db: Session = Depends(get_db)):
    target_url = request_data.url
    
    is_whitelisted = db.query(database.WhitelistWebsite).filter(database.WhitelistWebsite.url == target_url).first()
    if is_whitelisted:
        return {"status": "safe", "source": "whitelist", "message": "此網址已列入白名單，安全放行。", "reason": is_whitelisted.reason}

    existing_record = db.query(database.AIAnalysisResult).filter(database.AIAnalysisResult.url == target_url).first()
    if existing_record:
        return {
            "status": "success",
            "source": "history",
            "message": "偵測到歷史展示紀錄，直接回傳 AI 分析結果。",
            "data": existing_record
        }

    CRAWLER_API_URL = "http://127.0.0.1:8001/analyze" 
    try:
        response = requests.post(CRAWLER_API_URL, json={"url": target_url}, timeout=60)
        response.raise_for_status() 
        crawler_result = response.json()
        
        score_num = crawler_result.get("risk_score", 0)
        level = "極高風險" if score_num >= 800 else "高風險" if score_num >= 600 else "中低風險"
        
        yolo_words = crawler_result.get("details", {}).get("yolo_objects", [])
        nlp_words = crawler_result.get("details", {}).get("nlp_keywords", [])
        
        yolo_str = ", ".join(yolo_words) if yolo_words else "無檢出影像特徵"
        nlp_str = ", ".join(nlp_words) if nlp_words else "無檢出文字特徵"
        
        frontend_record = database.AIAnalysisResult(
            url=target_url,
            yolo_details=yolo_str,
            nlp_details=nlp_str,
            risk_score=score_num,
            risk_level=level
        )
        db.add(frontend_record)
        db.commit()
        
        return {
            "status": "success",
            "source": "crawler",
            "message": "AI 分析完畢，已將格式化情資同步至前端展示表。",
            "data": frontend_record
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"即時識別處理失敗：{str(e)}")


#  模組三：查詢已識別網站 (右下角卡片) ->  鎖定只從 AIAnalysisResult 撈取
@app.get("/api/crawler/report/", summary="獲取前端專用 AI 分析黑名單報表")
def get_frontend_report(current_user: database.User = Depends(verify_admin), db: Session = Depends(get_db)):
    results = db.query(database.AIAnalysisResult).all()
    return {
        "status": "success",
        "message": "成功抓取最新 AI 多模態識別資料庫",
        "total_count": len(results),
        "data": results
    }

# 模組四：爬蟲專用通道 (免登入) -> 專門讓爬蟲「透過後端存進 suspect_websites」

@app.post("/api/crawler/report/", summary="爬蟲端專用：將原始結果(含 HTML/圖片)寫入 suspect_websites 表")
def receive_crawler_raw_data(report: WebsiteReport, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        print(f"收到爬蟲通報網址：{report.url}")
        
        existing_site = db.query(database.SuspectWebsite).filter(database.SuspectWebsite.url == report.url).first()
        if existing_site:
             print(f"網址 {report.url} 已存在於 suspect_websites，跳過寫入。")
             return {"status": "ignored", "message": "此原始網址已記錄於內部 suspect_websites 中。"}

        images_json_string = json.dumps(report.images, ensure_ascii=False) if report.images else "[]"

        new_website = database.SuspectWebsite(
            url=report.url,
            title=report.title,
            risk_level=report.risk_level,
            keywords_found=report.keywords_found,
            reported_by="爬蟲端自動上傳",
            html_content=report.html_content if report.html_content else "",    
            images_data=images_json_string       
        )
        db.add(new_website)
        db.commit()
        print(" 原始網頁快照已成功寫入資料庫！")
        
        try:
            background_tasks.add_task(dispatch_to_ai_engines, report.url, report.html_content if report.html_content else "", report.images if report.images else [])
            print("背景派發任務已順利啟動！")
        except Exception as ai_err:
            print(f"背景任務加入失敗（不影響存檔）：{str(ai_err)}")

        return {"status": "success", "message": "原始情資與網頁快照已成功寫入內部資料庫，並已於背景自動派發。"}

    except Exception as e:
        db.rollback()
        print(f"嚴重錯誤：API 崩潰了，原因：{str(e)}")
        raise HTTPException(status_code=500, detail=f"伺服器內部錯誤：{str(e)}")
@app.post("/api/sync_data/", summary="爬蟲端專用：批次同步原始數據(含 HTML/圖片)至 suspect_websites")
async def sync_crawler_data(data_list: List[Dict[str, Any]], db: Session = Depends(get_db)): 
    try:
        success_count = 0
        for item in data_list:
            found_url = item.get("url")
            if not found_url: continue
                
            if db.query(database.SuspectWebsite).filter(database.SuspectWebsite.url == found_url).first():
                continue
                
            score_num = item.get("risk_score", 0)
            level = "極高風險" if score_num >= 800 else "高風險" if score_num >= 600 else "中低風險"
            
            all_keywords = ", ".join(item.get("details", {}).get("yolo_objects", []) + item.get("details", {}).get("nlp_keywords", []))
            
            html_val = item.get("html_content", "")
            images_list = item.get("images", [])
            images_json_string = json.dumps(images_list, ensure_ascii=False)
            
            new_record = database.SuspectWebsite(
                url=found_url, title="爬蟲大批同步建檔", risk_level=level, risk_score=score_num,
                keywords_found=all_keywords if all_keywords else "無檢出關鍵字",
                reported_by="Auto_Crawler_Sync",
                html_content=html_val,              
                images_data=images_json_string      
            )
            db.add(new_record)
            success_count += 1
            
        db.commit()
        return {"status": "success", "message": f"原始資料同步完畢，成功寫入 suspect_websites 共 {success_count} 筆！"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"爬蟲批次同步至內部表時發生錯誤：{str(e)}")
#  模組五：合併報表 / 批次匯入 (左下角卡片) -> 前端手動上傳報表用
@app.post("/api/upload_file/", summary="前端手動批次匯入展示報表")
async def upload_crawler_json_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        content = await file.read()
        data_list = json.loads(content)
        success_count = 0
        
        for item in data_list:
            url_check = item.get("url")
            if not url_check: continue
            
            if db.query(database.AIAnalysisResult).filter(database.AIAnalysisResult.url == url_check).first():
                continue
                
            score_num = item.get("risk_score", 0)
            level = "極高風險" if score_num >= 800 else "高風險" if score_num >= 600 else "中低風險"
            
            yolo_str = ", ".join(item.get("details", {}).get("yolo_objects", []))
            nlp_str = ", ".join(item.get("details", {}).get("nlp_keywords", []))

            frontend_record = database.AIAnalysisResult(
                url=url_check,
                yolo_details=yolo_str if yolo_str else "無檢出影像特徵",
                nlp_details=nlp_str if nlp_str else "無檢出文字特徵",
                risk_score=score_num,
                risk_level=level
            )
            db.add(frontend_record)
            success_count += 1
            
        db.commit()
        return {"status": "success", "message": f"手動合併報表完畢！成功將 {success_count} 筆分析情資匯入展示庫。"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"解析並上傳合併報表失敗：{str(e)}")



#  模組六：白名單維護管理
@app.get("/api/whitelist/", summary="查看白名單清單")
def list_whitelist(db: Session = Depends(get_db)):
    return db.query(database.WhitelistWebsite).all()

@app.post("/api/whitelist/", summary="最高權限：新增白名單")
def add_whitelist(data: WhitelistCreate, admin: database.User = Depends(verify_super_admin), db: Session = Depends(get_db)):
    existing = db.query(database.WhitelistWebsite).filter(database.WhitelistWebsite.url == data.url).first()
    if existing:
        raise HTTPException(status_code=400, detail="該網址已存在於白名單中。")
    new_white = database.WhitelistWebsite(url=data.url, title=data.title, reason=data.reason, added_by=admin.account)
    db.add(new_white); db.commit()
    return {"status": "success", "message": f"成功由總管理員 {admin.account} 新增白名單。"}

@app.delete("/api/whitelist/{id}", summary="最高權限：刪除白名單")
def delete_whitelist(id: int, admin: database.User = Depends(verify_super_admin), db: Session = Depends(get_db)):
    target = db.query(database.WhitelistWebsite).filter(database.WhitelistWebsite.id == id).first()
    if not target:
        raise HTTPException(status_code=404, detail="找不到該白名單項目。")
    db.delete(target); db.commit()
    return {"status": "success", "message": "已成功移除白名單項目。"}

#  模組七：YOLO 獨立分析結果接收通道 
@app.post("/api/ai_result/report/", summary="YOLO 引擎專用：接收影像與分數並自動統整")
def receive_ai_analysis_result(report: YOLOAnalysisReport, db: Session = Depends(get_db)):
    yolo_str = ", ".join(report.yolo_objects) if report.yolo_objects else "無檢出影像特徵"
    
    existing_record = db.query(database.AIAnalysisResult).filter(database.AIAnalysisResult.url == report.url).first()
    
    if existing_record:
        existing_record.yolo_details = yolo_str
        
        final_score = max(existing_record.risk_score, report.risk_score)
        existing_record.risk_score = final_score
        existing_record.risk_level = "極高風險" if final_score >= 800 else "高風險" if final_score >= 600 else "中低風險"
        
        
        db.commit()
        return {"status": "success", "message": f"成功統整！已將 YOLO 影像與分數補充至 {report.url}"}
    else:
        try:
            level = "極高風險" if report.risk_score >= 800 else "高風險" if report.risk_score >= 600 else "中低風險"
            new_record = database.AIAnalysisResult(
                url=report.url,
                yolo_details=yolo_str,
                nlp_details="文字分析中...", 
                risk_score=report.risk_score,
                risk_level=level
            )
            db.add(new_record)
            db.commit() 
            return {"status": "success", "message": f"成功建檔！已為 {report.url} 建立全新 AI 影像展示紀錄。"}
        
        except IntegrityError:
            db.rollback() 
            
            real_existing_record = db.query(database.AIAnalysisResult).filter(database.AIAnalysisResult.url == report.url).first()
            if real_existing_record:
                real_existing_record.yolo_details = yolo_str
                final_score = max(real_existing_record.risk_score, report.risk_score)
                real_existing_record.risk_score = final_score
                real_existing_record.risk_level = "極高風險" if final_score >= 800 else "高風險" if final_score >= 600 else "中低風險"
                db.commit()
            return {"status": "success", "message": "遭遇併發衝突，已自動轉為更新模式並將 YOLO 結果安全寫入！"}
#  模組八：NLP 獨立分析結果接收通道 
@app.post("/api/nlp/report/", summary="NLP 引擎專用：接收可疑文字與分數並自動統整")
def receive_nlp_analysis_result(report: NLPAnalysisReport, db: Session = Depends(get_db)):
    nlp_str = ", ".join(report.nlp_keywords) if report.nlp_keywords else "無檢出文字特徵"
    
    existing_record = db.query(database.AIAnalysisResult).filter(database.AIAnalysisResult.url == report.url).first()
    
    if existing_record:
        existing_record.nlp_details = nlp_str
        
        final_score = max(existing_record.risk_score, report.risk_score)
        existing_record.risk_score = final_score
        existing_record.risk_level = "極高風險" if final_score >= 800 else "高風險" if final_score >= 600 else "中低風險"
        
        db.commit()
        return {"status": "success", "message": f"成功統整！已將 NLP 文字與分數補充至 {report.url}"}
    else:
        try:
            level = "極高風險" if report.risk_score >= 800 else "高風險" if report.risk_score >= 600 else "中低風險"
            new_record = database.AIAnalysisResult(
                url=report.url,
                yolo_details="影像分析中...", 
                nlp_details=nlp_str,
                risk_score=report.risk_score,
                risk_level=level
            )
            db.add(new_record)
            db.commit()
            return {"status": "success", "message": f"成功建檔！已為 {report.url} 建立全新 AI 文字展示紀錄。"}
        
        except IntegrityError:
            db.rollback() 
            
            real_existing_record = db.query(database.AIAnalysisResult).filter(database.AIAnalysisResult.url == report.url).first()
            if real_existing_record:
                real_existing_record.nlp_details = nlp_str
                final_score = max(real_existing_record.risk_score, report.risk_score)
                real_existing_record.risk_score = final_score
                real_existing_record.risk_level = "極高風險" if final_score >= 800 else "高風險" if final_score >= 600 else "中低風險"
                db.commit()
            return {"status": "success", "message": "遭遇併發衝突，已自動轉為更新模式並將 NLP 結果安全寫入！"}
#  開發工具：一鍵清空測試資料 (測試完畢清理用)
@app.post("/api/test/cleanup/", summary="【開發專用】一鍵清空所有測試的網站與 AI 紀錄")
def cleanup_all_test_data(db: Session = Depends(get_db)):
    try:
        print("🧹 正在啟動資料庫清理程序...")
        
        deleted_frontend = db.query(database.AIAnalysisResult).delete()
        
        deleted_raw = db.query(database.SuspectWebsite).delete()
        
        # 如果你連測試建立的白名單也想一起清空，可以取消註解下面這行：
        # db.query(database.WhitelistWebsite).delete()
        
        db.commit()
        print(" 資料庫已完全清空！")
        
        return {
            "status": "success",
            "message": "系統已成功重置！所有測試資料已完全清空。",
            "details": {
                "cleared_ai_analysis_results": deleted_frontend,
                "cleared_suspect_websites": deleted_raw
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"重置資料庫失敗：{str(e)}")