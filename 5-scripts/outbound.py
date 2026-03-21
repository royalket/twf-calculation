"""
outbound.py
===========
MERGE of outbound_twf.py + energy.py

Computes outbound tourism footprint (water or energy) and net balance
vs inbound EEIO results.

Formula (Lee et al. 2021, adapted):
    footprint_d = tourists_to_d × avg_stay_days × (local_rate_d / 365) × multiplier

Two scopes are computed for water stressor:
    tourism  — stays ≤4 weeks (ITS Table 4.8.2); primary result for TWF paper.
    all_INDs — total Indian National Departures incl. workers/diaspora >1 month;
               reported as Panel B2 in outbound table for context.

Entry points:
    run(stressor="water")
    run(stressor="energy")

# ─────────────────────────────────────────────────────────────────────────────
# TODO
# ─────────────────────────────────────────────────────────────────────────────
# TODO-1  Replace sys.path.insert with proper package (pyproject.toml).
#
# TODO-2  OUTBOUND_DESTINATIONS and OUTBOUND_ENERGY_DESTINATIONS in config.py
#         should be unified into a single list keyed by stressor, e.g.:
#             OUTBOUND_DESTINATIONS = {
#                 "water":  [...],   # local_wf_m3_yr, wsi_dest
#                 "energy": [...],   # local_ef_mj_yr, carbon_intensity
#             }
#         Currently two separate lists in config.py require manual sync.
#
# TODO-3  OUTBOUND_COUNTS is the same for both stressors (it's tourist counts,
#         not stressor-specific). Confirm and document in config.py.
#
# TODO-4  Write regression tests for:
#           - compute_outbound(): total > 0, dest rows sum to total
#           - load_inbound_split(): returns 0.0 + warns when file is missing
#           - net balance direction: positive = importer, negative = exporter
#
# TODO-5  DONE: dual-scope (tourism vs all_INDs) now implemented.
#         Energy stressor uses tourism scope only (all_INDs not meaningful for
#         energy since Gulf workers have very different energy profiles).
# ─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))   # TODO-1: remove after packaging
from config import (
    DIRS, STUDY_YEARS, OUTBOUND_DESTINATIONS, OUTBOUND_COUNTS,
    OUTBOUND_ENERGY_DESTINATIONS, TOURIST_WF_MULTIPLIER, TOURIST_ENERGY_MULTIPLIER,
)
from utils import (
    ok, warn, save_csv, safe_csv, compare_across_years,
    enrich_df, add_total_row, safe_divide, Timer, Logger, fmt_m3, fmt_mj,
)

Stressor = Literal["water", "energy"]
DAYS_PER_YEAR = 365

# ── Per-stressor configuration ────────────────────────────────────────────────
_CFG: dict[str, dict] = {
    "water": {
        "destinations":     None,           # set at runtime from config
        "rate_key":         "local_wf_m3_yr",
        "unit":             "m3",
        "unit_label":       "m³",
        "bn_divisor":       1e9,
        "bn_label":         "bn m³",
        "split_dir_key":    "indirect",
        "split_template":   "indirect_water_{year}_split.csv",
        "split_value_col":  "TWF_m3",
        "out_dir_key":      "outbound",
        "log_name":         "outbound_twf",
        "section_title":    "OUTBOUND TOURISM WATER FOOTPRINT & NET BALANCE",
        "fmt_fn":           fmt_m3,
        "data_note":        "Destination shares: India Tourism Statistics 2022 (MoT). "
                            "Local WF: Hoekstra & Mekonnen (2012) national per-capita WF.",
        "placeholder_warn": "NOTE: Destination shares are PLACEHOLDER — verify before publication.",
    },
    "energy": {
        "destinations":     None,           # set at runtime from config
        "rate_key":         "local_ef_mj_yr",
        "unit":             "MJ",
        "unit_label":       "MJ",
        "bn_divisor":       1e9,
        "bn_label":         "bn MJ",
        "split_dir_key":    "indirect_energy",
        "split_template":   "indirect_energy_{year}_split.csv",
        "split_value_col":  "Inbound_Primary",
        "out_dir_key":      "outbound_energy",
        "log_name":         "outbound_energy",
        "section_title":    "OUTBOUND ENERGY FOOTPRINT & NET BALANCE",
        "fmt_fn":           fmt_mj,
        "data_note":        "Formula: Outbound = tourists × avg_stay × (local_EF_MJ_yr/365) × 1.5",
        "placeholder_warn": "",
    },
}


def _get_destinations(stressor: Stressor) -> list:
    """Resolve destination list from config at call time."""
    if stressor == "water":
        return OUTBOUND_DESTINATIONS or []
    return OUTBOUND_ENERGY_DESTINATIONS or []


# ══════════════════════════════════════════════════════════════════════════════
# CORE CALCULATOR
# ══════════════════════════════════════════════════════════════════════════════

def compute_outbound(year: str, stressor: Stressor,
                     scope: str = "tourism",
                     log: Logger = None) -> tuple[float, list[dict]]:
    """
    Compute outbound footprint for one study year.

    Parameters
    ----------
    scope : "tourism"  — uses tourism_M + avg_stay_tourism (stays ≤4 weeks).
                         Primary result for TWF paper.
            "all_INDs" — uses all_INDs_M + avg_stay_all (incl. workers/diaspora).
                         Supplementary context only; not recommended for TWF paper.

    Formula per destination d:
        tourists_d = total_tourists × dest_share_d
        footprint_d = tourists_d × avg_stay × (rate_d / 365) × multiplier

    Returns (total_footprint, list_of_dest_rows).
    """
    cfg   = _CFG[stressor]
    dests = _get_destinations(stressor)
    counts = OUTBOUND_COUNTS.get(year)

    if counts is None:
        warn(f"No outbound counts for {year} — skipping", log)
        return 0.0, []
    if not dests:
        warn(f"No destination data for {stressor} — check reference_data.md", log)
        return 0.0, []

    # Select tourists and avg_stay based on scope
    if scope == "all_INDs":
        total_tourists = counts["all_INDs_M"] * 1e6
        avg_stay       = counts["avg_stay_all"]
    else:  # tourism (default)
        total_tourists = counts["tourism_M"] * 1e6
        avg_stay       = counts["avg_stay_tourism"]

    rate_key       = cfg["rate_key"]
    dest_rows: list[dict] = []
    total = 0.0
    # FIX-3c: use stressor-specific tourist multiplier.
    # Water: 1.5× (Hadjikakou 2015; Li 2018; Lee 2021). Energy: 1.0× (no literature basis yet).
    tourist_mult = TOURIST_WF_MULTIPLIER if stressor == "water" else TOURIST_ENERGY_MULTIPLIER

    for dest in dests:
        tourists_d  = total_tourists * dest["dest_share"]
        daily_rate  = dest[rate_key] / DAYS_PER_YEAR
        footprint_d = tourists_d * avg_stay * daily_rate * tourist_mult
        total      += footprint_d

        row: dict = {
            "Year":         year,
            "Scope":        scope,
            "Country":      dest["country"],
            "Dest_share":   dest["dest_share"],
            rate_key:       dest[rate_key],
            "Tourists_M":   round(tourists_d / 1e6, 3),
            "Avg_stay_days": avg_stay,
            "Footprint":    round(footprint_d),
            f"Footprint_bn_{cfg['unit']}": round(footprint_d / cfg["bn_divisor"], 5),
        }
        # Water-specific scarce footprint
        if stressor == "water" and "wsi_dest" in dest:
            row["WSI_dest"]    = dest["wsi_dest"]
            row["Scarce_m3"]   = footprint_d * dest["wsi_dest"]
        # Energy-specific carbon intensity
        if stressor == "energy":
            row["Carbon_intensity"] = dest.get("carbon_intensity", 0.5)

        dest_rows.append(row)

    ok(f"Outbound {stressor} {year} [{scope}]: {total_tourists/1e6:.1f}M tourists × "
       f"{avg_stay:.1f} days → {cfg['fmt_fn'](total)}", log)
    return total, dest_rows


def load_inbound_split(year: str, stressor: Stressor, log: Logger = None) -> float:
    """
    Load inbound-only footprint from the EEIO indirect split CSV.

    Returns 0.0 with a critical warning if the file is missing — the correct
    fix is to re-run indirect.py after ensuring inbound/domestic demand vectors
    exist in the demand directory.

    CRITICAL: do NOT fall back to total indirect footprint (inbound + domestic
    combined) — that made the net balance appear 4-5× wrong in earlier code.
    """
    cfg        = _CFG[stressor]
    split_path = DIRS[cfg["split_dir_key"]] / cfg["split_template"].format(year=year)
    split_df   = safe_csv(split_path)
    val_col    = cfg["split_value_col"]

    if not split_df.empty and "Type" in split_df.columns and val_col in split_df.columns:
        inb = split_df[split_df["Type"] == "Inbound"]
        if not inb.empty:
            return float(inb[val_col].iloc[0])

    warn(
        f"CRITICAL: {split_path.name} missing or lacks 'Type'/'{val_col}' columns. "
        f"Net {stressor} balance for {year} will be UNRELIABLE — inbound set to 0.0. "
        f"Re-run indirect.py after ensuring split demand files exist.",
        log,
    )
    return 0.0


# ══════════════════════════════════════════════════════════════════════════════
# REPORTING
# ══════════════════════════════════════════════════════════════════════════════

def _print_net_balance(all_rows: list[dict], stressor: Stressor, log: Logger = None):
    cfg    = _CFG[stressor]
    unit   = cfg["bn_label"]
    lines  = [
        f"\n  {'Year':<6}  {'Outbound':>16}  {'Inbound':>16}  "
        f"{'Net':>14}  {'Direction':>12}",
        "  " + "─" * 68,
    ]
    for r in all_rows:
        outb = r["Outbound_bn"]
        inb  = r["Inbound_bn"]
        net  = r["Net_bn"]
        direction = "exporter" if net < 0 else "importer"
        lines.append(
            f"  {r['Year']:<6}  {outb:>14.4f} {unit}  {inb:>14.4f} {unit}  "
            f"{net:>+12.4f} {unit}  {direction:>12}"
        )
    msg = "\n".join(lines)
    if log:
        log._log(msg)
    else:
        print(msg)

    last = all_rows[-1] if all_rows else None
    if last:
        direction = "NET EXPORTER" if last["Net_bn"] < 0 else "NET IMPORTER"
        ok(f"{last['Year']}: India is a {direction} of virtual {stressor} via tourism.", log)


def _save_summary_txt(all_rows: list[dict], path: Path, stressor: Stressor,
                      log: Logger = None):
    cfg = _CFG[stressor]
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"OUTBOUND TOURISM {stressor.upper()} FOOTPRINT & NET BALANCE\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"{cfg['data_note']}\n\n")
        if cfg["placeholder_warn"]:
            f.write(f"{cfg['placeholder_warn']}\n\n")
        for r in all_rows:
            f.write(f"Year: {r['Year']}\n")
            f.write(f"  Outbound tourists:   {r['Outbound_tourists_M']:.1f} M\n")
            f.write(f"  Avg stay abroad:     {r['Avg_stay_days']:.1f} days\n")
            f.write(f"  Outbound footprint:  {r['Outbound_bn']:.4f} {cfg['bn_label']}\n")
            f.write(f"  Inbound footprint:   {r['Inbound_bn']:.4f} {cfg['bn_label']}\n")
            net_sign = "+" if r["Net_bn"] >= 0 else ""
            f.write(f"  Net balance:         {net_sign}{r['Net_bn']:.4f} {cfg['bn_label']}\n")
            f.write(f"  India is net:        {'IMPORTER' if r['Net_bn'] > 0 else 'EXPORTER'}\n\n")
    ok(f"Summary: {path.name}", log)


# ══════════════════════════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════════════════════════

def run(stressor: Stressor = "water", **kwargs):
    cfg     = _CFG[stressor]
    out_dir = DIRS[cfg["out_dir_key"]]
    out_dir.mkdir(parents=True, exist_ok=True)

    with Logger(cfg["log_name"], DIRS["logs"]) as log:
        t = Timer()
        log.section(cfg["section_title"])
        log.info(cfg["data_note"])
        if cfg["placeholder_warn"]:
            log.info(cfg["placeholder_warn"])
        _mult = TOURIST_WF_MULTIPLIER if stressor == "water" else TOURIST_ENERGY_MULTIPLIER
        log.info(f"Tourist multiplier = {_mult} ({'water literature' if stressor == 'water' else 'neutral — no energy literature yet'})")

        all_year_rows: list[dict] = []
        all_dest_rows: list[pd.DataFrame] = []
        all_dest_rows_allinds: list[pd.DataFrame] = []

        for year in STUDY_YEARS:
            counts = OUTBOUND_COUNTS.get(year)
            if counts is None:
                warn(f"No outbound counts for {year}", log)
                continue

            # ── Primary: tourism-only scope (stays ≤4 weeks) ─────────────────
            outbound_tourism, dest_rows_t = compute_outbound(
                year, stressor, scope="tourism", log=log)
            inbound_total = load_inbound_split(year, stressor, log)
            net_tourism   = outbound_tourism - inbound_total

            # ── Supplementary: all-INDs scope (incl. workers/diaspora) ───────
            # Water only — all_INDs not meaningful for energy stressor
            outbound_all = 0.0
            dest_rows_a  = []
            if stressor == "water":
                outbound_all, dest_rows_a = compute_outbound(
                    year, stressor, scope="all_INDs", log=log)

            if dest_rows_t:
                dest_df = pd.DataFrame(dest_rows_t)
                all_dest_rows.append(dest_df)

                # Water: log top 5 destinations by water stress
                if stressor == "water":
                    log.subsection(f"Top 5 destinations by outbound footprint — {year} [tourism]")
                    sorted_dests = sorted(dest_rows_t, key=lambda x: x["Footprint"], reverse=True)
                    log.table(
                        ["Country", "Share", "Rate", "Tourists(M)", "Footprint"],
                        [[d["Country"], f"{d['Dest_share']*100:.0f}%",
                          f"{d[cfg['rate_key']]:,}", f"{d['Tourists_M']:.2f}",
                          f"{d['Footprint']:,.0f}"]
                         for d in sorted_dests[:5]],
                    )

            # Save all_INDs dest rows separately
            if dest_rows_a:
                all_dest_rows_allinds.append(pd.DataFrame(dest_rows_a))

            all_year_rows.append({
                "Year":                     year,
                # Tourism scope
                "Outbound_tourists_M":      counts["tourism_M"],
                "Avg_stay_days":            counts["avg_stay_tourism"],
                "Outbound":                 round(outbound_tourism),
                "Outbound_bn":              round(outbound_tourism / cfg["bn_divisor"], 5),
                "Outbound_M_m3":            round(outbound_tourism / 1e6, 2),
                # All-INDs scope (water only)
                "All_INDs_M":               counts["all_INDs_M"],
                "Avg_stay_all_days":        counts["avg_stay_all"],
                "Outbound_allINDs":         round(outbound_all),
                "Outbound_allINDs_M_m3":    round(outbound_all / 1e6, 2),
                # Inbound + net
                "Inbound":                  round(inbound_total),
                "Inbound_bn":               round(inbound_total / cfg["bn_divisor"], 5),
                "Net":                      round(net_tourism),
                "Net_bn":                   round(net_tourism / cfg["bn_divisor"], 5),
                "Net_bn_m3":                round(net_tourism / cfg["bn_divisor"], 5),  # alias for compare.py
                "Net_M_m3":                 round(net_tourism / 1e6, 2),
                "Outbound_to_Inbound_Ratio": round(safe_divide(outbound_tourism, max(inbound_total, 1)), 3),
                "Net_Direction":            "exporter" if net_tourism < 0 else "importer",
                "Tourist_Multiplier":       TOURIST_WF_MULTIPLIER if stressor == "water" else TOURIST_ENERGY_MULTIPLIER,
                # Water-specific scarce footprint
                **({
                    "Outbound_Scarce":          round(sum(r.get("Scarce_m3", 0) for r in dest_rows_t)),
                    "Outbound_Scarce_M_m3":     round(sum(r.get("Scarce_m3", 0) for r in dest_rows_t) / 1e6, 2),
                    "Outbound_allINDs_Scarce_M_m3": round(sum(r.get("Scarce_m3", 0) for r in dest_rows_a) / 1e6, 2),
                    "Data_Status":              "VERIFIED — ITS 2022 Table 4.8.2",
                    "Net_Balance_Method_Note": (
                        "Outbound=activity-based tourism-only (Lee et al. 2021, stays≤4wk); "
                        "Inbound=EEIO Leontief (W·L·Y). Indicative balance only."
                    ),
                } if stressor == "water" else {}),
            })

        if all_year_rows:
            _print_net_balance(all_year_rows, stressor, log)

            summary_df = pd.DataFrame(all_year_rows)
            if len(summary_df) >= 2:
                v0 = summary_df["Outbound_bn"].iloc[0]
                summary_df["Pct_Change_vs_base"] = (
                    100 * (summary_df["Outbound_bn"] - v0) / v0
                ).round(2)
            summary_df = add_total_row(summary_df, label_col="Year")

            save_csv(summary_df, out_dir / f"outbound_{stressor}_all_years.csv",
                     f"Outbound {stressor} all years", log=log)
            _save_summary_txt(all_year_rows, out_dir / f"outbound_{stressor}_summary.txt",
                              stressor, log)

            compare_across_years(
                {r["Year"]: r["Outbound_bn"] for r in all_year_rows},
                f"Outbound {stressor} ({cfg['bn_label']})", unit=f" {cfg['bn_label']}", log=log,
            )
            compare_across_years(
                {r["Year"]: r["Net_bn"] for r in all_year_rows},
                f"Net {stressor} balance ({cfg['bn_label']}; + = importer)",
                unit=f" {cfg['bn_label']}", log=log,
            )

        if all_dest_rows:
            save_csv(pd.concat(all_dest_rows, ignore_index=True),
                     out_dir / f"outbound_{stressor}_by_dest.csv",
                     f"Outbound {stressor} by destination [tourism]", log=log)

        if all_dest_rows_allinds and stressor == "water":
            save_csv(pd.concat(all_dest_rows_allinds, ignore_index=True),
                     out_dir / f"outbound_{stressor}_by_dest_allinds.csv",
                     f"Outbound {stressor} by destination [all-INDs]", log=log)

        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--stressor", choices=["water", "energy"], default="water")
    run(stressor=ap.parse_args().stressor)