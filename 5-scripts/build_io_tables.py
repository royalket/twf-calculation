"""
Build product×product IO tables from Supply-Use Tables (SUT).

Method: Product Technology Assumption (PTA)
  D = V / q    market share matrix, products × industries
  Z = U @ D.T  intermediate flow matrix, products × products
  A = Z / x    technical coefficients
  L = (I-A)^-1 Leontief inverse

Example (illustrative, ₹ crore):
  Suppose SUT has 3 products: Agriculture (1), Food (2), Services (3)
  V (supply):
    [500  0   0 ]   Agriculture supplied by industry 1
    [ 0  300   0]   Food supplied by industry 2
    [ 0   0  400]   Services supplied by industry 3
  q (product gross output from supply) = [500, 300, 400]
  D = V / q = I  (identity for simple case: each industry makes one product)
  U (intermediate use):
    [100  50  20]   Agriculture used by industries 1,2,3
    [ 30  80  10]   Food used by industries 1,2,3
    [ 40  60 100]   Services used by industries 1,2,3
  Z = U @ D.T = U  (since D=I in this example)
  y (final demand) = [330, 180, 200]
  x = Z.sum(axis=0) + y = [500, 370, 330] ... (demand-side output estimate)
  A = Z / x  (column-normalised)
  L = (I - A)^-1  (Leontief inverse)

Supports: 2015-16, 2019-20, 2021-22 (auto-discovers from available SUT files)

Outputs per year (in io-table/{year}/):
  io_Z_{year}.csv      — intermediate flows (140×140)
  io_A_{year}.csv      — technical coefficients (140×140)
  io_L_{year}.csv      — Leontief inverse (140×140)
  io_output_{year}.csv — total output, final demand, deflated output
  io_products_{year}.csv — product list

Cross-year:
  io_summary_all_years.csv — output, balance error, real growth, spectral radii
"""

import time
import pandas as pd
import numpy as np
from pathlib import Path
import argparse
import sys

sys.path.insert(0, str(Path(__file__).parent))
from config import BASE_DIR, DIRS, SUT_UNIT_TO_CRORE, CPI, STUDY_YEARS
from utils import (
    section, subsection, ok, warn, fail, save_csv,
    check_conservation, check_matrix_properties,
    check_spectral_radius, check_a_stability,
    compare_across_years, top_n, Timer, Logger,
)


FINAL_DEMAND_COLS = ["PFCE", "GFCE", "GFCF", "CIS", "Valuables", "Export"]


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
    # FIX: applymap() was deprecated in pandas 2.1 and removed in 2.2+; use map()
    df = df.map(lambda v: v.strip() if isinstance(v, str) else v).replace("", 0)
    products = df[prod_col].astype(str).str.strip().tolist()
    ind_cols = df.columns[2:68].tolist()
    matrix = df[ind_cols].apply(pd.to_numeric, errors="coerce").fillna(0).values * unit_scale
    return products, matrix, df, ind_cols


def pta(V: np.ndarray, U: np.ndarray, y: np.ndarray):
    """
    Product Technology Assumption.

    q  = V.sum(axis=1)    product gross output from supply side
    D  = V / q            market share: D[i,j] = share of product i made by industry j
    Z  = U @ D.T          intermediate flows, products×products
    x  = Z.sum(axis=0)+y  total output from demand side
    A  = Z / x            technical coefficients
    L  = (I-A)^{-1}       Leontief inverse

    Returns: Z, A, L, x (demand-side), q (supply-side)
    """
    q = V.sum(axis=1)
    q_safe = np.where(q < 0.001, 1.0, q)
    D = V / q_safe[:, np.newaxis]
    Z = U @ D.T
    x = Z.sum(axis=0) + y
    x_safe = np.where(x < 0.001, 1.0, x)
    A = Z / x_safe[np.newaxis, :]
    I = np.eye(len(A))
    try:
        L = np.linalg.inv(I - A)
    except np.linalg.LinAlgError:
        warn("Singular I-A — using pseudo-inverse")
        L = np.linalg.pinv(I - A)
    return Z, A, L, x, q


def validate(Z, A, L, x, q, y, year, log: Logger = None):
    subsection("Validation", log)
    check_conservation(x.sum(), (Z.sum(axis=0) + y).sum(), "Output balance", log=log)
    check_conservation(x.sum(), q.sum(), "Demand-side x vs supply-side q", log=log)
    check_matrix_properties(A, "A", log)
    check_matrix_properties(L, "L", log)
    rho = check_spectral_radius(A, f"A_{year}", log)

    bad_diag = (np.diag(L) < 1).sum()
    if bad_diag:
        warn(f"{bad_diag} diagonal L entries < 1 — review data", log)
    else:
        ok("All diagonal L ≥ 1", log)

    col_sums = A.sum(axis=0)
    if (col_sums >= 1).any():
        warn(f"{(col_sums>=1).sum()} A column sums ≥ 1 — economy may be infeasible", log)
    else:
        ok("All A column sums < 1 (Hawkins-Simon satisfied)", log)
    return rho


def process_year(year_str: str, a_matrices: dict, log: Logger = None) -> dict:
    section(f"Processing SUT → IO: {year_str}", log=log)
    scale = SUT_UNIT_TO_CRORE.get(year_str, 1.0)
    sut_dir = DIRS["sut"]

    supply_path = sut_dir / f"supply-table-{year_str}.csv"
    use_path    = sut_dir / f"USE-TABLE-{year_str}.csv"
    for p in [supply_path, use_path]:
        if not p.exists():
            raise FileNotFoundError(f"Missing SUT file: {p}")

    products, V, supply_df, ind_cols = read_sut(supply_path, scale, log)
    n = len(products)
    ok(f"Products: {n},  Industries: {len(ind_cols)},  Scale: ×{scale}", log)

    _, U, use_df, _ = read_sut(use_path, scale, log)
    if U.shape[0] != n:
        min_r = min(U.shape[0], n)
        warn(f"Row mismatch — trimming to {min_r}", log)
        U = U[:min_r]; V = V[:min_r]; products = products[:min_r]; n = min_r

    fd_cols = [c for c in use_df.columns if c in FINAL_DEMAND_COLS]
    Y_mat = use_df[fd_cols].iloc[:n].apply(pd.to_numeric, errors="coerce").fillna(0).values * scale
    y = Y_mat.sum(axis=1)
    ok(f"Final demand: ₹{y.sum():,.0f} crore  [{', '.join(fd_cols)}]", log)

    Z, A, L, x, q = pta(V, U, y)
    ok(f"V total: ₹{V.sum():,.0f} cr | Z: ₹{Z.sum():,.0f} cr | x: ₹{x.sum():,.0f} cr", log)

    rho = validate(Z, A, L, x, q, y, year_str, log)

    # A-matrix stability check against previous year
    if a_matrices:
        prev_year = list(a_matrices.keys())[-1]
        if A.shape == a_matrices[prev_year].shape:
            check_a_stability(a_matrices[prev_year], A, prev_year, year_str, log=log)
        else:
            warn(
                f"Cannot compare A matrices: shape mismatch "
                f"({a_matrices[prev_year].shape} vs {A.shape})",
                log,
            )
    a_matrices[year_str] = A

    top_n(
        pd.DataFrame({"Product": products, "Output": x}),
        "Output", "Product", n=10, unit=" cr", pct_base=x.sum(), log=log,
    )

    tag = year_str.replace("-", "_")
    out_dir = DIRS["io"] / year_str
    out_dir.mkdir(parents=True, exist_ok=True)

    def save(arr, name, idx=None, cols=None):
        frame = pd.DataFrame(arr, index=idx, columns=cols)
        if idx is not None:
            frame.index.name = "Product"   # gives the index a name so save_csv writes it
        save_csv(frame, out_dir / f"{name}.csv", name, log=log)

    save(Z, f"io_Z_{tag}", idx=products, cols=products)
    save(A, f"io_A_{tag}", idx=products, cols=products)
    save(L, f"io_L_{tag}", idx=products, cols=products)

    deflator = CPI[year_str] / CPI["2015-16"]
    out_df = pd.DataFrame({
        "Product":                  products,
        "Total_Output_crore":       x,
        "Final_Demand_crore":       y,
        "Supply_Output_crore":      q,
        "Total_Output_2015prices":  x / deflator,
        "Deflator":                 deflator,
    })
    save_csv(out_df, out_dir / f"io_output_{tag}.csv", f"output {year_str}", log=log)

    prod_df = pd.DataFrame({"Product_ID": range(1, n+1), "Product_Name": products})
    save_csv(prod_df, out_dir / f"io_products_{tag}.csv", f"products {year_str}", log=log)
    save_csv(prod_df, DIRS["io"] / "product_list.csv", "generic product list", log=log)

    balance_err = 100 * np.abs(x - (Z.sum(axis=0) + y)).max() / x.max()
    return {
        "year":                       year_str,
        "n_products":                 n,
        "total_output_crore":         round(x.sum()),
        "total_intermediate_crore":   round(Z.sum()),
        "total_final_demand_crore":   round(y.sum()),
        "balance_error_pct":          round(balance_err, 4),
        "deflator":                   deflator,
        "total_output_2015prices":    round(x.sum() / deflator),
        "spectral_radius":            round(rho, 6),
    }


def cross_year_summary(rows: list, log: Logger = None):
    section("Cross-Year IO Summary", log=log)
    df = pd.DataFrame(rows)

    real_output = {r["year"]: r["total_output_2015prices"] for r in rows}
    compare_across_years(real_output, "Real output (2015-16 ₹ crore)", unit=" cr", log=log)

    header = (
        f"\n  {'Year':<12} {'Output (cr)':>16} {'Intermediate':>16} "
        f"{'FinalDemand':>16} {'Bal.Err%':>10} {'ρ(A)':>10}\n"
        f"  {'─'*82}"
    )
    lines = [header]
    for r in rows:
        lines.append(
            f"  {r['year']:<12} {r['total_output_crore']:>16,.0f} "
            f"{r['total_intermediate_crore']:>16,.0f} "
            f"{r['total_final_demand_crore']:>16,.0f} "
            f"{r['balance_error_pct']:>10.3f} "
            f"{r['spectral_radius']:>10.6f}"
        )
    output = "\n".join(lines)
    if log:
        log._log(output)
    else:
        print(output)

    save_csv(df, DIRS["io"] / "io_summary_all_years.csv", "IO summary all years", log=log)


def run(years: list = None):
    with Logger("build_io_tables", DIRS["logs"]) as log:
        t = Timer()
        log.section("BUILD IO TABLES (SUT → PTA → L)")

        if not years:
            years = []
            for p in sorted(DIRS["sut"].glob("supply-table-*.csv")):
                yr = p.name[len("supply-table-"):-len(".csv")]
                if (DIRS["sut"] / f"USE-TABLE-{yr}.csv").exists():
                    years.append(yr)
            if not years:
                log.fail(f"No SUT pairs found in {DIRS['sut']}")
                return

        log.ok(f"Years to process: {years}")
        summary = []
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", nargs="*")
    args = parser.parse_args()
    run(args.years)