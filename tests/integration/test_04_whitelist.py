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
