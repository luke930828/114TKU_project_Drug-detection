from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import pandas as pd
import io

import database
from dependencies import get_db

# 宣告 router
router = APIRouter(tags=["報表匯出模組"])

# ... 下面接著放你的 @router.get("/api/export/ai_results_excel/") 等等 ... 
       # ==========================================
# 模組九：資料庫報表匯出 (前端一鍵下載 Excel)
# ==========================================
@router.get("/api/export/ai_results_excel/", summary="匯出 AI 分析結果資料表")
def export_raw_results_to_excel(db: Session = Depends(get_db)):
    # 1. 撈取資料庫所有紀錄
    results = db.query(database.AIAnalysisResult).all()
    
    if not results:
        raise HTTPException(status_code=404, detail="目前沒有任何分析資料可以匯出")

    # 2. 將 SQLAlchemy 物件動態轉換為字典列表
    data_list = []
    for row in results:
        # 動態抓取資料表的所有欄位，未來資料庫加欄位這裡也不用改！
        row_dict = {column.name: getattr(row, column.name) for column in row.__table__.columns}
        data_list.append(row_dict)

    # 3. 使用 Pandas 轉換為 DataFrame
    df = pd.DataFrame(data_list)
    
    # 4. 準備暫存空間來裝 Excel 檔 (避免寫入實體硬碟)
    stream = io.BytesIO()
    
    with pd.ExcelWriter(stream, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='AI分析總表')
    
    stream.seek(0) # 指針歸零

    # 5. 回傳檔案流給前端觸發下載
    headers = {
        'Content-Disposition': 'attachment; filename="ai_analysis_database_export.xlsx"'
    }
    
    return StreamingResponse(
        stream, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
        headers=headers
    )
