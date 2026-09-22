"""
Playwright client for iscout.club boss locations.
Supports:
- managed: launch Chrome, login, reuse storage_state
- cdp: attach to an already-running Chrome (--remote-debugging-port)
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from utils.iscout_config import (
    load_iscout_config,
    save_iscout_config,
    storage_state_path,
)

LOGIN_URL = "https://www.iscout.club/vi/login"
DASHBOARD_URL = "https://www.iscout.club/vi/dashboard"
TABLE_SELECTOR = "table.min-w-full.divide-y.mb-4 tbody tr"

LogFn = Optional[Callable[[str], None]]


def _log(message: str, log_fn: LogFn = None) -> None:
    print(message)
    if log_fn:
        try:
            log_fn(message)
        except Exception:
            pass


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
        login_timeout_sec: int = 120,
        headless: bool = False,
        log_fn: LogFn = None,
    ):
        self.email = (email or "").strip()
        self.password = password or ""
        self.mode = mode if mode in ("managed", "cdp") else "managed"
        self.cdp_port = int(cdp_port or 9014)
        self.login_timeout_sec = int(login_timeout_sec or 120)
        self.headless = bool(headless)
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
            login_timeout_sec=cfg.get("login_timeout_sec", 120),
            headless=cfg.get("headless", False),
            log_fn=log_fn,
        )

    def fetch_boss_locations(self, max_retries: int = 3) -> List[Dict[str, Any]]:
        last_error: Optional[Exception] = None
        for attempt in range(1, max_retries + 1):
            try:
                _log(f"iScout: lấy boss (lần {attempt}/{max_retries}, mode={self.mode})", self.log_fn)
                bosses = self._fetch_once()
                _log(f"iScout: lấy được {len(bosses)} boss", self.log_fn)
                return bosses
            except Exception as e:
                last_error = e
                _log(f"iScout lỗi lần {attempt}: {e}", self.log_fn)
        if last_error:
            _log(f"iScout thất bại: {last_error}", self.log_fn)
        return []

    def test_login(self) -> bool:
        """Open browser, ensure logged in, save session. Returns True on dashboard."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "Chưa cài Playwright. Chạy: pip install playwright && playwright install chromium"
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
                        "Chưa đăng nhập được iscout. Kiểm tra email/password hoặc giải captcha trên Chrome."
                    )
                self._save_storage_state(context)

                if "dashboard" not in (page.url or ""):
                    page.goto(DASHBOARD_URL, wait_until="domcontentloaded")

                page.wait_for_selector(TABLE_SELECTOR, timeout=30000)
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
                # CDP: don't kill user's Chrome; only disconnect.
                if self.mode == "cdp":
                    if browser:
                        browser.close()
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

        launch_kwargs = {
            "headless": self.headless,
        }
        # Prefer installed Chrome when available
        try:
            browser = playwright.chromium.launch(channel="chrome", **launch_kwargs)
        except Exception:
            browser = playwright.chromium.launch(**launch_kwargs)

        storage = storage_state_path()
        if os.path.exists(storage):
            _log("iScout: dùng storage_state đã lưu", self.log_fn)
            context = browser.new_context(storage_state=storage)
        else:
            context = browser.new_context()
        page = context.new_page()
        return browser, context, page

    def _ensure_logged_in(self, page, context) -> bool:
        page.goto(DASHBOARD_URL, wait_until="domcontentloaded")
        if "dashboard" in (page.url or "") and self._has_boss_table(page):
            return True

        # Not logged in / redirected to login
        if "login" not in (page.url or ""):
            page.goto(LOGIN_URL, wait_until="domcontentloaded")

        if not self.email or not self.password:
            if self.mode == "cdp":
                _log(
                    f"iScout: chờ bạn đăng nhập thủ công trên Chrome (timeout {self.login_timeout_sec}s)...",
                    self.log_fn,
                )
                try:
                    page.wait_for_url(re.compile(r".*dashboard.*"), timeout=self.login_timeout_sec * 1000)
                    return True
                except Exception:
                    return False
            raise RuntimeError("Chưa cấu hình email/password iScout trong GUI.")

        _log("iScout: đang điền form đăng nhập...", self.log_fn)
        page.wait_for_selector("#email", timeout=20000)
        page.fill("#email", self.email)
        page.fill("#password", self.password)

        # Click login button (Vietnamese UI)
        login_btn = page.locator("button:has-text('Đăng nhập')")
        if login_btn.count() == 0:
            login_btn = page.locator("button[type='submit']")
        login_btn.first.click()

        # Optional captcha checkbox
        try:
            checkbox = page.locator(".cb-lb input[type='checkbox']")
            checkbox.first.wait_for(state="visible", timeout=5000)
            _log("iScout: phát hiện verify human, click checkbox...", self.log_fn)
            checkbox.first.click(force=True)
        except Exception:
            pass

        _log(
            f"iScout: chờ vào dashboard (có thể cần giải captcha thủ công, timeout {self.login_timeout_sec}s)...",
            self.log_fn,
        )
        try:
            page.wait_for_url(re.compile(r".*dashboard.*"), timeout=self.login_timeout_sec * 1000)
            return True
        except Exception:
            # Last chance: maybe already on dashboard without URL match timing
            if "dashboard" in (page.url or ""):
                return True
            return False

    def _has_boss_table(self, page) -> bool:
        try:
            page.wait_for_selector(TABLE_SELECTOR, timeout=5000)
            return True
        except Exception:
            return False

    def _save_storage_state(self, context) -> None:
        if self.mode == "cdp":
            # Still useful if we can export cookies from attached context
            pass
        try:
            path = storage_state_path()
            context.storage_state(path=path)
            _log(f"iScout: đã lưu session → {path}", self.log_fn)
        except Exception as e:
            _log(f"iScout: không lưu được session: {e}", self.log_fn)

    @staticmethod
    def _close(browser, context) -> None:
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
        }
    )
