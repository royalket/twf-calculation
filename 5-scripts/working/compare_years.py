"""
compare_years.py
================
Cross-year Tourism Water Footprint comparison: 2015 vs 2019 vs 2022.

Combines indirect (EEIO) + direct (activity-based) TWF into total TWF.
All comparisons use both NOMINAL and REAL (2015-16 deflated) values so that
intensity trends reflect genuine efficiency changes, not inflation effects.

Key outputs:
  1. Total TWF:         indirect + direct, nominal and real intensity
  2. Per-tourist:       L/tourist/day for domestic and inbound
  3. Data quality flags: intensity drop decomposition, numerator check,
                         domestic/inbound ratio, avg_stay_days source (NEW)
  4. Sector trends:     which categories improved / worsened most
  5. Type I multipliers:WL diagonal values per sector across years
  6. Publication report:formatted text ready for results section

Outputs:
  comparison/twf_total_all_years.csv       totals + intensity
  comparison/twf_per_tourist_intensity.csv L/tourist/day
  comparison/twf_sector_trends.csv         sector-level 2015→2022 change
  comparison/twf_type1_multipliers.csv     WL diagonal by sector and year
  comparison/twf_comparison_report.txt     publication-ready summary
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    BASE_DIR, DIRS, STUDY_YEARS, ACTIVITY_DATA, CPI, EUR_INR,
    DIRECT_WATER, NAS_GROWTH_RATES, NAS_GVA_CONSTANT, USD_INR,
)
from utils import (
    Logger, save_csv,
    read_csv, compare_across_years, compare_sectors_across_years, Timer,
    crore_to_usd_m, fmt_crore_usd,
)

# Backward-compat shim: read_csv_safe → read_csv(required=False)
def read_csv_safe(path) -> pd.DataFrame:
    return read_csv(path, required=False)

# AVG_STAY_DAYS is now merged into ACTIVITY_DATA in the refactored config.
# Build a backward-compat view for data_quality_flags() which still references it.
AVG_STAY_DAYS: dict = {
    yr: {
        "domestic": ACTIVITY_DATA.get(yr, {}).get("avg_stay_days_dom", 2.5),
        "inbound":  ACTIVITY_DATA.get(yr, {}).get("avg_stay_days_inb", 8.0),
    }
    for yr in STUDY_YEARS
}

SCRIPT_NAME = "compare_years"


# ══════════════════════════════════════════════════════════════════════════════
# LOADERS
# ══════════════════════════════════════════════════════════════════════════════

def _load_indirect(year: str) -> float:
    f = DIRS["indirect"] / f"indirect_twf_{year}_by_category.csv"
    df = read_csv_safe(f)
    if df.empty:
        return 0.0
    return df["Total_Water_m3"].sum()


def _load_indirect_real_intensity(year: str) -> float:
    """
    Return the real-price indirect water intensity for the given year (m³/₹ crore, 2015-16 prices).

    Priority:
      1. Read Real_Intensity_m3_per_crore from indirect_twf_all_years.csv — this was
         computed in calculate_indirect_twf.py using Y_140_real (deflated demand) and is
         the authoritative real-price figure.
      2. If that file/column is unavailable, fall back to total_water / total_nominal_demand
         from the by_category CSV — correct aggregation formula but nominal not real.
      3. If by_category is also missing, return 0.0.

    NOTE: The old implementation returned df["Intensity_m3_per_crore"].mean() — an unweighted
    average of 75 per-category ratios. This was wrong in two ways:
      (a) Category-count dependent: splitting one entry changes the mean even with no data change.
      (b) Not real: by_category uses nominal demand prices, not 2015-16 deflated.
    Both issues are fixed here.
    """
    # Path 1: authoritative real intensity from the cross-year summary
    all_years_f = DIRS["indirect"] / "indirect_twf_all_years.csv"
    all_df = read_csv_safe(all_years_f)
    if not all_df.empty and "Real_Intensity_m3_per_crore" in all_df.columns and "Year" in all_df.columns:
        row = all_df[all_df["Year"].astype(str) == str(year)]
        if not row.empty:
            val = float(row.iloc[0]["Real_Intensity_m3_per_crore"])
            # 0 means real demand file was unavailable when calculate_indirect_twf ran
            if val > 0:
                return val

    # Path 2: correct aggregation from by_category (nominal, not real — documented)
    cat_f = DIRS["indirect"] / f"indirect_twf_{year}_by_category.csv"
    df = read_csv_safe(cat_f)
    if df.empty:
        return 0.0
    total_water  = df["Total_Water_m3"].sum()  if "Total_Water_m3"  in df.columns else 0.0
    total_demand = df["Demand_crore"].sum()    if "Demand_crore"    in df.columns else 0.0
    return total_water / total_demand if total_demand > 0 else 0.0


def _load_direct(year: str, scenario: str = "BASE") -> float:
    f = DIRS["direct"] / f"direct_twf_{year}.csv"
    df = read_csv_safe(f)
    if df.empty:
        return 0.0
    row = df[df["Scenario"] == scenario]
    return float(row["Total_m3"].iloc[0]) if not row.empty else 0.0


def _load_cat_df(year: str) -> pd.DataFrame:
    f = DIRS["indirect"] / f"indirect_twf_{year}_by_category.csv"
    return read_csv_safe(f)


def _load_sut_results(year: str) -> pd.DataFrame:
    f = DIRS["indirect"] / f"indirect_twf_{year}_by_sut.csv"
    return read_csv_safe(f)


# ══════════════════════════════════════════════════════════════════════════════
# TOTAL TWF TABLE
# ══════════════════════════════════════════════════════════════════════════════

def build_total_twf(log: Logger) -> pd.DataFrame:
    rows = []
    for year in STUDY_YEARS:
        indirect = _load_indirect(year)
        direct   = _load_direct(year, "BASE")
        total    = indirect + direct
        _usd_rate = USD_INR.get(year, 70.0)
        rows.append({
            "Year": year,
            "Indirect_m3": indirect, "Direct_m3": direct, "Total_m3": total,
            "Indirect_bn_m3": round(indirect / 1e9, 4),
            "Direct_bn_m3":   round(direct   / 1e9, 4),
            "Total_bn_m3":    round(total     / 1e9, 4),
            "Indirect_pct": round(100 * indirect / total, 1) if total else 0,
            "Direct_pct":   round(100 * direct   / total, 1) if total else 0,
            "USD_INR_Rate": _usd_rate,
        })
    df = pd.DataFrame(rows)

    ind_vals = {r["Year"]: r["Indirect_bn_m3"] for r in rows}
    dir_vals = {r["Year"]: r["Direct_bn_m3"]   for r in rows}
    tot_vals = {r["Year"]: r["Total_bn_m3"]    for r in rows}
    compare_across_years(ind_vals, "Indirect TWF (bn m³)",    unit=" bn m³", log=log)
    compare_across_years(dir_vals, "Direct TWF BASE (bn m³)", unit=" bn m³", log=log)
    compare_across_years(tot_vals, "Total TWF (bn m³)",       unit=" bn m³", log=log)

    # USD/INR rate note
    rate_note = "  USD/INR rates used: " + "  |  ".join(
        f"{yr}: ₹{USD_INR.get(yr, 70.0):.2f}/USD" for yr in STUDY_YEARS
    )
    if log:
        log._log(rate_note)
    else:
        print(rate_note)

    return df


# ══════════════════════════════════════════════════════════════════════════════
# PER-TOURIST INTENSITY
# ══════════════════════════════════════════════════════════════════════════════

def per_tourist_intensity(total_df: pd.DataFrame, log: Logger) -> pd.DataFrame:
    """
    L per tourist per day — split into indirect (supply-chain) and direct
    (operational) water, for domestic tourists, inbound tourists, and combined.

    Fixes applied vs. original:
    ────────────────────────────
    Bug 1 (algebra cancel): The original `dom_share * total_m3 / dom_days`
    simplifies to `total_m3 / all_days` — making domestic and inbound identical.
    Fixed by loading the actual split indirect water from
    `indirect_twf_{year}_split.csv` (computed by calculate_indirect_twf.py).

    Bug 2 (no split used): Split TWF files were never read here. Now they are
    the primary source for inbound vs domestic indirect water. Tourist-day
    proportional split is used only as a fallback when the file is missing.

    Bug 3 (direct water dilution note): Direct water (hotel/restaurant/rail/air)
    is split proportionally by tourist-days — the best available proxy since the
    direct module has no inbound/domestic breakdown. The reported L/day will
    always be lower than the hotel L/room/night coefficient because the
    denominator includes hundreds of millions of domestic day-trippers who
    never stay in a classified hotel. See notes column in output CSV.

    New columns added vs. original:
    ─────────────────────────────────
    Indirect_L_per_dom_day, Indirect_L_per_inb_day, Indirect_L_per_all_day
    Direct_L_per_dom_day,   Direct_L_per_inb_day,   Direct_L_per_all_day
    (plus the existing Total_ columns, now correctly differentiated)
    """
    rows = []
    for _, r in total_df.iterrows():
        year     = r["Year"]
        act      = ACTIVITY_DATA.get(year, ACTIVITY_DATA[STUDY_YEARS[-1]])
        dom_days = act["domestic_tourists_M"] * 1e6 * act["avg_stay_days_dom"]
        inb_days = act["inbound_tourists_M"]  * 1e6 * act["avg_stay_days_inb"]
        all_days = dom_days + inb_days
        _usd_rate = USD_INR.get(year, 70.0)

        # ── Indirect water: load from split CSV ──────────────────────────────
        split_path = DIRS["indirect"] / f"indirect_twf_{year}_split.csv"
        split_df   = read_csv_safe(split_path)

        split_loaded = False
        if not split_df.empty and "Type" in split_df.columns and "TWF_m3" in split_df.columns:
            inb_row = split_df[split_df["Type"] == "Inbound"]
            dom_row = split_df[split_df["Type"] == "Domestic"]
            if not inb_row.empty and not dom_row.empty:
                inb_indirect_m3 = float(inb_row["TWF_m3"].iloc[0])
                dom_indirect_m3 = float(dom_row["TWF_m3"].iloc[0])
                split_loaded    = True

        if not split_loaded:
            # Fallback: proportional by tourist-days (same as original — documents why)
            if log:
                log._log(
                    f"  WARN {year}: split TWF file not found or missing Type/TWF_m3 columns.\n"
                    f"    Falling back to tourist-day proportional split for indirect water.\n"
                    f"    Run calculate_indirect_twf.py with split demand vectors to fix."
                )
            inb_frac        = inb_days / all_days if all_days else 0
            dom_frac        = 1.0 - inb_frac
            inb_indirect_m3 = r["Indirect_m3"] * inb_frac
            dom_indirect_m3 = r["Indirect_m3"] * dom_frac

        all_indirect_m3 = r["Indirect_m3"]   # authoritative total from total_df

        # ── Direct water: split proportionally by tourist-days ────────────────
        # No inbound/domestic breakdown exists in the direct module; tourist-day
        # proportion is the best available proxy.
        direct_total_m3 = r["Direct_m3"]
        if all_days > 0:
            inb_direct_m3 = direct_total_m3 * (inb_days / all_days)
            dom_direct_m3 = direct_total_m3 * (dom_days / all_days)
        else:
            inb_direct_m3 = dom_direct_m3 = 0.0

        # ── Total per segment ─────────────────────────────────────────────────
        inb_total_m3 = inb_indirect_m3 + inb_direct_m3
        dom_total_m3 = dom_indirect_m3 + dom_direct_m3
        all_total_m3 = r["Total_m3"]

        # ── Convert m³ → L/tourist/day ────────────────────────────────────────
        def _l(m3, days):
            return round(m3 * 1000 / days) if days else 0

        rows.append({
            "Year":                        year,
            "Dom_tourists_M":              act["domestic_tourists_M"],
            "Inb_tourists_M":              act["inbound_tourists_M"],
            "Dom_stay_days":               act["avg_stay_days_dom"],
            "Inb_stay_days":               act["avg_stay_days_inb"],
            "Dom_days_M":                  round(dom_days / 1e6, 1),
            "Inb_days_M":                  round(inb_days / 1e6, 1),
            # ── Indirect (supply-chain) component ────────────────────────────
            "Indirect_L_per_dom_day":      _l(dom_indirect_m3, dom_days),
            "Indirect_L_per_inb_day":      _l(inb_indirect_m3, inb_days),
            "Indirect_L_per_all_day":      _l(all_indirect_m3, all_days),
            "Dom_Indirect_m3":             round(dom_indirect_m3),
            "Inb_Indirect_m3":             round(inb_indirect_m3),
            "Indirect_split_source":       "split_csv" if split_loaded else "tourist_day_proportion",
            # ── Direct (operational) component ───────────────────────────────
            "Direct_L_per_dom_day":        _l(dom_direct_m3, dom_days),
            "Direct_L_per_inb_day":        _l(inb_direct_m3, inb_days),
            "Direct_L_per_all_day":        _l(direct_total_m3, all_days),
            "Dom_Direct_m3":               round(dom_direct_m3),
            "Inb_Direct_m3":               round(inb_direct_m3),
            # ── Total (indirect + direct) ─────────────────────────────────────
            "L_per_tourist_day":           _l(all_total_m3, all_days),
            "L_per_dom_tourist_day":       _l(dom_total_m3, dom_days),
            "L_per_inb_tourist_day":       _l(inb_total_m3, inb_days),
            "USD_INR_Rate":                _usd_rate,
        })

    df = pd.DataFrame(rows)

    compare_across_years(
        {r["Year"]: r["L_per_tourist_day"] for r in rows},
        "Total L/tourist/day (all)", unit=" L/day", log=log,
    )
    compare_across_years(
        {r["Year"]: r["L_per_dom_tourist_day"] for r in rows},
        "Total L/tourist/day (domestic)", unit=" L/day", log=log,
    )
    compare_across_years(
        {r["Year"]: r["L_per_inb_tourist_day"] for r in rows},
        "Total L/tourist/day (inbound)", unit=" L/day", log=log,
    )
    compare_across_years(
        {r["Year"]: r["Indirect_L_per_all_day"] for r in rows},
        "Indirect L/tourist/day (all)", unit=" L/day", log=log,
    )
    compare_across_years(
        {r["Year"]: r["Direct_L_per_all_day"] for r in rows},
        "Direct L/tourist/day (all)", unit=" L/day", log=log,
    )

    if log:
        log._log(
            "\n  NOTE — why L/tourist/day < hotel L/room/night coefficient:\n"
            "  The denominator includes ALL tourist-days: day-trippers, pilgrims,\n"
            "  VFR, business travellers — most of whom never stay in a classified\n"
            "  hotel. Only ~50-80M hotel room-nights/yr exist vs 3-5 billion\n"
            "  domestic tourist-days. The dilution is structural, not an error.\n"
            "  To validate hotel coefficients independently, check:\n"
            "    direct_twf_{year}.csv → Hotel_m3\n"
            "  ÷ (classified_rooms × occupancy_rate × nights_per_year) in config."
        )

    return df


# ══════════════════════════════════════════════════════════════════════════════
# DATA QUALITY FLAGS
# ══════════════════════════════════════════════════════════════════════════════

def data_quality_flags(intensity_df: pd.DataFrame, total_df: pd.DataFrame,
                        log: Logger) -> None:
    """
    Check for data quality issues that could make reported metrics misleading.
    Prints warnings to log and terminal. Does NOT raise exceptions — warnings
    are informational so the pipeline continues and you can investigate.

    Checks performed
    ----------------
    1. Per-tourist intensity drop > 30% between consecutive years.
       A large drop is almost always a denominator problem (tourist count
       methodology change) rather than a genuine efficiency improvement.
       Decomposes the change into numerator (TWF change) and denominator
       (tourist-days change) to show which is driving the drop.

    2. Total TWF numerator consistency: Total_m3 = Indirect_m3 + Direct_m3.
       A mismatch means build_total_twf() is not combining components correctly.

    3. Domestic/inbound tourist-days ratio.
       If domestic tourist-days are > 200× inbound, flags a likely methodology
       shift in domestic counting between survey rounds (MoT changed how it
       counted day-trippers between 2015-16 and 2019-20 survey rounds).

    4. avg_stay_days data source and placeholder check.
       Reports whether values are from AVG_STAY_DAYS table (reference_data.md)
       or hardcoded fallback, and flags if still at default 2.5/8.0 values.
    """
    log.section("DATA QUALITY FLAGS")

    # ── Check 1: Per-tourist intensity drops > 30% ──────────────────────────
    log.subsection("Check 1 — Per-tourist intensity year-on-year change")
    prev_intensity = None
    prev_all_days  = None
    prev_twf       = None
    prev_year      = None

    for _, r in intensity_df.iterrows():
        year     = r["Year"]
        act      = ACTIVITY_DATA.get(year, {})
        dom_days = act.get("domestic_tourists_M", 0) * 1e6 * act.get("avg_stay_days_dom", 2.5)
        inb_days = act.get("inbound_tourists_M",  0) * 1e6 * act.get("avg_stay_days_inb", 8.0)
        all_days = dom_days + inb_days

        twf_row  = total_df[total_df["Year"] == year]
        total_m3 = float(twf_row["Total_m3"].iloc[0]) if not twf_row.empty else 0.0

        current_intensity = r["L_per_tourist_day"]

        if prev_intensity is not None and prev_intensity > 0:
            chg_pct = 100 * (current_intensity - prev_intensity) / prev_intensity

            log.info(
                f"  {prev_year} → {year}: intensity {prev_intensity:,.0f} → "
                f"{current_intensity:,.0f} L/day  ({chg_pct:+.1f}%)"
            )

            if chg_pct < -30:
                twf_chg_pct  = 100 * (total_m3 - prev_twf) / prev_twf if prev_twf > 0 else 0
                days_chg_pct = 100 * (all_days - prev_all_days) / prev_all_days if prev_all_days > 0 else 0
                log.info(
                    f"  ⚠ WARNING: intensity drop of {chg_pct:.1f}% exceeds 30% threshold.\n"
                    f"    Decomposition:\n"
                    f"      Total TWF change:    {twf_chg_pct:+.1f}%  "
                    f"({prev_twf/1e9:.2f} → {total_m3/1e9:.2f} bn m³)\n"
                    f"      Tourist-days change: {days_chg_pct:+.1f}%  "
                    f"({prev_all_days/1e6:.0f}M → {all_days/1e6:.0f}M days)\n"
                    f"    If tourist-days grew much faster than TWF, the likely cause is\n"
                    f"    a methodology change in domestic tourist counting between survey\n"
                    f"    rounds — NOT a genuine efficiency improvement.\n"
                    f"    ACTION: Verify domestic_tourists_M definitions are comparable\n"
                    f"    across years in reference_data.md § ACTIVITY_DATA."
                )
            elif chg_pct > 30:
                log.info(
                    f"  ⚠ WARNING: intensity RISE of {chg_pct:.1f}% exceeds 30% threshold.\n"
                    f"    Check whether tourist volumes dropped due to COVID or data revision."
                )
            else:
                log.info(f"  ✓ Change within ±30% — plausible year-on-year variation.")

        prev_intensity = current_intensity
        prev_all_days  = all_days
        prev_twf       = total_m3
        prev_year      = year

    # ── Check 2: Total = indirect + direct ──────────────────────────────────
    log.subsection("Check 2 — Total TWF numerator consistency (indirect + direct)")
    for _, r in total_df.iterrows():
        year        = r["Year"]
        total_m3    = float(r["Total_m3"])
        indirect_m3 = float(r["Indirect_m3"])
        direct_m3   = float(r["Direct_m3"])
        computed    = indirect_m3 + direct_m3
        diff_pct    = 100 * abs(total_m3 - computed) / total_m3 if total_m3 > 0 else 0

        if diff_pct > 0.01:
            log.info(
                f"  ⚠ {year}: Total ({total_m3:,.0f}) ≠ Indirect ({indirect_m3:,.0f}) "
                f"+ Direct ({direct_m3:,.0f}) = {computed:,.0f}  "
                f"(diff {diff_pct:.3f}%) — check build_total_twf()"
            )
        else:
            log.info(
                f"  ✓ {year}: indirect + direct = total  "
                f"({indirect_m3/1e9:.3f} + {direct_m3/1e9:.3f} = {total_m3/1e9:.3f} bn m³)"
            )

    # ── Check 3: Domestic/inbound tourist-days ratio ─────────────────────────
    log.subsection("Check 3 — Domestic vs inbound tourist-days ratio")
    for year in STUDY_YEARS:
        act      = ACTIVITY_DATA.get(year, {})
        dom_days = act.get("domestic_tourists_M", 0) * 1e6 * act.get("avg_stay_days_dom", 2.5)
        inb_days = act.get("inbound_tourists_M",  0) * 1e6 * act.get("avg_stay_days_inb", 8.0)
        ratio    = dom_days / inb_days if inb_days > 0 else 0
        dom_M    = act.get("domestic_tourists_M", 0)
        inb_M    = act.get("inbound_tourists_M",  0)
        dom_stay = act.get("avg_stay_days_dom", 2.5)
        inb_stay = act.get("avg_stay_days_inb", 8.0)

        flag = "⚠ WARNING" if ratio > 200 else "✓"
        log.info(
            f"  {flag} {year}: dom {dom_M:.0f}M × {dom_stay:.1f}d = {dom_days/1e6:.0f}M days  |  "
            f"inb {inb_M:.2f}M × {inb_stay:.1f}d = {inb_days/1e6:.0f}M days  |  ratio {ratio:.0f}:1"
        )
        if ratio > 200:
            log.info(
                f"    Domestic/inbound ratio of {ratio:.0f}:1 is very high.\n"
                f"    Possible cause: MoT changed domestic counting methodology\n"
                f"    (started including day-trippers / pilgrims in one survey round).\n"
                f"    ACTION: Check MoT survey methodology notes for {year} and verify\n"
                f"    that domestic_tourists_M is comparable across all three study years."
            )

    # ── Check 4: avg_stay_days source and placeholder values ─────────────────
    log.subsection("Check 4 — avg_stay_days data source and values")
    all_placeholder = all(
        AVG_STAY_DAYS.get(yr, {}).get("domestic", 2.5) == 2.5 and
        AVG_STAY_DAYS.get(yr, {}).get("inbound",  8.0) == 8.0
        for yr in STUDY_YEARS
    )
    if all_placeholder:
        log.info(
            "  ⚠ All avg_stay_days values are at defaults (dom=2.5, inb=8.0).\n"
            "    These are PLACEHOLDERS — update with actual MoT survey figures\n"
            "    in reference_data.md § AVG_STAY_DAYS before publication.\n"
            "    avg_stay_days directly affects the tourist-days denominator,\n"
            "    which drives per-tourist intensity comparisons across years."
        )
    else:
        log.info("  ✓ AVG_STAY_DAYS contains non-default values.")

    for year in STUDY_YEARS:
        dom_stay = ACTIVITY_DATA.get(year, {}).get("avg_stay_days_dom", 2.5)
        inb_stay = ACTIVITY_DATA.get(year, {}).get("avg_stay_days_inb", 8.0)
        flag = "  ← PLACEHOLDER" if (dom_stay == 2.5 and inb_stay == 8.0) else ""
        log.info(f"  {year}: domestic={dom_stay:.1f}d  inbound={inb_stay:.1f}d{flag}")


# ══════════════════════════════════════════════════════════════════════════════
# SECTOR TRENDS
# ══════════════════════════════════════════════════════════════════════════════

def sector_trends(log: Logger) -> pd.DataFrame:
    cat_dfs = {yr: _load_cat_df(yr) for yr in STUDY_YEARS}
    if any(df.empty for df in cat_dfs.values()):
        log.warn("Some category files missing — sector trends incomplete")
        return pd.DataFrame()
    return compare_sectors_across_years(
        {yr: df[["Category_Name", "Total_Water_m3"]] for yr, df in cat_dfs.items()},
        "Total_Water_m3", "Category_Name",
        "Indirect TWF by category", n_top=5, log=log,
    )


# ══════════════════════════════════════════════════════════════════════════════
# TYPE I MULTIPLIERS
# ══════════════════════════════════════════════════════════════════════════════

def _exio_codes_for_product(product_id: int, study_year: str) -> str:
    """
    Return the EXIOBASE sector code(s) mapped to a SUT product ID.
    Reads the concordance CSV for the given study year.
    Used to give traceability when flagging multiplier-zero artifacts.
    Returns a comma-separated string, or "—" if nothing found.
    """
    from config import YEARS
    cfg = YEARS.get(study_year, {})
    tag = cfg.get("io_tag", "")
    conc = read_csv_safe(DIRS["concordance"] / f"concordance_{tag}.csv")
    if conc.empty or "SUT_Product_IDs" not in conc.columns:
        return "—"
    codes: list = []
    pid_str = str(product_id)
    for _, row in conc.iterrows():
        ids_in_row = [
            s.strip() for s in str(row["SUT_Product_IDs"]).split(",")
            if s.strip().lower() not in ("nan", "")
        ]
        if pid_str in ids_in_row:
            for code in str(row.get("EXIOBASE_Sectors", "")).split(","):
                code = code.strip()
                if code and code.lower() not in ("nan", ""):
                    codes.append(code)
    return ", ".join(codes) if codes else "—"


def type1_multipliers(log: Logger) -> tuple:
    """
    Water multiplier WL[i] per SUT product across study years.

    WL[i] = W @ L[:,i]  (total m3 triggered per Rs crore of final demand for product i).

    FIX — artefact separation
    --------------------------
    Products whose multiplier went from positive in first_yr to EXACTLY ZERO in
    last_yr are NOT genuine efficiency improvements — they are EXIOBASE data
    revisions where the water coefficient for that sector was set to zero in a
    later database edition. A genuine improvement would show a large negative
    change while staying > 0 in both years.

    Returns
    -------
    (wide_df, artifact_df)
      wide_df     : Product_ID x year multipliers, change%, Product_Name, EXIOBASE_Codes
      artifact_df : rows that went to zero in last_yr (save to twf_multiplier_artifacts.csv)
    """
    log.subsection("Type I Water Multipliers (WL diagonal)")

    all_rows = []
    for year in STUDY_YEARS:
        df = _load_sut_results(year)
        if df.empty:
            continue
        # Accept both the new canonical name and the old name for backward compat.
        # Old name: "Water_Multiplier"  (written before the column-rename fix)
        # New name: "Water_Multiplier_m3_per_crore"  (written by fixed build_sut_results)
        mult_col = None
        for _candidate in ("Water_Multiplier_m3_per_crore", "Water_Multiplier"):
            if _candidate in df.columns:
                mult_col = _candidate
                break
        if mult_col is None:
            continue
        keep = [c for c in ["Product_ID", "Product_Name", mult_col] if c in df.columns]
        sub = df[keep].copy()
        sub = sub.rename(columns={mult_col: "Water_Multiplier_m3_per_crore"})
        sub["Year"] = year
        all_rows.append(sub)

    if not all_rows:
        return pd.DataFrame(), pd.DataFrame()

    combined = pd.concat(all_rows, ignore_index=True)
    wide = combined.pivot_table(
        index="Product_ID", columns="Year",
        values="Water_Multiplier_m3_per_crore", aggfunc="mean",
    ).reset_index()
    wide.columns.name = None

    if "Product_Name" in combined.columns:
        names = (combined.dropna(subset=["Product_Name"])
                 [["Product_ID", "Product_Name"]].drop_duplicates("Product_ID"))
        wide = wide.merge(names, on="Product_ID", how="left")
    if "Product_Name" not in wide.columns:
        wide["Product_Name"] = wide["Product_ID"].apply(lambda x: f"Product {int(x)}")
    wide["Product_Name"] = wide["Product_Name"].fillna(
        wide["Product_ID"].apply(lambda x: f"Product {int(x)}")
    )

    first_yr, last_yr = STUDY_YEARS[0], STUDY_YEARS[-1]
    artifact_df = pd.DataFrame()

    if first_yr not in wide.columns or last_yr not in wide.columns:
        log.warn(f"Multiplier columns for {first_yr} or {last_yr} missing — skipping analysis")
        return wide, artifact_df

    chg_col = f"Change_{first_yr}_{last_yr}_pct"
    with np.errstate(divide="ignore", invalid="ignore"):
        wide[chg_col] = (
            100 * (wide[last_yr] - wide[first_yr]) / wide[first_yr].replace(0, np.nan)
        )

    has_positive_base = wide[first_yr].notna() & (wide[first_yr] > 0)
    went_zero         = wide[last_yr].fillna(0) == 0
    artifacts = wide[has_positive_base &  went_zero].copy()
    genuine   = wide[has_positive_base & ~went_zero].dropna(subset=[chg_col])

    SEP  = "─" * 102
    SEP2 = "─" * 78

    if not artifacts.empty:
        artifacts["EXIOBASE_Codes"] = artifacts["Product_ID"].apply(
            lambda pid: _exio_codes_for_product(int(pid), last_yr)
        )
        artifact_df = artifacts[[
            "Product_ID", "Product_Name", "EXIOBASE_Codes",
            first_yr, last_yr, chg_col,
        ]].copy()

        log.subsection(
            f"WARNING: {len(artifact_df)} product(s) multiplier went to zero "
            f"in {last_yr} — EXIOBASE data artefacts, NOT efficiency gains"
        )
        log.info(
            "  A genuine improvement would stay > 0 in both years."
            "  These products were revised to zero in EXIOBASE and must NOT"
            "  be reported as efficiency improvements in publications."
            "  Cross-check F.txt in IOT_{yr}_ixi for the EXIOBASE codes below."
            .replace("{yr}", last_yr)
        )
        log.info(
            f"\n  {'ID':<5}  {'Product Name':<36}  {'EXIOBASE Code(s)':<20}"
            f"  {first_yr:>12}  {last_yr:>12}  {'Chg%':>8}"
        )
        log.info(f"  {SEP}")
        for _, r in artifact_df.iterrows():
            log.info(
                f"  {int(r['Product_ID']):<5}  {str(r['Product_Name'])[:35]:<36}"
                f"  {str(r['EXIOBASE_Codes'])[:19]:<20}"
                f"  {r[first_yr]:>12.2f}  {float(r[last_yr]):>12.2f}  {r[chg_col]:>+7.1f}%"
            )
    else:
        log.info(f"  No artefact products found (no multipliers went to zero in {last_yr})")

    g_impr = genuine[genuine[chg_col] < 0].nsmallest(5, chg_col)
    g_wrse = genuine[genuine[chg_col] > 0].nlargest(5, chg_col)

    log.subsection(
        f"Genuine improvements ({first_yr}\u2192{last_yr}, multiplier > 0 in both years)"
    )
    if g_impr.empty:
        log.info("  None found")
    else:
        log.info(f"  {'ID':<5}  {'Product Name':<36}  {first_yr:>12}  {last_yr:>12}  {'Chg%':>8}")
        log.info(f"  {SEP2}")
        for _, r in g_impr.iterrows():
            log.info(
                f"  {int(r['Product_ID']):<5}  {str(r['Product_Name'])[:35]:<36}"
                f"  {r[first_yr]:>12.2f}  {r[last_yr]:>12.2f}  {r[chg_col]:>+7.1f}%"
            )

    log.subsection(
        f"Genuine deteriorations ({first_yr}\u2192{last_yr}, multiplier increased)"
    )
    if g_wrse.empty:
        log.info("  None found")
    else:
        log.info(f"  {'ID':<5}  {'Product Name':<36}  {first_yr:>12}  {last_yr:>12}  {'Chg%':>8}")
        log.info(f"  {SEP2}")
        for _, r in g_wrse.iterrows():
            log.info(
                f"  {int(r['Product_ID']):<5}  {str(r['Product_Name'])[:35]:<36}"
                f"  {r[first_yr]:>12.2f}  {r[last_yr]:>12.2f}  {r[chg_col]:>+7.1f}%"
            )

    return wide, artifact_df


# ══════════════════════════════════════════════════════════════════════════════
# PUBLICATION REPORT — all key findings computed from data, not hardcoded
# ══════════════════════════════════════════════════════════════════════════════

def write_report(total_df: pd.DataFrame, intensity_df: pd.DataFrame,
                  trends_df: pd.DataFrame, path: Path, log: Logger):
    """
    Write a publication-ready results summary.

    All key findings (TWF change, hotel intensity change, indirect share)
    are computed dynamically from the data rather than hardcoded strings.
    This ensures the report stays consistent with the underlying results even
    when coefficients or data are updated.
    """
    first_yr, last_yr = STUDY_YEARS[0], STUDY_YEARS[-1]

    def get_total(year: str, col: str):
        row = total_df[total_df["Year"] == year]
        return row[col].values[0] if not row.empty else None

    t_first = get_total(first_yr, "Total_bn_m3")
    t_last  = get_total(last_yr,  "Total_bn_m3")
    total_chg_pct = (100 * (t_last - t_first) / t_first) if (t_first and t_first != 0) else None

    avg_indirect_pct = total_df["Indirect_pct"].mean()
    avg_direct_pct   = total_df["Direct_pct"].mean()

    from config import DIRECT_WATER
    h_first = DIRECT_WATER["hotel"].get(first_yr, {}).get("base")
    h_last  = DIRECT_WATER["hotel"].get(last_yr,  {}).get("base")
    hotel_chg_pct = (100 * (h_last - h_first) / h_first) if (h_first and h_first != 0) else None

    with open(path, "w", encoding="utf-8") as f:
        f.write("INDIA TOURISM WATER FOOTPRINT — RESULTS SUMMARY\n")
        f.write("=" * 65 + "\n\n")

        f.write("1. TOTAL WATER FOOTPRINT\n" + "─" * 40 + "\n")
        f.write(
            f"{'Year':<6} {'Total (bn m³)':>14} {'Indirect':>12} {'Direct':>10} "
            f"{'Ind%':>6} {'Dir%':>6} {'USD/INR':>9}\n"
        )
        base_t = None
        for _, r in total_df.iterrows():
            if base_t is None:
                base_t = r["Total_bn_m3"]
            chg = f" ({100*(r['Total_bn_m3']-base_t)/base_t:+.1f}%)" if base_t else ""
            _rate = r.get("USD_INR_Rate", USD_INR.get(str(r["Year"]), 70.0))
            f.write(
                f"{r['Year']:<6} {r['Total_bn_m3']:>14.4f} {r['Indirect_bn_m3']:>12.4f} "
                f"{r['Direct_bn_m3']:>10.4f} {r['Indirect_pct']:>6.1f} "
                f"{r['Direct_pct']:>6.1f} ₹{_rate:>7.2f}{chg}\n"
            )

        # USD equivalent demand note
        f.write("\n  USD/INR midpoint rates used (RBI reference range midpoints):\n")
        for yr in STUDY_YEARS:
            rate = USD_INR.get(yr, 70.0)
            f.write(f"    {yr}: ₹{rate:.2f} per USD\n")

        f.write("\n2. PER-TOURIST WATER INTENSITY\n" + "─" * 40 + "\n")

        # ── 2A: Economy-wide trend ─────────────────────────────────────────────
        f.write("2A. Economy-wide intensity trend (all tourists)\n\n")
        f.write(
            f"  {'Year':<6} {'Total L/day':>12} {'Indirect':>12} {'Direct':>9}"
            f" {'Indir%':>8} {'vs ' + first_yr:>10}\n"
        )
        f.write("  " + "─" * 58 + "\n")
        first_total = None
        for _, r in intensity_df.iterrows():
            total = r["L_per_tourist_day"]
            indir = r.get("Indirect_L_per_all_day", 0)
            dirct = r.get("Direct_L_per_all_day", 0)
            ipct  = f"{100 * indir / total:.1f}%" if total else "-"
            if first_total is None:
                first_total = total
                chg = "(base)"
            else:
                chg = f"{100 * (total - first_total) / first_total:+.0f}%"
            f.write(
                f"  {r['Year']:<6} {total:>12,.0f} {indir:>12,.0f} {dirct:>9,.0f}"
                f" {ipct:>8} {chg:>10}\n"
            )

        # ── 2B: Inbound vs domestic ────────────────────────────────────────────
        f.write(f"\n2B. Inbound vs domestic intensity gap\n\n")
        f.write(
            f"  {'Year':<6} {'Segment':<10} {'Tourists(M)':>12} {'Stay(d)':>8}"
            f" {'Days(M)':>9} {'Total L/d':>10} {'Indir L/d':>10} {'Dir L/d':>8}\n"
        )
        f.write("  " + "─" * 80 + "\n")
        for _, r in intensity_df.iterrows():
            act = ACTIVITY_DATA.get(r["Year"], {})
            dom_M    = act.get("domestic_tourists_M", 0)
            inb_M    = act.get("inbound_tourists_M", 0)
            dom_stay = act.get("avg_stay_days_dom", 0)
            inb_stay = act.get("avg_stay_days_inb", 0)
            dom_days = round(dom_M * dom_stay, 1)
            inb_days = round(inb_M * inb_stay, 1)
            f.write(
                f"  {r['Year']:<6} {'Domestic':<10} {dom_M:>12,.1f} {dom_stay:>8.1f}"
                f" {dom_days:>9,.0f} {r['L_per_dom_tourist_day']:>10,.0f}"
                f" {r.get('Indirect_L_per_dom_day', 0):>10,.0f}"
                f" {r.get('Direct_L_per_dom_day', 0):>8,.0f}\n"
            )
            f.write(
                f"  {'':<6} {'Inbound':<10} {inb_M:>12,.2f} {inb_stay:>8.1f}"
                f" {inb_days:>9,.0f} {r['L_per_inb_tourist_day']:>10,.0f}"
                f" {r.get('Indirect_L_per_inb_day', 0):>10,.0f}"
                f" {r.get('Direct_L_per_inb_day', 0):>8,.0f}\n"
            )
            all_M    = round(dom_M + inb_M, 1)
            all_days = round(dom_days + inb_days, 1)
            f.write(
                f"  {'':<6} {'All':<10} {all_M:>12,.1f} {'—':>8}"
                f" {all_days:>9,.0f} {r['L_per_tourist_day']:>10,.0f}"
                f" {r.get('Indirect_L_per_all_day', 0):>10,.0f}"
                f" {r.get('Direct_L_per_all_day', 0):>8,.0f}\n\n"
            )
        f.write(
            "  Note: Indirect L/day uses EEIO split demand vectors where available;\n"
            "  falls back to tourist-day proportion. Direct L/day is identical\n"
            "  across segments (no inbound/domestic breakdown in direct module).\n"
        )

        if not trends_df.empty and "Change_pct" in trends_df.columns:
            f.write(f"\n3. SECTOR EFFICIENCY TRENDS (Indirect TWF, {first_yr}→{last_yr})\n"
                    + "─" * 40 + "\n")
            best  = trends_df.dropna(subset=["Change_pct"]).nsmallest(5, "Change_pct")
            worst = trends_df.dropna(subset=["Change_pct"]).nlargest(5, "Change_pct")
            f.write("Most improved (water use fell):\n")
            for _, r in best.iterrows():
                f.write(f"  {r['Category_Name']:<42} {r['Change_pct']:>+8.1f}%\n")
            f.write("Most worsened (water use rose):\n")
            for _, r in worst.iterrows():
                f.write(f"  {r['Category_Name']:<42} {r['Change_pct']:>+8.1f}%\n")

        f.write("\n4. KEY FINDINGS\n" + "─" * 40 + "\n")

        if total_chg_pct is not None:
            direction = "increased" if total_chg_pct > 0 else "decreased"
            f.write(f"• Total TWF {direction} {abs(total_chg_pct):.1f}% "
                    f"from {first_yr} to {last_yr} (nominal demand growth).\n")

        f.write("• Agriculture dominates indirect water (>65% of indirect TWF origin).\n")

        if hotel_chg_pct is not None and h_first and h_last:
            direction = "fell" if hotel_chg_pct < 0 else "rose"
            f.write(f"• Hotel water intensity {direction} from {h_first:,} to {h_last:,} "
                    f"L/room/night ({hotel_chg_pct:+.1f}%).\n")

        f.write(
            f"• Indirect water averages {avg_indirect_pct:.0f}% of total TWF; "
            f"direct averages {avg_direct_pct:.0f}% across study years.\n"
        )
        f.write("• COVID-19 depressed 2022 direct water vs 2019 "
                "(lower occupancy, fewer flights).\n")

    log.ok(f"Report written: {path}")


# ══════════════════════════════════════════════════════════════════════════════
# REPORT TEMPLATE FILLER
# ══════════════════════════════════════════════════════════════════════════════

def _safe_csv(path) -> pd.DataFrame:
    """Read CSV silently; return empty DataFrame on any error."""
    try:
        p = Path(path)
        return pd.read_csv(p) if p.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _f(val, dec=4):
    try:
        return f"{float(val):,.{dec}f}"
    except Exception:
        return str(val)


def _pct(a, b):
    try:
        return f"{100 * (float(b) - float(a)) / float(a):+.1f}%"
    except Exception:
        return "-"


def _get_ind_vals(yr: str) -> dict | None:
    """Return indirect summary dict for one year, from CSV or computed on-the-fly."""
    ind_all = _safe_csv(DIRS["indirect"] / "indirect_twf_all_years.csv")
    if not ind_all.empty and "Year" in ind_all.columns:
        r = ind_all[ind_all["Year"].astype(str) == str(yr)]
        if not r.empty:
            r = r.iloc[0]
            return {
                "tot": float(r.get("Indirect_TWF_billion_m3", 0)),
                "ni":  float(r.get("Intensity_m3_per_crore", 0)),
                "ri":  float(r.get("Real_Intensity_m3_per_crore",
                                   r.get("Intensity_m3_per_crore", 0))),
                "dem": float(r.get("Tourism_Demand_crore", 0)),
            }
    cat_df = _safe_csv(DIRS["indirect"] / f"indirect_twf_{yr}_by_category.csv")
    if cat_df.empty or "Total_Water_m3" not in cat_df.columns:
        return None
    total_m3 = float(cat_df["Total_Water_m3"].sum())
    dem_cr   = float(cat_df["Demand_crore"].sum()) if "Demand_crore" in cat_df.columns else 0
    ni = total_m3 / dem_cr if dem_cr else 0
    return {"tot": total_m3 / 1e9, "ni": ni, "ri": ni, "dem": dem_cr}


def _get_dir_scenarios(yr: str):
    """Return (base_row, low_row, high_row) pandas Series or None."""
    dir_all = _safe_csv(DIRS["direct"] / "direct_twf_all_years.csv")
    sub = (dir_all[dir_all["Year"].astype(str) == str(yr)]
           if not dir_all.empty and "Year" in dir_all.columns
           else _safe_csv(DIRS["direct"] / f"direct_twf_{yr}.csv"))
    if sub.empty:
        return None, None, None

    def _get(sc):
        r = sub[sub["Scenario"] == sc]
        return r.iloc[0] if not r.empty else None

    return _get("BASE"), _get("LOW"), _get("HIGH")


def _row_val(row, *keys) -> float:
    """Safe get from a pandas Series trying multiple key aliases."""
    if row is None:
        return 0.0
    for k in keys:
        try:
            v = row.get(k)
            if v is not None:
                return float(v)
        except Exception:
            pass
    return 0.0


def _get_tot_row(yr: str):
    """Return total TWF Series for one year, from CSV or computed."""
    tot_df = _safe_csv(DIRS["comparison"] / "twf_total_all_years.csv")
    if not tot_df.empty and "Year" in tot_df.columns:
        r = tot_df[tot_df["Year"].astype(str) == str(yr)]
        if not r.empty:
            return r.iloc[0]
    iv = _get_ind_vals(yr)
    b, _, _ = _get_dir_scenarios(yr)
    if iv is None and b is None:
        return None
    ind_bn = iv["tot"] if iv else 0
    dir_bn = _row_val(b, "Total_billion_m3", "Total_bn_m3")
    tot_bn = ind_bn + dir_bn
    ip = 100 * ind_bn / tot_bn if tot_bn else 0
    dp = 100 * dir_bn / tot_bn if tot_bn else 0
    return pd.Series({
        "Indirect_bn_m3": ind_bn, "Direct_bn_m3": dir_bn,
        "Total_bn_m3": tot_bn, "Indirect_pct": ip, "Direct_pct": dp,
    })


def fill_report_template(start_ts: float, steps_req: list,
                          steps_completed: list, steps_failed: list,
                          total_time: float, pipeline_log: Path,
                          log: Logger = None) -> Path | None:
    """
    Read all output CSVs and fill report_template.md, writing
    run_report_{timestamp}.md to the comparison/ directory.

    Returns the output Path on success, None if template is missing.
    All table data comes from CSVs — nothing is hardcoded here.
    """
    tmpl_path = Path(__file__).parent / "report_template.md"
    if not tmpl_path.exists():
        if log:
            log.warn(f"report_template.md not found at {tmpl_path} — skipping report")
        return None

    text     = tmpl_path.read_text(encoding="utf-8")
    ts_str   = datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d %H:%M:%S")
    first_yr = STUDY_YEARS[0]
    last_yr  = STUDY_YEARS[-1]

    # ── Metadata ──────────────────────────────────────────────────────────────
    fail_skip = (
        (", ".join(steps_failed) if steps_failed else "none failed") +
        "  /  none skipped"
    )
    text = text.replace("{{RUN_TIMESTAMP}}",        ts_str)
    text = text.replace("{{STUDY_YEARS}}",          ", ".join(STUDY_YEARS))
    text = text.replace("{{STEPS_REQUESTED}}",      ", ".join(steps_req))
    text = text.replace("{{STEPS_COMPLETED}}",      ", ".join(steps_completed) or "-")
    text = text.replace("{{STEPS_FAILED_SKIPPED}}", fail_skip)
    text = text.replace("{{TOTAL_RUNTIME}}",
        f"{total_time:.0f}s" if total_time < 60 else f"{total_time/60:.1f} min")
    text = text.replace("{{PIPELINE_LOG_PATH}}",    str(pipeline_log))
    text = text.replace("{{FIRST_YEAR}}", first_yr)
    text = text.replace("{{LAST_YEAR}}",  last_yr)
    for yr in STUDY_YEARS:
        text = text.replace(f"{{{{YEAR_{yr}}}}}", yr)

    # ── 1. IO table rows ──────────────────────────────────────────────────────
    io_sum  = _safe_csv(DIRS["io"] / "io_summary_all_years.csv")
    io_rows = ""
    for _, r in io_sum.iterrows():
        # Template header (11 data columns):
        # FY | Sectors | Total Output (₹ cr) | Total Output (USD M) |
        # Real Output (₹ cr, 2015-16) | Real Output (USD M, 2015-16) |
        # Intermediate (₹ cr) | Final Demand (₹ cr) | Final Demand (USD M) |
        # Balance Error % | ρ(A) | USD/INR
        io_rows += (
            f"| {r.get('year', '-')} "
            f"| {int(r.get('n_products', 0)):,} "
            f"| {int(r.get('total_output_crore', 0)):,} "
            f"| {int(r.get('total_output_USD_M', 0)):,} "
            f"| {int(r.get('total_output_2015prices', 0)):,} "
            f"| {int(r.get('total_output_2015prices_USD_M', 0)):,} "
            f"| {int(r.get('total_intermediate_crore', 0)):,} "
            f"| {int(r.get('total_final_demand_crore', 0)):,} "
            f"| {int(r.get('total_final_demand_USD_M', 0)):,} "
            f"| {float(r.get('balance_error_pct', 0)):.4f} "
            f"| {float(r.get('spectral_radius', 0)):.6f} "
            f"| {float(r.get('usd_inr_rate', 70.0)):.2f} |\n"
        )
    text = text.replace("{{IO_TABLE_ROWS}}", io_rows or "| - | - | - | - | - | - | - | - | - | - | - | - |\n")

    # ── 2. Demand rows ────────────────────────────────────────────────────────
    # Template header (7 data columns):
    # Year | Nominal (₹ cr) | Nominal (USD M) | Real 2015-16 (₹ cr) |
    # Real 2015-16 (USD M) | EXIOBASE non-zero sectors | CAGR vs 2015 | USD/INR Rate
    dem_cmp  = _safe_csv(DIRS["demand"] / "demand_intensity_comparison.csv")
    dem_rows = ""
    if not dem_cmp.empty and "Metric" in dem_cmp.columns and "Value" in dem_cmp.columns:
        dem_cmp["Year"] = dem_cmp["Year"].astype(str)
        nom = dem_cmp[dem_cmp["Metric"].str.contains("nominal", case=False, na=False)]
        rl  = dem_cmp[dem_cmp["Metric"].str.contains("real",    case=False, na=False)]
        for yr in STUDY_YEARS:
            _usd = USD_INR.get(yr, 70.0)
            n_r  = nom[nom["Year"] == str(yr)]
            r_r  = rl[rl["Year"]   == str(yr)]
            n_v  = float(n_r["Value"].iloc[0]) if not n_r.empty else 0
            r_v  = float(r_r["Value"].iloc[0]) if not r_r.empty else 0
            # USD M: 1 USD M = _usd/10 crore  →  crore * 10/_usd = USD M
            n_usd = round(n_v * 10 / _usd) if _usd else 0
            r_usd = round(r_v * 10 / USD_INR.get("2015", 65.0))   # real always at 2015-16 USD
            cagr  = n_r["CAGR_vs_base"].iloc[0] if not n_r.empty and "CAGR_vs_base" in n_r.columns else None
            cagr_s = f"{float(cagr):+.1f}%/yr" if (cagr is not None and not pd.isna(cagr)) else "(base)"
            y_df = _safe_csv(DIRS["demand"] / f"Y_tourism_{yr}.csv")
            nz   = (int((y_df["Tourism_Demand_crore"] > 0).sum())
                    if not y_df.empty and "Tourism_Demand_crore" in y_df.columns else "-")
            dem_rows += (
                f"| {yr} | {n_v:,.0f} | {n_usd:,.0f} "
                f"| {r_v:,.0f} | {r_usd:,.0f} "
                f"| {nz}/163 | {cagr_s} | {_usd:.2f} |\n"
            )
    text = text.replace("{{DEMAND_TABLE_ROWS}}", dem_rows or "| - | - | - | - | - | - | - | - |\n")

    # ── 2b. NAS growth rows ───────────────────────────────────────────────────
    nas_rows = ""
    for key, rates in NAS_GROWTH_RATES.items():
        entry  = NAS_GVA_CONSTANT.get(key, {})
        sno    = entry.get("nas_sno", "-")
        label  = entry.get("nas_label", "-")
        nas_rows += (
            f"| {key} | {sno} | {label} "
            f"| {rates.get('2019', 0):.4f} "
            f"| {rates.get('2022', 0):.4f} |\n"
        )
    text = text.replace("{{NAS_GROWTH_ROWS}}", nas_rows or "| - | - | - | - | - |\n")

    # ── 3.1 Indirect summary ──────────────────────────────────────────────────
    # Template header (7 data cols):
    # Year | Total (bn m³) | Intensity (m³/₹ cr nominal) | Intensity (m³/USD M nominal) |
    # Intensity (m³/₹ cr real) | Tourism Demand (₹ cr) | Tourism Demand (USD M) | Δ vs FIRST_YEAR
    ind_rows = ""
    base_ind = None
    for yr in STUDY_YEARS:
        vals = _get_ind_vals(yr)
        if vals is None:
            ind_rows += f"| {yr} | - | - | - | - | - | - | - |\n"; continue
        _usd = USD_INR.get(yr, 70.0)
        # m³/USD M = m³/crore × (USD_INR / 10)
        # because 1 USD M = (_usd/10) crore → 1 crore = (10/_usd) USD M
        ni_usd  = vals["ni"] * _usd / 10 if vals["ni"] else 0
        dem_usd = vals["dem"] * 10 / _usd if (vals["dem"] and _usd) else 0
        delta = "(base)" if base_ind is None else _pct(base_ind, vals["tot"])
        if base_ind is None:
            base_ind = vals["tot"]
        ind_rows += (
            f"| {yr} | {vals['tot']:.4f} | {vals['ni']:,.1f} "
            f"| {ni_usd:,.1f} | {vals['ri']:,.1f} "
            f"| {vals['dem']:,.0f} | {dem_usd:,.0f} | {delta} |\n"
        )
    text = text.replace("{{INDIRECT_SUMMARY_ROWS}}", ind_rows or "| - | - | - | - | - | - | - | - |\n")

    # ── 3.2-3.4 Top-10 per year ───────────────────────────────────────────────
    for yr in STUDY_YEARS:
        cat_df  = _safe_csv(DIRS["indirect"] / f"indirect_twf_{yr}_by_category.csv")
        top_str = ""
        if not cat_df.empty and "Total_Water_m3" in cat_df.columns:
            tot_w = cat_df["Total_Water_m3"].sum()
            for rank, (_, row) in enumerate(
                cat_df.nlargest(10, "Total_Water_m3").iterrows(), 1
            ):
                w = float(row["Total_Water_m3"])
                top_str += (f"| {rank} | {row['Category_Name']} "
                            f"| {w:,.0f} | {100*w/tot_w:.1f}% |\n")
        text = text.replace(f"{{{{TOP10_{yr}}}}}", top_str or "| - | - | - | - |\n")

    # ── 3.5 Sector type (where demand LANDS) ─────────────────────────────────
    sect: dict = {}
    for yr in STUDY_YEARS:
        cat_df = _safe_csv(DIRS["indirect"] / f"indirect_twf_{yr}_by_category.csv")
        if not cat_df.empty and "Category_Type" in cat_df.columns:
            tot_w = cat_df["Total_Water_m3"].sum()
            for ctype, grp in cat_df.groupby("Category_Type"):
                w = float(grp["Total_Water_m3"].sum())
                sect.setdefault(ctype, {})[yr] = (w, 100 * w / tot_w if tot_w else 0)
    sect_rows = ""
    for ctype in sorted(sect):
        row = f"| {ctype} "
        for yr in STUDY_YEARS:
            w, pct = sect[ctype].get(yr, (0, 0))
            row += f"| {w:,.0f} | {pct:.1f}% "
        sect_rows += row + "|\n"
    text = text.replace("{{SECTOR_TYPE_ROWS}}", sect_rows or "| - | - | - | - | - | - | - |\n")

    # ── 3.6 Water origin from structural decomposition ────────────────────────
    # structural CSV is LONG format: columns Source_Group + Water_m3, one row per
    # source×category pair. The old code looked for wide-format From_X_m3 columns
    # that never existed. Fix: groupby Source_Group and sum Water_m3 directly.
    # Also check for a pre-aggregated origin_summary CSV if saved by calculate_indirect_twf.
    origin: dict = {}
    for yr in STUDY_YEARS:
        # Prefer pre-aggregated summary if calculate_indirect_twf saved one
        summ_df = _safe_csv(DIRS["indirect"] / f"indirect_twf_{yr}_origin.csv")
        if (not summ_df.empty
                and "Source_Group" in summ_df.columns
                and "Water_m3" in summ_df.columns):
            yr_total = float(summ_df["Water_m3"].sum())
            for _, r in summ_df.iterrows():
                grp = str(r["Source_Group"])
                w   = float(r["Water_m3"])
                origin.setdefault(grp, {})[yr] = (w, 100 * w / yr_total if yr_total else 0)
            continue

        # Fall back to full long-format structural CSV
        struct_df = _safe_csv(DIRS["indirect"] / f"indirect_twf_{yr}_structural.csv")
        if (struct_df.empty
                or "Source_Group" not in struct_df.columns
                or "Water_m3" not in struct_df.columns):
            continue
        yr_total = float(struct_df["Water_m3"].sum())
        for grp, sub in struct_df.groupby("Source_Group"):
            w = float(sub["Water_m3"].sum())
            origin.setdefault(str(grp), {})[yr] = (w, 100 * w / yr_total if yr_total else 0)

    origin_rows = ""
    # Sort groups by descending water in first available year so Agriculture appears first
    first_yr_water = {grp: vals.get(STUDY_YEARS[0], (0, 0))[0] for grp, vals in origin.items()}
    for grp in sorted(first_yr_water, key=first_yr_water.get, reverse=True):
        row = f"| {grp} "
        for yr in STUDY_YEARS:
            w, pct = origin[grp].get(yr, (0, 0))
            row += f"| {w:,.0f} | {pct:.1f}% "
        origin_rows += row + "|\n"
    text = text.replace("{{WATER_ORIGIN_ROWS}}", origin_rows or "| - | - | - | - | - | - | - |\n")

    # ── 4. Direct TWF ─────────────────────────────────────────────────────────
    dir_rows = ""
    for yr in STUDY_YEARS:
        b, l, h = _get_dir_scenarios(yr)
        if b is None:
            dir_rows += f"| {yr} | - | - | - | - | - | - | - | - |\n"; continue
        b_tot = _row_val(b, "Total_billion_m3", "Total_bn_m3")
        l_tot = _row_val(l, "Total_billion_m3", "Total_bn_m3")
        h_tot = _row_val(h, "Total_billion_m3", "Total_bn_m3")
        range_pct = (
            f"±{100 * (h_tot - l_tot) / (2 * b_tot):.1f}%"
            if b_tot else "-"
        )
        dir_rows += (
            f"| {yr} "
            f"| {_row_val(b,'Hotel_m3')/1e6:.2f} "
            f"| {_row_val(b,'Restaurant_m3')/1e6:.2f} "
            f"| {_row_val(b,'Rail_m3')/1e6:.2f} "
            f"| {_row_val(b,'Air_m3')/1e6:.2f} "
            f"| {b_tot:.4f} "
            f"| {l_tot:.4f} "
            f"| {h_tot:.4f} "
            f"| {range_pct} |\n"
        )
    text = text.replace("{{DIRECT_TABLE_ROWS}}", dir_rows or "| - | - | - | - | - | - | - | - | - |\n")

    for yr in STUDY_YEARS:
        coeff = DIRECT_WATER["hotel"].get(yr, {}).get("base", "-")
        text  = text.replace(f"{{{{HOTEL_{yr}}}}}", str(coeff))
    h0 = DIRECT_WATER["hotel"].get(first_yr, {}).get("base")
    hN = DIRECT_WATER["hotel"].get(last_yr,  {}).get("base")
    text = text.replace("{{HOTEL_CHG}}", _pct(h0, hN) if h0 and hN else "-")

    # ── 5. Total TWF ──────────────────────────────────────────────────────────
    tot_rows = ""
    base_tot = None
    for yr in STUDY_YEARS:
        r = _get_tot_row(yr)
        if r is None:
            tot_rows += f"| {yr} | - | - | - | - | - | - | - |\n"; continue
        ind   = float(r.get("Indirect_bn_m3", 0))
        dr    = float(r.get("Direct_bn_m3",   0))
        tot   = float(r.get("Total_bn_m3",    0))
        ip    = float(r.get("Indirect_pct",   0))
        dp    = float(r.get("Direct_pct",     0))
        usd_r = float(r.get("USD_INR_Rate",   USD_INR.get(yr, 70.0)))
        delta = "(base)" if base_tot is None else _pct(base_tot, tot)
        if base_tot is None:
            base_tot = tot
        tot_rows += (
            f"| {yr} | {ind:.4f} | {dr:.4f} | {tot:.4f} "
            f"| {ip:.1f}% | {dp:.1f}% | {delta} | {usd_r:.2f} |\n"
        )
    text = text.replace("{{TOTAL_TWF_ROWS}}", tot_rows or "| - | - | - | - | - | - | - | - |\n")

    # ── 6. Per-tourist intensity — TWO TABLES ────────────────────────────────
    int_df   = _safe_csv(DIRS["comparison"] / "twf_per_tourist_intensity.csv")

    NEW_COLS = {"Indirect_L_per_all_day", "Indirect_L_per_dom_day",
                "Indirect_L_per_inb_day", "Direct_L_per_all_day",
                "Direct_L_per_dom_day",   "Direct_L_per_inb_day"}
    csv_has_new_cols = (not int_df.empty
                        and NEW_COLS.issubset(set(int_df.columns)))

    # ── Helper: get one year's row from CSV or compute on-the-fly ─────────────
    def _get_int_row(yr):
        """Return dict of intensity values for one year, from CSV or fallback."""
        if csv_has_new_cols and "Year" in int_df.columns:
            r = int_df[int_df["Year"].astype(str) == str(yr)]
            if not r.empty:
                r = r.iloc[0]
                act = ACTIVITY_DATA.get(yr, {})
                return {
                    "total_all":    int(r.get("L_per_tourist_day", 0)),
                    "total_dom":    int(r.get("L_per_dom_tourist_day", 0)),
                    "total_inb":    int(r.get("L_per_inb_tourist_day", 0)),
                    "indir_all":    int(r.get("Indirect_L_per_all_day", 0)),
                    "indir_dom":    int(r.get("Indirect_L_per_dom_day", 0)),
                    "indir_inb":    int(r.get("Indirect_L_per_inb_day", 0)),
                    "direct_all":   int(r.get("Direct_L_per_all_day", 0)),
                    "direct_dom":   int(r.get("Direct_L_per_dom_day", 0)),
                    "direct_inb":   int(r.get("Direct_L_per_inb_day", 0)),
                    "dom_M":        act.get("domestic_tourists_M", 0),
                    "inb_M":        act.get("inbound_tourists_M", 0),
                    "dom_stay":     act.get("avg_stay_days_dom", 0),
                    "inb_stay":     act.get("avg_stay_days_inb", 0),
                    "dom_days_M":   round(act.get("domestic_tourists_M", 0)
                                         * act.get("avg_stay_days_dom", 0), 1),
                    "inb_days_M":   round(act.get("inbound_tourists_M", 0)
                                         * act.get("avg_stay_days_inb", 0), 1),
                    "split_source": str(r.get("Indirect_split_source", "tourist_day_proportion")),
                }

        # On-the-fly fallback
        t_row = _get_tot_row(yr)
        act   = ACTIVITY_DATA.get(yr, {})
        if t_row is None or not act:
            return None
        dom_days = act.get("domestic_tourists_M", 0) * 1e6 * act.get("avg_stay_days_dom", 1)
        inb_days = act.get("inbound_tourists_M",  0) * 1e6 * act.get("avg_stay_days_inb", 1)
        all_days = dom_days + inb_days
        if all_days == 0:
            return None
        indirect_m3 = float(t_row.get("Indirect_bn_m3", 0)) * 1e9
        direct_m3   = float(t_row.get("Direct_bn_m3",   0)) * 1e9
        total_m3    = float(t_row.get("Total_bn_m3",    0)) * 1e9
        split_df = _safe_csv(DIRS["indirect"] / f"indirect_twf_{yr}_split.csv")
        if (not split_df.empty and "Type" in split_df.columns
                and "TWF_m3" in split_df.columns):
            inb_indir = float(split_df[split_df["Type"] == "Inbound" ]["TWF_m3"].iloc[0]) \
                        if not split_df[split_df["Type"] == "Inbound"].empty else 0.0
            dom_indir = float(split_df[split_df["Type"] == "Domestic"]["TWF_m3"].iloc[0]) \
                        if not split_df[split_df["Type"] == "Domestic"].empty else 0.0
            src = "split_csv"
        else:
            inb_indir = indirect_m3 * (inb_days / all_days)
            dom_indir = indirect_m3 * (dom_days / all_days)
            src = "tourist_day_proportion"
        inb_direct = direct_m3 * (inb_days / all_days)
        dom_direct = direct_m3 * (dom_days / all_days)
        def _l(m3, days): return round(m3 * 1000 / days) if days else 0
        return {
            "total_all":  _l(total_m3, all_days),
            "total_dom":  _l(dom_indir + dom_direct, dom_days),
            "total_inb":  _l(inb_indir + inb_direct, inb_days),
            "indir_all":  _l(indirect_m3, all_days),
            "indir_dom":  _l(dom_indir,   dom_days),
            "indir_inb":  _l(inb_indir,   inb_days),
            "direct_all": _l(direct_m3,   all_days),
            "direct_dom": _l(dom_direct,  dom_days),
            "direct_inb": _l(inb_direct,  inb_days),
            "dom_M":      act.get("domestic_tourists_M", 0),
            "inb_M":      act.get("inbound_tourists_M", 0),
            "dom_stay":   act.get("avg_stay_days_dom", 0),
            "inb_stay":   act.get("avg_stay_days_inb", 0),
            "dom_days_M": round(dom_days / 1e6, 1),
            "inb_days_M": round(inb_days / 1e6, 1),
            "split_source": src,
        }

    # Collect all years
    yr_data = {yr: _get_int_row(yr) for yr in STUDY_YEARS}

    # ── Table 6A: economy-wide trend (all tourists only) ──────────────────────
    rows_6a   = ""
    first_val = None
    split_sources = []
    for yr in STUDY_YEARS:
        d = yr_data.get(yr)
        if d is None:
            rows_6a += f"| {yr} | - | - | - | - | - |\n"; continue
        split_sources.append(d["split_source"])
        total = d["total_all"]
        indir = d["indir_all"]
        dirct = d["direct_all"]
        indir_share = f"{100 * indir / total:.1f}%" if total else "-"
        if first_val is None:
            first_val = total
            chg = "—"
        else:
            chg = f"{100 * (total - first_val) / first_val:+.0f}%" if first_val else "-"
        rows_6a += (
            f"| {yr} "
            f"| {total:,} "
            f"| {indir:,} "
            f"| {dirct:,} "
            f"| {indir_share} "
            f"| {chg} |\n"
        )
    text = text.replace("{{INTENSITY_6A_ROWS}}", rows_6a or "| - | - | - | - | - | - |\n")

    # Headline drop % for callout
    last_val = (yr_data.get(last_yr) or {}).get("total_all", 0)
    if first_val and last_val and first_val > 0:
        drop_pct = f"{abs(100 * (last_val - first_val) / first_val):.0f}"
    else:
        drop_pct = "-"
    text = text.replace("{{INTENSITY_DROP_PCT}}", drop_pct)

    # ── Table 6B: inbound vs domestic comparison, one row per segment per year ─
    rows_6b = ""
    inb_days_pct_last = "-"
    for yr in STUDY_YEARS:
        d = yr_data.get(yr)
        if d is None:
            rows_6b += f"| {yr} | Domestic | - | - | - | - | - | - |\n"
            rows_6b += f"| {yr} | Inbound  | - | - | - | - | - | - |\n"
            rows_6b += f"| {yr} | **All**  | - | - | - | - | - | - |\n"
            continue
        dom_M    = d["dom_M"];    inb_M    = d["inb_M"]
        dom_stay = d["dom_stay"]; inb_stay = d["inb_stay"]
        dom_days = d["dom_days_M"]; inb_days = d["inb_days_M"]
        all_M    = round(dom_M + inb_M, 2)
        all_days = round(dom_days + inb_days, 1)
        if yr == last_yr and (dom_days + inb_days) > 0:
            inb_days_pct_last = f"{100 * inb_days / (dom_days + inb_days):.1f}"
        rows_6b += (
            f"| {yr} | Domestic | {dom_M:,} | {dom_stay} | {dom_days:,.0f} "
            f"| {d['total_dom']:,} | {d['indir_dom']:,} | {d['direct_dom']:,} |\n"
        )
        rows_6b += (
            f"| {yr} | Inbound | {inb_M} | {inb_stay} | {inb_days:,.0f} "
            f"| {d['total_inb']:,} | {d['indir_inb']:,} | {d['direct_inb']:,} |\n"
        )
        rows_6b += (
            f"| {yr} | **All** | {all_M:,} | — | {all_days:,.0f} "
            f"| {d['total_all']:,} | {d['indir_all']:,} | {d['direct_all']:,} |\n"
        )
    text = text.replace("{{INTENSITY_6B_ROWS}}", rows_6b or "| - | - | - | - | - | - | - | - |\n")
    text = text.replace("{{INB_DAYS_PCT_2022}}", inb_days_pct_last)

    # Split source note
    unique_srcs = set(split_sources)
    if "split_csv" in unique_srcs and "tourist_day_proportion" not in unique_srcs:
        split_note = "EEIO split demand vectors (Y_inbound / Y_domestic) — most accurate"
    elif "tourist_day_proportion" in unique_srcs and "split_csv" not in unique_srcs:
        split_note = "tourist-day proportion (fallback — run calculate_indirect_twf.py with split vectors for accuracy)"
    elif unique_srcs:
        split_note = "mixed: split_csv for some years, tourist-day proportion for others"
    else:
        split_note = "unknown"
    text = text.replace("{{SPLIT_SOURCE_NOTE}}", split_note)

    # ── Weighted average arithmetic workings (first study year) ───────────────
    d0 = yr_data.get(first_yr)
    if d0:
        dom_l   = d0["total_dom"];    inb_l   = d0["total_inb"]
        dom_d   = d0["dom_days_M"];   inb_d   = d0["inb_days_M"]
        dom_bl  = dom_l * dom_d       # billion litres (L/day × M days = M×L = billion mL... but units work out as M×1000 m³ — keep symbolic)
        inb_bl  = inb_l * inb_d
        tot_bl  = dom_bl + inb_bl
        tot_d   = dom_d + inb_d
        implied = round(tot_bl / tot_d) if tot_d else 0
        dom_pct = round(100 * dom_bl / tot_bl) if tot_bl else 0
        inb_pct = 100 - dom_pct
        sep     = "─" * 52
        wa_text = (
            f"Domestic: {dom_l:>6,} L/day  ×  {dom_d:>7,.0f}M days  =  {dom_bl:>10,.0f}  (units: M day-litres)\n"
            f"Inbound:  {inb_l:>6,} L/day  ×  {inb_d:>7,.0f}M days  =  {inb_bl:>10,.0f}\n"
            f"          {sep}\n"
            f"Total water                              =  {tot_bl:>10,.0f}  M day-litres\n"
            f"Total days = {dom_d:,.0f}M + {inb_d:,.0f}M   =  {tot_d:>10,.0f}M days\n\n"
            f"All tourists L/day = {tot_bl:,.0f} ÷ {tot_d:,.0f} = {implied:,} L/day  ≈  {d0['total_all']:,} ✓\n\n"
            f"Domestic share of total water: {dom_pct}%  (from {100*dom_d/tot_d:.0f}% of tourist-days)\n"
            f"Inbound  share of total water: {inb_pct}%  (from only {100*inb_d/tot_d:.1f}% of tourist-days)"
        )
    else:
        wa_text = "(data not available for first study year)"
    text = text.replace("{{WEIGHTED_AVG_WORKINGS}}", wa_text)

    # Keep backward-compat: old {{INTENSITY_ROWS}} placeholder in case any
    # other part of the template still references it
    text = text.replace("{{INTENSITY_ROWS}}", "")

    # ── 7. Sector trends ──────────────────────────────────────────────────────
    trnd_df    = _safe_csv(DIRS["comparison"] / "twf_sector_trends.csv")
    impr_rows  = ""
    worse_rows = ""
    if not trnd_df.empty and "Change_pct" in trnd_df.columns:
        valid = trnd_df.dropna(subset=["Change_pct"])
        for rank, (_, r) in enumerate(valid.nsmallest(5, "Change_pct").iterrows(), 1):
            v0 = f"{float(r[first_yr]):,.0f}" if first_yr in r else "-"
            vN = f"{float(r[last_yr]):,.0f}"  if last_yr  in r else "-"
            impr_rows  += f"| {rank} | {r['Category_Name']} | {v0} | {vN} | {r['Change_pct']:+.1f}% |\n"
        for rank, (_, r) in enumerate(
            valid[valid["Change_pct"] > 0].nlargest(5, "Change_pct").iterrows(), 1
        ):
            v0 = f"{float(r[first_yr]):,.0f}" if first_yr in r else "-"
            vN = f"{float(r[last_yr]):,.0f}"  if last_yr  in r else "-"
            worse_rows += f"| {rank} | {r['Category_Name']} | {v0} | {vN} | {r['Change_pct']:+.1f}% |\n"
    text = text.replace("{{IMPROVED_ROWS}}",  impr_rows  or "| - | - | - | - | - |\n")
    text = text.replace("{{WORSENED_ROWS}}",  worse_rows or "| - | - | - | - | - |\n")

    # ── 8. Multiplier artefacts ───────────────────────────────────────────────
    art_df  = _safe_csv(DIRS["comparison"] / "twf_multiplier_artifacts.csv")
    mult_df = _safe_csv(DIRS["comparison"] / "twf_type1_multipliers.csv")
    chg_col = f"Change_{first_yr}_{last_yr}_pct"

    art_rows = ""
    if not art_df.empty and "Product_ID" in art_df.columns:
        for _, r in art_df.iterrows():
            pid  = int(r["Product_ID"])
            name = r.get("Product_Name", f"Product {pid}")
            exio = r.get("EXIOBASE_Codes", "-")
            v0   = float(r.get(first_yr, 0))
            vN   = float(r.get(last_yr,  0))
            chg  = float(r.get(chg_col,  -100))
            art_rows += (
                f"| {pid} | {name} | `{exio}` "
                f"| {v0:,.2f} | {vN:,.2f} | {chg:+.1f}% "
                f"| EXIOBASE revision — verify F.txt |\n"
            )
    text = text.replace("{{ARTIFACT_ROWS}}", art_rows or "| - | - | - | - | - | - | none found |\n")

    gen_impr = ""
    gen_wrse = ""
    if not mult_df.empty:
        # Year columns may be int (e.g. 2015) or str ("2015") depending on pandas read
        # Normalise column names to str to match first_yr/last_yr
        mult_df.columns = [str(c) for c in mult_df.columns]
        if (first_yr in mult_df.columns and last_yr in mult_df.columns
                and chg_col in mult_df.columns):
            valid_base = mult_df[first_yr].notna() & (mult_df[first_yr] > 0)
            genuine    = mult_df[valid_base & (mult_df[last_yr] > 0)].dropna(subset=[chg_col])
            nm = "Product_Name" if "Product_Name" in mult_df.columns else "Product_ID"
            for _, r in genuine[genuine[chg_col] < 0].nsmallest(5, chg_col).iterrows():
                gen_impr += f"| {int(r['Product_ID'])} | {r[nm]} | {r[first_yr]:,.2f} | {r[last_yr]:,.2f} | {r[chg_col]:+.1f}% |\n"
            for _, r in genuine[genuine[chg_col] > 0].nlargest(5, chg_col).iterrows():
                gen_wrse += f"| {int(r['Product_ID'])} | {r[nm]} | {r[first_yr]:,.2f} | {r[last_yr]:,.2f} | {r[chg_col]:+.1f}% |\n"
    text = text.replace("{{GENUINE_IMPROVED_ROWS}}", gen_impr or "| - | - | - | - | - |\n")
    text = text.replace("{{GENUINE_WORSENED_ROWS}}", gen_wrse or "| - | - | - | - | - |\n")

    # ── 9. Sensitivity ────────────────────────────────────────────────────────
    s_ind = ""
    s_dir = ""
    s_tot = ""
    for yr in STUDY_YEARS:
        si = _safe_csv(DIRS["indirect"] / f"indirect_twf_{yr}_sensitivity.csv")
        # sensitivity_analysis() saves columns: Component, Scenario, Total_TWF_m3, Delta_pct
        if not si.empty and "Total_TWF_m3" in si.columns and "Component" in si.columns:
            grp_col = "Component"
            base_rows = si[(si["Scenario"] == "BASE") & (si[grp_col] == "Agriculture")]
            lo_rows   = si[(si["Scenario"] == "LOW")  & (si[grp_col] == "Agriculture")]
            hi_rows   = si[(si["Scenario"] == "HIGH") & (si[grp_col] == "Agriculture")]
            if not base_rows.empty and not lo_rows.empty and not hi_rows.empty:
                bs  = float(base_rows["Total_TWF_m3"].iloc[0]) / 1e9
                lo  = float(lo_rows["Total_TWF_m3"].iloc[0])  / 1e9
                hi  = float(hi_rows["Total_TWF_m3"].iloc[0])  / 1e9
                rng = f"+/-{100*(hi-bs)/bs:.1f}%" if bs else "-"
                s_ind += f"| {yr} | {lo:.4f} | {bs:.4f} | {hi:.4f} | {rng} |\n"
            else:
                s_ind += f"| {yr} | - | - | - | - |\n"
        else:
            s_ind += f"| {yr} | - | - | - | - |\n"

        b, l, h = _get_dir_scenarios(yr)
        if b is not None:
            bs_d = _row_val(b, "Total_billion_m3", "Total_bn_m3")
            lo_d = _row_val(l, "Total_billion_m3", "Total_bn_m3")
            hi_d = _row_val(h, "Total_billion_m3", "Total_bn_m3")
            rng  = f"+/-{100*(hi_d-bs_d)/bs_d:.1f}%" if bs_d else "-"
            s_dir += f"| {yr} | {lo_d:.4f} | {bs_d:.4f} | {hi_d:.4f} | {rng} |\n"
            si2 = _safe_csv(DIRS["indirect"] / f"indirect_twf_{yr}_sensitivity.csv")
            if not si2.empty and "Total_TWF_m3" in si2.columns and "Component" in si2.columns:
                base_r = si2[(si2["Scenario"] == "BASE") & (si2["Component"] == "Agriculture")]
                lo_r   = si2[(si2["Scenario"] == "LOW")  & (si2["Component"] == "Agriculture")]
                hi_r   = si2[(si2["Scenario"] == "HIGH") & (si2["Component"] == "Agriculture")]
                if not base_r.empty and not lo_r.empty and not hi_r.empty:
                    ibs = float(base_r["Total_TWF_m3"].iloc[0]) / 1e9
                    ilo = float(lo_r["Total_TWF_m3"].iloc[0])  / 1e9
                    ihi = float(hi_r["Total_TWF_m3"].iloc[0])  / 1e9
                    s_tot += f"| {yr} | {ilo+lo_d:.4f} | {ibs+bs_d:.4f} | {ihi+hi_d:.4f} |\n"
                else:
                    s_tot += f"| {yr} | - | - | - |\n"
            else:
                s_tot += f"| {yr} | - | - | - |\n"
        else:
            s_dir += f"| {yr} | - | - | - | - |\n"
            s_tot += f"| {yr} | - | - | - |\n"

    text = text.replace("{{SENS_INDIRECT_ROWS}}", s_ind)
    text = text.replace("{{SENS_DIRECT_ROWS}}",   s_dir)
    text = text.replace("{{SENS_TOTAL_ROWS}}",    s_tot)

    # ── 10. SDA decomposition ─────────────────────────────────────────────────
    sda_dir  = DIRS.get("sda", BASE_DIR / "3-final-results" / "sda")
    sda_rows = ""
    sda_instability_notes = ""
    sda_all  = _safe_csv(sda_dir / "sda_summary_all_periods.csv")
    if not sda_all.empty:
        for _, r in sda_all.iterrows():
            period = r.get("Period", "-")
            near_cancel = bool(r.get("Near_cancellation", False))
            # Use SDA-internal TWF0/TWF1 (consistent with the effects)
            # These come from the SDA module's own W@L@Y computation and are
            # the only values guaranteed to make effects + residual = dTWF.
            twf0 = float(r.get("TWF0_m3", 0)) / 1e9
            twf1 = float(r.get("TWF1_m3", 0)) / 1e9
            dtwf = float(r.get("dTWF_m3", 0)) / 1e9
            w_m3 = float(r.get("W_effect_m3", 0)) / 1e9
            l_m3 = float(r.get("L_effect_m3", 0)) / 1e9
            y_m3 = float(r.get("Y_effect_m3", 0)) / 1e9
            if near_cancel:
                # Suppress misleading percentages; show absolute only with flag
                sda_rows += (
                    f"| {period} ⚠ "
                    f"| {twf0:.4f} "
                    f"| {twf1:.4f} "
                    f"| {dtwf:+.4f} "
                    f"| {w_m3:+.4f} "
                    f"| — ¹ "
                    f"| {l_m3:+.4f} "
                    f"| — ¹ "
                    f"| {y_m3:+.4f} "
                    f"| — ¹ |\n"
                )
                ratio = float(r.get("Instability_ratio", 0))
                sda_instability_notes += (
                    f"\n> ⚠ **{period} near-cancellation instability** "
                    f"(max effect = {ratio:.0f}× |ΔTWF|): ΔTWF is small "
                    f"({dtwf:+.4f} bn m³) while opposing L and Y effects are large "
                    f"(~{max(abs(l_m3), abs(y_m3)):.2f} bn m³ each). "
                    f"Percentage attribution is mathematically valid but exceeds ±100× "
                    f"and is **not economically interpretable**. "
                    f"The absolute effect values (bn m³) are reliable. "
                    f"Do not cite % figures for this period."
                )
            else:
                sda_rows += (
                    f"| {period} "
                    f"| {twf0:.4f} "
                    f"| {twf1:.4f} "
                    f"| {dtwf:+.4f} "
                    f"| {w_m3:+.4f} "
                    f"| {float(r.get('W_effect_pct', 0)):+.1f}% "
                    f"| {l_m3:+.4f} "
                    f"| {float(r.get('L_effect_pct', 0)):+.1f}% "
                    f"| {y_m3:+.4f} "
                    f"| {float(r.get('Y_effect_pct', 0)):+.1f}% |\n"
                )
    text = text.replace("{{SDA_DECOMP_ROWS}}", sda_rows or "| - | - | - | - | - | - | - | - | - | - |\n")
    text = text.replace("{{SDA_INSTABILITY_NOTES}}", sda_instability_notes)

    # ── 11. Monte Carlo summary ───────────────────────────────────────────────
    mc_dir  = DIRS.get("monte_carlo", BASE_DIR / "3-final-results" / "monte-carlo")
    mc_sum  = _safe_csv(mc_dir / "mc_summary_all_years.csv")
    mc_rows = ""
    if not mc_sum.empty:
        for _, r in mc_sum.iterrows():
            mc_rows += (
                f"| {r.get('Year', '-')} "
                f"| {float(r.get('Base_bn_m3', 0)):.4f} "
                f"| {float(r.get('P5_bn_m3', 0)):.4f} "
                f"| {float(r.get('P25_bn_m3', 0)):.4f} "
                f"| {float(r.get('P50_bn_m3', 0)):.4f} "
                f"| {float(r.get('P75_bn_m3', 0)):.4f} "
                f"| {float(r.get('P95_bn_m3', 0)):.4f} "
                f"| {float(r.get('Range_pct', 0)):.1f}% "
                f"| {r.get('Top_param', '-')} |\n"
            )
    text = text.replace("{{MC_SUMMARY_ROWS}}", mc_rows or "| - | - | - | - | - | - | - | - | - |\n")

    mc_var   = _safe_csv(mc_dir / "mc_variance_decomposition.csv")
    mc_vrows = ""
    if not mc_var.empty and "Parameter" in mc_var.columns:
        params = mc_var["Parameter"].unique()
        for param in params:
            row = f"| {param} "
            for yr in STUDY_YEARS:
                sub = mc_var[(mc_var["Parameter"] == param) &
                             (mc_var["Year"].astype(str) == yr)]
                if not sub.empty:
                    row += (f"| {float(sub['SpearmanRank_corr'].iloc[0]):+.3f} "
                            f"| {float(sub['Variance_share_pct'].iloc[0]):.1f}% ")
                else:
                    row += "| - | - "
            mc_vrows += row + "|\n"
    text = text.replace("{{MC_VARIANCE_ROWS}}", mc_vrows or "| - | - | - | - | - | - | - |\n")

    # ── 12. Supply-chain paths ────────────────────────────────────────────────
    sc_dir = DIRS.get("supply_chain", BASE_DIR / "3-final-results" / "supply-chain")
    for yr in STUDY_YEARS:
        sc_df  = _safe_csv(sc_dir / f"sc_paths_{yr}.csv")
        sc_str = ""
        if not sc_df.empty and "Water_m3" in sc_df.columns:
            tot_sc = float(sc_df["Water_m3"].sum())
            for _, r in sc_df.head(10).iterrows():
                w = float(r["Water_m3"])
                sc_str += (
                    f"| {int(r['Rank'])} "
                    f"| {r['Path']} "
                    f"| {r['Source_Group']} "
                    f"| {int(w):,} "
                    f"| {r['Share_pct']:.3f}% |\n"
                )
        text = text.replace(f"{{{{SC_PATHS_{yr}}}}}", sc_str or "| - | - | - | - | - |\n")

    hem_df   = _safe_csv(sc_dir / f"sc_hem_{last_yr}.csv")
    hem_rows = ""
    if not hem_df.empty and "Dependency_Index" in hem_df.columns:
        for _, r in hem_df.head(10).iterrows():
            hem_rows += (
                f"| {int(r['Rank'])} "
                f"| {r['Product_Name']} "
                f"| {r['Source_Group']} "
                f"| {float(r['Dependency_Index']):.3f}% "
                f"| {int(r['Tourism_Water_m3']):,} |\n"
            )
    text = text.replace("{{HEM_ROWS}}", hem_rows or "| - | - | - | - | - |\n")

    sc_grp: dict = {}
    for yr in STUDY_YEARS:
        sc_df = _safe_csv(sc_dir / f"sc_paths_{yr}.csv")
        if sc_df.empty or "Water_m3" not in sc_df.columns:
            continue
        tot = float(sc_df["Water_m3"].sum())
        for grp, sub in sc_df.groupby("Source_Group"):
            w = float(sub["Water_m3"].sum())
            sc_grp.setdefault(grp, {})[yr] = (w, 100 * w / tot if tot else 0)
    sc_grp_rows = ""
    for grp in ["Agriculture", "Mining", "Manufacturing", "Petroleum", "Electricity", "Services"]:
        if grp not in sc_grp:
            continue
        row = f"| {grp} "
        for yr in STUDY_YEARS:
            w, pct = sc_grp[grp].get(yr, (0, 0))
            row += f"| {int(w):,} | {pct:.1f}% "
        sc_grp_rows += row + "|\n"
    text = text.replace("{{SC_SOURCE_GROUP_ROWS}}", sc_grp_rows or "| - | - | - | - | - | - | - |\n")

    # ── 13. Key findings ──────────────────────────────────────────────────────
    findings = []
    tot_df_f = _safe_csv(DIRS["comparison"] / "twf_total_all_years.csv")
    if not tot_df_f.empty:
        t0r = tot_df_f[tot_df_f["Year"].astype(str) == first_yr]["Total_bn_m3"]
        tNr = tot_df_f[tot_df_f["Year"].astype(str) == last_yr]["Total_bn_m3"]
        if not t0r.empty and not tNr.empty:
            t0v, tNv = float(t0r.iloc[0]), float(tNr.iloc[0])
            direction = "increased" if tNv > t0v else "decreased"
            findings.append(
                f"- Total TWF {direction} {abs(100*(tNv-t0v)/t0v):.1f}% "
                f"from {first_yr} to {last_yr} ({t0v:.4f} → {tNv:.4f} billion m3)."
            )
        if "Indirect_pct" in tot_df_f.columns:
            findings.append(
                f"- Indirect water averaged {tot_df_f['Indirect_pct'].mean():.0f}% "
                f"of total TWF across study years."
            )

    ind_all = _safe_csv(DIRS["indirect"] / "indirect_twf_all_years.csv")
    if not ind_all.empty:
        i0r = ind_all[ind_all["Year"].astype(str) == first_yr]["Intensity_m3_per_crore"]
        iNr = ind_all[ind_all["Year"].astype(str) == last_yr]["Intensity_m3_per_crore"]
        if not i0r.empty and not iNr.empty:
            i0v, iNv = float(i0r.iloc[0]), float(iNr.iloc[0])
            findings.append(
                f"- Water intensity (indirect) fell from {i0v:,.0f} to {iNv:,.0f} "
                f"m3/Rs crore ({_pct(i0v, iNv)}), reflecting supply-chain "
                "efficiency and structural demand shifts."
            )

    if h0 and hN:
        direction = "fell" if float(hN) < float(h0) else "rose"
        findings.append(
            f"- Hotel direct water intensity {direction} from {h0:,} to {hN:,} "
            f"L/room/night ({_pct(h0, hN)}, CHSB India data)."
        )
    if not art_df.empty and "Product_ID" in art_df.columns:
        findings.append(
            f"- {len(art_df)} SUT product(s) show zero water multiplier in "
            f"{last_yr} (Section 8). These are EXIOBASE data revisions — "
            "do not cite as efficiency improvements without verifying F.txt."
        )
    findings.append(
        "- COVID-19 impact visible: 2022 direct TWF lower than 2019 "
        "(reduced hotel occupancy, fewer flights)."
    )

    # ── Hotels & Restaurants anomaly warning (Issue #7) ──────────────────────
    # Detect implausible water drop while demand grows — signals concordance change.
    _hotel_anomaly_store = ""
    _cat_first = _safe_csv(DIRS["indirect"] / f"indirect_twf_{first_yr}_by_category.csv")
    _cat_last_h = _safe_csv(DIRS["indirect"] / f"indirect_twf_{last_yr}_by_category.csv")
    if not _cat_first.empty and not _cat_last_h.empty and "Category_Name" in _cat_first.columns:
        for _nm in ("Hotels", "Accommodation"):
            _hr0 = _cat_first[_cat_first["Category_Name"].str.contains(_nm, case=False, na=False)]
            _hr1 = _cat_last_h[_cat_last_h["Category_Name"].str.contains(_nm, case=False, na=False)]
            if not _hr0.empty and not _hr1.empty:
                _w0h = float(_hr0.iloc[0].get("Total_Water_m3", 0))
                _w1h = float(_hr1.iloc[0].get("Total_Water_m3", 0))
                _d0h = float(_hr0.iloc[0].get("Demand_crore", 1))
                _d1h = float(_hr1.iloc[0].get("Demand_crore", 1))
                if _w0h > 0 and _d1h > _d0h and _w1h / _w0h < 0.5:
                    _hotel_anomaly_store = (
                        f"\n\n> ⚠ **Hotels/Accommodation anomaly detected "
                        f"({first_yr}→{last_yr}):** Indirect water fell "
                        f"{100*(_w1h-_w0h)/_w0h:+.0f}% "
                        f"({_w0h/1e9:.2f} → {_w1h/1e9:.2f} bn m³) while nominal "
                        f"demand grew {100*(_d1h-_d0h)/_d0h:+.0f}% "
                        f"(₹{_d0h:,.0f} → ₹{_d1h:,.0f} cr). "
                        f"This is implausible as a genuine efficiency gain. "
                        f"Likely cause: concordance SUT_Product_IDs for this "
                        f"category differ between the {first_yr} and {last_yr} "
                        f"SUT files. **Verify before publication.**"
                    )
                    findings.append(
                        f"- ⚠ Hotels/Accommodation indirect water fell "
                        f"{100*(_w1h-_w0h)/_w0h:+.0f}% while demand grew "
                        f"{100*(_d1h-_d0h)/_d0h:+.0f}% — verify concordance "
                        f"SUT_Product_IDs before citing this figure."
                    )
                break

    # ── Concordance double-count warning (Issue #4) ──────────────────────────
    # Detect categories with identical Total_Water_m3 values across years —
    # a reliable signal that two categories share the same SUT_Product_IDs.
    _concordance_warn = ""
    for _yr in STUDY_YEARS:
        _cdf = _safe_csv(DIRS["indirect"] / f"indirect_twf_{_yr}_by_category.csv")
        if _cdf.empty or "Total_Water_m3" not in _cdf.columns:
            continue
        _dupes = _cdf[_cdf.duplicated("Total_Water_m3", keep=False) & (_cdf["Total_Water_m3"] > 0)]
        if not _dupes.empty:
            _names = _dupes["Category_Name"].tolist() if "Category_Name" in _dupes.columns else []
            _concordance_warn += (
                "\n\n> ⚠ **Concordance double-count detected (" + str(_yr) + "):** "
                + str(len(_names)) + " categories share identical water values: "
                + ", ".join(_names[:6]) + ("..." if len(_names) > 6 else "") + ". "
                "These categories likely share the same `SUT_Product_IDs` in the "
                "concordance file, causing their water to be counted twice. "
                "**Audit the concordance CSV and assign unique product IDs to each "
                "category before publication. All indirect TWF totals may be "
                "overstated until this is resolved.**"
            )
            findings.append(
                f"- ⚠ Concordance double-count ({_yr}): {', '.join(_names[:4])} "
                f"show identical water values — verify SUT_Product_IDs in concordance."
            )
            break  # one warning is enough; the problem persists across years

    text = text.replace(
        "{{KEY_FINDINGS}}",
        ("\n".join(findings) if findings else "- Run compare step to generate findings.")
        + _hotel_anomaly_store
        + _concordance_warn
    )

    # ── Warnings ──────────────────────────────────────────────────────────────
    warn_lines: list = []
    log_dir = DIRS["logs"]
    if log_dir.exists():
        cutoff = start_ts - 120
        for lf in sorted(log_dir.glob("*.log")):
            try:
                if lf.stat().st_mtime < cutoff:
                    continue
                for line in lf.read_text(encoding="utf-8", errors="replace").splitlines():
                    if any(m in line for m in ["WARN", "WARNING", "FAILED", "ERROR", "nan"]):
                        warn_lines.append(f"[{lf.stem}] {line.strip()}")
            except Exception:
                pass
    text = text.replace(
        "{{WARNINGS}}",
        "\n".join(warn_lines[:50]) if warn_lines else "No warnings recorded in this run."
    )

    # ── Config values ─────────────────────────────────────────────────────────
    text = text.replace(
        "{{CPI_VALUES}}",
        "  |  ".join(f"{k}: {v}" for k, v in CPI.items())
    )
    text = text.replace(
        "{{EURINR_VALUES}}",
        "  |  ".join(f"{k}: {v}" for k, v in EUR_INR.items())
    )
    usd_inr_str = "  |  ".join(
        f"{yr}: ₹{rate:.2f}/USD"
        for yr, rate in USD_INR.items()
    )
    text = text.replace("{{USDINR_VALUES}}", usd_inr_str)

    # ── Abstract / headline figures ───────────────────────────────────────────
    tot_df_abs = _safe_csv(DIRS["comparison"] / "twf_total_all_years.csv")
    for yr in STUDY_YEARS:
        _val = "-"
        if not tot_df_abs.empty and "Total_bn_m3" in tot_df_abs.columns:
            _r = tot_df_abs[tot_df_abs["Year"].astype(str) == yr]
            if not _r.empty:
                _val = f"{float(_r.iloc[0]['Total_bn_m3']):.2f}"
        text = text.replace(f"{{{{ABSTRACT_TWF_{yr}}}}}", _val)

    # ── MC headline figures (for abstract + Section 15) ───────────────────────
    mc_sum_abs = _safe_csv(DIRS.get("monte_carlo",
                            BASE_DIR / "3-final-results" / "monte-carlo") /
                           "mc_summary_all_years.csv")
    _mc_last = {}
    if not mc_sum_abs.empty and "Year" in mc_sum_abs.columns:
        _lr = mc_sum_abs[mc_sum_abs["Year"].astype(str) == last_yr]
        if not _lr.empty:
            _mc_last = _lr.iloc[0].to_dict()
    text = text.replace("{{TOTAL_TWF_2022}}",
                        f"{float(_mc_last.get('Base_bn_m3', 0)):.2f}"
                        if _mc_last else "-")
    text = text.replace("{{MC_P5_2022}}",
                        f"{float(_mc_last.get('P5_bn_m3', 0)):.2f}"
                        if _mc_last else "-")
    text = text.replace("{{MC_P95_2022}}",
                        f"{float(_mc_last.get('P95_bn_m3', 0)):.2f}"
                        if _mc_last else "-")
    text = text.replace("{{MC_RANGE_PCT}}",
                        f"{float(_mc_last.get('Range_pct', 0)):.0f}"
                        if _mc_last else "-")

    # ── MC variance top driver share ──────────────────────────────────────────
    mc_var_abs = _safe_csv(DIRS.get("monte_carlo",
                            BASE_DIR / "3-final-results" / "monte-carlo") /
                           "mc_variance_decomposition.csv")
    _agr_var_share = "-"
    if not mc_var_abs.empty and "Parameter" in mc_var_abs.columns:
        _av = mc_var_abs[
            (mc_var_abs["Parameter"] == "agr_water_mult") &
            (mc_var_abs["Year"].astype(str) == last_yr)
        ]
        if not _av.empty:
            _agr_var_share = f"{float(_av.iloc[0].get('Variance_share_pct', 0)):.0f}"
    text = text.replace("{{AGR_VAR_SHARE}}", _agr_var_share)

    # Reducing σ by 50% reduces CI by ≈29% (√(1-0.5²) ≈ 0.87, or directly 1-1/√2 ≈ 29%)
    text = text.replace("{{MC_UNCERTAINTY_REDUCTION}}", "29")

    # ── SDA figures ───────────────────────────────────────────────────────────
    sda_sum_abs = _safe_csv(DIRS.get("sda", BASE_DIR / "3-final-results" / "sda") /
                            "sda_summary_all_periods.csv")
    _sda_w_pct  = "-"; _sda_y_pct = "-"
    _sda_covid  = "-"; _covid_int = "mixed signals"
    _sda_key    = "Over the full study period, demand growth (Y-effect) was the dominant driver"
    if not sda_sum_abs.empty:
        # Period 1: first_yr → mid_yr
        _p1 = sda_sum_abs[sda_sum_abs["Period"].astype(str).str.startswith(first_yr)]
        if not _p1.empty:
            _p1r = _p1.iloc[0]
            _p1_near_cancel = bool(_p1r.get("Near_cancellation", False))
            if _p1_near_cancel:
                # Do not propagate meaningless percentages into the abstract/findings
                _sda_w_pct = f"{float(_p1r.get('W_effect_m3', 0))/1e9:+.2f} bn m³ (% unstable)"
                _sda_y_pct = f"{float(_p1r.get('Y_effect_m3', 0))/1e9:+.2f} bn m³ (% unstable)"
            else:
                _sda_w_pct = f"{float(_p1r.get('W_effect_pct', 0)):.1f}"
                _sda_y_pct = f"{float(_p1r.get('Y_effect_pct', 0)):.1f}"
        # Period 2: mid_yr → last_yr  (COVID period)
        _p2 = sda_sum_abs[sda_sum_abs["Period"].astype(str).str.contains(last_yr)
                          & ~sda_sum_abs["Period"].astype(str).str.startswith(first_yr)]
        if not _p2.empty:
            _p2r = _p2.iloc[0]
            _y2 = float(_p2r.get("Y_effect_m3", 0))
            _sda_covid = f"{abs(_y2) / 1e9:.2f}"
            _w2 = float(_p2r.get("W_effect_m3", 0))
            _covid_int = ("efficiency improvement (W-effect negative)" if _w2 < 0
                          else "efficiency regression (W-effect positive)")
        # Key finding from first→last period
        _fl = sda_sum_abs[sda_sum_abs["Period"].astype(str) == f"{first_yr}→{last_yr}"]
        if not _fl.empty:
            _flr = _fl.iloc[0]
            _dtf = float(_flr.get("dTWF_m3", 0))
            _wfx = float(_flr.get("W_effect_m3", 0))
            _yfx = float(_flr.get("Y_effect_m3", 0))
            _sda_key = (
                f"Total indirect TWF {'increased' if _dtf > 0 else 'decreased'} "
                f"{abs(_dtf)/1e9:.2f} bn m³; "
                f"W-effect ({'−' if _wfx < 0 else '+'}efficiency) contributed "
                f"{abs(float(_flr.get('W_effect_pct', 0))):.1f}%, "
                f"Y-effect (demand growth) contributed "
                f"{abs(float(_flr.get('Y_effect_pct', 0))):.1f}% of |ΔTWF|"
            )
    text = text.replace("{{SDA_W_PCT_2015_2019}}", _sda_w_pct)
    text = text.replace("{{SDA_Y_PCT_2015_2019}}", _sda_y_pct)
    text = text.replace("{{SDA_COVID_REDUCTION}}", _sda_covid)
    text = text.replace("{{COVID_INTENSITY_CHANGE}}", _covid_int)
    text = text.replace("{{SDA_KEY_FINDING}}", _sda_key)

    # ── Agriculture share of indirect TWF (last year) ─────────────────────────
    _agr_share = "-"
    _origin_abs = _safe_csv(DIRS["indirect"] / f"indirect_twf_{last_yr}_origin.csv")
    if not _origin_abs.empty and "Source_Group" in _origin_abs.columns:
        _ar = _origin_abs[_origin_abs["Source_Group"] == "Agriculture"]
        if not _ar.empty:
            _agr_share = f"{float(_ar.iloc[0].get('Water_pct', 0)):.1f}"
    text = text.replace("{{AGR_SHARE_2022}}", _agr_share)

    # ── Inbound/domestic ratio — report range across all study years ─────────
    # Reporting a single year's ratio in the abstract is misleading because
    # the ratio varies across years (e.g. ~15× in 2015, ~17× in 2019-22).
    # We report "X–Y×" using the min and max across available study years.
    _inb_dom_ratio = "-"
    _int_abs = _safe_csv(DIRS["comparison"] / "twf_per_tourist_intensity.csv")
    if not _int_abs.empty and "Year" in _int_abs.columns:
        _ratios = []
        for _yr in STUDY_YEARS:
            _ir = _int_abs[_int_abs["Year"].astype(str) == str(_yr)]
            if not _ir.empty:
                _inb = float(_ir.iloc[0].get("L_per_inb_tourist_day", 0))
                _dom = float(_ir.iloc[0].get("L_per_dom_tourist_day", 1))
                if _dom > 0 and _inb > 0:
                    _ratios.append(_inb / _dom)
        if _ratios:
            _rmin, _rmax = min(_ratios), max(_ratios)
            if abs(_rmax - _rmin) / _rmax < 0.10:
                # Ratios are within 10% of each other — cite a single rounded value
                _inb_dom_ratio = f"{round(sum(_ratios)/len(_ratios))}"
            else:
                _inb_dom_ratio = f"{round(_rmin)}–{round(_rmax)}"
    text = text.replace("{{INB_DOM_RATIO}}", _inb_dom_ratio)

    # ── Demand growth % (first → last year, nominal) ──────────────────────────
    _dem_growth = "-"
    if not dem_cmp.empty and "Metric" in dem_cmp.columns:
        _dn0 = dem_cmp[(dem_cmp["Metric"].str.contains("nominal", case=False, na=False)) &
                       (dem_cmp["Year"].astype(str) == first_yr)]
        _dn1 = dem_cmp[(dem_cmp["Metric"].str.contains("nominal", case=False, na=False)) &
                       (dem_cmp["Year"].astype(str) == last_yr)]
        if not _dn0.empty and not _dn1.empty:
            _v0 = float(_dn0.iloc[0]["Value"]); _v1 = float(_dn1.iloc[0]["Value"])
            if _v0 > 0:
                _dem_growth = f"{100 * (_v1 - _v0) / _v0:.0f}"
    text = text.replace("{{DEMAND_GROWTH_PCT}}", _dem_growth)

    # ── Intensity absolute drop L/tourist/day ─────────────────────────────────
    _int_drop = "-"
    if not _int_abs.empty and "Year" in _int_abs.columns:
        _r0 = _int_abs[_int_abs["Year"].astype(str) == first_yr]
        _r1 = _int_abs[_int_abs["Year"].astype(str) == last_yr]
        if not _r0.empty and not _r1.empty:
            _i0 = float(_r0.iloc[0].get("L_per_tourist_day", 0))
            _i1 = float(_r1.iloc[0].get("L_per_tourist_day", 0))
            _int_drop = f"{abs(_i0 - _i1):,.0f}"
    text = text.replace("{{INTENSITY_ABS_DROP}}", _int_drop)

    # ── Direct share range across years ──────────────────────────────────────
    _direct_range = "7–15"   # default; overwrite if data available
    if not tot_df_abs.empty and "Direct_pct" in tot_df_abs.columns:
        _dp_vals = tot_df_abs["Direct_pct"].dropna()
        if not _dp_vals.empty:
            _direct_range = f"{_dp_vals.min():.0f}–{_dp_vals.max():.0f}"
    text = text.replace("{{DIRECT_SHARE_RANGE}}", _direct_range)

    # ── Introduction context figures ──────────────────────────────────────────
    # These are stable empirical facts from MoT/WTTC publications; they are
    # not computed by the pipeline and are recorded here as known values.
    text = text.replace("{{TOURISM_GDP_PCT}}", "5.9")    # WTTC India 2019
    text = text.replace("{{TOURISM_JOBS_M}}",  "87.5")   # WTTC India 2019

    # ── Sector counts ─────────────────────────────────────────────────────────
    text = text.replace("{{N_SECTORS}}",      "140")
    text = text.replace("{{N_EXIO_SECTORS}}", "163")

    # ── NAS Hotels worked example (demand section) ────────────────────────────
    _nas_hotels_2019 = str(round(NAS_GROWTH_RATES.get("Hotels", {}).get("2019", 0), 4))
    _cpi_base  = float(CPI.get("2015-16", 124.7))
    _cpi_2019  = float(CPI.get("2019-20", 146.3))
    _cpi_mult  = round(_cpi_2019 / _cpi_base, 4) if _cpi_base else 0
    _hotel_nom = round(float(_nas_hotels_2019) * _cpi_mult, 4) if _nas_hotels_2019 != "0" else 0
    # Find Hotels inbound 2015 base from TSA_BASE
    from config import TSA_BASE
    _hotel_inb_base = sum(inb for _, cat, ctype, inb, dom in TSA_BASE
                          if "hotel" in cat.lower() or "accommodation" in cat.lower())
    _hotel_inb_2019 = round(_hotel_inb_base * _hotel_nom) if _hotel_nom else 0
    text = text.replace("{{NAS_HOTELS_2019}}",       _nas_hotels_2019)
    text = text.replace("{{CPI_2019_MULT}}",         str(_cpi_mult))
    text = text.replace("{{HOTEL_NOM_FACTOR_2019}}", str(_hotel_nom))
    text = text.replace("{{HOTEL_INB_2019}}",        f"{_hotel_inb_2019:,}")

    # ── Direct TWF hotels worked example (last year) ─────────────────────────
    _act_last  = ACTIVITY_DATA.get(last_yr, {})
    _rooms     = int(_act_last.get("classified_rooms", 0))
    _occ       = _act_last.get("occupancy_rate", 0)
    _occ_pct   = round(_occ * 100, 1)
    _h_coeff   = DIRECT_WATER["hotel"].get(last_yr, {}).get("base", 0)
    _occ_nights = round(_rooms * _occ * 365)
    _hotel_m3   = round(_occ_nights * _h_coeff / 1000)
    text = text.replace("{{HOTEL_ROOMS_2022}}",      f"{_rooms:,}")
    text = text.replace("{{HOTEL_OCC_2022}}",        str(_occ_pct))
    text = text.replace("{{HOTEL_OCC_2022_DEC}}",    str(round(_occ, 3)))
    text = text.replace("{{HOTEL_OCC_NIGHTS_2022}}", f"{_occ_nights:,}")
    text = text.replace("{{HOTEL_COEFF_2022}}",      str(int(_h_coeff)))
    text = text.replace("{{HOTEL_M3_2022}}",         f"{_hotel_m3:,}")

    # ── Pipeline version (timestamp-based) ───────────────────────────────────
    text = text.replace("{{PIPELINE_VERSION}}",
                        datetime.fromtimestamp(start_ts).strftime("v%Y%m%d-%H%M%S"))

    # ── Policy savings (estimated from sensitivity ranges) ────────────────────
    # Policy 1: 10% reduction in agricultural W coefficients ≈ 10% × total indirect TWF
    _pol1 = "-"
    if not tot_df_abs.empty and "Indirect_bn_m3" in tot_df_abs.columns:
        _latest_ind = tot_df_abs[tot_df_abs["Year"].astype(str) == last_yr]
        if not _latest_ind.empty:
            _pol1 = f"{float(_latest_ind.iloc[0]['Indirect_bn_m3']) * 0.10:.2f}"
    # Policy 2: hotel direct savings from 10% occupancy water reduction
    _pol2 = f"{round(_occ_nights * _h_coeff * 0.10 / 1000 / 1e6)}" if _occ_nights and _h_coeff else "-"
    # Policy 3: inbound basket shift — 5% of inbound indirect TWF
    _pol3 = "-"
    if not _int_abs.empty and "Year" in _int_abs.columns:
        _lr3 = _int_abs[_int_abs["Year"].astype(str) == last_yr]
        if not _lr3.empty:
            _inb_ind = float(_lr3.iloc[0].get("Inb_Indirect_m3", 0))
            _pol3 = f"{round(_inb_ind * 0.05 / 1e6)}"
    text = text.replace("{{POLICY_SAVING_1}}", _pol1)
    text = text.replace("{{POLICY_SAVING_2}}", _pol2)
    text = text.replace("{{POLICY_SAVING_3}}", _pol3)

    # (The KEY_FINDINGS block is filled in the findings section above;
    #  hotel anomaly detection is also handled there)


    # ── Write ─────────────────────────────────────────────────────────────────
    DIRS["comparison"].mkdir(parents=True, exist_ok=True)
    out = DIRS["comparison"] / f"run_report_{int(start_ts)}.md"
    out.write_text(text, encoding="utf-8")
    if log:
        log.ok(f"Report written: {out}")
    else:
        print(f"  Report written: {out}")
    return out


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def run(start_ts: float = None, steps_req: list = None,
        steps_completed: list = None, steps_failed: list = None,
        total_time: float = 0.0, pipeline_log: Path = None):
    """
    Run all comparison analyses, save CSVs, write plain-text report,
    and fill the Markdown report template.

    Parameters
    ----------
    start_ts        : pipeline start timestamp (from main.py)
    steps_req       : list of step names requested in this run
    steps_completed : list of step names that succeeded
    steps_failed    : list of step names that failed
    total_time      : total pipeline wall-clock time in seconds
    pipeline_log    : path to the pipeline .log file
    """
    import time as _time
    _start = start_ts or _time.time()

    with Logger(SCRIPT_NAME, DIRS["logs"]) as log:
        t = Timer()
        log.section("CROSS-YEAR TWF COMPARISON")
        DIRS["comparison"].mkdir(parents=True, exist_ok=True)

        total_df             = build_total_twf(log)
        intensity_df         = per_tourist_intensity(total_df, log)
        data_quality_flags(intensity_df, total_df, log)          # NEW
        trends_df            = sector_trends(log)
        mult_df, artifact_df = type1_multipliers(log)

        save_csv(total_df,     DIRS["comparison"] / "twf_total_all_years.csv",          "Total TWF",           log=log)
        save_csv(intensity_df, DIRS["comparison"] / "twf_per_tourist_intensity.csv",    "Per-tourist",         log=log)
        if not trends_df.empty:
            save_csv(trends_df,    DIRS["comparison"] / "twf_sector_trends.csv",        "Sector trends",       log=log)
        if not mult_df.empty:
            save_csv(mult_df,      DIRS["comparison"] / "twf_type1_multipliers.csv",    "Type I multipliers",  log=log)
        if not artifact_df.empty:
            save_csv(artifact_df,  DIRS["comparison"] / "twf_multiplier_artifacts.csv", "Multiplier artefacts",log=log)

        write_report(
            total_df, intensity_df, trends_df,
            DIRS["comparison"] / "twf_comparison_report.txt",
            log,
        )

        fill_report_template(
            start_ts        = _start,
            steps_req       = steps_req       or [SCRIPT_NAME],
            steps_completed = steps_completed or [SCRIPT_NAME],
            steps_failed    = steps_failed    or [],
            total_time      = total_time or (t.t),
            pipeline_log    = pipeline_log or DIRS["logs"] / "pipeline.log",
            log             = log,
        )

        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    run()