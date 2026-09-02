from dependencies import get_db, get_current_user
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
import json
import database
from schemas import WebsiteReport
from dependencies import get_db, verify_admin, verify_internal_token
from utils import calculate_multimodal_risk_100_scale, dispatch_to_ai_engines, needs_review
import traceback

router = APIRouter(tags=["自動爬蟲管理"])

#  模組三：查詢已識別網站
@router.get("/api/crawler/report/", summary="獲取前端專用 AI 分析黑名單報表")
def get_frontend_report(current_user: database.User = Depends(verify_admin), db: Session = Depends(get_db)):
    results = db.query(database.AIAnalysisResult).all()
    return {
        "status": "success",
        "message": "成功抓取最新 AI 多模態識別資料庫",
        "total_count": len(results),
        "data": results
    }

# 模組四：爬蟲專用通道 
@router.post("/api/crawler/report/", summary="爬蟲端專用：將原始結果寫入 suspect_websites 表")
def receive_crawler_raw_data(
    report: WebsiteReport,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _internal: bool = Depends(verify_internal_token),
):
    try:
        print(f"收到爬蟲通報網址：{report.url}")
        is_whitelisted = db.query(database.WhitelistWebsite).filter(
            database.WhitelistWebsite.url == report.url
        ).first()

        if is_whitelisted:
            print(f"[白名單放行] 網址 {report.url} 位於白名單中 ({is_whitelisted.title})，跳過後續所有動作！")
            return {
                "status": "skipped", 
                "message": f"攔截成功：網址 {report.url} 位於白名單中 ({is_whitelisted.title})，已自動放行。"
            }
        html_text = report.text_content if report.text_content else ""
        if "非毒品" in html_text or "無法正常登入" in html_text or "無法登入" in html_text:
            print(f" [攔截機制啟動] 爬蟲遇到需登入或非目標網站 ({report.url})，直接歸檔為 0 分！")
            
            new_website = database.SuspectWebsite(
                url=report.url,
                title="[系統攔截] 網站需登入或無效",
                keywords_found="",
                reported_by="爬蟲端自動上傳",
                html_content=html_text,    
                images_data="[]" 
            )
            db.add(new_website)
            
            existing_record = db.query(database.AIAnalysisResult).filter(database.AIAnalysisResult.url == report.url).first()
            if not existing_record:
                final_score, level = calculate_multimodal_risk_100_scale(0, 0)
                new_ai_record = database.AIAnalysisResult(
                    url=report.url,
                    yolo_details="無影像 (需登入或防爬蟲阻擋)",
                    yolo_score=0,
                    nlp_details=html_text[:50], 
                    nlp_score=0,
                    risk_score=final_score,
                    risk_level=level,
                    task_source=f"[{report.task_type}] 爬蟲自動通報"
                )
                db.add(new_ai_record)
            
            db.commit()
            return {"status": "success", "message": "已成功攔截無效網站，跳過 AI 派發並直接歸檔為 0 分。"}

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
        # 詳細錯誤只留在伺服器日誌，不要回給客戶端。
        # SQLAlchemy 的例外訊息會夾帶完整 SQL 語句、參數值與內部主機名，
        # 這個端點又沒有驗證，等於免費把資料庫結構送給任何人。
        print(f"嚴重錯誤：/api/crawler/report/ 處理失敗（{report.url}）：{e!r}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="伺服器內部錯誤，請聯繫系統管理員")
@router.get("/api/crawler/automated_24h_list/", summary="獲取 24 小時自動爬蟲清單")
def get_automated_24h_results(
    db: Session = Depends(get_db), 
    current_user = Depends(get_current_user),
    page: int = Query(1, description="當前頁碼 (預設第 1 頁)"),
    limit: int = Query(50, description="每頁顯示幾筆")
):
    
    base_query = db.query(database.AIAnalysisResult).filter(
        database.AIAnalysisResult.task_source.like("%[automated_24h]%")
    )

    # 統計也依 risk_level，不要再用 risk_score 自己切一套門檻
    total_count = base_query.count()
    high_risk_count = base_query.filter(
        database.AIAnalysisResult.risk_level == "極高風險").count()
    med_risk_count = base_query.filter(
        database.AIAnalysisResult.risk_level.in_(
            ["高風險 (優先人工覆核)", "中風險 (建議人工覆核)"])).count()
    low_risk_count = total_count - high_risk_count - med_risk_count
    skip = (page - 1) * limit
    results = base_query.order_by(database.AIAnalysisResult.created_at.desc()) \
                        .offset(skip) \
                        .limit(limit) \
                        .all()

    frontend_data = []
    
    for index, ai_record in enumerate(results, start=1):
        date_str = "2024-12-01" 
        if hasattr(ai_record, 'created_at') and ai_record.created_at:
            date_str = ai_record.created_at.strftime("%Y-%m-%d")

        # status 直接對應 risk_level，不要另外拿 risk_score 算一套門檻。
        # 以前這裡用 85/75，utils.py 用 74/35，同一筆資料在報表和清單上
        # 會顯示成不同等級——68 分在 risk_level 是「中風險」，在這裡卻是
        # 最低的 Monitored。
        status = {
            "極高風險": "Blocked",
            "高風險 (優先人工覆核)": "Investigation",
            "中風險 (建議人工覆核)": "Investigation",
        }.get(ai_record.risk_level, "Monitored")

        frontend_data.append({
            "id": ai_record.id,                                 
            "domain_name": ai_record.url,                
            "server_location": "Unknown",                
            "risk_score": ai_record.risk_score,          
            "discovered_date": date_str,                 
            "status": status,                            
            "task_source": ai_record.task_source, 
            "risk_level": ai_record.risk_level,
            "yolo_details": ai_record.yolo_details,
            "yolo_score": ai_record.yolo_score,
            "nlp_details": ai_record.nlp_details,
            "nlp_score": ai_record.nlp_score,
            "class_metadata": ai_record.class_metadata,
            "representative_image_base64": ai_record.representative_image_base64,
            "representative_image_detections": ai_record.representative_image_detections,
            "ocr_results": ai_record.ocr_results,
        })

    return {
        "status": "success",
        "message": "成功獲取 24 小時自動爬蟲清單",
        "total_count": total_count, 
        "stats": {
            "total": total_count,
            "high": high_risk_count,
            "medium": med_risk_count,
            "low": low_risk_count
        },
        "pagination": {
            "total_count": total_count,
            "current_page": page,
            "limit": limit,
            "total_pages": (total_count + limit - 1) // limit if limit > 0 else 0
        },
        "data": frontend_data
    }
