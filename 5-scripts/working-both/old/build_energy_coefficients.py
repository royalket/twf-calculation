"""
build_energy_coefficients.py
============================
EXIOBASE F.txt → India 163-sector energy coefficients → 140-product SUT table.

Mirrors build_water_coefficients.py exactly, but extracts energy rows instead
of water rows.  The same 163→75-category concordance and 75→140-SUT mapping
are re-used so sector alignment is identical between the two stressors.

Energy rows extracted from F.txt
---------------------------------
  ENERGY_ROW_FINAL    "Energy Carrier Net Total"
      → total primary energy supply per sector (TJ / EUR million of output)
  ENERGY_ROW_EMISSION "Energy Carrier Net Fossil"
      → combustion-based (fossil) energy; used as a carbon-intensity proxy

Unit conversion
---------------
  EXIOBASE reports F in TJ per EUR million of output.
  Convert to MJ per ₹ crore:
      e [MJ/cr] = e [TJ/EUR-M] × TJ_TO_MJ × 100 / EUR_INR[year]
               = e [TJ/EUR-M] × 1_000_000 × 100 / EUR_INR[year]

Note on 2022 data gap
---------------------
EXIOBASE energy F.txt for 2022 (IOT_2022_ixi) is currently not published.
When the file is missing the script extrapolates from the 2019 coefficients
using the NAS energy intensity trend (Final_MJ_per_crore_2022 =
Final_MJ_per_crore_2019 × NAS_energy_growth_ratio).
All extrapolated rows are flagged with Extrapolated=True in the output.

Outputs (in 2-intermediate-calculations/concordance/)
------------------------------------------------------
  energy_coefficients_140_{io_tag}.csv   — 140 SUT products × Final + Emission MJ/crore
  concordance_energy_{io_tag}.csv        — 75 categories × Final + Emission MJ/crore
  (audit)  exiobase-raw/output/{year}/India_Energy_Coefficients_{year}.csv
"""

from __future__ import annotations

import copy
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    BASE_DIR, DIRS, EUR_INR, YEARS, STUDY_YEARS,
    TJ_TO_MJ, ENERGY_ROW_FINAL, ENERGY_ROW_EMISSION,
    NAS_GROWTH_RATES,
)
from utils import (
    section, subsection, ok, warn, fail, save_csv,
    compare_across_years, top_n, Timer, Logger,
)


# ══════════════════════════════════════════════════════════════════════════════
# SECTOR METADATA  (re-used from build_water_coefficients — keep in sync)
# ══════════════════════════════════════════════════════════════════════════════

SECTOR_LABELS = {
    "IN": "Paddy rice",           "IN.1": "Wheat",              "IN.2": "Cereal grains nec",
    "IN.3": "Vegetables/fruit",   "IN.4": "Oil seeds",          "IN.5": "Sugar cane",
    "IN.6": "Plant fibres",       "IN.7": "Crops nec",          "IN.8": "Cattle",
    "IN.9": "Pigs",               "IN.10": "Poultry",           "IN.11": "Meat animals nec",
    "IN.12": "Animal products",   "IN.13": "Raw milk",          "IN.14": "Wool/silk",
    "IN.15": "Forestry",          "IN.16": "Fishing",           "IN.92": "Electricity coal",
    "IN.93": "Electricity gas",   "IN.94": "Electricity nuclear","IN.95": "Electricity hydro",
    "IN.96": "Electricity wind",  "IN.97": "Electricity petroleum","IN.98": "Electricity biomass",
    "IN.99": "Electricity solar PV","IN.100": "Electricity solar thermal",
    "IN.101": "Electricity tide", "IN.102": "Electricity geothermal",
    "IN.103": "Electricity nec",  "IN.104": "Electricity transmission",
    "IN.105": "Electricity distribution", "IN.106": "Gas distribution",
    "IN.107": "Steam/hot water",  "IN.108": "Water supply",
    "IN.113": "Hotels and restaurants", "IN.114": "Railway transport",
    "IN.115": "Road transport",   "IN.119": "Air transport",
}

SECTOR_BROAD = {
    range(0, 17): "Agriculture", range(17, 34): "Mining",
    range(34, 82): "Manufacturing", range(82, 92): "Energy Processing",
    range(92, 109): "Utilities/Energy", range(109, 138): "Services",
}

def broad_category(idx: int) -> str:
    for r, cat in SECTOR_BROAD.items():
        if idx in r:
            return cat
    return "Other"


# ══════════════════════════════════════════════════════════════════════════════
# PART 1 — EXIOBASE extraction  (163 India sectors → Final + Emission MJ/crore)
# ══════════════════════════════════════════════════════════════════════════════

def extract_india_energy(f_path: Path, year: str, log: Logger = None) -> pd.DataFrame:
    """
    Extract India Final and Emission energy coefficients from EXIOBASE F.txt.

    Final rows    : rows whose index starts with ENERGY_ROW_FINAL
                    ("Energy Carrier Net Total")
    Emission rows : rows whose index starts with ENERGY_ROW_EMISSION
                    ("Energy Carrier Net Fossil")

    Conversion:
        TJ/EUR-million → MJ/₹ crore
        = value × TJ_TO_MJ × 100 / EUR_INR[year]

    Returns DataFrame (163 rows) with columns:
        Sector_Index, Sector_Code, Sector_Name, Broad_Category,
        Energy_{year}_Final_TJ_per_EUR_million,
        Energy_{year}_Final_MJ_per_crore,
        Energy_{year}_Emission_TJ_per_EUR_million,
        Energy_{year}_Emission_MJ_per_crore,
    """
    section(f"Extracting EXIOBASE energy (Final + Emission) — {year}", log=log)
    if not f_path.exists():
        raise FileNotFoundError(f"EXIOBASE F.txt not found: {f_path}")

    raw = pd.read_csv(f_path, sep="\t", header=0, index_col=0, low_memory=False)
    ok(f"F.txt loaded: {raw.shape[0]} extensions × {raw.shape[1]} sectors", log)

    india_cols = [c for c in raw.columns if c == "IN" or c.startswith("IN.")]
    if len(india_cols) != 163:
        warn(f"Expected 163 India sectors, found {len(india_cols)}", log)
    ok(f"India sectors: {len(india_cols)}", log)

    eur_inr = EUR_INR[year]
    # TJ/EUR-M → MJ/₹ crore :  × TJ_TO_MJ × 100 / EUR_INR
    conv = TJ_TO_MJ * 100.0 / eur_inr

    def _extract_rows(prefix: str) -> pd.Series:
        """Sum all F.txt rows whose label starts with `prefix` for India cols."""
        matched = [r for r in raw.index if str(r).startswith(prefix)]
        if not matched:
            warn(f"No '{prefix}' rows found in F.txt — energy set to zero", log)
            return pd.Series(0.0, index=india_cols)
        ok(f"'{prefix}' rows matched ({len(matched)}): {matched[:3]}"
           + (" …" if len(matched) > 3 else ""), log)
        return (
            raw.loc[matched, india_cols]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0)
            .sum(axis=0)
        )

    final_tj    = _extract_rows(ENERGY_ROW_FINAL)
    emission_tj = _extract_rows(ENERGY_ROW_EMISSION)

    final_mj_cr    = final_tj    * conv
    emission_mj_cr = emission_tj * conv

    rows = []
    for i, code in enumerate(india_cols):
        rows.append({
            "Sector_Index":   i,
            "Sector_Code":    code,
            "Sector_Name":    SECTOR_LABELS.get(code, f"Sector {i}"),
            "Broad_Category": broad_category(i),
            f"Energy_{year}_Final_TJ_per_EUR_million":    float(final_tj.iloc[i]),
            f"Energy_{year}_Final_MJ_per_crore":          float(final_mj_cr.iloc[i]),
            f"Energy_{year}_Emission_TJ_per_EUR_million": float(emission_tj.iloc[i]),
            f"Energy_{year}_Emission_MJ_per_crore":       float(emission_mj_cr.iloc[i]),
            "Extrapolated": False,
        })

    df = pd.DataFrame(rows)
    final_col    = f"Energy_{year}_Final_MJ_per_crore"
    emission_col = f"Energy_{year}_Emission_MJ_per_crore"

    f_nz = (df[final_col]    > 0).sum()
    e_nz = (df[emission_col] > 0).sum()
    ok(f"Final:    {df[final_col].sum():,.1f} MJ/crore total  |  {f_nz}/163 non-zero", log)
    ok(f"Emission: {df[emission_col].sum():,.1f} MJ/crore total  |  {e_nz}/163 non-zero", log)

    emission_share = (
        100 * df[emission_col].sum() / max(df[final_col].sum(), 1e-9)
    )
    ok(f"Emission/Final ratio: {emission_share:.1f}% (fossil share of total energy)", log)

    top_n(df, final_col, "Sector_Name", n=10, unit=" MJ/cr",
          pct_base=df[final_col].sum(), log=log)
    return df


def extrapolate_from_prior(
    prior_df: pd.DataFrame,
    prior_year: str,
    target_year: str,
    log: Logger = None,
) -> pd.DataFrame:
    """
    Fallback for missing F.txt: scale prior-year coefficients by the NAS
    energy-sector growth ratio (Electricity sector GVA as proxy for
    economy-wide energy intensity change).

    Formula:
        coeff_target = coeff_prior × NAS_growth_ratio(Electricity, target_year)
                                   / NAS_growth_ratio(Electricity, prior_year)
    All output rows are flagged Extrapolated=True.
    """
    warn(
        f"F.txt missing for {target_year} — extrapolating from {prior_year} "
        "using NAS Electricity GVA growth ratio",
        log,
    )
    # Use Electricity sector as energy intensity proxy
    elec_key = "Electricity"
    prior_g  = NAS_GROWTH_RATES.get(elec_key, {}).get(prior_year,  1.0)
    target_g = NAS_GROWTH_RATES.get(elec_key, {}).get(target_year, 1.0)
    scale    = target_g / max(prior_g, 1e-9)
    ok(f"NAS Electricity ratio {prior_year}→{target_year}: {scale:.4f}", log)

    df = prior_df.copy()
    prior_final_col    = f"Energy_{prior_year}_Final_MJ_per_crore"
    prior_emission_col = f"Energy_{prior_year}_Emission_MJ_per_crore"
    target_final_col    = f"Energy_{target_year}_Final_MJ_per_crore"
    target_emission_col = f"Energy_{target_year}_Emission_MJ_per_crore"

    df[f"Energy_{target_year}_Final_TJ_per_EUR_million"]    = (
        df.get(f"Energy_{prior_year}_Final_TJ_per_EUR_million", 0) * scale
    )
    df[f"Energy_{target_year}_Emission_TJ_per_EUR_million"] = (
        df.get(f"Energy_{prior_year}_Emission_TJ_per_EUR_million", 0) * scale
    )
    df[target_final_col]    = df[prior_final_col]    * scale
    df[target_emission_col] = df[prior_emission_col] * scale
    df["Extrapolated"] = True

    ok(
        f"Extrapolated {target_year} Final: {df[target_final_col].sum():,.1f} MJ/crore  "
        f"(×{scale:.4f} vs {prior_year})",
        log,
    )
    return df


# ══════════════════════════════════════════════════════════════════════════════
# PART 2 — Concordance  (163 EXIOBASE → 75 categories)
# ══════════════════════════════════════════════════════════════════════════════
# Intentionally identical mapping to build_water_coefficients.get_concordance()
# so that sector alignment between water and energy results is guaranteed.

def get_concordance() -> dict:
    """
    Returns the same 163→75-category concordance used by the water pipeline.
    Energy coefficients are aggregated by summing all EXIOBASE codes in each
    category (same logic as water — average not used because energy is additive).
    """
    return {
        # ── AGRICULTURE ────────────────────────────────────────────────────────
        "AGR_001": {"name": "Paddy",               "sut": [1],         "exio": ["IN"],               "cat": "Agriculture"},
        "AGR_002": {"name": "Wheat",               "sut": [2],         "exio": ["IN.1"],             "cat": "Agriculture"},
        "AGR_003": {"name": "Sugarcane",           "sut": [12],        "exio": ["IN.5"],             "cat": "Agriculture"},
        "AGR_004": {"name": "Milk (Raw)",          "sut": [21],        "exio": ["IN.13"],            "cat": "Agriculture"},
        "AGR_005": {"name": "Wool/Silk",           "sut": [22],        "exio": ["IN.14"],            "cat": "Agriculture"},
        "AGR_006": {"name": "Egg & Poultry (Live)","sut": [23],        "exio": ["IN.10"],            "cat": "Agriculture"},
        "AGR_M01": {"name": "Cereals & Pulses",    "sut": [3,4,5,6],   "exio": ["IN.2"],             "cat": "Agriculture"},
        "AGR_M02": {"name": "Oil Seeds",           "sut": [7,8,9],     "exio": ["IN.4"],             "cat": "Agriculture"},
        "AGR_M03": {"name": "Cotton & Jute",       "sut": [10,11],     "exio": ["IN.6"],             "cat": "Agriculture"},
        "AGR_M04": {"name": "Fruits & Vegetables", "sut": [13,18,19],  "exio": ["IN.3"],             "cat": "Agriculture"},
        "AGR_M05": {"name": "Other Crops",         "sut": [14,15,16,17,20], "exio": ["IN.7"],        "cat": "Agriculture"},
        "AGR_M06": {"name": "Other Livestock",     "sut": [24],        "exio": ["IN.8","IN.9","IN.11","IN.12"], "cat": "Agriculture"},
        "AGR_M07": {"name": "Forestry",            "sut": [25,26,27],  "exio": ["IN.15"],            "cat": "Agriculture"},
        "AGR_M08": {"name": "Fishing",             "sut": [28,29],     "exio": ["IN.16"],            "cat": "Agriculture"},
        # ── MINING ────────────────────────────────────────────────────────────
        "MIN_001": {"name": "Crude Petroleum",     "sut": [32],        "exio": ["IN.25"],            "cat": "Mining"},
        "MIN_002": {"name": "Natural Gas",         "sut": [31],        "exio": ["IN.26"],            "cat": "Mining"},
        "MIN_003": {"name": "Iron Ore",            "sut": [33],        "exio": ["IN.30"],            "cat": "Mining"},
        "MIN_004": {"name": "Copper Ore",          "sut": [36],        "exio": ["IN.31"],            "cat": "Mining"},
        "MIN_M01": {"name": "Coal & Lignite",      "sut": [30],
                    "exio": ["IN.17","IN.18","IN.19","IN.20","IN.21","IN.22","IN.23","IN.24"], "cat": "Mining"},
        "MIN_M02": {"name": "Other Metallic Minerals", "sut": [34,35,37], "exio": ["IN.32","IN.33"], "cat": "Mining"},
        "MIN_M03": {"name": "Non-Metallic Minerals","sut": [38,39,40], "exio": ["IN.27","IN.28","IN.29"], "cat": "Mining"},
        # ── FOOD MANUFACTURING ─────────────────────────────────────────────────
        "FOOD_001": {"name": "Processed Poultry",  "sut": [41],        "exio": ["IN.36"],            "cat": "Food Mfg"},
        "FOOD_002": {"name": "Processed Fish",     "sut": [43],        "exio": ["IN.44"],            "cat": "Food Mfg"},
        "FOOD_003": {"name": "Dairy Products",     "sut": [45],        "exio": ["IN.39"],            "cat": "Food Mfg"},
        "FOOD_004": {"name": "Sugar",              "sut": [48],        "exio": ["IN.41"],            "cat": "Food Mfg"},
        "FOOD_005": {"name": "Tobacco Products",   "sut": [55],        "exio": ["IN.45"],            "cat": "Food Mfg"},
        "FOOD_M01": {"name": "Processed Meat",     "sut": [42],        "exio": ["IN.34","IN.35","IN.37"], "cat": "Food Mfg"},
        "FOOD_M02": {"name": "Processed Fruit/Veg","sut": [44],        "exio": ["IN.42"],            "cat": "Food Mfg"},
        "FOOD_M03": {"name": "Edible Oils",        "sut": [46],        "exio": ["IN.38"],            "cat": "Food Mfg"},
        "FOOD_M04": {"name": "Grain Mill & Bakery","sut": [47,49],     "exio": ["IN.40"],            "cat": "Food Mfg"},
        "FOOD_M05": {"name": "Misc Food Products", "sut": [50],        "exio": [],                   "cat": "Food Mfg"},
        "FOOD_M06": {"name": "Beverages",          "sut": [51,52],     "exio": ["IN.43"],            "cat": "Food Mfg"},
        "FOOD_M07": {"name": "Processed Tea/Coffee","sut": [53,54],    "exio": [],                   "cat": "Food Mfg"},
        # ── TEXTILES ──────────────────────────────────────────────────────────
        "TEXT_001": {"name": "Ready Made Garments","sut": [61],        "exio": ["IN.47"],            "cat": "Textiles"},
        "TEXT_002": {"name": "Leather Footwear",   "sut": [63],        "exio": ["IN.48"],            "cat": "Textiles"},
        "TEXT_M01": {"name": "Textiles",           "sut": [56,57,58,59,60,62], "exio": ["IN.46"],    "cat": "Textiles"},
        "TEXT_M02": {"name": "Leather (excl Ftwr)","sut": [64],        "exio": [],                   "cat": "Textiles"},
        # ── WOOD & PAPER ──────────────────────────────────────────────────────
        "WOOD_M01": {"name": "Wood & Furniture",   "sut": [65,68],     "exio": ["IN.49"],            "cat": "Manufacturing"},
        "WOOD_M02": {"name": "Paper Products",     "sut": [66],        "exio": ["IN.50","IN.51","IN.52","IN.138","IN.162"], "cat": "Manufacturing"},
        "WOOD_M03": {"name": "Printing/Publishing","sut": [67],        "exio": ["IN.53"],            "cat": "Manufacturing"},
        # ── CHEMICALS & PETROLEUM ─────────────────────────────────────────────
        "CHEM_M01": {"name": "Rubber & Plastics",  "sut": [69,70],
                     "exio": ["IN.71","IN.72","IN.75","IN.76","IN.77","IN.78","IN.79","IN.80","IN.81","IN.140"], "cat": "Manufacturing"},
        "CHEM_M02": {"name": "Petroleum Products", "sut": [71,72],
                     "exio": ["IN.54","IN.55","IN.56","IN.57","IN.58","IN.59","IN.60",
                              "IN.61","IN.62","IN.63","IN.64","IN.65","IN.66","IN.67",
                              "IN.68","IN.69","IN.70","IN.73","IN.74"],              "cat": "Manufacturing"},
        "CHEM_M03": {"name": "Fertilizers",        "sut": [75],        "exio": ["IN.89","IN.90"],    "cat": "Manufacturing"},
        "CHEM_M04": {"name": "Other Chemicals",    "sut": [73,74,76,77,78,79,80,81], "exio": ["IN.91"], "cat": "Manufacturing"},
        # ── METALS ────────────────────────────────────────────────────────────
        "METAL_M01": {"name": "Cement & Non-Metallic","sut": [82,83],  "exio": ["IN.139","IN.147"],  "cat": "Manufacturing"},
        "METAL_M02": {"name": "Iron & Steel",      "sut": [84,85,86],  "exio": ["IN.141"],           "cat": "Manufacturing"},
        "METAL_M03": {"name": "Non-Ferrous Metals", "sut": [87,88,89],
                      "exio": ["IN.142","IN.143","IN.144","IN.145","IN.146","IN.160","IN.161"], "cat": "Manufacturing"},
        # ── MACHINERY ─────────────────────────────────────────────────────────
        "MACH_M01": {"name": "Machinery",          "sut": [90,91,92,93,94],    "exio": [],           "cat": "Manufacturing"},
        "MACH_M02": {"name": "Electrical Machinery","sut": [95,96,97,98,100],  "exio": [],           "cat": "Manufacturing"},
        "MACH_M03": {"name": "Electronics",        "sut": [99,101,102,103],    "exio": [],           "cat": "Manufacturing"},
        "MACH_M04": {"name": "Transport Equipment","sut": [104,105,106,107,108,109,110], "exio": ["IN.110"], "cat": "Manufacturing"},
        # ── OTHER MANUFACTURING ────────────────────────────────────────────────
        "MISC_M01": {"name": "Gems & Jewellery",   "sut": [111],       "exio": [],                   "cat": "Manufacturing"},
        "MISC_M02": {"name": "Misc Manufacturing", "sut": [112],       "exio": [],                   "cat": "Manufacturing"},
        # ── UTILITIES ─────────────────────────────────────────────────────────
        "UTIL_M01": {"name": "Electricity, Heat & Energy", "sut": [114],
                     "exio": ["IN.82","IN.83","IN.84","IN.85","IN.86","IN.87","IN.88",
                              "IN.92","IN.93","IN.94","IN.95","IN.96","IN.97","IN.98",
                              "IN.99","IN.100","IN.101","IN.102","IN.103",
                              "IN.104","IN.105","IN.106","IN.107"],                  "cat": "Utilities"},
        "UTIL_M02": {"name": "Water Supply",       "sut": [115],       "exio": ["IN.108"],           "cat": "Utilities"},
        # ── CONSTRUCTION ──────────────────────────────────────────────────────
        "CONS_M01": {"name": "Construction",       "sut": [116],       "exio": ["IN.109"],           "cat": "Manufacturing"},
        # ── SERVICES ──────────────────────────────────────────────────────────
        "SERV_001": {"name": "Hotels & Restaurants","sut": [118],      "exio": ["IN.113"],           "cat": "Services"},
        "SERV_002": {"name": "Railway Transport",  "sut": [119],       "exio": ["IN.114"],           "cat": "Services"},
        "SERV_003": {"name": "Road Transport",     "sut": [120],       "exio": ["IN.115"],           "cat": "Services"},
        "SERV_004": {"name": "Air Transport",      "sut": [122],       "exio": ["IN.119"],           "cat": "Services"},
        "SERV_005": {"name": "Financial Services", "sut": [126],       "exio": ["IN.122","IN.123","IN.124"], "cat": "Services"},
        "SERV_006": {"name": "Real Estate",        "sut": [127],       "exio": ["IN.125"],           "cat": "Services"},
        "SERV_007": {"name": "Computer & R&D",     "sut": [128,129],   "exio": ["IN.127","IN.128"],  "cat": "Services"},
        "SERV_008": {"name": "Trade (Retail & Wholesale)", "sut": [117], "exio": ["IN.111","IN.112"], "cat": "Services"},
        "SERV_009": {"name": "Business Services",  "sut": [130],       "exio": ["IN.129"],           "cat": "Services"},
        "SERV_010": {"name": "Public Admin & Education","sut": [131],  "exio": ["IN.130","IN.131"],  "cat": "Services"},
        "SERV_011": {"name": "Defence",            "sut": [],          "exio": [],                   "cat": "Services"},
        "SERV_012": {"name": "Health & Social Work","sut": [132],      "exio": ["IN.132"],           "cat": "Services"},
        "SERV_013": {"name": "Sewage/Waste Mgmt",  "sut": [133],
                     "exio": ["IN.133","IN.148","IN.149","IN.150","IN.151","IN.152",
                              "IN.153","IN.154","IN.155","IN.156","IN.157","IN.158","IN.159"], "cat": "Services"},
        "SERV_016": {"name": "Waste Management",   "sut": [],          "exio": [],                   "cat": "Services"},
        "SERV_017": {"name": "Cultural & Rec Services","sut": [135],   "exio": ["IN.135"],           "cat": "Services"},
        "SERV_018": {"name": "Other Services",     "sut": [136,137],   "exio": ["IN.134","IN.136","IN.137"], "cat": "Services"},
        "SERV_019": {"name": "Post & Telecom",     "sut": [134],       "exio": ["IN.121"],           "cat": "Services"},
        "SERV_M02": {"name": "Pipeline/Water Transport","sut": [123],  "exio": ["IN.116","IN.117","IN.118"], "cat": "Services"},
        "SERV_M03": {"name": "Support & Travel Agencies","sut": [124], "exio": ["IN.120"],           "cat": "Services"},
        "SERV_M04": {"name": "Machinery Rental",   "sut": [125],       "exio": ["IN.126"],           "cat": "Services"},
    }


def self_check(concordance: dict, log: Logger = None) -> bool:
    """Verify no EXIOBASE code is mapped more than once."""
    seen: dict = defaultdict(list)
    for cat_id, info in concordance.items():
        for code in info["exio"]:
            seen[code].append(cat_id)
    dups = {k: v for k, v in seen.items() if len(v) > 1}
    for code, cats in dups.items():
        fail(f"Duplicate: {code} in {cats}", log)
    all_163  = set(["IN"] + [f"IN.{i}" for i in range(1, 163)])
    assigned = set(seen.keys())
    missing  = all_163 - assigned
    if missing:
        warn(
            f"{len(missing)} EXIOBASE India sectors unassigned (will receive zero energy): "
            f"{sorted(missing, key=lambda x: int(x.split('.')[1]) if '.' in x else 0)}",
            log,
        )
    if not dups:
        ok(f"Self-check: {len(assigned)} sectors assigned, {len(missing)} unassigned, 0 duplicates", log)
    return not bool(dups)


# ══════════════════════════════════════════════════════════════════════════════
# PART 3 — Build concordance table  (163 → 75 categories)
# ══════════════════════════════════════════════════════════════════════════════

def build_concordance_table(
    exio_df: pd.DataFrame,
    concordance: dict,
    final_col: str,
    emission_col: str,
    log: Logger = None,
) -> pd.DataFrame:
    """
    Aggregate 163-sector energy coefficients to 75 categories by summing.
    Energy is additive (unlike water where per-crore is averaged for water-
    intensive sub-sectors) — summing reflects total embodied energy per ₹ crore
    of category demand.
    """
    exio_final    = dict(zip(exio_df["Sector_Code"], exio_df[final_col]))
    exio_emission = dict(zip(exio_df["Sector_Code"], exio_df[emission_col]))
    rows = []
    for cat_id, info in concordance.items():
        ef = sum(exio_final.get(code,    0) for code in info["exio"])
        ee = sum(exio_emission.get(code, 0) for code in info["exio"])
        rows.append({
            "Category_ID":        cat_id,
            "Category_Name":      info["name"],
            "Category_Type":      info["cat"],
            "N_EXIOBASE_Sectors": len(info["exio"]),
            "EXIOBASE_Sectors":   ",".join(info["exio"]),
            "SUT_Product_IDs":    ",".join(map(str, info["sut"])),
            final_col:            ef,
            emission_col:         ee,
        })
    df = pd.DataFrame(rows)
    df["Emission_Final_ratio"] = (
        df[emission_col] / df[final_col].replace(0, float("nan"))
    ).fillna(0)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# PART 4 — Build SUT energy table  (75 categories → 140 products)
# ══════════════════════════════════════════════════════════════════════════════

def build_sut_energy_table(
    concordance_df: pd.DataFrame,
    products_df: pd.DataFrame,
    final_col: str,
    emission_col: str,
    log: Logger = None,
) -> pd.DataFrame:
    """
    Distribute category energy coefficients equally across mapped SUT products.
    Identical logic to build_water_coefficients.build_sut_water_table().
    """
    n = len(products_df)
    final_arr    = np.zeros(n)
    emission_arr = np.zeros(n)

    for _, row in concordance_df.iterrows():
        raw_ids = str(row["SUT_Product_IDs"])
        if not raw_ids.strip() or raw_ids.strip() in ("nan", ""):
            continue
        sut_ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]
        ef  = row[final_col]
        ee  = row[emission_col]
        per = len(sut_ids) if sut_ids else 1
        for sid in sut_ids:
            if 1 <= sid <= n:
                final_arr[sid - 1]    += ef / per
                emission_arr[sid - 1] += ee / per

    result = products_df.copy()
    result[final_col]    = final_arr
    result[emission_col] = emission_arr
    result["Emission_Final_ratio"] = (
        result[emission_col] / result[final_col].replace(0, float("nan"))
    ).fillna(0)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════════════════════════

def run(**kwargs):
    with Logger("build_energy_coefficients", DIRS["logs"]) as log:
        t = Timer()
        log.section("BUILD ENERGY COEFFICIENTS  (EXIOBASE → concordance → SUT 140)")
        log.info(f"Energy row (Final):    {ENERGY_ROW_FINAL}")
        log.info(f"Energy row (Emission): {ENERGY_ROW_EMISSION}")

        concordance_template = get_concordance()
        if not self_check(concordance_template, log):
            log.fail("Concordance self-check failed — aborting")
            return

        out_dir   = DIRS["concordance"]
        out_dir.mkdir(parents=True, exist_ok=True)
        exio_base = DIRS["exiobase"]

        yearly_extractions: dict = {}
        all_summaries: list      = []

        for study_year in STUDY_YEARS:
            cfg        = YEARS[study_year]
            io_year    = cfg["io_year"]
            io_tag     = cfg["io_tag"]
            water_year = cfg["water_year"]   # same tag used for energy year label
            final_col    = f"Energy_{water_year}_Final_MJ_per_crore"
            emission_col = f"Energy_{water_year}_Emission_MJ_per_crore"

            log.section(f"Year: {io_year}  (energy: {water_year})")

            # ── Locate F.txt ─────────────────────────────────────────────────
            _candidates = [
                exio_base / f"IOT_{water_year}_ixi" / "F.txt",
                exio_base / f"IOT_{water_year}_ixi" / "satellite" / "F.txt",
                exio_base / f"IOT_{water_year}_ixi" / "energy"    / "F.txt",
            ]
            f_path = next((p for p in _candidates if p.exists()), None)

            if f_path is None:
                # Attempt extrapolation from prior year (handles 2022 gap)
                prior_years = [y for y in STUDY_YEARS if y < study_year and y in yearly_extractions]
                if prior_years:
                    prior_key  = max(prior_years)
                    prior_data = yearly_extractions[prior_key]
                    exio_df    = extrapolate_from_prior(
                        prior_data, YEARS[prior_key]["water_year"], water_year, log
                    )
                else:
                    warn(
                        f"EXIOBASE F.txt not found for {water_year} and no prior year available. "
                        f"Tried:\n" + "\n".join(f"  {p}" for p in _candidates)
                        + "\nSkipping this year.",
                        log,
                    )
                    continue
            else:
                ok(f"F.txt found: {f_path}", log)
                exio_df = extract_india_energy(f_path, water_year, log)

            yearly_extractions[water_year] = exio_df

            # ── Audit save ────────────────────────────────────────────────────
            audit_dir = exio_base / "output" / water_year
            audit_dir.mkdir(parents=True, exist_ok=True)
            save_csv(exio_df, audit_dir / f"India_Energy_Coefficients_{water_year}.csv",
                     f"Raw energy extraction {water_year}", log=log)

            # ── Concordance + SUT ─────────────────────────────────────────────
            prod_file = DIRS["io"] / io_year / f"io_products_{io_tag}.csv"
            if not prod_file.exists():
                warn(f"Product list missing: {prod_file} — run build_io_tables.py first", log)
                continue
            products_df = pd.read_csv(prod_file)

            concordance_df = build_concordance_table(
                exio_df, concordance_template, final_col, emission_col, log
            )
            sut_df = build_sut_energy_table(
                concordance_df, products_df, final_col, emission_col, log
            )

            # Top energy-intensive categories
            top_n(concordance_df, final_col, "Category_Name", n=10, unit=" MJ/cr",
                  pct_base=concordance_df[final_col].sum(), log=log)

            save_csv(concordance_df, out_dir / f"concordance_energy_{io_tag}.csv",
                     f"Energy concordance {io_year}", log=log)
            save_csv(sut_df,         out_dir / f"energy_coefficients_140_{io_tag}.csv",
                     f"SUT energy {io_year}", log=log)

            extrapolated_n = int(exio_df.get("Extrapolated", pd.Series([False] * len(exio_df))).sum())
            all_summaries.append({
                "io_year":                    io_year,
                "water_year":                 water_year,
                "total_final_mj_crore":       round(concordance_df[final_col].sum(), 2),
                "total_emission_mj_crore":    round(concordance_df[emission_col].sum(), 2),
                "emission_final_ratio":       round(
                    concordance_df[emission_col].sum()
                    / max(concordance_df[final_col].sum(), 1e-9), 3
                ),
                "n_nonzero_final":            int((sut_df[final_col]    > 0).sum()),
                "n_nonzero_emission":         int((sut_df[emission_col] > 0).sum()),
                "extrapolated_sectors":       extrapolated_n,
            })

        # ── Cross-year comparison ─────────────────────────────────────────────
        if len(all_summaries) >= 2:
            log.section("Cross-Year Energy Intensity Comparison")
            compare_across_years(
                {r["io_year"]: r["total_final_mj_crore"]    for r in all_summaries},
                "Economy-wide Final energy intensity (MJ/crore)", unit=" MJ/cr", log=log,
            )
            compare_across_years(
                {r["io_year"]: r["emission_final_ratio"]    for r in all_summaries},
                "Emission/Final ratio (fossil share)", unit="", log=log,
            )
            save_csv(
                pd.DataFrame(all_summaries),
                out_dir / "energy_coefficients_summary.csv",
                "Energy coefficients summary", log=log,
            )

        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    run()
