import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from crawl_logger import CrawlLogger
from crawl_core import safe_page_text


DEFAULT_AUTH_BYPASS = {
    "reject_login_register_walls": True,
    "mode": "off",
    "known_targets": {},
}

REGISTER_URL_HINTS = ("register", "signup", "sign-up", "create-account", "join", "account/create")
LOGIN_URL_HINTS = ("login", "signin", "sign-in", "wp-login", "my-account")

CHALLENGE_HTML_HINTS = (
    "cf-browser-verification",
    "challenge-platform",
    "challenges.cloudflare.com",
    "cdn-cgi/challenge",
    "turnstile",
    "hcaptcha",
    "recaptcha",
    "g-recaptcha",
    "cf-challenge",
    "checking your browser",
    "just a moment",
    "verify you are human",
    "attention required",
    "ddos protection",
)
CHALLENGE_TEXT_HINTS = (
    "checking your browser",
    "just a moment",
    "verify you are human",
    "complete the security check",
    "enable javascript and cookies",
    "ray id:",
)


class AuthBypassEngine:
    """
    登入/註冊牆偵測（不填表、不嘗試自動登入/註冊）。

    若 reject_login_register_walls=true（預設）：
    偵測到需登入或註冊的頁面 → 應立即中止爬取並回傳「非毒品網站或無法登入」。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        raw = {**DEFAULT_AUTH_BYPASS, **((config or {}).get("auth_bypass") or {})}
        self.reject_walls = bool(raw.get("reject_login_register_walls", True))
        self.mode = (raw.get("mode") or "off").lower()
        self.known_targets: Dict[str, Dict[str, str]] = raw.get("known_targets") or {}

    async def detect_access_barrier(self, page, current_url: str) -> Dict[str, Any]:
        """判斷是否為登入牆/註冊頁/反爬驗證頁；should_reject=true 時應中止爬取。"""
        pwd_count = 0
        page_text = ""
        page_text_lower = ""
        page_html_lower = ""
        page_title_lower = ""
        try:
            pwd_count = await page.locator("input[type='password']").count()
            page_text = await safe_page_text(page)
            page_text_lower = page_text.lower()
            page_html_lower = (await page.content() or "").lower()
            page_title_lower = (await page.title() or "").lower()
        except Exception:
            pass

        # --- 反爬 / CAPTCHA / Cloudflare ---
        is_bot_challenge = False
        challenge_reason = ""
        combined = f"{page_title_lower} {page_text_lower[:800]} {page_html_lower[:4000]}"
        if any(h in combined for h in CHALLENGE_HTML_HINTS) or any(
            h in page_text_lower[:600] for h in CHALLENGE_TEXT_HINTS
        ):
            is_bot_challenge = True
            challenge_reason = "偵測到反爬/驗證頁（Cloudflare、CAPTCHA 等）"
        elif await page.locator(
            "iframe[src*='captcha'], iframe[src*='turnstile'], .g-recaptcha, .h-captcha, #cf-turnstile"
        ).count() > 0:
            is_bot_challenge = True
            challenge_reason = "偵測到 CAPTCHA / Turnstile 元件"

        if is_bot_challenge and self.reject_walls:
            return {
                "should_reject": True,
                "barrier_type": "bot_challenge",
                "reason": challenge_reason,
                "needs_login": False,
                "needs_register": False,
                "password_field_count": pwd_count,
                "page_text_length": len(page_text_lower),
                "has_login_url": False,
                "has_register_url": False,
            }

        url_lower = current_url.lower()
        path_lower = urlparse(current_url).path.lower()
        page_len = len(page_text_lower)

        has_register_url = any(h in path_lower or h in url_lower for h in REGISTER_URL_HINTS)
        has_login_url = any(h in path_lower or h in url_lower for h in LOGIN_URL_HINTS)

        register_keywords = [
            "sign up", "create account", "register", "join us", "建立帳號", "註冊帳號",
        ]
        login_keywords = [
            "log in", "login", "sign in", "welcome back", "登入", "請登入", "會員登入",
        ]

        has_register_text = any(k in page_text_lower[:1200] for k in register_keywords)
        has_login_text = any(k in page_text_lower[:1200] for k in login_keywords)
        has_confirm_pwd = (
            "confirm password" in page_text_lower
            or "re-type password" in page_text_lower
            or "再次輸入密碼" in page_text_lower
        )

        is_register_wall = False
        is_login_wall = False
        reason = ""

        if pwd_count >= 2 or has_confirm_pwd:
            is_register_wall = True
            reason = "偵測到註冊表單（確認密碼欄位或多個密碼框）"
        elif has_register_url and pwd_count >= 1:
            is_register_wall = True
            reason = "URL 為註冊/建立帳號頁且含密碼欄位"
        elif has_register_text and pwd_count >= 1 and page_len < 3500:
            is_register_wall = True
            reason = "頁面以註冊為主且含密碼欄位"
        elif pwd_count >= 1 and has_login_url and page_len < 4000:
            is_login_wall = True
            reason = "URL 為登入頁且含密碼欄位"
        elif pwd_count >= 1 and has_login_text and page_len < 2500 and not has_register_text:
            is_login_wall = True
            reason = "偵測到登入牆（密碼框 + 登入文案，內容偏短）"
        elif pwd_count >= 1 and page_len < 1200 and not has_register_text:
            is_login_wall = True
            reason = "偵測到登入牆（密碼框且頁面內容極短）"

        should_reject = self.reject_walls and (is_register_wall or is_login_wall)
        barrier_type = "none"
        if is_register_wall:
            barrier_type = "register"
        elif is_login_wall:
            barrier_type = "login"

        return {
            "should_reject": should_reject,
            "barrier_type": barrier_type,
            "reason": reason,
            "needs_login": is_login_wall,
            "needs_register": is_register_wall,
            "password_field_count": pwd_count,
            "page_text_length": page_len,
            "has_login_url": has_login_url,
            "has_register_url": has_register_url,
        }

    async def unlock(
        self,
        page,
        current_url: str,
        crawl_log: Optional[CrawlLogger] = None,
    ) -> Dict[str, Any]:
        """相容舊呼叫點：僅做屏障偵測，不做任何填表/登入/註冊。"""
        detection = await self.detect_access_barrier(page, current_url)

        if crawl_log:
            crawl_log.phase(
                "AUTH",
                "登入/註冊屏障掃描完成",
                should_reject=detection["should_reject"],
                barrier_type=detection["barrier_type"],
                reason=detection["reason"] or "none",
                password_fields=detection["password_field_count"],
                page_len=detection["page_text_length"],
            )
        elif detection["should_reject"]:
            logging.info(
                f"[AUTH] 拒絕爬取 {current_url} | type={detection['barrier_type']} "
                f"| {detection['reason']}"
            )

        if detection["should_reject"]:
            return {**detection, "action": "reject_wall"}
        if detection["barrier_type"] == "none":
            return {**detection, "action": "pass"}
        return {**detection, "action": "detect_only"}
