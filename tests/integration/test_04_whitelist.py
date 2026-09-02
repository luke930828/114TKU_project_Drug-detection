"""白名單：加進去之後，爬蟲端與手動掃描端都要放行。"""
import pytest
from helpers import crawler_report, find_result

pytestmark = pytest.mark.integration


@pytest.fixture
def whitelisted(admin, unique_url):
    r = admin.post("/api/whitelist/", json={
        "url": unique_url, "title": "整合測試白名單", "reason": "測試用"})
    assert r.status_code == 200, r.text[:300]
    yield unique_url
    for w in admin.get("/api/whitelist/").json():
        if w["url"] == unique_url:
            admin.delete(f"/api/whitelist/{w['id']}")


def test_add_and_list(admin, whitelisted):
    urls = [w["url"] for w in admin.get("/api/whitelist/").json()]
    assert whitelisted in urls


def test_crawler_report_skipped_for_whitelisted(internal, admin, whitelisted):
    r = crawler_report(internal, whitelisted)
    assert r.status_code == 200
    assert r.json()["status"] == "skipped", "白名單網址仍然被寫進黑名單流程"
    assert find_result(admin, whitelisted) is None, "白名單網址不該產生 AI 分析結果"


def test_scan_target_returns_safe_for_whitelisted(admin, whitelisted):
    r = admin.post("/api/scan_target/", json={"url": whitelisted})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "safe"
    assert body["source"] == "whitelist"
    assert body["data"]["risk_score"] == 0


def test_duplicate_rejected(admin, whitelisted):
    r = admin.post("/api/whitelist/", json={
        "url": whitelisted, "title": "重複", "reason": "重複"})
    assert r.status_code == 400


def test_delete_removes_it(admin, unique_url):
    admin.post("/api/whitelist/", json={
        "url": unique_url, "title": "待刪除", "reason": "測試"})
    wid = next(w["id"] for w in admin.get("/api/whitelist/").json()
               if w["url"] == unique_url)
    assert admin.delete(f"/api/whitelist/{wid}").status_code == 200
    assert unique_url not in [w["url"] for w in admin.get("/api/whitelist/").json()]


def test_whitelist_matches_whole_domain(internal, admin, unique_url):
    """
    白名單要擋整個網域，不是只擋加進去的那一個網址。

    以前是拿完整網址做等值比對：加了 https://www.momoshop.com.tw/ 之後，
    https://www.momoshop.com.tw/goods/GoodsDetail.jsp?i_code=12345 照樣被分析。
    momo 有幾十萬個商品頁，一頁一頁加是不可能的——白名單形同無效。
    """
    import uuid
    domain = f"wl-{uuid.uuid4().hex[:8]}.invalid"
    r = admin.post("/api/whitelist/", json={
        "url": f"https://www.{domain}/", "title": "測試白名單", "reason": "整合測試"})
    assert r.status_code == 200, f"建立白名單失敗：{r.status_code} {r.text[:150]}"

    try:
        # 加進去的那一個網址
        assert crawler_report(internal, f"https://www.{domain}/").json()["status"] == "skipped"
        # 同網域的子頁面
        assert crawler_report(
            internal, f"https://www.{domain}/goods/detail?id=123").json()["status"] == "skipped", \
            "子頁面沒有被白名單擋掉——白名單只比對完整網址"
        # 沒有 www. 也算同一個站
        assert crawler_report(internal, f"https://{domain}/x").json()["status"] == "skipped"
        # 別的網域不受影響
        assert crawler_report(internal, unique_url).json()["status"] != "skipped"
    finally:
        rows = admin.get("/api/whitelist/").json()
        for row in rows:
            if domain in (row.get("url") or ""):
                admin.delete(f"/api/whitelist/{row['id']}")
