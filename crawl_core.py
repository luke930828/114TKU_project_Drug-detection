"""手動 / 24H 共用：Context、彈窗、滾動、商品圖擷取。"""
import asyncio
import base64
import hashlib
import logging
import os
import random
import re
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from dedup_store import DedupStore


HARVEST_CONTEXT_OPTS: Dict[str, Any] = {
    "viewport": {"width": 1280, "height": 720},
    "user_agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "ignore_https_errors": True,
}


async def safe_page_text(page) -> str:
    """安全取得 body 文字；body 為 null 或 evaluate 失敗時回傳空字串。"""
    try:
        return (
            await page.evaluate(
                "() => (document.body && document.body.innerText) ? document.body.innerText : ''"
            )
            or ""
        )
    except Exception:
        return ""


def build_context_options(config: Dict[str, Any], viewport: Tuple[int, int] = (1280, 720)) -> Dict[str, Any]:
    locations = config.get("locations", [])
    if locations:
        loc = random.choice(locations)
        geo = {"latitude": loc["latitude"], "longitude": loc["longitude"], "accuracy": 100}
        timezone_id = loc.get("timezone", "America/New_York")
        locale = loc.get("locale", "en-US")
    else:
        geo = config.get("geolocation", {"latitude": 37.7749, "longitude": -122.4194, "accuracy": 100})
        timezone_id = config.get("timezone", "America/Los_Angeles")
        locale = config.get("locale", "en-US")

    opts: Dict[str, Any] = {
        "ignore_https_errors": True,
        "viewport": {"width": viewport[0], "height": viewport[1]},
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "geolocation": geo,
        "permissions": ["geolocation"],
        "timezone_id": timezone_id,
        "locale": locale,
    }
    proxy_pool = config.get("proxy_pool", [])
    single_proxy = config.get("proxy")
    p = random.choice(proxy_pool) if proxy_pool else single_proxy or None
    if p:
        opts["proxy"] = {"server": p} if isinstance(p, str) else p
    return opts


async def setup_resource_routes(page, block_fonts: bool = False, lightweight: bool = False) -> None:
    blocked = ["mp4", "mov", "avi", "webm"]
    if block_fonts or lightweight:
        blocked.extend(["woff", "woff2", "ttf", "otf", "eot"])
    if lightweight:
        blocked.extend(["png", "jpg", "jpeg", "gif", "svg", "ico", "webp", "css"])
    pattern = "**/*.{" + ",".join(sorted(set(blocked))) + "}"
    await page.route(pattern, lambda route: route.abort())


# 年齡閘優先點這些（不要放 No，以免拒絕進入）
AGE_GATE_CLICK_LABELS = (
    "Yes",
    "YES",
    "I am 21",
    "I am 18",
    "I'm 21",
    "I'm 18",
    "I am 21+",
    "I am over 21",
    "I am over 18",
    "21+",
    "18+",
    "Enter Site",
    "Enter",
    "Confirm Age",
    "Verify Age",
    "I Agree",
    "Agree & Enter",
    "是",
    "我已滿21歲",
    "我已滿18歲",
    "已滿21歲",
    "已滿18歲",
    "進入網站",
    "進入",
)


async def _click_first_visible_label(page, labels, *, timeout_ms: int = 1200) -> bool:
    """依序嘗試點可見按鈕／連結；成功點到一個就回 True。"""
    for kw in labels:
        try:
            selector = (
                f"button:has-text('{kw}'), a:has-text('{kw}'), "
                f"[role='button']:has-text('{kw}'), input[type='button'][value*='{kw}' i], "
                f"input[type='submit'][value*='{kw}' i]"
            )
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=timeout_ms):
                await btn.click(timeout=2500)
                await asyncio.sleep(0.4)
                return True
        except Exception:
            continue
    return False


async def dismiss_overlays(page, light: bool = False) -> bool:
    """處理彈窗；回傳是否疑似登入牆（供 early_exit 使用）。"""
    is_login_required = False

    # 1) 先處理年齡閘（Yes / 21+ / 18+），light／完整模式都做
    age_timeout = 900 if light else 1500
    await _click_first_visible_label(page, AGE_GATE_CLICK_LABELS, timeout_ms=age_timeout)

    dismiss_keywords = (
        ["Accept", "Agree", "OK", "同意", "接受"]
        if light
        else [
            "Accept All", "Accept all cookies", "Accept Cookies",
            "Allow All", "I Accept", "I Agree", "Agree & Proceed",
            "Got it", "OK", "Okay", "Close",
            "I am 21", "I am 18", "Enter Site", "Confirm Age", "Yes",
            "No thanks", "Skip", "Dismiss", "Not now", "Continue",
            "Accept", "Agree", "同意", "接受", "Allow all",
        ]
    )

    for kw in dismiss_keywords:
        try:
            selector = f"button:has-text('{kw}'), a:has-text('{kw}'), [role='button']:has-text('{kw}')"
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=1200 if light else 1500):
                await btn.click()
                await asyncio.sleep(0.5 if light else 1)
                break
        except Exception:
            continue

    if not light:
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
        except Exception:
            pass

    try:
        await page.evaluate(
            """
            () => {
                const selectors = [
                    '[class*="cookie"]', '[class*="consent"]', '[class*="gdpr"]',
                    '[class*="overlay"]', '[class*="modal"]', '[class*="popup"]',
                    '[class*="banner"]',
                    '#onetrust-banner-sdk', '#cookiebanner', '.fc-dialog-container'
                ];
                selectors.forEach(sel =>
                    document.querySelectorAll(sel).forEach(el => el.remove())
                );
                document.body.style.overflow = 'auto';
                document.documentElement.style.overflow = 'auto';
            }
            """
        )
    except Exception:
        pass

    try:
        page_text_lower = (await safe_page_text(page)).lower()
        page_len = len(page_text_lower)
        has_password_field = await page.query_selector('input[type="password"]')
        login_kw = ("log in", "login", "sign in", "登入", "會員登入", "please log in")
        has_login_text = any(k in page_text_lower[:800] for k in login_kw)
        # 弱提示：頁面極短 + 密碼框 + 登入文案（避免電商頁側欄 login 誤判）
        if has_password_field and page_len < 800 and has_login_text:
            is_login_required = True
    except Exception:
        pass

    return is_login_required


async def simulate_human(page, mode: str = "light") -> None:
    try:
        if mode == "light":
            await page.evaluate("window.scrollBy(0, 400)")
            await asyncio.sleep(0.3)
            return
        if mode == "deep":
            for _ in range(4):
                x, y = random.randint(100, 1000), random.randint(100, 800)
                await page.mouse.move(x, y, steps=15)
                await asyncio.sleep(random.uniform(0.2, 0.4))
            scroll_js = """async () => {
                await new Promise((resolve) => {
                    let total = 0, dist = 250;
                    let t = setInterval(() => {
                        window.scrollBy(0, dist); total += dist;
                        if (total >= document.body.scrollHeight) { clearInterval(t); resolve(); }
                    }, 300);
                });
            }"""
            await page.evaluate(scroll_js)
            await asyncio.sleep(2)
        else:
            for _ in range(3):
                x, y = random.randint(100, 800), random.randint(100, 600)
                await page.mouse.move(x, y, steps=10)
                await asyncio.sleep(random.uniform(0.1, 0.3))
            await page.evaluate("""async () => {
                await new Promise((resolve) => {
                    let total = 0, dist = 400;
                    let t = setInterval(() => {
                        window.scrollBy(0, dist); total += dist;
                        if (total >= document.body.scrollHeight) { clearInterval(t); resolve(); }
                    }, 200);
                });
            }""")
            await asyncio.sleep(2)
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(0.5)
    except Exception as e:
        logging.debug(f"[crawl_core] simulate_human: {e}")


async def _download_image(
    page,
    src: str,
    index: int,
    timeout_ms: int,
    save_local: bool,
    save_dir: Optional[str],
    filename_prefix: str,
) -> Optional[Dict[str, str]]:
    try:
        response = await page.request.get(src, timeout=timeout_ms)
        if not response.ok:
            return None
        img_binary = await response.body()
        if len(img_binary) < 5000:
            return None
        content_type = response.headers.get("content-type", "")
        ext = "png" if "png" in content_type else "webp" if "webp" in content_type else "jpg"
        filename = f"{filename_prefix}_{index + 1:02d}.{ext}"
        if save_local and save_dir:
            os.makedirs(save_dir, exist_ok=True)
            with open(os.path.join(save_dir, filename), "wb") as f:
                f.write(img_binary)
        return {
            "filename": filename,
            "base64_data": base64.b64encode(img_binary).decode("utf-8"),
            "_hash": hashlib.md5(img_binary).hexdigest(),
            "_binary_len": len(img_binary),
        }
    except Exception:
        return None


async def extract_product_images(
    page,
    config: Dict[str, Any],
    *,
    domain: str = "unknown",
    dedup: Optional[DedupStore] = None,
    max_images: int = 12,
    min_size: int = 100,
    lazy_load_scroll: bool = True,
    image_timeout_ms: int = 8000,
    parallel_downloads: int = 1,
    save_local: bool = False,
    save_dir: Optional[str] = None,
    classify_dir: Optional[str] = None,
    scroll_timeout_ms: int = 8000,
    max_scroll_steps: int = 25,
) -> List[Dict[str, str]]:
    """統一商品圖擷取（lazy-load + 關鍵字排序 + 可選 SQLite 去重）。"""
    try:
        if lazy_load_scroll:
            # 新聞站等動態長高頁面，舊邏輯會無限滾；限制步數 + 高度連續不變 + 總逾時
            try:
                await asyncio.wait_for(
                    page.evaluate(
                        f"""
                        async () => {{
                            const distance = 400;
                            const maxSteps = {int(max_scroll_steps)};
                            let lastHeight = 0;
                            let stable = 0;
                            for (let i = 0; i < maxSteps; i++) {{
                                window.scrollBy(0, distance);
                                await new Promise(r => setTimeout(r, 120));
                                const h = document.body ? document.body.scrollHeight : 0;
                                if (h <= lastHeight) {{
                                    stable += 1;
                                    if (stable >= 3) break;
                                }} else {{
                                    stable = 0;
                                    lastHeight = h;
                                }}
                            }}
                            window.scrollTo(0, 0);
                        }}
                        """
                    ),
                    timeout=max(1.0, scroll_timeout_ms / 1000.0),
                )
            except asyncio.TimeoutError:
                logging.warning(f"[crawl_core] lazy-load 滾動逾時，略過繼續抓圖 | domain={domain}")
                try:
                    await page.evaluate("window.scrollTo(0, 0)")
                except Exception:
                    pass
            except Exception as e:
                logging.debug(f"[crawl_core] lazy-load 滾動失敗: {e}")
            await page.wait_for_timeout(400 if min_size >= 200 else 800)

        raw_img_data = await page.evaluate(
            f"""
            () => Array.from(document.querySelectorAll('img')).map(img => {{
                const lazySrc = img.getAttribute('data-src')
                    || img.getAttribute('data-lazy-src')
                    || img.getAttribute('data-original')
                    || img.getAttribute('data-lazy') || '';
                const finalSrc = (img.naturalWidth >= {min_size} && img.src.startsWith('http'))
                    ? img.src
                    : (lazySrc.startsWith('http') ? lazySrc : img.src);
                let contextText = '';
                if (img.parentElement) contextText = img.parentElement.innerText || '';
                return {{
                    src: finalSrc,
                    naturalWidth: img.naturalWidth,
                    alt: (img.alt || img.title || '').toLowerCase(),
                    context: contextText.toLowerCase().substring(0, 200)
                }};
            }}).filter(item => item.src && item.src.startsWith('http')
                && (item.naturalWidth >= {min_size} || item.naturalWidth === 0))
            """
        )
        if not raw_img_data:
            return []

        keywords = config.get("keyword_groups", {}).get("A_Product", [])
        seen_src: set = set()
        img_list = []
        for item in raw_img_data:
            if item["src"] in seen_src:
                continue
            seen_src.add(item["src"])
            search_text = f"{item['alt']} {item['src']} {item.get('context', '')}".lower()
            item["has_keyword"] = any(kw.lower() in search_text for kw in keywords)
            img_list.append(item)

        img_list.sort(key=lambda x: x["has_keyword"], reverse=True)
        img_list = img_list[:max_images]

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = f"{domain}_{timestamp_str}"
        sem = asyncio.Semaphore(max(1, parallel_downloads))

        async def _one(i: int, data: dict) -> Optional[Dict[str, str]]:
            async with sem:
                return await _download_image(
                    page, data["src"], i, image_timeout_ms,
                    save_local, save_dir, prefix,
                )

        results = await asyncio.gather(
            *[_one(i, d) for i, d in enumerate(img_list)],
            return_exceptions=True,
        )

        b64_results: List[Dict[str, str]] = []
        for i, r in enumerate(results):
            if not isinstance(r, dict):
                continue
            img_hash = r.pop("_hash", None)
            r.pop("_binary_len", None)
            if dedup and img_hash and dedup.has_image_hash(img_hash):
                continue
            if dedup and img_hash:
                dedup.add_image_hash(img_hash)

            if classify_dir and save_local:
                label = "Unknown"
                data = img_list[i]
                search_text = f"{data['alt']} {data['src']} {data.get('context', '')}".lower()
                for kw in keywords:
                    if kw.lower() in search_text:
                        label = kw
                        break
                safe_label = re.sub(r"[^\w\-]", "_", label)
                class_dir = os.path.join(classify_dir, f"class_{safe_label}")
                os.makedirs(class_dir, exist_ok=True)
                src_path = os.path.join(save_dir or "", r["filename"])
                if save_dir and os.path.isfile(src_path):
                    shutil.copy2(src_path, os.path.join(class_dir, r["filename"]))

            b64_results.append({"filename": r["filename"], "base64_data": r["base64_data"]})

        return b64_results
    except Exception as e:
        logging.warning(f"[crawl_core] extract_product_images 失敗: {e!r}")
        return []


def resolve_engine_crawl_opts(config: Dict[str, Any]) -> Dict[str, Any]:
    """24H 引擎爬取 profile：fast / full 皆完整採集，差在 timeout/滾動深度（非 lightweight）。"""
    raw = config.get("engine_24h") or {}
    profile_key = "fast" if (raw.get("crawl_profile") or "fast") == "fast" else "full"
    shared_max_images = int(raw.get("max_product_images", 10))
    defaults = {
        "fast": {
            "lightweight": False,
            "goto_timeout_ms": 25000,
            "post_goto_sleep_ms": 1200,
            "max_product_images": shared_max_images,
            "min_image_size": 100,
            "parallel_image_downloads": 2,
            "image_download_timeout_ms": 6000,
            "human_mode": "light",
            "block_fonts": True,
            "skip_auth_scan": False,
        },
        "full": {
            "lightweight": False,
            "goto_timeout_ms": 60000,
            "post_goto_sleep_ms": 2500,
            "max_product_images": shared_max_images,
            "min_image_size": 100,
            "parallel_image_downloads": 1,
            "image_download_timeout_ms": 8000,
            "human_mode": "full",
            "block_fonts": False,
            "skip_auth_scan": False,
        },
    }
    merged = {**defaults[profile_key], **(raw.get(profile_key) or {})}
    merged["profile"] = profile_key
    return merged
