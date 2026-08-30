"""授權：誰可以做什麼。"""
import pytest
from conftest import known_vuln

pytestmark = pytest.mark.security

ADMIN_ONLY = [
    ("GET", "/api/users/"),
    ("GET", "/api/users/audit-logs"),
    ("GET", "/api/whitelist/"),
    ("GET", "/api/crawler/report/"),
]


@pytest.mark.parametrize("method,path", ADMIN_ONLY)
def test_normal_user_blocked_from_admin_endpoints(make_user, method, path):
    _, _, api = make_user()
    r = api.request(method, path)
    assert r.status_code == 403, f"一般人員可以存取 {method} {path}"


def test_normal_user_cannot_create_user(make_user):
    _, _, api = make_user()
    r = api.post("/api/users/", json={
        "account": "should_not_exist", "password": "Whatever1!aa",
        "role": "系統管理員", "department": "x"})
    assert r.status_code == 403


def test_normal_user_cannot_modify_whitelist(make_user, unique_url):
    _, _, api = make_user()
    r = api.post("/api/whitelist/", json={
        "url": unique_url, "title": "x", "reason": "x"})
    assert r.status_code == 403


def test_normal_user_cannot_promote_self(make_user, admin):
    account, _, api = make_user()
    uid = {u["account"]: u["id"] for u in admin.get("/api/users/").json()}[account]
    r = api.put(f"/api/users/{uid}/role", json={"role": "系統管理員"})
    assert r.status_code == 403, "一般人員可以把自己升成管理員"


@known_vuln("SEC-12")
def test_export_requires_admin(make_user):
    """
    Excel 匯出只掛 get_current_user，一般人員也能整包帶走全部蒐證資料。
    這是數位證據系統，匯出應該限管理員並留稽核紀錄。
    """
    _, _, api = make_user()
    r = api.get("/api/export/ai_results_excel/")
    assert r.status_code == 403, f"一般人員可以匯出全部資料（HTTP {r.status_code}）"


@known_vuln("SEC-12")
def test_automated_list_requires_admin(make_user):
    _, _, api = make_user()
    r = api.get("/api/crawler/automated_24h_list/")
    assert r.status_code == 403, "一般人員可以讀取完整的可疑網站清單"


@known_vuln("SEC-13")
def test_role_must_be_from_allowed_set(admin, make_user):
    """role 是自由字串，可以寫進任意值。"""
    account, _, _ = make_user()
    uid = {u["account"]: u["id"] for u in admin.get("/api/users/").json()}[account]
    r = admin.put(f"/api/users/{uid}/role", json={"role": "隨便打的字串🙃"})
    assert r.status_code in (400, 422), "role 接受任意字串，沒有白名單"


@known_vuln("SEC-13")
def test_admin_cannot_freeze_self(admin, make_user):
    """
    管理員不該能凍結自己（delete 有防，toggle-status 沒有）。

    ⚠️ 這裡刻意用「另外開的管理員」來做，不能拿預設 admin 試——
    一旦凍結成功，它自己的 token 立刻失效，就再也解不開，整套測試會全部掛掉。
    解凍由沒被凍結的主 admin 出手。
    """
    account, _, second_admin = make_user(role="系統管理員")
    uid = {u["account"]: u["id"] for u in admin.get("/api/users/").json()}[account]

    r = second_admin.put(f"/api/users/{uid}/toggle-status")   # 自己凍結自己
    if r.status_code == 200:
        admin.put(f"/api/users/{uid}/toggle-status")          # 主 admin 解凍
    assert r.status_code in (400, 403), "管理員可以把自己凍結，能鎖死整個系統"
