# India Tourism Water Footprint — Reference Data

> **Single source of truth for all empirical data.**
>
> Read at runtime by `config.py` via `load_reference_data()` in `utils.py`.
> Pipeline scripts get everything through `config` — never read this file directly.
>
> ### How to edit data
> Find the relevant section and change table values. Nothing else.
>
> ### How to add a new study year (e.g. 2025)
> 1. Add `2025 | 2024-25` to `STUDY_TO_FISCAL`.
> 2. Add `2024-25` column to `NAS_GVA_CONSTANT`.
> 3. Add `2025` column to `ACTIVITY_DATA` (includes avg_stay_days rows).
> 4. Add `2025` row to `CPI`, `EUR_INR`.
> 5. Add `2025` rows to `HOTEL_WATER_COEFFICIENTS`, `RESTAURANT_WATER_COEFFICIENTS`.
> 6. Add `"2025"` to `STUDY_YEARS` in `config.py`.
> 7. Re-run pipeline. Growth rates computed automatically.
>
> ### How to add a new section
> 1. Add `## SECTION: YOUR_ID` block.
> 2. Write a `<!-- meta ... -->` block with source, unit, notes.
> 3. Write a Markdown table (header + separator + data rows).
> 4. Register a loader in `config.py` using `_rows()`, `_keyed()`, or `_scenario_rows()`.
>
> ### Table rules
> - First column is the row key.
> - Column headers must be unique within a table.
> - Numeric cells: plain numbers only — no ₹, no commas, no %.
> - Notes go in `<!-- meta -->` blocks, not table cells.

---

## SECTION: NAS_GVA_CONSTANT

<!-- meta
id: NAS_GVA_CONSTANT
description: GVA by economic activity, constant 2011-12 prices
source: MoSPI National Accounts Statistics 2024, Statement 6.1
unit: crore INR, 2011-12 constant prices
base_year: 2015-16
-->

| sector_key     | nas_sno | nas_label                                                  | 2015-16  | 2019-20  | 2021-22  | notes                                                                                                                                                                     |
|----------------|---------|------------------------------------------------------------|----------|----------|----------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Hotels         | 6.2     | Hotels & restaurants                                       | 111305   | 153261   | 96968    | TSA: Accommodation services/hotels. NAS 6.2 covers hotels AND restaurants jointly; Hotels key used for accommodation scaling only.                                       |
| Trade          | 6.1     | Trade & repair services                                    | 1150121  | 1675607  | 1517811  | TSA: Food and beverage serving services/restaurants. Trade (6.1) better captures food-service growth; correctly shows COVID divergence between hotel occupancy and delivery. |
| Railway        | 7.1     | Railways                                                   | 85452    | 82303    | 79828    | TSA: Railway passenger transport services. Real GVA declined 2015-2022; known anomaly in NAS railway deflation.                                                           |
| Road           | 7.2     | Road transport                                             | 343155   | 432160   | 426710   | TSA: Road passenger transport services.                                                                                                                                   |
| Water_Trans    | 7.3     | Water transport                                            | 8095     | 13016    | 13053    | TSA: Water passenger transport services.                                                                                                                                  |
| Air            | 7.4     | Air transport                                              | 6053     | 9158     | 5443     | TSA: Air passenger transport. 2021-22 below 2015-16 baseline; COVID-19 aviation collapse.                                                                                 |
| Transport_Svcs | 7.5     | Services incidental to transport                           | 81156    | 91356    | 84531    | TSA: Transport equipment rental; Travel agencies and reservation services.                                                                                                |
| Food_Mfg       | 3.1     | Food Products, Beverages and Tobacco                       | 183150   | 217690   | 208077   | TSA: Processed Food; Alcohol and tobacco; Imputed expenditures on food.                                                                                                   |
| Textiles       | 3.2     | Textiles, Apparel and Leather Products                     | 258936   | 290913   | 312949   | TSA: Readymade garments; Footwear.                                                                                                                                        |
| Other_Mfg      | 3.5     | Other Manufactured Goods                                   | 806908   | 886120   | 1031289  | TSA: Travel related consumer goods; Soaps, cosmetics; Gems and jewellery; Books, stationery.                                                                              |
| Real_Estate    | 9       | Real estate, ownership of dwelling & professional services | 1621999  | 2113708  | 2291542  | TSA: Cultural; Sports; Health; Vacation homes; Social transfers; Producers guest houses.                                                                                  |
| Finance        | 8       | Financial services                                         | 672788   | 784536   | 831305   | TSA: FISIM.                                                                                                                                                               |

---

## SECTION: STUDY_TO_FISCAL

<!-- meta
id: STUDY_TO_FISCAL
description: Maps 4-digit study year to NAS fiscal year string
source: config.py YEARS mapping
unit: N/A
notes: Keep in sync with YEARS in config.py. study_year is the 4-digit pipeline key; fiscal_year is the NAS column header in NAS_GVA_CONSTANT.
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
| 2015       | 71.0    |
| 2019       | 79.0    |
| 2022       | 88.5    |

---

## SECTION: ACTIVITY_DATA

<!-- meta
id: ACTIVITY_DATA
description: Tourism activity volumes and stay duration by year for direct water footprint calculation.
  Includes avg_stay_days_dom and avg_stay_days_inb (formerly a separate AVG_STAY_DAYS section).
source: India Tourism Statistics 2022/2016; TSA Table 10.7; DGCA Annual Reports; MoT Hotel Survey
unit: classified_rooms=count | occupancy_rate=fraction | nights_per_year=days | tourists=million |
      rail_pkm_B=billion pkm | air_pax_M=million passengers | shares=fraction |
      avg_stay_days=nights per trip
notes: 2022 classified_rooms from FHRAI 2022 estimate. 2022 occupancy_rate reflects post-COVID recovery.
       IMPORTANT: Verify domestic_tourists_M definitions are comparable across years before computing
       per-tourist intensity trends. MoT changed survey methodology between rounds.
       avg_stay_days_dom and avg_stay_days_inb are PLACEHOLDER values (2.5 dom / 8.0 inb).
       Update with actual MoT survey figures. These directly affect the tourist-days denominator.
-->

| field                 | 2015   | 2019   | 2022   |
|-----------------------|--------|--------|--------|
| classified_rooms      | 113622  | 140111  | 152945 |
| occupancy_rate        | 0.63   | 0.61   | 0.66   |
| nights_per_year       | 365    | 365    | 365    |
| domestic_tourists_M   | 1431.97 | 2321.0 | 1731.0 |
| inbound_tourists_M    | 8.03   | 10.93  | 8.58   |
| meals_per_tourist_day | 2.5    | 2.5    | 2.5    |
| rail_pkm_B            | 115.0  | 141.0  | 135.0  |
| air_pax_M             | 85.0   | 145.0  | 130.0  |
| tourist_rail_share    | 0.25   | 0.25   | 0.25   |
| tourist_air_share     | 0.60   | 0.60   | 0.60   |
| avg_stay_days_dom     | 3.5    | 4.2    | 5.0    |
| avg_stay_days_inb     | 21.0    | 22.0    | 20.5    |

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
unit: rail=litres per passenger-km | air=litres per passenger | water_transport=litres per passenger
notes: No year column because these coefficients do not vary by study year.
-->

| mode            | low | base | high |
|-----------------|-----|------|------|
| rail            | 2.6 | 3.5  | 4.4  |
| air             | 13  | 18   | 23   |
| water_transport | 15  | 20   | 28   |

---

## SECTION: WSI_WEIGHTS

<!-- meta
id: WSI_WEIGHTS
description: Water Stress Index (WSI) characterisation factors by SUT product group for India
source_paper: Pfister, S., Koehler, A., & Hellweg, S. (2009). Assessing the environmental
  impacts of freshwater consumption in LCA. Environmental Science & Technology, 43(11),
  4098–4104. DOI: 10.1021/es802423e
  Full paper URL: https://pubs.acs.org/doi/10.1021/es802423e
  PubMed: https://pubmed.ncbi.nlm.nih.gov/19569336/

source_data: The country-level WSI values were published by the authors as a Google Earth
  layer: www.ifu.ethz.ch/ESD/downloads/WSI_HHEQ.kmz (ETH Zurich, Institute of Environmental
  Engineering). This URL may no longer be active — if unavailable, request from:
  pfister@ifu.baug.ethz.ch (corresponding author) or use the AWARE replacement below.

modern_replacement: Boulay, A.-M. et al. (2018). The WULCA consensus characterization model
  for water scarcity footprints. Int J Life Cycle Assess 23, 2393–2411.
  DOI: 10.1007/s11367-017-1333-8
  Data download: https://wulca-waterlca.org/aware/download-aware-factors/

IMPORTANT — DATA STATUS OF VALUES BELOW:
  The WSI values listed in this table are DERIVED ESTIMATES, not directly read from
  Pfister et al. (2009) Table S2. They are based on:
  (a) The logistic function WSI = 1/(1+e^(-6.4*(WTA*-0.4))) applied to India's national
      WTA* (water withdrawal-to-availability ratio)
  (b) The widely-cited "India national average WSI ≈ 0.47" used in many LCA papers
      citing Pfister 2009 for India
  (c) Sector-specific adjustments based on the nature of water use (direct extraction
      vs grid/treated supply)

  ACTION REQUIRED: Download the actual SI data from the paper URL above and replace
  the derived estimates with the exact Pfister 2009 country values. The 0.47 national
  average appears confirmed by the literature for India overall; sectoral disaggregation
  (0.67 for agriculture, 0.57 for electricity) is a reasonable derivation but should
  be verified against watershed-level AWARE data for India.

unit: dimensionless (0.01–1.00 scale; 1 = maximum water stress / deprivation potential)
notes: WSI is used to compute stress-weighted scarce water footprint: scarce_m3 = blue_m3 × WSI.
  Agriculture typically dominates India TWF (60–80% upstream pull). Using 0.67 vs 0.47
  increases scarce-water footprint ~43% for agriculture-dominated sectors.
  Services set to 0.00 because services don't extract directly from aquifers — their
  water use is captured upstream in the Leontief multiplier chain.
-->

| product_group | wsi_weight | status        | basis                                                                    |
|---------------|------------|---------------|--------------------------------------------------------------------------|
| Agriculture   | 0.67       | DERIVED       | Logistic fn on India WTA*≈0.54; higher than national avg due to direct extraction |
| Mining        | 0.67       | DERIVED       | Same as agriculture — mining draws from same stressed aquifer systems    |
| Manufacturing | 0.47       | LITERATURE    | India national average from Pfister 2009 as cited in multiple LCA studies |
| Electricity   | 0.57       | DERIVED       | Intermediate — thermal cooling is water-intensive; India mix ~60% coal   |
| Petroleum     | 0.47       | LITERATURE    | National average applied — refineries draw partly from treated supply    |
| Services      | 0.00       | CONFIRMED     | Services don't extract from aquifers; stress mediated through input sectors |

---

## SECTION: TSA_BASE

<!-- meta
id: TSA_BASE
description: Tourism Satellite Account 2015-16 base expenditure by category
source: Tourism Satellite Account India 2015-16, Ministry of Tourism
unit: crore INR, 2015-16 nominal prices
notes: Category types: Characteristic = products specific to tourism; Connected = products tourists
       buy that are also sold to non-tourists; Imputed = non-market services.
       This is structural model metadata defining the 24 TSA categories and base-year expenditures.
       Update when a new TSA edition is published for India.
-->

| id | category                                              | category_type  | inbound_crore | domestic_crore |
|----|-------------------------------------------------------|----------------|---------------|----------------|
| 1  | Accommodation services/hotels                         | Characteristic | 41373         | 5610           |
| 2  | Food and beverage serving services/restaurants        | Characteristic | 73470         | 88588          |
| 3  | Railway passenger transport services                  | Characteristic | 2032          | 19096          |
| 4  | Road passenger transport services                     | Characteristic | 18699         | 183807         |
| 5  | Water passenger transport services                    | Characteristic | 614           | 924            |
| 6  | Air passenger transport services                      | Characteristic | 14172         | 57962          |
| 7  | Transport equipment rental services                   | Characteristic | 330           | 634            |
| 8  | Travel agencies and other reservation services        | Characteristic | 4073          | 5345           |
| 9  | Cultural and religious services                       | Characteristic | 974           | 52             |
| 10 | Sports and other recreational services                | Characteristic | 6690          | 209            |
| 11 | Health and medical related services                   | Characteristic | 11514         | 79130          |
| 12 | Readymade garments                                    | Connected      | 20364         | 51003          |
| 13 | Processed Food                                        | Connected      | 2851          | 11597          |
| 14 | Alcohol and tobacco products                          | Connected      | 4254          | 3489           |
| 15 | Travel related consumer goods                         | Connected      | 14918         | 26646          |
| 16 | Footwear                                              | Connected      | 2809          | 7908           |
| 17 | Soaps, cosmetics and glycerine                        | Connected      | 638           | 935            |
| 18 | Gems and jewellery                                    | Connected      | 13985         | 8807           |
| 19 | Books, journals, magazines, stationery                | Connected      | 1571          | 1452           |
| 20 | Vacation homes                                        | Imputed        | 0             | 4248           |
| 21 | Social transfers in kind                              | Imputed        | 0             | 4177           |
| 22 | FISIM                                                 | Imputed        | 0             | 42924          |
| 23 | Producers guest houses                                | Imputed        | 0             | 64716          |
| 24 | Imputed expenditures on food                          | Imputed        | 0             | 25215          |

---

## SECTION: TSA_TO_NAS

<!-- meta
id: TSA_TO_NAS
description: Maps each TSA category to its NAS growth-rate proxy sector
source: Researcher judgement; see notes for rationale
unit: N/A
notes: Restaurants mapped to Trade (NAS 6.1) not Hotels (NAS 6.2) because NAS 6.2 tracks
       hotel occupancy; restaurants during COVID pivoted to delivery, tracking more closely
       with trade/retail dynamics. Using Trade avoids conflating accommodation contraction
       with food service activity.
-->

| category                                              | nas_sector     |
|-------------------------------------------------------|----------------|
| Accommodation services/hotels                         | Hotels         |
| Food and beverage serving services/restaurants        | Trade          |
| Railway passenger transport services                  | Railway        |
| Road passenger transport services                     | Road           |
| Water passenger transport services                    | Water_Trans    |
| Air passenger transport services                      | Air            |
| Transport equipment rental services                   | Transport_Svcs |
| Travel agencies and other reservation services        | Transport_Svcs |
| Cultural and religious services                       | Real_Estate    |
| Sports and other recreational services                | Real_Estate    |
| Health and medical related services                   | Real_Estate    |
| Readymade garments                                    | Textiles       |
| Processed Food                                        | Food_Mfg       |
| Alcohol and tobacco products                          | Food_Mfg       |
| Travel related consumer goods                         | Other_Mfg      |
| Footwear                                              | Textiles       |
| Soaps, cosmetics and glycerine                        | Other_Mfg      |
| Gems and jewellery                                    | Other_Mfg      |
| Books, journals, magazines, stationery                | Other_Mfg      |
| Vacation homes                                        | Real_Estate    |
| Social transfers in kind                              | Real_Estate    |
| FISIM                                                 | Finance        |
| Producers guest houses                                | Real_Estate    |
| Imputed expenditures on food                          | Food_Mfg       |

---

## SECTION: TSA_TO_EXIOBASE

<!-- meta
id: TSA_TO_EXIOBASE
description: Maps each TSA category to EXIOBASE India sector codes with allocation shares
source: EXIOBASE v3 India sector classification; researcher allocation
unit: share = fraction (shares per category sum to 1.0)
notes: EXIOBASE India codes: IN (sector 0) through IN.162 (163 sectors total).
       Shares for "Travel related consumer goods": IN.91=Chemicals (toiletries) 0.45,
       IN.48=Leather (luggage) 0.20, IN.46=Textiles (accessories) 0.15,
       IN.53=Printed matter 0.10, IN.52=Paper 0.05, IN.103=Electronics 0.05.
       Unmapped categories fall back to IN.136 (Other Services).
-->

| category                                              | exio_code | share |
|-------------------------------------------------------|-----------|-------|
| Accommodation services/hotels                         | IN.113    | 1.00  |
| Food and beverage serving services/restaurants        | IN.113    | 0.50  |
| Food and beverage serving services/restaurants        | IN.42     | 0.30  |
| Food and beverage serving services/restaurants        | IN.43     | 0.20  |
| Railway passenger transport services                  | IN.114    | 1.00  |
| Road passenger transport services                     | IN.115    | 1.00  |
| Water passenger transport services                    | IN.117    | 0.70  |
| Water passenger transport services                    | IN.118    | 0.30  |
| Air passenger transport services                      | IN.119    | 1.00  |
| Transport equipment rental services                   | IN.126    | 1.00  |
| Travel agencies and other reservation services        | IN.120    | 1.00  |
| Cultural and religious services                       | IN.135    | 1.00  |
| Sports and other recreational services                | IN.135    | 1.00  |
| Health and medical related services                   | IN.132    | 1.00  |
| Readymade garments                                    | IN.47     | 1.00  |
| Processed Food                                        | IN.42     | 0.70  |
| Processed Food                                        | IN.40     | 0.30  |
| Alcohol and tobacco products                          | IN.43     | 0.60  |
| Alcohol and tobacco products                          | IN.45     | 0.40  |
| Travel related consumer goods                         | IN.91     | 0.45  |
| Travel related consumer goods                         | IN.48     | 0.20  |
| Travel related consumer goods                         | IN.46     | 0.15  |
| Travel related consumer goods                         | IN.53     | 0.10  |
| Travel related consumer goods                         | IN.52     | 0.05  |
| Travel related consumer goods                         | IN.103    | 0.05  |
| Footwear                                              | IN.48     | 1.00  |
| Soaps, cosmetics and glycerine                        | IN.91     | 1.00  |
| Gems and jewellery                                    | IN.91     | 1.00  |
| Books, journals, magazines, stationery                | IN.53     | 0.60  |
| Books, journals, magazines, stationery                | IN.52     | 0.40  |
| Vacation homes                                        | IN.125    | 1.00  |
| Social transfers in kind                              | IN.130    | 1.00  |
| FISIM                                                 | IN.122    | 1.00  |
| Producers guest houses                                | IN.125    | 0.50  |
| Producers guest houses                                | IN.136    | 0.50  |
| Imputed expenditures on food                          | IN.42     | 1.00  |

---

*End of reference data. Add new sections above this line following the template at the top.*