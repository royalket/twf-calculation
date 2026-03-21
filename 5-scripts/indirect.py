"""
indirect.py
===========
MERGE of calculate_indirect_twf.py + calculate_indirect_energy.py

Core formula (EEIO Leontief):
    Footprint = C × L × Y

Where:
    C   = diagonal coefficient vector (water m³/₹cr  OR  energy MJ/₹cr)
    L   = Leontief inverse (140×140), from build_io.py
    Y   = 140-sector tourism demand vector (₹ crore), from build_demand.py

Water-specific extras: WSI scarce water, green/blue split, structural decomposition.
Energy-specific extras: Emission/Final ratio, extrapolation flag.

Entry points:
    run(stressor="water")
    run(stressor="energy")

# ─────────────────────────────────────────────────────────────────────────────
# TODO
# ─────────────────────────────────────────────────────────────────────────────
# TODO-1  Replace sys.path.insert with proper package (pyproject.toml).
#
# TODO-2  map_y_to_sut() is identical for both stressors. Move it to utils.py
#         so build_demand.py and any future stressor can import it from one place.
#
# TODO-3  sensitivity_analysis() uses hardcoded product-ID ranges for sectors
#         (e.g. pid==114 for Electricity, 71<=pid<=80 for Petroleum). These
#         should be named constants in config.py, not magic numbers.
#
# TODO-4  Water structural_decomposition() and compute_split_twf() are water-only.
#         Consider moving them to a separate water_eeio.py if the file grows too large
#         after the merge of the indirect files.
#
# TODO-5  Convert "BUG FIX" comments in the original files into pytest tests:
#           - Green split conservation: inb + dom ≈ aggregate green (within 0.5%)
#           - WSI application: scarce/blue ratio in [0.30, 0.95]
#           - Product_ID column lookup (not index) in aggregate_to_categories()
# ─────────────────────────────────────────────────────────────────────────────

BUG FIXES (vs previous version)
─────────────────────────────────────────────────────────────────────────────
FIX-1  map_y_to_sut — assigned_exio guard was set but never enforced.
       The demand accumulation `demand += Y_163[idx]` was unconditionally
       outside the `if code not in assigned_exio:` block, so any EXIO code
       appearing in N concordance rows was added to Y_140 N times instead of
       once.  Fixed: `continue` immediately if the code was already assigned.

FIX-2  aggregate_to_categories — overlapping SUT_Product_IDs caused
       double-counting across category rows.  If Product_ID 45 appeared in
       both "Food" and "Beverages" rows of the concordance, its
       Total_Water_m3 was summed into both categories.  The resulting
       category total exceeded the SUT total, and compare.py's
       `df["Total_Water_m3"].sum()` (used to fill the TSA table) inherited
       that inflation.  Fixed: a `seen_product_ids` set ensures each
       Product_ID is attributed to at most one category.

FIX-3  structural_decomposition — same SUT_Product_IDs overlap issue as
       FIX-2.  If a sid appeared in N concordance rows, its Leontief
       contribution `C[src] * L[src,:] * cat_y` was emitted N times.
       Fixed: `seen_sids` set applied per concordance row.

─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))   # TODO-1: remove after packaging
from config import (
    DIRS, YEARS, STUDY_YEARS, USD_INR,
    TJ_TO_MJ, ENERGY_ROW_FINAL, ENERGY_ROW_EMISSION,
)
from config import (
    WSI_WEIGHTS, WSI_RAW_SCORES,
)
from utils import (
    section, subsection, ok, warn, save_csv, safe_csv,
    read_csv, compare_across_years, top_n, Timer, Logger,
    crore_to_usd_m, classify_source_group, safe_divide,
)

Stressor = Literal["water", "energy", "depletion"]

# ── Per-stressor configuration ────────────────────────────────────────────────
_CFG: dict[str, dict] = {
    "water": {
        "coeff_file":       "water_coefficients_140_{io_tag}.csv",
        "coeff_col_fn":     lambda wy: f"Water_{wy}_Blue_m3_per_crore",
        "coeff_col_sec_fn": lambda wy: f"Water_{wy}_Green_m3_per_crore",
        "unit":             "m3",
        "bn_label":         "bn m³",
        "out_dir_key":      "indirect",
        "log_name":         "calculate_indirect_twf",
        "section_title":    "CALCULATE INDIRECT WATER FOOTPRINT  (W × L × Y)",
        "split_val_col":    "TWF_m3",
        "split_sec_col":    "Green_m3",
    },
    "energy": {
        "coeff_file":       "energy_coefficients_140_{io_tag}.csv",
        "coeff_col_fn":     lambda wy: f"Energy_{wy}_Final_MJ_per_crore",
        "coeff_col_sec_fn": lambda wy: f"Energy_{wy}_Emission_MJ_per_crore",
        "unit":             "MJ",
        "bn_label":         "bn MJ",
        "out_dir_key":      "indirect_energy",
        "log_name":         "calculate_indirect_energy",
        "section_title":    "CALCULATE INDIRECT ENERGY FOOTPRINT  (E × L × Y)",
        "split_val_col":    "Final_Primary_MJ",
        "split_sec_col":    "Emission_MJ",
    },
    "depletion": {
        "coeff_file":       "depletion_coefficients_140_{io_tag}.csv",
        "coeff_col_fn":     lambda wy: f"Depletion_{wy}_t_per_crore",
        "coeff_col_sec_fn": lambda wy: f"Depletion_{wy}_t_per_crore_sec",
        "unit":             "t",
        "bn_label":         "M tonnes",
        "out_dir_key":      "indirect_depletion",
        "log_name":         "calculate_indirect_depletion",
        "section_title":    "CALCULATE INDIRECT DEPLETION  (D × L × Y)",
        "split_val_col":    "Total_Depletion_t",
        "split_sec_col":    "Fossil_Total_t",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# SHARED UTILITIES
# TODO-2: map_y_to_sut should move to utils.py
# ══════════════════════════════════════════════════════════════════════════════

def map_y_to_sut(Y_163: np.ndarray, concordance_df: pd.DataFrame,
                  n_sut: int = 140, log: Logger = None) -> np.ndarray:
    """
    Map 163-sector EXIOBASE demand to 140-sector SUT via concordance.
    Identical logic for both stressors — single implementation.

    FIX-1: Each EXIO code is assigned to Y_140 exactly once across all
    concordance rows.  The original code set `assigned_exio[code] = True`
    inside the guard but then accumulated `demand += Y_163[idx]`
    unconditionally outside it, so codes appearing in multiple concordance
    rows were added multiple times.  The fix moves the accumulation inside
    the guard with a `continue` early-exit for already-seen codes.
    """
    Y_140        = np.zeros(n_sut)
    assigned_exio: dict = {}

    for _, row in concordance_df.iterrows():
        exio_str   = str(row.get("EXIOBASE_Sectors", ""))
        sut_str    = str(row.get("SUT_Product_IDs",  ""))
        exio_codes = [e.strip() for e in exio_str.split(",")
                      if e.strip() and e.strip().lower() != "nan"]
        sut_ids    = [int(s.strip()) for s in sut_str.split(",")
                      if s.strip() and s.strip().lower() != "nan"]

        demand = 0.0
        for code in exio_codes:
            # FIX-1: skip codes already attributed to a previous concordance row
            if code in assigned_exio:
                continue
            assigned_exio[code] = True

            if code == "IN":
                idx = 0
            elif code.startswith("IN."):
                try:
                    idx = int(code.split(".")[1])
                except (IndexError, ValueError):
                    continue
            else:
                continue

            if 0 <= idx < len(Y_163):
                demand += Y_163[idx]

        if not sut_ids or demand == 0:
            continue
        per_sut = demand / len(sut_ids)
        for sid in sut_ids:
            if 1 <= sid <= n_sut:
                Y_140[sid - 1] += per_sut

    ok(f"Y_140: ₹{Y_140.sum():,.0f} crore  "
       f"(coverage {100 * Y_140.sum() / max(Y_163.sum(), 1):.1f}%)", log)
    return Y_140


# ══════════════════════════════════════════════════════════════════════════════
# INPUT LOADING
# ══════════════════════════════════════════════════════════════════════════════

def _load_inputs(year: str, stressor: Stressor, log: Logger = None) -> dict | None:
    """Load all inputs for C × L × Y. Returns None if any required file is missing."""
    cfg_s = _CFG[stressor]
    cfg_y = YEARS[year]
    io_tag     = cfg_y["io_tag"]
    io_year    = cfg_y["io_year"]
    water_year = cfg_y["water_year"]

    # Demand vector (163 EXIOBASE sectors)
    y_path = DIRS["demand"] / f"Y_tourism_{year}.csv"
    if not y_path.exists():
        warn(f"Demand vector missing: {y_path} — run build_demand.py first", log)
        return None
    Y_163 = read_csv(y_path)["Tourism_Demand_crore"].values
    ok(f"Y_tourism {year}: ₹{Y_163.sum():,.0f} cr  {np.count_nonzero(Y_163)}/163 non-zero", log)

    # Leontief inverse
    l_path = DIRS["io"] / io_year / f"io_L_{io_tag}.csv"
    if not l_path.exists():
        warn(f"Leontief inverse missing: {l_path} — run build_io.py first", log)
        return None
    L = read_csv(l_path, index_col=0).values
    ok(f"L ({io_year}): {L.shape}  diag mean={np.diag(L).mean():.4f}", log)

    # Concordance (for Y mapping and category aggregation)
    conc_path = DIRS["concordance"] / f"concordance_{io_tag}.csv"
    if not conc_path.exists():
        warn(f"Concordance missing: {conc_path}", log)
        return None
    concordance = read_csv(conc_path)

    # Stressor coefficients
    coeff_path = DIRS["concordance"] / cfg_s["coeff_file"].format(io_tag=io_tag)
    if not coeff_path.exists():
        warn(f"Coefficients missing: {coeff_path} — run build_coefficients.py first", log)
        return None
    sut_df = read_csv(coeff_path)

    primary_col   = cfg_s["coeff_col_fn"](water_year)
    secondary_col = cfg_s["coeff_col_sec_fn"](water_year)

    # Column fallback with friendly warning
    for attr, col in [("primary_col", primary_col), ("secondary_col", secondary_col)]:
        if col not in sut_df.columns:
            suffix = primary_col.split("_", 2)[-1] if attr == "primary_col" else secondary_col.split("_", 2)[-1]
            candidates = [c for c in sut_df.columns if suffix.lower() in c.lower()]
            if candidates:
                if attr == "primary_col":
                    primary_col = candidates[0]
                else:
                    secondary_col = candidates[0]
                warn(f"Column fallback [{stressor}]: using '{candidates[0]}'", log)
            else:
                if attr == "secondary_col":
                    warn(f"Secondary column '{col}' not found — secondary footprint will be zero", log)
                    secondary_col = None
                else:
                    warn(f"Primary column '{col}' not found. Available: {sut_df.columns.tolist()}", log)
                    return None

    # Optional inbound/domestic split demand
    Y_inb = Y_dom = None
    f_inb = DIRS["demand"] / f"Y_tourism_{year}_inbound.csv"
    f_dom = DIRS["demand"] / f"Y_tourism_{year}_domestic.csv"
    if f_inb.exists() and f_dom.exists():
        Y_inb = read_csv(f_inb)["Tourism_Demand_crore"].values
        Y_dom = read_csv(f_dom)["Tourism_Demand_crore"].values
        ok(f"Split demand {year}: inbound ₹{Y_inb.sum():,.0f} cr  domestic ₹{Y_dom.sum():,.0f} cr", log)
    else:
        warn(f"Split demand files not found for {year} — inbound/domestic split skipped", log)

    return {
        "Y_163": Y_163, "L": L, "concordance": concordance, "sut_df": sut_df,
        "primary_col": primary_col, "secondary_col": secondary_col,
        "Y_inb": Y_inb, "Y_dom": Y_dom,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CORE EEIO COMPUTATION  C × L × Y
# ══════════════════════════════════════════════════════════════════════════════

def compute_footprint(C: np.ndarray, L: np.ndarray, Y: np.ndarray,
                      stressor: Stressor) -> tuple[np.ndarray, np.ndarray]:
    """
    Footprint = C @ L * Y  (element-wise product at end).
    Returns (footprint_vector, CL_vector), both shape (140,).
    CL[j] = resource per ₹ crore of demand for product j.
    """
    CL  = C @ L
    FP  = CL * Y
    cfg = _CFG[stressor]
    ok(f"Footprint [{stressor}]: {FP.sum()/1e9:.4f} {cfg['bn_label']}  "
       f"| CL mean={CL.mean():.4f}  Y sum={Y.sum():,.0f} cr")
    return FP, CL


# ══════════════════════════════════════════════════════════════════════════════
# RESULT BUILDERS  (stressor-specific column names matching old output schema)
# ══════════════════════════════════════════════════════════════════════════════
#
# Water column schema (matches calculate_indirect_twf.py output exactly):
#   Tourism_Demand_crore, Water_Multiplier_m3_per_crore, Total_Water_m3,
#   Green_Water_m3, Source_Group, Water_pct, WSI_weight, Scarce_m3,
#   Scarce_pct, Multiplier_Ratio, Product_ID
#
# Energy column schema (matches calculate_indirect_energy.py output exactly):
#   Tourism_Demand_crore, EL_MJ_per_crore, Final_Primary_MJ, Emission_MJ,
#   Source_Group, Energy_pct, Emission_Final_ratio, Product_ID
#
# Shared columns: Product_ID, Tourism_Demand_crore, Source_Group

def build_sut_results(sut_df: pd.DataFrame, primary_col: str, secondary_col: str | None,
                       Y_140: np.ndarray, CL: np.ndarray,
                       FP_primary: np.ndarray, FP_secondary: np.ndarray | None,
                       stressor: Stressor) -> pd.DataFrame:
    """
    Build 140-product SUT results DataFrame with stressor-specific column names.

    Water output columns (matches calculate_indirect_twf.py):
        Tourism_Demand_crore, Water_Multiplier_m3_per_crore, Total_Water_m3,
        Green_Water_m3, Source_Group, Water_pct, WSI_weight, Scarce_m3,
        Scarce_pct, Multiplier_Ratio, Product_ID

    Energy output columns (matches calculate_indirect_energy.py):
        Tourism_Demand_crore, EL_MJ_per_crore, Final_Primary_MJ, Emission_MJ,
        Source_Group, Energy_pct, Emission_Final_ratio, Product_ID
    """
    df  = sut_df.copy().reset_index(drop=True)   # guarantee 0-based index for array assignments
    n   = len(FP_primary)
    tot = FP_primary.sum()

    df["Product_ID"]           = range(1, n + 1)
    df["Tourism_Demand_crore"] = Y_140
    df["Source_Group"]         = [classify_source_group(i + 1) for i in range(n)]

    if stressor == "water":
        df["Water_Multiplier_m3_per_crore"] = CL
        df["Total_Water_m3"]                = FP_primary
        df["Green_Water_m3"]                = FP_secondary if FP_secondary is not None else 0.0
        df["Water_pct"]                     = 100 * FP_primary / max(tot, 1e-9)

        # WSI scarce water
        wsi_map = WSI_WEIGHTS
        df["WSI_weight"] = df["Source_Group"].map(
            lambda g: wsi_map.get(g, wsi_map.get("Manufacturing", 0.814))
        ).fillna(0.814)
        df["Scarce_m3"]  = df["Total_Water_m3"] * df["WSI_weight"]
        df["Scarce_pct"] = 100 * df["Scarce_m3"] / max(df["Scarce_m3"].sum(), 1e-9)

        # Water multiplier ratio (WL[j] / demand-weighted economy avg WL)
        total_demand = float(Y_140.sum())
        if total_demand > 0:
            economy_avg_WL = float((CL * Y_140).sum()) / total_demand
            if economy_avg_WL > 0:
                df["Multiplier_Ratio"] = CL / economy_avg_WL
            else:
                df["Multiplier_Ratio"] = 1.0
        else:
            df["Multiplier_Ratio"] = 1.0

        return df.sort_values("Total_Water_m3", ascending=False)

    else:  # energy
        df["EL_MJ_per_crore"]  = CL
        df["Final_Primary_MJ"] = FP_primary
        df["Emission_MJ"]      = FP_secondary if FP_secondary is not None else 0.0
        tot_mj = FP_primary.sum()
        df["Energy_pct"]       = 100 * FP_primary / max(tot_mj, 1e-9)
        # Derived unit columns
        df["Final_Primary_GJ"] = df["Final_Primary_MJ"] / 1e3
        df["Final_Primary_TJ"] = df["Final_Primary_MJ"] / 1e6
        if FP_secondary is not None and tot_mj > 0:
            df["Emission_Final_ratio"] = (
                df["Emission_MJ"] / df["Final_Primary_MJ"].replace(0, float("nan"))
            )

        return df.sort_values("Final_Primary_MJ", ascending=False)


def aggregate_to_categories(sut_results: pd.DataFrame,
                              concordance: pd.DataFrame,
                              stressor: Stressor) -> pd.DataFrame:
    """
    Aggregate 140-product results to concordance categories.

    Water output columns: Category_ID, Category_Name, Category_Type,
        Total_Water_m3, Green_Water_m3, Scarce_m3, Demand_crore,
        Water_pct, Scarce_pct, Intensity_m3_per_crore, Scarce_Intensity_m3_per_crore

    Energy output columns: Category_ID, Category_Name, Category_Type,
        Final_Primary_MJ, Emission_MJ, Demand_crore,
        Energy_pct, Intensity_MJ_per_crore

    FIX-2: A `seen_product_ids` set ensures each Product_ID contributes its
    footprint to exactly one category.  Previously, a Product_ID listed in
    the SUT_Product_IDs column of multiple concordance rows had its
    Total_Water_m3 (or Final_Primary_MJ) summed into every matching category,
    causing the category grand-total to exceed the SUT-level total.  That
    inflated number propagated directly into the TSA table via
    compare.py::_load_indirect_m3 which sums `Total_Water_m3` across all
    category rows.
    """
    rows = []
    seen_product_ids: set[int] = set()   # FIX-2: each SUT product counted once
    # FIX-3b: track skipped water/energy so data loss is quantified, not just logged
    skipped_primary = 0.0
    primary_col_name = "Total_Water_m3" if stressor == "water" else "Final_Primary_MJ"

    for _, crow in concordance.iterrows():
        sut_str = str(crow.get("SUT_Product_IDs", ""))
        all_ids = [int(s.strip()) for s in sut_str.split(",")
                   if s.strip() and s.strip().lower() != "nan"]

        # FIX-2: restrict to IDs not yet attributed to a previous category
        new_ids = [pid for pid in all_ids if pid not in seen_product_ids]
        if all_ids and len(new_ids) < len(all_ids):
            skipped = sorted(set(all_ids) - set(new_ids))
            # FIX-3b: accumulate skipped footprint volume
            skipped_sub = sut_results[sut_results["Product_ID"].isin(skipped)]
            if primary_col_name in skipped_sub.columns:
                skipped_primary += float(skipped_sub[primary_col_name].sum())
            warn(f"aggregate_to_categories: Product_IDs {skipped} already attributed "
                 f"to a prior category — skipping duplicates for "
                 f"'{crow.get('Category_Name', crow.get('Category_ID', '?'))}'")
        seen_product_ids.update(new_ids)

        sub    = sut_results[sut_results["Product_ID"].isin(new_ids)]
        demand = float(sub["Tourism_Demand_crore"].sum())

        if stressor == "water":
            water  = float(sub["Total_Water_m3"].sum())
            scarce = float(sub["Scarce_m3"].sum()) if "Scarce_m3" in sub.columns else 0.0
            green  = float(sub["Green_Water_m3"].sum()) if "Green_Water_m3" in sub.columns else 0.0
            rows.append({
                "Category_ID":   crow["Category_ID"],
                "Category_Name": crow.get("Category_Name", str(crow["Category_ID"])),
                "Category_Type": crow.get("Category_Type", ""),
                "Total_Water_m3": water,
                "Green_Water_m3": green,
                "Scarce_m3":      scarce,
                "Demand_crore":   demand,
                "Water_pct":      0.0,   # filled below
                "Scarce_pct":     0.0,
            })
        else:
            final  = float(sub["Final_Primary_MJ"].sum())
            emiss  = float(sub["Emission_MJ"].sum()) if "Emission_MJ" in sub.columns else 0.0
            rows.append({
                "Category_ID":      crow["Category_ID"],
                "Category_Name":    crow.get("Category_Name", str(crow["Category_ID"])),
                "Category_Type":    crow.get("Category_Type", ""),
                "Final_Primary_MJ": final,
                "Emission_MJ":      emiss,
                "Demand_crore":     demand,
                "Energy_pct":       0.0,  # filled below
            })

    # FIX-3b: quantified conservation check — warn if skipped footprint is material
    if skipped_primary > 0:
        sut_total_primary = float(sut_results[primary_col_name].sum()) if primary_col_name in sut_results.columns else 0.0
        if sut_total_primary > 0:
            skip_pct = 100 * skipped_primary / sut_total_primary
            if skip_pct > 0.1:
                warn(f"aggregate_to_categories: {skip_pct:.2f}% of total {stressor} footprint "
                     f"({skipped_primary:,.0f} units) skipped due to duplicate SUT_Product_IDs "
                     "in concordance — review get_concordance() in build_coefficients.py")
            else:
                ok(f"aggregate_to_categories: {skip_pct:.4f}% skipped (< 0.1% — negligible)")

    df = pd.DataFrame(rows)

    if stressor == "water":
        df = df.sort_values("Total_Water_m3", ascending=False)
        tot_w = df["Total_Water_m3"].sum()
        tot_s = df["Scarce_m3"].sum()
        df["Water_pct"]  = 100 * df["Total_Water_m3"] / tot_w if tot_w > 0 else 0.0
        df["Scarce_pct"] = 100 * df["Scarce_m3"]      / tot_s if tot_s > 0 else 0.0
        df["Intensity_m3_per_crore"] = (
            df["Total_Water_m3"] / df["Demand_crore"].replace(0, float("nan"))
        ).fillna(0)
        df["Scarce_Intensity_m3_per_crore"] = (
            df["Scarce_m3"] / df["Demand_crore"].replace(0, float("nan"))
        ).fillna(0)
    else:
        df = df.sort_values("Final_Primary_MJ", ascending=False)
        tot_mj = df["Final_Primary_MJ"].sum()
        df["Energy_pct"] = 100 * df["Final_Primary_MJ"] / tot_mj if tot_mj > 0 else 0.0
        df["Intensity_MJ_per_crore"] = (
            df["Final_Primary_MJ"] / df["Demand_crore"].replace(0, float("nan"))
        ).fillna(0)
        df["Final_Primary_GJ"] = df["Final_Primary_MJ"] / 1e3
        df["Final_Primary_TJ"] = df["Final_Primary_MJ"] / 1e6

    return df


def build_origin_summary(sut_results: pd.DataFrame, stressor: Stressor,
                          C_primary: np.ndarray = None,
                          C_secondary: np.ndarray = None,
                          L: np.ndarray = None,
                          Y: np.ndarray = None) -> pd.DataFrame:
    """
    Aggregate footprint by upstream SOURCE group — the sector where water/energy
    physically originates, not the sector where tourism demand lands.

    Water: Source_Group, Water_m3, Scarce_m3, WSI_weight, Water_pct,
           Scarce_pct, Green_Water_m3
    Energy: Source_Group, Final_Primary_MJ, Emission_MJ, Energy_pct

    SOURCE view vs DESTINATION view
    --------------------------------
    The destination view (grouping sut_results by Product_ID source group) assigns
    footprint to whatever product a tourist buys — so Agriculture = 0% because no
    tourist rupee flows directly to raw crops.

    The source view uses the pull matrix:
        pull[i, j] = C[i] * L[i, j] * Y[j]
        source_water[i] = sum_j pull[i, j]  =  C[i] * (L[i, :] @ Y)

    This correctly shows Agriculture ~80% because paddy/wheat water propagates
    through food manufacturing supply chains into tourism demand.

    C, L, Y are required for the source view. If not provided we fall back to the
    destination view (grouping sut_results) with a warning — this preserves
    backward compatibility when the function is called without the extra args.
    """
    if stressor == "water":
        if C_primary is not None and L is not None and Y is not None:
            # ── Source (pull matrix) view ─────────────────────────────────────
            n = len(C_primary)
            # source_water[i] = C[i] * sum_j L[i,j]*Y[j]
            LY          = L @ Y                             # shape (n,)
            source_w    = C_primary   * LY                 # shape (n,)
            source_g    = C_secondary * LY if C_secondary is not None else np.zeros(n)

            rows = []
            groups = sorted(set(classify_source_group(i + 1) for i in range(n)))
            for grp in groups:
                mask  = np.array([classify_source_group(i + 1) == grp for i in range(n)])
                w     = float(source_w[mask].sum())
                g     = float(source_g[mask].sum())
                wsi   = WSI_WEIGHTS.get(grp, WSI_WEIGHTS.get("Manufacturing", 0.814))
                sc    = w * wsi
                rows.append({
                    "Source_Group":    grp,
                    "Water_m3":        w,
                    "Scarce_m3":       sc,
                    "WSI_weight":      wsi,
                    "Green_Water_m3":  g,
                })

            grp_df  = pd.DataFrame(rows)
            tot_w   = grp_df["Water_m3"].sum()
            tot_s   = grp_df["Scarce_m3"].sum()
            grp_df["Water_pct"]  = 100 * grp_df["Water_m3"]  / tot_w if tot_w > 0 else 0.0
            grp_df["Scarce_pct"] = 100 * grp_df["Scarce_m3"] / tot_s if tot_s > 0 else 0.0
            return grp_df.sort_values("Water_m3", ascending=False)

        else:
            # ── Fallback: destination view (old behaviour) ────────────────────
            warn("build_origin_summary: C/L/Y not provided — "
                 "falling back to destination view; Agriculture will show ~0%")
            grp = (
                sut_results.groupby("Source_Group")
                .agg(Water_m3=("Total_Water_m3", "sum"),
                     Scarce_m3=("Scarce_m3",      "sum"))
                .reset_index()
            )
            grp["WSI_weight"]    = grp["Source_Group"].map(
                lambda g: WSI_WEIGHTS.get(g, WSI_WEIGHTS.get("Manufacturing", 0.814))
            )
            grp["Green_Water_m3"] = 0.0
            tot_w = grp["Water_m3"].sum()
            tot_s = grp["Scarce_m3"].sum()
            grp["Water_pct"]  = 100 * grp["Water_m3"]  / tot_w if tot_w > 0 else 0.0
            grp["Scarce_pct"] = 100 * grp["Scarce_m3"] / tot_s if tot_s > 0 else 0.0
            return grp.sort_values("Water_m3", ascending=False)

    else:  # energy
        if C_primary is not None and L is not None and Y is not None:
            n  = len(C_primary)
            LY = L @ Y
            source_f = C_primary   * LY
            source_e = C_secondary * LY if C_secondary is not None else np.zeros(n)

            rows = []
            groups = sorted(set(classify_source_group(i + 1) for i in range(n)))
            for grp in groups:
                mask = np.array([classify_source_group(i + 1) == grp for i in range(n)])
                rows.append({
                    "Source_Group":    grp,
                    "Final_Primary_MJ": float(source_f[mask].sum()),
                    "Emission_MJ":      float(source_e[mask].sum()),
                })
            grp_df = pd.DataFrame(rows)
            tot    = grp_df["Final_Primary_MJ"].sum()
            grp_df["Energy_pct"] = 100 * grp_df["Final_Primary_MJ"] / max(tot, 1e-9)
            return grp_df.sort_values("Final_Primary_MJ", ascending=False)

        else:
            agg_cols = {"Final_Primary_MJ": ("Final_Primary_MJ", "sum")}
            if "Emission_MJ" in sut_results.columns:
                agg_cols["Emission_MJ"] = ("Emission_MJ", "sum")
            grp = sut_results.groupby("Source_Group").agg(**agg_cols).reset_index()
            tot = grp["Final_Primary_MJ"].sum()
            grp["Energy_pct"] = 100 * grp["Final_Primary_MJ"] / max(tot, 1e-9)
            return grp.sort_values("Final_Primary_MJ", ascending=False)


def sensitivity_analysis(C: np.ndarray, L: np.ndarray, Y: np.ndarray,
                          stressor: Stressor, log: Logger = None) -> pd.DataFrame:
    """
    ±20% sensitivity on key sector groups.
    TODO-3: replace magic product-ID ranges with named constants from config.

    Water output columns:  Component, Scenario, Total_TWF_m3, Delta_pct, Scarce_m3_est
    Energy output columns: Component, Scenario, Total_IEF_MJ, Total_IEF_GJ, Delta_pct
    """
    base_fp = (C @ L * Y).sum()

    def fp_with_factor(group_fn, factor) -> float:
        C2 = C.copy()
        for i in range(len(C2)):
            if group_fn(i + 1):
                C2[i] *= factor
        return (C2 @ L * Y).sum()

    if stressor == "water":
        groups = [
            ("Agriculture", lambda pid: 1 <= pid <= 29),
            ("Electricity", lambda pid: pid == 114),
            ("Petroleum",   lambda pid: 71 <= pid <= 80),
        ]
    else:
        groups = [
            ("Electricity", lambda pid: pid == 114),
            ("Petroleum",   lambda pid: 71 <= pid <= 80),
            ("Utilities",   lambda pid: 92 <= pid <= 109),
        ]

    rows = []
    for label, group_fn in groups:
        for scenario, factor in [("LOW", 0.8), ("BASE", 1.0), ("HIGH", 1.2)]:
            fp = fp_with_factor(group_fn, factor) if scenario != "BASE" else base_fp
            if stressor == "water":
                rows.append({
                    "Component":    label,
                    "Scenario":     scenario,
                    "Total_TWF_m3": round(fp),
                    "Delta_pct":    round(100 * (fp - base_fp) / base_fp, 2) if base_fp else 0,
                    "Scarce_m3_est": round(fp * WSI_WEIGHTS.get(label, 0.814)),
                })
            else:
                rows.append({
                    "Component":    label,
                    "Scenario":     scenario,
                    "Total_IEF_MJ": round(fp),
                    "Total_IEF_GJ": round(fp / 1e3, 2),
                    "Delta_pct":    round(100 * (fp - base_fp) / base_fp, 2) if base_fp else 0,
                })
        ok(f"Sensitivity {label}: "
           f"LOW={fp_with_factor(group_fn, 0.8)/1e9:.4f}  "
           f"BASE={base_fp/1e9:.4f}  "
           f"HIGH={fp_with_factor(group_fn, 1.2)/1e9:.4f} {_CFG[stressor]['bn_label']}", log)
    return pd.DataFrame(rows)


def compute_split_footprint(C: np.ndarray, L: np.ndarray,
                              Y_inb_163: np.ndarray, Y_dom_163: np.ndarray,
                              concordance: pd.DataFrame, year: str,
                              stressor: Stressor,
                              C_secondary: np.ndarray = None,
                              log: Logger = None) -> pd.DataFrame:
    """
    Inbound vs domestic split indirect footprint.
    Column names match what outbound.py::load_inbound_split() expects per stressor.

    Water output: Year, Type, TWF_m3, TWF_bn_m3, Scarce_m3, Green_m3, Green_bn_m3, Demand_crore
    Energy output: Year, Type, Final_Primary_MJ, Final_Primary_GJ, Final_Primary_TJ,
                   Emission_MJ, Inbound_Primary, Demand_crore
    """
    cfg   = _CFG[stressor]
    Y_inb = map_y_to_sut(Y_inb_163, concordance, log=log)
    Y_dom = map_y_to_sut(Y_dom_163, concordance, log=log)
    CL    = C @ L

    fp_inb = float((CL * Y_inb).sum())
    fp_dom = float((CL * Y_dom).sum())
    sec_inb = float(((C_secondary @ L) * Y_inb).sum()) if C_secondary is not None else 0.0
    sec_dom = float(((C_secondary @ L) * Y_dom).sum()) if C_secondary is not None else 0.0

    ok(f"Split {stressor} {year}: inbound={fp_inb/1e9:.4f}  "
       f"domestic={fp_dom/1e9:.4f} {cfg['bn_label']}", log)

    if stressor == "water":
        # WSI-weighted scarce split
        wsi_vec   = np.array([WSI_WEIGHTS.get(classify_source_group(i + 1),
                                               WSI_WEIGHTS.get("Manufacturing", 0.814))
                               for i in range(len(C))])
        WL_scarce = (C * wsi_vec) @ L
        scarce_inb = float((WL_scarce * Y_inb).sum())
        scarce_dom = float((WL_scarce * Y_dom).sum())
        return pd.DataFrame([
            {
                "Year":        year,
                "Type":        "Inbound",
                "TWF_m3":      fp_inb,
                "TWF_bn_m3":   fp_inb / 1e9,
                "Scarce_m3":   scarce_inb,
                "Green_m3":    sec_inb,
                "Green_bn_m3": sec_inb / 1e9,
                "Demand_crore": float(Y_inb.sum()),
            },
            {
                "Year":        year,
                "Type":        "Domestic",
                "TWF_m3":      fp_dom,
                "TWF_bn_m3":   fp_dom / 1e9,
                "Scarce_m3":   scarce_dom,
                "Green_m3":    sec_dom,
                "Green_bn_m3": sec_dom / 1e9,
                "Demand_crore": float(Y_dom.sum()),
            },
        ])
    else:
        return pd.DataFrame([
            {
                "Year":             year,
                "Type":             "Inbound",
                "Final_Primary_MJ": fp_inb,
                "Final_Primary_GJ": fp_inb / 1e3,
                "Final_Primary_TJ": fp_inb / 1e6,
                "Emission_MJ":      sec_inb,
                "Inbound_Primary":  fp_inb,   # alias read by outbound.py
                "Demand_crore":     float(Y_inb.sum()),
            },
            {
                "Year":             year,
                "Type":             "Domestic",
                "Final_Primary_MJ": fp_dom,
                "Final_Primary_GJ": fp_dom / 1e3,
                "Final_Primary_TJ": fp_dom / 1e6,
                "Emission_MJ":      sec_dom,
                "Inbound_Primary":  0.0,
                "Demand_crore":     float(Y_dom.sum()),
            },
        ])


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY TEXT  (replaces 2 separate save_summary_txt functions)
# ══════════════════════════════════════════════════════════════════════════════

def _save_summary_txt(all_results: dict, out_path: Path, stressor: Stressor,
                       log: Logger = None):
    cfg = _CFG[stressor]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"INDIRECT TOURISM {stressor.upper()} FOOTPRINT (EEIO)\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Formula: Footprint = C × L × Y  ({cfg['unit']})\n\n")
        for year, r in sorted(all_results.items()):
            f.write(f"Year: {year}\n")
            if stressor == "water":
                f.write(f"  Indirect TWF (bn m³):     {r.get('Indirect_TWF_billion_m3', 0):>10.4f}\n")
                f.write(f"  Scarce TWF (bn m³):       {r.get('Scarce_TWF_billion_m3', 0):>10.4f}\n")
                f.write(f"  Scarce/Blue ratio:        {r.get('Scarce_Blue_Ratio', 0):>10.3f}\n")
                f.write(f"  Green TWF (bn m³):        {r.get('Green_TWF_billion_m3', 0):>10.4f}\n")
                f.write(f"  Intensity (m³/₹ crore):   {r.get('Intensity_m3_per_crore', 0):>10.2f}\n")
                f.write(f"  Inbound (bn m³):          {r.get('Inbound_TWF_billion_m3', 0):>10.4f}\n")
                f.write(f"  Domestic (bn m³):         {r.get('Domestic_TWF_billion_m3', 0):>10.4f}\n")
                f.write(f"  Top sector:               {r.get('Top_Sector', '')}\n\n")
            else:
                f.write(f"  Primary energy (TJ):      {r.get('Primary_Total_TJ', 0):>10.2f}\n")
                f.write(f"  Primary energy (bn MJ):   {r.get('Primary_Total_bn_MJ', 0):>10.4f}\n")
                f.write(f"  Emission energy (MJ):     {r.get('Emission_Total_MJ', 0):>14,.0f}\n")
                f.write(f"  Emission share (%):       {r.get('Emission_pct', 0):>10.1f}\n")
                f.write(f"  Intensity (MJ/₹ crore):   {r.get('Intensity_MJ_per_crore', 0):>10.2f}\n")
                f.write(f"  Inbound (bn MJ):          {r.get('Inbound_Primary_bn', 0):>10.4f}\n")
                f.write(f"  Domestic (bn MJ):         {r.get('Domestic_Primary_bn', 0):>10.4f}\n")
                f.write(f"  Top sector:               {r.get('Top_Sector', '')}\n\n")
    ok(f"Summary: {out_path.name}", log)


# ══════════════════════════════════════════════════════════════════════════════
# STRUCTURAL DECOMPOSITION  (water-only; called from _process_year)
# ══════════════════════════════════════════════════════════════════════════════

def structural_decomposition(C: np.ndarray, L: np.ndarray, Y: np.ndarray,
                               concordance: pd.DataFrame,
                               sut_df: pd.DataFrame,
                               year: str,
                               log: Logger = None) -> pd.DataFrame:
    """
    Decompose footprint by source sector × tourism category.
    Returns DataFrame with: Category_ID, Category_Name, Source_ID, Source_Name,
    Source_Group, Water_m3, WSI_weight, Scarce_m3, Water_pct, Scarce_pct.

    (Water-specific function — energy has no equivalent structural decomposition.)

    FIX-3: A `seen_sids` set prevents a SUT product that appears in multiple
    concordance rows from contributing its Leontief column multiple times to
    the structural totals.  Without this guard, `C[src] * L[src,:] * cat_y`
    was emitted once per concordance row that listed the sid, causing the
    structural grand-total to exceed the footprint computed by
    compute_footprint().
    """
    from config import WSI_WEIGHTS as _WSI
    n = len(C)

    def _wsi(grp):
        return _WSI.get(grp, _WSI.get("Manufacturing", 0.814))

    rows = []
    seen_sids: set[int] = set()   # FIX-3: track 0-based indices

    for _, crow in concordance.iterrows():
        sut_str = str(crow.get("SUT_Product_IDs", ""))
        all_sids_1based = [
            int(s.strip())
            for s in sut_str.split(",")
            if s.strip() and s.strip().lower() != "nan"
            and 1 <= int(s.strip()) <= n
        ]

        # FIX-3: only include sids not yet attributed to a prior category
        new_sids_0based = [sid - 1 for sid in all_sids_1based
                           if (sid - 1) not in seen_sids]
        seen_sids.update(new_sids_0based)

        if not new_sids_0based:
            continue

        cat_y = np.zeros(n)
        for sid in new_sids_0based:
            cat_y[sid] = Y[sid]

        for src_id in range(n):
            w_src = C[src_id] * L[src_id, :] * cat_y
            grp   = classify_source_group(src_id + 1)
            water = float(w_src.sum())
            rows.append({
                "Category_ID":   crow["Category_ID"],
                "Category_Name": crow.get("Category_Name", ""),
                "Source_ID":     src_id + 1,
                "Source_Name":   (sut_df.iloc[src_id].get("Product_Name", str(src_id + 1))
                                  if src_id < len(sut_df) else str(src_id + 1)),
                "Source_Group":  grp,
                "Water_m3":      water,
                "WSI_weight":    _wsi(grp),
                "Scarce_m3":     water * _wsi(grp),
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    total_w = df["Water_m3"].sum()
    total_s = df["Scarce_m3"].sum()
    df["Water_pct"]  = 100 * df["Water_m3"]  / total_w if total_w > 0 else 0
    df["Scarce_pct"] = 100 * df["Scarce_m3"] / total_s if total_s > 0 else 0
    return df.sort_values("Water_m3", ascending=False)


# ══════════════════════════════════════════════════════════════════════════════
# SECTOR DECOMP  (water-only)
# Produces indirect_water_{year}_sector_decomp.csv, which compare.py reads
# to fill the TSA Main Table 7 ({{TSA_WIDE_ROWS}}) and Supp S7d.
# ══════════════════════════════════════════════════════════════════════════════

# Source-group labels that map to each decomp column.
# Uses flexible prefix matching so variations like "Utilities/Energy" and
# "Energy Processing" both contribute to Elec_pct_of_indirect.
_AGR_GROUPS   = {"agriculture"}
_ELEC_GROUPS  = {"utilities/energy", "energy processing", "electricity", "utilities"}
_PETRO_GROUPS = {"mining", "petroleum", "energy processing"}


def build_sector_decomp(cat_results: pd.DataFrame,
                         struct_df: pd.DataFrame,
                         year: str,
                         direct_dir: "Path",
                         log: Logger = None) -> pd.DataFrame:
    """
    Build the sector_decomp table that compare.py needs for the TSA Main Table 7.

    Columns produced
    ----------------
    Category_Name, Category_Type, Demand_crore,
    Total_Water_m3        — blue indirect (m³); used as _icol by compare.py
    Agr_pct_of_indirect   — % of indirect sourced from Agriculture supply chain
    Elec_pct_of_indirect  — % from Utilities/Energy supply chain
    Petro_pct_of_indirect — % from Mining/Petroleum supply chain
    Direct_m3             — operational direct water (m³); loaded from direct_twf_{year}.csv
                            distributed proportionally by demand share across categories.
                            Set to 0 if direct file unavailable.

    Why proportional direct allocation?
    direct_twf_{year}.csv reports Hotel/Restaurant/Rail/Air totals, not per-TSA-category
    totals.  Distributing by demand share is the standard approximation; it is only used
    for the Direct % annotation column in Main Table 7, not for the headline TWF numbers.
    """
    if cat_results.empty:
        return pd.DataFrame()

    # ── 1. Base: indirect per category ──────────────────────────────────────
    rows = []
    cat_cols = ["Category_Name", "Category_Type", "Demand_crore", "Total_Water_m3"]
    for col in cat_cols:
        if col not in cat_results.columns:
            warn(f"build_sector_decomp: column '{col}' missing from cat_results — "
                 f"sector_decomp will be incomplete", log)

    for _, r in cat_results.iterrows():
        rows.append({
            "Category_Name":  r.get("Category_Name", ""),
            "Category_Type":  r.get("Category_Type", ""),
            "Demand_crore":   float(r.get("Demand_crore",   0)),
            "Total_Water_m3": float(r.get("Total_Water_m3", 0)),
            "Green_Water_m3": float(r.get("Green_Water_m3", 0)),
        })

    df = pd.DataFrame(rows)

    # ── 2. Source-group percentages per category from struct_df ──────────────
    # struct_df has: Category_Name, Source_Group, Water_m3
    # Agr/Elec/Petro pct = group water / category indirect total * 100
    df["Agr_pct_of_indirect"]   = 0.0
    df["Elec_pct_of_indirect"]  = 0.0
    df["Petro_pct_of_indirect"] = 0.0

    if not struct_df.empty and "Category_Name" in struct_df.columns \
            and "Source_Group" in struct_df.columns and "Water_m3" in struct_df.columns:

        # Group struct_df by category × source_group
        grp = (
            struct_df.groupby(["Category_Name", "Source_Group"])["Water_m3"]
            .sum()
            .reset_index()
        )

        for _, cat_row in df.iterrows():
            cat_name  = cat_row["Category_Name"]
            cat_total = cat_row["Total_Water_m3"]
            if cat_total <= 0:
                continue

            cat_grp = grp[grp["Category_Name"] == cat_name]

            def _grp_pct(label_set: set) -> float:
                mask = cat_grp["Source_Group"].str.lower().isin(label_set)
                return 100.0 * float(cat_grp.loc[mask, "Water_m3"].sum()) / cat_total

            df.loc[df["Category_Name"] == cat_name, "Agr_pct_of_indirect"]   = round(_grp_pct(_AGR_GROUPS),   1)
            df.loc[df["Category_Name"] == cat_name, "Elec_pct_of_indirect"]  = round(_grp_pct(_ELEC_GROUPS),  1)
            df.loc[df["Category_Name"] == cat_name, "Petro_pct_of_indirect"] = round(_grp_pct(_PETRO_GROUPS), 1)
    else:
        warn(f"build_sector_decomp {year}: struct_df empty or missing columns — "
             f"Agr/Elec/Petro percentages will be zero", log)

    # ── 3. Direct water — proportional allocation from direct_twf_{year}.csv ─
    df["Direct_m3"] = 0.0
    direct_path = direct_dir / f"direct_twf_{year}.csv"
    if direct_path.exists():
        try:
            dir_df  = pd.read_csv(direct_path)
            base_row = dir_df[dir_df["Scenario"] == "BASE"] if "Scenario" in dir_df.columns else dir_df
            total_direct = float(base_row["Total_m3"].iloc[0]) if not base_row.empty and "Total_m3" in base_row.columns else 0.0
            total_demand = float(df["Demand_crore"].sum())
            if total_direct > 0 and total_demand > 0:
                df["Direct_m3"] = (df["Demand_crore"] / total_demand * total_direct).round(0)
                ok(f"Sector decomp {year}: direct {total_direct/1e6:.2f}M m³ "
                   f"distributed across {len(df)} categories by demand share", log)
        except Exception as e:
            warn(f"build_sector_decomp {year}: could not load direct TWF — {e}", log)
    else:
        ok(f"Sector decomp {year}: no direct_twf file found at {direct_path} — Direct_m3 = 0", log)

    df = df.sort_values("Total_Water_m3", ascending=False).reset_index(drop=True)
    ok(f"Sector decomp {year}: {len(df)} categories  "
       f"total indirect {df['Total_Water_m3'].sum()/1e9:.4f} bn m³", log)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# PER-YEAR PROCESSOR
# ══════════════════════════════════════════════════════════════════════════════

def _process_year(year: str, stressor: Stressor,
                  out_dir: Path, log: Logger) -> dict | None:
    cfg_s = _CFG[stressor]
    cfg_y = YEARS[year]
    log.subsection(f"Year: {year}  ({cfg_y['io_year']})")

    inputs = _load_inputs(year, stressor, log)
    if inputs is None:
        return None

    Y_163         = inputs["Y_163"]
    L             = inputs["L"]
    concordance   = inputs["concordance"]
    sut_df        = inputs["sut_df"]
    primary_col   = inputs["primary_col"]
    secondary_col = inputs["secondary_col"]

    C_primary   = sut_df[primary_col].values.astype(float)
    C_secondary = sut_df[secondary_col].values.astype(float) if secondary_col else None

    Y_140 = map_y_to_sut(Y_163, concordance, log=log)

    FP_primary, CL = compute_footprint(C_primary, L, Y_140, stressor)
    FP_secondary   = None
    if C_secondary is not None:
        FP_secondary, _ = compute_footprint(C_secondary, L, Y_140, stressor)

    # ── SUT-level results ────────────────────────────────────────────────────
    sut_results = build_sut_results(
        sut_df, primary_col, secondary_col,
        Y_140, CL, FP_primary,
        FP_secondary if FP_secondary is not None else np.zeros_like(FP_primary),
        stressor,
    )
    save_csv(sut_results, out_dir / f"indirect_{stressor}_{year}_by_sut.csv",
             f"Indirect {stressor} SUT {year}", log=log)

    # ── Water multiplier ratio file — written separately so compare.py can read it
    # without loading the full SUT results frame.  compare.py expects:
    #   water_multiplier_ratio_{year}.csv with columns:
    #   Product_ID, Product_Name, Water_Multiplier_m3_per_crore, Multiplier_Ratio
    if stressor == "water" and "Multiplier_Ratio" in sut_results.columns:
        ratio_cols = [c for c in
                      ("Product_ID", "Product_Name", "Water_Multiplier_m3_per_crore",
                       "Multiplier_Ratio", "Source_Group")
                      if c in sut_results.columns]
        ratio_df = (sut_results[ratio_cols]
                    .sort_values("Multiplier_Ratio", ascending=False)
                    .reset_index(drop=True))
        save_csv(ratio_df,
                 out_dir / f"water_multiplier_ratio_{year}.csv",
                 f"Water multiplier ratio {year}", log=log)

    # ── Category-level results ───────────────────────────────────────────────
    cat_results = aggregate_to_categories(sut_results, concordance, stressor)
    save_csv(cat_results, out_dir / f"indirect_{stressor}_{year}_by_category.csv",
             f"Indirect {stressor} by category {year}", log=log)

    # Integrity check: category grand-total must equal SUT grand-total within 0.1%.
    # A larger gap means the concordance still has duplicate SUT_Product_IDs.
    if stressor == "water":
        sut_total = float(sut_results["Total_Water_m3"].sum())
        cat_total = float(cat_results["Total_Water_m3"].sum())
    else:
        sut_total = float(sut_results["Final_Primary_MJ"].sum())
        cat_total = float(cat_results["Final_Primary_MJ"].sum())
    if sut_total > 0:
        mismatch_pct = 100 * abs(cat_total - sut_total) / sut_total
        if mismatch_pct > 0.1:
            warn(
                f"Category vs SUT total mismatch {mismatch_pct:.2f}% "
                f"(cat={cat_total:.0f}, sut={sut_total:.0f}) — "
                f"check concordance for duplicate SUT_Product_IDs", log
            )
        else:
            ok(f"Category/SUT total agreement: {mismatch_pct:.4f}%", log)

    # ── Source-group origin summary (SOURCE/pull-matrix view) ───────────────
    origin_df = build_origin_summary(
        sut_results, stressor,
        C_primary=C_primary, C_secondary=C_secondary, L=L, Y=Y_140,
    )
    save_csv(origin_df, out_dir / f"indirect_{stressor}_{year}_origin.csv",
             f"Indirect {stressor} origin {year}", log=log)

    # ── Sensitivity ±20% ────────────────────────────────────────────────────
    sens_df = sensitivity_analysis(C_primary, L, Y_140, stressor, log)
    save_csv(sens_df, out_dir / f"indirect_{stressor}_{year}_sensitivity.csv",
             f"Indirect {stressor} sensitivity {year}", log=log)

    # ── Water-only: structural decomposition + sector_decomp for compare.py ──
    if stressor == "water":
        struct_df = structural_decomposition(
            C_primary, L, Y_140, concordance, sut_df, year, log
        )
        save_csv(struct_df, out_dir / f"indirect_{stressor}_{year}_structural.csv",
                 f"Structural {year}", log=log)

        # Build sector_decomp — the file compare.py reads for TSA Main Table 7.
        # Joins cat_results (indirect per category) + struct_df (source-group %)
        # + direct_twf_{year}.csv (operational direct, distributed by demand share).
        decomp_df = build_sector_decomp(
            cat_results, struct_df, year, DIRS["direct"], log
        )
        save_csv(decomp_df, out_dir / f"indirect_{stressor}_{year}_sector_decomp.csv",
                 f"Sector decomp {year}", log=log)

    # ── Inbound / domestic split ─────────────────────────────────────────────
    inb_total = dom_total = 0.0
    if inputs["Y_inb"] is not None and inputs["Y_dom"] is not None:
        split_df = compute_split_footprint(
            C_primary, L, inputs["Y_inb"], inputs["Y_dom"],
            concordance, year, stressor, C_secondary, log,
        )
        save_csv(split_df, out_dir / f"indirect_{stressor}_{year}_split.csv",
                 f"Indirect {stressor} split {year}", log=log)
        inb_row = split_df[split_df["Type"] == "Inbound"]
        dom_row = split_df[split_df["Type"] == "Domestic"]
        _pcol = "TWF_m3" if stressor == "water" else "Final_Primary_MJ"
        if not inb_row.empty:
            inb_total = float(inb_row[_pcol].iloc[0])
        if not dom_row.empty:
            dom_total = float(dom_row[_pcol].iloc[0])
    else:
        warn(f"Skipping split for {year} — demand files not found", log)

    total_primary = FP_primary.sum()
    total_sec     = FP_secondary.sum() if FP_secondary is not None else 0.0
    demand_cr     = Y_140.sum()

    ok(f"Indirect {stressor} {year}: "
       f"Total={total_primary/1e9:.4f} {cfg_s['bn_label']}  "
       f"Intensity={total_primary / max(demand_cr, 1):.2f} {cfg_s['unit']}/cr", log)

    # ── Return dict — keys match all_years CSV schema ────────────────────────
    if stressor == "water":
        # Columns mirror indirect_water_all_years.csv.
        # Total_Water_m3 / Indirect_TWF_m3 are BLUE only.
        # Green is tracked separately in Green_TWF_m3 / Green_TWF_billion_m3.
        total_scarce = float(
            sut_results["Scarce_m3"].sum() if "Scarce_m3" in sut_results.columns else 0
        )
        top_cat = cat_results.iloc[0]["Category_Name"] if not cat_results.empty else ""
        return {
            "Year":                       year,
            "Indirect_TWF_m3":            round(total_primary),
            "Indirect_TWF_billion_m3":    round(total_primary / 1e9, 6),
            "Scarce_TWF_m3":              round(total_scarce),
            "Scarce_TWF_billion_m3":      round(total_scarce / 1e9, 6),
            "Scarce_Blue_Ratio":          round(total_scarce / max(total_primary, 1e-9), 3),
            "Green_TWF_m3":               round(total_sec),
            "Green_TWF_billion_m3":       round(total_sec / 1e9, 6),
            "Tourism_Demand_crore":       round(demand_cr, 2),
            "Intensity_m3_per_crore":     round(total_primary / max(demand_cr, 1), 4),
            "Inbound_TWF_billion_m3":     round(inb_total / 1e9, 6),
            "Domestic_TWF_billion_m3":    round(dom_total / 1e9, 6),
            "Top_Sector":                 top_cat,
        }
    else:
        # Columns mirror indirect_energy_all_years.csv
        emission_total = float(
            sut_results["Emission_MJ"].sum() if "Emission_MJ" in sut_results.columns else 0
        )
        top_cat = cat_results.iloc[0]["Category_Name"] if not cat_results.empty else ""
        return {
            "Year":                   year,
            "Primary_Total_MJ":       round(total_primary),
            "Primary_Total_bn_MJ":    round(total_primary / 1e9, 6),
            "Primary_Total_TJ":       round(total_primary / 1e6, 4),
            "Emission_Total_MJ":      round(emission_total),
            "Emission_pct":           round(100 * emission_total / max(total_primary, 1e-9), 2),
            "Intensity_MJ_per_crore": round(total_primary / max(demand_cr, 1), 4),
            "Inbound_Primary_MJ":     round(inb_total),
            "Inbound_Primary_bn":     round(inb_total / 1e9, 6),
            "Domestic_Primary_MJ":    round(dom_total),
            "Domestic_Primary_bn":    round(dom_total / 1e9, 6),
            "Tourism_Demand_crore":   round(demand_cr, 2),
            "Top_Sector":             top_cat,
        }


# ══════════════════════════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════════════════════════

def run(stressor: Stressor = "water", **kwargs):
    cfg_s   = _CFG[stressor]
    out_dir = DIRS[cfg_s["out_dir_key"]]
    out_dir.mkdir(parents=True, exist_ok=True)

    with Logger(cfg_s["log_name"], DIRS["logs"]) as log:
        t = Timer()
        log.section(cfg_s["section_title"])

        all_results: list[dict] = []
        by_year:     dict       = {}

        for year in STUDY_YEARS:
            result = _process_year(year, stressor, out_dir, log)
            if result is not None:
                all_results.append(result)
                by_year[year] = result

        if all_results:
            log.section(f"Cross-Year {stressor.capitalize()} Footprint Comparison")
            if stressor == "water":
                compare_across_years(
                    {r["Year"]: r["Indirect_TWF_billion_m3"] for r in all_results},
                    "Indirect TWF (bn m³)", unit=" bn m³", log=log,
                )
                compare_across_years(
                    {r["Year"]: r["Scarce_TWF_billion_m3"] for r in all_results},
                    "Scarce TWF (bn m³; Aqueduct 4.0)", unit=" bn m³", log=log,
                )
                compare_across_years(
                    {r["Year"]: r["Intensity_m3_per_crore"] for r in all_results},
                    "Water intensity (m³/₹ crore)", unit=" m³/cr", log=log,
                )
            else:
                compare_across_years(
                    {r["Year"]: r["Primary_Total_TJ"] for r in all_results},
                    "Indirect energy footprint (TJ)", unit=" TJ", log=log,
                )
                compare_across_years(
                    {r["Year"]: r["Emission_pct"] for r in all_results},
                    "Fossil emission share (%)", unit="%", log=log,
                )
                compare_across_years(
                    {r["Year"]: r["Intensity_MJ_per_crore"] for r in all_results},
                    "Energy intensity (MJ/₹ crore)", unit=" MJ/cr", log=log,
                )

            all_df = pd.DataFrame(all_results)
            save_csv(all_df, out_dir / f"indirect_{stressor}_all_years.csv",
                     f"Indirect {stressor} all years", log=log)
            _save_summary_txt(by_year, out_dir / f"indirect_{stressor}_summary.txt",
                              stressor, log)

        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--stressor", choices=["water", "energy", "depletion"], default="water")
    run(stressor=ap.parse_args().stressor)