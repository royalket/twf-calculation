"""
postprocess.py — Post-Indirect Stressor Processing
====================================================
Universal dispatcher for all post-indirect steps. Merged from:
    direct.py      (direct activity-based water TWF)
    monetise.py    (physical depletion → monetary ₹ crore)
    ndp_report.py  (NDP = GDP − CFC − depletion compute)

Architecture
------------
POST_CFG dict drives which sub-steps run for each stressor.
Adding a new stressor = add one entry to POST_CFG. No new files.

main.py step registry dispatches three step names to this file:
    "direct"     → run(stressor="water")   → _run_direct_water()
    "monetise"   → run(stressor="depletion", phase="monetise")
    "ndp_report" → run(stressor="depletion", phase="ndp")

Output files — ALL unchanged from original:
    direct-water/direct_twf_{year}.csv
    direct-water/direct_twf_all_years.csv
    direct-water/direct_twf_{year}_summary.txt
    monetary-depletion/monetary_depletion_{year}.csv
    monetary-depletion/monetary_depletion_all_years.csv
    monetary-depletion/monetary_depletion_summary.txt
    ndp/ndp_all_years.csv
    ndp/ndp_decomposition_{year}.csv
    ndp/ndp_summary.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    DIRS, STUDY_YEARS, ACTIVITY_DATA, DIRECT_WATER,
    UNIT_RENTS, NAS_MACRO, USD_INR,
)
from utils import (
    section, subsection, ok, warn, save_csv, compare_across_years,
    Timer, Logger, fmt_m3, table_str, fmt_sens_range,
)


# ══════════════════════════════════════════════════════════════════════════════
# POST_CFG — what each stressor needs after indirect.py
# Adding emissions: add entry here, nothing else.
# ══════════════════════════════════════════════════════════════════════════════

POST_CFG: dict[str, dict] = {
    "water": {
        "has_direct":   True,
        "has_monetise": False,
        "has_ndp":      False,
    },
    "energy": {
        # Energy direct is already inside indirect.py (Emission/Final ratio).
        # No additional post-processing needed.
        "has_direct":   False,
        "has_monetise": False,
        "has_ndp":      False,
    },
    "depletion": {
        "has_direct":   False,
        "has_monetise": True,
        "has_ndp":      True,
    },
    "emissions": {      # future stressor — add direct/carbon-price logic here
        "has_direct":   False,
        "has_monetise": False,
        "has_ndp":      False,
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — DIRECT WATER TWF  (was direct.py)
# ══════════════════════════════════════════════════════════════════════════════

def _calc_hotel(year: str, scenario: str) -> float:
    """
    m³/year from hotel-nights × L/room/night coefficient.

    WHY hotel shares?
    dom_hotel_share (0.15): Blended fraction of domestic tourist-nights in
    paid accommodation. Derived from NSS Report 580, Table 3.14 (MOSPI 2017),
    applying Census 2011 rural/urban weights (65%×9% + 35%×25.8% ≈ 15%).
    Multiplying ALL domestic tourist-nights by the hotel coefficient would
    inflate domestic hotel water by ~5–6×.
    inb_hotel_share (1.00): All inbound tourists use paid accommodation —
    the VFR discount does not apply to international arrivals.
    """
    act             = ACTIVITY_DATA[year]
    coeff           = DIRECT_WATER["hotel"].get(year, DIRECT_WATER["hotel"]["2022"])[scenario]
    dom_hotel_share = act.get("dom_hotel_share", 0.15)
    inb_hotel_share = act.get("inb_hotel_share", 1.00)
    dom_nights = act["domestic_tourists_M"] * 1e6 * act["avg_stay_days_dom"] * dom_hotel_share
    inb_nights = act["inbound_tourists_M"]  * 1e6 * act["avg_stay_days_inb"] * inb_hotel_share
    return (dom_nights + inb_nights) * coeff / 1_000


def _calc_restaurant(year: str, scenario: str) -> float:
    """m³ from tourist meals (tourist-days × meals/day × L/meal)."""
    act   = ACTIVITY_DATA[year]
    coeff = DIRECT_WATER["restaurant"][year][scenario]
    dom_days    = act["domestic_tourists_M"] * 1e6 * act["avg_stay_days_dom"]
    inb_days    = act["inbound_tourists_M"]  * 1e6 * act["avg_stay_days_inb"]
    total_meals = (dom_days + inb_days) * act["meals_per_tourist_day"]
    return total_meals * coeff / 1_000


def _calc_rail(year: str, scenario: str) -> float:
    """
    m³/year from tourist rail travel — demand-side formula.

    tourist_pkm = dom_tourists × dom_rail_modal_share × avg_tourist_rail_km
    water_m3    = tourist_pkm × L/pkm

    Replaces old supply-side formula (rail_pkm_B × tourist_rail_share) which
    used an unverifiable 115B pkm figure implying ~80km avg trip (commuter
    range, not tourism). See reference_data.md ACTIVITY_DATA meta for sources.
    """
    act    = ACTIVITY_DATA[year]
    coeff  = DIRECT_WATER["rail"][scenario]
    modal  = act.get("dom_rail_modal_share", 0.25)
    # FIX-2f: removed circular fallback that derived avg_km from rail_pkm_B
    # (total system pkm ≠ tourist pkm). Hard error forces correct data entry.
    avg_km = act.get("avg_tourist_rail_km")
    if avg_km is None:
        raise KeyError(
            f"avg_tourist_rail_km missing for year {year} in ACTIVITY_DATA. "
            "Add value from Ministry of Railways Annual Statistical Statement Table 2 "
            "(Average Lead, non-suburban). E.g. 2015=242, 2019=254, 2022=261 km."
        )
    tourist_pkm = act["domestic_tourists_M"] * 1e6 * modal * avg_km
    return tourist_pkm * coeff / 1_000


def _calc_air(year: str, scenario: str) -> float:
    """m³ from tourist air travel (passengers × L/passenger)."""
    act   = ACTIVITY_DATA[year]
    coeff = DIRECT_WATER["air"][scenario]
    return act["air_pax_M"] * 1e6 * act["tourist_air_share"] * coeff / 1_000


_SECTOR_CALCS: dict = {
    "hotel":      _calc_hotel,
    "restaurant": _calc_restaurant,
    "rail":       _calc_rail,
    "air":        _calc_air,
}


def calculate_sector_water(year: str, sector: str, scenario: str) -> float:
    """Universal direct water calculator for any sector × scenario."""
    fn = _SECTOR_CALCS.get(sector)
    if fn is None:
        raise ValueError(f"Unknown sector '{sector}'. Available: {list(_SECTOR_CALCS)}")
    return fn(year, scenario)


def _calculate_direct_year(year: str, log: Logger = None) -> pd.DataFrame:
    """
    Calculate direct TWF for all sectors and scenarios for one year.
    Returns DataFrame: Year, Scenario, Hotel_m3, Restaurant_m3, Rail_m3,
    Air_m3, Total_m3, Total_billion_m3, {Sector}_pct columns.
    """
    section(f"Direct TWF — FY {year}", log=log)
    act = ACTIVITY_DATA[year]

    subsection("Activity inputs", log=log)
    act_rows = [
        ["Domestic tourists",      f"{act['domestic_tourists_M']:.1f} M",              "MoT Annual Report"],
        ["Inbound tourists",       f"{act['inbound_tourists_M']:.2f} M",               "MoT/UNWTO"],
        ["Avg stay (domestic)",    f"{act['avg_stay_days_dom']:.1f} days",              "NSSO Tourism Survey"],
        ["Avg stay (inbound)",     f"{act['avg_stay_days_inb']:.1f} days",              "MoT"],
        ["Dom hotel share",        f"{act.get('dom_hotel_share',0.15)*100:.0f}%",       "NSS Report 580, Table 3.14; Census 2011"],
        ["Inb hotel share",        f"{act.get('inb_hotel_share',1.0)*100:.0f}%",        "MoT IPS / TSA 2015-16 Table 3"],
        ["Rail modal share (dom)", f"{act.get('dom_rail_modal_share',0.25)*100:.0f}%",  "NSS Report 580, Table 3.6"],
        ["Avg tourist rail km",    f"{act.get('avg_tourist_rail_km',242):.0f} km",      "MoR Annual Statistical Statement Table 2"],
        ["Air passengers",         f"{act['air_pax_M']:.1f} M",                        "DGCA"],
        ["Tourist air share",      f"{act['tourist_air_share']*100:.0f}%",              "DGCA/NSSO"],
    ]
    if log:
        log.table(["Parameter", "Value", "Source"], act_rows)
    else:
        print(table_str(["Parameter", "Value", "Source"], act_rows))

    rows = []
    for scenario in ["low", "base", "high"]:
        vals  = {s: calculate_sector_water(year, s, scenario) for s in _SECTOR_CALCS}
        total = sum(vals.values())
        row   = {
            "Year":             year,
            "Scenario":         scenario.upper(),
            "Hotel_m3":         round(vals["hotel"]),
            "Restaurant_m3":    round(vals["restaurant"]),
            "Rail_m3":          round(vals["rail"]),
            "Air_m3":           round(vals["air"]),
            "Total_m3":         round(total),
            "Total_billion_m3": round(total / 1e9, 4),
            "Hotel_pct":        round(100 * vals["hotel"]      / total, 1),
            "Rest_pct":         round(100 * vals["restaurant"] / total, 1),
            "Rail_pct":         round(100 * vals["rail"]       / total, 1),
            "Air_pct":          round(100 * vals["air"]        / total, 1),
        }
        rows.append(row)

        if scenario == "base":
            subsection("BASE scenario breakdown", log=log)
            dom_hotel_share = act.get("dom_hotel_share", 0.15)
            inb_hotel_share = act.get("inb_hotel_share", 1.00)
            dom_nights  = act["domestic_tourists_M"] * 1e6 * act["avg_stay_days_dom"] * dom_hotel_share
            inb_nights  = act["inbound_tourists_M"]  * 1e6 * act["avg_stay_days_inb"] * inb_hotel_share
            total_nights = dom_nights + inb_nights
            coeff_rows = [
                ["Hotels",      f"{vals['hotel']/1e6:.2f} M m³",      f"{row['Hotel_pct']:.1f}%",
                 f"{DIRECT_WATER['hotel'].get(year, DIRECT_WATER['hotel']['2022'])['base']} L/room/night  "
                 f"({total_nights/1e6:.1f}M hotel-nights: {dom_nights/1e6:.1f}M dom "
                 f"[×{dom_hotel_share:.0%}] + {inb_nights/1e6:.1f}M inb [×{inb_hotel_share:.0%}])"],
                ["Restaurants", f"{vals['restaurant']/1e6:.2f} M m³", f"{row['Rest_pct']:.1f}%",
                 f"{DIRECT_WATER['restaurant'][year]['base']} L/meal"],
                ["Rail",        f"{vals['rail']/1e6:.2f} M m³",       f"{row['Rail_pct']:.1f}%",
                 f"{DIRECT_WATER['rail']['base']} L/pkm  "
                 f"({act['domestic_tourists_M']:.0f}M tourists × "
                 f"{act.get('dom_rail_modal_share',0.25)*100:.0f}% modal × "
                 f"{act.get('avg_tourist_rail_km',242):.0f}km avg = "
                 f"{act['domestic_tourists_M']*act.get('dom_rail_modal_share',0.25)*act.get('avg_tourist_rail_km',242)/1e9:.1f}B pkm)"],
                ["Air",         f"{vals['air']/1e6:.2f} M m³",        f"{row['Air_pct']:.1f}%",
                 f"{DIRECT_WATER['air']['base']} L/passenger"],
                ["TOTAL",       fmt_m3(total),                          "100.0%", ""],
            ]
            if log:
                log.table(["Sector", "Volume", "Share", "Coefficient"], coeff_rows)
            else:
                print(table_str(["Sector", "Volume", "Share", "Coefficient"], coeff_rows))

    df = pd.DataFrame(rows)

    base_total = df[df["Scenario"] == "BASE"]["Total_m3"].iloc[0]
    low_total  = df[df["Scenario"] == "LOW"]["Total_m3"].iloc[0]
    high_total = df[df["Scenario"] == "HIGH"]["Total_m3"].iloc[0]

    subsection("Sensitivity range", log=log)
    ok(f"LOW:  {fmt_m3(low_total)}", log)
    ok(f"BASE: {fmt_m3(base_total)}", log)
    ok(f"HIGH: {fmt_m3(high_total)}  (range: {fmt_sens_range(low_total, base_total, high_total)} around BASE)", log)

    if base_total / 1e9 > 5.0:
        warn(f"BASE direct TWF = {fmt_m3(base_total)} — unusually high (>5 bn m³). "
             "Verify activity data coefficients.", log)
    return df


def _save_direct_summary_txt(df: pd.DataFrame, year: str, path: Path,
                              log: Logger = None):
    """Write plain-text direct TWF summary (unchanged output format)."""
    base = df[df["Scenario"] == "BASE"].iloc[0]
    low  = df[df["Scenario"] == "LOW"].iloc[0]
    high = df[df["Scenario"] == "HIGH"].iloc[0]
    act  = ACTIVITY_DATA[year]

    dom_hotel_share    = act.get("dom_hotel_share", 0.15)
    inb_hotel_share    = act.get("inb_hotel_share", 1.00)
    dom_rail_modal     = act.get("dom_rail_modal_share", 0.25)
    avg_rail_km        = act.get("avg_tourist_rail_km", 242)
    dom_nights         = act["domestic_tourists_M"] * 1e6 * act["avg_stay_days_dom"] * dom_hotel_share
    inb_nights         = act["inbound_tourists_M"]  * 1e6 * act["avg_stay_days_inb"] * inb_hotel_share
    total_nights       = dom_nights + inb_nights
    tourist_rail_pkm_B = act["domestic_tourists_M"] * dom_rail_modal * avg_rail_km / 1e3

    lines = [
        f"DIRECT TWF — FY {year}", "=" * 60, "",
        "Activity Data",
        f"  Domestic tourists      : {act['domestic_tourists_M']:.1f} M",
        f"  Inbound tourists       : {act['inbound_tourists_M']:.2f} M",
        f"  Avg stay (domestic)    : {act['avg_stay_days_dom']:.1f} days",
        f"  Avg stay (inbound)     : {act['avg_stay_days_inb']:.1f} days",
        f"  Dom hotel share        : {dom_hotel_share:.0%}  (NSS Report 580, Table 3.14; Census 2011)",
        f"  Inb hotel share        : {inb_hotel_share:.0%}  (structural; MoT IPS / TSA 2015-16 Table 3)",
        f"  Hotel-nights (dom)     : {dom_nights/1e6:.1f} M",
        f"  Hotel-nights (inb)     : {inb_nights/1e6:.1f} M",
        f"  Hotel-nights total     : {total_nights/1e6:.1f} M",
        f"  Rail modal share (dom) : {dom_rail_modal:.0%}  (NSS Report 580, Table 3.6)",
        f"  Avg tourist rail km    : {avg_rail_km:.0f} km  (MoR Annual Statistical Statement Table 2)",
        f"  Tourist rail pkm       : {tourist_rail_pkm_B:.1f}B pkm",
        "",
        "BASE Scenario",
        f"  Hotels      : {base['Hotel_m3']:>15,.0f} m³  ({base['Hotel_pct']:.1f}%)",
        f"  Restaurants : {base['Restaurant_m3']:>15,.0f} m³  ({base['Rest_pct']:.1f}%)",
        f"  Rail        : {base['Rail_m3']:>15,.0f} m³  ({base['Rail_pct']:.1f}%)",
        f"  Air         : {base['Air_m3']:>15,.0f} m³  ({base['Air_pct']:.1f}%)",
        f"  TOTAL       : {base['Total_m3']:>15,.0f} m³  = {base['Total_billion_m3']:.4f} bn m³",
        "",
        "Sensitivity (LOW / BASE / HIGH)",
        f"  LOW:  {low['Total_billion_m3']:.4f} bn m³",
        f"  BASE: {base['Total_billion_m3']:.4f} bn m³",
        f"  HIGH: {high['Total_billion_m3']:.4f} bn m³",
        f"  Range: {fmt_sens_range(low['Total_m3'], base['Total_m3'], high['Total_m3'])} around BASE",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    ok(f"Summary written: {path.name}", log)


def _run_direct_water(log: Logger):
    """Run direct water TWF calculation for all study years."""
    log.section("CALCULATE DIRECT TWF (Activity-Based, 4-Sector Model)")

    log.subsection("Water coefficients by year")
    log.info("Hotel coefficients (L/room/night):")
    hotel_rows = [
        [yr, DIRECT_WATER["hotel"][yr]["low"],
             DIRECT_WATER["hotel"][yr]["base"],
             DIRECT_WATER["hotel"][yr]["high"]]
        for yr in STUDY_YEARS if yr in DIRECT_WATER["hotel"]
    ]
    log.table(["Year", "LOW", "BASE", "HIGH"], hotel_rows)
    log.info(
        f"  Rail — LOW:{DIRECT_WATER['rail']['low']}  "
        f"BASE:{DIRECT_WATER['rail']['base']}  HIGH:{DIRECT_WATER['rail']['high']}  L/pkm"
    )
    log.info(
        f"  Air  — LOW:{DIRECT_WATER['air']['low']}  "
        f"BASE:{DIRECT_WATER['air']['base']}  HIGH:{DIRECT_WATER['air']['high']}  L/passenger"
    )

    out_dir = DIRS["direct"]
    out_dir.mkdir(parents=True, exist_ok=True)

    all_dfs   = []
    base_vals = {}

    for year in STUDY_YEARS:
        df = _calculate_direct_year(year, log)
        save_csv(df, out_dir / f"direct_twf_{year}.csv", f"Direct TWF {year}", log=log)
        _save_direct_summary_txt(df, year, out_dir / f"direct_twf_{year}_summary.txt", log)
        all_dfs.append(df)
        base_vals[year] = df[df["Scenario"] == "BASE"]["Total_billion_m3"].iloc[0]

    save_csv(
        pd.concat(all_dfs, ignore_index=True),
        out_dir / "direct_twf_all_years.csv",
        "Direct TWF all years",
        log=log,
    )

    log.section("Cross-Year Direct TWF Comparison")
    compare_across_years(base_vals, "Direct TWF BASE (billion m³)", STUDY_YEARS, " bn m³", log=log)

    if "2015" in DIRECT_WATER["hotel"] and "2022" in DIRECT_WATER["hotel"]:
        h15 = DIRECT_WATER["hotel"]["2015"]["base"]
        h22 = DIRECT_WATER["hotel"]["2022"]["base"]
        chg = 100 * (h22 - h15) / h15
        ok(f"Hotel water efficiency: {h15} → {h22} L/room/night  ({chg:+.1f}% change, 2015→2022)", log)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — MONETISE DEPLETION  (was monetise.py)
# ══════════════════════════════════════════════════════════════════════════════

def _monetise_year(year: str, log: Logger = None) -> dict | None:
    """
    Monetise physical depletion for one study year.
    Reads indirect_depletion_{year}_by_sut.csv, applies UNIT_RENTS.
    Returns result dict or None if input file missing.
    """
    dep_dir  = DIRS["indirect_depletion"]
    sut_path = dep_dir / f"indirect_depletion_{year}_by_sut.csv"

    if not sut_path.exists():
        warn(
            f"Depletion SUT file missing: {sut_path}\n"
            f"  → Run:  python main.py --stressor depletion --steps indirect",
            log,
        )
        return None

    df    = pd.read_csv(sut_path)
    rents = UNIT_RENTS.get(year, UNIT_RENTS["2022"])

    fossil_t  = float(df["Fossil_t"].sum())   if "Fossil_t"   in df.columns else 0.0
    other_t   = float(df["AllOther_t"].sum()) if "AllOther_t" in df.columns else 0.0
    total_t   = fossil_t + other_t

    fossil_mon = fossil_t * rents["fossil"]
    other_mon  = other_t  * rents.get("metal", rents["fossil"] * 0.3)
    total_mon  = fossil_mon + other_mon
    usd_rate   = USD_INR.get(year, 70.0)

    subsection(f"Year {year}", log)
    ok(f"Fossil fuel depletion  : {fossil_t:>16,.0f} t   × ₹{rents['fossil']:.5f} cr/t"
       f"  = ₹{fossil_mon:>12,.2f} cr", log)
    ok(f"Other natural capital  : {other_t:>16,.0f} t   × ₹{rents.get('metal', 0):.5f} cr/t"
       f"  = ₹{other_mon:>12,.2f} cr", log)
    ok(f"Total monetary depletion {year}: ₹{total_mon:,.2f} cr  "
       f"(${total_mon * 10 / usd_rate:,.1f}M)", log)

    result = {
        "year":                        year,
        "fossil_physical_t":           round(fossil_t),
        "other_physical_t":            round(other_t),
        "total_physical_t":            round(total_t),
        "fossil_monetary_crore":       round(fossil_mon, 2),
        "other_monetary_crore":        round(other_mon,  2),
        "monetary_depletion_crore":    round(total_mon,  2),
        "fossil_unit_rent_cr_per_t":   rents["fossil"],
        "other_unit_rent_cr_per_t":    rents.get("metal", 0),
        "usd_rate":                    usd_rate,
        "monetary_depletion_usd_m":    round(total_mon * 10 / usd_rate, 1),
    }

    out_dir = DIRS["monetary_depletion"]
    out_dir.mkdir(parents=True, exist_ok=True)
    save_csv(pd.DataFrame([result]),
             out_dir / f"monetary_depletion_{year}.csv",
             f"Monetary depletion {year}", log=log)
    return result


def _save_monetise_summary(results: list[dict], out_path: Path, log: Logger = None):
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("MONETARY NATURAL CAPITAL DEPLETION — INDIA\n")
        f.write("=" * 60 + "\n\n")
        f.write("Method: Leontief EEIO (C × L × Y) + unit rent monetisation\n")
        f.write("Source: EXIOBASE 3 material/F.txt + World Bank Wealth Accounts\n\n")
        for r in sorted(results, key=lambda x: x["year"]):
            f.write(f"Year: {r['year']}\n")
            f.write(f"  Fossil physical    : {r['fossil_physical_t']:>14,.0f} tonnes\n")
            f.write(f"  Other physical     : {r['other_physical_t']:>14,.0f} tonnes\n")
            f.write(f"  Total physical     : {r['total_physical_t']:>14,.0f} tonnes\n")
            f.write(f"  Fossil monetary    : ₹{r['fossil_monetary_crore']:>12,.2f} crore\n")
            f.write(f"  Other monetary     : ₹{r['other_monetary_crore']:>12,.2f} crore\n")
            f.write(f"  TOTAL MONETARY DEP : ₹{r['monetary_depletion_crore']:>12,.2f} crore\n")
            f.write(f"  USD equivalent     : ${r['monetary_depletion_usd_m']:>10,.1f} M\n\n")
    ok(f"Summary: {out_path.name}", log)


def _run_monetise(log: Logger):
    """Monetise physical depletion for all study years."""
    log.section("MONETISE NATURAL CAPITAL DEPLETION  (physical tonnes → ₹ crore)")
    log.info("Unit rents source: reference_data.md § UNIT_RENTS "
             "(World Bank Wealth Accounts + IBM/MoM royalty data)")

    out_dir = DIRS["monetary_depletion"]
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for year in STUDY_YEARS:
        result = _monetise_year(year, log)
        if result:
            results.append(result)

    if not results:
        log.fail("No depletion results found — run indirect.py with stressor=depletion first")
        return

    log.section("Cross-Year Monetary Depletion Summary")
    compare_across_years(
        {r["year"]: r["monetary_depletion_crore"] for r in results},
        "Monetary natural capital depletion (₹ crore)", unit=" cr", log=log,
    )
    compare_across_years(
        {r["year"]: r["fossil_monetary_crore"] for r in results},
        "  of which: fossil fuels (₹ crore)", unit=" cr", log=log,
    )
    compare_across_years(
        {r["year"]: r["total_physical_t"] for r in results},
        "Total physical depletion (tonnes)", unit=" t", log=log,
    )

    df_all = pd.DataFrame(results)
    save_csv(df_all, out_dir / "monetary_depletion_all_years.csv",
             "Monetary depletion all years", log=log)
    _save_monetise_summary(results, out_dir / "monetary_depletion_summary.txt", log=log)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — NDP COMPUTE  (was ndp_report.py)
# Narrative template filling → compare.py fill_ndp_extras()
# ══════════════════════════════════════════════════════════════════════════════

def _compute_ndp(year: str, monetary_depletion_crore: float,
                 log: Logger = None) -> dict:
    """
    Compute NDP for one year.  NDP = GDP − CFC − Natural_Capital_Depletion.
    All values in ₹ crore at current prices.
    Framework: SEEA-CF / UNSC recommendation.
    """
    macro    = NAS_MACRO.get(year, {})
    gdp      = macro.get("gdp_crore", 0.0)
    cfc      = macro.get("cfc_crore", 0.0)
    dep      = monetary_depletion_crore
    ndp      = gdp - cfc - dep
    usd_rate = USD_INR.get(year, 70.0)
    def _usd(c): return round(c * 10 / usd_rate, 1)

    ok(f"{year}:  GDP ₹{gdp:>14,.0f} cr"
       f"  − CFC ₹{cfc:>12,.0f} cr"
       f"  − Depletion ₹{dep:>10,.0f} cr"
       f"  = NDP ₹{ndp:>14,.0f} cr", log)

    return {
        "year":                        year,
        "gdp_crore":                   round(gdp),
        "cfc_crore":                   round(cfc),
        "natural_depletion_crore":     round(dep, 2),
        "ndp_crore":                   round(ndp, 2),
        "gdp_usd_m":                   _usd(gdp),
        "ndp_usd_m":                   _usd(ndp),
        "depletion_usd_m":             _usd(dep),
        "cfc_pct_of_gdp":              round(100 * cfc / gdp, 3) if gdp else 0,
        "depletion_pct_of_gdp":        round(100 * dep / gdp, 4) if gdp else 0,
        "total_adjustment_pct_of_gdp": round(100 * (cfc + dep) / gdp, 3) if gdp else 0,
        "ndp_gdp_ratio":               round(ndp / gdp, 6) if gdp else 0,
        "ndp_pct_of_gdp":              round(100 * ndp / gdp, 3) if gdp else 0,
        "usd_inr_rate":                usd_rate,
    }


def _build_ndp_decomposition(result: dict) -> pd.DataFrame:
    """4-row decomposition table (GDP / CFC / Depletion / NDP) for one year."""
    return pd.DataFrame([
        {
            "Component":  "Gross Domestic Product (GDP)",
            "Crore_INR":  result["gdp_crore"],
            "USD_Million": result["gdp_usd_m"],
            "Pct_of_GDP": 100.0,
            "Note":       "MoSPI NAS 2023, Statement 1 — current prices",
        },
        {
            "Component":  "Less: Consumption of Fixed Capital (CFC)",
            "Crore_INR":  -result["cfc_crore"],
            "USD_Million": -result["gdp_usd_m"] * result["cfc_pct_of_gdp"] / 100,
            "Pct_of_GDP": -result["cfc_pct_of_gdp"],
            "Note":       "MoSPI NAS 2023, Statement 2 — depreciation of produced assets",
        },
        {
            "Component":  "Less: Natural Capital Depletion",
            "Crore_INR":  -result["natural_depletion_crore"],
            "USD_Million": -result["depletion_usd_m"],
            "Pct_of_GDP": -result["depletion_pct_of_gdp"],
            "Note":       "EEIO estimate — D×L×Y, EXIOBASE material/F.txt + unit rents (reference_data.md § UNIT_RENTS)",
        },
        {
            "Component":  "= Net Domestic Product (NDP)",
            "Crore_INR":  result["ndp_crore"],
            "USD_Million": result["ndp_usd_m"],
            "Pct_of_GDP": result["ndp_pct_of_gdp"],
            "Note":       "NDP = GDP − CFC − Natural Capital Depletion",
        },
    ])


def _save_ndp_summary_txt(results: list[dict], out_path: Path, log: Logger = None):
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("INDIA NET DOMESTIC PRODUCT (NDP) — EEIO ESTIMATE\n")
        f.write("=" * 65 + "\n\n")
        f.write("NDP = GDP − Consumption of Fixed Capital (CFC)\n")
        f.write("           − Natural Capital Depletion (EEIO-based)\n\n")
        f.write("Framework: SEEA-CF / UNSC recommendation\n")
        f.write("Method:    Environmentally Extended Input-Output (EEIO)\n")
        f.write("           Leontief inverse from MoSPI SUT (140×140)\n")
        f.write("           Depletion coefficients from EXIOBASE 3 material/F.txt\n")
        f.write("           Monetised via World Bank Wealth Account unit rents\n")
        f.write("           (reference_data.md § UNIT_RENTS and § NAS_MACRO)\n\n")
        f.write("-" * 65 + "\n\n")

        for r in sorted(results, key=lambda x: x["year"]):
            f.write(f"FISCAL YEAR {r['year']}\n")
            f.write(f"  GDP                          : ₹{r['gdp_crore']:>14,.0f} crore\n")
            f.write(f"  Less: CFC                    : ₹{r['cfc_crore']:>14,.0f} crore"
                    f"  ({r['cfc_pct_of_gdp']:.1f}% of GDP)\n")
            f.write(f"  Less: Natural capital dep.   : ₹{r['natural_depletion_crore']:>14,.2f} crore"
                    f"  ({r['depletion_pct_of_gdp']:.3f}% of GDP)\n")
            f.write(f"  {'─'*53}\n")
            f.write(f"  NET DOMESTIC PRODUCT (NDP)   : ₹{r['ndp_crore']:>14,.2f} crore"
                    f"  ({r['ndp_pct_of_gdp']:.2f}% of GDP)\n")
            f.write(f"  NDP/GDP ratio                : {r['ndp_gdp_ratio']:.6f}\n")
            f.write(f"  Total adjustment (CFC+dep)   : {r['total_adjustment_pct_of_gdp']:.2f}% of GDP\n\n")

        if len(results) >= 2:
            r0 = sorted(results, key=lambda x: x["year"])[0]
            r1 = sorted(results, key=lambda x: x["year"])[-1]
            dep_chg = r1["depletion_pct_of_gdp"] - r0["depletion_pct_of_gdp"]
            ndp_chg = r1["ndp_pct_of_gdp"]        - r0["ndp_pct_of_gdp"]
            f.write("TREND NARRATIVE\n")
            f.write(f"  Between {r0['year']} and {r1['year']}, natural capital depletion\n")
            f.write(f"  as a share of GDP {'increased' if dep_chg > 0 else 'decreased'} by"
                    f" {abs(dep_chg):.3f} percentage points,\n")
            f.write(f"  from {r0['depletion_pct_of_gdp']:.3f}% to {r1['depletion_pct_of_gdp']:.3f}%.\n")
            f.write(f"  NDP as a share of GDP {'fell' if ndp_chg < 0 else 'rose'} by"
                    f" {abs(ndp_chg):.2f} pp over the same period.\n\n")

        f.write("NOTE ON UNIT RENTS\n")
        f.write("  Unit rents (₹ crore per tonne) are in reference_data.md § UNIT_RENTS.\n")
        f.write("  Derived from World Bank Wealth Accounts (2021) and IBM/MoM royalty data.\n")
        f.write("  Sensitivity: ±20% on unit rents shifts NDP by approx. ±0.01-0.03% of GDP.\n")

    ok(f"Summary narrative: {out_path.name}", log)


def _run_ndp(log: Logger):
    """Compute NDP for all study years from monetise outputs."""
    log.section("NDP REPORT  (GDP − CFC − Natural Capital Depletion)")
    log.info("Framework: SEEA-CF / UNSC recommendation")
    log.info("GDP + CFC source: reference_data.md § NAS_MACRO (MoSPI NAS 2023)")

    ndp_dir  = DIRS["ndp"]
    ndp_dir.mkdir(parents=True, exist_ok=True)

    mon_path = DIRS["monetary_depletion"] / "monetary_depletion_all_years.csv"
    if not mon_path.exists():
        log.fail(
            f"Missing: {mon_path}\n"
            f"  → Run:  python main.py --stressor depletion --steps monetise"
        )
        return

    mon_df  = pd.read_csv(mon_path)
    results = []

    for year in STUDY_YEARS:
        row = mon_df[mon_df["year"].astype(str) == str(year)]
        if row.empty:
            warn(f"No monetary depletion data for {year} — skipping", log)
            continue
        dep    = float(row["monetary_depletion_crore"].iloc[0])
        result = _compute_ndp(year, dep, log)
        results.append(result)

        decomp_df = _build_ndp_decomposition(result)
        save_csv(decomp_df, ndp_dir / f"ndp_decomposition_{year}.csv",
                 f"NDP decomposition {year}", log=log)

    if not results:
        log.fail("No NDP results computed — check monetise outputs")
        return

    df_all = pd.DataFrame(results)
    save_csv(df_all, ndp_dir / "ndp_all_years.csv", "NDP all years", log=log)

    log.section("Cross-Year NDP Comparison")
    compare_across_years({r["year"]: r["ndp_crore"]              for r in results}, "NDP (₹ crore)",                           unit=" cr", log=log)
    compare_across_years({r["year"]: r["ndp_pct_of_gdp"]          for r in results}, "NDP as % of GDP",                         unit="%",   log=log)
    compare_across_years({r["year"]: r["depletion_pct_of_gdp"]    for r in results}, "Natural capital depletion as % of GDP",   unit="%",   log=log)
    compare_across_years({r["year"]: r["total_adjustment_pct_of_gdp"] for r in results}, "Total adjustment (CFC+dep) as % of GDP", unit="%", log=log)

    _save_ndp_summary_txt(results, ndp_dir / "ndp_summary.txt", log=log)


# ══════════════════════════════════════════════════════════════════════════════
# UNIVERSAL DISPATCHER
# ══════════════════════════════════════════════════════════════════════════════

def run(stressor: str = "water", phase: str = "all", **kwargs):
    """
    Universal post-indirect dispatcher.

    Parameters
    ----------
    stressor : "water" | "energy" | "depletion" | "emissions"
    phase    : "all" | "direct" | "monetise" | "ndp"
               "all" runs everything configured for this stressor.
               Specific phases let main.py dispatch "monetise" and "ndp_report"
               as separate step names while routing both to this file.
    """
    cfg = POST_CFG.get(stressor, {})
    log_dir = DIRS["logs"] / f"postprocess_{stressor}"

    with Logger(f"postprocess_{stressor}", log_dir) as log:
        t = Timer()
        log.section(f"POST-INDIRECT PROCESSING [{stressor.upper()}]")

        run_direct   = cfg.get("has_direct",   False) and phase in ("all", "direct")
        run_monetise = cfg.get("has_monetise", False) and phase in ("all", "monetise")
        run_ndp      = cfg.get("has_ndp",      False) and phase in ("all", "ndp")

        if not any([run_direct, run_monetise, run_ndp]):
            log.info(f"No post-indirect steps configured for stressor='{stressor}' phase='{phase}'.")
            return

        if run_direct:
            _run_direct_water(log)
        if run_monetise:
            _run_monetise(log)
        if run_ndp:
            _run_ndp(log)

        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Post-indirect stressor processing")
    p.add_argument("--stressor", default="water",
                   choices=list(POST_CFG), help="Stressor to process")
    p.add_argument("--phase", default="all",
                   choices=["all", "direct", "monetise", "ndp"],
                   help="Which sub-step to run")
    args = p.parse_args()
    run(stressor=args.stressor, phase=args.phase)
