from dependencies import get_db, get_current_user
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
    current_user = Depends(get_current_user)
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

    headers = {
        'Content-Disposition': 'attachment; filename="ai_analysis_database_export.xlsx"'
    }
    
    return StreamingResponse(
        stream, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
        headers=headers
    )