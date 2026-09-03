import os
import uuid
from urllib.parse import urlparse

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
    # 舊寫法（勿用）：... or yolo_raw_score >= NLP_HIGH
    # 上面才剛說「YOLO 不參與要不要覆核的判定」，這一行卻讓 YOLO 單獨把東西
    # 推進覆核清單，是當初漏改的。實測代價很大：
    #   線上資料 中風險 155 筆，其中 121 筆（78%）是這條觸發的，那批 nlp 平均 0 分
    #   217 筆人工標註裡符合這條的有 12 筆，真陽性 0 個，命中率 0%
    #   拿掉之後少標 12 筆，漏掉的真毒品網站是 0 個
    # 也就是說它只產生誤報。YOLO 在乾淨的商品照上很容易把保健食品、化妝品、
    # 食品看成毒品，而文字完全沒有訊號時那幾乎一定是誤判。
    elif nlp_raw_score >= NLP_MEDIUM:
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
    # 不給預設值。以前這裡寫死了某台機器的 tailnet IP，環境變數沒設時
    # 會靜靜地把蒐證資料送到那台機器去——那比啟動失敗嚴重得多。
    # 跟 DB_PASSWORD / JWT_SECRET_KEY 一樣，沒設就直接爆掉。
    NLP_PREDICT_URL = os.environ["NLP_PREDICT_URL"]
    YOLO_API_URL = os.environ["YOLO_API_URL"]
    BACKEND_NLP_REPORT_URL = os.getenv("BACKEND_NLP_REPORT_URL", "http://127.0.0.1:8000/api/nlp/report/")
    # /api/nlp/report/ 現在要驗證了，後端打自己也不例外。
    # 走 HTTP 回推自己這件事本身有點怪（BUG-03 的重複寫入就是這樣來的），
    # 但在改掉之前，它一樣得帶 token，不然這條路徑會靜靜地全部 401。
    INTERNAL_HEADERS = {"X-Internal-Token": os.environ["INTERNAL_API_TOKEN"]}
    
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
            requests.post(BACKEND_NLP_REPORT_URL, json=internal_payload,
                          headers=INTERNAL_HEADERS, timeout=10)
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

def registrable_domain(url: str) -> str:
    """
    取出用來比對白名單的網域。www. 視為同一個站。

    不用 tldextract：後端沒這個相依，而且白名單比的是「使用者輸入的那個站」，
    不需要處理 co.uk 這種多段字尾——momo.com.tw 與 www.momo.com.tw
    要視為同一個，剩下的交給完整網域字串比對就夠準了。
    """
    try:
        host = (urlparse(url if "//" in url else f"//{url}").hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def is_whitelisted(db, url: str):
    """
    這個網址所屬的網域在不在白名單裡。找到就回傳那一筆，否則 None。

    以前是拿完整網址做等值比對，等於只擋得住白名單裡「一模一樣」的那一頁。
    實測 https://www.momoshop.com.tw/ 加了白名單之後，
    https://www.momoshop.com.tw/goods/GoodsDetail.jsp?i_code=12345 照樣被分析——
    momo 有幾十萬個商品頁，一頁一頁加是不可能的，白名單形同無效。
    改成比對網域。
    """
    import database
    target = registrable_domain(url)
    if not target:
        return None
    for row in db.query(database.WhitelistWebsite).all():
        if registrable_domain(row.url) == target:
            return row
    return None


def is_blacklisted(db, url: str):
    """這個網址所屬的網域在不在人工黑名單裡。找到就回傳那一筆，否則 None。"""
    import database
    target = registrable_domain(url)
    if not target:
        return None
    for row in db.query(database.BlacklistWebsite).all():
        if registrable_domain(row.url) == target:
            return row
    return None


# LIKE 的萬用字元。搜尋關鍵字是使用者輸入的，不跳脫的話 q=% 會把整張表撈出來，
# q=a_b 會誤命中 axb——實測 q=% 在 6695 筆的表上回傳全部 6695 筆。
# 反斜線要第一個換，不然後面換出來的跳脫字元會被重複處理。
LIKE_SPECIAL = (("\\", "\\\\"), ("%", "\\%"), ("_", "\\_"))


def like_pattern(keyword: str) -> str:
    """把使用者的關鍵字轉成安全的 LIKE 樣式（呼叫端要配 escape="\\"）。"""
    text = (keyword or "").strip()
    for src, dst in LIKE_SPECIAL:
        text = text.replace(src, dst)
    return f"%{text}%"


# OCR 文字要「另外」送給 NLP，不能接在網頁文字後面
# ────────────────────────────────────────────────
# NLP 的 tokenizer 是 truncation=True, max_length=256（modules/nlp/app/main.py），
# 網頁文字通常早就超過 256 個 token 了，OCR 附在後面會被整段截掉，
# 等於什麼都沒做——而且不會有任何錯誤訊息，看起來像「OCR 沒幫上忙」。
#
# 所以獨立呼叫一次 /predict，拿到「圖片文字的毒品機率」，再跟網頁文字的分數合併。
OCR_MIN_CONFIDENCE = 0.5     # EasyOCR 低於這個值的多半是雜訊（實測 0.36 是 'SHIPPIHGORLDWIIDE'）
OCR_MIN_CHARS = 2            # 一兩個字元的碎片沒有語意
OCR_MIN_TOTAL_CHARS = 10     # 全部串起來還不到 10 個字就別浪費一次推論


def ocr_texts_to_sentence(ocr_results) -> str:
    """把 OCR 的結果整理成一段可以餵給 NLP 的文字。

    只留信心夠高、長度夠的片段。順序照 EasyOCR 給的（大致是由上到下、
    由左到右），比照原樣串起來比重新排序更接近人看到的版面。
    """
    if not ocr_results:
        return ""
    texts = (ocr_results or {}).get("detected_texts") or []
    kept = []
    for item in texts:
        text = (item.get("text") or "").strip()
        if len(text) < OCR_MIN_CHARS:
            continue
        if (item.get("confidence") or 0) < OCR_MIN_CONFIDENCE:
            continue
        kept.append(text)
    return " ".join(kept)


def analyze_ocr_text_with_nlp(url: str, ocr_results):
    """把圖片裡的文字送去 NLP 判一次，分數比原本高才更新。

    為什麼是「比較高才更新」
    ────────────────────
    OCR 文字是「額外」的證據，不是「更好」的證據。圖片上的字通常零碎
    （'SATIVA'、'netwt'、'403'），單獨判分數常常偏低。如果無條件覆蓋，
    一個網頁文字判 80 分的站，會因為圖片文字只判 20 分而被拉下來——
    證據變多反而結論變弱，那是錯的。

    只在「圖片文字判得更高」時更新，代表這一頁的毒品跡證主要藏在圖片裡，
    純文字爬蟲看不到——那正是加 OCR 想抓的情況。
    """
    sentence = ocr_texts_to_sentence(ocr_results)
    if len(sentence) < OCR_MIN_TOTAL_CHARS:
        return

    NLP_PREDICT_URL = os.environ["NLP_PREDICT_URL"]
    BACKEND_NLP_REPORT_URL = os.getenv(
        "BACKEND_NLP_REPORT_URL", "http://127.0.0.1:8000/api/nlp/report/")
    INTERNAL_HEADERS = {"X-Internal-Token": os.environ["INTERNAL_API_TOKEN"]}

    try:
        # report=False：不要讓 NLP 自己回寫，否則圖片文字的分數會直接蓋掉
        # 網頁文字的分數，合併規則就沒機會生效了。
        resp = requests.post(
            NLP_PREDICT_URL,
            json={"url": url, "text": sentence[:4000], "report": False},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"[OCR→NLP] {url} 回應 {resp.status_code}，略過")
            return
        result = resp.json()
    except Exception as e:
        print(f"[OCR→NLP] {url} 呼叫 NLP 失敗：{e}")
        return

    ocr_score = int(float(result.get("score", 0)) * 100)

    # 拿現在的分數來比。這裡直接開 session 讀，不繞 HTTP——
    # 只是讀一個欄位，沒必要再多一次自己打自己的請求。
    import database
    db = database.SessionLocal()
    try:
        row = db.query(database.AIAnalysisResult).filter(
            database.AIAnalysisResult.url == url).first()
        current = (row.nlp_score or 0) if row else 0
    finally:
        db.close()

    if ocr_score <= current:
        print(f"[OCR→NLP] {url} 圖片文字 {ocr_score} 分，沒有超過現有的 {current} 分，不更新")
        return

    print(f"[OCR→NLP] {url} 圖片文字 {ocr_score} 分 > 現有 {current} 分，更新")
    try:
        requests.post(
            BACKEND_NLP_REPORT_URL,
            json={
                "url": url,
                "risk_score": ocr_score,
                # 標明來源。之後看報表時要分得出「這個關鍵字是從圖片上讀到的」，
                # 不然承辦人員在網頁原始碼裡怎麼找都找不到那個字。
                "nlp_keywords": [f"[圖片文字] {k}" for k in (result.get("keywords") or [])][:100],
            },
            headers=INTERNAL_HEADERS,
            timeout=10,
        )
    except Exception as e:
        print(f"[OCR→NLP] {url} 回寫失敗：{e}")
