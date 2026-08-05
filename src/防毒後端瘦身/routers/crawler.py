
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
import json

import database
# 從你建好的抽屜拿出對應的工具
from schemas import WebsiteReport
from dependencies import get_db, verify_admin
from utils import calculate_multimodal_risk_100_scale, dispatch_to_ai_engines

# 宣告 router
router = APIRouter(tags=["自動爬蟲管理"])

# ... 下面接著放你的 @router.get("/api/crawler/report/") 等等 ...
#  模組三：查詢已識別網站 (右下角卡片) ->  鎖定只從 AIAnalysisResult 撈取
@router.get("/api/crawler/report/", summary="獲取前端專用 AI 分析黑名單報表")
def get_frontend_report(current_user: database.User = Depends(verify_admin), db: Session = Depends(get_db)):
    results = db.query(database.AIAnalysisResult).all()
    return {
        "status": "success",
        "message": "成功抓取最新 AI 多模態識別資料庫",
        "total_count": len(results),
        "data": results
    }

# 模組四：爬蟲專用通道 (支援字典解開封裝 + 抓猴雷達 + 🌟 融合無效網站攔截器)
@router.post("/api/crawler/report/", summary="爬蟲端專用：將原始結果寫入 suspect_websites 表")
def receive_crawler_raw_data(report: WebsiteReport, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        print(f"收到爬蟲通報網址：{report.url}")
        
        # =========================================================
        # 🛡️ 【新增防線：無效網站攔截器】(插在你原本的邏輯最前面)
        # =========================================================
        html_text = report.text_content if report.text_content else ""
        if "非毒品" in html_text or "無法正常登入" in html_text or "無法登入" in html_text:
            print(f"🛑 [攔截機制啟動] 爬蟲遇到需登入或非目標網站 ({report.url})，直接歸檔為 0 分！")
            
            # 1. 寫入 suspect_websites (當作紀錄)
            new_website = database.SuspectWebsite(
                url=report.url,
                title="[系統攔截] 網站需登入或無效",
                keywords_found="",
                reported_by="爬蟲端自動上傳",
                html_content=html_text,    
                images_data="[]" 
            )
            db.add(new_website)
            
            # 2. 建立「已結案」的 0 分展示紀錄給前端撈取
            existing_record = db.query(database.AIAnalysisResult).filter(database.AIAnalysisResult.url == report.url).first()
            if not existing_record:
                final_score, level = calculate_multimodal_risk_100_scale(0, 0)
                new_ai_record = database.AIAnalysisResult(
                    url=report.url,
                    yolo_details="無影像 (需登入或防爬蟲阻擋)",
                    yolo_score=0,
                    nlp_details=html_text[:50], # 直接把「無法登入」這句話印在前端畫面上
                    nlp_score=0,
                    risk_score=final_score,
                    risk_level=level,
                    task_source=f"[{report.task_type}] 爬蟲自動通報"
                )
                db.add(new_ai_record)
            
            db.commit()
            return {"status": "success", "message": "已成功攔截無效網站，跳過 AI 派發並直接歸檔為 0 分。"}
            # ⛔ 只要進了這個 if，程式就會在這裡 return 結束，不會往下跑！
        # =========================================================

        # 👇 以下完全保留你原本寫好的完美邏輯，沒有做任何更改：
        extracted_images = []
        
        incoming_images = report.product_images_b64 or report.product_images_base64 or []
        
        print(f"爬蟲傳來的圖片陣列內容：{incoming_images[:2]} ")
        
        for img_obj in incoming_images:
            if isinstance(img_obj, dict):
                base64_str = img_obj.get("base64_data") or img_obj.get("base64") or img_obj.get("data") or img_obj.get("image")
                if base64_str:
                    extracted_images.append(base64_str)
            elif isinstance(img_obj, str):
                extracted_images.append(img_obj)

        images_json_string = json.dumps(extracted_images, ensure_ascii=False) if extracted_images else "[]"
        keywords_str = ", ".join(report.keywords) if report.keywords else ""

        new_website = database.SuspectWebsite(
            url=report.url,
            title=f"[{report.task_type}] 爬蟲自動通報",
            keywords_found=keywords_str,
            reported_by="爬蟲端自動上傳",
            html_content=report.text_content if report.text_content else "",    
            images_data=images_json_string 
        )
        db.add(new_website)
        db.commit()
        print(f"原始網頁快照寫入成功！成功從包裹中萃取出 {len(extracted_images)} 張圖片。")
        
        try:
            background_tasks.add_task(
                dispatch_to_ai_engines, 
                report.url, 
                report.text_content if report.text_content else "", 
                extracted_images  
            )
            print("背景派發任務已順利啟動！")
        except Exception as ai_err:
            print(f"背景任務加入失敗：{str(ai_err)}")

        return {"status": "success", "message": "資料已接收並解開封裝，自動派發中。"}

    except Exception as e:
        db.rollback()
        print(f"嚴重錯誤：API 崩潰了，原因：{str(e)}")
        raise HTTPException(status_code=500, detail=f"伺服器內部錯誤：{str(e)}")
    
@router.get("/api/crawler/automated_24h_list/", summary="獲取 24 小時自動爬蟲的 AI 分析結果")
def get_automated_24h_results(db: Session = Depends(get_db)):
    
    # 🚀 直接單表查詢！不需要 JOIN 了，效能超級快！
    results = db.query(database.AIAnalysisResult).filter(
        database.AIAnalysisResult.task_source.like("%[automated_24h]%")
    ).all()

    frontend_data = []
    
    for index, ai_record in enumerate(results, start=1):
        # 處理日期格式
        date_str = "2024-12-01" 
        if hasattr(ai_record, 'created_at') and ai_record.created_at:
            date_str = ai_record.created_at.strftime("%Y-%m-%d")

        # 動態決定處置狀態
        status = "Active"
        if ai_record.risk_score >= 85:
            status = "Blocked"
        elif 75 <= ai_record.risk_score < 85:
            status = "Investigation"
        elif ai_record.risk_score < 75:
            status = "Monitored"

        frontend_data.append({
            "id": index,                                 
            "domain_name": ai_record.url,                
            "server_location": "Unknown",                
            "risk_score": ai_record.risk_score,          
            "discovered_date": date_str,                 
            "status": status,                            
            "task_source": ai_record.task_source, # 把來源標籤也傳給前端
            "risk_level": ai_record.risk_level,
            "yolo_details": ai_record.yolo_details,
            "nlp_details": ai_record.nlp_details
        })

    return {
        "status": "success",
        "message": "成功獲取 24 小時自動爬蟲清單",
        "total_count": len(frontend_data),
        "data": frontend_data
    }