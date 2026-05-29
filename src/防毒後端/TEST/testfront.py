import httpx

payload = {
  "task_type": "automated_24h",
  "timestamp": "2026-05-23 12:00:00",
  "keywords": ["毒品","交易"],
  "url": "https://example.com/product/123",
  "screenshot_b64": "BASE64_SCREENSHOT_DATA_HERE",
  "product_images_b64": ["BASE64_IMG_1", "BASE64_IMG_2"],
  "text_content": "頁面文字內容..."
}

resp = httpx.post("http://127.0.0.1:8000/api/crawler/report/", json=payload, timeout=15)
print(resp.status_code)
print(resp.json())