from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, JSON, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
from sqlalchemy.dialects.mysql import LONGTEXT
import json
import os

# 1. 設定資料庫連線網址（一律從環境變數讀，不要寫死密碼——這行已經被改回寫死兩次了，
#    再改回去之前請先確認你本機有設好 DB_PASSWORD / DB_HOST，見 .env.local）
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.environ["DB_PASSWORD"]  # 必填，沒設就直接爆掉，不要靜靜用預設值跑錯
DB_HOST = os.getenv("DB_HOST", "mysql")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "drug_prevention_db")
SQLALCHEMY_DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?charset=utf8mb4"
)
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
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
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    audit_logs = relationship("AuditLog", back_populates="user")



# 3. 定義「數位證據稽核日誌」資料表
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    log_id = Column(Integer, primary_key=True, index=True) 
    
    user_id = Column(String(50), ForeignKey("users.user_id"), nullable=False)
    
    action_type = Column(String(100), nullable=False)
    
    action_timestamp = Column(DateTime, default=datetime.utcnow) 
    
    details = Column(String(500), nullable=True)
    
    user = relationship("User", back_populates="audit_logs")
# 4. 定義：「可疑網站黑名單」資料表
# 4. 定義：「可疑網站黑名單」資料表
class SuspectWebsite(Base):
    __tablename__ = "suspect_websites"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(768), unique=True, index=True, nullable=False)
    title = Column(String(100))
    keywords_found = Column(String(500))
    reported_by = Column(String(50))
    created_at = Column(DateTime, default=func.now())

    html_content = Column(LONGTEXT, nullable=True)  
    images_data = Column(LONGTEXT, nullable=True)
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
    
    class_metadata = Column(JSON, nullable=True) 
    representative_image_base64 = Column(LONGTEXT, nullable=True)
    representative_image_detections = Column(JSON, nullable=True)
    task_source = Column(String(100), default="未知來源")
    created_at = Column(DateTime, default=func.now())


#  7. 執行建立資料表的指令 
if __name__ == "__main__":
    print("正在連線資料庫並建立資料表...")
    Base.metadata.create_all(bind=engine)
    print(" 資料表建立完成！")