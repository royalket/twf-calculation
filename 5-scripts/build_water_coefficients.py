"""
build_water_coefficients.py
============================
EXIOBASE F.txt → India 163-sector → 75-category concordance → 140 SUT products.

Changes vs previous version
----------------------------
- Now extracts BOTH blue and green water from F.txt in a single pass.
  Blue rows:  "Water Consumption Blue - ..."
  Green rows: "Water Consumption Green - ..."
- Output files carry both Water_{year}_Blue_m3_per_crore and
  Water_{year}_Green_m3_per_crore columns.
- calculate_indirect_twf.py uses the blue column for EEIO (unchanged behaviour);
  green column is reported separately for disclosure.
- All extraction logic is unified in extract_india_water() which returns one
  DataFrame with both colour columns.

Pipeline
--------
  F.txt (m³/EUR million) → India 163-sector coefficients (blue + green, m³/₹ crore)
        → 75-category concordance
        → 140 SUT products

Unit conversion
---------------
  EXIOBASE reports F in m³ per EUR million of output.
  EUR_INR[year] = average annual exchange rate.
  w [m³/EUR million] × 100/EUR_INR = w [m³/crore INR]
"""

import copy
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import BASE_DIR, DIRS, EUR_INR, YEARS, STUDY_YEARS
from utils import (
    section, subsection, ok, warn, fail, save_csv,
    check_conservation, top_n, compare_across_years,
    Timer, Logger,
)


# ══════════════════════════════════════════════════════════════════════════════
# SECTOR METADATA
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
# PART 1 — EXIOBASE extraction (blue + green, 163 India sectors)
# ══════════════════════════════════════════════════════════════════════════════

def extract_india_water(f_path: Path, year: str, log: Logger = None) -> pd.DataFrame:
    """
    Extract India blue AND green water coefficients from EXIOBASE F.txt.

    Blue rows  : index starts with "Water Consumption Blue"
    Green rows : index starts with "Water Consumption Green"

    Conversion: m³/EUR million → m³/₹ crore  using w × 100 / EUR_INR[year]

    Returns DataFrame with columns:
        Sector_Index, Sector_Code, Sector_Name, Broad_Category,
        Water_{year}_Blue_m3_per_EUR_million,
        Water_{year}_Blue_m3_per_crore,
        Water_{year}_Green_m3_per_EUR_million,
        Water_{year}_Green_m3_per_crore,
        Water_{year}_Total_m3_per_crore   (blue + green combined)
    """
    section(f"Extracting EXIOBASE water (blue + green) — {year}", log=log)
    if not f_path.exists():
        raise FileNotFoundError(f"EXIOBASE F.txt not found: {f_path}")

    raw = pd.read_csv(f_path, sep="\t", header=0, index_col=0, low_memory=False)
    ok(f"F.txt loaded: {raw.shape[0]} extensions × {raw.shape[1]} sectors", log)

    india_cols = [c for c in raw.columns if c == "IN" or c.startswith("IN.")]
    if len(india_cols) != 163:
        warn(f"Expected 163 India sectors, found {len(india_cols)}", log)
    ok(f"India sectors: {len(india_cols)}", log)

    eur_inr = EUR_INR[year]
    conv    = 100.0 / eur_inr  # m³/EUR million → m³/₹ crore

    def _extract_colour(prefix: str) -> pd.Series:
        """Sum all rows whose index starts with prefix for India columns."""
        matched = [r for r in raw.index if r.startswith(prefix)]
        if not matched:
            warn(f"No '{prefix}' rows found in F.txt — setting to zero", log)
            return pd.Series(0.0, index=india_cols)
        ok(f"'{prefix}' rows found: {matched}", log)
        return (
            raw.loc[matched, india_cols]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0)
            .sum(axis=0)
        )

    blue_eur  = _extract_colour("Water Consumption Blue")
    green_eur = _extract_colour("Water Consumption Green")

    blue_crore  = blue_eur  * conv
    green_crore = green_eur * conv
    total_crore = blue_crore + green_crore

    rows = []
    for i, code in enumerate(india_cols):
        rows.append({
            "Sector_Index":   i,
            "Sector_Code":    code,
            "Sector_Name":    SECTOR_LABELS.get(code, f"Sector {i}"),
            "Broad_Category": broad_category(i),
            f"Water_{year}_Blue_m3_per_EUR_million":  float(blue_eur.iloc[i]),
            f"Water_{year}_Blue_m3_per_crore":        float(blue_crore.iloc[i]),
            f"Water_{year}_Green_m3_per_EUR_million": float(green_eur.iloc[i]),
            f"Water_{year}_Green_m3_per_crore":       float(green_crore.iloc[i]),
            f"Water_{year}_Total_m3_per_crore":       float(total_crore.iloc[i]),
        })

    df = pd.DataFrame(rows)
    blue_col  = f"Water_{year}_Blue_m3_per_crore"
    green_col = f"Water_{year}_Green_m3_per_crore"
    total_col = f"Water_{year}_Total_m3_per_crore"

    b_nz = (df[blue_col]  > 0).sum()
    g_nz = (df[green_col] > 0).sum()
    ok(
        f"Blue:  {df[blue_col].sum():,.1f} m³/crore total  |  {b_nz}/163 non-zero",
        log,
    )
    ok(
        f"Green: {df[green_col].sum():,.1f} m³/crore total  |  {g_nz}/163 non-zero",
        log,
    )
    ok(
        f"Green share of total: "
        f"{100*df[green_col].sum()/max(df[total_col].sum(),1e-9):.1f}%",
        log,
    )
    top_n(df, blue_col, "Sector_Name", n=10, unit=" m³/cr",
          pct_base=df[blue_col].sum(), log=log)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# PART 2 — Concordance (163 EXIOBASE → 75 categories → 140 SUT products)
# ══════════════════════════════════════════════════════════════════════════════

def get_concordance() -> dict:
    """
    Master concordance: maps each of the 163 EXIOBASE India sectors to one
    of 75 categories, and each category to one or more of the 140 SUT products.
    Invariant: every EXIOBASE code IN through IN.137 appears in EXACTLY ONE entry.
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
        "AGR_M05": {"name": "Other Crops",         "sut": [14,15,16,17,20],"exio": ["IN.7"],         "cat": "Agriculture"},
        "AGR_M06": {"name": "Other Livestock",     "sut": [24],        "exio": ["IN.8","IN.9","IN.11","IN.12"],"cat": "Agriculture"},
        "AGR_M07": {"name": "Forestry",            "sut": [25,26,27],  "exio": ["IN.15"],            "cat": "Agriculture"},
        "AGR_M08": {"name": "Fishing",             "sut": [28,29],     "exio": ["IN.16"],            "cat": "Agriculture"},
        # ── MINING ────────────────────────────────────────────────────────────
        "MIN_001": {"name": "Crude Petroleum",     "sut": [32],        "exio": ["IN.25"],            "cat": "Mining"},
        "MIN_002": {"name": "Natural Gas",         "sut": [31],        "exio": ["IN.26"],            "cat": "Mining"},
        "MIN_003": {"name": "Iron Ore",            "sut": [33],        "exio": ["IN.30"],            "cat": "Mining"},
        "MIN_004": {"name": "Copper Ore",          "sut": [36],        "exio": ["IN.31"],            "cat": "Mining"},
        "MIN_M01": {"name": "Coal & Lignite",      "sut": [30],
                    "exio": ["IN.17","IN.18","IN.19","IN.20","IN.21","IN.22","IN.23","IN.24"],"cat": "Mining"},
        "MIN_M02": {"name": "Other Metallic Minerals","sut": [34,35,37],"exio": ["IN.32","IN.33"],   "cat": "Mining"},
        "MIN_M03": {"name": "Non-Metallic Minerals","sut": [38,39,40], "exio": ["IN.27","IN.28","IN.29"],"cat": "Mining"},
        # ── FOOD MANUFACTURING ─────────────────────────────────────────────────
        "FOOD_001": {"name": "Processed Poultry",  "sut": [41],        "exio": ["IN.36"],            "cat": "Food Mfg"},
        "FOOD_002": {"name": "Processed Fish",     "sut": [43],        "exio": ["IN.44"],            "cat": "Food Mfg"},
        "FOOD_003": {"name": "Dairy Products",     "sut": [45],        "exio": ["IN.39"],            "cat": "Food Mfg"},
        "FOOD_004": {"name": "Sugar",              "sut": [48],        "exio": ["IN.41"],            "cat": "Food Mfg"},
        "FOOD_005": {"name": "Tobacco Products",   "sut": [55],        "exio": ["IN.45"],            "cat": "Food Mfg"},
        "FOOD_M01": {"name": "Processed Meat",     "sut": [42],        "exio": ["IN.34","IN.35","IN.37"],"cat": "Food Mfg"},
        "FOOD_M02": {"name": "Processed Fruit/Veg","sut": [44],        "exio": ["IN.42"],            "cat": "Food Mfg"},
        "FOOD_M03": {"name": "Edible Oils",        "sut": [46],        "exio": ["IN.38"],            "cat": "Food Mfg"},
        "FOOD_M04": {"name": "Grain Mill & Bakery","sut": [47,49],     "exio": ["IN.40"],            "cat": "Food Mfg"},
        "FOOD_M05": {"name": "Misc Food Products", "sut": [50],        "exio": [],                   "cat": "Food Mfg"},
        "FOOD_M06": {"name": "Beverages",          "sut": [51,52],     "exio": ["IN.43"],            "cat": "Food Mfg"},
        "FOOD_M07": {"name": "Processed Tea/Coffee","sut": [53,54],    "exio": [],                   "cat": "Food Mfg"},
        # ── TEXTILES ──────────────────────────────────────────────────────────
        "TEXT_001": {"name": "Ready Made Garments","sut": [61],        "exio": ["IN.47"],            "cat": "Textiles"},
        "TEXT_002": {"name": "Leather Footwear",   "sut": [63],        "exio": ["IN.48"],            "cat": "Textiles"},
        "TEXT_M01": {"name": "Textiles",           "sut": [56,57,58,59,60,62],"exio": ["IN.46"],    "cat": "Textiles"},
        "TEXT_M02": {"name": "Leather (excl. Ftwr)","sut": [64],       "exio": [],                   "cat": "Textiles"},
        # ── WOOD & PAPER ──────────────────────────────────────────────────────
        "WOOD_M01": {"name": "Wood & Furniture",   "sut": [65,68],     "exio": ["IN.49"],            "cat": "Manufacturing"},
        "WOOD_M02": {"name": "Paper Products",     "sut": [66],        "exio": ["IN.50","IN.51","IN.52","IN.138","IN.162"],"cat": "Manufacturing"},
        "WOOD_M03": {"name": "Printing/Publishing","sut": [67],        "exio": ["IN.53"],            "cat": "Manufacturing"},
        # ── CHEMICALS & PETROLEUM ─────────────────────────────────────────────
        "CHEM_M01": {"name": "Rubber & Plastics",  "sut": [69,70],
                     "exio": ["IN.71","IN.72","IN.75","IN.76","IN.77","IN.78","IN.79","IN.80","IN.81","IN.140"],"cat": "Manufacturing"},
        "CHEM_M02": {"name": "Petroleum Products", "sut": [71,72],
                     "exio": ["IN.54","IN.55","IN.56","IN.57","IN.58","IN.59","IN.60",
                              "IN.61","IN.62","IN.63","IN.64","IN.65","IN.66","IN.67",
                              "IN.68","IN.69","IN.70","IN.73","IN.74"],              "cat": "Manufacturing"},
        "CHEM_M03": {"name": "Fertilizers",        "sut": [75],        "exio": ["IN.89","IN.90"],    "cat": "Manufacturing"},
        "CHEM_M04": {"name": "Other Chemicals",    "sut": [73,74,76,77,78,79,80,81],"exio": ["IN.91"],"cat": "Manufacturing"},
        # ── METALS ────────────────────────────────────────────────────────────
        "METAL_M01": {"name": "Cement & Non-Metallic","sut": [82,83],  "exio": ["IN.139","IN.147"],  "cat": "Manufacturing"},
        "METAL_M02": {"name": "Iron & Steel",      "sut": [84,85,86],  "exio": ["IN.141"],           "cat": "Manufacturing"},
        "METAL_M03": {"name": "Non-Ferrous Metals", "sut": [87,88,89],
                      "exio": ["IN.142","IN.143","IN.144","IN.145","IN.146","IN.160","IN.161"],"cat": "Manufacturing"},
        # ── MACHINERY ─────────────────────────────────────────────────────────
        "MACH_M01": {"name": "Machinery",          "sut": [90,91,92,93,94],"exio": [],               "cat": "Manufacturing"},
        "MACH_M02": {"name": "Electrical Machinery","sut": [95,96,97,98,100],"exio": [],             "cat": "Manufacturing"},
        "MACH_M03": {"name": "Electronics",        "sut": [99,101,102,103],"exio": [],               "cat": "Manufacturing"},
        "MACH_M04": {"name": "Transport Equipment","sut": [104,105,106,107,108,109,110],"exio": ["IN.110"],"cat": "Manufacturing"},
        # ── OTHER MANUFACTURING ────────────────────────────────────────────────
        "MISC_M01": {"name": "Gems & Jewellery",   "sut": [111],       "exio": [],                   "cat": "Manufacturing"},
        "MISC_M02": {"name": "Misc Manufacturing", "sut": [112],       "exio": [],                   "cat": "Manufacturing"},
        # ── UTILITIES ─────────────────────────────────────────────────────────
        "UTIL_M01": {"name": "Electricity, Heat & Energy","sut": [114],
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
        "SERV_005": {"name": "Financial Services", "sut": [126],       "exio": ["IN.122","IN.123","IN.124"],"cat": "Services"},
        "SERV_006": {"name": "Real Estate",        "sut": [127],       "exio": ["IN.125"],           "cat": "Services"},
        "SERV_007": {"name": "Computer & R&D",     "sut": [128,129],   "exio": ["IN.127","IN.128"],  "cat": "Services"},
        # India SUT 117 = "Trade and repair services" — wholesale (IN.111) and retail (IN.112)
        # are aggregated into one product in the 140-sector table. Single entry, both EXIO codes.
        "SERV_008": {"name": "Trade (Retail & Wholesale)","sut": [117], "exio": ["IN.111","IN.112"],"cat": "Services"},
        "SERV_009": {"name": "Business Services",  "sut": [130],       "exio": ["IN.129"],           "cat": "Services"},
        # India SUT 131 = "Public administration, defence and education" (combined in 140-sector aggregate).
        # EXIOBASE separates them (IN.130 Public Admin, IN.131 Education); both feed into SUT 131.
        "SERV_010": {"name": "Public Admin & Education","sut": [131],  "exio": ["IN.130","IN.131"],  "cat": "Services"},
        # Defence: no EXIOBASE water coefficient; SUT product unclear — assigned empty to avoid duplication.
        "SERV_011": {"name": "Defence",            "sut": [],          "exio": [],                   "cat": "Services"},
        "SERV_012": {"name": "Health & Social Work","sut": [132],      "exio": ["IN.132"],           "cat": "Services"},
        "SERV_013": {"name": "Sewage/Waste Mgmt",  "sut": [133],
                     "exio": ["IN.133","IN.148","IN.149","IN.150","IN.151","IN.152",
                              "IN.153","IN.154","IN.155","IN.156","IN.157","IN.158","IN.159"],"cat": "Services"},
        # SERV_015 removed (was exact duplicate of SERV_012).
        # SERV_016 Waste Management: empty exio — no EXIOBASE water; SUT unclear, use empty sut.
        "SERV_016": {"name": "Waste Management",   "sut": [],          "exio": [],                   "cat": "Services"},
        "SERV_017": {"name": "Cultural & Rec Services","sut": [135],   "exio": ["IN.135"],           "cat": "Services"},
        "SERV_018": {"name": "Other Services",     "sut": [136,137],   "exio": ["IN.134","IN.136","IN.137"],"cat": "Services"},
        "SERV_019": {"name": "Post & Telecom",     "sut": [134],       "exio": ["IN.121"],           "cat": "Services"},
        "SERV_M02": {"name": "Pipeline/Water Transport","sut": [123],  "exio": ["IN.116","IN.117","IN.118"],"cat": "Services"},
        "SERV_M03": {"name": "Support & Travel Agencies","sut": [124], "exio": ["IN.120"],           "cat": "Services"},
        "SERV_M04": {"name": "Machinery Rental",   "sut": [125],       "exio": ["IN.126"],           "cat": "Services"},
        # IN.134 (Membership Orgs) merged into SERV_018 Other Services — SUT 136/137 already covers
        # community/personal/membership activity in India's 140-sector aggregate.
        # SERV_M05 removed: sut:[134] was duplicating Post & Telecom (SERV_019).
    }


def self_check(concordance: dict, log: Logger = None) -> bool:
    seen = defaultdict(list)
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
            f"{len(missing)} EXIOBASE India sectors not assigned (will receive zero water): "
            f"{sorted(missing, key=lambda x: int(x.split('.')[1]) if '.' in x else 0)}",
            log,
        )
    if not dups:
        ok(f"Self-check: {len(assigned)} sectors assigned, {len(missing)} unassigned, 0 duplicates", log)
    return not bool(dups)


def check_steam_product(products_df: pd.DataFrame, concordance: dict, log: Logger = None) -> dict:
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


def build_concordance_table(exio_df: pd.DataFrame, concordance: dict,
                             blue_col: str, green_col: str,
                             log: Logger = None) -> pd.DataFrame:
    """
    Aggregate sector water coefficients to 75 categories.
    Both blue and green columns are propagated.
    """
    exio_blue  = dict(zip(exio_df["Sector_Code"], exio_df[blue_col]))
    exio_green = dict(zip(exio_df["Sector_Code"], exio_df[green_col]))
    rows = []
    for cat_id, info in concordance.items():
        wb = sum(exio_blue.get(code,  0) for code in info["exio"])
        wg = sum(exio_green.get(code, 0) for code in info["exio"])
        rows.append({
            "Category_ID":        cat_id,
            "Category_Name":      info["name"],
            "Category_Type":      info["cat"],
            "N_EXIOBASE_Sectors": len(info["exio"]),
            "EXIOBASE_Sectors":   ",".join(info["exio"]),
            "SUT_Product_IDs":    ",".join(map(str, info["sut"])),
            blue_col:             wb,
            green_col:            wg,
        })
    df = pd.DataFrame(rows)
    df["Green_share_pct"] = 100 * df[green_col] / (df[blue_col] + df[green_col]).replace(0, float("nan"))
    return df


def build_sut_water_table(concordance_df: pd.DataFrame, products_df: pd.DataFrame,
                           blue_col: str, green_col: str,
                           log: Logger = None) -> pd.DataFrame:
    """Distribute category water coefficients equally across mapped SUT products."""
    n = len(products_df)
    blue_arr  = np.zeros(n)
    green_arr = np.zeros(n)

    for _, row in concordance_df.iterrows():
        raw_ids = str(row["SUT_Product_IDs"])
        sut_ids = [int(x) for x in raw_ids.split(",") if x.strip() and x.strip().isdigit()]
        if not raw_ids.strip() or raw_ids.strip() in ("nan", ""):
            continue  # entry has no SUT products (e.g. Defence with empty sut list)
        wb = row[blue_col]
        wg = row[green_col]
        per = len(sut_ids) if sut_ids else 1
        for sid in sut_ids:
            if 1 <= sid <= n:
                blue_arr[sid - 1]  += wb / per
                green_arr[sid - 1] += wg / per

    result = products_df.copy()
    result[blue_col]  = blue_arr
    result[green_col] = green_arr
    result["Green_share_pct"] = (
        100 * result[green_col] / (result[blue_col] + result[green_col]).replace(0, float("nan"))
    ).fillna(0)
    return result


def report_green_blue_split(concordance_df: pd.DataFrame, blue_col: str,
                             green_col: str, log: Logger = None):
    """Log the agriculture vs total green water share — key metric for the paper."""
    subsection("Blue vs Green water split by category type", log)
    for cat_type, grp in concordance_df.groupby("Category_Type"):
        b = grp[blue_col].sum()
        g = grp[green_col].sum()
        t = b + g
        if t == 0:
            continue
        line = (f"    {cat_type:<20}  Blue: {b:>10,.1f}  Green: {g:>10,.1f}  "
                f"Green%: {100*g/t:>5.1f}%")
        if log:
            log.info(line)
        else:
            print(line)

    # Agriculture summary — cite-worthy number
    agr = concordance_df[concordance_df["Category_Type"] == "Agriculture"]
    if not agr.empty:
        b = agr[blue_col].sum()
        g = agr[green_col].sum()
        t = b + g
        msg = (
            f"Agriculture: blue={b:,.1f}  green={g:,.1f}  "
            f"green share={100*g/t:.1f}% — "
            f"reflects rainfed irrigation dominance in India"
        )
        ok(msg, log)


def compare_water_years(yearly_dfs: dict, log: Logger = None) -> pd.DataFrame:
    section("Cross-Year Water Intensity Comparison (Blue + Green)", log=log)
    years = STUDY_YEARS

    # Build wide frame on blue column (primary for EEIO)
    base = yearly_dfs[years[0]][["Sector_Code", "Sector_Name", "Broad_Category",
                                  f"Water_{years[0]}_Blue_m3_per_crore"]].copy()
    for yr in years[1:]:
        col = f"Water_{yr}_Blue_m3_per_crore"
        base = base.merge(yearly_dfs[yr][["Sector_Code", col]], on="Sector_Code", how="left")

    base["Chg_2015_2019_pct"] = 100 * (
        base[f"Water_2019_Blue_m3_per_crore"] - base[f"Water_2015_Blue_m3_per_crore"]
    ) / base[f"Water_2015_Blue_m3_per_crore"].replace(0, float("nan"))
    base["Chg_2015_2022_pct"] = 100 * (
        base[f"Water_2022_Blue_m3_per_crore"] - base[f"Water_2015_Blue_m3_per_crore"]
    ) / base[f"Water_2015_Blue_m3_per_crore"].replace(0, float("nan"))

    totals = {yr: yearly_dfs[yr][f"Water_{yr}_Blue_m3_per_crore"].sum() for yr in years}
    compare_across_years(totals, "Economy-wide blue water intensity (m³/crore)", years, log=log)

    gtotals = {yr: yearly_dfs[yr][f"Water_{yr}_Green_m3_per_crore"].sum() for yr in years}
    compare_across_years(gtotals, "Economy-wide green water intensity (m³/crore)", years, log=log)

    improving = base.dropna(subset=["Chg_2015_2022_pct"])
    lines = ["\n  📉 Best improving sectors — blue intensity fell (2015→2022):"]
    for _, r in improving.nsmallest(5, "Chg_2015_2022_pct").iterrows():
        lines.append(f"     {r['Sector_Name']:<40}  {r['Chg_2015_2022_pct']:+.1f}%")
    lines.append("\n  📈 Worst sectors — blue intensity rose (2015→2022):")
    for _, r in improving.nlargest(5, "Chg_2015_2022_pct").iterrows():
        lines.append(f"     {r['Sector_Name']:<40}  {r['Chg_2015_2022_pct']:+.1f}%")
    output = "\n".join(lines)
    if log:
        log._log(output)
    else:
        print(output)

    return base


# ── Main ──────────────────────────────────────────────────────────────────────

def run(**kwargs):
    with Logger("build_water_coefficients", DIRS["logs"]) as log:
        t = Timer()
        log.section("BUILD WATER COEFFICIENTS  (EXIOBASE → concordance → SUT 140)")
        log.info("Extracting both BLUE and GREEN water from F.txt")

        concordance_template = get_concordance()
        if not self_check(concordance_template, log):
            log.fail("Concordance self-check failed — aborting")
            return

        out_dir    = DIRS["concordance"]
        out_dir.mkdir(parents=True, exist_ok=True)
        exio_base  = DIRS["exiobase"]

        yearly_extractions = {}
        all_summaries      = []

        for study_year in STUDY_YEARS:
            cfg        = YEARS[study_year]
            io_year    = cfg["io_year"]
            io_tag     = cfg["io_tag"]
            water_year = cfg["water_year"]
            blue_col   = f"Water_{water_year}_Blue_m3_per_crore"
            green_col  = f"Water_{water_year}_Green_m3_per_crore"

            log.section(f"Year: {io_year}  (water: {water_year})")

            # Part 1: extract from EXIOBASE
            # EXIOBASE F.txt location varies by download version and extraction method.
            # Try three common layouts in order:
            #   1. Standard EXIOBASE download root:    IOT_{year}_ixi/F.txt
            #   2. EXIOBASE "satellite" subfolder:     IOT_{year}_ixi/satellite/F.txt
            #   3. Legacy / custom "water" subfolder:  IOT_{year}_ixi/water/F.txt
            _candidates = [
                exio_base / f"IOT_{water_year}_ixi" / "F.txt",
                exio_base / f"IOT_{water_year}_ixi" / "satellite" / "F.txt",
                exio_base / f"IOT_{water_year}_ixi" / "water"     / "F.txt",
            ]
            f_path = next((p for p in _candidates if p.exists()), None)
            if f_path is None:
                warn(
                    f"EXIOBASE F.txt not found for {water_year}. Tried:\n"
                    + "\n".join(f"  {p}" for p in _candidates)
                    + "\nSkipping this year — existing concordance files will be reused.",
                    log,
                )
                continue
            ok(f"F.txt found: {f_path}", log)
            exio_df = extract_india_water(f_path, water_year, log)
            yearly_extractions[water_year] = exio_df

            audit_dir = exio_base / "output" / water_year
            audit_dir.mkdir(parents=True, exist_ok=True)
            save_csv(exio_df, audit_dir / f"India_Water_Coefficients_{water_year}.csv",
                     f"Raw extraction {water_year}", log=log)

            # Part 2: build concordance
            prod_file = DIRS["io"] / io_year / f"io_products_{io_tag}.csv"
            if not prod_file.exists():
                warn(f"Product list missing: {prod_file} — run build_io_tables.py first", log)
                continue
            products_df = pd.read_csv(prod_file)

            year_concordance = copy.deepcopy(concordance_template)
            year_concordance = check_steam_product(products_df, year_concordance, log)

            concordance_df = build_concordance_table(exio_df, year_concordance,
                                                      blue_col, green_col, log)
            sut_df         = build_sut_water_table(concordance_df, products_df,
                                                    blue_col, green_col, log)

            report_green_blue_split(concordance_df, blue_col, green_col, log)
            top_n(concordance_df, blue_col, "Category_Name", n=10,
                  unit=" m³/cr", pct_base=concordance_df[blue_col].sum(), log=log)

            save_csv(concordance_df, out_dir / f"concordance_{io_tag}.csv",
                     f"concordance {io_year}", log=log)
            save_csv(sut_df, out_dir / f"water_coefficients_140_{io_tag}.csv",
                     f"SUT water {io_year}", log=log)

            all_summaries.append({
                "io_year":                  io_year,
                "water_year":               water_year,
                "total_blue_m3_crore":      round(concordance_df[blue_col].sum(), 2),
                "total_green_m3_crore":     round(concordance_df[green_col].sum(), 2),
                "green_share_pct":          round(
                    100 * concordance_df[green_col].sum()
                    / max(concordance_df[blue_col].sum() + concordance_df[green_col].sum(), 1e-9),
                    1,
                ),
                "n_nonzero_blue":           int((sut_df[blue_col]  > 0).sum()),
                "n_nonzero_green":          int((sut_df[green_col] > 0).sum()),
            })

        # Part 3: cross-year comparison
        if len(yearly_extractions) == len(STUDY_YEARS):
            comparison = compare_water_years(yearly_extractions, log)
            save_csv(comparison, out_dir / "water_coefficients_year_comparison.csv",
                     "Year comparison", log=log)

        if all_summaries:
            save_csv(pd.DataFrame(all_summaries), out_dir / "water_intensity_trend.csv",
                     "Intensity trend", log=log)
            log.table(
                ["Year", "Blue m³/cr", "Green m³/cr", "Green%", "Blue non-zero", "Green non-zero"],
                [[s["water_year"], s["total_blue_m3_crore"], s["total_green_m3_crore"],
                  f"{s['green_share_pct']}%", s["n_nonzero_blue"], s["n_nonzero_green"]]
                 for s in all_summaries],
            )

        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    run()
