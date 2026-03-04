"""
calculate_direct_twf.py — Direct (on-site operational) Tourism Water Footprint
===============================================================================

WHY SEPARATE FROM EEIO?
EXIOBASE water data is production-based (WaterGAP/WFN) and assigns zero to
service sectors.  Direct operational water (hotel taps, restaurant kitchens,
station facilities) must be estimated via activity-based coefficients.

FRAMEWORK  (four sectors, three scenarios)
──────────────────────────────────────────
  Hotels      : occupied_rooms × occupancy_rate × nights_per_year × L/room/night
  Restaurants : (domestic_days + inbound_days) × meals/day × L/meal
  Rail        : rail_pkm_B × 1e9 × tourist_share × L/pkm
  Air         : air_pax_M × 1e6 × tourist_share × L/passenger

  Scenarios   : LOW / BASE / HIGH  (coefficient uncertainty)

OUTPUTS
───────
  direct_twf_{year}.csv          — activity data + water by sector + scenarios
  direct_twf_all_years.csv       — cross-year comparison
  direct_twf_{year}_summary.txt  — plain-text summary for each year
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import DIRS, DIRECT_WATER, STUDY_YEARS, ACTIVITY_DATA
from utils import (
    section, subsection, ok, warn, save_csv, compare_across_years,
    Timer, Logger, fmt_m3, table_str,
)


# ══════════════════════════════════════════════════════════════════════════════
# SECTOR CALCULATORS  (unified dispatcher)
# ══════════════════════════════════════════════════════════════════════════════

def _calc_hotel(year: str, scenario: str) -> float:
    """m³/year from classified hotel rooms."""
    act   = ACTIVITY_DATA[year]
    coeff = DIRECT_WATER["hotel"].get(year, DIRECT_WATER["hotel"]["2022"])[scenario]
    occupied_nights = (
        act["classified_rooms"] * act["occupancy_rate"] * act["nights_per_year"]
    )
    return occupied_nights * coeff / 1_000


def _calc_restaurant(year: str, scenario: str) -> float:
    """m³ from tourist meals (domestic + inbound tourist-days × meals/day × L/meal)."""
    act   = ACTIVITY_DATA[year]
    coeff = DIRECT_WATER["restaurant"][year][scenario]
    dom_days    = act["domestic_tourists_M"] * 1e6 * act["avg_stay_days_dom"]
    inb_days    = act["inbound_tourists_M"]  * 1e6 * act["avg_stay_days_inb"]
    total_meals = (dom_days + inb_days) * act["meals_per_tourist_day"]
    return total_meals * coeff / 1_000


def _calc_rail(year: str, scenario: str) -> float:
    """m³ from tourist rail travel (passenger-km × L/pkm)."""
    act   = ACTIVITY_DATA[year]
    coeff = DIRECT_WATER["rail"][scenario]
    return act["rail_pkm_B"] * 1e9 * act["tourist_rail_share"] * coeff / 1_000


def _calc_air(year: str, scenario: str) -> float:
    """m³ from tourist air travel (passengers × L/passenger)."""
    act   = ACTIVITY_DATA[year]
    coeff = DIRECT_WATER["air"][scenario]
    return act["air_pax_M"] * 1e6 * act["tourist_air_share"] * coeff / 1_000


# Dispatch table: sector_name → calculator function
_SECTOR_CALCS = {
    "hotel":      _calc_hotel,
    "restaurant": _calc_restaurant,
    "rail":       _calc_rail,
    "air":        _calc_air,
}

def calculate_sector_water(year: str, sector: str, scenario: str) -> float:
    """
    Universal water calculator.

    Parameters
    ----------
    year     : study year string ("2015", "2019", "2022")
    sector   : one of "hotel", "restaurant", "rail", "air"
    scenario : one of "low", "base", "high"

    Returns
    -------
    float : water in m³
    """
    fn = _SECTOR_CALCS.get(sector)
    if fn is None:
        raise ValueError(f"Unknown sector '{sector}'. Available: {list(_SECTOR_CALCS)}")
    return fn(year, scenario)


# ══════════════════════════════════════════════════════════════════════════════
# YEAR CALCULATOR
# ══════════════════════════════════════════════════════════════════════════════

def calculate_year(year: str, log: Logger = None) -> pd.DataFrame:
    """
    Calculate direct TWF for all sectors and scenarios for one study year.

    Prints a rich activity breakdown table and returns a DataFrame with
    columns: Year, Scenario, Hotel_m3, Restaurant_m3, Rail_m3, Air_m3,
             Total_m3, Total_billion_m3, {Sector}_pct, ...
    """
    section(f"Direct TWF — FY {year}", log=log)
    act = ACTIVITY_DATA[year]

    # ── Activity data summary ────────────────────────────────────────────────
    subsection("Activity inputs", log=log)
    act_rows = [
        ["Domestic tourists",   f"{act['domestic_tourists_M']:.1f} M",        "MoT Annual Report"],
        ["Inbound tourists",    f"{act['inbound_tourists_M']:.2f} M",          "MoT/UNWTO"],
        ["Avg stay (domestic)", f"{act['avg_stay_days_dom']:.1f} days",        "NSSO Tourism Survey"],
        ["Avg stay (inbound)",  f"{act['avg_stay_days_inb']:.1f} days",        "MoT"],
        ["Classified hotel rooms", f"{act['classified_rooms']:,.0f}",          "MoT Hotel Survey"],
        ["Hotel occupancy rate",   f"{act['occupancy_rate']*100:.0f}%",        "MoT Hotel Survey"],
        ["Rail pkm",            f"{act['rail_pkm_B']:.1f} B pkm",              "MoR Annual Report"],
        ["Air passengers",      f"{act['air_pax_M']:.1f} M",                   "DGCA"],
        ["Tourist rail share",  f"{act['tourist_rail_share']*100:.0f}%",       "NSSO Tourism Survey"],
        ["Tourist air share",   f"{act['tourist_air_share']*100:.0f}%",        "DGCA/NSSO"],
    ]
    if log:
        log.table(["Parameter", "Value", "Source"], act_rows)
    else:
        print(table_str(["Parameter", "Value", "Source"], act_rows))

    # ── Compute all sector × scenario combinations ───────────────────────────
    rows = []
    for scenario in ["low", "base", "high"]:
        vals = {s: calculate_sector_water(year, s, scenario) for s in _SECTOR_CALCS}
        total = sum(vals.values())

        row = {
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
            coeff_rows = [
                ["Hotels",      f"{vals['hotel']/1e6:.2f} M m³",      f"{row['Hotel_pct']:.1f}%",
                 f"{DIRECT_WATER['hotel'].get(year, DIRECT_WATER['hotel']['2022'])['base']} L/room/night"],
                ["Restaurants", f"{vals['restaurant']/1e6:.2f} M m³", f"{row['Rest_pct']:.1f}%",
                 f"{DIRECT_WATER['restaurant'][year]['base']} L/meal"],
                ["Rail",        f"{vals['rail']/1e6:.2f} M m³",       f"{row['Rail_pct']:.1f}%",
                 f"{DIRECT_WATER['rail']['base']} L/pkm"],
                ["Air",         f"{vals['air']/1e6:.2f} M m³",        f"{row['Air_pct']:.1f}%",
                 f"{DIRECT_WATER['air']['base']} L/passenger"],
                ["TOTAL",       fmt_m3(total),                          "100.0%", ""],
            ]
            if log:
                log.table(["Sector", "Volume", "Share", "Coefficient"], coeff_rows)
            else:
                print(table_str(["Sector", "Volume", "Share", "Coefficient"], coeff_rows))

    df = pd.DataFrame(rows)

    # ── Sensitivity summary ─────────────────────────────────────────────────
    base_total = df[df["Scenario"] == "BASE"]["Total_m3"].iloc[0]
    low_total  = df[df["Scenario"] == "LOW"]["Total_m3"].iloc[0]
    high_total = df[df["Scenario"] == "HIGH"]["Total_m3"].iloc[0]
    range_pct  = 100 * (high_total - low_total) / base_total

    subsection("Sensitivity range", log=log)
    ok(f"LOW:  {fmt_m3(low_total)}", log)
    ok(f"BASE: {fmt_m3(base_total)}", log)
    ok(f"HIGH: {fmt_m3(high_total)}  (range: ±{range_pct/2:.1f}% around BASE)", log)

    # Sanity check: direct should be < 20% of a plausible total
    # (Total indirect will be around 10× direct; warn if outside expected range)
    if base_total / 1e9 > 5.0:
        warn(f"BASE direct TWF = {fmt_m3(base_total)} — unusually high (>5 bn m³). "
             "Verify activity data coefficients.", log)

    return df


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY TEXT FILE
# ══════════════════════════════════════════════════════════════════════════════

def save_summary_txt(df: pd.DataFrame, year: str, path: Path,
                     log: Logger = None):
    base = df[df["Scenario"] == "BASE"].iloc[0]
    low  = df[df["Scenario"] == "LOW"].iloc[0]
    high = df[df["Scenario"] == "HIGH"].iloc[0]
    act  = ACTIVITY_DATA[year]

    lines = [
        f"DIRECT TWF — FY {year}",
        "=" * 60,
        "",
        "Activity Data",
        f"  Domestic tourists   : {act['domestic_tourists_M']:.1f} M",
        f"  Inbound tourists    : {act['inbound_tourists_M']:.2f} M",
        f"  Avg stay (domestic) : {act['avg_stay_days_dom']:.1f} days",
        f"  Avg stay (inbound)  : {act['avg_stay_days_inb']:.1f} days",
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
        f"  Range: {100*(high['Total_m3']-low['Total_m3'])/base['Total_m3']:.1f}% around BASE",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    ok(f"Summary written: {path.name}", log)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def run(**kwargs):
    log_dir = DIRS["logs"] / "direct_twf"
    with Logger("calculate_direct_twf", log_dir) as log:
        t = Timer()
        log.section("CALCULATE DIRECT TWF (Activity-Based, 4-Sector Model)")

        # ── Print water coefficient tables ────────────────────────────────────
        log.subsection("Water coefficients by year")
        log.info("Hotel coefficients (L/room/night):")
        hotel_rows = [
            [yr, DIRECT_WATER["hotel"][yr]["low"],
                 DIRECT_WATER["hotel"][yr]["base"],
                 DIRECT_WATER["hotel"][yr]["high"]]
            for yr in STUDY_YEARS if yr in DIRECT_WATER["hotel"]
        ]
        log.table(["Year", "LOW", "BASE", "HIGH"], hotel_rows)
        log.info("Restaurant (L/meal)  Rail (L/pkm)  Air (L/pax):")
        log.info(
            f"  Rail  — LOW:{DIRECT_WATER['rail']['low']}  "
            f"BASE:{DIRECT_WATER['rail']['base']}  HIGH:{DIRECT_WATER['rail']['high']}"
        )
        log.info(
            f"  Air   — LOW:{DIRECT_WATER['air']['low']}  "
            f"BASE:{DIRECT_WATER['air']['base']}  HIGH:{DIRECT_WATER['air']['high']}"
        )

        out_dir = DIRS["direct"]
        out_dir.mkdir(parents=True, exist_ok=True)

        all_dfs   = []
        base_vals = {}

        for year in STUDY_YEARS:
            df = calculate_year(year, log)
            save_csv(df, out_dir / f"direct_twf_{year}.csv", f"Direct TWF {year}", log=log)
            save_summary_txt(df, year, out_dir / f"direct_twf_{year}_summary.txt", log)
            all_dfs.append(df)
            base_vals[year] = df[df["Scenario"] == "BASE"]["Total_billion_m3"].iloc[0]

        save_csv(
            pd.concat(all_dfs, ignore_index=True),
            out_dir / "direct_twf_all_years.csv",
            "Direct TWF all years",
            log=log,
        )

        # ── Cross-year comparison ─────────────────────────────────────────────
        log.section("Cross-Year Direct TWF Comparison")
        compare_across_years(
            base_vals,
            "Direct TWF BASE (billion m³)",
            STUDY_YEARS,
            " bn m³",
            log=log,
        )

        # Hotel efficiency trend
        if "2015" in DIRECT_WATER["hotel"] and "2022" in DIRECT_WATER["hotel"]:
            h15 = DIRECT_WATER["hotel"]["2015"]["base"]
            h22 = DIRECT_WATER["hotel"]["2022"]["base"]
            chg = 100 * (h22 - h15) / h15
            ok(f"Hotel water efficiency: {h15} → {h22} L/room/night  "
               f"({chg:+.1f}% change, 2015→2022)", log)

        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    run()
