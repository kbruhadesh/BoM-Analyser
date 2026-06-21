"""
main.py — FastAPI entry point for BoM Analyzer.
All monetary values in Indian Rupees (INR).
"""
import os
import uuid
import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from sqlalchemy.orm import Session

from models import (
    BomTask, BomItem, OptimizedResult, ScrapeAuditLog,
    init_db, get_engine, get_session_factory,
)
from schemas import (
    BomAnalyzeRequest, NormalizeRequest,
    TaskCreatedResponse, TaskStatusResponse,
    AnalysisResultResponse, AnalysisSummary,
    OptimizedResultSchema, VendorResultSchema, PriceBreak,
    NormalizeResponse,
)
from tasks import analyze_bom
from currency import get_usd_inr_rate
from parser.normalizer import normalize_mpn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── App setup ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="BoM Analyzer API",
    description="Bill of Materials price analysis & vendor optimization — prices in INR",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bom.db")
engine = init_db(DATABASE_URL)
SessionLocal = get_session_factory(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _orm_to_optimized_schema(orm_result: OptimizedResult) -> OptimizedResultSchema:
    """Convert ORM OptimizedResult → Pydantic schema."""
    raw_vendors = orm_result.all_vendors_json or []
    vendor_schemas = []
    for v in raw_vendors:
        breaks = [
            PriceBreak(qty=b["qty"], price_inr=b.get("price_inr", 0), price_usd=b.get("price_usd"))
            for b in v.get("price_breaks", [])
        ]
        vendor_schemas.append(VendorResultSchema(
            vendor=v.get("vendor", ""),
            vendor_part_number=v.get("vendor_part_number", ""),
            unit_price_inr=v.get("unit_price_inr", 0),
            unit_price_usd=v.get("unit_price_usd"),
            price_breaks=breaks,
            stock_qty=v.get("stock_qty", 0),
            availability=v.get("availability", "Unknown"),
            moq=v.get("moq", 1),
            lead_time_weeks=v.get("lead_time_weeks"),
            datasheet_url=v.get("datasheet_url"),
        ))

    return OptimizedResultSchema(
        component=orm_result.component,
        normalized_mpn=orm_result.normalized_mpn,
        quantity_required=orm_result.quantity_required,
        best_vendor=orm_result.best_vendor,
        best_unit_price_inr=orm_result.best_unit_price_inr,
        best_total_price_inr=orm_result.best_total_price_inr,
        availability=orm_result.availability,
        moq=orm_result.moq,
        all_vendors=vendor_schemas,
        alternatives=orm_result.alternatives_json or [],
        savings_vs_worst_inr=orm_result.savings_vs_worst_inr or 0.0,
        recommendation_reason=orm_result.recommendation_reason,
    )


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", tags=["health"])
def root():
    return {"status": "ok", "service": "BoM Analyzer", "currency": "INR"}


@app.get("/health", tags=["health"])
def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/bom/analyze", response_model=TaskCreatedResponse, tags=["bom"])
def analyze(request: BomAnalyzeRequest, db: Session = Depends(get_db)):
    """
    Submit a BoM for analysis. Returns a task_id to poll for status.
    """
    if not request.bom_text.strip():
        raise HTTPException(status_code=400, detail="bom_text must not be empty.")

    task_id = str(uuid.uuid4())

    # Persist task record
    task = BomTask(
        id=task_id,
        status="pending",
        progress=0,
        raw_input=request.bom_text,
        input_format=request.format,
    )
    db.add(task)
    db.commit()

    # Dispatch Celery task
    analyze_bom.delay(task_id, request.bom_text, request.format)
    logger.info("Task %s queued.", task_id)

    return TaskCreatedResponse(task_id=task_id)


@app.get("/api/bom/status/{task_id}", response_model=TaskStatusResponse, tags=["bom"])
def get_status(task_id: str, db: Session = Depends(get_db)):
    task = db.query(BomTask).filter_by(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found.")
    return TaskStatusResponse(
        task_id=task_id,
        status=task.status,
        progress=task.progress,
        current_component=task.current_component,
        error_message=task.error_message,
    )


@app.get("/api/bom/result/{task_id}", response_model=AnalysisResultResponse, tags=["bom"])
def get_result(task_id: str, db: Session = Depends(get_db)):
    task = db.query(BomTask).filter_by(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found.")
    if task.status != "complete":
        raise HTTPException(status_code=202, detail=f"Task status: {task.status}")

    orm_results = db.query(OptimizedResult).filter_by(task_id=task_id).all()
    result_schemas = [_orm_to_optimized_schema(r) for r in orm_results]

    # Build summary
    total_cost = sum(r.best_total_price_inr or 0 for r in orm_results)
    total_savings = sum(r.savings_vs_worst_inr or 0 for r in orm_results)
    in_stock = sum(1 for r in orm_results if r.availability == "In Stock")
    oos = sum(1 for r in orm_results if r.availability == "Out of Stock")

    # Most used best vendor
    from collections import Counter
    vendor_counts = Counter(r.best_vendor for r in orm_results if r.best_vendor)
    cheapest_vendor = vendor_counts.most_common(1)[0][0] if vendor_counts else None

    rate = get_usd_inr_rate()

    return AnalysisResultResponse(
        task_id=task_id,
        analyzed_at=task.completed_at or datetime.utcnow(),
        summary=AnalysisSummary(
            total_components=len(orm_results),
            total_estimated_cost_inr=round(total_cost, 2),
            total_savings_inr=round(total_savings, 2),
            components_in_stock=in_stock,
            components_out_of_stock=oos,
            cheapest_vendor_overall=cheapest_vendor,
            usd_inr_rate=rate,
        ),
        results=result_schemas,
    )


@app.get("/api/bom/export/{task_id}", tags=["bom"])
def export_results(task_id: str, format: str = "json", db: Session = Depends(get_db)):
    """
    Download analysis results.
    format: 'json' | 'excel'
    """
    task = db.query(BomTask).filter_by(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.status != "complete":
        raise HTTPException(status_code=202, detail="Analysis not yet complete.")

    orm_results = db.query(OptimizedResult).filter_by(task_id=task_id).all()

    if format == "excel":
        from exporter.excel_exporter import export_to_excel
        audit = db.query(ScrapeAuditLog).filter_by(task_id=task_id).all()
        audit_dicts = [
            {
                "component": a.mpn,
                "vendor": a.vendor,
                "scraped_at": a.scraped_at.isoformat() if a.scraped_at else "",
                "vendors_queried": a.vendor,
                "cache_hit": a.cache_hit,
                "status": "OK" if not a.error else "ERROR",
                "error": a.error or "",
            }
            for a in audit
        ]
        rate = get_usd_inr_rate()
        results_dicts = [
            {
                "normalized_mpn": r.normalized_mpn,
                "component": r.component,
                "quantity_required": r.quantity_required,
                "best_vendor": r.best_vendor,
                "best_unit_price_inr": r.best_unit_price_inr,
                "best_total_price_inr": r.best_total_price_inr,
                "availability": r.availability,
                "moq": r.moq,
                "savings_vs_worst_inr": r.savings_vs_worst_inr,
                "recommendation_reason": r.recommendation_reason,
                "all_vendors": r.all_vendors_json or [],
            }
            for r in orm_results
        ]
        xlsx_bytes = export_to_excel(results_dicts, task_id, rate, audit_dicts)
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=bom-analysis-{task_id[:8]}.xlsx"},
        )

    # Default: JSON
    schemas = [_orm_to_optimized_schema(r) for r in orm_results]
    return JSONResponse(
        content={
            "task_id": task_id,
            "currency": "INR",
            "analyzed_at": (task.completed_at or datetime.utcnow()).isoformat(),
            "total_components": len(schemas),
            "results": [s.model_dump() for s in schemas],
        }
    )


@app.post("/api/components/normalize", response_model=NormalizeResponse, tags=["components"])
def normalize(request: NormalizeRequest):
    """Normalize a single MPN and return the canonical form + confidence."""
    result = normalize_mpn(request.mpn)
    return NormalizeResponse(
        original=request.mpn,
        normalized=result.normalized_mpn,
        confidence=result.confidence,
        aliases_applied=result.aliases_applied,
    )


@app.get("/api/fx/rate", tags=["utility"])
def fx_rate():
    """Return the current USD → INR exchange rate."""
    rate = get_usd_inr_rate()
    return {"from": "USD", "to": "INR", "rate": rate, "fetched_at": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
