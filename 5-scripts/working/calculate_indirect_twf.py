"""
calculate_indirect_twf.py — Indirect Tourism Water Footprint (EEIO).

Core formula:
  TWF_indirect = W × L × Y
Where:
  W = water coefficient vector (m³/₹ crore), shape (140,)
  L = Leontief inverse (I-A)⁻¹, shape (140×140)
  Y = tourism final demand vector (₹ crore), shape (140,)

Unit consistency: ALL variables in ₹ crore → result in m³.

3-sector illustration:
  W = [5000, 0, 0]   m³/crore  (Agriculture only)
  L = [[1.2, 0.8, 0.1],
        [0.3, 1.5, 0.2],
        [0.4, 0.6, 1.3]]
  Y = [0, 150, 300]  crore
  WL  = W @ L = [6000, 4000, 500]  m³/crore
  TWF = WL * Y = 750,000 m³

Additional analyses:
  1. Structural decomposition: per-tourism-sector water pull by SOURCE sector
  2. Water origin summary: aggregated source-group totals
  3. Price deflation: TWF intensity using real (2015-16) demand
  4. Sensitivity: ±20% on agriculture, electricity AND petroleum coefficients
  5. Per-sector intensity: m³ per ₹ crore of tourism spending by category
  6. Inbound vs domestic split TWF

Two "sector" views per year:
  A. "By destination" — groups by WHERE tourism demand lands.
     Agriculture = 0 here because tourists don't buy raw crops directly.
  B. "By source sector" — from structural decomposition.
     Agriculture typically dominates (60-80% upstream pull).

Outputs per year:
  indirect_twf_{year}_by_sut.csv       140 products × water contribution
  indirect_twf_{year}_by_category.csv  75 categories × water contribution
  indirect_twf_{year}_structural.csv   water pull by source sector × category
  indirect_twf_{year}_origin.csv       aggregated water origin by source group
  indirect_twf_{year}_intensity.csv    m³/crore by tourism category
  indirect_twf_{year}_sensitivity.csv  LOW/BASE/HIGH sensitivity
  indirect_twf_{year}_split.csv        inbound vs domestic TWF split
  indirect_twf_{year}_summary.txt      key metrics
  indirect_twf_all_years.csv           cross-year summary
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import DIRS, YEARS, CPI, STUDY_YEARS, USD_INR
from utils import (
    section, subsection, ok, warn, save_csv,
    read_csv, check_conservation, check_matrix_properties,
    top_n, compare_across_years, Timer, Logger,
    crore_to_usd_m, fmt_crore_usd,
)


# ── Input loaders ─────────────────────────────────────────────────────────────

def _load_inputs(year: str, log: Logger = None) -> dict:
    """Load all inputs for one study year and return as a dict."""
    cfg = YEARS[year]

    Y_163 = read_csv(DIRS["demand"] / f"Y_tourism_{year}.csv")["Tourism_Demand_crore"].values
    _usd_rate = USD_INR.get(year, 70.0)
    ok(f"Y_tourism {year} (nominal): {fmt_crore_usd(Y_163.sum(), _usd_rate)}, "
       f"{np.count_nonzero(Y_163)}/163 non-zero", log)

    L = read_csv(DIRS["io"] / cfg["io_year"] / f"io_L_{cfg['io_tag']}.csv",
                 index_col=0).values
    ok(f"L ({cfg['io_year']}): {L.shape}  diag mean={np.diag(L).mean():.4f}", log)

    concordance = read_csv(DIRS["concordance"] / f"concordance_{cfg['io_tag']}.csv")
    ok(f"Concordance {cfg['io_year']}: {len(concordance)} categories", log)

    # ── Concordance duplicate SUT_Product_IDs check ──────────────────────────
    # If two categories share the same SUT_Product_IDs the same water gets
    # counted twice and both rows show identical m³ values (e.g. Leather
    # Footwear = Machinery Rental in some concordance versions).
    _all_sut_ids: list = []
    for _, _crow in concordance.iterrows():
        _sut_str = str(_crow.get("SUT_Product_IDs", ""))
        _ids = frozenset(
            int(s.strip()) for s in _sut_str.split(",")
            if s.strip() and s.strip().lower() not in ("nan", "")
        )
        _all_sut_ids.append((_crow.get("Category_Name", _crow["Category_ID"]), _ids))
    _seen_ids: dict = {}
    for _cat_name, _id_set in _all_sut_ids:
        for _sid in _id_set:
            _seen_ids.setdefault(_sid, []).append(_cat_name)
    _dupes = {k: v for k, v in _seen_ids.items() if len(v) > 1}
    if _dupes:
        warn(
            f"Concordance {cfg['io_year']}: {len(_dupes)} SUT product ID(s) "
            f"mapped to MORE THAN ONE category — these will be double-counted!\n"
            + "\n".join(
                f"    Product_ID {pid}: {cats}"
                for pid, cats in sorted(_dupes.items())
            ),
            log,
        )
    else:
        ok(f"Concordance {cfg['io_year']}: no duplicate SUT_Product_IDs found", log)

    sut_water_df = read_csv(DIRS["concordance"] / f"water_coefficients_140_{cfg['io_tag']}.csv")
    wc = [c for c in sut_water_df.columns if "Water" in c and "crore" in c][0]
    ok(f"SUT water {cfg['io_year']}: {(sut_water_df[wc]>0).sum()}/140 non-zero", log)

    # Real demand (optional)
    Y_163_real = None
    real_path = DIRS["demand"] / f"Y_tourism_{year}_real.csv"
    if real_path.exists():
        Y_163_real = read_csv(real_path)["Tourism_Demand_crore"].values

    # Split vectors (optional)
    Y_inb = Y_dom = None
    f_inb = DIRS["demand"] / f"Y_tourism_{year}_inbound.csv"
    f_dom = DIRS["demand"] / f"Y_tourism_{year}_domestic.csv"
    if f_inb.exists() and f_dom.exists():
        Y_inb = read_csv(f_inb)["Tourism_Demand_crore"].values
        Y_dom = read_csv(f_dom)["Tourism_Demand_crore"].values
        ok(f"Split demand {year}: inbound ₹{Y_inb.sum():,.0f} cr  "
           f"(${crore_to_usd_m(Y_inb.sum(), USD_INR.get(year, 70.0)):,.0f}M)  "
           f"domestic ₹{Y_dom.sum():,.0f} cr  "
           f"(${crore_to_usd_m(Y_dom.sum(), USD_INR.get(year, 70.0)):,.0f}M)", log)
    else:
        warn(f"Split demand files not found for {year} — inbound/domestic analysis skipped.", log)

    return {
        "Y_163": Y_163, "L": L, "concordance": concordance,
        "sut_water_df": sut_water_df, "wc": wc,
        "Y_163_real": Y_163_real, "Y_inb": Y_inb, "Y_dom": Y_dom,
    }


# ── Y mapping: EXIOBASE 163 → SUT 140 ────────────────────────────────────────

def map_y_to_sut(Y_163: np.ndarray, concordance_df: pd.DataFrame,
                  n_sut: int = 140, log: Logger = None) -> np.ndarray:
    """Map 163-sector EXIOBASE demand to 140 SUT products via concordance."""
    Y_140 = np.zeros(n_sut)
    assigned_exio: dict = {}

    for _, row in concordance_df.iterrows():
        cat_id   = row["Category_ID"]
        exio_str = str(row.get("EXIOBASE_Sectors", ""))
        sut_str  = str(row.get("SUT_Product_IDs", ""))

        exio_codes = [e.strip() for e in exio_str.split(",")
                      if e.strip() and e.strip().lower() != "nan"]
        sut_ids    = [int(s.strip()) for s in sut_str.split(",")
                      if s.strip() and s.strip().lower() != "nan"]

        demand = 0.0
        for code in exio_codes:
            if code != "IN" and not code.startswith("IN."):
                warn(f"Skipping unrecognised EXIOBASE code '{code}' in category {cat_id}", log)
                continue
            # Map code to 0-based index
            if code == "IN":
                idx = 0
            else:
                try:
                    idx = int(code.split(".")[1])
                except (IndexError, ValueError):
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
    ok(f"Y_140: ₹{Y_140.sum():,.0f} crore from ₹{Y_163.sum():,.0f} EXIO total "
       f"(coverage {100*Y_140.sum()/max(Y_163.sum(),1):.1f}%)", log)
    return Y_140


# ── Core TWF computation ──────────────────────────────────────────────────────

def compute_twf(W: np.ndarray, L: np.ndarray, Y: np.ndarray):
    """
    TWF = W @ L * Y  (element-wise at the end)
    Returns: TWF vector (per-product water pull), WL vector (water multipliers).
    """
    WL  = W @ L          # shape (140,): water embodied per unit of each product
    TWF = WL * Y         # shape (140,): water pulled by tourism demand
    ok(f"TWF: {TWF.sum()/1e9:.4f} bn m³  |  W mean={W.mean():.2f}  "
       f"WL mean={WL.mean():.2f}  Y sum={Y.sum():,.0f} cr")
    return TWF, WL


def classify_source_group(product_id: int) -> str:
    if 1 <= product_id <= 29:   return "Agriculture"
    if 30 <= product_id <= 40:  return "Mining"
    if product_id == 114:       return "Electricity"
    if 71 <= product_id <= 80:  return "Petroleum"
    if 41 <= product_id <= 113: return "Manufacturing"
    return "Services"


def build_sut_results(sut_water_df: pd.DataFrame, wc: str,
                       Y_140: np.ndarray, WL: np.ndarray, TWF: np.ndarray) -> pd.DataFrame:
    """Build the 140-product SUT results frame.

    Column name fix: the multiplier column is written as
    'Water_Multiplier_m3_per_crore' (not 'Water_Multiplier') so that
    compare_years.type1_multipliers() can find it by its expected name.
    Both names referred to the same quantity (WL[i] = m³ per ₹ crore of
    final demand for product i); the old name was just ambiguous.

    Sort note: the frame is sorted by Total_Water_m3 descending for display
    convenience, but the original 0-based integer index is preserved.
    calculate_sda_mc.load_y() re-sorts by Product_ID before extracting
    values so that Y stays aligned with W and L (which are always in
    product-ID order).
    """
    df = sut_water_df.copy()
    df["Tourism_Demand_crore"]       = Y_140
    df["Water_Multiplier_m3_per_crore"] = WL   # FIX: was "Water_Multiplier"
    df["Total_Water_m3"]             = TWF
    df["Source_Group"]               = [classify_source_group(i + 1) for i in range(len(TWF))]
    df["Water_pct"]                  = 100 * df["Total_Water_m3"] / df["Total_Water_m3"].sum()
    return df.sort_values("Total_Water_m3", ascending=False)


def aggregate_to_categories(sut_results: pd.DataFrame,
                              concordance: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, crow in concordance.iterrows():
        sut_str = str(crow.get("SUT_Product_IDs", ""))
        sut_ids = [int(s.strip()) for s in sut_str.split(",")
                   if s.strip() and s.strip().lower() != "nan"]
        mask    = sut_results.index.isin([i - 1 for i in sut_ids])
        water   = sut_results.loc[mask, "Total_Water_m3"].sum()
        demand  = sut_results.loc[mask, "Tourism_Demand_crore"].sum()
        rows.append({
            "Category_ID":   crow["Category_ID"],
            "Category_Name": crow.get("Category_Name", str(crow["Category_ID"])),
            "Category_Type": crow.get("Category_Type", ""),
            "Total_Water_m3": water,
            "Demand_crore":   demand,
            "Water_pct":      0.0,
        })
    df = pd.DataFrame(rows).sort_values("Total_Water_m3", ascending=False)
    total = df["Total_Water_m3"].sum()
    df["Water_pct"] = 100 * df["Total_Water_m3"] / total if total > 0 else 0
    return df


def per_sector_intensity(cat_df: pd.DataFrame) -> pd.DataFrame:
    df = cat_df.copy()
    df["Intensity_m3_per_crore"] = df.apply(
        lambda r: r["Total_Water_m3"] / r["Demand_crore"] if r["Demand_crore"] > 0 else 0,
        axis=1,
    )
    return df.sort_values("Intensity_m3_per_crore", ascending=False)


def structural_decomposition(W: np.ndarray, L: np.ndarray, Y: np.ndarray,
                               sut_water_df: pd.DataFrame, wc: str,
                               concordance: pd.DataFrame,
                               log: Logger = None) -> pd.DataFrame:
    """
    Decompose water pull by source sector (WHERE water is extracted)
    for each tourism category (WHERE tourism spends money).
    """
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

        WL_cat = W @ L
        TWF_cat = WL_cat * cat_y

        for src_id in range(n):
            w_src = W[src_id] * L[src_id, :] * cat_y
            rows.append({
                "Category_ID":   crow["Category_ID"],
                "Category_Name": crow.get("Category_Name", ""),
                "Source_ID":     src_id + 1,
                "Source_Name":   sut_water_df.iloc[src_id].get("Product_Name", str(src_id + 1))
                                  if src_id < len(sut_water_df) else str(src_id + 1),
                "Source_Group":  classify_source_group(src_id + 1),
                "Water_m3":      w_src.sum(),
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    total = df["Water_m3"].sum()
    df["Water_pct"] = 100 * df["Water_m3"] / total if total > 0 else 0
    return df.sort_values("Water_m3", ascending=False)


def build_origin_summary(struct_df: pd.DataFrame) -> pd.DataFrame:
    if struct_df.empty:
        return pd.DataFrame()
    grp   = struct_df.groupby("Source_Group")["Water_m3"].sum().reset_index()
    total = grp["Water_m3"].sum()
    grp["Water_pct"] = 100 * grp["Water_m3"] / total if total > 0 else 0
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
        ("Agriculture",  lambda pid: 1 <= pid <= 29),
        ("Electricity",  lambda pid: pid == 114),
        ("Petroleum",    lambda pid: 71 <= pid <= 80),
    ]:
        for scenario, factor in [("LOW", 0.8), ("BASE", 1.0), ("HIGH", 1.2)]:
            twf = twf_with_factor(group_fn, factor) if scenario != "BASE" else base_twf
            rows.append({
                "Component": label, "Scenario": scenario,
                "Total_TWF_m3": round(twf),
                "Delta_pct": round(100 * (twf - base_twf) / base_twf, 2) if base_twf else 0,
            })
        ok(
            f"Sensitivity {label}: "
            f"LOW={twf_with_factor(group_fn, 0.8)/1e9:.4f} bn m³  "
            f"BASE={base_twf/1e9:.4f}  "
            f"HIGH={twf_with_factor(group_fn, 1.2)/1e9:.4f}",
            log,
        )
    return pd.DataFrame(rows)


def compute_split_twf(W: np.ndarray, L: np.ndarray,
                       Y_inb_163: np.ndarray, Y_dom_163: np.ndarray,
                       concordance: pd.DataFrame, year: str,
                       log: Logger = None) -> pd.DataFrame:
    """Compute W×L×Y separately for inbound and domestic demand vectors."""
    from utils import pivot_transposed  # avoid circular at module level

    # Map to SUT 140
    Y_inb = map_y_to_sut(Y_inb_163, concordance, log=log)
    Y_dom = map_y_to_sut(Y_dom_163, concordance, log=log)

    TWF_inb = (W @ L) * Y_inb
    TWF_dom = (W @ L) * Y_dom

    ok(f"Split TWF {year}: inbound={TWF_inb.sum()/1e9:.4f} bn m³  "
       f"domestic={TWF_dom.sum()/1e9:.4f} bn m³", log)

    return pd.DataFrame({
        "Year": year,
        "Type": ["Inbound", "Domestic"],
        "TWF_m3": [TWF_inb.sum(), TWF_dom.sum()],
        "TWF_bn_m3": [TWF_inb.sum() / 1e9, TWF_dom.sum() / 1e9],
        "Demand_crore": [Y_inb.sum(), Y_dom.sum()],
    })


# ── Print helpers ─────────────────────────────────────────────────────────────

def print_summary(cat_df: pd.DataFrame, year: str, log: Logger = None):
    total  = cat_df["Total_Water_m3"].sum()
    demand = cat_df["Demand_crore"].sum()
    _usd_rate = USD_INR.get(year, 70.0)
    usd_demand_m = crore_to_usd_m(demand, _usd_rate)
    lines  = [
        f"\n  Indirect TWF — {year}",
        f"  Total:           {total:>20,.0f} m³",
        f"  Total (bn m³):   {total/1e9:>20.4f}",
        f"  Tourism demand:  {demand:>20,.0f} crore  (${usd_demand_m:,.0f}M @ ₹{_usd_rate}/USD)",
        f"  Water intensity: {total/demand:>20.1f} m³/crore  "
        f"({total/usd_demand_m*1000:.1f} m³/USD thousand)",
    ]
    if log:
        log._log("\n".join(lines))
    else:
        print("\n".join(lines))
    top_n(cat_df, "Total_Water_m3", "Category_Name", n=10, unit=" m³", pct_base=total, log=log)
    subsection("By sector type", log)
    for ctype, grp in cat_df.groupby("Category_Type"):
        w    = grp["Total_Water_m3"].sum()
        line = f"    {ctype:<20}: {w:>16,.0f} m³  ({100*w/total:.1f}%)"
        if log:
            log.info(line)
        else:
            print(line)


def print_water_origin_summary(origin_df: pd.DataFrame, year: str, log: Logger = None):
    if origin_df.empty:
        return
    lines = [f"\n  Water origin by source sector — {year}"]
    for _, r in origin_df.iterrows():
        lines.append(
            f"    {r['Source_Group']:<20}  {r['Water_m3']:>16,.0f} m³  ({r['Water_pct']:.1f}%)"
        )
    if log:
        log._log("\n".join(lines))
    else:
        print("\n".join(lines))


def save_summary_txt(cat_df: pd.DataFrame, origin_df: pd.DataFrame,
                      year: str, out_path: Path, log: Logger = None):
    total = cat_df["Total_Water_m3"].sum()
    demand = cat_df["Demand_crore"].sum()
    _usd_rate = USD_INR.get(year, 70.0)
    usd_demand_m = crore_to_usd_m(demand, _usd_rate)
    nom_intensity = total / demand if demand > 0 else 0
    usd_intensity = total / usd_demand_m if usd_demand_m > 0 else 0   # m³ per USD million
    with open(out_path, "w") as f:
        f.write(f"INDIRECT TWF — {year}\n{'='*60}\n\n")
        f.write(f"Total:        {total:,.0f} m³  ({total/1e9:.4f} billion m³)\n")
        f.write(f"Demand (INR): ₹{demand:,.0f} crore\n")
        f.write(f"Demand (USD): ${usd_demand_m:,.0f} million  (@ ₹{_usd_rate:.2f}/USD)\n")
        f.write(f"Intensity:    {nom_intensity:.1f} m³/₹ crore  |  "
                f"{usd_intensity:.1f} m³/USD million\n\n")
        f.write("Top 20 categories (destination view):\n")
        for rank, (_, r) in enumerate(cat_df.head(20).iterrows(), 1):
            f.write(f"  {rank:2d}. {r['Category_Name']:<40} {r['Total_Water_m3']:>14,.0f} m³\n")
        if not origin_df.empty:
            f.write("\nWater origin by source sector (upstream extraction):\n")
            for _, r in origin_df.iterrows():
                f.write(f"  {r['Source_Group']:<20}  {r['Water_m3']:>16,.0f} m³  ({r['Water_pct']:.1f}%)\n")
    ok(f"Summary: {out_path.name}", log)


# ── Process one year ──────────────────────────────────────────────────────────

def _process_year(year: str, out_dir: Path, log: Logger) -> dict | None:
    log.section(f"Year: {year}")
    try:
        inp = _load_inputs(year, log)
        Y_163, L, concordance     = inp["Y_163"], inp["L"], inp["concordance"]
        sut_water_df, wc          = inp["sut_water_df"], inp["wc"]

        check_matrix_properties(L, f"L_{year}", log)
        Y_140 = map_y_to_sut(Y_163, concordance, log=log)
        W_140 = sut_water_df[wc].values

        TWF, WL      = compute_twf(W_140, L, Y_140)
        sut_results  = build_sut_results(sut_water_df, wc, Y_140, WL, TWF)
        cat_results  = aggregate_to_categories(sut_results, concordance)

        print_summary(cat_results, year, log)

        log.subsection(f"Structural decomposition — {year}")
        struct_df  = structural_decomposition(W_140, L, Y_140, sut_water_df, wc, concordance, log)
        save_csv(struct_df, out_dir / f"indirect_twf_{year}_structural.csv",
                 f"Structural decomp {year}", log=log)

        origin_df = build_origin_summary(struct_df)
        save_csv(origin_df, out_dir / f"indirect_twf_{year}_origin.csv",
                 f"Water origin {year}", log=log)
        print_water_origin_summary(origin_df, year, log)

        intensity_df = per_sector_intensity(cat_results)
        save_csv(intensity_df, out_dir / f"indirect_twf_{year}_intensity.csv",
                 f"Sector intensity {year}", log=log)
        log.subsection("Top 5 most water-intensive tourism spending categories")
        for _, r in intensity_df.head(5).iterrows():
            log.info(
                f"    {r['Category_Name']:<40}  "
                f"{r['Intensity_m3_per_crore']:>10,.1f} m³/crore  "
                f"(demand: ₹{r['Demand_crore']:,.0f} cr)"
            )

        # ── Intensity (nominal and real-price) ───────────────────────────────────
        # nominal_intensity: TWF / nominal demand (current prices for the year)
        nominal_intensity = TWF.sum() / Y_140.sum() if Y_140.sum() > 0 else 0
        real_intensity     = None   # only set if real demand file is available

        if inp["Y_163_real"] is not None:
            Y_140_real     = map_y_to_sut(inp["Y_163_real"], concordance, log=log)
            real_intensity = TWF.sum() / Y_140_real.sum() if Y_140_real.sum() > 0 else 0
            _usd_real      = crore_to_usd_m(Y_140_real.sum(), USD_INR.get("2015", 65.0))
            usd_real_int   = TWF.sum() / _usd_real if _usd_real > 0 else 0
            ok(
                f"Real-price intensity: {real_intensity:.1f} m³/₹ crore (2015-16)  |  "
                f"{usd_real_int:.1f} m³/USD million (2015-16 prices, @ ₹{USD_INR.get('2015', 65.0)}/USD)",
                log,
            )
        else:
            warn(
                f"Real demand file not found — storing nominal intensity "
                f"({nominal_intensity:.1f} m³/crore) under Nominal_Intensity only; "
                "Real_Intensity_m3_per_crore will be 0 in output.",
                log,
            )

        # Sensitivity
        log.subsection(f"Sensitivity (±20% agr./elec./petrol.) — {year}")
        sens_df = sensitivity_analysis(W_140, L, Y_140, sut_water_df, wc, log)
        save_csv(sens_df, out_dir / f"indirect_twf_{year}_sensitivity.csv",
                 f"Sensitivity {year}", log=log)

        # Inbound / domestic split
        if inp["Y_inb"] is not None and inp["Y_dom"] is not None:
            split_df = compute_split_twf(W_140, L, inp["Y_inb"], inp["Y_dom"],
                                          concordance, year, log)
            save_csv(split_df, out_dir / f"indirect_twf_{year}_split.csv",
                     f"Split {year}", log=log)

        # Main outputs
        save_csv(sut_results, out_dir / f"indirect_twf_{year}_by_sut.csv",
                 f"SUT results {year}", log=log)
        save_csv(cat_results, out_dir / f"indirect_twf_{year}_by_category.csv",
                 f"Category results {year}", log=log)
        save_summary_txt(cat_results, origin_df, year,
                         out_dir / f"indirect_twf_{year}_summary.txt", log)

        agr_pct = 0.0
        if not origin_df.empty:
            agr_row = origin_df[origin_df["Source_Group"] == "Agriculture"]
            if not agr_row.empty:
                agr_pct = float(agr_row.iloc[0]["Water_pct"])

        _usd_rate = USD_INR.get(year, 70.0)
        _usd_demand_m = crore_to_usd_m(Y_140.sum(), _usd_rate) if Y_140.sum() > 0 else 0
        _usd_intensity = TWF.sum() / _usd_demand_m if _usd_demand_m > 0 else 0
        return {
            "Year":                          year,
            "Indirect_TWF_m3":               TWF.sum(),
            "Indirect_TWF_billion_m3":       TWF.sum() / 1e9,
            "Tourism_Demand_crore":          Y_140.sum(),
            "Tourism_Demand_USD_M":          round(_usd_demand_m, 1),
            "USD_INR_Rate":                  _usd_rate,
            "Intensity_m3_per_crore":        nominal_intensity,         # nominal prices
            "Intensity_m3_per_USD_M":        round(_usd_intensity, 2),
            # Real_Intensity is 0 when real demand file is unavailable —
            # compare_years.py checks this and falls back to nominal when 0.
            "Real_Intensity_m3_per_crore":   real_intensity if real_intensity is not None else 0,
            "Real_Intensity_available":      real_intensity is not None,
            "Top_Sector":                    cat_results.iloc[0]["Category_Name"],
            "Agr_Origin_pct":                agr_pct,
        }

    except FileNotFoundError as e:
        warn(f"{year}: {e} — skipping", log)
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def run(**kwargs):
    with Logger("calculate_indirect_twf", DIRS["logs"]) as log:
        t       = Timer()
        out_dir = DIRS["indirect"]
        out_dir.mkdir(parents=True, exist_ok=True)
        log.section("CALCULATE INDIRECT TWF  (W × L × Y)")

        all_results = [
            res for year in STUDY_YEARS
            if (res := _process_year(year, out_dir, log)) is not None
        ]

        if all_results:
            log.section("Cross-Year Indirect TWF Comparison")
            compare_across_years({r["Year"]: r["Indirect_TWF_billion_m3"] for r in all_results},
                                  "Indirect TWF (billion m³)", unit=" bn m³", log=log)
            compare_across_years({r["Year"]: r["Intensity_m3_per_crore"] for r in all_results},
                                  "Water intensity nominal (m³/₹ crore)", unit=" m³/cr", log=log)
            compare_across_years({r["Year"]: r["Intensity_m3_per_USD_M"] for r in all_results},
                                  "Water intensity nominal (m³/USD million)", unit=" m³/$M", log=log)
            compare_across_years({r["Year"]: r["Real_Intensity_m3_per_crore"] for r in all_results},
                                  "Water intensity real 2015-16 (m³/₹ crore)", unit=" m³/cr", log=log)
            compare_across_years({r["Year"]: r["Agr_Origin_pct"] for r in all_results},
                                  "Agriculture share of water origin (%)", unit="%", log=log)

            save_csv(pd.DataFrame(all_results),
                     out_dir / "indirect_twf_all_years.csv", "All-year summary", log=log)

        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    run()