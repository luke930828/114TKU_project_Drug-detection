import base64
import threading
import cv2
import numpy as np
import requests
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Any
from ultralytics import YOLO

app = FastAPI(title="防毒軟體 - YOLO 影像分析部門 API")

# 1. 載入妳的專屬權重檔 (維持正確的 models/best.pt 相對路徑)
try:
    model = YOLO("models/best.pt")
    print("🎉 [成功] YOLOv8 自定義模型 models/best.pt 已順利載入！")
    print("🚨 模型內部真正的 ID 對應是：", model.names)
except Exception as e:
    print(f"🚨 [錯誤] 模型載入失敗，請確認 best.pt 是否在 models/ 目錄下！錯誤: {e}")

# 2. 妳們專案對齊的 3 種目標毒品標籤 (Key 維持數字 ID，用來做核心對齊)
CLASS_NAMES = {
    0: "大麻",
    1: "海洛因",
    2: "可卡因"
}

# 後端同學的接收網址
BACKEND_REPORT_URL = "http://100.123.184.43:8000/api/ai_result/report/"

# 🌟 全域計分板：用來統整同一個批次網址的多張圖片結果
BATCH_MEMORY = {}
memory_lock = threading.Lock()

# 4. 影像解碼小工具 (記憶體直接流轉，完全不寫入硬碟，速度最快)
def decode_base64_to_cv2(b64_data, task_id: str):
    if not b64_data: return None
    if isinstance(b64_data, list):
        if len(b64_data) > 0: b64_data = b64_data[0]
        else: return None

    b64_data = str(b64_data).strip('[]"\' ')
    if not b64_data or b64_data.lower() == 'none': return None
    if "," in b64_data: b64_data = b64_data.split(",")[1]
    
    missing_padding = len(b64_data) % 4
    if missing_padding: b64_data += "=" * (4 - missing_padding)
        
    try:
        img_data = base64.b64decode(b64_data)
        nparr = np.frombuffer(img_data, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception as decode_err:
        print(f"[⚠️ 解碼炸裂] Base64 解析失敗 (Task: {task_id}): {decode_err}")
        return None

# 5. 核心非同步工廠：偷偷在背景算 YOLO，全部圖片到齊後才打電話給後端
def background_yolo_and_report(url: str, image_base64: Any, task_id: str, total_images: int):
    print(f"\n[🔥 影像分析啟動] 正在處理任務: {task_id}")
    
    batch_id = task_id.split("_")[0] if "_" in task_id else task_id
    
    try:
        # 解碼圖片
        img = decode_base64_to_cv2(image_base64, task_id)
        
        current_objects = []
        current_score = 0
        is_valid = False
        
        if img is not None:
            # 執行推論，信心度門檻開 0.1 逼低分訊號現形
            results = model(img, conf=0.1)
            
            max_conf = 0.0
            for r in results:
                for box in r.boxes:
                    conf = float(box.conf)
                    cls_id = int(box.cls)  # 👈 這是模型吐出來的原始數字 ID (0, 1, 2)
                    
                    actual_name = r.names.get(cls_id, "未知")
                    print(f"🔍 YOLO 原始偵測 -> ID: {cls_id}, 信心度: {conf:.2f}, 原始標籤: {actual_name}")
                    
                    # 🌟 【關鍵修正】：直接用數字 ID (cls_id) 去查字典！
                    # 不管模型吐出 'cannabis' 還是什麼，只要 cls_id 是 0、1、2，就 100% 抓得到！
                    if cls_id in CLASS_NAMES:
                        target_zh_name = CLASS_NAMES[cls_id]  # 自動轉成漂亮的中文標籤
                        if target_zh_name not in current_objects:
                            current_objects.append(target_zh_name)
                        if conf > max_conf:
                            max_conf = conf
            
            # 只有當這張圖成功認出目標毒品（current_objects 有東西）時，才算有效分數
            current_score = int(max_conf * 100) if current_objects else 0
            is_valid = True if current_score > 0 else False

        # 控制是否發送最終報告的變數
        should_report = False
        final_risk_score = 0
        detected_objects = []
        is_valid_drug_payload = False

        # -----------------------------------------------------------------
        # 🌟 核心記憶體統整算式：使用 Lock 確保多執行緒累加安全
        # -----------------------------------------------------------------
        with memory_lock:
            if batch_id not in BATCH_MEMORY:
                BATCH_MEMORY[batch_id] = {
                    "total_valid_score": 0,
                    "valid_count": 0,
                    "all_detected_drugs": set(),
                    "history_max_score": 0,
                    "processed_count": 0  
                }
            
            # 圖片處理計數器 +1
            BATCH_MEMORY[batch_id]["processed_count"] += 1
            
            # 🌟 只有算出那三種毒品且有分數的，才拿來累加進分子與分母
            if is_valid:
                BATCH_MEMORY[batch_id]["total_valid_score"] += current_score
                BATCH_MEMORY[batch_id]["valid_count"] += 1
                for obj in current_objects:
                    BATCH_MEMORY[batch_id]["all_detected_drugs"].add(obj)
            
            # 更新歷史最高單張分數（作為 0 分時的保底防線）
            if current_score > BATCH_MEMORY[batch_id]["history_max_score"]:
                BATCH_MEMORY[batch_id]["history_max_score"] = current_score
            
            current_progress = BATCH_MEMORY[batch_id]["processed_count"]
            print(f"📊 批次進度追蹤 [{batch_id}]: {current_progress} / {total_images} (當前任務: {task_id})")
            
            # 🌟 檢查：是否所有圖片都到齊了？
            if current_progress >= total_images:
                should_report = True  
                
                v_count = BATCH_MEMORY[batch_id]["valid_count"]
                if v_count > 0:
                    # 🌟 精準平均分 = 總有效分 / 有效圖筆數
                    final_risk_score = int(BATCH_MEMORY[batch_id]["total_valid_score"] / v_count)
                    detected_objects = list(BATCH_MEMORY[batch_id]["all_detected_drugs"])
                    is_valid_drug_payload = True
                else:
                    # 如果整批 11 張圖都沒有半張抓到毒品，給予歷史最高分（0分）安全開局
                    final_risk_score = BATCH_MEMORY[batch_id]["history_max_score"]
                    detected_objects = ["未偵測到管制毒品"]
                    is_valid_drug_payload = False

        # -----------------------------------------------------------------
        # 6. 打包最終成果回傳給中央後端 (Leo) -> 只有到齊了才發送
        # -----------------------------------------------------------------
        if should_report:
            payload = {
                "url": url,                                  
                "risk_score": final_risk_score,               
                "yolo_objects": detected_objects, # 這裡保證絕對只會是中文毒品名稱
                "processed_images": [],                        
                "is_valid_drug": is_valid_drug_payload          
            }
            
            print(f"\n[🚀 批次全數到齊！] 正在發送最終結算報告給後端。批次: {batch_id}")
            print(f"   -> 最終有效圖筆數: {v_count}, 總毒品種類: {detected_objects}")
            print(f"   -> 最終精準平均分數: {final_risk_score} 分")
            
            response = requests.post(BACKEND_REPORT_URL, json=payload, timeout=5)
            print(f"[✨ 後端回應] 狀態碼: {response.status_code}, 內容: {response.text}")
            
            # 釋放記憶體
            with memory_lock:
                if batch_id in BATCH_MEMORY:
                    del BATCH_MEMORY[batch_id]
                    print(f"🧹 [記憶體清理] 已成功釋放批次 {batch_id} 的緩存空間。")
        else:
            print(f"⏳ 任務 {task_id} 處理完畢，目前累計 {current_progress} 張圖，等待其餘圖片到齊中...")
            
    except Exception as e:
        print(f"❌ 背景處理或回報失敗: {str(e)}")

# 7. 接收口
@app.post("/api/v1/predict/trigger")
async def receive_from_backend(data: dict, background_tasks: BackgroundTasks):
    task_id = data.get("task_id", "unknown_task")
    url = data.get("url", "")
    image_base64 = data.get("image_base64", None)
    priority = data.get("priority", 0)
    
    # 🌟 讀取後端加在最後一條位子的 total_images
    total_images = data.get("total_images", 11)
    
    background_tasks.add_task(background_yolo_and_report, url, image_base64, task_id, total_images)
    return {"status": "success", "message": f"YOLO 已經接單 (Task: {task_id}, 預期總圖數: {total_images})"}