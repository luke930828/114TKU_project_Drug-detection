import os
import logging
import httpx
import torch
import torch.nn.functional as F
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from typing import List, Optional

# ── 模型設定 ──────────────────────────────────────────────────────────────────
# 微調過的模型放在 Hugging Face Hub，容器啟動時直接下載，不用把 1GB+ 權重包進 image
MODEL_ID = os.getenv("MODEL_ID", "matt0513/drug-detection-xlm-roberta")

# 後端主系統位址（docker-compose 網路裡用 service name，本機測試可覆寫）
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://backend:8000")
BACKEND_NLP_URL = f"{BACKEND_BASE_URL}/api/nlp/report/"

# ── 啟動時只載入一次模型 ─────────────────────────────────────────────────────
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_ID,
    attn_implementation="eager",  # sdpa 不支援 output_attentions，改用 eager
)
model.config.output_attentions = True
model.to(device)
model.eval()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nlp_api")

# ── FastAPI 應用程式 ───────────────────────────────────────────────────────────
app = FastAPI(title="毒品黑話偵測 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# ── 資料格式定義 ───────────────────────────────────────────────────────────────
class PredictRequest(BaseModel):
    url: str            # 被掃描的網址（送給後端用）
    text: str           # 要偵測的文字內容


class PredictResponse(BaseModel):
    label: str          # "DRUG" 或 "SAFE"
    score: float        # 毒品機率，0.0 ~ 1.0
    keywords: List[str] # 觸發判斷的關鍵字


# ── 關鍵字提取（透過 Attention 權重）────────────────────────────────────────────
def extract_keywords(text: str, top_k: int = 5) -> List[str]:
    """用 CLS token 的 Attention 找出模型最依賴的詞"""
    encoding = tokenizer(
        text, return_tensors="pt", truncation=True, padding=True, max_length=256
    )
    input_ids = encoding["input_ids"][0].tolist()
    inputs = {k: v.to(device) for k, v in encoding.items()}

    with torch.no_grad():
        outputs = model(**inputs, output_attentions=True)

    # (layers, 1, heads, seq, seq) → 取 CLS 行，對層數和 head 取平均 → (seq_len,)
    attentions = torch.stack(outputs.attentions)
    cls_attn = attentions[:, 0, :, 0, :].mean(dim=(0, 1)).cpu().tolist()

    special_ids = {0, 1, 2}  # <s>, </s>, <pad>
    scored = []
    for token_id, attn_score in zip(input_ids, cls_attn):
        if token_id in special_ids:
            continue
        token_text = tokenizer.decode([token_id]).strip().lstrip("▁")
        if len(token_text) > 1:
            scored.append((attn_score, token_text))

    scored.sort(reverse=True)
    seen: set = set()
    keywords: List[str] = []
    for _, token in scored:
        if token.lower() not in seen:
            seen.add(token.lower())
            keywords.append(token)
        if len(keywords) >= top_k:
            break

    return keywords


# ── 推送結果給後端主系統 ────────────────────────────────────────────────────────
async def push_to_backend(url: str, risk_score: float, nlp_keywords: List[str]) -> None:
    """
    把 NLP 分析結果 POST 給後端主系統的 /api/nlp/report/。
    失敗只記 log，不影響回傳給呼叫方的結果。
    """
    payload = {
        "url": url,
        "risk_score": round(risk_score * 100),  # 後端要整數 0~100
        "nlp_keywords": nlp_keywords,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(BACKEND_NLP_URL, json=payload)
            resp.raise_for_status()
            logger.info(f"推送成功 {url} → {resp.status_code}")
    except Exception as e:
        # 推送失敗不中斷主流程，只記 log
        logger.warning(f"推送後端失敗 ({url}): {e}")


# ── API 端點 ──────────────────────────────────────────────────────────────────
@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    """
    輸入網址 + 文字，回傳 label/score/keywords，
    並自動把結果推送到後端主系統的 /api/nlp/report/。
    """
    text = req.text.strip()
    if not text:
        return PredictResponse(label="SAFE", score=0.0, keywords=[])

    # 1. 預測
    encoding = tokenizer(
        text, return_tensors="pt", truncation=True, padding=True, max_length=256
    )
    inputs = {k: v.to(device) for k, v in encoding.items()}

    with torch.no_grad():
        outputs = model(**inputs)

    probs = F.softmax(outputs.logits, dim=-1).squeeze().tolist()
    pred_idx = torch.argmax(outputs.logits, dim=-1).item()

    label = "DRUG" if pred_idx == 1 else "SAFE"
    drug_score = round(float(probs[1]), 4) if pred_idx == 1 else 0.0

    # 2. 提取關鍵字（機率 > 0.3 才值得標）
    keywords = extract_keywords(text) if drug_score > 0.3 else []

    # 3. 非同步推送給後端主系統（不阻塞回應）
    await push_to_backend(req.url, drug_score, keywords)

    return PredictResponse(label=label, score=drug_score, keywords=keywords)


@app.get("/health")
def health():
    return {"status": "ok", "device": str(device)}
