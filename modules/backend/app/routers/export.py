from dependencies import get_db, get_current_user
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import pandas as pd
import io
import database
from dependencies import get_db

router = APIRouter(tags=["報表匯出模組"])

# 模組九：資料庫報表匯出 
@router.get("/api/export/ai_results_excel/", summary="匯出 AI 分析結果資料表")
def export_raw_results_to_excel(db: Session = Depends(get_db), current_user = Depends(get_current_user)): 
    results = db.query(database.AIAnalysisResult).all()
    
    if not results:
        raise HTTPException(status_code=404, detail="目前沒有任何分析資料可以匯出")

    data_list = []
    for row in results:
        row_dict = {column.name: getattr(row, column.name) for column in row.__table__.columns}
        data_list.append(row_dict)

    df = pd.DataFrame(data_list)
    df = df[['id', 'url','risk_score', 'risk_level']]
    
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
