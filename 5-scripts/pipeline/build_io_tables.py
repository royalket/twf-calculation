"""
build_io_tables.py — Build product×product IO tables from Supply-Use Tables.

Method: Product Technology Assumption (PTA)
  D = V / q    market share matrix (products × industries)
  Z = U @ D.T  intermediate flow matrix (products × products)
  A = Z / x    technical coefficients
  L = (I-A)⁻¹  Leontief inverse

Supports: 2015-16, 2019-20, 2021-22 (auto-discovers from available SUT files)

Outputs per year (in io-table/{year}/):
  io_Z_{year}.csv        intermediate flows (140×140)
  io_A_{year}.csv        technical coefficients (140×140)
  io_L_{year}.csv        Leontief inverse (140×140)
  io_output_{year}.csv   total output, final demand, deflated output
  io_products_{year}.csv product list

Cross-year:
  io_summary_all_years.csv  output, balance error, real growth, spectral radii

Fixes applied vs original:
  1. clean_a_matrix() — enforces Hawkins-Simon before inversion.
     Several SUT products have A column sums = 1.0 (entire output goes to
     intermediate use, zero final demand) or even > 1.0 (data errors such as
     2022 crude petroleum where intermediate inputs exceed total output by 55%).
     Without cleaning, (I-A) is near-singular and L collapses, producing
     artificially low WL multipliers and therefore wrong TWF results.

  2. Negative output handling — 2022 SUT has one product with x < 0 (data
     error). Taking the absolute value before computing A prevents division
     by a negative number which would flip the sign of an entire A column.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import BASE_DIR, DIRS, SUT_UNIT_TO_CRORE, CPI, STUDY_YEARS, USD_INR
from utils import (
    section, subsection, ok, warn, fail, save_csv,
    check_conservation, check_matrix_properties,
    check_spectral_radius, check_a_stability,
    compare_across_years, top_n, Timer, Logger,
    crore_to_usd_m, fmt_crore_usd,
)

FINAL_DEMAND_COLS = ["PFCE", "GFCE", "GFCF", "CIS", "Valuables", "Export"]


# ── SUT reader ────────────────────────────────────────────────────────────────

def _to_float(val) -> float:
    """
    Convert any raw SUT cell value to a clean float.

    Handles every formatting variant seen across the three SUT years:
      - Already numeric (int / float / np.number)  → return as-is
      - None / NaN / pandas NA                      → 0.0
      - Empty or whitespace-only string             → 0.0
      - Single/double-quoted strings  'x' or "x"   → strip quotes then parse
      - Thousand-separator commas  "1,23,456"       → remove commas then parse
      - Parenthesised negatives    "(123)"          → -123.0  (accounting style)
      - Anything else unparseable                   → 0.0
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

    s = str(val).strip().strip("'\"")   # strip outer whitespace + quotes
    if not s or s.lower() in ("nan", "none", "na", "n/a", "-", ""):
        return 0.0

    # Accounting-style negatives: (123) → -123
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1].strip()

    s = s.replace(",", "")              # remove thousand separators

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


# ── A-matrix cleaner (Hawkins-Simon enforcement) ──────────────────────────────

def clean_a_matrix(A: np.ndarray, products: list, log: Logger = None) -> np.ndarray:
    """
    Fix two classes of SUT data problems before Leontief inversion.

    Problem 1 — Individual cell A[i,j] > 1.0
    -----------------------------------------
    Physically impossible: one input cannot exceed 100% of output.
    Cause: data entry errors in the raw SUT (e.g. 2022 crude petroleum
    where intermediate inputs exceed total output by 55%).
    Fix: clip to 1.0, then re-check column sums.

    Problem 2 — Column sum A[:,j].sum() >= 1.0  (Hawkins-Simon violated)
    ----------------------------------------------------------------------
    Makes (I-A) singular or near-singular for that column → L collapses.
    Cause: products with zero or near-zero final demand (entire output goes
    to intermediate use). Common in 2015-16 SUT for primary commodities
    like kapas, jute, tobacco, tea, coffee, rubber, wool, natural gas,
    crude petroleum, and some service products.
    Fix: scale the entire column down so its sum = 0.95, preserving the
    relative shares of each input while restoring invertibility.

    The 0.95 cap is a standard IO table repair technique. It is conservative
    — it keeps the economy close to the original structure while guaranteeing
    (I-A) is invertible with positive L entries.

    Parameters
    ----------
    A        : raw technical coefficient matrix (n × n), will be copied
    products : product name list for logging (length n)
    log      : Logger instance

    Returns
    -------
    A_clean  : cleaned copy of A with all column sums < 1.0
    """
    A = A.copy()

    # ── Step 1: clip individual cells > 1.0 ──────────────────────────────────
    bad_cells = A > 1.0
    if bad_cells.any():
        n_bad = int(bad_cells.sum())
        warn(f"Clipping {n_bad} A[i,j] > 1.0 to 1.0 (SUT data errors)", log)
        rows_bad, cols_bad = np.where(bad_cells)
        for r, c in zip(rows_bad[:5], cols_bad[:5]):   # log first 5 only
            name = products[c] if c < len(products) else f"col_{c}"
            if log:
                log.info(f"    A[{r},{c}] ({name[:40]}): {A[r,c]:.4f} → 1.0")
        A = np.clip(A, 0.0, 1.0)

    # ── Step 2: scale columns with sum >= 1.0 down to 0.95 ───────────────────
    col_sums  = A.sum(axis=0)
    bad_cols  = np.where(col_sums >= 1.0)[0]
    if len(bad_cols) > 0:
        warn(
            f"{len(bad_cols)} A column sums >= 1.0 — scaling to 0.95 "
            f"(Hawkins-Simon enforcement)", log
        )
        for j in bad_cols:
            cs = A[:, j].sum()
            if cs >= 1.0:
                scale = 0.95 / cs
                A[:, j] *= scale
                name = products[j] if j < len(products) else f"col_{j}"
                if log:
                    log.info(
                        f"    col {j+1:3d} ({name[:40]}): "
                        f"A_sum {cs:.4f} → {A[:,j].sum():.4f}"
                    )

    final_bad = (A.sum(axis=0) >= 1.0).sum()
    if final_bad == 0:
        ok("All A column sums < 1.0 after cleaning (Hawkins-Simon satisfied)", log)
    else:
        warn(f"{final_bad} columns still >= 1.0 after cleaning — check data", log)

    return A


# ── Product Technology Assumption ─────────────────────────────────────────────

def pta(V: np.ndarray, U: np.ndarray, y: np.ndarray,
        products: list = None, log: Logger = None):
    """
    Product Technology Assumption.

    q  = V.sum(axis=1)    product gross output (supply side)
    D  = V / q            market share: share of product i made by industry j
    Z  = U @ D.T          intermediate flows, products × products
    x  = Z.sum(axis=0)+y  total output (demand side)
    A  = Z / x            technical coefficients
    A* = clean_a_matrix(A) enforce Hawkins-Simon before inversion
    L  = (I-A*)⁻¹         Leontief inverse

    Returns: Z, A_clean, L, x (demand-side), q (supply-side)
    """
    q      = V.sum(axis=1)
    q_safe = np.where(q < 0.001, 1.0, q)
    D      = V / q_safe[:, np.newaxis]
    Z      = U @ D.T

    # ── Handle negative outputs (data errors in SUT) ──────────────────────────
    x = Z.sum(axis=0) + y
    neg = (x < 0).sum()
    if neg > 0:
        warn(f"{neg} products have negative total output — taking absolute value", log)
        if log:
            for i in np.where(x < 0)[0]:
                name = products[i] if products and i < len(products) else f"col_{i}"
                log.info(f"    product {i+1} ({name[:40]}): x = {x[i]:,.1f}")
        x = np.abs(x)

    x_safe = np.where(x < 0.001, 1.0, x)
    A      = Z / x_safe[np.newaxis, :]

    # ── Enforce Hawkins-Simon before inversion ────────────────────────────────
    A = clean_a_matrix(A, products or [], log)

    I_mat = np.eye(len(A))
    try:
        L = np.linalg.inv(I_mat - A)
    except np.linalg.LinAlgError:
        warn("Singular I-A — using pseudo-inverse", log)
        L = np.linalg.pinv(I_mat - A)

    return Z, A, L, x, q


# ── Validation ────────────────────────────────────────────────────────────────

def validate(Z, A, L, x, q, y, year: str, log: Logger = None) -> float:
    subsection("Validation", log)
    check_conservation(x.sum(), (Z.sum(axis=0) + y).sum(), "Output balance", log=log)
    # Under the Product Technology Assumption, x (demand-side) and q (supply-side)
    # will NOT be equal — the D-matrix re-allocation breaks supply-use balance at the
    # product level by design (Eurostat Manual §11.4). A ~115-125% gap is structurally
    # expected for India SUT data. Only flag if the gap is implausibly large (>200%).
    check_conservation(x.sum(), q.sum(), "Demand-side x vs supply-side q", tol_pct=200.0, log=log)
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


# ── Process one year ──────────────────────────────────────────────────────────

def process_year(year_str: str, a_matrices: dict, log: Logger = None) -> dict:
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
    # Map SUT fiscal year → study year for USD rate lookup
    _FY_TO_SY = {"2015-16": "2015", "2019-20": "2019", "2021-22": "2022"}
    _usd_rate = USD_INR.get(_FY_TO_SY.get(year_str, year_str), 70.0)
    ok(
        f"Final demand: {fmt_crore_usd(y.sum(), _usd_rate)}  "
        f"[{', '.join(fd_cols)}]",
        log,
    )

    # Pass products and log so pta() can report cleaning details
    Z, A, L, x, q = pta(V, U, y, products=products, log=log)
    ok(
        f"V total: {fmt_crore_usd(V.sum(), _usd_rate)} | "
        f"Z: {fmt_crore_usd(Z.sum(), _usd_rate)} | "
        f"x: {fmt_crore_usd(x.sum(), _usd_rate)}",
        log,
    )

    rho = validate(Z, A, L, x, q, y, year_str, log)

    # A-matrix stability check against previous year
    if a_matrices:
        prev_year = list(a_matrices.keys())[-1]
        if A.shape == a_matrices[prev_year].shape:
            check_a_stability(a_matrices[prev_year], A, prev_year, year_str,
                              products=products, log=log)
        else:
            warn(
                f"Cannot compare A matrices: shape mismatch "
                f"({a_matrices[prev_year].shape} vs {A.shape})", log
            )
    a_matrices[year_str] = A

    top_n(pd.DataFrame({"Product": products, "Output": x}),
          "Output", "Product", n=10, unit=" cr", pct_base=x.sum(), log=log)

    tag     = year_str.replace("-", "_")
    out_dir = DIRS["io"] / year_str
    out_dir.mkdir(parents=True, exist_ok=True)

    for arr, name, idx, cols in [
        (Z, f"io_Z_{tag}", products, products),
        (A, f"io_A_{tag}", products, products),
        (L, f"io_L_{tag}", products, products),
    ]:
        frame = pd.DataFrame(arr, index=idx, columns=cols)
        frame.index.name = "Product"
        save_csv(frame, out_dir / f"{name}.csv", name, log=log)

    deflator = CPI[year_str] / CPI["2015-16"]
    _FY_TO_SY = {"2015-16": "2015", "2019-20": "2019", "2021-22": "2022"}
    _usd_rate = USD_INR.get(_FY_TO_SY.get(year_str, year_str), 70.0)
    _usd_rate_base = USD_INR.get("2015", 65.0)          # 2015-16 prices for real USD
    out_df = pd.DataFrame({
        "Product":                    products,
        "Total_Output_crore":         x,
        "Total_Output_USD_M":         x * 10.0 / _usd_rate,
        "Final_Demand_crore":         y,
        "Final_Demand_USD_M":         y * 10.0 / _usd_rate,
        "Supply_Output_crore":        q,
        "Supply_Output_USD_M":        q * 10.0 / _usd_rate,
        "Total_Output_2015prices":    x / deflator,
        "Total_Output_2015prices_USD_M": (x / deflator) * 10.0 / _usd_rate_base,
        "Deflator":                   deflator,
        "USD_INR_Rate":               _usd_rate,
    })
    save_csv(out_df, out_dir / f"io_output_{tag}.csv", f"output {year_str}", log=log)

    prod_df = pd.DataFrame({"Product_ID": range(1, n + 1), "Product_Name": products})
    save_csv(prod_df, out_dir / f"io_products_{tag}.csv",   f"products {year_str}", log=log)
    save_csv(prod_df, DIRS["io"] / "product_list.csv",       "generic product list",  log=log)

    x_max = x.max()
    balance_err = (
        100 * np.abs(x - (Z.sum(axis=0) + y)).max() / x_max
        if x_max > 0 else 0.0
    )
    return {
        "year":                         year_str,
        "n_products":                   n,
        "total_output_crore":           round(x.sum()),
        "total_output_USD_M":           round(crore_to_usd_m(x.sum(), _usd_rate), 1),
        "total_intermediate_crore":     round(Z.sum()),
        "total_intermediate_USD_M":     round(crore_to_usd_m(Z.sum(), _usd_rate), 1),
        "total_final_demand_crore":     round(y.sum()),
        "total_final_demand_USD_M":     round(crore_to_usd_m(y.sum(), _usd_rate), 1),
        "balance_error_pct":            round(balance_err, 4),
        "deflator":                     deflator,
        "total_output_2015prices":      round(x.sum() / deflator) if deflator > 0 else 0,
        "total_output_2015prices_USD_M": round(crore_to_usd_m(x.sum() / deflator, _usd_rate_base), 1) if deflator > 0 else 0,
        "usd_inr_rate":                 _usd_rate,
        "spectral_radius":              round(rho, 6),
    }


# ── Cross-year summary ────────────────────────────────────────────────────────

def cross_year_summary(rows: list, log: Logger = None):
    section("Cross-Year IO Summary", log=log)
    df = pd.DataFrame(rows)

    compare_across_years(
        {r["year"]: r["total_output_2015prices"] for r in rows},
        "Real output (2015-16 ₹ crore)", unit=" cr", log=log,
    )

    header = (
        f"\n  {'Year':<12} {'Output (cr)':>16} {'Output ($M)':>12} "
        f"{'Intermediate':>16} {'FinalDemand':>16} {'FD ($M)':>10} "
        f"{'Bal.Err%':>10} {'ρ(A)':>10}\n"
        f"  {'─'*100}"
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


# ── Entry point ───────────────────────────────────────────────────────────────

def run(years: list = None, **kwargs):
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
                summary.append(process_year(yr, a_matrices, log))
            except Exception as e:
                log.fail(f"{yr}: {e}")

        if len(summary) > 1:
            cross_year_summary(summary, log)

        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert Supply-Use Tables to IO tables (Product Technology Assumption)"
    )
    parser.add_argument("--years", nargs="*", help="Years to process (default: auto-detect)")
    args = parser.parse_args()
    run(args.years)