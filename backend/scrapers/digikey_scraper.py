"""
digikey_scraper.py — DigiKey scraper using Playwright headless Chromium.
Prices are in USD (DigiKey IN shows USD); converted to INR.
"""
import re
import json
import logging
from datetime import datetime
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.digikey.in/en/products/result?keywords={mpn}"


class DigiKeyScraper(BaseScraper):
    VENDOR_NAME = "DigiKey"
    BASE_DOMAIN = "www.digikey.in"

    async def search(self, mpn: str, qty: int, rate_inr: float) -> list[dict]:
        cached = self._get_cache(mpn)
        if cached:
            logger.debug("[DigiKey] Cache hit for %s", mpn)
            return json.loads(cached)

        url = SEARCH_URL.format(mpn=mpn)
        html = await self._get_page(
            url,
            wait_selector="[data-testid='search-results-table'], .no-result",
        )

        if not html:
            return []

        results = self._parse_results(html, qty, rate_inr)

        if results:
            self._set_cache(mpn, json.dumps(results))

        return results

    def _parse_price(self, text: str) -> float | None:
        """Extract numeric price from strings like '₹125.45' or '$1.25'."""
        text = text.strip().replace(",", "")
        m = re.search(r"[\d]+\.?\d*", text)
        if m:
            return float(m.group())
        return None

    def _parse_results(self, html: str, qty: int, rate_inr: float) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # DigiKey renders a data table; try testid selectors first
        table = soup.find("table", {"data-testid": "search-results-table"})
        if not table:
            # Fallback: any product table
            table = soup.find("table", class_=re.compile("product", re.I))

        if not table:
            logger.warning("[DigiKey] No results table found in HTML.")
            return []

        rows = table.find_all("tr")[1:]  # skip header

        for row in rows[:5]:
            try:
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue

                # Part number
                pn_cell = row.find("td", {"data-testid": "part-number"}) or cells[0]
                vpn = pn_cell.get_text(strip=True)

                # Unit price at qty 1
                price_cell = row.find("td", {"data-testid": "unit-price"}) or cells[2]
                price_raw = price_cell.get_text(strip=True)
                price_val = self._parse_price(price_raw)
                if price_val is None:
                    continue

                # Check if price is already INR (₹) or USD ($)
                price_inr: float
                price_usd: float | None = None
                if "₹" in price_raw:
                    price_inr = price_val
                else:
                    price_usd = price_val
                    price_inr = round(price_val * rate_inr, 4)

                # Stock quantity
                stock_cell = row.find("td", {"data-testid": "quantity-available"}) or cells[3]
                stock_text = stock_cell.get_text(strip=True).replace(",", "")
                try:
                    stock = int(re.sub(r"[^\d]", "", stock_text) or "0")
                except ValueError:
                    stock = 0

                # MOQ
                moq_cell = row.find("td", {"data-testid": "minimum-quantity"})
                moq = 1
                if moq_cell:
                    try:
                        moq = int(re.sub(r"[^\d]", "", moq_cell.get_text(strip=True)) or "1")
                    except ValueError:
                        pass

                avail = "In Stock" if stock > 0 else "Out of Stock"

                # Datasheet
                ds_link = row.find("a", href=re.compile(r"datasheet|\.pdf", re.I))
                datasheet = ds_link["href"] if ds_link else None

                results.append({
                    "vendor": "DigiKey",
                    "vendor_part_number": vpn,
                    "unit_price_inr": price_inr,
                    "unit_price_usd": price_usd,
                    "price_breaks": [],         # populated by detail page if needed
                    "stock_qty": stock,
                    "availability": avail,
                    "moq": moq,
                    "lead_time_weeks": None,
                    "datasheet_url": datasheet,
                    "scraped_at": datetime.utcnow().isoformat(),
                })

            except Exception as exc:
                logger.warning("[DigiKey] Row parse error: %s", exc)
                continue

        return results
