"""
currency.py — USD → INR conversion with live rate fallback.
Caches the exchange rate in Redis for 1 hour.
"""
import os
import json
import logging
import httpx

logger = logging.getLogger(__name__)

FALLBACK_USD_INR = 83.5          # Reasonable 2024-25 fallback rate
CACHE_KEY = "fx:usd_inr"
CACHE_TTL = 3600                 # 1 hour


def _redis_client():
    try:
        import redis
        return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
    except Exception:
        return None


def get_usd_inr_rate() -> float:
    """
    Fetch live USD→INR rate. Sources tried in order:
    1. Redis cache
    2. exchangerate-api (free tier, no key needed for basic endpoint)
    3. Fallback constant
    """
    r = _redis_client()

    # 1. Cache hit
    if r:
        try:
            cached = r.get(CACHE_KEY)
            if cached:
                return float(cached)
        except Exception:
            pass

    # 2. Live fetch (free, no API key)
    try:
        resp = httpx.get(
            "https://open.er-api.com/v6/latest/USD",
            timeout=5.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            rate = float(data["rates"]["INR"])
            if r:
                try:
                    r.setex(CACHE_KEY, CACHE_TTL, str(rate))
                except Exception:
                    pass
            logger.info("Live USD/INR rate: %.2f", rate)
            return rate
    except Exception as exc:
        logger.warning("Could not fetch live FX rate: %s — using fallback %.2f", exc, FALLBACK_USD_INR)

    return FALLBACK_USD_INR


def usd_to_inr(usd_price: float, rate: float | None = None) -> float:
    if rate is None:
        rate = get_usd_inr_rate()
    return round(usd_price * rate, 4)


def inr_to_usd(inr_price: float, rate: float | None = None) -> float:
    if rate is None:
        rate = get_usd_inr_rate()
    return round(inr_price / rate, 4)
