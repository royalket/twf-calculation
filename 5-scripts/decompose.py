"""
decompose.py — Universal SDA + Monte Carlo for All Stressors
=============================================================
Structurally decomposes inter-period footprint changes and quantifies
uncertainty via Monte Carlo for any registered stressor.

Framework: TWF = W · L · Y  (diagonal intensity × Leontief × demand)
  W  = stressor intensity vector (diagonalised)
  L  = Leontief inverse (same IO table for all stressors)
  Y  = tourism demand vector (same TSA demand for all stressors)

SDA method: Six-polar Dietzenbacher-Los (1998) via utils.six_polar_sda().
  Averages all 3! = 6 orderings; residual ≈ 0 by construction.
  Output schema is identical for all stressors — compare.py reads the same
  CSV structure regardless of stressor.

MC method: Log-normal perturbation of the dominant uncertainty group.
  One correlated multiplier per draw, applied to all sectors in the group.
  Conservative upper bound — partial independence reduces CI by ~30-40%.

Adding a new stressor
---------------------
  1. Add entry to SDA_CFG (coeff file, column, output dir, unit).
  2. Add entry to MC_CFG  (perturb group, sigma, output dir).
  3. Add DIRS key to config.py.
  That's all. The run() function and all algorithms are unchanged.

Output files — ALL consistent across stressors:
  water:     sda/sda_summary_all_periods.csv          (legacy filename)
             monte-carlo/mc_summary_all_years.csv      (legacy filename)
  energy:    sda-energy/sda_energy_summary_all_periods.csv
             monte-carlo-energy/mc_energy_summary_all_years.csv
  depletion: sda-depletion/sda_depletion_summary_all_periods.csv
             monte-carlo-depletion/mc_depletion_summary_all_years.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import DIRS, STUDY_YEARS, YEARS
from utils import (
    section, subsection, ok, warn, save_csv,
    compare_across_years, Timer, Logger,
    six_polar_sda, classify_source_group,
)

# ── Type alias ────────────────────────────────────────────────────────────────
Stressor = str  # "water" | "energy" | "depletion" | "emissions"


# ══════════════════════════════════════════════════════════════════════════════
# SDA CONFIG — one entry per stressor
# ══════════════════════════════════════════════════════════════════════════════

SDA_CFG: dict[str, dict] = {
    "water": {
        # Coefficient file written by build_coefficients.py to DIRS["concordance"]
        # Column already unit-converted: m³/EUR-M → m³/₹ crore (conv_fn = 100/EUR_INR)
        "coeff_file_fn":  lambda io_tag: f"water_coefficients_140_{io_tag}.csv",
        "coeff_col_fn":   lambda wy:     f"Water_{wy}_Blue_m3_per_crore",
        "out_dir_key":    "sda",
        "unit_label":     "bn m³",
        "scale":          1e9,
        "primary_key":    "Indirect_TWF_billion_m3",
        # Legacy output filenames preserved for backward compat with compare.py
        "summary_file":   "sda_summary_all_periods.csv",
        "detail_prefix":  "sda",
    },
    "energy": {
        "coeff_file_fn":  lambda io_tag: f"energy_coefficients_140_{io_tag}.csv",
        "coeff_col_fn":   lambda wy:     f"Energy_{wy}_Final_MJ_per_crore",
        "out_dir_key":    "sda_energy",
        "unit_label":     "bn MJ",
        "scale":          1e9,
        "primary_key":    "Primary_Total_bn_MJ",
        "summary_file":   "sda_energy_summary_all_periods.csv",
        "detail_prefix":  "sda_energy",
    },
    "depletion": {
        "coeff_file_fn":  lambda io_tag: f"depletion_coefficients_140_{io_tag}.csv",
        "coeff_col_fn":   lambda wy:     f"Depletion_{wy}_Fossil_t_per_crore",
        "out_dir_key":    "sda_depletion",
        "unit_label":     "M tonnes",
        "scale":          1e6,
        "primary_key":    "Total_Depletion_t",
        "summary_file":   "sda_depletion_summary_all_periods.csv",
        "detail_prefix":  "sda_depletion",
    },
    "emissions": {          # future stressor — add when emissions indirect runs
        "coeff_file_fn":  lambda io_tag: f"emissions_coefficients_140_{io_tag}.csv",
        "coeff_col_fn":   lambda wy:     f"Emissions_{wy}_kgCO2e_per_crore",
        "out_dir_key":    "sda_emissions",
        "unit_label":     "Mt CO2e",
        "scale":          1e9,
        "primary_key":    "Total_kgCO2e",
        "summary_file":   "sda_emissions_summary_all_periods.csv",
        "detail_prefix":  "sda_emissions",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# MC CONFIG — one entry per stressor
# ══════════════════════════════════════════════════════════════════════════════

MC_CFG: dict[str, dict] = {
    "water": {
        # Agriculture coefficients carry ±30% uncertainty (WaterGAP/Rodell 2018)
        "perturb_group": "Agriculture",
        "sigma_lognorm": 0.30,
        "n_samples":     10_000,
        "seed":          42,
        "out_dir_key":   "monte_carlo",
        "unit_label":    "bn m³",
        "scale":         1e9,
        "rationale":     "WaterGAP paddy/wheat coefficients (Rodell et al. 2018 ±30%)",
        # Legacy filename preserved for compare.py backward compat
        "summary_file":  "mc_summary_all_years.csv",
    },
    "energy": {
        # Electricity satellite carries ±20% (IEA vs national data gap)
        "perturb_group": "Electricity",
        "sigma_lognorm": 0.20,
        "n_samples":     10_000,
        "seed":          42,
        "out_dir_key":   "monte_carlo_energy",
        "unit_label":    "bn MJ",
        "scale":         1e9,
        "rationale":     "EXIOBASE electricity energy intensity ±20% (IEA vs national data gap)",
        "summary_file":  "mc_energy_summary_all_years.csv",
    },
    "depletion": {
        # Material extraction coefficients ±25% (EXIOBASE material satellite)
        "perturb_group": "Mining",
        "sigma_lognorm": 0.25,
        "n_samples":     5_000,
        "seed":          42,
        "out_dir_key":   "monte_carlo_depletion",
        "unit_label":    "M tonnes",
        "scale":         1e6,
        "rationale":     "EXIOBASE material extraction coefficients ±25%",
        "summary_file":  "mc_depletion_summary_all_years.csv",
    },
    "emissions": {          # future
        "perturb_group": "Electricity",
        "sigma_lognorm": 0.15,
        "n_samples":     10_000,
        "seed":          42,
        "out_dir_key":   "monte_carlo_emissions",
        "unit_label":    "Mt CO2e",
        "scale":         1e9,
        "rationale":     "EXIOBASE GHG coefficients ±15%",
        "summary_file":  "mc_emissions_summary_all_years.csv",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# SHARED INPUT LOADERS
# These exactly mirror indirect.py's _load_inputs() so that decompose.py uses
# the same W, L, Y as the main footprint calculation.  Critically:
#   • W  is read from the CONCORDANCE dir (already unit-converted by
#     build_coefficients.py: m³/EUR-M → m³/₹ crore via 100/EUR_INR).
#     Column name matches _CFG[stressor]["coeff_col_fn"](water_year).
#   • L  is read from DIRS["io"]/{io_year}/io_L_{io_tag}.csv (unchanged).
#   • Y  is mapped from 163-sector EXIOBASE demand to 140 SUT sectors using
#     map_y_to_sut() — EXIOBASE_Sectors + SUT_Product_IDs columns, with
#     the FIX-1 assigned_exio guard so each EXIO code is used exactly once.
# ══════════════════════════════════════════════════════════════════════════════

def _map_y_to_sut(Y_163: np.ndarray, concordance_df: pd.DataFrame,
                   n_sut: int = 140) -> np.ndarray:
    """
    Map 163-sector EXIOBASE demand to 140-sector SUT via concordance.
    Mirrors indirect.py map_y_to_sut() exactly (FIX-1 included):
    each EXIO code is assigned to Y_140 exactly once even if it appears
    in multiple concordance rows.
    """
    Y_140         = np.zeros(n_sut)
    assigned_exio: dict = {}

    for _, row in concordance_df.iterrows():
        exio_str   = str(row.get("EXIOBASE_Sectors", ""))
        sut_str    = str(row.get("SUT_Product_IDs",  ""))
        exio_codes = [e.strip() for e in exio_str.split(",")
                      if e.strip() and e.strip().lower() != "nan"]
        sut_ids    = [int(s.strip()) for s in sut_str.split(",")
                      if s.strip() and s.strip().lower() != "nan"
                      and s.strip().isdigit()]

        demand = 0.0
        for code in exio_codes:
            if code in assigned_exio:          # FIX-1: each code counted once
                continue
            assigned_exio[code] = True
            if code == "IN":
                idx = 0
            elif code.startswith("IN."):
                try:
                    idx = int(code.split(".")[1])
                except (IndexError, ValueError):
                    continue
            else:
                continue
            if 0 <= idx < len(Y_163):
                demand += Y_163[idx]

        if not sut_ids or demand == 0:
            continue
        per_sut = demand / len(sut_ids)
        for sid in sut_ids:
            if 1 <= sid <= n_sut:
                Y_140[sid - 1] += per_sut

    return Y_140


def _load_L(year: str) -> np.ndarray | None:
    """Load 140×140 Leontief inverse — same path as indirect.py."""
    io_year = YEARS[year]["io_year"]
    io_tag  = YEARS[year]["io_tag"]
    path    = DIRS["io"] / io_year / f"io_L_{io_tag}.csv"
    if not path.exists():
        warn(f"Leontief inverse missing: {path} — run build_io step first")
        return None
    return pd.read_csv(path, index_col=0).values.astype(float)


def _load_Y(year: str) -> np.ndarray | None:
    """
    Load 163-sector demand vector then map to 140 SUT sectors.
    Mirrors indirect.py _load_inputs() exactly:
      - reads Y_tourism_{year}.csv from DIRS["demand"]
      - maps via concordance_{io_tag}.csv using EXIOBASE_Sectors + SUT_Product_IDs
    """
    demand_path = DIRS["demand"] / f"Y_tourism_{year}.csv"
    if not demand_path.exists():
        warn(f"Demand vector missing: {demand_path} — run demand step first")
        return None
    df = pd.read_csv(demand_path)
    if "Tourism_Demand_crore" not in df.columns:
        warn(f"Tourism_Demand_crore column missing in {demand_path}")
        return None
    Y_163 = df["Tourism_Demand_crore"].values.astype(float)

    io_tag    = YEARS[year]["io_tag"]
    conc_path = DIRS["concordance"] / f"concordance_{io_tag}.csv"
    if not conc_path.exists():
        warn(f"Concordance missing: {conc_path}")
        return None
    concordance = pd.read_csv(conc_path)
    return _map_y_to_sut(Y_163, concordance)


def _load_W(year: str, stressor: Stressor, cfg: dict) -> np.ndarray | None:
    """
    Load 140-element intensity vector W for given stressor and year.

    Reads from DIRS["concordance"] — the same directory and file that
    indirect.py uses.  The coefficient CSV is written by build_coefficients.py
    with unit conversion already applied (m³/EUR-M → m³/₹ crore for water;
    TJ/EUR-M → MJ/₹ crore for energy).  We must NOT re-read the raw EUR
    column or apply any further conversion here.

    Column name follows _CFG[stressor]["coeff_col_fn"](water_year), e.g.:
        water:     Water_{wy}_Blue_m3_per_crore
        energy:    Energy_{wy}_Final_MJ_per_crore
        depletion: Depletion_{wy}_Fossil_t_per_crore
    """
    io_tag     = YEARS[year]["io_tag"]
    water_year = YEARS[year]["water_year"]

    coeff_file = cfg["coeff_file_fn"](io_tag)
    coeff_path = DIRS["concordance"] / coeff_file
    if not coeff_path.exists():
        warn(f"Coefficient file missing: {coeff_path} — run build_coefficients step first")
        return None

    df  = pd.read_csv(coeff_path)
    col = cfg["coeff_col_fn"](water_year)

    if col not in df.columns:
        # Exact match failed — try suffix match on the already-converted column
        # (never fall back to the raw EUR column)
        converted_suffix = col.split("_", 2)[-1]   # e.g. "Blue_m3_per_crore"
        candidates = [c for c in df.columns
                      if converted_suffix.lower() in c.lower()
                      and "EUR" not in c and "eur" not in c]
        if candidates:
            col = candidates[0]
            warn(f"W column fallback [{stressor} {year}]: using '{col}'")
        else:
            warn(f"W column '{col}' not found in {coeff_path.name}. "
                 f"Available: {list(df.columns)[:8]}")
            return None

    return df[col].fillna(0).values.astype(float)[:140]


def _load_direct_m3_scalar(year: str, stressor: Stressor) -> float:
    """
    Load BASE-scenario direct (activity-based) footprint in raw units.
    Added so MC base = indirect + direct, matching compare.py's reported total.
    For water: reads direct_twf_{year}.csv → Total_m3 BASE.
    For energy: reads direct_ef_{year}.csv → Total_MJ BASE.
    Returns 0.0 for stressors with no direct component.
    """
    from utils import safe_csv
    direct_map = {
        "water":  ("direct",        "direct_twf_{y}.csv", "Total_m3"),
        "energy": ("direct_energy", "direct_ef_{y}.csv",  "Total_MJ"),
    }
    if stressor not in direct_map:
        return 0.0
    dir_key, tmpl, col = direct_map[stressor]
    d = DIRS.get(dir_key)
    if d is None:
        return 0.0
    df = safe_csv(d / tmpl.replace("{y}", year))
    if df.empty or "Scenario" not in df.columns or col not in df.columns:
        return 0.0
    r = df[df["Scenario"] == "BASE"]
    return float(r[col].iloc[0]) if not r.empty else 0.0


def _mc_param_distributions(year: str) -> dict:
    """
    Define independent probability distributions for all uncertain parameters.
    Returns {param_name: (dist_type, *params)} — one entry per parameter.
    Each parameter is sampled independently per draw so variance decomposition
    via Spearman ρ² gives meaningful attribution across all inputs.

    Sources:
      agr_water_mult:   WaterGAP ±30% (σ=0.30 log-normal) — Rodell et al. 2018
      hotel_coeff_mult: CHSB India field study σ=0.25 log-normal
      rest_coeff_mult:  Lee et al. 2021 ±20%
      dom_tourist_mult: MoT ±8%
      inb_tourist_mult: MoT IPS ±5%
      rail_coeff_mult:  Literature range ±20%
      air_coeff_mult:   Literature range ±20%
    """
    from config import ACTIVITY_DATA, DIRECT_WATER
    act = ACTIVITY_DATA.get(year, {})
    return {
        "agr_water_mult":   ("lognormal", 0.0, 0.30),
        "hotel_coeff_mult": ("lognormal", 0.0, 0.25),
        "rest_coeff_mult":  ("normal",    1.0, 0.15),
        "dom_tourist_mult": ("normal",    1.0, 0.08),
        "inb_tourist_mult": ("normal",    1.0, 0.05),
        "rail_coeff_mult":  ("normal",    1.0, 0.20),
        "air_coeff_mult":   ("normal",    1.0, 0.20),
    }


def _sample_one_draw(specs: dict, rng: np.random.Generator) -> dict:
    """Draw one independent sample for each parameter."""
    out = {}
    for name, spec in specs.items():
        dist = spec[0]
        if dist == "lognormal":
            out[name] = float(rng.lognormal(spec[1], spec[2]))
        elif dist == "normal":
            out[name] = float(np.clip(rng.normal(spec[1], spec[2]), 0.1, 3.0))
        else:
            out[name] = 1.0
    return out


def _direct_twf_sim_mc(year: str, hotel_mult: float, rest_mult: float,
                        dom_mult: float, inb_mult: float,
                        rail_mult: float, air_mult: float) -> float:
    """
    Compute direct TWF m³ for one MC draw.
    Mirrors the logic of the old run_monte_carlo._direct_twf_sim().
    """
    from config import ACTIVITY_DATA, DIRECT_WATER
    act = ACTIVITY_DATA.get(year, ACTIVITY_DATA[STUDY_YEARS[-1]])
    dw  = DIRECT_WATER
    yr_key = year

    hotel_base = dw["hotel"].get(yr_key, dw["hotel"][STUDY_YEARS[-1]]).get("base", 0)
    rest_base  = dw["restaurant"].get(yr_key, {}).get("base", 0)
    rail_base  = dw.get("rail", {}).get("base", 3.5)
    air_base   = dw.get("air",  {}).get("base", 18.0)

    dom_hotel_share = act.get("dom_hotel_share", 0.15)
    inb_hotel_share = act.get("inb_hotel_share", 1.00)
    # FIX-2a: keep volume perturbation (dom_mult/inb_mult) in nights only;
    # apply coefficient perturbation (hotel_mult) to the base rate only.
    # Previously hotel_mult was multiplied onto the already-perturbed nights total,
    # squaring the hotel coefficient uncertainty for domestic and cross-applying
    # it to inbound nights that should only carry inb_mult.
    dom_hotel_nights = act["domestic_tourists_M"] * 1e6 * act["avg_stay_days_dom"] * dom_hotel_share * dom_mult
    inb_hotel_nights = act["inbound_tourists_M"]  * 1e6 * act["avg_stay_days_inb"] * inb_hotel_share * inb_mult
    hotel_coeff = hotel_base * hotel_mult   # coefficient uncertainty applied once, to the rate
    hotel_m3 = (dom_hotel_nights + inb_hotel_nights) * hotel_coeff / 1_000

    dom_days = act["domestic_tourists_M"] * 1e6 * act["avg_stay_days_dom"] * dom_mult
    inb_days = act["inbound_tourists_M"]  * 1e6 * act["avg_stay_days_inb"] * inb_mult
    rest_m3  = (dom_days + inb_days) * act.get("meals_per_tourist_day", 2.5) * rest_base * rest_mult / 1_000

    dom_rail_modal = act.get("dom_rail_modal_share", 0.25)
    avg_rail_km    = act.get("avg_tourist_rail_km", 242)
    dom_rail_m3 = act["domestic_tourists_M"] * 1e6 * dom_mult * dom_rail_modal * avg_rail_km * rail_base * rail_mult / 1_000

    air_m3 = act.get("air_pax_M", 0) * 1e6 * act.get("tourist_air_share", 0.6) * air_base * air_mult / 1_000

    return hotel_m3 + rest_m3 + dom_rail_m3 + air_m3


# ══════════════════════════════════════════════════════════════════════════════
# UNIVERSAL SDA RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def run_sda_for_stressor(stressor: Stressor, log: Logger) -> pd.DataFrame:
    """
    Run six-polar SDA for all consecutive year pairs for any stressor.

    Uses six_polar_sda() from utils.py — pure linear algebra, stressor-agnostic.
    Output CSV schema is identical for all stressors so compare.py reads it
    universally via REPORT_CFG["sda_file"].

    Output columns:
        Period, TWF0_{unit}, TWF1_{unit}, dTWF_{unit},
        W_effect_{unit}, L_effect_{unit}, Y_effect_{unit},
        W_effect_pct, L_effect_pct, Y_effect_pct,
        Residual_pct, Near_cancellation, Instability_ratio,
        SDA_Method, Stressor, Unit
    """
    cfg   = SDA_CFG[stressor]
    pairs = [(STUDY_YEARS[i], STUDY_YEARS[i + 1]) for i in range(len(STUDY_YEARS) - 1)]
    scale = cfg["scale"]
    unit  = cfg["unit_label"]

    results = []
    for yr0, yr1 in pairs:
        section(f"SDA [{stressor}]  {yr0} → {yr1}", log=log)

        W0 = _load_W(yr0, stressor, cfg)
        W1 = _load_W(yr1, stressor, cfg)
        L0 = _load_L(yr0)
        L1 = _load_L(yr1)
        Y0 = _load_Y(yr0)
        Y1 = _load_Y(yr1)

        if any(x is None for x in [W0, W1, L0, L1, Y0, Y1]):
            warn(f"SDA [{stressor}] {yr0}→{yr1}: missing inputs — skipping", log)
            continue

        # Trim/pad to common size
        n = min(len(W0), len(W1), len(L0), len(Y0))
        W0, W1 = W0[:n], W1[:n]
        L0, L1 = L0[:n, :n], L1[:n, :n]
        Y0, Y1 = Y0[:n], Y1[:n]

        result = six_polar_sda(
            np.diag(W0), L0, Y0,
            np.diag(W1), L1, Y1,
        )

        # Rename generic m³ keys to stressor-appropriate unit labels in summary
        result["Period"]    = f"{yr0}→{yr1}"
        result["Stressor"]  = stressor
        result["Unit"]      = unit

        ok(f"SDA {yr0}→{yr1}: ΔTWF={result['dTWF_m3']/scale:+.4f} {unit}  "
           f"W={result['W_effect_m3']/scale:+.4f}  "
           f"L={result['L_effect_m3']/scale:+.4f}  "
           f"Y={result['Y_effect_m3']/scale:+.4f}  "
           f"Residual={result['Residual_pct']:.4f}%", log)

        if result["Near_cancellation"]:
            warn(f"Near-cancellation ({yr0}→{yr1}): "
                 f"max effect = {result['Instability_ratio']:.0f}× |ΔTWF|. "
                 "Absolute values reliable; % shares suppressed.", log)

        results.append(result)

    df = pd.DataFrame(results)

    out_dir = DIRS.get(cfg["out_dir_key"])
    if out_dir is None:
        warn(f"DIRS['{cfg['out_dir_key']}'] not found — add to config.py DIRS")
        return df
    out_dir.mkdir(parents=True, exist_ok=True)
    save_csv(df, out_dir / cfg["summary_file"], f"SDA {stressor} all periods", log=log)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# UNIVERSAL MONTE CARLO RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def run_mc_for_stressor(stressor: Stressor, log: Logger) -> pd.DataFrame:
    """
    Monte Carlo uncertainty quantification — independently samples all uncertain
    parameters per draw so Spearman ρ² variance decomposition gives meaningful
    attribution across agr_water_mult, hotel, restaurant, tourist volumes, transport.

    Also adds direct TWF to base and every sample (direct is perturbed via
    hotel/rest/tourist/transport multipliers; only agr indirect is EEIO-perturbed).

    Writes:
      {out_dir}/{summary_file}            — percentiles + CI + top param per year
      {out_dir}/mc_results_{year}.csv     — one row per simulation, all param cols
      {out_dir}/mc_variance_decomposition.csv — Spearman ρ² per param per year
    """
    cfg   = MC_CFG[stressor]
    sda_c = SDA_CFG[stressor]
    rng   = np.random.default_rng(cfg["seed"])
    n_s   = cfg["n_samples"]
    group = cfg["perturb_group"]
    scale = cfg["scale"]

    section(f"MONTE CARLO [{stressor.upper()}]  n={n_s:,}  σ_agr={cfg['sigma_lognorm']}", log=log)
    ok(f"Rationale: {cfg['rationale']}", log)

    all_summary_rows  = []
    all_var_rows      = []

    for year in STUDY_YEARS:
        subsection(f"Year {year}", log=log)
        W = _load_W(year, stressor, sda_c)
        L = _load_L(year)
        Y = _load_Y(year)

        if W is None or L is None or Y is None:
            warn(f"MC [{stressor}] {year}: missing inputs — skipping", log)
            continue

        n = min(len(W), len(L), len(Y))
        W, L, Y = W[:n], L[:n, :n], Y[:n]

        agr_mask = np.array([
            classify_source_group(i + 1).lower() == group.lower()
            for i in range(n)
        ])
        ok(f"  Perturb group '{group}': {agr_mask.sum()} sectors", log)

        # Base: indirect EEIO + direct activity-based
        indirect_base = float((np.diag(W) @ L @ Y).sum())
        direct_base   = _load_direct_m3_scalar(year, stressor)
        base_fp       = (indirect_base + direct_base) / scale
        ok(f"  Indirect base: {indirect_base/scale:.4f}  "
           f"Direct: {direct_base/scale:.4f}  Total: {base_fp:.4f} {cfg['unit_label']}", log)

        # ── Draw n_s independent samples ─────────────────────────────────────
        dist_specs = _mc_param_distributions(year)
        sim_rows   = []

        for i in range(n_s):
            draw = _sample_one_draw(dist_specs, rng)

            # Perturb agricultural water coefficients (indirect EEIO component)
            W_sim = W.copy()
            W_sim[agr_mask] *= draw["agr_water_mult"]
            ind_sim = float((np.diag(W_sim) @ L @ Y).sum())

            # Perturb direct component via hotel/rest/tourist/transport multipliers
            if stressor == "water":
                dir_sim = _direct_twf_sim_mc(
                    year,
                    hotel_mult = draw["hotel_coeff_mult"],
                    rest_mult  = draw["rest_coeff_mult"],
                    dom_mult   = draw["dom_tourist_mult"],
                    inb_mult   = draw["inb_tourist_mult"],
                    rail_mult  = draw["rail_coeff_mult"],
                    air_mult   = draw["air_coeff_mult"],
                )
            else:
                dir_sim = direct_base   # energy direct not parametrised yet

            total_sim = (ind_sim + dir_sim) / scale
            row = {"Indirect_m3": round(ind_sim), "Direct_m3": round(dir_sim),
                   "Total_m3":    round(ind_sim + dir_sim)}
            row.update({f"param_{k}": v for k, v in draw.items()})
            sim_rows.append(row)

        # FIX-3e: removed dead first assignment (algebraically trivial, ran 10k times per year)
        sim_arr = np.array([(r["Indirect_m3"] + r["Direct_m3"]) / scale
                            for r in sim_rows])

        p5, p25, p50, p75, p95 = np.percentile(sim_arr, [5, 25, 50, 75, 95])
        range_pct    = 100 * (p95 - p5)  / base_fp if base_fp > 0 else 0
        ci_lower_pct = 100 * (base_fp - p5)  / base_fp if base_fp > 0 else 0
        ci_upper_pct = 100 * (p95 - base_fp) / base_fp if base_fp > 0 else 0

        # ── Variance decomposition — Spearman ρ² per parameter ───────────────
        import pandas as _pd2
        sim_df     = _pd2.DataFrame(sim_rows)
        total_col  = (sim_df["Indirect_m3"] + sim_df["Direct_m3"]) / scale
        var_rows_yr = []
        top_param   = group
        top_rho_sq  = 0.0
        try:
            from scipy.stats import spearmanr
            for pname in dist_specs:
                pcol = f"param_{pname}"
                if pcol not in sim_df.columns:
                    continue
                rho, _ = spearmanr(sim_df[pcol].values, total_col.values)
                rho_sq = float(rho) ** 2
                var_rows_yr.append({
                    "Year":               year,
                    "Parameter":          pname,
                    "SpearmanRank_corr":  round(float(rho), 4),
                    "Variance_share_pct": round(rho_sq * 100, 2),
                    "Stressor":           stressor,
                })
                if rho_sq > top_rho_sq:
                    top_rho_sq = rho_sq
                    top_param  = pname
            all_var_rows.extend(var_rows_yr)
        except Exception as _e:
            warn(f"MC variance decomp {year}: {_e}", log)
        top_var_share = f"{top_rho_sq * 100:.1f}"

        ok(f"  P5–P95: [{p5:.4f}–{p95:.4f}]  Range: {range_pct:.1f}%  "
           f"Top: {top_param} ({top_var_share}%)", log)

        all_summary_rows.append({
            "Year":             year,
            "Base_bn_m3":       round(base_fp, 6),
            "P5_bn_m3":         round(p5,  6),
            "P25_bn_m3":        round(p25, 6),
            "P50_bn_m3":        round(p50, 6),
            "P75_bn_m3":        round(p75, 6),
            "P95_bn_m3":        round(p95, 6),
            "Range_pct":        round(range_pct,    2),
            "CI_lower_pct":     round(ci_lower_pct, 1),
            "CI_upper_pct":     round(ci_upper_pct, 1),
            "Top_param":        top_param,
            "Variance_share_pct": top_var_share,
            "Stressor":         stressor,
            "Unit":             cfg["unit_label"],
        })

        # Per-year simulation results (all param columns restored)
        out_dir = DIRS.get(cfg["out_dir_key"])
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            save_csv(
                pd.DataFrame(sim_rows),
                out_dir / f"mc_results_{year}.csv",
                f"MC results {year}", log=log,
            )

    summary_df = pd.DataFrame(all_summary_rows)
    out_dir    = DIRS.get(cfg["out_dir_key"])
    if out_dir is None:
        warn(f"DIRS['{cfg['out_dir_key']}'] not found — add to config.py DIRS")
        return summary_df
    out_dir.mkdir(parents=True, exist_ok=True)

    save_csv(summary_df, out_dir / cfg["summary_file"],
             f"MC {stressor} all years", log=log)

    if all_var_rows:
        var_df = pd.DataFrame(all_var_rows)
        save_csv(var_df, out_dir / "mc_variance_decomposition.csv",
                 f"MC variance decomposition {stressor}", log=log)

    return summary_df


# ══════════════════════════════════════════════════════════════════════════════
# SUPPLY-CHAIN PATHS  (water-only for now — can be universalised later)
# ══════════════════════════════════════════════════════════════════════════════

def run_supply_chain(stressor: Stressor, log: Logger):
    """
    Build supply-chain path analysis (top upstream paths by footprint pull).

    Output schema (rich, all stressors):
        Rank, Source_ID, Source_Name, Source_Group,
        Dest_ID, Dest_Name, Dest_Group,
        Water_m3, Share_pct, Path
    Note: 'Water_m3' column name is kept for all stressors for backward
    compatibility with compare.py which reads this column by name.

    Also writes per-year source-group summary CSVs and a Markdown narrative
    report for the water stressor.
    """
    if stressor != "water":
        log.info(f"Supply-chain path analysis not yet implemented for '{stressor}' — skipping.")
        return

    sc_dir = DIRS.get("supply_chain")
    if sc_dir is None:
        warn("supply_chain DIRS key missing — skipping supply-chain analysis", log)
        return
    sc_dir.mkdir(parents=True, exist_ok=True)

    section("SUPPLY-CHAIN PATH ANALYSIS [water]", log=log)

    all_year_paths: dict[str, pd.DataFrame] = {}

    for year in STUDY_YEARS:
        subsection(f"Year {year}", log=log)
        W = _load_W(year, stressor, SDA_CFG[stressor])
        L = _load_L(year)
        Y = _load_Y(year)

        if W is None or L is None or Y is None:
            warn(f"Supply-chain [{year}]: missing inputs — skipping", log)
            continue

        n = min(len(W), len(L), len(Y))
        W, L, Y = W[:n], L[:n, :n], Y[:n]

        # Leontief pull: source i → destination j = W[i] × L[i,j] × Y[j]
        WL = np.diag(W) @ L
        paths = []
        total_footprint = (WL * Y).sum()

        for j in range(n):
            if Y[j] <= 0:
                continue
            for i in range(n):
                pull = WL[i, j] * Y[j]
                if pull > 1e3:
                    paths.append({
                        "Source_ID":    i + 1,
                        "Source_Name":  f"Product {i+1}",   # resolved below
                        "Source_Group": classify_source_group(i + 1),
                        "Dest_ID":      j + 1,
                        "Dest_Name":    f"Product {j+1}",
                        "Dest_Group":   classify_source_group(j + 1),
                        "Water_m3":     round(pull, 2),
                    })

        if not paths:
            warn(f"No supply-chain paths found for {year}", log)
            continue

        path_df = pd.DataFrame(paths).sort_values("Water_m3", ascending=False).reset_index(drop=True)
        path_df.insert(0, "Rank", range(1, len(path_df) + 1))
        path_df["Share_pct"] = round(100 * path_df["Water_m3"] / total_footprint, 4)
        path_df["Path"] = (path_df["Source_Name"].astype(str) + " → " +
                           path_df["Dest_Name"].astype(str))

        top_df = path_df.head(500)
        save_csv(top_df, sc_dir / f"sc_paths_{year}.csv",
                 f"Supply-chain paths {year}", log=log)
        all_year_paths[year] = top_df

        ok(f"  Top path: {top_df.iloc[0]['Source_Group']} sector {int(top_df.iloc[0]['Source_ID'])} "
           f"→ sector {int(top_df.iloc[0]['Dest_ID'])} "
           f"= {top_df.iloc[0]['Water_m3']/1e9:.4f} bn m³ "
           f"({top_df.iloc[0]['Share_pct']:.2f}% of total)", log)

        # Source-group summary
        grp_df = (path_df.groupby("Source_Group")["Water_m3"]
                   .sum().reset_index()
                   .sort_values("Water_m3", ascending=False))
        grp_df["Share_pct"] = round(100 * grp_df["Water_m3"] / total_footprint, 2)
        save_csv(grp_df, sc_dir / f"sc_by_source_group_{year}.csv",
                 f"SC by source group {year}", log=log)

        # ── HEM (Hypothetical Extraction Method) ─────────────────────────────
        # FIX: HEM was missing from run_supply_chain(). compare.py reads
        # sc_hem_{year}.csv with columns: Rank, Product_Name, Source_Group,
        # Dependency_Index (%), Tourism_Water_m3.
        # Dependency_Index = sector i's tourism-driven output share of total
        # tourism-driven output across all sectors.
        # x_tourism[i] = sum_j L[i,j] * Y[j]  (row sum of L weighted by Y)
        x_tourism     = (L * Y[np.newaxis, :]).sum(axis=1)
        total_t_output = x_tourism.sum()
        hem_rows_list  = []
        for i in range(n):
            dep   = float(x_tourism[i] / total_t_output * 100) if total_t_output > 0 else 0
            tw_m3 = float(W[i] * x_tourism[i])
            hem_rows_list.append({
                "Product_ID":       i + 1,
                "Product_Name":     f"Product {i+1}",  # resolved by _load_product_names if available
                "Source_Group":     classify_source_group(i + 1),
                "Dependency_Index": round(dep, 4),
                "Tourism_Water_m3": round(tw_m3),
            })
        hem_df = (pd.DataFrame(hem_rows_list)
                  .sort_values("Dependency_Index", ascending=False)
                  .reset_index(drop=True))
        hem_df.insert(0, "Rank", range(1, len(hem_df) + 1))
        save_csv(hem_df, sc_dir / f"sc_hem_{year}.csv",
                 f"SC HEM {year}", log=log)
        ok(f"  HEM top: {hem_df.iloc[0]['Product_Name']} "
           f"dep={hem_df.iloc[0]['Dependency_Index']:.3f}%  "
           f"water={hem_df.iloc[0]['Tourism_Water_m3']/1e6:.2f}M m³", log)

    # ── Markdown narrative report (water only) ────────────────────────────────
    if all_year_paths:
        _write_sc_markdown(all_year_paths, sc_dir, log)


def _write_sc_markdown(all_year_paths: dict, sc_dir, log: Logger):
    """Write Markdown supply-chain narrative report."""
    first_yr = STUDY_YEARS[0]
    last_yr  = STUDY_YEARS[-1]
    lines = [
        "# Supply-Chain Water Path Analysis — India Tourism",
        "",
        "> Generated by `decompose.py` · Formula: `W[i] × L[i,j] × Y[j]`",
        "> Source i → Destination j = water pulled from sector i by tourism demand for sector j.",
        "",
        "---",
        "",
    ]

    for year, df in all_year_paths.items():
        total_m3 = df["Water_m3"].sum()
        lines += [
            f"## {year}",
            "",
            f"**Total represented** (top 500 paths): {total_m3/1e9:.4f} bn m³",
            "",
            "### Top-10 Supply-Chain Paths",
            "",
            "| Rank | Path | Source Group | Water (M m³) | Share % |",
            "|-----:|------|--------------|-------------:|--------:|",
        ]
        for _, r in df.head(10).iterrows():
            lines.append(
                f"| {int(r['Rank'])} | {r['Path'][:60]} "
                f"| {r['Source_Group']} "
                f"| {r['Water_m3']/1e6:,.2f} "
                f"| {r['Share_pct']:.3f}% |"
            )

        # Source-group summary
        grp = df.groupby("Source_Group")["Water_m3"].sum().sort_values(ascending=False)
        lines += [
            "",
            "### Water by Source Group",
            "",
            "| Source Group | Water (M m³) | Share % |",
            "|--------------|-------------:|--------:|",
        ]
        tot = grp.sum()
        for grp_name, w in grp.items():
            lines.append(f"| {grp_name} | {w/1e6:,.2f} | {100*w/tot:.1f}% |")

        lines += ["", "---", ""]

    # Cross-year source-group comparison
    lines += ["## Cross-Year Source-Group Summary", ""]
    all_groups = sorted(set(
        g for df in all_year_paths.values()
        for g in df["Source_Group"].unique()
    ))
    header = "| Source Group | " + " | ".join(f"{yr} (M m³) | {yr} %" for yr in all_year_paths) + " |"
    sep    = "|---|" + "---|---|" * len(all_year_paths)
    lines += [header, sep]
    for grp_name in all_groups:
        row = f"| {grp_name} |"
        for yr, df in all_year_paths.items():
            tot = df["Water_m3"].sum()
            w   = df[df["Source_Group"] == grp_name]["Water_m3"].sum()
            row += f" {w/1e6:,.2f} | {100*w/max(tot,1):.1f}% |"
        lines.append(row)

    lines += ["", f"*Study years: {', '.join(STUDY_YEARS)} · Top 500 paths per year.*", ""]

    out = sc_dir / "sc_analysis_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    if log:
        log.ok(f"Supply-chain markdown report: {out.name}")


# ══════════════════════════════════════════════════════════════════════════════
# UNIVERSAL RUN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def run(stressor: Stressor = "water", **kwargs):
    """
    Run SDA + Monte Carlo (+ supply-chain for water) for any stressor.
    Called by main.py step "sda".
    """
    if stressor not in SDA_CFG:
        raise ValueError(
            f"Stressor '{stressor}' not in SDA_CFG. "
            f"Available: {list(SDA_CFG)}. "
            "Add entry to SDA_CFG and MC_CFG to register new stressor."
        )

    log_name = f"decompose_{stressor}"
    with Logger(log_name, DIRS["logs"]) as log:
        t = Timer()
        log.section(f"SDA + MONTE CARLO [{stressor.upper()}]")
        log.info(f"SDA method:  six-polar Dietzenbacher-Los (1998)")
        log.info(f"MC  method:  log-normal perturbation of {MC_CFG[stressor]['perturb_group']}")
        log.info(f"MC  samples: {MC_CFG[stressor]['n_samples']:,}  σ={MC_CFG[stressor]['sigma_lognorm']}")

        sda_df = run_sda_for_stressor(stressor, log)
        mc_df  = run_mc_for_stressor(stressor, log)
        run_supply_chain(stressor, log)

        # Cross-period summary
        if not sda_df.empty and "dTWF_m3" in sda_df.columns:
            log.section(f"SDA Cross-Period Summary [{stressor}]")
            cfg   = SDA_CFG[stressor]
            scale = cfg["scale"]
            unit  = cfg["unit_label"]
            for _, r in sda_df.iterrows():
                period = r.get("Period", "?")
                dtwf   = float(r.get("dTWF_m3", 0)) / scale
                w_eff  = float(r.get("W_effect_m3", 0)) / scale
                l_eff  = float(r.get("L_effect_m3", 0)) / scale
                y_eff  = float(r.get("Y_effect_m3", 0)) / scale
                log.info(
                    f"  {period}: ΔTWF={dtwf:+.4f} {unit}  "
                    f"W={w_eff:+.4f}  L={l_eff:+.4f}  Y={y_eff:+.4f}"
                )

        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Universal SDA + Monte Carlo")
    p.add_argument("--stressor", default="water",
                   choices=list(SDA_CFG), help="Stressor to decompose")
    args = p.parse_args()
    run(stressor=args.stressor)