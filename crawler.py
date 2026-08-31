"""
爬蟲核心：HeuristicAnalyzer（手動 + 24H 評分）、AntiDetectionCrawler（24H 引擎，對齊 monitor_engine_v2 最初版）。
"""
import asyncio
import base64
import hashlib
import json
import logging
import os
import random
import re
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

# Investigator / Harvester 分開限流，避免搜尋把進站全卡死
INVESTIGATE_SEMAPHORE: Optional[asyncio.Semaphore] = None
HARVEST_SEMAPHORE: Optional[asyncio.Semaphore] = None
INVESTIGATE_SEM_LIMIT: int = 8
HARVEST_SEM_LIMIT: int = 2
MAX_WORKERS_BUDGET: int = 8

_HARD_NAV_ERRORS = (
    "ERR_ABORTED",
    "ERR_NAME_NOT_RESOLVED",
    "ERR_SSL",
    "ERR_CONNECTION_REF",
    "ERR_INVALID_URL",
    "Download is starting",
)

# 相容舊呼叫
GLOBAL_CONTEXT_SEMAPHORE: Optional[asyncio.Semaphore] = None
GLOBAL_SEM_LIMIT: int = 12


class HeuristicAnalyzer:
    def __init__(self, config):
        self.config = config or {}
        self.weights = self.config.get("scoring_weights", {
            "core_keywords": 60,
            "supporting_keywords": 40,
            "blacklist_penalty": -500,
            "min_total_score": 75
        })
        self.keyword_groups = self.config.get("keyword_groups", {})
        self.entity_regex = {
            "Telegram": r"(?:t\.me/|@|telegram\.me/)([a-zA-Z0-9_]{5,32})",
            "BTC": r"[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[ac-hj-np-z02-9]{11,71}",
            "XMR": r"4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}",
            "USDT_TRC20": r"T[A-Za-z1-9]{33}",
        }
        self.synonyms = self.config.get("keyword_synonyms") or {}
        self.price_patterns = [
            r"\$\s?\d{1,4}(?:\.\d{2})?",
            r"\d{1,4}\s?(?:usd|usdt|eur|gbp)\b",
            r"\d+\s?(?:g|gram|grams|mg|oz)\b",
        ]

    def _expand_text(self, text: str) -> str:
        expanded = text.lower()
        for base, alts in self.synonyms.items():
            if base.lower() in expanded:
                expanded += " " + " ".join(a.lower() for a in alts)
        return expanded

    def analyze(self, text: str, html: str, url: str) -> Dict:
        score = 0
        matched_keywords = []
        text_lower = self._expand_text(text)
        html_lower = html.lower()

        for kw in self.keyword_groups.get("A_Product", []):
            if kw.lower() in text_lower:
                score += self.weights["core_keywords"]
                matched_keywords.append(kw)

        for kw in self.keyword_groups.get("C_Payment_Contact", []):
            if kw.lower() in text_lower:
                score += self.weights["supporting_keywords"]
                matched_keywords.append(kw)

        for kw in self.keyword_groups.get("X_Content_Blacklist", []):
            if kw.lower() in text_lower:
                score += self.weights["blacklist_penalty"]

        # 商店動作：很多站不用「Add to cart」字樣，過窄會導致「進得去卻永遠抓不到」
        has_cart = any(c in text_lower for c in (
            "add to cart", "add to bag", "add-to-cart", "add to basket",
            "proceed to checkout", "checkout", "shopping cart",
            "buy now", "order now", "shop now", "purchase now",
        ))
        has_crypto = any(c in text_lower for c in (
            "monero", "bitcoin", "btc", "cryptocurrency", "xmr", "usdt", "crypto",
        ))
        has_private_contact = any(p in text_lower for p in (
            "telegram link", "signal me", "@plug", "wickr me", "join our channel",
            "t.me/", "telegram.me/",
        ))
        a_set = {k.lower() for k in self.keyword_groups.get("A_Product", [])}
        has_product_hit = any(m.lower() in a_set for m in matched_keywords)

        if has_cart and has_crypto:
            score = max(score, 100)
        elif (has_crypto or has_private_contact) and score >= 60:
            score = max(score, 80)
        elif has_cart and has_product_hit and score >= 60:
            score = max(score, 80)

        # 無商店動作／私聯 → 不當成目標店（新聞／百科）
        if not has_cart and not has_private_contact:
            score = 0

        if 'itemtype="http://schema.org/product"' in html_lower or '"@type":"product"' in html_lower:
            score += 25
            matched_keywords.append("schema.org/Product")

        for pat in self.price_patterns:
            if re.search(pat, text_lower, re.IGNORECASE):
                score += 15
                matched_keywords.append("price_pattern")
                break

        fingerprints = []
        wp_plugins = re.findall(r"/wp-content/plugins/([a-zA-Z0-9\-_]+)/", html_lower)
        fingerprints.extend([f"/wp-content/plugins/{p}/" for p in set(wp_plugins)])
        if "woo-crypto" in html_lower:
            fingerprints.append("woo-crypto-gateway")

        entities = {}
        for name, pattern in self.entity_regex.items():
            found = re.findall(pattern, text, re.IGNORECASE)
            if found:
                entities[name] = list(set(found))

        min_score = self.weights.get("min_total_score", 75)
        tier = "SKIP"
        if score >= 150:
            tier = "HIGH"
        elif score >= 100:
            tier = "MEDIUM"
        elif score >= min_score:
            tier = "NORMAL"

        return {
            "url": url, "score": score, "tier": tier,
            "matched": list(set(matched_keywords)),
            "fingerprints": fingerprints,
            "entities": entities
        }


def configure_global_sem(config: Dict) -> asyncio.Semaphore:
    """Investigator 專用 semaphore；Harvester 另開，互不搶。"""
    global INVESTIGATE_SEMAPHORE, HARVEST_SEMAPHORE
    global INVESTIGATE_SEM_LIMIT, HARVEST_SEM_LIMIT, MAX_WORKERS_BUDGET
    global GLOBAL_CONTEXT_SEMAPHORE, GLOBAL_SEM_LIMIT

    workers = int(config.get("max_workers", 8))
    contexts = int(config.get("max_browser_contexts", 20))
    harvest_n = int((config.get("engine_24h") or {}).get("max_harvest_parallel", 2))

    MAX_WORKERS_BUDGET = workers
    INVESTIGATE_SEM_LIMIT = max(workers, min(contexts, workers + 2))
    HARVEST_SEM_LIMIT = max(1, min(harvest_n, 4))
    INVESTIGATE_SEMAPHORE = asyncio.Semaphore(INVESTIGATE_SEM_LIMIT)
    HARVEST_SEMAPHORE = asyncio.Semaphore(HARVEST_SEM_LIMIT)
    # 舊名相容
    GLOBAL_SEM_LIMIT = INVESTIGATE_SEM_LIMIT
    GLOBAL_CONTEXT_SEMAPHORE = INVESTIGATE_SEMAPHORE
    logging.info(
        f"[SEM] investigate={INVESTIGATE_SEM_LIMIT} harvest={HARVEST_SEM_LIMIT} "
        f"(workers={workers})"
    )
    return INVESTIGATE_SEMAPHORE


def get_global_sem() -> asyncio.Semaphore:
    global INVESTIGATE_SEMAPHORE, GLOBAL_CONTEXT_SEMAPHORE
    if INVESTIGATE_SEMAPHORE is None:
        INVESTIGATE_SEMAPHORE = asyncio.Semaphore(INVESTIGATE_SEM_LIMIT)
        GLOBAL_CONTEXT_SEMAPHORE = INVESTIGATE_SEMAPHORE
    return INVESTIGATE_SEMAPHORE


def get_harvest_sem() -> asyncio.Semaphore:
    global HARVEST_SEMAPHORE
    if HARVEST_SEMAPHORE is None:
        HARVEST_SEMAPHORE = asyncio.Semaphore(HARVEST_SEM_LIMIT)
    return HARVEST_SEMAPHORE


def _build_context_options(config: Dict, viewport: Tuple[int, int] = (1280, 720)) -> Dict:
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

    opts: Dict = {
        "ignore_https_errors": True,
        "viewport": {"width": viewport[0], "height": viewport[1]},
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "geolocation": geo,
        "permissions": ["geolocation"],
        "timezone_id": timezone_id,
        "locale": locale,
    }
    return opts


async def _safe_page_text(page) -> str:
    try:
        return await page.evaluate(
            "() => (document.body && document.body.innerText) ? document.body.innerText : ''"
        )
    except Exception:
        return ""


async def _simulate_human_light(page) -> None:
    """輕量互動：完整滾到頁底在慢站上會拖死 worker。"""
    try:
        await page.mouse.move(random.randint(120, 700), random.randint(120, 500), steps=8)
        await page.evaluate("window.scrollBy(0, Math.min(1200, document.body.scrollHeight || 800))")
        await asyncio.sleep(random.uniform(0.6, 1.2))
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(0.3)
    except Exception:
        pass


class AntiDetectionCrawler:
    """24H V46 — Investigating (Full) / [HARVESTER] / [POPUP]（對齊 monitor_engine_v2 最初版）。"""

    def __init__(self, headless=True, config=None):
        self.headless = headless
        self.config = config or {}
        self.analyzer = HeuristicAnalyzer(self.config)
        self.blacklist = self.config.get("keyword_groups", {}).get("X_Domain_Blacklist", [])

        output_dirs = self.config.get("output_dirs", {})
        # 24H 不再落地 testjpg / testHTML；圖與 HTML 只留記憶體給 Webhook，紀錄走 Record/
        self.jpg_dir = output_dirs.get("test_jpg", "testjpg")
        self.html_dir = output_dirs.get("test_html", "testHTML")
        self.record_dir = "Record"
        self.save_local_files = False

        os.makedirs(self.record_dir, exist_ok=True)

        configure_global_sem(self.config)

        # dedup 只留記憶體，不再另寫 Record/dedup_*.json（Record 只保留 2 個 json）
        self.seen_urls_path = ""
        self.seen_hashes_path = ""
        self.seen_urls: Set[str] = set()
        self.seen_hashes: Set[str] = set()

        self.manifest_path = ""

        self._pw_instance = None
        self._browser = None          # Investigator（8 worker）
        self._browser_search = None   # Harvester（獨立，不跟進站搶）
        self._browser_lock = asyncio.Lock()
        self.capture_full_page_screenshot = bool(
            self.config.get("capture_full_page_screenshot", False)
        )
        self._dedup_lock = asyncio.Lock()

    def _load_json_set(self, path: str) -> Set[str]:
        if not os.path.isfile(path):
            return set()
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return set(data) if isinstance(data, list) else set()
        except Exception:
            return set()

    def _save_json_set(self, path: str, data: Set[str]) -> None:
        # Record 精簡後不再持久化 dedup json
        return

    async def _dismiss_popups(self, page) -> None:
        # 年齡閘優先（Yes / 21+ / 18+），不要點 No
        age_labels = (
            "Yes", "YES", "I am 21", "I am 18", "I'm 21", "I'm 18",
            "I am 21+", "I am over 21", "I am over 18", "21+", "18+",
            "Enter Site", "Enter", "Confirm Age", "Verify Age",
            "是", "我已滿21歲", "我已滿18歲", "已滿21歲", "已滿18歲", "進入網站", "進入",
        )
        labels = age_labels + (
            "OK", "Ok", "Accept", "Accept all", "I agree", "Agree", "Continue",
            "Got it", "Allow all", "Allow", "Close", "Dismiss",
            "同意", "接受", "確定", "關閉",
        )
        for label in labels:
            try:
                btn = page.get_by_role("button", name=label, exact=False).first
                if await btn.is_visible(timeout=400):
                    await btn.click(timeout=2000)
                    logging.info(f"   [POPUP] 已自動點擊: '{label}'")
                    if label in age_labels or label in ("Yes", "YES", "Enter", "Enter Site"):
                        break
            except Exception:
                pass
        # 再試連結型年齡按鈕
        for label in ("Yes", "I am 21", "I am 18", "Enter Site", "進入"):
            try:
                link = page.get_by_role("link", name=label, exact=False).first
                if await link.is_visible(timeout=300):
                    await link.click(timeout=2000)
                    logging.info(f"   [POPUP] 已自動點擊連結: '{label}'")
                    break
            except Exception:
                pass
        try:
            await page.evaluate(
                """() => {
                    const selectors = [
                        '[class*="cookie"] button', '[class*="consent"] button',
                        '#onetrust-accept-btn-handler', '.fc-cta-consent',
                        '[aria-label*="close" i]', 'button.close'
                    ];
                    for (const sel of selectors) {
                        document.querySelectorAll(sel).forEach(el => {
                            try { el.click(); } catch (e) {}
                        });
                    }
                }"""
            )
        except Exception:
            pass

    async def _extract_product_images(self, page, domain: str) -> List[Dict[str, str]]:
        max_images = int((self.config.get("engine_24h") or {}).get("max_product_images", 12))
        min_size = 100
        try:
            # 只滾一段，避免無限頁拖死
            await page.evaluate(
                """async () => {
                    for (let i = 0; i < 6; i++) {
                        window.scrollBy(0, 400);
                        await new Promise(r => setTimeout(r, 120));
                    }
                    window.scrollTo(0, 0);
                }"""
            )
            await asyncio.sleep(0.8)

            raw = await page.evaluate(
                f"""() => Array.from(document.querySelectorAll('img')).map(img => {{
                    const lazy = img.getAttribute('data-src') || img.getAttribute('data-lazy-src') || '';
                    const src = (img.naturalWidth >= {min_size} && img.src.startsWith('http'))
                        ? img.src : (lazy.startsWith('http') ? lazy : img.src);
                    return {{ src, alt: (img.alt || '').toLowerCase(), w: img.naturalWidth }};
                }}).filter(i => i.src && i.src.startsWith('http')
                    && (i.w >= {min_size} || i.w === 0))"""
            )
            if not raw:
                return []

            keywords = self.config.get("keyword_groups", {}).get("A_Product", [])
            seen_src: Set[str] = set()
            candidates = []
            for item in raw:
                if item["src"] in seen_src:
                    continue
                seen_src.add(item["src"])
                text = f"{item['alt']} {item['src']}".lower()
                item["kw"] = any(kw.lower() in text for kw in keywords)
                candidates.append(item)
            candidates.sort(key=lambda x: x["kw"], reverse=True)
            candidates = candidates[:max_images]

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            results: List[Dict[str, str]] = []
            new_hashes: Set[str] = set()

            for i, item in enumerate(candidates):
                try:
                    resp = await page.request.get(item["src"], timeout=8000)
                    if not resp.ok:
                        continue
                    body = await resp.body()
                    if len(body) < 3000:
                        continue
                    img_hash = hashlib.md5(body).hexdigest()
                    if img_hash in self.seen_hashes or img_hash in new_hashes:
                        continue
                    new_hashes.add(img_hash)
                    self.seen_hashes.add(img_hash)

                    ext = "jpg"
                    ct = resp.headers.get("content-type", "")
                    if "png" in ct:
                        ext = "png"
                    elif "webp" in ct:
                        ext = "webp"
                    filename = f"{domain}_{ts}_{i + 1:02d}.{ext}"
                    # 不寫入 testjpg；只保留 base64 供 Webhook / Record
                    results.append({
                        "filename": filename,
                        "base64_data": base64.b64encode(body).decode("utf-8"),
                    })
                except Exception:
                    continue

            if new_hashes:
                async with self._dedup_lock:
                    self._save_json_set(self.seen_hashes_path, self.seen_hashes)
            return results
        except Exception as e:
            logging.warning(f"   商品圖擷取失敗: {e}")
            return []

    async def _block_heavy_assets(self, page) -> None:
        """擋字型／媒體加快載入（保留圖片給商品圖）。"""
        async def _route(route):
            try:
                rt = route.request.resource_type
                if rt in ("media", "font", "websocket"):
                    await route.abort()
                else:
                    await route.continue_()
            except Exception:
                try:
                    await route.continue_()
                except Exception:
                    pass
        try:
            await page.route("**/*", _route)
        except Exception:
            pass

    async def crawl(
        self,
        url: str,
        lightweight: Optional[bool] = None,
        retry_count: int = 1,
        crawl_opts: Optional[Dict] = None,
    ) -> Dict:
        """Investigator：進站 → 評分 → 截圖／商品圖。用獨立 browser，不跟 Harvester 搶。"""
        normalized_url = url.split("#")[0]
        if any(black in normalized_url.lower() for black in self.blacklist):
            return {"url": normalized_url, "score": 0, "tier": "SKIP", "links": []}

        path_l = normalized_url.lower().split("?", 1)[0]
        if any(path_l.endswith(ext) for ext in (
            ".pdf", ".xml", ".rss", ".atom", ".zip", ".mp4", ".jpg", ".png", ".gif",
        )) or path_l.endswith("/atom.xml") or path_l.endswith("/feed"):
            logging.info(f"   [SKIP] 非網頁資源: {url}")
            return {"url": normalized_url, "score": 0, "tier": "SKIP", "links": []}

        sem = get_global_sem()
        for attempt in range(retry_count + 1):
            context = None
            try:
                async with sem:
                    await self._ensure_browsers()
                    logging.info(f"   Investigating (Full) [Attempt {attempt + 1}]: {url}")
                    context = await self._browser.new_context(
                        **_build_context_options(self.config, viewport=(1280, 720))
                    )
                    page = await context.new_page()
                    self._setup_dialog_handler(page)
                    await self._block_heavy_assets(page)
                    try:
                        await stealth_async(page)
                    except Exception:
                        pass

                    # commit 先拿到回應，再短等 DOM；避免慢站卡滿 60s
                    goto_timeout = 45000 if attempt == 0 else 30000
                    resp = await page.goto(
                        url, wait_until="commit", timeout=goto_timeout
                    )
                    status = resp.status if resp else 0
                    try:
                        await page.wait_for_load_state(
                            "domcontentloaded", timeout=20000
                        )
                    except Exception:
                        logging.info(f"   [NAV] DOM 未齊仍繼續讀內容: {url}")

                    # 403／挑戰：多等一下再讀，很多站會放行或仍有可讀 HTML
                    if status in (403, 429, 503):
                        logging.info(f"   [NAV] HTTP {status}，短暫等待後仍嘗試解析: {url}")
                        await asyncio.sleep(4)
                    else:
                        await asyncio.sleep(1.5)

                    await self._dismiss_popups(page)
                    await _simulate_human_light(page)

                    html_raw = await page.content()
                    text = await _safe_page_text(page)
                    if not (text or "").strip() and status >= 400:
                        raise RuntimeError(f"HTTP {status} empty body")

                    res = self.analyzer.analyze(text, html_raw, url)
                    res["text_content"] = text
                    logging.info(
                        f"   [SCORE] {res.get('tier')} score={res.get('score', 0)} | {url}"
                    )

                    if res.get("tier") != "SKIP":
                        domain = urlparse(url).netloc or "unknown"
                        await page.evaluate("window.scrollTo(0, 0)")
                        await asyncio.sleep(0.4)
                        viewport_binary = await page.screenshot(
                            type="jpeg", quality=80, full_page=False
                        )
                        shot = base64.b64encode(viewport_binary).decode("utf-8")
                        res["screenshot_b64"] = shot
                        res["full_screenshot_base64"] = shot
                        res["product_images"] = await self._extract_product_images(
                            page, domain
                        )
                        # 沒抓到商品圖時用截圖頂上，避免 webhook 因 images 空而不送
                        if not res["product_images"] and shot:
                            res["product_images"] = [{
                                "filename": f"{domain}_viewport.jpg",
                                "base64_data": shot,
                            }]
                        async with self._dedup_lock:
                            if normalized_url not in self.seen_urls:
                                self.seen_urls.add(normalized_url)
                                self._save_json_set(self.seen_urls_path, self.seen_urls)

                    links = await page.evaluate(
                        """() => Array.from(document.querySelectorAll('a'))
                            .map(a => a.href.split('#')[0])
                            .filter(h => h.startsWith('http') && h.includes(location.hostname));"""
                    )
                    res["links"] = list(set(links))[:15]
                    return res

            except Exception as e:
                err = str(e)
                logging.error(f"   [RETRY] 嘗試 {attempt + 1} 失敗 {url}: {e}")
                if any(h in err for h in _HARD_NAV_ERRORS):
                    return {"url": url, "score": 0, "tier": "SKIP", "links": []}
                if attempt < retry_count:
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                    continue
                return {"url": url, "score": 0, "tier": "SKIP", "links": []}
            finally:
                if context:
                    try:
                        await context.close()
                    except Exception:
                        pass
        return {"url": url, "score": 0, "tier": "SKIP", "links": []}

    async def _launch_chrome(self):
        launch_kwargs = {
            "headless": self.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        }
        try:
            browser = await self._pw_instance.chromium.launch(
                channel="chrome", **launch_kwargs
            )
            return browser, "chrome"
        except Exception as e:
            logging.warning(f"系統 Chrome 不可用，改用 Chromium: {e}")
            browser = await self._pw_instance.chromium.launch(**launch_kwargs)
            return browser, "chromium"

    async def _ensure_browsers(self) -> None:
        async with self._browser_lock:
            if self._pw_instance is None:
                self._pw_instance = await async_playwright().start()

            need_inv = True
            if self._browser is not None:
                try:
                    need_inv = not self._browser.is_connected()
                except Exception:
                    need_inv = True
            if need_inv:
                if self._browser:
                    try:
                        await self._browser.close()
                    except Exception:
                        pass
                self._browser, kind = await self._launch_chrome()
                logging.info(f"V46.0 Investigate Browser ready ({kind}).")

            need_search = True
            if self._browser_search is not None:
                try:
                    need_search = not self._browser_search.is_connected()
                except Exception:
                    need_search = True
            if need_search:
                if self._browser_search:
                    try:
                        await self._browser_search.close()
                    except Exception:
                        pass
                self._browser_search, kind = await self._launch_chrome()
                logging.info(f"V46.0 Harvest Browser ready ({kind}).")

    async def init(self):
        await self._ensure_browsers()

    def _setup_dialog_handler(self, page):
        page.on("dialog", lambda dialog: asyncio.ensure_future(dialog.accept()))

    async def _search_single_engine(self, query: str, engine: dict) -> List[str]:
        name = engine.get("name", "?")
        sem = get_harvest_sem()
        context = None
        try:
            await self._ensure_browsers()
            async with sem:
                context = await self._browser_search.new_context(
                    **_build_context_options(self.config, viewport=(1280, 720))
                )
                page = await context.new_page()
                try:
                    await stealth_async(page)
                except Exception:
                    pass
                await page.route(
                    "**/*.{png,jpg,jpeg,gif,svg,woff,woff2,mp4}",
                    lambda route: route.abort(),
                )
                search_url = engine.get("url", "").format(urllib.parse.quote(query))
                logging.info(f"   -> [HARVESTER:{name}] 檢索: {query[:40]}...")
                await page.goto(search_url, wait_until="commit", timeout=45000)
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(2.0, 3.5))
                hrefs = await page.evaluate(
                    "() => Array.from(document.querySelectorAll('a')).map(a => a.href)"
                )
                result = hrefs if hrefs else []
                logging.info(f"   -> [HARVESTER:{name}] 完成: {len(result)} 個連結")
                return result
        except Exception as e:
            logging.warning(f"   -> [HARVESTER:{name}] 失敗: {str(e)[:120]}")
            return []
        finally:
            if context:
                try:
                    await context.close()
                except Exception:
                    pass

    async def search_harvester(self, query: str, max_results: int) -> List[str]:
        """關鍵字搜尋；使用獨立 harvest browser，不佔用 8 軌進站。"""
        await self._ensure_browsers()
        engines = self.config.get("search_engines", [])
        batch = int((self.config.get("engine_24h") or {}).get("max_harvest_parallel", 2))
        batch = max(1, min(batch, len(engines) or 1))

        all_hrefs: List[str] = []
        for i in range(0, len(engines), batch):
            chunk = engines[i : i + batch]
            results_per_engine = await asyncio.gather(
                *[self._search_single_engine(query, engine) for engine in chunk],
                return_exceptions=True,
            )
            for result in results_per_engine:
                if isinstance(result, list):
                    all_hrefs.extend(result)

        noise_domains = [
            "google.", "bing.", "duckduckgo.", "swisscows.", "searx.", "startpage.",
            "mojeek.", "yandex.", "facebook.com", "linkedin.com", "instagram.com",
            "twitter.com", "tiktok.com", "github.com", "youtube.com",
            "gibiru.com", "qwant.com", "coccoc.com", "brave.com",
            "bbc.", "newsweek.", "cnn.", "reuters.", "nytimes.",
            "huggingface.co", "buttondown.email",
        ]
        filtered = []
        for h in all_hrefs:
            if h and h.startswith("http") and not any(b in h.lower() for b in self.blacklist):
                if not any(n in h.lower() for n in noise_domains):
                    if not any(p in h.lower() for p in [
                        "/privacy", "/settings", "/accounts", "/preferences", "/search?",
                    ]):
                        path = h.lower().split("#", 1)[0].split("?", 1)[0]
                        if any(path.endswith(ext) for ext in (
                            ".pdf", ".xml", ".rss", ".atom", ".zip", ".mp4",
                            ".jpg", ".png", ".gif", ".css", ".js", ".txt",
                        )):
                            continue
                        if path.endswith("/atom.xml") or path.endswith("/feed"):
                            continue
                        filtered.append(h)

        per_engine_limit = max_results * len(engines)
        unique = list(set(filtered))[:per_engine_limit]
        logging.info(
            f"   -> [HARVESTER] 全引擎合併: {len(unique)} 個有效 URL（共 {len(engines)} 個引擎）"
        )
        return unique

    async def close(self):
        for attr in ("_browser", "_browser_search"):
            b = getattr(self, attr, None)
            if b:
                try:
                    await b.close()
                except Exception:
                    pass
                setattr(self, attr, None)
        if self._pw_instance:
            try:
                await self._pw_instance.stop()
            except Exception:
                pass
            self._pw_instance = None
