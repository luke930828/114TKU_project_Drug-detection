from pydantic import BaseModel
from typing import List, Dict, Any, Optional
class UserLogin(BaseModel):
    account: str
    password: str


class FrontendScanRequest(BaseModel):
    url: str

class WhitelistCreate(BaseModel):
    url: str
    title: str
    reason: str


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