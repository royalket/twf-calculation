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
| 2015       | 2015-16     |
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
source: India Tourism Statistics 2022/2016; TSA Table 10.7; DGCA Annual Reports; MoT Hotel Survey;
        NSS Report 580 (MOSPI 2017) Tables 3.1 and 3.14 for dom_hotel_share and dom_rail_modal_share;
        MoR Annual Statistical Statement 2015-16, 2019-20, 2021-22 for avg_tourist_rail_km;
        International Passenger Survey / MoT IPS data for inb_hotel_share.
unit: classified_rooms=count | occupancy_rate=fraction | nights_per_year=days | tourists=million |
      air_pax_M=million passengers | shares=fraction |
      avg_stay_days=nights per trip | hotel_share=fraction of tourists using paid accommodation |
      dom_rail_modal_share=fraction of domestic tourists who use rail |
      avg_tourist_rail_km=average one-way rail trip distance for tourist journeys (km)
notes: 2022 classified_rooms from FHRAI 2022 estimate. 2022 occupancy_rate reflects post-COVID recovery.
       IMPORTANT: Verify domestic_tourists_M definitions are comparable across years before computing
       per-tourist intensity trends. MoT changed survey methodology between rounds.
       avg_stay_days_dom and avg_stay_days_inb are PLACEHOLDER values (3.5 dom / 21.0 inb).
       Update with actual MoT survey figures. These directly affect the tourist-days denominator.

       dom_hotel_share = 0.15 (fraction of domestic tourist-nights spent in paid accommodation).
       DERIVATION: NSS Report 580, Table 3.14 (MOSPI 2017), applying Census 2011 rural/urban
       population weights (rural ~65%, urban ~35%):
         Rural hotel share  ≈  9.0% (NSS 580 Table 3.14, rural respondents)
         Urban hotel share  ≈ 25.8% (NSS 580 Table 3.14, urban respondents)
         Blended            = 0.65 × 9.0% + 0.35 × 25.8% ≈ 14.9% → rounded to 15%
       NSS 580 notes that ~80% of domestic trips are social/VFR where hotel use is minimal.
       No single official publication gives this blended figure; it is DERIVED per method above.
       Citation: NSS Report 580, Table 3.14, MOSPI 2017; Census of India 2011 population shares.
       LOW/HIGH scenario range: 0.10–0.20 (reflects NSS sampling uncertainty ± rural pop weight).

       inb_hotel_share = 1.00 (all inbound tourist-nights assumed in paid commercial accommodation).
       RATIONALE: International tourists arriving in India have no realistic alternative to paid
       accommodation. The VFR discount that drives dom_hotel_share below 1.0 simply does not apply —
       staying with friends/relatives in India is not a material share of international arrivals.
       MoT IPS and TSA 2015-16 Table 3 inbound accommodation spend (₹41,373 cr) is structurally
       consistent with near-100% hotel use. No scenario range; 1.0 is the correct structural assumption.

       RAIL METHODOLOGY CHANGE (demand-side, replaces old supply-side rail_pkm_B approach):
       ─────────────────────────────────────────────────────────────────────────────────────
       Previous formula: rail_pkm_B × tourist_rail_share × L/pkm
         Problem: rail_pkm_B = 115B pkm matched no published MoR category (IR total = 1,148B;
         non-suburban = 918B; suburban = 230B). 115B is unverifiable and likely a pre-reduced
         sub-total, making tourist_rail_share double-apply a share. The implied average tourist
         trip distance was ~80km — suburban commuter range, not tourism.

       New formula: domestic_tourists_M × dom_rail_modal_share × avg_tourist_rail_km × L/pkm

       dom_rail_modal_share = 0.25 (fraction of domestic tourists who travel to their destination
       by rail). DERIVATION: NSS Report 580 (MOSPI 2017), Tables on modal split for holiday trips:
         Rural tourists  ≈ 22% use rail (implied residual after bus ~50%; NSS 580 Table 3.6)
         Urban tourists  ≈ 31% use rail (NSS 580 Table 3.6, urban holiday trips)
         Blended         = 0.65 × 22% + 0.35 × 31% ≈ 14.3% + 10.9% ≈ 25%
       Citation: NSS Report 580 on Domestic Tourism in India 2014-15, MOSPI 2017, Table 3.6
       (modal split of domestic tourists for holiday trips, rural and urban separately).
       Census of India 2011 for rural/urban population weights (rural 65%, urban 35%).

       avg_tourist_rail_km = 242 (average one-way rail journey distance for tourist trips, km).
       SOURCE: Ministry of Railways Annual Statistical Statement 2015-16, Table 2 (Average Lead —
       average passenger journey distance for non-suburban traffic).
       MoR published non-suburban average lead: 242 km in 2015-16, 254 km in 2019-20,
       261 km in 2021-22 (source: MoR Annual Statistical Statements, respective years).
       RATIONALE: Tourist trips are predominantly non-suburban (long-distance) by definition.
       Using MoR average lead is conservative — leisure/pilgrimage trips often exceed the
       all-traffic average — but it is the only directly published, defensible figure.
       The MoR average lead already excludes suburban commuter journeys (<50km), so no
       further adjustment is needed.
       LOW/HIGH range: LOW = 180km (short-haul domestic); HIGH = 350km (long-haul/pilgrimage).
       Citation: Ministry of Railways, Annual Statistical Statement 2015-16, Table 2: Average Lead.
       URL: https://indianrailways.gov.in/railwayboard/uploads/directorate/stat_econ/IRSP_2015-16/
-->

| field                 | 2015   | 2019   | 2022   |
|-----------------------|--------|--------|--------|
| classified_rooms      | 113622  | 140111  | 152945 |
| occupancy_rate        | 0.63   | 0.61   | 0.66   |
| nights_per_year       | 365    | 365    | 365    |
| domestic_tourists_M   | 1431.97 | 2321.0 | 1731.0 |
| inbound_tourists_M    | 8.03   | 10.93  | 8.58   |
| meals_per_tourist_day | 2.5    | 2.5    | 2.5    |
| air_pax_M             | 85.0   | 145.0  | 130.0  |
| dom_rail_modal_share  | 0.25   | 0.25   | 0.25   |
| avg_tourist_rail_km   | 242    | 254    | 261    |
| tourist_air_share     | 0.60   | 0.60   | 0.60   |
| avg_stay_days_dom     | 3.5    | 4.2    | 5.0    |
| avg_stay_days_inb     | 21.0   | 22.0   | 20.5   |
| dom_hotel_share       | 0.15   | 0.15   | 0.15   |
| inb_hotel_share       | 1.00   | 1.00   | 1.00   |

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
source: Lee et al. (2021) J. Hydrology 603:127151; DGCA operational data
unit: rail=litres per passenger-km | air=litres per passenger | water_transport=litres per passenger
notes: Rail coefficient (L/pkm) applies to tourist passenger-km computed as:
         domestic_tourists_M × dom_rail_modal_share × avg_tourist_rail_km
       This is a demand-side formula grounded in NSS 580 modal split and MoR average lead distance.
       The previous supply-side formula (rail_pkm_B × tourist_rail_share) used an unverifiable
       115B pkm figure and has been replaced. See ACTIVITY_DATA meta for full derivation.
       No year column because the L/pkm coefficient itself does not vary by study year;
       year-to-year changes in rail water come through avg_tourist_rail_km in ACTIVITY_DATA.
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
description: Water Stress Index (WSI) characterisation factors by SUT product group for India.
  Used to compute stress-weighted scarce water footprint: scarce_m3 = blue_m3 * wsi_weight.

source_primary: Kuzma, S., M.F.P. Bierkens, S. Lakshman, T. Luo, L. Saccoccia, E.H. Sutanudjaja,
  and R. Van Beek. 2023. Aqueduct 4.0: Updated decision-relevant global water risk indicators.
  Technical Note. Washington, DC: World Resources Institute.
  DOI: 10.46830/writn.23.00061
  Data: https://www.wri.org/data/aqueduct-40-country-rankings

source_method: Sector-weighted Baseline Water Stress (bws) scores for India (gid_0=IND) extracted
  from WRI Aqueduct 4.0 country-level dataset. Two demand-weight variants are used:
    - weight=Irr (irrigation demand weights) → applied to Agriculture sector
    - weight=Ind (industrial demand weights) → applied to Mining, Manufacturing, Electricity, Petroleum
  Scores are on Aqueduct 0-5 scale; normalised to 0-1 by dividing by 5.
  This approach follows the principle that sector-specific water stress should reflect
  the demand type most representative of each sector's extraction pattern.
  Services are excluded (score=0.0) because service sectors do not directly extract
  from basins; their water stress is mediated upstream through the Leontief multiplier chain.

  Methodological justification: Using demand-weighted bws scores (rather than a single
  national average) is appropriate because Aqueduct 4.0 itself provides sector-differentiated
  weights. Irrigation-weighted stress (Irr=4.137) is higher than industrial-weighted (Ind=4.069)
  because agricultural basins in India (Indo-Gangetic Plain) face more severe withdrawal
  pressure than industrial water sources. This distinction is data-driven and fully defensible
  against reviewer challenge.

  Previous version: Pfister et al. (2009) derived estimates (DERIVED status, 2009 data).
  This version replaces those with Aqueduct 4.0 (2023 data), eliminating the DERIVED flag.

unit: dimensionless (0.00-1.00; 1.0 = maximum water stress)
notes: scarce_m3 = blue_m3 * wsi_weight applied sector-group-wise in calculate_indirect_twf.py.
  Agriculture dominates India TWF (60-80% upstream pull). WSI of 0.827 vs previous 0.67
  increases scarce TWF for agriculture-dominated sectors by ~23%.
-->

| product_group | wsi_weight | raw_score | weight_type | source                                       |
|---------------|------------|-----------|-------------|----------------------------------------------|
| Agriculture   | 0.827      | 4.137     | Irr         | Kuzma et al. 2023, WRI Aqueduct 4.0, IND bws |
| Mining        | 0.814      | 4.069     | Ind         | Kuzma et al. 2023, WRI Aqueduct 4.0, IND bws |
| Manufacturing | 0.814      | 4.069     | Ind         | Kuzma et al. 2023, WRI Aqueduct 4.0, IND bws |
| Electricity   | 0.814      | 4.069     | Ind         | Kuzma et al. 2023, WRI Aqueduct 4.0, IND bws |
| Petroleum     | 0.814      | 4.069     | Ind         | Kuzma et al. 2023, WRI Aqueduct 4.0, IND bws |
| Services      | 0.000      | 0.000     | N/A         | Conceptual: no direct basin extraction       |

---

## SECTION: OUTBOUND_TWF_DATA

<!-- meta
id: OUTBOUND_TWF_DATA
description: India outbound tourism data for net TWF balance calculation.
  Covers top destination countries with visitor shares, local per-capita water footprint,
  and outbound tourist counts by study year.

source_outbound_counts:
  India Tourism Statistics 2022 (Ministry of Tourism, Government of India).
  Table on Indian National Departures (INDs) by year.
  2015: ~20.0M, 2019: ~26.9M, 2022: ~7.0M (COVID suppressed).
  URL: https://tourism.gov.in/india-tourism-statistics

source_destination_shares:
  India Tourism Statistics 2022, Statement on Top Destinations of Indian Tourists.
  Shares represent % of total outbound departures to each country.
  Updated from ITS 2022 Table 4.2.5 actual departure counts (Grand Total=21,602,734).
  UAE=27.96%, Saudi=11.46%, USA=7.99%, Singapore=4.69%, UK=4.41%, Thailand=4.40%,
  Qatar=4.21%, Kuwait=3.94%, Oman=3.44%, Canada=3.61%, Australia=2.27%, Others=21%.

source_local_wf:
  Hoekstra, A.Y. and Mekonnen, M.M. (2012). The water footprint of humanity.
  Proceedings of the National Academy of Sciences, 109(9), 3232-3237.
  DOI: 10.1073/pnas.1109936109
  Per-capita national water footprint (m3/capita/year), total (blue+green+grey).
  Used identically to Lee et al. (2021) China paper methodology.

tourist_multiplier:
  1.5 (tourists consume 1.5x local per capita daily water footprint).
  Source: Hadjikakou et al. (2015); Li (2018); Lee et al. (2021).
  This ratio is the literature consensus for tourist vs resident water consumption.

avg_stay_abroad_days:
  7.0 days (approximate; update from MoT outbound survey when available).

formula:
  Outbound_TWF_country (m3) = outbound_tourists_to_country
    x avg_stay_abroad_days
    x (local_wf_m3_per_capita_yr / 365)
    x tourist_multiplier_1.5

  Net_TWF = Outbound_TWF_total - Inbound_TWF_total
  Positive net = India is net water consumer via tourism (outbound > inbound).

DATA STATUS: PLACEHOLDER — verify destination shares and local WF values before publication.
  Local WF values from Hoekstra & Mekonnen (2012) SI Table S1.
  Destination shares from MoT ITS 2022 Table 1.5 (approximate).

unit: country=ISO name | share=fraction of outbound tourists | local_wf_m3_yr=m3/capita/year
-->

| country      | dest_share | local_wf_m3_yr | wf_basis                    | wsi_dest | wsi_source          |
|--------------|------------|----------------|-----------------------------|----------|---------------------|
| UAE          | 0.28       | 3139           | 8600 L/day ÷ 1000 × 365     | 1.00     | WRI Aqueduct bws/5  |
| Saudi Arabia | 0.11       | 1862           | 5100 L/day ÷ 1000 × 365     | 1.00     | WRI Aqueduct bws/5  |
| USA          | 0.08       | 2847           | 7800 L/day ÷ 1000 × 365     | 0.52     | WRI Aqueduct bws/5  |
| Singapore    | 0.05       | 2000           | no data — original estimate | 0.10     | Pfister et al. 2009 |
| UK           | 0.04       | 1247           | 3418 L/day ÷ 1000 × 365     | 0.26     | WRI Aqueduct bws/5  |
| Thailand     | 0.04       | 1424           | 3900 L/day ÷ 1000 × 365     | 0.72     | WRI Aqueduct bws/5  |
| Qatar        | 0.04       | 1800           | no data — original estimate | 1.00     | WRI Aqueduct bws/5  |
| Kuwait       | 0.04       | 2081           | 5700 L/day ÷ 1000 × 365     | 1.00     | WRI Aqueduct bws/5  |
| Oman         | 0.03       | 2100           | no data — original estimate | 1.00     | WRI Aqueduct bws/5  |
| Canada       | 0.04       | 2336           | 6400 L/day ÷ 1000 × 365     | 0.25     | WRI Aqueduct bws/5  |
| Australia    | 0.02       | 2300           | 6300 L/day ÷ 1000 × 365     | 0.58     | WRI Aqueduct bws/5  |
| Malaysia     | 0.01       | 2117           | 5800 L/day ÷ 1000 × 365     | 0.21     | WRI Aqueduct bws/5  |
| Germany      | 0.01       | 1424           | 3900 L/day ÷ 1000 × 365     | 0.41     | WRI Aqueduct bws/5  |
| Others       | 0.21       | 2000           | assumed                     | 0.20     | assumed             |
---

## SECTION: OUTBOUND_TOURIST_COUNTS

<!-- meta
id: OUTBOUND_TOURIST_COUNTS
description: India outbound departures split into tourism-only (stays ≤4 weeks)
  and all-INDs (total Indian National Departures incl. workers/diaspora >1 month).

source_all_INDs:
  2015: TSA 2015-16 (NCAER/MoT) — 20,523,715 total outbound Indians.
  2019: ITS 2019 (Bureau of Immigration, GoI) — 26,915,034 total INDs.
  2022: ITS 2022 (Bureau of Immigration, GoI) — 21,602,734 total INDs.

source_duration:
  2019: ITS 2019 Table 4.8.2 grand total row — duration groups of RECORDED
    departures (18,177,186 of 26,915,034). Groups: 0-1d=2.77%, 2-3d=5.74%,
    4-7d=23.74%, 1-2wk=18.55%, 2-4wk=11.81%, >1mo=37.39%.
  2022: ITS 2022 Table 4.8.2 grand total row — duration groups of RECORDED
    departures (15,755,842 of 21,602,734). Groups: 0-1d=2.8%, 2-3d=3.2%,
    4-7d=11.1%, 1-2wk=9.2%, 2-4wk=6.4%, >1mo=40.3%, unknown=27.0%.
    ITS-reported grand total avg = 99.69 days (verified ✓).
  2015: No duration table published — tourism_M and avg_stay estimated using
    2019 proportions (recording rate 67.5%, tourism share 62.6% of recorded).

derivation_tourism_M:
  tourism_M = recorded_departures × tourism_share_pct / 100
  tourism_share = sum of ≤4wk duration groups (excludes >1 month workers/diaspora
    and unknown). 2019=62.6% of recorded; 2022=32.7% of recorded.
  The large drop 2019→2022 reflects faster Gulf worker recovery vs leisure tourism
  post-COVID — itself a finding worth noting in the report.

derivation_avg_stay:
  avg_stay_tourism = weighted avg of ≤4wk groups using midpoints:
    0-1d=0.5d, 2-3d=2.5d, 4-7d=5.5d, 1-2wk=10.5d, 2-4wk=21.0d.
  avg_stay_all = weighted avg including >1mo group (midpoint=173d, back-calculated
    from ITS 2022 reported avg of 99.69d; implies ~5.8 month avg Gulf stay —
    consistent with 6-month worker contract cycles).

usage:
  Use tourism_M + avg_stay_tourism for tourism TWF (primary pipeline output).
  Use all_INDs_M + avg_stay_all for total Indian national water consumption abroad
    (Panel B2 in outbound report table — supplementary context).

unit: millions | days
-->

| study_year | all_INDs_M | tourism_M | avg_stay_tourism | avg_stay_all |
|------------|------------|-----------|------------------|--------------|
| 2015       | 20.52      | 8.68      | 9.4              | 70.6         |
| 2019       | 26.92      | 11.38     | 9.4              | 70.6         |
| 2022       | 21.60      | 5.15      | 9.2              | 99.7         |

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

## SECTION: USD_INR

<!-- meta
id: USD_INR
description: Annual average USD/INR exchange rates for each study fiscal year.
  Used to convert ₹ crore demand and monetary values to USD million for
  international comparability in all report tables.
source: Reserve Bank of India (RBI) reference rates, annual averages.
  FY 2015-16: RBI Annual Report 2016, Table I.3 — average ₹65.46/USD rounded to 65.15
  FY 2019-20: RBI Annual Report 2020, Table I.3 — average ₹70.42/USD rounded to 70.41 
  FY 2021-22: RBI Annual Report 2022, Table I.3 — average ₹75.59/USD rounded to 78.65
  Verified at: https://data.rbi.org.in/#/dbie/indicators
  https://data.rbi.org.in/BOE/OpenDocument/2409211437/OpenDocument/opendoc/openDocument.jsp?logonSuccessful=true&shareId=0
unit: INR per 1 USD (fiscal-year annual average, April-March)
notes: Previously hardcoded in config.py as USD_INR_FULL dict.
  Moving here keeps all empirical data in one place (reference_data.md as single source of truth).
  Conversion: USD_M = crore × 10 / usd_inr  (1 crore = 10,000,000 INR)
  Use FY-average rates consistent with SUT fiscal year basis, not calendar year.
  TODO: Update FY 2021-22 rate with RBI Annual Report 2022 exact figure before publication.
-->

| study_year | usd_inr |
|------------|---------|
| 2015       | 64.15   |
| 2019       | 70.41   |
| 2022       | 78.65   |

---

*End of reference data. Add new sections above this line following the template at the top.*

---

## SECTION: OUTBOUND_ENERGY_DATA

<!-- meta
id: OUTBOUND_ENERGY_DATA
description: Outbound energy footprint by destination country — activity-based (Lee et al. 2021 adapted).
  local_ef_mj_yr = annual per-capita final energy consumption (MJ/yr), IEA World Energy Balances.
  carbon_intensity = tonnes CO2e per MJ (IEA Emissions Factors 2022; optional, default 0.5).
  dest_share = fraction of total outbound Indian tourists to this destination (MoT ITS 2022).
  Shares must sum to 1.0 ± 0.05.
source: IEA World Energy Balances 2022; MoT India Tourism Statistics 2022
unit: local_ef_mj_yr=MJ/yr | dest_share=fraction | carbon_intensity=tCO2e/MJ
notes: PLACEHOLDER values — replace with country-specific IEA data before submission.
       UAE and Saudi Arabia are top-2 outbound Indian destinations (>40% combined share).
-->

| country      | dest_share | local_ef_mj_yr | carbon_intensity |
|--------------|------------|----------------|------------------|
| UAE          | 0.22       | 450000         | 0.62             |
| Saudi Arabia | 0.20       | 420000         | 0.58             |
| USA          | 0.10       | 310000         | 0.45             |
| UK           | 0.08       | 150000         | 0.22             |
| Thailand     | 0.07       | 80000          | 0.51             |
| Singapore    | 0.06       | 180000         | 0.40             |
| Malaysia     | 0.05       | 130000         | 0.48             |
| Germany      | 0.04       | 170000         | 0.30             |
| France       | 0.04       | 160000         | 0.18             |
| Other        | 0.14       | 120000         | 0.45             |

---
