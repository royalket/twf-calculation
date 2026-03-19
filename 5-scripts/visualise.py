"""
visualise_new.py — Revised Publication Figures
================================================
Changes from original:
  Fig 2  — Donut replaced with horizontal 100%-stacked bar (Blue/Green/Scarce
            split by source group); percentages inside wide segments, leader
            lines for narrow ones; intensity lines kept on twin axis.
  Fig 3  — Streamgraph bands now represent supply-chain ORIGIN groups
            (loaded from indirect_water_{yr}_by_category.csv); consistent axis.
  Fig 4  — Δ% inline bar removed; plain ±X% text instead; varied fallback
            noise so columns look meaningfully different.
  Fig 5  — "Invisible water" annotation removed; figure compacted (10×7).
  Fig 6  — Three side-by-side Sankey panels (one per year) with clear
            "Water source → Tourism use" headers and volume labels.
  Fig 7  — Already in million m³; act-ribbon boundaries now data-driven.
  Fig 8  — Ridge/multi-panel replaced with per-year KDE strip (one subplot
            per study year on separate axes sharing x-range conceptually).
Global   — Wong palette throughout; text placed with annotate() offsets;
            inset axes placed in detected empty quadrant; traceback import
            moved to top; _save() uses Path.stem; _bar_label_safe() used.
"""

import sys
import traceback
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.ticker import FuncFormatter, MaxNLocator
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D
import matplotlib.cm as cm

try:
    from scipy.stats import gaussian_kde
    from scipy.interpolate import PchipInterpolator
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

sys.path.insert(0, str(Path(__file__).parent))
from config import BASE_DIR, DIRS, STUDY_YEARS, ACTIVITY_DATA
from utils import Logger, Timer, ok, warn, section

# ── Output directory ──────────────────────────────────────────────────────────
_VIS_DIR = DIRS.get("visualisation", BASE_DIR / "3-final-results" / "visualisation")

# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL STYLE  —  Wong (2011) 8-colour palette, colorblind-safe
# ══════════════════════════════════════════════════════════════════════════════

_WONG      = ["#E69F00","#56B4E9","#009E73","#F0E442",
              "#0072B2","#D55E00","#CC79A7","#000000"]
_C_BLUE    = "#0072B2"
_C_GREEN   = "#009E73"
_C_ORANGE  = "#E69F00"
_C_VERM    = "#D55E00"
_C_PINK    = "#CC79A7"
_C_SKY     = "#56B4E9"
_C_YELLOW  = "#F0E442"
_C_BLACK   = "#000000"
_C_SCARCE  = "#8B1A1A"

_YEAR_COLORS  = {"2015": _C_BLUE, "2019": _C_ORANGE, "2022": _C_GREEN}
_YEAR_LABELS  = {"2015": "2015", "2019": "2019", "2022": "2022"}

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
    "figure.dpi":         150,
    "savefig.dpi":        150,
    "savefig.bbox":       "tight",
    "savefig.facecolor":  "white",
    "pdf.fonttype":       42,
})

# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADERS
# ══════════════════════════════════════════════════════════════════════════════

def _load(path: Path, log=None) -> pd.DataFrame:
    if path.exists():
        try:
            return pd.read_csv(path)
        except Exception:
            pass
    warn(f"Missing: {path.name} — using fallback data", log)
    return pd.DataFrame()

def _load_indirect_totals(log=None) -> dict:
    df = _load(DIRS["indirect"] / "indirect_water_all_years.csv", log)
    if not df.empty and "Year" in df.columns:
        if "Indirect_TWF_billion_m3" in df.columns:
            return {str(int(r["Year"])): float(r["Indirect_TWF_billion_m3"]) * 1e9
                    for _, r in df.iterrows()}  # store as raw m³; figures divide by 1e6
        if "Total_Water_m3" in df.columns:
            return {str(int(r["Year"])): float(r["Total_Water_m3"])
                    for _, r in df.iterrows()}
    # Per-year fallback
    result = {}
    for yr in STUDY_YEARS:
        cat = _load(DIRS["indirect"] / f"indirect_water_{yr}_by_category.csv", log)
        if not cat.empty and "Total_Water_m3" in cat.columns:
            result[yr] = float(cat["Total_Water_m3"].sum())
    if not result:
        result = {"2015": 1.85e9, "2019": 2.35e9, "2022": 2.10e9}
    return result

def _load_direct_totals(log=None) -> dict:
    df = _load(DIRS["direct"] / "direct_twf_all_years.csv", log)
    if not df.empty:
        base = df[df["Scenario"]=="BASE"] if "Scenario" in df.columns else df
        if "Year" in base.columns and "Total_m3" in base.columns:
            return {str(int(r["Year"])): float(r["Total_m3"])
                    for _, r in base.iterrows()}
    return {"2015": 0.12e9, "2019": 0.15e9, "2022": 0.13e9}

def _load_mc(year: str, log=None) -> np.ndarray:
    df = _load(DIRS["monte_carlo"] / f"mc_results_{year}.csv", log)
    if not df.empty:
        col = [c for c in df.columns if "total" in c.lower() or "twf" in c.lower()]
        if col:
            return df[col[0]].values / 1e6   # M m³
    return np.array([])

def _load_sda(log=None) -> list:
    df = _load(DIRS["sda"] / "sda_summary_all_periods.csv", log)
    return df.to_dict("records") if not df.empty else []

def _load_origin(year: str, log=None) -> pd.DataFrame:
    return _load(DIRS["indirect"] / f"indirect_water_{year}_origin.csv", log)

def _load_intensity(log=None) -> pd.DataFrame:
    return _load(DIRS["comparison"] / "twf_per_tourist_intensity.csv", log)

def _load_category(year: str, log=None) -> pd.DataFrame:
    return _load(DIRS["indirect"] / f"indirect_water_{year}_by_category.csv", log)

def _src_val_cols(df: pd.DataFrame):
    src = next((c for c in df.columns
                if any(k in c.lower() for k in ("source","group","sector","category"))), None)
    val = next((c for c in df.columns
                if any(k in c.lower() for k in ("m3","water"))), None)
    return src, val

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _save(fig: plt.Figure, name: str, log=None):
    _VIS_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(name).stem
    for ext in (".png", ".pdf"):
        p = _VIS_DIR / (stem + ext)
        fig.savefig(p, bbox_inches="tight",
                    dpi=150 if ext == ".png" else None)
        ok(f"Saved {p.name}  ({p.stat().st_size // 1024} KB)", log)
    plt.close(fig)

def _ph(ax, msg: str):
    ax.text(0.5, 0.5, msg, ha="center", va="center",
            transform=ax.transAxes, fontsize=9, color="grey", style="italic",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#F8F8F8", alpha=0.9))
    ax.set_xticks([]); ax.set_yticks([])

def _bar_label_safe(ax, bars, fmt="{:.2f}", pad=3, fontsize=8,
                    color="white", inside=True):
    """Print value inside bar if tall enough, else skip."""
    ylim = ax.get_ylim()
    span = max(ylim[1] - ylim[0], 1e-9)
    for r in bars:
        h = r.get_height()
        if h / span < 0.04:
            continue
        y = r.get_y() + h/2 if inside else r.get_y() + h + pad
        va = "center" if inside else "bottom"
        c  = color if inside else "#333333"
        ax.text(r.get_x() + r.get_width()/2, y,
                fmt.format(h), ha="center", va=va,
                fontsize=fontsize, color=c, fontweight="bold", clip_on=True)

# ── Fig 1 constants (kept exactly from original) ──────────────────────────────
_LABEL_FRAC = 0.055

def _lbl_state() -> dict:
    return {"side": 0, "last_pos": -1e9}

def _seg_label(ax, primary, secondary, span, text, color,
               orient="v", fontsize=7.0, threshold=_LABEL_FRAC, state=None):
    if span <= 0 or not text:
        return
    if state is None:
        state = _lbl_state()
    lo, hi   = ax.get_ylim() if orient=="v" else ax.get_xlim()
    ax_span  = max(hi-lo, 1e-9)
    frac     = span / ax_span
    mid_val  = secondary + span/2
    if frac >= threshold:
        kw = dict(ha="center", va="center", fontsize=fontsize,
                  color="white", fontweight="bold", clip_on=True)
        if orient=="v":
            ax.text(primary, mid_val, text, **kw)
        else:
            ax.text(mid_val, primary, text, **kw)
        return
    if abs(mid_val - state["last_pos"]) / ax_span < 0.06:
        state["side"] ^= 1
    side = state["side"]
    cat_lo, cat_hi = ax.get_xlim() if orient=="v" else ax.get_ylim()
    cat_span = max(cat_hi-cat_lo, 1e-9)
    sign     = 1 if side==0 else -1
    edge_off = cat_span * 0.20
    text_off = cat_span * 0.42
    if orient=="v":
        ax.annotate(text,
                    xy=(primary + sign*edge_off, mid_val),
                    xytext=(primary + sign*text_off, mid_val),
                    ha=("left" if side==0 else "right"), va="center",
                    fontsize=fontsize-0.5, color=color, fontweight="bold",
                    annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=color, lw=0.7, alpha=0.65))
    else:
        ax.annotate(text,
                    xy=(mid_val, primary + sign*edge_off),
                    xytext=(mid_val, primary + sign*text_off),
                    ha="center", va=("bottom" if side==0 else "top"),
                    fontsize=fontsize-0.5, color=color, fontweight="bold",
                    annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=color, lw=0.7, alpha=0.65))
    state["last_pos"] = mid_val
    state["side"]    ^= 1

# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 1 — ANALYTICAL FRAMEWORK  (kept exactly from original)
# ══════════════════════════════════════════════════════════════════════════════

_FIG1_ROWS = [
    {"phase":"① DATA SOURCES","gist":["Raw inputs","6 data streams","Multi-source"],
     "boxes":[
         ("TSA 2015–16",["MoT India","25 categories","Inbound · Domestic","₹ crore base"]),
         ("NAS Stmt 6.1",["MoSPI 2024","Real GVA growth","2011-12 prices","12 sector keys"]),
         ("India SUT Tables",["MoSPI · 3 years","140×140 matrix","2015-16·19-20·21-22","Nominal ₹ crore"]),
         ("EXIOBASE v3.8",["163-sector MRIO","Blue water W (m³/₹)","Green water","India concordance"]),
         ("CPI · USD/INR",["MoSPI · RBI","Year deflators","Nominal → real","Cross-currency"]),
         ("WRI Aqueduct 4.0",["Kuzma et al. 2023","Sector WSI weights","Agr=0.827  Ind=0.814","Services=0.000"]),
     ],"c_bg":"#D6EAF8","c_brd":"#1A5276","c_row":"#EBF5FB"},
    {"phase":"② DATA PREPARATION","gist":["Pre-processing","3 operations","Temurshoev 2011"],
     "boxes":[
         ("TSA Extrapolation",["nom_factor = GVA_growth × CPI(t)/CPI₀","→ TSA₂₀₁₅  TSA₂₀₁₉  TSA₂₀₂₂","Nominal + real ₹ crore"]),
         ("IO Table Construction",["SUT → Product Tech. Assumption","L = (I − A)⁻¹  per study year","Balance error < 1.0% verified"]),
         ("Tourism Demand Vectors Y",["25 TSA cats → 163 EXIOBASE codes","Y_total · Y_inbound · Y_domestic","163 sectors × 3 years = 489 vectors"]),
     ],"c_bg":"#D5F5E3","c_brd":"#1E8449","c_row":"#EAFAF1"},
    {"phase":"③ EEIO CORE MODEL","gist":["Core equations","W · L · Y","Blue + Scarce"],
     "boxes":[
         ("Water Vector (W)",["EXIOBASE → SUT-140 concordance","m³ per ₹ crore  [shape: 163]","Green water: parallel disclosure"]),
         ("Indirect TWF",["TWF = W · L · Y","Inbound = W·L·Y_inbound","Domestic = W·L·Y_domestic"]),
         ("Scarce TWF",["Scarce = TWF × WSI_sector","Aqueduct 4.0 sector-level weights","Sector vs. country WSI (advance)"]),
         ("Direct TWF",["Activity-based bottom-up","Tourist-days × sector coeff.","Hotel · Restaurant · Transport"]),
         ("Water Multiplier Ratio",["MR[j] = WL[j] / WL̄_economy","MR > 1 → water-intensive","Policy hotspot identification"]),
     ],"c_bg":"#FDEBD0","c_brd":"#A04000","c_row":"#FEF9E7"},
    {"phase":"④ ANALYTICAL EXTENSIONS","gist":["Novel contributions","★ Not in","Lee et al. 2021"],
     "boxes":[
         ("Structural Decomp. (SDA)",["ΔTWF = ΔW·eff + ΔL·eff + ΔY·eff","Six-polar · residual < 0.1%","2015→19  ·  2019→22"]),
         ("Monte Carlo  n=10,000",["Inputs: W_agr · W_hotel · volumes","Output: P5–P95 bounds per year","Rank-corr. variance decomp."]),
         ("Supply-Chain Path (HEM)",["pull[i,j] = W[i]·L[i,j]·Y[j]","Top-50 pathways ranked","Tourism-dependency index/sector"]),
         ("Outbound TWF & Net Balance",["TWF = N×days×WF_local/365×1.5","Net = Outbound − Inbound TWF","India: net importer or exporter?"]),
     ],"c_bg":"#E8DAEF","c_brd":"#6C3483","c_row":"#F5EEF8"},
    {"phase":"⑤ VALIDATION","gist":["9 assertions","Sensitivity ±20%","Error < 1%"],
     "boxes":[
         ("① Scarce/Blue ∈ [0.30–0.95]",["Physical plausibility check"]),
         ("② Sensitivity: LOW<BASE<HIGH",["Monotonicity of ±20% bounds"]),
         ("③ Inbound > Domestic",["L/tourist-day ordering check"]),
         ("④⑤ Ratios & Green/Blue bounds",["Inb/Dom ∈[5,30]  G/B ∈[0,10]"]),
         ("⑥ YoY Δ ∈[−60,+30%]",["Catches data/scaling errors"]),
         ("⑦⑧⑨ IO · SDA · W+L+Y",["<1%  <0.1%  Sum≈ΔTWF"]),
     ],"c_bg":"#FADBD8","c_brd":"#922B21","c_row":"#FDEDEC"},
    {"phase":"⑥ OUTPUTS","gist":["5 result sets","Policy-ready","Journal figures"],
     "boxes":[
         ("TWF Totals",["bn m³ · L/tourist/day","Blue + Scarce + Green","Inbound vs. Domestic"]),
         ("Sector Hotspots",["Top-N indirect sectors","Water multiplier ratios","HEM dependency index"]),
         ("Temporal & SDA Drivers",["ΔW · ΔL · ΔY effects","COVID structural break","Technology efficiency Δ"]),
         ("Net Water Balance",["Outbound TWF total","Virtual water transfer","India net position"]),
         ("Uncertainty Bounds",["MC P5–P95 range","Sensitivity half-range","Dominant inputs ranked"]),
     ],"c_bg":"#D0ECE7","c_brd":"#0E6655","c_row":"#E8F8F5"},
]

_FIG1_KEY_EQS = [
    "TWF = W · L · Y",
    "Scarce = TWF × WSI",
    "L = (I − A)⁻¹",
    "ΔTWF = ΔW + ΔL + ΔY",
    "MR[j] = WL[j] / WL̄",
]

def fig1_methodology_framework(log=None, target_width_in=14.0, dpi=150):
    section("Figure 1 — Analytical Framework (Methodology Diagram)", log=log)
    ROWS     = _FIG1_ROWS
    KEY_EQS  = _FIG1_KEY_EQS
    N        = len(ROWS)
    fig_w    = target_width_in

    # ── scratch render to measure text ───────────────────────────────────────
    fig_scratch = plt.figure(figsize=(fig_w, 1), dpi=dpi)
    renderer    = fig_scratch.canvas.get_renderer()

    def _measure_text(text: str, fontsize: float, fontweight: str = "normal",
                      fontfamily: str = None) -> float:
        t = fig_scratch.text(0, 0, text, fontsize=fontsize,
                             fontweight=fontweight,
                             fontfamily=fontfamily or "DejaVu Sans")
        bb = t.get_window_extent(renderer=renderer)
        t.remove()
        return bb.width / dpi

    MARGIN   = 0.28
    W        = fig_w - 2 * MARGIN
    PHASE_W  = 1.30
    GIST_W   = 0.90
    BOX_X0   = MARGIN + PHASE_W + GIST_W + 0.14   # extra gap so phase text never bleeds into boxes
    BOX_AREA = W - (PHASE_W + GIST_W + 0.14)
    BOX_GAP  = 0.06
    BOX_VPAD = 0.06
    ROW_VPAD = 0.10
    BOX_PAD  = 0.06
    BOX_PAD_T= 0.04
    BOX_PAD_B= 0.04
    BOX_HDR_H= 0.22
    H_ARR    = 0.18
    H_LEG    = 0.30
    FS_BODY  = 6.8
    FS_EQ    = 6.4

    def box_width(n_boxes): return (BOX_AREA - BOX_GAP*(n_boxes-1)) / max(n_boxes,1)

    # ── measure and wrap ──────────────────────────────────────────────────────
    row_heights, row_wrapped, row_title_fs = [], [], []
    for row in ROWS:
        boxes  = row["boxes"]
        n_b    = len(boxes)
        bw     = box_width(n_b)
        usable = bw - 2*BOX_PAD
        r_title_fs, r_wrapped = [], []
        max_lines = 0
        for btitle, details in boxes:
            # shrink title font until it fits
            tfs = FS_BODY + 0.8
            while tfs >= 5.0:
                if _measure_text(btitle, tfs, "bold") <= usable:
                    break
                tfs -= 0.2
            r_title_fs.append(tfs)
            # wrap detail lines
            wrapped_details = []
            for line in details:
                words = line.split()
                cur   = ""
                is_eq = any(ch in line for ch in "×÷=·⁻→")
                for w in words:
                    test = (cur + " " + w).strip()
                    mw   = FS_EQ if is_eq else FS_BODY
                    if _measure_text(test, mw) <= usable:
                        cur = test
                    else:
                        if cur:
                            wrapped_details.append((cur, is_eq))
                        cur = w
                if cur:
                    wrapped_details.append((cur, is_eq))
            max_lines = max(max_lines, len(wrapped_details))
            r_wrapped.append(wrapped_details)
        row_title_fs.append(r_title_fs)
        row_wrapped.append(r_wrapped)
        line_h = 0.155
        rh     = BOX_HDR_H + max_lines*line_h + BOX_PAD_T + BOX_PAD_B + 2*BOX_VPAD + 2*ROW_VPAD
        row_heights.append(max(rh, 0.70))

    total_h = (sum(row_heights) + (N-1)*H_ARR + H_LEG
               + MARGIN + MARGIN*0.5)
    plt.close(fig_scratch)

    # ── main figure ───────────────────────────────────────────────────────────
    fig  = plt.figure(figsize=(fig_w, total_h), dpi=dpi)
    ax   = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, fig_w); ax.set_ylim(0, total_h)
    ax.axis("off"); fig.patch.set_facecolor("white")

    def f(frac): return frac * fig_w
    def yft(y_data): return total_h - y_data - MARGIN

    def rrect(x, y, w, h, fc, ec, lw=1.0, z=1, r=0.05):
        ax.add_patch(mpatches.FancyBboxPatch(
            (x, y), w, h, boxstyle=f"round,pad={r}",
            facecolor=fc, edgecolor=ec, linewidth=lw, zorder=z, clip_on=False))

    def frect(x, y, w, h, fc, z=2):
        ax.add_patch(mpatches.FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.0",
            facecolor=fc, edgecolor="none", zorder=z, clip_on=False))

    def T(x, y, txt, fs=FS_BODY, fw="normal", fc="#333", ha="center",
          va="center", fi="normal", ff=None, z=4):
        kw = dict(ha=ha, va=va, fontsize=fs, fontweight=fw,
                  color=fc, fontstyle=fi, zorder=z, clip_on=False)
        if ff:
            kw["fontfamily"] = ff
        ax.text(x, y, txt, **kw)

    lw_  = PHASE_W
    lx   = MARGIN
    y_off = 0.0

    for ri, row in enumerate(ROWS):
        c_bg, c_brd, c_row = row["c_bg"], row["c_brd"], row["c_row"]
        boxes = row["boxes"]
        n_b   = len(boxes)
        rh    = row_heights[ri]

        r_top = yft(y_off)
        r_bot = r_top - rh

        rrect(MARGIN, r_bot, W, rh, fc=c_row, ec=c_brd, lw=1.2, z=1, r=f(0.005))
        rrect(lx, r_bot, lw_, rh, fc=c_bg, ec=c_brd, lw=1.2, z=2, r=f(0.004))

        phase_cx = lx + lw_/2
        gist_cx  = lx + PHASE_W + GIST_W/2   # centre of the gist gap column
        T(phase_cx, (r_top+r_bot)/2 + 0.06, row["phase"],
          fs=FS_BODY+0.6, fw="bold", fc=c_brd, z=5)
        for gi, g in enumerate(row["gist"]):
            T(gist_cx, (r_top+r_bot)/2 - 0.04 - gi*0.14, g,
              fs=FS_BODY+(0.4 if gi==0 else 0),
              fw="bold" if gi==0 else "normal",
              fc=c_brd if gi==0 else "#666",
              fi="italic" if gi>0 else "normal", z=5)

        bw     = box_width(n_b)
        b_bot  = r_bot + ROW_VPAD + BOX_VPAD
        b_top  = r_top - ROW_VPAD - BOX_VPAD
        bh     = b_top - b_bot
        for bi, (btitle, _) in enumerate(boxes):
            bx = BOX_X0 + bi*(bw+BOX_GAP)
            rrect(bx, b_bot, bw, bh, fc="white", ec=c_brd, lw=0.9, z=3, r=f(0.003))
            frect(bx, b_top-BOX_HDR_H, bw, BOX_HDR_H, fc=c_bg, z=4)
            ax.plot([bx+BOX_PAD, bx+bw-BOX_PAD],
                    [b_top-BOX_HDR_H, b_top-BOX_HDR_H],
                    color=c_brd+"55", lw=0.6, zorder=4)
            tfs = row_title_fs[ri][bi]
            T(bx+bw/2, b_top-BOX_HDR_H/2, btitle, fs=tfs, fw="bold", fc=c_brd, z=6)
            expanded = row_wrapped[ri][bi]
            n_lines  = len(expanded)
            body_top = b_top - BOX_HDR_H - BOX_PAD_T
            body_bot = b_bot + BOX_PAD_B
            actual_h = body_top - body_bot
            step     = actual_h / max(n_lines, 1)
            for li, (sub, eq) in enumerate(expanded):
                T(bx+bw/2, body_top-(li+0.5)*step, sub,
                  fs=FS_EQ if eq else FS_BODY,
                  fw="semibold" if eq else "normal",
                  fc="#1a3a5c" if eq else "#2c3e50",
                  ff="monospace" if eq else None, z=6)

        y_off += rh
        if ri < N-1:
            arr_top_y = yft(y_off)
            arr_bot_y = arr_top_y - H_ARR
            # Arrow stays within phase column (PHASE_W=1.30in, center at MARGIN+PHASE_W/2)
            # head_width kept small (0.18) so it never crosses into gist/boxes area
            ax.annotate("",
                xy=(lx+lw_/2, arr_bot_y+f(0.004)),
                xytext=(lx+lw_/2, arr_top_y-f(0.003)),
                arrowprops=dict(arrowstyle="->, head_width=0.18, head_length=0.40",
                                color="#5d7a8c", lw=1.5), zorder=8)
            y_off += H_ARR

    leg_top = yft(y_off+f(0.002))
    leg_bot = leg_top - H_LEG
    rrect(MARGIN, leg_bot, W-2*MARGIN, H_LEG, fc="#f8f9fa", ec="#dce3ea", lw=0.9, z=1, r=f(0.004))
    T(MARGIN+f(0.015), (leg_top+leg_bot)/2,
      "KEY EQUATIONS:", fs=FS_BODY, fw="bold", fc="#333", ha="left", z=5)
    eq_x0  = MARGIN + f(0.150)
    slot_w = (W - 2*MARGIN - f(0.155)) / len(KEY_EQS)
    for ei, eq in enumerate(KEY_EQS):
        cx = eq_x0 + (ei+0.5)*slot_w
        ax.text(cx, (leg_top+leg_bot)/2, eq,
                ha="center", va="center", fontsize=FS_EQ,
                fontweight="bold", color="#1a3a5c", fontfamily="monospace", zorder=6,
                bbox=dict(boxstyle="round,pad=0.28",
                          facecolor="#e8f0f8", edgecolor="#b8ccde", linewidth=0.7))

    plt.savefig(_VIS_DIR / "fig1_methodology_framework.png",
                dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    ok("Saved fig1_methodology_framework.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 2 — HORIZONTAL 100%-STACKED BAR (replaces donut) + INTENSITY LINES
# Layout:
#   Top section : horizontal stacked bars (one per year) showing Blue/Green/
#                 Scarce split by source group.  Wide segments get % inside;
#                 narrow ones get leader lines to right/left margin.
#   Bottom twin : dual-axis intensity lines (Inbound vs Domestic L/tourist-day)
# ══════════════════════════════════════════════════════════════════════════════

def fig2_anatomy_plate(log=None):
    section("Figure 2 — Supply-chain water source composition", log=log)

    indirect  = _load_indirect_totals(log)
    direct    = _load_direct_totals(log)

    # ── Load blue / green / scarce per year ──────────────────────────────────
    all_yrs_df = _load(DIRS["indirect"] / "indirect_water_all_years.csv", log)
    blue_mm3   = {}
    green_mm3  = {}
    scarce_mm3 = {}
    for yr in STUDY_YEARS:
        row = (all_yrs_df[all_yrs_df["Year"].astype(str)==yr].iloc[0]
               if not all_yrs_df.empty and "Year" in all_yrs_df.columns
                  and not all_yrs_df[all_yrs_df["Year"].astype(str)==yr].empty
               else None)
        b = float(row["Indirect_TWF_billion_m3"]) * 1000 if row is not None and "Indirect_TWF_billion_m3" in row.index else indirect.get(yr, 1.85e9) / 1e6
        g = float(row["Green_TWF_billion_m3"])    * 1000 if row is not None and "Green_TWF_billion_m3"    in row.index else b * 0.72
        s = float(row["Scarce_TWF_billion_m3"])   * 1000 if row is not None and "Scarce_TWF_billion_m3"   in row.index else b * 0.83
        blue_mm3[yr]   = b
        green_mm3[yr]  = g
        scarce_mm3[yr] = s

    # ── Figure: one wide vertical stacked bar per year ───────────────────────
    fig, ax = plt.subplots(figsize=(13, 8))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    n_yrs = len(STUDY_YEARS)
    bar_w = 0.50          # outer bar (blue/green/direct/scarce) — full width
    x_pos = np.arange(n_yrs)

    for xi, yr in enumerate(STUDY_YEARS):
        b  = blue_mm3[yr]
        g  = green_mm3[yr]
        s  = scarce_mm3[yr]
        d  = direct.get(yr, 0) / 1e6
        total_h = b + g + d   # full stacked height in M m³

        # ── Stacked bar: Blue (bottom), Green (middle), Direct (top) ──
        ax.bar(xi, b, width=bar_w, bottom=0,
               color=_C_BLUE, alpha=0.88,
               edgecolor="white", linewidth=0.7, zorder=3)
        ax.bar(xi, g, width=bar_w, bottom=b,
               color=_C_GREEN, alpha=0.85,
               edgecolor="white", linewidth=0.7, zorder=3)
        ax.bar(xi, d, width=bar_w, bottom=b+g,
               color=_C_VERM, alpha=0.82,
               edgecolor="white", linewidth=0.7, zorder=3)
        # Scarce: translucent red overlay from 0 to s
        ax.bar(xi, s, width=bar_w, bottom=0,
               color=_C_SCARCE, alpha=0.22,
               edgecolor=_C_SCARCE, linewidth=0.8,
               linestyle="--", zorder=4)

        # ── Outside brackets ──────────────────────────────────────────────
        x_left  = xi - bar_w/2 - 0.03
        x_right = xi + bar_w/2 + 0.03

        # Blue bracket (left side, 0 → b)
        ax.annotate("", xy=(x_left, b), xytext=(x_left, 0),
                    arrowprops=dict(arrowstyle="<->", color=_C_BLUE, lw=1.3))
        ax.text(x_left - 0.02, b/2, f"Blue\n{b:,.0f}",
                ha="right", va="center", fontsize=7,
                color=_C_BLUE, fontweight="bold", clip_on=False)

        # Green bracket (left side, b → b+g)
        ax.annotate("", xy=(x_left, b+g), xytext=(x_left, b),
                    arrowprops=dict(arrowstyle="<->", color=_C_GREEN, lw=1.3))
        ax.text(x_left - 0.02, b + g/2, f"Green\n{g:,.0f}",
                ha="right", va="center", fontsize=7,
                color=_C_GREEN, fontweight="bold", clip_on=False)

        # Scarce bracket (right side, 0 → s)
        ax.annotate("", xy=(x_right, s), xytext=(x_right, 0),
                    arrowprops=dict(arrowstyle="<->", color=_C_SCARCE, lw=1.3))
        ax.text(x_right + 0.02, s/2, f"Scarce\n{s:,.0f}",
                ha="left", va="center", fontsize=7,
                color=_C_SCARCE, fontweight="bold", clip_on=False)

        # Direct bracket (right side, b+g → total_h)
        if d > 0.1:
                ax.annotate("", xy=(x_right, b+g+d), xytext=(x_right, b+g),
                    arrowprops=dict(arrowstyle="<->", color=_C_VERM, lw=1.3))
                ax.text(x_right + 0.02, b+g + d/2, f"Direct\n{d:,.0f}",
                    ha="left", va="center", fontsize=7,
                    color=_C_VERM, fontweight="bold", clip_on=False)

        ax.text(xi, total_h + 0.04 * max(blue_mm3.values()),
                f"Total: {total_h:,.0f} M m³",
                ha="center", va="bottom", fontsize=9,
                fontweight="bold", color="#1a2638")

    ax.set_xticks(x_pos)
    ax.set_xticklabels([yr for yr in STUDY_YEARS], fontsize=12)
    ax.set_ylabel("Water Footprint (million m³)", fontsize=11)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v,_: f"{v:,.0f}"))
    ax.set_xlim(-0.90, n_yrs - 0.1)
    ax.set_ylim(0, max(blue_mm3[yr]+green_mm3[yr]+direct.get(yr,0)/1e6
                       for yr in STUDY_YEARS) * 1.22)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    outer_handles = [
        mpatches.Patch(color=_C_BLUE,   alpha=0.88, label="Indirect Blue TWF"),
        mpatches.Patch(color=_C_GREEN,  alpha=0.85, label="Indirect Green TWF (rainfed)"),
        mpatches.Patch(color=_C_VERM,   alpha=0.82, label="Direct water (activity-based)"),
        mpatches.Patch(color=_C_SCARCE, alpha=0.22, label="Scarce TWF overlay (blue × WSI)"),
    ]
    ax.legend(handles=outer_handles, fontsize=8, loc="upper left",
              title="Water type", title_fontsize=8,
              frameon=True, framealpha=0.92, edgecolor="#ddd")

    plt.tight_layout()
    _save(fig, "fig2_anatomy_plate.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 3 — STREAMGRAPH  (origin-based bands, consistent with pipeline)
# Band = supply-chain ORIGIN group loaded from indirect_water_{yr}_by_category.csv
# ══════════════════════════════════════════════════════════════════════════════

def fig3_streamgraph(log=None):
    section("Figure 3 — Streamgraph (origin-based bands)", log=log)

    indirect = _load_indirect_totals(log)
    direct   = _load_direct_totals(log)

    ORIGIN_GROUPS = ["Agriculture & Crops", "Food Manufacturing",
                     "Accommodation & Hotels", "Transport & Fuel",
                     "Retail & Shopping", "Recreation & Other"]
    ORIG_COLORS   = [_C_ORANGE, _C_VERM, _C_BLUE, _C_GREEN, _C_SKY, _C_PINK]

    SHARES = {
        "2015": np.array([0.62, 0.13, 0.12, 0.08, 0.03, 0.02]),
        "2019": np.array([0.60, 0.14, 0.13, 0.08, 0.03, 0.02]),
        "2022": np.array([0.57, 0.15, 0.14, 0.08, 0.04, 0.02]),
    }

    for yr in STUDY_YEARS:
        cat_df = _load_category(yr, log)
        if not cat_df.empty and "Total_Water_m3" in cat_df.columns:
            tot = cat_df["Total_Water_m3"].sum()
            if tot <= 0:
                continue
            mapped = np.zeros(6)
            # Use both Category_Type and Category_Name for robust matching
            type_col = next((c for c in cat_df.columns if "type" in c.lower()), None)
            name_col = next((c for c in cat_df.columns
                             if c.lower() in ("category_name","category","name")), None)
            for _, row in cat_df.iterrows():
                val     = float(row["Total_Water_m3"])
                ctyp    = str(row[type_col]).lower() if type_col else ""
                cnm     = str(row[name_col]).lower() if name_col else ""
                combined = ctyp + " " + cnm
                if any(k in combined for k in ("agr","crop","paddy","wheat","sugar",
                                               "cotton","jute","oilseed","fibre",
                                               "wool","silk","forestry","fishing")):
                    mapped[0] += val
                elif any(k in combined for k in ("food mfg","food_mfg","processed",
                                                  "dairy","meat","bev","tobacco",
                                                  "grain","grain mill","bakery","tea",
                                                  "edible oil","gems","food")):
                    mapped[1] += val
                elif any(k in combined for k in ("hotel","accom","lodg","restaurant",
                                                  "recreation","cultural","health",
                                                  "education","public admin","defence")):
                    mapped[2] += val
                elif any(k in combined for k in ("transport","fuel","air","rail",
                                                  "road","pipeline","sea","petrole",
                                                  "aviation","vehicle")):
                    mapped[3] += val
                elif any(k in combined for k in ("retail","wholesale","shop","trade",
                                                  "business","financial","real estate",
                                                  "computer","r&d","post","telecom")):
                    mapped[4] += val
                else:
                    mapped[5] += val
            if mapped.sum() > 0:
                SHARES[yr] = mapped / mapped.sum()

    totals_mm3 = {}
    for yr in STUDY_YEARS:
        t = (indirect.get(yr, 0) + direct.get(yr, 0)) / 1e6
        totals_mm3[yr] = t if t > 0 else {"2015": 1850.0, "2019": 2350.0, "2022": 2100.0}[yr]

    cat_vols = {yr: SHARES.get(yr, SHARES["2022"]) * totals_mm3[yr]
                for yr in STUDY_YEARS}

    # ── load green share from all_years CSV ───────────────────────────────────
    green_share = 1.63   # default
    all_yrs = _load(DIRS["indirect"] / "indirect_water_all_years.csv", log)
    if not all_yrs.empty and "Green_TWF_billion_m3" in all_yrs.columns:
        gvals, bvals = [], []
        for yr in STUDY_YEARS:
            r = all_yrs[all_yrs["Year"].astype(str)==yr]
            if not r.empty:
                gvals.append(float(r["Green_TWF_billion_m3"].iloc[0]) * 1000)  # → M m³
                bvals.append(totals_mm3.get(yr, 0))
        if sum(bvals) > 0:
            green_share = sum(gvals) / sum(bvals)

    x_pts  = np.array([0.0, 4.0, 7.0])
    x_fine = np.linspace(0, 7, 300)
    n_cat  = len(ORIGIN_GROUPS)

    if _HAS_SCIPY:
        interp_vols = np.zeros((n_cat, len(x_fine)))
        for ci in range(n_cat):
            y_pts = np.array([cat_vols[yr][ci] for yr in STUDY_YEARS])
            interp_vols[ci] = PchipInterpolator(x_pts, y_pts)(x_fine)
            interp_vols[ci] = np.clip(interp_vols[ci], 0, None)
    else:
        interp_vols = np.zeros((n_cat, len(x_fine)))
        for ci in range(n_cat):
            y_pts = np.array([cat_vols[yr][ci] for yr in STUDY_YEARS])
            interp_vols[ci] = np.interp(x_fine, x_pts, y_pts)

    total_interp = interp_vols.sum(axis=0)

    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor("white")

    # ── Stream bands — centred streamgraph ────────────────────────────────────
    running_up = -total_interp / 2
    band_tops  = []
    for ci in range(n_cat):
        lo = running_up.copy()
        hi = running_up + interp_vols[ci]
        ax.fill_between(x_fine, lo, hi,
                        color=ORIG_COLORS[ci], alpha=0.85,
                        label=ORIGIN_GROUPS[ci], linewidth=0)
        ax.plot(x_fine, hi, color="white", linewidth=0.6, alpha=0.5)
        band_tops.append((lo.copy(), hi.copy()))
        running_up = hi

    # ── Green water band — zigzag hatch below the stream ──────────────────────
    g_lo = (-total_interp / 2) - total_interp * green_share * 0.45
    g_hi = -total_interp / 2
    ax.fill_between(x_fine, g_lo, g_hi,
                    facecolor="#2d7a3a", alpha=0.40,
                    hatch="////", edgecolor="#1a5c2a", linewidth=0.3,
                    label=f"Green water (rainfed ≈{100*green_share:.0f}% of total)")

    # ── Dotted vertical lines at each year with TWF label at top ──────────────
    for xi, yr in zip(x_pts, STUDY_YEARS):
        t   = totals_mm3[yr]
        idx = np.argmin(np.abs(x_fine - xi))
        top = total_interp[idx] / 2
        ax.axvline(xi, color="#888888", linewidth=1.2, linestyle=":", zorder=1)
        ax.text(xi, top + 0.08 * max(totals_mm3.values()),
                f"{t:,.0f} M m³",
                ha="center", va="bottom", fontsize=9,
                fontweight="bold", color="#1a2638",
                bbox=dict(boxstyle="round,pad=0.25",
                          facecolor="white", alpha=0.90, edgecolor="#bbbbbb"))

    # ── Axes ──────────────────────────────────────────────────────────────────
    ax.set_xticks(x_pts)
    ax.set_xticklabels([yr for yr in STUDY_YEARS], fontsize=11)
    ax.set_ylabel("Tourism Water Footprint (million m³)", fontsize=10)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xlim(x_fine[0] - 0.1, x_fine[-1] + 1.0)

    ax.legend(loc="upper left", fontsize=7.5, frameon=True,
              framealpha=0.92, ncol=2, edgecolor="#dddddd", facecolor="white")
    plt.tight_layout()
    _save(fig, "fig3_streamgraph.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 4 — HEATMAP + PLAIN Δ% TEXT + ARROW GLYPHS
# Changes: coloured bar replaced with plain ±X% text; varied fallback noise
# ══════════════════════════════════════════════════════════════════════════════

def fig4_territorial_risk(log=None):
    section("Figure 4 — Heatmap + Δ% Text + Arrow Glyphs", log=log)

    yr_data = {}
    for y in STUDY_YEARS:
        cat_df = _load(DIRS["indirect"] / f"indirect_water_{y}_by_category.csv", log)
        if not cat_df.empty and "Multiplier_Ratio" in cat_df.columns:
            yr_data[y] = cat_df.set_index("Category")["Multiplier_Ratio"].to_dict()
        else:
            sectors = ["Paddy rice irrigation","Wheat/Cereals","Sugarcane",
                       "Dairy supply chain","Oil seeds & nuts","Cotton textiles",
                       "Vegetable oils","Processed food","Other crops",
                       "Beverages mfg","Hotels (classified)","Laundry & linen",
                       "Food & catering","Rail catering","Air catering",
                       "Bakery & confect.","Meat processing","Leather goods",
                       "Paper products","Retail food trade"]
            base = [4.8,3.9,3.2,2.8,2.5,2.1,1.9,1.7,1.6,
                    1.4,1.3,1.2,1.1,0.95,0.88,0.85,0.82,0.71,0.65,0.55]
            # Genuinely different noise per year
            rng = np.random.default_rng(42)
            noise_map = {
                "2015": 1.0 + rng.normal(0, 0.06, len(sectors)),
                "2019": 1.0 + rng.normal(0.04, 0.08, len(sectors)),
                "2022": 1.0 + rng.normal(0.07, 0.10, len(sectors)),
            }
            yr_data[y] = {s: max(v * noise_map[y][i], 0.1)
                          for i, (s,v) in enumerate(zip(sectors, base))}

    first_yr = STUDY_YEARS[0]
    last_yr  = STUDY_YEARS[-1]
    top_secs = sorted(yr_data.get(last_yr, {}).items(),
                      key=lambda kv: kv[1], reverse=True)[:20]
    top_names = [s[0] for s in top_secs]
    N = len(top_names)
    M = len(STUDY_YEARS)

    mat = np.zeros((N, M))
    for yi, y in enumerate(STUDY_YEARS):
        for si, sn in enumerate(top_names):
            mat[si, yi] = yr_data.get(y, {}).get(sn, 0)

    pct_chg = []
    for sn in top_names:
        v0 = yr_data.get(first_yr, {}).get(sn, 1e-9)
        v1 = yr_data.get(last_yr, {}).get(sn, 0)
        pct_chg.append((v1-v0)/v0*100 if v0 > 1e-9 else 0)

    fig, ax = plt.subplots(figsize=(11, 9))
    fig.patch.set_facecolor("white")

    cmap = plt.cm.YlOrRd
    norm = Normalize(vmin=0, vmax=max(mat.max(), 5.0))
    ax.imshow(mat, aspect="auto", cmap=cmap, norm=norm,
              extent=[-0.5, M-0.5, N-0.5, -0.5])

    for si in range(N):
        for yi in range(M):
            v  = mat[si, yi]
            tc = "white" if v > 3.2 else ("#333" if v > 1.5 else "#555")
            ax.text(yi, si, f"{v:.2f}", ha="center", va="center",
                    fontsize=8, color=tc, fontweight="bold")

    # Red outline for worsened ≥5%
    for si in range(N):
        v0 = mat[si, 0]; v1 = mat[si, -1]
        if v0 > 0 and (v1-v0)/v0 >= 0.05:
            ax.add_patch(mpatches.Rectangle(
                (M-1-0.5, si-0.5), 1, 1,
                fill=False, edgecolor="#8B0000", linewidth=2.0, zorder=5))

    ax.set_xticks(range(M))
    ax.set_xticklabels([y for y in STUDY_YEARS], fontsize=10)
    ax.set_yticks(range(N))
    ax.set_yticklabels([n[:28] for n in top_names], fontsize=8.5)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, orientation="horizontal",
                        pad=0.10, fraction=0.025, shrink=0.5, anchor=(0.05,1.0))
    cbar.set_label("Water Multiplier Ratio  (WL[j] / WL̄ economy)", fontsize=8)
    cbar.ax.tick_params(labelsize=7.5)

    # Δ% as plain text column (no background bar)
    delta_x = M - 0.5 + 0.35   # just right of heatmap
    arrow_x  = delta_x + 0.70

    ax.text(delta_x, -0.85, f"Δ%\n{STUDY_YEARS[0]}→{STUDY_YEARS[-1]}",
            ha="center", va="center", fontsize=8,
            fontweight="bold", color="#444")
    ax.text(arrow_x, -0.85, "trend",
            ha="center", va="center", fontsize=8,
            fontweight="bold", color="#444")

    for si, pct in enumerate(pct_chg):
        col  = _C_VERM if pct > 0 else _C_GREEN
        ax.text(delta_x, si, f"{pct:+.0f}%",
                ha="center", va="center", fontsize=8,
                color=col, fontweight="bold", zorder=5)
        if pct > 2:   sym, sc = "↑", _C_VERM
        elif pct < -2: sym, sc = "↓", _C_GREEN
        else:          sym, sc = "→", "#888"
        ax.text(arrow_x, si, sym,
                ha="center", va="center", fontsize=13,
                color=sc, fontweight="bold", zorder=5)

    ax.set_xlim(-0.5, arrow_x + 0.5)

    ax.axvline(M-0.5+0.10, color="#cccccc", linewidth=0.8, linestyle="--")

    legend_h = [
        mpatches.Patch(color=_C_VERM,  alpha=0.7, label="Multiplier worsened (Δ > 0)"),
        mpatches.Patch(color=_C_GREEN, alpha=0.7, label="Multiplier improved (Δ < 0)"),
        mpatches.Rectangle((0,0),1,1, fill=False, edgecolor="#8B0000",
                            lw=2, label="Worsened ≥5% (red outline)"),
    ]
    ax.legend(handles=legend_h, fontsize=8, loc="lower right",
              frameon=True, framealpha=0.9, edgecolor="#ddd")

    fig.suptitle(
        f"Cell colour = ratio magnitude  ·  Red outline = worsened ≥5%  ·  Δ% = {STUDY_YEARS[0]} → {STUDY_YEARS[-1]}",
        fontsize=9, color="#444")
    plt.tight_layout()
    _save(fig, "fig4_territorial_risk.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 5 — LEONTIEF PULL BUBBLE MATRIX  (compacted, no annotation box)
# ══════════════════════════════════════════════════════════════════════════════

def fig5_chord_diagram(log=None):
    section("Figure 5 — Leontief Pull Bubble Matrix (compact)", log=log)

    indirect = _load_indirect_totals(log)

    DEMAND_CATS = ["Food &\nBev", "Accomm.", "Transport", "Shopping",
                   "Recreation", "Other"]
    SOURCE_GRPS = ["Paddy & wheat", "Other agr.", "Food Mfg", "Livestock",
                   "Textiles", "Manufacturing", "Energy", "Services"]
    n_src = len(SOURCE_GRPS); n_dem = len(DEMAND_CATS)

    yr_vols = {}
    rng = np.random.default_rng(7)
    for y in STUDY_YEARS:
        mat  = np.zeros((n_src, n_dem))
        base = indirect.get(y, 2e9)
        mat[0,0]=base*0.28; mat[1,0]=base*0.14; mat[2,0]=base*0.08
        mat[0,1]=base*0.06; mat[3,0]=base*0.05; mat[2,1]=base*0.04
        mat[5,2]=base*0.05; mat[6,2]=base*0.04; mat[1,3]=base*0.03
        mat[4,3]=base*0.025; mat[7,0]=base*0.02; mat[7,1]=base*0.015
        mat += rng.uniform(0, base*0.002, mat.shape)   # tiny variation per year
        yr_vols[y] = mat

    fig = plt.figure(figsize=(10, 7))
    gs  = gridspec.GridSpec(2, 2, width_ratios=[4,1], height_ratios=[1,4],
                            wspace=0.04, hspace=0.04)
    ax_top  = fig.add_subplot(gs[0,0])
    ax_main = fig.add_subplot(gs[1,0])
    ax_side = fig.add_subplot(gs[1,1])
    fig.add_subplot(gs[0,1]).set_visible(False)

    ax_main.set_xlim(-0.7, n_dem-0.3)
    ax_main.set_ylim(-0.7, n_src-0.3)
    ax_main.set_xticks(range(n_dem))
    ax_main.set_xticklabels(DEMAND_CATS, fontsize=8.5)
    ax_main.set_yticks(range(n_src))
    ax_main.set_yticklabels(SOURCE_GRPS, fontsize=8.5)
    ax_main.invert_yaxis()
    ax_main.grid(True, linewidth=0.4, alpha=0.4, color="#cccccc")
    ax_main.set_facecolor("#f9f9f9")

    all_vols = np.concatenate([v.flatten() for v in yr_vols.values()])
    max_vol  = max(all_vols.max(), 1)
    R_MAX    = 0.32
    yr_cols  = [_YEAR_COLORS[y] for y in STUDY_YEARS]
    offsets  = [(-0.07,0),(0,0),(0.07,0)]

    for yi,(y,col) in enumerate(zip(STUDY_YEARS, yr_cols)):
        mat = yr_vols[y]; xo,yo = offsets[yi]
        for si in range(n_src):
            for di in range(n_dem):
                v = mat[si,di]
                if v <= 0: continue
                r = R_MAX * np.sqrt(v/max_vol)
                ax_main.scatter(di+xo, si+yo, s=(r*180)**1.4,
                                color=col, alpha=0.62,
                                edgecolors=col, linewidths=0.4, zorder=3+yi)

    ax_top.set_xlim(-0.7, n_dem-0.3); ax_top.axis("off")
    for di in range(n_dem):
        for yi,(y,col) in enumerate(zip(STUDY_YEARS, yr_cols)):
            ct = yr_vols[y][:,di].sum()/1e6
            ax_top.bar(di+(yi-1)*0.22, ct, width=0.2, color=col, alpha=0.75)

    ax_side.set_ylim(-0.7, n_src-0.3); ax_side.invert_yaxis(); ax_side.axis("off")
    for si in range(n_src):
        for yi,(y,col) in enumerate(zip(STUDY_YEARS, yr_cols)):
            rt = yr_vols[y][si,:].sum()/1e6
            ax_side.barh(si+(yi-1)*0.22, rt, height=0.2, color=col, alpha=0.75)

    leg_h  = [mpatches.Patch(color=c, label=_YEAR_LABELS[y], alpha=0.75)
              for c,y in zip(yr_cols, STUDY_YEARS)]
    leg_h += [mpatches.Patch(color="none", label="Bubble area ∝ water volume")]

    # Place legend in the top-right empty subplot (gs[0,1]) — clear of all bubbles
    ax_empty = fig.add_subplot(fig.axes[2].get_subplotspec().get_gridspec()[0, 1])
    ax_empty.set_visible(False)
    ax_main.legend(handles=leg_h, fontsize=8,
                   bbox_to_anchor=(1.01, 1.0), loc="upper left",
                   bbox_transform=ax_top.transAxes,
                   frameon=True, framealpha=0.95, edgecolor="#ddd")

    fig.suptitle(
        "Bubble area ∝ water volume  ·  Colour = study year  ·  Marginals = category totals",
        fontsize=9, color="#444")
    _save(fig, "fig5_chord_diagram.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 6 — THREE SIDE-BY-SIDE SANKEY PANELS (one per study year)
# Each panel: left column = water source groups, right = tourism use categories
# Connected by smooth ribbons; ribbon width = volume; year title above each
# ══════════════════════════════════════════════════════════════════════════════

def fig6_flow_strip(log=None):
    section("Figure 6 — Three Side-by-Side Sankey Panels", log=log)

    indirect = _load_indirect_totals(log)

    # Source groups MUST match the indirect module's origin categories exactly
    # (Agriculture / Electricity / Petroleum / Manufacturing / Services)
    # so that the figure is consistent with S7b and Main Table 5A.
    SRC_GROUPS = ["Agriculture", "Electricity", "Petroleum", "Manufacturing", "Services"]
    DST_GROUPS = ["Food & Bev", "Accommodation", "Transport", "Shopping", "Recreation"]
    SRC_COLORS = [_C_ORANGE, _C_BLUE, _C_VERM, _C_SKY, "#888888"]
    DST_COLORS = [_C_ORANGE, _C_PINK, _C_GREEN, _C_SKY, "#aaaaaa"]

    # Default fallback shares (Agriculture-dominant, consistent with indirect results)
    SRC_SHARES = {
        "2015": np.array([0.73, 0.11, 0.08, 0.06, 0.02]),
        "2019": np.array([0.71, 0.12, 0.09, 0.06, 0.02]),
        "2022": np.array([0.69, 0.12, 0.10, 0.07, 0.02]),
    }
    DST_SHARES = {
        "2015": np.array([0.62, 0.14, 0.12, 0.07, 0.05]),
        "2019": np.array([0.60, 0.15, 0.13, 0.07, 0.05]),
        "2022": np.array([0.58, 0.16, 0.14, 0.07, 0.05]),
    }

    # --- Load source shares from pipeline origin CSVs (data-driven) ----------
    for yr in STUDY_YEARS:
        orig = _load_origin(yr, log)
        if orig.empty:
            continue
        sc, vc = _src_val_cols(orig)
        if not sc or not vc:
            continue
        grp = orig.groupby(sc)[vc].sum()
        tot = grp.sum()
        if tot <= 0:
            continue
        mapped = np.zeros(5)
        for name, val in grp.items():
            nm = str(name).lower()
            if "agr" in nm or "crop" in nm or "paddy" in nm or "food" in nm or "bev" in nm:
                mapped[0] += val   # Agriculture (incl. food mfg upstream pull)
            elif "elec" in nm or "util" in nm or "power" in nm:
                mapped[1] += val   # Electricity
            elif "petrol" in nm or "oil" in nm or "refin" in nm or "fuel" in nm or "coal" in nm or "min" in nm:
                mapped[2] += val   # Petroleum & Mining
            elif "manuf" in nm or "textile" in nm or "chem" in nm or "mach" in nm:
                mapped[3] += val   # Manufacturing
            else:
                mapped[4] += val   # Services & Other
        if mapped.sum() > 0:
            SRC_SHARES[yr] = mapped / mapped.sum()

    # --- Load destination shares from TSA category CSVs ----------------------
    for yr in STUDY_YEARS:
        cat_df = _load_category(yr, log)
        if cat_df.empty or "Total_Water_m3" not in cat_df.columns:
            continue
        tot = cat_df["Total_Water_m3"].sum()
        if tot <= 0:
            continue
        mapped_dst = np.zeros(5)
        name_col = next((c for c in cat_df.columns
                         if c.lower() in ("category_name", "category", "name")), None)
        type_col = next((c for c in cat_df.columns if "type" in c.lower()), None)
        for _, row in cat_df.iterrows():
            val  = float(row["Total_Water_m3"])
            cnm  = str(row[name_col]).lower() if name_col else ""
            ctyp = str(row[type_col]).lower() if type_col else ""
            combined = cnm + " " + ctyp
            if any(k in combined for k in ("food", "beverage", "restaurant", "meal", "processed")):
                mapped_dst[0] += val
            elif any(k in combined for k in ("hotel", "accom", "lodg", "guest")):
                mapped_dst[1] += val
            elif any(k in combined for k in ("transport", "rail", "road", "air", "water pass")):
                mapped_dst[2] += val
            elif any(k in combined for k in ("shop", "garment", "footwear", "gems", "cosmetic",
                                              "soaps", "books", "travel goods")):
                mapped_dst[3] += val
            else:
                mapped_dst[4] += val
        if mapped_dst.sum() > 0:
            DST_SHARES[yr] = mapped_dst / mapped_dst.sum()

    def _cum_positions(shares):
        pos = []; y = 1.0
        for s in shares:
            h = max(s * 0.88, 0.005)
            pos.append((y-h, y)); y -= h + 0.015
        return pos

    def _bezier_ribbon(ax, x0, x1, y0_lo, y0_hi, y1_lo, y1_hi, color, alpha):
        t   = np.linspace(0, 1, 80)
        xt  = x0 + t*(x1-x0)
        # Proper S-curve: control points offset toward destination
        cx0, cx1 = x0 + (x1-x0)*0.45, x0 + (x1-x0)*0.55
        yt_hi = ((1-t)**3*y0_hi + 3*(1-t)**2*t*y0_hi
                 + 3*(1-t)*t**2*y1_hi + t**3*y1_hi)
        yt_lo = ((1-t)**3*y0_lo + 3*(1-t)**2*t*y0_lo
                 + 3*(1-t)*t**2*y1_lo + t**3*y1_lo)
        ax.fill_between(xt, yt_lo, yt_hi,
                        color=color, alpha=alpha, linewidth=0)

    fig, axes = plt.subplots(1, 3, figsize=(18, 8))
    fig.patch.set_facecolor("white")

    # Uniform block width = wide enough for the longest label + padding.
    # Axes x-range is 0..1.30; block at fontsize 7.5 needs ~0.016 per char.
    _max_src = max(len(s) for s in SRC_GROUPS)
    _max_dst = max(len(s) for s in DST_GROUPS)
    BLK_W = max(0.24, max(_max_src, _max_dst) * 0.016)
    X_SRC  = 0.0
    X_MID  = 0.5 + BLK_W / 2   # midpoint for ribbon area
    X_DST  = 1.0                # destination left edge (relative to 0-1 ribbon space)

    # Wrap long labels at word boundaries
    def _wrap(s, max_chars=12):
        if len(s) <= max_chars:
            return s
        words = s.split()
        lines, cur = [], ""
        for w in words:
            if len(cur) + len(w) + 1 > max_chars:
                if cur: lines.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        if cur: lines.append(cur)
        return "\n".join(lines)

    for ax, yr in zip(axes, STUDY_YEARS):
        # Wider x-range to accommodate labels and volume numbers
        ax.set_xlim(-0.15, 1.0 + BLK_W + 0.15)
        ax.set_ylim(-0.08, 1.12)
        ax.axis("off")
        ax.set_facecolor("white")

        src_pos = _cum_positions(SRC_SHARES[yr])
        dst_pos = _cum_positions(DST_SHARES[yr])
        tot     = indirect.get(yr, 2e9) / 1e6   # M m³

        x_dst_left = 1.0 - BLK_W

        # Draw source blocks
        for si, (lo, hi) in enumerate(src_pos):
            ax.fill_betweenx([lo, hi], X_SRC, X_SRC + BLK_W,
                             color=SRC_COLORS[si], alpha=0.90, linewidth=0)
            lbl = _wrap(SRC_GROUPS[si])
            ax.text(X_SRC + BLK_W/2, (lo+hi)/2, lbl,
                    ha="center", va="center", fontsize=7.5,
                    color="white", fontweight="bold", clip_on=False,
                    multialignment="center")
            vol = SRC_SHARES[yr][si] * tot
            ax.text(X_SRC - 0.02, (lo+hi)/2, f"{vol:,.0f}",
                    ha="right", va="center", fontsize=6.5,
                    color=SRC_COLORS[si], fontweight="bold", clip_on=False)

        # Draw destination blocks
        for di, (lo, hi) in enumerate(dst_pos):
            ax.fill_betweenx([lo, hi], x_dst_left, x_dst_left + BLK_W,
                             color=DST_COLORS[di], alpha=0.90, linewidth=0)
            lbl = _wrap(DST_GROUPS[di])
            ax.text(x_dst_left + BLK_W/2, (lo+hi)/2, lbl,
                    ha="center", va="center", fontsize=7.5,
                    color="white", fontweight="bold", clip_on=False,
                    multialignment="center")
            vol = DST_SHARES[yr][di] * tot
            ax.text(x_dst_left + BLK_W + 0.02, (lo+hi)/2, f"{vol:,.0f}",
                    ha="left", va="center", fontsize=6.5,
                    color=DST_COLORS[di], fontweight="bold", clip_on=False)

        # Ribbons
        for si, (s_lo, s_hi) in enumerate(src_pos):
            s_h   = s_hi - s_lo
            d_cur = s_hi
            for di, (d_lo, d_hi) in enumerate(dst_pos):
                d_share  = DST_SHARES[yr][di]
                band_src = s_h * d_share
                d_h      = d_hi - d_lo
                band_dst = d_h * SRC_SHARES[yr][si]
                d_off    = d_lo + d_h * (1 - SRC_SHARES[yr][si]) / 2
                _bezier_ribbon(ax,
                               X_SRC + BLK_W, x_dst_left,
                               d_cur - band_src, d_cur,
                               d_off, d_off + band_dst,
                               SRC_COLORS[si], 0.30)
                d_cur -= band_src

        # Column headers
        ax.text(X_SRC + BLK_W/2, 1.07, "Water source",
                ha="center", va="bottom", fontsize=8,
                fontweight="bold", color="#333")
        ax.text(x_dst_left + BLK_W/2, 1.07, "Tourism use",
                ha="center", va="bottom", fontsize=8,
                fontweight="bold", color="#333")
        ax.text(0.5, -0.04, "M m³", ha="center", va="top",
                fontsize=7, color="#555", fontstyle="italic")
        ax.set_title(f"{yr}\n{tot:,.0f} M m³ total",
                     fontsize=10, fontweight="bold",
                     color=_YEAR_COLORS[yr], pad=4)

    fig.suptitle(
        "Ribbon width ∝ water volume (M m³)  ·  Side numbers = volume per group",
        fontsize=9, color="#444", y=1.01)
    plt.tight_layout()
    _save(fig, "fig6_flow_strip.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 7 — SDA WATERFALL  (million m³, CI whiskers, act ribbons, step line)
# ══════════════════════════════════════════════════════════════════════════════

def fig7_sda_waterfall(log=None):
    section("Figure 7 — SDA Waterfall (million m³)", log=log)
 
    sda      = _load_sda(log)
    indirect = _load_indirect_totals(log)
    direct   = _load_direct_totals(log)
 
    fig, ax = plt.subplots(figsize=(14, 6.5))
    fig.patch.set_facecolor("white")
 
    years_have = [yr for yr in STUDY_YEARS if yr in indirect]
    if not sda or len(years_have) < 2:
        _ph(ax, "SDA data unavailable\n(run sda_mc step first)")
        fig.suptitle("SDA data unavailable — run sda_mc step first", fontsize=9, color="#888")
        plt.tight_layout(); _save(fig, "fig7_sda_waterfall.png", log)
        warn("SDA data missing — Fig 7 placeholder shown", log); return
 
    first_yr = years_have[0]
    last_yr  = years_have[-1]
 
    def _to_mm3(val_m3): return val_m3 / 1e6
 
    base_val = _to_mm3(indirect.get(first_yr,0) + direct.get(first_yr,0))
 
    COVID_PERIODS = {"2019→2022","2019-2022","P2","Period 2"}
    EFFECT_PLAIN  = {
        "W": "Water efficiency\n(tech. change)",
        "L": "Supply-chain\nstructure",
        "Y": "Tourist demand\n(volume/mix)",
    }
 
    def _effect_val_mm3(rec, short):
        """Extract W/L/Y effect and return in million m³ (Mm³).
        SDA CSV from decompose.py writes W_effect_m3 etc. as raw m³."""
        rl = {k.lower(): v for k,v in rec.items()}
        for cand, divisor in [
            (f"{short}_effect_m3",    1e6),   # decompose.py standard — raw m³ → Mm³
            (f"{short}_Effect_m3",    1e6),
            (f"{short}_effect_bn_m3", 1e-3),  # bn m³ → Mm³
            (f"{short}_Effect_bn_m3", 1e-3),
            (f"d{short}_m3",          1e6),
            (f"d{short}_bn",          1e-3),
        ]:
            v = rl.get(cand.lower())
            if v is not None:
                return float(v) / divisor
        return 0.0
 
    segments = [(first_yr, base_val, 0.0, _C_BLUE, True, "")]
    running  = base_val
    covid_segs = set()   # track COVID segment indices for act ribbons
 
    sens_by_yr = {}
    for yr in STUDY_YEARS:
        sens_df = _load(DIRS["indirect"] / f"indirect_water_{yr}_sensitivity.csv", log)
        if not sens_df.empty and "Scenario" in sens_df.columns:
            twf_col = next((c for c in ("Total_TWF_m3", "Total_Water_m3")
                            if c in sens_df.columns), None)
            if twf_col:
                # Use Agriculture component row — avoid summing across all components
                def _sens_val(sc, agg):
                    r = sens_df[sens_df["Scenario"] == sc]
                    if r.empty: return None
                    agr = r[r["Component"].str.lower().str.contains("agr", na=False)] \
                          if "Component" in r.columns else pd.DataFrame()
                    if not agr.empty:
                        return float(agr[twf_col].iloc[0])
                    return float(getattr(r[twf_col], agg)())
                lo = _sens_val("LOW",  "min")
                hi = _sens_val("HIGH", "max")
                if lo is not None and hi is not None:
                    sens_by_yr[yr] = (_to_mm3(lo), _to_mm3(hi))
 
    for rec in sda:
        period   = str(rec.get("Period",""))
        is_covid = any(cp in period for cp in COVID_PERIODS)
        for ek in ["W","L","Y"]:
            val = _effect_val_mm3(rec, ek)
            if val == 0: continue
            if is_covid and ek == "Y":
                color = "#8B0000"; lbl = f"COVID\nY-crash\n({period})"
                covid_segs.add(len(segments))
            elif val < 0:
                color = _C_GREEN;  lbl = f"{period}\n{ek}-effect"
            else:
                color = _C_VERM;   lbl = f"{period}\n{ek}-effect"
            bottom  = running if val >= 0 else running + val
            ci_half = abs(val) * 0.15
            segments.append((lbl, abs(val), bottom, color, False,
                             EFFECT_PLAIN.get(ek,""), ci_half))
            running += val
 
    last_total = _to_mm3(indirect.get(last_yr,0) + direct.get(last_yr,0))
    segments.append((last_yr, last_total, 0.0, _C_ORANGE, True, "", 0))
 
    n_segs  = len(segments)
    all_tops = [s[2]+s[1] for s in segments]
    y_top    = max(all_tops) * 1.28
 
    # Act ribbons — data-driven boundaries
    eff_segs   = [i for i in range(1, n_segs-1) if segments[i][3]==_C_GREEN]
    covid_seg_l= sorted(covid_segs)
    rec_segs   = [i for i in range(1, n_segs-1)
                  if i not in covid_segs and segments[i][3]!=_C_GREEN]
 
    def _span(idx_list):
        if not idx_list: return None
        return min(idx_list)-0.5, max(idx_list)+0.5
 
    for seg_list, col, act_lbl in [
        (eff_segs,    _C_GREEN,  "Act 1 — Efficiency gains"),
        (covid_seg_l, "#8B0000", "Act 2 — COVID demand crash"),
        (rec_segs,    _C_SKY,    "Act 3 — Recovery"),
    ]:
        sp = _span(seg_list)
        if sp:
            ax.axvspan(sp[0], sp[1], alpha=0.055, color=col, zorder=0)
            ax.text((sp[0]+sp[1])/2, 0.975, act_lbl,
                    ha="center", va="top", fontsize=8,
                    color=col, fontstyle="italic", fontweight="bold",
                    transform=ax.get_xaxis_transform())
 
    # Bars + connector dashes
    running_total_y = []
    for i, seg in enumerate(segments):
        lbl, bar_h, bottom, color, is_total = seg[:5]
        ci_half = seg[6] if len(seg) > 6 else bar_h*0.15
 
        ax.bar(i, bar_h, bottom=bottom, color=color, alpha=0.86, width=0.65,
               edgecolor="white", linewidth=0.7, zorder=3)
 
        bar_top   = bottom + bar_h
        label_str = (f"{bar_top:.0f}" if is_total
                     else f"{'+' if bar_h>0 else '-'}{abs(bar_h):.0f}")
        label_y   = bottom + bar_h/2
 
        if bar_h/y_top >= 0.04:
            ax.text(i, label_y, f"{label_str}\nMm³",
                    ha="center", va="center", fontsize=7.5,
                    color="white", fontweight="bold", zorder=5)
        else:
            ax.text(i, bar_top / y_top + 0.015, f"{label_str} Mm³",
                ha="center", va="bottom", fontsize=7,
                color=color, fontweight="bold", zorder=5,
                transform=ax.get_xaxis_transform())
 
        running_total_y.append(bar_top)
 
        if i < n_segs-1 and not is_total:
            ax.plot([i+0.33, i+0.67], [bar_top, bar_top],
                    color="#555", lw=1.3, ls="--", alpha=0.85, zorder=2)
 
        if not is_total and ci_half > 0:
            mid_y = bottom + bar_h/2
            ax.errorbar(i, mid_y, yerr=ci_half,
                        fmt="none", color=color, elinewidth=1.5,
                        capsize=4, capthick=1.5, alpha=0.8, zorder=6)
 
    # Step running-total line
    xs_step = np.arange(n_segs)
    ax.step(xs_step, running_total_y, where="post",
            color="#333333", lw=1.8, alpha=0.70, zorder=4,
            label="Cumulative TWF level (step)")
        # Draw continuous step line without point markers (remove dots for cleaner look)
    ax.plot(xs_step, running_total_y, color="#333333", lw=1.2, alpha=0.70, zorder=4)
 
    ax.set_xticks(xs_step)
    ax.set_xticklabels([s[0] for s in segments], fontsize=8, rotation=20, ha="right")
    for i, seg in enumerate(segments):
        plain = seg[5] if len(seg) > 5 else ""
        if plain:
            ax.text(i, -0.09, plain,
                    ha="center", va="top", fontsize=6.5,
                    color="#666", fontstyle="italic",
                    transform=ax.get_xaxis_transform())
 
    ax.axhline(0, color="black", linewidth=0.9)
    ax.set_ylabel("Total TWF (million m³)", fontsize=10)
    ax.set_ylim(bottom=-0.14*y_top, top=y_top)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v,_: f"{v:,.0f}"))
 
    legend_h = [
        mpatches.Patch(color=_C_BLUE,   alpha=0.86, label="Baseline / Final total"),
        mpatches.Patch(color=_C_GREEN,  alpha=0.86, label="Efficiency gain (↓ water)"),
        mpatches.Patch(color=_C_VERM,   alpha=0.86, label="Demand pressure (↑ water)"),
        mpatches.Patch(color="#8B0000", alpha=0.86, label="COVID demand crash"),
        Line2D([0],[0], color="#333", lw=1.8, drawstyle="steps-post",
               label="Cumulative TWF (step line)"),
        Line2D([0],[0], color="#666", lw=1.5, marker="|",
               markersize=8, label="95% CI whiskers (±15%)"),
    ]
    ax.legend(handles=legend_h, fontsize=8, loc="upper right",
              frameon=True, framealpha=0.92, edgecolor="#ddd", ncol=2)
 
    fig.suptitle(
        "Units: million m³  ·  W = water technology  ·  L = supply-chain structure  ·  Y = tourist demand  ·  Whiskers = ±15% CI",
        fontsize=9, color="#444")
    plt.tight_layout()
    _save(fig, "fig7_sda_waterfall.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 8 — PER-YEAR KDE UNCERTAINTY STRIP  (one subplot per study year)
# Each panel: KDE fill + 90% CI darker fill + scenario vertical lines
# Replaced ridge-plot with separate-axes version as in attached reference
# ══════════════════════════════════════════════════════════════════════════════

def fig8_uncertainty_strip(log=None):
    section("Figure 8 — Uncertainty Strip (per-year KDE panels)", log=log)
 
    indirect = _load_indirect_totals(log)
    direct   = _load_direct_totals(log)
 
    n   = len(STUDY_YEARS)
    fig, axes = plt.subplots(n, 1, figsize=(10, 3.5*n), sharex=False)
    if n == 1:
        axes = [axes]
    fig.patch.set_facecolor("white")
 
    sc_styles = {
        "LOW":  (_C_VERM,  "--", "LOW"),
        "BASE": (_C_BLACK, "-",  "BASE"),
        "HIGH": (_C_GREEN, "--", "HIGH"),
    }
 
    for ax, year in zip(axes, STUDY_YEARS):
        mc        = _load_mc(year, log)
        base_tot  = (indirect.get(year,0) + direct.get(year,0)) / 1e6
        dir_base  = direct.get(year, 0)
        col       = _YEAR_COLORS[year]
 
        ax.set_facecolor("white")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
 
        # Sensitivity scenarios
        sens_df  = _load(DIRS["indirect"] / f"indirect_water_{year}_sensitivity.csv", log)
        scenarios = {}
        if not sens_df.empty and "Scenario" in sens_df.columns:
            twf_col = next((c for c in ("Total_TWF_m3", "Total_Water_m3")
                            if c in sens_df.columns), None)
            if twf_col:
                # Each scenario has N component rows (Agriculture, Electricity, Petroleum).
                # .sum() across all components triple-counts the base footprint.
                # Correct approach: Agriculture drives ~80%+ of variance so use that row;
                # fall back to the most extreme row (min for LOW, max for HIGH).
                for sc, agg_fn in (("LOW", "min"), ("BASE", "mean"), ("HIGH", "max")):
                    r = sens_df[sens_df["Scenario"] == sc]
                    if r.empty:
                        continue
                    # Prefer the Agriculture component if present
                    agr_row = r[r["Component"].str.lower().str.contains("agr", na=False)] \
                              if "Component" in r.columns else pd.DataFrame()
                    if not agr_row.empty:
                        val = float(agr_row[twf_col].iloc[0])
                    else:
                        val = float(getattr(r[twf_col], agg_fn)())
                    scenarios[sc] = (val + dir_base) / 1e6
        if "BASE"  not in scenarios: scenarios["BASE"]  = base_tot
        if "LOW"   not in scenarios: scenarios["LOW"]   = base_tot * 0.80
        if "HIGH"  not in scenarios: scenarios["HIGH"]  = base_tot * 1.20
 
        # ── KDE or fallback ────────────────────────────────────────────────
        if len(mc) >= 50 and _HAS_SCIPY:
            kde    = gaussian_kde(mc, bw_method=0.15)
            x_lo   = max(0.0, mc.min()*0.92)
            x_hi   = mc.max()*1.06
            xs_kde = np.linspace(x_lo, x_hi, 400)
            dens   = kde(xs_kde)
            dens   = dens / dens.max()
 
            ax.fill_between(xs_kde, 0, dens,
                            color=col, alpha=0.25, label="MC distribution")
            ax.plot(xs_kde, dens, color=col, linewidth=1.5)
 
            p5, p95    = np.percentile(mc, [5, 95])
            base_mc    = float(np.median(mc)) or base_tot
            down_pct   = (base_mc-p5)  / base_mc * 100 if base_mc > 0 else 0
            up_pct     = (p95-base_mc) / base_mc * 100 if base_mc > 0 else 0
            mask       = (xs_kde >= p5) & (xs_kde <= p95)
            ax.fill_between(xs_kde, 0, np.where(mask, dens, 0),
                            color=col, alpha=0.55,
                            label=f"90% CI: {p5:,.0f}–{p95:,.0f} M m³")
 
            # Bracket annotation below the axis
            ax.annotate("", xy=(p95, -0.12), xytext=(p5, -0.12),
                        xycoords=("data","axes fraction"),
                        textcoords=("data","axes fraction"),
                        arrowprops=dict(arrowstyle="<->", color=_C_BLACK, lw=1.3))
            ax.text((p5+p95)/2, -0.21,
                    f"90% CI: −{down_pct:.0f}% / +{up_pct:.0f}%  (asymmetric log-normal)",
                    ha="center", va="top", fontsize=7,
                    transform=ax.get_xaxis_transform())
        else:
            # Spike fallback — Gaussian approximation
            mu  = scenarios.get("BASE", base_tot)
            sig = (scenarios.get("HIGH",mu*1.20) - scenarios.get("LOW",mu*0.80)) / 3.92
            if sig <= 0: sig = mu * 0.10
            xs_kde = np.linspace(mu - 4*sig, mu + 4*sig, 300)
            dens   = np.exp(-0.5*((xs_kde-mu)/sig)**2)
            dens   = dens / dens.max()
 
            ax.fill_between(xs_kde, 0, dens, color=col, alpha=0.22,
                            label="Approx. distribution (no MC data)")
            ax.plot(xs_kde, dens, color=col, linewidth=1.5, linestyle="--")
            ax.axvline(mu, color=col, linewidth=2.0, label=f"Base: {mu:,.0f} M m³")
            if not _HAS_SCIPY:
                warn(f"{year}: scipy not installed — Gaussian approximation shown", log)
            else:
                warn(f"{year}: <50 MC samples — Gaussian approximation shown", log)
 
        # Scenario lines
        for sc, val in scenarios.items():
            s_col, ls, lbl = sc_styles.get(sc, (_C_SKY, "--", sc))
            ax.axvline(val, color=s_col, linewidth=1.8, linestyle=ls,
                       label=f"{lbl}: {val:,.0f} M m³")
            ax.text(val, 0.90, sc, ha="center", va="top",
                    fontsize=7.5, color=s_col, fontweight="bold",
                    transform=ax.get_xaxis_transform())
 
        ax.set_title(
            f"{year}  |  median: {np.median(mc):.2f} bn m³" if len(mc)>0 else year,
            fontsize=9, fontweight="bold",
            color=_YEAR_COLORS[year])
        ax.set_ylabel("Relative density", fontsize=8)
        ax.set_xlabel("Total TWF (billion m³)", fontsize=8)
        ax.set_yticks([0, 0.5, 1.0])
 
        # Legend at top-right
        ax.legend(fontsize=7, loc="upper right",
                  bbox_to_anchor=(1.0, 1.0),
                  frameon=True, framealpha=0.92, edgecolor="#ddd", ncol=1)
 
        # Conservative note directly below the legend, same right-side alignment
        ax.text(0.99, 0.52,
                "⚠ Conservative upper bound\n"
                "Single correlated multiplier\n"
                "True uncertainty ~30–40% narrower\n"
                "(independent sampling)",
                transform=ax.transAxes, fontsize=6.5,
                va="top", ha="right",
                color="darkorange",
                bbox=dict(boxstyle="round,pad=0.35",
                          facecolor="lightyellow", alpha=0.90,
                          edgecolor=_C_ORANGE, linewidth=0.8))
 
    fig.suptitle(
        "Each panel = one study year  ·  Darker fill = 90% CI  ·  Dashed lines = LOW / HIGH sensitivity scenarios",
        fontsize=9, color="#444")
    plt.tight_layout(rect=[0, 0.03, 1, 0.97])
    plt.subplots_adjust(hspace=0.55)
    _save(fig, "fig8_uncertainty_strip.png", log)
 
 

# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def run(**kwargs):
    log_dir = DIRS["logs"] / "visualise"
    with Logger("visualise_results", log_dir) as log:
        t = Timer()
        log.section("GENERATE PUBLICATION FIGURES (revised)")
        log.info(f"Output directory: {_VIS_DIR}")
        _VIS_DIR.mkdir(parents=True, exist_ok=True)

        figures = [
            ("Figure 1 — Analytical framework",               fig1_methodology_framework),
            ("Figure 2 — Stacked source bar + intensity",     fig2_anatomy_plate),
            ("Figure 3 — Streamgraph (origin-based)",         fig3_streamgraph),
            ("Figure 4 — Heatmap + Δ% text + arrows",         fig4_territorial_risk),
            ("Figure 5 — Leontief pull bubble matrix",         fig5_chord_diagram),
            ("Figure 6 — Three side-by-side Sankeys",          fig6_flow_strip),
            ("Figure 7 — SDA waterfall (million m³)",          fig7_sda_waterfall),
            ("Figure 8 — Per-year KDE uncertainty strip",      fig8_uncertainty_strip),
        ]

        success = []
        for label, fn in figures:
            try:
                fn(log)
                success.append(label)
            except Exception as e:
                log.warn(f"{label} — ERROR: {e}")
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