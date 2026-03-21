"""
pipeline_inputs.py — IO Tables + Tourism Demand Vectors
========================================================
Merged from build_io.py + build_demand.py.  Both steps are stressor-blind
and always run first; combining them into one file reflects that coupling
while keeping the logic in two clearly labelled sections.

main.py step registry calls:
    run_io()     ← dispatched by step "build_io"
    run_demand() ← dispatched by step "demand"
    run()        ← runs both in sequence (standalone use)

Section 1 — IO TABLES
─────────────────────
Build product×product IO tables from Supply-Use Tables using the
Product Technology Assumption (PTA):
    D = V / q    market share matrix
    Z = U @ D.T  intermediate flows
    A = Z / x    technical coefficients
    L = (I-A)⁻¹  Leontief inverse

Outputs per year (in io-table/{year}/):
    io_Z_{year}.csv, io_A_{year}.csv, io_L_{year}.csv,
    io_output_{year}.csv, io_products_{year}.csv
Cross-year: io_summary_all_years.csv

Section 2 — TOURISM DEMAND VECTORS
────────────────────────────────────
TSA 2015-16 base × NAS real GVA growth rates × CPI deflator
→ 163-sector EXIOBASE demand vectors (Y_tourism, ₹ crore)

Outputs:
    tsa/tsa_scaled_{year}.csv, tsa/tsa_all_years.csv
    demand/Y_tourism_{year}.csv, demand/Y_tourism_{year}_real.csv
    demand/Y_tourism_{year}_inbound.csv, demand/Y_tourism_{year}_domestic.csv
    demand/demand_intensity_comparison.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    BASE_DIR, DIRS, SUT_UNIT_TO_CRORE, CPI, STUDY_YEARS, USD_INR, YEARS,
    NAS_GROWTH_RATES, NAS_GVA_CONSTANT, TSA_BASE, TSA_TO_NAS,
    TSA_TO_EXIOBASE, EXIO_IDX, EXIO_CODES,
)
from utils import (
    section, subsection, ok, warn, fail, save_csv,
    check_conservation, check_matrix_properties,
    check_spectral_radius, check_a_stability,
    compare_across_years, top_n, Timer, Logger,
    crore_to_usd_m, fmt_crore_usd, table_str,
)

FINAL_DEMAND_COLS = ["PFCE", "GFCE", "GFCF", "CIS", "Valuables", "Export"]


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — IO TABLES  (was build_io.py)
# ══════════════════════════════════════════════════════════════════════════════

def _to_float(val) -> float:
    """
    Convert any raw SUT cell value to a clean float.
    Handles: numeric, None/NaN, empty strings, quoted strings,
    thousand-separator commas, and parenthesised negatives (accounting style).
    """
    if val is None:
        return 0.0
    if isinstance(val, (int, float, np.integer, np.floating)):
        return float(val) if not np.isnan(val) else 0.0
    try:
        if pd.isna(val):
            return 0.0
    except (TypeError, ValueError):
        pass

    s = str(val).strip().strip("'\"")
    if not s or s.lower() in ("nan", "none", "na", "n/a", "-", ""):
        return 0.0
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1].strip()
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def read_sut(path: Path, unit_scale: float, log: Logger = None):
    df = pd.read_csv(path, header=0)
    if df.iloc[0].astype(str).str.match(r"^\d*$").any():
        df = df.iloc[1:].reset_index(drop=True)
    df = df.dropna(how="all").reset_index(drop=True)

    prod_col = df.columns[1]
    df = df[df[prod_col].notna() & df[prod_col].astype(str).str.strip().ne("")]
    df = df[~df[prod_col].astype(str).str.contains(
        r"CIF|Purchases|Total|Output", na=False, case=False, regex=True
    )].reset_index(drop=True)

    products = df[prod_col].astype(str).str.strip().tolist()
    ind_cols = df.columns[2:68].tolist()
    matrix   = (df[ind_cols].map(_to_float).values * unit_scale)
    return products, matrix, df, ind_cols


def clean_a_matrix(A: np.ndarray, products: list, log: Logger = None) -> np.ndarray:
    """
    Enforce Hawkins-Simon condition before Leontief inversion.

    Step 1: Clip individual cells A[i,j] > 1.0 (physically impossible).
    Step 2: Scale columns with sum >= 1.0 down to 0.95 (standard IO repair).

    Several SUT products have A column sums >= 1.0 (zero final demand, data
    errors). Without cleaning, (I-A) is near-singular → L collapses → wrong
    TWF results. The 0.95 cap is conservative and preserves relative shares.
    """
    A = A.copy()

    bad_cells = A > 1.0
    if bad_cells.any():
        n_bad = int(bad_cells.sum())
        warn(f"Clipping {n_bad} A[i,j] > 1.0 to 1.0 (SUT data errors)", log)
        rows_bad, cols_bad = np.where(bad_cells)
        for r, c in zip(rows_bad[:5], cols_bad[:5]):
            name = products[c] if c < len(products) else f"col_{c}"
            if log:
                log.info(f"    A[{r},{c}] ({name[:40]}): {A[r,c]:.4f} → 1.0")
        A = np.clip(A, 0.0, 1.0)

    col_sums = A.sum(axis=0)
    bad_cols = np.where(col_sums >= 1.0)[0]
    if len(bad_cols) > 0:
        warn(f"{len(bad_cols)} A column sums >= 1.0 — scaling to 0.95 (Hawkins-Simon)", log)
        for j in bad_cols:
            cs = A[:, j].sum()
            if cs >= 1.0:
                A[:, j] *= 0.95 / cs
                name = products[j] if j < len(products) else f"col_{j}"
                if log:
                    log.info(f"    col {j+1:3d} ({name[:40]}): A_sum {cs:.4f} → {A[:,j].sum():.4f}")

    final_bad = (A.sum(axis=0) >= 1.0).sum()
    if final_bad == 0:
        ok("All A column sums < 1.0 after cleaning (Hawkins-Simon satisfied)", log)
    else:
        warn(f"{final_bad} columns still >= 1.0 after cleaning — check data", log)
    return A


def pta(V: np.ndarray, U: np.ndarray, y: np.ndarray,
        products: list = None, log: Logger = None):
    """
    Product Technology Assumption.
    Returns: Z, A_clean, L, x (demand-side total output), q (supply-side).
    """
    q      = V.sum(axis=1)
    q_safe = np.where(q < 0.001, 1.0, q)
    D      = V / q_safe[:, np.newaxis]
    Z      = U @ D.T

    x = Z.sum(axis=0) + y
    # FIX-3d: track sign corrections so output CSV can flag them
    sign_corrected = x < 0
    neg = sign_corrected.sum()
    if neg > 0:
        warn(f"{neg} products have negative total output — taking absolute value", log)
        if log:
            for i in np.where(x < 0)[0]:
                name = products[i] if products and i < len(products) else f"col_{i}"
                log.info(f"    product {i+1} ({name[:40]}): x = {x[i]:,.1f}")
        x = np.abs(x)

    x_safe = np.where(x < 0.001, 1.0, x)
    A      = Z / x_safe[np.newaxis, :]
    A      = clean_a_matrix(A, products or [], log)

    I_mat = np.eye(len(A))
    try:
        L = np.linalg.inv(I_mat - A)
    except np.linalg.LinAlgError:
        warn("Singular I-A — using pseudo-inverse", log)
        L = np.linalg.pinv(I_mat - A)

    return Z, A, L, x, q, sign_corrected


def validate_io(Z, A, L, x, q, y, year: str, log: Logger = None) -> float:
    """Run IO integrity checks. Returns spectral radius ρ(A)."""
    subsection("Validation", log)
    check_conservation(x.sum(), (Z.sum(axis=0) + y).sum(), "Output balance", log=log)
    # PTA: x (demand-side) and q (supply-side) will differ by design (Eurostat §11.4).
    check_conservation(x.sum(), q.sum(), "Demand x vs supply q", tol_pct=200.0, log=log)
    check_matrix_properties(A, "A", log)
    check_matrix_properties(L, "L", log)
    rho = check_spectral_radius(A, f"A_{year}", log)

    bad_diag = (np.diag(L) < 1).sum()
    if bad_diag:
        warn(f"{bad_diag} diagonal L entries < 1 — review data", log)
    else:
        ok("All diagonal L ≥ 1", log)

    if (A.sum(axis=0) >= 1).any():
        warn(f"{(A.sum(axis=0)>=1).sum()} A column sums ≥ 1 — review cleaning step", log)
    else:
        ok("All A column sums < 1 (Hawkins-Simon satisfied)", log)
    return rho


def process_io_year(year_str: str, a_matrices: dict, log: Logger = None) -> dict:
    """Build IO table for one fiscal year. Returns summary dict."""
    section(f"Processing SUT → IO: {year_str}", log=log)
    scale = SUT_UNIT_TO_CRORE.get(year_str, 1.0)

    supply_path = DIRS["sut"] / f"supply-table-{year_str}.csv"
    use_path    = DIRS["sut"] / f"USE-TABLE-{year_str}.csv"
    for p in [supply_path, use_path]:
        if not p.exists():
            raise FileNotFoundError(f"Missing SUT file: {p}")

    products, V, _, ind_cols = read_sut(supply_path, scale, log)
    n = len(products)
    ok(f"Products: {n},  Industries: {len(ind_cols)},  Scale: ×{scale}", log)

    _, U, use_df, _ = read_sut(use_path, scale, log)
    if U.shape[0] != n:
        min_r = min(U.shape[0], n)
        warn(f"Row mismatch — trimming to {min_r}", log)
        U = U[:min_r]; V = V[:min_r]; products = products[:min_r]; n = min_r

    fd_cols = [c for c in use_df.columns if c in FINAL_DEMAND_COLS]
    y = use_df[fd_cols].iloc[:n].map(_to_float).values.sum(axis=1) * scale

    _FY_TO_SY  = {"2015-16": "2015", "2019-20": "2019", "2021-22": "2022"}
    _usd_rate  = USD_INR.get(_FY_TO_SY.get(year_str, year_str), 70.0)
    ok(f"Final demand: {fmt_crore_usd(y.sum(), _usd_rate)}  [{', '.join(fd_cols)}]", log)

    Z, A, L, x, q, sign_corrected = pta(V, U, y, products=products, log=log)
    ok(f"V total: {fmt_crore_usd(V.sum(), _usd_rate)} | Z: {fmt_crore_usd(Z.sum(), _usd_rate)} | x: {fmt_crore_usd(x.sum(), _usd_rate)}", log)

    rho = validate_io(Z, A, L, x, q, y, year_str, log)

    if a_matrices:
        prev_year = list(a_matrices.keys())[-1]
        if A.shape == a_matrices[prev_year].shape:
            check_a_stability(a_matrices[prev_year], A, prev_year, year_str,
                              products=products, log=log)
        else:
            warn(f"Cannot compare A matrices: shape mismatch "
                 f"({a_matrices[prev_year].shape} vs {A.shape})", log)
    a_matrices[year_str] = A

    top_n(pd.DataFrame({"Product": products, "Output": x}),
          "Output", "Product", n=10, unit=" cr", pct_base=x.sum(), log=log)

    tag     = year_str.replace("-", "_")
    out_dir = DIRS["io"] / year_str
    out_dir.mkdir(parents=True, exist_ok=True)

    for arr, name in [(Z, f"io_Z_{tag}"), (A, f"io_A_{tag}"), (L, f"io_L_{tag}")]:
        frame = pd.DataFrame(arr, index=products, columns=products)
        frame.index.name = "Product"
        save_csv(frame, out_dir / f"{name}.csv", name, log=log)

    deflator     = CPI[year_str] / CPI["2015-16"]
    _usd_base    = USD_INR.get("2015", 65.0)
    out_df = pd.DataFrame({
        "Product":                       products,
        "Total_Output_crore":            x,
        "Total_Output_USD_M":            x * 10.0 / _usd_rate,
        "Final_Demand_crore":            y,
        "Final_Demand_USD_M":            y * 10.0 / _usd_rate,
        "Supply_Output_crore":           q,
        "Supply_Output_USD_M":           q * 10.0 / _usd_rate,
        "Total_Output_2015prices":       x / deflator,
        "Total_Output_2015prices_USD_M": (x / deflator) * 10.0 / _usd_base,
        "Deflator":                      deflator,
        "USD_INR_Rate":                  _usd_rate,
        # FIX-3d: flag products whose output was negative in SUT and corrected via abs()
        "Output_Sign_Corrected":         sign_corrected.astype(int),
    })
    save_csv(out_df, out_dir / f"io_output_{tag}.csv", f"output {year_str}", log=log)

    prod_df = pd.DataFrame({"Product_ID": range(1, n + 1), "Product_Name": products})
    save_csv(prod_df, out_dir / f"io_products_{tag}.csv", f"products {year_str}", log=log)
    save_csv(prod_df, DIRS["io"] / "product_list.csv", "generic product list", log=log)

    x_max        = x.max()
    balance_err  = (100 * np.abs(x - (Z.sum(axis=0) + y)).max() / x_max if x_max > 0 else 0.0)
    return {
        "year":                          year_str,
        "n_products":                    n,
        "total_output_crore":            round(x.sum()),
        "total_output_USD_M":            round(crore_to_usd_m(x.sum(), _usd_rate), 1),
        "total_intermediate_crore":      round(Z.sum()),
        "total_intermediate_USD_M":      round(crore_to_usd_m(Z.sum(), _usd_rate), 1),
        "total_final_demand_crore":      round(y.sum()),
        "total_final_demand_USD_M":      round(crore_to_usd_m(y.sum(), _usd_rate), 1),
        "balance_error_pct":             round(balance_err, 4),
        "deflator":                      deflator,
        "total_output_2015prices":       round(x.sum() / deflator) if deflator > 0 else 0,
        "total_output_2015prices_USD_M": round(crore_to_usd_m(x.sum() / deflator, _usd_base), 1) if deflator > 0 else 0,
        "usd_inr_rate":                  _usd_rate,
        "spectral_radius":               round(rho, 6),
    }


def cross_year_io_summary(rows: list, log: Logger = None):
    section("Cross-Year IO Summary", log=log)
    df = pd.DataFrame(rows)
    compare_across_years(
        {r["year"]: r["total_output_2015prices"] for r in rows},
        "Real output (2015-16 ₹ crore)", unit=" cr", log=log,
    )
    header = (
        f"\n  {'Year':<12} {'Output (cr)':>16} {'Output ($M)':>12} "
        f"{'Intermediate':>16} {'FinalDemand':>16} {'FD ($M)':>10} "
        f"{'Bal.Err%':>10} {'ρ(A)':>10}\n  {'─'*100}"
    )
    lines = [header]
    for r in rows:
        lines.append(
            f"  {r['year']:<12} {r['total_output_crore']:>16,.0f} "
            f"{r.get('total_output_USD_M', 0):>12,.0f} "
            f"{r['total_intermediate_crore']:>16,.0f} "
            f"{r['total_final_demand_crore']:>16,.0f} "
            f"{r.get('total_final_demand_USD_M', 0):>10,.0f} "
            f"{r['balance_error_pct']:>10.3f} "
            f"{r['spectral_radius']:>10.6f}"
        )
    output = "\n".join(lines)
    if log:
        log._log(output)
    else:
        print(output)
    save_csv(df, DIRS["io"] / "io_summary_all_years.csv", "IO summary all years", log=log)


def run_io(years: list = None, **kwargs):
    """Entry point for step 'build_io'. Builds Leontief inverses for all years."""
    with Logger("build_io_tables", DIRS["logs"]) as log:
        t = Timer()
        log.section("BUILD IO TABLES (SUT → PTA → L)")

        if not years:
            years = [
                p.name[len("supply-table-"):-len(".csv")]
                for p in sorted(DIRS["sut"].glob("supply-table-*.csv"))
                if (DIRS["sut"] / f"USE-TABLE-{p.name[len('supply-table-'):-len('.csv')]}.csv").exists()
            ]
            if not years:
                log.fail(f"No SUT pairs found in {DIRS['sut']}")
                return

        log.ok(f"Years to process: {years}")
        summary    = []
        a_matrices = {}
        for yr in years:
            try:
                summary.append(process_io_year(yr, a_matrices, log))
            except Exception as e:
                log.fail(f"{yr}: {e}")

        if len(summary) > 1:
            cross_year_io_summary(summary, log)

        log.ok(f"Done in {t.elapsed()}")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — TOURISM DEMAND VECTORS  (was build_demand.py)
# ══════════════════════════════════════════════════════════════════════════════

_YEAR_TO_IO: dict = {yr: info["io_year"] for yr, info in YEARS.items()}
_BASE_YEAR:  str  = STUDY_YEARS[0]


def _cpi_mult(year: str) -> float:
    """CPI multiplier relative to 2015-16 base."""
    return CPI[_YEAR_TO_IO[year]] / CPI["2015-16"]


def _deflator(year: str) -> float:
    """Price deflator relative to 2015-16."""
    return CPI.get(_YEAR_TO_IO.get(year, "2015-16"), CPI["2015-16"]) / CPI["2015-16"]


def scale_tsa(log: Logger = None) -> pd.DataFrame:
    """
    Scale TSA 2015-16 base to each study year using NAS growth rates + CPI.

    Nominal factor = real_GVA_growth(sector, year) × CPI(year) / CPI(2015-16)

    Returns DataFrame: one row per TSA category, one column per year.
    """
    section("NAS Growth Rates & TSA Scaling", log=log)
    cpi_mults = {yr: _cpi_mult(yr) for yr in STUDY_YEARS}

    subsection("NAS GVA growth multipliers (constant 2011-12 prices)", log=log)
    ok("CPI multipliers vs 2015-16: " +
       "  ".join(f"{yr}={cpi_mults[yr]:.4f}" for yr in STUDY_YEARS), log)

    growth_rows = [
        [key, NAS_GVA_CONSTANT[key]["nas_sno"]] + [f"{rates.get(yr, 1.0):.4f}" for yr in STUDY_YEARS]
        for key, rates in NAS_GROWTH_RATES.items()
    ]
    hdrs = ["Sector key", "NAS S.No."] + [f"×{yr}" for yr in STUDY_YEARS]
    if log:
        log.table(hdrs, growth_rows)
    else:
        print(table_str(hdrs, growth_rows))

    base = pd.DataFrame(TSA_BASE, columns=["ID", "Category", "Category_Type",
                                            "Inbound_2015", "Domestic_2015"])
    base["Total_2015"] = base["Inbound_2015"] + base["Domestic_2015"]

    rows = []
    for _, r in base.iterrows():
        nas_key = TSA_TO_NAS.get(r["Category"], "Other_Mfg")
        row = {**r.to_dict(), "NAS_Sector": nas_key}
        for yr in STUDY_YEARS:
            real_g = NAS_GROWTH_RATES[nas_key].get(yr, 1.0)
            nom_g  = real_g * cpi_mults[yr]
            row[f"Real_G{yr[2:]}"]    = real_g
            row[f"Nominal_G{yr[2:]}"] = nom_g
            for seg in ("Inbound", "Domestic", "Total"):
                row[f"{seg}_{yr}"] = r[f"{seg}_2015"] * nom_g
        rows.append(row)

    df     = pd.DataFrame(rows)
    totals = {yr: df[f"Total_{yr}"].sum() for yr in STUDY_YEARS}
    compare_across_years(totals, "Total tourism spending (₹ crore nominal)", unit=" cr", log=log)

    usd_lines = ["  Total tourism spending (USD million equivalent):"]
    for yr in STUDY_YEARS:
        rate  = USD_INR.get(yr, 70.0)
        usd_m = crore_to_usd_m(totals[yr], rate)
        usd_lines.append(f"    {yr}: ${usd_m:,.0f}M  (@ ₹{rate:.2f}/USD)")
    msg = "\n".join(usd_lines)
    if log:
        log._emit(msg)
    else:
        print(msg)

    for i in range(1, len(STUDY_YEARS)):
        prev, curr = STUDY_YEARS[i - 1], STUDY_YEARS[i]
        n_yrs = int(curr) - int(prev)
        cagr  = 100 * ((totals[curr] / totals[prev]) ** (1 / n_yrs) - 1)
        ok(f"CAGR {prev}→{curr}: {cagr:.1f}%/yr", log)
        if abs(cagr) > 25:
            warn(f"CAGR {prev}→{curr} >25% — COVID impact likely; review NAS scaling", log)

    return df


def build_demand_vectors(tsa_df: pd.DataFrame, year: str,
                         demand_col: str = None,
                         log: Logger = None) -> tuple:
    """
    Build nominal and real 163-sector EXIOBASE demand vectors.

    Parameters
    ----------
    demand_col : column to use (default: Total_{year}).
                 Pass "Inbound_{year}" or "Domestic_{year}" for split vectors.

    Returns (Y_nominal, Y_real) — both shape (163,) in ₹ crore.
    """
    if demand_col is None:
        demand_col = f"Total_{year}"

    Y = np.zeros(163)
    for _, row in tsa_df.iterrows():
        demand = row[demand_col]
        if demand == 0:
            continue
        mappings = TSA_TO_EXIOBASE.get(row["Category"], [("IN.136", 1.0)])

        share_by_code: dict = {}
        for code, share in mappings:
            share_by_code[code] = share_by_code.get(code, 0) + share
        total_share = sum(share_by_code.values())

        for code, share in share_by_code.items():
            idx = EXIO_IDX.get(code)
            if idx is not None:
                Y[idx] += demand * (share / total_share)
            else:
                warn(f"EXIOBASE code '{code}' not in EXIO_IDX — check TSA_TO_EXIOBASE", log)

    deflator = _deflator(year)
    Y_real   = Y / deflator
    ok(f"Y_tourism {year} [{demand_col}]: ₹{Y.sum():,.0f} cr  "
       f"non-zero: {np.count_nonzero(Y)}/163  deflator: {deflator:.4f}  "
       f"real: ₹{Y_real.sum():,.0f} cr", log)
    return Y, Y_real


def _make_y_df(Y: np.ndarray) -> pd.DataFrame:
    """Convert 163-element demand array to labelled DataFrame."""
    return pd.DataFrame({
        "Sector_Index":         range(len(EXIO_CODES)),
        "Sector_Code":          EXIO_CODES,
        "Tourism_Demand_crore": Y,
    })


def run_demand(**kwargs):
    """Entry point for step 'demand'. Builds TSA-scaled EXIOBASE demand vectors."""
    log_dir = DIRS["logs"] / "tourism_demand"
    with Logger("build_tourism_demand", log_dir) as log:
        t = Timer()
        log.section("BUILD TOURISM DEMAND VECTORS (TSA → NAS-scaled → EXIOBASE Y)")

        tsa_df  = scale_tsa(log)
        tsa_out = DIRS["tsa"]
        tsa_out.mkdir(parents=True, exist_ok=True)
        save_csv(tsa_df, tsa_out / "tsa_all_years.csv", "TSA all years", log=log)

        demand_out = DIRS["demand"]
        demand_out.mkdir(parents=True, exist_ok=True)

        intensity_rows = []
        for year in STUDY_YEARS:
            log.subsection(f"Building demand vectors — {year}")
            total_col = f"Total_{year}"
            inb_col   = f"Inbound_{year}"
            dom_col   = f"Domestic_{year}"

            year_cols = [c for c in ["ID", "Category", "Category_Type",
                          inb_col, dom_col, total_col, "NAS_Sector",
                          f"Real_G{year[2:]}", f"Nominal_G{year[2:]}"]
                         if c in tsa_df.columns]
            save_csv(tsa_df[year_cols], tsa_out / f"tsa_scaled_{year}.csv",
                     f"TSA {year}", log=log)

            Y, Y_real = build_demand_vectors(tsa_df, year, demand_col=total_col, log=log)
            save_csv(_make_y_df(Y),      demand_out / f"Y_tourism_{year}.csv",      f"Y_tourism {year}",      log=log)
            save_csv(_make_y_df(Y_real), demand_out / f"Y_tourism_{year}_real.csv", f"Y_tourism {year} real", log=log)

            for col, suffix in [(inb_col, "inbound"), (dom_col, "domestic")]:
                if col in tsa_df.columns:
                    Y_split, _ = build_demand_vectors(tsa_df, year, demand_col=col, log=log)
                    save_csv(_make_y_df(Y_split),
                             demand_out / f"Y_tourism_{year}_{suffix}.csv",
                             f"Y_tourism {year} {suffix}", log=log)
                else:
                    warn(f"Column {col} not found — {suffix} split skipped for {year}", log)

            usd_rate = USD_INR.get(year, 70.0)
            intensity_rows.append({
                "Year":            year,
                "Nominal_crore":   Y.sum(),
                "Real_crore":      Y_real.sum(),
                "Nominal_USD_M":   round(crore_to_usd_m(Y.sum(), usd_rate), 1),
                "Real_USD_M":      round(crore_to_usd_m(Y_real.sum(), USD_INR.get(_BASE_YEAR, 65.0)), 1),
                "USD_INR_Rate":    usd_rate,
                "NonZero_Sectors": int(np.count_nonzero(Y)),
            })

        log.section("Tourism Demand Cross-Year Comparison")
        comparisons = [
            ("Tourism demand (₹ crore nominal)",          "Nominal_crore"),
            ("Tourism demand (₹ crore real 2015-16)",     "Real_crore"),
            ("Tourism demand (USD million nominal)",       "Nominal_USD_M"),
            ("Tourism demand (USD million real 2015-16)", "Real_USD_M"),
        ]
        df_list = [
            compare_across_years({r["Year"]: r[key] for r in intensity_rows}, label, log=log)
            for label, key in comparisons
        ]
        save_csv(pd.concat(df_list, ignore_index=True),
                 demand_out / "demand_intensity_comparison.csv",
                 "Demand comparison", log=log)

        log.ok(f"Done in {t.elapsed()}")


# ══════════════════════════════════════════════════════════════════════════════
# MASTER ENTRY POINT  (runs both sections in sequence)
# ══════════════════════════════════════════════════════════════════════════════

def run(years: list = None, **kwargs):
    """Run IO table construction then demand vector building."""
    run_io(years=years, **kwargs)
    run_demand(**kwargs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build IO tables and tourism demand vectors"
    )
    parser.add_argument("--io-only",     action="store_true", help="Run IO step only")
    parser.add_argument("--demand-only", action="store_true", help="Run demand step only")
    parser.add_argument("--years", nargs="*", help="IO years to process (default: auto-detect)")
    args = parser.parse_args()

    if args.io_only:
        run_io(years=args.years)
    elif args.demand_only:
        run_demand()
    else:
        run(years=args.years)
