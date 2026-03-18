"""
build_coefficients.py
=====================
MERGE of build_water_coefficients.py + build_energy_coefficients.py.

Both stressors share identical pipeline:
    EXIOBASE F.txt → 163 India sectors → 75-category concordance → 140 SUT products

The only differences are:
  - which F.txt rows are extracted  (water: Blue/Green;  energy: Final/Emission)
  - unit conversion                 (water: m³/EUR-M → m³/₹cr;  energy: TJ/EUR-M → MJ/₹cr)
  - energy-only: extrapolation fallback when 2022 F.txt is missing

Entry points (called from main.py):
    run(stressor="water")
    run(stressor="energy")

# ─────────────────────────────────────────────────────────────────────────────
# TODO
# ─────────────────────────────────────────────────────────────────────────────
# TODO-1  Replace sys.path.insert with a proper package (pyproject.toml + pip install -e .)
#         so every file can use  `from config import ...`  without path hacking.
#
# TODO-2  Move SECTOR_LABELS, SECTOR_BROAD, broad_category() and get_concordance()
#         to config.py or a new concordance.py — they are shared data, not logic,
#         and should not live inside a pipeline script.
#
# TODO-3  Add TypedDict for the stressor config dicts (STRESSOR_CFG values)
#         so callers get IDE autocomplete and key-typo errors at type-check time.
#
# TODO-4  self_check() is identical for water and energy — it currently lives
#         here and was previously duplicated. If concordance moves to config.py
#         (TODO-2), self_check() should move to utils.py.
#
# TODO-5  Write regression tests for:
#           - extract_stressor(): water total should be > 0 for agriculture sectors
#           - build_sut_table(): sum of SUT products ≈ sum of concordance categories
#           - extrapolate_from_prior(): output > 0 and Extrapolated flag is set
#         These replace the "BUG FIX" comments in the original files.
# ─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import copy
import sys
from collections import defaultdict
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))   # TODO-1: remove after packaging
from config import (
    BASE_DIR, DIRS, EUR_INR, YEARS, STUDY_YEARS,
    TJ_TO_MJ, ENERGY_ROW_FINAL, ENERGY_ROW_EMISSION,
    NAS_GROWTH_RATES,
)
from utils import (
    section, subsection, ok, warn, fail, save_csv,
    check_conservation, top_n, compare_across_years,
    Timer, Logger,
)

Stressor = Literal["water", "energy"]

# ── Per-stressor configuration ────────────────────────────────────────────────
# All differences between water and energy pipelines are captured here.
# Functions below are stressor-agnostic and read from this dict.
STRESSOR_CFG: dict[str, dict] = {
    "water": {
        "row_prefixes": {                       # F.txt row label prefixes to sum
            "primary": "Water Consumption Blue",
            "secondary": "Water Consumption Green",
        },
        "col_suffix_primary":   "Blue_m3_per_crore",
        "col_suffix_secondary": "Green_m3_per_crore",
        "col_suffix_raw":       "Blue_m3_per_EUR_million",   # audit column
        "col_suffix_raw_sec":   "Green_m3_per_EUR_million",
        "unit_label":           "m³/crore",
        "conv_fn": lambda eur_inr: 100.0 / eur_inr,         # m³/EUR-M → m³/₹cr
        "concordance_file":     "concordance_{io_tag}.csv",
        "sut_file":             "water_coefficients_140_{io_tag}.csv",
        "audit_file":           "India_Water_Coefficients_{year}.csv",
        "ratio_col":            "Green_share_pct",
        "ratio_fn": lambda primary, secondary: (
            100 * secondary / (primary + secondary).replace(0, float("nan"))
        ),
        "extrapolate": False,
    },
    "energy": {
        "row_prefixes": {
            "primary":   ENERGY_ROW_FINAL,
            "secondary": ENERGY_ROW_EMISSION,
        },
        "col_suffix_primary":   "Final_MJ_per_crore",
        "col_suffix_secondary": "Emission_MJ_per_crore",
        "col_suffix_raw":       "Final_TJ_per_EUR_million",
        "col_suffix_raw_sec":   "Emission_TJ_per_EUR_million",
        "unit_label":           "MJ/crore",
        "conv_fn": lambda eur_inr: TJ_TO_MJ * 100.0 / eur_inr,  # TJ/EUR-M → MJ/₹cr
        "concordance_file":     "concordance_energy_{io_tag}.csv",
        "sut_file":             "energy_coefficients_140_{io_tag}.csv",
        "audit_file":           "India_Energy_Coefficients_{year}.csv",
        "ratio_col":            "Emission_Final_ratio",
        "ratio_fn": lambda primary, secondary: (
            (secondary / primary.replace(0, float("nan"))).fillna(0)
        ),
        "extrapolate": True,    # energy F.txt for 2022 may be missing
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# SECTOR METADATA  (shared by both stressors)
# TODO-2: move to config.py or concordance.py
# ══════════════════════════════════════════════════════════════════════════════

SECTOR_LABELS = {
    "IN": "Paddy rice",          "IN.1": "Wheat",              "IN.2": "Cereal grains nec",
    "IN.3": "Vegetables/fruit",  "IN.4": "Oil seeds",          "IN.5": "Sugar cane",
    "IN.6": "Plant fibres",      "IN.7": "Crops nec",          "IN.8": "Cattle",
    "IN.9": "Pigs",              "IN.10": "Poultry",           "IN.11": "Meat animals nec",
    "IN.12": "Animal products",  "IN.13": "Raw milk",          "IN.14": "Wool/silk",
    "IN.15": "Forestry",         "IN.16": "Fishing",           "IN.17": "Anthracite",
    "IN.18": "Coking Coal",      "IN.19": "Bituminous Coal",   "IN.20": "Sub-Bituminous Coal",
    "IN.21": "Patent Fuel",      "IN.22": "Lignite",           "IN.23": "BKB/Peat",
    "IN.24": "Peat",             "IN.25": "Crude petroleum",   "IN.26": "Natural gas",
    "IN.27": "Gas liquids",      "IN.28": "Other hydrocarbons","IN.29": "Uranium/thorium",
    "IN.30": "Iron ores",        "IN.31": "Copper ores",       "IN.32": "Nickel ores",
    "IN.33": "Aluminium ores",   "IN.34": "Meat cattle",       "IN.35": "Meat pigs",
    "IN.36": "Meat poultry",     "IN.37": "Meat nec",          "IN.38": "Vegetable oils",
    "IN.39": "Dairy products",   "IN.40": "Processed rice",    "IN.41": "Sugar",
    "IN.42": "Food products nec","IN.43": "Beverages",         "IN.44": "Fish products",
    "IN.45": "Tobacco products", "IN.46": "Textiles",          "IN.47": "Wearing apparel",
    "IN.48": "Leather products", "IN.49": "Wood products",     "IN.50": "Pulp",
    "IN.51": "Re-processed paper","IN.52": "Paper products",   "IN.53": "Printed matter",
    "IN.54": "Coke Oven Coke",   "IN.55": "Gas Coke",         "IN.56": "Coal Tar",
    "IN.57": "Gas Works Gas",    "IN.58": "Coke oven gas",     "IN.59": "Blast Furnace Gas",
    "IN.60": "Other recovered gases","IN.61": "Petroleum Refinery","IN.62": "Ethane",
    "IN.63": "LPG",              "IN.64": "Motor Gasoline",    "IN.65": "Aviation Gasoline",
    "IN.66": "Jet Fuel (gasoline)","IN.67": "Jet Fuel (kerosene)","IN.68": "Kerosene",
    "IN.69": "Gas/Diesel Oil",   "IN.70": "Heavy Fuel Oil",    "IN.71": "Refinery Gas",
    "IN.72": "Liquefied Refinery Gas","IN.73": "Refinery Feedstocks","IN.74": "Additives",
    "IN.75": "Other Hydrocarbons","IN.76": "White Spirit",     "IN.77": "Lubricants",
    "IN.78": "Bitumen",          "IN.79": "Paraffin Waxes",   "IN.80": "Petroleum Coke",
    "IN.81": "Non-spec Petroleum","IN.82": "Industrial Biofuels","IN.83": "Municipal wastes (renew)",
    "IN.84": "Solid biofuels",   "IN.85": "Other liquid biofuels","IN.86": "Municipal Wastes (non-renew)",
    "IN.87": "Solid biofuels (2)","IN.88": "Other liquid biofuels (2)","IN.89": "N-fertiliser",
    "IN.90": "P-fertiliser",     "IN.91": "Chemicals nec",    "IN.92": "Electricity coal",
    "IN.93": "Electricity gas",  "IN.94": "Electricity nuclear","IN.95": "Electricity hydro",
    "IN.96": "Electricity wind", "IN.97": "Electricity petroleum","IN.98": "Electricity biomass",
    "IN.99": "Electricity solar PV","IN.100": "Electricity solar thermal","IN.101": "Electricity tide",
    "IN.102": "Electricity geothermal","IN.103": "Electricity nec","IN.104": "Electricity transmission",
    "IN.105": "Electricity distribution","IN.106": "Gas distribution","IN.107": "Steam/hot water",
    "IN.108": "Water supply",    "IN.109": "Construction",    "IN.110": "Motor vehicles",
    "IN.111": "Wholesale trade", "IN.112": "Retail trade",    "IN.113": "Hotels and restaurants",
    "IN.114": "Railway transport","IN.115": "Road transport",  "IN.116": "Pipeline transport",
    "IN.117": "Sea/coastal transport","IN.118": "Inland water transport","IN.119": "Air transport",
    "IN.120": "Transport support/travel agencies","IN.121": "Post and telecom",
    "IN.122": "Financial services","IN.123": "Insurance",     "IN.124": "Financial auxiliaries",
    "IN.125": "Real estate",     "IN.126": "Machinery rental","IN.127": "Computer services",
    "IN.128": "R&D services",    "IN.129": "Business services","IN.130": "Public administration",
    "IN.131": "Education",       "IN.132": "Health and social work","IN.133": "Sewage/refuse",
    "IN.134": "Membership organizations","IN.135": "Recreational/cultural",
    "IN.136": "Other services",  "IN.137": "Private households",
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
# CONCORDANCE  (163 EXIOBASE → 75 categories → 140 SUT)
# Shared by both stressors — sector alignment is guaranteed identical.
# TODO-2: move to config.py or concordance.py
# ══════════════════════════════════════════════════════════════════════════════

def get_concordance() -> dict:
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
        "TEXT_M02": {"name": "Leather (excl. Ftwr)","sut": [64],       "exio": [],                   "cat": "Textiles"},
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


def self_check(concordance: dict, stressor: str, log: Logger = None) -> bool:
    """Verify no EXIOBASE code is mapped more than once. Shared by both stressors."""
    seen: dict = defaultdict(list)
    for cat_id, info in concordance.items():
        for code in info["exio"]:
            seen[code].append(cat_id)
    dups = {k: v for k, v in seen.items() if len(v) > 1}
    for code, cats in dups.items():
        fail(f"Duplicate [{stressor}]: {code} in {cats}", log)
    all_163  = set(["IN"] + [f"IN.{i}" for i in range(1, 163)])
    assigned = set(seen.keys())
    missing  = all_163 - assigned
    if missing:
        warn(
            f"{len(missing)} EXIOBASE India sectors unassigned (will receive zero {stressor}): "
            f"{sorted(missing, key=lambda x: int(x.split('.')[1]) if '.' in x else 0)}",
            log,
        )
    if not dups:
        ok(f"Self-check [{stressor}]: {len(assigned)} sectors assigned, "
           f"{len(missing)} unassigned, 0 duplicates", log)
    return not bool(dups)


def check_steam_product(products_df: pd.DataFrame, concordance: dict,
                         log: Logger = None) -> dict:
    """Water-specific: remap IN.107 (Steam) if it appears as a distinct SUT product."""
    match = products_df[
        products_df["Product_Name"].str.lower().str.contains("steam|hot water", na=False)
    ]
    if not match.empty:
        sut_id = int(match.iloc[0]["Product_ID"])
        warn(f"Steam product found in SUT (ID={sut_id}) — mapping IN.107 there", log)
        concordance["UTIL_M01"]["exio"] = [
            e for e in concordance["UTIL_M01"]["exio"] if e != "IN.107"
        ]
        concordance["SERV_STEAM"] = {
            "name": "Steam/Hot Water", "sut": [sut_id],
            "exio": ["IN.107"], "cat": "Services"
        }
    return concordance


# ══════════════════════════════════════════════════════════════════════════════
# PART 1 — EXIOBASE EXTRACTION  (universal for both stressors)
# ══════════════════════════════════════════════════════════════════════════════

def extract_stressor(f_path: Path, year: str, stressor: Stressor,
                     log: Logger = None) -> pd.DataFrame:
    """
    Extract primary + secondary stressor coefficients from EXIOBASE F.txt.

    Water:  primary = Blue (m³/crore),  secondary = Green (m³/crore)
    Energy: primary = Final (MJ/crore), secondary = Emission (MJ/crore)

    Unit conversion is handled by STRESSOR_CFG[stressor]["conv_fn"].
    Returns a 163-row DataFrame with Sector_Index, Sector_Code, Sector_Name,
    Broad_Category, and four stressor columns (raw + converted).
    """
    cfg = STRESSOR_CFG[stressor]
    section(f"Extracting EXIOBASE {stressor} — {year}", log=log)

    if not f_path.exists():
        raise FileNotFoundError(f"EXIOBASE F.txt not found: {f_path}")

    raw = pd.read_csv(f_path, sep="\t", header=0, index_col=0, low_memory=False)
    ok(f"F.txt loaded: {raw.shape[0]} extensions × {raw.shape[1]} sectors", log)

    india_cols = [c for c in raw.columns if c == "IN" or c.startswith("IN.")]
    if len(india_cols) != 163:
        warn(f"Expected 163 India sectors, found {len(india_cols)}", log)

    conv = cfg["conv_fn"](EUR_INR[year])

    def _sum_rows(prefix: str) -> pd.Series:
        matched = [r for r in raw.index if str(r).startswith(prefix)]
        if not matched:
            warn(f"No '{prefix}' rows found in F.txt — setting to zero", log)
            return pd.Series(0.0, index=india_cols)
        ok(f"'{prefix}' matched ({len(matched)}): {matched[:3]}"
           + (" …" if len(matched) > 3 else ""), log)
        return (
            raw.loc[matched, india_cols]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0)
            .sum(axis=0)
        )

    primary_raw   = _sum_rows(cfg["row_prefixes"]["primary"])
    secondary_raw = _sum_rows(cfg["row_prefixes"]["secondary"])
    primary_conv   = primary_raw   * conv
    secondary_conv = secondary_raw * conv

    rows = []
    for i, code in enumerate(india_cols):
        rows.append({
            "Sector_Index":   i,
            "Sector_Code":    code,
            "Sector_Name":    SECTOR_LABELS.get(code, f"Sector {i}"),
            "Broad_Category": broad_category(i),
            f"{stressor.capitalize()}_{year}_{cfg['col_suffix_raw']}":       float(primary_raw.iloc[i]),
            f"{stressor.capitalize()}_{year}_{cfg['col_suffix_primary']}":   float(primary_conv.iloc[i]),
            f"{stressor.capitalize()}_{year}_{cfg['col_suffix_raw_sec']}":   float(secondary_raw.iloc[i]),
            f"{stressor.capitalize()}_{year}_{cfg['col_suffix_secondary']}": float(secondary_conv.iloc[i]),
            "Extrapolated": False,
        })

    df = pd.DataFrame(rows)
    p_col = f"{stressor.capitalize()}_{year}_{cfg['col_suffix_primary']}"
    s_col = f"{stressor.capitalize()}_{year}_{cfg['col_suffix_secondary']}"
    ok(f"Primary:   {df[p_col].sum():,.1f} {cfg['unit_label']}  "
       f"| {(df[p_col] > 0).sum()}/163 non-zero", log)
    ok(f"Secondary: {df[s_col].sum():,.1f} {cfg['unit_label']}  "
       f"| {(df[s_col] > 0).sum()}/163 non-zero", log)
    top_n(df, p_col, "Sector_Name", n=10, unit=f" {cfg['unit_label']}",
          pct_base=df[p_col].sum(), log=log)
    return df


def extrapolate_from_prior(prior_df: pd.DataFrame, prior_year: str,
                            target_year: str, stressor: Stressor,
                            log: Logger = None) -> pd.DataFrame:
    """
    Energy-only fallback when F.txt is missing for target_year.
    Scales prior-year coefficients by NAS Electricity GVA growth ratio.
    All rows are flagged Extrapolated=True.
    """
    warn(
        f"F.txt missing for {target_year} — extrapolating from {prior_year} "
        "using NAS Electricity GVA growth ratio", log,
    )
    cfg      = STRESSOR_CFG[stressor]
    prior_g  = NAS_GROWTH_RATES.get("Electricity", {}).get(prior_year,  1.0)
    target_g = NAS_GROWTH_RATES.get("Electricity", {}).get(target_year, 1.0)
    scale    = target_g / max(prior_g, 1e-9)
    ok(f"NAS Electricity ratio {prior_year}→{target_year}: {scale:.4f}", log)

    df = prior_df.copy()
    for suffix in [cfg["col_suffix_primary"], cfg["col_suffix_secondary"],
                   cfg["col_suffix_raw"],     cfg["col_suffix_raw_sec"]]:
        prior_col  = f"{stressor.capitalize()}_{prior_year}_{suffix}"
        target_col = f"{stressor.capitalize()}_{target_year}_{suffix}"
        if prior_col in df.columns:
            df[target_col] = df[prior_col] * scale
    df["Extrapolated"] = True

    p_col = f"{stressor.capitalize()}_{target_year}_{cfg['col_suffix_primary']}"
    ok(f"Extrapolated {target_year} primary: {df[p_col].sum():,.1f} {cfg['unit_label']} "
       f"(×{scale:.4f} vs {prior_year})", log)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# PART 2 — CONCORDANCE TABLE  (163 → 75 categories)
# ══════════════════════════════════════════════════════════════════════════════

def build_concordance_table(exio_df: pd.DataFrame, concordance: dict,
                             primary_col: str, secondary_col: str,
                             stressor: Stressor,
                             log: Logger = None) -> pd.DataFrame:
    """Aggregate sector coefficients to 75 categories by summing."""
    cfg         = STRESSOR_CFG[stressor]
    exio_prim   = dict(zip(exio_df["Sector_Code"], exio_df[primary_col]))
    exio_sec    = dict(zip(exio_df["Sector_Code"], exio_df[secondary_col]))
    rows = []
    for cat_id, info in concordance.items():
        vp = sum(exio_prim.get(code, 0) for code in info["exio"])
        vs = sum(exio_sec.get(code, 0)  for code in info["exio"])
        rows.append({
            "Category_ID":        cat_id,
            "Category_Name":      info["name"],
            "Category_Type":      info["cat"],
            "N_EXIOBASE_Sectors": len(info["exio"]),
            "EXIOBASE_Sectors":   ",".join(info["exio"]),
            "SUT_Product_IDs":    ",".join(map(str, info["sut"])),
            primary_col:          vp,
            secondary_col:        vs,
        })
    df = pd.DataFrame(rows)
    df[cfg["ratio_col"]] = cfg["ratio_fn"](df[primary_col], df[secondary_col])
    return df


# ══════════════════════════════════════════════════════════════════════════════
# PART 3 — SUT TABLE  (75 categories → 140 products)
# ══════════════════════════════════════════════════════════════════════════════

def build_sut_table(concordance_df: pd.DataFrame, products_df: pd.DataFrame,
                     primary_col: str, secondary_col: str,
                     stressor: Stressor,
                     log: Logger = None) -> pd.DataFrame:
    """Distribute category coefficients equally across mapped SUT products."""
    cfg        = STRESSOR_CFG[stressor]
    n          = len(products_df)
    prim_arr   = np.zeros(n)
    sec_arr    = np.zeros(n)

    for _, row in concordance_df.iterrows():
        raw_ids = str(row["SUT_Product_IDs"])
        if not raw_ids.strip() or raw_ids.strip() in ("nan", ""):
            continue
        sut_ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]
        vp, vs  = row[primary_col], row[secondary_col]
        per     = len(sut_ids) if sut_ids else 1
        for sid in sut_ids:
            if 1 <= sid <= n:
                prim_arr[sid - 1] += vp / per
                sec_arr[sid - 1]  += vs / per

    result = products_df.copy()
    result[primary_col]   = prim_arr
    result[secondary_col] = sec_arr
    result[cfg["ratio_col"]] = cfg["ratio_fn"](
        pd.Series(prim_arr), pd.Series(sec_arr)
    ).fillna(0).values
    return result


# ══════════════════════════════════════════════════════════════════════════════
# RUN  (called from main.py with stressor="water" or "energy")
# ══════════════════════════════════════════════════════════════════════════════

def run(stressor: Stressor = "water", **kwargs):
    cfg_s = STRESSOR_CFG[stressor]

    with Logger(f"build_{stressor}_coefficients", DIRS["logs"]) as log:
        t = Timer()
        log.section(f"BUILD {stressor.upper()} COEFFICIENTS  (EXIOBASE → concordance → SUT 140)")

        concordance_template = get_concordance()
        if not self_check(concordance_template, stressor, log):
            log.fail("Concordance self-check failed — aborting")
            return

        out_dir   = DIRS["concordance"]
        out_dir.mkdir(parents=True, exist_ok=True)
        exio_base = DIRS["exiobase"]

        yearly_extractions: dict = {}
        all_summaries: list      = []

        for study_year in STUDY_YEARS:
            cfg_y      = YEARS[study_year]
            io_year    = cfg_y["io_year"]
            io_tag     = cfg_y["io_tag"]
            year_label = cfg_y["water_year"]
            primary_col   = f"{stressor.capitalize()}_{year_label}_{cfg_s['col_suffix_primary']}"
            secondary_col = f"{stressor.capitalize()}_{year_label}_{cfg_s['col_suffix_secondary']}"

            log.section(f"Year: {io_year}  ({stressor}: {year_label})")

            # ── Locate F.txt ─────────────────────────────────────────────────
            sub = "energy" if stressor == "energy" else "water"
            candidates = [
                exio_base / f"IOT_{year_label}_ixi" / "F.txt",
                exio_base / f"IOT_{year_label}_ixi" / "satellite" / "F.txt",
                exio_base / f"IOT_{year_label}_ixi" / sub / "F.txt",
            ]
            f_path = next((p for p in candidates if p.exists()), None)

            if f_path is None:
                if cfg_s["extrapolate"]:
                    # Energy fallback: extrapolate from most recent available year
                    prior_keys = [y for y in STUDY_YEARS if y < study_year
                                  and YEARS[y]["water_year"] in yearly_extractions]
                    if prior_keys:
                        prior_year  = YEARS[max(prior_keys)]["water_year"]
                        exio_df = extrapolate_from_prior(
                            yearly_extractions[prior_year], prior_year, year_label, stressor, log
                        )
                    else:
                        warn(f"F.txt not found for {year_label} and no prior year available. "
                             f"Tried:\n" + "\n".join(f"  {p}" for p in candidates)
                             + "\nSkipping.", log)
                        continue
                else:
                    warn(f"EXIOBASE F.txt not found for {year_label}. Tried:\n"
                         + "\n".join(f"  {p}" for p in candidates)
                         + "\nSkipping — existing files will be reused.", log)
                    continue
            else:
                ok(f"F.txt found: {f_path}", log)
                exio_df = extract_stressor(f_path, year_label, stressor, log)

            yearly_extractions[year_label] = exio_df

            # Audit save
            audit_dir = exio_base / "output" / year_label
            audit_dir.mkdir(parents=True, exist_ok=True)
            save_csv(exio_df, audit_dir / cfg_s["audit_file"].format(year=year_label),
                     f"Raw {stressor} extraction {year_label}", log=log)

            # ── Concordance + SUT ─────────────────────────────────────────────
            prod_file = DIRS["io"] / io_year / f"io_products_{io_tag}.csv"
            if not prod_file.exists():
                warn(f"Product list missing: {prod_file} — run build_io.py first", log)
                continue
            products_df = pd.read_csv(prod_file)

            year_concordance = copy.deepcopy(concordance_template)
            if stressor == "water":
                year_concordance = check_steam_product(products_df, year_concordance, log)

            concordance_df = build_concordance_table(
                exio_df, year_concordance, primary_col, secondary_col, stressor, log
            )
            sut_df = build_sut_table(
                concordance_df, products_df, primary_col, secondary_col, stressor, log
            )

            top_n(concordance_df, primary_col, "Category_Name", n=10,
                  unit=f" {cfg_s['unit_label']}",
                  pct_base=concordance_df[primary_col].sum(), log=log)

            save_csv(concordance_df,
                     out_dir / cfg_s["concordance_file"].format(io_tag=io_tag),
                     f"{stressor} concordance {io_year}", log=log)
            save_csv(sut_df,
                     out_dir / cfg_s["sut_file"].format(io_tag=io_tag),
                     f"SUT {stressor} {io_year}", log=log)

            extrapolated_n = int(exio_df.get("Extrapolated", pd.Series([False]*len(exio_df))).sum())
            all_summaries.append({
                "io_year":            io_year,
                "year_label":         year_label,
                "stressor":           stressor,
                "total_primary":      round(concordance_df[primary_col].sum(), 2),
                "total_secondary":    round(concordance_df[secondary_col].sum(), 2),
                "ratio":              round(
                    concordance_df[secondary_col].sum()
                    / max(concordance_df[primary_col].sum(), 1e-9), 3
                ),
                "n_nonzero_primary":  int((sut_df[primary_col]   > 0).sum()),
                "n_nonzero_secondary":int((sut_df[secondary_col] > 0).sum()),
                "extrapolated_n":     extrapolated_n,
            })

        # ── Cross-year comparison ─────────────────────────────────────────────
        if len(all_summaries) >= 2:
            compare_across_years(
                {r["io_year"]: r["total_primary"] for r in all_summaries},
                f"Economy-wide {stressor} primary intensity ({cfg_s['unit_label']})",
                unit=f" {cfg_s['unit_label']}", log=log,
            )
            save_csv(
                pd.DataFrame(all_summaries),
                out_dir / f"{stressor}_coefficients_summary.csv",
                f"{stressor} coefficients summary", log=log,
            )

        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--stressor", choices=["water", "energy"], default="water")
    run(stressor=ap.parse_args().stressor)
