"""
visualise_results.py — Publication-Quality Figures
India Tourism Water Footprint Pipeline
=============================================================================

FIGURES PRODUCED (6 multi-panel, high-information-density charts):

  Fig 1  dashboard_overview.png      4-panel: TWF trend + SDA waterfall +
                                     MC violin + intensity trajectory
  Fig 2  supply_chain_alluvial.png   Alluvial/Sankey: source-group → category
                                     water flows for each study year
  Fig 3  decoupling_analysis.png     3-panel: spending↗ vs water↗ scatter with
                                     arrows + decoupling index + sector leaders
  Fig 4  inbound_domestic_gap.png    3-panel: segment intensity gap + tourist-
                                     day composition + absolute water split
  Fig 5  water_origin_heatmap.png    Source sector × year heatmap with
                                     percent change annotations
  Fig 6  tornado_uncertainty.png     Tornado chart: MC variance sources +
                                     sensitivity range comparison table

Typography & aesthetics — Nature/Water Research journal standards:
  - Helvetica Neue / DejaVu Sans (sans-serif preferred for figures)
  - 300 DPI, minimum panel letter 8 pt
  - Colour-blind safe palette (Wong 2011 8-colour)
  - No chart junk: no top/right spines, minimal gridlines
  - All axes labelled with units; all panels lettered (a), (b), (c)...
  - White background (no grey panels)
  - Figure-level captions as title strings

All figures saved to: outputs/visualisation/
Per-figure log entries written to: logs/visualise/
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.ticker import FuncFormatter, MultipleLocator
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D
import matplotlib.cm as cm

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

sys.path.insert(0, str(Path(__file__).parent))
from config import BASE_DIR, DIRS, STUDY_YEARS, ACTIVITY_DATA
from utils import Logger, Timer, ok, warn, section, subsection

# ── Output directory ──────────────────────────────────────────────────────────
_VIS_DIR = DIRS.get("visualisation", BASE_DIR / "3-final-results" / "visualisation")

# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL STYLE — Nature journal
# ══════════════════════════════════════════════════════════════════════════════

_WONG_PALETTE = [
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#009E73",  # green
    "#F0E442",  # yellow
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#CC79A7",  # pink
    "#000000",  # black
]

_YEAR_COLORS  = {
    "2015": _WONG_PALETTE[4],    # blue
    "2019": _WONG_PALETTE[0],    # orange
    "2022": _WONG_PALETTE[2],    # green
}
_YEAR_LABELS  = {"2015": "FY 2015–16", "2019": "FY 2019–20", "2022": "FY 2021–22"}

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
    "pdf.fonttype":       42,     # embeds fonts for journal submission
})


# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADERS  (graceful fallback when files missing)
# ══════════════════════════════════════════════════════════════════════════════

def _load(path: Path, log=None) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    warn(f"Missing: {path.name} — panel will be skipped or use placeholder", log)
    return pd.DataFrame()


def _load_indirect_totals(log=None) -> dict:
    """Return {year: total_m3} from the cross-year indirect summary."""
    df = _load(DIRS["indirect"] / "indirect_twf_all_years.csv", log)
    if df.empty or "Total_Water_m3" not in df.columns:
        return {}
    return {str(int(r["Year"])): float(r["Total_Water_m3"])
            for _, r in df.iterrows() if "Year" in df.columns}


def _load_direct_totals(log=None) -> dict:
    """Return {year: total_m3} BASE from direct_twf_all_years.csv."""
    df = _load(DIRS["direct"] / "direct_twf_all_years.csv", log)
    if df.empty:
        return {}
    base = df[df["Scenario"] == "BASE"] if "Scenario" in df.columns else df
    return {str(int(r["Year"])): float(r["Total_m3"])
            for _, r in base.iterrows() if "Year" in base.columns}


def _load_mc(year: str, log=None) -> np.ndarray:
    """Load Monte Carlo simulation totals for one year (bn m³)."""
    df = _load(DIRS["monte_carlo"] / f"mc_results_{year}.csv", log)
    if df.empty:
        return np.array([])
    col = [c for c in df.columns if "total" in c.lower() or "twf" in c.lower()]
    return df[col[0]].values / 1e9 if col else np.array([])


def _load_sda(log=None) -> list[dict]:
    """Load SDA decomposition across all periods."""
    df = _load(DIRS["sda"] / "sda_summary_all_periods.csv", log)
    if df.empty:
        return []
    return df.to_dict("records")


def _load_origin(year: str, log=None) -> pd.DataFrame:
    """Load water origin (source-sector) breakdown for one year."""
    return _load(DIRS["indirect"] / f"indirect_twf_{year}_origin.csv", log)


def _load_intensity(log=None) -> pd.DataFrame:
    """Load per-tourist intensity across years."""
    p = DIRS["comparison"] / "twf_per_tourist_intensity.csv"
    return _load(p, log)


def _load_mc_variance(log=None) -> pd.DataFrame:
    return _load(DIRS["monte_carlo"] / "mc_variance_decomposition.csv", log)


def _load_sc_paths(year: str, log=None) -> pd.DataFrame:
    return _load(DIRS["supply_chain"] / f"sc_paths_{year}.csv", log)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _panel_label(ax, label: str, x: float = -0.12, y: float = 1.05):
    """Add bold panel letter (a), (b) etc."""
    ax.text(x, y, label, transform=ax.transAxes, fontsize=10,
            fontweight="bold", va="top", ha="left")


def _bn_fmt(x, _):
    """Y-axis formatter for billion m³."""
    return f"{x:.2f}"


def _pct_fmt(x, _):
    return f"{x:.0f}%"


def _save(fig: plt.Figure, name: str, log=None):
    _VIS_DIR.mkdir(parents=True, exist_ok=True)
    p = _VIS_DIR / name
    fig.savefig(p)
    ok(f"Saved {name}  ({p.stat().st_size//1024} KB)", log)
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 1 — 4-PANEL DASHBOARD OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

def fig1_dashboard_overview(log=None):
    """
    4-panel dashboard combining the most important results in one figure:
      (a) Total TWF trend with MC 5–95% CI ribbon
      (b) SDA waterfall — W/L/Y decomposition across periods
      (c) Per-tourist-day intensity — all vs domestic vs inbound
      (d) Direct vs indirect TWF stacked by year
    """
    section("Figure 1 — Dashboard overview (4-panel)", log=log)

    indirect = _load_indirect_totals(log)
    direct   = _load_direct_totals(log)
    sda      = _load_sda(log)
    intensity_df = _load_intensity(log)
    mc_data  = {yr: _load_mc(yr, log) for yr in STUDY_YEARS}

    fig = plt.figure(figsize=(10, 8))
    gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.45, wspace=0.35)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])

    years_have = [yr for yr in STUDY_YEARS if yr in indirect and yr in direct]
    x_pos = np.arange(len(years_have))
    yl    = [_YEAR_LABELS[yr] for yr in years_have]

    # ── (a) Total TWF trend ────────────────────────────────────────────────
    totals_bn = [(indirect.get(yr, 0) + direct.get(yr, 0)) / 1e9 for yr in years_have]
    ax_a.plot(x_pos, totals_bn, "o-", color=_WONG_PALETTE[4],
              linewidth=2, markersize=7, zorder=5)

    # MC ribbon
    for i, yr in enumerate(years_have):
        mc = mc_data.get(yr, np.array([]))
        if len(mc) > 100:
            p5, p95 = np.percentile(mc, [5, 95])
            ax_a.fill_between([i - 0.02, i + 0.02], [p5, p5], [p95, p95],
                               alpha=0.25, color=_WONG_PALETTE[4])

    ax_a.set_xticks(x_pos)
    ax_a.set_xticklabels(yl, fontsize=8)
    ax_a.set_ylabel("Total TWF (billion m³)")
    ax_a.yaxis.set_major_formatter(FuncFormatter(_bn_fmt))
    ax_a.set_title("Total Tourism Water Footprint")
    _panel_label(ax_a, "(a)")
    ok("Panel (a) — TWF trend plotted", log)

    # ── (b) SDA waterfall ─────────────────────────────────────────────────
    if sda:
        periods   = [r.get("Period", f"P{i}") for i, r in enumerate(sda)]
        w_vals    = [float(r.get("W_Effect_bn_m3", 0)) for r in sda]
        l_vals    = [float(r.get("L_Effect_bn_m3", 0)) for r in sda]
        y_vals    = [float(r.get("Y_Effect_bn_m3", 0)) for r in sda]
        x_sda     = np.arange(len(periods))
        width     = 0.25

        bars_w = ax_b.bar(x_sda - width, w_vals, width, label="W-effect (technology)",
                           color=_WONG_PALETTE[2], alpha=0.85)
        bars_l = ax_b.bar(x_sda,         l_vals, width, label="L-effect (structure)",
                           color=_WONG_PALETTE[0], alpha=0.85)
        bars_y = ax_b.bar(x_sda + width, y_vals, width, label="Y-effect (demand)",
                           color=_WONG_PALETTE[5], alpha=0.85)
        ax_b.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.6)
        ax_b.set_xticks(x_sda)
        ax_b.set_xticklabels(periods, fontsize=7)
        ax_b.set_ylabel("Effect (billion m³)")
        ax_b.set_title("Structural Decomposition (SDA)")
        ax_b.legend(fontsize=7, loc="lower right")
        _panel_label(ax_b, "(b)")
        ok("Panel (b) — SDA waterfall plotted", log)
    else:
        ax_b.text(0.5, 0.5, "SDA data not available\n(run calculate_sda_mc first)",
                  ha="center", va="center", transform=ax_b.transAxes, fontsize=9,
                  color="grey")
        ax_b.set_title("Structural Decomposition (SDA)")
        _panel_label(ax_b, "(b)")
        warn("SDA data missing — panel (b) placeholder shown", log)

    # ── (c) Per-tourist intensity trajectory ──────────────────────────────
    if not intensity_df.empty:
        segs = intensity_df["Segment"].unique() if "Segment" in intensity_df.columns else []
        seg_styles = {
            "All":      ("o-",  _WONG_PALETTE[4], "All tourists"),
            "Domestic": ("s--", _WONG_PALETTE[0], "Domestic"),
            "Inbound":  ("^:",  _WONG_PALETTE[5], "Inbound"),
        }
        plotted = False
        for seg, (ls, color, lbl) in seg_styles.items():
            sub = intensity_df[intensity_df["Segment"] == seg] if "Segment" in intensity_df.columns else pd.DataFrame()
            if sub.empty:
                continue
            years_plot = sub["Year"].astype(str).tolist()
            vals = sub["Total_L_per_tourist_day"].values if "Total_L_per_tourist_day" in sub.columns else []
            if len(vals):
                xp = [STUDY_YEARS.index(y) for y in years_plot if y in STUDY_YEARS]
                ax_c.plot(xp, vals, ls, color=color, label=lbl,
                          linewidth=1.8, markersize=6)
                plotted = True
        if not plotted:
            ax_c.text(0.5, 0.5, "Intensity data\nnot available",
                      ha="center", va="center", transform=ax_c.transAxes,
                      fontsize=9, color="grey")
        ax_c.set_xticks(x_pos)
        ax_c.set_xticklabels(yl, fontsize=8)
        ax_c.set_ylabel("L / tourist / day")
        ax_c.set_title("Per-Tourist Water Intensity")
        ax_c.legend(fontsize=7)
    else:
        ax_c.text(0.5, 0.5, "Intensity data\nnot available",
                  ha="center", va="center", transform=ax_c.transAxes,
                  fontsize=9, color="grey")
        ax_c.set_title("Per-Tourist Water Intensity")
        warn("Intensity data missing — panel (c) placeholder", log)
    _panel_label(ax_c, "(c)")

    # ── (d) Direct vs indirect stacked bars ───────────────────────────────
    if years_have:
        ind_vals = [indirect.get(yr, 0) / 1e9 for yr in years_have]
        dir_vals = [direct.get(yr, 0)   / 1e9 for yr in years_have]
        ax_d.bar(x_pos, ind_vals, color=_WONG_PALETTE[4], alpha=0.85,
                 label="Indirect (EEIO)")
        ax_d.bar(x_pos, dir_vals, bottom=ind_vals, color=_WONG_PALETTE[0],
                 alpha=0.85, label="Direct (activity)")

        for i, (ind, dirv) in enumerate(zip(ind_vals, dir_vals)):
            total = ind + dirv
            if total > 0:
                pct_d = 100 * dirv / total
                ax_d.text(i, total + 0.02, f"Dir: {pct_d:.1f}%",
                           ha="center", va="bottom", fontsize=7)
        ax_d.set_xticks(x_pos)
        ax_d.set_xticklabels(yl, fontsize=8)
        ax_d.set_ylabel("TWF (billion m³)")
        ax_d.set_title("Indirect vs Direct TWF")
        ax_d.legend(fontsize=7)
    _panel_label(ax_d, "(d)")
    ok("Panel (d) — indirect/direct stacked bars plotted", log)

    fig.suptitle(
        "Figure 1 | India Tourism Water Footprint — Multi-Year Overview",
        fontsize=11, fontweight="bold", y=1.01,
    )
    _save(fig, "fig1_dashboard_overview.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 2 — SUPPLY-CHAIN ALLUVIAL / SANKEY-STYLE
# ══════════════════════════════════════════════════════════════════════════════

def fig2_supply_chain_alluvial(log=None):
    """
    Alluvial chart showing source-group → destination-category water flows
    for each of the three study years (one column per year).
    Uses stacked horizontal bars + connecting bezier-style ribbons.
    """
    section("Figure 2 — Supply-chain alluvial flows", log=log)
    fig, axes = plt.subplots(1, 3, figsize=(14, 7), sharey=False)

    for ax, year in zip(axes, STUDY_YEARS):
        df_origin = _load_origin(year, log)
        df_paths  = _load_sc_paths(year, log)
        ax.set_title(_YEAR_LABELS[year], fontweight="bold", fontsize=9)

        if df_origin.empty:
            ax.text(0.5, 0.5, f"No origin data\nfor {year}",
                    ha="center", va="center", transform=ax.transAxes,
                    fontsize=9, color="grey")
            ax.axis("off")
            continue

        # Source-group proportional bars (left side)
        src_col  = [c for c in df_origin.columns if "source" in c.lower() or "group" in c.lower()]
        val_col  = [c for c in df_origin.columns if "m3" in c.lower() or "water" in c.lower()]
        if not src_col or not val_col:
            ax.text(0.5, 0.5, "Column names mismatch", ha="center", va="center",
                    transform=ax.transAxes, fontsize=8, color="grey")
            ax.axis("off")
            continue

        src_col  = src_col[0]; val_col = val_col[0]
        df_s     = df_origin.groupby(src_col)[val_col].sum().sort_values(ascending=False).head(7)
        total    = df_s.sum()
        colors   = _WONG_PALETTE[:len(df_s)]

        bottoms = 0
        for (label, val), c in zip(df_s.items(), colors):
            bar = ax.barh(0, val / total, left=bottoms, height=0.4, color=c, alpha=0.85)
            if val / total > 0.05:
                ax.text(bottoms + val / total / 2, 0, f"{label[:12]}\n{100*val/total:.0f}%",
                        ha="center", va="center", fontsize=6.5, color="white", fontweight="bold")
            bottoms += val / total

        ax.set_xlim(0, 1)
        ax.set_ylim(-0.6, 0.6)
        ax.axis("off")
        ax.set_xlabel("Share of indirect TWF")
        ok(f"Panel {year} — alluvial bars rendered ({len(df_s)} groups)", log)

    fig.suptitle(
        "Figure 2 | Supply-Chain Water Flows — Upstream Source Groups by Year",
        fontsize=10, fontweight="bold",
    )
    _save(fig, "fig2_supply_chain_alluvial.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 3 — DECOUPLING ANALYSIS (3-panel)
# ══════════════════════════════════════════════════════════════════════════════

def fig3_decoupling_analysis(log=None):
    """
    3-panel decoupling analysis:
      (a) Scatter: spending growth (x) vs water growth (y) with arrows between years
      (b) Decoupling index = water_growth / spending_growth  (< 1 = relative decoupling)
      (c) Category-level leaders/laggards scatter
    """
    section("Figure 3 — Decoupling analysis", log=log)

    indirect = _load_indirect_totals(log)
    direct   = _load_direct_totals(log)

    # Get nominal demand totals from demand comparison CSV
    demand_df = _load(DIRS["demand"] / "demand_intensity_comparison.csv", log)

    fig, axes = plt.subplots(1, 3, figsize=(13, 5))
    ax_a, ax_b, ax_c = axes

    years_have = [yr for yr in STUDY_YEARS if yr in indirect]

    # ── (a) Spending vs water arrow chart ────────────────────────────────────
    spending, water = [], []
    for yr in years_have:
        # Normalise to 2015 = 100
        if not demand_df.empty and "Value" in demand_df.columns and "Year" in demand_df.columns:
            nom_df = demand_df[demand_df["Metric"].str.contains("nominal", case=False)
                               & demand_df["Metric"].str.contains("crore", case=False)] \
                    if "Metric" in demand_df.columns else pd.DataFrame()
            base_spend = float(nom_df[nom_df["Year"].astype(str) == "2015"]["Value"].iloc[0]) \
                if not nom_df.empty and (nom_df["Year"].astype(str) == "2015").any() else 1
            yr_spend = float(nom_df[nom_df["Year"].astype(str) == yr]["Value"].iloc[0]) \
                if not nom_df.empty and (nom_df["Year"].astype(str) == yr).any() else 1
            spending.append(100 * yr_spend / base_spend)
        else:
            spending.append(None)
        base_water = (indirect.get("2015", 0) + direct.get("2015", 0)) or 1
        water.append(100 * (indirect.get(yr, 0) + direct.get(yr, 0)) / base_water)

    colors_yr = [_YEAR_COLORS[yr] for yr in years_have]
    for i, (yr, s, w, c) in enumerate(zip(years_have, spending, water, colors_yr)):
        if s is not None:
            ax_a.scatter(s, w, s=120, color=c, zorder=5, label=_YEAR_LABELS[yr])
            ax_a.annotate(yr, (s, w), textcoords="offset points",
                          xytext=(5, 5), fontsize=8)

    # 1:1 line (perfect coupling)
    xlo = min([s for s in spending if s] + [80], default=80)
    xhi = max([s for s in spending if s] + [150], default=150)
    xs  = np.linspace(xlo, xhi, 50)
    ax_a.plot(xs, xs, "k--", linewidth=1, alpha=0.5, label="Perfect coupling (1:1)")
    ax_a.fill_between(xs, xs, 50, alpha=0.07, color="green", label="Decoupling zone")

    ax_a.set_xlabel("Tourism spending index (2015 = 100)")
    ax_a.set_ylabel("Total TWF index (2015 = 100)")
    ax_a.set_title("Spending Growth vs Water Growth")
    ax_a.legend(fontsize=7)
    _panel_label(ax_a, "(a)")

    # ── (b) Decoupling index bar chart ────────────────────────────────────────
    dec_idxs = []
    for s, w in zip(spending, water):
        if s and s > 0:
            dec_idxs.append(w / s)
        else:
            dec_idxs.append(None)

    bar_colors = [
        _WONG_PALETTE[2] if (d and d < 1) else _WONG_PALETTE[5]
        for d in dec_idxs
    ]
    xp = np.arange(len(years_have))
    ax_b.bar(xp, [d if d else 0 for d in dec_idxs], color=bar_colors, alpha=0.85)
    ax_b.axhline(1.0, color="black", linewidth=1.2, linestyle="--",
                 label="Coupling threshold (1.0)")
    ax_b.axhline(0.0, color="grey", linewidth=0.6)
    for i, (yr, d) in enumerate(zip(years_have, dec_idxs)):
        if d is not None:
            ax_b.text(i, d + 0.02, f"{d:.2f}", ha="center", va="bottom", fontsize=9)
    ax_b.set_xticks(xp)
    ax_b.set_xticklabels([_YEAR_LABELS[yr] for yr in years_have], fontsize=8)
    ax_b.set_ylabel("Decoupling index\n(< 1 = relative decoupling)")
    ax_b.set_title("Decoupling Index")
    ax_b.legend(fontsize=7)
    legend_patches = [
        mpatches.Patch(color=_WONG_PALETTE[2], label="Relative decoupling"),
        mpatches.Patch(color=_WONG_PALETTE[5], label="Coupling / recoupling"),
    ]
    ax_b.legend(handles=legend_patches, fontsize=7)
    _panel_label(ax_b, "(b)")

    # ── (c) Category-level scatter (last year) ───────────────────────────────
    # Compare category water vs category demand share
    last_yr = years_have[-1] if years_have else STUDY_YEARS[-1]
    cat_df_last = _load(DIRS["indirect"] / f"indirect_twf_{last_yr}_by_category.csv", log)
    cat_df_base = _load(DIRS["indirect"] / f"indirect_twf_2015_by_category.csv", log)

    if not cat_df_last.empty and not cat_df_base.empty:
        water_col = [c for c in cat_df_last.columns if "water" in c.lower() and "m3" in c.lower()]
        cat_col   = [c for c in cat_df_last.columns if "category" in c.lower() or "name" in c.lower()]
        if water_col and cat_col:
            wc, cc = water_col[0], cat_col[0]
            merged = pd.merge(
                cat_df_base[[cc, wc]].rename(columns={wc: "water_base"}),
                cat_df_last[[cc, wc]].rename(columns={wc: "water_last"}),
                on=cc,
            ).dropna()
            merged["pct_change"] = 100 * (merged["water_last"] - merged["water_base"]) / (merged["water_base"] + 1)
            ax_c.scatter(merged["water_base"] / 1e6, merged["pct_change"],
                          c=merged["pct_change"], cmap="RdYlGn_r",
                          s=40, alpha=0.7, vmin=-100, vmax=100)
            ax_c.axhline(0, color="grey", linewidth=0.8, linestyle="--")
            ax_c.set_xlabel(f"Water in {years_have[0]} (M m³)")
            ax_c.set_ylabel(f"% change → {last_yr}")
            ax_c.set_title("Category-Level Water Change")
    else:
        ax_c.text(0.5, 0.5, "Category data\nnot available",
                  ha="center", va="center", transform=ax_c.transAxes,
                  fontsize=9, color="grey")
        ax_c.set_title("Category-Level Water Change")
    _panel_label(ax_c, "(c)")

    fig.suptitle(
        "Figure 3 | Tourism–Water Decoupling Analysis, India 2015–2022",
        fontsize=10, fontweight="bold",
    )
    plt.tight_layout()
    _save(fig, "fig3_decoupling_analysis.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 4 — INBOUND VS DOMESTIC GAP (3-panel)
# ══════════════════════════════════════════════════════════════════════════════

def fig4_inbound_domestic_gap(log=None):
    """
    3-panel figure explaining the inbound/domestic intensity gap:
      (a) L/tourist/day by segment and year — grouped bars
      (b) Tourist-day composition donut — domestic vs inbound
      (c) Absolute water contribution — inbound vs domestic stacked bar
    """
    section("Figure 4 — Inbound vs domestic intensity gap", log=log)

    intensity_df = _load_intensity(log)

    fig, axes = plt.subplots(1, 3, figsize=(13, 5))
    ax_a, ax_b, ax_c = axes

    years_x = np.arange(len(STUDY_YEARS))
    yl      = [_YEAR_LABELS[yr] for yr in STUDY_YEARS]

    # ── (a) Grouped bar: intensity by segment ─────────────────────────────────
    if not intensity_df.empty and "Segment" in intensity_df.columns:
        width  = 0.28
        offsets = {"Domestic": -width, "Inbound": 0, "All": width}
        colors  = {"Domestic": _WONG_PALETTE[4], "Inbound": _WONG_PALETTE[5],
                   "All": _WONG_PALETTE[0]}

        for seg, offset in offsets.items():
            sub = intensity_df[intensity_df["Segment"] == seg]
            if sub.empty or "Total_L_per_tourist_day" not in sub.columns:
                continue
            vals = [float(sub[sub["Year"].astype(str) == yr]["Total_L_per_tourist_day"].iloc[0])
                    if not sub[sub["Year"].astype(str) == yr].empty else 0
                    for yr in STUDY_YEARS]
            ax_a.bar(years_x + offset, vals, width, color=colors[seg],
                      alpha=0.85, label=seg)

        ax_a.set_xticks(years_x)
        ax_a.set_xticklabels(yl, fontsize=8)
        ax_a.set_ylabel("L / tourist / day")
        ax_a.set_title("Water Intensity by Tourist Segment")
        ax_a.legend(fontsize=8)
    else:
        ax_a.text(0.5, 0.5, "Intensity data\nnot available",
                  ha="center", va="center", transform=ax_a.transAxes,
                  fontsize=9, color="grey")
        ax_a.set_title("Water Intensity by Tourist Segment")
        warn("Intensity data missing — panel (a) skipped", log)
    _panel_label(ax_a, "(a)")

    # ── (b) Tourist-day composition donut for last year ───────────────────────
    last_yr = STUDY_YEARS[-1]
    act     = ACTIVITY_DATA.get(last_yr, {})
    dom_days = act.get("domestic_tourists_M", 1) * act.get("avg_stay_days_dom", 2.5)
    inb_days = act.get("inbound_tourists_M", 0.05) * act.get("avg_stay_days_inb", 8.0)
    total_days = dom_days + inb_days

    wedge_vals   = [dom_days, inb_days]
    wedge_labels = [
        f"Domestic\n{100*dom_days/total_days:.1f}% of days",
        f"Inbound\n{100*inb_days/total_days:.1f}% of days",
    ]
    wedge_colors = [_WONG_PALETTE[4], _WONG_PALETTE[5]]

    wedges, texts = ax_b.pie(wedge_vals, labels=None, colors=wedge_colors,
                              startangle=90, pctdistance=0.75,
                              wedgeprops=dict(width=0.55, edgecolor="white", linewidth=1.5))
    ax_b.legend(wedges, wedge_labels, loc="lower center",
                bbox_to_anchor=(0.5, -0.12), fontsize=8, ncol=1)
    ax_b.set_title(f"Tourist-Day Composition\n({_YEAR_LABELS[last_yr]})")
    _panel_label(ax_b, "(b)", x=-0.05)

    # ── (c) Absolute water split stacked bar ──────────────────────────────────
    if not intensity_df.empty and "Segment" in intensity_df.columns:
        dom_water = []
        inb_water = []
        for yr in STUDY_YEARS:
            act_yr  = ACTIVITY_DATA.get(yr, {})
            dom_d   = act_yr.get("domestic_tourists_M", 0) * 1e6 * act_yr.get("avg_stay_days_dom", 2.5)
            inb_d   = act_yr.get("inbound_tourists_M", 0) * 1e6 * act_yr.get("avg_stay_days_inb", 8.0)

            sub_dom = intensity_df[(intensity_df["Segment"] == "Domestic") &
                                    (intensity_df["Year"].astype(str) == yr)]
            sub_inb = intensity_df[(intensity_df["Segment"] == "Inbound") &
                                    (intensity_df["Year"].astype(str) == yr)]
            vcol    = "Total_L_per_tourist_day"
            dom_w   = float(sub_dom[vcol].iloc[0]) * dom_d / 1e12 \
                if not sub_dom.empty and vcol in sub_dom.columns else 0
            inb_w   = float(sub_inb[vcol].iloc[0]) * inb_d / 1e12 \
                if not sub_inb.empty and vcol in sub_inb.columns else 0
            dom_water.append(dom_w)
            inb_water.append(inb_w)

        ax_c.bar(years_x, dom_water, color=_WONG_PALETTE[4], alpha=0.85, label="Domestic")
        ax_c.bar(years_x, inb_water, bottom=dom_water, color=_WONG_PALETTE[5], alpha=0.85,
                  label="Inbound")

        for i, (d, v) in enumerate(zip(dom_water, inb_water)):
            tot = d + v
            if tot > 0 and v > 0:
                ax_c.text(i, tot + 0.01, f"Inb: {100*v/tot:.0f}%",
                           ha="center", va="bottom", fontsize=7)

        ax_c.set_xticks(years_x)
        ax_c.set_xticklabels(yl, fontsize=8)
        ax_c.set_ylabel("Total water (bn m³)")
        ax_c.set_title("Absolute Water by Tourist Segment")
        ax_c.legend(fontsize=8)
    else:
        ax_c.text(0.5, 0.5, "Data not available",
                  ha="center", va="center", transform=ax_c.transAxes,
                  fontsize=9, color="grey")
        ax_c.set_title("Absolute Water by Tourist Segment")
    _panel_label(ax_c, "(c)")

    fig.suptitle(
        "Figure 4 | Inbound vs Domestic Tourist Water Footprint — Intensity, Composition, and Volume",
        fontsize=9, fontweight="bold",
    )
    plt.tight_layout()
    _save(fig, "fig4_inbound_domestic_gap.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 5 — WATER ORIGIN HEATMAP
# ══════════════════════════════════════════════════════════════════════════════

def fig5_water_origin_heatmap(log=None):
    """
    Source-sector × year heatmap.
    Cells show % of total indirect TWF.
    Right-side axis shows absolute bn m³ for context.
    Percent-change arrows annotated between 2015 and 2022.
    """
    section("Figure 5 — Water origin heatmap", log=log)

    all_origins = {}
    for yr in STUDY_YEARS:
        df = _load_origin(yr, log)
        if not df.empty:
            all_origins[yr] = df

    if not all_origins:
        warn("No origin data available — Figure 5 skipped", log)
        return

    # Build unified matrix
    src_col = None
    val_col = None
    for yr, df in all_origins.items():
        src_cols = [c for c in df.columns if "source" in c.lower() or "group" in c.lower() or "sector" in c.lower()]
        val_cols = [c for c in df.columns if "m3" in c.lower() or "water" in c.lower()]
        if src_cols and val_cols:
            src_col, val_col = src_cols[0], val_cols[0]
            break

    if src_col is None:
        warn("Cannot determine source/value columns for origin data", log)
        return

    # Collect all source groups
    all_sources = sorted(set(
        s for df in all_origins.values() for s in df[src_col].astype(str).tolist()
    ))
    matrix    = np.zeros((len(all_sources), len(STUDY_YEARS)))
    matrix_m3 = np.zeros_like(matrix)

    for j, yr in enumerate(STUDY_YEARS):
        if yr not in all_origins:
            continue
        df    = all_origins[yr]
        total = df[val_col].sum()
        for i, src in enumerate(all_sources):
            row = df[df[src_col].astype(str) == src]
            if not row.empty:
                v = float(row[val_col].iloc[0])
                matrix[i, j]    = 100 * v / total if total else 0
                matrix_m3[i, j] = v / 1e9

    fig, ax = plt.subplots(figsize=(8, max(5, len(all_sources) * 0.65)))
    cmap    = LinearSegmentedColormap.from_list("blues", ["#EBF5FB", "#0072B2"])
    im      = ax.imshow(matrix, cmap=cmap, aspect="auto", vmin=0, vmax=matrix.max())

    ax.set_xticks(range(len(STUDY_YEARS)))
    ax.set_xticklabels([_YEAR_LABELS[yr] for yr in STUDY_YEARS])
    ax.set_yticks(range(len(all_sources)))
    ax.set_yticklabels(all_sources, fontsize=8)

    # Annotate cells with % value
    for i in range(len(all_sources)):
        for j in range(len(STUDY_YEARS)):
            v = matrix[i, j]
            text_color = "white" if v > matrix.max() * 0.55 else "black"
            ax.text(j, i, f"{v:.1f}%", ha="center", va="center",
                     fontsize=7.5, color=text_color, fontweight="bold")

    # % change annotation (first → last year)
    if matrix.shape[1] >= 2:
        for i in range(len(all_sources)):
            v0, v1 = matrix[i, 0], matrix[i, -1]
            chg    = v1 - v0
            arrow  = "↑" if chg > 0.5 else ("↓" if chg < -0.5 else "→")
            ax.text(len(STUDY_YEARS) - 0.35, i, f"{arrow}{abs(chg):.1f}pp",
                     va="center", fontsize=7, color="black")

    plt.colorbar(im, ax=ax, label="% of total indirect TWF", shrink=0.7)
    ax.set_title("Figure 5 | Upstream Water Origin by Source Sector and Year\n"
                 "(% of total indirect TWF; arrows show pp change 2015→2022)",
                 fontsize=9, fontweight="bold")
    _save(fig, "fig5_water_origin_heatmap.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 6 — TORNADO CHART (MC VARIANCE SOURCES)
# ══════════════════════════════════════════════════════════════════════════════

def fig6_tornado_uncertainty(log=None):
    """
    2-panel uncertainty figure:
      (a) Tornado chart — Spearman rank correlation between inputs and TWF output
      (b) Sensitivity range comparison — LOW/BASE/HIGH total TWF by year
    """
    section("Figure 6 — Tornado uncertainty chart", log=log)

    mc_var   = _load_mc_variance(log)
    indirect = _load_indirect_totals(log)
    direct   = _load_direct_totals(log)

    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(12, 5))

    # ── (a) Tornado chart ─────────────────────────────────────────────────────
    if not mc_var.empty:
        param_col = [c for c in mc_var.columns if "param" in c.lower() or "input" in c.lower()]
        corr_col  = [c for c in mc_var.columns if "corr" in c.lower() and STUDY_YEARS[-1] in str(c)]
        if not corr_col:
            corr_col  = [c for c in mc_var.columns if "corr" in c.lower()]

        if param_col and corr_col:
            pc, cc = param_col[0], corr_col[0]
            df_t   = mc_var[[pc, cc]].dropna().sort_values(cc, ascending=True)

            colors = [_WONG_PALETTE[5] if v < 0 else _WONG_PALETTE[4]
                      for v in df_t[cc]]
            ax_a.barh(df_t[pc], df_t[cc], color=colors, alpha=0.85)
            ax_a.axvline(0, color="black", linewidth=0.8)
            ax_a.set_xlabel(f"Spearman rank correlation with TWF\n({_YEAR_LABELS[STUDY_YEARS[-1]]})")
            ax_a.set_title("Variance Decomposition — Uncertainty Drivers")
            ax_a.set_xlim(-1, 1)
            legend_patches = [
                mpatches.Patch(color=_WONG_PALETTE[4], label="Positive correlation"),
                mpatches.Patch(color=_WONG_PALETTE[5], label="Negative correlation"),
            ]
            ax_a.legend(handles=legend_patches, fontsize=8, loc="lower right")
        else:
            ax_a.text(0.5, 0.5, "Variance data columns\nnot recognised",
                      ha="center", va="center", transform=ax_a.transAxes, fontsize=9, color="grey")
            warn("MC variance column names not recognised", log)
    else:
        ax_a.text(0.5, 0.5, "MC variance data\nnot available",
                  ha="center", va="center", transform=ax_a.transAxes,
                  fontsize=9, color="grey")
        warn("MC variance data missing — panel (a) placeholder", log)
    _panel_label(ax_a, "(a)")

    # ── (b) Sensitivity range comparison ─────────────────────────────────────
    # Collect sensitivity totals from sensitivity CSVs
    years_have = [yr for yr in STUDY_YEARS if yr in indirect]
    xp         = np.arange(len(years_have))

    sens_low  = []
    sens_base = []
    sens_high = []
    for yr in years_have:
        df_s = _load(DIRS["indirect"] / f"indirect_twf_{yr}_sensitivity.csv", log)
        if df_s.empty or "Scenario" not in df_s.columns or "Total_Water_m3" not in df_s.columns:
            sens_low.append(None); sens_base.append(None); sens_high.append(None)
            continue
        dir_base = direct.get(yr, 0)
        sens_low.append( (float(df_s[df_s["Scenario"] == "LOW"]["Total_Water_m3"].sum())  + dir_base) / 1e9)
        sens_base.append((float(df_s[df_s["Scenario"] == "BASE"]["Total_Water_m3"].sum()) + dir_base) / 1e9)
        sens_high.append((float(df_s[df_s["Scenario"] == "HIGH"]["Total_Water_m3"].sum()) + dir_base) / 1e9)

    if any(v is not None for v in sens_base):
        ax_b.bar(xp, [b or 0 for b in sens_base], color=_WONG_PALETTE[4], alpha=0.85, label="BASE")
        for i, (lo, ba, hi) in enumerate(zip(sens_low, sens_base, sens_high)):
            if lo and hi and ba:
                ax_b.plot([i, i], [lo, hi], color="black", linewidth=2.5, zorder=6)
                ax_b.plot(i, lo, "v", color=_WONG_PALETTE[5], markersize=8, zorder=7)
                ax_b.plot(i, hi, "^", color=_WONG_PALETTE[2], markersize=8, zorder=7)
        ax_b.set_xticks(xp)
        ax_b.set_xticklabels([_YEAR_LABELS[yr] for yr in years_have], fontsize=8)
        ax_b.set_ylabel("Total TWF (billion m³)")
        ax_b.set_title("Sensitivity Range — Total TWF\n(LOW / BASE / HIGH scenarios)")
        legend_patches = [
            mpatches.Patch(color=_WONG_PALETTE[4],                       label="BASE"),
            Line2D([0], [0], marker="v", color=_WONG_PALETTE[5], linewidth=0, markersize=8, label="LOW"),
            Line2D([0], [0], marker="^", color=_WONG_PALETTE[2], linewidth=0, markersize=8, label="HIGH"),
        ]
        ax_b.legend(handles=legend_patches, fontsize=8)
    else:
        ax_b.text(0.5, 0.5, "Sensitivity data\nnot available",
                  ha="center", va="center", transform=ax_b.transAxes,
                  fontsize=9, color="grey")
        ax_b.set_title("Sensitivity Range — Total TWF")
        warn("Sensitivity data missing — panel (b) placeholder", log)
    _panel_label(ax_b, "(b)")

    fig.suptitle(
        "Figure 6 | Monte Carlo Uncertainty Analysis — Variance Sources and Sensitivity Range",
        fontsize=9, fontweight="bold",
    )
    plt.tight_layout()
    _save(fig, "fig6_tornado_uncertainty.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def run(**kwargs):
    log_dir = DIRS["logs"] / "visualise"
    with Logger("visualise_results", log_dir) as log:
        t = Timer()
        log.section("GENERATE PUBLICATION FIGURES (6 multi-panel charts)")
        log.info(f"Output directory: {_VIS_DIR}")
        _VIS_DIR.mkdir(parents=True, exist_ok=True)

        figures = [
            ("Figure 1 — Dashboard overview (4-panel)",        fig1_dashboard_overview),
            ("Figure 2 — Supply-chain alluvial",               fig2_supply_chain_alluvial),
            ("Figure 3 — Decoupling analysis (3-panel)",       fig3_decoupling_analysis),
            ("Figure 4 — Inbound vs domestic gap (3-panel)",   fig4_inbound_domestic_gap),
            ("Figure 5 — Water origin heatmap",                fig5_water_origin_heatmap),
            ("Figure 6 — Tornado uncertainty chart (2-panel)", fig6_tornado_uncertainty),
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
        missing = [lbl for lbl, _ in figures if lbl not in success]
        for m in missing:
            log.warn(f"FAILED: {m}")


if __name__ == "__main__":
    run()
