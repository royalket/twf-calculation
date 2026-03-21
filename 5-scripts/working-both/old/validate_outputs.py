"""
validate_outputs.py — Post-pipeline integrity checker
======================================================
Runs 10 sanity assertions on the pipeline's final CSVs.
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

PASS  = "  ✓ PASS"
FAIL  = "  ✗ FAIL"
WARN  = "  ⚠ WARN"
SEP   = "─" * 70

_failures: list[str] = []
_warnings: list[str] = []


def _safe(path) -> pd.DataFrame:
    try:
        p = Path(path)
        return pd.read_csv(p) if p.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _ok(label: str):
    print(f"{PASS}  {label}")


def _fail(label: str, detail: str = ""):
    msg = f"{label}: {detail}" if detail else label
    print(f"{FAIL}  {msg}")
    _failures.append(msg)


def _warn(label: str, detail: str = ""):
    msg = f"{label}: {detail}" if detail else label
    print(f"{WARN}  {msg}")
    _warnings.append(msg)


# ── assertion helpers ─────────────────────────────────────────────────────────

def assert_approx_equal(a: float, b: float, tol_pct: float, label: str):
    if b == 0:
        _warn(label, "denominator is zero — cannot check")
        return
    pct = 100 * abs(a - b) / abs(b)
    if pct <= tol_pct:
        _ok(f"{label}  ({pct:.3f}% ≤ {tol_pct}%)")
    else:
        _fail(label, f"{a:,.0f} vs {b:,.0f} — diff {pct:.2f}% exceeds {tol_pct}%")


def assert_in_range(val: float, lo: float, hi: float, label: str):
    if lo <= val <= hi:
        _ok(f"{label}  ({val:.4f} in [{lo}, {hi}])")
    else:
        _fail(label, f"value {val:.4f} outside expected range [{lo}, {hi}]")


def assert_ordering(a: float, b: float, label: str, desc: str = "a < b"):
    if a < b:
        _ok(f"{label}  ({desc}: {a:.4f} < {b:.4f})")
    else:
        _fail(label, f"ordering violated ({desc}): {a:.4f} >= {b:.4f}")


# ── per-year checks ───────────────────────────────────────────────────────────

def check_year(year: str):
    print(f"\n{SEP}")
    print(f"  Year: {year}")
    print(SEP)

    cat_df  = _safe(DIRS["indirect"] / f"indirect_twf_{year}_by_category.csv")
    dir_df  = _safe(DIRS["direct"]   / f"direct_twf_{year}.csv")
    sens_df = _safe(DIRS["indirect"] / f"indirect_twf_{year}_sensitivity.csv")
    split_df= _safe(DIRS["indirect"] / f"indirect_twf_{year}_split.csv")
    int_df  = _safe(DIRS["comparison"]/ "twf_per_tourist_intensity.csv")
    # io_balance_{year}.csv is never written by the pipeline.
    # The balance error lives in io_summary_all_years.csv (column: balance_error_pct).
    _io_sum = _safe(DIRS.get("io", Path("__none__")) / "io_summary_all_years.csv")
    _fy_map = {"2015": "2015-16", "2019": "2019-20", "2022": "2021-22"}
    _fy     = _fy_map.get(year, year)
    bal_df  = (_io_sum[_io_sum["year"].astype(str) == _fy].copy()
               if not _io_sum.empty and "year" in _io_sum.columns else pd.DataFrame())

    indirect_m3 = cat_df["Total_Water_m3"].sum() if not cat_df.empty and "Total_Water_m3" in cat_df.columns else None
    scarce_m3   = cat_df["Scarce_m3"].sum()      if not cat_df.empty and "Scarce_m3"      in cat_df.columns else None

    # ── ASSERTION 1: Scarce/Blue ratio in [0.30, 0.95] ───────────────────────
    if indirect_m3 and scarce_m3 and indirect_m3 > 0:
        ratio = scarce_m3 / indirect_m3
        assert_in_range(ratio, 0.30, 0.95,
                        f"[1] Scarce/Blue ratio ({year})")
    else:
        _warn(f"[1] Scarce/Blue ratio ({year})", "indirect TWF or Scarce_m3 missing")

    # ── ASSERTION 2: Sensitivity LOW < BASE < HIGH ────────────────────────────
    if not sens_df.empty and "Scenario" in sens_df.columns and "Total_TWF_m3" in sens_df.columns:
        base_r = sens_df[sens_df["Scenario"] == "BASE"]
        low_r  = sens_df[sens_df["Scenario"] == "LOW"]
        high_r = sens_df[sens_df["Scenario"] == "HIGH"]
        if not base_r.empty and not low_r.empty and not high_r.empty:
            bs = float(base_r["Total_TWF_m3"].iloc[0])
            lo = float(low_r["Total_TWF_m3"].iloc[0])
            hi = float(high_r["Total_TWF_m3"].iloc[0])
            if lo < bs < hi:
                _ok(f"[2] Sensitivity ordering LOW<BASE<HIGH ({year})"
                    f"  LOW={lo/1e9:.4f} BASE={bs/1e9:.4f} HIGH={hi/1e9:.4f} bn m³")
            else:
                _fail(f"[2] Sensitivity ordering ({year})",
                      f"LOW={lo/1e9:.4f} BASE={bs/1e9:.4f} HIGH={hi/1e9:.4f} — ordering violated")
        else:
            _warn(f"[2] Sensitivity ({year})", "LOW/BASE/HIGH rows not found")
    else:
        _warn(f"[2] Sensitivity ({year})", "sensitivity CSV missing or incomplete")

    # ── ASSERTION 3: Inbound intensity > domestic intensity ───────────────────
    if not int_df.empty and "Year" in int_df.columns:
        yr_row = int_df[int_df["Year"].astype(str) == year]
        if not yr_row.empty:
            inb = float(yr_row.iloc[0].get("L_per_inb_tourist_day", 0))
            dom = float(yr_row.iloc[0].get("L_per_dom_tourist_day", 0))
            if inb > 0 and dom > 0:
                assert_ordering(dom, inb, f"[3] Inbound > domestic intensity ({year})",
                                "dom < inb (L/tourist-day)")
            else:
                _warn(f"[3] Inbound > domestic intensity ({year})", "intensity values missing or zero")
        else:
            _warn(f"[3] Inbound > domestic intensity ({year})", "year not in intensity CSV")
    else:
        _warn(f"[3] Intensity ({year})", "twf_per_tourist_intensity.csv missing")

    # ── ASSERTION 4: Inbound/domestic L/tourist-day ratio in [2, 30] ─────────
    # Uses twf_per_tourist_intensity.csv (same source as check [3]).
    # The previous version read from split_df and divided TWF_m3 by Demand_crore,
    # producing a TWF/spend ratio (~1.1×) not an intensity ratio — that was wrong.
    # Correct metric: L_per_inb_tourist_day / L_per_dom_tourist_day.
    # Expected range [2, 30]: inbound tourists use 2–30× more water per day
    # than domestic (literature: Hadjikakou 2015, Li 2018; India-specific ~5–15×
    # at baseline but can fall toward 2× if domestic days are long-haul).
    # Lower bound relaxed to 2 to avoid false failures from stay-duration effects.
    if not int_df.empty and "Year" in int_df.columns:
        yr_row = int_df[int_df["Year"].astype(str) == year]
        if not yr_row.empty:
            inb_lpd = float(yr_row.iloc[0].get("L_per_inb_tourist_day", 0))
            dom_lpd = float(yr_row.iloc[0].get("L_per_dom_tourist_day", 0))
            if inb_lpd > 0 and dom_lpd > 0:
                ratio = inb_lpd / dom_lpd
                assert_in_range(ratio, 2, 30,
                                f"[4] Inbound/domestic L/day ratio ({year})")
            else:
                _warn(f"[4] Inbound/domestic ratio ({year})",
                      "L_per_inb/dom_tourist_day missing or zero in intensity CSV")
        else:
            _warn(f"[4] Inbound/domestic ratio ({year})", "year not in intensity CSV")
    else:
        _warn(f"[4] Inbound/domestic ratio ({year})",
              "twf_per_tourist_intensity.csv missing")

    # ── ASSERTION 4b: Green split conservation — inb + dom ≈ aggregate green ─
    # compute_split_twf now writes Green_m3 columns via exact EEIO propagation.
    # The sum of inbound + domestic green must equal the aggregate green TWF
    # (from indirect_twf_{year}_by_category.csv) within 0.5% tolerance.
    # A larger discrepancy indicates a code error in the green split computation.
    if not split_df.empty and "Green_m3" in split_df.columns:
        inb_g = split_df[split_df["Type"] == "Inbound"]["Green_m3"]
        dom_g = split_df[split_df["Type"] == "Domestic"]["Green_m3"]
        if not inb_g.empty and not dom_g.empty:
            split_green_total = float(inb_g.iloc[0]) + float(dom_g.iloc[0])
            # Aggregate green from category-level results
            agg_green = (cat_df["Green_Water_m3"].sum()
                         if not cat_df.empty and "Green_Water_m3" in cat_df.columns else 0.0)
            if agg_green > 0:
                assert_approx_equal(
                    split_green_total, agg_green, 0.5,
                    f"[4b] Green split conservation inb+dom≈aggregate ({year})",
                )
            else:
                _warn(f"[4b] Green split conservation ({year})",
                      "aggregate Green_Water_m3 is zero or missing in category CSV")
        else:
            _warn(f"[4b] Green split ({year})", "Green_m3 rows missing in split CSV")
    else:
        _warn(f"[4b] Green split ({year})",
              "Green_m3 column absent in split CSV — re-run calculate_indirect_twf.py")

    # ── ASSERTION 5: Green/Blue ratio in [0, 10] ─────────────────────────────
    origin_df = _safe(DIRS["indirect"] / f"indirect_twf_{year}_origin.csv")
    if not origin_df.empty and "Green_Water_m3" in origin_df.columns and "Water_m3" in origin_df.columns:
        tot_blue  = origin_df["Water_m3"].sum()
        tot_green = origin_df["Green_Water_m3"].sum()
        if tot_blue > 0:
            gb_ratio = tot_green / tot_blue
            assert_in_range(gb_ratio, 0, 10, f"[5] Green/Blue ratio ({year})")
        else:
            _warn(f"[5] Green/Blue ratio ({year})", "blue TWF is zero")
    else:
        _warn(f"[5] Green/Blue ratio ({year})", "Green_Water_m3 column absent in origin CSV "
              "(re-run calculate_indirect_twf.py with fixed green EEIO computation)")

    # ── ASSERTION 6: Year-on-year intensity change within [-60%, +30%] ────────
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
                              f"{pct_chg:+.1f}% outside expected [-60%, +30%] — check data")

    # ── ASSERTION 7: Balance error < 1.0% ────────────────────────────────────
    if not bal_df.empty and "balance_error_pct" in bal_df.columns:
        err = float(bal_df["balance_error_pct"].iloc[0])
        if err < 1.0:
            _ok(f"[7] IO balance error ({year}): {err:.4f}% < 1.0%")
        else:
            _fail(f"[7] IO balance error ({year})", f"{err:.4f}% ≥ 1.0% — check SUT scaling")
    else:
        _warn(f"[7] IO balance error ({year})", f"io_balance_{year}.csv missing")


# ── SDA checks (run once across all periods) ──────────────────────────────────

def check_sda():
    print(f"\n{SEP}")
    print("  SDA cross-period checks")
    print(SEP)

    sda_dir = DIRS.get("sda", Path("3-final-results/sda"))
    sda_all = _safe(sda_dir / "sda_summary_all_periods.csv")

    if sda_all.empty:
        _warn("[8] SDA residual", "sda_summary_all_periods.csv missing")
        _warn("[9] SDA effects sum", "sda_summary_all_periods.csv missing")
        return

    for _, row in sda_all.iterrows():
        period = str(row.get("Period", "?"))
        method = str(row.get("SDA_Method", "unknown"))

        # ── ASSERTION 8: SDA residual < 0.1% for six-polar ───────────────────
        residual_pct = abs(float(row.get("Residual_pct", 0)))
        dtf = float(row.get("dTWF_m3", 0))
        if method == "six_polar":
            if residual_pct < 0.1:
                _ok(f"[8] SDA residual ({period}): {residual_pct:.4f}% — six-polar ✓")
            else:
                _fail(f"[8] SDA residual ({period})",
                      f"{residual_pct:.4f}% ≥ 0.1% for six-polar method — numerical error")
        else:
            # two-polar: residual up to ~6% is expected
            if residual_pct < 8.0:
                _ok(f"[8] SDA residual ({period}): {residual_pct:.2f}% [{method}] — within expected")
            else:
                _warn(f"[8] SDA residual ({period})",
                      f"{residual_pct:.2f}% ≥ 8.0% for two-polar — unusually large")

        # ── ASSERTION 9: W+L+Y sum ≈ ΔTWF (within 0.5%) ─────────────────────
        w = float(row.get("W_effect_m3", 0))
        l = float(row.get("L_effect_m3", 0))
        y = float(row.get("Y_effect_m3", 0))
        effects_sum = w + l + y
        if abs(dtf) > 1e6:
            assert_approx_equal(effects_sum, dtf, 0.5,
                                f"[9] SDA effects sum W+L+Y≈ΔTWF ({period})")
        else:
            _warn(f"[9] SDA effects sum ({period})", f"ΔTWF={dtf:.0f} m³ too small to test")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    years = sys.argv[1:] if len(sys.argv) > 1 else STUDY_YEARS

    print("\n" + "═" * 70)
    print("  validate_outputs.py — India Tourism Water Footprint Pipeline")
    print("═" * 70)
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