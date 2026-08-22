from pydantic import BaseModel, field_validator
from typing import List, Dict, Any, Optional
import html
import re

def check_xss(value: str) -> str:
    if not isinstance(value, str):
        return value
    
    dangerous_keywords = ["<script>", "javascript:", "onload=", "onerror="]
    val_lower = value.lower()
    for kw in dangerous_keywords:
        if kw in val_lower:
            raise ValueError("系統警告：偵測到危險的惡意程式碼，連線已攔截！")
            
    return html.escape(value)


# 前端輸入區 (嚴格防護)
class UserLogin(BaseModel):
    account: str
    password: str

    @field_validator('account')
    @classmethod
    def sanitize_account(cls, v):
        return check_xss(v)

class FrontendScanRequest(BaseModel):
    url: str

    @field_validator('url')
    @classmethod
    def sanitize_url(cls, v):
        return check_xss(v)

class WhitelistCreate(BaseModel):
    url: str
    title: str
    reason: str

    @field_validator('url', 'title', 'reason')
    @classmethod
    def sanitize_whitelist(cls, v):
        return check_xss(v)


#  內部通訊區 
class WebsiteReport(BaseModel):
    task_type: Optional[str] = "unknown"  
    timestamp: Optional[str] = "unknown"  
    keywords: Optional[List[str]] = []    
    url: str                             
    screenshot_b64: Optional[str] = None
    full_screenshot_base64: Optional[str] = None
    product_images_b64: Optional[List[Any]] = None   
    product_images_base64: Optional[List[Any]] = None
    text_content: Optional[str] = None

class YOLOAnalysisReport(BaseModel):
    url: str
    risk_score: int
    yolo_objects: List[str] = []
    processed_images: Optional[List[str]] = []
    class_metadata: Optional[Dict[str, Any]] = None
    representative_image_base64: Optional[str] = None
    representative_image_detections: Optional[List[Dict[str, Any]]] = None

class NLPAnalysisReport(BaseModel):
    url: str
    risk_score: int
    nlp_keywords: List[str] = []