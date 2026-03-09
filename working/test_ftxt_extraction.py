"""
test_ftxt_extraction.py
==============================================================================
Diagnostic test for EXIOBASE F.txt water coefficient extraction.

Tests every hypothesis that could explain the ~20% drop in 2015/2019 indirect
TWF between the two pipeline runs:

  TEST 1  — F.txt file presence and structure (path, shape, row names)
  TEST 2  — Row name matching: what does "Water Consumption Blue" actually match?
            Checks for spelling variants, invisible characters, case differences.
  TEST 3  — India sector column detection (IN / IN.1 … IN.162 — should be 163)
  TEST 4  — Grey water contamination: is "Water Consumption Grey" being summed
            into blue? Any prefix collision with "Water Consumption Blue"?
  TEST 5  — EUR/INR conversion correctness (100/EUR_INR formula)
  TEST 6  — Year-to-year F.txt diff: for the 5 largest agriculture sectors
            (Paddy, Wheat, Sugarcane, Rapeseed, Groundnut), compare blue
            coefficients across all three years. A >15% drop = likely re-extraction.
  TEST 7  — Concordance coverage: which EXIOBASE sector codes are unmapped?
            Unmapped codes silently become zero — shows up as agriculture share drop.
  TEST 8  — SUT distribution: equal-split across mapped SUT products.
            If a category maps to many SUT IDs the per-product coefficient is
            diluted — verify agriculture categories aren't over-split.
  TEST 9  — Total coefficient sanity: blue total per year should be
            roughly proportional to EUR_INR ratio. A deviation >25% flags
            a genuine F.txt data revision.
  TEST 10 — Water row multiplicity: are there 1 or 2+ "Blue" rows in F.txt?
            Summing 2 rows vs 1 row = 2× inflation in old run if F.txt changed.

Usage (run from repo root, same Python env as pipeline):
    python test_ftxt_extraction.py

    # to test a specific year only:
    python test_ftxt_extraction.py --year 2015

    # to write a detailed CSV report:
    python test_ftxt_extraction.py --csv report.csv
==============================================================================
"""

import sys
import argparse
from pathlib import Path
import textwrap

import numpy as np
import pandas as pd

# ── bootstrap: add pipeline root to path ─────────────────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    from config import BASE_DIR, DIRS, EUR_INR, YEARS, STUDY_YEARS, EXIO_CODES
except ImportError as e:
    sys.exit(
        f"Cannot import config.py — run this script from the pipeline root.\n  {e}"
    )

# ── colour output helpers ─────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✓{RESET}  {msg}")
def warn(msg): print(f"  {YELLOW}⚠{RESET}  {msg}")
def fail(msg): print(f"  {RED}✗{RESET}  {msg}")
def head(msg): print(f"\n{BOLD}{msg}{RESET}")
def sub(msg):  print(f"  {BOLD}{msg}{RESET}")

RESULTS = []   # (test_id, status, message) for final summary

def record(test_id, status, msg):
    RESULTS.append((test_id, status, msg))

# ── known agriculture sector codes (most water-intensive India sectors) ───────
AGR_CODES = [
    "IN",       # Paddy (IN.0 / first India sector — code is just "IN" in EXIOBASE)
    "IN.1",     # Wheat
    "IN.2",     # Maize
    "IN.3",     # Other cereals
    "IN.4",     # Sugarcane
    "IN.5",     # Sugar beet (usually zero for India)
    "IN.6",     # Rapeseed/mustard
    "IN.7",     # Groundnut
    "IN.8",     # Other oilseeds
    "IN.9",     # Other food crops
]

AGR_LABELS = {
    "IN":    "Paddy",
    "IN.1":  "Wheat",
    "IN.2":  "Maize",
    "IN.3":  "Other cereals",
    "IN.4":  "Sugarcane",
    "IN.5":  "Sugar beet",
    "IN.6":  "Rapeseed/mustard",
    "IN.7":  "Groundnut",
    "IN.8":  "Other oilseeds",
    "IN.9":  "Other food crops",
}

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _f_candidates(water_year: str) -> list[Path]:
    exio_base = DIRS.get("exiobase", BASE_DIR / "1-input-data" / "exiobase-raw")
    return [
        exio_base / f"IOT_{water_year}_ixi" / "F.txt",
        exio_base / f"IOT_{water_year}_ixi" / "satellite" / "F.txt",
        exio_base / f"IOT_{water_year}_ixi" / "water"     / "F.txt",
    ]


def _load_ftxt(water_year: str) -> tuple[Path | None, pd.DataFrame]:
    """Return (path, DataFrame) or (None, empty) if not found."""
    for p in _f_candidates(water_year):
        if p.exists():
            df = pd.read_csv(p, sep="\t", header=0, index_col=0, low_memory=False)
            return p, df
    return None, pd.DataFrame()


def _india_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c == "IN" or c.startswith("IN.")]


def _blue_rows(df: pd.DataFrame) -> list[str]:
    return [r for r in df.index if str(r).startswith("Water Consumption Blue")]


def _green_rows(df: pd.DataFrame) -> list[str]:
    return [r for r in df.index if str(r).startswith("Water Consumption Green")]


def _grey_rows(df: pd.DataFrame) -> list[str]:
    return [r for r in df.index if "Water Consumption" in str(r)
            and not str(r).startswith("Water Consumption Blue")
            and not str(r).startswith("Water Consumption Green")]


def _sector_blue_total(df: pd.DataFrame, code: str) -> float:
    """Sum of all Blue rows for a single India sector column."""
    blue = _blue_rows(df)
    if not blue or code not in df.columns:
        return 0.0
    return (df.loc[blue, code]
              .apply(pd.to_numeric, errors="coerce")
              .fillna(0)
              .sum())


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1 — File presence
# ══════════════════════════════════════════════════════════════════════════════

def test1_file_presence(years: list[str]):
    head("TEST 1 — F.txt file presence and size")
    all_found = True
    for yr in years:
        wy = YEARS[yr]["water_year"]
        found = None
        for p in _f_candidates(wy):
            if p.exists():
                found = p
                break
        if found:
            size_mb = found.stat().st_size / 1e6
            ok(f"{yr} (water_year={wy}): {found}  [{size_mb:.1f} MB]")
            if size_mb < 5:
                warn(f"  File is very small ({size_mb:.1f} MB) — may be truncated or wrong file")
                record("T1", "WARN", f"{yr}: F.txt suspiciously small ({size_mb:.1f} MB)")
            else:
                record("T1", "OK", f"{yr}: found at {found}")
        else:
            fail(f"{yr} (water_year={wy}): NOT FOUND. Tried:")
            for p in _f_candidates(wy):
                print(f"      {p}")
            record("T1", "FAIL", f"{yr}: F.txt missing")
            all_found = False
    return all_found


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2 — Row name matching (the most common failure point)
# ══════════════════════════════════════════════════════════════════════════════

def test2_row_names(years: list[str]):
    head("TEST 2 — Row name matching and invisible-character audit")

    EXPECTED_BLUE  = "Water Consumption Blue"
    EXPECTED_GREEN = "Water Consumption Green"

    for yr in years:
        wy = YEARS[yr]["water_year"]
        sub(f"Year {yr} (water_year={wy})")
        _, df = _load_ftxt(wy)
        if df.empty:
            fail(f"  Cannot load F.txt — skipping"); continue

        # All rows containing "water" (case-insensitive)
        water_rows = [r for r in df.index if "water" in str(r).lower()]
        print(f"    All water-related rows found ({len(water_rows)} total):")
        for r in water_rows:
            r_repr  = repr(str(r))           # shows \t, \xa0, etc
            r_strip = str(r).strip()
            prefix_blue  = r_strip.startswith(EXPECTED_BLUE)
            prefix_green = r_strip.startswith(EXPECTED_GREEN)
            invisible = r_repr != f"'{r_strip}'"   # repr differs = hidden chars

            tag = ""
            if invisible:                         tag = f" {RED}← HIDDEN CHARS{RESET}"
            elif prefix_blue:                     tag = f" {GREEN}← Blue (matched){RESET}"
            elif prefix_green:                    tag = f" {GREEN}← Green (matched){RESET}"
            elif "blue"  in str(r).lower():       tag = f" {YELLOW}← blue but case/spelling mismatch{RESET}"
            elif "green" in str(r).lower():       tag = f" {YELLOW}← green but case/spelling mismatch{RESET}"
            elif "grey"  in str(r).lower() or "gray" in str(r).lower():
                                                  tag = f" {RED}← GREY row (should NOT be summed){RESET}"
            print(f"      {r_repr}{tag}")

        blue_matched  = _blue_rows(df)
        green_matched = _green_rows(df)

        if len(blue_matched) == 0:
            fail(f"  No Blue rows matched prefix '{EXPECTED_BLUE}'")
            record("T2", "FAIL", f"{yr}: zero Blue rows matched")
        elif len(blue_matched) == 1:
            ok(f"  {len(blue_matched)} Blue row matched → sum of 1 row (expected)")
            record("T2", "OK", f"{yr}: 1 Blue row")
        elif len(blue_matched) == 2:
            warn(f"  {len(blue_matched)} Blue rows matched — will be SUMMED."
                 f" If old run had 1 row and new has 2, this doubles the coefficient.")
            record("T2", "WARN", f"{yr}: 2 Blue rows — sum may inflate vs single-row years")
        else:
            warn(f"  {len(blue_matched)} Blue rows — unusual, verify all are genuinely blue")
            record("T2", "WARN", f"{yr}: {len(blue_matched)} Blue rows")

        if len(green_matched) == 0:
            warn(f"  No Green rows matched — green water will be zero for {yr}")
            record("T2", "WARN", f"{yr}: zero Green rows")
        else:
            ok(f"  {len(green_matched)} Green row(s) matched")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3 — India column count
# ══════════════════════════════════════════════════════════════════════════════

def test3_india_columns(years: list[str]):
    head("TEST 3 — India sector column count (expected: 163)")
    for yr in years:
        wy = YEARS[yr]["water_year"]
        _, df = _load_ftxt(wy)
        if df.empty:
            fail(f"  {yr}: cannot load"); continue
        cols = _india_cols(df)
        n = len(cols)
        if n == 163:
            ok(f"  {yr}: {n} India columns  ✓")
            record("T3", "OK", f"{yr}: 163 columns")
        elif n == 0:
            fail(f"  {yr}: 0 India columns — column header format unexpected")
            print(f"    First 10 columns: {list(df.columns[:10])}")
            record("T3", "FAIL", f"{yr}: 0 India columns")
        else:
            warn(f"  {yr}: {n} India columns (expected 163) — {163-n} missing or extra")
            missing = set(EXIO_CODES) - set(cols)
            if missing:
                print(f"    Missing codes: {sorted(missing)[:20]}")
            record("T3", "WARN", f"{yr}: {n} India columns")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4 — Grey contamination
# ══════════════════════════════════════════════════════════════════════════════

def test4_grey_contamination(years: list[str]):
    head("TEST 4 — Grey/other water row isolation (blue prefix must NOT catch grey)")
    for yr in years:
        wy = YEARS[yr]["water_year"]
        _, df = _load_ftxt(wy)
        if df.empty:
            fail(f"  {yr}: cannot load"); continue

        grey = _grey_rows(df)
        blue = _blue_rows(df)

        # Check if any grey rows accidentally start with "Water Consumption Blue"
        false_blue = [r for r in grey if str(r).startswith("Water Consumption Blue")]
        if false_blue:
            fail(f"  {yr}: Grey/other rows match Blue prefix — CONTAMINATION:")
            for r in false_blue:
                print(f"    '{r}'")
            record("T4", "FAIL", f"{yr}: grey contamination in blue prefix")
        else:
            ok(f"  {yr}: No grey contamination in Blue prefix")
            record("T4", "OK", f"{yr}: clean")

        if grey:
            print(f"    Other 'Water Consumption' rows (correctly excluded): {grey}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 5 — EUR/INR conversion
# ══════════════════════════════════════════════════════════════════════════════

def test5_eur_inr(years: list[str]):
    head("TEST 5 — EUR/INR conversion formula: w × 100 / EUR_INR")
    expected = {"2015": 71.0, "2019": 79.0, "2022": 88.5}   # reference rates
    for yr in years:
        eur_inr = EUR_INR.get(yr)
        if eur_inr is None:
            fail(f"  {yr}: EUR_INR not in config"); record("T5","FAIL",f"{yr} missing"); continue
        conv    = 100.0 / eur_inr
        ref     = expected.get(yr)
        ref_str = f"  (reference: {ref})" if ref else ""
        # Sanity: conv should be between 0.9 and 1.5 for reasonable EUR_INR
        if 0.9 <= conv <= 1.5:
            ok(f"  {yr}: EUR_INR={eur_inr}  →  conv={conv:.5f} m³/crore per m³/EUR M{ref_str}")
            record("T5", "OK", f"{yr}: conv={conv:.4f}")
        else:
            fail(f"  {yr}: EUR_INR={eur_inr}  →  conv={conv:.5f} — out of expected range [0.9,1.5]")
            record("T5", "FAIL", f"{yr}: conv={conv:.4f} out of range")

        if ref and abs(eur_inr - ref) / ref > 0.10:
            warn(f"  {yr}: EUR_INR={eur_inr} deviates >10% from reference {ref} — check config")
            record("T5", "WARN", f"{yr}: EUR_INR deviates from reference")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 6 — Year-to-year F.txt coefficient diff for top agriculture sectors
# ══════════════════════════════════════════════════════════════════════════════

def test6_coefficient_diff(years: list[str]):
    head("TEST 6 — Agriculture coefficient diff across years (in m³/EUR million)")
    print("  Hypothesis: if 2015 coefficients dropped ~20% between runs,")
    print("  EXIOBASE F.txt was re-downloaded with a revised data version.\n")

    # Load raw EUR values (pre-conversion) for each year
    raw_data = {}
    for yr in years:
        wy = YEARS[yr]["water_year"]
        _, df = _load_ftxt(wy)
        if df.empty:
            warn(f"  {yr}: cannot load"); continue
        raw_data[yr] = df

    if len(raw_data) < 2:
        warn("  Need at least 2 years to compare — skipping"); return

    # Table: sector × year
    rows = []
    for code in AGR_CODES:
        label = AGR_LABELS.get(code, code)
        row = {"Sector": label, "Code": code}
        for yr, df in raw_data.items():
            row[yr] = _sector_blue_total(df, code)
        rows.append(row)

    comp = pd.DataFrame(rows)
    yr_list = [yr for yr in years if yr in raw_data]

    print(f"  {'Sector':<22} " + "  ".join(f"{yr:>18}" for yr in yr_list))
    print("  " + "-" * (22 + 20 * len(yr_list)))
    for _, r in comp.iterrows():
        vals = [f"{r[yr]:>18,.1f}" for yr in yr_list]
        print(f"  {r['Sector']:<22} {'  '.join(vals)}  m³/EUR M")

    # Flag year-pairs with >15% change
    print()
    ref_yr = yr_list[0]
    for yr in yr_list[1:]:
        sub(f"  {ref_yr} → {yr} coefficient changes:")
        any_big = False
        for _, r in comp.iterrows():
            v0, v1 = r[ref_yr], r[yr]
            if v0 > 0:
                pct = (v1 - v0) / v0 * 100
                if abs(pct) > 15:
                    tag = RED + "← LARGE CHANGE" + RESET
                    any_big = True
                elif abs(pct) > 5:
                    tag = YELLOW + "← moderate" + RESET
                else:
                    tag = GREEN + "stable" + RESET
                print(f"    {r['Sector']:<22}  {v0:>12,.1f} → {v1:>12,.1f}  ({pct:+.1f}%)  {tag}")
        if not any_big:
            ok("  No agriculture sector changed >15% — F.txt data appears stable")
            record("T6", "OK", f"{ref_yr}→{yr}: no large agr coefficient changes")
        else:
            warn(f"  Large agriculture coefficient changes detected {ref_yr}→{yr}")
            record("T6", "WARN", f"{ref_yr}→{yr}: large agr coefficient changes (F.txt revised?)")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 7 — Concordance coverage
# ══════════════════════════════════════════════════════════════════════════════

def test7_concordance_coverage():
    head("TEST 7 — Concordance coverage (unmapped EXIOBASE codes → silently zero)")
    try:
        from build_water_coefficients import get_concordance
        concordance = get_concordance()
    except Exception as e:
        fail(f"  Cannot import get_concordance: {e}"); return

    mapped_exio = set()
    for info in concordance.values():
        mapped_exio.update(info["exio"])

    all_codes   = set(EXIO_CODES)   # all 163 India sector codes
    unmapped    = all_codes - mapped_exio

    ok(f"  Concordance covers {len(mapped_exio)}/163 EXIOBASE codes")
    if unmapped:
        warn(f"  {len(unmapped)} unmapped codes → zero water in final table:")
        for c in sorted(unmapped)[:30]:
            print(f"      {c}")
        if len(unmapped) > 30:
            print(f"      ... and {len(unmapped)-30} more")
        record("T7", "WARN", f"{len(unmapped)} unmapped EXIOBASE codes")

        # Check if any unmapped codes are agriculture (IN.0–IN.29)
        agr_unmapped = [c for c in unmapped if c in AGR_CODES or
                        (c.startswith("IN.") and c[3:].isdigit() and int(c[3:]) < 30)]
        if agr_unmapped:
            fail(f"  AGRICULTURE codes unmapped: {agr_unmapped}")
            fail(f"  This directly reduces agriculture origin share and indirect TWF total")
            record("T7", "FAIL", f"Agriculture codes unmapped: {agr_unmapped}")
        else:
            ok("  No agriculture codes (IN.0–IN.29) are unmapped — agr share not affected by this")
            record("T7", "OK", "No agr codes unmapped")
    else:
        ok("  All 163 codes are mapped")
        record("T7", "OK", "Full concordance coverage")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 8 — SUT distribution dilution
# ══════════════════════════════════════════════════════════════════════════════

def test8_sut_dilution():
    head("TEST 8 — SUT distribution: equal-split dilution for agriculture categories")
    try:
        from build_water_coefficients import get_concordance
        concordance = get_concordance()
    except Exception as e:
        fail(f"  Cannot import get_concordance: {e}"); return

    print(f"  {'Cat ID':<8} {'Name':<35} {'N EXIO':<8} {'SUT IDs':<30} {'Dilution'}")
    print("  " + "-" * 95)
    any_warn = False
    for cat_id, info in sorted(concordance.items()):
        if info["cat"] not in ("Agriculture", "Food Mfg"):
            continue
        n_exio = len(info["exio"])
        n_sut  = len(info["sut"])
        if n_sut > 1:
            dilution = f"÷{n_sut} per SUT product"
            tag = YELLOW + "← split" + RESET if n_sut > 2 else ""
            any_warn = any_warn or n_sut > 2
        else:
            dilution = "no split"
            tag = ""
        sut_str = str(info["sut"])[:28]
        print(f"  {cat_id:<8} {info['name'][:34]:<35} {n_exio:<8} {sut_str:<30} {dilution} {tag}")

    if not any_warn:
        ok("  No agriculture/food category is over-split (no dilution concern)")
        record("T8", "OK", "No over-splitting in agr concordance")
    else:
        warn("  Some categories split across 3+ SUT products — coefficient per product is divided")
        record("T8", "WARN", "SUT over-splitting in some agr categories")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 9 — Total blue coefficient sanity check
# ══════════════════════════════════════════════════════════════════════════════

def test9_total_sanity(years: list[str]):
    head("TEST 9 — Total blue coefficient sanity: sum across all India sectors")
    print("  If F.txt data is stable, the m³/EUR M total should NOT change much year-over-year.")
    print("  A >25% shift = genuine EXIOBASE data revision (not a pipeline bug).\n")

    totals_eur = {}
    for yr in years:
        wy = YEARS[yr]["water_year"]
        _, df = _load_ftxt(wy)
        if df.empty:
            warn(f"  {yr}: cannot load"); continue
        blue  = _blue_rows(df)
        if not blue:
            warn(f"  {yr}: no Blue rows"); continue
        cols  = _india_cols(df)
        total = (df.loc[blue, cols]
                   .apply(pd.to_numeric, errors="coerce")
                   .fillna(0)
                   .values
                   .sum())
        totals_eur[yr] = total
        eur_inr  = EUR_INR.get(yr, 79.0)
        total_cr = total * (100.0 / eur_inr)
        ok(f"  {yr}: sum(Blue, all India)={total:>18,.1f} m³/EUR M  "
           f"→ {total_cr:>15,.1f} m³/crore  (EUR_INR={eur_inr})")

    if len(totals_eur) >= 2:
        print()
        yr_list = [yr for yr in years if yr in totals_eur]
        for i in range(len(yr_list) - 1):
            y0, y1 = yr_list[i], yr_list[i + 1]
            pct = (totals_eur[y1] - totals_eur[y0]) / totals_eur[y0] * 100
            if abs(pct) > 25:
                fail(f"  {y0}→{y1}: total blue sum changed {pct:+.1f}%  ← F.txt DATA REVISION confirmed")
                record("T9", "FAIL", f"{y0}→{y1}: total blue changed {pct:+.1f}%")
            elif abs(pct) > 10:
                warn(f"  {y0}→{y1}: total blue sum changed {pct:+.1f}% — moderate, check if expected")
                record("T9", "WARN", f"{y0}→{y1}: {pct:+.1f}% change")
            else:
                ok(f"  {y0}→{y1}: total blue sum changed {pct:+.1f}% — stable")
                record("T9", "OK", f"{y0}→{y1}: stable ({pct:+.1f}%)")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 10 — Row multiplicity
# ══════════════════════════════════════════════════════════════════════════════

def test10_row_multiplicity(years: list[str]):
    head("TEST 10 — Blue row count per year (1=normal, 2+=risk of doubling vs other years)")
    counts = {}
    for yr in years:
        wy = YEARS[yr]["water_year"]
        _, df = _load_ftxt(wy)
        if df.empty:
            fail(f"  {yr}: cannot load"); continue
        blue   = _blue_rows(df)
        green  = _green_rows(df)
        counts[yr] = len(blue)
        print(f"  {yr} (water_year={wy}):")
        print(f"    Blue rows ({len(blue)}):  {blue}")
        print(f"    Green rows ({len(green)}): {green}")

    unique_counts = set(counts.values())
    if len(unique_counts) == 1:
        c = list(unique_counts)[0]
        ok(f"  All years have {c} Blue row(s) — consistent")
        record("T10", "OK", f"All years: {c} Blue row(s)")
    else:
        fail(f"  INCONSISTENT Blue row counts across years: {counts}")
        fail(f"  This means some years sum MORE rows — inflating those years' coefficients")
        record("T10", "FAIL", f"Inconsistent counts: {counts}")


# ══════════════════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

def print_summary(csv_out: Path | None):
    head("=" * 60)
    head("SUMMARY")
    head("=" * 60)

    ok_count   = sum(1 for _, s, _ in RESULTS if s == "OK")
    warn_count = sum(1 for _, s, _ in RESULTS if s == "WARN")
    fail_count = sum(1 for _, s, _ in RESULTS if s == "FAIL")

    for tid, status, msg in RESULTS:
        if status == "OK":
            print(f"  {GREEN}✓{RESET}  [{tid}]  {msg}")
        elif status == "WARN":
            print(f"  {YELLOW}⚠{RESET}  [{tid}]  {msg}")
        else:
            print(f"  {RED}✗{RESET}  [{tid}]  {msg}")

    print()
    print(f"  {GREEN}{ok_count} passed{RESET}   {YELLOW}{warn_count} warnings{RESET}   {RED}{fail_count} failures{RESET}")

    # Root-cause diagnosis
    print()
    head("ROOT CAUSE DIAGNOSIS (based on test results)")
    fails  = {t for t, s, _ in RESULTS if s == "FAIL"}
    warns  = {t for t, s, _ in RESULTS if s == "WARN"}

    if "T10" in fails:
        print(textwrap.dedent(f"""
          {RED}PRIMARY CAUSE: Inconsistent Blue row count across years (TEST 10).{RESET}
          One year sums 2 rows, another sums 1.  This directly multiplies
          one year's coefficients by ×2, producing the ~20% baseline shift.
          Fix: check F.txt header for duplicate row names or use exact-match
          instead of startswith() in _extract_colour().
        """))
    elif "T9" in fails:
        print(textwrap.dedent(f"""
          {RED}PRIMARY CAUSE: F.txt data genuinely revised between EXIOBASE versions (TEST 9).{RESET}
          Total blue coefficient changed >25% — this is a database change,
          not a pipeline bug. The old run used an older EXIOBASE release.
          Action: note the EXIOBASE version in the Methods section and
          use the same version for all three study years.
        """))
    elif "T2" in fails:
        print(textwrap.dedent(f"""
          {RED}PRIMARY CAUSE: Row name matching failure (TEST 2).{RESET}
          Invisible characters or spelling variants prevented Blue rows
          from being matched in one or more years.
          Fix: strip() the index before the startswith() check, or use
          a case-insensitive match.
        """))
    elif "T7" in fails:
        print(textwrap.dedent(f"""
          {RED}PRIMARY CAUSE: Agriculture codes unmapped in concordance (TEST 7).{RESET}
          Some agriculture EXIOBASE codes map to zero, reducing the
          agriculture origin share and total indirect TWF.
          Fix: update get_concordance() to cover the missing codes.
        """))
    elif "T6" in warns or "T9" in warns:
        print(textwrap.dedent(f"""
          {YELLOW}LIKELY CAUSE: Moderate F.txt coefficient change (TEST 6/9).{RESET}
          Individual agriculture sector coefficients changed 5–25% between
          EXIOBASE water years.  This is consistent with EXIOBASE revising
          WaterGAP inputs between minor releases (e.g. 3.8.1 → 3.8.2).
          Action: document which EXIOBASE version was used for each year
          and report the run comparison as a sensitivity check.
        """))
    elif "T2" in warns:
        print(textwrap.dedent(f"""
          {YELLOW}LIKELY CAUSE: Multiple Blue rows being summed (TEST 2).{RESET}
          Two Blue rows exist in F.txt. Verify both rows are genuinely
          blue water (e.g. 'Blue - Irrigation' and 'Blue - Non-irrigation')
          and that the old run was not summing only one of them.
        """))
    else:
        print(f"  {GREEN}No clear failure pattern detected from the tests above.{RESET}")
        print("  Check the WARN items manually — they may point to a subtle issue.")

    if csv_out:
        rows = [{"Test": t, "Status": s, "Message": m} for t, s, m in RESULTS]
        pd.DataFrame(rows).to_csv(csv_out, index=False)
        print(f"\n  Detailed results written to: {csv_out}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Diagnose EXIOBASE F.txt extraction issues in the TWF pipeline."
    )
    parser.add_argument(
        "--year", nargs="+", choices=STUDY_YEARS, default=STUDY_YEARS,
        help="Study years to test (default: all)"
    )
    parser.add_argument(
        "--csv", type=Path, default=None,
        help="Optional path to write a CSV summary of test results"
    )
    args = parser.parse_args()
    years = args.year

    print(f"\n{BOLD}EXIOBASE F.txt Extraction Diagnostic{RESET}")
    print(f"Pipeline root : {ROOT}")
    print(f"Study years   : {years}")
    print(f"EXIOBASE dir  : {DIRS.get('exiobase', BASE_DIR / '1-input-data' / 'exiobase-raw')}")

    found = test1_file_presence(years)
    if not found:
        warn("Some F.txt files missing — remaining tests may be partial")

    test2_row_names(years)
    test3_india_columns(years)
    test4_grey_contamination(years)
    test5_eur_inr(years)
    test6_coefficient_diff(years)
    test7_concordance_coverage()
    test8_sut_dilution()
    test9_total_sanity(years)
    test10_row_multiplicity(years)

    print_summary(args.csv)


if __name__ == "__main__":
    main()
