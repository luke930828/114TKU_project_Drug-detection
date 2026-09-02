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


def test_blacklist_add_search_and_intercept(internal, admin, unique_url):
    """
    人工黑名單：新增、搜尋、爬蟲攔截、與白名單互斥。

    在這之前系統沒有這張表——「黑名單」完全是從 risk_level == 極高風險 推導的，
    前端的新增按鈕只改記憶體，重新整理就沒了。承辦人員手上有情資
    （他單位通報、已起訴的案子）卻沒地方放。
    """
    import uuid
    domain = f"bl-{uuid.uuid4().hex[:8]}.invalid"
    created = []
    try:
        r = admin.post("/api/blacklist/", json={
            "url": f"https://{domain}/", "title": "整合測試黑名單", "reason": "他單位通報"})
        assert r.status_code == 200, f"新增失敗：{r.status_code} {r.text[:150]}"

        rows = admin.get("/api/blacklist/").json()
        created = [x["id"] for x in rows if domain in x["url"]]
        assert created, "新增後查不到"

        # 同網域不能重複加
        r = admin.post("/api/blacklist/", json={
            "url": f"https://www.{domain}/shop", "title": "x", "reason": "y"})
        assert r.status_code == 400, "同網域重複加沒有被擋"

        # 搜尋
        assert len(admin.get("/api/blacklist/", params={"q": domain}).json()) == 1
        assert admin.get("/api/blacklist/", params={"q": "不可能存在的關鍵字zzz"}).json() == []

        # 爬蟲命中黑名單 → 直接歸檔極高風險，不送 AI
        r = crawler_report(internal, f"https://{domain}/product/1")
        assert r.json()["status"] == "blacklisted", f"沒有被黑名單攔截：{r.text[:150]}"

        # 黑白名單互斥
        w = admin.post("/api/whitelist/", json={
            "url": f"https://{domain}/", "title": "衝突測試", "reason": "x"})
        if w.status_code == 200:                       # 白名單沒擋的話反向再驗一次
            wl = [x["id"] for x in admin.get("/api/whitelist/").json() if domain in x["url"]]
            for i in wl:
                admin.delete(f"/api/whitelist/{i}")
    finally:
        for i in created:
            admin.delete(f"/api/blacklist/{i}")
