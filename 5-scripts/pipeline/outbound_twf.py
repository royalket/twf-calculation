"""
outbound_twf.py — India Outbound Tourism Water Footprint & Net Balance
=======================================================================

Formula (Lee et al. 2021 methodology, adapted for India):
  Outbound_TWF_country = N_tourists_to_country
                         × avg_stay_abroad_days
                         × (local_WF_m3_yr / 365)
                         × tourist_multiplier (1.5)

  Net_TWF = Outbound_TWF_total - Inbound_TWF_total
  Positive net = India is net water consumer via tourism (outbound > inbound).
  Negative net = India is net water exporter via tourism (inbound > outbound).

Data sources:
  - Destination shares: India Tourism Statistics 2022 (MoT), OUTBOUND_TWF_DATA section
  - Outbound counts:    OUTBOUND_TOURIST_COUNTS section in reference_data.md
  - Inbound TWF:        loaded from indirect_twf_{year}_by_category.csv
  - Local WF:           Hoekstra & Mekonnen (2012) PNAS national per-capita WF

Outputs (in 3-final-results/outbound-twf/):
  outbound_twf_all_years.csv    — per-year outbound totals + net balance
  outbound_twf_by_dest.csv      — per-destination breakdown (all years)
  outbound_twf_summary.txt      — human-readable summary

WSI note:
  Destination WSI weights (wsi_dest) from OUTBOUND_TWF_DATA allow a scarce-water
  variant: outbound_scarce_m3 = outbound_m3 × wsi_dest. UAE/Saudi Arabia score
  1.0 (maximum stress), USA 0.35, UK 0.18.

Citation:
  Lee, C.-W., Li, J., & Luo, D. (2021). Tourism water footprint: A case study of
  China's outbound tourism. Journal of Hydrology, 603, 127151.
  Hoekstra, A.Y. and Mekonnen, M.M. (2012). The water footprint of humanity.
  PNAS, 109(9), 3232-3237.
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    DIRS, STUDY_YEARS, OUTBOUND_DESTINATIONS, OUTBOUND_COUNTS,
    TOURIST_WF_MULTIPLIER, USD_INR,
)
from utils import (
    section, subsection, ok, warn, save_csv, safe_csv,
    read_csv, compare_across_years, Timer, Logger, fmt_m3,
)


DAYS_PER_YEAR: int = 365


# ══════════════════════════════════════════════════════════════════════════════
# CORE CALCULATOR
# ══════════════════════════════════════════════════════════════════════════════

def compute_outbound_year(year: str, log: Logger = None) -> tuple[float, list[dict]]:
    """
    Compute outbound TWF for one study year.

    Returns (total_outbound_m3, list_of_dest_rows).

    Formula per destination d:
        tourists_to_d = outbound_total × dest_share_d
        daily_wf_d    = local_wf_m3_yr_d / DAYS_PER_YEAR
        outbound_m3_d = tourists_to_d × avg_stay_days × daily_wf_d × 1.5

    The 1.5 tourist multiplier accounts for tourists consuming 50% more water
    per day than local residents (higher-quality accommodation, more showers,
    laundry, pool use).
    Source: Hadjikakou et al. (2015); Lee et al. (2021).
    """
    counts = OUTBOUND_COUNTS.get(year)
    if counts is None:
        warn(f"No outbound counts for {year} — skipping", log)
        return 0.0, []

    total_tourists   = counts["outbound_tourists_M"] * 1e6
    avg_stay         = counts["avg_stay_abroad_days"]
    multiplier       = TOURIST_WF_MULTIPLIER         # 1.5

    if not OUTBOUND_DESTINATIONS:
        warn("OUTBOUND_TWF_DATA section is empty — check reference_data.md", log)
        return 0.0, []

    dest_rows: list[dict] = []
    total_m3 = 0.0

    for dest in OUTBOUND_DESTINATIONS:
        tourists_d    = total_tourists * dest["dest_share"]
        daily_wf_d    = dest["local_wf_m3_yr"] / DAYS_PER_YEAR
        outbound_m3   = tourists_d * avg_stay * daily_wf_d * multiplier
        scarce_m3     = outbound_m3 * dest.get("wsi_dest", 0.5)
        total_m3     += outbound_m3

        dest_rows.append({
            "Year":              year,
            "Country":           dest["country"],
            "Dest_share":        dest["dest_share"],
            "Local_WF_m3_yr":    dest["local_wf_m3_yr"],
            "WSI_dest":          dest.get("wsi_dest", 0.5),
            "Tourists_M":        round(tourists_d / 1e6, 3),
            "Avg_stay_days":     avg_stay,
            "Outbound_m3":       round(outbound_m3),
            "Outbound_bn_m3":    round(outbound_m3 / 1e9, 5),
            "Scarce_m3":         scarce_m3,   # raw float — rounded at aggregation stage
        })

    ok(
        f"Outbound TWF {year}: {total_tourists/1e6:.1f}M tourists × "
        f"{avg_stay:.1f} days → {total_m3/1e9:.4f} bn m³",
        log,
    )
    return total_m3, dest_rows


def load_inbound_twf(year: str, log=None) -> float:
    """
    Load inbound-only indirect TWF from split CSV.

    CRITICAL BUG FIX: The previous fallback returned *total* indirect TWF
    (domestic + inbound combined) when the split CSV was missing. This made
    inbound appear 4–5× larger than reality, causing the net balance to show
    India as a massive net water exporter when the truth may be near-zero.

    Now: returns 0.0 with a critical warning when the split CSV is missing.
    The correct fix is to re-run calculate_indirect_twf.py with inbound/domestic
    demand vectors present (Y_tourism_{year}_inbound.csv, Y_tourism_{year}_domestic.csv).
    """
    split_path = DIRS["indirect"] / f"indirect_twf_{year}_split.csv"
    split_df   = safe_csv(split_path)
    if not split_df.empty and "Type" in split_df.columns and "TWF_m3" in split_df.columns:
        inb_row = split_df[split_df["Type"] == "Inbound"]
        if not inb_row.empty:
            return float(inb_row["TWF_m3"].iloc[0])

    warn(
        f"CRITICAL: indirect_twf_{year}_split.csv not found or lacks 'Type'/'TWF_m3' columns. "
        "Net TWF balance for this year will be UNRELIABLE — inbound TWF set to 0.0 m³. "
        "Re-run calculate_indirect_twf.py after ensuring Y_tourism_{year}_inbound.csv "
        "and Y_tourism_{year}_domestic.csv exist in the demand directory.",
        log,
    )
    return 0.0


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY REPORTER
# ══════════════════════════════════════════════════════════════════════════════

def print_net_balance_summary(all_rows: list[dict], log: Logger = None):
    subsection("Net TWF Balance (Outbound − Inbound)", log)
    lines = [
        f"\n  {'Year':<6}  {'Outbound (bn m³)':>18}  {'Inbound (bn m³)':>17}  "
        f"{'Net (bn m³)':>13}  {'Direction':>12}",
        "  " + "─" * 72,
    ]
    for r in all_rows:
        outb = r["Outbound_bn_m3"]
        inb  = r["Inbound_bn_m3"]
        net  = r["Net_bn_m3"]
        direction = "exporter" if net < 0 else "importer"
        lines.append(
            f"  {r['Year']:<6}  {outb:>18.4f}  {inb:>17.4f}  "
            f"{net:>+13.4f}  {direction:>12}"
        )
    msg = "\n".join(lines)
    if log:
        log._log(msg)
    else:
        print(msg)

    # Key policy finding
    last = all_rows[-1] if all_rows else None
    if last:
        net_sign = "NET EXPORTER" if last["Net_bn_m3"] < 0 else "NET IMPORTER"
        ok(
            f"{last['Year']}: India is a {net_sign} of water via tourism. "
            f"Top destinations UAE/Saudi Arabia face extreme water stress (WSI=1.0) — "
            f"India's outbound tourism embeds virtual water in water-scarce regions.",
            log,
        )


def save_summary_txt(all_rows: list[dict], out_path: Path, log: Logger = None):
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("OUTBOUND TOURISM WATER FOOTPRINT & NET BALANCE\n")
        f.write("=" * 60 + "\n\n")
        f.write("Methodology\n")
        f.write("-----------\n")
        f.write(
            "Outbound_m3 = tourists_to_country × avg_stay_days\n"
            "              × (local_WF_m3_yr / 365) × 1.5\n\n"
            "Tourist multiplier 1.5: tourists consume 50% more than local\n"
            "residents per day (Hadjikakou et al. 2015; Lee et al. 2021).\n\n"
            "Local WF: Hoekstra & Mekonnen (2012) national per-capita WF.\n"
            "Destination shares: India Tourism Statistics 2022, MoT.\n\n"
            "DATA STATUS: PLACEHOLDER — verify destination shares before publication.\n\n"
        )
        for r in all_rows:
            f.write(f"Year: {r['Year']}\n")
            f.write(f"  Outbound tourists:    {r['Outbound_tourists_M']:.1f} M\n")
            f.write(f"  Avg stay abroad:      {r['Avg_stay_days']:.1f} days\n")
            f.write(f"  Outbound TWF (blue):  {r['Outbound_bn_m3']:.4f} bn m³\n")
            f.write(f"  Outbound TWF (scarce):{r['Outbound_Scarce_bn_m3']:.4f} bn m³\n")
            f.write(f"  Inbound TWF (EEIO):   {r['Inbound_bn_m3']:.4f} bn m³\n")
            net_sign = "+" if r['Net_bn_m3'] >= 0 else ""
            f.write(f"  Net TWF balance:      {net_sign}{r['Net_bn_m3']:.4f} bn m³\n")
            f.write(f"  India is net:         {'IMPORTER' if r['Net_bn_m3'] > 0 else 'EXPORTER'}\n\n")
    ok(f"Summary: {out_path.name}", log)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def run(**kwargs):
    with Logger("outbound_twf", DIRS["logs"]) as log:
        t       = Timer()
        out_dir = DIRS["outbound"]
        out_dir.mkdir(parents=True, exist_ok=True)
        log.section("OUTBOUND TOURISM WATER FOOTPRINT & NET BALANCE")
        log.info("Source: India Tourism Statistics 2022 destination shares")
        log.info("        × Hoekstra & Mekonnen (2012) national WF")
        log.info(f"        × tourist multiplier = {TOURIST_WF_MULTIPLIER}")
        log.info("NOTE: Destination shares are PLACEHOLDER — verify before publication.")

        all_year_rows : list[dict] = []
        all_dest_rows : list[dict] = []

        for year in STUDY_YEARS:
            log.subsection(f"Year: {year}")
            counts = OUTBOUND_COUNTS.get(year)
            if counts is None:
                warn(f"No outbound counts for {year}", log)
                continue

            outbound_m3, dest_rows = compute_outbound_year(year, log)
            inbound_m3             = load_inbound_twf(year, log)

            # Scarce outbound
            outbound_scarce = sum(r["Scarce_m3"] for r in dest_rows)  # sum exact floats first

            # Top 3 destinations by outbound_m3
            if dest_rows:
                sorted_dests = sorted(dest_rows, key=lambda x: x["Outbound_m3"], reverse=True)
                log.subsection(f"Top 5 destinations by outbound TWF — {year}")
                log.table(
                    ["Country", "Share", "WF(L)", "Tourists(M)", "Outbound m³", "WSI"],
                    [[
                        d["Country"],
                        f"{d['Dest_share']*100:.0f}%",
                        f"{d['Local_WF_m3_yr']:,}",
                        f"{d['Tourists_M']:.2f}",
                        f"{d['Outbound_m3']:,.0f}",
                        f"{d['WSI_dest']:.2f}",
                    ] for d in sorted_dests[:5]],
                )

            net_m3 = outbound_m3 - inbound_m3

            all_year_rows.append({
                "Year":                   year,
                "Outbound_tourists_M":    counts["outbound_tourists_M"],
                "Avg_stay_days":          counts["avg_stay_abroad_days"],
                "Outbound_m3":            round(outbound_m3),
                "Outbound_bn_m3":         round(outbound_m3 / 1e9, 5),
                "Outbound_Scarce_m3":     round(outbound_scarce),
                "Outbound_Scarce_bn_m3":  round(outbound_scarce / 1e9, 5),
                "Inbound_m3":             round(inbound_m3),
                "Inbound_bn_m3":          round(inbound_m3 / 1e9, 5),
                "Net_m3":                 round(net_m3),
                "Net_bn_m3":              round(net_m3 / 1e9, 5),
                "Tourist_Multiplier":     TOURIST_WF_MULTIPLIER,
                "Data_Status":            "PLACEHOLDER — verify MoT destination shares",
                # ── Methodological note ──────────────────────────────────────
                # Outbound TWF uses a per-capita activity multiplier
                # (Lee et al. 2021: tourists × days × local_WF/365 × 1.5).
                # Inbound TWF uses EEIO Leontief pull (W·L·Y_inbound).
                # These are NOT methodologically equivalent — activity-based
                # vs supply-chain-embedded water. Net balance should be
                # treated as indicative only, not a precise bilateral comparison.
                "Net_Balance_Method_Note": (
                    "Outbound=activity-based (Lee et al. 2021); "
                    "Inbound=EEIO Leontief (W·L·Y). "
                    "Not directly comparable — indicative balance only."
                ),
            })
            all_dest_rows.extend(dest_rows)

        if all_year_rows:
            print_net_balance_summary(all_year_rows, log)

            df_years = pd.DataFrame(all_year_rows)
            df_dests = pd.DataFrame(all_dest_rows)
            save_csv(df_years, out_dir / "outbound_twf_all_years.csv",
                     "Outbound TWF all years", log=log)
            save_csv(df_dests, out_dir / "outbound_twf_by_dest.csv",
                     "Outbound TWF by destination", log=log)
            save_summary_txt(all_year_rows, out_dir / "outbound_twf_summary.txt", log)

            compare_across_years(
                {r["Year"]: r["Outbound_bn_m3"] for r in all_year_rows},
                "Outbound TWF (billion m³)", unit=" bn m³", log=log,
            )
            compare_across_years(
                {r["Year"]: r["Net_bn_m3"] for r in all_year_rows},
                "Net TWF balance (billion m³; + = importer)", unit=" bn m³", log=log,
            )

        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    run()