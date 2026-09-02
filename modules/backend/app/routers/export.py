from dependencies import get_db, get_current_user, verify_admin, log_audit_action
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
import pandas as pd
import io
import database

router = APIRouter(tags=["報表匯出模組"])

@router.get("/api/export/ai_results_excel/", summary="匯出 AI 分析結果資料表")
def export_raw_results_to_excel(
    start_date: Optional[str] = Query(None, description="開始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="結束日期 (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    # 匯出是把「全部蒐證資料」一次帶走，不是一般查詢——限管理員（SEC-12）。
    # 原本是 get_current_user，任何登入者都能整包下載。
    current_user = Depends(verify_admin),
): 
    query = db.query(
        database.AIAnalysisResult.id,
        database.AIAnalysisResult.url,
        database.AIAnalysisResult.risk_score,
        database.AIAnalysisResult.risk_level,
        database.AIAnalysisResult.created_at 
    )
    
    if start_date:
        query = query.filter(database.AIAnalysisResult.created_at >= start_date)
    if end_date:
        query = query.filter(database.AIAnalysisResult.created_at <= f"{end_date} 23:59:59")
        
    results = query.all()
    
    if not results:
        raise HTTPException(status_code=404, detail="目前沒有符合該時間區間的分析資料可以匯出")

    data_list = [
        {
            "id": row.id,
            "url": row.url,
            "risk_score": row.risk_score,
            "risk_level": row.risk_level
        }
        for row in results
    ]

    df = pd.DataFrame(data_list)
    
    stream = io.BytesIO()
    
    with pd.ExcelWriter(stream, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='AI分析總表')
    
    stream.seek(0)

    # 「誰在什麼時候把整批蒐證資料帶走了」——這是稽核軌跡裡最該留的一筆
    log_audit_action(
        db, current_user.user_id, "匯出報表",
        f"匯出 {len(data_list)} 筆 AI 分析結果"
        + (f"（{start_date} ~ {end_date}）" if start_date or end_date else ""),
    )

    headers = {
        'Content-Disposition': 'attachment; filename="ai_analysis_database_export.xlsx"'
    }
    
    return StreamingResponse(
        stream, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
        headers=headers
    )