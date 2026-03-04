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

Changes vs previous version
----------------------------
- WSI_WEIGHTS: updated to WRI Aqueduct 4.0 (Kuzma et al. 2023) values.
  Agriculture=0.827 (Irr-weighted bws), Industry sectors=0.814 (Ind-weighted bws).
  All DERIVED/LITERATURE flags removed — values now from published 2023 dataset.
- Added OUTBOUND_TWF_DATA and OUTBOUND_TOURIST_COUNTS loaders for net TWF module.
- _build_wsi_weights() now reads 'wsi_weight' column (backward-compatible);
  also exposes WSI_RAW_SCORES dict for reporting.
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
    "outbound":      BASE_DIR / "3-final-results" / "outbound-twf",
    "visualisation": BASE_DIR / "3-final-results" / "visualisation",
    "logs":          BASE_DIR / "logs",
}


# ══════════════════════════════════════════════════════════════════════════════
# STUDY YEARS & IO-YEAR MAPPINGS
# ══════════════════════════════════════════════════════════════════════════════

STUDY_YEARS = ["2015", "2019", "2022"]

YEARS = {
    "2015": {"io_year": "2015-16", "io_tag": "2015_16", "water_year": "2015"},
    "2019": {"io_year": "2019-20", "io_tag": "2019_20", "water_year": "2019"},
    "2022": {"io_year": "2021-22", "io_tag": "2021_22", "water_year": "2022"},
}

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
    return _REF.get(section_id, {}).get("rows", [])

def _keyed(section_id: str, key_col: str, val_col: str) -> dict:
    return {str(r[key_col]): r[val_col] for r in _rows(section_id)}

def _scenario_rows(section_id: str, key_col: str) -> dict:
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

CPI: dict = {k: float(v) for k, v in _keyed("CPI", "io_year", "cpi").items()}


# ══════════════════════════════════════════════════════════════════════════════
# EUR → INR & USD → INR EXCHANGE RATES
# ══════════════════════════════════════════════════════════════════════════════

EUR_INR: dict = {str(int(float(k))): float(v)
                 for k, v in _keyed("EUR_INR", "study_year", "eur_inr").items()}

USD_INR_FULL: dict = {
    "2015": 65.00, "2016": 66.50, "2017": 64.50, "2018": 69.00,
    "2019": 70.00, "2020": 74.50, "2021": 74.00, "2022": 79.50, "2023": 82.00,
}

USD_INR: dict = {yr: USD_INR_FULL[yr] for yr in ["2015", "2019", "2022"]}


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
    from utils import pivot_transposed
    return pivot_transposed(_rows("ACTIVITY_DATA"), key_col="field")

ACTIVITY_DATA: dict = _build_activity_data()


# ══════════════════════════════════════════════════════════════════════════════
# WSI WEIGHTS  (WRI Aqueduct 4.0 — Kuzma et al. 2023)
# ══════════════════════════════════════════════════════════════════════════════
# Sector-weighted Baseline Water Stress (bws) scores, normalised 0-1 (÷5).
# Agriculture uses irrigation-demand weights (Irr); all extractive sectors
# use industrial-demand weights (Ind); Services = 0 (no direct extraction).
# These replace the Pfister (2009) derived estimates in the previous version.

def _build_wsi_weights() -> dict:
    """Return {product_group: wsi_weight (0-1 scale)}."""
    rows = _rows("WSI_WEIGHTS")
    if not rows:
        # Fallback to Aqueduct 4.0 values if section is missing
        return {
            "Agriculture":  0.827, "Mining":        0.814,
            "Manufacturing":0.814, "Electricity":   0.814,
            "Petroleum":    0.814, "Services":      0.000,
        }
    return {str(r["product_group"]): float(r["wsi_weight"]) for r in rows}

def _build_wsi_raw_scores() -> dict:
    """Return {product_group: raw_score (0-5 scale)} for reporting."""
    rows = _rows("WSI_WEIGHTS")
    if not rows:
        return {}
    return {str(r["product_group"]): float(r.get("raw_score", 0)) for r in rows}

WSI_WEIGHTS: dict    = _build_wsi_weights()
WSI_RAW_SCORES: dict = _build_wsi_raw_scores()

# Tourist multiplier: tourists use 1.5× local per-capita water footprint.
# Source: Hadjikakou et al. (2015); Li (2018); Lee et al. (2021).
TOURIST_WF_MULTIPLIER: float = 1.5


# ══════════════════════════════════════════════════════════════════════════════
# OUTBOUND TWF DATA  (for net TWF balance calculation)
# ══════════════════════════════════════════════════════════════════════════════

def _build_outbound_destinations() -> list[dict]:
    """
    Return list of destination dicts:
        [{country, dest_share, local_wf_m3_yr, wsi_dest}, ...]
    """
    rows = _rows("OUTBOUND_TWF_DATA")
    if not rows:
        return []
    return [
        {
            "country":        str(r["country"]),
            "dest_share":     float(r["dest_share"]),
            "local_wf_m3_yr": float(r["local_wf_m3_yr"]),
            "wsi_dest":       float(r.get("wsi_dest", 0.5)),
        }
        for r in rows
    ]

def _build_outbound_counts() -> dict:
    """
    Return {study_year: {outbound_tourists_M, avg_stay_abroad_days}}.
    """
    rows = _rows("OUTBOUND_TOURIST_COUNTS")
    if not rows:
        return {}
    return {
        str(int(r["study_year"])): {
            "outbound_tourists_M":    float(r["outbound_tourists_M"]),
            "avg_stay_abroad_days":   float(r["avg_stay_abroad_days"]),
        }
        for r in rows
    }

OUTBOUND_DESTINATIONS: list  = _build_outbound_destinations()
OUTBOUND_COUNTS: dict        = _build_outbound_counts()


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
    if sector not in NAS_GROWTH_RATES:
        raise KeyError(f"Unknown NAS sector '{sector}'. Available: {sorted(NAS_GROWTH_RATES)}")
    if study_year not in NAS_GROWTH_RATES[sector]:
        raise KeyError(
            f"Unknown study year '{study_year}' for sector '{sector}'. "
            f"Available: {sorted(NAS_GROWTH_RATES[sector])}"
        )
    return NAS_GROWTH_RATES[sector][study_year]


# ══════════════════════════════════════════════════════════════════════════════
# TSA BASE DATA
# ══════════════════════════════════════════════════════════════════════════════

def _build_tsa_base() -> list:
    return [
        (int(r["id"]), str(r["category"]), str(r["category_type"]),
         float(r["inbound_crore"]), float(r["domestic_crore"]))
        for r in _rows("TSA_BASE")
    ]

TSA_BASE: list = _build_tsa_base()


# ══════════════════════════════════════════════════════════════════════════════
# TSA MAPPINGS
# ══════════════════════════════════════════════════════════════════════════════

TSA_TO_NAS: dict = _keyed("TSA_TO_NAS", "category", "nas_sector")

def _build_tsa_to_exiobase() -> dict:
    out: dict = {}
    for r in _rows("TSA_TO_EXIOBASE"):
        cat  = str(r["category"])
        code = str(r["exio_code"])
        share = float(r["share"])
        out.setdefault(cat, []).append((code, share))
    return out

TSA_TO_EXIOBASE: dict = _build_tsa_to_exiobase()


# ══════════════════════════════════════════════════════════════════════════════
# EXIOBASE SECTOR INDEX  (163 India sectors)
# ══════════════════════════════════════════════════════════════════════════════

EXIO_CODES: list = ["IN"] + [f"IN.{i}" for i in range(1, 163)]
EXIO_IDX:   dict = {code: i for i, code in enumerate(EXIO_CODES)}


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION ON IMPORT
# ══════════════════════════════════════════════════════════════════════════════

def _validate():
    for key, rates in NAS_GROWTH_RATES.items():
        for yr, val in rates.items():
            if val <= 0:
                raise ValueError(
                    f"config: NAS_GROWTH_RATES['{key}']['{yr}'] = {val} ≤ 0."
                )
            if val > 3.0:
                raise ValueError(
                    f"config: NAS_GROWTH_RATES['{key}']['{yr}'] = {val:.4f}x — "
                    "implies >200% real growth."
                )
    # Verify WSI weights are in valid range
    for grp, w in WSI_WEIGHTS.items():
        if not (0.0 <= w <= 1.0):
            raise ValueError(
                f"config: WSI_WEIGHTS['{grp}'] = {w} — must be in [0, 1]."
            )
    # Verify outbound destination shares sum to ≈1
    if OUTBOUND_DESTINATIONS:
        total_share = sum(d["dest_share"] for d in OUTBOUND_DESTINATIONS)
        if abs(total_share - 1.0) > 0.05:
            import warnings
            warnings.warn(
                f"OUTBOUND_TWF_DATA destination shares sum to {total_share:.3f} "
                "(expected 1.0 ± 0.05). Check reference_data.md § OUTBOUND_TWF_DATA."
            )

_validate()
