"""
base_scraper.py — Abstract base for all vendor scrapers.
Handles: Playwright launch, UA rotation, Redis caching, rate limiting,
robots.txt compliance, and audit logging.
"""
import os
import re
import time
import random
import hashlib
import logging
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 OPR/107.0.0.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
]

CACHE_TTL = 4 * 3600            # 4 hours per component/vendor
MIN_DELAY = 1.5                 # seconds between requests to same domain
MAX_DELAY = 3.0
MAX_RETRIES = 3


def _redis_client():
    try:
        import redis
        return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
    except Exception:
        return None


class BaseScraper(ABC):
    VENDOR_NAME: str = "Unknown"
    BASE_DOMAIN: str = ""

    def __init__(self):
        self._redis = _redis_client()
        self._robots: dict[str, RobotFileParser] = {}
        self._last_request_time: dict[str, float] = {}

    # ── Public interface ───────────────────────────────────────────────────────

    @abstractmethod
    async def search(self, mpn: str, qty: int, rate_inr: float) -> list[dict]:
        """
        Search for mpn and return a list of VendorResult-compatible dicts.
        rate_inr: current USD→INR exchange rate.
        """
        ...

    # ── Caching ───────────────────────────────────────────────────────────────

    def _cache_key(self, mpn: str) -> str:
        h = hashlib.md5(f"{self.VENDOR_NAME}:{mpn}".encode()).hexdigest()[:12]
        return f"bom:price:{h}"

    def _get_cache(self, mpn: str) -> Optional[str]:
        if not self._redis:
            return None
        try:
            return self._redis.get(self._cache_key(mpn))
        except Exception:
            return None

    def _set_cache(self, mpn: str, data: str) -> None:
        if not self._redis:
            return
        try:
            self._redis.setex(self._cache_key(mpn), CACHE_TTL, data)
        except Exception:
            pass

    # ── Rate limiting ──────────────────────────────────────────────────────────

    async def _rate_limit(self, domain: str) -> None:
        last = self._last_request_time.get(domain, 0)
        elapsed = time.monotonic() - last
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        self._last_request_time[domain] = time.monotonic()

    # ── robots.txt ─────────────────────────────────────────────────────────────

    def _is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain not in self._robots:
            rp = RobotFileParser()
            robots_url = f"{parsed.scheme}://{domain}/robots.txt"
            try:
                rp.set_url(robots_url)
                rp.read()
            except Exception:
                rp = None  # If we can't read robots.txt, be permissive
            self._robots[domain] = rp
        rp = self._robots.get(domain)
        if rp is None:
            return True
        return rp.can_fetch("*", url)

    # ── Playwright page fetch ──────────────────────────────────────────────────

    async def _get_page(self, url: str, wait_selector: Optional[str] = None,
                        timeout: int = 30000) -> str:
        """Fetch page HTML using Playwright with stealth UA and rate limiting."""
        domain = urlparse(url).netloc

        if not self._is_allowed(url):
            logger.warning("[%s] robots.txt disallows: %s", self.VENDOR_NAME, url)
            return ""

        await self._rate_limit(domain)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                from playwright.async_api import async_playwright
                async with async_playwright() as pw:
                    browser = await pw.chromium.launch(headless=True)
                    context = await browser.new_context(
                        user_agent=random.choice(USER_AGENTS),
                        viewport={"width": 1280, "height": 800},
                        locale="en-IN",
                        timezone_id="Asia/Kolkata",
                    )
                    page = await context.new_page()

                    # Block images/fonts to speed up
                    await page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf}",
                                     lambda r: r.abort())

                    await page.goto(url, timeout=timeout, wait_until="domcontentloaded")

                    if wait_selector:
                        try:
                            await page.wait_for_selector(wait_selector, timeout=10000)
                        except Exception:
                            logger.debug("[%s] Selector %s not found.", self.VENDOR_NAME, wait_selector)

                    html = await page.content()
                    await browser.close()
                    return html

            except Exception as exc:
                logger.warning("[%s] Attempt %d/%d failed for %s: %s",
                               self.VENDOR_NAME, attempt, MAX_RETRIES, url, exc)
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)

        logger.error("[%s] All %d attempts failed for %s — marking manual lookup.",
                     self.VENDOR_NAME, MAX_RETRIES, url)
        return ""

    # ── JSON fetch (no Playwright) ─────────────────────────────────────────────

    async def _get_json(self, url: str, params: dict | None = None,
                        headers: dict | None = None) -> dict | list | None:
        domain = urlparse(url).netloc
        await self._rate_limit(domain)

        base_headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json",
            "Accept-Language": "en-IN,en;q=0.9",
        }
        if headers:
            base_headers.update(headers)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(url, params=params, headers=base_headers)
                    resp.raise_for_status()
                    return resp.json()
            except Exception as exc:
                logger.warning("[%s] JSON fetch attempt %d/%d failed: %s",
                               self.VENDOR_NAME, attempt, MAX_RETRIES, exc)
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)
        return None
