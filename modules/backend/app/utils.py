import os
import uuid
import requests

# 分級門檻。crawler.py 的 24 小時清單也讀這裡，不要各寫一套
# （以前 utils 用 74/35、crawler 用 85/75，同一筆資料會有兩個答案）。
NLP_HIGH = 90        # NLP 到這個分數就一定要送人工覆核
NLP_MEDIUM = 60
YOLO_CONFIRM = 30    # 影像也附和到這個程度，覆核優先度往上提


def calculate_multimodal_risk_100_scale(nlp_raw_score: int, yolo_raw_score: int):
    """
    依 NLP 與 YOLO 的原始分數（0~100）算出綜合分數與風險等級。

    為什麼不再用加權平均
    ────────────────────
    原本是 0.6×NLP + 0.4×YOLO > 74 才算極高風險。問題是純文字的販售頁、
    訂單查詢頁、FAQ 頁本來就沒有商品圖可辨識，YOLO 給 0 分是正確的——
    但 0.6×100 + 0.4×0 = 60，低於 74，整個網站就被放行了。

    用 217 筆人工標註的真實網頁量過（data/eval_sample/）：
        舊規則 0.6n+0.4y > 74   recall 0.653　漏掉 41 個毒品網站
        改用   NLP >= 90         recall 0.975　漏掉  3 個
    而且把 YOLO 加進判定條件完全沒有幫助（漏報一樣是 3 個，
    precision 卻從 0.772 掉到 0.706，還多 14 件要人工看）。

    所以 YOLO 不參與「要不要覆核」的判定，改用來排覆核的優先順序：
    NLP 高分且 YOLO 也附和的那批，實際命中率 81%；YOLO 沒附和的是 69%。

    綜合分數仍以加權算出並保留，因為前端與報表要拿它排序；
    但風險等級不再由它決定。
    """
    combined = int(0.6 * nlp_raw_score + 0.4 * yolo_raw_score)

    if nlp_raw_score >= NLP_HIGH and yolo_raw_score >= YOLO_CONFIRM:
        risk_level = "極高風險"                      # 兩個引擎都指向毒品
    elif nlp_raw_score >= NLP_HIGH:
        risk_level = "高風險 (優先人工覆核)"          # 文字確定，影像沒東西可看
    elif nlp_raw_score >= NLP_MEDIUM or yolo_raw_score >= NLP_HIGH:
        risk_level = "中風險 (建議人工覆核)"
    else:
        risk_level = "低風險"

    return combined, risk_level


def needs_review(nlp_raw_score: int, yolo_raw_score: int) -> bool:
    """這筆要不要進人工覆核清單。分級規則只寫在這個檔案，避免又出現兩套標準。"""
    return nlp_raw_score >= NLP_HIGH or yolo_raw_score >= NLP_HIGH


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