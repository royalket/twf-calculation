# India Tourism Water Footprint — Reference Data

> **This file is the single source of truth for all empirical data.**
>
> It is read at runtime by `config.py` via `load_reference_data()` in `utils.py`.
> Pipeline scripts get everything through `config` — they never read this file directly.
>
> ### How to edit data
> Find the relevant section below and change the table values. Nothing else.
>
> ### How to add a new dataset
> 1. Add a new `## SECTION: YOUR_ID` block anywhere in this file.
> 2. Write a `<!-- meta ... -->` block documenting source, unit, notes.
> 3. Write a Markdown table (header + separator + data rows).
> 4. Register the new key in `config.py` with a one-line `_build_*()` loader.
>    No changes to `utils.py` are ever needed.
>
> ### How to add a new study year (e.g. 2025)
> 1. Add a `2024-25` column to the `NAS_GVA_CONSTANT` table.
> 2. Add a row `2025 | 2024-25` to the `STUDY_TO_FISCAL` table.
> 3. Add a `2025` column to `ACTIVITY_DATA`, `HOTEL_WATER_COEFFICIENTS`,
>    and `RESTAURANT_WATER_COEFFICIENTS`.
> 4. Add `2025 | <rate>` rows to `CPI` and `EUR_INR`.
> 5. Add `"2025"` to `STUDY_YEARS` in `config.py` and update `YEARS`.
> 6. Re-run the pipeline. Growth rates are computed automatically.
>
> ### Table rules
> - First column is the row key.
> - Column headers must be unique within a table.
> - Numeric cells: plain numbers only — no ₹, no commas, no %.
> - Notes go in the `<!-- meta -->` block, not in table cells.

---

## SECTION: NAS_GVA_CONSTANT

<!-- meta
id: NAS_GVA_CONSTANT
description: GVA by economic activity, constant 2011-12 prices
source: MoSPI National Accounts Statistics 2024, Statement 6.1
table_ref: Statement 6.1 — Gross Value Added at Basic Prices by Economic Activity
edition: NAS 2024 (file: modified6_1.csv supplied by researcher)
unit: crore INR, 2011-12 constant prices
base_year: 2015-16
csv_positions: 2015-16 col 7 | 2019-20 col 9 | 2021-22 col 10
-->

| sector_key     | nas_sno | nas_label                                                    | 2015-16  | 2019-20  | 2021-22  | notes                                                                                                                                                                     |
|----------------|---------|--------------------------------------------------------------|----------|----------|----------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Hotels         | 6.2     | Hotels & restaurants                                         | 111305   | 153261   | 96968    | TSA: Accommodation services/hotels. NAS 6.2 covers hotels AND restaurants jointly; Hotels key used for accommodation scaling only.                                       |
| Trade          | 6.1     | Trade & repair services                                      | 1150121  | 1675607  | 1517811  | TSA: Food and beverage serving services/restaurants. Trade (6.1) better captures food-service growth; correctly shows COVID divergence between hotel occupancy and delivery. |
| Railway        | 7.1     | Railways                                                     | 85452    | 82303    | 79828    | TSA: Railway passenger transport services. Real GVA declined 2015-2022; known anomaly in NAS railway deflation.                                                           |
| Road           | 7.2     | Road transport                                               | 343155   | 432160   | 426710   | TSA: Road passenger transport services.                                                                                                                                   |
| Water_Trans    | 7.3     | Water transport                                              | 8095     | 13016    | 13053    | TSA: Water passenger transport services. Real GVA ~doubled 2015-2022 reflecting coastal shipping expansion.                                                               |
| Air            | 7.4     | Air transport                                                | 6053     | 9158     | 5443     | TSA: Air passenger transport. 2021-22 below 2015-16 baseline; correctly captures COVID-19 aviation collapse.                                                              |
| Transport_Svcs | 7.5     | Services incidental to transport                             | 81156    | 91356    | 84531    | TSA: Transport equipment rental; Travel agencies and reservation services. Best proxy for travel agency activity.                                                         |
| Food_Mfg       | 3.1     | Food Products, Beverages and Tobacco                         | 183150   | 217690   | 208077   | TSA: Processed Food; Alcohol and tobacco; Imputed expenditures on food.                                                                                                   |
| Textiles       | 3.2     | Textiles, Apparel and Leather Products                       | 258936   | 290913   | 312949   | TSA: Readymade garments; Footwear.                                                                                                                                        |
| Other_Mfg      | 3.5     | Other Manufactured Goods                                     | 806908   | 886120   | 1031289  | TSA: Travel related consumer goods; Soaps, cosmetics; Gems and jewellery; Books, stationery.                                                                              |
| Real_Estate    | 9       | Real estate, ownership of dwelling & professional services   | 1621999  | 2113708  | 2291542  | TSA: Cultural; Sports; Health; Vacation homes; Social transfers; Producers guest houses.                                                                                  |
| Finance        | 8       | Financial services                                           | 672788   | 784536   | 831305   | TSA: FISIM.                                                                                                                                                               |

---

## SECTION: STUDY_TO_FISCAL

<!-- meta
id: STUDY_TO_FISCAL
description: Maps pipeline 4-digit study year to NAS fiscal year string
source: config.py YEARS mapping
unit: N/A
notes: Keep in sync with YEARS in config.py. study_year is the 4-digit key used throughout the pipeline; fiscal_year is the NAS column header used in NAS_GVA_CONSTANT.
-->

| study_year | fiscal_year |
|------------|-------------|
| 2019       | 2019-20     |
| 2022       | 2021-22     |

---

## SECTION: CPI

<!-- meta
id: CPI
description: Consumer Price Index, FY averages, base 2015-16
source: MoSPI
unit: index (base 2015-16 = 100)
base_year: 2015-16
notes: Used to convert nominal to real crore for intensity comparisons. Keyed by io_year string matching YEARS mapping in config.py.
-->

| io_year | cpi   |
|---------|-------|
| 2015-16 | 124.7 |
| 2019-20 | 146.3 |
| 2021-22 | 163.8 |

---

## SECTION: EUR_INR

<!-- meta
id: EUR_INR
description: EUR to INR annual average exchange rates
source: RBI / ECB annual averages
unit: INR per EUR
notes: Used when converting EXIOBASE water coefficients from m3/EUR million to m3/Rs crore. Keyed by 4-digit study year.
-->

| study_year | eur_inr |
|------------|---------|
| 2015       | 70.0    |
| 2019       | 78.8    |
| 2022       | 82.5    |

---

## SECTION: HOTEL_WATER_COEFFICIENTS

<!-- meta
id: HOTEL_WATER_COEFFICIENTS
description: Hotel water use per occupied room per night, by year and scenario
source: Cornell Hotel Sustainability Benchmarking (CHSB) India
unit: litres per occupied room per night
notes: 2015 base is CHSB 2015 India median (n=77 hotels). 2022 weighted avg: Budget 30%x497L + Mid 25%x720L + Upscale 25%x900L + Luxury 18%x1247L + Resort 2%x1100L = 818L approx. 2019 values linearly interpolated.
-->

| year | low | base | high |
|------|-----|------|------|
| 2015 | 953 | 1251 | 1797 |
| 2019 | 700 | 1000 | 1400 |
| 2022 | 497 | 818  | 1247 |

---

## SECTION: RESTAURANT_WATER_COEFFICIENTS

<!-- meta
id: RESTAURANT_WATER_COEFFICIENTS
description: Restaurant water use per meal served, by year and scenario
source: Lee et al. (2021) J. Hydrology 603:127151, adapted for India
unit: litres per meal served
notes: Small year-on-year increase in base coefficient reflects mild water efficiency degradation in informal restaurant sector.
-->

| year | low | base | high |
|------|-----|------|------|
| 2015 | 20  | 30   | 45   |
| 2019 | 20  | 31   | 45   |
| 2022 | 20  | 32   | 45   |

---

## SECTION: TRANSPORT_WATER_COEFFICIENTS

<!-- meta
id: TRANSPORT_WATER_COEFFICIENTS
description: Water use for transport modes by scenario. Constant across study years.
source: Lee et al. (2021), DGCA operational data
unit: rail = litres per passenger-km | air = litres per passenger | water_transport = litres per passenger
notes: No year column because these coefficients do not vary by study year.
-->

| mode            | low | base | high |
|-----------------|-----|------|------|
| rail            | 2.6 | 3.5  | 4.4  |
| air             | 13  | 18   | 23   |
| water_transport | 15  | 20   | 28   |

---

## SECTION: ACTIVITY_DATA

<!-- meta
id: ACTIVITY_DATA
description: Tourism activity volumes by year for direct water footprint calculation
source: India Tourism Statistics 2022/2016; TSA Table 10.7; DGCA Annual Reports; MoT Hotel Survey
unit: classified_rooms=count | occupancy_rate=fraction | nights_per_year=days | tourists=million | rail_pkm_B=billion pkm | air_pax_M=million passengers | shares=fraction | avg_stay_days=nights
notes: 2022 classified_rooms from FHRAI 2022 estimate. 2022 occupancy_rate reflects post-COVID recovery (MoT 2022). 2022 domestic_tourists_M reduced post-COVID.
       IMPORTANT: Verify that domestic_tourists_M definitions are comparable across years before
       computing per-tourist intensity trends. MoT changed survey methodology between rounds.
       avg_stay_days_dom and avg_stay_days_inb are now in a separate AVG_STAY_DAYS section
       (below) so they can be updated independently as better data becomes available.
-->

| field                 | 2015   | 2019   | 2022   |
|-----------------------|--------|--------|--------|
| classified_rooms      | 79879  | 99000  | 110000 |
| occupancy_rate        | 0.60   | 0.62   | 0.55   |
| nights_per_year       | 365    | 365    | 365    |
| domestic_tourists_M   | 1432.0 | 2321.0 | 1800.0 |
| inbound_tourists_M    | 8.03   | 10.93  | 6.44   |
| meals_per_tourist_day | 2.5    | 2.5    | 2.5    |
| rail_pkm_B            | 115.0  | 141.0  | 135.0  |
| air_pax_M             | 85.0   | 145.0  | 130.0  |
| tourist_rail_share    | 0.25   | 0.25   | 0.25   |
| tourist_air_share     | 0.60   | 0.60   | 0.60   |

---

## SECTION: AVG_STAY_DAYS

<!-- meta
id: AVG_STAY_DAYS
description: Average length of stay in days by tourist type and study year
source: PLACEHOLDER — update with actual MoT survey / India Tourism Statistics figures
unit: days per trip
notes: Separated from ACTIVITY_DATA so stay duration can be updated independently
       without touching other activity data. Currently set to 2.5 dom / 8.0 inb
       as a placeholder matching the hardcoded values used previously.
       These figures directly affect the tourist-days denominator in per-tourist
       intensity calculations. If MoT changed how day-trippers are counted between
       survey rounds, adjust dom values here rather than in tourist volume figures.
       Cross-check: if per-tourist intensity drops >30% between years despite
       similar total TWF, the denominator (stay × count) is the likely cause.
-->

| type     | 2015 | 2019 | 2022 |
|----------|------|------|------|
| domestic | 2.5  | 2.5  | 2.5  |
| inbound  | 8.0  | 8.0  | 8.0  |

---

## SECTION: WSI_WEIGHTS

<!-- meta
id: WSI_WEIGHTS
description: Water Stress Index (WSI) characterisation factors by SUT product group
source: PLACEHOLDER — update with Pfister et al. (2009) / AWARE method values
        for Indian river basins matched to SUT agricultural product origins.
        Recommended source: Aware for Humans characterisation factors at
        country/state level (www.wulca-waterlca.org).
unit: dimensionless (0–1 scale, higher = more water stressed)
notes: Used to compute WSI-weighted scarce water footprint:
         scarce_m3 = blue_m3 × WSI_weight
       This transforms volume-based TWF into scarcity-weighted TWF, making
       1 m3 extracted in Rajasthan (high WSI) count more than 1 m3 in Assam
       (low WSI). This is the key extension recommended by Lee et al. (2021)
       and the single largest contribution this study can make over existing
       India literature.

       The product_group column maps to SUT Product_ID ranges:
         Agriculture  → IDs 1–29
         Mining       → IDs 30–40
         Manufacturing→ IDs 41–113  (excl. Electricity)
         Electricity  → ID 114
         Petroleum    → IDs 71–80
         Services     → IDs 115–140

       PLACEHOLDER VALUES BELOW — all set to 0.47 (India national average WSI
       from Pfister et al. 2009). Replace with basin-specific values once you
       obtain the AWARE characterisation factors for Indian agricultural regions.
       Agriculture WSI should be highest (~0.6–0.8 for NW India irrigated crops).
       Services WSI is typically set to 0 or national average (water use not
       geographically specific in production accounts).
-->

| product_group   | wsi_weight | notes                                                              |
|-----------------|------------|--------------------------------------------------------------------|
| Agriculture     | 0.47       | PLACEHOLDER: India national avg. Update with crop/basin specific.  |
| Mining          | 0.47       | PLACEHOLDER: India national avg.                                   |
| Manufacturing   | 0.47       | PLACEHOLDER: India national avg.                                   |
| Electricity     | 0.47       | PLACEHOLDER: India national avg. Thermal cooling water intensive.  |
| Petroleum       | 0.47       | PLACEHOLDER: India national avg.                                   |
| Services        | 0.00       | Services excluded — water use not in production accounts.          |

---

*End of reference data. Add new sections above this line following the template at the top.*