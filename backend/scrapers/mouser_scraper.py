"""
mouser_scraper.py — Mouser scraper.
Mouser India (in.mouser.com) shows INR prices directly.
Uses Playwright with stealth-like header setup since Mouser blocks basic UA.
"""
import re
import json
import logging
from datetime import datetime
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://in.mouser.com/Search/Refine?Keyword={mpn}"


class MouserScraper(BaseScraper):
    VENDOR_NAME = "Mouser"
    BASE_DOMAIN = "in.mouser.com"

    # Extra stealth headers Mouser needs
    _EXTRA_HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    async def search(self, mpn: str, qty: int, rate_inr: float) -> list[dict]:
        cached = self._get_cache(mpn)
        if cached:
            logger.debug("[Mouser] Cache hit for %s", mpn)
            return json.loads(cached)

        url = SEARCH_URL.format(mpn=mpn)
        html = await self._get_page(url, wait_selector=".product-table, .search-results-table")

        if not html:
            return []

        results = self._parse_results(html, qty, rate_inr)
        if results:
            self._set_cache(mpn, json.dumps(results))
        return results

    def _parse_price_inr(self, text: str) -> float | None:
        """Parse INR price strings like '₹1,234.56' or 'INR 45.00'."""
        text = re.sub(r"[₹INR\s,]", "", text)
        m = re.search(r"[\d]+\.?\d*", text)
        return float(m.group()) if m else None

    def _parse_results(self, html: str, qty: int, rate_inr: float) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # Mouser product table
        product_rows = (
            soup.select("tr.SearchResultsRow") or
            soup.select(".product-table tr[class]") or
            soup.select("tr[data-sku]")
        )

        for row in product_rows[:5]:
            try:
                # Part number
                pn = row.select_one(".mfr-part-num, [data-sku], .part-num")
                vpn = pn.get_text(strip=True) if pn else ""
                if not vpn:
                    continue

                # Price
                price_el = row.select_one(".price, .unit-price, [data-price]")
                price_inr = None
                if price_el:
                    price_inr = self._parse_price_inr(price_el.get_text(strip=True))

                # Some cells store price in data attribute
                if price_inr is None:
                    dp = row.select_one("[data-price]")
                    if dp:
                        try:
                            price_inr = float(dp["data-price"]) * rate_inr
                        except (ValueError, KeyError):
                            pass

                if price_inr is None:
                    continue

                # Stock
                stock_el = row.select_one(".stock, .qty-in-stock, .quantity-available, [data-stock]")
                stock = 0
                if stock_el:
                    stock_text = re.sub(r"[^\d]", "", stock_el.get_text(strip=True))
                    stock = int(stock_text) if stock_text else 0

                # MOQ
                moq_el = row.select_one(".min-order, .moq, [data-moq]")
                moq = 1
                if moq_el:
                    try:
                        moq = int(re.sub(r"[^\d]", "", moq_el.get_text(strip=True)) or "1")
                    except ValueError:
                        pass

                avail = "In Stock" if stock > 0 else "Out of Stock"

                results.append({
                    "vendor": "Mouser",
                    "vendor_part_number": vpn,
                    "unit_price_inr": price_inr,
                    "unit_price_usd": None,
                    "price_breaks": [],
                    "stock_qty": stock,
                    "availability": avail,
                    "moq": moq,
                    "lead_time_weeks": None,
                    "datasheet_url": None,
                    "scraped_at": datetime.utcnow().isoformat(),
                })

            except Exception as exc:
                logger.warning("[Mouser] Row parse error: %s", exc)
                continue

        return results
