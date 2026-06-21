# BoM Analyzer — Backend

> **Bill of Materials price analysis & vendor optimization for Indian electronics procurement.**  
> All prices displayed and exported in **Indian Rupees (₹ INR)**. Live USD→INR rates fetched automatically.

---

## Vendors Supported

| Vendor | Region | Price Currency | Method |
|--------|--------|----------------|--------|
| **LCSC** | Global / ships India | USD → INR | Public JSON API (no key) |
| **DigiKey** | digikey.in | INR native | Playwright |
| **Mouser** | in.mouser.com | INR native | Playwright + stealth |
| **Arrow** | arrow.com | USD → INR | Partner JSON API |
| **Robu.in** | India 🇮🇳 | INR native | Playwright |
| **Evelta** | India 🇮🇳 | INR native | Playwright |

> **Why LCSC first?** LCSC has a public JSON search endpoint (`wmsc.lcsc.com/ftps/wdSearch`) that requires no API key and no browser — fastest and most reliable for the initial pipeline test.

---

## Quick Start

### 1. Clone & install

```bash
cd backend/
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium          # headless browser for scraping
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — set DATABASE_URL and REDIS_URL if not using defaults
```

### 3. Start Redis (needed for Celery + price cache)

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

### 4. Run services

```bash
# Terminal 1 — FastAPI
uvicorn main:app --reload --port 8000

# Terminal 2 — Celery worker
celery -A tasks worker --loglevel=info --concurrency=4

# (Optional) Terminal 3 — Flower task monitor
celery -A tasks flower --port=5555
```

### 5. Or use Docker Compose (recommended)

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Flower (Celery monitor) | http://localhost:5555 |
| Frontend | http://localhost:3000 |

---

## API Reference

### Submit BoM
```
POST /api/bom/analyze
Content-Type: application/json

{
  "bom_text": "Qty,MPN,Description,Manufacturer,Ref\n10,ATmega328P-PU,8-bit MCU,Microchip,U1",
  "format": "auto"
}
```
Returns: `{ "task_id": "uuid4" }`

### Poll status
```
GET /api/bom/status/{task_id}
```
Returns: `{ "status": "pending|processing|complete|failed", "progress": 0-100, "current_component": "..." }`

### Get results (INR)
```
GET /api/bom/result/{task_id}
```
Returns full analysis with `best_unit_price_inr`, `best_total_price_inr`, `savings_vs_worst_inr`.

### Export
```
GET /api/bom/export/{task_id}?format=json   # JSON download
GET /api/bom/export/{task_id}?format=excel  # .xlsx with ₹ formatting
```

### Normalize MPN
```
POST /api/components/normalize
{ "mpn": "ATmega328P-PU" }
→ { "normalized": "ATmega328P", "confidence": 0.97 }
```

### Live FX Rate
```
GET /api/fx/rate
→ { "from": "USD", "to": "INR", "rate": 83.52 }
```

---

## Currency Handling

- Live USD→INR rate fetched from `open.er-api.com` (free, no key needed)
- Rate cached in Redis for **1 hour** (`fx:usd_inr`)
- Fallback hardcoded to ₹83.5 if fetch fails
- All DB storage and API responses use INR
- Excel export: ₹ symbol with `₹#,##0.00` number format

---

## Weighted Scoring Formula

```
score = 0.50 × price_score        # lower price → higher score (inverted after normalization)
      + 0.30 × stock_adequacy     # stock ≥ qty → 1.0
      + 0.15 × moq_fit            # moq ≤ qty → 1.0
      + 0.05 × lead_time_score    # in_stock → 1.0
```

Split-order: if no single vendor covers full qty, greedy bin-packing fills from cheapest in-stock vendors first.

---

## Running Tests

```bash
pip install pytest pytest-asyncio
pytest tests/test_backend.py -v
```

Test coverage:
- BoM parser (CSV/TSV/text/fuzzy headers/edge cases): **10 tests**
- MPN normalizer (suffixes/aliases/Indian market parts): **12 tests**
- Cost optimizer (scoring/savings/split-order/MOQ penalty): **8 tests**
- Currency converter (roundtrip/fallback): **4 tests**
- LCSC scraper mock: **2 tests**
- Excel exporter (bytes/sheets/data): **4 tests**
- FastAPI endpoints (health/normalize/analyze/errors): **7 tests**

---

## File Structure

```
backend/
├── main.py                  ← FastAPI routes
├── models.py                ← SQLAlchemy ORM (BomTask, VendorResult, etc.)
├── schemas.py               ← Pydantic request/response schemas
├── tasks.py                 ← Celery async pipeline
├── currency.py              ← Live USD→INR + caching
├── parser/
│   ├── bom_parser.py        ← CSV/XLSX/TSV/text parser + fuzzy header matching
│   └── normalizer.py        ← MPN normalizer + alias table (Indian market aliases included)
├── scrapers/
│   ├── base_scraper.py      ← Playwright + rate-limiting + robots.txt + Redis cache
│   ├── lcsc_scraper.py      ← LCSC JSON API (no auth)
│   ├── digikey_scraper.py   ← DigiKey India Playwright scraper
│   ├── mouser_scraper.py    ← Mouser India stealth scraper
│   ├── arrow_scraper.py     ← Arrow JSON API
│   ├── robu_scraper.py      ← Robu.in (WooCommerce) 🇮🇳
│   └── evelta_scraper.py    ← Evelta.com (WooCommerce) 🇮🇳
├── optimizer/
│   └── cost_optimizer.py    ← Weighted scoring + split-order greedy packing
├── exporter/
│   └── excel_exporter.py    ← 3-sheet .xlsx with ₹ formatting + conditional highlighting
└── tests/
    └── test_backend.py      ← 47 unit + integration tests
```

---

## Enterprise Compliance

- ✅ All prices cached in Redis (TTL 4h per component/vendor pair)
- ✅ Rate-limiting: 1.5–3s random delay between requests per domain
- ✅ No credentials in code — `.env` only (see `.env.example`)
- ✅ `robots.txt` fetched and parsed before scraping each domain
- ✅ Audit log in SQLite/Postgres for every scrape (timestamp, URL, cache hit, error)
- ✅ Playwright headless — no GUI needed, runs in Docker
- ✅ RPA fallback: after 3 failed attempts → "manual lookup required"
- ✅ All data on-premise — no cloud dependency
