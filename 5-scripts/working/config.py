"""
config.py
=========
Shared configuration: directory layout, year mappings, and all
empirical constants loaded from reference_data.md.

Architecture
------------
    reference_data.md   — all empirical numbers (edit here to change data)
         ↓  parsed by load_reference_data() in utils.py
    config.py           — builds typed Python dicts from parsed sections
         ↓  imported by every pipeline script
    pipeline scripts    — never read reference_data.md directly

Adding a new study year (e.g. 2025)
-------------------------------------
1. Update reference_data.md — add columns/rows for the new year.
2. Add "2025" to STUDY_YEARS below.
3. Add the mapping to YEARS below.
4. Re-run. Growth rates are computed automatically from .md data.

USD / INR exchange rates
------------------------
USD_INR keys are study years ("2015", "2019", "2022").
Rates are annual midpoints of the RBI reference rate ranges provided.
Used to display all ₹ crore monetary outputs as USD million equivalents.
    2015 (FY 2015-16): (₹64–66) midpoint → 65.00
    2019 (FY 2019-20): (₹69–71) midpoint → 70.00
    2022 (FY 2021-22): (₹78–81) midpoint → 79.50
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
    "sut":           BASE_DIR / "1-input-data" / "sut",
    "exiobase":      BASE_DIR / "1-input-data" / "exiobase-raw",
    "nas":           BASE_DIR / "1-input-data" / "nas" / "2025",
    "io":            BASE_DIR / "2-intermediate-calculations" / "io-table",
    "concordance":   BASE_DIR / "2-intermediate-calculations" / "concordance",
    "demand":        BASE_DIR / "2-intermediate-calculations" / "tourism-demand",
    "tsa":           BASE_DIR / "2-intermediate-calculations" / "tsa-demand",
    "nas_seg":       BASE_DIR / "2-intermediate-calculations" / "nas-segregation",
    "indirect":      BASE_DIR / "3-final-results" / "indirect-water",
    "direct":        BASE_DIR / "3-final-results" / "direct-water",
    "comparison":    BASE_DIR / "3-final-results" / "comparison",
    "sda":           BASE_DIR / "3-final-results" / "sda",
    "monte_carlo":   BASE_DIR / "3-final-results" / "monte-carlo",
    "supply_chain":  BASE_DIR / "3-final-results" / "supply-chain",
    "visualisation": BASE_DIR / "3-final-results" / "visualisation",
    "logs":          BASE_DIR / "logs",
}


# ══════════════════════════════════════════════════════════════════════════════
# STUDY YEARS & IO-YEAR MAPPINGS
# ══════════════════════════════════════════════════════════════════════════════

# All scripts must iterate over STUDY_YEARS — never hardcode year lists.
STUDY_YEARS = ["2015", "2019", "2022"]

YEARS = {
    "2015": {"io_year": "2015-16", "io_tag": "2015_16", "water_year": "2015"},
    "2019": {"io_year": "2019-20", "io_tag": "2019_20", "water_year": "2019"},
    "2022": {"io_year": "2021-22", "io_tag": "2021_22", "water_year": "2022"},
}

# 2015-16 SUT is published in ₹ lakh; the other two are in ₹ crore.
SUT_UNIT_TO_CRORE = {"2015-16": 1.0, "2019-20": 1.0, "2021-22": 1.0}


# ══════════════════════════════════════════════════════════════════════════════
# LOAD REFERENCE DATA
# ══════════════════════════════════════════════════════════════════════════════

def _load_ref_sections() -> dict:
    from utils import load_reference_data
    for p in [
        Path(__file__).parent / "reference_data.md",
        Path(__file__).parent.parent / "reference_data.md",
    ]:
        if p.exists():
            return load_reference_data(p)
    raise FileNotFoundError("reference_data.md not found alongside config.py")

_REF = _load_ref_sections()


# ── Universal section helpers ─────────────────────────────────────────────────

def _rows(section_id: str) -> list:
    """Return row list for a section, or [] if section is missing."""
    return _REF.get(section_id, {}).get("rows", [])

def _keyed(section_id: str, key_col: str, val_col: str) -> dict:
    """Return {row[key_col]: row[val_col]} for a section."""
    return {str(r[key_col]): r[val_col] for r in _rows(section_id)}

def _scenario_rows(section_id: str, key_col: str) -> dict:
    """Return {key: {low, base, high}} for scenario tables."""
    out = {}
    for r in _rows(section_id):
        k = str(int(r[key_col])) if isinstance(r[key_col], (int, float)) else str(r[key_col])
        out[k] = {
            "low":  float(r.get("low",  0)),
            "base": float(r.get("base", 0)),
            "high": float(r.get("high", 0)),
        }
    return out


# ══════════════════════════════════════════════════════════════════════════════
# CPI  (Consumer Price Index, FY averages, base 2015-16)
# ══════════════════════════════════════════════════════════════════════════════

CPI: dict = _keyed("CPI", "io_year", "cpi")
CPI = {k: float(v) for k, v in CPI.items()}


# ══════════════════════════════════════════════════════════════════════════════
# EUR → INR EXCHANGE RATES
# ══════════════════════════════════════════════════════════════════════════════

EUR_INR: dict = {str(int(float(k))): float(v)
                 for k, v in _keyed("EUR_INR", "study_year", "eur_inr").items()}


# ══════════════════════════════════════════════════════════════════════════════
# USD → INR EXCHANGE RATES  (annual midpoints, keyed by study year)
# ══════════════════════════════════════════════════════════════════════════════
# Source: RBI reference rate ranges supplied with project specification.
# Midpoints used:
#   2015 (FY 2015-16): range ₹64–66  → 65.00
#   2016 (calendar):   range ₹66–67  → 66.50
#   2017 (calendar):   range ₹64–65  → 64.50
#   2018 (calendar):   range ₹68–70  → 69.00
#   2019 (FY 2019-20): range ₹69–71  → 70.00
#   2020 (calendar):   range ₹74–75  → 74.50
#   2021 (calendar):   range ₹73–75  → 74.00
#   2022 (FY 2021-22): range ₹78–81  → 79.50
#   2023 (calendar):   range ₹81–83  → 82.00
#
# Pipeline uses study-year keys only ("2015", "2019", "2022").
# Full calendar-year table is provided for reference and future extension.

USD_INR_FULL: dict = {
    "2015": 65.00,
    "2016": 66.50,
    "2017": 64.50,
    "2018": 69.00,
    "2019": 70.00,
    "2020": 74.50,
    "2021": 74.00,
    "2022": 79.50,
    "2023": 82.00,
}

# Study-year lookup — only the three years actually used by the pipeline.
USD_INR: dict = {
    "2015": USD_INR_FULL["2015"],   # FY 2015-16
    "2019": USD_INR_FULL["2019"],   # FY 2019-20
    "2022": USD_INR_FULL["2022"],   # FY 2021-22
}


# ══════════════════════════════════════════════════════════════════════════════
# DIRECT WATER COEFFICIENTS  (activity-based, LOW / BASE / HIGH scenarios)
# ══════════════════════════════════════════════════════════════════════════════

def _build_direct_water() -> dict:
    trans = _scenario_rows("TRANSPORT_WATER_COEFFICIENTS", "mode")
    return {
        "hotel":           _scenario_rows("HOTEL_WATER_COEFFICIENTS", "year"),
        "restaurant":      _scenario_rows("RESTAURANT_WATER_COEFFICIENTS", "year"),
        "rail":            trans.get("rail",            {"low": 2.6, "base": 3.5, "high": 4.4}),
        "air":             trans.get("air",             {"low": 13,  "base": 18,  "high": 23}),
        "water_transport": trans.get("water_transport", {"low": 15,  "base": 20,  "high": 28}),
    }

DIRECT_WATER: dict = _build_direct_water()


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVITY DATA  (tourism volumes + stay duration, for direct TWF)
# ══════════════════════════════════════════════════════════════════════════════

def _build_activity_data() -> dict:
    """
    Pivot transposed ACTIVITY_DATA table (rows=fields, columns=years) into:
        {study_year: {field: value}}

    avg_stay_days_dom and avg_stay_days_inb are included as rows in the table
    in reference_data.md — no separate merge step needed.
    """
    from utils import pivot_transposed
    return pivot_transposed(_rows("ACTIVITY_DATA"), key_col="field")

ACTIVITY_DATA: dict = _build_activity_data()


# ══════════════════════════════════════════════════════════════════════════════
# WSI WEIGHTS  (Water Stress Index characterisation factors)
# ══════════════════════════════════════════════════════════════════════════════

def _build_wsi_weights() -> dict:
    rows = _rows("WSI_WEIGHTS")
    if not rows:
        return {"Agriculture": 0.47, "Mining": 0.47, "Manufacturing": 0.47,
                "Electricity": 0.47, "Petroleum": 0.47, "Services": 0.00}
    return {str(r["product_group"]): float(r["wsi_weight"]) for r in rows}

WSI_WEIGHTS: dict = _build_wsi_weights()


# ══════════════════════════════════════════════════════════════════════════════
# NAS GVA CONSTANT  (Statement 6.1, 2011-12 constant prices)
# ══════════════════════════════════════════════════════════════════════════════

def _build_nas_gva() -> dict:
    raw  = _REF.get("NAS_GVA_CONSTANT", {})
    unit = raw.get("_meta", {}).get("unit", "crore INR, 2011-12 constant prices")
    out  = {}
    for row in raw.get("rows", []):
        key = row["sector_key"]
        gva = {
            col: float(val)
            for col, val in row.items()
            if col not in ("sector_key", "nas_sno", "nas_label", "notes")
            and len(str(col).split("-")) == 2
            and all(p.isdigit() for p in str(col).split("-"))
        }
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
# ══════════════════════════════════════════════════════════════════════════════

def _build_study_to_fiscal() -> dict:
    return {str(int(r["study_year"])): str(r["fiscal_year"])
            for r in _rows("STUDY_TO_FISCAL")}

def _compute_growth_rates() -> dict:
    """
    NAS_GROWTH_RATES[sector][study_year] = GVA[fiscal_year] / GVA["2015-16"]

    Example: NAS_GROWTH_RATES["Hotels"]["2019"] = 1.377
    means Hotels GVA grew 37.7% in real terms 2015-16 → 2019-20.
    """
    mapping = _build_study_to_fiscal()
    rates: dict = {}
    for key, info in NAS_GVA_CONSTANT.items():
        base = info["gva"].get("2015-16", 0)
        if base <= 0:
            raise ValueError(
                f"config: NAS_GVA_CONSTANT['{key}'] has zero/negative "
                "2015-16 GVA — check reference_data.md § NAS_GVA_CONSTANT."
            )
        rates[key] = {}
        for study_yr, fiscal_yr in mapping.items():
            if fiscal_yr not in info["gva"]:
                raise KeyError(
                    f"config: NAS_GVA_CONSTANT['{key}'] missing GVA "
                    f"for fiscal year '{fiscal_yr}'. "
                    f"Available: {list(info['gva'].keys())}. "
                    "Add column to reference_data.md § NAS_GVA_CONSTANT."
                )
            rates[key][study_yr] = round(info["gva"][fiscal_yr] / base, 6)
    return rates

NAS_GROWTH_RATES: dict = _compute_growth_rates()


def get_growth_rate(sector: str, study_year: str) -> float:
    """Return the real GVA growth multiplier for a sector and study year."""
    if sector not in NAS_GROWTH_RATES:
        raise KeyError(f"Unknown NAS sector '{sector}'. Available: {sorted(NAS_GROWTH_RATES)}")
    if study_year not in NAS_GROWTH_RATES[sector]:
        raise KeyError(
            f"Unknown study year '{study_year}' for sector '{sector}'. "
            f"Available: {sorted(NAS_GROWTH_RATES[sector])}"
        )
    return NAS_GROWTH_RATES[sector][study_year]


# ══════════════════════════════════════════════════════════════════════════════
# TSA BASE DATA  (loaded from reference_data.md § TSA_BASE)
# ══════════════════════════════════════════════════════════════════════════════

def _build_tsa_base() -> list:
    """
    Load TSA 2015-16 base expenditure data from reference_data.md.
    Returns list of tuples: (id, category, category_type, inbound_crore, domestic_crore)
    for backward compatibility with existing code that iterates TSA_BASE.
    """
    return [
        (
            int(r["id"]),
            str(r["category"]),
            str(r["category_type"]),
            float(r["inbound_crore"]),
            float(r["domestic_crore"]),
        )
        for r in _rows("TSA_BASE")
    ]

TSA_BASE: list = _build_tsa_base()


# ══════════════════════════════════════════════════════════════════════════════
# TSA → NAS MAPPING  (loaded from reference_data.md § TSA_TO_NAS)
# ══════════════════════════════════════════════════════════════════════════════

TSA_TO_NAS: dict = _keyed("TSA_TO_NAS", "category", "nas_sector")


# ══════════════════════════════════════════════════════════════════════════════
# TSA → EXIOBASE MAPPING  (loaded from reference_data.md § TSA_TO_EXIOBASE)
# ══════════════════════════════════════════════════════════════════════════════

def _build_tsa_to_exiobase() -> dict:
    """
    Build {category: [(exio_code, share), ...]} from the flat table.
    Multiple rows per category are grouped into a list of (code, share) tuples.
    """
    out: dict = {}
    for r in _rows("TSA_TO_EXIOBASE"):
        cat  = str(r["category"])
        code = str(r["exio_code"])
        share = float(r["share"])
        out.setdefault(cat, []).append((code, share))
    return out

TSA_TO_EXIOBASE: dict = _build_tsa_to_exiobase()


# ══════════════════════════════════════════════════════════════════════════════
# EXIOBASE SECTOR INDEX  (163 India sectors: IN, IN.1 … IN.162)
# ══════════════════════════════════════════════════════════════════════════════

EXIO_CODES: list = ["IN"] + [f"IN.{i}" for i in range(1, 163)]   # 163 elements
EXIO_IDX:   dict = {code: i for i, code in enumerate(EXIO_CODES)}


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION ON IMPORT
# ══════════════════════════════════════════════════════════════════════════════

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
