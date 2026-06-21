"""
tasks.py — Celery async tasks for BoM analysis pipeline.
Windows-compatible: uses 'solo' pool to avoid prefork child-process import errors.
"""
import os
import sys
import asyncio
import logging
from datetime import datetime

from celery import Celery
from celery.signals import worker_process_init

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "bom_analyzer",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

# ── Detect Windows and choose the right pool ──────────────────────────────────
_ON_WINDOWS = sys.platform == "win32"

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="Asia/Kolkata",
    enable_utc=True,

    # Tracking
    task_track_started=True,
    result_expires=86400,       # 24 h

    # ── Windows fix: solo pool avoids prefork child import errors ─────────────
    # On Linux/Mac this stays as prefork (default, more performant).
    worker_pool="solo" if _ON_WINDOWS else "prefork",

    # Fix the CPendingDeprecationWarning shown in the logs
    broker_connection_retry_on_startup=True,

    # Windows: one worker is enough with solo pool
    worker_concurrency=1 if _ON_WINDOWS else (os.cpu_count() or 4),
)


# ── Windows asyncio policy fix ─────────────────────────────────────────────────
# Python 3.10+ on Windows defaults to ProactorEventLoop which breaks some
# async networking libs. Force SelectorEventLoop.
if _ON_WINDOWS:
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _get_db_session():
    from models import get_engine, get_session_factory
    db_url = os.getenv("DATABASE_URL", "sqlite:///./bom.db")
    engine = get_engine(db_url)
    factory = get_session_factory(engine)
    return factory()


def _update_task_status(
    task_id: str,
    status: str,
    progress: int,
    current_component: str | None = None,
    error: str | None = None,
) -> None:
    session = _get_db_session()
    try:
        from models import BomTask
        task = session.query(BomTask).filter_by(id=task_id).first()
        if task:
            task.status = status
            task.progress = progress
            task.current_component = current_component
            if error:
                task.error_message = error
            if status in ("complete", "failed"):
                task.completed_at = datetime.utcnow()
            session.commit()
    except Exception as exc:
        logger.error("Failed to update task status: %s", exc)
    finally:
        session.close()


async def _run_analysis(task_id: str, raw_input: str, fmt: str) -> None:
    """
    Async core: parse BoM → normalize → scrape all vendors → optimize → save.
    """
    from models import (
        BomItem, VendorResult, OptimizedResult, ScrapeAuditLog,
        get_engine, get_session_factory,
    )
    from parser.bom_parser import parse_bom
    from parser.normalizer import normalize_mpn
    from currency import get_usd_inr_rate
    from scrapers.lcsc_scraper import LCSCScraper
    from scrapers.digikey_scraper import DigiKeyScraper
    from scrapers.mouser_scraper import MouserScraper
    from scrapers.arrow_scraper import ArrowScraper
    from scrapers.robu_scraper import RobuScraper
    from optimizer.cost_optimizer import optimize

    db_url = os.getenv("DATABASE_URL", "sqlite:///./bom.db")
    engine = get_engine(db_url)
    Session = get_session_factory(engine)
    session = Session()

    try:
        # ── 1. Parse ──────────────────────────────────────────────────────────
        _update_task_status(task_id, "processing", 5, "Parsing BoM")
        items = parse_bom(raw_input, fmt)
        total = len(items)
        if total == 0:
            _update_task_status(
                task_id, "failed", 0,
                error="No components parsed from input."
            )
            return

        # ── 2. Live INR rate ───────────────────────────────────────────────────
        rate_inr = get_usd_inr_rate()
        logger.info("USD/INR rate: %.2f", rate_inr)

        # ── 3. Scrapers ────────────────────────────────────────────────────────
        scrapers = [
            LCSCScraper(),
            DigiKeyScraper(),
            MouserScraper(),
            ArrowScraper(),
            RobuScraper(),
        ]

        # ── 4. Per-component loop ─────────────────────────────────────────────
        for idx, item in enumerate(items):
            mpn = item.manufacturer_part_number or item.raw_description
            _update_task_status(
                task_id, "processing",
                progress=10 + int(80 * idx / total),
                current_component=mpn,
            )

            norm_result = normalize_mpn(mpn)
            search_mpn = norm_result.normalized_mpn or mpn

            bom_item = BomItem(
                task_id=task_id,
                line_number=item.line_number,
                quantity=item.quantity,
                raw_description=item.raw_description,
                manufacturer_part_number=mpn,
                normalized_mpn=search_mpn,
                normalization_confidence=norm_result.confidence,
                manufacturer=item.manufacturer,
                reference_designators=item.reference_designators,
                notes=item.notes,
            )
            session.add(bom_item)
            session.flush()

            # Run scrapers concurrently
            scrape_tasks = [
                s.search(search_mpn, item.quantity, rate_inr)
                for s in scrapers
            ]
            vendor_raw_lists = await asyncio.gather(
                *scrape_tasks, return_exceptions=True
            )

            all_vendor_results: list[dict] = []
            for s_idx, vendor_results in enumerate(vendor_raw_lists):
                vendor_name = scrapers[s_idx].VENDOR_NAME
                if isinstance(vendor_results, Exception):
                    logger.error(
                        "[%s] Scrape failed for %s: %s",
                        vendor_name, search_mpn, vendor_results,
                    )
                    session.add(ScrapeAuditLog(
                        task_id=task_id, vendor=vendor_name, url="",
                        mpn=search_mpn, error=str(vendor_results),
                        scraped_at=datetime.utcnow(),
                    ))
                    continue

                for vr in vendor_results:
                    all_vendor_results.append(vr)
                    session.add(VendorResult(
                        bom_item_id=bom_item.id,
                        vendor=vr["vendor"],
                        vendor_part_number=vr.get("vendor_part_number", ""),
                        unit_price_inr=vr.get("unit_price_inr", 0),
                        unit_price_usd=vr.get("unit_price_usd"),
                        price_breaks_json=vr.get("price_breaks", []),
                        stock_qty=vr.get("stock_qty", 0),
                        availability=vr.get("availability", "Unknown"),
                        moq=vr.get("moq", 1),
                        lead_time_weeks=vr.get("lead_time_weeks"),
                        datasheet_url=vr.get("datasheet_url"),
                    ))
                    session.add(ScrapeAuditLog(
                        task_id=task_id, vendor=vendor_name, url="",
                        mpn=search_mpn, response_status=200,
                        scraped_at=datetime.utcnow(),
                    ))

            opt = optimize(
                component=mpn,
                normalized_mpn=search_mpn,
                vendor_results=all_vendor_results,
                qty=item.quantity,
            )

            session.add(OptimizedResult(
                task_id=task_id,
                component=mpn,
                normalized_mpn=search_mpn,
                quantity_required=item.quantity,
                best_vendor=opt.best_vendor,
                best_unit_price_inr=opt.best_unit_price_inr,
                best_total_price_inr=opt.best_total_price_inr,
                availability=opt.availability,
                moq=opt.moq,
                alternatives_json=opt.alternatives,
                savings_vs_worst_inr=opt.savings_vs_worst_inr,
                recommendation_reason=opt.recommendation_reason,
                all_vendors_json=all_vendor_results,
            ))

            session.commit()

        # ── 5. Complete ───────────────────────────────────────────────────────
        _update_task_status(task_id, "complete", 100)
        logger.info("Task %s complete: %d components analyzed.", task_id, total)

    except Exception as exc:
        logger.exception("Task %s failed: %s", task_id, exc)
        session.rollback()
        _update_task_status(task_id, "failed", 0, error=str(exc))
    finally:
        session.close()


@celery_app.task(name="tasks.analyze_bom", bind=True, max_retries=1)
def analyze_bom(self, task_id: str, raw_input: str, fmt: str) -> dict:
    """
    Celery task entry point.
    Creates a fresh event loop per task — required on Windows with solo pool.
    """
    try:
        # Always create a brand-new event loop for this task invocation.
        # On Windows with SelectorEventLoopPolicy this avoids ProactorEventLoop
        # conflicts when Celery reuses worker processes.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run_analysis(task_id, raw_input, fmt))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        return {"task_id": task_id, "status": "complete"}

    except Exception as exc:
        logger.exception("Celery task crashed: %s", exc)
        _update_task_status(task_id, "failed", 0, error=str(exc))
        raise self.retry(exc=exc, countdown=5)
