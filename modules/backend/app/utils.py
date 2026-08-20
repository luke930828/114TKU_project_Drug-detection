import os
import uuid
import requests

def calculate_multimodal_risk_100_scale(nlp_raw_score: int, yolo_raw_score: int):
    """
    根據 NLP 與 YOLO 的原始分數 (0~100)，計算雙引擎加權總分與風險等級。
    """
    w_text = 0.6
    w_image = 0.4
    
    s_final = (w_text * nlp_raw_score) + (w_image * yolo_raw_score)
    
    if s_final > 74:
        risk_level = "極高風險"
    elif 35 <= s_final <= 74:
        risk_level = "中風險 (建議人工覆核)"
    else:
        risk_level = "低風險"
        
    return int(s_final), risk_level


def dispatch_to_ai_engines(url: str, html_content: str, images: list):
    """
    背景任務：將資料派發給 NLP 與 YOLO 引擎
    """
    # 讀取環境變數網址 (預設值為單機開發測試用)
    NLP_PREDICT_URL = os.getenv("NLP_PREDICT_URL", "http://100.69.185.94:8000/predict")
    YOLO_API_URL = os.getenv("YOLO_API_URL", "http://100.101.167.105:5000/api/v1/predict/trigger")
    BACKEND_NLP_REPORT_URL = os.getenv("BACKEND_NLP_REPORT_URL", "http://127.0.0.1:8000/api/nlp/report/")
    
    generated_task_id = str(uuid.uuid4())[:8]

    # 第一階段：派發給 NLP 的任務 (文字)
    try:
        nlp_payload = {
            "url": url,
            "text": html_content
        }
        print("準備將文字派發給 NLP...")

        response = requests.post(NLP_PREDICT_URL, json=nlp_payload, timeout=10)

        if response.status_code == 200:
            nlp_result = response.json()
            print(f"NLP 分析完成！收到結果：{nlp_result}")
            
            score_float = nlp_result.get("score", 0)
            risk_score_int = int(score_float * 100)
            
            internal_payload = {
                "url": url,
                "risk_score": risk_score_int,
                "nlp_keywords": nlp_result.get("keywords", [])
            }
            # 同步回傳給後端資料庫
            requests.post(BACKEND_NLP_REPORT_URL, json=internal_payload)
            print("NLP 結果已成功同步至資料庫！")
            
    except requests.exceptions.Timeout:
        print("呼叫 NLP 逾時！")
    except Exception as e:
        print(f"派發至 NLP 引擎失敗: {e}")

    # 第二階段：派發給 YOLO 的任務 (圖片)
    if images and len(images) > 0:
        print(f"準備將 {len(images)} 張圖片逐一派發給 YOLO...")
        
        for index, single_image_str in enumerate(images):
            try:
                yolo_payload = {
                    "task_id": f"{generated_task_id}_{index}", 
                    "url": url,
                    "image_base64": single_image_str,
                    "total_images": len(images),  
                    "priority": 0
                }
                response = requests.post(YOLO_API_URL, json=yolo_payload, timeout=5)
                print(f"    第 {index+1} 張派發成功！對方回應: {response.text}")
            except Exception as e:
                print(f"    第 {index+1} 張圖片派發至 YOLO 失敗: {e}")