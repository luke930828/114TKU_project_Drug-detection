from ultralytics import YOLO
import torch

def train_model():
    # 1. 載入妳放在 models 裡的基礎模型
    # 如果裡面還沒有 yolo11n.pt，它會自動幫妳從雲端下載最新版
    model = YOLO("models/yolo11n.pt") 

    # 2. 檢查 GPU 是否就緒 (妳的 3050 就在這裡發威)
    device = 0 if torch.cuda.is_available() else "cpu"
    print(f"🚀 偵測到硬體：{'NVIDIA GPU (3050)' if device == 0 else 'CPU (這會練很久喔)'}")

    # 3. 開始訓練
    model.train(
        data="data/processed/data.yaml", # 剛才辛苦修好的菜單
        epochs=50,                      # 跑 50 個循環，對 3050 來說剛剛好
        imgsz=640,                     # 照片縮放大小
        batch=16,                      # 每次餵 16 張圖給 GPU，如果記憶體爆了就改成 8
        device=device,                 # 使用 GPU 
        project="runs/detect",         # 訓練結果存放在這裡
        name="drug_prevention_v1",     # 這次實驗的名字
        exist_ok=True                  # 如果名字重複就直接覆蓋
    )

if __name__ == "__main__":
    train_model()