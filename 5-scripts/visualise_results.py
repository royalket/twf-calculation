"""
visualise_results.py — All chart generation for India Tourism Water Footprint
==============================================================================
Reads output CSVs from all pipeline steps and produces publication-quality charts.

Charts produced
---------------
  1.  waterfall_sda_{y0}_{y1}.png      SDA W/L/Y effect waterfall per period
  2.  violin_monte_carlo.png            MC distribution per year (violin)
  3.  stacked_bar_water_origin.png      Source-sector shares across years
  4.  horizontal_bar_top10_{year}.png   Top-10 categories dual-encoded
  5.  slope_per_tourist.png             L/tourist/day domestic vs inbound
  6.  sankey_water_origin_{year}.png    Source → destination Sankey per year
  7.  sc_paths_ranked_{year}.png        Top supply-chain paths horizontal bar
  8.  mc_variance_pie.png               Variance decomposition pie per year
  9.  total_twf_trend.png               Total TWF trend with MC CI bands
  10. sector_type_stacked.png           Demand-destination sector shares

All charts saved to outputs/visualisation/
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")   # non-interactive backend for pipeline use
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import FuncFormatter

warnings.filterwarnings("ignore", category=UserWarning)

sys.path.insert(0, str(Path(__file__).parent))
from config import BASE_DIR, DIRS, STUDY_YEARS
from utils import Logger, Timer, ok, warn, section, subsection

# ── Output directory ──────────────────────────────────────────────────────────
_VIS_DIR = DIRS.get("visualisation", BASE_DIR / "3-final-results" / "visualisation")

# ── Colour palette (consistent across all charts) ────────────────────────────
PALETTE = {
    "Agriculture":   "#2E8B57",   # forest green
    "Food Mfg":      "#F4A460",   # sandy brown
    "Manufacturing": "#4682B4",   # steel blue
    "Mining":        "#8B6914",   # dark gold
    "Services":      "#9370DB",   # medium purple
    "Textiles":      "#CD5C5C",   # indian red
    "Utilities":     "#20B2AA",   # light sea green
    "Electricity":   "#FFD700",   # gold
    "Petroleum":     "#696969",   # dim grey
    "W_effect":      "#E74C3C",   # red   (technology / efficiency)
    "L_effect":      "#3498DB",   # blue  (structure)
    "Y_effect":      "#2ECC71",   # green (demand)
    "2015":          "#1a6496",
    "2019":          "#e8a838",
    "2022":          "#c0392b",
    "Domestic":      "#2980B9",
    "Inbound":       "#E67E22",
}

YEAR_COLORS = [PALETTE["2015"], PALETTE["2019"], PALETTE["2022"]]

def _m(val): return FuncFormatter(lambda x, _: f"{x/1e9:.2f}")
def _safe_csv(path): 
    try:
        p = Path(path)
        return pd.read_csv(p) if p.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _save(fig, name: str, log: Logger = None, dpi: int = 180):
    out = _VIS_DIR / name
    fig.savefig(out, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    ok(f"Chart saved: {name}", log)
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 1. SDA WATERFALL CHART
# ══════════════════════════════════════════════════════════════════════════════

def chart_sda_waterfall(log: Logger = None):
    """Waterfall chart for each SDA period showing W / L / Y effects."""
    sda_dir = DIRS.get("sda", BASE_DIR / "3-final-results" / "sda")
    periods = []
    for y0, y1 in zip(STUDY_YEARS[:-1], STUDY_YEARS[1:]):
        df = _safe_csv(sda_dir / f"sda_decomposition_{y0}_{y1}.csv")
        if not df.empty:
            periods.append((y0, y1, df.iloc[0]))

    if not periods:
        warn("SDA waterfall: no decomposition CSVs found", log)
        return

    for y0, y1, r in periods:
        fig, ax = plt.subplots(figsize=(9, 6))

        effects = {
            "W effect\n(Technology)": float(r["W_effect_m3"]) / 1e9,
            "L effect\n(Structure)":  float(r["L_effect_m3"]) / 1e9,
            "Y effect\n(Demand)":     float(r["Y_effect_m3"]) / 1e9,
        }
        total_chg = float(r["dTWF_m3"]) / 1e9
        twf0 = float(r["TWF0_m3"]) / 1e9
        twf1 = float(r["TWF1_m3"]) / 1e9

        labels  = [f"TWF {y0}"] + list(effects) + [f"TWF {y1}"]
        vals    = [twf0] + list(effects.values()) + [twf1]
        bottoms = [0, twf0, twf0 + list(effects.values())[0],
                   twf0 + sum(list(effects.values())[:2]), 0]
        colors  = ["#95A5A6",
                   PALETTE["W_effect"] if list(effects.values())[0] < 0 else "#E74C3C",
                   PALETTE["L_effect"] if list(effects.values())[1] < 0 else "#3498DB",
                   PALETTE["Y_effect"] if list(effects.values())[2] < 0 else "#2ECC71",
                   "#95A5A6"]

        bars = ax.bar(labels, vals, bottom=bottoms, color=colors,
                      edgecolor="white", linewidth=0.8, width=0.6)

        # Value labels
        for bar, val, bot in zip(bars, vals, bottoms):
            y_pos = bot + val / 2
            sign = "+" if val > 0 else ""
            ax.text(bar.get_x() + bar.get_width() / 2, y_pos,
                    f"{sign}{val:.3f}", ha="center", va="center",
                    fontsize=9, fontweight="bold", color="white")

        ax.axhline(twf0, color="grey", linestyle="--", alpha=0.4, linewidth=0.8)
        ax.set_ylabel("Indirect TWF (billion m³)", fontsize=11)
        ax.set_title(f"SDA Waterfall — {y0} → {y1}\n"
                     f"What drove the change in tourism water footprint?",
                     fontsize=12, fontweight="bold")
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="x", labelsize=9)

        legend_patches = [
            mpatches.Patch(color=PALETTE["W_effect"], label="W effect (water technology change)"),
            mpatches.Patch(color=PALETTE["L_effect"], label="L effect (supply-chain restructuring)"),
            mpatches.Patch(color=PALETTE["Y_effect"], label="Y effect (tourism demand growth)"),
        ]
        ax.legend(handles=legend_patches, loc="upper right", fontsize=8, framealpha=0.9)
        fig.tight_layout()
        _save(fig, f"waterfall_sda_{y0}_{y1}.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# 2. MONTE CARLO VIOLIN CHART
# ══════════════════════════════════════════════════════════════════════════════

def chart_mc_violin(log: Logger = None):
    """Violin plot of MC total TWF distribution per year."""
    mc_dir = DIRS.get("monte_carlo", BASE_DIR / "3-final-results" / "monte-carlo")
    all_data = {}
    base_vals = {}

    for yr in STUDY_YEARS:
        df = _safe_csv(mc_dir / f"mc_results_{yr}.csv")
        if not df.empty and "Total_m3" in df.columns:
            all_data[yr] = df["Total_m3"].values / 1e9
        summ = _safe_csv(mc_dir / "mc_summary_all_years.csv")
        if not summ.empty:
            r = summ[summ["Year"].astype(str) == yr]
            if not r.empty:
                base_vals[yr] = float(r["Base_bn_m3"].iloc[0])

    if not all_data:
        warn("MC violin: no mc_results CSVs found", log)
        return

    fig, ax = plt.subplots(figsize=(10, 7))
    positions = list(range(len(all_data)))
    data_list = [all_data[yr] for yr in all_data]
    colors    = [PALETTE.get(yr, "#95A5A6") for yr in all_data]

    parts = ax.violinplot(data_list, positions=positions, showmedians=True,
                          showextrema=True, widths=0.7)

    for i, (pc, col) in enumerate(zip(parts["bodies"], colors)):
        pc.set_facecolor(col)
        pc.set_alpha(0.7)
        pc.set_edgecolor("white")

    parts["cmedians"].set_color("#2C3E50")
    parts["cmedians"].set_linewidth(2)

    # BASE estimate dot
    for i, yr in enumerate(all_data):
        if yr in base_vals:
            ax.scatter(i, base_vals[yr], color="black", zorder=5, s=60,
                       label="BASE estimate" if i == 0 else "")

    ax.set_xticks(positions)
    ax.set_xticklabels(list(all_data.keys()), fontsize=11)
    ax.set_ylabel("Total TWF (billion m³)", fontsize=11)
    ax.set_title("Monte Carlo Uncertainty Distribution\nTotal Tourism Water Footprint",
                 fontsize=12, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=9)

    legend_patches = [mpatches.Patch(color=PALETTE.get(yr, "#95A5A6"), label=yr)
                      for yr in all_data]
    legend_patches.append(mpatches.Patch(color="black", label="BASE estimate"))
    ax.legend(handles=legend_patches, fontsize=9)
    fig.tight_layout()
    _save(fig, "violin_monte_carlo.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# 3. STACKED BAR — WATER ORIGIN BY SOURCE SECTOR
# ══════════════════════════════════════════════════════════════════════════════

def chart_water_origin_stacked(log: Logger = None):
    """Cross-year stacked bar of water origin by source sector (from structural CSVs)."""
    SOURCE_GROUPS = ["Agriculture", "Mining", "Manufacturing",
                     "Petroleum", "Electricity", "Services"]
    origin: dict = {}
    totals: dict = {}

    for yr in STUDY_YEARS:
        df = _safe_csv(DIRS["indirect"] / f"indirect_twf_{yr}_structural.csv")
        if df.empty:
            continue
        tot = float(df["Total_Water_m3"].sum()) if "Total_Water_m3" in df.columns else 0
        totals[yr] = tot
        for grp in SOURCE_GROUPS:
            col = f"From_{grp}_m3"
            if col in df.columns:
                origin.setdefault(grp, {})[yr] = float(df[col].sum())

    if not origin:
        warn("Water origin stacked bar: no structural CSVs found", log)
        return

    years_avail = [yr for yr in STUDY_YEARS if yr in totals]
    x = np.arange(len(years_avail))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7))

    # Left: absolute m³
    bottoms = np.zeros(len(years_avail))
    for grp in SOURCE_GROUPS:
        vals = [origin.get(grp, {}).get(yr, 0) / 1e9 for yr in years_avail]
        ax1.bar(x, vals, bottom=bottoms, label=grp,
                color=PALETTE.get(grp, "#95A5A6"), edgecolor="white", linewidth=0.5)
        bottoms += np.array(vals)

    ax1.set_xticks(x); ax1.set_xticklabels(years_avail, fontsize=11)
    ax1.set_ylabel("Indirect TWF (billion m³)", fontsize=11)
    ax1.set_title("Water Origin — Absolute", fontsize=11, fontweight="bold")
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.legend(fontsize=8, loc="upper right")

    # Right: percentage
    bottoms = np.zeros(len(years_avail))
    for grp in SOURCE_GROUPS:
        pct_vals = [100 * origin.get(grp, {}).get(yr, 0) / totals.get(yr, 1)
                    for yr in years_avail]
        ax2.bar(x, pct_vals, bottom=bottoms, label=grp,
                color=PALETTE.get(grp, "#95A5A6"), edgecolor="white", linewidth=0.5)
        # Labels for large segments
        for xi, pv, bot in zip(x, pct_vals, bottoms):
            if pv > 5:
                ax2.text(xi, bot + pv / 2, f"{pv:.0f}%",
                         ha="center", va="center", fontsize=8, color="white",
                         fontweight="bold")
        bottoms += np.array(pct_vals)

    ax2.set_xticks(x); ax2.set_xticklabels(years_avail, fontsize=11)
    ax2.set_ylabel("Share (%)", fontsize=11)
    ax2.set_title("Water Origin — Share", fontsize=11, fontweight="bold")
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.set_ylim(0, 105)

    fig.suptitle("Where Tourism Water is Physically Extracted\n(Source-Sector View via Structural Decomposition)",
                 fontsize=13, fontweight="bold", y=1.01)
    fig.tight_layout()
    _save(fig, "stacked_bar_water_origin.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# 4. HORIZONTAL BAR — TOP-10 CATEGORIES (dual encoded)
# ══════════════════════════════════════════════════════════════════════════════

def chart_top10_categories(log: Logger = None):
    """Top-10 categories per year — horizontal bar with intensity dot."""
    TYPE_COLORS = {
        "Food Mfg":      PALETTE["Food Mfg"],
        "Services":      PALETTE["Services"],
        "Textiles":      PALETTE["Textiles"],
        "Manufacturing": PALETTE["Manufacturing"],
        "Agriculture":   PALETTE["Agriculture"],
        "Utilities":     PALETTE["Utilities"],
    }

    for yr in STUDY_YEARS:
        df = _safe_csv(DIRS["indirect"] / f"indirect_twf_{yr}_by_category.csv")
        if df.empty or "Total_Water_m3" not in df.columns:
            continue

        top = df.nlargest(10, "Total_Water_m3").copy()
        tot = float(df["Total_Water_m3"].sum())
        top["Share_pct"] = 100 * top["Total_Water_m3"] / tot

        fig, ax = plt.subplots(figsize=(12, 7))
        y_pos = np.arange(len(top))
        bar_colors = [TYPE_COLORS.get(str(r["Category_Type"]), "#95A5A6")
                      for _, r in top.iterrows()]

        bars = ax.barh(y_pos, top["Total_Water_m3"] / 1e9,
                       color=bar_colors, edgecolor="white", linewidth=0.5, height=0.7)

        # Intensity dots on secondary axis
        if "Demand_crore" in top.columns:
            top["Intensity"] = top["Total_Water_m3"] / top["Demand_crore"].replace(0, np.nan)
            ax2 = ax.twiny()
            ax2.scatter(top["Intensity"], y_pos, color="#2C3E50",
                        zorder=5, s=50, marker="D", label="m³/crore intensity")
            ax2.set_xlabel("Water Intensity (m³/₹ crore)", fontsize=9, color="#2C3E50")
            ax2.tick_params(axis="x", colors="#2C3E50", labelsize=8)

        # Share labels
        for bar, (_, r) in zip(bars, top.iterrows()):
            ax.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height() / 2,
                    f"{r['Share_pct']:.1f}%", va="center", fontsize=8, color="#2C3E50")

        ax.set_yticks(y_pos)
        ax.set_yticklabels(top["Category_Name"].str[:38].tolist(), fontsize=9)
        ax.set_xlabel("Total Water (billion m³)", fontsize=11)
        ax.set_title(f"Top-10 Tourism Categories by Water Footprint — {yr}",
                     fontsize=12, fontweight="bold")
        ax.spines[["top", "right"]].set_visible(False)
        ax.invert_yaxis()

        type_patches = [mpatches.Patch(color=c, label=t) for t, c in TYPE_COLORS.items()
                        if t in top["Category_Type"].values]
        ax.legend(handles=type_patches, fontsize=8, loc="lower right")
        fig.tight_layout()
        _save(fig, f"horizontal_bar_top10_{yr}.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# 5. SLOPE GRAPH — PER-TOURIST WATER INTENSITY
# ══════════════════════════════════════════════════════════════════════════════

def chart_slope_per_tourist(log: Logger = None):
    """Slope/connected-dot graph for L/tourist/day domestic vs inbound."""
    df = _safe_csv(DIRS["comparison"] / "twf_per_tourist_intensity.csv")
    if df.empty or "L_per_dom_tourist_day" not in df.columns:
        warn("Slope chart: per-tourist intensity CSV missing", log)
        return

    years = [str(y) for y in df["Year"].astype(str).tolist()]
    dom   = df["L_per_dom_tourist_day"].tolist()
    inb   = df["L_per_inb_tourist_day"].tolist()

    fig, ax = plt.subplots(figsize=(9, 6))
    x = np.arange(len(years))

    ax.plot(x, dom, "o-", color=PALETTE["Domestic"], linewidth=2.5,
            markersize=10, label="Domestic tourists", zorder=3)
    ax.plot(x, inb, "s-", color=PALETTE["Inbound"],  linewidth=2.5,
            markersize=10, label="Inbound tourists",  zorder=3)

    # Value labels
    for xi, dv, iv in zip(x, dom, inb):
        ax.annotate(f"{dv:,.0f}L", (xi, dv), textcoords="offset points",
                    xytext=(0, 12), ha="center", fontsize=9, color=PALETTE["Domestic"],
                    fontweight="bold")
        ax.annotate(f"{iv:,.0f}L", (xi, iv), textcoords="offset points",
                    xytext=(0, -18), ha="center", fontsize=9, color=PALETTE["Inbound"],
                    fontweight="bold")

    ax.set_xticks(x); ax.set_xticklabels(years, fontsize=11)
    ax.set_ylabel("Litres per tourist per day", fontsize=11)
    ax.set_title("Per-Tourist Water Intensity\nDomestic vs Inbound tourists",
                 fontsize=12, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=10)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    _save(fig, "slope_per_tourist.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# 6. SUPPLY-CHAIN PATHS RANKED BAR
# ══════════════════════════════════════════════════════════════════════════════

def chart_sc_paths(log: Logger = None):
    """Horizontal bar for top-20 supply-chain paths per year."""
    sc_dir = DIRS.get("supply_chain", BASE_DIR / "3-final-results" / "supply-chain")

    for yr in STUDY_YEARS:
        df = _safe_csv(sc_dir / f"sc_paths_{yr}.csv")
        if df.empty or "Water_m3" not in df.columns:
            continue

        top = df.head(20).copy()
        fig, ax = plt.subplots(figsize=(13, 8))
        y_pos = np.arange(len(top))

        bar_colors = [PALETTE.get(str(r["Source_Group"]), "#95A5A6")
                      for _, r in top.iterrows()]
        ax.barh(y_pos, top["Water_m3"] / 1e6, color=bar_colors,
                edgecolor="white", linewidth=0.4, height=0.7)

        ax.set_yticks(y_pos)
        ax.set_yticklabels(top["Path"].str[:65].tolist(), fontsize=7.5)
        ax.set_xlabel("Water (million m³)", fontsize=11)
        ax.set_title(f"Top-20 Dominant Supply-Chain Pathways — {yr}\n"
                     f"Source → Destination water flow",
                     fontsize=12, fontweight="bold")
        ax.spines[["top", "right"]].set_visible(False)
        ax.invert_yaxis()

        grp_patches = [mpatches.Patch(color=PALETTE.get(g, "#95A5A6"), label=g)
                       for g in ["Agriculture", "Manufacturing", "Services",
                                 "Mining", "Petroleum", "Electricity"]
                       if g in top["Source_Group"].values]
        ax.legend(handles=grp_patches, fontsize=8, loc="lower right")
        fig.tight_layout()
        _save(fig, f"sc_paths_ranked_{yr}.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# 7. MONTE CARLO VARIANCE PIE
# ══════════════════════════════════════════════════════════════════════════════

def chart_mc_variance(log: Logger = None):
    """Pie chart of variance decomposition by parameter per year."""
    mc_dir = DIRS.get("monte_carlo", BASE_DIR / "3-final-results" / "monte-carlo")
    df = _safe_csv(mc_dir / "mc_variance_decomposition.csv")
    if df.empty or "SpearmanRank_corr" not in df.columns:
        warn("MC variance pie: mc_variance_decomposition.csv missing", log)
        return

    years_avail = [yr for yr in STUDY_YEARS if yr in df["Year"].astype(str).values]
    if not years_avail:
        return

    n = len(years_avail)
    fig, axes = plt.subplots(1, n, figsize=(6 * n, 6))
    if n == 1:
        axes = [axes]

    PARAM_LABELS = {
        "agr_water_mult":   "Agr. water coefficients",
        "hotel_coeff_mult": "Hotel coefficients",
        "rest_coeff_mult":  "Restaurant coefficients",
        "dom_tourist_mult": "Domestic tourist volume",
        "inb_tourist_mult": "Inbound tourist volume",
        "rail_coeff_mult":  "Rail coefficients",
        "air_coeff_mult":   "Air coefficients",
    }
    PIE_COLORS = ["#2E8B57","#F4A460","#4682B4","#9370DB",
                  "#CD5C5C","#20B2AA","#FFD700"]

    for ax, yr in zip(axes, years_avail):
        sub = df[df["Year"].astype(str) == yr].copy()
        sub["abs_corr"] = sub["SpearmanRank_corr"].abs()
        sub = sub.sort_values("abs_corr", ascending=False)
        labels = [PARAM_LABELS.get(str(p), str(p)) for p in sub["Parameter"]]
        vals   = sub["abs_corr"].values

        wedges, texts, autotexts = ax.pie(
            vals, labels=None, colors=PIE_COLORS[:len(vals)],
            autopct="%1.1f%%", startangle=140,
            pctdistance=0.8, textprops={"fontsize": 8},
        )
        ax.legend(wedges, labels, loc="lower center",
                  bbox_to_anchor=(0.5, -0.25), fontsize=7.5, ncol=2)
        ax.set_title(f"{yr}", fontsize=11, fontweight="bold")

    fig.suptitle("Monte Carlo Variance Decomposition\n"
                 "Which inputs drive output uncertainty most?",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    _save(fig, "mc_variance_pie.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# 8. TOTAL TWF TREND WITH MC CONFIDENCE BANDS
# ══════════════════════════════════════════════════════════════════════════════

def chart_total_twf_trend(log: Logger = None):
    """Line chart of total TWF with MC 5th-95th percentile band."""
    tot_df = _safe_csv(DIRS["comparison"] / "twf_total_all_years.csv")
    mc_dir = DIRS.get("monte_carlo", BASE_DIR / "3-final-results" / "monte-carlo")
    mc_sum = _safe_csv(mc_dir / "mc_summary_all_years.csv")

    if tot_df.empty:
        warn("Total TWF trend: twf_total_all_years.csv missing", log)
        return

    years = [str(y) for y in tot_df["Year"].astype(str).tolist()]
    x     = np.arange(len(years))
    tot   = tot_df["Total_bn_m3"].tolist()
    ind   = tot_df["Indirect_bn_m3"].tolist()
    dir_  = tot_df["Direct_bn_m3"].tolist()

    fig, ax = plt.subplots(figsize=(10, 6))

    # MC confidence band
    if not mc_sum.empty and "P5_bn_m3" in mc_sum.columns:
        p5  = [float(mc_sum[mc_sum["Year"].astype(str) == yr]["P5_bn_m3"].iloc[0])
               if yr in mc_sum["Year"].astype(str).values else t
               for yr, t in zip(years, tot)]
        p95 = [float(mc_sum[mc_sum["Year"].astype(str) == yr]["P95_bn_m3"].iloc[0])
               if yr in mc_sum["Year"].astype(str).values else t
               for yr, t in zip(years, tot)]
        ax.fill_between(x, p5, p95, alpha=0.2, color="#2C3E50",
                        label="MC 5th–95th percentile")

    ax.plot(x, tot, "o-", color="#2C3E50", linewidth=2.5,
            markersize=10, label="Total TWF (BASE)", zorder=5)
    ax.plot(x, ind, "s--", color=PALETTE["2015"], linewidth=1.8,
            markersize=7, label="Indirect TWF")
    ax.plot(x, dir_, "^--", color=PALETTE["2022"], linewidth=1.8,
            markersize=7, label="Direct TWF")

    for xi, tv in zip(x, tot):
        ax.annotate(f"{tv:.3f}", (xi, tv),
                    textcoords="offset points", xytext=(0, 12),
                    ha="center", fontsize=9, fontweight="bold")

    ax.set_xticks(x); ax.set_xticklabels(years, fontsize=11)
    ax.set_ylabel("Water Footprint (billion m³)", fontsize=11)
    ax.set_title("Total Tourism Water Footprint — Trend with Uncertainty\n"
                 "India 2015–2022", fontsize=12, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    _save(fig, "total_twf_trend.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# 9. SECTOR TYPE STACKED — DEMAND DESTINATION VIEW
# ══════════════════════════════════════════════════════════════════════════════

def chart_sector_type_stacked(log: Logger = None):
    """Cross-year stacked bar of demand-destination sector types."""
    sector_data: dict = {}
    totals: dict = {}

    for yr in STUDY_YEARS:
        df = _safe_csv(DIRS["indirect"] / f"indirect_twf_{yr}_by_category.csv")
        if df.empty or "Category_Type" not in df.columns:
            continue
        tot = float(df["Total_Water_m3"].sum())
        totals[yr] = tot
        for ctype, grp in df.groupby("Category_Type"):
            w = float(grp["Total_Water_m3"].sum())
            sector_data.setdefault(ctype, {})[yr] = w

    if not sector_data:
        warn("Sector type stacked: no category CSVs found", log)
        return

    years_avail = [yr for yr in STUDY_YEARS if yr in totals]
    x = np.arange(len(years_avail))
    ctypes = sorted(sector_data)
    ctype_colors = {
        "Food Mfg":      PALETTE["Food Mfg"],
        "Services":      PALETTE["Services"],
        "Textiles":      PALETTE["Textiles"],
        "Manufacturing": PALETTE["Manufacturing"],
        "Agriculture":   PALETTE["Agriculture"],
        "Utilities":     PALETTE["Utilities"],
        "Mining":        PALETTE["Mining"],
    }

    fig, ax = plt.subplots(figsize=(10, 6))
    bottoms = np.zeros(len(years_avail))
    for ctype in ctypes:
        pcts = [100 * sector_data.get(ctype, {}).get(yr, 0) / totals.get(yr, 1)
                for yr in years_avail]
        col = ctype_colors.get(ctype, "#95A5A6")
        ax.bar(x, pcts, bottom=bottoms, label=ctype, color=col,
               edgecolor="white", linewidth=0.5)
        for xi, pv, bot in zip(x, pcts, bottoms):
            if pv > 4:
                ax.text(xi, bot + pv / 2, f"{pv:.0f}%",
                        ha="center", va="center", fontsize=8.5,
                        fontweight="bold", color="white")
        bottoms += np.array(pcts)

    ax.set_xticks(x); ax.set_xticklabels(years_avail, fontsize=11)
    ax.set_ylabel("Share of Indirect TWF (%)", fontsize=11)
    ax.set_ylim(0, 105)
    ax.set_title("Tourism Water Footprint by Demand Destination\n"
                 "(Where tourism spending lands — note Agriculture = 0 here;\n"
                 "agricultural water is embedded in Food Mfg via supply chains)",
                 fontsize=11, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=9, loc="upper right", bbox_to_anchor=(1.18, 1))
    fig.tight_layout()
    _save(fig, "sector_type_stacked.png", log)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN run()
# ══════════════════════════════════════════════════════════════════════════════

def run(**kwargs):
    """
    Generate all charts. Called by main.py as pipeline step 'visualise'.
    Failures in individual charts are caught and logged — they do not
    abort the rest of the chart generation.
    """
    with Logger("visualise_results", DIRS["logs"]) as log:
        t = Timer()
        log.section("VISUALISE RESULTS")
        _VIS_DIR.mkdir(parents=True, exist_ok=True)

        charts = [
            ("SDA waterfall",         chart_sda_waterfall),
            ("MC violin",             chart_mc_violin),
            ("Water origin stacked",  chart_water_origin_stacked),
            ("Top-10 categories",     chart_top10_categories),
            ("Slope per tourist",     chart_slope_per_tourist),
            ("Supply-chain paths",    chart_sc_paths),
            ("MC variance pie",       chart_mc_variance),
            ("Total TWF trend",       chart_total_twf_trend),
            ("Sector type stacked",   chart_sector_type_stacked),
        ]

        results = {}
        for name, fn in charts:
            subsection(name, log)
            try:
                fn(log)
                results[name] = "OK"
            except Exception as e:
                warn(f"{name} failed: {e}", log)
                results[name] = f"FAILED: {e}"

        log.section("Chart Summary")
        for name, status in results.items():
            if status == "OK":
                ok(f"{name:<35} ✓", log)
            else:
                warn(f"{name:<35} {status}", log)

        ok(f"Charts saved to: {_VIS_DIR}", log)
        ok(f"Done in {t.elapsed()}", log)


if __name__ == "__main__":
    run()
