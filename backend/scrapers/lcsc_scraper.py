"""
lcsc_scraper.py — LCSC scraper using their public search JSON API.
No API key required. Returns prices converted to INR.
LCSC ships to India directly; prices in USD, convert to INR.
"""
import json
import logging
from datetime import datetime

from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://wmsc.lcsc.com/ftps/wdSearch"
PRODUCT_URL_BASE = "https://www.lcsc.com/product-detail"


class LCSCScraper(BaseScraper):
    VENDOR_NAME = "LCSC"
    BASE_DOMAIN = "wmsc.lcsc.com"

    async def search(self, mpn: str, qty: int, rate_inr: float) -> list[dict]:
        # ── Cache check ────────────────────────────────────────────────────────
        cached = self._get_cache(mpn)
        if cached:
            logger.debug("[LCSC] Cache hit for %s", mpn)
            results = json.loads(cached)
            # Re-convert to INR with current rate
            return self._apply_rate(results, rate_inr)

        data = await self._get_json(
            SEARCH_URL,
            params={"keyword": mpn, "page": 1, "pageSize": 10},
            headers={"Referer": "https://www.lcsc.com/"},
        )

        if not data:
            return []

        try:
            products = (
                data.get("result", {})
                    .get("productSearchResultVO", {})
                    .get("productList", [])
            )
        except (AttributeError, KeyError):
            return []

        results = []
        for p in products[:5]:  # top 5 results
            try:
                vpn = str(p.get("productModel") or p.get("productCode") or "")
                if not vpn:
                    continue

                stock = int(p.get("stockNumber") or p.get("stockCount") or 0)
                moq = int(p.get("minBuyNumber") or p.get("minOrderQty") or 1)
                avail = "In Stock" if stock > 0 else "Out of Stock"
                datasheet = p.get("pdfUrl") or p.get("dataSheetUrl")

                # Price from productPriceList or minImage (fallback)
                price_list = p.get("productPriceList") or p.get("priceTiers") or []
                price_usd = None
                breaks_raw = []

                if price_list:
                    for tier in price_list:
                        tier_qty = int(tier.get("ladder") or tier.get("quantity") or 1)
                        tier_usd = float(tier.get("usdPrice") or tier.get("price") or 0)
                        if tier_usd <= 0:
                            continue
                        breaks_raw.append({"qty": tier_qty, "price_usd": tier_usd})
                        # Price at requested qty: highest ladder that doesn't exceed qty
                        if tier_qty <= qty:
                            price_usd = tier_usd

                    if price_usd is None and breaks_raw:
                        price_usd = breaks_raw[0]["price_usd"]
                else:
                    # Fallback: minImage field (sometimes holds unit price as string)
                    raw_price = p.get("minImage") or p.get("unitPrice")
                    if raw_price:
                        try:
                            price_usd = float(str(raw_price).replace("$", "").strip())
                        except ValueError:
                            pass

                if price_usd is None:
                    continue

                price_inr = round(price_usd * rate_inr, 4)
                breaks_inr = [
                    {
                        "qty": b["qty"],
                        "price_inr": round(b["price_usd"] * rate_inr, 4),
                        "price_usd": b["price_usd"],
                    }
                    for b in breaks_raw
                ]

                results.append({
                    "vendor": "LCSC",
                    "vendor_part_number": vpn,
                    "unit_price_inr": price_inr,
                    "unit_price_usd": price_usd,
                    "price_breaks": breaks_inr,
                    "stock_qty": stock,
                    "availability": avail,
                    "moq": moq,
                    "lead_time_weeks": None,
                    "datasheet_url": datasheet,
                    "scraped_at": datetime.utcnow().isoformat(),
                })

            except Exception as exc:
                logger.warning("[LCSC] Failed to parse product: %s", exc)
                continue

        # Cache raw USD results (rate-agnostic)
        if results:
            cache_payload = [
                {**r, "unit_price_inr": r["unit_price_usd"], "price_breaks": [
                    {**b, "price_inr": b["price_usd"]} for b in r["price_breaks"]
                ]}
                for r in results
            ]
            self._set_cache(mpn, json.dumps(cache_payload))

        return results

    def _apply_rate(self, cached_results: list[dict], rate: float) -> list[dict]:
        """Re-apply INR rate to cached USD data."""
        out = []
        for r in cached_results:
            r = dict(r)
            usd = r.get("unit_price_usd") or r.get("unit_price_inr")
            if usd:
                r["unit_price_inr"] = round(float(usd) * rate, 4)
            for b in r.get("price_breaks", []):
                usd_b = b.get("price_usd") or b.get("price_inr")
                if usd_b:
                    b["price_inr"] = round(float(usd_b) * rate, 4)
            out.append(r)
        return out
