"""
evelta_scraper.py — Evelta.com scraper.
Evelta is a popular Indian electronics component supplier showing INR prices.
Uses Playwright since they run a standard WooCommerce/Shopify-style store.
"""
import re
import json
import logging
from datetime import datetime
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://evelta.com/?s={mpn}&post_type=product"


class EveltaScraper(BaseScraper):
    VENDOR_NAME = "Evelta"
    BASE_DOMAIN = "evelta.com"

    async def search(self, mpn: str, qty: int, rate_inr: float) -> list[dict]:
        cached = self._get_cache(mpn)
        if cached:
            logger.debug("[Evelta] Cache hit for %s", mpn)
            return json.loads(cached)

        url = SEARCH_URL.format(mpn=mpn)
        html = await self._get_page(
            url,
            wait_selector=".products, .product, .woocommerce-loop-product",
        )
        if not html:
            return []

        results = self._parse_results(html, qty)
        if results:
            self._set_cache(mpn, json.dumps(results))
        return results

    def _parse_price_inr(self, text: str) -> float | None:
        text = re.sub(r"[₹\s,]", "", text)
        m = re.search(r"[\d]+\.?\d*", text)
        return float(m.group()) if m else None

    def _parse_results(self, html: str, qty: int) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        results = []

        products = (
            soup.select("li.product") or
            soup.select(".product-item") or
            soup.select("article.product")
        )

        for prod in products[:5]:
            try:
                name_el = (
                    prod.select_one("h2.woocommerce-loop-product__title") or
                    prod.select_one(".product-title") or
                    prod.select_one("h2") or
                    prod.select_one("h3")
                )
                if not name_el:
                    continue
                vpn = name_el.get_text(strip=True)[:80]

                price_el = (
                    prod.select_one(".price ins .amount") or   # sale price
                    prod.select_one(".price .amount bdi") or
                    prod.select_one(".price .amount") or
                    prod.select_one(".price")
                )
                if not price_el:
                    continue
                price_inr = self._parse_price_inr(price_el.get_text(strip=True))
                if price_inr is None:
                    continue

                stock_el = prod.select_one(".stock")
                if stock_el and "out-of-stock" in " ".join(stock_el.get("class", [])):
                    avail, stock = "Out of Stock", 0
                else:
                    avail, stock = "In Stock", 9999

                link_el = prod.select_one("a[href]")
                product_url = link_el["href"] if link_el else None

                results.append({
                    "vendor": "Evelta",
                    "vendor_part_number": vpn,
                    "unit_price_inr": price_inr,
                    "unit_price_usd": None,
                    "price_breaks": [],
                    "stock_qty": stock,
                    "availability": avail,
                    "moq": 1,
                    "lead_time_weeks": None,
                    "datasheet_url": product_url,
                    "scraped_at": datetime.utcnow().isoformat(),
                })
            except Exception as exc:
                logger.warning("[Evelta] Product parse error: %s", exc)
                continue

        return results
