"""
config.py
=========
Single source of truth for all shared data: paths, year mappings,
and empirical constants.

Architecture
------------
    reference_data.md   — all empirical numbers (edit here to change data)
         ↓  parsed by load_reference_data() in utils.py
    config.py           — builds typed Python dicts from the parsed sections
         ↓  imported by every pipeline script
    pipeline scripts    — never read reference_data.md directly

What lives here vs reference_data.md
-------------------------------------
    config.py           → directory layout, YEARS/STUDY_YEARS mappings,
                          SUT_UNIT_TO_CRORE, TSA_BASE, NAS_GVA_CONSTANT,
                          NAS_GROWTH_RATES, and all derived constants
    reference_data.md   → raw statistical numbers with source citations

Adding a new study year (e.g. 2025)
-------------------------------------
1. Update reference_data.md — add columns/rows for the new year.
2. Add "2025" to STUDY_YEARS below.
3. Add the mapping to YEARS below.
4. Re-run. Growth rates are computed automatically from the .md data.
"""

from pathlib import Path


# ══════════════════════════════════════════════════════════════════════════════
# PROJECT ROOT & DIRECTORY LAYOUT
# ══════════════════════════════════════════════════════════════════════════════

def _base_dir() -> Path:
    here = Path(__file__).parent.resolve()
    return here.parent if here.name == "5-scripts" else here / "twf-calculation"

BASE_DIR = _base_dir()

DIRS = {
    # inputs
    "sut":          BASE_DIR / "1-input-data" / "sut",
    "exiobase":     BASE_DIR / "1-input-data" / "exiobase-raw",
    "nas":          BASE_DIR / "1-input-data" / "nas" / "2025",
    # intermediate
    "io":           BASE_DIR / "2-intermediate-calculations" / "io-table",
    "concordance":  BASE_DIR / "2-intermediate-calculations" / "concordance",
    "demand":       BASE_DIR / "2-intermediate-calculations" / "tourism-demand",
    "tsa":          BASE_DIR / "2-intermediate-calculations" / "tsa-demand",
    "nas_seg":      BASE_DIR / "2-intermediate-calculations" / "nas-segregation",
    # results
    "indirect":     BASE_DIR / "3-final-results" / "indirect-water",
    "direct":       BASE_DIR / "3-final-results" / "direct-water",
    "comparison":   BASE_DIR / "3-final-results" / "comparison",
    # extended analysis results (added for SDA, MC, supply-chain, visualisation)
    "sda":          BASE_DIR / "3-final-results" / "sda",
    "monte_carlo":  BASE_DIR / "3-final-results" / "monte-carlo",
    "supply_chain": BASE_DIR / "3-final-results" / "supply-chain",
    "visualisation":BASE_DIR / "3-final-results" / "visualisation",
    # logs
    "logs":         BASE_DIR / "logs",
}


# ══════════════════════════════════════════════════════════════════════════════
# STUDY YEARS & IO-YEAR MAPPINGS
# ══════════════════════════════════════════════════════════════════════════════

# All scripts must iterate over STUDY_YEARS — never hardcode ["2015","2019","2022"]
STUDY_YEARS = ["2015", "2019", "2022"]

YEARS = {
    "2015": {"io_year": "2015-16", "io_tag": "2015_16", "water_year": "2015"},
    "2019": {"io_year": "2019-20", "io_tag": "2019_20", "water_year": "2019"},
    "2022": {"io_year": "2021-22", "io_tag": "2021_22", "water_year": "2022"},
}

# 2015-16 SUT is published in ₹ lakh; the other two are already in ₹ crore.
SUT_UNIT_TO_CRORE = {"2015-16": 0.01, "2019-20": 1.0, "2021-22": 1.0}


# ══════════════════════════════════════════════════════════════════════════════
# LOAD REFERENCE DATA FROM MARKDOWN
# ══════════════════════════════════════════════════════════════════════════════

def _load_ref_sections() -> dict:
    """
    Parse reference_data.md using load_reference_data() from utils.
    Looks alongside this file first, then up one level.
    """
    from utils import load_reference_data
    candidates = [
        Path(__file__).parent / "reference_data.md",
        Path(__file__).parent.parent / "reference_data.md",
    ]
    for p in candidates:
        if p.exists():
            return load_reference_data(p)
    raise FileNotFoundError(
        "reference_data.md not found. Searched:\n" +
        "\n".join(f"  {p}" for p in candidates)
    )


_REF = _load_ref_sections()


# ══════════════════════════════════════════════════════════════════════════════
# CPI  (Consumer Price Index, FY averages, base 2015-16)
# Source: reference_data.md § CPI  →  MoSPI
# ══════════════════════════════════════════════════════════════════════════════

def _build_cpi() -> dict:
    return {
        r["io_year"]: float(r["cpi"])
        for r in _REF.get("CPI", {}).get("rows", [])
    }

CPI: dict = _build_cpi()

# Convenience alias keyed by 4-digit study year
CPI_BY_STUDY_YEAR: dict = {
    "2015": CPI.get("2015-16", 124.7),
    "2019": CPI.get("2019-20", 146.3),
    "2022": CPI.get("2021-22", 163.8),
}


# ══════════════════════════════════════════════════════════════════════════════
# EUR → INR EXCHANGE RATES
# Source: reference_data.md § EUR_INR  →  RBI / ECB
# ══════════════════════════════════════════════════════════════════════════════

def _build_eur_inr() -> dict:
    return {
        str(int(r["study_year"])): float(r["eur_inr"])
        for r in _REF.get("EUR_INR", {}).get("rows", [])
    }

EUR_INR: dict = _build_eur_inr()


# ══════════════════════════════════════════════════════════════════════════════
# DIRECT WATER COEFFICIENTS  (activity-based, LOW / BASE / HIGH scenarios)
# Source: reference_data.md § HOTEL/RESTAURANT/TRANSPORT_WATER_COEFFICIENTS
# ══════════════════════════════════════════════════════════════════════════════

def _build_direct_water() -> dict:
    def _scen_rows(section_id: str, key_col: str) -> dict:
        out = {}
        for r in _REF.get(section_id, {}).get("rows", []):
            k = str(int(r[key_col])) if isinstance(r[key_col], (int, float)) else str(r[key_col])
            out[k] = {
                "low":  float(r.get("low",  0)),
                "base": float(r.get("base", 0)),
                "high": float(r.get("high", 0)),
            }
        return out

    trans = _scen_rows("TRANSPORT_WATER_COEFFICIENTS", "mode")

    return {
        "hotel":           _scen_rows("HOTEL_WATER_COEFFICIENTS", "year"),
        "restaurant":      _scen_rows("RESTAURANT_WATER_COEFFICIENTS", "year"),
        "rail":            trans.get("rail",            {"low": 2.6, "base": 3.5, "high": 4.4}),
        "air":             trans.get("air",             {"low": 13,  "base": 18,  "high": 23}),
        "water_transport": trans.get("water_transport", {"low": 15,  "base": 20,  "high": 28}),
    }

DIRECT_WATER: dict = _build_direct_water()


# ══════════════════════════════════════════════════════════════════════════════
# AVG STAY DAYS  (per tourist type, per study year)
# Source: reference_data.md § AVG_STAY_DAYS
# NOTE: Separated from ACTIVITY_DATA so stay duration can be updated
#       independently. These directly affect per-tourist intensity denominators.
# ══════════════════════════════════════════════════════════════════════════════

def _build_avg_stay_days() -> dict:
    """
    Build dict: {study_year: {"domestic": float, "inbound": float}}
    from the AVG_STAY_DAYS table in reference_data.md.

    The table is transposed: rows = tourist type, columns = study years.
    Falls back to hardcoded defaults (dom=2.5, inb=8.0) if section is missing,
    so existing runs are not broken before the section is added to the .md file.
    """
    rows = _REF.get("AVG_STAY_DAYS", {}).get("rows", [])
    if not rows:
        # Fallback: return same values as the old hardcoded constants
        return {yr: {"domestic": 2.5, "inbound": 8.0} for yr in STUDY_YEARS}

    year_cols = [k for k in rows[0] if k != "type" and str(k).isdigit()]
    out: dict = {str(y): {} for y in year_cols}
    for row in rows:
        ttype = str(row["type"])          # "domestic" or "inbound"
        for yr in year_cols:
            out[str(yr)][ttype] = float(row[yr])
    return out

AVG_STAY_DAYS: dict = _build_avg_stay_days()


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVITY DATA  (tourism volumes for direct TWF calculation)
# Source: reference_data.md § ACTIVITY_DATA
# NOTE: imported by calculate_direct_twf.py and compare_years.py.
#       Do NOT redefine ACTIVITY_DATA in those modules.
#       avg_stay_days_dom and avg_stay_days_inb are now sourced from
#       AVG_STAY_DAYS (above) and merged in here for backward compatibility.
# ══════════════════════════════════════════════════════════════════════════════

def _build_activity_data() -> dict:
    """
    The ACTIVITY_DATA table in reference_data.md is transposed:
        rows = fields,  columns = study years (2015, 2019, 2022, ...)
    This function pivots it into the standard dict:
        {study_year: {field: value}}

    After pivoting, avg_stay_days_dom and avg_stay_days_inb are merged in
    from AVG_STAY_DAYS so downstream code that reads ACTIVITY_DATA["2019"]
    ["avg_stay_days_dom"] continues to work without any changes.
    """
    rows = _REF.get("ACTIVITY_DATA", {}).get("rows", [])
    if not rows:
        return {}
    year_cols = [k for k in rows[0] if k != "field" and str(k).isdigit()]
    out: dict = {str(y): {} for y in year_cols}
    for row in rows:
        field = str(row["field"])
        for yr in year_cols:
            out[str(yr)][field] = float(row[yr])

    # Merge avg_stay_days from the dedicated AVG_STAY_DAYS section.
    # This overwrites any avg_stay_days_dom / avg_stay_days_inb values
    # that might still be in the ACTIVITY_DATA table (removed from .md).
    stay = AVG_STAY_DAYS
    for yr in year_cols:
        yr_str = str(yr)
        if yr_str in stay:
            out[yr_str]["avg_stay_days_dom"] = stay[yr_str].get("domestic", 2.5)
            out[yr_str]["avg_stay_days_inb"] = stay[yr_str].get("inbound",  8.0)

    return out

ACTIVITY_DATA: dict = _build_activity_data()


# ══════════════════════════════════════════════════════════════════════════════
# WSI WEIGHTS  (Water Stress Index characterisation factors by product group)
# Source: reference_data.md § WSI_WEIGHTS
# NOTE: Used by calculate_indirect_twf.py to compute scarce water footprint.
#       Currently placeholder values — update with Pfister/AWARE factors.
# ══════════════════════════════════════════════════════════════════════════════

def _build_wsi_weights() -> dict:
    """
    Build dict: {product_group: wsi_weight}
    from the WSI_WEIGHTS table in reference_data.md.

    product_group maps to SUT Product_ID ranges exactly as in
    classify_source_group() in calculate_indirect_twf.py:
      Agriculture  → IDs 1–29
      Mining       → IDs 30–40
      Manufacturing→ IDs 41–113 (excl. Electricity)
      Electricity  → ID 114
      Petroleum    → IDs 71–80
      Services     → IDs 115–140

    Falls back to all-0.47 (India national average) if section missing.
    """
    rows = _REF.get("WSI_WEIGHTS", {}).get("rows", [])
    if not rows:
        # Fallback: India national average WSI = 0.47 (Pfister et al. 2009)
        return {
            "Agriculture":  0.47,
            "Mining":       0.47,
            "Manufacturing":0.47,
            "Electricity":  0.47,
            "Petroleum":    0.47,
            "Services":     0.00,
        }
    return {
        str(r["product_group"]): float(r["wsi_weight"])
        for r in rows
    }

WSI_WEIGHTS: dict = _build_wsi_weights()


# ══════════════════════════════════════════════════════════════════════════════
# NAS GVA CONSTANT  (Statement 6.1, 2011-12 constant prices)
# Source: reference_data.md § NAS_GVA_CONSTANT
# ══════════════════════════════════════════════════════════════════════════════

def _build_nas_gva() -> dict:
    """
    Build the nested NAS_GVA_CONSTANT dict from the flat Markdown table.
    Result: {sector_key: {nas_sno, nas_label, unit, notes, gva: {fy: value}}}
    """
    raw  = _REF.get("NAS_GVA_CONSTANT", {})
    meta = raw.get("_meta", {})
    unit = meta.get("unit", "crore INR, 2011-12 constant prices")
    out  = {}
    for row in raw.get("rows", []):
        key = row["sector_key"]
        gva = {}
        for col, val in row.items():
            if col in ("sector_key", "nas_sno", "nas_label", "notes"):
                continue
            parts = col.split("-")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                gva[col] = float(val)
        out[key] = {
            "nas_sno":   str(row.get("nas_sno", "")),
            "nas_label": str(row.get("nas_label", "")),
            "unit":      unit,
            "notes":     str(row.get("notes", "")),
            "gva":       gva,
        }
    return out

NAS_GVA_CONSTANT: dict = _build_nas_gva()


# ══════════════════════════════════════════════════════════════════════════════
# NAS GROWTH RATES  (derived from NAS_GVA_CONSTANT + STUDY_TO_FISCAL)
# These are the multipliers consumed by build_tourism_demand.py
# ══════════════════════════════════════════════════════════════════════════════

def _build_study_to_fiscal() -> dict:
    return {
        str(int(r["study_year"])): str(r["fiscal_year"])
        for r in _REF.get("STUDY_TO_FISCAL", {}).get("rows", [])
    }

def _compute_growth_rates() -> dict:
    """
    NAS_GROWTH_RATES[sector][study_year] = GVA[fiscal_year] / GVA["2015-16"]

    Example: NAS_GROWTH_RATES["Hotels"]["2019"] = 1.377
    means Hotels & Restaurants GVA grew 37.7% in real terms 2015-16 → 2019-20.
    """
    mapping = _build_study_to_fiscal()
    rates: dict = {}
    for key, info in NAS_GVA_CONSTANT.items():
        base = info["gva"].get("2015-16", 0)
        if base <= 0:
            raise ValueError(
                f"config: NAS_GVA_CONSTANT['{key}'] has zero/negative "
                "2015-16 GVA — cannot compute growth rate. "
                "Check reference_data.md § NAS_GVA_CONSTANT."
            )
        rates[key] = {}
        for study_yr, fiscal_yr in mapping.items():
            if fiscal_yr not in info["gva"]:
                raise KeyError(
                    f"config: NAS_GVA_CONSTANT['{key}'] is missing GVA "
                    f"for fiscal year '{fiscal_yr}'. "
                    f"Available: {list(info['gva'].keys())}. "
                    "Add the column to reference_data.md § NAS_GVA_CONSTANT."
                )
            rates[key][study_yr] = round(info["gva"][fiscal_yr] / base, 6)
    return rates

NAS_GROWTH_RATES: dict = _compute_growth_rates()


# ── Convenience accessor ──────────────────────────────────────────────────────

def get_growth_rate(sector: str, study_year: str) -> float:
    """
    Return the real GVA growth multiplier for a sector and study year.

    Parameters
    ----------
    sector     : Key in NAS_GVA_CONSTANT (e.g. "Hotels", "Railway")
    study_year : "2019" or "2022"

    Raises KeyError if either is not found.
    """
    if sector not in NAS_GROWTH_RATES:
        raise KeyError(
            f"Unknown NAS sector '{sector}'. "
            f"Available: {sorted(NAS_GROWTH_RATES)}"
        )
    if study_year not in NAS_GROWTH_RATES[sector]:
        raise KeyError(
            f"Unknown study year '{study_year}' for sector '{sector}'. "
            f"Available: {sorted(NAS_GROWTH_RATES[sector])}"
        )
    return NAS_GROWTH_RATES[sector][study_year]


# ── Validation on import ──────────────────────────────────────────────────────

def _validate():
    for key, rates in NAS_GROWTH_RATES.items():
        for yr, val in rates.items():
            if val <= 0:
                raise ValueError(
                    f"config: NAS_GROWTH_RATES['{key}']['{yr}'] = {val} ≤ 0. "
                    "Check reference_data.md § NAS_GVA_CONSTANT."
                )
            if val > 3.0:
                raise ValueError(
                    f"config: NAS_GROWTH_RATES['{key}']['{yr}'] = {val:.4f}x. "
                    "Implies >200% real growth — likely a data entry error in "
                    "reference_data.md § NAS_GVA_CONSTANT."
                )

_validate()


# ══════════════════════════════════════════════════════════════════════════════
# TSA 2015-16 BASE DATA  (structural metadata — kept in config, not .md)
# Source: Tourism Satellite Account India 2015-16, Ministry of Tourism
# Columns: (ID, category_name, category_type, inbound_crore, domestic_crore)
#
# Category types:
#   Characteristic — products specific to tourism (hotels, transport etc.)
#   Connected      — products tourists buy that are also sold to non-tourists
#   Imputed        — non-market services (vacation homes, FISIM, social transfers)
#
# Note: TSA_BASE stays in config because it is structural model metadata
# (defines the 24 TSA categories and their base-year expenditures) rather than
# empirically updated statistical data. If it needs updating for a new TSA
# edition, move it to reference_data.md following the same table pattern.
# ══════════════════════════════════════════════════════════════════════════════

TSA_BASE = [
    (1,  "Accommodation services/hotels",                  "Characteristic", 41373,  5610),
    (2,  "Food and beverage serving services/restaurants", "Characteristic", 73470, 88588),
    (3,  "Railway passenger transport services",           "Characteristic",  2032, 19096),
    (4,  "Road passenger transport services",              "Characteristic", 18699,183807),
    (5,  "Water passenger transport services",             "Characteristic",   614,   924),
    (6,  "Air passenger transport services",               "Characteristic", 14172, 57962),
    (7,  "Transport equipment rental services",            "Characteristic",   330,   634),
    (8,  "Travel agencies and other reservation services", "Characteristic",  4073,  5345),
    (9,  "Cultural and religious services",                "Characteristic",   974,    52),
    (10, "Sports and other recreational services",         "Characteristic",  6690,   209),
    (11, "Health and medical related services",            "Characteristic", 11514, 79130),
    (12, "Readymade garments",                             "Connected",      20364, 51003),
    (13, "Processed Food",                                 "Connected",       2851, 11597),
    (14, "Alcohol and tobacco products",                   "Connected",       4254,  3489),
    (15, "Travel related consumer goods",                  "Connected",      14918, 26646),
    (16, "Footwear",                                       "Connected",       2809,  7908),
    (17, "Soaps, cosmetics and glycerine",                 "Connected",        638,   935),
    (18, "Gems and jewellery",                             "Connected",      13985,  8807),
    (19, "Books, journals, magazines, stationery",         "Connected",       1571,  1452),
    (20, "Vacation homes",                                 "Imputed",             0,  4248),
    (21, "Social transfers in kind",                       "Imputed",             0,  4177),
    (22, "FISIM",                                          "Imputed",             0, 42924),
    (23, "Producers guest houses",                         "Imputed",             0, 64716),
    (24, "Imputed expenditures on food",                   "Imputed",             0, 25215),
]