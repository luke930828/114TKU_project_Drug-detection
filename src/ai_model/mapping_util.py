import os
import shutil
from tqdm import tqdm

# --- 1. 路徑設定 (確認妳的照片在 raw 裡) ---
RAW_DATA_PATH = "./data/raw"        
DEST_DATA_PATH = "./data/processed"   

# --- 2. ID 對齊表 (Huangzixuan 的編號 -> 妳的定義) ---
# 邏輯：{ 他原本的ID : 妳要的ID }
ID_MAP = {
    "2": "0",  # 大麻：他的 2 -> 妳的 0
    "1": "1",  # 海洛因：他的 1 -> 妳的 1
    "0": "2"   # 可卡因：他的 0 -> 妳的 2
}

def process_and_move(subset):
    img_src = os.path.join(RAW_DATA_PATH, subset, "images")
    lbl_src = os.path.join(RAW_DATA_PATH, subset, "labels")
    img_dest = os.path.join(DEST_DATA_PATH, subset, "images")
    lbl_dest = os.path.join(DEST_DATA_PATH, subset, "labels")
    
    os.makedirs(img_dest, exist_ok=True)
    os.makedirs(lbl_dest, exist_ok=True)

    print(f"📦 正在整編 {subset} 大軍...")
    if not os.path.exists(lbl_src):
        print(f"⚠️ 找不到 {subset} 的標籤資料夾，跳過。")
        return

    labels = [f for f in os.listdir(lbl_src) if f.endswith(".txt")]
    for label_file in tqdm(labels):
        with open(os.path.join(lbl_src, label_file), "r") as f:
            lines = f.readlines()
        
        new_lines = []
        for line in lines:
            parts = line.split()
            if parts[0] in ID_MAP:
                parts[0] = ID_MAP[parts[0]] # 執行 ID 對齊
                new_lines.append(" ".join(parts) + "\n")
        
        if new_lines: # 只有包含我們要的毒品，才搬家
            with open(os.path.join(lbl_dest, label_file), "w") as f:
                f.writelines(new_lines)
            # 搬移照片 (支援 jpg 或 png)
            img_file = label_file.replace(".txt", ".jpg")
            if not os.path.exists(os.path.join(img_src, img_file)):
                img_file = label_file.replace(".txt", ".png")
                
            if os.path.exists(os.path.join(img_src, img_file)):
                shutil.copy(os.path.join(img_src, img_file), os.path.join(img_dest, img_file))

if __name__ == "__main__":
    for folder in ["train", "valid", "test"]:
        process_and_move(folder)
    print("🚀 全軍整編完成！2690 張圖已依照妳的定義歸位到 data/processed。")