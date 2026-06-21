"""
cost_optimizer.py — Vendor selection + split-order logic.
All prices in INR. Weighted scoring: price 50%, stock 30%, MOQ 15%, lead_time 5%.
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VendorScore:
    vendor_name: str
    unit_price_inr: float
    total_price_inr: float
    stock_qty: int
    moq: int
    availability: str
    score: float
    lead_time_weeks: Optional[int]
    vendor_part_number: str
    raw: dict


@dataclass
class OptimizationOutput:
    component: str
    normalized_mpn: str
    quantity_required: int
    best_vendor: Optional[str]
    best_unit_price_inr: Optional[float]
    best_total_price_inr: Optional[float]
    availability: str
    moq: Optional[int]
    all_vendors: list[dict]
    alternatives: list[dict] = field(default_factory=list)
    savings_vs_worst_inr: float = 0.0
    recommendation_reason: str = ""
    split_order: Optional[list[dict]] = None   # if no single vendor covers qty


def _normalize_scores(values: list[float]) -> list[float]:
    """Min-max normalize a list of floats to [0, 1]. All-equal → all 1.0."""
    mn, mx = min(values), max(values)
    if mx == mn:
        return [1.0] * len(values)
    return [(v - mn) / (mx - mn) for v in values]


def score_vendors(
    vendor_results: list[dict],
    qty: int,
) -> list[VendorScore]:
    """
    Score each vendor result using weighted criteria:
      price      weight=0.50  lower = better → invert after normalization
      stock      weight=0.30  stock ≥ qty = 1.0, else stock/qty
      moq_fit    weight=0.15  moq ≤ qty = 1.0, else qty/moq
      lead_time  weight=0.05  in_stock=1.0, <4wk=0.5, else=0.0
    """
    if not vendor_results:
        return []

    # Filter out completely unusable results
    usable = [v for v in vendor_results if v.get("unit_price_inr", 0) > 0]
    if not usable:
        return []

    prices = [v["unit_price_inr"] for v in usable]
    price_norms = _normalize_scores(prices)
    # Invert: lower price → higher score
    price_norms = [1.0 - p for p in price_norms]

    scored: list[VendorScore] = []
    for i, v in enumerate(usable):
        stock = int(v.get("stock_qty") or 0)
        moq = int(v.get("moq") or 1)
        lt = v.get("lead_time_weeks")
        avail = v.get("availability", "Out of Stock")

        # Stock adequacy
        if avail == "Out of Stock":
            stock_score = 0.0
        else:
            stock_score = min(1.0, stock / qty) if qty > 0 else 1.0

        # MOQ fit
        moq_score = 1.0 if moq <= qty else (qty / moq)

        # Lead time
        if avail == "In Stock":
            lt_score = 1.0
        elif lt is not None and lt < 4:
            lt_score = 0.5
        else:
            lt_score = 0.0

        score = (
            0.50 * price_norms[i] +
            0.30 * stock_score +
            0.15 * moq_score +
            0.05 * lt_score
        )

        price_inr = v["unit_price_inr"]
        scored.append(VendorScore(
            vendor_name=v.get("vendor", "Unknown"),
            unit_price_inr=price_inr,
            total_price_inr=round(price_inr * qty, 4),
            stock_qty=stock,
            moq=moq,
            availability=avail,
            score=round(score, 6),
            lead_time_weeks=lt,
            vendor_part_number=v.get("vendor_part_number", ""),
            raw=v,
        ))

    scored.sort(key=lambda x: -x.score)
    return scored


def _split_order(
    vendor_results: list[dict],
    qty: int,
) -> list[dict]:
    """
    Greedy bin-packing: find minimum set of vendors covering qty at lowest cost.
    Returns list of {vendor, qty_from_vendor, unit_price_inr, subtotal_inr}.
    """
    in_stock = [
        v for v in vendor_results
        if v.get("availability") == "In Stock" and v.get("stock_qty", 0) > 0
    ]
    if not in_stock:
        return []

    # Sort by price×available_qty ascending (cheapest usable first)
    in_stock.sort(key=lambda v: v["unit_price_inr"])

    remaining = qty
    plan: list[dict] = []

    for v in in_stock:
        if remaining <= 0:
            break
        available = min(int(v["stock_qty"]), remaining)
        moq = int(v.get("moq") or 1)
        # Must buy at least MOQ
        buy_qty = max(available, moq) if available > 0 else moq
        buy_qty = min(buy_qty, remaining + moq)   # don't over-buy too much
        price = v["unit_price_inr"]
        plan.append({
            "vendor": v["vendor"],
            "vendor_part_number": v["vendor_part_number"],
            "qty_from_vendor": buy_qty,
            "unit_price_inr": price,
            "subtotal_inr": round(price * buy_qty, 2),
        })
        remaining -= available

    if remaining > 0:
        logger.warning("Split order still %d units short — insufficient stock across all vendors.", remaining)

    return plan


def optimize(
    component: str,
    normalized_mpn: str,
    vendor_results: list[dict],
    qty: int,
) -> OptimizationOutput:
    """
    Main optimizer entry point for one component.
    Returns an OptimizationOutput with best vendor recommendation.
    """
    if not vendor_results:
        return OptimizationOutput(
            component=component,
            normalized_mpn=normalized_mpn,
            quantity_required=qty,
            best_vendor=None,
            best_unit_price_inr=None,
            best_total_price_inr=None,
            availability="No Data",
            moq=None,
            all_vendors=[],
            recommendation_reason="No vendor data available — manual lookup required.",
        )

    scored = score_vendors(vendor_results, qty)
    all_in_stock = [s for s in scored if s.availability == "In Stock" and s.stock_qty >= qty]
    any_in_stock = [s for s in scored if s.availability == "In Stock"]

    split_plan = None
    reason_parts = []

    if all_in_stock:
        best = all_in_stock[0]
        reason_parts.append(f"{best.vendor_name}: highest score ({best.score:.3f})")
        if best.unit_price_inr == min(s.unit_price_inr for s in all_in_stock):
            reason_parts.append("lowest price")
        reason_parts.append(f"full qty ({qty}) in stock, MOQ={best.moq}")
    elif any_in_stock:
        # No single vendor has full qty — try split order
        best = any_in_stock[0]
        split_plan = _split_order(vendor_results, qty)
        reason_parts.append(f"No single vendor has full qty={qty}.")
        if split_plan:
            vendors_used = ", ".join(p["vendor"] for p in split_plan)
            reason_parts.append(f"Split order recommended across: {vendors_used}.")
        reason_parts.append(f"Primary: {best.vendor_name} ({best.stock_qty} in stock).")
    else:
        # All OOS
        best = scored[0] if scored else None
        reason_parts.append("All vendors out of stock — shown for reference pricing only.")

    if best is None:
        return OptimizationOutput(
            component=component,
            normalized_mpn=normalized_mpn,
            quantity_required=qty,
            best_vendor=None,
            best_unit_price_inr=None,
            best_total_price_inr=None,
            availability="Out of Stock",
            moq=None,
            all_vendors=vendor_results,
            recommendation_reason="All vendors report out of stock.",
        )

    # Savings calculation
    in_stock_prices = [s.unit_price_inr for s in scored if s.availability == "In Stock"]
    savings_inr = 0.0
    if len(in_stock_prices) >= 2:
        worst_price = max(in_stock_prices)
        savings_inr = round((worst_price - best.unit_price_inr) * qty, 2)

    return OptimizationOutput(
        component=component,
        normalized_mpn=normalized_mpn,
        quantity_required=qty,
        best_vendor=best.vendor_name,
        best_unit_price_inr=best.unit_price_inr,
        best_total_price_inr=best.total_price_inr,
        availability=best.availability,
        moq=best.moq,
        all_vendors=vendor_results,
        alternatives=[],
        savings_vs_worst_inr=savings_inr,
        recommendation_reason=" | ".join(reason_parts),
        split_order=split_plan,
    )
