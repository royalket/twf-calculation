"""
utils.py
========
Shared utilities: logging, IO helpers, validation, reporting, and the
reference-data Markdown parser.

Public API
----------
Logging
    Logger                      — dual stdout+file logger (context manager)
    section / subsection        — section headers
    ok / warn / fail            — status line helpers

File IO
    read_csv(path)              — read CSV, raise on missing
    read_csv_safe(path)         — read CSV, return empty DataFrame on missing
    save_csv(df, path, label)   — save DataFrame (index only if named)

Reference data
    load_reference_data(path)   — parse reference_data.md → dict of sections
                                  Called once by config.py at import time.
                                  All pipeline scripts get their data through
                                  config — they never call this directly.

Validation
    check_conservation          — scalar balance check with % tolerance
    check_matrix_properties     — shape / neg / diag summary
    check_spectral_radius       — Hawkins-Simon ρ(A) < 1
    check_a_stability           — cross-year A-matrix column-sum drift

Reporting
    compare_across_years        — cross-year table + DataFrame
    compare_sectors_across_years— sector-level wide pivot + % change
    year_comparison_table       — thin alias (backward compat)
    top_n                       — print top-N rows of a DataFrame

Misc
    numeric_cols                — coerce string columns to float
    Timer                       — elapsed-time helper
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


# ══════════════════════════════════════════════════════════════════════════════
# LOGGER
# ══════════════════════════════════════════════════════════════════════════════

class Logger:
    """
    Dual-output logger: every message goes to both terminal (stdout) and a
    timestamped log file, using Python's logging module.

    Usage (context manager — preferred):
        with Logger("step_name", log_dir) as log:
            log.ok("All good")
            log.warn("Something odd")
            log.section("Processing")
    """

    def __init__(self, name: str, log_dir: Path):
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        ts        = int(time.time())
        self.path = log_dir / f"{name}_{ts}.log"

        self._logger = logging.getLogger(f"twf.{name}.{ts}")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False

        fmt = logging.Formatter("%(message)s")

        fh = logging.FileHandler(self.path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)

        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(fmt)

        self._logger.addHandler(fh)
        self._logger.addHandler(ch)
        self._logger.info(f"# Log started: {datetime.now().isoformat()}")

    def _log(self, msg: str):
        self._logger.info(msg)

    def section(self, title: str, width: int = 70):
        self._log(f"\n{'='*width}\n  {title}\n{'='*width}")

    def subsection(self, title: str):
        self._log(f"\n  ── {title}")

    def ok(self, msg: str):
        self._log(f"  ✓ {msg}")

    def warn(self, msg: str):
        self._log(f"  ⚠ {msg}")

    def fail(self, msg: str):
        self._log(f"  ✗ {msg}")

    def info(self, msg: str):
        self._log(f"  {msg}")

    def close(self):
        for h in list(self._logger.handlers):
            h.close()
            self._logger.removeHandler(h)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            import traceback as _tb
            self._log(f"  ✗ Exception: {exc_val}")
            self._log(_tb.format_exc())
        self.close()
        return False  # do not suppress exceptions


def get_log_dir() -> Path:
    """Return logs/ relative to this file."""
    return Path(__file__).parent / "logs"


# ── Standalone print helpers (fall back to print when no Logger given) ────────

def section(title: str, width: int = 70, log: Logger = None):
    msg = f"\n{'='*width}\n  {title}\n{'='*width}"
    if log:
        log._log(msg)
    else:
        print(msg)


def subsection(title: str, log: Logger = None):
    msg = f"\n  ── {title}"
    if log:
        log._log(msg)
    else:
        print(msg)


def ok(msg: str, log: Logger = None):
    msg = f"  ✓ {msg}"
    if log:
        log._log(msg)
    else:
        print(msg)


def warn(msg: str, log: Logger = None):
    msg = f"  ⚠ {msg}"
    if log:
        log._log(msg)
    else:
        print(msg)


def fail(msg: str, log: Logger = None):
    msg = f"  ✗ {msg}"
    if log:
        log._log(msg)
    else:
        print(msg)


# ══════════════════════════════════════════════════════════════════════════════
# REFERENCE DATA MARKDOWN PARSER
# ══════════════════════════════════════════════════════════════════════════════

def load_reference_data(md_path: Path) -> dict:
    """
    Parse a structured reference_data.md file into a dict of sections.

    Expected file format
    --------------------
    ## SECTION: <SECTION_ID>

    <!-- meta
    key: value
    key: value
    -->

    | col1 | col2 | col3 |
    |------|------|------|
    | val  | val  | val  |

    Returns
    -------
    dict keyed by SECTION_ID, each value:
        {
            "_meta": {key: value, ...},         # from <!-- meta ... --> block
            "rows":  [{"col1": val, ...}, ...]   # one dict per data row
        }

    Rules
    -----
    - Section IDs are case-sensitive, taken verbatim after "## SECTION:"
    - Meta block is optional; if absent, "_meta" is {}
    - Separator rows (all dashes/colons like |---|) are skipped
    - Numbers auto-cast: int → float → str
    - Rows with wrong column count are padded/truncated to match header
    - Sections with no table rows return {"_meta": {...}, "rows": []}

    To add new data
    ---------------
    Add a new "## SECTION: <ID>" block to reference_data.md.
    No changes to this file are ever needed.
    """
    md_path = Path(md_path)
    if not md_path.exists():
        raise FileNotFoundError(
            f"Reference data file not found: {md_path}\n"
            "Ensure reference_data.md lives alongside config.py."
        )

    lines = md_path.read_text(encoding="utf-8").splitlines()

    result: dict      = {}
    current_id        = None
    current_meta: dict = {}
    current_rows: list = []
    header_cols: list  = None
    in_meta: bool      = False
    meta_lines: list   = []

    def _cast(v: str):
        v = v.strip()
        try:
            return int(v)
        except ValueError:
            pass
        try:
            return float(v)
        except ValueError:
            pass
        return v

    def _is_sep(cols: list) -> bool:
        return all(
            set(c.replace(":", "").replace("-", "").replace(" ", "")) <= {""}
            for c in cols
        )

    def _flush():
        if current_id is not None:
            result[current_id] = {"_meta": current_meta, "rows": current_rows}

    for line in lines:
        s = line.strip()

        # Section header
        if s.startswith("## SECTION:"):
            _flush()
            current_id   = s[len("## SECTION:"):].strip()
            current_meta = {}
            current_rows = []
            header_cols  = None
            in_meta      = False
            meta_lines   = []
            continue

        if current_id is None:
            continue

        # Meta open/close/body
        if s.startswith("<!-- meta"):
            in_meta    = True
            meta_lines = []
            continue
        if s == "-->" and in_meta:
            in_meta = False
            for ml in meta_lines:
                if ":" in ml:
                    k, _, v = ml.partition(":")
                    current_meta[k.strip()] = v.strip()
            continue
        if in_meta:
            meta_lines.append(s)
            continue

        # Table rows
        if not s.startswith("|"):
            continue

        cols = [c.strip() for c in s.strip("|").split("|")]
        if _is_sep(cols):
            continue

        if header_cols is None:
            header_cols = cols
            continue

        # Normalise width
        while len(cols) < len(header_cols):
            cols.append("")
        cols = cols[: len(header_cols)]

        current_rows.append({header_cols[i]: _cast(cols[i])
                              for i in range(len(header_cols))})

    _flush()
    return result


# ══════════════════════════════════════════════════════════════════════════════
# FILE IO
# ══════════════════════════════════════════════════════════════════════════════

def read_csv(path: Path, **kwargs) -> pd.DataFrame:
    """Read CSV; raise FileNotFoundError if missing."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return pd.read_csv(path, **kwargs)


def read_csv_safe(path: Path, **kwargs) -> pd.DataFrame:
    """Read CSV; return empty DataFrame if missing (non-fatal)."""
    path = Path(path)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, **kwargs)


def save_csv(df: pd.DataFrame, path: Path, label: str = "",
             log: Logger = None):
    """Save DataFrame to CSV. Writes index only when it carries a name."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=df.index.name is not None)
    ok(f"Saved {label or path.name}  ({len(df):,} rows)", log)


def numeric_cols(df: pd.DataFrame, cols) -> pd.DataFrame:
    """Coerce listed columns to float (handles comma-formatted strings)."""
    df = df.copy()
    for c in cols:
        df[c] = pd.to_numeric(
            df[c].astype(str).str.replace(",", "").str.strip(),
            errors="coerce",
        ).fillna(0)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def check_conservation(actual: float, expected: float, label: str,
                        tol_pct: float = 1.0, log: Logger = None):
    """Warn if |actual − expected| / expected > tol_pct %."""
    if expected == 0:
        warn(f"{label}: expected is zero, cannot compute relative error", log)
        return
    diff_pct = 100 * abs(actual - expected) / abs(expected)
    if diff_pct <= tol_pct:
        ok(f"{label}: {actual:,.0f} ≈ {expected:,.0f}  (Δ {diff_pct:.3f}% — PASS)", log)
    else:
        warn(f"{label}: {actual:,.0f} vs {expected:,.0f}  (Δ {diff_pct:.2f}% — CHECK)", log)


def check_matrix_properties(A: np.ndarray, name: str = "A",
                              log: Logger = None):
    neg       = (A < 0).sum()
    diag_mean = np.diag(A).mean() if A.shape[0] == A.shape[1] else None
    ok(
        f"{name}: shape={A.shape}, non-zero={np.count_nonzero(A)}, "
        f"max={A.max():.4f}, neg={neg}"
        + (f", diag_mean={diag_mean:.4f}" if diag_mean is not None else ""),
        log,
    )
    if neg > 0:
        warn(f"{name} has {neg} negative values — review SUT data", log)


def check_spectral_radius(A: np.ndarray, name: str = "A",
                           log: Logger = None) -> float:
    """
    Compute ρ(A) = max|eigenvalue|.
    ρ(A) < 1 → Hawkins-Simon condition holds.
    ρ(A) ≥ 1 → Leontief inverse may be unreliable.
    """
    rho = float(np.max(np.abs(np.linalg.eigvals(A))))
    if rho < 1.0:
        ok(f"Spectral radius ρ({name}) = {rho:.6f}  < 1  ✓ Hawkins-Simon holds", log)
    else:
        warn(f"Spectral radius ρ({name}) = {rho:.6f}  ≥ 1  ⚠ Economy may not be productive", log)
    return rho


def check_a_stability(A_base: np.ndarray, A_new: np.ndarray,
                       year_base: str, year_new: str,
                       threshold_pct: float = 30.0,
                       log: Logger = None):
    """Compare column sums of two A matrices. Changes > threshold_pct % are flagged."""
    col_base   = A_base.sum(axis=0)
    col_new    = A_new.sum(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        pct_change = np.where(col_base > 0,
                               100 * (col_new - col_base) / col_base,
                               np.nan)
    n_big = int(np.sum(np.abs(pct_change) > threshold_pct))
    subsection(f"A-matrix stability: {year_base} → {year_new}", log)
    ok(
        f"Column-sum Δ: mean={np.nanmean(np.abs(pct_change)):.1f}%  "
        f"max={np.nanmax(np.abs(pct_change)):.1f}%  "
        f"n_>{threshold_pct}%: {n_big}/{A_base.shape[1]}",
        log,
    )
    if n_big > 0:
        warn(f"{n_big} sectors shifted >{threshold_pct}% — review NAS scaling", log)
    else:
        ok(f"All column-sum changes ≤ {threshold_pct}% — A matrix stable", log)
    return pct_change


# ══════════════════════════════════════════════════════════════════════════════
# REPORTING
# ══════════════════════════════════════════════════════════════════════════════

def compare_across_years(data: dict, metric: str, years: list = None,
                          unit: str = "", decimals: int = 4,
                          log: Logger = None) -> pd.DataFrame:
    """
    Print a cross-year comparison table and return a DataFrame.

    Parameters
    ----------
    data     : {year_str: numeric_value}
    metric   : human-readable label
    years    : ordered year keys (default: sorted keys of data)
    unit     : display suffix e.g. " bn m³"
    decimals : decimal places
    log      : Logger (optional)

    Returns pd.DataFrame with:
        Year, Value, Absolute_Change, Pct_Change, CAGR_vs_base, Metric
    """
    if years is None:
        years = sorted(data.keys())

    rows     = []
    base_val = None
    base_yr  = None
    fmt      = f"{{:.{decimals}f}}"

    lines = [
        f"\n  {metric}",
        f"  {'Year':<8}  {'Value':>14}  {'Abs_Chg':>12}  {'Pct_Chg':>10}  {'CAGR':>12}",
        "  " + "─" * 62,
    ]

    for yr in years:
        val = data.get(yr, 0.0)
        if base_val is None:
            base_val = val
            base_yr  = yr
            lines.append(f"  {yr:<8}  {fmt.format(val):>14}{unit}  {'(base)':>12}")
            rows.append({"Year": yr, "Value": val,
                         "Absolute_Change": 0.0, "Pct_Change": 0.0,
                         "CAGR_vs_base": 0.0})
            continue

        abs_chg = val - base_val
        pct_chg = 100 * abs_chg / base_val if base_val else float("nan")
        try:
            n_yrs = int(yr[:4]) - int(base_yr[:4])
        except ValueError:
            n_yrs = 1
        cagr = (100 * ((val / base_val) ** (1 / n_yrs) - 1)
                if base_val > 0 and n_yrs > 0 else float("nan"))

        arrow = "↑" if abs_chg > 0 else "↓"
        lines.append(
            f"  {yr:<8}  {fmt.format(val):>14}{unit}  "
            f"{arrow}{abs(abs_chg):>10.{decimals}f}  "
            f"{pct_chg:>+9.1f}%  {cagr:>+9.1f}%/yr"
        )
        rows.append({"Year": yr, "Value": val,
                     "Absolute_Change": abs_chg,
                     "Pct_Change":      round(pct_chg, 3),
                     "CAGR_vs_base":    round(cagr, 3)})

    output = "\n".join(lines)
    if log:
        log._log(output)
    else:
        print(output)

    df = pd.DataFrame(rows)
    df["Metric"] = metric
    return df


def compare_sectors_across_years(year_dfs: dict, value_col: str,
                                   label_col: str, metric: str,
                                   n_top: int = 5,
                                   log: Logger = None) -> pd.DataFrame:
    """
    Build a wide sector×year table and print top movers.

    Parameters
    ----------
    year_dfs  : {year_str: pd.DataFrame} — each needs label_col + value_col
    value_col : numeric column  (e.g. "Total_Water_m3")
    label_col : label column    (e.g. "Category_Name")
    metric    : description for printing
    n_top     : number of top movers to print
    log       : Logger (optional)

    Returns wide DataFrame with Change_pct column (first → last year).
    """
    years = sorted(year_dfs.keys())
    if not years:
        return pd.DataFrame()

    wide = year_dfs[years[0]][[label_col, value_col]].copy().rename(
        columns={value_col: years[0]}
    )
    for yr in years[1:]:
        other = year_dfs[yr][[label_col, value_col]].rename(columns={value_col: yr})
        wide  = wide.merge(other, on=label_col, how="outer")

    wide       = wide.fillna(0)
    first_yr   = years[0]
    last_yr    = years[-1]

    with np.errstate(divide="ignore", invalid="ignore"):
        wide["Change_pct"] = np.where(
            wide[first_yr] != 0,
            100 * (wide[last_yr] - wide[first_yr]) / wide[first_yr],
            np.nan,
        )

    lines = [f"\n  {metric} — sector trends ({first_yr} → {last_yr})"]
    valid = wide.dropna(subset=["Change_pct"])
    if not valid.empty:
        lines.append(f"  Top {n_top} improved (fell most):")
        for _, r in valid.nsmallest(n_top, "Change_pct").iterrows():
            lines.append(f"    {str(r[label_col]):<42}  {r['Change_pct']:>+8.1f}%")
        lines.append(f"  Top {n_top} worsened (rose most):")
        for _, r in valid.nlargest(n_top, "Change_pct").iterrows():
            lines.append(f"    {str(r[label_col]):<42}  {r['Change_pct']:>+8.1f}%")

    output = "\n".join(lines)
    if log:
        log._log(output)
    else:
        print(output)

    return wide


def year_comparison_table(data: dict, metric: str, years: list,
                           unit: str = "", log: Logger = None):
    """Thin backward-compat wrapper for compare_across_years."""
    compare_across_years(data, metric, years, unit, log=log)


def top_n(df: pd.DataFrame, value_col: str, label_col: str,
          n: int = 10, unit: str = "", pct_base: float = None,
          log: Logger = None):
    top   = df.nlargest(n, value_col)
    lines = [
        f"\n  Top {n} by {value_col}:",
        f"  {'Rank':<5} {label_col:<45} {value_col:>18} {'%':>8}",
        "  " + "─" * 80,
    ]
    for rank, (_, row) in enumerate(top.iterrows(), 1):
        val     = row[value_col]
        pct_str = f"{100*val/pct_base:6.1f}%" if pct_base else ""
        lines.append(
            f"  {rank:<5} {str(row[label_col])[:44]:<45} "
            f"{val:>18,.0f}{unit} {pct_str:>8}"
        )
    output = "\n".join(lines)
    if log:
        log._log(output)
    else:
        print(output)


# ══════════════════════════════════════════════════════════════════════════════
# TIMER
# ══════════════════════════════════════════════════════════════════════════════

class Timer:
    def __init__(self):
        self.t = time.time()

    def elapsed(self) -> str:
        s = time.time() - self.t
        return f"{s:.1f}s" if s < 60 else f"{s/60:.1f}min"
