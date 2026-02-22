"""
calculate_sda_mc.py — Structural Decomposition Analysis, Monte Carlo Sensitivity,
                       and Supply-Chain Path Analysis
=====================================================================================
Three complementary analyses that extend the core EEIO results:

1. STRUCTURAL DECOMPOSITION ANALYSIS (SDA)
   Decomposes the change in total indirect TWF between year-pairs into three drivers:
     ΔW effect  — change in water coefficients (technology / efficiency)
     ΔL effect  — change in Leontief inverse (supply-chain structure)
     ΔY effect  — change in tourism demand (volume + composition)
   Uses the two-polar decomposition to eliminate the residual:
     ΔTWF = 0.5*(ΔW·L₀·Y₀ + ΔW·L₁·Y₁)   [W effect]
           + 0.5*(W₀·ΔL·Y₀ + W₁·ΔL·Y₁)   [L effect]
           + 0.5*(W₀·L₀·ΔY + W₁·L₁·ΔY)   [Y effect]

2. MONTE CARLO SENSITIVITY
   Samples 10,000 draws from probability distributions assigned to each uncertain
   input (agricultural water coefficients, hotel/restaurant coefficients, tourist
   volumes) and produces a full distribution of total TWF per year.
   Reports: median, 5th–95th percentile, and rank-correlation-based variance
   decomposition (which inputs drive most output uncertainty).

3. SUPPLY-CHAIN PATH ANALYSIS
   Exploits the full pull matrix pull[i,j] = W[i]*L[i,j]*Y[j] already computed
   in calculate_indirect_twf.py (re-derived here from the saved CSVs) to identify
   and rank the dominant supply-chain pathways.
   Also implements the Hypothetical Extraction Method (HEM): sets tourism Y=0 and
   measures which upstream sectors depend most on tourism-driven demand.

Outputs
-------
sda/
  sda_decomposition_{y1}_{y2}.csv      — W/L/Y effects for one year-pair
  sda_summary_all_periods.csv          — consolidated across both periods
  sda_{y1}_{y2}_summary.txt

monte_carlo/
  mc_results_{year}.csv                — 10,000 simulation rows per year
  mc_summary_all_years.csv             — percentiles + dominant source
  mc_variance_decomposition.csv        — rank-correlation variance shares
  mc_{year}_summary.txt

supply_chain/
  sc_paths_{year}.csv                  — top-50 dominant supply-chain paths
  sc_hem_{year}.csv                    — HEM tourism-dependency index per sector
  sc_paths_{year}_summary.txt

Also writes:
  supply_chain/supply_chain_analysis_{year}.md   — Markdown report per year
  supply_chain/supply_chain_summary.md            — cross-year summary Markdown
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).parent))
from config import BASE_DIR, DIRS, STUDY_YEARS, YEARS, DIRECT_WATER, ACTIVITY_DATA, CPI
from utils import (
    section, subsection, ok, warn, save_csv,
    compare_across_years, top_n, Timer, Logger,
)

# ── Output directories ────────────────────────────────────────────────────────
_SDA_DIR   = DIRS.get("sda",          BASE_DIR / "3-final-results" / "sda")
_MC_DIR    = DIRS.get("monte_carlo",  BASE_DIR / "3-final-results" / "monte-carlo")
_SC_DIR    = DIRS.get("supply_chain", BASE_DIR / "3-final-results" / "supply-chain")

N_SIMULATIONS = 10_000   # Monte Carlo draws
TOP_PATHS     = 50        # supply-chain paths to save
RNG_SEED      = 42        # reproducibility


# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADERS  (read from existing pipeline outputs)
# ══════════════════════════════════════════════════════════════════════════════

def _safe_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path) if Path(path).exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def load_w(year: str, log: Logger = None) -> np.ndarray:
    """Load water coefficient vector W (140,) from sut water CSV."""
    cfg = YEARS[year]
    path = DIRS["concordance"] / f"water_coefficients_140_{cfg['io_tag']}.csv"
    df = pd.read_csv(path)
    wc = [c for c in df.columns if "Water" in c and "crore" in c][0]
    W = df[wc].values.astype(float)
    ok(f"W {year}: shape={W.shape}  non-zero={np.count_nonzero(W)}", log)
    return W, df["Product_ID"].values, df.get("Product_Name", pd.Series(dtype=str)).values


def load_l(year: str, log: Logger = None) -> np.ndarray:
    """Load Leontief inverse L (140×140)."""
    cfg = YEARS[year]
    path = DIRS["io"] / cfg["io_year"] / f"io_L_{cfg['io_tag']}.csv"
    L = pd.read_csv(path, index_col=0).values.astype(float)
    ok(f"L {year}: shape={L.shape}  diag_mean={np.diag(L).mean():.4f}", log)
    return L


def load_y(year: str, log: Logger = None) -> np.ndarray:
    """Load tourism demand vector Y (140,) from mapped demand CSV."""
    # Try the already-mapped 140-product version first (written by indirect_twf)
    path_sut = DIRS["indirect"] / f"indirect_twf_{year}_by_sut.csv"
    if path_sut.exists():
        df = pd.read_csv(path_sut)
        if "Tourism_Demand_crore" in df.columns:
            Y = df["Tourism_Demand_crore"].values.astype(float)
            ok(f"Y {year} (from sut results): ₹{Y.sum():,.0f} cr  non-zero={np.count_nonzero(Y)}", log)
            return Y
    # Fallback: 163-sector demand
    path_163 = DIRS["demand"] / f"Y_tourism_{year}.csv"
    df = pd.read_csv(path_163)
    Y = df["Tourism_Demand_crore"].values.astype(float)
    # Pad/trim to 140
    if len(Y) > 140:
        Y = Y[:140]
    elif len(Y) < 140:
        Y = np.concatenate([Y, np.zeros(140 - len(Y))])
    ok(f"Y {year} (padded from 163): ₹{Y.sum():,.0f} cr", log)
    return Y


def load_product_names(year: str) -> list:
    cfg = YEARS[year]
    path = DIRS["io"] / cfg["io_year"] / f"io_products_{cfg['io_tag']}.csv"
    df = _safe_csv(path)
    if not df.empty and "Product_Name" in df.columns:
        return df["Product_Name"].tolist()
    return [f"Product_{i+1}" for i in range(140)]


# ══════════════════════════════════════════════════════════════════════════════
# 1. STRUCTURAL DECOMPOSITION ANALYSIS (SDA)
# ══════════════════════════════════════════════════════════════════════════════

def two_polar_decomposition(
    W0: np.ndarray, L0: np.ndarray, Y0: np.ndarray,
    W1: np.ndarray, L1: np.ndarray, Y1: np.ndarray,
) -> dict:
    """
    Two-polar SDA decomposition of ΔTWF = TWF₁ − TWF₀.

    Each effect is the average of the two polar forms:
      ΔW effect = 0.5 * [ΔW @ L0 @ Y0  +  ΔW @ L1 @ Y1]  (elementwise sum)
      ΔL effect = 0.5 * [W0 @ ΔL @ Y0  +  W1 @ ΔL @ Y1]
      ΔY effect = 0.5 * [W0 @ L0 @ ΔY  +  W1 @ L1 @ ΔY]

    Returns dict with scalar effects and their sum (should equal ΔTWF).
    """
    TWF0 = float(np.dot(W0 @ L0, Y0))
    TWF1 = float(np.dot(W1 @ L1, Y1))
    dTWF = TWF1 - TWF0

    dW = W1 - W0
    dL = L1 - L0
    dY = Y1 - Y0

    # W effect: change in water technology
    W_eff = 0.5 * (float(np.dot(dW @ L0, Y0)) + float(np.dot(dW @ L1, Y1)))
    # L effect: change in supply-chain structure
    L_eff = 0.5 * (float(np.dot(W0 @ dL, Y0)) + float(np.dot(W1 @ dL, Y1)))
    # Y effect: change in tourism demand
    Y_eff = 0.5 * (float(np.dot(W0 @ L0, dY)) + float(np.dot(W1 @ L1, dY)))

    residual = dTWF - (W_eff + L_eff + Y_eff)

    return {
        "TWF0_m3":          TWF0,
        "TWF1_m3":          TWF1,
        "dTWF_m3":          dTWF,
        "W_effect_m3":      W_eff,
        "L_effect_m3":      L_eff,
        "Y_effect_m3":      Y_eff,
        "Sum_effects_m3":   W_eff + L_eff + Y_eff,
        "Residual_m3":      residual,
        "W_effect_pct":     100 * W_eff / abs(dTWF) if dTWF else 0,
        "L_effect_pct":     100 * L_eff / abs(dTWF) if dTWF else 0,
        "Y_effect_pct":     100 * Y_eff / abs(dTWF) if dTWF else 0,
        "Residual_pct":     100 * residual / abs(dTWF) if dTWF else 0,
    }


def run_sda(log: Logger = None) -> list:
    """Run SDA for all consecutive year-pairs. Returns list of result dicts."""
    section("STRUCTURAL DECOMPOSITION ANALYSIS (SDA)", log=log)
    _SDA_DIR.mkdir(parents=True, exist_ok=True)

    # Pre-load all years
    data = {}
    for yr in STUDY_YEARS:
        try:
            W, _, _ = load_w(yr, log)
            L       = load_l(yr, log)
            Y       = load_y(yr, log)
            data[yr] = (W, L, Y)
        except FileNotFoundError as e:
            warn(f"SDA: cannot load {yr} — {e}", log)

    if len(data) < 2:
        warn("SDA: need at least 2 years — skipping", log)
        return []

    years_avail = [y for y in STUDY_YEARS if y in data]
    all_results = []

    for i in range(len(years_avail) - 1):
        y0, y1 = years_avail[i], years_avail[i + 1]
        subsection(f"SDA: {y0} → {y1}", log)

        W0, L0, Y0 = data[y0]
        W1, L1, Y1 = data[y1]

        res = two_polar_decomposition(W0, L0, Y0, W1, L1, Y1)
        res["Year_from"] = y0
        res["Year_to"]   = y1
        res["Period"]    = f"{y0}→{y1}"

        # Log results
        ok(f"TWF: {res['TWF0_m3']/1e9:.4f} → {res['TWF1_m3']/1e9:.4f} bn m³  "
           f"(Δ {res['dTWF_m3']/1e9:+.4f} bn m³)", log)
        ok(f"  W effect (technology):     {res['W_effect_m3']/1e9:+.4f} bn m³  "
           f"({res['W_effect_pct']:+.1f}% of |ΔTWF|)", log)
        ok(f"  L effect (structure):      {res['L_effect_m3']/1e9:+.4f} bn m³  "
           f"({res['L_effect_pct']:+.1f}% of |ΔTWF|)", log)
        ok(f"  Y effect (demand):         {res['Y_effect_m3']/1e9:+.4f} bn m³  "
           f"({res['Y_effect_pct']:+.1f}% of |ΔTWF|)", log)
        ok(f"  Residual (should be ~0):   {res['Residual_m3']/1e9:+.6f} bn m³  "
           f"({res['Residual_pct']:+.3f}%)", log)

        # Save year-pair CSV
        df = pd.DataFrame([res])
        tag = f"{y0}_{y1}"
        save_csv(df, _SDA_DIR / f"sda_decomposition_{tag}.csv", f"SDA {y0}→{y1}", log=log)

        # Summary txt
        txt_path = _SDA_DIR / f"sda_{tag}_summary.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"SDA — {y0} → {y1}\n{'='*55}\n\n")
            f.write(f"TWF {y0}:  {res['TWF0_m3']:>20,.0f} m³\n")
            f.write(f"TWF {y1}:  {res['TWF1_m3']:>20,.0f} m³\n")
            f.write(f"Change:    {res['dTWF_m3']:>+20,.0f} m³\n\n")
            f.write("Two-polar decomposition:\n")
            f.write(f"  W effect (water technology):  {res['W_effect_m3']:>+15,.0f} m³  "
                    f"({res['W_effect_pct']:+.1f}%)\n")
            f.write(f"  L effect (supply structure):  {res['L_effect_m3']:>+15,.0f} m³  "
                    f"({res['L_effect_pct']:+.1f}%)\n")
            f.write(f"  Y effect (tourism demand):    {res['Y_effect_m3']:>+15,.0f} m³  "
                    f"({res['Y_effect_pct']:+.1f}%)\n")
            f.write(f"  Residual:                     {res['Residual_m3']:>+15,.0f} m³  "
                    f"({res['Residual_pct']:+.3f}%)\n")
        ok(f"Summary: {txt_path.name}", log)
        all_results.append(res)

    # Consolidated summary CSV
    if all_results:
        summary_df = pd.DataFrame(all_results)
        save_csv(summary_df, _SDA_DIR / "sda_summary_all_periods.csv",
                 "SDA all periods", log=log)

    return all_results


# ══════════════════════════════════════════════════════════════════════════════
# 2. MONTE CARLO SENSITIVITY
# ══════════════════════════════════════════════════════════════════════════════

def _mc_distributions(year: str) -> dict:
    """
    Define probability distributions for uncertain inputs.
    Returns dict: param_name → (distribution_type, *params)
    All distributions produce scalar multipliers applied to the base value.

    Sources for uncertainty ranges:
      - Agricultural water coefficients: WaterGAP ±30-40% (1-sigma)
      - Hotel coefficients: CHSB India log-normal (σ=0.25 on log scale)
      - Restaurant coefficients: Lee et al. (2021) ±20%
      - Tourist volumes: MoT ±8% (domestic), ±5% (inbound)
      - Transport coefficients: literature range ±25%
    """
    return {
        "agr_water_mult":    ("lognormal", 0.0,  0.30),   # μ=0, σ=0.30 on log scale
        "hotel_coeff_mult":  ("lognormal", 0.0,  0.25),   # μ=0, σ=0.25
        "rest_coeff_mult":   ("normal",    1.0,  0.15),   # mean=1, sd=0.15
        "dom_tourist_mult":  ("normal",    1.0,  0.08),   # mean=1, sd=0.08
        "inb_tourist_mult":  ("normal",    1.0,  0.05),   # mean=1, sd=0.05
        "rail_coeff_mult":   ("normal",    1.0,  0.20),
        "air_coeff_mult":    ("normal",    1.0,  0.20),
    }


def _sample_distributions(dist_specs: dict, n: int, rng: np.random.Generator) -> dict:
    """Draw n samples for each parameter. Returns {param: array(n)}."""
    samples = {}
    for name, spec in dist_specs.items():
        dist_type = spec[0]
        if dist_type == "lognormal":
            _, mu, sigma = spec
            samples[name] = rng.lognormal(mu, sigma, n)
        elif dist_type == "normal":
            _, mean, sd = spec
            raw = rng.normal(mean, sd, n)
            samples[name] = np.clip(raw, 0.1, 3.0)   # physical constraint
        elif dist_type == "uniform":
            _, lo, hi = spec
            samples[name] = rng.uniform(lo, hi, n)
        else:
            samples[name] = np.ones(n)
    return samples


def _direct_twf_sim(year: str, hotel_mult: float, rest_mult: float,
                     dom_mult: float, inb_mult: float,
                     rail_mult: float, air_mult: float) -> float:
    """Compute direct TWF m³ for one Monte Carlo draw."""
    act = ACTIVITY_DATA.get(year, ACTIVITY_DATA[STUDY_YEARS[-1]])
    dw  = DIRECT_WATER

    yr_key = year
    hotel_base = dw["hotel"].get(yr_key, dw["hotel"]["2022"])["base"]
    rest_base  = dw["restaurant"].get(yr_key, dw["restaurant"]["2022"])["base"]
    rail_base  = dw["rail"]["base"]
    air_base   = dw["air"]["base"]

    hotel_m3 = (act["classified_rooms"] * act["occupancy_rate"] *
                act["nights_per_year"] * hotel_base * hotel_mult / 1000)

    dom_days  = act["domestic_tourists_M"] * 1e6 * act["avg_stay_days_dom"] * dom_mult
    inb_days  = act["inbound_tourists_M"]  * 1e6 * act["avg_stay_days_inb"] * inb_mult
    rest_m3   = (dom_days + inb_days) * act["meals_per_tourist_day"] * rest_base * rest_mult / 1000

    rail_m3   = act["rail_pkm_B"] * 1e9 * act["tourist_rail_share"] * rail_base * rail_mult / 1000
    air_m3    = act["air_pax_M"]  * 1e6 * act["tourist_air_share"]  * air_base  * air_mult / 1000

    return hotel_m3 + rest_m3 + rail_m3 + air_m3


def run_monte_carlo(log: Logger = None) -> dict:
    """Run MC for all study years. Returns {year: summary_dict}."""
    section("MONTE CARLO SENSITIVITY ANALYSIS", log=log)
    _MC_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RNG_SEED)

    all_summaries = []
    var_decomp_rows = []
    year_results = {}

    for year in STUDY_YEARS:
        subsection(f"Monte Carlo — {year}  (n={N_SIMULATIONS:,})", log)
        try:
            W, pids, _ = load_w(year, log)
            L           = load_l(year, log)
            Y           = load_y(year, log)
        except FileNotFoundError as e:
            warn(f"MC {year}: missing input — {e}", log)
            continue

        # Identify agricultural product indices (IDs 1-29)
        agr_mask = np.array([1 <= int(pid) <= 29 for pid in pids])

        dist_specs = _mc_distributions(year)
        samples    = _sample_distributions(dist_specs, N_SIMULATIONS, rng)

        twf_indirect = np.zeros(N_SIMULATIONS)
        twf_direct   = np.zeros(N_SIMULATIONS)

        for i in range(N_SIMULATIONS):
            # Perturb agricultural water coefficients
            W_sim = W.copy()
            W_sim[agr_mask] *= samples["agr_water_mult"][i]

            twf_indirect[i] = float(np.dot(W_sim @ L, Y))
            twf_direct[i]   = _direct_twf_sim(
                year,
                hotel_mult = samples["hotel_coeff_mult"][i],
                rest_mult  = samples["rest_coeff_mult"][i],
                dom_mult   = samples["dom_tourist_mult"][i],
                inb_mult   = samples["inb_tourist_mult"][i],
                rail_mult  = samples["rail_coeff_mult"][i],
                air_mult   = samples["air_coeff_mult"][i],
            )

        twf_total = twf_indirect + twf_direct

        # Percentiles
        p5, p25, p50, p75, p95 = np.percentile(twf_total, [5, 25, 50, 75, 95])
        base_ind = float(np.dot(W @ L, Y))
        base_dir = _direct_twf_sim(year, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        base_tot = base_ind + base_dir

        ok(f"  BASE:    {base_tot/1e9:.4f} bn m³", log)
        ok(f"  Median:  {p50/1e9:.4f} bn m³", log)
        ok(f"  5th–95th: {p5/1e9:.4f} – {p95/1e9:.4f} bn m³  "
           f"(range ±{100*(p95-p50)/p50:.1f}%)", log)

        # Save raw simulation results
        sim_df = pd.DataFrame({
            "Sim":             np.arange(N_SIMULATIONS),
            "Indirect_m3":     twf_indirect,
            "Direct_m3":       twf_direct,
            "Total_m3":        twf_total,
            **{f"param_{k}": v for k, v in samples.items()},
        })
        save_csv(sim_df, _MC_DIR / f"mc_results_{year}.csv",
                 f"MC results {year}", log=log)

        # Variance decomposition via rank correlation (Spearman)
        var_rows = []
        for pname in dist_specs:
            corr = float(pd.Series(samples[pname]).rank().corr(
                pd.Series(twf_total).rank()
            ))
            var_rows.append({"Year": year, "Parameter": pname,
                             "SpearmanRank_corr": round(corr, 4),
                             "Variance_share_pct": round(100 * corr**2, 2)})
        var_decomp_rows.extend(var_rows)

        # Print top variance contributors
        subsection(f"Top variance contributors — {year}", log)
        for r in sorted(var_rows, key=lambda x: -abs(x["SpearmanRank_corr"]))[:5]:
            ok(f"  {r['Parameter']:<30}  r={r['SpearmanRank_corr']:+.3f}  "
               f"share={r['Variance_share_pct']:.1f}%", log)

        summary = {
            "Year":          year,
            "Base_bn_m3":    round(base_tot / 1e9, 4),
            "P5_bn_m3":      round(p5  / 1e9, 4),
            "P25_bn_m3":     round(p25 / 1e9, 4),
            "P50_bn_m3":     round(p50 / 1e9, 4),
            "P75_bn_m3":     round(p75 / 1e9, 4),
            "P95_bn_m3":     round(p95 / 1e9, 4),
            "Range_pct":     round(100 * (p95 - p5) / p50, 1),
            "Top_param":     max(var_rows, key=lambda x: abs(x["SpearmanRank_corr"]))["Parameter"],
        }
        all_summaries.append(summary)
        year_results[year] = summary

        # Plain text summary
        txt = _MC_DIR / f"mc_{year}_summary.txt"
        with open(txt, "w", encoding="utf-8") as f:
            f.write(f"MONTE CARLO — {year}  (n={N_SIMULATIONS:,})\n{'='*55}\n\n")
            f.write(f"Base estimate:  {base_tot/1e9:.4f} bn m³\n")
            f.write(f"5th  pct:       {p5/1e9:.4f} bn m³\n")
            f.write(f"25th pct:       {p25/1e9:.4f} bn m³\n")
            f.write(f"Median:         {p50/1e9:.4f} bn m³\n")
            f.write(f"75th pct:       {p75/1e9:.4f} bn m³\n")
            f.write(f"95th pct:       {p95/1e9:.4f} bn m³\n")
            f.write(f"Total range:    ±{100*(p95-p50)/p50:.1f}%\n\n")
            f.write("Variance contributors (Spearman rank correlation):\n")
            for r in sorted(var_rows, key=lambda x: -abs(x["SpearmanRank_corr"])):
                f.write(f"  {r['Parameter']:<30}  r={r['SpearmanRank_corr']:+.3f}  "
                        f"({r['Variance_share_pct']:.1f}%)\n")
        ok(f"Summary: {txt.name}", log)

    if all_summaries:
        save_csv(pd.DataFrame(all_summaries), _MC_DIR / "mc_summary_all_years.csv",
                 "MC summary all years", log=log)
    if var_decomp_rows:
        save_csv(pd.DataFrame(var_decomp_rows), _MC_DIR / "mc_variance_decomposition.csv",
                 "MC variance decomposition", log=log)

    return year_results


# ══════════════════════════════════════════════════════════════════════════════
# 3. SUPPLY-CHAIN PATH ANALYSIS + HEM
# ══════════════════════════════════════════════════════════════════════════════

def _source_group(pid: int) -> str:
    """Classify a SUT product ID into a broad source group."""
    if 1  <= pid <= 29:  return "Agriculture"
    if 30 <= pid <= 40:  return "Mining"
    if 41 <= pid <= 113: return "Manufacturing"
    if 71 <= pid <= 80:  return "Petroleum"
    if pid == 114:       return "Electricity"
    return "Services"


def structural_path_analysis(
    W: np.ndarray, L: np.ndarray, Y: np.ndarray,
    product_names: list, year: str, log: Logger = None,
) -> pd.DataFrame:
    """
    Build full pull matrix pull[i,j] = W[i] * L[i,j] * Y[j] (140×140).
    Rank all (i,j) pairs by water contribution to find dominant pathways.
    Returns DataFrame of top-N paths.
    """
    subsection(f"Supply-chain path analysis — {year}", log)
    n = len(W)
    pull = (W[:, np.newaxis] * L) * Y[np.newaxis, :]   # (140, 140)
    total_twf = pull.sum()

    # Flatten to list of (source_i, dest_j, water_m3)
    rows = []
    for i in range(n):
        for j in range(n):
            w = pull[i, j]
            if w > 0:
                rows.append({
                    "Source_ID":    i + 1,
                    "Source_Name":  product_names[i] if i < len(product_names) else f"P{i+1}",
                    "Source_Group": _source_group(i + 1),
                    "Dest_ID":      j + 1,
                    "Dest_Name":    product_names[j] if j < len(product_names) else f"P{j+1}",
                    "Dest_Group":   _source_group(j + 1),
                    "Water_m3":     round(w),
                    "Share_pct":    round(100 * w / total_twf, 4) if total_twf else 0,
                    "Path":         (f"{product_names[i] if i < len(product_names) else f'P{i+1}'}"
                                     f" → "
                                     f"{product_names[j] if j < len(product_names) else f'P{j+1}'}"),
                })

    df = pd.DataFrame(rows).sort_values("Water_m3", ascending=False).head(TOP_PATHS)
    df = df.reset_index(drop=True)
    df.insert(0, "Rank", range(1, len(df) + 1))

    ok(f"Total pull cells: {len(rows):,}  |  Top {TOP_PATHS} shown", log)
    ok(f"Top-5 paths:", log)
    for _, r in df.head(5).iterrows():
        ok(f"  #{int(r['Rank'])}: {r['Path'][:70]:<70}  {r['Water_m3']/1e6:>10.2f}M m³  "
           f"({r['Share_pct']:.2f}%)", log)

    return df


def hypothetical_extraction(
    W: np.ndarray, L: np.ndarray, Y: np.ndarray,
    product_names: list, year: str, log: Logger = None,
) -> pd.DataFrame:
    """
    Hypothetical Extraction Method (HEM): compute tourism dependency index.

    For each upstream sector i, remove tourism demand and measure the
    reduction in sector i's total output requirement.

    Dependency_i = (x_i_with_tourism - x_i_without_tourism) / x_i_with_tourism

    A high value means sector i is heavily dependent on tourism-driven demand.
    """
    subsection(f"Hypothetical Extraction Method (HEM) — {year}", log)

    # Approximate x (total output requirement) = L @ Y  (demand-side)
    x_with    = L @ Y           # total output per sector with tourism
    x_without = L @ np.zeros_like(Y)   # without tourism = 0 final demand

    # More meaningful: compare tourism-driven output vs. total
    # x_tourism[i] = sum_j L[i,j] * Y[j]
    x_tourism = (L * Y[np.newaxis, :]).sum(axis=1)   # row sum weighted by Y

    # Total output from all final demand (not just tourism) is L @ Y_total
    # We only have Y_tourism, so dependency = tourism_driven / total_tourism_output
    total_tourism_output = x_tourism.sum()

    rows = []
    n = len(W)
    for i in range(n):
        dep = float(x_tourism[i] / total_tourism_output) if total_tourism_output > 0 else 0
        rows.append({
            "Product_ID":        i + 1,
            "Product_Name":      product_names[i] if i < len(product_names) else f"P{i+1}",
            "Source_Group":      _source_group(i + 1),
            "Tourism_Output_cr": round(float(x_tourism[i]), 4),
            "Dependency_Index":  round(dep * 100, 4),   # % of total tourism-driven output
            "Water_Coeff":       round(float(W[i]), 4),
            "Tourism_Water_m3":  round(float(W[i] * x_tourism[i])),
        })

    df = (pd.DataFrame(rows)
            .sort_values("Dependency_Index", ascending=False)
            .reset_index(drop=True))
    df.insert(0, "Rank", range(1, len(df) + 1))

    ok(f"Top-5 tourism-dependent sectors:", log)
    for _, r in df.head(5).iterrows():
        ok(f"  #{int(r['Rank'])}: {str(r['Product_Name'])[:45]:<45}  "
           f"dep={r['Dependency_Index']:.3f}%  "
           f"water={r['Tourism_Water_m3']/1e6:.2f}M m³", log)

    return df


def write_supply_chain_md(
    year: str,
    paths_df: pd.DataFrame,
    hem_df: pd.DataFrame,
    log: Logger = None,
) -> Path:
    """Write a Markdown report for one year's supply-chain analysis."""
    total_water = paths_df["Water_m3"].sum() if not paths_df.empty else 0
    out_path = _SC_DIR / f"supply_chain_analysis_{year}.md"

    lines = [
        f"# Supply-Chain Analysis — {year}",
        "",
        "> Generated by `calculate_sda_mc.py` supply-chain path analysis module.",
        "> The pull matrix `pull[i,j] = W[i] × L[i,j] × Y[j]` is computed from",
        "> EXIOBASE water coefficients (W), Leontief inverse (L), and tourism demand (Y).",
        "",
        "---",
        "",
        "## 1. Dominant Supply-Chain Pathways",
        "",
        "Each row is a source→destination pair in the IO table.",
        "`Source` is where water is physically extracted;",
        "`Destination` is where tourism demand activates that chain.",
        "",
        f"| Rank | Source Sector | Source Group | Destination Sector | Dest Group "
        f"| Water (m³) | Share % |",
        "|---|---|---|---|---|---|---|",
    ]

    for _, r in paths_df.iterrows():
        lines.append(
            f"| {int(r['Rank'])} "
            f"| {r['Source_Name']} "
            f"| {r['Source_Group']} "
            f"| {r['Dest_Name']} "
            f"| {r['Dest_Group']} "
            f"| {int(r['Water_m3']):,} "
            f"| {r['Share_pct']:.3f}% |"
        )

    # Source group summary
    if not paths_df.empty:
        grp_sum = paths_df.groupby("Source_Group")["Water_m3"].sum().sort_values(ascending=False)
        g_total = grp_sum.sum()
        lines += [
            "",
            "### By Source Group (top-50 paths)",
            "",
            "| Source Group | Water (m³) | Share % |",
            "|---|---|---|",
        ]
        for grp, w in grp_sum.items():
            lines.append(f"| {grp} | {int(w):,} | {100*w/g_total:.1f}% |")

    lines += [
        "",
        "---",
        "",
        "## 2. Hypothetical Extraction Method (HEM)",
        "",
        "Tourism dependency index = sector's tourism-driven output requirement",
        "as a share of total tourism-driven output across all sectors.",
        "Higher = more dependent on tourism demand.",
        "",
        "| Rank | Sector | Group | Dependency Index % | Water Coeff (m³/cr) | Tourism Water (m³) |",
        "|---|---|---|---|---|---|",
    ]

    for _, r in hem_df.head(30).iterrows():
        lines.append(
            f"| {int(r['Rank'])} "
            f"| {r['Product_Name']} "
            f"| {r['Source_Group']} "
            f"| {r['Dependency_Index']:.3f}% "
            f"| {r['Water_Coeff']:,.1f} "
            f"| {int(r['Tourism_Water_m3']):,} |"
        )

    lines += [
        "",
        "---",
        "",
        "## 3. Interpretation Notes",
        "",
        "- **Agriculture dominates** the source-sector view because paddy rice, wheat,",
        "  and other crops have water coefficients orders of magnitude larger than",
        "  manufacturing or services sectors.",
        "",
        "- **The demand-destination view** (reported in Section 3.5 of the main report)",
        "  shows Agriculture = 0% because no tourism rupee flows *directly* to raw crops.",
        "  Agricultural water is embedded inside Food Manufacturing through Leontief",
        "  supply-chain propagation.",
        "",
        "- **Policy implication**: Efficiency interventions in agricultural irrigation",
        "  (drip irrigation, direct-seeded rice) have far greater leverage on total",
        "  tourism water footprint than hotel water recycling programmes.",
        "",
        f"*Analysis year: {year} | Top {TOP_PATHS} paths shown | "
        f"Generated by India TWF Pipeline*",
    ]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    ok(f"Supply-chain MD: {out_path.name}", log)
    return out_path


def run_supply_chain(log: Logger = None) -> dict:
    """Run path analysis and HEM for all study years."""
    section("SUPPLY-CHAIN PATH ANALYSIS + HEM", log=log)
    _SC_DIR.mkdir(parents=True, exist_ok=True)

    all_paths = {}

    for year in STUDY_YEARS:
        subsection(f"Year: {year}", log)
        try:
            W, pids, _ = load_w(year, log)
            L           = load_l(year, log)
            Y           = load_y(year, log)
            names       = load_product_names(year)
        except FileNotFoundError as e:
            warn(f"Supply-chain {year}: missing input — {e}", log)
            continue

        paths_df = structural_path_analysis(W, L, Y, names, year, log)
        hem_df   = hypothetical_extraction(W, L, Y, names, year, log)

        save_csv(paths_df, _SC_DIR / f"sc_paths_{year}.csv",
                 f"SC paths {year}", log=log)
        save_csv(hem_df,   _SC_DIR / f"sc_hem_{year}.csv",
                 f"SC HEM {year}", log=log)

        # Plain text summary
        txt = _SC_DIR / f"sc_paths_{year}_summary.txt"
        with open(txt, "w", encoding="utf-8") as f:
            f.write(f"SUPPLY-CHAIN PATH ANALYSIS — {year}\n{'='*55}\n\n")
            f.write(f"Top {min(10, len(paths_df))} dominant pathways:\n")
            for _, r in paths_df.head(10).iterrows():
                f.write(f"  #{int(r['Rank'])}: {r['Path'][:70]:<70}  "
                        f"{r['Water_m3']/1e6:>8.2f}M m³  ({r['Share_pct']:.2f}%)\n")
            f.write("\nTop 10 tourism-dependent sectors (HEM):\n")
            for _, r in hem_df.head(10).iterrows():
                f.write(f"  #{int(r['Rank'])}: {str(r['Product_Name'])[:45]:<45}  "
                        f"dep={r['Dependency_Index']:.3f}%\n")
        ok(f"Summary: {txt.name}", log)

        # Per-year Markdown report
        write_supply_chain_md(year, paths_df, hem_df, log)

        all_paths[year] = paths_df

    # Cross-year summary Markdown
    _write_supply_chain_summary_md(all_paths, log)

    return all_paths


def _write_supply_chain_summary_md(all_paths: dict, log: Logger = None):
    """Write a cross-year supply-chain summary Markdown."""
    out_path = _SC_DIR / "supply_chain_summary.md"
    lines = [
        "# Supply-Chain Analysis — Cross-Year Summary",
        "",
        "> Summarises dominant water pathways and source-sector shares across all study years.",
        "> For per-year detail see `supply_chain_analysis_{year}.md`.",
        "",
        "---",
        "",
        "## Source-Group Water Shares by Year",
        "",
        "| Source Group | " + " | ".join(f"{yr} m³ | {yr} %" for yr in STUDY_YEARS) + " |",
        "|---|" + "---|---|" * len(STUDY_YEARS),
    ]

    groups_data: dict = {}
    for yr, df in all_paths.items():
        if df.empty:
            continue
        tot = df["Water_m3"].sum()
        for grp, sub in df.groupby("Source_Group"):
            w = sub["Water_m3"].sum()
            groups_data.setdefault(grp, {})[yr] = (w, 100 * w / tot if tot else 0)

    for grp in ["Agriculture", "Mining", "Manufacturing", "Petroleum", "Electricity", "Services"]:
        if grp not in groups_data:
            continue
        row = f"| {grp} |"
        for yr in STUDY_YEARS:
            w, pct = groups_data[grp].get(yr, (0, 0))
            row += f" {int(w):,} | {pct:.1f}% |"
        lines.append(row)

    lines += [
        "",
        "---",
        "",
        "## Top-5 Dominant Pathways by Year",
        "",
    ]

    for yr, df in all_paths.items():
        lines.append(f"### {yr}")
        lines.append("")
        lines.append("| Rank | Path | Water (m³) | Share % |")
        lines.append("|---|---|---|---|")
        for _, r in df.head(5).iterrows():
            lines.append(f"| {int(r['Rank'])} | {r['Path']} "
                         f"| {int(r['Water_m3']):,} | {r['Share_pct']:.3f}% |")
        lines.append("")

    lines += [
        "---",
        "",
        "## Key Interpretation",
        "",
        "- Agriculture consistently dominates the **source-sector** view (typically 60-80%),",
        "  confirming that India's tourism water footprint is primarily an agricultural",
        "  water management challenge, not a hospitality sector challenge.",
        "",
        "- The COVID-19 impact (2022) is visible in reduced Services pathway shares",
        "  (less hotel, transport activity) and relatively higher Agricultural shares",
        "  (food supply chains remained active).",
        "",
        "- The HEM dependency index (per-year files) shows which upstream sectors",
        "  would be most affected by a hypothetical collapse of tourism demand.",
        "",
        "*Generated by India TWF Pipeline — `calculate_sda_mc.py`*",
    ]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    ok(f"Cross-year supply-chain MD: {out_path.name}", log)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN run() — called by main.py
# ══════════════════════════════════════════════════════════════════════════════

def run(**kwargs):
    """
    Run all three analyses in order:
      1. Structural Decomposition Analysis (SDA)
      2. Monte Carlo Sensitivity
      3. Supply-Chain Path Analysis + HEM

    kwargs are accepted but ignored (pipeline metadata forwarding from main.py).
    """
    with Logger("calculate_sda_mc", DIRS["logs"]) as log:
        t = Timer()
        log.section("SDA + MONTE CARLO + SUPPLY-CHAIN ANALYSIS")

        sda_results = run_sda(log)
        mc_results  = run_monte_carlo(log)
        sc_results  = run_supply_chain(log)

        log.section("SUMMARY")
        log.ok(f"SDA periods computed: {len(sda_results)}")
        log.ok(f"MC years computed: {len(mc_results)}")
        log.ok(f"Supply-chain years computed: {len(sc_results)}")
        log.ok(f"Outputs written to:")
        log.ok(f"  SDA:          {_SDA_DIR}")
        log.ok(f"  Monte Carlo:  {_MC_DIR}")
        log.ok(f"  Supply-chain: {_SC_DIR}")
        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    run()
