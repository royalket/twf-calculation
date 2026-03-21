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
> 3. Add `2025` column to `ACTIVITY_DATA`.
> 4. Add `2025` rows to `CPI`, `EUR_INR`, `USD_INR`, `UNIT_RENTS`, `NAS_MACRO`.
> 5. Add `2025` rows to `HOTEL_WATER_COEFFICIENTS`, `RESTAURANT_WATER_COEFFICIENTS`.
> 6. Add `"2025"` to `STUDY_YEARS` in `config.py`.
> 7. Re-run pipeline.
>
> ### How to add a new stressor (e.g. emissions)
> 1. Add coefficient config to `STRESSOR_CFG` in `build_coefficients.py`.
> 2. Add `_CFG` entry in `indirect.py`.
> 3. Add `POST_CFG` entry in `postprocess.py`.
> 4. Add `SDA_CFG` + `MC_CFG` entries in `decompose.py`.
> 5. Add `REPORT_CFG` entry in `compare.py` + write `fill_emissions_extras()`.
> 6. Add `## TEMPLATE: emissions` section to `report_template.md`.
> 7. No new files needed.
>
> ### Table rules
> - First column is the row key.
> - Numeric cells: plain numbers only — no ₹, no commas, no %.
> - `reference` column is visible citation in rendered Markdown.

---

## SECTION: NAS_GVA_CONSTANT

<!-- meta
id: NAS_GVA_CONSTANT
description: GVA by economic activity, constant 2011-12 prices
source: MoSPI National Accounts Statistics 2024, Statement 6.1
unit: crore INR, 2011-12 constant prices
base_year: 2015-16
-->

| sector_key     | nas_sno | nas_label                                                  | 2015-16  | 2019-20  | 2021-22  | notes                                                                                                                                                                      | reference                      |
|----------------|---------|------------------------------------------------------------|----------|----------|----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------|
| Hotels         | 6.2     | Hotels & restaurants                                       | 111305   | 153261   | 96968    | TSA: Accommodation services/hotels. NAS 6.2 covers hotels AND restaurants jointly.                                                                                        | MoSPI NAS 2024, Statement 6.1  |
| Trade          | 6.1     | Trade & repair services                                    | 1150121  | 1675607  | 1517811  | TSA: Food and beverage serving services/restaurants. Trade (6.1) captures COVID delivery dynamics better than 6.2.                                                         | MoSPI NAS 2024, Statement 6.1  |
| Railway        | 7.1     | Railways                                                   | 85452    | 82303    | 79828    | TSA: Railway passenger transport services. Real GVA declined 2015–2022; known NAS railway deflation anomaly.                                                               | MoSPI NAS 2024, Statement 6.1  |
| Road           | 7.2     | Road transport                                             | 343155   | 432160   | 426710   | TSA: Road passenger transport services.                                                                                                                                    | MoSPI NAS 2024, Statement 6.1  |
| Water_Trans    | 7.3     | Water transport                                            | 8095     | 13016    | 13053    | TSA: Water passenger transport services.                                                                                                                                   | MoSPI NAS 2024, Statement 6.1  |
| Air            | 7.4     | Air transport                                              | 6053     | 9158     | 5443     | TSA: Air passenger transport. 2021-22 below 2015-16 baseline; COVID-19 aviation collapse.                                                                                  | MoSPI NAS 2024, Statement 6.1  |
| Transport_Svcs | 7.5     | Services incidental to transport                           | 81156    | 91356    | 84531    | TSA: Transport equipment rental; Travel agencies and reservation services.                                                                                                 | MoSPI NAS 2024, Statement 6.1  |
| Food_Mfg       | 3.1     | Food Products, Beverages and Tobacco                       | 183150   | 217690   | 208077   | TSA: Processed Food; Alcohol and tobacco; Imputed expenditures on food.                                                                                                    | MoSPI NAS 2024, Statement 6.1  |
| Textiles       | 3.2     | Textiles, Apparel and Leather Products                     | 258936   | 290913   | 312949   | TSA: Readymade garments; Footwear.                                                                                                                                         | MoSPI NAS 2024, Statement 6.1  |
| Other_Mfg      | 3.5     | Other Manufactured Goods                                   | 806908   | 886120   | 1031289  | TSA: Travel related consumer goods; Soaps, cosmetics; Gems and jewellery; Books, stationery.                                                                               | MoSPI NAS 2024, Statement 6.1  |
| Real_Estate    | 9       | Real estate, ownership of dwelling & professional services | 1621999  | 2113708  | 2291542  | TSA: Cultural; Sports; Health; Vacation homes; Social transfers; Producers guest houses.                                                                                   | MoSPI NAS 2024, Statement 6.1  |
| Finance        | 8       | Financial services                                         | 672788   | 784536   | 831305   | TSA: FISIM.                                                                                                                                                                | MoSPI NAS 2024, Statement 6.1  |

---

## SECTION: STUDY_TO_FISCAL

<!-- meta
id: STUDY_TO_FISCAL
description: Maps 4-digit study year to NAS fiscal year string
source: config.py YEARS mapping
unit: N/A
-->

| study_year | fiscal_year | reference               |
|------------|-------------|-------------------------|
| 2015       | 2015-16     | config.py YEARS mapping |
| 2019       | 2019-20     | config.py YEARS mapping |
| 2022       | 2021-22     | config.py YEARS mapping |

---

## SECTION: CPI

<!-- meta
id: CPI
description: Consumer Price Index, FY averages, base 2015-16
source: MoSPI
unit: index (base 2015-16 = 100)
-->

| io_year | cpi   | reference                            |
|---------|-------|--------------------------------------|
| 2015-16 | 124.7 | MoSPI CPI, FY average, base 2015-16  |
| 2019-20 | 146.3 | MoSPI CPI, FY average, base 2015-16  |
| 2021-22 | 163.8 | MoSPI CPI, FY average, base 2015-16  |

---

## SECTION: EUR_INR

<!-- meta
id: EUR_INR
description: EUR to INR annual average exchange rates
source: RBI / ECB annual averages
unit: INR per EUR
-->

| study_year | eur_inr | reference                    |
|------------|---------|------------------------------|
| 2015       | 71.0    | RBI / ECB annual average FY  |
| 2019       | 79.0    | RBI / ECB annual average FY  |
| 2022       | 88.5    | RBI / ECB annual average FY  |

---

## SECTION: ACTIVITY_DATA

<!-- meta
id: ACTIVITY_DATA
description: Tourism activity volumes and stay duration by year for direct water footprint calculation.
source: India Tourism Statistics 2022/2016; TSA Table 10.7; DGCA Annual Reports; MoT Hotel Survey;
        NSS Report 580 (MOSPI 2017) Tables 3.1 and 3.14 for dom_hotel_share and dom_rail_modal_share;
        MoR Annual Statistical Statement 2015-16, 2019-20, 2021-22 for avg_tourist_rail_km.
unit: tourists=million | shares=fraction | avg_stay_days=nights per trip | avg_tourist_rail_km=km
notes: avg_stay_days_dom and avg_stay_days_inb are PLACEHOLDER values. Update from MoT surveys.
       dom_hotel_share=0.15: DERIVED from NSS 580 Table 3.14 × Census 2011 weights (rural 65%×9% + urban 35%×25.8% ≈ 15%).
       dom_rail_modal_share=0.25: DERIVED from NSS 580 Table 3.6 × Census 2011 weights.
       avg_tourist_rail_km: MoR non-suburban average lead (published annually in MoR Statistical Statement Table 2).
-->

| field                 | 2015    | 2019   | 2022   | reference                                                                                      |
|-----------------------|---------|--------|--------|-----------------------------------------------------------------------------------------------|
| classified_rooms      | 113622  | 140111 | 152945 | FHRAI Survey 2015/2019/2022; MoT Hotel Survey                                                |
| occupancy_rate        | 0.63    | 0.61   | 0.66   | FHRAI Survey; 2022 reflects post-COVID recovery                                               |
| nights_per_year       | 365     | 365    | 365    | Standard calendar assumption                                                                  |
| domestic_tourists_M   | 1431.97 | 2321.0 | 1731.0 | India Tourism Statistics 2022/2016, MoT                                                      |
| inbound_tourists_M    | 8.03    | 10.93  | 8.58   | India Tourism Statistics 2022/2016, MoT                                                      |
| meals_per_tourist_day | 2.5     | 2.5    | 2.5    | MoT visitor expenditure survey; TSA Table 10.7                                               |
| air_pax_M             | 85.0    | 145.0  | 130.0  | DGCA Annual Report 2015-16 / 2019-20 / 2021-22                                               |
| dom_rail_modal_share  | 0.25    | 0.25   | 0.25   | NSS Report 580 (MOSPI 2017) Table 3.6; Census 2011 rural/urban weights (65%/35%)             |
| avg_tourist_rail_km   | 242     | 254    | 261    | Ministry of Railways Annual Statistical Statement, Table 2 (Average Lead, non-suburban)      |
| tourist_air_share     | 0.60    | 0.60   | 0.60   | DGCA operational data; researcher estimate                                                    |
| avg_stay_days_dom     | 3.5     | 4.2    | 5.0    | PLACEHOLDER — update from MoT domestic tourism survey                                        |
| avg_stay_days_inb     | 21.0    | 22.0   | 20.5   | PLACEHOLDER — update from MoT IPS; TSA 2015-16 Table 10.7                                   |
| dom_hotel_share       | 0.15    | 0.15   | 0.15   | DERIVED: NSS Report 580 Table 3.14 (MOSPI 2017) × Census 2011 weights; LOW=0.10 HIGH=0.20   |
| inb_hotel_share       | 1.00    | 1.00   | 1.00   | Structural assumption; MoT IPS; TSA 2015-16 Table 3 confirms near-100% commercial hotel use  |

---

## SECTION: HOTEL_WATER_COEFFICIENTS

<!-- meta
id: HOTEL_WATER_COEFFICIENTS
description: Hotel water use per occupied room per night, by year and scenario
source: Cornell Hotel Sustainability Benchmarking (CHSB) India
unit: litres per occupied room per night
notes: 2015 base = CHSB 2015 India median (n=77 hotels). 2022 weighted avg: Budget 30%×497L + Mid 25%×720L + Upscale 25%×900L + Luxury 18%×1247L + Resort 2%×1100L ≈ 818L. 2019 linearly interpolated.
-->

| year | low | base | high | reference                                                                                   |
|------|-----|------|------|---------------------------------------------------------------------------------------------|
| 2015 | 953 | 1251 | 1797 | Cornell CHSB India 2015, median (n=77 hotels); LOW/HIGH = interquartile range               |
| 2019 | 700 | 1000 | 1400 | Linearly interpolated between 2015 CHSB and 2022 weighted average                          |
| 2022 | 497 | 818  | 1247 | CHSB 2022 weighted avg: Budget 30%×497 + Mid 25%×720 + Upscale 25%×900 + Luxury 18%×1247  |

---

## SECTION: RESTAURANT_WATER_COEFFICIENTS

<!-- meta
id: RESTAURANT_WATER_COEFFICIENTS
description: Restaurant water use per meal served, by year and scenario
source: Lee et al. (2021) J. Hydrology 603:127151, adapted for India
unit: litres per meal served
notes: Base coefficient increases 30→32 L/meal (2015→2022) reflecting mild efficiency degradation in informal restaurant sector.
-->

| year | low | base | high | reference                                                                                   |
|------|-----|------|------|---------------------------------------------------------------------------------------------|
| 2015 | 20  | 30   | 45   | Lee et al. (2021) J. Hydrology 603:127151, adapted for India; LOW/HIGH = literature range   |
| 2019 | 20  | 31   | 45   | Lee et al. (2021), base +1 L reflecting informal sector efficiency degradation              |
| 2022 | 20  | 32   | 45   | Lee et al. (2021), base +2 L reflecting informal sector efficiency degradation              |

---

## SECTION: TRANSPORT_WATER_COEFFICIENTS

<!-- meta
id: TRANSPORT_WATER_COEFFICIENTS
description: Water use for transport modes by scenario. Constant across study years.
source: Lee et al. (2021) J. Hydrology 603:127151; DGCA operational data
unit: rail=litres per passenger-km | air=litres per passenger | water_transport=litres per passenger
notes: Rail L/pkm applies to tourist_pkm = dom_tourists × dom_rail_modal_share × avg_tourist_rail_km (demand-side formula).
       Previous supply-side formula (rail_pkm_B × tourist_rail_share) used an unverifiable 115B pkm figure — replaced.
-->

| mode            | low | base | high | reference                                                                                         |
|-----------------|-----|------|------|---------------------------------------------------------------------------------------------------|
| rail            | 2.6 | 3.5  | 4.4  | Lee et al. (2021) J. Hydrology 603:127151; demand-side formula via NSS 580 + MoR average lead    |
| air             | 13  | 18   | 23   | Lee et al. (2021) J. Hydrology 603:127151; DGCA operational data for Indian airports             |
| water_transport | 15  | 20   | 28   | Lee et al. (2021) J. Hydrology 603:127151                                                        |

---

## SECTION: WSI_WEIGHTS

<!-- meta
id: WSI_WEIGHTS
description: Water Stress Index characterisation factors by SUT product group for India.
  Used to compute stress-weighted scarce water footprint: scarce_m3 = blue_m3 * wsi_weight.
source: Kuzma et al. 2023. Aqueduct 4.0. WRI. DOI: 10.46830/writn.23.00061
unit: dimensionless (0.00-1.00; 1.0 = maximum water stress)
notes: Agriculture uses Irr demand weights; Industry sectors use Ind demand weights. Services=0 (no direct basin extraction).
-->

| product_group | wsi_weight | raw_score | weight_type | reference                                                                                          |
|---------------|------------|-----------|-------------|-----------------------------------------------------------------------------------------------------|
| Agriculture   | 0.827      | 4.137     | Irr         | Kuzma et al. 2023, WRI Aqueduct 4.0 (DOI:10.46830/writn.23.00061); IND bws, Irr demand weights   |
| Mining        | 0.814      | 4.069     | Ind         | Kuzma et al. 2023, WRI Aqueduct 4.0; IND bws, Ind demand weights                                 |
| Manufacturing | 0.814      | 4.069     | Ind         | Kuzma et al. 2023, WRI Aqueduct 4.0; IND bws, Ind demand weights                                 |
| Electricity   | 0.814      | 4.069     | Ind         | Kuzma et al. 2023, WRI Aqueduct 4.0; IND bws, Ind demand weights                                 |
| Petroleum     | 0.814      | 4.069     | Ind         | Kuzma et al. 2023, WRI Aqueduct 4.0; IND bws, Ind demand weights                                 |
| Services      | 0.000      | 0.000     | N/A         | Conceptual: service sectors do not directly extract from basins; zero assigned by design           |

---

## SECTION: OUTBOUND_TWF_DATA

<!-- meta
id: OUTBOUND_TWF_DATA
description: India outbound tourism data for net TWF balance calculation.
source_counts: India Tourism Statistics 2022, MoT. URL: https://tourism.gov.in/india-tourism-statistics
source_wf: Hoekstra & Mekonnen (2012). PNAS 109(9):3232-3237. DOI: 10.1073/pnas.1109936109
tourist_multiplier: 1.5 — Hadjikakou et al. (2015); Li (2018); Lee et al. (2021).
unit: share=fraction | local_wf_m3_yr=m3/capita/year
notes: DATA STATUS: PLACEHOLDER — verify destination shares before publication.
-->

| country      | dest_share | local_wf_m3_yr | wf_basis                    | wsi_dest | wsi_source          | reference                                                            |
|--------------|------------|----------------|-----------------------------|----------|---------------------|----------------------------------------------------------------------|
| UAE          | 0.28       | 3139           | 8600 L/day ÷ 1000 × 365     | 1.00     | WRI Aqueduct bws/5  | ITS 2022 Table 4.2.5; Hoekstra & Mekonnen 2012 PNAS SI Table S1     |
| Saudi Arabia | 0.11       | 1862           | 5100 L/day ÷ 1000 × 365     | 1.00     | WRI Aqueduct bws/5  | ITS 2022 Table 4.2.5; Hoekstra & Mekonnen 2012 PNAS SI Table S1     |
| USA          | 0.08       | 2847           | 7800 L/day ÷ 1000 × 365     | 0.52     | WRI Aqueduct bws/5  | ITS 2022 Table 4.2.5; Hoekstra & Mekonnen 2012 PNAS SI Table S1     |
| Singapore    | 0.05       | 2000           | no data — original estimate | 0.10     | Pfister et al. 2009 | ITS 2022 Table 4.2.5; WF estimated                                   |
| UK           | 0.04       | 1247           | 3418 L/day ÷ 1000 × 365     | 0.26     | WRI Aqueduct bws/5  | ITS 2022 Table 4.2.5; Hoekstra & Mekonnen 2012 PNAS SI Table S1     |
| Thailand     | 0.04       | 1424           | 3900 L/day ÷ 1000 × 365     | 0.72     | WRI Aqueduct bws/5  | ITS 2022 Table 4.2.5; Hoekstra & Mekonnen 2012 PNAS SI Table S1     |
| Qatar        | 0.04       | 1800           | no data — original estimate | 1.00     | WRI Aqueduct bws/5  | ITS 2022 Table 4.2.5; WF estimated                                   |
| Kuwait       | 0.04       | 2081           | 5700 L/day ÷ 1000 × 365     | 1.00     | WRI Aqueduct bws/5  | ITS 2022 Table 4.2.5; Hoekstra & Mekonnen 2012 PNAS SI Table S1     |
| Oman         | 0.03       | 2100           | no data — original estimate | 1.00     | WRI Aqueduct bws/5  | ITS 2022 Table 4.2.5; WF estimated                                   |
| Canada       | 0.04       | 2336           | 6400 L/day ÷ 1000 × 365     | 0.25     | WRI Aqueduct bws/5  | ITS 2022 Table 4.2.5; Hoekstra & Mekonnen 2012 PNAS SI Table S1     |
| Australia    | 0.02       | 2300           | 6300 L/day ÷ 1000 × 365     | 0.58     | WRI Aqueduct bws/5  | ITS 2022 Table 4.2.5; Hoekstra & Mekonnen 2012 PNAS SI Table S1     |
| Malaysia     | 0.01       | 2117           | 5800 L/day ÷ 1000 × 365     | 0.21     | WRI Aqueduct bws/5  | ITS 2022 Table 4.2.5; Hoekstra & Mekonnen 2012 PNAS SI Table S1     |
| Germany      | 0.01       | 1424           | 3900 L/day ÷ 1000 × 365     | 0.41     | WRI Aqueduct bws/5  | ITS 2022 Table 4.2.5; Hoekstra & Mekonnen 2012 PNAS SI Table S1     |
| Others       | 0.21       | 2000           | assumed                     | 0.20     | assumed             | Residual; WF = unweighted average of destination-specific estimates  |

---

## SECTION: OUTBOUND_TOURIST_COUNTS

<!-- meta
id: OUTBOUND_TOURIST_COUNTS
description: India outbound departures split into tourism-only (stays ≤4 weeks) and all-INDs.
source: TSA 2015-16 (NCAER/MoT); ITS 2019 & 2022, Bureau of Immigration GoI.
  Duration groups from ITS Table 4.8.2. ITS 2022 grand total avg = 99.69 days (verified).
unit: millions | days
-->

| study_year | all_INDs_M | tourism_M | avg_stay_tourism | avg_stay_all | reference                                                                              |
|------------|------------|-----------|------------------|--------------|----------------------------------------------------------------------------------------|
| 2015       | 20.52      | 8.68      | 9.4              | 70.6         | TSA 2015-16 (NCAER/MoT); duration estimated from 2019 proportions                     |
| 2019       | 26.92      | 11.38     | 9.4              | 70.6         | ITS 2019, Bureau of Immigration GoI; Table 4.8.2 (18,177,186 recorded departures)     |
| 2022       | 21.60      | 5.15      | 9.2              | 99.7         | ITS 2022, Bureau of Immigration GoI; Table 4.8.2 (15,755,842 recorded departures)     |

---

## SECTION: TSA_BASE

<!-- meta
id: TSA_BASE
description: Tourism Satellite Account 2015-16 base expenditure by category
source: Tourism Satellite Account India 2015-16, Ministry of Tourism
unit: crore INR, 2015-16 nominal prices
notes: Category types: Characteristic = products specific to tourism; Connected = products tourists buy that non-tourists also buy; Imputed = non-market services.
-->

| id | category                                              | category_type  | inbound_crore | domestic_crore | reference                                   |
|----|-------------------------------------------------------|----------------|---------------|----------------|---------------------------------------------|
| 1  | Accommodation services/hotels                         | Characteristic | 41373         | 5610           | TSA India 2015-16, Ministry of Tourism, GoI |
| 2  | Food and beverage serving services/restaurants        | Characteristic | 73470         | 88588          | TSA India 2015-16, Ministry of Tourism, GoI |
| 3  | Railway passenger transport services                  | Characteristic | 2032          | 19096          | TSA India 2015-16, Ministry of Tourism, GoI |
| 4  | Road passenger transport services                     | Characteristic | 18699         | 183807         | TSA India 2015-16, Ministry of Tourism, GoI |
| 5  | Water passenger transport services                    | Characteristic | 614           | 924            | TSA India 2015-16, Ministry of Tourism, GoI |
| 6  | Air passenger transport services                      | Characteristic | 14172         | 57962          | TSA India 2015-16, Ministry of Tourism, GoI |
| 7  | Transport equipment rental services                   | Characteristic | 330           | 634            | TSA India 2015-16, Ministry of Tourism, GoI |
| 8  | Travel agencies and other reservation services        | Characteristic | 4073          | 5345           | TSA India 2015-16, Ministry of Tourism, GoI |
| 9  | Cultural and religious services                       | Characteristic | 974           | 52             | TSA India 2015-16, Ministry of Tourism, GoI |
| 10 | Sports and other recreational services                | Characteristic | 6690          | 209            | TSA India 2015-16, Ministry of Tourism, GoI |
| 11 | Health and medical related services                   | Characteristic | 11514         | 79130          | TSA India 2015-16, Ministry of Tourism, GoI |
| 12 | Readymade garments                                    | Connected      | 20364         | 51003          | TSA India 2015-16, Ministry of Tourism, GoI |
| 13 | Processed Food                                        | Connected      | 2851          | 11597          | TSA India 2015-16, Ministry of Tourism, GoI |
| 14 | Alcohol and tobacco products                          | Connected      | 4254          | 3489           | TSA India 2015-16, Ministry of Tourism, GoI |
| 15 | Travel related consumer goods                         | Connected      | 14918         | 26646          | TSA India 2015-16, Ministry of Tourism, GoI |
| 16 | Footwear                                              | Connected      | 2809          | 7908           | TSA India 2015-16, Ministry of Tourism, GoI |
| 17 | Soaps, cosmetics and glycerine                        | Connected      | 638           | 935            | TSA India 2015-16, Ministry of Tourism, GoI |
| 18 | Gems and jewellery                                    | Connected      | 13985         | 8807           | TSA India 2015-16, Ministry of Tourism, GoI |
| 19 | Books, journals, magazines, stationery                | Connected      | 1571          | 1452           | TSA India 2015-16, Ministry of Tourism, GoI |
| 20 | Vacation homes                                        | Imputed        | 0             | 4248           | TSA India 2015-16, Ministry of Tourism, GoI |
| 21 | Social transfers in kind                              | Imputed        | 0             | 4177           | TSA India 2015-16, Ministry of Tourism, GoI |
| 22 | FISIM                                                 | Imputed        | 0             | 42924          | TSA India 2015-16, Ministry of Tourism, GoI |
| 23 | Producers guest houses                                | Imputed        | 0             | 64716          | TSA India 2015-16, Ministry of Tourism, GoI |
| 24 | Imputed expenditures on food                          | Imputed        | 0             | 25215          | TSA India 2015-16, Ministry of Tourism, GoI |

---

## SECTION: TSA_TO_NAS

<!-- meta
id: TSA_TO_NAS
description: Maps each TSA category to its NAS growth-rate proxy sector
source: Researcher judgement
notes: Restaurants → Trade (NAS 6.1) not Hotels (NAS 6.2): 6.2 tracks hotel occupancy; restaurants during COVID pivoted to delivery tracking better with trade/retail dynamics.
-->

| category                                              | nas_sector     | reference                                        |
|-------------------------------------------------------|----------------|--------------------------------------------------|
| Accommodation services/hotels                         | Hotels         | NAS 6.2 (Hotels & restaurants)                  |
| Food and beverage serving services/restaurants        | Trade          | NAS 6.1 (Trade & repair); COVID delivery dynamics |
| Railway passenger transport services                  | Railway        | NAS 7.1 (Railways)                               |
| Road passenger transport services                     | Road           | NAS 7.2 (Road transport)                         |
| Water passenger transport services                    | Water_Trans    | NAS 7.3 (Water transport)                        |
| Air passenger transport services                      | Air            | NAS 7.4 (Air transport)                          |
| Transport equipment rental services                   | Transport_Svcs | NAS 7.5 (Services incidental to transport)       |
| Travel agencies and other reservation services        | Transport_Svcs | NAS 7.5 (Services incidental to transport)       |
| Cultural and religious services                       | Real_Estate    | NAS 9 (Real estate & professional services)      |
| Sports and other recreational services                | Real_Estate    | NAS 9 (Real estate & professional services)      |
| Health and medical related services                   | Real_Estate    | NAS 9 (Real estate & professional services)      |
| Readymade garments                                    | Textiles       | NAS 3.2 (Textiles, Apparel and Leather)          |
| Processed Food                                        | Food_Mfg       | NAS 3.1 (Food Products, Beverages and Tobacco)   |
| Alcohol and tobacco products                          | Food_Mfg       | NAS 3.1 (Food Products, Beverages and Tobacco)   |
| Travel related consumer goods                         | Other_Mfg      | NAS 3.5 (Other Manufactured Goods)               |
| Footwear                                              | Textiles       | NAS 3.2 (Textiles, Apparel and Leather)          |
| Soaps, cosmetics and glycerine                        | Other_Mfg      | NAS 3.5 (Other Manufactured Goods)               |
| Gems and jewellery                                    | Other_Mfg      | NAS 3.5 (Other Manufactured Goods)               |
| Books, journals, magazines, stationery                | Other_Mfg      | NAS 3.5 (Other Manufactured Goods)               |
| Vacation homes                                        | Real_Estate    | NAS 9 (Real estate & professional services)      |
| Social transfers in kind                              | Real_Estate    | NAS 9 (Real estate & professional services)      |
| FISIM                                                 | Finance        | NAS 8 (Financial services)                       |
| Producers guest houses                                | Real_Estate    | NAS 9 (Real estate & professional services)      |
| Imputed expenditures on food                          | Food_Mfg       | NAS 3.1 (Food Products, Beverages and Tobacco)   |

---

## SECTION: TSA_TO_EXIOBASE

<!-- meta
id: TSA_TO_EXIOBASE
description: Maps each TSA category to EXIOBASE India sector codes with allocation shares
source: EXIOBASE v3 India sector classification; researcher allocation
unit: share = fraction (shares per category sum to 1.0)
notes: EXIOBASE India codes: IN (sector 0) through IN.162 (163 sectors total). Unmapped categories fall back to IN.136 (Other Services).
-->

| category                                              | exio_code | share | reference                                              |
|-------------------------------------------------------|-----------|-------|--------------------------------------------------------|
| Accommodation services/hotels                         | IN.113    | 1.00  | EXIOBASE v3; researcher allocation                     |
| Food and beverage serving services/restaurants        | IN.113    | 0.50  | EXIOBASE v3 IN.113 (Hotels & restaurants)              |
| Food and beverage serving services/restaurants        | IN.42     | 0.30  | EXIOBASE v3 IN.42 (Food manufacturing)                 |
| Food and beverage serving services/restaurants        | IN.43     | 0.20  | EXIOBASE v3 IN.43 (Beverages)                          |
| Railway passenger transport services                  | IN.114    | 1.00  | EXIOBASE v3 IN.114 (Rail transport)                    |
| Road passenger transport services                     | IN.115    | 1.00  | EXIOBASE v3 IN.115 (Road transport)                    |
| Water passenger transport services                    | IN.117    | 0.70  | EXIOBASE v3 IN.117 (Inland waterways)                  |
| Water passenger transport services                    | IN.118    | 0.30  | EXIOBASE v3 IN.118 (Sea and coastal transport)         |
| Air passenger transport services                      | IN.119    | 1.00  | EXIOBASE v3 IN.119 (Air transport)                     |
| Transport equipment rental services                   | IN.126    | 1.00  | EXIOBASE v3 IN.126 (Rental and leasing)                |
| Travel agencies and other reservation services        | IN.120    | 1.00  | EXIOBASE v3 IN.120 (Travel agencies)                   |
| Cultural and religious services                       | IN.135    | 1.00  | EXIOBASE v3 IN.135 (Recreational services)             |
| Sports and other recreational services                | IN.135    | 1.00  | EXIOBASE v3 IN.135 (Recreational services)             |
| Health and medical related services                   | IN.132    | 1.00  | EXIOBASE v3 IN.132 (Health and social work)            |
| Readymade garments                                    | IN.47     | 1.00  | EXIOBASE v3 IN.47 (Wearing apparel)                    |
| Processed Food                                        | IN.42     | 0.70  | EXIOBASE v3 IN.42 (Food manufacturing)                 |
| Processed Food                                        | IN.40     | 0.30  | EXIOBASE v3 IN.40 (Agriculture residual)               |
| Alcohol and tobacco products                          | IN.43     | 0.60  | EXIOBASE v3 IN.43 (Beverages)                          |
| Alcohol and tobacco products                          | IN.45     | 0.40  | EXIOBASE v3 IN.45 (Tobacco products)                   |
| Travel related consumer goods                         | IN.91     | 0.45  | EXIOBASE v3 IN.91 (Chemicals — toiletries)             |
| Travel related consumer goods                         | IN.48     | 0.20  | EXIOBASE v3 IN.48 (Leather — luggage)                  |
| Travel related consumer goods                         | IN.46     | 0.15  | EXIOBASE v3 IN.46 (Textiles — accessories)             |
| Travel related consumer goods                         | IN.53     | 0.10  | EXIOBASE v3 IN.53 (Printed matter)                     |
| Travel related consumer goods                         | IN.52     | 0.05  | EXIOBASE v3 IN.52 (Paper)                              |
| Travel related consumer goods                         | IN.103    | 0.05  | EXIOBASE v3 IN.103 (Electronics)                       |
| Footwear                                              | IN.48     | 1.00  | EXIOBASE v3 IN.48 (Leather and footwear)               |
| Soaps, cosmetics and glycerine                        | IN.91     | 1.00  | EXIOBASE v3 IN.91 (Chemicals)                          |
| Gems and jewellery                                    | IN.91     | 1.00  | EXIOBASE v3 IN.91 (Chemicals/jewellery proxy)          |
| Books, journals, magazines, stationery                | IN.53     | 0.60  | EXIOBASE v3 IN.53 (Printed matter)                     |
| Books, journals, magazines, stationery                | IN.52     | 0.40  | EXIOBASE v3 IN.52 (Paper)                              |
| Vacation homes                                        | IN.125    | 1.00  | EXIOBASE v3 IN.125 (Real estate activities)            |
| Social transfers in kind                              | IN.130    | 1.00  | EXIOBASE v3 IN.130 (Public administration)             |
| FISIM                                                 | IN.122    | 1.00  | EXIOBASE v3 IN.122 (Financial intermediation)          |
| Producers guest houses                                | IN.125    | 0.50  | EXIOBASE v3 IN.125 (Real estate activities)            |
| Producers guest houses                                | IN.136    | 0.50  | EXIOBASE v3 IN.136 (Other services — NEC)              |
| Imputed expenditures on food                          | IN.42     | 1.00  | EXIOBASE v3 IN.42 (Food manufacturing)                 |

---

## SECTION: USD_INR

<!-- meta
id: USD_INR
description: Annual average USD/INR exchange rates for each study fiscal year.
source: Reserve Bank of India (RBI) reference rates, annual averages. Verified: https://data.rbi.org.in
unit: INR per 1 USD (fiscal-year annual average, April-March)
notes: Conversion: USD_M = crore × 10 / usd_inr
-->

| study_year | usd_inr | reference                                                                          |
|------------|---------|------------------------------------------------------------------------------------|
| 2015       | 64.15   | RBI Annual Report 2016, Table I.3; fiscal-year average April–March                 |
| 2019       | 70.41   | RBI Annual Report 2020, Table I.3; fiscal-year average April–March                 |
| 2022       | 78.65   | RBI Annual Report 2022, Table I.3; fiscal-year average April–March (TODO: verify)  |

---

## SECTION: UNIT_RENTS

<!-- meta
id: UNIT_RENTS
description: Unit resource rents for NDP monetary valuation — ₹ crore per physical tonne equivalent.
  Fossil fuels: net price method (market price minus average extraction cost).
  Metal/mineral: royalty-based rent from IBM/Ministry of Mines data.
  Biomass: stumpage value for timber; FAO unit value for fishery/crops.
source: World Bank Wealth Accounts 2021 India; IBM/Ministry of Mines royalty data; FAO unit values.
unit: crore INR per tonne equivalent
notes: Previously hardcoded in config.py (moved here as single source of truth).
  Sensitivity: ±20% on unit rents shifts NDP by approximately ±0.01–0.03% of GDP.
-->

| study_year | fossil   | metal    | nonmetal | biomass  | reference                                                                    |
|------------|----------|----------|----------|----------|------------------------------------------------------------------------------|
| 2015       | 0.00038  | 0.00012  | 0.000035 | 0.000080 | World Bank Wealth Accounts 2021 India; IBM/MoM royalty data; FAO unit values |
| 2019       | 0.00051  | 0.00015  | 0.000045 | 0.000095 | World Bank Wealth Accounts 2021 India; IBM/MoM royalty data; FAO unit values |
| 2022       | 0.00072  | 0.00019  | 0.000058 | 0.000110 | World Bank Wealth Accounts 2021 India; IBM/MoM royalty data; FAO unit values |

---

## SECTION: NAS_MACRO

<!-- meta
id: NAS_MACRO
description: GDP and Consumption of Fixed Capital (CFC) at current prices for NDP computation.
  NDP = GDP − CFC − Natural Capital Depletion (computed by postprocess.py).
source: MoSPI National Accounts Statistics 2023, Statement 1 (GDP) and Statement 2 (CFC).
unit: crore INR, current prices
notes: Previously hardcoded in config.py (moved here as single source of truth).
  Update when MoSPI revises figures — revisions are common for recent years.
  Framework: SEEA-CF / UNSC recommendation for NDP reporting.
-->

| study_year | gdp_crore  | cfc_crore | reference                                                               |
|------------|------------|-----------|-------------------------------------------------------------------------|
| 2015       | 13576086   | 1847000   | MoSPI NAS 2023, Statements 1 & 2, FY 2015-16, current prices           |
| 2019       | 20033022   | 2980000   | MoSPI NAS 2023, Statements 1 & 2, FY 2019-20, current prices           |
| 2022       | 23652441   | 3724000   | MoSPI NAS 2023, Statements 1 & 2, FY 2021-22, current prices           |

---

## SECTION: OUTBOUND_ENERGY_DATA

<!-- meta
id: OUTBOUND_ENERGY_DATA
description: Outbound energy footprint by destination country — activity-based (Lee et al. 2021 adapted).
source: IEA World Energy Balances 2022; MoT India Tourism Statistics 2022
unit: local_ef_mj_yr=MJ/yr | dest_share=fraction | carbon_intensity=tCO2e/MJ
notes: PLACEHOLDER values — replace with country-specific IEA data before submission.
-->

| country      | dest_share | local_ef_mj_yr | carbon_intensity | reference                                                   |
|--------------|------------|----------------|------------------|-------------------------------------------------------------|
| UAE          | 0.22       | 450000         | 0.62             | IEA World Energy Balances 2022; MoT ITS 2022 (PLACEHOLDER) |
| Saudi Arabia | 0.20       | 420000         | 0.58             | IEA World Energy Balances 2022; MoT ITS 2022 (PLACEHOLDER) |
| USA          | 0.10       | 310000         | 0.45             | IEA World Energy Balances 2022; MoT ITS 2022 (PLACEHOLDER) |
| UK           | 0.08       | 150000         | 0.22             | IEA World Energy Balances 2022; MoT ITS 2022 (PLACEHOLDER) |
| Thailand     | 0.07       | 80000          | 0.51             | IEA World Energy Balances 2022; MoT ITS 2022 (PLACEHOLDER) |
| Singapore    | 0.06       | 180000         | 0.40             | IEA World Energy Balances 2022; MoT ITS 2022 (PLACEHOLDER) |
| Malaysia     | 0.05       | 130000         | 0.48             | IEA World Energy Balances 2022; MoT ITS 2022 (PLACEHOLDER) |
| Germany      | 0.04       | 170000         | 0.30             | IEA World Energy Balances 2022; MoT ITS 2022 (PLACEHOLDER) |
| France       | 0.04       | 160000         | 0.18             | IEA World Energy Balances 2022; MoT ITS 2022 (PLACEHOLDER) |
| Other        | 0.14       | 120000         | 0.45             | Assumed average; IEA World Energy Balances 2022             |

---

*End of reference data. Add new sections above this line following the template at the top.*
