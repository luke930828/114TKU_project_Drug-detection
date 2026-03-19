from ultralytics import YOLO
import os

def run_prediction():
    # 指向妳放在 models 裡的那個「最強大腦」
    model_path = "models/best.pt"
    
    if not os.path.exists(model_path):
        print(f"❌ 找不到模型檔案：{model_path}，請確認 best.pt 有在 models 資料夾裡喔！")
        return

    # 載入練好的模型
    model = YOLO(model_path)

    # 告訴 AI 去哪裡找要測試的照片（用妳 test 資料夾的照片來試）
    source_path = "data/processed/test/images"

    print("🚀 AI 正在辨識照片中...")
    results = model.predict(
        source=source_path,
        conf=0.25,           # 信心值門檻
        save=True,           # 存下畫好框的照片
        project="runs/detect", 
        name="inference_results", 
        exist_ok=True
    )
    print(f"✅ 搞定！快去這裡看畫好框的照片：runs/detect/inference_results")

if __name__ == "__main__":
    run_prediction()