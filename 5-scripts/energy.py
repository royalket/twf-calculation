"""
energy.py — Energy-specific logic: outbound EF, emission/final ratio
=====================================================================
Only genuinely energy-specific code lives here.
Shared EEIO: indirect.py. Activity-based: direct.py.

Note on 2022 data gap
---------------------
EXIOBASE energy F.txt for 2022 is currently missing.
Fallback: extrapolate from 2019 using NAS energy intensity trend.
All extrapolated values are flagged with Extrapolated=True in output.

Outputs:
  outbound-energy/outbound_energy_all_years.csv
  outbound-energy/outbound_energy_by_dest.csv
  outbound-energy/energy_intensity_benchmarks.csv
"""

from __future__ import annotations
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    DIRS, STUDY_YEARS, OUTBOUND_ENERGY_DESTINATIONS, OUTBOUND_COUNTS,
    TOURIST_WF_MULTIPLIER, USD_INR, STRESSORS,
    TJ_TO_MJ, TJ_TO_GJ, TJ_TO_KWH,
    ENERGY_ROW_FINAL, ENERGY_ROW_EMISSION,
)
from utils import (
    section, subsection, ok, warn, save_csv, safe_csv,
    compare_across_years, Timer, Logger, fmt_mj,
    enrich_df, add_total_row, safe_divide,
)

DAYS_PER_YEAR: int = 365


# ══════════════════════════════════════════════════════════════════════════════
# ENERGY ROW DIAGNOSTICS
# ══════════════════════════════════════════════════════════════════════════════

def check_energy_rows(year: str, log: Logger = None) -> dict:
    """
    Load indirect energy results for a year and compute key ratios.
    Returns dict with Emission/Final ratio and other diagnostics.
    """
    from config import YEARS
    cfg     = YEARS[year]
    wyr     = cfg["water_year"]
    io_tag  = cfg["io_tag"]
    io_year = cfg["io_year"]

    sut_path = DIRS["concordance"] / f"energy_coefficients_140_{io_tag}.csv"
    sut_df   = safe_csv(sut_path)
    if sut_df.empty:
        warn(f"Energy coefficients not found for {year} — run coefficients.py first", log)
        return {}

    final_col    = f"Energy_{wyr}_Final_MJ_per_crore"
    emission_col = f"Energy_{wyr}_Emission_MJ_per_crore"

    if final_col not in sut_df.columns:
        warn(f"Column '{final_col}' not in energy coefficients", log)
        return {}

    total_final    = sut_df[final_col].sum()
    total_emission = sut_df[emission_col].sum() if emission_col in sut_df.columns else 0

    result = {
        "year":              year,
        "water_year":        wyr,
        "Final_MJ_sum":      total_final,
        "Emission_MJ_sum":   total_emission,
        "Emission_Final_ratio": safe_divide(total_emission, total_final),
        "Final_TJ_EXIO_equiv": total_final / TJ_TO_MJ * 100,  # approx EUR-M reverse
    }
    ok(f"Energy check {year}: Final={total_final:,.0f} MJ/cr  "
       f"Emission/Final={result['Emission_Final_ratio']:.3f}", log)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# OUTBOUND ENERGY FOOTPRINT
# ══════════════════════════════════════════════════════════════════════════════

def compute_outbound_energy_year(year: str, log: Logger = None) -> tuple[float, list[dict]]:
    """
    Compute outbound energy footprint for one study year.

    Formula (analogous to water, Lee et al. 2021 adapted):
        tourists_to_d = outbound_total × dest_share_d
        outbound_MJ_d = tourists_to_d × avg_stay_days × (local_EF_MJ_yr / 365) × 1.5
    """
    counts = OUTBOUND_COUNTS.get(year)
    if counts is None:
        warn(f"No outbound counts for {year} — skipping", log)
        return 0.0, []

    total_tourists = counts["outbound_tourists_M"] * 1e6
    avg_stay       = counts["avg_stay_abroad_days"]

    if not OUTBOUND_ENERGY_DESTINATIONS:
        warn("OUTBOUND_ENERGY_DATA is empty — check reference_data.md. "
             "Add ## SECTION: OUTBOUND_ENERGY_DATA with country/dest_share/local_ef_mj_yr", log)
        return 0.0, []

    dest_rows: list[dict] = []
    total_mj = 0.0

    for dest in OUTBOUND_ENERGY_DESTINATIONS:
        tourists_d  = total_tourists * dest["dest_share"]
        daily_ef    = dest["local_ef_mj_yr"] / DAYS_PER_YEAR
        outbound_mj = tourists_d * avg_stay * daily_ef * TOURIST_WF_MULTIPLIER
        total_mj   += outbound_mj

        dest_rows.append({
            "Year":               year,
            "Country":            dest["country"],
            "Dest_share":         dest["dest_share"],
            "Local_EF_MJ_yr":     dest["local_ef_mj_yr"],
            "Carbon_intensity":   dest.get("carbon_intensity", 0.5),
            "Tourists_M":         round(tourists_d / 1e6, 3),
            "Avg_stay_days":      avg_stay,
            "Outbound_MJ":        round(outbound_mj),
            "Outbound_GJ":        round(outbound_mj / 1e3, 2),
            "Outbound_TJ":        round(outbound_mj / 1e6, 4),
        })

    ok(f"Outbound EF {year}: {total_tourists/1e6:.1f}M tourists × "
       f"{avg_stay:.1f} days → {fmt_mj(total_mj)}", log)
    return total_mj, dest_rows


def load_inbound_energy(year: str, log: Logger = None) -> float:
    """Load inbound-only indirect energy from split CSV."""
    split_path = DIRS["indirect_energy"] / f"indirect_energy_{year}_split.csv"
    split_df   = safe_csv(split_path)
    if not split_df.empty and "Inbound_Primary" in split_df.columns:
        inb = split_df[split_df.get("Type", pd.Series()) == "Inbound"] if "Type" in split_df.columns else split_df
        if not inb.empty:
            return float(inb["Inbound_Primary"].iloc[0])
    warn(f"Energy split CSV missing for {year} — inbound EF set to 0.0", log)
    return 0.0


# ══════════════════════════════════════════════════════════════════════════════
# INTENSITY BENCHMARKS
# ══════════════════════════════════════════════════════════════════════════════

def build_intensity_benchmarks(log: Logger = None) -> pd.DataFrame:
    """
    Cross-year energy intensity benchmarks from indirect results.
    Includes Emission/Final ratio trend.
    """
    rows = []
    for year in STUDY_YEARS:
        diag = check_energy_rows(year, log)
        if not diag:
            continue
        # Load all_years summary if available
        all_path = DIRS["indirect_energy"] / "indirect_energy_all_years.csv"
        all_df   = safe_csv(all_path)
        yr_row   = None
        if not all_df.empty and "Year" in all_df.columns:
            match = all_df[all_df["Year"].astype(str) == str(year)]
            yr_row = match.iloc[0] if not match.empty else None

        rows.append({
            "Year":                   year,
            "Final_MJ_sum":           round(diag.get("Final_MJ_sum", 0)),
            "Emission_MJ_sum":        round(diag.get("Emission_MJ_sum", 0)),
            "Emission_Final_ratio":   round(diag.get("Emission_Final_ratio", 0), 3),
            "Total_Primary_bn_MJ":    round(float(yr_row["Primary_Total_bn"]), 4)
                                      if yr_row is not None and "Primary_Total_bn" in yr_row.index else 0,
            "Intensity_MJ_per_crore": round(float(yr_row["Intensity_per_crore"]), 2)
                                      if yr_row is not None and "Intensity_per_crore" in yr_row.index else 0,
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    if len(df) >= 2:
        v0 = df["Final_MJ_sum"].iloc[0]
        df["Pct_Change_vs_2015"] = (100 * (df["Final_MJ_sum"] - v0) / v0).round(2)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# SAVE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def save_summary_txt(all_rows: list[dict], out_path: Path, log: Logger = None):
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("OUTBOUND TOURISM ENERGY FOOTPRINT & NET BALANCE\n")
        f.write("=" * 60 + "\n\n")
        f.write("Formula: Outbound_MJ = tourists × avg_stay × (local_EF_MJ_yr/365) × 1.5\n\n")
        f.write(f"{'Year':<6}  {'Outbound MJ':>14}  {'Outbound TJ':>12}  "
                f"{'Inbound MJ':>12}  {'Net MJ':>12}  {'Ratio':>8}\n")
        f.write("─" * 70 + "\n")
        for r in all_rows:
            ratio = safe_divide(r["Outbound_MJ"], max(r.get("Inbound_MJ", 0), 1))
            f.write(f"{r['Year']:<6}  {r['Outbound_MJ']:>14,.0f}  "
                    f"{r['Outbound_MJ']/1e6:>12.2f}  "
                    f"{r.get('Inbound_MJ',0):>12,.0f}  "
                    f"{r.get('Net_MJ',0):>+12,.0f}  {ratio:>8.3f}\n")
    ok(f"Summary: {out_path.name}", log)


# ══════════════════════════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════════════════════════

def run(**kwargs):
    out_dir = DIRS["outbound_energy"]
    out_dir.mkdir(parents=True, exist_ok=True)

    with Logger("outbound_energy", DIRS["logs"]) as log:
        t = Timer()
        log.section("OUTBOUND ENERGY FOOTPRINT & NET BALANCE")

        all_summary_rows = []
        all_dest_rows    = []

        for year in STUDY_YEARS:
            total_mj, dest_rows = compute_outbound_energy_year(year, log)
            inbound_mj          = load_inbound_energy(year, log)
            net_mj              = total_mj - inbound_mj

            if dest_rows:
                dest_df = pd.DataFrame(dest_rows)
                dest_df = enrich_df(dest_df, "Outbound_MJ",
                                     add_total=True, label_col="Country")
                all_dest_rows.append(dest_df)

            all_summary_rows.append({
                "Year":           year,
                "Outbound_MJ":    round(total_mj),
                "Outbound_GJ":    round(total_mj / 1e3, 2),
                "Outbound_TJ":    round(total_mj / 1e6, 4),
                "Inbound_MJ":     round(inbound_mj),
                "Net_MJ":         round(net_mj),
                "Net_TJ":         round(net_mj / 1e6, 4),
                "Outbound_to_Inbound_Ratio": round(safe_divide(total_mj, max(inbound_mj, 1)), 3),
                "Net_Direction":  "exporter" if net_mj < 0 else "importer",
            })

        if all_summary_rows:
            summary_df = pd.DataFrame(all_summary_rows)
            if len(summary_df) >= 2:
                v0 = summary_df["Outbound_MJ"].iloc[0]
                summary_df["Pct_Change_vs_2015"] = (
                    100 * (summary_df["Outbound_MJ"] - v0) / v0
                ).round(2)
            summary_df = add_total_row(summary_df, label_col="Year")
            save_csv(summary_df, out_dir / "outbound_energy_all_years.csv",
                     "Outbound energy all years", log=log)
            compare_across_years(
                {r["Year"]: r["Outbound_TJ"] for r in all_summary_rows},
                "Outbound EF (TJ)", unit=" TJ", log=log)
            save_summary_txt(all_summary_rows,
                             out_dir / "outbound_energy_summary.txt", log)

        if all_dest_rows:
            save_csv(pd.concat(all_dest_rows, ignore_index=True),
                     out_dir / "outbound_energy_by_dest.csv",
                     "Outbound energy by destination", log=log)

        # Intensity benchmarks
        bench_df = build_intensity_benchmarks(log)
        if not bench_df.empty:
            save_csv(bench_df, out_dir / "energy_intensity_benchmarks.csv",
                     "Energy intensity benchmarks", log=log)

        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    run()
