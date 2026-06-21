from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Input schemas ──────────────────────────────────────────────────────────────

class BomAnalyzeRequest(BaseModel):
    bom_text: str = Field(..., description="Raw BoM content (CSV / TSV / plain text)")
    format: str = Field("auto", description="csv | text | xlsx_base64 | auto")


class NormalizeRequest(BaseModel):
    mpn: str


# ── Internal data models ───────────────────────────────────────────────────────

class BomItemSchema(BaseModel):
    line_number: int
    quantity: int
    raw_description: str
    manufacturer_part_number: Optional[str] = None
    manufacturer: Optional[str] = None
    reference_designators: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class PriceBreak(BaseModel):
    qty: int
    price_inr: float
    price_usd: Optional[float] = None


class VendorResultSchema(BaseModel):
    vendor: str
    vendor_part_number: str
    unit_price_inr: float
    unit_price_usd: Optional[float] = None
    price_breaks: list[PriceBreak] = []
    stock_qty: int
    availability: str          # "In Stock" | "Out of Stock" | "On Order"
    moq: int
    lead_time_weeks: Optional[int] = None
    datasheet_url: Optional[str] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class OptimizedResultSchema(BaseModel):
    component: str
    normalized_mpn: str
    quantity_required: int
    best_vendor: Optional[str]
    best_unit_price_inr: Optional[float]
    best_total_price_inr: Optional[float]
    availability: str
    moq: Optional[int]
    all_vendors: list[VendorResultSchema] = []
    alternatives: list[dict] = []
    savings_vs_worst_inr: float = 0.0
    recommendation_reason: Optional[str]

    class Config:
        from_attributes = True


# ── API response schemas ───────────────────────────────────────────────────────

class TaskCreatedResponse(BaseModel):
    task_id: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str           # pending|processing|complete|failed
    progress: int         # 0-100
    current_component: Optional[str] = None
    error_message: Optional[str] = None


class AnalysisSummary(BaseModel):
    total_components: int
    total_estimated_cost_inr: float
    total_savings_inr: float
    components_in_stock: int
    components_out_of_stock: int
    cheapest_vendor_overall: Optional[str]
    currency: str = "INR"
    usd_inr_rate: float


class AnalysisResultResponse(BaseModel):
    task_id: str
    analyzed_at: datetime
    summary: AnalysisSummary
    results: list[OptimizedResultSchema]


class NormalizeResponse(BaseModel):
    original: str
    normalized: str
    confidence: float
    aliases_applied: list[str] = []
