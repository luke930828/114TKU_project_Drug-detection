"""設定面：CORS、安全標頭、錯誤訊息、網路暴露。"""
from pathlib import Path

import pytest
import requests
from conftest import BACKEND, WEB, known_vuln

pytestmark = pytest.mark.security

REPO = Path(__file__).resolve().parents[2]


@known_vuln("SEC-06")
def test_cors_not_wildcard():
    """allow_origins=['*'] 搭配 allow_credentials=True 是無效且不安全的組合。"""
    r = requests.options(
        f"{BACKEND}/api/login/",
        headers={"Origin": "https://evil.example.com",
                 "Access-Control-Request-Method": "POST"},
        timeout=30)
    allowed = r.headers.get("access-control-allow-origin", "")
    assert allowed != "*", "CORS 對所有來源開放"
    assert "evil.example.com" not in allowed, "CORS 回應把任意來源都當成允許"


@known_vuln("SEC-06")
def test_cors_origins_env_is_used():
    """.env.local 設了 CORS_ORIGINS=http://localhost:8080，程式卻沒讀。"""
    src = (REPO / "modules/backend/app/main.py").read_text(encoding="utf-8")
    assert "CORS_ORIGINS" in src, (
        "main.py 沒有讀 CORS_ORIGINS，compose 傳進去的設定完全沒有作用"
    )


@known_vuln("SEC-11")
def test_errors_do_not_leak_internals(anon, unique_url):
    """
    crawler.py:115 把 str(e) 直接放進回應。

    用超長的 task_type 觸發：suspect_websites.title 是 String(100)，
    但由不受限的 task_type 組成，寫入時 MySQL 會丟 DataError，
    回應裡就會出現完整的 SQL 語句與參數。

    （不要用「掃描不存在的主機」來觸發——那條路徑會先被歷史紀錄短路掉，
    測不到真正的錯誤處理。）
    """
    r = anon.post("/api/crawler/report/", auth=False, json={
        "task_type": "X" * 500, "url": unique_url, "text_content": "x",
        "keywords": [], "product_images_b64": []})

    body = r.text.lower()
    leaks = [w for w in ("traceback", "sqlalchemy", "pymysql", "insert into",
                         "[sql:", "[parameters:", "/app/")
             if w in body]
    assert not leaks, (
        f"錯誤回應洩漏內部細節 {leaks}：\n{r.text[:400]}"
    )


@known_vuln("SEC-15")
@pytest.mark.parametrize("header", [
    "content-security-policy",
    "x-content-type-options",
    "x-frame-options",
])
def test_security_headers_present(header):
    r = requests.get(f"{WEB}/", timeout=30)
    assert header in {k.lower() for k in r.headers}, f"缺少安全標頭 {header}"


@known_vuln("SEC-22")
def test_internal_endpoints_not_exposed_through_nginx():
    """
    backend 綁 127.0.0.1:8000 看起來只有本機能連，但 frontend 是 8080:80
    （綁所有介面），nginx 的 /api/ 未經過濾轉給 backend。
    任何連得到 8080 的人都能打到那三個無驗證端點。
    """
    r = requests.post(f"{WEB}/api/nlp/report/",
                      json={"url": "https://via-nginx.invalid/x",
                            "risk_score": 1, "nlp_keywords": []},
                      timeout=30)
    assert r.status_code in (401, 403, 404), (
        f"透過前端的 8080 可以直接寫入內部回報端點（HTTP {r.status_code}）"
    )


@known_vuln("SEC-20")
def test_no_hardcoded_tailnet_ip():
    """make check 就是在抓這個，目前會失敗。"""
    import re
    hits = []
    for p in (REPO / "modules").rglob("*.py"):
        if "node_modules" in str(p):
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if re.search(r"100\.\d+\.\d+\.\d+", line):
                hits.append(f"{p.relative_to(REPO)}:{i}")
    assert not hits, "程式碼裡還有寫死的 tailnet IP 當預設值：\n  " + "\n  ".join(hits)


@known_vuln("SEC-21")
def test_ci_runs_tests():
    """沒有任何 workflow 會跑測試——修好的東西可能默默退回去。"""
    wf = REPO / ".github/workflows"
    files = list(wf.glob("*.yml")) + list(wf.glob("*.yaml")) if wf.exists() else []
    runs_tests = any("pytest" in f.read_text(encoding="utf-8") for f in files)
    assert runs_tests, "CI 沒有任何跑測試的 workflow"
