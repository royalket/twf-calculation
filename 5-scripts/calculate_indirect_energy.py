"""
calculate_indirect_energy.py — Indirect Tourism Energy Footprint (EEIO)
========================================================================

Core formula (mirrors calculate_indirect_twf.py):
    IEF_indirect = E × L × Y     (primary energy, MJ)
    Emission_IEF = E_emission × L × Y  (fossil energy, MJ)

Where:
    E   = diagonal vector of Final energy coefficients (MJ/₹ crore),
          loaded from energy_coefficients_140_{io_tag}.csv
    L   = Leontief inverse (140 × 140), from build_io_tables.py
    Y   = 140-sector tourism demand vector (₹ crore), from build_tourism_demand.py

Outputs per year (all in 3-final-results/indirect-energy/)
-----------------------------------------------------------
    indirect_energy_{year}_by_sut.csv       — 140 products × Final + Emission MJ
    indirect_energy_{year}_by_category.csv  — 75 categories × Final + Emission MJ
    indirect_energy_{year}_origin.csv       — origin by source group
    indirect_energy_{year}_split.csv        — inbound vs domestic  ← critical for energy.py
    indirect_energy_{year}_sensitivity.csv  — ±20% on Elec/Petroleum coefficients
    indirect_energy_{year}_summary.txt      — key metrics plain text
    indirect_energy_all_years.csv           — cross-year summary ← needed by energy.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    DIRS, YEARS, STUDY_YEARS, USD_INR, TJ_TO_MJ,
    ENERGY_ROW_FINAL, ENERGY_ROW_EMISSION,
)
from utils import (
    section, subsection, ok, warn, save_csv, safe_csv,
    read_csv, compare_across_years, top_n, Timer, Logger,
    crore_to_usd_m, fmt_crore_usd,
    classify_source_group,
)


# ══════════════════════════════════════════════════════════════════════════════
# INPUT LOADERS
# ══════════════════════════════════════════════════════════════════════════════

def _load_inputs(year: str, log: Logger = None) -> dict | None:
    """
    Load all inputs needed for the E × L × Y computation.
    Returns None if any required file is missing.
    """
    cfg = YEARS[year]

    # ── Demand vector ─────────────────────────────────────────────────────────
    y_path = DIRS["demand"] / f"Y_tourism_{year}.csv"
    if not y_path.exists():
        warn(f"Demand vector missing: {y_path} — run build_tourism_demand.py first", log)
        return None
    Y_163 = read_csv(y_path)["Tourism_Demand_crore"].values
    ok(f"Y_tourism {year}: ₹{Y_163.sum():,.0f} cr  {np.count_nonzero(Y_163)}/163 non-zero", log)

    # ── Leontief inverse ──────────────────────────────────────────────────────
    l_path = DIRS["io"] / cfg["io_year"] / f"io_L_{cfg['io_tag']}.csv"
    if not l_path.exists():
        warn(f"Leontief inverse missing: {l_path} — run build_io_tables.py first", log)
        return None
    L = read_csv(l_path, index_col=0).values
    ok(f"L ({cfg['io_year']}): {L.shape}  diag mean={np.diag(L).mean():.4f}", log)

    # ── Concordance (for Y mapping 163→140 and category aggregation) ──────────
    conc_path = DIRS["concordance"] / f"concordance_{cfg['io_tag']}.csv"
    if not conc_path.exists():
        warn(f"Concordance missing: {conc_path}", log)
        return None
    concordance = read_csv(conc_path)

    # ── Energy coefficients ───────────────────────────────────────────────────
    energy_path = DIRS["concordance"] / f"energy_coefficients_140_{cfg['io_tag']}.csv"
    if not energy_path.exists():
        warn(
            f"Energy coefficients missing: {energy_path} — "
            "run build_energy_coefficients.py first",
            log,
        )
        return None
    sut_energy_df = read_csv(energy_path)

    water_year  = cfg["water_year"]
    final_col    = f"Energy_{water_year}_Final_MJ_per_crore"
    emission_col = f"Energy_{water_year}_Emission_MJ_per_crore"

    if final_col not in sut_energy_df.columns:
        # Try to find any Final_MJ_per_crore column as fallback
        candidates = [c for c in sut_energy_df.columns
                      if "Final_MJ_per_crore" in c or "Final_mj_per_crore" in c.lower()]
        if candidates:
            final_col = candidates[0]
            warn(f"Expected column not found; using fallback: {final_col}", log)
        else:
            warn(f"Column '{final_col}' not in energy coefficients SUT file. "
                 f"Available: {sut_energy_df.columns.tolist()}", log)
            return None

    if emission_col not in sut_energy_df.columns:
        candidates = [c for c in sut_energy_df.columns
                      if "Emission_MJ_per_crore" in c or "emission_mj_per_crore" in c.lower()]
        if candidates:
            emission_col = candidates[0]
            warn(f"Emission column fallback: {emission_col}", log)
        else:
            warn(f"Emission column '{emission_col}' not found — Emission_IEF will be zero", log)
            emission_col = None

    ok(f"Energy coefficient columns — Final: '{final_col}', Emission: '{emission_col}'", log)
    ok(f"Final coeff non-zero: {(sut_energy_df[final_col] > 0).sum()}/140", log)

    # ── Optional inbound / domestic split demand ──────────────────────────────
    Y_inb = Y_dom = None
    f_inb = DIRS["demand"] / f"Y_tourism_{year}_inbound.csv"
    f_dom = DIRS["demand"] / f"Y_tourism_{year}_domestic.csv"
    if f_inb.exists() and f_dom.exists():
        Y_inb = read_csv(f_inb)["Tourism_Demand_crore"].values
        Y_dom = read_csv(f_dom)["Tourism_Demand_crore"].values
        ok(f"Split demand {year}: inbound ₹{Y_inb.sum():,.0f} cr  "
           f"domestic ₹{Y_dom.sum():,.0f} cr", log)
    else:
        warn(f"Split demand files not found for {year} — inbound/domestic split will be skipped", log)

    return {
        "Y_163": Y_163, "L": L, "concordance": concordance,
        "sut_energy_df": sut_energy_df,
        "final_col": final_col, "emission_col": emission_col,
        "Y_inb": Y_inb, "Y_dom": Y_dom,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Y MAPPING: EXIOBASE 163 → SUT 140  (same logic as calculate_indirect_twf)
# ══════════════════════════════════════════════════════════════════════════════

def map_y_to_sut(Y_163: np.ndarray, concordance_df: pd.DataFrame,
                  n_sut: int = 140, log: Logger = None) -> np.ndarray:
    """Map 163-sector EXIOBASE demand to 140-sector SUT via concordance."""
    Y_140 = np.zeros(n_sut)
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
                continue
            if 0 <= idx < len(Y_163):
                demand += Y_163[idx]
        if not sut_ids or demand == 0:
            continue
        per_sut = demand / len(sut_ids)
        for sid in sut_ids:
            if 1 <= sid <= n_sut:
                Y_140[sid - 1] += per_sut
    ok(f"Y_140 energy: ₹{Y_140.sum():,.0f} crore  "
       f"(coverage {100 * Y_140.sum() / max(Y_163.sum(), 1):.1f}%)", log)
    return Y_140


# ══════════════════════════════════════════════════════════════════════════════
# CORE IEF COMPUTATION  E × L × Y
# ══════════════════════════════════════════════════════════════════════════════

def compute_ief(E: np.ndarray, L: np.ndarray, Y: np.ndarray):
    """
    IEF = E @ L * Y  (element-wise product at the end).
    Returns: (IEF vector, EL vector) both shape (140,).
    EL[j] = MJ of embodied energy per ₹ crore of demand for product j.
    """
    EL  = E @ L
    IEF = EL * Y
    ok(f"IEF: {IEF.sum() / 1e9:.4f} bn MJ  |  EL mean={EL.mean():.4f}  "
       f"Y sum={Y.sum():,.0f} cr")
    return IEF, EL


# ══════════════════════════════════════════════════════════════════════════════
# RESULT BUILDERS
# ══════════════════════════════════════════════════════════════════════════════

def build_sut_results(
    sut_energy_df: pd.DataFrame,
    final_col: str,
    emission_col: str | None,
    Y_140: np.ndarray,
    EL_final: np.ndarray,
    IEF_final: np.ndarray,
    IEF_emission: np.ndarray,
) -> pd.DataFrame:
    """Build 140-product SUT results DataFrame."""
    df = sut_energy_df.copy()
    n  = len(IEF_final)
    df["Product_ID"]              = range(1, n + 1)
    df["Tourism_Demand_crore"]    = Y_140
    df["EL_MJ_per_crore"]         = EL_final
    df["Final_Primary_MJ"]        = IEF_final
    df["Emission_MJ"]             = IEF_emission if IEF_emission is not None else 0.0
    df["Source_Group"]            = [classify_source_group(i + 1) for i in range(n)]
    tot = df["Final_Primary_MJ"].sum()
    df["Energy_pct"]              = 100 * df["Final_Primary_MJ"] / max(tot, 1e-9)
    if IEF_emission is not None and tot > 0:
        df["Emission_Final_ratio"] = df["Emission_MJ"] / df["Final_Primary_MJ"].replace(0, float("nan"))
    return df.sort_values("Final_Primary_MJ", ascending=False)


def aggregate_to_categories(
    sut_results: pd.DataFrame,
    concordance: pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate 140-product results to 75 categories."""
    rows = []
    for _, crow in concordance.iterrows():
        sut_str = str(crow.get("SUT_Product_IDs", ""))
        sut_ids = [int(s.strip()) for s in sut_str.split(",")
                   if s.strip() and s.strip().lower() != "nan"]
        if "Product_ID" in sut_results.columns:
            sub = sut_results[sut_results["Product_ID"].isin(sut_ids)]
        else:
            sub = sut_results.iloc[[i - 1 for i in sut_ids if 1 <= i <= len(sut_results)]]
        rows.append({
            "Category_ID":      crow["Category_ID"],
            "Category_Name":    crow.get("Category_Name", str(crow["Category_ID"])),
            "Category_Type":    crow.get("Category_Type", ""),
            "Final_Primary_MJ": sub["Final_Primary_MJ"].sum(),
            "Emission_MJ":      sub["Emission_MJ"].sum() if "Emission_MJ" in sub.columns else 0.0,
            "Demand_crore":     sub["Tourism_Demand_crore"].sum(),
        })
    df = pd.DataFrame(rows).sort_values("Final_Primary_MJ", ascending=False)
    tot = df["Final_Primary_MJ"].sum()
    df["Energy_pct"] = 100 * df["Final_Primary_MJ"] / max(tot, 1e-9)
    if tot > 0:
        df["Intensity_MJ_per_crore"] = (
            df["Final_Primary_MJ"] / df["Demand_crore"].replace(0, float("nan"))
        ).fillna(0)
    return df


def build_origin_summary(
    sut_results: pd.DataFrame,
    concordance: pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate energy pull by source group."""
    grp = (
        sut_results.groupby("Source_Group")
        .agg(
            Final_Primary_MJ=("Final_Primary_MJ", "sum"),
            Emission_MJ     =("Emission_MJ",      "sum"),
        )
        .reset_index()
    )
    tot = grp["Final_Primary_MJ"].sum()
    grp["Energy_pct"] = 100 * grp["Final_Primary_MJ"] / max(tot, 1e-9)
    return grp.sort_values("Final_Primary_MJ", ascending=False)


def sensitivity_analysis(
    E: np.ndarray,
    L: np.ndarray,
    Y: np.ndarray,
    log: Logger = None,
) -> pd.DataFrame:
    """±20% on Electricity and Petroleum energy coefficients."""
    base_ief = (E @ L * Y).sum()

    def ief_with_factor(group_fn, factor):
        E2 = E.copy()
        for i in range(len(E2)):
            if group_fn(i + 1):
                E2[i] *= factor
        return (E2 @ L * Y).sum()

    rows = []
    for label, group_fn in [
        ("Electricity", lambda pid: pid == 114),
        ("Petroleum",   lambda pid: 71 <= pid <= 80),
        ("Utilities",   lambda pid: 92 <= pid <= 109),
    ]:
        for scenario, factor in [("LOW", 0.8), ("BASE", 1.0), ("HIGH", 1.2)]:
            ief = ief_with_factor(group_fn, factor) if scenario != "BASE" else base_ief
            rows.append({
                "Component":      label,
                "Scenario":       scenario,
                "Total_IEF_MJ":   round(ief),
                "Total_IEF_GJ":   round(ief / 1e3, 2),
                "Delta_pct":      round(100 * (ief - base_ief) / base_ief, 2) if base_ief else 0,
            })
        ok(
            f"Sensitivity {label}: "
            f"LOW={ief_with_factor(group_fn, 0.8)/1e9:.4f}  "
            f"BASE={base_ief/1e9:.4f}  "
            f"HIGH={ief_with_factor(group_fn, 1.2)/1e9:.4f} bn MJ",
            log,
        )
    return pd.DataFrame(rows)


def compute_split_energy(
    E: np.ndarray,
    L: np.ndarray,
    Y_inb_163: np.ndarray,
    Y_dom_163: np.ndarray,
    concordance: pd.DataFrame,
    year: str,
    E_emission: np.ndarray = None,
    log: Logger = None,
) -> pd.DataFrame:
    """
    Compute inbound vs domestic split indirect energy footprint.

    This CSV is the critical output read by energy.py::load_inbound_energy().
    Required columns:  Type, Inbound_Primary, Domestic_Primary
                       (plus TWF_m3 alias for backward compat with energy.py)

    Parameters
    ----------
    E          : Final energy coefficient vector (MJ/₹ crore), shape (140,)
    L          : Leontief inverse, shape (140, 140)
    Y_inb_163  : inbound demand vector (163 EXIOBASE sectors)
    Y_dom_163  : domestic demand vector (163 EXIOBASE sectors)
    E_emission : Emission energy coefficient vector (optional), shape (140,)
    """
    Y_inb = map_y_to_sut(Y_inb_163, concordance, log=log)
    Y_dom = map_y_to_sut(Y_dom_163, concordance, log=log)
    EL = E @ L

    IEF_inb = float((EL * Y_inb).sum())
    IEF_dom = float((EL * Y_dom).sum())

    Emiss_inb = float(((E_emission @ L) * Y_inb).sum()) if E_emission is not None else 0.0
    Emiss_dom = float(((E_emission @ L) * Y_dom).sum()) if E_emission is not None else 0.0

    ok(f"Split energy {year}: inbound={IEF_inb/1e9:.4f} bn MJ  "
       f"domestic={IEF_dom/1e9:.4f} bn MJ", log)

    rows = [
        {
            "Year":            year,
            "Type":            "Inbound",
            "Inbound_Primary": IEF_inb,          # column read by energy.py
            "Domestic_Primary": 0.0,
            "Final_Primary_MJ": IEF_inb,
            "Final_Primary_GJ": IEF_inb / 1e3,
            "Final_Primary_TJ": IEF_inb / 1e6,
            "Emission_MJ":      Emiss_inb,
            "Demand_crore":     float(Y_inb.sum()),
            # Alias for backward compatibility with energy.py::load_inbound_energy()
            # which checks for "Inbound_Primary" column — this is it.
        },
        {
            "Year":             year,
            "Type":             "Domestic",
            "Inbound_Primary":  0.0,
            "Domestic_Primary": IEF_dom,
            "Final_Primary_MJ": IEF_dom,
            "Final_Primary_GJ": IEF_dom / 1e3,
            "Final_Primary_TJ": IEF_dom / 1e6,
            "Emission_MJ":      Emiss_dom,
            "Demand_crore":     float(Y_dom.sum()),
        },
    ]
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY TEXT
# ══════════════════════════════════════════════════════════════════════════════

def save_summary_txt(results: dict, out_path: Path, log: Logger = None):
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("INDIRECT TOURISM ENERGY FOOTPRINT (EEIO)\n")
        f.write("=" * 60 + "\n\n")
        f.write("Formula: IEF = E × L × Y  (primary energy, MJ)\n\n")
        for year, r in sorted(results.items()):
            f.write(f"Year: {year}\n")
            f.write(f"  Total Primary (bn MJ):   {r['Primary_Total_bn']:.4f}\n")
            f.write(f"  Total Primary (TJ):      {r['Primary_Total_bn'] * 1e3:.2f}\n")
            f.write(f"  Emission share (%):      {r.get('Emission_pct', 0):.1f}%\n")
            f.write(f"  Intensity (MJ/cr):       {r['Intensity_per_crore']:.2f}\n")
            f.write(f"  Inbound (bn MJ):         {r.get('Inbound_bn', 0):.4f}\n")
            f.write(f"  Domestic (bn MJ):        {r.get('Domestic_bn', 0):.4f}\n\n")
    if log:
        ok(f"Summary: {out_path.name}", log)


# ══════════════════════════════════════════════════════════════════════════════
# PER-YEAR PROCESSOR
# ══════════════════════════════════════════════════════════════════════════════

def _process_year(year: str, out_dir: Path, log: Logger = None) -> dict | None:
    cfg = YEARS[year]
    log.subsection(f"Year: {year}  ({cfg['io_year']})")

    inputs = _load_inputs(year, log)
    if inputs is None:
        return None

    Y_163       = inputs["Y_163"]
    L           = inputs["L"]
    concordance = inputs["concordance"]
    sut_df      = inputs["sut_energy_df"]
    final_col   = inputs["final_col"]
    emission_col= inputs["emission_col"]

    # Build coefficient vectors (140-element arrays aligned to SUT)
    E_final    = sut_df[final_col].values.astype(float)
    E_emission = sut_df[emission_col].values.astype(float) if emission_col else None

    # Map demand to SUT-140
    Y_140 = map_y_to_sut(Y_163, concordance, log=log)

    # Core computation: Final energy
    IEF_final, EL_final = compute_ief(E_final, L, Y_140)

    # Emission energy (fossil)
    IEF_emission = None
    if E_emission is not None:
        IEF_emission, _ = compute_ief(E_emission, L, Y_140)

    # ── Build and save SUT results ─────────────────────────────────────────────
    sut_results = build_sut_results(
        sut_df, final_col, emission_col,
        Y_140, EL_final, IEF_final,
        IEF_emission if IEF_emission is not None else np.zeros_like(IEF_final),
    )
    save_csv(sut_results, out_dir / f"indirect_energy_{year}_by_sut.csv",
             f"Indirect energy SUT {year}", log=log)

    # ── Category aggregation ──────────────────────────────────────────────────
    cat_results = aggregate_to_categories(sut_results, concordance)
    save_csv(cat_results, out_dir / f"indirect_energy_{year}_by_category.csv",
             f"Indirect energy by category {year}", log=log)

    # ── Origin summary ────────────────────────────────────────────────────────
    origin_df = build_origin_summary(sut_results, concordance)
    save_csv(origin_df, out_dir / f"indirect_energy_{year}_origin.csv",
             f"Indirect energy origin {year}", log=log)

    # ── Sensitivity ───────────────────────────────────────────────────────────
    sens_df = sensitivity_analysis(E_final, L, Y_140, log)
    save_csv(sens_df, out_dir / f"indirect_energy_{year}_sensitivity.csv",
             f"Indirect energy sensitivity {year}", log=log)

    # ── Inbound/domestic split ────────────────────────────────────────────────
    inb_total = 0.0
    dom_total = 0.0
    if inputs["Y_inb"] is not None and inputs["Y_dom"] is not None:
        split_df = compute_split_energy(
            E_final, L,
            inputs["Y_inb"], inputs["Y_dom"],
            concordance, year,
            E_emission=E_emission,
            log=log,
        )
        save_csv(split_df, out_dir / f"indirect_energy_{year}_split.csv",
                 f"Indirect energy split {year}", log=log)
        inb_row = split_df[split_df["Type"] == "Inbound"]
        dom_row = split_df[split_df["Type"] == "Domestic"]
        if not inb_row.empty:
            inb_total = float(inb_row["Final_Primary_MJ"].iloc[0])
        if not dom_row.empty:
            dom_total = float(dom_row["Final_Primary_MJ"].iloc[0])
    else:
        warn(f"Skipping split for {year} — inbound/domestic demand files not found", log)

    # ── Key metrics ───────────────────────────────────────────────────────────
    total_mj    = IEF_final.sum()
    total_em_mj = IEF_emission.sum() if IEF_emission is not None else 0.0
    demand_cr   = Y_140.sum()

    ok(f"IEF {year}:  Total={total_mj/1e9:.4f} bn MJ  "
       f"Emission={total_em_mj/1e9:.4f} bn MJ  "
       f"Intensity={total_mj / max(demand_cr, 1):.2f} MJ/cr", log)

    # Top-5 energy-intensive categories
    if not cat_results.empty:
        top5 = cat_results.head(5)[["Category_Name", "Final_Primary_MJ", "Energy_pct"]]
        log.info("  Top-5 energy categories:")
        for _, r in top5.iterrows():
            log.info(f"    {r['Category_Name']:<35}  {r['Final_Primary_MJ']/1e6:>8.2f} TJ  "
                     f"({r['Energy_pct']:.1f}%)")

    return {
        "Year":               year,
        "Primary_Total_MJ":   round(total_mj),
        "Primary_Total_GJ":   round(total_mj / 1e3, 2),
        "Primary_Total_TJ":   round(total_mj / 1e6, 4),
        # ← these two column names are read by energy.py::build_intensity_benchmarks()
        "Primary_Total_bn":   round(total_mj / 1e9, 6),
        "Intensity_per_crore": round(total_mj / max(demand_cr, 1), 4),
        "Emission_MJ":        round(total_em_mj),
        "Emission_pct":       round(100 * total_em_mj / max(total_mj, 1e-9), 2),
        "Inbound_MJ":         round(inb_total),
        "Inbound_bn":         round(inb_total / 1e9, 6),
        "Domestic_MJ":        round(dom_total),
        "Domestic_bn":        round(dom_total / 1e9, 6),
        "Demand_crore":       round(demand_cr, 2),
        "USD_rate":           USD_INR.get(year, 70.0),
    }


# ══════════════════════════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════════════════════════

def run(**kwargs):
    with Logger("calculate_indirect_energy", DIRS["logs"]) as log:
        t       = Timer()
        out_dir = DIRS["indirect_energy"]
        out_dir.mkdir(parents=True, exist_ok=True)

        log.section("CALCULATE INDIRECT ENERGY FOOTPRINT  (E × L × Y)")
        log.info(f"Energy Final row:    {ENERGY_ROW_FINAL}")
        log.info(f"Energy Emission row: {ENERGY_ROW_EMISSION}")
        log.info("Unit: MJ (converted from TJ in EXIOBASE F.txt)")

        all_results: list[dict] = []
        all_results_by_year: dict = {}

        for year in STUDY_YEARS:
            result = _process_year(year, out_dir, log)
            if result is not None:
                all_results.append(result)
                all_results_by_year[year] = result

        if all_results:
            # ── Cross-year comparison ─────────────────────────────────────────
            log.section("Cross-Year Energy Footprint Comparison")
            compare_across_years(
                {r["Year"]: r["Primary_Total_bn"] for r in all_results},
                "Indirect energy (bn MJ)", unit=" bn MJ", log=log,
            )
            compare_across_years(
                {r["Year"]: r["Intensity_per_crore"] for r in all_results},
                "Energy intensity (MJ/₹ crore)", unit=" MJ/cr", log=log,
            )
            compare_across_years(
                {r["Year"]: r["Emission_pct"] for r in all_results},
                "Fossil share of energy (%)", unit="%", log=log,
            )
            if any(r["Inbound_MJ"] > 0 for r in all_results):
                compare_across_years(
                    {r["Year"]: r["Inbound_bn"] for r in all_results},
                    "Inbound indirect energy (bn MJ)", unit=" bn MJ", log=log,
                )

            # ── All-years summary CSV ← read by energy.py::build_intensity_benchmarks()
            all_df = pd.DataFrame(all_results)
            save_csv(all_df, out_dir / "indirect_energy_all_years.csv",
                     "Indirect energy all years", log=log)

            # ── Plain-text summary ────────────────────────────────────────────
            save_summary_txt(
                all_results_by_year,
                out_dir / "indirect_energy_summary.txt",
                log,
            )

        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    run()
