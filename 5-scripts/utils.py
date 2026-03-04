"""
utils.py  —  India Tourism Water Footprint Pipeline
====================================================
Shared utilities: logging, file I/O, validation, reporting, formatting, and
the reference-data Markdown parser.

Public API
----------
Logging
    Logger                      — dual stdout+file logger (context manager)
    section / subsection        — section-header helpers
    ok / warn / fail / info     — status-line helpers

Formatting
    fmt_m3(val)                 — smart m³ formatter (m³ / M m³ / bn m³)
    fmt_crore_usd(crore, rate)  — ₹X,XXX cr ($Y.YM / $Y.YB)
    crore_to_usd_m(crore, rate) — ₹ crore → USD million
    table_str(headers, rows)    — ASCII table → str

File I/O
    read_csv(path, required)    — read CSV; raise or return empty on missing
    save_csv(df, path, label)   — save DataFrame + log

Reference data
    load_reference_data(path)   — parse reference_data.md → dict of sections
    pivot_transposed(rows, key) — pivot field×year tables into {year: {field: val}}

Validation
    check_conservation          — scalar balance check with % tolerance
    check_matrix_properties     — shape / neg / diagonal summary
    check_spectral_radius       — Hawkins-Simon ρ(A) < 1
    check_a_stability           — cross-year A-matrix column-sum drift

Reporting
    compare_across_years        — cross-year table + DataFrame
    compare_sectors_across_years— sector-level wide pivot + % change
    top_n                       — print top-N rows of a DataFrame
    numeric_cols                — coerce string columns to float

Misc
    Timer                       — elapsed-time helper
    ProgressBar                 — simple ASCII progress bar for long loops
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
    Dual-output logger: messages go to both stdout and a timestamped .log file.
    Tracks warnings/errors for per-run WARNINGS.md summary.

    Usage (context manager — preferred):
        with Logger("step_name", log_dir) as log:
            log.ok("All good")
            log.warn("Something odd")
            log.section("Processing")
            log.table(["Col1","Col2"], [[1,2],[3,4]])
    """

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
        fh  = logging.FileHandler(self.path, encoding="utf-8")
        fh.setFormatter(fmt)
        ch  = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        self._logger.addHandler(fh)
        self._logger.addHandler(ch)

        self._log("═" * 70)
        self._log(f"  Log started : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self._log(f"  Step        : {name}")
        self._log(f"  Log file    : {self.path}")
        self._log("═" * 70)

    # ── core emit ─────────────────────────────────────────────────────────────

    def _log(self, msg: str):
        self._logger.info(msg)

    # ── typed emitters ────────────────────────────────────────────────────────

    def section(self, title: str, width: int = 70):
        self._log(f"\n{'═'*width}\n  {title}\n{'═'*width}")

    def subsection(self, title: str):
        self._log(f"\n  ── {title} ──")

    def ok(self, msg: str):
        self._log(f"  ✓  {msg}")

    def warn(self, msg: str):
        self._log(f"  ⚠  {msg}")
        self._warnings.append(msg)

    def fail(self, msg: str):
        self._log(f"  ✗  {msg}")
        self._errors.append(msg)

    def info(self, msg: str):
        self._log(f"     {msg}")

    def kv(self, key: str, val, width: int = 28):
        """Log a key-value pair with aligned columns."""
        self._log(f"     {key:<{width}}: {val}")

    def table(self, headers: list, rows: list, indent: int = 4):
        """Print a formatted ASCII table into the log."""
        self._log(table_str(headers, rows, indent=indent))

    def divider(self, char: str = "─", width: int = 70):
        self._log(f"  {char * width}")

    # ── summary writers ───────────────────────────────────────────────────────

    def write_warnings_summary(self):
        """Append WARNINGS.md in the log dir with this step's issues."""
        if not self._warnings and not self._errors:
            return
        warn_path = Path(self.path).parent / "WARNINGS.md"
        lines = [f"\n## {self.name}  ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n"]
        for w in self._warnings:
            lines.append(f"- ⚠  {w}")
        for e in self._errors:
            lines.append(f"- ✗  {e}")
        with open(warn_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def close(self):
        elapsed = Timer._fmt(time.time() - self._t0)
        self._log(f"\n{'─'*70}")
        self._log(f"  Step '{self.name}' finished  |  elapsed: {elapsed}")
        self._log(f"  Warnings: {len(self._warnings)}  |  Errors: {len(self._errors)}")
        if self._warnings:
            for w in self._warnings:
                self._log(f"    ⚠  {w}")
        self.write_warnings_summary()
        for h in list(self._logger.handlers):
            h.close()
            self._logger.removeHandler(h)

    @property
    def warning_count(self) -> int:
        """Number of warnings emitted so far in this step."""
        return len(self._warnings)

    @property
    def error_count(self) -> int:
        """Number of errors emitted so far in this step."""
        return len(self._errors)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            import traceback as _tb
            self.fail(f"Exception: {exc_val}")
            self._log(_tb.format_exc())
        self.close()
        return False


# ── Standalone helpers (use Logger when available, else print) ────────────────

def _emit(msg: str, log: Logger | None):
    if log:
        log._log(msg)
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


def crore_to_usd_m(crore: float, rate: float) -> float:
    """
    Convert ₹ crore → USD million.
    1 crore = 10,000,000 INR → USD M = crore × 10 / rate
    """
    return crore * 10.0 / rate


def fmt_crore_usd(crore: float, rate: float) -> str:
    """
    Format ₹ crore with USD equivalent.
    e.g. '₹50,000 cr  ($714.3M / $0.71B)'
    """
    usd_m = crore_to_usd_m(crore, rate)
    usd_b = usd_m / 1_000
    return f"₹{crore:,.0f} cr  (${usd_m:,.1f}M / ${usd_b:.2f}B)"


def table_str(headers: list, rows: list, indent: int = 4) -> str:
    """
    Render a plain-text ASCII table.

    Parameters
    ----------
    headers : column header strings
    rows    : list of row lists (any mix of str/int/float)
    indent  : leading spaces
    """
    pad = " " * indent
    str_rows = [[str(c) for c in r] for r in rows]
    widths = [max(len(str(h)), *(len(r[i]) for r in str_rows) if str_rows else [0])
              for i, h in enumerate(headers)]
    sep  = pad + "  ".join("─" * w for w in widths)
    head = pad + "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
    body = [
        pad + "  ".join(c.ljust(widths[j]) for j, c in enumerate(r))
        for r in str_rows
    ]
    return "\n".join(["", head, sep, *body, ""])


# ══════════════════════════════════════════════════════════════════════════════
# PROGRESS BAR
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
        self.total  = total
        self.label  = label
        self.width  = width
        self.log    = log
        self._n     = 0
        self._t0    = time.time()
        self._last  = -1

    def update(self, n: int = 1):
        self._n += n
        pct = int(100 * self._n / self.total)
        if pct == self._last:
            return
        self._last = pct
        if pct % 10 == 0:
            filled = int(self.width * self._n / self.total)
            bar    = "█" * filled + "░" * (self.width - filled)
            elapsed = time.time() - self._t0
            eta = (elapsed / self._n * (self.total - self._n)) if self._n else 0
            msg = f"  [{bar}] {pct:3d}%  {self._n:,}/{self.total:,}  ETA {eta:.0f}s"
            _emit(msg, self.log)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        elapsed = time.time() - self._t0
        ok(f"{self.label}: {self.total:,} iterations in {elapsed:.1f}s", self.log)


# ══════════════════════════════════════════════════════════════════════════════
# TIMER
# ══════════════════════════════════════════════════════════════════════════════

class Timer:
    def __init__(self):
        self.t = time.time()

    @staticmethod
    def _fmt(s: float) -> str:
        if s < 60:
            return f"{s:.1f}s"
        return f"{s/60:.1f}min"

    def elapsed(self) -> str:
        return self._fmt(time.time() - self.t)

    def lap(self, label: str = "", log: Logger | None = None) -> float:
        """Print elapsed since last lap and reset."""
        s = time.time() - self.t
        ok(f"{label + ': ' if label else ''}{self._fmt(s)}", log)
        self.t = time.time()
        return s


# ══════════════════════════════════════════════════════════════════════════════
# REFERENCE DATA MARKDOWN PARSER
# ══════════════════════════════════════════════════════════════════════════════

def load_reference_data(md_path: Path) -> dict:
    """
    Parse a structured reference_data.md file into a dict of sections.

    Expected format:
        ## SECTION: <SECTION_ID>

        <!-- meta
        key: value
        -->

        | col1 | col2 |
        |------|------|
        | val  | val  |

    Returns dict keyed by SECTION_ID, each value:
        {"_meta": {key: value}, "rows": [{col: val, ...}, ...]}
    """
    md_path = Path(md_path)
    if not md_path.exists():
        raise FileNotFoundError(
            f"Reference data file not found: {md_path}\n"
            "Ensure reference_data.md lives alongside config.py."
        )

    def _cast(v: str):
        v = v.strip()
        try:    return int(v)
        except ValueError: pass
        try:    return float(v)
        except ValueError: pass
        return v

    def _is_sep(cols: list) -> bool:
        return all(
            set(c.replace(":", "").replace("-", "").replace(" ", "")) <= {""}
            for c in cols
        )

    lines        = md_path.read_text(encoding="utf-8").splitlines()
    result       = {}
    current_id   = None
    current_meta = {}
    current_rows = []
    header_cols  = None
    in_meta      = False
    meta_lines   = []

    def _flush():
        if current_id is not None:
            result[current_id] = {"_meta": current_meta, "rows": current_rows}

    for line in lines:
        s = line.strip()
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
            header_cols = cols
            continue

        while len(cols) < len(header_cols):
            cols.append("")
        cols = cols[: len(header_cols)]
        current_rows.append({header_cols[i]: _cast(cols[i]) for i in range(len(header_cols))})

    _flush()
    return result


def pivot_transposed(rows: list, key_col: str) -> dict:
    """
    Pivot a transposed table (rows=fields, columns=years) into:
        {year_str: {field: value}}
    """
    if not rows:
        return {}
    year_cols = [k for k in rows[0] if k != key_col and str(k).isdigit()]
    out: dict = {str(y): {} for y in year_cols}
    for row in rows:
        field = str(row[key_col])
        for yr in year_cols:
            out[str(yr)][field] = float(row[yr])
    return out


# ══════════════════════════════════════════════════════════════════════════════
# FILE I/O
# ══════════════════════════════════════════════════════════════════════════════

def read_csv(path: Path, required: bool = True, **kwargs) -> pd.DataFrame:
    """
    Read CSV. If required=True (default) raise FileNotFoundError when missing.
    If required=False return an empty DataFrame when missing (non-fatal).
    """
    path = Path(path)
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Required file not found: {path}")
        return pd.DataFrame()
    return pd.read_csv(path, **kwargs)


def save_csv(df: pd.DataFrame, path: Path, label: str = "",
             log: Logger | None = None):
    """Save DataFrame to CSV. Writes index only when the index has a name.
    Silently skips (with a warning) when df is None."""
    if df is None:
        warn(f"save_csv: skipping '{label or path}' — DataFrame is None", log)
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=df.index.name is not None)
    ok(f"Saved {label or path.name}  ({len(df):,} rows → {path.name})", log)


def safe_csv(path, **kwargs) -> pd.DataFrame:
    """
    Read CSV without raising on missing or corrupt files.
    Returns an empty DataFrame on any error.
    Use read_csv() when the file is *required* (raises FileNotFoundError).
    Use safe_csv() when the file is optional (silently returns empty df).
    """
    try:
        p = Path(path)
        return pd.read_csv(p, **kwargs) if p.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# SENSITIVITY RANGE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def sensitivity_half_range_pct(low: float, base: float, high: float) -> float:
    """
    Symmetric sensitivity range as ±% of BASE.
    Formula: (HIGH - LOW) / |BASE| / 2 × 100

    This is the canonical definition used in Table 8 (direct TWF) throughout the
    report. Use this instead of the one-sided upside formula (HIGH-BASE)/BASE,
    which overstates uncertainty when HIGH and LOW are asymmetric.

    Returns 0.0 when base == 0.
    """
    if base == 0:
        return 0.0
    return 100.0 * (high - low) / abs(base) / 2.0


def fmt_sens_range(low: float, base: float, high: float) -> str:
    """
    Format sensitivity as '±X.X%' string.
    Returns '—' when base is zero (undefined range).
    """
    if base == 0:
        return "—"
    return f"±{sensitivity_half_range_pct(low, base, high):.1f}%"


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE-GROUP CLASSIFICATION  (WSI lookup)
# ══════════════════════════════════════════════════════════════════════════════

def classify_source_group(product_id: int) -> str:
    """
    Classify a 1-indexed SUT product_id into its upstream source group.
    Used for WSI weighting (WRI Aqueduct 4.0) and report tables.

    Based on India 140-sector SUT product list (NAS 2025 edition).

    Group boundaries (product_id):
      1 – 29   Agriculture   (WSI 0.827, Irr-weighted bws)
      30 – 40  Mining        (WSI 0.814, Ind-weighted bws)
      41 – 80  Manufacturing (WSI 0.814) — includes food mfg, textiles, chemicals
      71 – 80  Petroleum     (WSI 0.814) — subset of Manufacturing, separate category
      81 – 113 Manufacturing (WSI 0.814) — metals, machinery, misc mfg
      114 – 116 Electricity  (WSI 0.814) — power generation + distribution,
                                            water supply & distribution
      117 – 140 Services     (WSI 0.000) — transport, finance, health, etc.

    NOTE: Products 115–116 (Electricity distribution, Water supply) previously
    fell through to "Services" (WSI=0) because the old boundary was pid <= 113.
    This caused the Scarce/Blue ratio to be suppressed by ~35%. Fixed here.
    """
    pid = int(product_id)
    if 1   <= pid <= 29:  return "Agriculture"
    if 30  <= pid <= 40:  return "Mining"
    if 71  <= pid <= 80:  return "Petroleum"
    if 41  <= pid <= 113: return "Manufacturing"
    if pid == 114:        return "Electricity"        # power generation
    if 115 <= pid <= 116: return "Electricity"        # distrib + water supply
    return "Services"                                  # 117-140


# ══════════════════════════════════════════════════════════════════════════════
# WATER COLUMN FINDERS
# ══════════════════════════════════════════════════════════════════════════════

def find_blue_water_col(df: pd.DataFrame, year: str = None) -> str | None:
    """
    Find the blue water coefficient column in a SUT/concordance DataFrame.
    Priority order: year-specific Blue → any Blue → non-Green Water+crore → None.
    Never returns a Green column.

    Replaces ad-hoc one-liners scattered across calculate_indirect_twf.py and
    calculate_sda_mc.py that could accidentally pick up the Green column.
    """
    cols = df.columns.tolist()
    if year:
        yr_blue = [c for c in cols
                   if f"Water_{year}_Blue" in c and "crore" in c.lower()]
        if yr_blue:
            return yr_blue[0]
    any_blue = [c for c in cols
                if "Blue" in c and "crore" in c.lower()]
    if any_blue:
        return any_blue[0]
    fallback = [c for c in cols
                if "Water" in c and "crore" in c.lower() and "Green" not in c]
    return fallback[0] if fallback else None


def find_green_water_col(df: pd.DataFrame, year: str = None) -> str | None:
    """Find the green water coefficient column. Returns None if absent."""
    cols = df.columns.tolist()
    if year:
        yr_green = [c for c in cols
                    if f"Water_{year}_Green" in c and "crore" in c.lower()]
        if yr_green:
            return yr_green[0]
    return next((c for c in cols
                 if "Green" in c and "crore" in c.lower()), None)


# ══════════════════════════════════════════════════════════════════════════════
# ROW / VALUE HELPERS  (shared across compare_years, sda_mc, outbound_twf)
# ══════════════════════════════════════════════════════════════════════════════

def year_row(df: pd.DataFrame, year,
             year_col: str = "Year") -> "pd.Series | None":
    """
    Return the first row matching year in year_col.
    Compares as strings (handles int/float year values in CSV).
    Returns None when df is empty, year_col absent, or no match found.
    """
    if df is None or df.empty or year_col not in df.columns:
        return None
    matches = df[df[year_col].astype(str) == str(year)]
    return matches.iloc[0] if not matches.empty else None


def col_val(row: "pd.Series | None", *keys, default: float = 0.0) -> float:
    """
    Extract the first matching key from a pandas Series.
    Returns default when row is None or no key is found.
    Handles non-numeric values gracefully (returns default).

    Replaces _col() in compare_years.py which tries multiple column name
    fallbacks — now shared so all modules use the same logic.
    """
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
    W0: "np.ndarray", L0: "np.ndarray", Y0: "np.ndarray",
    W1: "np.ndarray", L1: "np.ndarray", Y1: "np.ndarray",
) -> dict:
    """
    Six-permutation (exhaustive) SDA for a 3-factor model TWF = W · L · Y.

    Averages all 3! = 6 orderings of variable substitution from year-0 to year-1.
    Residual = 0 by construction because all cross-product interaction terms
    (dW⊗dL, dW⊗dY, dL⊗dY, dW⊗dL⊗dY) are fully distributed across effects.

    This replaces the two-polar form  ΔW_eff = 0.5*(dW@L0 + dW@L1)@Y_mid
    which has a residual of 0.5*(dW@dL@dY) — typically 3–8% for large
    simultaneous changes in all three factors (as in 2015→2019).

    Reference: Dietzenbacher, E., & Los, B. (1998). Structural decomposition
    techniques: sense and sensitivity. Economic Systems Research, 10(4), 307–324.

    Parameters
    ----------
    W0, W1 : water intensity vectors (140,), m³/₹ crore, year-0 and year-1
    L0, L1 : Leontief inverse matrices (140, 140), year-0 and year-1
    Y0, Y1 : tourism demand vectors (140,), ₹ crore, year-0 and year-1

    Returns
    -------
    dict with keys:
      TWF0_m3, TWF1_m3, dTWF_m3     — total water footprint and change
      W_effect_m3, L_effect_m3, Y_effect_m3  — decomposed effects
      W_effect_pct, L_effect_pct, Y_effect_pct — as % of |dTWF|
      Residual_m3, Residual_pct      — should be ~0 (numerical noise only)
      Near_cancellation              — flag when effects >> net change
      Instability_ratio              — max(|effects|) / |dTWF|
      SDA_Method                     — 'six_polar'
    """
    from itertools import permutations

    def _twf(w, l, y):
        return float(np.dot(w @ l, y))

    base  = [W0, L0, Y0]
    year1 = [W1, L1, Y1]
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

    TWF0     = _twf(W0, L0, Y0)
    TWF1     = _twf(W1, L1, Y1)
    dTWF     = TWF1 - TWF0
    residual = dTWF - (W_eff + L_eff + Y_eff)

    max_eff      = max(abs(W_eff), abs(L_eff), abs(Y_eff))
    near_cancel  = bool(abs(dTWF) > 0 and max_eff > 5 * abs(dTWF))
    inst_ratio   = round(max_eff / abs(dTWF), 1) if abs(dTWF) > 1e-9 else float("inf")

    def _pct(v):
        return round(100 * v / abs(dTWF), 3) if abs(dTWF) > 1e-9 else 0.0

    return {
        "TWF0_m3":           TWF0,
        "TWF1_m3":           TWF1,
        "dTWF_m3":           dTWF,
        "W_effect_m3":       W_eff,
        "L_effect_m3":       L_eff,
        "Y_effect_m3":       Y_eff,
        "Sum_effects_m3":    W_eff + L_eff + Y_eff,
        "Residual_m3":       residual,
        "W_effect_pct":      _pct(W_eff),
        "L_effect_pct":      _pct(L_eff),
        "Y_effect_pct":      _pct(Y_eff),
        "Residual_pct":      _pct(residual),
        "Near_cancellation": near_cancel,
        "Instability_ratio": inst_ratio,
        "SDA_Method":        "six_polar",
    }


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
                        tol_pct: float = 1.0, log: Logger | None = None):
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
                              log: Logger | None = None):
    neg       = (A < 0).sum()
    diag_mean = np.diag(A).mean() if A.shape[0] == A.shape[1] else None
    ok(
        f"{name}: shape={A.shape}  non-zero={np.count_nonzero(A):,}  "
        f"max={A.max():.4f}  neg={neg}"
        + (f"  diag_mean={diag_mean:.4f}" if diag_mean is not None else ""),
        log,
    )
    if neg > 0:
        warn(f"{name} has {neg} negative values — review SUT data", log)


def check_spectral_radius(A: np.ndarray, name: str = "A",
                           log: Logger | None = None) -> float:
    """ρ(A) < 1 → Hawkins-Simon condition holds."""
    rho = float(np.max(np.abs(np.linalg.eigvals(A))))
    if rho < 1.0:
        ok(f"Spectral radius ρ({name}) = {rho:.6f}  < 1  ✓ Hawkins-Simon holds", log)
    else:
        warn(f"Spectral radius ρ({name}) = {rho:.6f}  ≥ 1  ⚠ Economy may not be productive", log)
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
    ok(
        f"Column-sum Δ: mean={np.nanmean(np.abs(pct_change)):.1f}%  "
        f"max={np.nanmax(np.abs(pct_change)):.1f}%  "
        f"n_>{threshold_pct}%: {n_big}/{A_base.shape[1]}",
        log,
    )
    if n_big > 0:
        warn(f"{n_big} sectors shifted >{threshold_pct}% — review NAS scaling", log)
        # Log which sectors so user can check if tourism sectors are affected
        big_idx = np.where(np.abs(pct_change) > threshold_pct)[0]
        for i in big_idx:
            name = products[i] if products and i < len(products) else f"col_{i+1}"
            pct  = pct_change[i]
            if log:
                log.info(f"    [{i+1:>3}] {name[:45]:<45}  Δ={pct:+.1f}%")
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

    Returns DataFrame with: Year, Value, Absolute_Change, Pct_Change, CAGR_vs_base, Metric
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
            base_val = val; base_yr = yr
            lines.append(f"  {yr:<8}  {fmt.format(val):>14}{unit}  {'(base)':>12}")
            rows.append({"Year": yr, "Value": val,
                         "Absolute_Change": 0.0, "Pct_Change": 0.0, "CAGR_vs_base": 0.0})
            continue

        abs_chg = val - base_val
        pct_chg = 100 * abs_chg / base_val if base_val else float("nan")
        try:
            n_yrs = int(yr[:4]) - int(base_yr[:4])
        except ValueError:
            n_yrs = 1
        # CAGR is only meaningful when both values share the same sign and base > 0.
        # When the series crosses zero (sign change) or base is non-positive, CAGR
        # is mathematically undefined — report NaN with a clear label instead of
        # letting Python produce a complex number or a silent +nan%/yr.
        if base_val > 0 and val > 0 and n_yrs > 0:
            cagr = 100 * ((val / base_val) ** (1 / n_yrs) - 1)
        elif base_val < 0 and val < 0 and n_yrs > 0:
            # Both negative: flip signs, compute, flip result
            cagr = 100 * ((val / base_val) ** (1 / n_yrs) - 1)
        elif n_yrs > 0 and base_val != 0 and (base_val * val) < 0:
            cagr = float("nan")  # sign crossing — CAGR undefined
        else:
            cagr = float("nan")

        arrow = "↑" if abs_chg > 0 else "↓"
        cagr_str = f"{cagr:>+9.1f}%/yr" if not (cagr != cagr) else "  sign-cross"  # NaN check
        lines.append(
            f"  {yr:<8}  {fmt.format(val):>14}{unit}  "
            f"{arrow}{abs(abs_chg):>10.{decimals}f}  "
            f"{pct_chg:>+9.1f}%  {cagr_str}"
        )
        rows.append({"Year": yr, "Value": val,
                     "Absolute_Change": abs_chg,
                     "Pct_Change":      round(pct_chg, 3),
                     "CAGR_vs_base":    round(cagr, 3)})

    _emit("\n".join(lines), log)
    df = pd.DataFrame(rows)
    df["Metric"] = metric
    return df


def compare_sectors_across_years(year_dfs: dict, value_col: str,
                                   label_col: str, metric: str,
                                   n_top: int = 5,
                                   log: Logger | None = None) -> pd.DataFrame:
    """Build a wide sector×year table and print top movers."""
    years = sorted(year_dfs.keys())
    if not years:
        return pd.DataFrame()

    wide = year_dfs[years[0]][[label_col, value_col]].copy().rename(
        columns={value_col: years[0]}
    )
    for yr in years[1:]:
        wide = wide.merge(
            year_dfs[yr][[label_col, value_col]].rename(columns={value_col: yr}),
            on=label_col, how="outer",
        )

    wide     = wide.fillna(0)
    first_yr = years[0]; last_yr = years[-1]
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