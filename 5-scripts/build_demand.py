"""
build_demand.py — Build Tourism Demand Vectors
=======================================================

Pipeline:
  TSA 2015-16 base (₹ crore)
    × NAS real growth rates (Statement 6.1, constant 2011-12 prices)
    × CPI deflator (real → nominal crore)
  → Scaled TSA for each study year
  → 163-sector EXIOBASE demand vectors (Y_tourism, ₹ crore)
  → Deflated to 2015-16 constant prices for real intensity comparisons

WHY NAS SCALING?
India's TSA was last published for 2015-16. The standard approach
(Temurshoev & Timmer 2011; OECD practice) extrapolates base-year sectoral
demand using NAS Statement 6.1 GVA growth rates.

OUTPUTS
───────
  tsa/tsa_scaled_{year}.csv              TSA in nominal crore by year
  tsa/tsa_all_years.csv                  all years combined
  demand/Y_tourism_{year}.csv            163-sector combined demand (nominal)
  demand/Y_tourism_{year}_real.csv       163-sector demand (2015-16 prices)
  demand/Y_tourism_{year}_inbound.csv    inbound-only demand vector
  demand/Y_tourism_{year}_domestic.csv   domestic-only demand vector
  demand/demand_intensity_comparison.csv cross-year demand comparison
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    DIRS, CPI, STUDY_YEARS, NAS_GROWTH_RATES, NAS_GVA_CONSTANT,
    TSA_BASE, TSA_TO_NAS, TSA_TO_EXIOBASE, EXIO_IDX, EXIO_CODES, USD_INR, YEARS,
)
from utils import (
    section, subsection, ok, warn, save_csv, compare_across_years,
    Timer, Logger, fmt_crore_usd, crore_to_usd_m, table_str,
)

# ── Year helpers ──────────────────────────────────────────────────────────────

_YEAR_TO_IO: dict = {yr: info["io_year"] for yr, info in YEARS.items()}
_BASE_YEAR: str   = STUDY_YEARS[0]

def _cpi_mult(year: str) -> float:
    """CPI multiplier vs 2015-16 base."""
    return CPI[_YEAR_TO_IO[year]] / CPI["2015-16"]

def _deflator(year: str) -> float:
    """Price deflator relative to 2015-16."""
    return CPI.get(_YEAR_TO_IO.get(year, "2015-16"), CPI["2015-16"]) / CPI["2015-16"]


# ══════════════════════════════════════════════════════════════════════════════
# TSA SCALING
# ══════════════════════════════════════════════════════════════════════════════

def scale_tsa(log: Logger = None) -> pd.DataFrame:
    """
    Scale TSA 2015-16 base to each study year using NAS growth rates + CPI.

    Nominal scaling factor:
        nom_factor = real_GVA_growth(sector, year) × CPI(year) / CPI(2015-16)

    Returns DataFrame with one row per TSA category, columns for each year.
    """
    section("NAS Growth Rates & TSA Scaling", log=log)
    cpi_mults = {yr: _cpi_mult(yr) for yr in STUDY_YEARS}

    # Growth rate table
    subsection("NAS GVA growth multipliers (constant 2011-12 prices)", log=log)
    ok("CPI multipliers vs 2015-16: " +
       "  ".join(f"{yr}={cpi_mults[yr]:.4f}" for yr in STUDY_YEARS), log)

    growth_rows = [
        [key, NAS_GVA_CONSTANT[key]["nas_sno"]] + [f"{rates.get(yr, 1.0):.4f}" for yr in STUDY_YEARS]
        for key, rates in NAS_GROWTH_RATES.items()
    ]
    hdrs = ["Sector key", "NAS S.No."] + [f"×{yr}" for yr in STUDY_YEARS]
    if log:
        log.table(hdrs, growth_rows)
    else:
        print(table_str(hdrs, growth_rows))

    # Build scaled TSA DataFrame
    base = pd.DataFrame(TSA_BASE, columns=["ID", "Category", "Category_Type",
                                            "Inbound_2015", "Domestic_2015"])
    base["Total_2015"] = base["Inbound_2015"] + base["Domestic_2015"]

    rows = []
    for _, r in base.iterrows():
        nas_key = TSA_TO_NAS.get(r["Category"], "Other_Mfg")
        row = {**r.to_dict(), "NAS_Sector": nas_key}
        for yr in STUDY_YEARS:
            real_g = NAS_GROWTH_RATES[nas_key].get(yr, 1.0)
            nom_g  = real_g * cpi_mults[yr]
            row[f"Real_G{yr[2:]}"]    = real_g
            row[f"Nominal_G{yr[2:]}"] = nom_g
            for seg in ("Inbound", "Domestic", "Total"):
                row[f"{seg}_{yr}"] = r[f"{seg}_2015"] * nom_g
        rows.append(row)

    df = pd.DataFrame(rows)

    # Summary + CAGR check
    totals = {yr: df[f"Total_{yr}"].sum() for yr in STUDY_YEARS}
    compare_across_years(totals, "Total tourism spending (₹ crore nominal)", unit=" cr", log=log)

    usd_lines = ["  Total tourism spending (USD million equivalent):"]
    for yr in STUDY_YEARS:
        rate  = USD_INR.get(yr, 70.0)
        usd_m = crore_to_usd_m(totals[yr], rate)
        usd_lines.append(f"    {yr}: ${usd_m:,.0f}M  (@ ₹{rate:.2f}/USD)")
    msg = "\n".join(usd_lines)
    if log:
        log._emit(msg)
    else:
        print(msg)

    for i in range(1, len(STUDY_YEARS)):
        prev, curr = STUDY_YEARS[i - 1], STUDY_YEARS[i]
        n_yrs = int(curr) - int(prev)
        cagr  = 100 * ((totals[curr] / totals[prev]) ** (1 / n_yrs) - 1)
        ok(f"CAGR {prev}→{curr}: {cagr:.1f}%/yr", log)
        if abs(cagr) > 25:
            warn(f"CAGR {prev}→{curr} >25% — COVID impact likely; review NAS scaling", log)

    return df


# ══════════════════════════════════════════════════════════════════════════════
# DEMAND VECTOR BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def build_demand_vectors(tsa_df: pd.DataFrame, year: str,
                          demand_col: str = None,
                          log: Logger = None) -> tuple:
    """
    Build nominal and real 163-sector EXIOBASE demand vectors.

    Parameters
    ----------
    demand_col : column to use (default: Total_{year}).
                 Pass "Inbound_{year}" or "Domestic_{year}" for split vectors.

    Returns (Y_nominal, Y_real) — both shape (163,) in ₹ crore
    """
    if demand_col is None:
        demand_col = f"Total_{year}"

    Y = np.zeros(163)
    for _, row in tsa_df.iterrows():
        demand = row[demand_col]
        if demand == 0:
            continue
        mappings = TSA_TO_EXIOBASE.get(row["Category"], [("IN.136", 1.0)])

        # Normalise shares (handles rounding / duplicates)
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

    deflator = _deflator(year)
    Y_real   = Y / deflator

    ok(f"Y_tourism {year} [{demand_col}]: ₹{Y.sum():,.0f} cr  "
       f"non-zero: {np.count_nonzero(Y)}/163  deflator: {deflator:.4f}  "
       f"real: ₹{Y_real.sum():,.0f} cr", log)
    return Y, Y_real


def _make_y_df(Y: np.ndarray) -> pd.DataFrame:
    """Convert 163-element array to labelled DataFrame."""
    return pd.DataFrame({
        "Sector_Index":         range(len(EXIO_CODES)),
        "Sector_Code":          EXIO_CODES,
        "Tourism_Demand_crore": Y,
    })


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def run(**kwargs):
    log_dir = DIRS["logs"] / "tourism_demand"
    with Logger("build_tourism_demand", log_dir) as log:
        t = Timer()
        log.section("BUILD TOURISM DEMAND VECTORS (TSA → NAS-scaled → EXIOBASE Y)")

        tsa_df = scale_tsa(log)
        tsa_out = DIRS["tsa"]
        tsa_out.mkdir(parents=True, exist_ok=True)
        save_csv(tsa_df, tsa_out / "tsa_all_years.csv", "TSA all years", log=log)

        demand_out = DIRS["demand"]
        demand_out.mkdir(parents=True, exist_ok=True)

        intensity_rows = []
        for year in STUDY_YEARS:
            log.subsection(f"Building demand vectors — {year}")
            total_col = f"Total_{year}"
            inb_col   = f"Inbound_{year}"
            dom_col   = f"Domestic_{year}"

            # Per-year TSA slice
            year_cols = [c for c in ["ID", "Category", "Category_Type",
                          inb_col, dom_col, total_col, "NAS_Sector",
                          f"Real_G{year[2:]}", f"Nominal_G{year[2:]}"]
                         if c in tsa_df.columns]
            save_csv(tsa_df[year_cols], tsa_out / f"tsa_scaled_{year}.csv",
                     f"TSA {year}", log=log)

            # Combined demand vector (nominal + real)
            Y, Y_real = build_demand_vectors(tsa_df, year, demand_col=total_col, log=log)
            save_csv(_make_y_df(Y),      demand_out / f"Y_tourism_{year}.csv",      f"Y_tourism {year}",      log=log)
            save_csv(_make_y_df(Y_real), demand_out / f"Y_tourism_{year}_real.csv", f"Y_tourism {year} real", log=log)

            # Inbound / domestic split
            for col, suffix in [(inb_col, "inbound"), (dom_col, "domestic")]:
                if col in tsa_df.columns:
                    Y_split, _ = build_demand_vectors(tsa_df, year, demand_col=col, log=log)
                    save_csv(_make_y_df(Y_split),
                             demand_out / f"Y_tourism_{year}_{suffix}.csv",
                             f"Y_tourism {year} {suffix}", log=log)
                else:
                    warn(f"Column {col} not found — {suffix} split skipped for {year}", log)

            usd_rate = USD_INR.get(year, 70.0)
            intensity_rows.append({
                "Year":            year,
                "Nominal_crore":   Y.sum(),
                "Real_crore":      Y_real.sum(),
                "Nominal_USD_M":   round(crore_to_usd_m(Y.sum(), usd_rate), 1),
                "Real_USD_M":      round(crore_to_usd_m(Y_real.sum(), USD_INR.get(_BASE_YEAR, 65.0)), 1),
                "USD_INR_Rate":    usd_rate,
                "NonZero_Sectors": int(np.count_nonzero(Y)),
            })

        # Cross-year demand comparison
        log.section("Tourism Demand Cross-Year Comparison")
        comparisons = [
            ("Tourism demand (₹ crore nominal)",         "Nominal_crore"),
            ("Tourism demand (₹ crore real 2015-16)",    "Real_crore"),
            ("Tourism demand (USD million nominal)",      "Nominal_USD_M"),
            ("Tourism demand (USD million real 2015-16)", "Real_USD_M"),
        ]
        df_list = [
            compare_across_years({r["Year"]: r[key] for r in intensity_rows}, label, log=log)
            for label, key in comparisons
        ]
        save_csv(pd.concat(df_list, ignore_index=True),
                 demand_out / "demand_intensity_comparison.csv",
                 "Demand comparison", log=log)

        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    run()
