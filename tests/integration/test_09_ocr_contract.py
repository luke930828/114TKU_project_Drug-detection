"""
OCR 的介面契約：YOLO 送出來的形狀，後端存得住、前端讀得到。

為什麼要有這一支
────────────────
OCR 功能是兩個人分頭做的：一個在 modules/yolo 做文字擷取，一個在
backend + frontend 做欄位與顯示。兩邊都寫完、都能跑、都 code review 過，
合起來卻是壞的——

  YOLO 送：  {"engine": "easyocr", "detected_texts": [{"text", "box", ...}]}
  前端讀：   if (!Array.isArray(value)) return [];   // 物件進來 → 直接回空陣列

所以 OCR 區塊從來沒有顯示過，而且失敗方式是「安靜地不顯示」，看起來就像
OCR 沒抓到東西，不會有任何錯誤訊息。單獨測任一邊都是綠的，只有把兩邊接起來
才看得出問題——這正是整合測試存在的理由。

這支測試釘住的是「形狀」本身，不是分數或內容。哪天有人改了其中一邊的欄位名，
這裡會紅，而不是等到展示的時候才發現畫面上空空如也。
"""
import pytest
from helpers import crawler_report, wait_for

pytestmark = pytest.mark.integration

# 跟 modules/yolo/app/main.py 送出的 payload 完全一致的形狀。
# 改這裡之前先確認那邊也改了，兩邊要一起動。
YOLO_OCR_PAYLOAD = {
    "engine": "easyocr",
    "detected_texts": [
        {"text": "藍色小藥丸 100mg", "confidence": 0.9123,
         "box_format": "xyxyn", "box": [0.1, 0.2, 0.5, 0.3], "image_index": 0},
        {"text": "SHIPPING WORLDWIDE", "confidence": 0.7788,
         "box_format": "xyxyn", "box": [0.2, 0.6, 0.9, 0.7], "image_index": 3},
    ],
}


def _yolo_report(url, ocr):
    return {
        "url": url,
        "risk_score": 62,
        "yolo_objects": ["pill"],
        "is_valid_drug": True,
        "class_metadata": {"pill": {"count": 2}},
        "representative_image_base64": None,
        "representative_image_detections": [],
        "ocr_results": ocr,
    }


def _row_from_24h_list(admin, url):
    """從前端 AIDetection 實際會打的那支端點撈回來。

    刻意不查資料庫：這裡要驗的是「前端拿得到什麼」，不是「資料庫存了什麼」。
    """
    r = admin.get("/api/crawler/automated_24h_list/?limit=200")
    if r.status_code != 200:
        return None
    for row in r.json().get("data", []):
        # 這支端點的網址欄位叫 domain_name（不是 url，也不是 websiteUrl）。
        # 前端 AIDetection 的 normalizeResult 讀的就是這個。
        if row.get("domain_name") == url:
            return row
    return None


def test_yolo_ocr_payload_accepted(internal, unique_url):
    """YOLO 送出的形狀，後端要收得下。"""
    r = internal.post("/api/ai_result/report/",
                      json=_yolo_report(unique_url, YOLO_OCR_PAYLOAD))
    assert r.status_code == 200, r.text[:300]


def test_ocr_survives_round_trip(internal, admin, unique_url):
    """存進去再讀出來，結構與內容都不能走樣。"""
    crawler_report(internal, unique_url)
    internal.post("/api/ai_result/report/",
                  json=_yolo_report(unique_url, YOLO_OCR_PAYLOAD))

    row = wait_for(lambda: _row_from_24h_list(admin, unique_url),
                   what=f"{unique_url} 出現在 24h 清單")

    ocr = row.get("ocr_results")
    assert ocr is not None, (
        "清單裡沒有 ocr_results——前端讀不到，OCR 區塊就不會出現。"
        f"實際欄位：{sorted(row.keys())}")
    assert isinstance(ocr, dict), f"應該是物件，實際是 {type(ocr).__name__}"
    assert ocr.get("engine") == "easyocr"

    texts = ocr.get("detected_texts")
    assert isinstance(texts, list) and len(texts) == 2, f"實際：{texts}"
    assert any("藍色小藥丸" in t["text"] for t in texts), "中文走樣了"
    # image_index 是「這段文字來自第幾張圖」，沒有的話前端只看得到一堆
    # 文字、不知道從哪張來。
    assert sorted(t.get("image_index") for t in texts) == [0, 3]
    # 欄位名是 box 不是 bbox，格式跟 YOLO 偵測框一致，前端才能共用畫框邏輯。
    assert all(t.get("box_format") == "xyxyn" for t in texts)
    assert all(len(t.get("box")) == 4 for t in texts)


def test_ocr_results_as_bare_list_is_rejected(internal, unique_url):
    """舊的錯誤形狀（直接送陣列）要被擋下來，不是靜靜地寫進去。

    ocr_results 一度是 Optional[Any]，什麼都收。那代表兩邊格式對不上時
    後端不會有任何反應，錯誤要一路傳到畫面上才會被發現。
    """
    r = internal.post("/api/ai_result/report/",
                      json=_yolo_report(unique_url, [{"text": "abc"}]))
    assert r.status_code == 422, f"應該被 schema 擋下，實際 {r.status_code}"


@pytest.mark.security
def test_ocr_text_length_is_bounded(internal, unique_url):
    """單段文字的長度要有上限（SEC-16 的同一類問題）。"""
    r = internal.post("/api/ai_result/report/", json=_yolo_report(
        unique_url, {"engine": "easyocr",
                     "detected_texts": [{"text": "A" * 600, "confidence": 0.5}]}))
    assert r.status_code == 422, f"600 字應該被擋，實際 {r.status_code}"


@pytest.mark.security
def test_ocr_text_count_is_bounded(internal, unique_url):
    """文字段數也要有上限，否則一個請求就能塞爆 JSON 欄位。"""
    r = internal.post("/api/ai_result/report/", json=_yolo_report(
        unique_url, {"engine": "easyocr",
                     "detected_texts": [{"text": "A", "confidence": 0.5}] * 2001}))
    assert r.status_code == 422, f"2001 段應該被擋，實際 {r.status_code}"


@pytest.mark.security
def test_ocr_report_still_needs_internal_token(anon, unique_url):
    """帶 OCR 的回報一樣不能繞過 SEC-01 的驗證。

    feature/v2-scoring 的 YOLO 曾經把 X-Internal-Token 整段拿掉，
    這支測試釘住那個回歸。
    """
    r = anon.post("/api/ai_result/report/",
                  json=_yolo_report(unique_url, YOLO_OCR_PAYLOAD))
    assert r.status_code in (401, 403), f"未驗證即可回報，實際 {r.status_code}"
