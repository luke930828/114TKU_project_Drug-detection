from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

# 1. 設定資料庫連線網址
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:MySQLdrug2026@localhost:3306/drug_prevention_db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
Base = declarative_base()

# ==========================================
# 2. 定義「使用者與權限」資料表
# ==========================================
class User(Base):
    __tablename__ = "users"

    user_id = Column(String(50), primary_key=True, index=True) 
    account = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False) 
    role = Column(String(20), nullable=False) 
    department = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    audit_logs = relationship("AuditLog", back_populates="user")

# ==========================================
# 3. 定義「數位證據稽核日誌」資料表
# ==========================================
class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey("users.user_id"), nullable=False)
    action_type = Column(String(100), nullable=False) 
    action_timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="audit_logs")

# ==========================================
# 4. 新增：「可疑網站黑名單」資料表
# ==========================================
class SuspectWebsite(Base):
    __tablename__ = "suspect_websites"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(500), nullable=False)        # 網址
    title = Column(String(200))                      # 網站標題
    risk_level = Column(String(50))
    risk_score = Column(Integer)                  # 風險等級
    keywords_found = Column(String(200))             # 發現的毒品關鍵字
    reported_by = Column(String(100))                # 是哪一隻爬蟲回報的
    created_at = Column(String(50))

# ==========================================
# 5. 執行建立資料表的指令 (⚠️ 必須放在所有資料表的最下方)
# ==========================================
if __name__ == "__main__":
    print("🚀 正在連線資料庫並建立資料表...")
    # 這裡會讀取上面定義的所有 Base，自動補齊 MySQL 缺少的表格
    Base.metadata.create_all(bind=engine)
    print("✅ 資料表建立完成！")

# database.py 裡面的新增內容
class WhitelistWebsite(Base):
    __tablename__ = "whitelist_websites"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(255), unique=True, index=True, nullable=False)
    title = Column(String(100))
    reason = Column(String(255)) # 為什麼它是白名單 (例如：政府官網)
    added_by = Column(String(50)) # 記錄是哪個總管理員加的
    created_at = Column(DateTime, default=func.now())