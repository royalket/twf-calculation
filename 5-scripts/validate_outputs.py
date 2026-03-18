"""
validate_outputs.py — Post-pipeline integrity checker
======================================================
Runs sanity assertions on the pipeline's final CSVs.
Call after a full pipeline run to catch numerical errors before report generation.

Usage:
    python validate_outputs.py            # all years
    python validate_outputs.py 2022       # single year

Exit codes:
    0 — all assertions passed
    1 — one or more assertions failed
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import DIRS, STUDY_YEARS

SEP = "─" * 70

_failures: list[str] = []
_warnings: list[str] = []

_FY_MAP = {"2015": "2015-16", "2019": "2019-20", "2022": "2021-22"}


# ── I/O helpers ───────────────────────────────────────────────────────────────

def _safe(path) -> pd.DataFrame:
    try:
        p = Path(path)
        return pd.read_csv(p) if p.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def _ok(label: str):   print(f"  ✓ PASS  {label}")
def _fail(label: str, detail: str = ""):
    msg = f"{label}: {detail}" if detail else label
    print(f"  ✗ FAIL  {msg}")
    _failures.append(msg)
def _warn(label: str, detail: str = ""):
    msg = f"{label}: {detail}" if detail else label
    print(f"  ⚠ WARN  {msg}")
    _warnings.append(msg)


# ── Generic assertion helpers ─────────────────────────────────────────────────

def _check_range(val: float, lo: float, hi: float, label: str):
    if lo <= val <= hi:
        _ok(f"{label}  ({val:.4f} in [{lo}, {hi}])")
    else:
        _fail(label, f"value {val:.4f} outside [{lo}, {hi}]")

def _check_approx(a: float, b: float, tol_pct: float, label: str):
    if b == 0:
        _warn(label, "denominator is zero"); return
    pct = 100 * abs(a - b) / abs(b)
    if pct <= tol_pct:
        _ok(f"{label}  ({pct:.3f}% ≤ {tol_pct}%)")
    else:
        _fail(label, f"{a:,.0f} vs {b:,.0f} — diff {pct:.2f}% exceeds {tol_pct}%")

def _check_order(a: float, b: float, label: str, desc: str = "a < b"):
    if a < b:
        _ok(f"{label}  ({desc}: {a:.4f} < {b:.4f})")
    else:
        _fail(label, f"ordering violated ({desc}): {a:.4f} >= {b:.4f}")

def _get_scenario_vals(sens_df: pd.DataFrame) -> tuple[float | None, float | None, float | None]:
    """Extract LOW/BASE/HIGH Total_TWF_m3 values from sensitivity DataFrame."""
    if sens_df.empty or "Scenario" not in sens_df.columns or "Total_TWF_m3" not in sens_df.columns:
        return None, None, None
    def _v(sc):
        r = sens_df[sens_df["Scenario"] == sc]
        return float(r["Total_TWF_m3"].iloc[0]) if not r.empty else None
    return _v("LOW"), _v("BASE"), _v("HIGH")


# ── Per-year checks ───────────────────────────────────────────────────────────

def check_year(year: str):
    print(f"\n{SEP}\n  Year: {year}\n{SEP}")

    cat_df   = _safe(DIRS["indirect"] / f"indirect_water_{year}_by_category.csv")
    sens_df  = _safe(DIRS["indirect"] / f"indirect_water_{year}_sensitivity.csv")
    split_df = _safe(DIRS["indirect"] / f"indirect_water_{year}_split.csv")
    int_df   = _safe(DIRS["comparison"] / "twf_per_tourist_intensity.csv")
    origin_df= _safe(DIRS["indirect"] / f"indirect_water_{year}_origin.csv")

    # IO balance from summary CSV
    io_sum = _safe(DIRS.get("io", Path("__none__")) / "io_summary_all_years.csv")
    bal_df = (io_sum[io_sum["year"].astype(str) == _FY_MAP.get(year, year)].copy()
              if not io_sum.empty and "year" in io_sum.columns else pd.DataFrame())

    indirect_m3 = cat_df["Total_Water_m3"].sum() if "Total_Water_m3" in cat_df.columns else None
    scarce_m3   = cat_df["Scarce_m3"].sum()       if "Scarce_m3"      in cat_df.columns else None

    # [1] Scarce/Blue ratio
    if indirect_m3 and scarce_m3 and indirect_m3 > 0:
        _check_range(scarce_m3 / indirect_m3, 0.30, 0.95, f"[1] Scarce/Blue ratio ({year})")
    else:
        _warn(f"[1] Scarce/Blue ratio ({year})", "indirect TWF or Scarce_m3 missing")

    # [2] Sensitivity ordering LOW < BASE < HIGH
    lo, bs, hi = _get_scenario_vals(sens_df)
    if lo is not None and bs is not None and hi is not None:
        if lo < bs < hi:
            _ok(f"[2] Sensitivity ordering LOW<BASE<HIGH ({year})  "
                f"LOW={lo/1e9:.4f} BASE={bs/1e9:.4f} HIGH={hi/1e9:.4f} bn m³")
        else:
            _fail(f"[2] Sensitivity ordering ({year})",
                  f"LOW={lo/1e9:.4f} BASE={bs/1e9:.4f} HIGH={hi/1e9:.4f} — ordering violated")
    else:
        _warn(f"[2] Sensitivity ({year})", "LOW/BASE/HIGH rows not found")

    # [3] & [4] Intensity checks from twf_per_tourist_intensity.csv
    yr_row = int_df[int_df["Year"].astype(str) == year].iloc[0] \
             if not int_df.empty and "Year" in int_df.columns and \
                not int_df[int_df["Year"].astype(str) == year].empty else None

    if yr_row is not None:
        inb_lpd = float(yr_row.get("L_per_inb_tourist_day", 0))
        dom_lpd = float(yr_row.get("L_per_dom_tourist_day", 0))
        if inb_lpd > 0 and dom_lpd > 0:
            _check_order(dom_lpd, inb_lpd, f"[3] Inbound > domestic intensity ({year})", "dom < inb")
            _check_range(inb_lpd / dom_lpd, 2, 30, f"[4] Inbound/domestic L/day ratio ({year})")
        else:
            _warn(f"[3,4] Intensity ({year})", "L_per_inb/dom_tourist_day missing or zero")
    else:
        _warn(f"[3,4] Intensity ({year})", "twf_per_tourist_intensity.csv missing or year not found")

    # [4b] Green split conservation
    if not split_df.empty and "Green_m3" in split_df.columns:
        inb_g = split_df[split_df["Type"] == "Inbound"]["Green_m3"]
        dom_g = split_df[split_df["Type"] == "Domestic"]["Green_m3"]
        if not inb_g.empty and not dom_g.empty:
            split_green_total = float(inb_g.iloc[0]) + float(dom_g.iloc[0])
            agg_green = float(cat_df["Green_Water_m3"].sum()) \
                        if "Green_Water_m3" in cat_df.columns else 0.0
            if agg_green > 0:
                _check_approx(split_green_total, agg_green, 0.5,
                              f"[4b] Green split conservation inb+dom≈aggregate ({year})")
            else:
                _warn(f"[4b] Green split ({year})", "aggregate Green_Water_m3 is zero or missing")
        else:
            _warn(f"[4b] Green split ({year})", "Green_m3 rows missing in split CSV")
    else:
        _warn(f"[4b] Green split ({year})", "Green_m3 column absent — re-run indirect.py")

    # [5] Green/Blue ratio
    if not origin_df.empty and "Green_Water_m3" in origin_df.columns and "Water_m3" in origin_df.columns:
        tot_blue  = origin_df["Water_m3"].sum()
        tot_green = origin_df["Green_Water_m3"].sum()
        if tot_blue > 0:
            _check_range(tot_green / tot_blue, 0, 10, f"[5] Green/Blue ratio ({year})")
        else:
            _warn(f"[5] Green/Blue ratio ({year})", "blue TWF is zero")
    else:
        _warn(f"[5] Green/Blue ratio ({year})", "Green_Water_m3 absent in origin CSV")

    # [6] Year-on-year intensity change within [-60%, +30%]
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
                        _ok(f"[6] Intensity YoY change ({prev_yr}→{year}): {pct_chg:+.1f}%")
                    else:
                        _warn(f"[6] Intensity YoY change ({prev_yr}→{year})",
                              f"{pct_chg:+.1f}% outside expected [-60%, +30%]")

    # [7] IO balance error < 1.0%
    if not bal_df.empty and "balance_error_pct" in bal_df.columns:
        err = float(bal_df["balance_error_pct"].iloc[0])
        if err < 1.0:
            _ok(f"[7] IO balance error ({year}): {err:.4f}% < 1.0%")
        else:
            _fail(f"[7] IO balance error ({year})", f"{err:.4f}% ≥ 1.0% — check SUT scaling")
    else:
        _warn(f"[7] IO balance error ({year})", "io_summary_all_years.csv missing or year not found")


# ── SDA checks ────────────────────────────────────────────────────────────────

def check_sda():
    print(f"\n{SEP}\n  SDA cross-period checks\n{SEP}")

    sda_dir = DIRS.get("sda", Path("3-final-results/sda"))
    sda_all = _safe(sda_dir / "sda_summary_all_periods.csv")

    if sda_all.empty:
        _warn("[8,9] SDA checks", "sda_summary_all_periods.csv missing")
        return

    for _, row in sda_all.iterrows():
        period   = str(row.get("Period", "?"))
        method   = str(row.get("SDA_Method", "unknown"))
        dtf      = float(row.get("dTWF_m3", 0))
        res_pct  = abs(float(row.get("Residual_pct", 0)))

        # [8] Residual check
        if method == "six_polar":
            if res_pct < 0.1:
                _ok(f"[8] SDA residual ({period}): {res_pct:.4f}% — six-polar ✓")
            else:
                _fail(f"[8] SDA residual ({period})",
                      f"{res_pct:.4f}% ≥ 0.1% for six-polar — numerical error")
        else:
            if res_pct < 8.0:
                _ok(f"[8] SDA residual ({period}): {res_pct:.2f}% [{method}] — within expected")
            else:
                _warn(f"[8] SDA residual ({period})", f"{res_pct:.2f}% ≥ 8.0% for two-polar")

        # [9] W+L+Y ≈ ΔTWF
        effects_sum = sum(float(row.get(f"{e}_effect_m3", 0)) for e in ("W", "L", "Y"))
        if abs(dtf) > 1e6:
            _check_approx(effects_sum, dtf, 0.5, f"[9] SDA effects sum W+L+Y≈ΔTWF ({period})")
        else:
            _warn(f"[9] SDA effects sum ({period})", f"ΔTWF={dtf:.0f} m³ too small to test")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    years = sys.argv[1:] if len(sys.argv) > 1 else STUDY_YEARS

    print(f"\n{'═'*70}\n  validate_outputs.py — India Tourism Water Footprint Pipeline\n{'═'*70}")
    print(f"  Years: {years}")

    for yr in years:
        check_year(yr)
    check_sda()

    print(f"\n{SEP}")
    print(f"  SUMMARY: {len(_failures)} failure(s), {len(_warnings)} warning(s)")
    if _failures:
        print("\n  FAILURES:")
        for f in _failures:
            print(f"    ✗ {f}")
    if _warnings:
        print("\n  WARNINGS:")
        for w in _warnings:
            print(f"    ⚠ {w}")
    print(SEP)
    sys.exit(1 if _failures else 0)


if __name__ == "__main__":
    main()
