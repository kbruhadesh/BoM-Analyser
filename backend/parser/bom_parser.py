"""
bom_parser.py — Parses CSV / XLSX / TSV / plain-text BoM into BomItemSchema list.
Uses fuzzy header matching so column names don't need to be exact.
"""
import io
import re
import base64
import logging
from typing import Optional

import pandas as pd
from thefuzz import process as fuzz_process

from schemas import BomItemSchema

logger = logging.getLogger(__name__)

# ── Column header aliases ──────────────────────────────────────────────────────
HEADER_ALIASES = {
    "quantity": ["qty", "quantity", "count", "pcs", "pieces", "amount", "num", "number"],
    "mpn":      ["mpn", "part number", "part_number", "partnumber", "mfr part", "mfr_part",
                 "manufacturer part", "manufacturer_part", "part no", "part_no", "pn"],
    "description": ["description", "desc", "component", "name", "part description",
                    "part_description", "value"],
    "manufacturer": ["manufacturer", "mfr", "make", "brand", "mfg"],
    "reference": ["ref", "reference", "ref des", "ref_des", "reference designator",
                  "reference_designator", "designator", "refdes"],
    "notes":    ["notes", "note", "comment", "comments", "remark", "remarks"],
}

FUZZY_THRESHOLD = 72


class ParseError(Exception):
    def __init__(self, message: str, line_number: Optional[int] = None):
        self.line_number = line_number
        super().__init__(f"Line {line_number}: {message}" if line_number else message)


def _fuzzy_match_header(col: str, candidates: list[str]) -> Optional[str]:
    """Return the best matching canonical field name or None."""
    col_clean = col.strip().lower().replace("-", " ").replace("_", " ")
    for canonical, aliases in HEADER_ALIASES.items():
        result = fuzz_process.extractOne(col_clean, aliases)
        if result and result[1] >= FUZZY_THRESHOLD:
            return canonical
    return None


def _map_columns(df: pd.DataFrame) -> dict[str, str]:
    """Return dict mapping canonical field → actual DataFrame column name."""
    mapping: dict[str, str] = {}
    for col in df.columns:
        canonical = _fuzzy_match_header(str(col), list(HEADER_ALIASES.keys()))
        if canonical and canonical not in mapping:
            mapping[canonical] = col
    return mapping


def _clean_mpn(val) -> Optional[str]:
    if pd.isna(val) or str(val).strip() in ("", "nan", "None", "-"):
        return None
    return str(val).strip().upper()


def _clean_qty(val) -> int:
    try:
        qty = int(float(str(val).strip().replace(",", "")))
        return max(1, qty)
    except (ValueError, TypeError):
        return 1


def _df_to_items(df: pd.DataFrame) -> list[BomItemSchema]:
    mapping = _map_columns(df)
    items: list[BomItemSchema] = []

    for idx, row in df.iterrows():
        line = idx + 2  # 1-based, skip header

        qty = _clean_qty(row[mapping["quantity"]]) if "quantity" in mapping else 1
        mpn = _clean_mpn(row[mapping["mpn"]]) if "mpn" in mapping else None
        desc = str(row[mapping["description"]]).strip() if "description" in mapping else ""
        mfr = str(row[mapping["manufacturer"]]).strip() if "manufacturer" in mapping else None
        ref = str(row[mapping["reference"]]).strip() if "reference" in mapping else None
        notes = str(row[mapping["notes"]]).strip() if "notes" in mapping else None

        # Fallback: if no MPN, use description as search key
        if not mpn and desc:
            mpn = desc.upper()

        if not mpn and not desc:
            logger.warning("Row %d: no MPN or description, skipping.", line)
            continue

        # Sanitise nan strings
        for field_val, field_name in [(mfr, "mfr"), (ref, "ref"), (notes, "notes")]:
            pass  # processed inline below

        items.append(BomItemSchema(
            line_number=line,
            quantity=qty,
            raw_description=desc,
            manufacturer_part_number=mpn,
            manufacturer=None if mfr in ("nan", "", "None") else mfr,
            reference_designators=None if ref in ("nan", "", "None") else ref,
            notes=None if notes in ("nan", "", "None") else notes,
        ))

    return items


def _detect_format(raw: str | bytes) -> str:
    if isinstance(raw, bytes):
        # Check for xlsx magic bytes
        if raw[:4] == b"PK\x03\x04":
            return "xlsx"
        raw_str = raw.decode("utf-8", errors="replace")
    else:
        raw_str = raw

    raw_str = raw_str.strip()
    lines = raw_str.splitlines()
    if not lines:
        return "text"

    first = lines[0]
    comma_count = first.count(",")
    tab_count = first.count("\t")
    semi_count = first.count(";")

    if tab_count >= 2:
        return "tsv"
    if comma_count >= 2:
        return "csv"
    if semi_count >= 2:
        return "csv_semi"
    return "text"


def _parse_text_bom(text: str) -> list[BomItemSchema]:
    """
    Fallback parser for plain text like:
      10x ATmega328P  8-bit MCU
    or just a list of MPNs one per line.
    """
    items = []
    for i, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Try pattern: qty x mpn description
        m = re.match(r"^(\d+)\s*[xX×*]\s*(\S+)\s*(.*)", line)
        if m:
            qty = int(m.group(1))
            mpn = m.group(2).upper()
            desc = m.group(3).strip()
        else:
            # Just treat the whole line as MPN / description
            qty = 1
            parts = line.split(None, 1)
            mpn = parts[0].upper()
            desc = parts[1] if len(parts) > 1 else ""

        items.append(BomItemSchema(
            line_number=i,
            quantity=qty,
            raw_description=desc,
            manufacturer_part_number=mpn,
        ))
    return items


def parse_bom(raw_input: str | bytes, format: str = "auto") -> list[BomItemSchema]:
    """
    Main entry point.
    format: "auto" | "csv" | "tsv" | "xlsx" | "xlsx_base64" | "text"
    """
    if format == "auto":
        format = _detect_format(raw_input)

    # ── XLSX (base64 encoded from API) ─────────────────────────────────────────
    if format == "xlsx_base64":
        raw_bytes = base64.b64decode(raw_input)
        df = pd.read_excel(io.BytesIO(raw_bytes), engine="openpyxl")
        df.columns = [str(c) for c in df.columns]
        df.dropna(how="all", inplace=True)
        return _df_to_items(df)

    # ── Raw XLSX bytes ─────────────────────────────────────────────────────────
    if format == "xlsx":
        raw_bytes = raw_input if isinstance(raw_input, bytes) else raw_input.encode()
        df = pd.read_excel(io.BytesIO(raw_bytes), engine="openpyxl")
        df.columns = [str(c) for c in df.columns]
        df.dropna(how="all", inplace=True)
        return _df_to_items(df)

    # Decode bytes → str for text-based formats
    if isinstance(raw_input, bytes):
        raw_input = raw_input.decode("utf-8", errors="replace")

    raw_input = raw_input.strip()

    # ── CSV / TSV ──────────────────────────────────────────────────────────────
    if format in ("csv", "tsv", "csv_semi"):
        sep = {"csv": ",", "tsv": "\t", "csv_semi": ";"}[format]
        try:
            df = pd.read_csv(io.StringIO(raw_input), sep=sep, dtype=str)
            df.dropna(how="all", inplace=True)
            if len(df.columns) < 2:
                raise ParseError("Too few columns detected — check separator.")
            return _df_to_items(df)
        except ParseError:
            raise
        except Exception as e:
            raise ParseError(f"CSV parse error: {e}") from e

    # ── Plain text fallback ────────────────────────────────────────────────────
    return _parse_text_bom(raw_input)
