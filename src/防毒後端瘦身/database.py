from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
from sqlalchemy.dialects.mysql import LONGTEXT
import json 

# 1. 設定資料庫連線網址
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:MySQLdrug2026@localhost:3306/drug_prevention_db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
Base = declarative_base()

# 2. 定義「使用者與權限」資料表
class User(Base):
    __tablename__ = "users"

    user_id = Column(String(50), primary_key=True, index=True) 
    account = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False) 
    role = Column(String(20), nullable=False) 
    department = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    audit_logs = relationship("AuditLog", back_populates="user")

# 3. 定義「數位證據稽核日誌」資料表
class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey("users.user_id"), nullable=False)
    action_type = Column(String(100), nullable=False) 
    action_timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="audit_logs")

# 4. 定義：「可疑網站黑名單」資料表
class SuspectWebsite(Base):
    __tablename__ = "suspect_websites"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(768), unique=True, index=True, nullable=False)
    title = Column(String(100))
    keywords_found = Column(String(500))
    reported_by = Column(String(50))
    created_at = Column(DateTime, default=func.now())

    html_content = Column(Text, nullable=True)  
    images_data = Column(Text, nullable=True)   

# 5. 定義：「白名單」資料表
class WhitelistWebsite(Base):
    __tablename__ = "whitelist_websites"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(768), unique=True, index=True, nullable=False)
    title = Column(String(100))
    reason = Column(String(255))
    added_by = Column(String(50)) 
    created_at = Column(DateTime, default=func.now())

# 6. 定義：專門展示給前端看的 AI 分析結果表
class AIAnalysisResult(Base):
    __tablename__ = "ai_analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(768), index=True, nullable=False)
    
    yolo_details = Column(String(500))  
    yolo_score = Column(Integer, default=0)
    
    nlp_details = Column(String(500))  
    nlp_score = Column(Integer, default=0)
    
    risk_score = Column(Integer)
    risk_level = Column(String(50))
    
    # 👇 已經將這三個新欄位補上
    class_metadata = Column(JSON, nullable=True) 
    representative_image_base64 = Column(LONGTEXT, nullable=True)
    representative_image_detections = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=func.now())


# 👇 7. 執行建立資料表的指令 (必須放在所有 class 的最下方！)
if __name__ == "__main__":
    print("正在連線資料庫並建立資料表...")
    Base.metadata.create_all(bind=engine)
    print(" 資料表建立完成！")