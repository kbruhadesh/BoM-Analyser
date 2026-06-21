"""
arrow_scraper.py — Arrow Electronics scraper via their public JSON API.
Arrow ships to India; prices in USD, converted to INR.
"""
import json
import logging
from datetime import datetime

from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

ARROW_API = "https://www.arrow.com/api/v1/parts"


class ArrowScraper(BaseScraper):
    VENDOR_NAME = "Arrow"
    BASE_DOMAIN = "www.arrow.com"

    async def search(self, mpn: str, qty: int, rate_inr: float) -> list[dict]:
        cached = self._get_cache(mpn)
        if cached:
            logger.debug("[Arrow] Cache hit for %s", mpn)
            cached_data = json.loads(cached)
            return self._apply_rate(cached_data, rate_inr)

        data = await self._get_json(
            ARROW_API,
            params={"q": mpn, "region": "IN", "currencyCode": "USD", "pageSize": 5},
            headers={
                "Referer": "https://www.arrow.com/",
                "Origin": "https://www.arrow.com",
            },
        )

        if not data:
            return []

        parts = data if isinstance(data, list) else data.get("parts", [])
        results = []

        for part in parts[:5]:
            try:
                vpn = part.get("partNumber") or part.get("itemId") or ""
                if not vpn:
                    continue

                # Pricing tiers
                tiers = (
                    part.get("pricingTiers") or
                    part.get("prices") or
                    []
                )
                price_usd = None
                breaks = []
                for tier in tiers:
                    tier_qty = int(tier.get("minQuantity") or tier.get("qty") or 1)
                    tier_price = float(tier.get("unitPrice") or tier.get("price") or 0)
                    if tier_price <= 0:
                        continue
                    breaks.append({"qty": tier_qty, "price_usd": tier_price})
                    if tier_qty <= qty:
                        price_usd = tier_price

                if price_usd is None and breaks:
                    price_usd = breaks[0]["price_usd"]

                if price_usd is None:
                    continue

                price_inr = round(price_usd * rate_inr, 4)
                breaks_inr = [
                    {"qty": b["qty"], "price_inr": round(b["price_usd"] * rate_inr, 4), "price_usd": b["price_usd"]}
                    for b in breaks
                ]

                # Inventory
                inv = part.get("inventory") or {}
                stock = int(inv.get("quantity") or inv.get("qty") or 0)
                avail = "In Stock" if stock > 0 else "Out of Stock"
                moq = int(inv.get("minOrderQty") or 1)

                # Lead time
                lt = part.get("leadTimeDays")
                lt_weeks = round(int(lt) / 7) if lt else None

                results.append({
                    "vendor": "Arrow",
                    "vendor_part_number": vpn,
                    "unit_price_inr": price_inr,
                    "unit_price_usd": price_usd,
                    "price_breaks": breaks_inr,
                    "stock_qty": stock,
                    "availability": avail,
                    "moq": moq,
                    "lead_time_weeks": lt_weeks,
                    "datasheet_url": part.get("datasheetUrl"),
                    "scraped_at": datetime.utcnow().isoformat(),
                })

            except Exception as exc:
                logger.warning("[Arrow] Part parse error: %s", exc)
                continue

        if results:
            self._set_cache(mpn, json.dumps(results))

        return results

    def _apply_rate(self, cached: list[dict], rate: float) -> list[dict]:
        out = []
        for r in cached:
            r = dict(r)
            usd = r.get("unit_price_usd")
            if usd:
                r["unit_price_inr"] = round(float(usd) * rate, 4)
            for b in r.get("price_breaks", []):
                if "price_usd" in b:
                    b["price_inr"] = round(float(b["price_usd"]) * rate, 4)
            out.append(r)
        return out
