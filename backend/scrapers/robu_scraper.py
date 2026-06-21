"""
robu_scraper.py — Robu.in scraper (Indian electronics marketplace).
Robu is one of India's largest component suppliers and shows INR natively.
Uses their search page via Playwright.
"""
import re
import json
import logging
from datetime import datetime
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://robu.in/?s={mpn}&post_type=product"


class RobuScraper(BaseScraper):
    VENDOR_NAME = "Robu"
    BASE_DOMAIN = "robu.in"

    async def search(self, mpn: str, qty: int, rate_inr: float) -> list[dict]:
        cached = self._get_cache(mpn)
        if cached:
            logger.debug("[Robu] Cache hit for %s", mpn)
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

        # WooCommerce product cards
        products = (
            soup.select("li.product") or
            soup.select(".product-item") or
            soup.select("article.product")
        )

        for prod in products[:5]:
            try:
                # Product name / VPN
                name_el = (
                    prod.select_one("h2.woocommerce-loop-product__title") or
                    prod.select_one(".product-title") or
                    prod.select_one("h2") or
                    prod.select_one("h3")
                )
                if not name_el:
                    continue
                vpn = name_el.get_text(strip=True)[:80]

                # Price — WooCommerce uses .price > .amount > bdi for INR
                price_el = prod.select_one(".price .amount bdi") or prod.select_one(".price .amount") or prod.select_one(".price")
                if not price_el:
                    continue
                price_inr = self._parse_price_inr(price_el.get_text(strip=True))
                if price_inr is None:
                    continue

                # Stock status
                stock_el = prod.select_one(".in-stock, .out-of-stock, .stock")
                if stock_el and "out-of-stock" in stock_el.get("class", []):
                    avail = "Out of Stock"
                    stock = 0
                else:
                    avail = "In Stock"
                    stock = 9999  # Robu doesn't show exact qty on listing

                # MOQ is typically 1 on Robu
                moq = 1

                # Product URL for datasheet
                link_el = prod.select_one("a.woocommerce-loop-product__link, a[href]")
                product_url = link_el["href"] if link_el else None

                results.append({
                    "vendor": "Robu",
                    "vendor_part_number": vpn,
                    "unit_price_inr": price_inr,
                    "unit_price_usd": None,
                    "price_breaks": [],          # Robu shows single price
                    "stock_qty": stock,
                    "availability": avail,
                    "moq": moq,
                    "lead_time_weeks": None,
                    "datasheet_url": product_url,
                    "scraped_at": datetime.utcnow().isoformat(),
                })

            except Exception as exc:
                logger.warning("[Robu] Product parse error: %s", exc)
                continue

        return results
