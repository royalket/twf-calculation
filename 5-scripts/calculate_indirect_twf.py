"""
calculate_indirect_twf.py — Indirect Tourism Water Footprint (EEIO)
====================================================================

Core formula:
  TWF_indirect = W × L × Y     (blue water, m³)
  Scarce_TWF   = TWF × WSI     (stress-weighted m³, Aqueduct 4.0)

Changes vs previous version
----------------------------
1. Scarce TWF: after computing TWF, weights each source-group's
   contribution by its WSI factor (WRI Aqueduct 4.0, Kuzma et al. 2023).
   Agriculture=0.827, Industry sectors=0.814, Services=0.0.
   New output columns: Scarce_m3, WSI_weight in all SUT/category/origin files.

2. Green water: if concordance file has a Green water column alongside
   the Blue column, it is loaded and reported in output CSVs and summary.
   The EEIO model (W @ L @ Y) uses ONLY blue water — green is reported
   as a parallel disclosure metric, not as an additional multiplier.
   This is consistent with EXIOBASE methodology (WaterGAP blue = surface
   + groundwater consumption; green = rainwater in agricultural production).

3. Water multiplier ratio: computes WL[j] / economy_avg_WL for each
   sector j. Ratio > 1 means tourism spending there is more water-intensive
   than average economic activity. New output: water_multiplier_ratio_{year}.csv

4. All output CSVs now include Scarce_m3 and Multiplier_Ratio columns.
   The origin summary now shows Scarce_m3 alongside raw Blue_m3.

Outputs per year (all in 3-final-results/indirect-water/):
  indirect_twf_{year}_by_sut.csv          — 140 products × water + scarce
  indirect_twf_{year}_by_category.csv     — 75 categories × water + scarce
  indirect_twf_{year}_structural.csv      — source-sector decomposition
  indirect_twf_{year}_origin.csv          — origin by source group + scarce
  indirect_twf_{year}_intensity.csv       — m³/crore by tourism category
  indirect_twf_{year}_sensitivity.csv     — ±20% agr/elec/petrol sensitivity
  indirect_twf_{year}_split.csv           — inbound vs domestic
  indirect_twf_{year}_summary.txt         — key metrics plain text
  water_multiplier_ratio_{year}.csv       — WL[j] / economy_avg_WL (NEW)
  indirect_twf_{year}_sector_decomp.csv  — per-TSA-category direct+indirect split
                                           with upstream supply-chain attribution
                                           (Agriculture/Electricity/Petroleum/Mfg/Svc %)
  indirect_twf_all_years.csv              — cross-year summary
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import DIRS, YEARS, CPI, STUDY_YEARS, USD_INR, WSI_WEIGHTS, TSA_TO_EXIOBASE, EXIO_IDX
from utils import (
    section, subsection, ok, warn, save_csv, safe_csv,
    read_csv, check_conservation, check_matrix_properties,
    top_n, compare_across_years, Timer, Logger,
    crore_to_usd_m, fmt_crore_usd,
    classify_source_group, find_blue_water_col, find_green_water_col,
    sensitivity_half_range_pct, fmt_sens_range,
)


# ══════════════════════════════════════════════════════════════════════════════
# WSI HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def get_wsi_for_group(source_group: str) -> float:
    """
    Return WSI weight (0-1) for a source group.
    Uses WRI Aqueduct 4.0 values loaded from config.
    Agriculture=0.827, Mining/Mfg/Elec/Petrol=0.814, Services=0.0.
    """
    return WSI_WEIGHTS.get(source_group, WSI_WEIGHTS.get("Manufacturing", 0.814))


def apply_wsi_to_sut(sut_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add Scarce_m3 column = Total_Water_m3 × WSI_weight for each row.
    WSI is looked up by Source_Group.
    """
    df = sut_df.copy()
    df["WSI_weight"] = df["Source_Group"].map(get_wsi_for_group).fillna(0.814)
    df["Scarce_m3"]  = df["Total_Water_m3"] * df["WSI_weight"]
    return df


def compute_scarce_origin(origin_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add Scarce_m3 and Scarce_pct to origin summary.
    Each source group's water is weighted by its WSI.
    """
    df = origin_df.copy()
    df["WSI_weight"] = df["Source_Group"].map(get_wsi_for_group).fillna(0.814)
    df["Scarce_m3"]  = df["Water_m3"] * df["WSI_weight"]
    total_scarce     = df["Scarce_m3"].sum()
    df["Scarce_pct"] = 100 * df["Scarce_m3"] / total_scarce if total_scarce > 0 else 0
    return df


# ══════════════════════════════════════════════════════════════════════════════
# INPUT LOADERS
# ══════════════════════════════════════════════════════════════════════════════

def _load_inputs(year: str, log: Logger = None) -> dict:
    cfg       = YEARS[year]
    _usd_rate = USD_INR.get(year, 70.0)

    Y_163 = read_csv(DIRS["demand"] / f"Y_tourism_{year}.csv")["Tourism_Demand_crore"].values
    ok(f"Y_tourism {year} (nominal): {fmt_crore_usd(Y_163.sum(), _usd_rate)}, "
       f"{np.count_nonzero(Y_163)}/163 non-zero", log)

    L = read_csv(DIRS["io"] / cfg["io_year"] / f"io_L_{cfg['io_tag']}.csv",
                 index_col=0).values
    ok(f"L ({cfg['io_year']}): {L.shape}  diag mean={np.diag(L).mean():.4f}", log)

    concordance = read_csv(DIRS["concordance"] / f"concordance_{cfg['io_tag']}.csv")
    ok(f"Concordance {cfg['io_year']}: {len(concordance)} categories", log)

    # Duplicate SUT_Product_ID check
    _seen: dict = {}
    for _, crow in concordance.iterrows():
        _sut_str = str(crow.get("SUT_Product_IDs", ""))
        _ids = frozenset(
            int(s.strip()) for s in _sut_str.split(",")
            if s.strip() and s.strip().lower() not in ("nan", "")
        )
        for _sid in _ids:
            _seen.setdefault(_sid, []).append(crow.get("Category_Name", "?"))
    _dupes = {k: v for k, v in _seen.items() if len(v) > 1}
    if _dupes:
        warn(
            f"Concordance {cfg['io_year']}: {len(_dupes)} SUT product ID(s) "
            "mapped to >1 category (double-counting risk):\n"
            + "\n".join(f"    Product_ID {pid}: {cats}" for pid, cats in sorted(_dupes.items())),
            log,
        )
    else:
        ok(f"Concordance {cfg['io_year']}: no duplicate SUT_Product_IDs", log)

    sut_water_df = read_csv(DIRS["concordance"] / f"water_coefficients_140_{cfg['io_tag']}.csv")

    # Find blue water column (primary for EEIO)
    blue_candidates = [c for c in sut_water_df.columns if "Blue" in c and "crore" in c]
    if blue_candidates:
        wc = blue_candidates[0]
    else:
        # Fallback: any Water column with crore
        fallback = [c for c in sut_water_df.columns if "Water" in c and "crore" in c]
        wc = fallback[0] if fallback else None
        if wc is None:
            raise ValueError(f"No water coefficient column found in {sut_water_df.columns.tolist()}")
        warn(f"No Blue-specific column; using fallback: {wc}", log)
    ok(f"Blue water column: '{wc}'  non-zero: {(sut_water_df[wc]>0).sum()}/140", log)

    # Green water column (disclosure only — not used in W@L@Y)
    green_candidates = [c for c in sut_water_df.columns if "Green" in c and "crore" in c]
    wc_green = green_candidates[0] if green_candidates else None
    if wc_green:
        ok(f"Green water column: '{wc_green}'  non-zero: {(sut_water_df[wc_green]>0).sum()}/140", log)
    else:
        warn("No green water column in SUT file — run build_water_coefficients.py to add it", log)

    # Optional real demand
    Y_163_real = None
    real_path  = DIRS["demand"] / f"Y_tourism_{year}_real.csv"
    if real_path.exists():
        Y_163_real = read_csv(real_path)["Tourism_Demand_crore"].values

    # Optional inbound/domestic split
    Y_inb = Y_dom = None
    f_inb = DIRS["demand"] / f"Y_tourism_{year}_inbound.csv"
    f_dom = DIRS["demand"] / f"Y_tourism_{year}_domestic.csv"
    if f_inb.exists() and f_dom.exists():
        Y_inb = read_csv(f_inb)["Tourism_Demand_crore"].values
        Y_dom = read_csv(f_dom)["Tourism_Demand_crore"].values
        ok(f"Split demand {year}: inbound ₹{Y_inb.sum():,.0f} cr  "
           f"domestic ₹{Y_dom.sum():,.0f} cr", log)
    else:
        warn(f"Split demand files not found for {year} — split analysis skipped.", log)

    return {
        "Y_163": Y_163, "L": L, "concordance": concordance,
        "sut_water_df": sut_water_df, "wc": wc, "wc_green": wc_green,
        "Y_163_real": Y_163_real, "Y_inb": Y_inb, "Y_dom": Y_dom,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Y MAPPING: EXIOBASE 163 → SUT 140
# ══════════════════════════════════════════════════════════════════════════════

def map_y_to_sut(Y_163: np.ndarray, concordance_df: pd.DataFrame,
                  n_sut: int = 140, log: Logger = None) -> np.ndarray:
    Y_140 = np.zeros(n_sut)
    assigned_exio: dict = {}

    for _, row in concordance_df.iterrows():
        exio_str = str(row.get("EXIOBASE_Sectors", ""))
        sut_str  = str(row.get("SUT_Product_IDs",  ""))

        exio_codes = [e.strip() for e in exio_str.split(",")
                      if e.strip() and e.strip().lower() != "nan"]
        sut_ids    = [int(s.strip()) for s in sut_str.split(",")
                      if s.strip() and s.strip().lower() != "nan"]

        demand = 0.0
        for code in exio_codes:
            if code == "IN":
                idx = 0
            elif code.startswith("IN."):
                try:
                    idx = int(code.split(".")[1])
                except (IndexError, ValueError):
                    continue
            else:
                warn(f"Unrecognised EXIOBASE code '{code}'", log)
                continue
            if 0 <= idx < len(Y_163):
                demand += Y_163[idx]
                assigned_exio[idx] = assigned_exio.get(idx, 0) + 1

        if not sut_ids or demand == 0:
            continue
        per_sut = demand / len(sut_ids)
        for sid in sut_ids:
            if 1 <= sid <= n_sut:
                Y_140[sid - 1] += per_sut

    unassigned = np.count_nonzero(Y_163) - len(assigned_exio)
    if unassigned > 0:
        warn(f"{unassigned} non-zero EXIO sectors not mapped to SUT", log)
    ok(f"Y_140: ₹{Y_140.sum():,.0f} crore  (coverage "
       f"{100*Y_140.sum()/max(Y_163.sum(),1):.1f}%)", log)
    return Y_140


# ══════════════════════════════════════════════════════════════════════════════
# CORE TWF COMPUTATION
# ══════════════════════════════════════════════════════════════════════════════

def compute_twf(W: np.ndarray, L: np.ndarray, Y: np.ndarray):
    """
    TWF = W @ L * Y  (element-wise product at the end).
    Returns: (TWF vector, WL vector) both shape (140,).
    WL[j] = m³ of water mobilised per ₹ crore of demand for product j.
    """
    WL  = W @ L
    TWF = WL * Y
    ok(f"TWF: {TWF.sum()/1e9:.4f} bn m³  |  WL mean={WL.mean():.2f}  "
       f"Y sum={Y.sum():,.0f} cr")
    return TWF, WL


def compute_water_multiplier_ratio(WL: np.ndarray, Y_economy: np.ndarray) -> np.ndarray:
    """
    Water multiplier ratio = WL[j] / economy_avg_WL

    economy_avg_WL = sum(WL[j] * x[j]) / sum(x[j])
    where x[j] is total output (approximated here by Y_economy,
    the full economy final demand vector, or a uniform proxy).

    Ratio > 1: sector j is more water-intensive than the economy average.
    Ratio < 1: sector j is below average water intensity.

    Parameters
    ----------
    WL        : water multiplier vector (m³/₹ crore), shape (140,)
    Y_economy : economy total output or final demand vector, shape (140,)
                Use the total output from the IO table (x = L @ y_total).

    Returns
    -------
    ratio : shape (140,) — WL[j] / economy_avg_WL
    """
    # Demand-weighted economy average
    total_demand  = Y_economy.sum()
    if total_demand <= 0:
        return np.ones_like(WL)
    economy_avg_WL = (WL * Y_economy).sum() / total_demand
    if economy_avg_WL <= 0:
        return np.ones_like(WL)
    ratio = WL / economy_avg_WL
    ok(f"Economy-avg water multiplier: {economy_avg_WL:.2f} m³/crore  "
       f"(tourism-weighted avg: {(WL * np.maximum(Y_economy, 0)).sum() / max(total_demand,1):.2f})")
    return ratio


# classify_source_group is imported from utils — do not redefine here.
# The authoritative version in utils.py fixes the 115-116 boundary bug
# where Electricity distribution (114-116) was wrongly classified as
# Services (WSI=0.0), suppressing ~35% of upstream water's WSI weighting.


# ══════════════════════════════════════════════════════════════════════════════
# RESULT BUILDERS
# ══════════════════════════════════════════════════════════════════════════════

def build_sut_results(sut_water_df: pd.DataFrame, wc: str,
                       Y_140: np.ndarray, WL: np.ndarray,
                       TWF: np.ndarray, multiplier_ratio: np.ndarray,
                       wc_green: str = None,
                       green_twf: np.ndarray = None) -> pd.DataFrame:
    """
    Build 140-product SUT results frame.
    Adds: Tourism_Demand_crore, Water_Multiplier_m3_per_crore,
          Total_Water_m3 (blue EEIO result), Green_Water_m3 (green EEIO result),
          Source_Group, Water_pct, WSI_weight, Scarce_m3, Scarce_pct,
          Multiplier_Ratio, Product_ID.

    Parameters
    ----------
    green_twf : actual green EEIO TWF vector (W_green @ L) * Y — shape (140,).
                Previously this was wrongly set to raw coefficients (m³/₹ crore).
                Pass the computed vector from _process_year().
    """
    df = sut_water_df.copy()
    n  = len(TWF)
    # Product_ID column is needed by aggregate_to_categories() to correctly
    # index into the sorted frame (index != Product_ID after sort_values).
    df["Product_ID"]                    = range(1, n + 1)
    df["Tourism_Demand_crore"]          = Y_140
    df["Water_Multiplier_m3_per_crore"] = WL
    df["Total_Water_m3"]                = TWF          # blue EEIO result
    df["Source_Group"]                  = [classify_source_group(i + 1) for i in range(n)]
    df["Water_pct"]                     = 100 * df["Total_Water_m3"] / max(df["Total_Water_m3"].sum(), 1e-9)

    # Scarce TWF
    df["WSI_weight"] = df["Source_Group"].map(get_wsi_for_group).fillna(0.814)
    df["Scarce_m3"]  = df["Total_Water_m3"] * df["WSI_weight"]
    df["Scarce_pct"] = 100 * df["Scarce_m3"] / max(df["Scarce_m3"].sum(), 1e-9)

    # Water multiplier ratio
    df["Multiplier_Ratio"] = multiplier_ratio

    # Green water EEIO result — actual m³ from (W_green @ L) * Y
    # Previously this column stored raw coefficients (m³/₹ crore) which was
    # ~7000× smaller than the true green TWF volume. Fixed by computing
    # green_twf = (W_green @ L) * Y in _process_year() before calling here.
    if green_twf is not None:
        df["Green_Water_m3"] = green_twf
    elif wc_green and wc_green in sut_water_df.columns:
        # Fallback: store coefficients with a clear name so downstream
        # code knows this is NOT a TWF volume.
        df["Green_Water_m3"]       = 0.0
        df["Green_Coeff_m3_crore"] = sut_water_df[wc_green].values
        warn("green_twf not provided — Green_Water_m3 set to 0. "
             "Pass green_twf from _process_year() to get correct EEIO green volumes.")
    else:
        df["Green_Water_m3"] = 0.0

    return df.sort_values("Total_Water_m3", ascending=False)


def build_multiplier_ratio_report(sut_results: pd.DataFrame,
                                   concordance: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate WL multiplier ratio to tourism category level.
    Returns category-level table sorted by ratio (most water-intensive first).

    BUG FIX: Uses Product_ID column (not .index) for lookup — the frame is
    sorted by Total_Water_m3, so the RangeIndex no longer corresponds to
    Product_ID after sort_values().
    """
    rows = []
    for _, crow in concordance.iterrows():
        sut_str = str(crow.get("SUT_Product_IDs", ""))
        sut_ids = [int(s.strip()) for s in sut_str.split(",")
                   if s.strip() and s.strip().lower() != "nan"]
        if not sut_ids:
            continue
        if "Product_ID" in sut_results.columns:
            sub = sut_results[sut_results["Product_ID"].isin(sut_ids)]
        else:
            sub = sut_results.iloc[[i - 1 for i in sut_ids if 1 <= i <= len(sut_results)]]
        demand = sub["Tourism_Demand_crore"].sum()
        if demand <= 0:
            continue
        # Demand-weighted average multiplier for this category
        wl_avg    = (sub["Water_Multiplier_m3_per_crore"] * sub["Tourism_Demand_crore"]).sum() / demand
        ratio_avg = (sub["Multiplier_Ratio"] * sub["Tourism_Demand_crore"]).sum() / demand
        scarce    = sub["Scarce_m3"].sum()
        rows.append({
            "Category_Name":         crow.get("Category_Name", str(crow["Category_ID"])),
            "Category_Type":         crow.get("Category_Type", ""),
            "Demand_crore":          demand,
            "WL_m3_per_crore":       wl_avg,
            "Multiplier_Ratio":      ratio_avg,
            "Above_Economy_Avg":     ratio_avg > 1.0,
            "Scarce_m3":             scarce,
        })
    df = pd.DataFrame(rows).sort_values("Multiplier_Ratio", ascending=False)
    return df


def aggregate_to_categories(sut_results: pd.DataFrame,
                              concordance: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate 140-product SUT results to 75 concordance categories.

    BUG FIX: Previously used `sut_results.index.isin([i-1 for i in sut_ids])`.
    After sort_values("Total_Water_m3") in build_sut_results, the integer index
    no longer corresponds to Product_ID — index[0] is the most water-intensive
    product, not product 1. This caused wrong products to be aggregated into
    each category. Now uses the Product_ID column which survives the sort.
    """
    rows = []
    for _, crow in concordance.iterrows():
        sut_str = str(crow.get("SUT_Product_IDs", ""))
        sut_ids = [int(s.strip()) for s in sut_str.split(",")
                   if s.strip() and s.strip().lower() != "nan"]
        if "Product_ID" in sut_results.columns:
            sub = sut_results[sut_results["Product_ID"].isin(sut_ids)]
        else:
            # Fallback for backward compatibility: pre-sorted frame where index == Product_ID - 1
            sub = sut_results.iloc[[i - 1 for i in sut_ids if 1 <= i <= len(sut_results)]]

        water  = sub["Total_Water_m3"].sum()
        scarce = sub["Scarce_m3"].sum()
        demand = sub["Tourism_Demand_crore"].sum()
        green  = sub["Green_Water_m3"].sum() if "Green_Water_m3" in sub.columns else 0.0
        rows.append({
            "Category_ID":   crow["Category_ID"],
            "Category_Name": crow.get("Category_Name", str(crow["Category_ID"])),
            "Category_Type": crow.get("Category_Type", ""),
            "Total_Water_m3":  water,
            "Green_Water_m3":  green,
            "Scarce_m3":       scarce,
            "Demand_crore":    demand,
            "Water_pct":       0.0,
            "Scarce_pct":      0.0,
        })
    df = pd.DataFrame(rows).sort_values("Total_Water_m3", ascending=False)
    tot_w = df["Total_Water_m3"].sum()
    tot_s = df["Scarce_m3"].sum()
    df["Water_pct"]  = 100 * df["Total_Water_m3"] / tot_w if tot_w > 0 else 0
    df["Scarce_pct"] = 100 * df["Scarce_m3"]      / tot_s if tot_s > 0 else 0
    return df


def per_sector_intensity(cat_df: pd.DataFrame) -> pd.DataFrame:
    df = cat_df.copy()
    df["Intensity_m3_per_crore"]       = df.apply(
        lambda r: r["Total_Water_m3"] / r["Demand_crore"] if r["Demand_crore"] > 0 else 0, axis=1)
    df["Scarce_Intensity_m3_per_crore"]= df.apply(
        lambda r: r["Scarce_m3"]      / r["Demand_crore"] if r["Demand_crore"] > 0 else 0, axis=1)
    return df.sort_values("Intensity_m3_per_crore", ascending=False)


def structural_decomposition(W: np.ndarray, L: np.ndarray, Y: np.ndarray,
                               sut_water_df: pd.DataFrame, wc: str,
                               concordance: pd.DataFrame,
                               log: Logger = None) -> pd.DataFrame:
    """Decompose water pull by source sector × tourism category."""
    n = len(W)
    rows = []
    for _, crow in concordance.iterrows():
        sut_str = str(crow.get("SUT_Product_IDs", ""))
        sut_ids = [int(s.strip()) - 1 for s in sut_str.split(",")
                   if s.strip() and s.strip().lower() != "nan"
                   and 1 <= int(s.strip()) <= n]
        if not sut_ids:
            continue
        cat_y = np.zeros(n)
        for sid in sut_ids:
            cat_y[sid] = Y[sid]
        for src_id in range(n):
            w_src = W[src_id] * L[src_id, :] * cat_y
            grp   = classify_source_group(src_id + 1)
            rows.append({
                "Category_ID":   crow["Category_ID"],
                "Category_Name": crow.get("Category_Name", ""),
                "Source_ID":     src_id + 1,
                "Source_Name":   (sut_water_df.iloc[src_id].get("Product_Name", str(src_id + 1))
                                  if src_id < len(sut_water_df) else str(src_id + 1)),
                "Source_Group":  grp,
                "Water_m3":      w_src.sum(),
                "WSI_weight":    get_wsi_for_group(grp),
                "Scarce_m3":     w_src.sum() * get_wsi_for_group(grp),
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    total = df["Water_m3"].sum()
    df["Water_pct"]  = 100 * df["Water_m3"]  / total if total > 0 else 0
    df["Scarce_pct"] = 100 * df["Scarce_m3"] / df["Scarce_m3"].sum() if df["Scarce_m3"].sum() > 0 else 0
    return df.sort_values("Water_m3", ascending=False)


def build_origin_summary(struct_df: pd.DataFrame) -> pd.DataFrame:
    if struct_df.empty:
        return pd.DataFrame()
    grp   = struct_df.groupby("Source_Group").agg(
        Water_m3 =("Water_m3",  "sum"),
        Scarce_m3=("Scarce_m3", "sum"),
    ).reset_index()
    grp["WSI_weight"] = grp["Source_Group"].map(get_wsi_for_group).fillna(0.814)
    tot_w = grp["Water_m3"].sum()
    tot_s = grp["Scarce_m3"].sum()
    grp["Water_pct"]  = 100 * grp["Water_m3"]  / tot_w if tot_w > 0 else 0
    grp["Scarce_pct"] = 100 * grp["Scarce_m3"] / tot_s if tot_s > 0 else 0
    return grp.sort_values("Water_m3", ascending=False)


def sensitivity_analysis(W: np.ndarray, L: np.ndarray, Y: np.ndarray,
                           sut_water_df: pd.DataFrame, wc: str,
                           log: Logger = None) -> pd.DataFrame:
    """±20% on agriculture, electricity, and petroleum water coefficients."""
    base_twf = (W @ L * Y).sum()

    def twf_with_factor(group_fn, factor):
        W2 = W.copy()
        for i in range(len(W2)):
            if group_fn(i + 1):
                W2[i] *= factor
        return (W2 @ L * Y).sum()

    rows = []
    for label, group_fn in [
        ("Agriculture", lambda pid: 1 <= pid <= 29),
        ("Electricity",  lambda pid: pid == 114),
        ("Petroleum",    lambda pid: 71 <= pid <= 80),
    ]:
        for scenario, factor in [("LOW", 0.8), ("BASE", 1.0), ("HIGH", 1.2)]:
            twf = twf_with_factor(group_fn, factor) if scenario != "BASE" else base_twf
            rows.append({
                "Component": label, "Scenario": scenario,
                "Total_TWF_m3":  round(twf),
                "Delta_pct":     round(100 * (twf - base_twf) / base_twf, 2) if base_twf else 0,
                "Scarce_m3_est": round(twf * WSI_WEIGHTS.get(label, 0.814)),
            })
        ok(
            f"Sensitivity {label}: "
            f"LOW={twf_with_factor(group_fn, 0.8)/1e9:.4f}  "
            f"BASE={base_twf/1e9:.4f}  "
            f"HIGH={twf_with_factor(group_fn, 1.2)/1e9:.4f} bn m³",
            log,
        )
    return pd.DataFrame(rows)


def compute_split_twf(W: np.ndarray, L: np.ndarray,
                       Y_inb_163: np.ndarray, Y_dom_163: np.ndarray,
                       concordance: pd.DataFrame, year: str,
                       W_green: np.ndarray = None,
                       log: Logger = None) -> pd.DataFrame:
    """
    Compute inbound vs domestic split TWF — blue, green, and scarce.

    Parameters
    ----------
    W        : blue water coefficient vector (m³/₹ crore), shape (140,)
    L        : Leontief inverse, shape (140, 140)
    Y_inb_163: inbound demand vector, shape (163,) — mapped to SUT-140 internally
    Y_dom_163: domestic demand vector, shape (163,) — mapped to SUT-140 internally
    W_green  : green water coefficient vector (m³/₹ crore), shape (140,).
               When provided, computes exact EEIO green TWF for each segment via
               (W_green @ L) * Y — the same Leontief propagation used for blue.
               When None, Green_m3 columns are omitted from output.

    Returns
    -------
    DataFrame with columns:
        Year, Type, TWF_m3, TWF_bn_m3,
        Green_m3, Green_bn_m3,          ← new (only when W_green is supplied)
        Scarce_m3, Demand_crore

    BUG FIX (original): Previously applied a flat 0.814 multiplier for scarce
    TWF on both splits. This is wrong — it ignores the source-group composition
    of each split and gives identical scarce ratios regardless of demand mix.
    Now uses the WSI vector computed from classify_source_group.
    """
    Y_inb = map_y_to_sut(Y_inb_163, concordance, log=log)
    Y_dom = map_y_to_sut(Y_dom_163, concordance, log=log)
    WL    = W @ L

    TWF_inb = WL * Y_inb
    TWF_dom = WL * Y_dom

    # Build per-product WSI vector for scarce computation
    wsi_vec    = np.array([WSI_WEIGHTS.get(classify_source_group(i + 1), 0.814)
                           for i in range(len(W))])
    WL_scarce  = (W * wsi_vec) @ L     # WSI-weighted water multiplier
    Scarce_inb = float((WL_scarce * Y_inb).sum())
    Scarce_dom = float((WL_scarce * Y_dom).sum())

    # Green water — exact EEIO propagation per segment
    # Formula: Green_TWF_segment = (W_green @ L) * Y_segment
    # This is NOT a proportional allocation — it is the same Leontief pull
    # used for blue water, applied to the green coefficient vector.
    # Green water is non-zero only in agricultural source rows; the Leontief
    # propagation distributes it across all destination sectors that draw on
    # agriculture through their supply chains.
    Green_inb = 0.0
    Green_dom = 0.0
    if W_green is not None:
        WL_green  = W_green @ L           # green water multiplier, shape (140,)
        Green_inb = float((WL_green * Y_inb).sum())
        Green_dom = float((WL_green * Y_dom).sum())
        ok(
            f"Split green TWF {year}: inbound={Green_inb/1e9:.4f}  "
            f"domestic={Green_dom/1e9:.4f} bn m³  "
            f"(green/blue inb={Green_inb/max(TWF_inb.sum(),1e-9):.3f}  "
            f"dom={Green_dom/max(TWF_dom.sum(),1e-9):.3f})",
            log,
        )

    ok(f"Split blue TWF {year}: inbound={TWF_inb.sum()/1e9:.4f}  "
       f"domestic={TWF_dom.sum()/1e9:.4f} bn m³  "
       f"scarce_inb={Scarce_inb/1e9:.4f}  scarce_dom={Scarce_dom/1e9:.4f} bn m³", log)

    df_dict = {
        "Year":         year,
        "Type":         ["Inbound", "Domestic"],
        "TWF_m3":       [float(TWF_inb.sum()), float(TWF_dom.sum())],
        "TWF_bn_m3":    [TWF_inb.sum() / 1e9,  TWF_dom.sum() / 1e9],
        "Scarce_m3":    [Scarce_inb,            Scarce_dom],
        "Demand_crore": [float(Y_inb.sum()),    float(Y_dom.sum())],
    }

    if W_green is not None:
        df_dict["Green_m3"]    = [Green_inb,            Green_dom]
        df_dict["Green_bn_m3"] = [Green_inb / 1e9,      Green_dom / 1e9]

    return pd.DataFrame(df_dict)


# ══════════════════════════════════════════════════════════════════════════════
# PRINT HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def print_summary(cat_df: pd.DataFrame, year: str, log: Logger = None):
    total        = cat_df["Total_Water_m3"].sum()
    total_scarce = cat_df["Scarce_m3"].sum()
    demand       = cat_df["Demand_crore"].sum()
    _usd_rate    = USD_INR.get(year, 70.0)
    usd_demand_m = crore_to_usd_m(demand, _usd_rate)
    lines = [
        f"\n  Indirect TWF — {year}",
        f"  Blue TWF total:   {total:>20,.0f} m³  ({total/1e9:.4f} bn m³)",
        f"  Scarce TWF total: {total_scarce:>20,.0f} m³  ({total_scarce/1e9:.4f} bn m³)",
        f"  Scarce/Blue ratio:{total_scarce/max(total,1):>19.3f}  "
        f"(WSI-weighted; Aqueduct 4.0 Agriculture=0.827, Industry=0.814)",
        f"  Tourism demand:   {demand:>20,.0f} crore  (${usd_demand_m:,.0f}M)",
        f"  Water intensity:  {total/demand:>20.1f} m³/crore",
    ]
    if log:
        log._log("\n".join(lines))
    else:
        print("\n".join(lines))
    top_n(cat_df, "Total_Water_m3", "Category_Name", n=10, unit=" m³",
          pct_base=total, log=log)
    subsection("By sector type (blue TWF)", log)
    for ctype, grp in cat_df.groupby("Category_Type"):
        w    = grp["Total_Water_m3"].sum()
        s    = grp["Scarce_m3"].sum()
        line = (f"    {ctype:<20}: {w:>16,.0f} m³ ({100*w/max(total,1):.1f}%)  "
                f"scarce: {s:>14,.0f} m³")
        if log:
            log.info(line)
        else:
            print(line)


def print_water_origin_summary(origin_df: pd.DataFrame, year: str, log: Logger = None):
    if origin_df.empty:
        return
    lines = [f"\n  Water origin by source sector — {year}  (Blue | Scarce)"]
    for _, r in origin_df.iterrows():
        lines.append(
            f"    {r['Source_Group']:<15}  WSI={r['WSI_weight']:.3f}  "
            f"Blue: {r['Water_m3']:>14,.0f} m³ ({r['Water_pct']:.1f}%)  "
            f"Scarce: {r['Scarce_m3']:>13,.0f} m³ ({r['Scarce_pct']:.1f}%)"
        )
    if log:
        log._log("\n".join(lines))
    else:
        print("\n".join(lines))


def print_multiplier_ratio_summary(mr_df: pd.DataFrame, year: str, log: Logger = None):
    subsection(f"Water multiplier ratio — {year}  (WL[j] / economy_avg_WL)", log)
    above = mr_df[mr_df["Above_Economy_Avg"]]
    below = mr_df[~mr_df["Above_Economy_Avg"]]
    lines = [
        f"    Sectors ABOVE economy average (ratio > 1):",
    ]
    for _, r in above.head(10).iterrows():
        lines.append(
            f"      {r['Category_Name']:<40}  ratio={r['Multiplier_Ratio']:.2f}x  "
            f"WL={r['WL_m3_per_crore']:.1f} m³/cr"
        )
    lines.append(f"    Sectors BELOW economy average (ratio < 1):")
    for _, r in below.head(5).iterrows():
        lines.append(
            f"      {r['Category_Name']:<40}  ratio={r['Multiplier_Ratio']:.2f}x  "
            f"WL={r['WL_m3_per_crore']:.1f} m³/cr"
        )
    if log:
        log._log("\n".join(lines))
    else:
        print("\n".join(lines))


def save_summary_txt(cat_df: pd.DataFrame, origin_df: pd.DataFrame,
                      year: str, out_path: Path, log: Logger = None):
    total        = cat_df["Total_Water_m3"].sum()
    total_scarce = cat_df["Scarce_m3"].sum() if "Scarce_m3" in cat_df.columns else 0
    demand       = cat_df["Demand_crore"].sum()
    _usd_rate    = USD_INR.get(year, 70.0)
    usd_demand_m = crore_to_usd_m(demand, _usd_rate)
    nom_intensity = total / demand if demand > 0 else 0

    with open(out_path, "w") as f:
        f.write(f"INDIRECT TWF — {year}\n{'='*60}\n\n")
        f.write(f"Blue TWF:     {total:,.0f} m³  ({total/1e9:.4f} billion m³)\n")
        f.write(f"Scarce TWF:   {total_scarce:,.0f} m³  ({total_scarce/1e9:.4f} billion m³)\n")
        f.write(f"  (Scarce = Blue × WSI; WSI from WRI Aqueduct 4.0, Kuzma et al. 2023)\n")
        f.write(f"  Agriculture WSI=0.827 (Irr-weighted bws); Industry WSI=0.814 (Ind-weighted)\n\n")
        f.write(f"Tourism demand: ₹{demand:,.0f} crore  (${usd_demand_m:,.0f}M @ ₹{_usd_rate}/USD)\n")
        f.write(f"Blue intensity: {nom_intensity:.1f} m³/₹ crore\n\n")
        f.write("Top 20 categories (blue TWF, destination view):\n")
        for rank, (_, r) in enumerate(cat_df.head(20).iterrows(), 1):
            f.write(f"  {rank:2d}. {r['Category_Name']:<40} {r['Total_Water_m3']:>14,.0f} m³  "
                    f"scarce: {r.get('Scarce_m3',0):>12,.0f} m³\n")
        if not origin_df.empty:
            f.write("\nWater origin (upstream extraction):\n")
            for _, r in origin_df.iterrows():
                f.write(
                    f"  {r['Source_Group']:<15}  WSI={r.get('WSI_weight',0):.3f}  "
                    f"blue={r['Water_m3']:>14,.0f} m³ ({r['Water_pct']:.1f}%)  "
                    f"scarce={r.get('Scarce_m3',0):>12,.0f} m³ ({r.get('Scarce_pct',0):.1f}%)\n"
                )
    ok(f"Summary: {out_path.name}", log)


# ══════════════════════════════════════════════════════════════════════════════
# SECTOR-LEVEL SUPPLY-CHAIN DECOMPOSITION  (Fig. 3 equivalent)
# ══════════════════════════════════════════════════════════════════════════════
#
# Replicates the analysis in e.g. Fig. 3 of Lee et al. (2021):
#   "Air transportation generates 9% direct use and 91% indirect use from the
#    supply chain. Among indirect TWFs, 56% is from agriculture, 15% electricity,
#    4% petroleum, 1% paper."
#
# For each TSA category we:
#   1. Isolate its demand in Y_163 (zero all other entries).
#   2. Map to Y_140 via the existing concordance.
#   3. Run W @ L * Y_140  →  indirect TWF for that sector.
#   4. Decompose the Leontief pull by source group (Agriculture / Electricity /
#      Petroleum / Manufacturing / Services) using classify_source_group().
#   5. Add direct TWF from direct_twf_{year}.csv (BASE scenario) for the four
#      sectors that have activity-based estimates (hotel, restaurant, rail, air).
#      All other categories have direct = 0 because EXIOBASE captures their
#      on-site water through the supply chain already.
#
# WHY direct ≈ 0 for most service sectors in EXIOBASE?
#   EXIOBASE W vector is WaterGAP blue-water abstraction at basin level.
#   Service sectors (hotels, airlines, rail) have near-zero abstraction
#   coefficients because their tap/operational water is not captured in
#   WaterGAP basin accounts — it appears instead through upstream utility
#   and agriculture supply chains. The activity-based estimates in
#   calculate_direct_twf.py fill this gap for the four measurable sectors.

# TSA category → key in direct_twf_{year}.csv column headers
# Only these four have non-zero activity-based direct estimates.
_TSA_TO_DIRECT: dict = {
    "Accommodation services/hotels":                  "hotel",
    "Food and beverage serving services/restaurants": "restaurant",
    "Railway passenger transport services":           "rail",
    "Air passenger transport services":               "air",
}


def _load_direct_twf_base(year: str, log: Logger = None) -> dict:
    """
    Load BASE-scenario direct TWF (m³) per activity sector for a given year.

    Returns
    -------
    dict : {sector_key: m³}  e.g. {"hotel": 1.2e9, "air": 3.5e8, ...}
    All keys present with 0.0 if file is missing or sector column absent.
    """
    zero = {"hotel": 0.0, "restaurant": 0.0, "rail": 0.0, "air": 0.0}
    path = DIRS["direct"] / f"direct_twf_{year}.csv"
    if not path.exists():
        warn(
            f"direct_twf_{year}.csv not found — direct TWF set to 0 for all sectors. "
            "Run calculate_direct_twf.py first so the sector decomposition includes "
            "activity-based direct water (hotel tap, restaurant kitchen, rail/air use).",
            log,
        )
        return zero
    try:
        df   = pd.read_csv(path)
        base = df[df["Scenario"] == "BASE"]
        if base.empty:
            warn(f"No BASE row in direct_twf_{year}.csv — direct TWF set to 0.", log)
            return zero
        row = base.iloc[0]
        return {
            "hotel":      float(row.get("Hotel_m3",      0)),
            "restaurant": float(row.get("Restaurant_m3", 0)),
            "rail":       float(row.get("Rail_m3",       0)),
            "air":        float(row.get("Air_m3",        0)),
        }
    except Exception as e:
        warn(f"Could not parse direct_twf_{year}.csv: {e} — direct set to 0.", log)
        return zero


def sector_supply_chain_decomposition(
    W_140:       np.ndarray,
    L:           np.ndarray,
    Y_163:       np.ndarray,
    concordance: pd.DataFrame,
    sut_water_df: pd.DataFrame,
    year:        str,
    log:         Logger = None,
) -> pd.DataFrame:
    """
    Per-TSA-category direct + indirect TWF with upstream supply-chain attribution.

    For each TSA category i:
        Y_163_i        = copy of Y_163 zeroed except this category's EXIO indices
        Y_140_i        = map_y_to_sut(Y_163_i, concordance)
        indirect_vec   = (W_140 @ L) * Y_140_i           ← shape (140,)
        indirect_m3    = indirect_vec.sum()

        source attribution:
            for src_id in range(140):
                pull = W_140[src_id] × dot(L[src_id, :], Y_140_i)
            aggregate pull by classify_source_group(src_id+1)

        direct_m3 = from direct_twf_{year}.csv BASE column (hotel/restaurant/rail/air only)
        total_m3  = indirect_m3 + direct_m3

    Parameters
    ----------
    W_140        : blue water coefficient vector (140,)  [m³/₹ crore]
    L            : Leontief inverse (140×140)
    Y_163        : full 163-sector tourism demand vector [₹ crore nominal]
    concordance  : EXIOBASE→SUT concordance DataFrame
    sut_water_df : water coefficient table (product names for logging)
    year         : study year string  e.g. "2019"
    log          : Logger instance

    Returns
    -------
    DataFrame sorted by Total_m3 descending, columns:
        Year, Rank, TSA_Category, Demand_crore,
        Indirect_m3, Direct_m3, Total_m3, Total_bn_m3,
        Direct_pct, Indirect_pct,
        Agr_m3, Elec_m3, Petro_m3, Mfg_m3, Svc_m3,
        Agr_pct_of_indirect, Elec_pct_of_indirect,
        Petro_pct_of_indirect, Mfg_pct_of_indirect, Svc_pct_of_indirect,
        Scarce_indirect_m3, Has_Direct_TWF
    """
    direct_by_sector = _load_direct_twf_base(year, log)

    # Pre-compute WSI-weighted water multiplier for scarce indirect TWF
    wsi_vec    = np.array([
        WSI_WEIGHTS.get(classify_source_group(i + 1), 0.814)
        for i in range(len(W_140))
    ])
    WL         = W_140 @ L            # shape (140,) — blue multiplier vector
    WL_scarce  = (W_140 * wsi_vec) @ L   # shape (140,) — scarce multiplier vector

    rows = []
    for cat, mappings in TSA_TO_EXIOBASE.items():

        # ── Step 1: isolate this category's demand in 163-sector space ────────
        Y_163_cat = np.zeros(len(Y_163))
        for code, _share in mappings:
            idx = EXIO_IDX.get(code)
            if idx is not None and idx < len(Y_163):
                Y_163_cat[idx] = Y_163[idx]
            else:
                warn(f"sector_decomp [{cat}]: EXIO code '{code}' not in EXIO_IDX", log)

        demand_crore = float(Y_163_cat.sum())
        if demand_crore == 0:
            # Category has zero demand this year — include as zero row so
            # the CSV is complete but don't pollute logs.
            continue

        # ── Step 2: map to SUT-140 (suppress per-category mapping logs) ───────
        Y_140_cat = map_y_to_sut(Y_163_cat, concordance, log=None)

        # ── Step 3: EEIO indirect TWF ─────────────────────────────────────────
        indirect_vec  = WL        * Y_140_cat
        scarce_ind_vec= WL_scarce * Y_140_cat
        indirect_m3   = float(indirect_vec.sum())
        scarce_ind_m3 = float(scarce_ind_vec.sum())

        # ── Step 4: source-group attribution of indirect TWF ─────────────────
        # For each source sector s:  pull_s = W[s] × Σ_j L[s,j] × Y_140_cat[j]
        # This is the same Leontief decomposition used in structural_decomposition()
        # but scoped to a single tourism category's demand vector.
        group_totals: dict[str, float] = {}
        for src_id in range(len(W_140)):
            grp  = classify_source_group(src_id + 1)
            pull = float(W_140[src_id] * np.dot(L[src_id, :], Y_140_cat))
            group_totals[grp] = group_totals.get(grp, 0.0) + pull

        agr_m3   = group_totals.get("Agriculture",   0.0)
        elec_m3  = group_totals.get("Electricity",   0.0)
        petro_m3 = group_totals.get("Petroleum",     0.0)
        mfg_m3   = group_totals.get("Manufacturing", 0.0)
        svc_m3   = group_totals.get("Services",      0.0)

        def _pct(v: float) -> float:
            return round(100.0 * v / indirect_m3, 2) if indirect_m3 > 0 else 0.0

        # ── Step 5: join with direct TWF ──────────────────────────────────────
        direct_key = _TSA_TO_DIRECT.get(cat)
        direct_m3  = direct_by_sector.get(direct_key, 0.0) if direct_key else 0.0

        total_m3   = indirect_m3 + direct_m3
        direct_pct = round(100.0 * direct_m3  / total_m3, 2) if total_m3 > 0 else 0.0
        indir_pct  = round(100.0 * indirect_m3 / total_m3, 2) if total_m3 > 0 else 0.0

        rows.append({
            "Year":                   year,
            "TSA_Category":           cat,
            "Demand_crore":           round(demand_crore, 2),
            # ── TWF volumes ───────────────────────────────────────────────
            "Indirect_m3":            round(indirect_m3),
            "Direct_m3":              round(direct_m3),
            "Total_m3":               round(total_m3),
            "Total_bn_m3":            round(total_m3 / 1e9, 6),
            # ── Direct / indirect split ───────────────────────────────────
            "Direct_pct":             direct_pct,
            "Indirect_pct":           indir_pct,
            # ── Upstream supply-chain attribution (absolute m³) ───────────
            "Agr_m3":                 round(agr_m3),
            "Elec_m3":                round(elec_m3),
            "Petro_m3":               round(petro_m3),
            "Mfg_m3":                 round(mfg_m3),
            "Svc_m3":                 round(svc_m3),
            # ── Upstream attribution as % of indirect TWF ─────────────────
            "Agr_pct_of_indirect":    _pct(agr_m3),
            "Elec_pct_of_indirect":   _pct(elec_m3),
            "Petro_pct_of_indirect":  _pct(petro_m3),
            "Mfg_pct_of_indirect":    _pct(mfg_m3),
            "Svc_pct_of_indirect":    _pct(svc_m3),
            # ── Scarce water ──────────────────────────────────────────────
            # Direct scarce uses industry WSI (0.814) as a conservative proxy
            # for hotel/restaurant/rail/air operational water stress.
            "Scarce_indirect_m3":     round(scarce_ind_m3),
            "Scarce_total_m3":        round(scarce_ind_m3 + direct_m3 * 0.814),
            "Has_Direct_TWF":         direct_m3 > 0,
        })

    if not rows:
        warn(f"sector_supply_chain_decomposition {year}: no rows produced — "
             "check TSA_TO_EXIOBASE in config.py and Y_163 demand vector.", log)
        return pd.DataFrame()

    df = (
        pd.DataFrame(rows)
        .sort_values("Total_m3", ascending=False)
        .reset_index(drop=True)
    )
    df.insert(0, "Rank", range(1, len(df) + 1))

    ok(
        f"Sector decomp {year}: {len(df)} categories  "
        f"top: {df.iloc[0]['TSA_Category'][:35]}  "
        f"total: {df['Total_m3'].sum()/1e9:.4f} bn m³  "
        f"(indirect {df['Indirect_m3'].sum()/1e9:.4f}  "
        f"direct {df['Direct_m3'].sum()/1e9:.4f} bn m³)",
        log,
    )
    return df


def print_sector_decomp_summary(df: pd.DataFrame, year: str, log: Logger = None):
    """
    Print top-5 sectors by total TWF with direct/indirect split
    and upstream attribution — mirrors the Fig. 3 narrative in the paper.
    """
    if df.empty:
        return
    subsection(
        f"Sector supply-chain decomposition — {year}  "
        f"(Top 5 by total TWF; Agr/Elec/Petro % are of indirect only)",
        log,
    )
    header = (
        f"\n  {'Rk':<3}  {'TSA Category':<44}  "
        f"{'Total bn m³':>11}  {'Dir%':>6}  {'Ind%':>6}  "
        f"{'Agr%':>6}  {'Elec%':>6}  {'Petro%':>7}  {'Mfg%':>6}"
    )
    sep = "  " + "─" * 103
    lines = [header, sep]
    for _, r in df.head(5).iterrows():
        lines.append(
            f"  {int(r['Rank']):<3}  {str(r['TSA_Category'])[:44]:<44}  "
            f"{r['Total_bn_m3']:>11.4f}  "
            f"{r['Direct_pct']:>6.1f}  {r['Indirect_pct']:>6.1f}  "
            f"{r['Agr_pct_of_indirect']:>6.1f}  "
            f"{r['Elec_pct_of_indirect']:>6.1f}  "
            f"{r['Petro_pct_of_indirect']:>7.1f}  "
            f"{r['Mfg_pct_of_indirect']:>6.1f}"
        )
    msg = "\n".join(lines)
    if log:
        log._log(msg)
    else:
        print(msg)


# ══════════════════════════════════════════════════════════════════════════════
# YEAR PROCESSOR
# ══════════════════════════════════════════════════════════════════════════════

def _process_year(year: str, out_dir: Path, log: Logger) -> dict | None:
    log.section(f"Year: {year}")
    try:
        inp = _load_inputs(year, log)
        Y_163, L       = inp["Y_163"], inp["L"]
        concordance    = inp["concordance"]
        sut_water_df   = inp["sut_water_df"]
        wc, wc_green   = inp["wc"], inp["wc_green"]

        check_matrix_properties(L, f"L_{year}", log)
        Y_140 = map_y_to_sut(Y_163, concordance, log=log)
        W_140 = sut_water_df[wc].values.astype(float)

        TWF, WL = compute_twf(W_140, L, Y_140)

        # --- Green water via full EEIO propagation ---
        # BUG FIX: previously stored raw green coefficients (m³/₹ crore) in
        # Green_Water_m3_direct. The correct approach is to apply the same
        # Leontief propagation as blue: Green_TWF = (W_green @ L) * Y_140
        # This accounts for all upstream supply-chain green water, not just
        # the direct coefficient — typically ~7000× larger.
        green_twf = None
        if wc_green and wc_green in sut_water_df.columns:
            W_green    = sut_water_df[wc_green].values.astype(float)
            green_twf  = (W_green @ L) * Y_140
            green_total = green_twf.sum()
            blue_total  = TWF.sum()
            ok(
                f"Green EEIO TWF {year}: {green_total/1e9:.4f} bn m³  "
                f"(green/blue ratio = {green_total/max(blue_total,1e-9):.3f})",
                log,
            )

        # --- Water multiplier ratio ---
        # Economy proxy: total final demand across all products (uniform proxy).
        # Best practice: replace Y_economy with the actual total output vector x
        # from the IO table (x = L @ y_total) when available.
        cfg      = YEARS[year]
        io_x_path = DIRS["io"] / cfg["io_year"] / f"io_output_{cfg['io_tag']}.csv"
        Y_economy = None
        if io_x_path.exists():
            try:
                io_out = pd.read_csv(io_x_path)
                if "Total_Output_crore" in io_out.columns and len(io_out) == len(W_140):
                    Y_economy = io_out["Total_Output_crore"].values.astype(float)
                    ok(f"Using IO total output for economy WL benchmark ({year})", log)
            except Exception as e:
                warn(f"Could not load IO total output for {year}: {e} — using uniform proxy", log)
        if Y_economy is None:
            Y_economy = np.ones(len(W_140)) * Y_140.sum() / max(len(W_140), 1)
            warn(f"Using uniform Y_economy proxy for {year} — "
                 "run build_io first to get correct sector-level benchmarks", log)

        multiplier_ratio = compute_water_multiplier_ratio(WL, Y_economy)

        sut_results = build_sut_results(
            sut_water_df, wc, Y_140, WL, TWF,
            multiplier_ratio, wc_green, green_twf=green_twf,
        )
        cat_results = aggregate_to_categories(sut_results, concordance)

        print_summary(cat_results, year, log)

        # Structural decomposition + origin
        log.subsection(f"Structural decomposition — {year}")
        struct_df = structural_decomposition(W_140, L, Y_140, sut_water_df, wc, concordance, log)

        # Add green water to origin summary for compare_years.py Table 7b
        origin_df = build_origin_summary(struct_df)
        if green_twf is not None and wc_green and wc_green in sut_water_df.columns:
            # Build green origin by SOURCE sector, mirroring how blue origin is
            # computed in structural_decomposition().
            #
            # WRONG (old): iterated over destination products (j) and accumulated
            # green_twf[j] per group. Because tourists buy zero raw agricultural
            # products directly (Y_140[agr_products] ≈ 0), this gave Agriculture
            # green = 0 — the exact same mistake that was fixed for blue water via
            # Product_ID. Agriculture's green water flows through supply-chain
            # propagation from source rows, not from direct final demand.
            #
            # CORRECT: for each source sector i, compute how much green water it
            # contributes across ALL tourism destination sectors j:
            #   green_pull[i] = W_green[i] × Σ_j( L[i,j] × Y_140[j] )
            # This is row i of (W_green[i] * L[i,:]) dot Y_140, i.e. the same
            # Leontief pull decomposition used in structural_decomposition() for blue.
            W_green_vec = sut_water_df[wc_green].values.astype(float)
            green_by_group: dict[str, float] = {}
            for src_id in range(len(W_green_vec)):
                grp = classify_source_group(src_id + 1)
                # Scalar: total green water pulled by tourism demand from source src_id
                green_pull = float(W_green_vec[src_id] * np.dot(L[src_id, :], Y_140))
                green_by_group[grp] = green_by_group.get(grp, 0.0) + green_pull

            ok(
                f"Green origin by source group ({year}): "
                + "  ".join(f"{g}={v/1e6:.1f}M" for g, v in sorted(green_by_group.items())),
                log,
            )

            if not origin_df.empty:
                origin_df["Green_Water_m3"] = origin_df["Source_Group"].map(
                    lambda g: green_by_group.get(g, 0.0)
                )

        save_csv(struct_df, out_dir / f"indirect_twf_{year}_structural.csv",
                 f"Structural decomp {year}", log=log)
        save_csv(origin_df, out_dir / f"indirect_twf_{year}_origin.csv",
                 f"Water origin {year}", log=log)
        print_water_origin_summary(origin_df, year, log)

        # Intensity
        intensity_df = per_sector_intensity(cat_results)
        save_csv(intensity_df, out_dir / f"indirect_twf_{year}_intensity.csv",
                 f"Sector intensity {year}", log=log)

        # Water multiplier ratio report
        mr_df = build_multiplier_ratio_report(sut_results, concordance)
        save_csv(mr_df, out_dir / f"water_multiplier_ratio_{year}.csv",
                 f"Multiplier ratio {year}", log=log)
        print_multiplier_ratio_summary(mr_df, year, log)

        # Nominal/real intensity
        nominal_intensity = TWF.sum() / Y_140.sum() if Y_140.sum() > 0 else 0
        real_intensity    = None
        if inp["Y_163_real"] is not None:
            Y_140_real    = map_y_to_sut(inp["Y_163_real"], concordance, log=log)
            real_intensity= TWF.sum() / Y_140_real.sum() if Y_140_real.sum() > 0 else 0
            ok(f"Real-price intensity: {real_intensity:.1f} m³/₹ crore (2015-16 prices)", log)

        # Sensitivity
        log.subsection(f"Sensitivity — {year}")
        sens_df = sensitivity_analysis(W_140, L, Y_140, sut_water_df, wc, log)
        save_csv(sens_df, out_dir / f"indirect_twf_{year}_sensitivity.csv",
                 f"Sensitivity {year}", log=log)

        # ── Supply-chain top-50 paths (sc_path_top50_{year}.csv) ──────────────
        # One row per source×destination pair, ranked by water volume.
        # Used by visualise_results.py fig5 bubble matrix and compare_years.py
        # Tables 20-22 (consolidated supply-chain path table).
        try:
            sc_dir = DIRS.get("supply_chain",
                              out_dir.parent / "supply-chain")
            sc_dir.mkdir(parents=True, exist_ok=True)

            # struct_df has columns: Category_ID, Category_Name,
            #   Source_ID, Source_Name, Source_Group, Water_m3, Scarce_m3
            if not struct_df.empty:
                top50 = (struct_df[struct_df["Water_m3"] > 0]
                         .copy()
                         .sort_values("Water_m3", ascending=False)
                         .head(50))
                total_w = float(struct_df["Water_m3"].sum()) or 1.0
                top50["Rank"]      = range(1, len(top50) + 1)
                top50["Share_pct"] = 100 * top50["Water_m3"] / total_w
                top50["Path"]      = (top50["Source_Name"].str[:30]
                                      + " → " + top50["Category_Name"].str[:25])
                out_cols = ["Rank", "Path", "Source_Group", "Source_Name",
                            "Category_Name", "Water_m3", "Scarce_m3",
                            "Share_pct"]
                save_csv(top50[out_cols],
                         sc_dir / f"sc_path_top50_{year}.csv",
                         f"SC top-50 paths {year}", log=log)
                ok(f"sc_path_top50_{year}.csv: {len(top50)} rows written", log)
            else:
                warn(f"struct_df empty for {year} — sc_path_top50 not written", log)
        except Exception as _sc_err:
            warn(f"sc_path_top50_{year}: {_sc_err}", log)

        # ── Sector supply-chain decomposition (Fig. 3 equivalent) ───────────
        # Runs W·L·Y per TSA category and joins with direct TWF.
        # Requires direct_twf_{year}.csv to already exist (run calculate_direct_twf
        # first); if missing, direct column will be zero but indirect is still valid.
        try:
            log.subsection(f"Sector supply-chain decomposition — {year}")
            sector_decomp_df = sector_supply_chain_decomposition(
                W_140, L, Y_163, concordance, sut_water_df, year, log,
            )
            if not sector_decomp_df.empty:
                save_csv(
                    sector_decomp_df,
                    out_dir / f"indirect_twf_{year}_sector_decomp.csv",
                    f"Sector decomp {year}",
                    log=log,
                )
                print_sector_decomp_summary(sector_decomp_df, year, log)
        except Exception as _sd_err:
            warn(f"sector_supply_chain_decomposition {year}: {_sd_err} — skipping", log)

        # Inbound/domestic split
        # W_green is None when no green column exists in the concordance file —
        # compute_split_twf handles that gracefully (omits Green_m3 columns).
        if inp["Y_inb"] is not None and inp["Y_dom"] is not None:
            split_df = compute_split_twf(
                W_140, L, inp["Y_inb"], inp["Y_dom"],
                concordance, year,
                W_green=W_green,    # None when wc_green absent — handled inside
                log=log,
            )
            save_csv(split_df, out_dir / f"indirect_twf_{year}_split.csv",
                     f"Split {year}", log=log)

        # Main CSVs
        save_csv(sut_results, out_dir / f"indirect_twf_{year}_by_sut.csv",
                 f"SUT results {year}", log=log)
        save_csv(cat_results, out_dir / f"indirect_twf_{year}_by_category.csv",
                 f"Category results {year}", log=log)
        save_summary_txt(cat_results, origin_df, year,
                         out_dir / f"indirect_twf_{year}_summary.txt", log)

        # Agriculture share
        agr_pct = 0.0
        if not origin_df.empty:
            agr_row = origin_df[origin_df["Source_Group"] == "Agriculture"]
            if not agr_row.empty:
                agr_pct = float(agr_row.iloc[0]["Water_pct"])

        # Scarce TWF totals
        total_scarce = sut_results["Scarce_m3"].sum() if "Scarce_m3" in sut_results.columns else 0

        # Green TWF totals — sum from category-level results (EEIO green propagated)
        total_green = 0.0
        if green_twf is not None:
            total_green = float(green_twf.sum())
        elif "Green_Water_m3" in cat_results.columns:
            total_green = float(cat_results["Green_Water_m3"].sum())

        _usd_rate     = USD_INR.get(year, 70.0)
        _usd_demand_m = crore_to_usd_m(Y_140.sum(), _usd_rate) if Y_140.sum() > 0 else 0
        _usd_intensity= TWF.sum() / _usd_demand_m if _usd_demand_m > 0 else 0

        return {
            "Year":                           year,
            "Indirect_TWF_m3":                TWF.sum(),
            "Indirect_TWF_billion_m3":        TWF.sum() / 1e9,
            "Green_TWF_m3":                   total_green,
            "Green_TWF_billion_m3":           round(total_green / 1e9, 4),
            "Blue_plus_Green_TWF_m3":         TWF.sum() + total_green,
            "Blue_plus_Green_TWF_billion_m3": round((TWF.sum() + total_green) / 1e9, 4),
            "Scarce_TWF_m3":                  total_scarce,
            "Scarce_TWF_billion_m3":          total_scarce / 1e9,
            "Scarce_Blue_Ratio":              round(total_scarce / max(TWF.sum(), 1e-9), 3),
            "Tourism_Demand_crore":           Y_140.sum(),
            "Tourism_Demand_USD_M":           round(_usd_demand_m, 1),
            "USD_INR_Rate":                   _usd_rate,
            "Intensity_m3_per_crore":         nominal_intensity,
            "Intensity_m3_per_USD_M":         round(_usd_intensity, 2),
            "Real_Intensity_m3_per_crore":    real_intensity if real_intensity is not None else 0,
            "Real_Intensity_available":       real_intensity is not None,
            "Top_Sector":                     cat_results.iloc[0]["Category_Name"],
            "Agr_Origin_pct":                 agr_pct,
            "WSI_Source":                     "Kuzma et al. 2023, WRI Aqueduct 4.0",
        }

    except FileNotFoundError as e:
        warn(f"{year}: {e} — skipping", log)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def run(**kwargs):
    with Logger("calculate_indirect_twf", DIRS["logs"]) as log:
        t       = Timer()
        out_dir = DIRS["indirect"]
        out_dir.mkdir(parents=True, exist_ok=True)
        log.section("CALCULATE INDIRECT TWF  (W × L × Y  +  Scarce_TWF  +  Multiplier_Ratio)")
        log.info("WSI source: WRI Aqueduct 4.0 (Kuzma et al. 2023)")
        log.info(f"  Agriculture WSI = {WSI_WEIGHTS.get('Agriculture', 0.827):.3f} (Irr-weighted bws)")
        log.info(f"  Industry WSI    = {WSI_WEIGHTS.get('Manufacturing', 0.814):.3f} (Ind-weighted bws)")
        log.info("  Services WSI    = 0.000 (no direct basin extraction)")

        all_results = [
            res for year in STUDY_YEARS
            if (res := _process_year(year, out_dir, log)) is not None
        ]

        if all_results:
            log.section("Cross-Year Comparison")
            compare_across_years({r["Year"]: r["Indirect_TWF_billion_m3"] for r in all_results},
                                  "Blue indirect TWF (billion m³)", unit=" bn m³", log=log)
            compare_across_years({r["Year"]: r["Green_TWF_billion_m3"] for r in all_results},
                                  "Green indirect TWF (billion m³)", unit=" bn m³", log=log)
            compare_across_years({r["Year"]: r["Blue_plus_Green_TWF_billion_m3"] for r in all_results},
                                  "Blue+Green indirect TWF (billion m³)", unit=" bn m³", log=log)
            compare_across_years({r["Year"]: r["Scarce_TWF_billion_m3"] for r in all_results},
                                  "Scarce TWF (billion m³, Aqueduct 4.0)", unit=" bn m³", log=log)
            compare_across_years({r["Year"]: r["Intensity_m3_per_crore"] for r in all_results},
                                  "Water intensity nominal (m³/₹ crore)", unit=" m³/cr", log=log)
            compare_across_years({r["Year"]: r["Agr_Origin_pct"] for r in all_results},
                                  "Agriculture share of water origin (%)", unit="%", log=log)

            save_csv(pd.DataFrame(all_results),
                     out_dir / "indirect_twf_all_years.csv", "All-year summary", log=log)

        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    run()