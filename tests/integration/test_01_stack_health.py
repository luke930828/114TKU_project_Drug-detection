"""服務都活著，而且彼此連得到。這組壞了，後面全部不用看。"""
import pytest
import requests

pytestmark = pytest.mark.integration

STUBS = {
    "nlp": "http://127.0.0.1:18000",
    "yolo": "http://127.0.0.1:15000",
    "crawler": "http://127.0.0.1:18001",
}


def test_backend_health(anon):
    r = anon.get("/health", auth=False)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_backend_root(anon):
    assert anon.get("/", auth=False).status_code == 200


def test_openapi_available(anon):
    r = anon.get("/openapi.json", auth=False)
    assert r.status_code == 200
    assert "/api/login/" in r.json()["paths"]


@pytest.mark.parametrize("role", list(STUBS))
def test_stub_alive(stack_ready, role):
    r = requests.get(f"{STUBS[role]}/health", timeout=10)
    assert r.status_code == 200
    assert r.json()["role"] == role


def test_no_conflicting_real_engines_running():
    """
    真的 nlp/yolo/crawler 不能跟 stub 同時跑。

    base compose 的服務名是 nlp/yolo/crawler，stub 用的是同名的網路別名——
    兩邊都在的話 Docker DNS 會輪流解析，後端有時打到真引擎、有時打到 stub，
    分數變成不確定的，測試就會時好時壞。這種失敗很難查，所以直接擋在最前面。
    """
    import subprocess
    try:
        names = subprocess.run(["docker", "ps", "--format", "{{.Names}}"],
                               capture_output=True, text=True, timeout=30).stdout.split()
    except (subprocess.SubprocessError, FileNotFoundError):
        pytest.skip("這個環境沒有 docker 指令")

    clashing = [n for n in names
                if any(n.endswith(f"-{svc}-1") for svc in ("nlp", "yolo", "crawler"))]
    assert not clashing, (
        f"真的 AI 服務還跑著，會跟 stub 的網路別名衝突：{clashing}\n"
        f"先跑 make test-up（它會自動收掉），或手動："
        f"docker compose -f deploy/docker-compose.yml --profile full rm -sf nlp yolo crawler"
    )


def test_frontend_serves_spa(web):
    r = web.get("/", auth=False)
    assert r.status_code == 200
    assert "<div id=\"root\"" in r.text or "<html" in r.text.lower()


def test_nginx_proxies_api_to_backend(web):
    """前端的 /api/ 要真的轉到後端——這是整個前後端串接的基礎。"""
    r = web.get("/api/../health", auth=False)
    # nginx 只轉 /api/ 前綴，用一個確實存在的 API 路徑驗證
    r = web.post("/api/login/", auth=False,
                 json={"account": "definitely_not_exist", "password": "x"})
    assert r.status_code == 401, "nginx 沒有把 /api/ 轉給後端"


def test_db_reachable(db):
    with db.cursor() as c:
        c.execute("SELECT 1 AS ok")
        assert c.fetchone()["ok"] == 1


def test_all_tables_created(db):
    """backend 的 Dockerfile CMD 會跑 create_all，五張表都該在。"""
    expected = {"users", "audit_logs", "suspect_websites",
                "whitelist_websites", "ai_analysis_results"}
    with db.cursor() as c:
        c.execute("SHOW TABLES")
        actual = {list(r.values())[0] for r in c.fetchall()}
    assert expected <= actual, f"缺少資料表：{expected - actual}"
