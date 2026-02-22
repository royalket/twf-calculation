"""
Calculate direct (on-site operational) Tourism Water Footprint.

Why separate from EEIO: EXIOBASE water data is production-based (WaterGAP/WFN)
and assigns zero to service sectors. Direct operational water (hotel taps,
restaurant kitchens, station facilities) must be estimated via activity-based
coefficients.

Activity framework:
  Hotels:       occupied_rooms × L/room/night → m³
  Restaurants:  meals_served   × L/meal       → m³
  Rail:         passenger_km   × L/pkm        → m³
  Air:          passengers     × L/passenger  → m³

Three scenarios (LOW / BASE / HIGH) for sensitivity analysis.
Direct water is typically 8-15% of total TWF.

Outputs:
  direct_twf_{year}.csv          — activity data + water by sector + scenarios
  direct_twf_all_years.csv       — cross-year comparison
  direct_twf_{year}_summary.txt
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
# FIX: Import ACTIVITY_DATA from config (single source of truth).
# The original module defined its own duplicate copy, risking silent data drift.
from config import BASE_DIR, DIRS, DIRECT_WATER, TSA_BASE, STUDY_YEARS, ACTIVITY_DATA
from utils import (
    section, subsection, ok, warn, save_csv,
    year_comparison_table, Timer, Logger,
)


# ── Hotel water ───────────────────────────────────────────────────────────────

def hotel_water(year: str, scenario: str) -> float:
    """m³ per year from classified hotel rooms."""
    act = ACTIVITY_DATA[year]
    coeff = DIRECT_WATER["hotel"].get(year, DIRECT_WATER["hotel"]["2022"])[scenario]  # L/room/night
    occupied_nights = act["classified_rooms"] * act["occupancy_rate"] * act["nights_per_year"]
    m3 = occupied_nights * coeff / 1000  # L → m³
    return m3


# ── Restaurant water ──────────────────────────────────────────────────────────

def restaurant_water(year: str, scenario: str) -> float:
    """m³ from tourist meals at restaurants."""
    act = ACTIVITY_DATA[year]
    coeff = DIRECT_WATER["restaurant"][year][scenario]  # L/meal

    # Total tourist days × meals/day
    # FIX: use avg_stay_days_dom and avg_stay_days_inb (config key names)
    domestic_days = act["domestic_tourists_M"] * 1e6 * act["avg_stay_days_dom"]
    inbound_days  = act["inbound_tourists_M"]  * 1e6 * act["avg_stay_days_inb"]
    total_meals   = (domestic_days + inbound_days) * act["meals_per_tourist_day"]
    m3 = total_meals * coeff / 1000
    return m3


# ── Rail water ────────────────────────────────────────────────────────────────

def rail_water(year: str, scenario: str) -> float:
    """m³ from tourist rail travel."""
    act = ACTIVITY_DATA[year]
    coeff = DIRECT_WATER["rail"][scenario]  # L/passenger-km

    tourist_pkm = act["rail_pkm_B"] * 1e9 * act["tourist_rail_share"]
    m3 = tourist_pkm * coeff / 1000
    return m3


# ── Air water ─────────────────────────────────────────────────────────────────

def air_water(year: str, scenario: str) -> float:
    """m³ from tourist air travel."""
    act = ACTIVITY_DATA[year]
    coeff = DIRECT_WATER["air"][scenario]  # L/passenger

    tourist_pax = act["air_pax_M"] * 1e6 * act["tourist_air_share"]
    m3 = tourist_pax * coeff / 1000
    return m3


# ── Year calculator ───────────────────────────────────────────────────────────

def calculate_year(year: str, log: Logger = None) -> pd.DataFrame:
    section(f"Direct TWF — {year}", log=log)
    rows = []

    for scenario in ["low", "base", "high"]:
        hw = hotel_water(year, scenario)
        rw = restaurant_water(year, scenario)
        rl = rail_water(year, scenario)
        aw = air_water(year, scenario)
        total = hw + rw + rl + aw

        rows.append({
            "Year": year, "Scenario": scenario.upper(),
            "Hotel_m3":         round(hw),
            "Restaurant_m3":    round(rw),
            "Rail_m3":          round(rl),
            "Air_m3":           round(aw),
            "Total_m3":         round(total),
            "Total_billion_m3": round(total / 1e9, 4),
            "Hotel_pct": round(100 * hw / total, 1),
            "Rest_pct":  round(100 * rw / total, 1),
            "Rail_pct":  round(100 * rl / total, 1),
            "Air_pct":   round(100 * aw / total, 1),
        })

        if scenario == "base":
            ok(
                f"BASE: Hotels={hw/1e6:.2f}M m³  Restaurants={rw/1e6:.2f}M m³  "
                f"Rail={rl/1e6:.2f}M m³  Air={aw/1e6:.2f}M m³",
                log,
            )
            ok(f"BASE TOTAL: {total/1e9:.4f} billion m³", log)

    df = pd.DataFrame(rows)

    # Sensitivity range
    base_total = df[df["Scenario"] == "BASE"]["Total_m3"].iloc[0]
    low_total  = df[df["Scenario"] == "LOW"]["Total_m3"].iloc[0]
    high_total = df[df["Scenario"] == "HIGH"]["Total_m3"].iloc[0]
    ok(
        f"Sensitivity range: {low_total/1e9:.4f} – {high_total/1e9:.4f} billion m³  "
        f"(BASE = {base_total/1e9:.4f})",
        log,
    )
    ok(
        f"±{100*(high_total-base_total)/base_total:.0f}% uncertainty in direct has "
        f"~{(high_total-base_total)*0.12/1e9*100:.1f}% impact on total TWF",
        log,
    )

    return df


def save_summary_txt(df: pd.DataFrame, year: str, path: Path, log: Logger = None):
    base = df[df["Scenario"] == "BASE"].iloc[0]
    with open(path, "w") as f:
        f.write(f"DIRECT TWF — {year}\n{'='*55}\n\n")
        f.write("BASE scenario:\n")
        f.write(f"  Hotels:      {base['Hotel_m3']:>15,.0f} m³  ({base['Hotel_pct']:.1f}%)\n")
        f.write(f"  Restaurants: {base['Restaurant_m3']:>15,.0f} m³  ({base['Rest_pct']:.1f}%)\n")
        f.write(f"  Rail:        {base['Rail_m3']:>15,.0f} m³  ({base['Rail_pct']:.1f}%)\n")
        f.write(f"  Air:         {base['Air_m3']:>15,.0f} m³  ({base['Air_pct']:.1f}%)\n")
        f.write(f"  TOTAL:       {base['Total_m3']:>15,.0f} m³  = {base['Total_billion_m3']:.4f} bn m³\n\n")
        f.write("Sensitivity:\n")
        for _, r in df.iterrows():
            f.write(f"  {r['Scenario']}: {r['Total_billion_m3']:.4f} bn m³\n")
    ok(f"Summary: {path.name}", log)


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    with Logger("calculate_direct_twf", DIRS["logs"]) as log:
        t = Timer()
        log.section("CALCULATE DIRECT TWF (Activity-Based)")

        out_dir = DIRS["direct"]
        out_dir.mkdir(parents=True, exist_ok=True)

        all_dfs = []
        base_vals = {}

        # FIX: iterate over STUDY_YEARS from config instead of hardcoded list
        for year in STUDY_YEARS:
            df = calculate_year(year, log)
            save_csv(df, out_dir / f"direct_twf_{year}.csv", f"Direct TWF {year}", log=log)
            save_summary_txt(df, year, out_dir / f"direct_twf_{year}_summary.txt", log)
            all_dfs.append(df)
            base_vals[year] = df[df["Scenario"] == "BASE"]["Total_billion_m3"].iloc[0]

        # Cross-year
        all_df = pd.concat(all_dfs, ignore_index=True)
        save_csv(all_df, out_dir / "direct_twf_all_years.csv", "Direct TWF all years", log=log)

        log.section("Cross-Year Direct TWF Comparison")
        year_comparison_table(base_vals, "Direct TWF BASE (billion m³)", STUDY_YEARS, " bn m³", log=log)

        # Hotel coefficient improvement
        h15 = DIRECT_WATER["hotel"]["2015"]["base"]
        h22 = DIRECT_WATER["hotel"]["2022"]["base"]
        ok(
            f"Hotel water efficiency: {h15} → {h22} L/room/night  "
            f"({100*(h22-h15)/h15:.1f}% change  2015→2022)",
            log,
        )

        log.ok(f"Done in {t.elapsed()}")


if __name__ == "__main__":
    run()