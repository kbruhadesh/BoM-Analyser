"""
normalizer.py — Normalizes raw MPNs to canonical form.
Strips package suffixes, resolves aliases, and returns a confidence score.
"""
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── Package suffix patterns to strip ──────────────────────────────────────────
PACKAGE_SUFFIX_PATTERN = re.compile(
    r"[-/](PU|AU|MU|TU|DIP\d*|SOIC\d*|QFP\d*|QFN\d*|TQFP\d*|LQFP\d*|"
    r"SMD|TH|SMT|SOP\d*|SSOP\d*|VQFN\d*|BGA\d*|LGA\d*|MLF\d*|"
    r"T&R|TR|TAPE|REEL|BULK|CUT|TUBE|TRAY|BOX|CT|ND|DKR)$",
    re.IGNORECASE,
)

# Strip trailing temperature/grade suffixes like -40C, /85, etc.
TEMP_SUFFIX_PATTERN = re.compile(r"[-/]\d{2,3}[CF]$")

# ── Common manufacturer prefixes to strip when prepended ─────────────────────
MFR_PREFIXES = [
    "microchip", "texas instruments", "ti ", "stmicroelectronics", "stmicro",
    "nxp", "infineon", "nordic semi", "nordic semiconductor", "murata",
    "vishay", "yageo", "samsung", "tdk", "avx", "bourns", "panasonic",
    "wurth", "molex", "amphenol", "te connectivity",
]

# ── Alias table  (normalised key → canonical MPN) ────────────────────────────
# Keys are lowercase, stripped of spaces/dashes for fast lookup
ALIAS_TABLE: dict[str, str] = {
    # Microcontrollers
    "atmega328p": "ATmega328P",
    "atmega328":  "ATmega328P",
    "mega328":    "ATmega328P",
    "328p":       "ATmega328P",
    "atmega2560": "ATmega2560",
    "stm32f103":  "STM32F103C8T6",
    "bluepill":   "STM32F103C8T6",
    "esp8266":    "ESP8266EX",
    "esp32":      "ESP32-D0WDQ6",
    "esp32s3":    "ESP32-S3",
    "rp2040":     "RP2040",
    # RF
    "nrf24l01":   "NRF24L01+",
    "nrf24":      "NRF24L01+",
    # Regulators
    "lm7805":     "L7805",
    "7805":       "L7805",
    "ams1117":    "AMS1117-3.3",
    "ams11173":   "AMS1117-3.3",
    "lm317":      "LM317T",
    # Passives
    "1k":         "CRCW04021K00FKED",
    "10k":        "CRCW040210K0FKED",
    "100uf":      "GRM188R61A106KE69D",
    "100nf":      "GRM188R71H104KA93D",
    # Logic
    "ne555":      "NE555P",
    "555":        "NE555P",
    "lm358":      "LM358P",
    "lm741":      "UA741CP",
    # MOSFETs
    "irf540":     "IRF540N",
    "irf520":     "IRF520N",
    # Indian market popular parts
    "l298n":      "L298N",
    "a4988":      "A4988SETTR-T",
    "drv8825":    "DRV8825PWPR",
    "hc05":       "HC-05",
    "hc06":       "HC-06",
    "hc-sr04":    "HC-SR04",
    "max7219":    "MAX7219CNG+",
    "ds18b20":    "DS18B20+",
    "ds1307":     "DS1307+",
    "pcf8574":    "PCF8574AT",
    "mcp23017":   "MCP23017-E/SP",
    "ft232":      "FT232RL",
    "ch340":      "CH340G",
    "cp2102":     "CP2102",
}


@dataclass
class NormalizationResult:
    normalized_mpn: str
    confidence: float           # 0.0 – 1.0
    aliases_applied: list[str]
    original: str


def _alias_key(mpn: str) -> str:
    """Lower-case, strip spaces/dashes/+ for alias lookup."""
    return re.sub(r"[\s\-+/]", "", mpn).lower()


def normalize_mpn(raw_mpn: str) -> NormalizationResult:
    """
    Normalize a raw MPN string.  Steps (applied in order):
    1. Strip leading manufacturer name
    2. Uppercase
    3. Strip package/temperature suffixes
    4. Lookup alias table
    5. Compute confidence score
    """
    if not raw_mpn:
        return NormalizationResult("", 0.0, [], raw_mpn)

    original = raw_mpn.strip()
    working = original
    aliases_applied: list[str] = []
    confidence = 1.0

    # Step 1 — strip prepended manufacturer name
    lower = working.lower()
    for prefix in MFR_PREFIXES:
        if lower.startswith(prefix):
            working = working[len(prefix):].strip()
            aliases_applied.append(f"stripped_mfr_prefix:{prefix}")
            confidence -= 0.05
            break

    # Step 2 — uppercase (MPNs are conventionally uppercase)
    working = working.upper()

    # Step 3 — strip package suffix
    before_pkg = working
    working = PACKAGE_SUFFIX_PATTERN.sub("", working)
    working = TEMP_SUFFIX_PATTERN.sub("", working)
    if working != before_pkg:
        aliases_applied.append(f"stripped_package:{before_pkg} → {working}")
        confidence -= 0.03

    # Step 4 — alias table lookup (try progressively shorter keys)
    key = _alias_key(working)
    if key in ALIAS_TABLE:
        resolved = ALIAS_TABLE[key]
        aliases_applied.append(f"alias:{working} → {resolved}")
        working = resolved
        confidence = min(confidence, 0.97)
    else:
        # Partial match: try removing trailing alphanumeric variant chars
        short_key = re.sub(r"[A-Z0-9]{1,3}$", "", key)
        if len(short_key) >= 3 and short_key in ALIAS_TABLE:
            resolved = ALIAS_TABLE[short_key]
            aliases_applied.append(f"partial_alias:{working} → {resolved}")
            working = resolved
            confidence = min(confidence, 0.80)

    # Step 5 — penalise if very short (likely not a real MPN)
    if len(working) < 4:
        confidence = min(confidence, 0.50)

    return NormalizationResult(
        normalized_mpn=working,
        confidence=round(confidence, 4),
        aliases_applied=aliases_applied,
        original=original,
    )


def add_alias(raw_key: str, canonical_mpn: str) -> None:
    """Runtime alias addition (e.g. from admin API)."""
    ALIAS_TABLE[_alias_key(raw_key)] = canonical_mpn
    logger.info("Added alias: %s → %s", raw_key, canonical_mpn)
