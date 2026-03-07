"""
visualise_results.py — Publication-Quality Figures
India Tourism Water Footprint Pipeline
=============================================================================

FIGURES PRODUCED (10 publication-quality charts):

  Fig 1  fig1_methodology_framework.png  Two-column analytical framework diagram.
                                          6 horizontal rows (Data Sources → Data
                                          Preparation → EEIO Core → Analytical
                                          Extensions → Validation → Outputs).
                                          Each row: narrow phase label on left,
                                          detail boxes on right. Pure matplotlib —
                                          no external dependencies. Journal-ready.

  Fig 2  fig2_diverging_bar.png          Double-ended diverging bar: water SOURCE
                                          (left) ↔ tourism CONSUMPTION (right).
                                          Same total, opposite perspectives —
                                          the EEIO methodology in one visual.

  Fig 3  fig3_proportional_area.png      Area-encoded domestic/inbound intensity.
                                          Width = tourist-days, height = L/tourist/day,
                                          AREA = total TWF. All 3 years side-by-side.

  Fig 4  fig4_sda_waterfall.png          Annotated SDA waterfall (W / L / Y effects)
                                          with COVID narrative labels and baseline→total
                                          flow. Guard: graceful placeholder if no data.

  Fig 5  fig5_nested_bar_ghost.png       3 years nested stacked bars. Ghost outline of
                                          2015 sits behind 2019 and 2022. Intensity
                                          dots on secondary axis.

  Fig 6  fig6_flow_strip.png             3-column supply-chain Sankey strip:
                                          Water source group → Sector → Tourism demand.

  Fig 7  fig7_state_pressure_map.png     India state bubble chart (or map if geopandas
                                          present): circle size = TWF volume,
                                          colour = WRI Aqueduct 4.0 WSI stress.

  Fig 8  fig8_uncertainty_strip.png      Stacked KDE density strips per year with
                                          LOW / BASE / HIGH scenario markers and
                                          90% CI bracket annotation.

  Fig 9  fig9_multistory_dashboard.png   6-panel overview dashboard: total TWF trend,
                                          per-tourist intensity lines, upstream origin
                                          doughnut, scarce TWF bars, inbound/domestic
                                          ratio, and MC whisker chart.

  Fig 10 fig10_blue_green_comparison.png Blue vs Blue+Green indirect TWF grouped bars
                                          (full hydrological disclosure). Guard:
                                          placeholder if green column absent.

All figures saved to: outputs/visualisation/
"""

import sys
import textwrap
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.ticker import FuncFormatter
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D
import matplotlib.cm as cm

try:
    from scipy.stats import gaussian_kde
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

sys.path.insert(0, str(Path(__file__).parent))
from config import BASE_DIR, DIRS, STUDY_YEARS, ACTIVITY_DATA
from utils import Logger, Timer, ok, warn, section

# ── Output directory ───────────────────────────────────────────────────────────
_VIS_DIR = DIRS.get("visualisation", BASE_DIR / "3-final-results" / "visualisation")

# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL STYLE — Nature/Water Research journal
# ══════════════════════════════════════════════════════════════════════════════

_WONG = [
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#009E73",  # green
    "#F0E442",  # yellow
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#CC79A7",  # pink
    "#000000",  # black
]

_YEAR_COLORS = {"2015": _WONG[4], "2019": _WONG[0], "2022": _WONG[2]}
_YEAR_LABELS = {"2015": "FY 2015–16", "2019": "FY 2019–20", "2022": "FY 2021–22"}

plt.rcParams.update({
    "font.family":        "DejaVu Sans",
    "font.size":          9,
    "axes.labelsize":     10,
    "axes.titlesize":     10,
    "axes.titleweight":   "bold",
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "axes.linewidth":     0.8,
    "xtick.major.width":  0.8,
    "ytick.major.width":  0.8,
    "xtick.direction":    "out",
    "ytick.direction":    "out",
    "legend.frameon":     False,
    "legend.fontsize":    8,
    "figure.dpi":         300,
    "savefig.dpi":        300,
    "savefig.bbox":       "tight",
    "savefig.facecolor":  "white",
    "pdf.fonttype":       42,
})


# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADERS
# ══════════════════════════════════════════════════════════════════════════════

def _load(path: Path, log=None) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    warn(f"Missing: {path.name} — panel will be skipped", log)
    return pd.DataFrame()


def _load_indirect_totals(log=None) -> dict:
    df = _load(DIRS["indirect"] / "indirect_twf_all_years.csv", log)
    if df.empty or "Year" not in df.columns:
        return {}
    # all_years CSV uses "Indirect_TWF_billion_m3" (in bn m³), not "Total_Water_m3"
    # Support both column conventions so the loader works whether called before
    # or after compare_years has run.
    if "Indirect_TWF_billion_m3" in df.columns:
        return {str(int(r["Year"])): float(r["Indirect_TWF_billion_m3"]) * 1e9
                for _, r in df.iterrows()}
    if "Total_Water_m3" in df.columns:
        return {str(int(r["Year"])): float(r["Total_Water_m3"])
                for _, r in df.iterrows()}
    # Last resort: sum category CSV directly
    result = {}
    for yr_str in STUDY_YEARS:
        cat = _load(DIRS["indirect"] / f"indirect_twf_{yr_str}_by_category.csv", log)
        if not cat.empty and "Total_Water_m3" in cat.columns:
            result[yr_str] = float(cat["Total_Water_m3"].sum())
    return result


def _load_direct_totals(log=None) -> dict:
    df = _load(DIRS["direct"] / "direct_twf_all_years.csv", log)
    if df.empty:
        return {}
    base = df[df["Scenario"] == "BASE"] if "Scenario" in df.columns else df
    return {str(int(r["Year"])): float(r["Total_m3"])
            for _, r in base.iterrows() if "Year" in base.columns}


def _load_mc(year: str, log=None) -> np.ndarray:
    df = _load(DIRS["monte_carlo"] / f"mc_results_{year}.csv", log)
    if df.empty:
        return np.array([])
    col = [c for c in df.columns if "total" in c.lower() or "twf" in c.lower()]
    return df[col[0]].values / 1e9 if col else np.array([])


def _load_sda(log=None) -> list:
    df = _load(DIRS["sda"] / "sda_summary_all_periods.csv", log)
    return df.to_dict("records") if not df.empty else []


def _load_origin(year: str, log=None) -> pd.DataFrame:
    return _load(DIRS["indirect"] / f"indirect_twf_{year}_origin.csv", log)


def _load_intensity(log=None) -> pd.DataFrame:
    return _load(DIRS["comparison"] / "twf_per_tourist_intensity.csv", log)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _panel_label(ax, label: str, x=-0.12, y=1.05):
    ax.text(x, y, label, transform=ax.transAxes,
            fontsize=10, fontweight="bold", va="top", ha="left")


def _save(fig: plt.Figure, name: str, log=None):
    _VIS_DIR.mkdir(parents=True, exist_ok=True)
    p = _VIS_DIR / name
    fig.savefig(p)
    ok(f"Saved {name}  ({p.stat().st_size // 1024} KB)", log)
    plt.close(fig)


def _ph(ax, msg: str):
    """Show a placeholder text block when data is missing."""
    ax.text(0.5, 0.5, msg, ha="center", va="center", transform=ax.transAxes,
            fontsize=8.5, color="grey", style="italic",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#F8F8F8", alpha=0.9))
    ax.set_xticks([]); ax.set_yticks([])


def _src_val_cols(df: pd.DataFrame):
    """Auto-detect source-group and value columns in an origin/category dataframe."""
    src = next((c for c in df.columns
                if any(k in c.lower() for k in ("source", "group", "sector"))), None)
    val = next((c for c in df.columns
                if any(k in c.lower() for k in ("m3", "water"))), None)
    return src, val


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 1 — ANALYTICAL FRAMEWORK (methodology diagram)
# ══════════════════════════════════════════════════════════════════════════════

def fig1_methodology_framework(log=None, target_width_in=14.0, dpi=300):
    """
    Fully responsive methodology framework diagram.

    Like a browser CSS layout engine:
      1. Builds a scratch figure at the target output width
      2. Uses the renderer to measure every string's ACTUAL pixel width
      3. Wraps text word-by-word so nothing ever overflows its box
      4. Computes row heights from the real wrapped line counts
      5. Sizes the figure height to fit all content exactly

    Change `target_width_in` to reflow the whole diagram — like resizing a browser.
    """
    section("Figure 1 — Analytical Framework (Methodology Diagram)", log=log)

    # ── Content data ─────────────────────────────────────────────────────────
    ROWS = [
        {
            "phase": "① DATA SOURCES",
            "gist":  ["Raw inputs", "6 data streams", "Multi-source"],
            "boxes": [
                ("TSA 2015–16",      ["MoT India", "25 categories", "Inbound · Domestic", "₹ crore base"]),
                ("NAS Stmt 6.1",     ["MoSPI 2024", "Real GVA growth", "2011-12 prices", "12 sector keys"]),
                ("India SUT Tables", ["MoSPI · 3 years", "140×140 matrix", "2015-16·19-20·21-22", "Nominal ₹ crore"]),
                ("EXIOBASE v3.8",    ["163-sector MRIO", "Blue water W (m³/₹)", "Green water", "India concordance"]),
                ("CPI · USD/INR",    ["MoSPI · RBI", "Year deflators", "Nominal → real", "Cross-currency"]),
                ("WRI Aqueduct 4.0", ["Kuzma et al. 2023", "Sector WSI weights", "Agr=0.827  Ind=0.814", "Services=0.000"]),
            ],
            "c_bg": "#D6EAF8", "c_brd": "#1A5276", "c_row": "#EBF5FB",
        },
        {
            "phase": "② DATA PREPARATION",
            "gist":  ["Pre-processing", "3 operations", "Temurshoev 2011"],
            "boxes": [
                ("TSA Extrapolation",        ["nom_factor = GVA_growth × CPI(t)/CPI₀", "→ TSA₂₀₁₅  TSA₂₀₁₉  TSA₂₀₂₂", "Nominal + real ₹ crore"]),
                ("IO Table Construction",    ["SUT → Product Tech. Assumption", "L = (I − A)⁻¹  per study year", "Balance error < 1.0% verified"]),
                ("Tourism Demand Vectors Y", ["25 TSA cats → 163 EXIOBASE codes", "Y_total · Y_inbound · Y_domestic", "163 sectors × 3 years = 489 vectors"]),
            ],
            "c_bg": "#D5F5E3", "c_brd": "#1E8449", "c_row": "#EAFAF1",
        },
        {
            "phase": "③ EEIO CORE MODEL",
            "gist":  ["Core equations", "W · L · Y", "Blue + Scarce"],
            "boxes": [
                ("Water Vector (W)",      ["EXIOBASE → SUT-140 concordance", "m³ per ₹ crore  [shape: 163]", "Green water: parallel disclosure"]),
                ("Indirect TWF",          ["TWF = W · L · Y", "Inbound = W·L·Y_inbound", "Domestic = W·L·Y_domestic"]),
                ("Scarce TWF",            ["Scarce = TWF × WSI_sector", "Aqueduct 4.0 sector-level weights", "Sector vs. country WSI (advance)"]),
                ("Direct TWF",            ["Activity-based bottom-up", "Tourist-days × sector coeff.", "Hotel · Restaurant · Transport"]),
                ("Water Multiplier Ratio",["MR[j] = WL[j] / WL̄_economy", "MR > 1 → water-intensive", "Policy hotspot identification"]),
            ],
            "c_bg": "#FDEBD0", "c_brd": "#A04000", "c_row": "#FEF9E7",
        },
        {
            "phase": "④ ANALYTICAL EXTENSIONS",
            "gist":  ["Novel contributions", "★ Not in", "Lee et al. 2021"],
            "boxes": [
                ("Structural Decomp. (SDA)",  ["ΔTWF = ΔW·eff + ΔL·eff + ΔY·eff", "Six-polar · residual < 0.1%", "2015→19  ·  2019→22"]),
                ("Monte Carlo  n=10,000",      ["Inputs: W_agr · W_hotel · volumes", "Output: P5–P95 bounds per year", "Rank-corr. variance decomp."]),
                ("Supply-Chain Path (HEM)",    ["pull[i,j] = W[i]·L[i,j]·Y[j]", "Top-50 pathways ranked", "Tourism-dependency index/sector"]),
                ("Outbound TWF & Net Balance", ["TWF = N×days×WF_local/365×1.5", "Net = Outbound − Inbound TWF", "India: net importer or exporter?"]),
            ],
            "c_bg": "#E8DAEF", "c_brd": "#6C3483", "c_row": "#F5EEF8",
        },
        {
            "phase": "⑤ VALIDATION",
            "gist":  ["9 assertions", "Sensitivity ±20%", "Error < 1%"],
            "boxes": [
                ("① Scarce/Blue ∈ [0.30–0.95]", ["Physical plausibility check"]),
                ("② Sensitivity: LOW<BASE<HIGH",  ["Monotonicity of ±20% bounds"]),
                ("③ Inbound > Domestic",          ["L/tourist-day ordering check"]),
                ("④⑤ Ratios & Green/Blue bounds", ["Inb/Dom ∈[5,30]  G/B ∈[0,10]"]),
                ("⑥ YoY Δ ∈[−60,+30%]",          ["Catches data/scaling errors"]),
                ("⑦⑧⑨ IO · SDA · W+L+Y",         ["<1%  <0.1%  Sum≈ΔTWF"]),
            ],
            "c_bg": "#FADBD8", "c_brd": "#922B21", "c_row": "#FDEDEC",
        },
        {
            "phase": "⑥ OUTPUTS",
            "gist":  ["5 result sets", "Policy-ready", "Journal figures"],
            "boxes": [
                ("TWF Totals",            ["bn m³ · L/tourist/day", "Blue + Scarce + Green", "Inbound vs. Domestic"]),
                ("Sector Hotspots",       ["Top-N indirect sectors", "Water multiplier ratios", "HEM dependency index"]),
                ("Temporal & SDA Drivers",["ΔW · ΔL · ΔY effects", "COVID structural break", "Technology efficiency Δ"]),
                ("Net Water Balance",     ["Outbound TWF total", "Virtual water transfer", "India net position"]),
                ("Uncertainty Bounds",    ["MC P5–P95 range", "Sensitivity half-range", "Dominant inputs ranked"]),
            ],
            "c_bg": "#D0ECE7", "c_brd": "#0E6655", "c_row": "#E8F8F5",
        },
    ]

    KEY_EQS = [
        "TWF = W · L · Y",
        "Scarce = TWF × WSI",
        "L = (I − A)⁻¹",
        "ΔTWF = ΔW + ΔL + ΔY",
        "MR[j] = WL[j] / WL̄",
    ]

    # ── Layout constants (in "data units" where canvas = 100 wide) ───────────
    # These are STRUCTURAL proportions, not font sizes — they scale with width.
    MARGIN      = 0.8    # outer margin
    LBL_FRAC    = 0.135  # label column as fraction of total width (auto scales)
    GAP_LR      = 0.008  # gap between label col and boxes, as fraction
    BOX_GAP_F   = 0.005  # gap between boxes, as fraction
    BOX_PAD_F   = 0.006  # horizontal text padding inside box, as fraction

    PHASE_HDR_F = 0.028  # phase header strip height, fraction of width
    BOX_HDR_F   = 0.020  # box title strip height, fraction of width
    BOX_PAD_T_F = 0.004
    BOX_PAD_B_F = 0.003
    BOX_VPAD_F  = 0.005
    ROW_VPAD_F  = 0.004
    H_ARR_F     = 0.022
    H_TITLE_F   = 0.046
    H_LEG_F     = 0.032
    LINE_H_F    = 0.016  # line height as fraction of width

    # Font sizes scale with width: fs = base_fs * (target_width_in / reference_width)
    REF_WIDTH   = 14.0
    FS_SCALE    = target_width_in / REF_WIDTH

    FS_TITLE  = max(7.0,  8.5  * FS_SCALE)
    FS_SUB    = max(5.5,  6.2  * FS_SCALE)
    FS_PHASE  = max(6.0,  7.0  * FS_SCALE)
    FS_BODY   = max(5.5,  6.5  * FS_SCALE)
    FS_BTITLE = max(5.5,  6.8  * FS_SCALE)
    FS_EQ     = max(5.0,  6.2  * FS_SCALE)

    # Convert fractions → data units (canvas = 100 wide)
    W = 100.0
    def f(frac): return frac * W

    LBL_W    = f(LBL_FRAC)
    BOX_X0   = MARGIN + LBL_W + f(GAP_LR)
    BOX_X1   = W - MARGIN
    BOX_GAP  = f(BOX_GAP_F)
    BOX_PAD  = f(BOX_PAD_F)

    PHASE_HDR = f(PHASE_HDR_F)
    BOX_HDR_H = f(BOX_HDR_F)
    BOX_PAD_T = f(BOX_PAD_T_F)
    BOX_PAD_B = f(BOX_PAD_B_F)
    BOX_VPAD  = f(BOX_VPAD_F)
    ROW_VPAD  = f(ROW_VPAD_F)
    H_ARR     = f(H_ARR_F)
    H_TITLE   = f(H_TITLE_F)
    H_LEG     = f(H_LEG_F)
    LINE_H    = f(LINE_H_F)

    def box_width(n_boxes):
        avail = BOX_X1 - BOX_X0 - (n_boxes - 1) * BOX_GAP
        return avail / n_boxes

    def is_eq(s):
        return any(c in s for c in
                   ("·","=","×","→","⁻","Δ","∈","≈","<",">",
                    "TWF","WL[","MR[","pull","nom_","GVA"))

    # ── Step 1: scratch figure for renderer-based measurement ────────────────
    _sf, _sa = plt.subplots(figsize=(target_width_in, target_width_in * 0.5))
    _sa.set_xlim(0, W); _sa.set_ylim(0, W * 0.5)
    _sa.axis("off")
    _sf.canvas.draw()
    _rend = _sf.canvas.get_renderer()

    def _tw(s, fs, ff="DejaVu Sans"):
        """Measure text width in data-units on the scratch axes."""
        t = _sa.text(W/2, W*0.25, s, fontsize=fs,
                     fontfamily=ff, ha="center", va="center")
        _sf.canvas.draw()
        bb = t.get_window_extent(renderer=_rend)
        inv = _sa.transData.inverted()
        x0, _ = inv.transform((bb.x0, bb.y0))
        x1, _ = inv.transform((bb.x1, bb.y0))
        t.remove()
        return abs(x1 - x0)

    def _fit_font(s, max_w, fs_start, ff):
        """Find largest font size ≤ fs_start where s fits within max_w."""
        fs = fs_start
        while fs > 4.5 and _tw(s, fs, ff) > max_w:
            fs -= 0.3
        return fs

    def smart_wrap(s, max_w, fs, ff):
        """Split s into lines that each fit within max_w data-units."""
        if _tw(s, fs, ff) <= max_w:
            return [s]
        words = s.split(" ")
        lines, cur = [], ""
        for word in words:
            cand = (cur + " " + word).strip()
            if _tw(cand, fs, ff) <= max_w:
                cur = cand
            else:
                if cur:
                    lines.append(cur)
                # single word wider than box — force-break at midpoint
                if _tw(word, fs, ff) > max_w:
                    mid = max(1, len(word) // 2)
                    lines.append(word[:mid] + "-")
                    cur = word[mid:]
                else:
                    cur = word
        if cur:
            lines.append(cur)
        return lines or [s]

    # ── Step 2: pre-compute all wrapped lines ────────────────────────────────
    row_wrapped = []   # row → box → [(sub_line, is_equation)]
    row_title_fs = []  # row → box → fitted font size for box title

    for row in ROWS:
        n_b   = len(row["boxes"])
        bw    = box_width(n_b)
        inner = bw - 2 * BOX_PAD

        boxes_lines = []
        boxes_tfs   = []
        for (btitle, blines) in row["boxes"]:
            # title font: shrink until it fits the header strip width
            tfs = _fit_font(btitle, inner, FS_BTITLE, "DejaVu Sans")
            boxes_tfs.append(tfs)

            expanded = []
            for line in blines:
                eq  = is_eq(line)
                fs  = FS_EQ if eq else FS_BODY
                ff  = "monospace" if eq else "DejaVu Sans"
                for sub in smart_wrap(line, inner, fs, ff):
                    expanded.append((sub, eq))
            boxes_lines.append(expanded)

        row_wrapped.append(boxes_lines)
        row_title_fs.append(boxes_tfs)

    # Pre-compute label-column phase name fitting
    lbl_inner = LBL_W - 2 * BOX_PAD
    phase_fits = []   # list of (lines, font_size) per row
    for row in ROWS:
        pfs = _fit_font(row["phase"], lbl_inner, FS_PHASE, "DejaVu Sans")
        if _tw(row["phase"], pfs, "DejaVu Sans") <= lbl_inner:
            phase_fits.append(([row["phase"]], pfs))
        else:
            # wrap to two lines: circled number + rest
            parts = row["phase"].split(" ", 1)
            phase_fits.append((parts, max(pfs - 0.5, 4.5)))

    plt.close(_sf)

    # ── Step 3: compute row heights from wrapped line counts ─────────────────
    def row_height(ri):
        max_lines = max(len(box) for box in row_wrapped[ri])
        body_h = max_lines * LINE_H
        return PHASE_HDR + BOX_PAD_T + body_h + BOX_PAD_B + 2*BOX_VPAD + 2*ROW_VPAD

    N = len(ROWS)
    row_heights = [row_height(i) for i in range(N)]
    TOTAL_H = H_TITLE + sum(row_heights) + (N - 1) * H_ARR + H_LEG + f(0.01)

    # ── Step 4: build the final figure at correct height ─────────────────────
    fig_h_in = target_width_in * (TOTAL_H / W)
    fig, ax = plt.subplots(figsize=(target_width_in, fig_h_in))
    ax.set_xlim(0, W)
    ax.set_ylim(0, TOTAL_H)
    ax.set_aspect("auto")
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    def rrect(x, y, w, h, fc, ec, lw=1.2, z=2, r=None):
        r = r if r is not None else f(0.004)
        ax.add_patch(mpatches.FancyBboxPatch(
            (x, y), w, h,
            boxstyle=f"round,pad=0,rounding_size={r}",
            linewidth=lw, edgecolor=ec, facecolor=fc,
            zorder=z, clip_on=False))

    def frect(x, y, w, h, fc, z=3):
        ax.add_patch(plt.Polygon(
            [[x,y],[x+w,y],[x+w,y+h],[x,y+h]],
            closed=True, facecolor=fc, edgecolor="none", linewidth=0,
            zorder=z, clip_on=True))

    def T(x, y, s, fs=6.5, fw="normal", fc="#2c3e50",
          ha="center", va="center", fi="normal", ff=None, z=5):
        kw = dict(ha=ha, va=va, fontsize=fs, fontweight=fw,
                  color=fc, fontstyle=fi, zorder=z, clip_on=True)
        if ff: kw["fontfamily"] = ff
        ax.text(x, y, s, **kw)

    def yft(offset):
        return TOTAL_H - offset

    # ── Title block ───────────────────────────────────────────────────────────
    T(W/2, yft(f(0.009)),
      "Fig. 1.  Analytical framework for estimating India's tourism water footprint (TWF) across three study years",
      fs=FS_TITLE, fw="bold", fc="#1a2638")
    T(W/2, yft(f(0.022)),
      "2015–16 · 2019–20 · 2021–22   |   EEIO = Environmentally Extended IO   |   "
      "SDA = Structural Decomposition Analysis   |   HEM = Hypothetical Extraction   |   WSI = Water Stress Index",
      fs=FS_SUB, fc="#5a6a7a", fi="italic")

    y_off = H_TITLE

    # ── Phase rows ────────────────────────────────────────────────────────────
    for ri, row in enumerate(ROWS):
        rh    = row_heights[ri]
        c_bg  = row["c_bg"]
        c_brd = row["c_brd"]
        c_row = row["c_row"]
        boxes = row["boxes"]
        n_b   = len(boxes)

        r_top = yft(y_off)
        r_bot = r_top - rh

        # Row background
        rrect(MARGIN, r_bot + ROW_VPAD, W - 2*MARGIN, rh - 2*ROW_VPAD,
              fc=c_row, ec=c_brd, lw=1.8, z=1, r=f(0.005))

        # Label column box
        lx  = MARGIN + f(0.002)
        lw_ = LBL_W - f(0.002)
        rrect(lx, r_bot + ROW_VPAD + f(0.001), lw_, rh - 2*ROW_VPAD - f(0.002),
              fc=c_bg, ec=c_brd, lw=1.4, z=2, r=f(0.004))

        # Phase header strip
        strip_top = r_top - ROW_VPAD - f(0.001)
        frect(lx, strip_top - PHASE_HDR, lw_, PHASE_HDR, fc=c_brd, z=3)

        # Phase name — potentially two lines
        p_lines, p_fs = phase_fits[ri]
        mid_strip = strip_top - PHASE_HDR / 2
        if len(p_lines) == 1:
            T(lx + lw_/2, mid_strip, p_lines[0],
              fs=p_fs, fw="bold", fc="white", z=6)
        else:
            step = p_fs * f(0.0012) * 1.1
            for pi, pl in enumerate(p_lines):
                T(lx + lw_/2, mid_strip + step*(0.5 - pi),
                  pl, fs=p_fs, fw="bold", fc="white", z=6)

        # Gist lines in label column body
        gist = row["gist"]
        col_body_top = strip_top - PHASE_HDR
        col_body_bot = r_bot + ROW_VPAD + f(0.001)
        body_mid = (col_body_top + col_body_bot) / 2
        g_step   = LINE_H * 1.05
        g_start  = body_mid + (len(gist) - 1) * g_step / 2
        for gi, gl in enumerate(gist):
            T(lx + lw_/2, g_start - gi * g_step, gl,
              fs=FS_BODY + (0.4 if gi==0 else 0),
              fw="bold" if gi==0 else "normal",
              fc=c_brd if gi==0 else "#666",
              fi="italic" if gi>0 else "normal", z=5)

        # Detail boxes
        bw    = box_width(n_b)
        b_bot = r_bot + ROW_VPAD + BOX_VPAD
        b_top = r_top - ROW_VPAD - BOX_VPAD
        bh    = b_top - b_bot

        for bi, (btitle, _) in enumerate(boxes):
            bx = BOX_X0 + bi * (bw + BOX_GAP)

            rrect(bx, b_bot, bw, bh, fc="white", ec=c_brd, lw=0.9, z=3, r=f(0.003))
            frect(bx, b_top - BOX_HDR_H, bw, BOX_HDR_H, fc=c_bg, z=4)
            ax.plot([bx + BOX_PAD, bx + bw - BOX_PAD],
                    [b_top - BOX_HDR_H, b_top - BOX_HDR_H],
                    color=c_brd + "55", lw=0.6, zorder=4)

            tfs = row_title_fs[ri][bi]
            T(bx + bw/2, b_top - BOX_HDR_H/2,
              btitle, fs=tfs, fw="bold", fc=c_brd, z=6)

            expanded = row_wrapped[ri][bi]
            n_lines  = len(expanded)
            body_top = b_top - BOX_HDR_H - BOX_PAD_T
            body_bot = b_bot + BOX_PAD_B
            actual_h = body_top - body_bot
            step     = actual_h / max(n_lines, 1)

            for li, (sub, eq) in enumerate(expanded):
                T(bx + bw/2,
                  body_top - (li + 0.5) * step,
                  sub,
                  fs=FS_EQ if eq else FS_BODY,
                  fw="semibold" if eq else "normal",
                  fc="#1a3a5c" if eq else "#2c3e50",
                  ff="monospace" if eq else None,
                  z=6)

        y_off += rh

        # Arrow between rows
        if ri < N - 1:
            arr_top_y = yft(y_off)
            arr_bot_y = arr_top_y - H_ARR
            ax.annotate("",
                xy=(lx + lw_/2, arr_bot_y + f(0.004)),
                xytext=(lx + lw_/2, arr_top_y - f(0.003)),
                arrowprops=dict(
                    arrowstyle="->, head_width=0.38, head_length=0.55",
                    color="#5d7a8c", lw=1.5,
                ), zorder=8)
            y_off += H_ARR

    # ── Legend / key equations strip ─────────────────────────────────────────
    leg_top = yft(y_off + f(0.002))
    leg_bot = leg_top - H_LEG
    rrect(MARGIN, leg_bot, W - 2*MARGIN, H_LEG,
          fc="#f8f9fa", ec="#dce3ea", lw=0.9, z=1, r=f(0.004))

    T(MARGIN + f(0.015), (leg_top + leg_bot)/2,
      "KEY EQUATIONS:", fs=FS_BODY, fw="bold", fc="#333", ha="left", z=5)

    eq_x0  = MARGIN + f(0.150)
    slot_w = (W - 2*MARGIN - f(0.155)) / len(KEY_EQS)
    for ei, eq in enumerate(KEY_EQS):
        cx = eq_x0 + (ei + 0.5) * slot_w
        ax.text(cx, (leg_top + leg_bot)/2, eq,
                ha="center", va="center", fontsize=FS_EQ,
                fontweight="bold", color="#1a3a5c",
                fontfamily="monospace", zorder=6,
                bbox=dict(boxstyle="round,pad=0.28",
                          facecolor="#e8f0f8", edgecolor="#b8ccde", linewidth=0.7))

    plt.savefig(_VIS_DIR / "fig1_methodology_framework.png",
                dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    ok("Saved fig1_methodology_framework.png", log)


def fig2_diverging_bar(log=None):
    """
    The EEIO paradox made visual.
    LEFT  = where water physically originates (sum rows of pull matrix = source view).
    RIGHT = what tourists consumed (sum columns = demand-destination view).
    Same total, opposite reading direction.  One panel per study year.
    """
    section("Figure 2 — Double-Ended Diverging Bar", log=log)

    n = len(STUDY_YEARS)
    fig, axes = plt.subplots(n, 1, figsize=(11, 3.2 * n))
    if n == 1:
        axes = [axes]

    for ax, year in zip(axes, STUDY_YEARS):
        origin_df = _load_origin(year, log)
        cat_df    = _load(DIRS["indirect"] / f"indirect_twf_{year}_by_category.csv", log)

        # ── left: source-sector proportions ───────────────────────────────────
        sc, vc = _src_val_cols(origin_df)
        if not origin_df.empty and sc and vc:
            grp   = origin_df.groupby(sc)[vc].sum().sort_values(ascending=False)
            total = grp.sum()
            left  = {k: v / total for k, v in grp.items()} if total else {}
        else:
            left = {"Agriculture": 0.73, "Manufacturing": 0.11,
                    "Services": 0.09, "Mining": 0.04, "Other": 0.03}
            warn(f"{year}: origin data missing — using illustrative proportions", log)

        # ── right: demand-category proportions ────────────────────────────────
        if (not cat_df.empty and "Category_Type" in cat_df.columns
                and "Total_Water_m3" in cat_df.columns):
            grp2   = cat_df.groupby("Category_Type")["Total_Water_m3"].sum()
            total2 = grp2.sum()
            right  = {k: v / total2 for k, v in grp2.items()} if total2 else {}
        else:
            right = {"Agriculture": 0.65, "Food Mfg": 0.13,
                     "Services": 0.12, "Manufacturing": 0.10}

        # Sorted by share descending for visual clarity
        left_sorted  = sorted(left.items(),  key=lambda x: x[1], reverse=True)
        right_sorted = sorted(right.items(), key=lambda x: x[1], reverse=True)

        # Plot left bars (negative direction)
        x_cur = 0.0
        for i, (name, frac) in enumerate(left_sorted):
            c = _WONG[i % len(_WONG)]
            ax.barh(0, -frac, height=0.38, left=-x_cur, color=c, alpha=0.85,
                    edgecolor="white", linewidth=0.5)
            if frac > 0.05:
                ax.text(-x_cur - frac / 2, 0, f"{name[:10]}\n{100*frac:.0f}%",
                        ha="center", va="center", fontsize=6, color="white", fontweight="bold")
            x_cur += frac

        # Plot right bars (positive direction)
        x_cur = 0.0
        for i, (name, frac) in enumerate(right_sorted):
            c = _WONG[(i + 2) % len(_WONG)]
            ax.barh(0, frac, height=0.38, left=x_cur, color=c, alpha=0.85,
                    edgecolor="white", linewidth=0.5)
            if frac > 0.05:
                ax.text(x_cur + frac / 2, 0, f"{name[:13]}\n{100*frac:.0f}%",
                        ha="center", va="center", fontsize=6, color="white", fontweight="bold")
            x_cur += frac

        ax.axvline(0, color="black", linewidth=1.2)
        ax.set_xlim(-1.08, 1.08)
        ax.set_ylim(-0.5, 0.5)
        ax.set_yticks([])
        ax.set_xticks([-1, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1])
        ax.set_xticklabels(["100%", "75%", "50%", "25%", "0",
                             "25%", "50%", "75%", "100%"], fontsize=7)
        ax.set_title(
            f"{_YEAR_LABELS[year]}  |  ← Water source (upstream origin)  "
            f"|  Tourism consumption (destination) →", fontsize=9)
        ok(f"Panel {year} rendered", log)

    fig.text(0.25, 0.01, "← Where water physically comes from", ha="center",
             fontsize=8, color="dimgrey")
    fig.text(0.75, 0.01, "What tourism types consume →", ha="center",
             fontsize=8, color="dimgrey")
    fig.suptitle(
        "Figure 2 | EEIO Source vs Consumption View — Same Total Water, Opposite Perspectives",
        fontsize=10, fontweight="bold",
    )
    plt.tight_layout(rect=[0, 0.04, 1, 0.96])
    _save(fig, "fig2_diverging_bar.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 3 — PROPORTIONAL AREA BAR  (DOMESTIC vs INBOUND INTENSITY)  [was Fig 2]
# ══════════════════════════════════════════════════════════════════════════════

def fig3_proportional_area(log=None):
    """
    Bar width  = tourist-days (volume proxy for how many people).
    Bar height = L / tourist / day (intensity).
    Bar AREA   = total TWF for that segment.
    Domestic: wide + short.   Inbound: narrow + tall.
    3 year groups side-by-side.
    """
    section("Figure 3 — Proportional Area Bar (Domestic vs Inbound)", log=log)

    intensity_df = _load_intensity(log)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_xlabel("← Tourist volume (bar width = million tourist-days) →", fontsize=9)
    ax.set_ylabel("Water intensity (L / tourist / day)\n[Bar height = intensity]", fontsize=9)

    seg_colors = {"Domestic": _WONG[4], "Inbound": _WONG[5]}
    BAR_SCALE  = 0.014   # M tourist-days → plot width
    GAP        = 0.25    # gap between year groups

    x_cursor   = 0.0
    year_mids  = []

    for year in STUDY_YEARS:
        act       = ACTIVITY_DATA.get(year, {})
        dom_days  = act.get("domestic_tourists_M", 0) * act.get("avg_stay_days_dom", 2.5)
        inb_days  = act.get("inbound_tourists_M",  0) * act.get("avg_stay_days_inb", 8.0)
        segs      = [("Domestic", dom_days), ("Inbound", inb_days)]
        x_start   = x_cursor

        # intensity_df is WIDE format (one row per Year); columns are:
        #   L_per_dom_tourist_day, L_per_inb_tourist_day, Dom_days_M, Inb_days_M
        # There is NO "Segment" column — the old filter always returned empty,
        # so intensity was always 0 and bars had zero height (invisible).
        yr_row = (intensity_df[intensity_df["Year"].astype(str) == year].iloc[0]
                  if not intensity_df.empty and "Year" in intensity_df.columns
                  and not intensity_df[intensity_df["Year"].astype(str) == year].empty
                  else None)

        _col_map = {
            "Domestic": "L_per_dom_tourist_day",
            "Inbound":  "L_per_inb_tourist_day",
        }

        for seg, days_M in segs:
            intensity = 0.0
            if yr_row is not None:
                col_name = _col_map.get(seg, "L_per_tourist_day")
                intensity = float(yr_row.get(col_name, 0) or 0)
            width = max(days_M * BAR_SCALE, 0.05)

            ax.bar(x_cursor + width / 2, intensity, width=width,
                   color=seg_colors[seg], alpha=0.82,
                   edgecolor="white", linewidth=0.6)

            # Label inside (if bar is large enough)
            if intensity > 30 and width > 0.12:
                ax.text(x_cursor + width / 2, intensity * 0.5,
                        f"{seg[:3]}\n{days_M:.0f}M\n{intensity:,.0f} L",
                        ha="center", va="center", fontsize=6.5,
                        color="white", fontweight="bold")
            elif intensity > 0:
                ax.text(x_cursor + width / 2, intensity + max(intensity * 0.04, 10),
                        f"{seg[:3]}\n{intensity:,.0f}",
                        ha="center", va="bottom", fontsize=6.5,
                        color=seg_colors[seg])

            x_cursor += width + 0.02

        year_mids.append((x_start + x_cursor) / 2)
        x_cursor += GAP

    # Year labels between group brackets
    for x, lbl in zip(year_mids, [_YEAR_LABELS[yr] for yr in STUDY_YEARS]):
        ax.text(x, ax.get_ylim()[1] * 0.97, lbl,
                ha="center", va="top", fontsize=8.5, color="dimgrey")

    ax.set_xticks([])
    handles = [mpatches.Patch(color=seg_colors[s], label=s) for s in seg_colors]
    ax.legend(handles=handles, fontsize=8, loc="upper right")
    ax.text(0.01, 0.96,
            "Bar area  =  tourist-days × L/day  =  total water volume",
            transform=ax.transAxes, fontsize=8, va="top", color="dimgrey",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.75))

    fig.suptitle(
        "Figure 3 | Domestic vs Inbound Water Intensity — Area Encodes Total Volume",
        fontsize=10, fontweight="bold",
    )
    plt.tight_layout()
    _save(fig, "fig3_proportional_area.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 4 — ANNOTATED SDA WATERFALL  (COVID NARRATIVE)  [was Fig 3]
# ══════════════════════════════════════════════════════════════════════════════

def fig4_sda_waterfall(log=None):
    """
    SDA decomposition as a floating-bar waterfall readable by non-specialists.
    Baseline 2015 → W-effect (technology) → L-effect (structure) → Y-effect (demand)
    per period → lands at 2022 total.  COVID crash in dark-red.
    Guard: if SDA data is missing / years_have is empty, shows placeholder.
    """
    section("Figure 4 — Annotated SDA Waterfall (COVID Narrative)", log=log)

    sda      = _load_sda(log)
    indirect = _load_indirect_totals(log)
    direct   = _load_direct_totals(log)

    fig, ax = plt.subplots(figsize=(13, 6))

    # ── Guard: no SDA data ────────────────────────────────────────────────────
    years_have = [yr for yr in STUDY_YEARS if yr in indirect]
    if not sda or len(years_have) < 2:
        _ph(ax, "SDA data not available\n(run sda_mc step first)")
        fig.suptitle("Figure 4 | SDA Waterfall — Data Unavailable", fontsize=10)
        plt.tight_layout()
        _save(fig, "fig4_sda_waterfall.png", log)
        warn("SDA data missing — Figure 4 placeholder shown", log)
        return

    first_yr = years_have[0]
    last_yr  = years_have[-1]
    base_val = (indirect.get(first_yr, 0) + direct.get(first_yr, 0)) / 1e9

    # Build segments list: (x_label, bar_value, bar_bottom, color, is_total)
    segments = []
    segments.append((_YEAR_LABELS[first_yr], base_val, 0.0, _WONG[4], True))

    COVID_PERIODS = {"2019→2022", "2019-2022", "P2", "Period 2"}
    running = base_val

    for rec in sda:
        period   = str(rec.get("Period", ""))
        is_covid = any(cp in period for cp in COVID_PERIODS)
        # Normalise column names: SDA CSVs may use any of:
        #   W_Effect_bn_m3 / W_effect_m3 / dW_bn / w_effect_bn_m3 …
        # Build a case-insensitive alias map once per record.
        _rec_lower = {k.lower(): v for k, v in rec.items()}

        def _effect_val(short: str) -> float:
            """Extract effect value (always in bn m³) regardless of column convention."""
            for candidate in [
                f"{short}_Effect_bn_m3", f"{short}_effect_bn_m3",
                f"d{short}_bn", f"{short}_effect_m3", f"{short}_Effect_m3",
            ]:
                v = _rec_lower.get(candidate.lower())
                if v is not None and float(v) != 0:
                    raw = float(v)
                    # If column ends in _m3 (not _bn_m3), convert to bn
                    if candidate.lower().endswith("_m3") and not candidate.lower().endswith("_bn_m3"):
                        raw /= 1e9
                    return raw
            return 0.0

        for effect_key, effect_short in [
            ("W", "W"),
            ("L", "L"),
            ("Y", "Y"),
        ]:
            val = _effect_val(effect_key)
            if val == 0:
                continue
            if is_covid and effect_key == "Y_Effect_bn_m3":
                color = "#8B0000"
                lbl   = f"COVID\ndemand\ncrash"
            elif val < 0:
                color = _WONG[2]
                lbl   = f"{period}\n{effect_short}-effect"
            else:
                color = _WONG[5]
                lbl   = f"{period}\n{effect_short}-effect"
            bottom = running if val >= 0 else running + val
            segments.append((lbl, abs(val), bottom, color, False))
            running += val

    last_total = (indirect.get(last_yr, 0) + direct.get(last_yr, 0)) / 1e9
    segments.append((_YEAR_LABELS[last_yr], last_total, 0.0, _WONG[0], True))

    xs = np.arange(len(segments))

    for i, (lbl, bar_h, bottom, color, is_total) in enumerate(segments):
        ax.bar(i, bar_h, bottom=bottom, color=color, alpha=0.85, width=0.65,
               edgecolor="white", linewidth=0.6, zorder=3)

        # Value label inside bar — threshold reduced to 0.08 so near-cancellation
        # small bars still get labelled (was 0.04, now 0.08 guards very tiny bars)
        mid = bottom + bar_h / 2
        if bar_h > 0.08:
            signed = f"{bar_h:.2f}" if is_total else f"{bar_h:+.2f}"
            ax.text(i, mid, f"{signed}\nbn m³",
                    ha="center", va="center", fontsize=7,
                    color="white", fontweight="bold")

        # Connector line to next bar (running total)
        if i < len(segments) - 1 and not is_total:
            next_bottom = bottom + bar_h if not segments[i + 1][4] else 0
            ax.plot([i + 0.33, i + 0.67],
                    [bottom + bar_h, bottom + bar_h],
                    color="dimgrey", linewidth=0.9, linestyle="--",
                    alpha=0.55, zorder=2)

    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(xs)
    ax.set_xticklabels([s[0] for s in segments], fontsize=7.5)
    ax.set_ylabel("Total TWF (billion m³)", fontsize=10)

    legend_handles = [
        mpatches.Patch(color=_WONG[4], label="Baseline / Total"),
        mpatches.Patch(color=_WONG[2], label="Positive effect (↓ water)"),
        mpatches.Patch(color=_WONG[5], label="Negative effect (↑ water)"),
        mpatches.Patch(color="#8B0000", label="COVID demand crash"),
    ]
    ax.legend(handles=legend_handles, fontsize=7.5, loc="upper right")

    fig.suptitle(
        "Figure 4 | SDA Decomposition — W / L / Y Effects with COVID Narrative",
        fontsize=10, fontweight="bold",
    )
    plt.tight_layout()
    _save(fig, "fig4_sda_waterfall.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 5 — NESTED BAR WITH GHOST OVERLAY  [was Fig 4]
# ══════════════════════════════════════════════════════════════════════════════

def fig5_nested_bar_ghost(log=None):
    """
    Stacked bars for each study year, with a ghost (dashed outline) of the
    2015 bar sitting behind 2019 and 2022 — change is instantly visible.
    Sector composition inside bars.  Intensity dots on secondary y-axis.
    """
    section("Figure 5 — Nested Bar with Ghost Overlay", log=log)

    indirect = _load_indirect_totals(log)
    direct   = _load_direct_totals(log)
    intensity_df = _load_intensity(log)

    years_have = [yr for yr in STUDY_YEARS if yr in indirect]
    if not years_have:
        warn("No indirect data — Figure 4 skipped", log)
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    ax2     = ax.twinx()

    bar_w  = 0.55
    xs     = np.arange(len(years_have))
    labels = [_YEAR_LABELS[yr] for yr in years_have]

    SECTOR_ORDER  = ["Agriculture", "Food Mfg", "Manufacturing",
                     "Services", "Utilities", "Mining", "Other"]
    sector_colors = {s: _WONG[i % len(_WONG)] for i, s in enumerate(SECTOR_ORDER)}

    baseline_total = (indirect.get(years_have[0], 0) + direct.get(years_have[0], 0)) / 1e9

    for i, yr in enumerate(years_have):
        total_yr = (indirect.get(yr, 0) + direct.get(yr, 0)) / 1e9

        # Ghost outline of 2015 baseline behind later years
        if i > 0 and baseline_total > 0:
            ax.bar(i, baseline_total, width=bar_w + 0.10,
                   color="none",
                   edgecolor=_YEAR_COLORS[years_have[0]],
                   linewidth=1.6, linestyle="--", alpha=0.55, zorder=2)

        # Stacked sector breakdown
        cat_df = _load(DIRS["indirect"] / f"indirect_twf_{yr}_by_category.csv", log)
        bottom = 0.0

        if (not cat_df.empty and "Category_Type" in cat_df.columns
                and "Total_Water_m3" in cat_df.columns):
            grp = cat_df.groupby("Category_Type")["Total_Water_m3"].sum()
            for stype in SECTOR_ORDER:
                val = grp.get(stype, 0) / 1e9
                if val <= 0:
                    continue
                ax.bar(i, val, bottom=bottom, width=bar_w,
                       color=sector_colors[stype], alpha=0.85,
                       edgecolor="white", linewidth=0.4, zorder=3)
                if total_yr > 0 and val / total_yr > 0.07:
                    ax.text(i, bottom + val / 2,
                            f"{stype[:4]}\n{100*val/total_yr:.0f}%",
                            ha="center", va="center",
                            fontsize=5.5, color="white", fontweight="bold")
                bottom += val
        else:
            ind_bn = indirect.get(yr, 0) / 1e9
            dir_bn = direct.get(yr, 0) / 1e9
            ax.bar(i, ind_bn, width=bar_w, color=_WONG[4], alpha=0.85, zorder=3,
                   label="Indirect (EEIO)" if i == 0 else "")
            ax.bar(i, dir_bn, bottom=ind_bn, width=bar_w, color=_WONG[0], alpha=0.85,
                   zorder=3, label="Direct" if i == 0 else "")
            bottom = ind_bn + dir_bn

        ax.text(i, bottom + 0.04, f"{total_yr:.2f}\nbn m³",
                ha="center", va="bottom", fontsize=8, fontweight="bold")

    # Intensity dots on secondary axis
    for i, yr in enumerate(years_have):
        sub = (intensity_df[intensity_df["Year"].astype(str) == yr]
               if not intensity_df.empty else pd.DataFrame())
        if not sub.empty and "L_per_tourist_day" in sub.columns:
            v = float(sub["L_per_tourist_day"].iloc[0])
            ax2.plot(i, v, "D", color=_WONG[7], markersize=9, zorder=6)
            ax2.annotate(f"{v:,.0f} L/d", (i, v),
                         textcoords="offset points", xytext=(10, 4),
                         fontsize=7, color=_WONG[7])

    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Total TWF (billion m³)", fontsize=10)
    ax2.set_ylabel("Per-tourist intensity (L / tourist / day)",
                   fontsize=9, color=_WONG[7])
    ax2.tick_params(axis="y", colors=_WONG[7])
    ax2.spines["right"].set_visible(True)
    ax2.spines["right"].set_color(_WONG[7])

    handles = [mpatches.Patch(color=sector_colors.get(s, _WONG[7]), label=s)
               for s in SECTOR_ORDER]
    handles += [
        mpatches.Patch(color="none",
                       edgecolor=_YEAR_COLORS[years_have[0]],
                       linestyle="--", linewidth=1.5,
                       label=f"{_YEAR_LABELS[years_have[0]]} baseline (ghost)"),
        Line2D([0], [0], marker="D", color=_WONG[7],
               linewidth=0, markersize=8, label="L/tourist/day (right axis)"),
    ]
    ax.legend(handles=handles, fontsize=7, loc="upper right", ncol=2)

    fig.suptitle(
        "Figure 5 | Cross-Year TWF Volume: Sector Composition + 2015 Ghost + Intensity Dots",
        fontsize=10, fontweight="bold",
    )
    plt.tight_layout()
    _save(fig, "fig5_nested_bar_ghost.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 6 — FLOW STRIP (3-STAGE SANKEY)  [was Fig 5]
# ══════════════════════════════════════════════════════════════════════════════

def fig6_flow_strip(log=None):
    """
    3-column supply-chain reading left-to-right:
      Col 1 (x=0.0): Water source groups (stacked blocks)
      Col 2 (x=1.75): Tourism demand categories (stacked blocks)
    Bezier ribbons connect source to destination proportionally.
    One panel per study year.
    """
    section("Figure 6 — Flow Strip (Supply-Chain Sankey)", log=log)

    fig, axes = plt.subplots(1, len(STUDY_YEARS),
                              figsize=(5 * len(STUDY_YEARS), 7))
    if len(STUDY_YEARS) == 1:
        axes = [axes]

    def _ribbon(ax, x0, x1, y0_lo, y0_hi, y1_lo, y1_hi, color, alpha=0.22):
        t  = np.linspace(0, 1, 60)
        xt = x0 + t * (x1 - x0)
        # Cubic bezier with midpoint anchors for smooth "S" shape
        yt_hi = ((1-t)**3 * y0_hi + 3*(1-t)**2*t * y0_hi
                 + 3*(1-t)*t**2 * y1_hi + t**3 * y1_hi)
        yt_lo = ((1-t)**3 * y0_lo + 3*(1-t)**2*t * y0_lo
                 + 3*(1-t)*t**2 * y1_lo + t**3 * y1_lo)
        ax.fill_between(xt, yt_lo, yt_hi, color=color, alpha=alpha)

    for ax, year in zip(axes, STUDY_YEARS):
        origin_df = _load_origin(year, log)
        cat_df    = _load(DIRS["indirect"] / f"indirect_twf_{year}_by_category.csv", log)

        ax.set_xlim(0, 2)
        ax.set_ylim(0, 1)
        ax.axis("off")
        ax.set_title(_YEAR_LABELS[year], fontweight="bold", fontsize=9)

        # ── Left column: source proportions ───────────────────────────────────
        sc, vc = _src_val_cols(origin_df)
        if not origin_df.empty and sc and vc:
            src = origin_df.groupby(sc)[vc].sum().sort_values(ascending=False)
            src_frac = (src / src.sum()).to_dict()
        else:
            src_frac = {"Agriculture": 0.73, "Manufacturing": 0.12,
                        "Services": 0.09, "Other": 0.06}

        # ── Right column: destination proportions ─────────────────────────────
        if (not cat_df.empty and "Category_Type" in cat_df.columns
                and "Total_Water_m3" in cat_df.columns):
            dst = cat_df.groupby("Category_Type")["Total_Water_m3"].sum()
            dst = dst.sort_values(ascending=False)
            dst_frac = (dst / dst.sum()).to_dict()
        else:
            dst_frac = {"Agriculture": 0.68, "Food Mfg": 0.14,
                        "Services": 0.11, "Other": 0.07}

        # Build cumulative positions
        def _cum(frac_dict):
            pos = {}
            y = 1.0
            for k, v in sorted(frac_dict.items(), key=lambda x: x[1], reverse=True):
                h = max(v, 0.01)
                pos[k] = (y - h, y)
                y -= h
            return pos

        src_pos = _cum(src_frac)
        dst_pos = _cum(dst_frac)

        # Draw source blocks (left, x 0→0.28)
        for i, (name, (ylo, yhi)) in enumerate(src_pos.items()):
            c = _WONG[i % len(_WONG)]
            ax.fill_betweenx([ylo, yhi], 0, 0.28, color=c, alpha=0.85)
            if (yhi - ylo) > 0.04:
                ax.text(0.14, (ylo + yhi) / 2, str(name)[:10],
                        ha="center", va="center", fontsize=5.5,
                        color="white", fontweight="bold")

        # Draw destination blocks (right, x 1.72→2.0)
        for i, (name, (ylo, yhi)) in enumerate(dst_pos.items()):
            c = _WONG[(i + 3) % len(_WONG)]
            ax.fill_betweenx([ylo, yhi], 1.72, 2.0, color=c, alpha=0.85)
            if (yhi - ylo) > 0.04:
                ax.text(1.86, (ylo + yhi) / 2, str(name)[:12],
                        ha="center", va="center", fontsize=5.5,
                        color="white", fontweight="bold")

        # Draw ribbons: each source → each destination, proportional to product of shares
        for i_s, (s_name, (s_lo, s_hi)) in enumerate(src_pos.items()):
            s_h   = s_hi - s_lo
            s_col = _WONG[i_s % len(_WONG)]
            # Distribute this source band across all destinations
            d_cursor = s_hi
            for d_name, (d_lo, d_hi) in dst_pos.items():
                d_share   = dst_frac.get(d_name, 0)
                band_src  = s_h * d_share
                d_h       = d_hi - d_lo
                band_dst  = d_h * src_frac.get(s_name, 0)
                d_off     = (d_lo + d_h * (1 - src_frac.get(s_name, 0)) / 2)
                _ribbon(ax, 0.28, 1.72,
                        d_cursor - band_src, d_cursor,
                        d_off, d_off + band_dst,
                        s_col, alpha=0.18)
                d_cursor -= band_src

        ax.text(0.14, 1.03, "Source", ha="center", fontsize=8, fontweight="bold")
        ax.text(1.86, 1.03, "Tourism\nuse",  ha="center", fontsize=8, fontweight="bold")
        ok(f"Panel {year} — flow strip rendered", log)

    fig.suptitle(
        "Figure 6 | Supply-Chain Water Flow: Source Group → Tourism Demand Category",
        fontsize=10, fontweight="bold",
    )
    plt.tight_layout()
    _save(fig, "fig6_flow_strip.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 7 — STATE-LEVEL PRESSURE MAP  (WSI × TWF)
# ══════════════════════════════════════════════════════════════════════════════

# Placeholder state data — replace with actual MoT ITS 2022 + Aqueduct 4.0 state WSI
_STATE_DATA = {
    # state: (wsi_score 0–5, tourist_visit_share_pct)
    "Rajasthan":      (4.2, 8.1),
    "Uttar Pradesh":  (3.8, 14.2),
    "Delhi":          (4.5, 7.3),
    "Maharashtra":    (3.1, 9.8),
    "Tamil Nadu":     (2.9, 11.4),
    "Karnataka":      (2.6, 8.0),
    "Madhya Pradesh": (3.3, 5.9),
    "Gujarat":        (3.7, 4.4),
    "Kerala":         (1.8, 6.2),
    "Himachal Pradesh":(1.2, 2.1),
    "West Bengal":    (2.0, 4.5),
    "Goa":            (1.5, 3.8),
}
_STATE_COORDS = {
    "Rajasthan":      (26.5, 73.9), "Uttar Pradesh":  (27.0, 80.9),
    "Delhi":          (28.6, 77.2), "Maharashtra":    (19.7, 75.7),
    "Tamil Nadu":     (11.1, 78.7), "Karnataka":      (15.3, 75.7),
    "Madhya Pradesh": (22.9, 78.7), "Gujarat":        (22.3, 71.2),
    "Kerala":         (10.9, 76.3), "Himachal Pradesh":(32.1, 77.2),
    "West Bengal":    (22.6, 88.4), "Goa":            (15.3, 74.0),
}


def fig7_state_pressure_map(log=None):
    """
    State bubble chart (or geopandas map if shapefile present).
    Circle/bar size = TWF volume triggered by state's tourist share.
    Colour       = WRI Aqueduct 4.0 WSI water-stress score.
    """
    section("Figure 7 — State-Level Pressure Map (WSI × TWF)", log=log)

    indirect = _load_indirect_totals(log)
    direct   = _load_direct_totals(log)
    last_yr  = STUDY_YEARS[-1]
    total_bn = (indirect.get(last_yr, 0) + direct.get(last_yr, 0)) / 1e9

    state_twf = {s: d[1] / 100 * total_bn for s, d in _STATE_DATA.items()}

    cmap = plt.cm.RdYlBu_r
    norm = Normalize(vmin=1, vmax=5)

    # ── Try geopandas shapefile ───────────────────────────────────────────────
    shp = next(
        (p for p in [
            BASE_DIR / "0-raw-data" / "shapefiles" / "india_states.shp",
            BASE_DIR / "data" / "india_states.shp",
        ] if p.exists()),
        None,
    )
    try:
        import geopandas as gpd
        if shp:
            gdf = gpd.read_file(shp)
            fig, ax = plt.subplots(figsize=(8, 9))
            gdf.plot(ax=ax, color="#F5F5F5", edgecolor="#AAAAAA", linewidth=0.5)
            max_twf = max(state_twf.values()) if state_twf else 1
            for state, (wsi, _) in _STATE_DATA.items():
                lat, lon = _STATE_COORDS.get(state, (20, 78))
                size = max(state_twf[state] / max_twf * 1400, 25)
                ax.scatter(lon, lat, s=size, c=[[cmap(norm(wsi))]],
                           alpha=0.78, edgecolors="black", linewidth=0.4, zorder=5)
                if state_twf[state] > max_twf * 0.05:
                    ax.text(lon + 0.25, lat + 0.25, state[:6], fontsize=5, zorder=6)
            ax.set_axis_off()
            sm = cm.ScalarMappable(cmap=cmap, norm=norm)
            sm.set_array([])
            plt.colorbar(sm, ax=ax, label="WSI (1=low stress, 5=extreme)",
                         shrink=0.45, orientation="horizontal", pad=0.02)
            _finish_state_fig(fig, last_yr, log, use_map=True)
            return
    except ImportError:
        warn("geopandas unavailable — using bubble-bar fallback", log)

    # ── Fallback: bubble-bar chart sorted by risk (WSI × TWF) ────────────────
    states   = list(_STATE_DATA.keys())
    wsi_vals = np.array([_STATE_DATA[s][0] for s in states])
    twf_vals = np.array([state_twf[s]      for s in states])
    risk     = wsi_vals * twf_vals  # combined risk score
    order    = np.argsort(risk)[::-1]

    states   = [states[i] for i in order]
    wsi_vals = wsi_vals[order]
    twf_vals = twf_vals[order]

    fig, ax = plt.subplots(figsize=(11, 6))
    xs = np.arange(len(states))
    ax.bar(xs, twf_vals,
           color=[cmap(norm(w)) for w in wsi_vals],
           alpha=0.85, edgecolor="white", linewidth=0.5)

    for x, w, t in zip(xs, wsi_vals, twf_vals):
        ax.text(x, t + 0.001, f"WSI\n{w:.1f}",
                ha="center", va="bottom", fontsize=6, color="dimgrey")

    ax.set_xticks(xs)
    ax.set_xticklabels(states, rotation=38, ha="right", fontsize=7.5)
    ax.set_ylabel("Estimated TWF triggered by state's tourist share (bn m³)", fontsize=9)
    ax.set_xlabel("State  (sorted by WSI × TWF risk score; bar colour = water stress)",
                  fontsize=8)

    sm = cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    plt.colorbar(sm, ax=ax, label="WRI Aqueduct 4.0 WSI",
                 orientation="vertical", shrink=0.55)

    ax.text(0.01, 0.98,
            "⚠ Placeholder data — update with MoT ITS 2022 state shares\n"
            "  and WRI Aqueduct 4.0 state-level WSI before publication",
            transform=ax.transAxes, fontsize=7, va="top", color="darkorange",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.8))

    _finish_state_fig(fig, last_yr, log, use_map=False)


def _finish_state_fig(fig, last_yr, log, use_map=False):
    fig.suptitle(
        f"Figure 7 | State Water-Stress × Tourism TWF Pressure — {_YEAR_LABELS.get(last_yr, last_yr)}\n"
        "(colour = WRI Aqueduct 4.0 WSI; size/height = TWF volume)",
        fontsize=10, fontweight="bold",
    )
    plt.tight_layout()
    _save(fig, "fig7_state_pressure_map.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 7 — UNCERTAINTY STRIP  (MC + SENSITIVITY)
# ══════════════════════════════════════════════════════════════════════════════

def fig8_uncertainty_strip(log=None):
    """
    Stacked KDE density strips (one per study year).
    Each strip: filled KDE curve of MC totals + 90% CI shading.
    Vertical lines show LOW / BASE / HIGH sensitivity scenario values.
    Width of distribution visually encodes year-specific uncertainty.
    Guard: falls back to spike plot if scipy/MC data unavailable.
    """
    section("Figure 8 — Uncertainty Strip (MC + Sensitivity)", log=log)

    indirect = _load_indirect_totals(log)
    direct   = _load_direct_totals(log)

    n   = len(STUDY_YEARS)
    fig, axes = plt.subplots(n, 1, figsize=(10, 3.5 * n), sharex=False)
    if n == 1:
        axes = [axes]

    sc_styles = {
        "LOW":  ("#D55E00", "--", "LOW"),
        "BASE": ("#000000", "-",  "BASE"),
        "HIGH": ("#009E73", "--", "HIGH"),
    }

    for ax, year in zip(axes, STUDY_YEARS):
        mc        = _load_mc(year, log)
        base_tot  = (indirect.get(year, 0) + direct.get(year, 0)) / 1e9
        dir_base  = direct.get(year, 0)
        col       = _YEAR_COLORS[year]

        # Sensitivity scenarios
        sens_df  = _load(DIRS["indirect"] / f"indirect_twf_{year}_sensitivity.csv", log)
        scenarios = {}
        if not sens_df.empty and "Scenario" in sens_df.columns and "Total_Water_m3" in sens_df.columns:
            for sc in ("LOW", "BASE", "HIGH"):
                r = sens_df[sens_df["Scenario"] == sc]
                if not r.empty:
                    scenarios[sc] = (r["Total_Water_m3"].sum() + dir_base) / 1e9
        if "BASE" not in scenarios:
            scenarios["BASE"] = base_tot

        # ── KDE density strip ─────────────────────────────────────────────────
        if len(mc) >= 50 and _HAS_SCIPY:
            from scipy.stats import gaussian_kde
            kde     = gaussian_kde(mc, bw_method=0.15)
            x_lo    = max(0.0, mc.min() * 0.92)
            x_hi    = mc.max() * 1.06
            xs_kde  = np.linspace(x_lo, x_hi, 400)
            dens    = kde(xs_kde)
            dens    = dens / dens.max()

            ax.fill_between(xs_kde, 0, dens,
                             color=col, alpha=0.28, label="MC distribution")
            ax.plot(xs_kde, dens, color=col, linewidth=1.3)

            # 90% CI shading and bracket
            p5, p95 = np.percentile(mc, [5, 95])
            mask    = (xs_kde >= p5) & (xs_kde <= p95)
            ax.fill_between(xs_kde, 0, np.where(mask, dens, 0),
                             color=col, alpha=0.55,
                             label=f"90% CI: {p5:.2f}–{p95:.2f} bn m³")
            ax.annotate("", xy=(p95, -0.12), xytext=(p5, -0.12),
                        xycoords=("data", "axes fraction"),
                        textcoords=("data", "axes fraction"),
                        arrowprops=dict(arrowstyle="<->", color="black", lw=1.3))
            ax.text((p5 + p95) / 2, -0.22,
                    f"90% CI: {p95 - p5:.2f} bn m³",
                    ha="center", va="top", fontsize=7,
                    transform=ax.get_xaxis_transform())
        else:
            # Spike fallback
            ax.axvline(base_tot, color=col, linewidth=2.5,
                       label=f"Base total: {base_tot:.2f} bn m³")
            if not _HAS_SCIPY:
                warn(f"{year}: scipy not installed — KDE unavailable, spike shown", log)
            else:
                warn(f"{year}: <50 MC samples — density skipped, spike shown", log)

        # Scenario lines
        for sc, val in scenarios.items():
            style_col, ls, lbl = sc_styles.get(sc, (_WONG[1], "--", sc))
            ax.axvline(val, color=style_col, linewidth=1.8, linestyle=ls,
                       label=f"{lbl}: {val:.2f} bn m³")
            ax.text(val, 0.88, f"{sc}", ha="center", va="top",
                    fontsize=7, color=style_col,
                    transform=ax.get_xaxis_transform())

        ax.set_title(f"{_YEAR_LABELS[year]}  |  median: {np.median(mc):.2f} bn m³"
                     if len(mc) > 0 else _YEAR_LABELS[year],
                     fontsize=9, fontweight="bold")
        ax.set_ylabel("Relative density", fontsize=8)
        ax.set_xlabel("Total TWF (billion m³)", fontsize=8)
        ax.set_yticks([0, 0.5, 1.0])
        ax.legend(fontsize=7, loc="upper left")

    fig.suptitle(
        "Figure 8 | Monte Carlo Distribution with Sensitivity Scenario Markers",
        fontsize=10, fontweight="bold",
    )
    plt.tight_layout()
    _save(fig, "fig8_uncertainty_strip.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 8 — MULTI-STORY DASHBOARD  (6-panel overview)
# ══════════════════════════════════════════════════════════════════════════════

def fig9_multistory_dashboard(log=None):
    """
    6-panel publication dashboard summarising all key results in one figure:
      A (top-left)    Total TWF trend (indirect + direct stacked bars, all years)
      B (top-centre)  Per-tourist intensity trend (L/day by segment)
      C (top-right)   Agriculture upstream share doughnut (latest year)
      D (bottom-left) Scarce TWF trend (WSI-weighted blue water)
      E (bottom-centre) Inbound vs domestic ratio bar
      F (bottom-right) MC uncertainty range (base + 90% CI whisker)

    Each sub-panel has a _ph() guard that shows a grey placeholder if the
    required data file is absent, so the dashboard never crashes mid-pipeline.
    """
    section("Figure 9 — Multi-Story Dashboard", log=log)

    indirect  = _load_indirect_totals(log)
    direct    = _load_direct_totals(log)
    intensity = _load_intensity(log)
    last_yr   = STUDY_YEARS[-1]
    years_have = [yr for yr in STUDY_YEARS if yr in indirect]

    fig = plt.figure(figsize=(16, 9))
    gs  = gridspec.GridSpec(2, 3, figure=fig, hspace=0.42, wspace=0.38)
    axA = fig.add_subplot(gs[0, 0])
    axB = fig.add_subplot(gs[0, 1])
    axC = fig.add_subplot(gs[0, 2])
    axD = fig.add_subplot(gs[1, 0])
    axE = fig.add_subplot(gs[1, 1])
    axF = fig.add_subplot(gs[1, 2])

    xs = np.arange(len(years_have))
    labels = [_YEAR_LABELS[yr] for yr in years_have]

    # ── Panel A: Total TWF stacked bars ──────────────────────────────────────
    if years_have:
        ind_vals = [indirect.get(yr, 0) / 1e9 for yr in years_have]
        dir_vals = [direct.get(yr, 0)   / 1e9 for yr in years_have]
        axA.bar(xs, ind_vals, color=_WONG[4], alpha=0.85, label="Indirect (EEIO)")
        axA.bar(xs, dir_vals, bottom=ind_vals, color=_WONG[0], alpha=0.85, label="Direct")
        for i, (iv, dv) in enumerate(zip(ind_vals, dir_vals)):
            total = iv + dv
            axA.text(i, total + max(total * 0.02, 0.01), f"{total:.2f}",
                     ha="center", va="bottom", fontsize=7, fontweight="bold")
        axA.set_xticks(xs); axA.set_xticklabels(labels, fontsize=7, rotation=12)
        axA.set_ylabel("TWF (billion m³)", fontsize=8)
        axA.legend(fontsize=7, loc="upper right")
        axA.set_title("(A) Total TWF", fontsize=9, fontweight="bold")
        _panel_label(axA, "A")
    else:
        _ph(axA, "No indirect data")
        axA.set_title("(A) Total TWF", fontsize=9, fontweight="bold")

    # ── Panel B: Per-tourist intensity trend ─────────────────────────────────
    if not intensity.empty and "Year" in intensity.columns:
        for seg, col_name, color in [
            ("All",      "L_per_tourist_day",     _WONG[7]),
            ("Domestic", "L_per_dom_tourist_day",  _WONG[4]),
            ("Inbound",  "L_per_inb_tourist_day",  _WONG[5]),
        ]:
            vals = []
            for yr in years_have:
                r = intensity[intensity["Year"].astype(str) == yr]
                vals.append(float(r.iloc[0][col_name]) if not r.empty and col_name in r.columns else 0)
            axB.plot(xs, vals, marker="o", color=color, label=seg, linewidth=1.8, markersize=5)
        axB.set_xticks(xs); axB.set_xticklabels(labels, fontsize=7, rotation=12)
        axB.set_ylabel("L / tourist / day", fontsize=8)
        axB.legend(fontsize=7)
        axB.set_title("(B) Per-tourist intensity", fontsize=9, fontweight="bold")
        _panel_label(axB, "B")
    else:
        _ph(axB, "Intensity data unavailable\n(run compare step)")
        axB.set_title("(B) Per-tourist intensity", fontsize=9, fontweight="bold")

    # ── Panel C: Agriculture share doughnut (latest year) ────────────────────
    origin_last = _load_origin(last_yr, log)
    sc, vc = _src_val_cols(origin_last)
    if not origin_last.empty and sc and vc:
        grp = origin_last.groupby(sc)[vc].sum().sort_values(ascending=False)
        vals_c = grp.values
        lbls_c = [f"{k[:8]}\n{100*v/vals_c.sum():.0f}%" for k, v in grp.items()]
        wedges, _ = axC.pie(
            vals_c,
            labels=lbls_c,
            colors=[_WONG[i % len(_WONG)] for i in range(len(vals_c))],
            startangle=90,
            wedgeprops=dict(width=0.55, edgecolor="white", linewidth=0.8),
            textprops=dict(fontsize=6),
        )
        axC.set_title(f"(C) Upstream origin\n({_YEAR_LABELS[last_yr]})",
                      fontsize=9, fontweight="bold")
        _panel_label(axC, "C")
    else:
        _ph(axC, f"Origin data missing\nfor {last_yr}")
        axC.set_title("(C) Upstream origin", fontsize=9, fontweight="bold")

    # ── Panel D: Scarce TWF trend ─────────────────────────────────────────────
    all_yrs_df = _load(DIRS["indirect"] / "indirect_twf_all_years.csv", log)
    if not all_yrs_df.empty and "Scarce_TWF_billion_m3" in all_yrs_df.columns:
        scarce_vals = []
        for yr in years_have:
            r = all_yrs_df[all_yrs_df["Year"].astype(str) == yr]
            scarce_vals.append(float(r["Scarce_TWF_billion_m3"].iloc[0]) if not r.empty else 0)
        axD.bar(xs, scarce_vals, color=_WONG[5], alpha=0.82)
        for i, v in enumerate(scarce_vals):
            axD.text(i, v + max(v * 0.02, 0.005), f"{v:.3f}",
                     ha="center", va="bottom", fontsize=7)
        axD.set_xticks(xs); axD.set_xticklabels(labels, fontsize=7, rotation=12)
        axD.set_ylabel("Scarce TWF (billion m³)", fontsize=8)
        axD.set_title("(D) Scarce TWF (WSI-weighted)", fontsize=9, fontweight="bold")
        _panel_label(axD, "D")
        axD.text(0.02, 0.95, "Blue × WSI (Aqueduct 4.0)",
                 transform=axD.transAxes, fontsize=6.5, va="top", color="dimgrey")
    else:
        _ph(axD, "Scarce TWF data unavailable\n(run indirect_twf step)")
        axD.set_title("(D) Scarce TWF", fontsize=9, fontweight="bold")

    # ── Panel E: Inbound/domestic intensity ratio bar ─────────────────────────
    if not intensity.empty and "Year" in intensity.columns:
        ratios = []
        for yr in years_have:
            r = intensity[intensity["Year"].astype(str) == yr]
            if not r.empty:
                inb = float(r.iloc[0].get("L_per_inb_tourist_day", 0) or 0)
                dom = float(r.iloc[0].get("L_per_dom_tourist_day", 1) or 1)
                ratios.append(inb / dom if dom > 0 else 0)
            else:
                ratios.append(0)
        bars = axE.bar(xs, ratios,
                       color=[_YEAR_COLORS[yr] for yr in years_have], alpha=0.85)
        axE.axhline(1.0, color="black", linewidth=0.9, linestyle="--", alpha=0.5,
                    label="Ratio = 1 (equal intensity)")
        for bar, v in zip(bars, ratios):
            if v > 0:
                axE.text(bar.get_x() + bar.get_width() / 2,
                         v + max(v * 0.02, 0.1),
                         f"{v:.1f}×", ha="center", va="bottom", fontsize=8, fontweight="bold")
        axE.set_xticks(xs); axE.set_xticklabels(labels, fontsize=7, rotation=12)
        axE.set_ylabel("Inbound / domestic intensity ratio", fontsize=8)
        axE.legend(fontsize=7)
        axE.set_title("(E) Inbound/domestic intensity ratio", fontsize=9, fontweight="bold")
        _panel_label(axE, "E")
    else:
        _ph(axE, "Intensity ratio data unavailable")
        axE.set_title("(E) Inbound/domestic ratio", fontsize=9, fontweight="bold")

    # ── Panel F: MC 90% CI whisker chart ─────────────────────────────────────
    mc_sum = _load(DIRS["monte_carlo"] / "mc_summary_all_years.csv", log)
    if not mc_sum.empty and "Base_bn_m3" in mc_sum.columns:
        mc_xs = np.arange(len(years_have))
        for i, yr in enumerate(years_have):
            r = mc_sum[mc_sum["Year"].astype(str) == yr]
            if r.empty:
                continue
            base = float(r["Base_bn_m3"].iloc[0])
            p5   = float(r["P5_bn_m3"].iloc[0])
            p95  = float(r["P95_bn_m3"].iloc[0])
            axF.bar(i, base, color=_YEAR_COLORS[yr], alpha=0.80, width=0.5)
            axF.errorbar(i, base, yerr=[[base - p5], [p95 - base]],
                         fmt="none", color="black", capsize=5, linewidth=1.5)
            axF.text(i, p95 + max(p95 * 0.02, 0.01),
                     f"±{100*(p95-p5)/(2*base):.0f}%\nhalf-CI",
                     ha="center", va="bottom", fontsize=6.5)
        axF.set_xticks(mc_xs); axF.set_xticklabels(labels, fontsize=7, rotation=12)
        axF.set_ylabel("Total TWF (billion m³)", fontsize=8)
        axF.set_title("(F) MC uncertainty (90% CI whiskers)", fontsize=9, fontweight="bold")
        _panel_label(axF, "F")
        axF.text(0.02, 0.95, "σ = 0.30 log-normal (agr. coeff.)\nBiemans et al. 2011",
                 transform=axF.transAxes, fontsize=6, va="top", color="dimgrey")
    else:
        _ph(axF, "MC results unavailable\n(run sda_mc step)")
        axF.set_title("(F) MC uncertainty", fontsize=9, fontweight="bold")

    fig.suptitle(
        "Figure 9 | India Tourism Water Footprint — Key Results Dashboard",
        fontsize=11, fontweight="bold", y=1.01,
    )
    _save(fig, "fig9_multistory_dashboard.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 9 — BLUE vs BLUE + GREEN COMPARISON
# ══════════════════════════════════════════════════════════════════════════════

def fig10_blue_green_comparison(log=None):
    """
    Side-by-side grouped bars comparing:
      - Blue indirect TWF  (EEIO W×L×Y, surface + groundwater)
      - Green indirect TWF (rainfall evapotranspiration via supply chain)
      - Blue + Green total indirect TWF

    One group of 3 bars per study year. Stacked variant on the right panel
    shows the composition of Blue+Green by upstream source group.

    Guard: if Green_TWF_billion_m3 column is absent in indirect_twf_all_years.csv
    (old pipeline run without the fix), shows a clear placeholder message
    directing user to re-run calculate_indirect_twf.py.
    """
    section("Figure 10 — Blue vs Blue+Green Indirect TWF", log=log)

    all_yrs_df = _load(DIRS["indirect"] / "indirect_twf_all_years.csv", log)
    last_yr    = STUDY_YEARS[-1]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    has_green = (
        not all_yrs_df.empty
        and "Green_TWF_billion_m3" in all_yrs_df.columns
        and all_yrs_df["Green_TWF_billion_m3"].sum() > 0
    )

    years_have = (
        [yr for yr in STUDY_YEARS
         if not all_yrs_df[all_yrs_df["Year"].astype(str) == yr].empty]
        if not all_yrs_df.empty and "Year" in all_yrs_df.columns
        else []
    )
    xs = np.arange(len(years_have))
    labels = [_YEAR_LABELS[yr] for yr in years_have]

    # ── Left panel: grouped bars ──────────────────────────────────────────────
    if not years_have or all_yrs_df.empty:
        _ph(ax1, "indirect_twf_all_years.csv missing\nRun indirect_twf step first")
        _ph(ax2, "Data unavailable")
        fig.suptitle("Figure 10 | Blue vs Blue+Green — Data Unavailable", fontsize=10)
        plt.tight_layout()
        _save(fig, "fig10_blue_green_comparison.png", log)
        return

    if not has_green:
        _ph(ax1,
            "Green_TWF_billion_m3 column absent.\n"
            "Re-run calculate_indirect_twf.py\n"
            "(fix adds green EEIO columns to all_years CSV)")
        _ph(ax2,
            "Green water data unavailable.\n"
            "Blue-only TWF shown in Fig 4.")
        warn("Figure 10: Green_TWF_billion_m3 absent — showing placeholder", log)
        fig.suptitle("Figure 10 | Blue vs Blue+Green — Green Data Unavailable", fontsize=10)
        plt.tight_layout()
        _save(fig, "fig10_blue_green_comparison.png", log)
        return

    blue_vals   = []
    green_vals  = []
    bg_vals     = []

    for yr in years_have:
        r = all_yrs_df[all_yrs_df["Year"].astype(str) == yr].iloc[0]
        b  = float(r.get("Indirect_TWF_billion_m3", 0))
        g  = float(r.get("Green_TWF_billion_m3",    0))
        bg = float(r.get("Blue_plus_Green_TWF_billion_m3", b + g))
        if bg == 0:
            bg = b + g
        blue_vals.append(b)
        green_vals.append(g)
        bg_vals.append(bg)

    bar_w = 0.22
    ax1.bar(xs - bar_w, blue_vals,  width=bar_w, color=_WONG[4],  alpha=0.85, label="Blue (EEIO)")
    ax1.bar(xs,          green_vals, width=bar_w, color=_WONG[2],  alpha=0.85, label="Green (EEIO)")
    ax1.bar(xs + bar_w, bg_vals,    width=bar_w, color=_WONG[0],  alpha=0.85, label="Blue + Green")

    for i, (b, g, bg) in enumerate(zip(blue_vals, green_vals, bg_vals)):
        for x_off, val, col in [(-bar_w, b, _WONG[4]), (0, g, _WONG[2]), (bar_w, bg, _WONG[0])]:
            if val > 0:
                ax1.text(xs[i] + x_off, val + max(val * 0.02, 0.05),
                         f"{val:.2f}", ha="center", va="bottom", fontsize=6.5, color=col)

    ax1.set_xticks(xs); ax1.set_xticklabels(labels, fontsize=8)
    ax1.set_ylabel("Indirect TWF (billion m³)", fontsize=9)
    ax1.legend(fontsize=8)
    ax1.set_title("Blue vs Green vs Blue+Green Indirect TWF", fontsize=9, fontweight="bold")
    ax1.text(0.01, 0.98,
             "Blue  = surface + groundwater (EEIO W×L×Y)\n"
             "Green = rainfall in rainfed crop supply chains\n"
             "Headline metric: blue only (cross-study compatibility)",
             transform=ax1.transAxes, fontsize=7, va="top",
             bbox=dict(boxstyle="round,pad=0.35", facecolor="lightyellow", alpha=0.8))

    # ── Right panel: stacked green share by source group (latest year) ────────
    origin_last = _load_origin(last_yr, log)
    if (not origin_last.empty
            and "Source_Group" in origin_last.columns
            and "Green_Water_m3" in origin_last.columns
            and origin_last["Green_Water_m3"].sum() > 0):

        grps     = origin_last["Source_Group"].tolist()
        blues    = origin_last["Water_m3"].tolist()     if "Water_m3"     in origin_last else [0]*len(grps)
        greens   = origin_last["Green_Water_m3"].tolist()
        x2       = np.arange(len(grps))
        ax2.bar(x2, blues,  color=_WONG[4], alpha=0.85, label="Blue")
        ax2.bar(x2, greens, bottom=blues, color=_WONG[2], alpha=0.85, label="Green")

        for i, (b, g) in enumerate(zip(blues, greens)):
            tot = b + g
            if tot > 0 and g > 0:
                ax2.text(i, tot + max(tot * 0.02, 0.005),
                         f"{100*g/tot:.0f}%\ngreen",
                         ha="center", va="bottom", fontsize=6.5, color=_WONG[2])
        ax2.set_xticks(x2)
        ax2.set_xticklabels([g[:12] for g in grps], rotation=30, ha="right", fontsize=7.5)
        ax2.set_ylabel("Water (m³)", fontsize=9)
        ax2.legend(fontsize=8)
        ax2.set_title(
            f"Blue vs Green by Upstream Source Group\n({_YEAR_LABELS[last_yr]})",
            fontsize=9, fontweight="bold",
        )
        # Annotate agriculture dominance of green
        agr_row = origin_last[origin_last["Source_Group"].str.lower().str.startswith("agr")]
        if not agr_row.empty:
            agr_g = float(agr_row.iloc[0].get("Green_Water_m3", 0))
            tot_g = sum(greens)
            if tot_g > 0:
                ax2.text(0.02, 0.97,
                         f"Agriculture = {100*agr_g/tot_g:.0f}% of total green TWF\n"
                         "(rainfed crops dominate)",
                         transform=ax2.transAxes, fontsize=7, va="top",
                         bbox=dict(boxstyle="round,pad=0.35", facecolor="honeydew", alpha=0.85))
    else:
        _ph(ax2,
            f"Green_Water_m3 absent in\nindirect_twf_{last_yr}_origin.csv\n"
            "Re-run calculate_indirect_twf.py")
        ax2.set_title("Blue vs Green by Source Group", fontsize=9, fontweight="bold")

    fig.suptitle(
        "Figure 10 | Blue vs Blue+Green Indirect TWF — Full Hydrological Disclosure",
        fontsize=10, fontweight="bold",
    )
    plt.tight_layout()
    _save(fig, "fig10_blue_green_comparison.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def run(**kwargs):
    log_dir = DIRS["logs"] / "visualise"
    with Logger("visualise_results", log_dir) as log:
        t = Timer()
        log.section("GENERATE PUBLICATION FIGURES (10 charts: Fig 1 = methodology framework)")
        log.info(f"Output directory: {_VIS_DIR}")
        _VIS_DIR.mkdir(parents=True, exist_ok=True)

        figures = [
            ("Figure 1  — Analytical framework (methodology diagram)",      fig1_methodology_framework),
            ("Figure 2  — Diverging bar (source ↔ consumption)",            fig2_diverging_bar),
            ("Figure 3  — Proportional area (domestic vs inbound)",         fig3_proportional_area),
            ("Figure 4  — SDA waterfall (COVID narrative)",                 fig4_sda_waterfall),
            ("Figure 5  — Nested bar with ghost overlay",                   fig5_nested_bar_ghost),
            ("Figure 6  — Flow strip (supply-chain Sankey)",                fig6_flow_strip),
            ("Figure 7  — State-level pressure map (WSI × TWF)",           fig7_state_pressure_map),
            ("Figure 8  — Uncertainty strip (MC + sensitivity)",            fig8_uncertainty_strip),
            ("Figure 9  — Multi-story dashboard (6-panel overview)",        fig9_multistory_dashboard),
            ("Figure 10 — Blue vs Blue+Green comparison (green disclosure)", fig10_blue_green_comparison),
        ]

        success = []
        for label, fn in figures:
            try:
                fn(log)
                success.append(label)
            except Exception as e:
                log.warn(f"{label} — ERROR: {e}")
                import traceback
                log.info(traceback.format_exc())

        log.section("Figure generation summary")
        log.ok(f"{len(success)}/{len(figures)} figures completed in {t.elapsed()}")
        for s in success:
            log.ok(s)
        for label, _ in figures:
            if label not in success:
                log.warn(f"FAILED: {label}")


if __name__ == "__main__":
    run()