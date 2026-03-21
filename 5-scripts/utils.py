"""
utils.py  —  India Tourism Water + Energy Footprint Pipeline
=============================================================
Shared utilities: logging, file I/O, validation, reporting, formatting, and
the reference-data Markdown parser.

Public API
----------
Logging
    Logger                      — dual stdout+file logger (context manager)
    section / subsection        — section-header helpers
    ok / warn / fail / info     — status-line helpers (Logger-aware)

Formatting
    fmt_value(val, stressor)    — universal formatter (m³ or MJ, auto-scale)
    fmt_m3(val)                 — water volume formatter
    fmt_mj(val)                 — energy formatter
    fmt_crore_usd(crore, rate)  — ₹X,XXX cr ($Y.YM)
    crore_to_usd_m(crore, rate) — ₹ crore → USD million
    table_str(headers, rows)    — ASCII table → str

File I/O
    read_csv / safe_csv         — required vs optional CSV reads
    save_csv                    — save DataFrame + log

Reference data
    load_reference_data(path)   — parse reference_data.md → dict
    pivot_transposed(rows, key) — pivot field×year tables

Validation
    check_conservation          — scalar balance check
    check_matrix_properties     — shape / neg / diagonal summary
    check_spectral_radius       — Hawkins-Simon ρ(A) < 1
    check_a_stability           — cross-year A-matrix drift

Reporting
    compare_across_years        — cross-year table + DataFrame
    compare_sectors_across_years— sector-level wide pivot
    top_n                       — print top-N rows of a DataFrame

Misc
    Timer / ProgressBar         — timing helpers
    safe_divide                 — zero-safe division
    sensitivity_half_range_pct  — ±% of BASE
    six_polar_sda               — 6-polar SDA decomposition
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
    Dual-output logger: stdout + timestamped .log file.
    Tracks warnings/errors for a WARNINGS.md summary.

    Usage (context manager — preferred):
        with Logger("step_name", log_dir) as log:
            log.ok("All good")
            log.warn("Something odd")
            log.table(["Col1", "Col2"], [[1, 2]])
    """

    _ICONS = {"ok": "✓", "warn": "⚠", "fail": "✗", "info": " "}

    def __init__(self, name: str, log_dir: Path):
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = log_dir / f"{name}_{ts}.log"
        self.name = name
        self._warnings: list[str] = []
        self._errors:   list[str] = []
        self._t0 = time.time()

        self._logger = logging.getLogger(f"twf.{name}.{ts}")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False
        fmt = logging.Formatter("%(message)s")
        for handler in (logging.FileHandler(self.path, encoding="utf-8"),
                        logging.StreamHandler(sys.stdout)):
            handler.setFormatter(fmt)
            self._logger.addHandler(handler)

        self._emit(f"{'═'*70}\n  Log started : {datetime.now():%Y-%m-%d %H:%M:%S}"
                   f"\n  Step        : {name}\n  Log file    : {self.path}\n{'═'*70}")

    # ── core emit ─────────────────────────────────────────────────────────────

    def _emit(self, msg: str):
        self._logger.info(msg)

    # Backwards-compatible alias used across older modules
    def _log(self, msg: str):
        self._emit(msg)

    # ── typed emitters ────────────────────────────────────────────────────────

    def section(self, title: str, width: int = 70):
        self._emit(f"\n{'═'*width}\n  {title}\n{'═'*width}")

    def subsection(self, title: str):
        self._emit(f"\n  ── {title} ──")

    def ok(self, msg: str):
        self._emit(f"  ✓  {msg}")

    def warn(self, msg: str):
        self._emit(f"  ⚠  {msg}")
        self._warnings.append(msg)

    def fail(self, msg: str):
        self._emit(f"  ✗  {msg}")
        self._errors.append(msg)

    def info(self, msg: str):
        self._emit(f"     {msg}")

    def kv(self, key: str, val, width: int = 28):
        self._emit(f"     {key:<{width}}: {val}")

    def table(self, headers: list, rows: list, indent: int = 4):
        self._emit(table_str(headers, rows, indent=indent))

    def divider(self, char: str = "─", width: int = 70):
        self._emit(f"  {char * width}")

    # ── summary ───────────────────────────────────────────────────────────────

    def write_warnings_summary(self):
        if not self._warnings and not self._errors:
            return
        warn_path = Path(self.path).parent / "WARNINGS.md"
        lines = [f"\n## {self.name}  ({datetime.now():%Y-%m-%d %H:%M})\n"]
        lines += [f"- ⚠  {w}" for w in self._warnings]
        lines += [f"- ✗  {e}" for e in self._errors]
        with open(warn_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def close(self):
        elapsed = Timer._fmt(time.time() - self._t0)
        self._emit(f"\n{'─'*70}\n  Step '{self.name}' finished  |  elapsed: {elapsed}"
                   f"\n  Warnings: {len(self._warnings)}  |  Errors: {len(self._errors)}")
        for w in self._warnings:
            self._emit(f"    ⚠  {w}")
        self.write_warnings_summary()
        for h in list(self._logger.handlers):
            h.close()
            self._logger.removeHandler(h)

    @property
    def warning_count(self) -> int:
        return len(self._warnings)

    @property
    def error_count(self) -> int:
        return len(self._errors)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            import traceback as _tb
            self.fail(f"Exception: {exc_val}")
            self._emit(_tb.format_exc())
        self.close()
        return False


# ── Standalone helpers (use Logger when available, else print) ────────────────

def _emit(msg: str, log: Logger | None):
    if log:
        log._emit(msg)
    else:
        print(msg)

def section(title: str, width: int = 70, log: Logger | None = None):
    _emit(f"\n{'═'*width}\n  {title}\n{'═'*width}", log)

def subsection(title: str, log: Logger | None = None):
    _emit(f"\n  ── {title} ──", log)

def ok(msg: str, log: Logger | None = None):
    _emit(f"  ✓  {msg}", log)

def warn(msg: str, log: Logger | None = None):
    _emit(f"  ⚠  {msg}", log)
    if log and hasattr(log, "_warnings"):
        log._warnings.append(msg)

def fail(msg: str, log: Logger | None = None):
    _emit(f"  ✗  {msg}", log)

def info(msg: str, log: Logger | None = None):
    _emit(f"     {msg}", log)


# ══════════════════════════════════════════════════════════════════════════════
# FORMATTING
# ══════════════════════════════════════════════════════════════════════════════

def fmt_m3(val: float) -> str:
    """Smart formatter for water volumes: auto-selects m³ / M m³ / bn m³."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "—"
    if val >= 1e9:
        return f"{val/1e9:.3f} bn m³"
    if val >= 1e6:
        return f"{val/1e6:.1f} M m³"
    return f"{val:,.0f} m³"


def fmt_mj(val: float) -> str:
    """Smart formatter for energy: auto-selects MJ / GJ / TJ / PJ."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "—"
    if abs(val) >= 1e12:
        return f"{val/1e12:.3f} PJ"
    if abs(val) >= 1e9:
        return f"{val/1e9:.3f} TJ"
    if abs(val) >= 1e6:
        return f"{val/1e6:.1f} GJ"
    return f"{val:,.0f} MJ"


def fmt_value(val: float, stressor: str) -> str:
    """Universal formatter — dispatches to fmt_m3 or fmt_mj by stressor."""
    return fmt_m3(val) if stressor == "water" else fmt_mj(val)


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Division that returns `default` on zero denominator."""
    try:
        return numerator / denominator if denominator != 0 else default
    except (TypeError, ZeroDivisionError):
        return default


def crore_to_usd_m(crore: float, rate: float) -> float:
    """₹ crore → USD million.  1 crore = 10 M INR → USD M = crore × 10 / rate"""
    return crore * 10.0 / rate


def fmt_crore_usd(crore: float, rate: float) -> str:
    """Format ₹ crore with USD equivalent: '₹50,000 cr  ($714.3M / $0.71B)'"""
    usd_m = crore_to_usd_m(crore, rate)
    return f"₹{crore:,.0f} cr  (${usd_m:,.1f}M / ${usd_m/1000:.2f}B)"


def table_str(headers: list, rows: list, indent: int = 4) -> str:
    """Render a plain-text ASCII table."""
    pad = " " * indent
    str_rows = [[str(c) for c in r] for r in rows]
    widths = [
        max(len(str(h)), *(len(r[i]) for r in str_rows) if str_rows else [0])
        for i, h in enumerate(headers)
    ]
    sep  = pad + "  ".join("─" * w for w in widths)
    head = pad + "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
    body = [pad + "  ".join(c.ljust(widths[j]) for j, c in enumerate(r)) for r in str_rows]
    return "\n".join(["", head, sep, *body, ""])


def sensitivity_half_range_pct(low: float, base: float, high: float) -> float:
    """Symmetric sensitivity range as ±% of BASE: (HIGH - LOW) / |BASE| / 2 × 100"""
    return 100.0 * (high - low) / abs(base) / 2.0 if base != 0 else 0.0


def fmt_sens_range(low: float, base: float, high: float) -> str:
    """Format sensitivity as '±X.X%' string."""
    return f"±{sensitivity_half_range_pct(low, base, high):.1f}%" if base != 0 else "—"


def enrich_df(df: pd.DataFrame, value_col: str,
              add_total: bool = False, label_col: str = "Country") -> pd.DataFrame:
    """Add Share_pct column (value / sum × 100). Optionally append a TOTAL row."""
    df = df.copy()
    total_val = df[value_col].sum()
    df["Share_pct"] = (df[value_col] / total_val * 100).round(2) if total_val else 0.0
    if add_total and not df.empty:
        total_row = {c: "" for c in df.columns}
        total_row[label_col] = "TOTAL"
        total_row[value_col] = total_val
        total_row["Share_pct"] = 100.0
        df = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)
    return df


def add_total_row(df: pd.DataFrame, label_col: str = "Year") -> pd.DataFrame:
    """Append a TOTAL row summing all numeric columns."""
    num_cols = df.select_dtypes(include="number").columns.tolist()
    total_row = {c: df[c].sum() if c in num_cols else ("TOTAL" if c == label_col else "")
                 for c in df.columns}
    return pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)


def numeric_cols(df: pd.DataFrame, cols) -> pd.DataFrame:
    """Coerce listed columns to float (handles comma-formatted strings)."""
    df = df.copy()
    for c in cols:
        df[c] = pd.to_numeric(
            df[c].astype(str).str.replace(",", "").str.strip(), errors="coerce"
        ).fillna(0)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# PROGRESS BAR & TIMER
# ══════════════════════════════════════════════════════════════════════════════

class ProgressBar:
    """
    Simple ASCII progress bar for long loops (e.g. Monte Carlo simulations).

    Usage:
        with ProgressBar(total=10_000, label="Monte Carlo", log=log) as pb:
            for i in range(total):
                pb.update()
    """

    def __init__(self, total: int, label: str = "", width: int = 40,
                 log: Logger | None = None):
        self.total = total
        self.label = label
        self.width = width
        self.log   = log
        self._n    = 0
        self._t0   = time.time()
        self._last = -1

    def update(self, n: int = 1):
        self._n += n
        pct = int(100 * self._n / self.total)
        if pct == self._last or pct % 10 != 0:
            return
        self._last = pct
        filled  = int(self.width * self._n / self.total)
        bar     = "█" * filled + "░" * (self.width - filled)
        elapsed = time.time() - self._t0
        eta     = (elapsed / self._n * (self.total - self._n)) if self._n else 0
        _emit(f"  [{bar}] {pct:3d}%  {self._n:,}/{self.total:,}  ETA {eta:.0f}s", self.log)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        ok(f"{self.label}: {self.total:,} iterations in {time.time() - self._t0:.1f}s", self.log)


class Timer:
    def __init__(self):
        self.t = time.time()

    @staticmethod
    def _fmt(s: float) -> str:
        return f"{s:.1f}s" if s < 60 else f"{s/60:.1f}min"

    def elapsed(self) -> str:
        return self._fmt(time.time() - self.t)

    def lap(self, label: str = "", log: Logger | None = None) -> float:
        s = time.time() - self.t
        ok(f"{label + ': ' if label else ''}{self._fmt(s)}", log)
        self.t = time.time()
        return s


# ══════════════════════════════════════════════════════════════════════════════
# REFERENCE DATA MARKDOWN PARSER
# ══════════════════════════════════════════════════════════════════════════════

def load_reference_data(md_path: Path) -> dict:
    """
    Parse structured reference_data.md into a dict of sections.

    Expected format:
        ## SECTION: <SECTION_ID>
        <!-- meta  key: value  -->
        | col1 | col2 |
        |------|------|
        | val  | val  |

    Returns {SECTION_ID: {"_meta": {k: v}, "rows": [{col: val, ...}]}}
    """
    md_path = Path(md_path)
    if not md_path.exists():
        raise FileNotFoundError(f"Reference data not found: {md_path}")

    def _cast(v: str):
        v = v.strip()
        for conv in (int, float):
            try:
                return conv(v)
            except ValueError:
                pass
        return v

    def _is_sep(cols: list) -> bool:
        return all(set(c.replace(":", "").replace("-", "").replace(" ", "")) <= {""} for c in cols)

    lines = md_path.read_text(encoding="utf-8").splitlines()
    result, current_id, current_meta, current_rows = {}, None, {}, []
    header_cols, in_meta, meta_lines = None, False, []

    def _flush():
        if current_id is not None:
            result[current_id] = {"_meta": current_meta, "rows": current_rows}

    for line in lines:
        s = line.strip()
        if s.startswith("## SECTION:"):
            _flush()
            current_id, current_meta, current_rows = s[len("## SECTION:"):].strip(), {}, []
            header_cols, in_meta, meta_lines = None, False, []
            continue
        if current_id is None:
            continue
        if s.startswith("<!-- meta"):
            in_meta = True; meta_lines = []; continue
        if s == "-->" and in_meta:
            in_meta = False
            for ml in meta_lines:
                if ":" in ml:
                    k, _, v = ml.partition(":")
                    current_meta[k.strip()] = v.strip()
            continue
        if in_meta:
            meta_lines.append(s); continue
        if not s.startswith("|"):
            continue
        cols = [c.strip() for c in s.strip("|").split("|")]
        if _is_sep(cols):
            continue
        if header_cols is None:
            header_cols = cols; continue
        cols = (cols + [""] * len(header_cols))[: len(header_cols)]
        current_rows.append({header_cols[i]: _cast(cols[i]) for i in range(len(header_cols))})

    _flush()
    return result


def pivot_transposed(rows: list, key_col: str) -> dict:
    """Pivot a transposed table (rows=fields, cols=years) into {year: {field: value}}."""
    if not rows:
        return {}
    year_cols = [k for k in rows[0] if k != key_col and str(k).isdigit()]
    out = {str(y): {} for y in year_cols}
    for row in rows:
        field = str(row[key_col])
        for yr in year_cols:
            out[str(yr)][field] = float(row[yr])
    return out


# ══════════════════════════════════════════════════════════════════════════════
# FILE I/O
# ══════════════════════════════════════════════════════════════════════════════

def read_csv(path: Path, required: bool = True, **kwargs) -> pd.DataFrame:
    """Read CSV; raise FileNotFoundError if required=True and missing."""
    path = Path(path)
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Required file not found: {path}")
        return pd.DataFrame()
    return pd.read_csv(path, **kwargs)


def safe_csv(path, **kwargs) -> pd.DataFrame:
    """Read CSV without raising. Returns empty DataFrame on any error."""
    try:
        p = Path(path)
        return pd.read_csv(p, **kwargs) if p.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def save_csv(df: pd.DataFrame, path: Path, label: str = "",
             log: Logger | None = None):
    """Save DataFrame to CSV with logging. Silently skips when df is None."""
    if df is None:
        warn(f"save_csv: skipping '{label or path}' — DataFrame is None", log)
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=df.index.name is not None)
    ok(f"Saved {label or path.name}  ({len(df):,} rows → {path.name})", log)


# ══════════════════════════════════════════════════════════════════════════════
# SENSITIVITY HELPERS
# ══════════════════════════════════════════════════════════════════════════════

# fmt_sens_range and sensitivity_half_range_pct defined above in FORMATTING.


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE-GROUP CLASSIFICATION  (shared WSI lookup)
# ══════════════════════════════════════════════════════════════════════════════

def classify_source_group(product_id: int) -> str:
    """
    Classify a 1-indexed SUT product_id into its upstream source group.
    Based on India 140-sector SUT product list (NAS 2025 edition).

    Group boundaries (product_id):
      1  – 29   Agriculture
      30 – 40   Mining
      41 – 113  Manufacturing  (71–80 = Petroleum, separate sub-group)
      114 – 116 Electricity + Water supply
      117 – 140 Services

    THIS IS THE SINGLE SOURCE OF TRUTH for group boundaries.
    All other files must import and call this function — never define
    their own boundary ranges or group-name strings.
    """
    pid = int(product_id)
    if 1   <= pid <= 29:  return "Agriculture"
    if 30  <= pid <= 40:  return "Mining"
    if 71  <= pid <= 80:  return "Petroleum"
    if 41  <= pid <= 113: return "Manufacturing"
    if 114 <= pid <= 116: return "Electricity"
    return "Services"


# ── Canonical group taxonomy ──────────────────────────────────────────────────
# Ordered list matching classify_source_group() output exactly.
# Import SOURCE_GROUPS from here wherever a list of group names is needed —
# never define the list locally in individual scripts.
SOURCE_GROUPS: list[str] = [
    "Agriculture",
    "Mining",
    "Petroleum",
    "Manufacturing",
    "Electricity",
    "Services",
]

# Product-ID ranges for each group (inclusive, 1-indexed, matching above).
# Use these for sensitivity lambdas and MC masks instead of hardcoding ranges.
SOURCE_GROUP_RANGES: dict[str, tuple[int, int] | list[tuple[int, int]]] = {
    "Agriculture":  [(1,  29)],
    "Mining":       [(30, 40)],
    "Petroleum":    [(71, 80)],
    "Manufacturing":[(41, 70), (81, 113)],   # excl. Petroleum 71-80
    "Electricity":  [(114, 116)],
    "Services":     [(117, 140)],
}

# Alias sets for tolerant matching of legacy strings produced by
# build_coefficients.py ("Energy Processing", "Utilities/Energy") or
# any other code that writes non-canonical group names into CSVs.
# Usage:  canonical = SOURCE_GROUP_ALIASES.get(raw.lower(), raw)
SOURCE_GROUP_ALIASES: dict[str, str] = {
    # Electricity aliases
    "electricity":       "Electricity",
    "utilities/energy":  "Electricity",
    "energy processing": "Electricity",
    "utilities":         "Electricity",
    "util":              "Electricity",
    "power":             "Electricity",
    # Agriculture aliases
    "agriculture":       "Agriculture",
    "agr":               "Agriculture",
    "crops":             "Agriculture",
    # Mining aliases
    "mining":            "Mining",
    "min":               "Mining",
    # Petroleum aliases
    "petroleum":         "Petroleum",
    "petrol":            "Petroleum",
    "oil":               "Petroleum",
    # Manufacturing aliases
    "manufacturing":     "Manufacturing",
    "manuf":             "Manufacturing",
    # Services aliases
    "services":          "Services",
    "service":           "Services",
}


def canonical_source_group(raw: str) -> str:
    """
    Map any raw/legacy group label to the canonical SOURCE_GROUPS name.
    Falls back to the original string if no alias is found.
    Use this whenever reading Source_Group from a CSV that may have been
    written by build_coefficients.py or older pipeline versions.
    """
    return SOURCE_GROUP_ALIASES.get(str(raw).strip().lower(), str(raw).strip())


# Sector-decomp label sets used by indirect.py build_sector_decomp().
# Defined here so indirect.py, compare.py and visualise.py all share them.
# Keys are lowercase canonical names for .str.lower().isin() matching.
SRC_DECOMP_AGR_LABELS:   frozenset[str] = frozenset({"agriculture"})
SRC_DECOMP_ELEC_LABELS:  frozenset[str] = frozenset({
    "electricity", "utilities/energy", "energy processing", "utilities"
})
SRC_DECOMP_PETRO_LABELS: frozenset[str] = frozenset({
    "petroleum", "mining"
    # NOTE: "energy processing" deliberately removed — it was in both ELEC
    # and PETRO causing double-counting. "Energy Processing" maps to Electricity
    # via SOURCE_GROUP_ALIASES; Mining is canonical and stands alone here.
})


# ══════════════════════════════════════════════════════════════════════════════
# WATER COLUMN FINDERS
# ══════════════════════════════════════════════════════════════════════════════

def find_blue_water_col(df: pd.DataFrame, year: str = None) -> str | None:
    """Find the blue water coefficient column. Never returns a Green column."""
    cols = df.columns.tolist()
    if year:
        yr_blue = [c for c in cols if f"Water_{year}_Blue" in c and "crore" in c.lower()]
        if yr_blue:
            return yr_blue[0]
    any_blue = [c for c in cols if "Blue" in c and "crore" in c.lower()]
    if any_blue:
        return any_blue[0]
    fallback = [c for c in cols if "Water" in c and "crore" in c.lower() and "Green" not in c]
    return fallback[0] if fallback else None


def find_green_water_col(df: pd.DataFrame, year: str = None) -> str | None:
    """Find the green water coefficient column. Returns None if absent."""
    cols = df.columns.tolist()
    if year:
        yr_green = [c for c in cols if f"Water_{year}_Green" in c and "crore" in c.lower()]
        if yr_green:
            return yr_green[0]
    return next((c for c in cols if "Green" in c and "crore" in c.lower()), None)


# ══════════════════════════════════════════════════════════════════════════════
# ROW / VALUE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def year_row(df: pd.DataFrame, year, year_col: str = "Year") -> pd.Series | None:
    """Return the first row matching year in year_col, or None."""
    if df is None or df.empty or year_col not in df.columns:
        return None
    matches = df[df[year_col].astype(str) == str(year)]
    return matches.iloc[0] if not matches.empty else None


def col_val(row: pd.Series | None, *keys, default: float = 0.0) -> float:
    """Extract the first matching key from a pandas Series. Returns default on miss."""
    if row is None:
        return default
    for k in keys:
        if k in row.index:
            try:
                return float(row[k])
            except (TypeError, ValueError):
                pass
    return default


# ══════════════════════════════════════════════════════════════════════════════
# SIX-POLAR STRUCTURAL DECOMPOSITION ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def six_polar_sda(
    W0: np.ndarray, L0: np.ndarray, Y0: np.ndarray,
    W1: np.ndarray, L1: np.ndarray, Y1: np.ndarray,
) -> dict:
    """
    Six-permutation (exhaustive) SDA for a 3-factor model: TWF = W · L · Y.

    Averages all 3! = 6 orderings. Residual ≈ 0 by construction.

    Reference: Dietzenbacher & Los (1998). Economic Systems Research, 10(4).
    """
    from itertools import permutations

    def _twf(w, l, y):
        # Accept either a diagonal matrix `w` (n×n) or a 1-D intensity vector.
        # Compute w^T (L y) → scalar. This avoids calling float() on an array.
        wy = l @ y
        if isinstance(w, np.ndarray) and w.ndim == 2 and w.shape[0] == w.shape[1]:
            w_vec = np.diag(w)
        else:
            w_vec = np.asarray(w).ravel()
        return float(np.dot(w_vec, wy))

    base, year1 = [W0, L0, Y0], [W1, L1, Y1]
    names = ["W", "L", "Y"]
    effects: dict = {"W": [], "L": [], "Y": []}

    for order in permutations([0, 1, 2]):
        state = list(base)
        prev  = _twf(*state)
        for idx in order:
            state[idx] = year1[idx]
            nxt = _twf(*state)
            effects[names[idx]].append(nxt - prev)
            prev = nxt

    W_eff = sum(effects["W"]) / 6.0
    L_eff = sum(effects["L"]) / 6.0
    Y_eff = sum(effects["Y"]) / 6.0
    TWF0  = _twf(W0, L0, Y0)
    TWF1  = _twf(W1, L1, Y1)
    dTWF  = TWF1 - TWF0
    residual = dTWF - (W_eff + L_eff + Y_eff)

    max_eff     = max(abs(W_eff), abs(L_eff), abs(Y_eff))
    near_cancel = bool(abs(dTWF) > 0 and max_eff > 5 * abs(dTWF))
    inst_ratio  = round(max_eff / abs(dTWF), 1) if abs(dTWF) > 1e-9 else float("inf")

    def _pct(v):
        return round(100 * v / abs(dTWF), 3) if abs(dTWF) > 1e-9 else 0.0

    return {
        "TWF0_m3": TWF0, "TWF1_m3": TWF1, "dTWF_m3": dTWF,
        "W_effect_m3": W_eff, "L_effect_m3": L_eff, "Y_effect_m3": Y_eff,
        "Sum_effects_m3": W_eff + L_eff + Y_eff,
        "Residual_m3": residual,
        "W_effect_pct": _pct(W_eff), "L_effect_pct": _pct(L_eff), "Y_effect_pct": _pct(Y_eff),
        "Residual_pct": _pct(residual),
        "Near_cancellation": near_cancel,
        "Instability_ratio": inst_ratio,
        "SDA_Method": "six_polar",
    }


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def check_conservation(actual: float, expected: float, label: str,
                        tol_pct: float = 1.0, log: Logger | None = None):
    """Warn if |actual − expected| / expected > tol_pct %."""
    if expected == 0:
        warn(f"{label}: expected is zero, cannot compute relative error", log)
        return
    diff_pct = 100 * abs(actual - expected) / abs(expected)
    msg = f"{label}: {actual:,.0f} ≈ {expected:,.0f}  (Δ {diff_pct:.3f}% — {'PASS' if diff_pct <= tol_pct else 'CHECK'})"
    (ok if diff_pct <= tol_pct else warn)(msg, log)


def check_matrix_properties(A: np.ndarray, name: str = "A", log: Logger | None = None):
    neg       = (A < 0).sum()
    diag_mean = np.diag(A).mean() if A.shape[0] == A.shape[1] else None
    ok(f"{name}: shape={A.shape}  non-zero={np.count_nonzero(A):,}  "
       f"max={A.max():.4f}  neg={neg}"
       + (f"  diag_mean={diag_mean:.4f}" if diag_mean is not None else ""), log)
    if neg > 0:
        warn(f"{name} has {neg} negative values — review SUT data", log)


def check_spectral_radius(A: np.ndarray, name: str = "A",
                           log: Logger | None = None) -> float:
    """ρ(A) < 1 → Hawkins-Simon condition holds."""
    rho = float(np.max(np.abs(np.linalg.eigvals(A))))
    msg = f"Spectral radius ρ({name}) = {rho:.6f}"
    (ok if rho < 1.0 else warn)(
        f"{msg}  {'< 1  ✓ Hawkins-Simon holds' if rho < 1.0 else '≥ 1  ⚠ Economy may not be productive'}",
        log,
    )
    return rho


def check_a_stability(A_base: np.ndarray, A_new: np.ndarray,
                       year_base: str, year_new: str,
                       threshold_pct: float = 30.0,
                       products: list = None,
                       log: Logger | None = None):
    """Compare column sums of two A matrices. Changes > threshold_pct % are flagged."""
    col_base = A_base.sum(axis=0)
    col_new  = A_new.sum(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        pct_change = np.where(col_base > 0,
                               100 * (col_new - col_base) / col_base, np.nan)
    n_big = int(np.sum(np.abs(pct_change) > threshold_pct))
    subsection(f"A-matrix stability: {year_base} → {year_new}", log)
    ok(f"Column-sum Δ: mean={np.nanmean(np.abs(pct_change)):.1f}%  "
       f"max={np.nanmax(np.abs(pct_change)):.1f}%  n_>{threshold_pct}%: {n_big}/{A_base.shape[1]}", log)
    if n_big > 0:
        warn(f"{n_big} sectors shifted >{threshold_pct}% — review NAS scaling", log)
        for i in np.where(np.abs(pct_change) > threshold_pct)[0]:
            name = products[i] if products and i < len(products) else f"col_{i+1}"
            warn(f"    [{i+1:>3}] {name[:45]:<45}  Δ={pct_change[i]:+.1f}%", log)
    else:
        ok(f"All column-sum changes ≤ {threshold_pct}% — A matrix stable", log)
    return pct_change


# ══════════════════════════════════════════════════════════════════════════════
# REPORTING
# ══════════════════════════════════════════════════════════════════════════════

def compare_across_years(data: dict, metric: str, years: list = None,
                          unit: str = "", decimals: int = 4,
                          log: Logger | None = None) -> pd.DataFrame:
    """
    Print a cross-year comparison table and return a DataFrame.
    Columns: Year, Value, Absolute_Change, Pct_Change, CAGR_vs_base, Metric
    """
    if years is None:
        years = sorted(data.keys())

    rows, base_val, base_yr = [], None, None
    fmt = f"{{:.{decimals}f}}"
    lines = [
        f"\n  {metric}",
        f"  {'Year':<8}  {'Value':>14}  {'Abs_Chg':>12}  {'Pct_Chg':>10}  {'CAGR':>12}",
        "  " + "─" * 62,
    ]

    for yr in years:
        val = data.get(yr, 0.0)
        if base_val is None:
            base_val, base_yr = val, yr
            lines.append(f"  {yr:<8}  {fmt.format(val):>14}{unit}  {'(base)':>12}")
            rows.append({"Year": yr, "Value": val, "Absolute_Change": 0.0,
                         "Pct_Change": 0.0, "CAGR_vs_base": 0.0})
            continue

        abs_chg = val - base_val
        pct_chg = 100 * abs_chg / base_val if base_val else float("nan")
        try:
            n_yrs = int(yr[:4]) - int(base_yr[:4])
        except ValueError:
            n_yrs = 1

        if base_val > 0 and val > 0 and n_yrs > 0:
            cagr = 100 * ((val / base_val) ** (1 / n_yrs) - 1)
        elif base_val < 0 and val < 0 and n_yrs > 0:
            cagr = 100 * ((val / base_val) ** (1 / n_yrs) - 1)
        else:
            cagr = float("nan")

        arrow    = "↑" if abs_chg > 0 else "↓"
        cagr_str = f"{cagr:>+9.1f}%/yr" if cagr == cagr else "  sign-cross"  # NaN check
        lines.append(
            f"  {yr:<8}  {fmt.format(val):>14}{unit}  "
            f"{arrow}{abs(abs_chg):>10.{decimals}f}  "
            f"{pct_chg:>+9.1f}%  {cagr_str}"
        )
        rows.append({"Year": yr, "Value": val, "Absolute_Change": abs_chg,
                     "Pct_Change": round(pct_chg, 3), "CAGR_vs_base": round(cagr, 3)})

    _emit("\n".join(lines), log)
    df = pd.DataFrame(rows)
    df["Metric"] = metric
    return df


def compare_sectors_across_years(year_dfs: dict, value_col: str, label_col: str,
                                   metric: str, n_top: int = 5,
                                   log: Logger | None = None) -> pd.DataFrame:
    """Build a wide sector×year table and print top movers."""
    years = sorted(year_dfs.keys())
    if not years:
        return pd.DataFrame()

    wide = year_dfs[years[0]][[label_col, value_col]].rename(columns={value_col: years[0]})
    for yr in years[1:]:
        wide = wide.merge(
            year_dfs[yr][[label_col, value_col]].rename(columns={value_col: yr}),
            on=label_col, how="outer",
        )
    wide = wide.fillna(0)
    first_yr, last_yr = years[0], years[-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        wide["Change_pct"] = np.where(
            wide[first_yr] != 0,
            100 * (wide[last_yr] - wide[first_yr]) / wide[first_yr],
            np.nan,
        )

    lines = [f"\n  {metric} — sector trends ({first_yr} → {last_yr})"]
    valid = wide.dropna(subset=["Change_pct"])
    if not valid.empty:
        for label, fn in [(f"Top {n_top} improved (fell most):", "nsmallest"),
                          (f"Top {n_top} worsened (rose most):", "nlargest")]:
            lines.append(f"  {label}")
            for _, r in getattr(valid, fn)(n_top, "Change_pct").iterrows():
                lines.append(f"    {str(r[label_col]):<42}  {r['Change_pct']:>+8.1f}%")
    _emit("\n".join(lines), log)
    return wide


def top_n(df: pd.DataFrame, value_col: str, label_col: str,
          n: int = 10, unit: str = "", pct_base: float = None,
          log: Logger | None = None):
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
    _emit("\n".join(lines), log)
