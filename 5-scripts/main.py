"""
main.py — Pipeline Orchestrator
================================
Runs the full India tourism footprint pipeline.

Usage (CLI)
-----------
    python main.py --water               # water pipeline only
    python main.py --energy              # energy pipeline only
    python main.py --ndp                 # NDP depletion pipeline
    python main.py --all                 # water + energy + NDP + combined report
    python main.py --steps build_io coefficients indirect
    python main.py --stressor energy --steps indirect sda
    python main.py --validate-only       # run sanity checks only
    python main.py --list-steps

Steps
-----
    build_io        — pipeline_inputs.py    (SUT → Leontief L)
    demand          — pipeline_inputs.py    (TSA demand vectors)
    coefficients    — build_coefficients.py (F.txt → SUT 140)
    indirect        — indirect.py           (C×L×Y footprint)
    direct          — postprocess.py        (activity-based direct TWF)
    outbound        — outbound.py           (outbound + net balance)
    sda             — decompose.py          (SDA + MC, universal stressor)
    monetise        — postprocess.py        (physical depletion → ₹ crore)
    ndp_report      — postprocess.py        (NDP = GDP − CFC − depletion)
    report          — compare.py            (cross-year report + Markdown)
    visualise       — visualise.py          (all charts)
    validate        — (built-in)            (sanity checks on all outputs)

File consolidation (from 18 → 13 files):
    pipeline_inputs.py   ← build_io.py + build_demand.py
    postprocess.py       ← direct.py + monetise.py + ndp_report.py
    decompose.py         ← universal SDA + MC for all stressors
    main.py              ← main.py + validate_outputs.py
    report_template.md   ← water_report_template.md + energy_report_template.md + NDP template
    reference_data.md    ← reference_data.md + UNIT_RENTS + NAS_MACRO sections
    config.py            ← config.py with loaders + indirect_dir() + new DIRS
"""

from __future__ import annotations
import argparse
import importlib
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import DIRS, STUDY_YEARS, STRESSORS, indirect_dir
from utils import Logger, Timer, section, ok, warn, table_str

import numpy as np
import pandas as pd


# ══════════════════════════════════════════════════════════════════════════════
# STEP REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

def _get_step_fns() -> dict:
    """Lazy-import all step run() functions."""

    def _mod(name):
        return importlib.import_module(name)

    return {
        # ── IO + demand (pipeline_inputs.py — was build_io.py + build_demand.py) ──
        "build_io":     lambda stressor, **kw: _mod("pipeline_inputs").run_io(**kw),
        "demand":       lambda stressor, **kw: _mod("pipeline_inputs").run_demand(**kw),

        # ── Coefficients (unchanged) ─────────────────────────────────────────
        "coefficients": lambda stressor, **kw: _mod("build_coefficients").run(stressor=stressor, **kw),

        # ── Indirect footprint (unchanged) ───────────────────────────────────
        "indirect":     lambda stressor, **kw: _mod("indirect").run(stressor=stressor, **kw),

        # ── Post-indirect (postprocess.py — was direct.py + monetise.py + ndp_report.py) ──
        "direct":       lambda stressor, **kw: _mod("postprocess").run(
                            stressor="water", phase="direct", **kw),
        "monetise":     lambda stressor, **kw: _mod("postprocess").run(
                            stressor="depletion", phase="monetise", **kw),
        "ndp_report":   lambda stressor, **kw: _mod("postprocess").run(
                            stressor="depletion", phase="ndp", **kw),

        # ── Outbound (unchanged) ─────────────────────────────────────────────
        "outbound":     lambda stressor, **kw: _mod("outbound").run(stressor=stressor, **kw),

        # ── SDA + MC (decompose.py — now universal across stressors) ─────────
        "sda":          lambda stressor, **kw: _mod("decompose").run(stressor=stressor, **kw),

        # ── Reporting + visualisation (unchanged) ─────────────────────────────
        "report":       lambda stressor, **kw: _mod("compare").run(
                            mode="combined" if stressor == "combined" else stressor, **kw),
        "visualise":    lambda stressor, **kw: _mod("visualise").run(stressor=stressor, **kw),

        # ── Validate (built-in — was validate_outputs.py) ────────────────────
        "validate":     lambda stressor, **kw: _run_validate(stressor=stressor),
    }


# ── Step dependencies ─────────────────────────────────────────────────────────

DEPS: dict[str, list[str]] = {
    "build_io":     [],
    "demand":       ["build_io"],
    "coefficients": ["build_io"],
    "indirect":     ["build_io", "demand", "coefficients"],
    "direct":       ["demand"],
    "outbound":     ["indirect"],
    "sda":          ["indirect"],
    "monetise":     ["indirect"],
    "ndp_report":   ["monetise"],
    "report":       ["indirect", "direct"],
    "visualise":    ["indirect", "direct", "report"],
    "validate":     ["indirect"],
}

# ── Step descriptions ─────────────────────────────────────────────────────────

STEP_DESCS: dict[str, str] = {
    "build_io":     "Build IO tables from SUT  (pipeline_inputs.py)",
    "demand":       "Tourism demand vectors  (pipeline_inputs.py)",
    "coefficients": "EXIOBASE extract + concordance  (build_coefficients.py)",
    "indirect":     "Indirect footprint C·L·Y  (indirect.py)",
    "direct":       "Direct operational footprint  (postprocess.py)",
    "outbound":     "Outbound footprint + net balance  (outbound.py)",
    "sda":          "SDA + Monte Carlo [universal stressor]  (decompose.py)",
    "monetise":     "Monetise depletion → ₹ crore  (postprocess.py)",
    "ndp_report":   "NDP = GDP − CFC − Depletion  (postprocess.py)",
    "report":       "Cross-year report + Markdown  (compare.py)",
    "visualise":    "All chart generation  (visualise.py)",
    "validate":     "Sanity checks on all outputs  (built-in)",
}

WATER_STEPS  = ["build_io", "demand", "coefficients", "indirect",
                "direct", "outbound", "sda", "report", "visualise", "validate"]
ENERGY_STEPS = ["build_io", "demand", "coefficients", "indirect",
                "outbound", "sda", "report", "visualise", "validate"]
NDP_STEPS    = ["build_io", "demand", "coefficients", "indirect",
                "monetise", "ndp_report"]
ALL_STEPS    = list(dict.fromkeys(WATER_STEPS + ENERGY_STEPS + NDP_STEPS))

PIPELINE = ALL_STEPS   # canonical order for interactive menu


# ══════════════════════════════════════════════════════════════════════════════
# BUILT-IN VALIDATION  (was validate_outputs.py)
# ══════════════════════════════════════════════════════════════════════════════

_SEP      = "─" * 70
_failures: list[str] = []
_warnings: list[str] = []
_FY_MAP   = {"2015": "2015-16", "2019": "2019-20", "2022": "2021-22"}


def _safe(path) -> pd.DataFrame:
    try:
        p = Path(path)
        return pd.read_csv(p) if p.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _vok(label: str):
    print(f"  ✓ PASS  {label}")


def _vfail(label: str, detail: str = ""):
    msg = f"{label}: {detail}" if detail else label
    print(f"  ✗ FAIL  {msg}")
    _failures.append(msg)


def _vwarn(label: str, detail: str = ""):
    msg = f"{label}: {detail}" if detail else label
    print(f"  ⚠ WARN  {msg}")
    _warnings.append(msg)


def _check_range(val: float, lo: float, hi: float, label: str):
    if lo <= val <= hi:
        _vok(f"{label}  ({val:.4f} in [{lo}, {hi}])")
    else:
        _vfail(label, f"value {val:.4f} outside [{lo}, {hi}]")


def _check_approx(a: float, b: float, tol_pct: float, label: str):
    if b == 0:
        _vwarn(label, "denominator is zero"); return
    pct = 100 * abs(a - b) / abs(b)
    if pct <= tol_pct:
        _vok(f"{label}  ({pct:.3f}% ≤ {tol_pct}%)")
    else:
        _vfail(label, f"{a:,.0f} vs {b:,.0f} — diff {pct:.2f}% exceeds {tol_pct}%")


def _check_order(a: float, b: float, label: str, desc: str = "a < b"):
    if a < b:
        _vok(f"{label}  ({desc}: {a:.4f} < {b:.4f})")
    else:
        _vfail(label, f"ordering violated ({desc}): {a:.4f} >= {b:.4f}")


def _get_sensitivity_vals(sens_df: pd.DataFrame, val_col: str
                          ) -> tuple[float | None, float | None, float | None]:
    """Extract LOW/BASE/HIGH values from a sensitivity DataFrame."""
    if sens_df.empty or "Scenario" not in sens_df.columns or val_col not in sens_df.columns:
        return None, None, None
    def _v(sc):
        r = sens_df[sens_df["Scenario"] == sc]
        return float(r[val_col].iloc[0]) if not r.empty else None
    return _v("LOW"), _v("BASE"), _v("HIGH")


# ── Universal per-year + per-stressor checks ──────────────────────────────────

def check_stressor_year(stressor: str, year: str):
    """
    Universal per-year integrity checks for any stressor.
    Water-specific checks (scarce/blue, green split, tourist intensity)
    are guarded by `if stressor == "water"`.
    """
    print(f"\n{_SEP}\n  [{stressor.upper()}] Year: {year}\n{_SEP}")

    ind_dir  = indirect_dir(stressor)
    cat_df   = _safe(ind_dir / f"indirect_{stressor}_{year}_by_category.csv")
    sens_df  = _safe(ind_dir / f"indirect_{stressor}_{year}_sensitivity.csv")
    split_df = _safe(ind_dir / f"indirect_{stressor}_{year}_split.csv")

    # Choose the primary value column based on stressor
    val_cols = {
        "water":     "Total_Water_m3",
        "energy":    "Final_Primary_MJ",
        "depletion": "Total_Depletion_t",
        "emissions": "Total_kgCO2e",
    }
    sens_val_cols = {
        "water":     "Total_TWF_m3",
        "energy":    "Total_MJ",
        "depletion": "Total_t",
        "emissions": "Total_kgCO2e",
    }
    primary_col  = val_cols.get(stressor, "Total_Water_m3")
    sens_val_col = sens_val_cols.get(stressor, "Total_TWF_m3")

    # IO balance from summary CSV — universal (same IO table for all stressors)
    io_sum = _safe(DIRS.get("io", Path("__none__")) / "io_summary_all_years.csv")
    bal_df = (io_sum[io_sum["year"].astype(str) == _FY_MAP.get(year, year)].copy()
              if not io_sum.empty and "year" in io_sum.columns else pd.DataFrame())

    # [U1] Total footprint > 0
    if not cat_df.empty and primary_col in cat_df.columns:
        total = float(cat_df[primary_col].sum())
        if total > 0:
            _vok(f"[U1] {stressor} footprint > 0 ({year}): {total:,.0f}")
        else:
            _vfail(f"[U1] {stressor} footprint ({year})", "total is zero or negative")
    else:
        _vwarn(f"[U1] {stressor} footprint ({year})", f"{primary_col} missing")

    # [U2] Sensitivity ordering LOW < BASE < HIGH
    lo, bs, hi = _get_sensitivity_vals(sens_df, sens_val_col)
    if lo is not None and bs is not None and hi is not None:
        if lo < bs < hi:
            _vok(f"[U2] Sensitivity ordering LOW<BASE<HIGH ({year})")
        else:
            _vfail(f"[U2] Sensitivity ordering ({year})",
                   f"LOW={lo:.4f} BASE={bs:.4f} HIGH={hi:.4f} — violated")
    else:
        _vwarn(f"[U2] Sensitivity ({year})", f"LOW/BASE/HIGH rows not found in {sens_val_col}")

    # [U3] IO balance error < 1%
    if not bal_df.empty and "balance_error_pct" in bal_df.columns:
        err = float(bal_df["balance_error_pct"].iloc[0])
        if err < 1.0:
            _vok(f"[U3] IO balance error ({year}): {err:.4f}% < 1.0%")
        else:
            _vfail(f"[U3] IO balance error ({year})", f"{err:.4f}% ≥ 1.0% — check SUT scaling")
    else:
        _vwarn(f"[U3] IO balance ({year})", "io_summary_all_years.csv missing or year not found")

    # ── Water-specific checks ─────────────────────────────────────────────────
    if stressor == "water":
        # Load intensity file for tourist L/day checks
        int_df   = _safe(DIRS["comparison"] / "twf_per_tourist_intensity.csv")
        origin_df = _safe(ind_dir / f"indirect_water_{year}_origin.csv")

        indirect_m3 = cat_df["Total_Water_m3"].sum() if "Total_Water_m3" in cat_df.columns else None
        scarce_m3   = cat_df["Scarce_m3"].sum()       if "Scarce_m3"      in cat_df.columns else None

        # [W1] Scarce/Blue ratio
        if indirect_m3 and scarce_m3 and indirect_m3 > 0:
            _check_range(scarce_m3 / indirect_m3, 0.30, 0.95, f"[W1] Scarce/Blue ratio ({year})")
        else:
            _vwarn(f"[W1] Scarce/Blue ratio ({year})", "indirect TWF or Scarce_m3 missing")

        # [W2] Inbound > domestic tourist-day intensity
        yr_row = (int_df[int_df["Year"].astype(str) == year].iloc[0]
                  if not int_df.empty and "Year" in int_df.columns
                  and not int_df[int_df["Year"].astype(str) == year].empty else None)
        if yr_row is not None:
            inb_lpd = float(yr_row.get("L_per_inb_tourist_day", 0))
            dom_lpd = float(yr_row.get("L_per_dom_tourist_day", 0))
            if inb_lpd > 0 and dom_lpd > 0:
                _check_order(dom_lpd, inb_lpd, f"[W2] Inbound > domestic intensity ({year})", "dom < inb")
                _check_range(inb_lpd / dom_lpd, 2, 30, f"[W3] Inbound/domestic L/day ratio ({year})")
            else:
                _vwarn(f"[W2,W3] Intensity ({year})", "L_per_inb/dom_tourist_day missing or zero")
        else:
            _vwarn(f"[W2,W3] Intensity ({year})", "twf_per_tourist_intensity.csv missing")

        # [W4] Green/Blue ratio
        if not origin_df.empty and "Green_Water_m3" in origin_df.columns and "Water_m3" in origin_df.columns:
            tot_blue  = origin_df["Water_m3"].sum()
            tot_green = origin_df["Green_Water_m3"].sum()
            if tot_blue > 0:
                _check_range(tot_green / tot_blue, 0, 10, f"[W4] Green/Blue ratio ({year})")
            else:
                _vwarn(f"[W4] Green/Blue ratio ({year})", "blue TWF is zero")

        # [W5] Green split conservation
        if not split_df.empty and "Green_m3" in split_df.columns:
            inb_g = split_df[split_df["Type"] == "Inbound"]["Green_m3"]
            dom_g = split_df[split_df["Type"] == "Domestic"]["Green_m3"]
            if not inb_g.empty and not dom_g.empty:
                split_green = float(inb_g.iloc[0]) + float(dom_g.iloc[0])
                agg_green   = float(cat_df["Green_Water_m3"].sum()) if "Green_Water_m3" in cat_df.columns else 0.0
                if agg_green > 0:
                    _check_approx(split_green, agg_green, 0.5,
                                  f"[W5] Green split conservation inb+dom≈aggregate ({year})")

        # [W6] YoY intensity change
        if not int_df.empty and "Year" in int_df.columns and "Intensity_m3_per_crore" in int_df.columns:
            years_sorted = sorted(STUDY_YEARS)
            idx = years_sorted.index(year) if year in years_sorted else -1
            if idx > 0:
                prev_yr = years_sorted[idx - 1]
                r0 = int_df[int_df["Year"].astype(str) == prev_yr]
                r1 = int_df[int_df["Year"].astype(str) == year]
                if not r0.empty and not r1.empty:
                    i0 = float(r0.iloc[0]["Intensity_m3_per_crore"])
                    i1 = float(r1.iloc[0]["Intensity_m3_per_crore"])
                    if i0 > 0:
                        pct_chg = 100 * (i1 - i0) / i0
                        if -60 <= pct_chg <= 30:
                            _vok(f"[W6] Intensity YoY change ({prev_yr}→{year}): {pct_chg:+.1f}%")
                        else:
                            _vwarn(f"[W6] Intensity YoY change ({prev_yr}→{year})",
                                   f"{pct_chg:+.1f}% outside expected [-60%, +30%]")


def check_ndp():
    """Sanity checks on NDP pipeline outputs (postprocess.py monetise + ndp phases)."""
    print(f"\n{_SEP}\n  NDP pipeline checks\n{_SEP}")

    ndp_dir = DIRS.get("ndp", Path("3-final-results/ndp"))
    mon_dir = DIRS.get("monetary_depletion", Path("3-final-results/monetary-depletion"))

    ndp_df = _safe(ndp_dir / "ndp_all_years.csv")
    mon_df = _safe(mon_dir / "monetary_depletion_all_years.csv")

    if ndp_df.empty:
        _vwarn("[NDP-1] ndp_all_years.csv missing", "run ndp_report step first"); return
    if mon_df.empty:
        _vwarn("[NDP-2] monetary_depletion_all_years.csv missing", "run monetise step first"); return

    for _, row in ndp_df.iterrows():
        yr  = str(row.get("year", "?"))
        ndp = float(row.get("ndp_crore", 0))
        gdp = float(row.get("gdp_crore", 0))
        dep_pct = float(row.get("depletion_pct_of_gdp", 0))
        cfc_pct = float(row.get("cfc_pct_of_gdp", 0))

        if ndp > 0:
            _vok(f"[NDP-1] NDP positive ({yr}): ₹{ndp:,.0f} cr")
        else:
            _vfail(f"[NDP-1] NDP non-positive ({yr})", f"₹{ndp:,.0f} cr")

        if gdp > 0 and 0 < ndp < gdp:
            _vok(f"[NDP-2] NDP < GDP ({yr}): {100*ndp/gdp:.2f}% of GDP")
        else:
            _vfail(f"[NDP-2] NDP not in (0, GDP) ({yr})")

        if 0.01 <= dep_pct <= 5.0:
            _vok(f"[NDP-3] Depletion % of GDP plausible ({yr}): {dep_pct:.3f}%")
        else:
            _vwarn(f"[NDP-3] Depletion % of GDP unusual ({yr})",
                   f"{dep_pct:.3f}% — expected 0.01%–5.0%")

        if 10.0 <= cfc_pct <= 25.0:
            _vok(f"[NDP-4] CFC % of GDP in range ({yr}): {cfc_pct:.1f}%")
        else:
            _vwarn(f"[NDP-4] CFC % of GDP outside range ({yr})",
                   f"{cfc_pct:.1f}% — expected 10%–25%")

    if "monetary_depletion_crore" in mon_df.columns:
        neg = (mon_df["monetary_depletion_crore"] <= 0).sum()
        if neg == 0:
            _vok("[NDP-5] All monetary depletion values > 0")
        else:
            _vfail("[NDP-5] Zero or negative monetary depletion", f"{neg} year(s)")

    if len(ndp_df) >= 2 and "ndp_pct_of_gdp" in ndp_df.columns:
        ratios    = ndp_df["ndp_pct_of_gdp"].tolist()
        max_swing = max(abs(ratios[i] - ratios[i-1]) for i in range(1, len(ratios)))
        if max_swing <= 15.0:
            _vok(f"[NDP-6] NDP/GDP ratio stable — max swing {max_swing:.2f}pp")
        else:
            _vwarn("[NDP-6] Large NDP/GDP swing between years",
                   f"{max_swing:.2f}pp — review unit rents or depletion coefficients")


def check_sda(stressor: str = "water"):
    """SDA cross-period checks for any stressor."""
    print(f"\n{_SEP}\n  SDA cross-period checks [{stressor}]\n{_SEP}")

    from config import DIRS as _DIRS
    if stressor == "water":
        sda_file = _DIRS["sda"] / "sda_summary_all_periods.csv"
    else:
        sda_file = _DIRS.get(f"sda_{stressor}", _DIRS["sda"]) / f"sda_{stressor}_summary_all_periods.csv"

    sda_all = _safe(sda_file)
    if sda_all.empty:
        _vwarn(f"[SDA-1] SDA checks [{stressor}]", f"{sda_file.name} missing"); return

    for _, row in sda_all.iterrows():
        period  = str(row.get("Period", "?"))
        method  = str(row.get("SDA_Method", "unknown"))
        dtf     = float(row.get("dTWF_m3", 0))
        res_pct = abs(float(row.get("Residual_pct", 0)))

        if method == "six_polar":
            if res_pct < 0.1:
                _vok(f"[SDA-1] Residual ({period}): {res_pct:.4f}% — six-polar ✓")
            else:
                _vfail(f"[SDA-1] Residual ({period})",
                       f"{res_pct:.4f}% ≥ 0.1% for six-polar — numerical error")
        else:
            if res_pct < 8.0:
                _vok(f"[SDA-1] Residual ({period}): {res_pct:.2f}% [{method}] — within expected")
            else:
                _vwarn(f"[SDA-1] Residual ({period})", f"{res_pct:.2f}% ≥ 8.0%")

        effects_sum = sum(float(row.get(f"{e}_effect_m3", 0)) for e in ("W", "L", "Y"))
        if abs(dtf) > 1e6:
            _check_approx(effects_sum, dtf, 0.5, f"[SDA-2] W+L+Y≈ΔTWF ({period})")
        else:
            _vwarn(f"[SDA-2] ({period})", f"ΔTWF={dtf:.0f} too small to test")


def _run_validate(stressor: str = "water"):
    """
    Run all validation checks.
    Called by the 'validate' step in the registry.
    Can also be invoked standalone via --validate-only.
    """
    # Reset accumulators (important when run multiple times in same process)
    global _failures, _warnings
    _failures, _warnings = [], []

    print(f"\n{'═'*70}")
    print(f"  PIPELINE VALIDATION  [{stressor.upper()}]")
    print(f"{'═'*70}")

    for yr in STUDY_YEARS:
        check_stressor_year(stressor, yr)

    check_sda(stressor)

    if stressor == "depletion":
        check_ndp()

    print(f"\n{_SEP}")
    print(f"  SUMMARY: {len(_failures)} failure(s), {len(_warnings)} warning(s)")
    if _failures:
        print("\n  FAILURES:")
        for f in _failures:
            print(f"    ✗ {f}")
    if _warnings:
        print("\n  WARNINGS:")
        for w in _warnings:
            print(f"    ⚠ {w}")
    print(_SEP)

    if _failures:
        raise RuntimeError(
            f"validate: {len(_failures)} check(s) failed — see output above"
        )


# ══════════════════════════════════════════════════════════════════════════════
# DEPENDENCY CHECKER
# ══════════════════════════════════════════════════════════════════════════════

def check_deps(step: str, completed: set[str], ignore: bool = False, stressor: str | None = None) -> list[str]:
    """Return list of unmet dependencies for `step`.

    For non-water stressors we allow reporting/visualisation to run without the
    activity-based `direct` step (which is currently only implemented for
    `water`). This function therefore drops the `direct` dependency for
    `report` and `visualise` when `stressor != 'water'`.
    """
    if ignore:
        return []

    reqs = list(DEPS.get(step, []))
    # Allow report/visualise to run without `direct` for non-water stressors.
    if stressor is not None and stressor != "water" and step in ("report", "visualise"):
        reqs = [r for r in reqs if r != "direct"]

    return [d for d in reqs if d not in completed]


# ══════════════════════════════════════════════════════════════════════════════
# INTERACTIVE MENU
# ══════════════════════════════════════════════════════════════════════════════

def interactive_menu() -> tuple[list[str], str]:
    """Display numbered step menu. Returns (steps_to_run, stressor)."""
    bar = "=" * 65
    while True:
        print(f"\n{bar}")
        print("  India Tourism Footprint — Pipeline")
        print(bar)
        print(f"  {'#':<4}  {'Step':<22}  Description")
        print(f"  {'─'*4}  {'─'*22}  {'─'*34}")
        for i, key in enumerate(PIPELINE, 1):
            deps = DEPS.get(key, [])
            dep_note = f"  [needs: {', '.join(deps)}]" if deps else ""
            print(f"  {i:<4}  {key:<22}  {STEP_DESCS.get(key, '')}{dep_note}")

        print()
        print("  Stressor presets:  W=water  E=energy  N=NDP  A=all")
        print("  Or enter step numbers (e.g. 1 2 3)  |  Q=quit")
        print(bar)

        raw = input("  Your choice: ").strip().upper()
        if raw in ("Q", ""):
            return [], "water"
        if raw == "W":
            return WATER_STEPS[:], "water"
        if raw == "E":
            return ENERGY_STEPS[:], "energy"
        if raw == "N":
            return NDP_STEPS[:], "depletion"
        if raw == "A":
            return ALL_STEPS[:], "combined"

        tokens   = raw.replace(",", " ").split()
        selected: list[str] = []
        invalid:  list[str] = []
        for tok in tokens:
            if tok.isdigit():
                idx = int(tok)
                if 1 <= idx <= len(PIPELINE):
                    selected.append(PIPELINE[idx - 1])
                else:
                    invalid.append(tok)
            elif tok.lower() in DEPS:
                selected.append(tok.lower())
            else:
                invalid.append(tok)

        if invalid:
            print(f"\n  ⚠  Unknown input(s): {', '.join(invalid)}")
            continue
        if not selected:
            print("\n  ⚠  Nothing selected — try again.")
            continue

        stressor = _ask_stressor()
        return selected, stressor


def _ask_stressor() -> str:
    print("\n  Stressor:  1=water  2=energy  3=depletion")
    raw = input("  Choice [1]: ").strip()
    return {"1": "water", "2": "energy", "3": "depletion",
            "water": "water", "energy": "energy", "depletion": "depletion"}.get(raw, "water")


# ══════════════════════════════════════════════════════════════════════════════
# RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def run_pipeline(steps: list[str], stressor: str, log: Logger,
                 ignore_deps: bool = False) -> dict[str, str]:
    """Run a list of steps in order. Returns {step: 'OK'|'SKIP'|'FAIL'}."""
    fns       = _get_step_fns()
    completed: set[str]       = set()
    results:   dict[str, str] = {}
    timing:    dict[str, float] = {}

    for step in steps:
        missing = check_deps(step, completed, ignore=ignore_deps, stressor=stressor)
        if missing:
            warn(f"Skipping '{step}' — unfulfilled deps: {missing}", log)
            results[step] = "SKIP"
            continue

        if step not in fns:
            warn(f"Unknown step '{step}'", log)
            results[step] = "SKIP"
            continue

        log.section(f"STEP: {step.upper()}  [{stressor}]")
        t0 = time.time()
        try:
            fns[step](stressor)
            elapsed = time.time() - t0
            ok(f"Step '{step}' completed in {elapsed:.1f}s", log)
            results[step] = "OK"
            completed.add(step)
            timing[step]  = elapsed
        except Exception as exc:
            elapsed = time.time() - t0
            log.fail(f"Step '{step}' FAILED after {elapsed:.1f}s: {exc}")
            log._log(traceback.format_exc())
            results[step] = "FAIL"
            timing[step]  = elapsed

    log.section("PIPELINE SUMMARY")
    log.table(
        ["Step", "Status", "Time (s)"],
        [[s, results.get(s, "—"), f"{timing.get(s, 0):.1f}"] for s in steps],
    )
    n_ok   = sum(1 for v in results.values() if v == "OK")
    n_fail = sum(1 for v in results.values() if v == "FAIL")
    n_skip = sum(1 for v in results.values() if v == "SKIP")
    log.info(f"OK: {n_ok}  |  FAIL: {n_fail}  |  SKIP: {n_skip}")
    return results


def _run_combined(log: Logger, ignore_deps: bool = False):
    ok("Running WATER stressor steps...", log)
    run_pipeline(WATER_STEPS,  "water",     log, ignore_deps)
    ok("Running ENERGY stressor steps...", log)
    run_pipeline(ENERGY_STEPS, "energy",    log, ignore_deps)
    ok("Running NDP depletion steps...", log)
    run_pipeline(NDP_STEPS,    "depletion", log, ignore_deps)
    ok("Running combined report...", log)
    try:
        compare = importlib.import_module("compare")
        compare.run(mode="combined")
    except Exception as exc:
        log.fail(f"Combined report failed: {exc}")
        log._log(traceback.format_exc())


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def _parse_args():
    p = argparse.ArgumentParser(
        description="India Tourism Water + Energy + NDP Footprint Pipeline",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py                             # interactive menu\n"
            "  python main.py --water                     # full water pipeline\n"
            "  python main.py --energy                    # full energy pipeline\n"
            "  python main.py --ndp                       # NDP depletion pipeline\n"
            "  python main.py --all                       # all stressors + combined report\n"
            "  python main.py --steps build_io demand coefficients\n"
            "  python main.py --stressor energy --steps indirect sda\n"
            "  python main.py --validate-only             # sanity checks only\n"
            "  python main.py --list-steps\n"
        ),
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--water",         action="store_true", help="Run water pipeline")
    mode.add_argument("--energy",        action="store_true", help="Run energy pipeline")
    mode.add_argument("--ndp",           action="store_true", help="Run NDP depletion pipeline")
    mode.add_argument("--all",           action="store_true", help="Run all stressors + combined")
    mode.add_argument("--validate-only", action="store_true", help="Run validation only, no pipeline")

    p.add_argument("--stressor", choices=list(STRESSORS) + ["combined"],
                   default=None, help="Override stressor")
    p.add_argument("--steps", nargs="+", default=None,
                   choices=list(_get_step_fns()), metavar="STEP",
                   help="Run specific steps only")
    p.add_argument("--list-steps", action="store_true",
                   help="Print all steps and exit")
    p.add_argument("--ignore-deps", action="store_true",
                   help="Skip dependency checks")
    p.add_argument("--years", nargs="+", default=STUDY_YEARS,
                   help=f"Study years (default: {STUDY_YEARS})")
    return p.parse_args()


def main():
    args = _parse_args()

    if args.list_steps:
        print("\n  Steps and dependencies:")
        for key in PIPELINE:
            deps    = DEPS.get(key, [])
            dep_str = f"  [needs: {', '.join(deps)}]" if deps else "  [no deps]"
            print(f"    {key:<22}  {STEP_DESCS.get(key, '')}{dep_str}")
        print(f"\n  Order: {' → '.join(PIPELINE)}")
        sys.exit(0)

    # ── validate-only mode ────────────────────────────────────────────────────
    if args.validate_only:
        stressor = args.stressor or "water"
        try:
            _run_validate(stressor=stressor)
        except RuntimeError as e:
            print(f"\n  {e}")
            sys.exit(1)
        sys.exit(0)

    # ── Determine steps + stressor ────────────────────────────────────────────
    interactive = False
    if args.all:
        stressor, steps = "combined", ALL_STEPS[:]
    elif args.water:
        stressor, steps = "water",     WATER_STEPS[:]
    elif args.energy:
        stressor, steps = "energy",    ENERGY_STEPS[:]
    elif args.ndp:
        stressor, steps = "depletion", NDP_STEPS[:]
    elif args.stressor:
        stressor = args.stressor
        steps    = args.steps or (
            WATER_STEPS   if stressor == "water"     else
            ENERGY_STEPS  if stressor == "energy"    else
            NDP_STEPS     if stressor == "depletion" else
            ALL_STEPS
        )
    elif args.steps:
        stressor = "water"
        steps    = args.steps
    else:
        interactive = True
        steps, stressor = interactive_menu()
        if not steps:
            print("  Nothing to run. Exiting.")
            sys.exit(0)

    # ── Run ───────────────────────────────────────────────────────────────────
    DIRS["logs"].mkdir(parents=True, exist_ok=True)
    with Logger("pipeline", DIRS["logs"]) as log:
        t = Timer()
        log.section(f"INDIA TOURISM FOOTPRINT PIPELINE  [{stressor.upper()}]")
        log.info(f"Steps    : {' → '.join(steps)}")
        log.info(f"Stressor : {stressor}")
        log.info(f"Years    : {args.years if not interactive else STUDY_YEARS}")
        if args.ignore_deps:
            log.info("Deps     : checks DISABLED (--ignore-deps)")

        if stressor == "combined":
            _run_combined(log, ignore_deps=args.ignore_deps)
        else:
            run_pipeline(steps, stressor, log, ignore_deps=args.ignore_deps)

        log.ok(f"Pipeline complete in {t.elapsed()}")


if __name__ == "__main__":
    main()
