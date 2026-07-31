from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class PredictRequest(BaseModel):
    url: str
    text: str


@app.post("/predict")
def predict(req: PredictRequest):
    # 回傳一個範例結果，方便本機測試 i.py
    return {
        "label": "SAFE",
        "score": 0.95,
        "keywords": ["測試", "範例"],
        "url": req.url,
    }
