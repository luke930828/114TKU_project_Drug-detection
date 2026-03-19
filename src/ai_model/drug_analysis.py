import os
from ultralytics import YOLO
import torch

# 1. 初始化：喚醒 3050 Ti 與 AI 大腦
model = YOLO("yolo11n.pt") 
device = "0" if torch.cuda.is_available() else "cpu"
input_path = "./test_images"  # 告訴 AI 去哪裡找那 10 張圖

print(f"🚀 系統啟動：正在使用 {torch.cuda.get_device_name(0)} 進行硬體加速...")

# 2. 批量推理 (Batch Inference)
# stream=True 可以節省記憶體，這對處理大量照片很有幫助
results = model.predict(source=input_path, device=device, save=True, conf=0.25)

print("\n" + "="*50)
print(f"{'檔案名稱':<20} | {'辨識標籤':<15} | {'信心度':<10}")
print("-"*50)

# 3. 讀取結果並顯示 (這就是妳要內化的邏輯)
for result in results:
    # 取得原始檔名
    img_name = os.path.basename(result.path)
    
    # 如果 AI 什麼都沒抓到
    if len(result.boxes) == 0:
        print(f"{img_name:<20} | {'(未偵測到目標)':<15} | {'N/A'}")
    
    # 如果有抓到東西，逐一印出
    for box in result.boxes:
        label_index = int(box.cls[0])      # 標籤編號
        label_name = model.names[label_index] # 轉換成人類看得懂的文字 (如: bottle)
        confidence = box.conf[0].item()    # 信心度 (0~1)
        
        print(f"{img_name:<20} | {label_name:<15} | {confidence:.2%}")

print("="*50)
print(f"✅ 分析完成！辨識後的照片已存入: {results[0].save_dir}")