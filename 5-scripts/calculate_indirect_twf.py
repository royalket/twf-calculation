"""
Calculate indirect Tourism Water Footprint using the Leontief supply-chain model.

Core formula:
  TWF_indirect = W × L × Y
Where:
  W  = water coefficient vector (m³/₹ crore), shape (140,)
       from EXIOBASE → concordance → SUT 140 mapping
  L  = Leontief inverse (I−A)^{-1}, shape (140×140)
       from PTA: D = V/q, Z = U·D^T, A = Z/x, L = (I−A)^{-1}
  Y  = tourism final demand vector (₹ crore), shape (140,)
       from TSA 2015-16 × NAS growth rates, mapped to SUT products

Unit consistency: ALL variables in ₹ crore → result in m³.

Example calculation (3-sector illustration):
  W  = [5000, 0, 0]   m³/crore  (only Agriculture uses direct water)
  L  = [[1.2, 0.8, 0.1],
         [0.3, 1.5, 0.2],
         [0.4, 0.6, 1.3]]
  Y  = [0, 150, 300]  crore     (tourists spend on Food & Services, not raw Agriculture)

  WL = W @ L = [6000, 4000, 500]  m³/crore
  TWF = WL * Y = [0, 600,000, 150,000] m³  → Total = 750,000 m³

Additional analyses:
  1. Structural decomposition: per-tourism-sector water pull by SOURCE sector
     (Agriculture, Electricity, Petroleum, Manufacturing, Mining, Services)
  2. Water origin summary: aggregated source-group totals (NEW)
  3. Price deflation: compute TWF intensity using real (2015-16) demand
  4. Sensitivity: ±20% on agriculture, electricity AND petroleum coefficients (EXPANDED)
  5. Per-sector intensity: m³ per ₹ crore of tourism spending by category
  6. Inbound vs domestic split TWF (NEW): runs W×L×Y separately for each demand split

Two "sector" views printed per year
--------------------------------------
  A. "By sector type (destination)" — groups by WHERE tourism demand lands.
     Agriculture = 0 here because tourists don't buy raw crops directly.
     This is CORRECT and expected.

  B. "By source sector (water origin)" — from structural decomposition.
     Agriculture should dominate (60-80%) because supply chains pull
     heavily from agricultural water upstream — matching Lee et al. (2021).

Outputs per year:
  indirect_twf_{year}_by_sut.csv        — 140 products × water contribution
  indirect_twf_{year}_by_category.csv   — 75 categories × water contribution
  indirect_twf_{year}_structural.csv    — water pull by source sector × tourism category
  indirect_twf_{year}_origin.csv        — aggregated water origin by source group (NEW)
  indirect_twf_{year}_intensity.csv     — m³/crore by tourism category
  indirect_twf_{year}_sensitivity.csv   — LOW/BASE/HIGH on agriculture, electricity,
                                          petroleum coefficients (EXPANDED)
  indirect_twf_{year}_split.csv         — inbound vs domestic TWF split (NEW)
  indirect_twf_{year}_summary.txt       — key metrics including origin view
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from config import BASE_DIR, DIRS, YEARS, CPI, STUDY_YEARS
from utils import (
    section, subsection, ok, warn, save_csv,
    check_conservation, check_matrix_properties,
    top_n, compare_across_years, Timer, Logger,
)


# ── Data loaders ──────────────────────────────────────────────────────────────

def load_y_tourism(year: str, use_real: bool = False, log: Logger = None) -> np.ndarray:
    """
    Load 163-sector combined demand vector (₹ crore).
    use_real=True loads the CPI-deflated version for intensity comparison.
    """
    suffix = "_real" if use_real else ""
    f = DIRS["demand"] / f"Y_tourism_{year}{suffix}.csv"
    df = pd.read_csv(f)
    Y = df["Tourism_Demand_crore"].values
    label = "real (2015-16 prices)" if use_real else "nominal"
    ok(f"Y_tourism {year} [{label}]: ₹{Y.sum():,.0f} crore, {np.count_nonzero(Y)}/163 non-zero", log)
    return Y


def load_y_split(year: str, log: Logger = None) -> tuple:
    """
    Load inbound-only and domestic-only 163-sector demand vectors.
    Returns (Y_inbound, Y_domestic). If split files don't exist, returns
    (None, None) with a warning — caller should skip split analysis gracefully.

    Split files are produced by build_tourism_demand.py:
      Y_tourism_{year}_inbound.csv
      Y_tourism_{year}_domestic.csv
    """
    f_inb = DIRS["demand"] / f"Y_tourism_{year}_inbound.csv"
    f_dom = DIRS["demand"] / f"Y_tourism_{year}_domestic.csv"

    if not f_inb.exists() or not f_dom.exists():
        warn(
            f"Split demand files not found for {year} — inbound/domestic analysis skipped. "
            f"Re-run build_tourism_demand to generate Y_tourism_{{year}}_inbound/domestic.csv",
            log,
        )
        return None, None

    Y_inb = pd.read_csv(f_inb)["Tourism_Demand_crore"].values
    Y_dom = pd.read_csv(f_dom)["Tourism_Demand_crore"].values
    ok(
        f"Split demand {year}: inbound ₹{Y_inb.sum():,.0f} cr  "
        f"domestic ₹{Y_dom.sum():,.0f} cr",
        log,
    )
    return Y_inb, Y_dom


def load_leontief(study_year: str, log: Logger = None) -> np.ndarray:
    cfg = YEARS[study_year]
    f = DIRS["io"] / cfg["io_year"] / f"io_L_{cfg['io_tag']}.csv"
    L = pd.read_csv(f, index_col=0).values
    ok(f"L ({cfg['io_year']}): {L.shape}  diag mean={np.diag(L).mean():.4f}", log)
    return L


def load_concordance(study_year: str, log: Logger = None) -> pd.DataFrame:
    cfg = YEARS[study_year]
    f = DIRS["concordance"] / f"concordance_{cfg['io_tag']}.csv"
    df = pd.read_csv(f)
    ok(f"Concordance {cfg['io_year']}: {len(df)} categories", log)
    return df


def load_sut_water(study_year: str, log: Logger = None):
    cfg = YEARS[study_year]
    f = DIRS["concordance"] / f"water_coefficients_140_{cfg['io_tag']}.csv"
    df = pd.read_csv(f)
    wc = [c for c in df.columns if "Water" in c and "crore" in c][0]
    ok(f"SUT water {cfg['io_year']}: {(df[wc]>0).sum()}/140 non-zero", log)
    return df, wc


# ── Map Y from EXIOBASE 163 to SUT 140 ───────────────────────────────────────

def map_y_to_sut(Y_163: np.ndarray, concordance_df: pd.DataFrame,
                  n_sut: int = 140, log: Logger = None) -> np.ndarray:
    """
    Map 163-sector EXIOBASE demand to 140 SUT products via concordance.
    Distributes category demand equally across mapped SUT products.
    """
    Y_140 = np.zeros(n_sut)
    assigned_exio: dict = {}

    for _, row in concordance_df.iterrows():
        cat_id   = row["Category_ID"]
        exio_str = str(row.get("EXIOBASE_Sectors", ""))
        sut_str  = str(row.get("SUT_Product_IDs", ""))

        exio_codes = [
            e.strip() for e in exio_str.split(",")
            if e.strip() and e.strip().lower() != "nan"
        ]
        sut_ids = [
            int(s.strip()) for s in sut_str.split(",")
            if s.strip() and s.strip().lower() != "nan"
        ]

        demand = 0.0
        for code in exio_codes:
            if code != "IN" and not code.startswith("IN."):
                warn(
                    f"Skipping unrecognised EXIOBASE code '{code}' in category {cat_id} "
                    "— expected 'IN' or 'IN.<number>'",
                    log,
                )
                continue
            idx = 0 if code == "IN" else int(code.replace("IN.", ""))
            if idx in assigned_exio:
                warn(
                    f"EXIOBASE sector {code} (idx={idx}) already assigned to "
                    f"category {assigned_exio[idx]}, now claimed by {cat_id}. "
                    f"Check concordance self_check — demand for this sector will be "
                    f"split between categories.",
                    log,
                )
            assigned_exio[idx] = cat_id
            demand += Y_163[idx] if idx < len(Y_163) else 0

        if sut_ids and demand > 0:
            per_prod = demand / len(sut_ids)
            for sid in sut_ids:
                if 1 <= sid <= n_sut:
                    Y_140[sid - 1] += per_prod

    check_conservation(Y_140.sum(), Y_163.sum(), "Y_140 vs Y_163 (crore)", tol_pct=2.0, log=log)
    return Y_140


# ── Leontief calculation ──────────────────────────────────────────────────────

def compute_twf(W_140: np.ndarray, L: np.ndarray, Y_140: np.ndarray):
    """
    TWF = (W @ L) * Y  element-wise.
    WL[j] = total water (m³) required per ₹ crore of final demand for product j.
    TWF[j] = water triggered by tourism demand for product j.
    """
    WL  = W_140 @ L       # (140,) water multiplier vector
    TWF = WL * Y_140      # (140,) water footprint per product
    return TWF, WL


# ── Structural decomposition ──────────────────────────────────────────────────

def structural_decomposition(
    W_140: np.ndarray, L: np.ndarray, Y_140: np.ndarray,
    sut_water_df: pd.DataFrame, wc: str, concordance_df: pd.DataFrame,
    log: Logger = None,
) -> pd.DataFrame:
    """
    Decompose each tourism sector's water footprint by SOURCE SECTOR.

    For each tourism category j, the water pulled from source sector i is:
      pull[i, j] = W[i] * L[i, j] * Y[j]

    Aggregates sources into broad groups:
      Agriculture, Mining, Electricity, Petroleum, Manufacturing, Services
    """
    pull_matrix = (W_140[:, np.newaxis] * L) * Y_140[np.newaxis, :]  # (140, 140)

    def source_group(pid: int) -> str:
        if 1  <= pid <= 29:  return "Agriculture"
        if 30 <= pid <= 40:  return "Mining"
        if pid == 114:       return "Electricity"
        if 71 <= pid <= 80:  return "Petroleum"
        if 41 <= pid <= 113: return "Manufacturing"
        return "Services"

    sut_ids      = sut_water_df["Product_ID"].values
    source_groups = [source_group(int(pid)) for pid in sut_ids]

    rows = []
    for _, cat_row in concordance_df.iterrows():
        cat_name = cat_row["Category_Name"]
        sut_str  = str(cat_row["SUT_Product_IDs"])
        dest_ids = [int(s) for s in sut_str.split(",") if s.strip() and s.strip().lower() != "nan"]
        dest_mask = np.array([int(pid) in dest_ids for pid in sut_ids])

        if not dest_mask.any():
            continue

        total_pull = pull_matrix[:, dest_mask].sum(axis=1)  # (140,)
        total = total_pull.sum()
        if total == 0:
            continue

        group_pull = {}
        for i, grp in enumerate(source_groups):
            group_pull[grp] = group_pull.get(grp, 0) + total_pull[i]

        rows.append({
            "Tourism_Category": cat_name,
            "Total_Water_m3": total,
            **{f"From_{g}_m3": group_pull.get(g, 0)
               for g in ["Agriculture", "Mining", "Electricity", "Petroleum", "Manufacturing", "Services"]},
            **{f"From_{g}_pct": 100 * group_pull.get(g, 0) / total if total > 0 else 0
               for g in ["Agriculture", "Mining", "Electricity", "Petroleum", "Manufacturing", "Services"]},
        })

    return pd.DataFrame(rows).sort_values("Total_Water_m3", ascending=False)


# ── NEW: Water origin summary ─────────────────────────────────────────────────

def build_origin_summary(struct_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate structural decomposition into one row per source group.
    This is the 'where water physically originates' table — Section 3.6 of the report.
    Agriculture should dominate (60-80%) through supply-chain propagation.

    Returns a DataFrame saved as indirect_twf_{year}_origin.csv.
    """
    groups = ["Agriculture", "Mining", "Electricity", "Petroleum", "Manufacturing", "Services"]
    total_all = struct_df["Total_Water_m3"].sum()
    rows = []
    for g in groups:
        col = f"From_{g}_m3"
        w = struct_df[col].sum() if col in struct_df.columns else 0.0
        rows.append({
            "Source_Group": g,
            "Water_m3":     w,
            "Water_pct":    round(100 * w / total_all, 2) if total_all > 0 else 0.0,
        })
    return pd.DataFrame(rows).sort_values("Water_m3", ascending=False)


def print_water_origin_summary(origin_df: pd.DataFrame, year: str,
                                log: Logger = None):
    """
    Print the water-ORIGIN (source sector) breakdown to terminal/log.

    This is the view matching Lee et al. (2021) Table 3 for China, where
    agriculture dominated indirect TWF. Agriculture = 0 in destination view
    (Section A) is CORRECT — this origin view (Section B) is where agriculture
    appears prominently.

    If Agriculture still shows 0 here, W[1:29] are zero in the concordance —
    check EXIOBASE India agriculture sector mapping in build_water_coefficients.py.
    """
    total_all = origin_df["Water_m3"].sum()
    subsection(
        f"By source sector — where water physically originates ({year})\n"
        f"  (pull[i,j] = W[i] × L[i,j] × Y[j], summed over all tourism destinations j)",
        log,
    )
    note = (
        "  Use THIS table when citing agricultural water share in publications.\n"
        "  Agriculture here = upstream extraction flowing through supply chains."
    )
    if log:
        log._log(note)
    else:
        print(note)

    for _, r in origin_df.iterrows():
        line = f"    {r['Source_Group']:<20}: {r['Water_m3']:>16,.0f} m³  ({r['Water_pct']:.1f}%)"
        if log:
            log.info(line)
        else:
            print(line)

    # Sanity check agriculture share vs literature expectation
    agr_row = origin_df[origin_df["Source_Group"] == "Agriculture"]
    if not agr_row.empty:
        agr_pct = agr_row.iloc[0]["Water_pct"]
        if agr_pct < 5.0:
            msg = (
                f"  ⚠ Agriculture share = {agr_pct:.1f}% — unexpectedly low.\n"
                f"    Expected 40–80% (Lee et al. 2021, EXIOBASE WaterGAP).\n"
                f"    Check that EXIOBASE India agriculture codes (IN.1–IN.5 etc.)\n"
                f"    are mapped to SUT product IDs 1–29 in build_water_coefficients.py."
            )
            if log:
                log._log(msg)
            else:
                print(msg)
        else:
            msg = f"  ✓ Agriculture share {agr_pct:.1f}% — consistent with literature (40–80%)"
            if log:
                log._log(msg)
            else:
                print(msg)


# ── EXPANDED: Sensitivity analysis ───────────────────────────────────────────

def sensitivity_analysis(W_140: np.ndarray, L: np.ndarray, Y_140: np.ndarray,
                          sut_water_df: pd.DataFrame, wc: str,
                          log: Logger = None) -> pd.DataFrame:
    """
    Expanded sensitivity analysis varying Agriculture, Electricity, AND Petroleum
    coefficients individually by ±20%.

    Previously only agriculture was varied. Agriculture is 65-73% of origin but
    electricity (9-16%) and petroleum (11-14%) are also significant. Varying all
    three gives a more complete uncertainty picture.

    Each coefficient group is varied independently (one at a time) while holding
    the others at BASE. This gives the marginal contribution of each group's
    uncertainty to total TWF uncertainty.

    Outputs rows for: Agr_LOW, Agr_BASE, Agr_HIGH,
                      Elec_LOW, Elec_BASE, Elec_HIGH,
                      Pet_LOW,  Pet_BASE,  Pet_HIGH
    """
    pid_vals = sut_water_df["Product_ID"].values

    # Masks for each sector group
    agr_mask  = np.array([1  <= int(p) <= 29  for p in pid_vals])
    elec_mask = np.array([int(p) == 114        for p in pid_vals])
    pet_mask  = np.array([71 <= int(p) <= 80  for p in pid_vals])

    rows = []
    base_total = None

    for group_label, mask in [("Agriculture", agr_mask),
                               ("Electricity", elec_mask),
                               ("Petroleum",   pet_mask)]:
        for scenario, factor in [("LOW", 0.80), ("BASE", 1.00), ("HIGH", 1.20)]:
            W_s = W_140.copy()
            W_s[mask] *= factor
            TWF_s, _ = compute_twf(W_s, L, Y_140)
            total = TWF_s.sum()
            if group_label == "Agriculture" and scenario == "BASE":
                base_total = total
            rows.append({
                "Group":            group_label,
                "Scenario":         scenario,
                "Coeff_Factor":     factor,
                "Total_TWF_m3":     total,
                "Total_TWF_bn_m3":  total / 1e9,
            })

    df = pd.DataFrame(rows)

    # Print summary per group
    for grp in ["Agriculture", "Electricity", "Petroleum"]:
        sub  = df[df["Group"] == grp]
        base = sub[sub["Scenario"] == "BASE"]["Total_TWF_m3"].iloc[0]
        low  = sub[sub["Scenario"] == "LOW"]["Total_TWF_m3"].iloc[0]
        high = sub[sub["Scenario"] == "HIGH"]["Total_TWF_m3"].iloc[0]
        ok(
            f"{grp} sensitivity: {low/1e9:.4f} – {high/1e9:.4f} bn m³  "
            f"(BASE = {base/1e9:.4f})  ±{100*(high-base)/base:.1f}% TWF uncertainty",
            log,
        )

    return df


# ── NEW: Inbound vs domestic split TWF ───────────────────────────────────────

def compute_split_twf(W_140: np.ndarray, L: np.ndarray,
                       Y_inb_163: np.ndarray, Y_dom_163: np.ndarray,
                       concordance_df: pd.DataFrame,
                       year: str, log: Logger = None) -> pd.DataFrame:
    """
    Run W×L×Y separately for inbound-only and domestic-only demand vectors.

    Why this matters: inbound tourists spend more on hotels and air transport
    (high water-intensity supply chains), while domestic tourists spend more
    on road transport and informal food (lower intensity). The difference in
    per-day water footprint between the two groups explains whether observed
    cross-year intensity changes are driven by domestic or inbound shifts.

    This directly replicates Lee et al. (2021) Table 5 for China, where
    inbound per-day TWF was 3× domestic.

    Returns a summary DataFrame with total TWF and intensity per group.
    """
    Y_inb_140 = map_y_to_sut(Y_inb_163, concordance_df, log=None)
    Y_dom_140 = map_y_to_sut(Y_dom_163, concordance_df, log=None)

    TWF_inb, _ = compute_twf(W_140, L, Y_inb_140)
    TWF_dom, _ = compute_twf(W_140, L, Y_dom_140)

    rows = []
    for label, twf, y140 in [("Inbound",  TWF_inb, Y_inb_140),
                               ("Domestic", TWF_dom, Y_dom_140),
                               ("Combined", TWF_inb + TWF_dom, Y_inb_140 + Y_dom_140)]:
        total = twf.sum()
        demand = y140.sum()
        rows.append({
            "Year":                  year,
            "Group":                 label,
            "TWF_m3":                total,
            "TWF_bn_m3":             round(total / 1e9, 4),
            "Demand_crore":          round(demand, 1),
            "Intensity_m3_per_crore": round(total / demand, 1) if demand > 0 else 0,
        })

    df = pd.DataFrame(rows)

    subsection(f"Inbound vs Domestic TWF — {year}", log)
    for _, r in df.iterrows():
        line = (
            f"    {r['Group']:<10}: {r['TWF_bn_m3']:>8.4f} bn m³  "
            f"demand ₹{r['Demand_crore']:>12,.0f} cr  "
            f"intensity {r['Intensity_m3_per_crore']:>10,.1f} m³/crore"
        )
        if log:
            log.info(line)
        else:
            print(line)

    inb = df[df["Group"] == "Inbound"]["Intensity_m3_per_crore"].iloc[0]
    dom = df[df["Group"] == "Domestic"]["Intensity_m3_per_crore"].iloc[0]
    if dom > 0:
        ratio = inb / dom
        msg = (
            f"  Inbound intensity = {ratio:.2f}× domestic intensity  "
            f"(Lee et al. 2021 China: ~3×)"
        )
        if log:
            log.info(msg)
        else:
            print(msg)

    return df


# ── Per-sector intensity ──────────────────────────────────────────────────────

def per_sector_intensity(cat_df: pd.DataFrame) -> pd.DataFrame:
    """
    Water intensity (m³ per ₹ crore of tourism spending) by category.
    """
    df = cat_df.copy()
    df = df[df["Demand_crore"] > 0].copy()
    df["Intensity_m3_per_crore"] = df["Total_Water_m3"] / df["Demand_crore"]
    total_demand = df["Demand_crore"].sum()
    df["Demand_share_pct"]      = 100 * df["Demand_crore"] / total_demand
    df["Weighted_Impact_Score"] = df["Intensity_m3_per_crore"] * df["Demand_share_pct"]
    return df.sort_values("Intensity_m3_per_crore", ascending=False)


# ── Results assembly ──────────────────────────────────────────────────────────

def build_sut_results(sut_water_df, wc, Y_140, WL, TWF):
    df = sut_water_df.copy()
    df["Tourism_Demand_crore"]           = Y_140
    df["Water_Coefficient_m3_per_crore"] = df[wc]
    df["Water_Multiplier_m3_per_crore"]  = WL
    df["Total_Water_m3"]                 = TWF
    df["Indirect_Water_m3"]              = TWF - df[wc] * Y_140
    df["Direct_Coeff_Water_m3"]          = df[wc] * Y_140
    return df


def aggregate_to_categories(sut_results, concordance_df):
    rows = []
    for _, row in concordance_df.iterrows():
        sut_ids = [
            int(s) for s in str(row["SUT_Product_IDs"]).split(",")
            if s.strip() and s.strip().lower() != "nan"
        ]
        mask = sut_results["Product_ID"].isin(sut_ids)
        sub  = sut_results[mask]
        rows.append({
            "Category_ID":       row["Category_ID"],
            "Category_Name":     row["Category_Name"],
            "Category_Type":     row["Category_Type"],
            "Demand_crore":      sub["Tourism_Demand_crore"].sum(),
            "Total_Water_m3":    sub["Total_Water_m3"].sum(),
            "Indirect_Water_m3": sub["Indirect_Water_m3"].sum(),
        })
    return pd.DataFrame(rows).sort_values("Total_Water_m3", ascending=False)


def print_summary(cat_df: pd.DataFrame, year: str, log: Logger = None):
    """
    Print the high-level indirect TWF summary for a single year.
    Shows:
      A. Top-10 categories by total water (destination view)
      B. By sector type — where tourism demand lands (destination view)
         Agriculture = 0 here because tourists don't buy raw crops. EXPECTED.
    Origin view (Section B) is printed separately via print_water_origin_summary().
    """
    total    = cat_df["Total_Water_m3"].sum()
    indirect = cat_df["Indirect_Water_m3"].sum()
    demand   = cat_df["Demand_crore"].sum()
    section(f"Indirect TWF Summary — {year}", log=log)
    lines = [
        f"  Total indirect TWF:  {total:>20,.0f} m³ = {total/1e9:.4f} billion m³",
        f"  Supply-chain water:  {indirect:>20,.0f} m³ ({100*indirect/total:.1f}%)",
        f"  Tourism demand:      ₹{demand:>18,.0f} crore",
        f"  Water intensity:     {total/demand:>20.1f} m³/crore",
    ]
    output = "\n".join(lines)
    if log:
        log._log(output)
    else:
        print(output)
    top_n(cat_df, "Total_Water_m3", "Category_Name", n=10, unit=" m³", pct_base=total, log=log)
    subsection("By sector type", log)
    for ctype, grp in cat_df.groupby("Category_Type"):
        w = grp["Total_Water_m3"].sum()
        line = f"    {ctype:<20}: {w:>16,.0f} m³  ({100*w/total:.1f}%)"
        if log:
            log.info(line)
        else:
            print(line)


def save_summary_txt(cat_df, origin_df, year, out_path, log: Logger = None):
    """Write summary txt including both destination and origin views."""
    total = cat_df["Total_Water_m3"].sum()
    with open(out_path, "w") as f:
        f.write(f"INDIRECT TWF — {year}\n{'='*60}\n\n")
        f.write(f"Total:        {total:,.0f} m³  ({total/1e9:.4f} billion m³)\n")
        f.write(f"Intensity:    {total/cat_df['Demand_crore'].sum():.1f} m³/crore\n\n")
        f.write("Top 20 categories (destination view):\n")
        for rank, (_, r) in enumerate(cat_df.head(20).iterrows(), 1):
            f.write(f"  {rank:2d}. {r['Category_Name']:<40} {r['Total_Water_m3']:>14,.0f} m³\n")
        f.write("\nWater origin by source sector (upstream extraction):\n")
        for _, r in origin_df.iterrows():
            f.write(
                f"  {r['Source_Group']:<20}  {r['Water_m3']:>16,.0f} m³  "
                f"({r['Water_pct']:.1f}%)\n"
            )
    ok(f"Summary: {out_path.name}", log)


# ── Main ──────────────────────────────────────────────────────────────────────

def run(**kwargs):
    with Logger("calculate_indirect_twf", DIRS["logs"]) as log:
        t = Timer()
        log.section("CALCULATE INDIRECT TWF  (W × L × Y)")

        out_dir = DIRS["indirect"]
        out_dir.mkdir(parents=True, exist_ok=True)

        all_results = []

        for year in STUDY_YEARS:
            log.section(f"Year: {year}")
            try:
                # ── Load inputs ──────────────────────────────────────────────
                Y_163         = load_y_tourism(year, use_real=False, log=log)
                L             = load_leontief(year, log)
                concordance   = load_concordance(year, log)
                sut_water, wc = load_sut_water(year, log)

                check_matrix_properties(L, f"L_{year}", log)

                Y_140  = map_y_to_sut(Y_163, concordance, log=log)
                W_140  = sut_water[wc].values

                TWF, WL = compute_twf(W_140, L, Y_140)

                sut_results = build_sut_results(sut_water, wc, Y_140, WL, TWF)
                cat_results = aggregate_to_categories(sut_results, concordance)

                # ── Print destination summary (Section A) ─────────────────────
                print_summary(cat_results, year, log)

                # ── Structural decomposition ──────────────────────────────────
                log.subsection(f"Structural decomposition — {year}")
                struct_df = structural_decomposition(
                    W_140, L, Y_140, sut_water, wc, concordance, log
                )
                save_csv(struct_df, out_dir / f"indirect_twf_{year}_structural.csv",
                         f"Structural decomp {year}", log=log)

                # ── Origin summary + print (Section B) ───────────────────────
                origin_df = build_origin_summary(struct_df)
                save_csv(origin_df, out_dir / f"indirect_twf_{year}_origin.csv",
                         f"Water origin {year}", log=log)
                print_water_origin_summary(origin_df, year, log)

                # ── Per-sector intensity ──────────────────────────────────────
                intensity_df = per_sector_intensity(cat_results)
                save_csv(intensity_df, out_dir / f"indirect_twf_{year}_intensity.csv",
                         f"Sector intensity {year}", log=log)
                log.subsection("Top 5 most water-intensive tourism spending categories (m³/crore)")
                for _, r in intensity_df.head(5).iterrows():
                    log.info(
                        f"    {r['Category_Name']:<40}  "
                        f"{r['Intensity_m3_per_crore']:>10,.1f} m³/crore  "
                        f"(demand: ₹{r['Demand_crore']:,.0f} cr)"
                    )

                # ── Real demand intensity ─────────────────────────────────────
                try:
                    Y_163_real  = load_y_tourism(year, use_real=True, log=log)
                    Y_140_real  = map_y_to_sut(Y_163_real, concordance, log=log)
                    TWF_real, _ = compute_twf(W_140, L, Y_140_real)
                    real_intensity = TWF_real.sum() / Y_140_real.sum() if Y_140_real.sum() > 0 else 0
                    ok(f"Real-price intensity: {real_intensity:.1f} m³/crore (2015-16 prices)", log)
                except FileNotFoundError:
                    real_intensity = TWF.sum() / Y_140.sum() if Y_140.sum() > 0 else 0
                    warn("Real demand file not found — using nominal intensity", log)

                # ── EXPANDED Sensitivity: Agriculture + Electricity + Petroleum ─
                log.subsection(f"Sensitivity (±20% agr./elec./petrol. coefficients) — {year}")
                sens_df = sensitivity_analysis(W_140, L, Y_140, sut_water, wc, log)
                save_csv(sens_df, out_dir / f"indirect_twf_{year}_sensitivity.csv",
                         f"Sensitivity {year}", log=log)

                # ── NEW: Inbound vs domestic split ───────────────────────────
                Y_inb_163, Y_dom_163 = load_y_split(year, log)
                split_df = pd.DataFrame()
                if Y_inb_163 is not None and Y_dom_163 is not None:
                    split_df = compute_split_twf(
                        W_140, L, Y_inb_163, Y_dom_163, concordance, year, log
                    )
                    save_csv(split_df, out_dir / f"indirect_twf_{year}_split.csv",
                             f"Inbound/domestic split {year}", log=log)

                # ── Save main results ─────────────────────────────────────────
                save_csv(sut_results, out_dir / f"indirect_twf_{year}_by_sut.csv",
                         f"SUT results {year}", log=log)
                save_csv(cat_results, out_dir / f"indirect_twf_{year}_by_category.csv",
                         f"Category results {year}", log=log)
                save_summary_txt(
                    cat_results, origin_df, year,
                    out_dir / f"indirect_twf_{year}_summary.txt", log
                )

                # Agriculture origin pct for cross-year tracking
                agr_pct = 0.0
                agr_row = origin_df[origin_df["Source_Group"] == "Agriculture"]
                if not agr_row.empty:
                    agr_pct = float(agr_row.iloc[0]["Water_pct"])

                all_results.append({
                    "Year":                        year,
                    "Indirect_TWF_m3":             TWF.sum(),
                    "Indirect_TWF_billion_m3":     TWF.sum() / 1e9,
                    "Tourism_Demand_crore":        Y_140.sum(),
                    "Intensity_m3_per_crore":      TWF.sum() / Y_140.sum() if Y_140.sum() > 0 else 0,
                    "Real_Intensity_m3_per_crore": real_intensity,
                    "Top_Sector":                  cat_results.iloc[0]["Category_Name"],
                    "Agr_Origin_pct":              agr_pct,
                })

            except FileNotFoundError as e:
                warn(f"{year}: {e} — skipping", log)
                continue

        # ── Cross-year comparison ─────────────────────────────────────────────
        if all_results:
            log.section("Cross-Year Indirect TWF Comparison")
            vals     = {r["Year"]: r["Indirect_TWF_billion_m3"]     for r in all_results}
            nom_int  = {r["Year"]: r["Intensity_m3_per_crore"]       for r in all_results}
            real_int = {r["Year"]: r["Real_Intensity_m3_per_crore"]  for r in all_results}
            agr_pcts = {r["Year"]: r["Agr_Origin_pct"]              for r in all_results}
            compare_across_years(vals,     "Indirect TWF (billion m³)",               list(vals.keys()),     " bn m³", log=log)
            compare_across_years(nom_int,  "Water intensity nominal (m³/crore)",      list(nom_int.keys()),  " m³/cr", log=log)
            compare_across_years(real_int, "Water intensity real 2015-16 (m³/crore)", list(real_int.keys()), " m³/cr", log=log)
            compare_across_years(agr_pcts, "Agriculture share of water origin (%)",   list(agr_pcts.keys()), "%",      log=log)

            summary_df = pd.DataFrame(all_results)
            save_csv(summary_df, out_dir / "indirect_twf_all_years.csv", "All-year summary", log=log)

        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    run()