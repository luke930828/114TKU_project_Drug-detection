import re
import json

# 1. 讀取原始的 txt 檔案
with open("raw_log.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

json_data = []
# 正規表達式：抓取時間、分數、網址
pattern = r"\[(.*?)\] Score: (\d+) \| (.*)"

# 2. 逐行轉換
for line in lines:
    match = re.search(pattern, line.strip())
    if match:
        log_time = match.group(1)
        score = int(match.group(2))
        url = match.group(3)
        
        # 組裝成我們的標準 JSON 格式
        json_data.append({
            "url": url,
            "risk_score": score,
            "created_at": log_time,
            "details": {
                "yolo_objects": [],
                "nlp_keywords": []
            }
        })

# 3. 輸出成 JSON 檔案
with open("converted_data.json", "w", encoding="utf-8") as f:
    json.dump(json_data, f, ensure_ascii=False, indent=4)

print(f"🎉 轉換成功！共轉換了 {len(json_data)} 筆資料。")