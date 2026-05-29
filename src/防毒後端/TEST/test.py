import httpx

resp = httpx.post("http://100.69.185.94:8000/predict", json={
    "url": "https://example-hivbiyl-drug-site99.com/item/123",
    "text": "Buy cannabis online THC 94%"
})
print(resp.json())
