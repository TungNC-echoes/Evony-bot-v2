"""
Playwright client for iscout.club boss locations.

Handles:
- Cloudflare "Performing security verification" interstitial
- Human-like delays (reduce bot triggers)
- Optional Turnstile / verify-human checkbox
- managed Chrome launch or CDP attach
"""

from __future__ import annotations

import os
import random
import re
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from utils.iscout_config import (
    load_iscout_config,
    save_iscout_config,
    session_dir,
    storage_state_path,
)

LOGIN_URL = "https://www.iscout.club/vi/login"
DASHBOARD_URL = "https://www.iscout.club/vi/dashboard"
TABLE_SELECTOR = "table.min-w-full.divide-y.mb-4 tbody tr"

# Cloudflare / bot-wall signals
CF_TEXT_PATTERNS = [
    "Performing security verification",
    "Checking your browser",
    "Just a moment",
    "Verify you are human",
    "verifying you are human",
    "This website uses a security service",
    "Enable JavaScript and cookies",
    "cf-browser-verification",
    "Attention Required",
]

LogFn = Optional[Callable[[str], None]]


def _log(message: str, log_fn: LogFn = None) -> None:
    print(message)
    if log_fn:
        try:
            log_fn(message)
        except Exception:
            pass


def _sleep(a: float, b: Optional[float] = None) -> None:
    """Human-like random delay (seconds)."""
    if b is None:
        b = a
    time.sleep(random.uniform(min(a, b), max(a, b)))


def _parse_boss_rows(rows_text: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    boss_list: List[Dict[str, Any]] = []
    for row in rows_text:
        name = (row.get("name") or "").strip()
        coordinates = (row.get("coordinates") or "").strip()
        level_text = row.get("level") or ""

        level_info: Dict[str, str] = {}
        if level_text:
            for line in level_text.split("\n"):
                if ":" in line:
                    key, value = map(str.strip, line.split(":", 1))
                    if key in ("S", "X", "Y"):
                        level_info[key] = value

        if not name:
            continue

        boss_list.append(
            {
                "name": name,
                "coordinates": coordinates,
                "level": level_info,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "attacked": 0,
            }
        )
    return boss_list


class IScoutClient:
    def __init__(
        self,
        email: str = "",
        password: str = "",
        mode: str = "managed",
        cdp_port: int = 9014,
        login_timeout_sec: int = 180,
        cloudflare_timeout_sec: int = 120,
        headless: bool = False,
        log_fn: LogFn = None,
    ):
        self.email = (email or "").strip()
        self.password = password or ""
        self.mode = mode if mode in ("managed", "cdp") else "managed"
        self.cdp_port = int(cdp_port or 9014)
        self.login_timeout_sec = int(login_timeout_sec or 180)
        self.cloudflare_timeout_sec = int(cloudflare_timeout_sec or 120)
        # Cloudflare almost always fails in headless — force visible browser
        self.headless = False if not headless else bool(headless)
        if headless:
            # Keep param but warn via log later; CF needs headed Chrome
            self.headless = False
        self.log_fn = log_fn

    @classmethod
    def from_config(cls, log_fn: LogFn = None, **overrides: Any) -> "IScoutClient":
        cfg = load_iscout_config()
        cfg.update({k: v for k, v in overrides.items() if v is not None})
        return cls(
            email=cfg.get("email", ""),
            password=cfg.get("password", ""),
            mode=cfg.get("mode", "managed"),
            cdp_port=cfg.get("cdp_port", 9014),
            login_timeout_sec=cfg.get("login_timeout_sec", 180),
            cloudflare_timeout_sec=cfg.get("cloudflare_timeout_sec", 120),
            headless=cfg.get("headless", False),
            log_fn=log_fn,
        )

    def fetch_boss_locations(self, max_retries: int = 3) -> List[Dict[str, Any]]:
        last_error: Optional[Exception] = None
        for attempt in range(1, max_retries + 1):
            try:
                _log(
                    f"iScout: lấy boss (lần {attempt}/{max_retries}, mode={self.mode})",
                    self.log_fn,
                )
                bosses = self._fetch_once()
                _log(f"iScout: lấy được {len(bosses)} boss", self.log_fn)
                return bosses
            except Exception as e:
                last_error = e
                _log(f"iScout lỗi lần {attempt}: {e}", self.log_fn)
                _sleep(2.0, 4.0)
        if last_error:
            _log(f"iScout thất bại: {last_error}", self.log_fn)
        return []

    def test_login(self) -> bool:
        """Open browser, pass Cloudflare if needed, login, save session."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "Chưa cài Playwright. Chạy: python -m pip install playwright "
                "&& python -m playwright install chromium"
            ) from e

        with sync_playwright() as p:
            browser = None
            context = None
            try:
                browser, context, page = self._open_page(p)
                ok = self._ensure_logged_in(page, context)
                if ok:
                    self._save_storage_state(context)
                    _log("iScout: đăng nhập / session OK", self.log_fn)
                return ok
            finally:
                self._close(browser, context)

    def _fetch_once(self) -> List[Dict[str, Any]]:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = None
            context = None
            try:
                browser, context, page = self._open_page(p)
                if not self._ensure_logged_in(page, context):
                    raise RuntimeError(
                        "Chưa đăng nhập được iscout. Thường do Cloudflare chưa pass "
                        "hoặc sai account. Thử mode CDP (Chrome đã mở sẵn) hoặc Login lại."
                    )
                self._save_storage_state(context)

                if "dashboard" not in (page.url or ""):
                    self._safe_goto(page, DASHBOARD_URL)
                else:
                    self._wait_cloudflare_clear(page)

                _sleep(1.2, 2.2)
                page.wait_for_selector(TABLE_SELECTOR, timeout=45000)
                _sleep(0.6, 1.2)

                rows = page.query_selector_all(TABLE_SELECTOR)
                raw_rows: List[Dict[str, str]] = []
                for row in rows:
                    cols = row.query_selector_all("td")
                    if len(cols) < 3:
                        continue
                    raw_rows.append(
                        {
                            "name": cols[0].inner_text(),
                            "coordinates": cols[1].inner_text(),
                            "level": cols[2].inner_text(),
                        }
                    )

                bosses = _parse_boss_rows(raw_rows)
                for boss in bosses:
                    _log(f"Đã lấy: {boss['name']} ({boss['coordinates']})", self.log_fn)
                return bosses
            finally:
                if self.mode == "cdp":
                    if browser:
                        try:
                            browser.close()
                        except Exception:
                            pass
                else:
                    self._close(browser, context)

    def _open_page(self, playwright):
        if self.mode == "cdp":
            endpoint = f"http://127.0.0.1:{self.cdp_port}"
            _log(f"iScout: attach CDP {endpoint}", self.log_fn)
            browser = playwright.chromium.connect_over_cdp(endpoint)
            if browser.contexts:
                context = browser.contexts[0]
            else:
                context = browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()
            return browser, context, page

        # Persistent Chrome profile survives Cloudflare cookies better than storage_state alone
        profile_dir = os.path.join(session_dir(), "chrome_profile")
        os.makedirs(profile_dir, exist_ok=True)
        _log(f"iScout: mở Chrome persistent profile → {profile_dir}", self.log_fn)

        launch_args = {
            "user_data_dir": profile_dir,
            "headless": False,
            "viewport": {"width": 1280, "height": 900},
            "locale": "vi-VN",
            "args": [
                "--disable-blink-features=AutomationControlled",
            ],
        }
        try:
            context = playwright.chromium.launch_persistent_context(
                channel="chrome",
                **launch_args,
            )
        except Exception:
            context = playwright.chromium.launch_persistent_context(**launch_args)

        page = context.pages[0] if context.pages else context.new_page()
        return None, context, page

    def _safe_goto(self, page, url: str) -> None:
        _log(f"iScout: mở {url}", self.log_fn)
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        _sleep(1.5, 2.8)
        self._wait_cloudflare_clear(page)

    def _page_looks_like_cloudflare(self, page) -> bool:
        try:
            title = (page.title() or "").lower()
            if "just a moment" in title or "attention required" in title:
                return True
            body = ""
            try:
                body = page.inner_text("body", timeout=2000) or ""
            except Exception:
                body = page.content() or ""
            body_l = body.lower()
            for pat in CF_TEXT_PATTERNS:
                if pat.lower() in body_l:
                    return True
            # Cloudflare challenge iframe / turnstile
            if page.locator("iframe[src*='challenges.cloudflare.com']").count() > 0:
                return True
            if page.locator("iframe[src*='turnstile']").count() > 0:
                return True
            if page.locator("#challenge-form, #cf-challenge-running, .cf-turnstile").count() > 0:
                return True
        except Exception:
            return False
        return False

    def _wait_cloudflare_clear(self, page) -> bool:
        """
        Wait until Cloudflare interstitial is gone.
        Tries to click Turnstile/verify checkbox when visible.
        User may still need to click manually in the Chrome window.
        """
        deadline = time.time() + self.cloudflare_timeout_sec
        saw_cf = False

        while time.time() < deadline:
            if not self._page_looks_like_cloudflare(page):
                # Also require we are not stuck on blank challenge
                url = page.url or ""
                if "cdn-cgi/challenge" in url:
                    pass
                else:
                    if saw_cf:
                        _log("iScout: Cloudflare đã qua", self.log_fn)
                        _sleep(0.8, 1.5)
                    return True

            if not saw_cf:
                saw_cf = True
                _log(
                    f"iScout: đang chờ Cloudflare verify "
                    f"(tối đa {self.cloudflare_timeout_sec}s — có thể cần click trên Chrome)...",
                    self.log_fn,
                )

            self._try_click_verify_human(page)
            _sleep(1.5, 2.5)

            try:
                page.wait_for_load_state("domcontentloaded", timeout=3000)
            except Exception:
                pass

        _log("iScout: hết thời gian chờ Cloudflare", self.log_fn)
        return not self._page_looks_like_cloudflare(page)

    def _try_click_verify_human(self, page) -> bool:
        """Best-effort click on Turnstile / 'Verify you are human' controls."""
        selectors = [
            ".cb-lb input[type='checkbox']",
            "input[type='checkbox']",
            ".cf-turnstile",
            "#challenge-stage input",
            "label:has-text('Verify you are human')",
            "text=Verify you are human",
            "text=Xác minh bạn là con người",
        ]
        for sel in selectors:
            try:
                loc = page.locator(sel)
                if loc.count() == 0:
                    continue
                target = loc.first
                if not target.is_visible():
                    continue
                _log(f"iScout: thử click verify human ({sel})", self.log_fn)
                _sleep(0.4, 0.9)
                target.click(timeout=3000, force=True)
                _sleep(1.0, 2.0)
                return True
            except Exception:
                continue

        # Turnstile is often inside iframe — try first challenge iframe
        try:
            frames = page.frames
            for frame in frames:
                furl = frame.url or ""
                if "challenges.cloudflare.com" not in furl and "turnstile" not in furl:
                    continue
                for sel in ("input[type='checkbox']", "body"):
                    try:
                        el = frame.locator(sel)
                        if el.count() == 0:
                            continue
                        _log("iScout: thử click trong iframe Cloudflare", self.log_fn)
                        _sleep(0.5, 1.0)
                        el.first.click(timeout=3000, force=True)
                        _sleep(1.5, 2.5)
                        return True
                    except Exception:
                        continue
        except Exception:
            pass
        return False

    def _ensure_logged_in(self, page, context) -> bool:
        self._safe_goto(page, DASHBOARD_URL)
        if "dashboard" in (page.url or "") and self._has_boss_table(page):
            return True

        if "login" not in (page.url or ""):
            self._safe_goto(page, LOGIN_URL)
        else:
            self._wait_cloudflare_clear(page)

        if not self.email or not self.password:
            if self.mode == "cdp":
                _log(
                    f"iScout: chờ đăng nhập thủ công (timeout {self.login_timeout_sec}s)...",
                    self.log_fn,
                )
                return self._wait_dashboard(page)
            raise RuntimeError("Chưa cấu hình email/password iScout trong GUI.")

        # If still on CF after goto login, wait more
        if self._page_looks_like_cloudflare(page):
            if not self._wait_cloudflare_clear(page):
                return False

        _log("iScout: đang điền form đăng nhập (chậm, giống người dùng)...", self.log_fn)
        try:
            page.wait_for_selector("#email", timeout=30000)
        except Exception:
            # Maybe still blocked
            if self._page_looks_like_cloudflare(page):
                _log("iScout: vẫn kẹt Cloudflare trước form login", self.log_fn)
                self._wait_cloudflare_clear(page)
            page.wait_for_selector("#email", timeout=30000)

        _sleep(0.8, 1.5)
        page.click("#email")
        _sleep(0.2, 0.5)
        page.fill("#email", "")
        page.type("#email", self.email, delay=random.randint(45, 110))
        _sleep(0.5, 1.1)

        page.click("#password")
        _sleep(0.2, 0.4)
        page.fill("#password", "")
        page.type("#password", self.password, delay=random.randint(50, 120))
        _sleep(0.8, 1.6)

        login_btn = page.locator("button:has-text('Đăng nhập')")
        if login_btn.count() == 0:
            login_btn = page.locator("button[type='submit']")
        login_btn.first.click()
        _sleep(1.5, 2.5)

        # Post-login CF or verify-human
        self._try_click_verify_human(page)
        self._wait_cloudflare_clear(page)

        _log(
            f"iScout: chờ vào dashboard (timeout {self.login_timeout_sec}s)...",
            self.log_fn,
        )
        return self._wait_dashboard(page)

    def _wait_dashboard(self, page) -> bool:
        deadline = time.time() + self.login_timeout_sec
        while time.time() < deadline:
            if self._page_looks_like_cloudflare(page):
                self._try_click_verify_human(page)
                _sleep(1.5, 2.5)
                continue
            url = page.url or ""
            if "dashboard" in url:
                _sleep(0.8, 1.5)
                return True
            _sleep(1.0, 1.8)
        return "dashboard" in (page.url or "")

    def _has_boss_table(self, page) -> bool:
        try:
            if self._page_looks_like_cloudflare(page):
                return False
            page.wait_for_selector(TABLE_SELECTOR, timeout=8000)
            return True
        except Exception:
            return False

    def _save_storage_state(self, context) -> None:
        try:
            path = storage_state_path()
            context.storage_state(path=path)
            _log(f"iScout: đã lưu session → {path}", self.log_fn)
        except Exception as e:
            _log(f"iScout: không lưu được session: {e}", self.log_fn)

    def _close(self, browser, context) -> None:
        # Persistent context: closing context closes the browser
        try:
            if context:
                context.close()
        except Exception:
            pass
        try:
            if browser:
                browser.close()
        except Exception:
            pass


def save_credentials(email: str, password: str, mode: str = "managed", cdp_port: int = 9014) -> bool:
    return save_iscout_config(
        {
            "email": (email or "").strip(),
            "password": password or "",
            "mode": mode,
            "cdp_port": int(cdp_port),
            "login_timeout_sec": 180,
            "cloudflare_timeout_sec": 120,
        }
    )
