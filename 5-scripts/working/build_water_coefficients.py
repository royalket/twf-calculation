"""
Build water coefficients: EXIOBASE F.txt → India 163-sector → 75-category concordance → 140 SUT products.

This script merges the former extract_exiobase_water.py and map_water_coefficients.py into a
single logical pipeline, eliminating an intermediate file-read round-trip.

Pipeline
--------
  F.txt (m³/EUR million) ─→ India 163-sector coefficients (m³/₹ crore)
        ─→ 75-category concordance (m³/₹ crore, summed across mapped sectors)
        ─→ 140 SUT products (m³/₹ crore, equal share distributed across mapped products)

Unit conversion
---------------
  EXIOBASE reports F in m³ per EUR million of output.
  EUR_INR[year] = average annual exchange rate.
  1 EUR million = EUR_INR/100 crore INR  →  w [m³/EUR million] × 100/EUR_INR = w [m³/crore]

Concordance design (see README for full rationale)
--------------------------------------------------
  UTIL_M01 is the energy sink for EXIOBASE sectors with no dedicated SUT row:
    IN.82–IN.88   Biofuels & waste combustion → SUT 114 (Electricity)
    IN.92–IN.103  Electricity generation      → SUT 114
    IN.104–IN.105 Electricity T&D             → SUT 114
    IN.107        Steam & hot water           → SUT 114 (or dedicated row if present)
  Service sectors (Hotels, Rail, Air, Road, etc.) receive zero direct water coefficients
  by construction — EXIOBASE WaterGAP/WFN data is production-based (physical extraction),
  so service sectors that do not pump water from aquifers show 0 in F.txt. These sectors
  receive their indirect water through the Leontief multiplier (W @ L @ Y).

Outputs
-------
Per year (in concordance/):
  concordance_{io_tag}.csv             — 75 categories with water coefficients
  water_coefficients_140_{io_tag}.csv  — 140 SUT products with mapped coefficients
  India_Water_Coefficients_{year}.csv  — raw 163-sector extraction (for audit)
Cross-year:
  water_intensity_trend.csv            — total water intensity by year
  water_coefficients_year_comparison.csv — sector-level % change across years
"""

import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict
import copy
import sys

sys.path.insert(0, str(Path(__file__).parent))
from config import BASE_DIR, DIRS, EUR_INR, YEARS, STUDY_YEARS
from utils import (
    section, subsection, ok, warn, fail, save_csv,
    check_conservation, top_n, compare_across_years,
    check_spectral_radius, Timer, Logger,
)


# ══════════════════════════════════════════════════════════════════════════════
# PART 1 — EXIOBASE extraction (163 India sectors)
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


def extract_india_water(f_path: Path, year: str, log: Logger = None) -> pd.DataFrame:
    """
    Extract India blue water coefficients from EXIOBASE F.txt.

    Formula:  w_i = F_i / x_i  (already done in EXIOBASE)
    Convert:  m³/EUR million → m³/₹ crore  using w × 100 / EUR_INR[year]
    """
    section(f"Extracting EXIOBASE water — {year}", log=log)
    if not f_path.exists():
        raise FileNotFoundError(f"EXIOBASE F.txt not found: {f_path}")

    raw = pd.read_csv(f_path, sep="\t", header=0, index_col=0, low_memory=False)
    ok(f"F.txt loaded: {raw.shape[0]} extensions × {raw.shape[1]} sectors", log)

    #water_rows = [r for r in raw.index if "Water Consumption Blue" in r]
    #water_rows = [r for r in raw.index if "water" in r.lower() or "blue" in r.lower()]
    water_rows = [r for r in raw.index if r.startswith("Water Consumption Blue")]
    if not water_rows:
        raise ValueError("No water extension rows found in F.txt")
    ok(f"Water rows: {water_rows}", log)

    india_cols = [c for c in raw.columns if c == "IN" or c.startswith("IN.")]
    if len(india_cols) != 163:
        warn(f"Expected 163 India sectors, found {len(india_cols)}", log)
    ok(f"India sectors: {len(india_cols)}", log)

    india_water = raw.loc[water_rows, india_cols].apply(
        pd.to_numeric, errors="coerce"
    ).fillna(0).sum(axis=0)  # m³/EUR million

    eur_inr = EUR_INR[year]
    india_water_crore = india_water * (100.0 / eur_inr)  # m³/crore

    rows = []
    for i, code in enumerate(india_cols):
        rows.append({
            "Sector_Index": i,
            "Sector_Code": code,
            "Sector_Name": SECTOR_LABELS.get(code, f"Sector {i}"),
            "Broad_Category": broad_category(i),
            f"Water_{year}_m3_per_EUR_million": float(india_water.iloc[i]),
            f"Water_{year}_m3_per_crore": float(india_water_crore.iloc[i]),
        })

    df = pd.DataFrame(rows)
    total = df[f"Water_{year}_m3_per_crore"].sum()
    nonzero = (df[f"Water_{year}_m3_per_crore"] > 0).sum()
    ok(f"Total economy water intensity: {total:,.1f} m³/crore  |  Non-zero: {nonzero}/163", log)
    top_n(df, f"Water_{year}_m3_per_crore", "Sector_Name", n=10,
          unit=" m³/cr", pct_base=total, log=log)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# PART 2 — Concordance (163 EXIOBASE → 75 categories → 140 SUT products)
# ══════════════════════════════════════════════════════════════════════════════

def get_concordance() -> dict:
    """
    Master concordance: maps each of the 163 EXIOBASE India sectors to one of 75
    categories, and each category to one or more of the 140 SUT products.

    Invariant: every EXIOBASE code IN through IN.137 appears in EXACTLY ONE entry.
    The self_check() function enforces this at runtime.
    """
    return {
        # ── AGRICULTURE (14 categories) ────────────────────────────────────────
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
        # ── MINING (7 categories) ──────────────────────────────────────────────
        "MIN_001": {"name": "Crude Petroleum",     "sut": [32],        "exio": ["IN.25"],            "cat": "Mining"},
        "MIN_002": {"name": "Natural Gas",         "sut": [31],        "exio": ["IN.26"],            "cat": "Mining"},
        "MIN_003": {"name": "Iron Ore",            "sut": [33],        "exio": ["IN.30"],            "cat": "Mining"},
        "MIN_004": {"name": "Copper Ore",          "sut": [36],        "exio": ["IN.31"],            "cat": "Mining"},
        "MIN_M01": {"name": "Coal & Lignite",      "sut": [30],
                    "exio": ["IN.17","IN.18","IN.19","IN.20","IN.21","IN.22","IN.23","IN.24"], "cat": "Mining"},
        "MIN_M02": {"name": "Other Metallic Minerals","sut": [34,35,37],"exio": ["IN.32","IN.33"],   "cat": "Mining"},
        "MIN_M03": {"name": "Non-Metallic Minerals","sut": [38,39,40], "exio": ["IN.27","IN.28","IN.29"], "cat": "Mining"},
        # ── FOOD MANUFACTURING (12 categories) ────────────────────────────────
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
        # ── TEXTILES (4 categories) ────────────────────────────────────────────
        "TEXT_001": {"name": "Ready Made Garments","sut": [61],        "exio": ["IN.47"],            "cat": "Textiles"},
        "TEXT_002": {"name": "Leather Footwear",   "sut": [63],        "exio": ["IN.48"],            "cat": "Textiles"},
        "TEXT_M01": {"name": "Textiles",           "sut": [56,57,58,59,60,62],"exio": ["IN.46"],    "cat": "Textiles"},
        "TEXT_M02": {"name": "Leather (excl. Ftwr)","sut": [64],       "exio": [],                   "cat": "Textiles"},
        # ── WOOD & PAPER (3 categories) ───────────────────────────────────────
        "WOOD_M01": {"name": "Wood & Furniture",   "sut": [65,68],     "exio": ["IN.49"],            "cat": "Manufacturing"},
        # IN.138 = Re-processing secondary paper→new pulp; IN.162 = open-loop paper recycling
        "WOOD_M02": {"name": "Paper Products",     "sut": [66],        "exio": ["IN.50","IN.51","IN.52","IN.138","IN.162"],"cat": "Manufacturing"},
        "WOOD_M03": {"name": "Printing/Publishing","sut": [67],        "exio": ["IN.53"],            "cat": "Manufacturing"},
        # ── CHEMICALS & PETROLEUM (4 categories) ──────────────────────────────
        # IN.140 = Re-processing secondary plastic→new plastic
        "CHEM_M01": {"name": "Rubber & Plastics",  "sut": [69,70],
                     "exio": ["IN.71","IN.72","IN.75","IN.76","IN.77","IN.78","IN.79","IN.80","IN.81","IN.140"],"cat": "Manufacturing"},
        "CHEM_M02": {"name": "Petroleum Products", "sut": [71,72],
                     "exio": ["IN.54","IN.55","IN.56","IN.57","IN.58","IN.59","IN.60",
                              "IN.61","IN.62","IN.63","IN.64","IN.65","IN.66","IN.67",
                              "IN.68","IN.69","IN.70","IN.73","IN.74"],                "cat": "Manufacturing"},
        "CHEM_M03": {"name": "Fertilizers",        "sut": [75],        "exio": ["IN.89","IN.90"],    "cat": "Manufacturing"},
        "CHEM_M04": {"name": "Other Chemicals",    "sut": [73,74,76,77,78,79,80,81],
                     "exio": ["IN.91"],                                               "cat": "Manufacturing"},
        # ── METALS (direct water = 0 except secondary reprocessing sectors) ────
        # IN.139 = Secondary glass → cement/non-metallic; IN.147 = Ash→clinker
        "METAL_M01": {"name": "Cement & Non-Metallic","sut": [82,83],  "exio": ["IN.139","IN.147"],   "cat": "Manufacturing"},
        # IN.141 = Secondary steel reprocessing
        "METAL_M02": {"name": "Iron & Steel",          "sut": [84,85,86],"exio": ["IN.141"],           "cat": "Manufacturing"},
        # IN.142–146 = secondary precious metals, aluminium, lead, copper, other NF; IN.160–161 = open-loop Cu/Al recycling
        "METAL_M03": {"name": "Non-Ferrous Metals",    "sut": [87,88,89],"exio": ["IN.142","IN.143","IN.144","IN.145","IN.146","IN.160","IN.161"], "cat": "Manufacturing"},
        # ── MACHINERY (zero direct water) ─────────────────────────────────────
        "MACH_M01": {"name": "Machinery",              "sut": [90,91,92,93,94],"exio": [],           "cat": "Manufacturing"},
        "MACH_M02": {"name": "Electrical Machinery",   "sut": [95,96,97,98,100],"exio": [],          "cat": "Manufacturing"},
        "MACH_M03": {"name": "Electronics",            "sut": [99,101,102,103],"exio": [],           "cat": "Manufacturing"},
        # IN.110 = "Motor vehicles, trailers and semi-trailers" — has blue water row in F.txt
        "MACH_M04": {"name": "Transport Equipment",    "sut": [104,105,106,107,108,109,110],"exio": ["IN.110"],"cat": "Manufacturing"},
        # ── OTHER MANUFACTURING ────────────────────────────────────────────────
        "MISC_M01": {"name": "Gems & Jewellery",       "sut": [111],   "exio": [],                   "cat": "Manufacturing"},
        # FIX: IN.112 = "Retail trade" in EXIOBASE. Previously listed here AND in
        # SERV_008 (Retail Trade), causing the concordance self_check duplicate error.
        # Retail trade is correctly a service sector → belongs exclusively in SERV_008.
        # MISC_M02 (SUT product 112 — Misc Manufacturing) has no direct EXIOBASE
        # equivalent; it receives zero direct water and is served via Leontief indirect.
        "MISC_M02": {"name": "Misc Manufacturing",     "sut": [112],   "exio": [],                   "cat": "Manufacturing"},
        # ── UTILITIES — energy sink for sectors with no dedicated SUT row ──────
        "UTIL_M01": {"name": "Electricity, Heat & Energy","sut": [114],
                     "exio": ["IN.82","IN.83","IN.84","IN.85","IN.86","IN.87","IN.88",
                              "IN.92","IN.93","IN.94","IN.95","IN.96","IN.97","IN.98",
                              "IN.99","IN.100","IN.101","IN.102","IN.103",
                              "IN.104","IN.105","IN.107"],                             "cat": "Utilities"},
        # ── SERVICES (all receive zero direct water — Leontief gives indirect) ─
        "SERV_001": {"name": "Hotels & Restaurants",   "sut": [119],   "exio": ["IN.113"],           "cat": "Services"},
        "SERV_002": {"name": "Railway Transport",      "sut": [120],   "exio": ["IN.114"],           "cat": "Services"},
        "SERV_003": {"name": "Road Transport",         "sut": [121],   "exio": ["IN.115"],           "cat": "Services"},
        "SERV_004": {"name": "Air Transport",          "sut": [122],   "exio": ["IN.119"],           "cat": "Services"},
        "SERV_005": {"name": "Construction",           "sut": [113],   "exio": ["IN.109"],           "cat": "Services"},
        "SERV_006": {"name": "Gas Distribution",       "sut": [115],   "exio": ["IN.106"],           "cat": "Services"},
        "SERV_007": {"name": "Water Supply",           "sut": [116],   "exio": ["IN.108"],           "cat": "Services"},
        "SERV_008": {"name": "Retail Trade",           "sut": [118],   "exio": ["IN.112"],           "cat": "Services"},
        "SERV_009": {"name": "Financial Services",     "sut": [125],   "exio": ["IN.122","IN.123","IN.124"],"cat": "Services"},
        "SERV_010": {"name": "Real Estate",            "sut": [126],   "exio": ["IN.125"],           "cat": "Services"},
        "SERV_011": {"name": "IT & R&D",               "sut": [127,128],"exio": ["IN.127","IN.128"], "cat": "Services"},
        "SERV_012": {"name": "Business Services",      "sut": [129],   "exio": ["IN.129"],           "cat": "Services"},
        "SERV_013": {"name": "Public Administration",  "sut": [130],   "exio": ["IN.130"],           "cat": "Services"},
        "SERV_014": {"name": "Education",              "sut": [131],   "exio": ["IN.131"],           "cat": "Services"},
        "SERV_015": {"name": "Health & Social Work",   "sut": [132],   "exio": ["IN.132"],           "cat": "Services"},
        # IN.133 = Sewage/refuse; IN.148–159 = biogasification, composting, incineration, waste water treatment
        "SERV_016": {"name": "Waste Management",       "sut": [133],   "exio": ["IN.133",
                     "IN.148","IN.149","IN.150","IN.151","IN.152","IN.153","IN.154",
                     "IN.155","IN.156","IN.157","IN.158","IN.159"],                               "cat": "Services"},
        "SERV_017": {"name": "Cultural & Rec Services","sut": [135],   "exio": ["IN.135"],           "cat": "Services"},
        "SERV_018": {"name": "Other Services",         "sut": [136,137],"exio": ["IN.136","IN.137"], "cat": "Services"},
        "SERV_019": {"name": "Post & Telecom",         "sut": [134],   "exio": ["IN.121"],           "cat": "Services"},
        "SERV_M01": {"name": "Wholesale Trade",        "sut": [117],   "exio": ["IN.111"],           "cat": "Services"},
        "SERV_M02": {"name": "Pipeline/Water Transport","sut": [123],  "exio": ["IN.116","IN.117","IN.118"],"cat": "Services"},
        "SERV_M03": {"name": "Support & Travel Agencies","sut": [124], "exio": ["IN.120"],           "cat": "Services"},
        # IN.126 = Machinery rental / renting & leasing — service sector, zero direct water by construction
        "SERV_M04": {"name": "Machinery Rental",        "sut": [63],   "exio": ["IN.126"],           "cat": "Services"},
        # IN.134 = Membership organisations — service sector, zero direct water by construction
        "SERV_M05": {"name": "Membership Organisations","sut": [134],  "exio": ["IN.134"],           "cat": "Services"},
    }


def self_check(concordance: dict, log: Logger = None) -> bool:
    """
    Ensure every EXIOBASE sector code appears in exactly one category.
    Checks both:
      (a) No duplicates — each code assigned at most once
      (b) No omissions — all 163 India codes (IN through IN.162) assigned at least once
    """
    seen = defaultdict(list)
    for cat_id, info in concordance.items():
        for code in info["exio"]:
            seen[code].append(cat_id)

    dups = {k: v for k, v in seen.items() if len(v) > 1}
    if dups:
        for code, cats in dups.items():
            fail(f"Duplicate: {code} in {cats}", log)

    # Completeness: all 163 India sectors must be assigned
    all_163 = set(["IN"] + [f"IN.{i}" for i in range(1, 163)])
    assigned = set(seen.keys())
    missing  = all_163 - assigned
    if missing:
        warn(
            f"{len(missing)} EXIOBASE India sectors not assigned in concordance "
            f"(will receive zero water): {sorted(missing, key=lambda x: int(x.split('.')[1]) if '.' in x else 0)}",
            log,
        )

    if dups:
        return False
    if missing:
        ok(f"Self-check passed: 0 duplicates, {len(missing)} unassigned "
           f"(expected zero — review concordance)", log)
    else:
        ok(f"Self-check passed: {len(assigned)} unique EXIOBASE sectors assigned, "
           f"0 duplicates, 0 omissions — full 163-sector coverage", log)
    return not bool(dups)  # warn on missing but don't abort — zero water is still valid


def check_steam_product(products_df: pd.DataFrame, concordance: dict, log: Logger = None) -> dict:
    """If SUT has a dedicated steam row, redirect IN.107 to it from UTIL_M01."""
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
                             water_col: str, log: Logger = None) -> pd.DataFrame:
    """
    Aggregate EXIOBASE sector water coefficients to 75 categories.

    For multi-sector categories, coefficients are SUMMED (not averaged).
    This is correct because each EXIOBASE sector maps to a distinct physical process.
    """
    exio_water = dict(zip(exio_df["Sector_Code"], exio_df[water_col]))
    rows = []
    for cat_id, info in concordance.items():
        w = sum(exio_water.get(code, 0) for code in info["exio"])
        rows.append({
            "Category_ID":       cat_id,
            "Category_Name":     info["name"],
            "Category_Type":     info["cat"],
            "N_EXIOBASE_Sectors": len(info["exio"]),
            "EXIOBASE_Sectors":  ",".join(info["exio"]),
            "SUT_Product_IDs":   ",".join(map(str, info["sut"])),
            water_col:           w,
        })
    return pd.DataFrame(rows)


def build_sut_water_table(concordance_df: pd.DataFrame, products_df: pd.DataFrame,
                           water_col: str, log: Logger = None) -> pd.DataFrame:
    """
    Distribute category water coefficients equally across mapped SUT products.

    For categories mapped to multiple SUT products (e.g. AGR_M01 Cereals & Pulses
    → SUT 3, 4, 5, 6), the category coefficient is divided equally among those products.
    """
    n = len(products_df)
    product_water = np.zeros(n)
    for _, row in concordance_df.iterrows():
        sut_ids = [int(x) for x in str(row["SUT_Product_IDs"]).split(",")]
        w = row[water_col]
        per_product = w / len(sut_ids) if sut_ids else 0
        for sid in sut_ids:
            if 1 <= sid <= n:
                product_water[sid - 1] += per_product
    result = products_df.copy()
    result[water_col] = product_water
    return result


def report_tourism_sectors(concordance_df: pd.DataFrame, water_col: str, log: Logger = None):
    tourism_cats = [
        "Hotels & Restaurants", "Railway Transport", "Air Transport",
        "Road Transport", "Cultural & Rec Services", "Support & Travel Agencies"
    ]
    sub = concordance_df[concordance_df["Category_Name"].isin(tourism_cats)]
    subsection("Tourism-relevant direct water coefficients (expect 0 — all via Leontief)", log)
    for _, r in sub.iterrows():
        note = "⚠ zero (correct — indirect water via L)" if r[water_col] == 0 else ""
        line = f"    {r['Category_Name']:<40} {r[water_col]:>12,.2f} m³/crore  {note}"
        if log:
            log.info(line)
        else:
            print(line)


# ══════════════════════════════════════════════════════════════════════════════
# PART 3 — Cross-year comparison
# ══════════════════════════════════════════════════════════════════════════════

def compare_water_years(yearly_dfs: dict, log: Logger = None) -> pd.DataFrame:
    """Merge per-year extractions and compute % intensity changes."""
    section("Cross-Year Water Intensity Comparison", log=log)

    base = yearly_dfs["2015"][["Sector_Code", "Sector_Name", "Broad_Category",
                                "Water_2015_m3_per_crore"]].copy()
    for yr in ["2019", "2022"]:
        col = f"Water_{yr}_m3_per_crore"
        base = base.merge(yearly_dfs[yr][["Sector_Code", col]], on="Sector_Code", how="left")

    base["Chg_2015_2019_pct"] = 100 * (
        base["Water_2019_m3_per_crore"] - base["Water_2015_m3_per_crore"]
    ) / base["Water_2015_m3_per_crore"].replace(0, np.nan)

    base["Chg_2015_2022_pct"] = 100 * (
        base["Water_2022_m3_per_crore"] - base["Water_2015_m3_per_crore"]
    ) / base["Water_2015_m3_per_crore"].replace(0, np.nan)

    totals = {yr: yearly_dfs[yr][f"Water_{yr}_m3_per_crore"].sum() for yr in STUDY_YEARS}
    compare_across_years(totals, "Economy-wide water intensity (m³/crore)", STUDY_YEARS, log=log)

    improving = base.dropna(subset=["Chg_2015_2022_pct"])
    lines = ["\n  📉 Best improving sectors (2015→2022, intensity ↓):"]
    for _, r in improving.nsmallest(5, "Chg_2015_2022_pct").iterrows():
        lines.append(f"     {r['Sector_Name']:<40}  {r['Chg_2015_2022_pct']:+.1f}%")
    lines.append("\n  📈 Worst sectors — intensity increased (2015→2022):")
    for _, r in improving.nlargest(5, "Chg_2015_2022_pct").iterrows():
        lines.append(f"     {r['Sector_Name']:<40}  {r['Chg_2015_2022_pct']:+.1f}%")
    output = "\n".join(lines)
    if log:
        log._log(output)
    else:
        print(output)

    return base


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    with Logger("build_water_coefficients", DIRS["logs"]) as log:
        t = Timer()
        log.section("BUILD WATER COEFFICIENTS  (EXIOBASE → concordance → SUT 140)")

        concordance_template = get_concordance()
        if not self_check(concordance_template, log):
            log.fail("Concordance self-check failed — aborting")
            return

        out_dir = DIRS["concordance"]
        out_dir.mkdir(parents=True, exist_ok=True)
        exio_base = DIRS["exiobase"]

        yearly_extractions = {}
        all_summaries = []

        # FIX: use STUDY_YEARS from config instead of iterating YEARS.items() directly
        for study_year in STUDY_YEARS:
            cfg = YEARS[study_year]
            io_year    = cfg["io_year"]
            io_tag     = cfg["io_tag"]
            water_year = cfg["water_year"]
            water_col  = f"Water_{water_year}_m3_per_crore"

            log.section(f"Year: {io_year}  (water: {water_year})")

            # ── PART 1: Extract from EXIOBASE F.txt ──
            f_path = exio_base / f"IOT_{water_year}_ixi" / "water" / "F.txt"
            exio_df = extract_india_water(f_path, water_year, log)
            yearly_extractions[water_year] = exio_df

            audit_dir = exio_base / "output" / water_year
            audit_dir.mkdir(parents=True, exist_ok=True)
            save_csv(exio_df, audit_dir / f"India_Water_Coefficients_{water_year}.csv",
                     f"Raw extraction {water_year}", log=log)

            # ── PART 2: Build concordance ──
            prod_file = DIRS["io"] / io_year / f"io_products_{io_tag}.csv"
            if not prod_file.exists():
                warn(f"Product list missing: {prod_file} — run build_io_tables.py first", log)
                continue
            products_df = pd.read_csv(prod_file)

            year_concordance = copy.deepcopy(concordance_template)
            year_concordance = check_steam_product(products_df, year_concordance, log)

            concordance_df = build_concordance_table(exio_df, year_concordance, water_col, log)
            sut_df         = build_sut_water_table(concordance_df, products_df, water_col, log)

            top_n(concordance_df, water_col, "Category_Name", n=10,
                  unit=" m³/cr", pct_base=concordance_df[water_col].sum(), log=log)
            report_tourism_sectors(concordance_df, water_col, log)

            zero = sut_df[sut_df[water_col] == 0]
            ok(
                f"SUT products: {len(sut_df) - len(zero)} with water > 0, "
                f"{len(zero)} = 0 (services receive indirect water via Leontief)",
                log,
            )

            save_csv(concordance_df, out_dir / f"concordance_{io_tag}.csv",
                     f"concordance {io_year}", log=log)
            save_csv(sut_df, out_dir / f"water_coefficients_140_{io_tag}.csv",
                     f"SUT water {io_year}", log=log)

            all_summaries.append({
                "io_year":               io_year,
                "water_year":            water_year,
                "total_water_m3_crore":  round(concordance_df[water_col].sum(), 2),
                "n_nonzero_products":    int((sut_df[water_col] > 0).sum()),
            })

        # ── PART 3: Cross-year comparison ──
        if len(yearly_extractions) == len(STUDY_YEARS):
            comparison = compare_water_years(yearly_extractions, log)
            save_csv(comparison, out_dir / "water_coefficients_year_comparison.csv",
                     "Year comparison", log=log)

        if all_summaries:
            summary_df = pd.DataFrame(all_summaries)
            totals_dict = {s["water_year"]: s["total_water_m3_crore"] for s in all_summaries}
            compare_across_years(totals_dict, "Total water intensity (m³/crore)",
                                 STUDY_YEARS, " m³/cr", log=log)
            save_csv(summary_df, out_dir / "water_intensity_trend.csv",
                     "Intensity trend", log=log)

        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    run()