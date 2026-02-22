"""
Build tourism demand vectors: TSA 2015-16 → NAS-scaled 2019 & 2022 → EXIOBASE Y vectors.

This script merges the former scale_tsa_demand.py and build_demand_vectors.py, eliminating
an intermediate file-read step. The full pipeline is:

  TSA 2015-16 base (₹ crore)
    × NAS real growth rates (Statement 6.1, constant 2011-12 prices)
    × CPI deflator (real → nominal crore)
  → Scaled TSA for 2019 and 2022
  → Split into EXIOBASE 163-sector demand vectors (Y_tourism, ₹ crore)
  → Optionally deflated to 2015-16 constant prices for real intensity comparisons

Why scale TSA with NAS?
-----------------------
India's Tourism Satellite Account (TSA) was last published for 2015-16. No TSA exists
for 2019-20 or 2021-22. The standard approach (Temurshoev & Timmer 2011, OECD practice)
is to extrapolate base-year sectoral demand using national accounts growth rates at the
most granular available sector level (NAS Statement 6.1: GVA by economic activity).

The method uses NOMINAL scaling: real growth × CPI inflation = nominal crore factor.
This preserves consistency with SUT data (which is in nominal crore).

NAS growth rates are loaded from reference_data.md via config.NAS_GROWTH_RATES.
This eliminates all runtime string matching and CSV parsing, making the pipeline
deterministic and audit-friendly. To update values, edit reference_data.md.

EXIOBASE demand vector construction
------------------------------------
The 163-sector Y_tourism vector maps each TSA category to one or more EXIOBASE India
sectors. The mapping uses fixed assumed shares where a TSA category spans multiple
EXIOBASE sectors (e.g. "Travel related consumer goods" split across Other Mfg,
Leather, Chemicals, Printing, Paper, Electronics).

EXIOBASE India sectors: IN (Paddy rice = sector 0) through IN.162 (Private households
= sector 162), totalling 163 sectors. Codes IN.138–IN.162 correspond to additional
service/household sectors not individually mapped in TSA_TO_EXIOBASE — they receive
zero tourism demand but are included to keep the Y vector the correct length.

NEW: Inbound and domestic split vectors
----------------------------------------
In addition to the combined Y vector, this script now produces separate inbound-only
and domestic-only Y vectors for each year. These allow calculate_indirect_twf.py to
run W×L×Y separately for each tourist type, revealing:
  - Whether inbound or domestic tourists have higher per-day water footprint
  - Which supply chain sectors are disproportionately driven by inbound spend
  - Whether cross-year intensity changes are driven by domestic or inbound shifts
This directly replicates the Lee et al. (2021) inbound/domestic comparison for China,
where inbound per-day TWF was ~3× domestic.

Price deflation for real intensity comparison
---------------------------------------------
When comparing water intensity (m³/₹ crore) across 2015, 2019, 2022, the denominator
(tourism demand in ₹ crore) should be in constant prices. Without deflation, part of
the apparent intensity change is just price inflation, not a real change in economic
activity. This script outputs BOTH nominal and real (2015-16 constant price) demand.

Outputs
-------
  tsa_scaled_{year}.csv            — TSA in nominal crore by year
  tsa_all_years.csv                — all years combined
  Y_tourism_{year}.csv             — 163-sector EXIOBASE combined demand vector (nominal crore)
  Y_tourism_{year}_real.csv        — 163-sector combined demand vector (2015-16 constant prices)
  Y_tourism_{year}_inbound.csv     — 163-sector inbound-only demand vector (NEW)
  Y_tourism_{year}_domestic.csv    — 163-sector domestic-only demand vector (NEW)
  demand_intensity_comparison.csv  — per-crore demand comparison across years
"""

import time
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from config import BASE_DIR, DIRS, CPI, TSA_BASE, STUDY_YEARS, NAS_GROWTH_RATES, NAS_GVA_CONSTANT
from utils import (
    section, subsection, ok, warn, save_csv,
    compare_across_years, Timer, Logger,
)


# ══════════════════════════════════════════════════════════════════════════════
# PART 0 — NAS growth rate accessor
# ══════════════════════════════════════════════════════════════════════════════

def load_nas_growth_rates(log: Logger = None) -> dict:
    """
    Return NAS real GVA growth multipliers from config.NAS_GROWTH_RATES.

    Previously this function parsed a NAS CSV file at runtime using fragile
    string matching. Growth rates are now pre-computed in config.py from the
    values in reference_data.md (NAS Statement 6.1, constant 2011-12 prices,
    NAS 2024 edition). To update the values, edit reference_data.md.

    The returned dict has the same structure as before so all callers are unchanged:
      {sector_key: {"2019": float, "2022": float}}

    Growth rates are real (constant-price) multipliers vs 2015-16 base.
    They are combined with CPI deflation in scale_tsa() to produce nominal factors.
    """
    section("NAS Growth Rates (Constant Prices, Statement 6.1)", log=log)
    ok("Loading from config.NAS_GROWTH_RATES (pre-computed from reference_data.md)", log)

    lines = [
        f"\n  {'Sector':<18} {'NAS S.No.':>10} {'×2019':>10} {'×2022':>10}",
        "  " + "─" * 52,
    ]

    for key, rates in NAS_GROWTH_RATES.items():
        sno = NAS_GVA_CONSTANT[key]["nas_sno"]
        lines.append(
            f"  {key:<18} {sno:>10} {rates['2019']:>10.4f} {rates['2022']:>10.4f}"
        )

    output = "\n".join(lines)
    if log:
        log._log(output)
    else:
        print(output)

    return NAS_GROWTH_RATES


# ══════════════════════════════════════════════════════════════════════════════
# PART 1 — TSA scaling
# ══════════════════════════════════════════════════════════════════════════════

# FIX (restaurants): mapped to "Trade" (NAS 6.1) not "Hotels" (NAS 6.2).
# NAS 6.2 tracks hotel occupancy; restaurants during COVID pivoted to delivery,
# tracking more closely with trade/retail dynamics. Using Trade gives a more
# appropriate growth trajectory and avoids conflating accommodation contraction
# (2021-22 NAS 6.2 fell below 2015-16 baseline) with food service activity.
TSA_TO_NAS = {
    "Accommodation services/hotels":                  "Hotels",
    "Food and beverage serving services/restaurants": "Trade",
    "Railway passenger transport services":           "Railway",
    "Road passenger transport services":              "Road",
    "Water passenger transport services":             "Water_Trans",
    "Air passenger transport services":               "Air",
    "Transport equipment rental services":            "Transport_Svcs",
    "Travel agencies and other reservation services": "Transport_Svcs",
    "Cultural and religious services":                "Real_Estate",
    "Sports and other recreational services":         "Real_Estate",
    "Health and medical related services":            "Real_Estate",
    "Readymade garments":                             "Textiles",
    "Processed Food":                                 "Food_Mfg",
    "Alcohol and tobacco products":                   "Food_Mfg",
    "Travel related consumer goods":                  "Other_Mfg",
    "Footwear":                                       "Textiles",
    "Soaps, cosmetics and glycerine":                 "Other_Mfg",
    "Gems and jewellery":                             "Other_Mfg",
    "Books, journals, magazines, stationery":         "Other_Mfg",
    "Vacation homes":                                 "Real_Estate",
    "Social transfers in kind":                       "Real_Estate",
    "FISIM":                                          "Finance",
    "Producers guest houses":                         "Real_Estate",
    "Imputed expenditures on food":                   "Food_Mfg",
}


def scale_tsa(growth: dict, log: Logger = None) -> pd.DataFrame:
    section("Scaling TSA 2015-16 → 2019, 2022", log=log)

    cols = ["ID", "Category", "Category_Type", "Inbound_2015", "Domestic_2015"]
    base = pd.DataFrame(TSA_BASE, columns=cols)
    base["Total_2015"] = base["Inbound_2015"] + base["Domestic_2015"]

    cpi_2019 = CPI["2019-20"] / CPI["2015-16"]
    cpi_2022 = CPI["2021-22"] / CPI["2015-16"]
    ok(f"CPI multipliers: 2019={cpi_2019:.4f}  2022={cpi_2022:.4f}", log)

    rows = []
    header = (
        f"\n  {'Category':<55} {'NAS':>12} "
        f"{'real×2019':>10} {'nom×2019':>10} "
        f"{'real×2022':>10} {'nom×2022':>10}\n"
        f"  {'─'*112}"
    )
    if log:
        log.info(header)
    else:
        print(header)

    for _, r in base.iterrows():
        nas_key  = TSA_TO_NAS.get(r["Category"], "Other_Mfg")
        real_g19 = growth[nas_key]["2019"]
        real_g22 = growth[nas_key]["2022"]
        nom_g19  = real_g19 * cpi_2019   # real × CPI = nominal scaling factor
        nom_g22  = real_g22 * cpi_2022

        line = (
            f"  {r['Category'][:54]:<55} {nas_key:>12} "
            f"{real_g19:>10.4f} {nom_g19:>10.4f} "
            f"{real_g22:>10.4f} {nom_g22:>10.4f}"
        )
        if log:
            log.info(line)
        else:
            print(line)

        rows.append({
            **r.to_dict(),
            "NAS_Sector":    nas_key,
            "Real_G19":      real_g19,
            "Nominal_G19":   nom_g19,
            "Real_G22":      real_g22,
            "Nominal_G22":   nom_g22,
            "Inbound_2019":  r["Inbound_2015"]  * nom_g19,
            "Domestic_2019": r["Domestic_2015"] * nom_g19,
            "Total_2019":    r["Total_2015"]    * nom_g19,
            "Inbound_2022":  r["Inbound_2015"]  * nom_g22,
            "Domestic_2022": r["Domestic_2015"] * nom_g22,
            "Total_2022":    r["Total_2015"]    * nom_g22,
        })

    df = pd.DataFrame(rows)

    totals = {
        "2015": df["Total_2015"].sum(),
        "2019": df["Total_2019"].sum(),
        "2022": df["Total_2022"].sum(),
    }
    compare_across_years(totals, "Total tourism spending (₹ crore nominal)", unit=" cr", log=log)

    t15, t19, t22 = totals["2015"], totals["2019"], totals["2022"]
    cagr_15_19 = 100 * ((t19 / t15) ** 0.25 - 1)
    cagr_19_22 = 100 * ((t22 / t19) ** (1 / 3) - 1)
    ok(f"CAGR 2015→2019: {cagr_15_19:.1f}%/yr  |  CAGR 2019→2022: {cagr_19_22:.1f}%/yr", log)
    if abs(cagr_19_22) > 25:
        warn("CAGR 2019→2022 >25% — COVID impact visible; review", log)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# PART 2 — EXIOBASE demand vector construction
# ══════════════════════════════════════════════════════════════════════════════

# Mapping: TSA category → list of (EXIOBASE_sector_code, share)
# Shares sum to 1.0 per category. Where multiple EXIOBASE sectors map to one TSA
# category, shares reflect approximate production proportions (documented below).
#
# FIX: Duplicate IN.91 entries in "Travel related consumer goods" corrected.
# The original had IN.91 at shares 0.45 and 0.15 (copy-paste error).
# The 0.15 entry is corrected to IN.46 (Textiles — luggage/bags/accessories).
TSA_TO_EXIOBASE = {
    "Accommodation services/hotels":                  [("IN.113", 1.0)],
    "Food and beverage serving services/restaurants": [("IN.113", 0.5), ("IN.42", 0.3), ("IN.43", 0.2)],
    "Railway passenger transport services":           [("IN.114", 1.0)],
    "Road passenger transport services":              [("IN.115", 1.0)],
    "Water passenger transport services":             [("IN.117", 0.7), ("IN.118", 0.3)],
    "Air passenger transport services":               [("IN.119", 1.0)],
    "Transport equipment rental services":            [("IN.126", 1.0)],
    "Travel agencies and other reservation services": [("IN.120", 1.0)],
    "Cultural and religious services":                [("IN.135", 1.0)],
    "Sports and other recreational services":         [("IN.135", 1.0)],
    "Health and medical related services":            [("IN.132", 1.0)],
    "Readymade garments":                             [("IN.47",  1.0)],
    "Processed Food":                                 [("IN.42",  0.7), ("IN.40", 0.3)],
    "Alcohol and tobacco products":                   [("IN.43",  0.6), ("IN.45", 0.4)],
    # Travel goods: split across EXIOBASE sectors.
    # IN.91 = Chemicals nec (toiletries/cosmetics in travel kits): 0.45
    # IN.48 = Leather products (luggage, bags): 0.20
    # IN.46 = Textiles (soft goods, scarves, accessories): 0.15
    # IN.53 = Printed matter (guides, maps): 0.10
    # IN.52 = Paper products: 0.05
    # IN.103 = Electricity nec (electronics, adapters): 0.05
    "Travel related consumer goods": [
        ("IN.91", 0.45), ("IN.48", 0.20), ("IN.46", 0.15),
        ("IN.53", 0.10), ("IN.52", 0.05), ("IN.103", 0.05),
    ],
    "Footwear":                                       [("IN.48",  1.0)],
    "Soaps, cosmetics and glycerine":                 [("IN.91",  1.0)],
    "Gems and jewellery":                             [("IN.91",  1.0)],
    "Books, journals, magazines, stationery":         [("IN.53",  0.6), ("IN.52", 0.4)],
    "Vacation homes":                                 [("IN.125", 1.0)],
    "Social transfers in kind":                       [("IN.130", 1.0)],
    "FISIM":                                          [("IN.122", 1.0)],
    "Producers guest houses":                         [("IN.125", 0.5), ("IN.136", 0.5)],
    "Imputed expenditures on food":                   [("IN.42",  1.0)],
}

# EXIOBASE India sector codes: IN (sector 0) through IN.162 (sector 162) = 163 total.
# FIX: was range(1, 138) producing only 138 codes, causing a length mismatch with
# Y = np.zeros(163). Corrected to range(1, 163) for 163 codes total.
# Sectors IN.138–IN.162 are not individually mapped in TSA_TO_EXIOBASE but must
# be present to keep the Y vector the correct shape for W @ L @ Y in EEIO.
_EXIO_CODES = ["IN"] + [f"IN.{i}" for i in range(1, 163)]   # 163 elements
EXIO_IDX    = {code: i for i, code in enumerate(_EXIO_CODES)}


def build_y_vector(tsa_df: pd.DataFrame, year: str,
                   demand_col: str = None, log: Logger = None) -> np.ndarray:
    """
    Build 163-sector EXIOBASE demand vector from scaled TSA.

    Algorithm:
      For each TSA category, take the demand from demand_col (₹ crore nominal).
      Distribute across EXIOBASE sectors according to TSA_TO_EXIOBASE shares.
      Shares for duplicate sector codes within one category are summed.

    Parameters
    ----------
    demand_col : column to use for demand values.
                 Defaults to Total_{year} (combined inbound + domestic).
                 Pass "Inbound_{year}" or "Domestic_{year}" for split vectors.

    Returns np.ndarray of shape (163,) in ₹ crore nominal.
    """
    if demand_col is None:
        demand_col = f"Total_{year}"

    Y = np.zeros(163)

    for _, row in tsa_df.iterrows():
        cat    = row["Category"]
        demand = row[demand_col]
        if demand == 0:
            continue
        mappings = TSA_TO_EXIOBASE.get(cat, [("IN.136", 1.0)])  # fallback: Other Services

        # Normalise shares in case of duplicate codes or rounding != 1.0
        share_by_code: dict = {}
        for code, share in mappings:
            share_by_code[code] = share_by_code.get(code, 0) + share
        total_share = sum(share_by_code.values())

        for code, share in share_by_code.items():
            idx = EXIO_IDX.get(code)
            if idx is not None:
                Y[idx] += demand * (share / total_share)
            else:
                warn(f"EXIOBASE code '{code}' not in EXIO_IDX — check TSA_TO_EXIOBASE", log)

    label = demand_col
    ok(
        f"Y_tourism {year} [{label}]: ₹{Y.sum():,.0f} crore  "
        f"non-zero sectors: {np.count_nonzero(Y)}/163",
        log,
    )
    return Y


def build_y_real(Y_nominal: np.ndarray, year: str) -> np.ndarray:
    """
    Deflate nominal demand vector to 2015-16 constant prices.

    Deflator = CPI[year] / CPI["2015-16"]
    Dividing by deflator converts nominal → real (2015-16 base).
    """
    year_map = {"2015": "2015-16", "2019": "2019-20", "2022": "2021-22"}
    fy = year_map.get(year, year)
    deflator = CPI.get(fy, 1.0) / CPI["2015-16"]
    return Y_nominal / deflator


def _make_y_df(Y: np.ndarray) -> pd.DataFrame:
    """Package a Y vector into a standard DataFrame for saving."""
    return pd.DataFrame({
        "Sector_Index":         range(len(_EXIO_CODES)),
        "Sector_Code":          _EXIO_CODES,
        "Tourism_Demand_crore": Y,
    })


# ══════════════════════════════════════════════════════════════════════════════
# PART 3 — Main
# ══════════════════════════════════════════════════════════════════════════════

def run(**kwargs):
    with Logger("build_tourism_demand", DIRS["logs"]) as log:
        t = Timer()
        log.section("BUILD TOURISM DEMAND VECTORS (TSA → NAS scale → EXIOBASE Y)")

        growth  = load_nas_growth_rates(log)
        tsa_df  = scale_tsa(growth, log)

        tsa_out = DIRS["tsa"]
        tsa_out.mkdir(parents=True, exist_ok=True)
        save_csv(tsa_df, tsa_out / "tsa_all_years.csv", "TSA all years", log=log)

        demand_out = DIRS["demand"]
        demand_out.mkdir(parents=True, exist_ok=True)

        intensity_comparison = []

        for year in STUDY_YEARS:
            total_col  = f"Total_{year}"
            inb_col    = f"Inbound_{year}"
            dom_col    = f"Domestic_{year}"

            year_cols  = [
                "ID", "Category", "Category_Type",
                inb_col, dom_col, total_col,
                "NAS_Sector",
                f"Real_G{year[2:]}", f"Nominal_G{year[2:]}",
            ]
            # Only keep columns that actually exist (future-proofs new years)
            year_cols = [c for c in year_cols if c in tsa_df.columns]
            save_csv(
                tsa_df[year_cols],
                tsa_out / f"tsa_scaled_{year}.csv",
                f"TSA {year}",
                log=log,
            )

            # ── Combined (inbound + domestic) ────────────────────────────────
            Y      = build_y_vector(tsa_df, year, demand_col=total_col, log=log)
            Y_real = build_y_real(Y, year)

            save_csv(_make_y_df(Y),      demand_out / f"Y_tourism_{year}.csv",
                     f"Y_tourism {year}",      log=log)
            save_csv(_make_y_df(Y_real), demand_out / f"Y_tourism_{year}_real.csv",
                     f"Y_tourism {year} real", log=log)

            # ── NEW: Inbound-only vector ─────────────────────────────────────
            if inb_col in tsa_df.columns:
                Y_inb = build_y_vector(tsa_df, year, demand_col=inb_col, log=log)
                save_csv(_make_y_df(Y_inb), demand_out / f"Y_tourism_{year}_inbound.csv",
                         f"Y_tourism {year} inbound", log=log)
            else:
                warn(f"Column {inb_col} not found — inbound split not saved for {year}", log)

            # ── NEW: Domestic-only vector ────────────────────────────────────
            if dom_col in tsa_df.columns:
                Y_dom = build_y_vector(tsa_df, year, demand_col=dom_col, log=log)
                save_csv(_make_y_df(Y_dom), demand_out / f"Y_tourism_{year}_domestic.csv",
                         f"Y_tourism {year} domestic", log=log)
            else:
                warn(f"Column {dom_col} not found — domestic split not saved for {year}", log)

            log.ok(
                f"{year}: nominal total ₹{Y.sum():,.0f} cr  |  "
                f"real total ₹{Y_real.sum():,.0f} cr  |  "
                f"non-zero sectors: {np.count_nonzero(Y)}/163"
            )
            intensity_comparison.append({
                "Year":          year,
                "Nominal_crore": Y.sum(),
                "Real_crore":    Y_real.sum(),
            })

        # Cross-year comparison
        log.section("Tourism Demand Cross-Year Comparison")
        nominal_dict = {r["Year"]: r["Nominal_crore"] for r in intensity_comparison}
        real_dict    = {r["Year"]: r["Real_crore"]    for r in intensity_comparison}
        df1 = compare_across_years(nominal_dict, "Tourism demand (₹ crore nominal)",      unit=" cr", log=log)
        df2 = compare_across_years(real_dict,    "Tourism demand (₹ crore real 2015-16)", unit=" cr", log=log)
        combined = pd.concat([df1, df2], ignore_index=True)
        save_csv(combined, demand_out / "demand_intensity_comparison.csv", "Demand comparison", log=log)

        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    run()