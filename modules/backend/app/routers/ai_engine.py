from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import database
from schemas import YOLOAnalysisReport, NLPAnalysisReport
from dependencies import get_db, verify_internal_token
from utils import calculate_multimodal_risk_100_scale

router = APIRouter(tags=["AI 引擎分析結果接收"])

# 模組七：YOLO 獨立分析結果接收通道
@router.post("/api/ai_result/report/", summary="YOLO 引擎專用：接收影像與分數並自動統整")
def receive_ai_analysis_result(
    report: YOLOAnalysisReport,
    db: Session = Depends(get_db),
    _internal: bool = Depends(verify_internal_token),
):
    # 一定要截斷：yolo_details / nlp_details 都是 varchar(500)，
    # 串接後超長的話 MySQL 會丟 DataError，整個請求 500 而且分析結果不會寫進去。
    # schema 已經擋掉離譜的輸入，這裡是第二層——欄位長度是資料庫的事實，
    # 不該依賴呼叫端剛好沒送太長。
    yolo_str = (", ".join(report.yolo_objects) if report.yolo_objects
                else "無檢出影像特徵")[:500]
    existing_record = db.query(database.AIAnalysisResult).filter(database.AIAnalysisResult.url == report.url).first()
    suspect = db.query(database.SuspectWebsite).filter(database.SuspectWebsite.url == report.url).first()
    source_title = suspect.title if suspect else "未知來源"
    
    if existing_record:
        existing_record.yolo_details = yolo_str
        existing_record.yolo_score = report.risk_score

        existing_record.task_source = source_title
        
        existing_record.class_metadata = report.class_metadata
        existing_record.representative_image_base64 = report.representative_image_base64
        existing_record.representative_image_detections = report.representative_image_detections
        
        current_nlp_score = existing_record.nlp_score or 0
        final_score, level = calculate_multimodal_risk_100_scale(current_nlp_score, existing_record.yolo_score)
        
        existing_record.risk_score = final_score
        existing_record.risk_level = level
        db.commit()
        return {"status": "success", "message": f"成功統整！已將 YOLO 影像與分數補算至 {report.url}"}
    else:
        try:
            final_score, level = calculate_multimodal_risk_100_scale(0, report.risk_score)
            
            new_record = database.AIAnalysisResult(
                url=report.url, yolo_details=yolo_str, yolo_score=report.risk_score,
                nlp_details="文字分析中...", nlp_score=0, risk_score=final_score, risk_level=level,
                class_metadata=report.class_metadata,
                representative_image_base64=report.representative_image_base64,
                representative_image_detections=report.representative_image_detections,
                task_source=source_title
            )
            db.add(new_record)
            db.commit() 
            return {"status": "success", "message": f"成功建檔！已為 {report.url} 建立全新 AI 影像紀錄。"}
        
        except IntegrityError:
            db.rollback() 
            real_existing = db.query(database.AIAnalysisResult).filter(database.AIAnalysisResult.url == report.url).first()
            if real_existing:
                real_existing.yolo_details = yolo_str
                real_existing.yolo_score = report.risk_score
                
                real_existing.class_metadata = report.class_metadata
                real_existing.representative_image_base64 = report.representative_image_base64
                real_existing.representative_image_detections = report.representative_image_detections
                real_existing.task_source = source_title
                current_nlp_score = real_existing.nlp_score or 0
                final_score, level = calculate_multimodal_risk_100_scale(current_nlp_score, real_existing.yolo_score)
                real_existing.risk_score = final_score
                real_existing.risk_level = level
                db.commit()
            return {"status": "success", "message": "遭遇併發衝突，已轉為更新模式寫入！"}
# 模組八：NLP 獨立分析結果接收通道
@router.post("/api/nlp/report/", summary="NLP 引擎專用：接收可疑文字與分數並自動統整")
def receive_nlp_analysis_result(
    report: NLPAnalysisReport,
    db: Session = Depends(get_db),
    _internal: bool = Depends(verify_internal_token),
):
    nlp_str = (", ".join(report.nlp_keywords) if report.nlp_keywords
               else "無檢出文字特徵")[:500]
    existing_record = db.query(database.AIAnalysisResult).filter(database.AIAnalysisResult.url == report.url).first()
    suspect = db.query(database.SuspectWebsite).filter(database.SuspectWebsite.url == report.url).first()
    source_title = suspect.title if suspect else "未知來源"
    
    if existing_record:
        existing_record.nlp_details = nlp_str
        existing_record.nlp_score = report.risk_score
        existing_record.task_source = source_title
        
        current_yolo_score = existing_record.yolo_score or 0
        final_score, level = calculate_multimodal_risk_100_scale(report.risk_score, current_yolo_score)
        
        existing_record.risk_score = final_score
        existing_record.risk_level = level
        db.commit()
        return {"status": "success", "message": f"成功統整！已將 NLP 文字與分數補充至 {report.url}"}
    else:
        try:
            final_score, level = calculate_multimodal_risk_100_scale(report.risk_score, 0)
            new_record = database.AIAnalysisResult(
                url=report.url, yolo_details="影像分析中...", yolo_score=0, 
                nlp_details=nlp_str, nlp_score=report.risk_score, risk_score=final_score, risk_level=level,         
                task_source=source_title
            )
            db.add(new_record)
            db.commit()
            return {"status": "success", "message": f"成功建檔！已為 {report.url} 建立全新 AI 文字紀錄。"}
        except IntegrityError:
            db.rollback() 
            real_existing = db.query(database.AIAnalysisResult).filter(database.AIAnalysisResult.url == report.url).first()
            if real_existing:
                real_existing.nlp_details = nlp_str
                real_existing.nlp_score = report.risk_score
                real_existing.task_source = source_title
                
                current_yolo_score = real_existing.yolo_score or 0
                final_score, level = calculate_multimodal_risk_100_scale(report.risk_score, current_yolo_score)
                
                real_existing.risk_score = final_score
                real_existing.risk_level = level
                db.commit()
            return {"status": "success", "message": "遭遇併發衝突，已成功將 NLP 轉為更新模式寫入！"}