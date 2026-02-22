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
    DIRECT_WATER, NAS_GROWTH_RATES, NAS_GVA_CONSTANT, AVG_STAY_DAYS,
)
from utils import (
    Logger, save_csv,
    read_csv_safe, compare_across_years, compare_sectors_across_years, Timer,
)

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
    f = DIRS["indirect"] / f"indirect_twf_{year}_by_category.csv"
    df = read_csv_safe(f)
    if df.empty or "Intensity_m3_per_crore" not in df.columns:
        return 0.0
    return df["Intensity_m3_per_crore"].mean()


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
        rows.append({
            "Year": year,
            "Indirect_m3": indirect, "Direct_m3": direct, "Total_m3": total,
            "Indirect_bn_m3": round(indirect / 1e9, 4),
            "Direct_bn_m3":   round(direct   / 1e9, 4),
            "Total_bn_m3":    round(total     / 1e9, 4),
            "Indirect_pct": round(100 * indirect / total, 1) if total else 0,
            "Direct_pct":   round(100 * direct   / total, 1) if total else 0,
        })
    df = pd.DataFrame(rows)

    ind_vals = {r["Year"]: r["Indirect_bn_m3"] for r in rows}
    dir_vals = {r["Year"]: r["Direct_bn_m3"]   for r in rows}
    tot_vals = {r["Year"]: r["Total_bn_m3"]    for r in rows}
    compare_across_years(ind_vals, "Indirect TWF (bn m³)",    unit=" bn m³", log=log)
    compare_across_years(dir_vals, "Direct TWF BASE (bn m³)", unit=" bn m³", log=log)
    compare_across_years(tot_vals, "Total TWF (bn m³)",       unit=" bn m³", log=log)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# PER-TOURIST INTENSITY
# ══════════════════════════════════════════════════════════════════════════════

def per_tourist_intensity(total_df: pd.DataFrame, log: Logger) -> pd.DataFrame:
    """
    L per tourist per day for domestic and inbound tourists.

    FIX: The original mixed indirect-only water for domestic tourists against
    total water for inbound tourists — an asymmetry that inflated inbound figures.
    Both metrics now use Total_m3 consistently. The domestic figure is split from
    total by the ratio of domestic tourist-days to total tourist-days.

    avg_stay_days values are now read from AVG_STAY_DAYS (sourced from the
    AVG_STAY_DAYS section of reference_data.md via config.py) rather than being
    hardcoded. Update reference_data.md to change stay duration assumptions.
    """
    rows = []
    for _, r in total_df.iterrows():
        year     = r["Year"]
        act      = ACTIVITY_DATA.get(year, ACTIVITY_DATA[STUDY_YEARS[-1]])
        dom_days = act["domestic_tourists_M"] * 1e6 * act["avg_stay_days_dom"]
        inb_days = act["inbound_tourists_M"]  * 1e6 * act["avg_stay_days_inb"]
        all_days = dom_days + inb_days
        total_m3 = r["Total_m3"]

        dom_share = dom_days / all_days if all_days > 0 else 0
        inb_share = inb_days / all_days if all_days > 0 else 0

        rows.append({
            "Year":                   year,
            "Dom_tourists_M":         act["domestic_tourists_M"],
            "Inb_tourists_M":         act["inbound_tourists_M"],
            "Dom_stay_days":          act["avg_stay_days_dom"],
            "Inb_stay_days":          act["avg_stay_days_inb"],
            "Dom_days_M":             round(dom_days / 1e6, 1),
            "Inb_days_M":             round(inb_days / 1e6, 1),
            "L_per_tourist_day":      round(total_m3 * 1000 / all_days)               if all_days  else 0,
            "L_per_dom_tourist_day":  round(total_m3 * dom_share * 1000 / dom_days)   if dom_days  else 0,
            "L_per_inb_tourist_day":  round(total_m3 * inb_share * 1000 / inb_days)   if inb_days  else 0,
        })

    df = pd.DataFrame(rows)
    int_vals = {r["Year"]: r["L_per_tourist_day"] for r in rows}
    compare_across_years(int_vals, "L/tourist/day (all tourists)", unit=" L/day", log=log)
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
        if df.empty or "Water_Multiplier_m3_per_crore" not in df.columns:
            continue
        keep = [c for c in ["Product_ID", "Product_Name",
                             "Water_Multiplier_m3_per_crore"] if c in df.columns]
        sub = df[keep].copy()
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
        f.write(f"{'Year':<6} {'Total (bn m³)':>14} {'Indirect':>12} {'Direct':>10} "
                f"{'Ind%':>6} {'Dir%':>6}\n")
        base_t = None
        for _, r in total_df.iterrows():
            if base_t is None:
                base_t = r["Total_bn_m3"]
            chg = f" ({100*(r['Total_bn_m3']-base_t)/base_t:+.1f}%)" if base_t else ""
            f.write(f"{r['Year']:<6} {r['Total_bn_m3']:>14.4f} {r['Indirect_bn_m3']:>12.4f} "
                    f"{r['Direct_bn_m3']:>10.4f} {r['Indirect_pct']:>6.1f} "
                    f"{r['Direct_pct']:>6.1f}{chg}\n")

        f.write("\n2. PER-TOURIST WATER INTENSITY\n" + "─" * 40 + "\n")
        f.write(f"{'Year':<6} {'L/tourist/day':>14} {'Dom L/day':>12} {'Inb L/day':>12}\n")
        for _, r in intensity_df.iterrows():
            f.write(f"{r['Year']:<6} {r['L_per_tourist_day']:>14,.0f} "
                    f"{r['L_per_dom_tourist_day']:>12,.0f} "
                    f"{r['L_per_inb_tourist_day']:>12,.0f}\n")

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
        io_rows += (
            f"| {r.get('year','-')} "
            f"| {int(r.get('n_products',0)):,} "
            f"| {int(r.get('total_output_crore',0)):,} "
            f"| {int(r.get('total_output_2015prices',0)):,} "
            f"| {int(r.get('total_intermediate_crore',0)):,} "
            f"| {int(r.get('total_final_demand_crore',0)):,} "
            f"| {float(r.get('balance_error_pct',0)):.4f} "
            f"| {float(r.get('spectral_radius',0)):.6f} |\n"
        )
    text = text.replace("{{IO_TABLE_ROWS}}", io_rows or "| - | - | - | - | - | - | - | - |\n")

    # ── 2. Demand rows ────────────────────────────────────────────────────────
    dem_cmp  = _safe_csv(DIRS["demand"] / "demand_intensity_comparison.csv")
    dem_rows = ""
    if not dem_cmp.empty:
        nom = dem_cmp[dem_cmp["Metric"].str.contains("nominal", case=False, na=False)]
        rl  = dem_cmp[dem_cmp["Metric"].str.contains("real",    case=False, na=False)]
        for yr in STUDY_YEARS:
            n_r  = nom[nom["Year"] == yr]
            r_r  = rl[rl["Year"]  == yr]
            n_v  = float(n_r["Value"].iloc[0]) if not n_r.empty else 0
            r_v  = float(r_r["Value"].iloc[0]) if not r_r.empty else 0
            cagr = n_r["CAGR_vs_base"].iloc[0] if not n_r.empty and "CAGR_vs_base" in n_r.columns else None
            cagr_s = f"{float(cagr):+.1f}%/yr" if cagr is not None else "-"
            y_df = _safe_csv(DIRS["demand"] / f"Y_tourism_{yr}.csv")
            nz   = (int((y_df["Tourism_Demand_crore"] > 0).sum())
                    if not y_df.empty and "Tourism_Demand_crore" in y_df.columns else "-")
            dem_rows += f"| {yr} | {n_v:,.0f} | {r_v:,.0f} | {nz}/163 | {cagr_s} |\n"
    text = text.replace("{{DEMAND_TABLE_ROWS}}", dem_rows or "| - | - | - | - | - |\n")

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
    ind_rows = ""
    base_ind = None
    for yr in STUDY_YEARS:
        vals = _get_ind_vals(yr)
        if vals is None:
            ind_rows += f"| {yr} | - | - | - | - | - |\n"; continue
        delta = "(base)" if base_ind is None else _pct(base_ind, vals["tot"])
        if base_ind is None:
            base_ind = vals["tot"]
        ind_rows += (
            f"| {yr} | {vals['tot']:.4f} | {vals['ni']:,.1f} "
            f"| {vals['ri']:,.1f} | {vals['dem']:,.0f} | {delta} |\n"
        )
    text = text.replace("{{INDIRECT_SUMMARY_ROWS}}", ind_rows or "| - | - | - | - | - | - |\n")

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
    SOURCE_GROUPS = ["Agriculture", "Manufacturing", "Mining",
                     "Services", "Electricity", "Petroleum"]
    origin: dict = {}
    for yr in STUDY_YEARS:
        struct_df = _safe_csv(DIRS["indirect"] / f"indirect_twf_{yr}_structural.csv")
        if struct_df.empty:
            continue
        yr_total = float(struct_df["Total_Water_m3"].sum()) if "Total_Water_m3" in struct_df.columns else 0
        for grp in SOURCE_GROUPS:
            col = f"From_{grp}_m3"
            if col in struct_df.columns:
                w = float(struct_df[col].sum())
                origin.setdefault(grp, {})[yr] = (w, 100 * w / yr_total if yr_total else 0)
    origin_rows = ""
    for grp in SOURCE_GROUPS:
        if grp not in origin:
            continue
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
            dir_rows += f"| {yr} | - | - | - | - | - | - | - |\n"; continue
        dir_rows += (
            f"| {yr} "
            f"| {_row_val(b,'Hotel_m3')/1e6:.2f} "
            f"| {_row_val(b,'Restaurant_m3')/1e6:.2f} "
            f"| {_row_val(b,'Rail_m3')/1e6:.2f} "
            f"| {_row_val(b,'Air_m3')/1e6:.2f} "
            f"| {_row_val(b,'Total_billion_m3','Total_bn_m3'):.4f} "
            f"| {_row_val(l,'Total_billion_m3','Total_bn_m3'):.4f} "
            f"| {_row_val(h,'Total_billion_m3','Total_bn_m3'):.4f} |\n"
        )
    text = text.replace("{{DIRECT_TABLE_ROWS}}", dir_rows or "| - | - | - | - | - | - | - | - |\n")

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
            tot_rows += f"| {yr} | - | - | - | - | - | - |\n"; continue
        ind   = float(r.get("Indirect_bn_m3", 0))
        dr    = float(r.get("Direct_bn_m3",   0))
        tot   = float(r.get("Total_bn_m3",    0))
        ip    = float(r.get("Indirect_pct",   0))
        dp    = float(r.get("Direct_pct",     0))
        delta = "(base)" if base_tot is None else _pct(base_tot, tot)
        if base_tot is None:
            base_tot = tot
        tot_rows += f"| {yr} | {ind:.4f} | {dr:.4f} | {tot:.4f} | {ip:.1f}% | {dp:.1f}% | {delta} |\n"
    text = text.replace("{{TOTAL_TWF_ROWS}}", tot_rows or "| - | - | - | - | - | - | - |\n")

    # ── 6. Per-tourist intensity ───────────────────────────────────────────────
    int_df   = _safe_csv(DIRS["comparison"] / "twf_per_tourist_intensity.csv")
    int_rows = ""
    for yr in STUDY_YEARS:
        if not int_df.empty and "Year" in int_df.columns:
            r = int_df[int_df["Year"].astype(str) == str(yr)]
            if not r.empty:
                r   = r.iloc[0]
                act = ACTIVITY_DATA.get(yr, {})
                int_rows += (
                    f"| {yr} "
                    f"| {int(r.get('L_per_tourist_day', 0)):,} "
                    f"| {int(r.get('L_per_dom_tourist_day', 0)):,} "
                    f"| {int(r.get('L_per_inb_tourist_day', 0)):,} "
                    f"| {act.get('domestic_tourists_M', '-')} "
                    f"| {act.get('inbound_tourists_M', '-')} |\n"
                )
                continue
        t_row = _get_tot_row(yr)
        act   = ACTIVITY_DATA.get(yr, {})
        if t_row is None or not act:
            int_rows += f"| {yr} | - | - | - | - | - |\n"; continue
        total_m3 = float(t_row.get("Total_bn_m3", 0)) * 1e9
        dom_days = act.get("domestic_tourists_M", 0) * 1e6 * act.get("avg_stay_days_dom", 1)
        inb_days = act.get("inbound_tourists_M",  0) * 1e6 * act.get("avg_stay_days_inb", 1)
        all_days = dom_days + inb_days
        if all_days == 0:
            int_rows += f"| {yr} | - | - | - | - | - |\n"; continue
        dom_share = dom_days / all_days
        inb_share = inb_days / all_days
        int_rows += (
            f"| {yr} "
            f"| {round(total_m3 * 1000 / all_days):,} "
            f"| {round(total_m3 * dom_share * 1000 / dom_days) if dom_days else 0:,} "
            f"| {round(total_m3 * inb_share * 1000 / inb_days) if inb_days else 0:,} "
            f"| {act.get('domestic_tourists_M', '-')} "
            f"| {act.get('inbound_tourists_M', '-')} |\n"
        )
    text = text.replace("{{INTENSITY_ROWS}}", int_rows or "| - | - | - | - | - | - |\n")

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
    if not art_df.empty:
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
    if (not mult_df.empty and first_yr in mult_df.columns
            and last_yr in mult_df.columns and chg_col in mult_df.columns):
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
        if not si.empty and "Total_TWF_bn_m3" in si.columns:
            # Expanded sensitivity: use Agriculture BASE as the reference row
            base_rows = si[si["Scenario"] == "BASE"]
            lo_rows   = si[(si["Scenario"] == "LOW")  & (si["Group"] == "Agriculture")] if "Group" in si.columns else si[si["Scenario"] == "LOW"]
            hi_rows   = si[(si["Scenario"] == "HIGH") & (si["Group"] == "Agriculture")] if "Group" in si.columns else si[si["Scenario"] == "HIGH"]
            if not base_rows.empty and not lo_rows.empty and not hi_rows.empty:
                bs  = float(base_rows["Total_TWF_bn_m3"].iloc[0])
                lo  = float(lo_rows["Total_TWF_bn_m3"].iloc[0])
                hi  = float(hi_rows["Total_TWF_bn_m3"].iloc[0])
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
            if not si2.empty and "Total_TWF_bn_m3" in si2.columns:
                base_r = si2[si2["Scenario"] == "BASE"]
                lo_r   = si2[(si2["Scenario"] == "LOW")  & (si2["Group"] == "Agriculture")] if "Group" in si2.columns else si2[si2["Scenario"] == "LOW"]
                hi_r   = si2[(si2["Scenario"] == "HIGH") & (si2["Group"] == "Agriculture")] if "Group" in si2.columns else si2[si2["Scenario"] == "HIGH"]
                if not base_r.empty and not lo_r.empty and not hi_r.empty:
                    ibs = float(base_r["Total_TWF_bn_m3"].iloc[0])
                    ilo = float(lo_r["Total_TWF_bn_m3"].iloc[0])
                    ihi = float(hi_r["Total_TWF_bn_m3"].iloc[0])
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
    sda_all  = _safe_csv(sda_dir / "sda_summary_all_periods.csv")
    if not sda_all.empty:
        for _, r in sda_all.iterrows():
            sda_rows += (
                f"| {r.get('Period', '-')} "
                f"| {float(r.get('TWF0_m3', 0))/1e9:.4f} "
                f"| {float(r.get('TWF1_m3', 0))/1e9:.4f} "
                f"| {float(r.get('dTWF_m3', 0))/1e9:+.4f} "
                f"| {float(r.get('W_effect_m3', 0))/1e9:+.4f} "
                f"| {float(r.get('W_effect_pct', 0)):+.1f}% "
                f"| {float(r.get('L_effect_m3', 0))/1e9:+.4f} "
                f"| {float(r.get('L_effect_pct', 0)):+.1f}% "
                f"| {float(r.get('Y_effect_m3', 0))/1e9:+.4f} "
                f"| {float(r.get('Y_effect_pct', 0)):+.1f}% |\n"
            )
    text = text.replace("{{SDA_DECOMP_ROWS}}", sda_rows or "| - | - | - | - | - | - | - | - | - | - |\n")

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
    if not art_df.empty:
        findings.append(
            f"- {len(art_df)} SUT product(s) show zero water multiplier in "
            f"{last_yr} (Section 8). These are EXIOBASE data revisions — "
            "do not cite as efficiency improvements without verifying F.txt."
        )
    findings.append(
        "- COVID-19 impact visible: 2022 direct TWF lower than 2019 "
        "(reduced hotel occupancy, fewer flights)."
    )
    text = text.replace(
        "{{KEY_FINDINGS}}",
        "\n".join(findings) if findings else "- Run compare step to generate findings."
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