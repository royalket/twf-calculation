# India Tourism Water Footprint (2015 vs 2022)

**Method**: Environmentally Extended Input-Output (EEIO) Analysis + Activity-Based Direct Water  
**Reference**: Lee et al. (2021) — *Journal of Hydrology* 603, 127151  
**Scope**: TWF for 2015 (baseline) and 2022 (target), temporal comparison

---

## 1. PROJECT OVERVIEW

This project calculates India's Tourism Water Footprint (TWF) for **2015 and 2022** and compares them to assess changes in tourism water intensity over time. TWF is decomposed into:

- **Indirect water** — virtual water embedded in supply chains (food production, electricity, manufacturing) triggered by tourism spending. Calculated via EEIO using EXIOBASE water coefficients.
- **Direct water** — operational water consumed on-site by tourism service establishments (hotels, restaurants, transport). EXIOBASE assigns **zero** to service sectors by design (production-based accounting only). Calculated separately via activity-based coefficients.

**Key constraint**: India's IO tables are available for 2015-16 and 2019-20 (MoSPI Supply-Use Tables). Each year uses its own year-matched SUT: the **2015-16 SUT** is the structural backbone for the 2015 calculation, and the **2019-20 SUT** is the structural backbone for the 2022 calculation. Tourism demand vectors for 2015 and 2022 are derived separately from TSA data.

---

## 2. RESEARCH OBJECTIVES

1. Calculate India's total TWF for 2015 and 2022
2. Decompose into direct vs indirect water consumption
3. Identify key sectors driving tourism water use
4. Compute per-tourist water intensity (L/tourist/day) for domestic and inbound tourists
5. Compare temporal change and assess efficiency trends

---

## 3. KEY DATA SOURCES

| Data | Source | Year Used | Details |
|------|--------|-----------|---------|
| **Input-Output Table (2015)** | MoSPI Supply-Use Tables | 2015-16 | 140 products × 66 industries → converted to 140×140 symmetric IO |
| **Input-Output Table (2022)** | MoSPI SUT 2019-20 + NAS 2021-22 | 2019-20 updated to 2022 | A matrix scaled using NAS sector output indices → new L_2022 = (I−A_2022)⁻¹ |
| **Water Coefficients (Indirect)** | EXIOBASE 3 (ixi) | 2015, 2022 | 163 sectors × 44 countries; water extension in `/water/F.txt` |
| **Tourism Demand (2015)** | TSA India 2015-16 | 2015-16 | 24 product categories, ₹ crores |
| **Tourism Demand (2022)** | TSA 2015-16 scaled via NAS | 2022 | Sector-specific growth rates from NAS 2021-22 |
| **Hotel Direct Water** | Cornell CHSB 2022 India | 2022 | Measure 8: 818 L/occupied room/night (weighted by India hotel mix) |
| **Hotel Direct Water (2015)** | Cornell CHSB 2015 India | 2015 | Measure 8: 1,251 L/night, median (n=77) |
| **Restaurant Water** | Lee et al. (2021) | Both | 30 L/meal (2015), 32 L/meal (2022) |
| **Rail Transport Water** | Transport literature | Both | 3.5 L/passenger-km |
| **Air Transport Water** | Aviation studies | Both | 18 L/passenger |
| **Hotel Room Distribution** | TSA Table 10.7 (2016) | 2015 | 79,879 rooms: 59.2% in 5-star, 22% in 3-star, 12.4% in 4-star |
| **NAS Growth Rates** | MoSPI NAS 2021-22 | 2022 | Tables 8.1, 8.9, 1.6 for sector-specific scaling |

---

## 4. WHY EXIOBASE HAS ZERO FOR SERVICE SECTORS

EXIOBASE water data comes from WaterGAP (industrial sectors) and Water Footprint Network (agriculture). Both are **production-based**: they measure water used to produce physical goods, not water used during service delivery.

**Result**: Hotels, restaurants, transport services = **0.0 m³/₹ crore** in EXIOBASE.

This was verified across all major MRIO databases:
- **EXIOBASE**: WaterGAP + WFN → zero for services
- **Eora26**: WFN (rows 2496-2513) → same source, same result (confirmed by extracting India Hotels sector)
- **WIOD**: Energy-focused; service water not captured
- **GTAP**: No water extensions

**Conclusion**: No existing database captures service sector operational water. A two-component framework is required.

---

## 5. REFERENCE: LEE ET AL. (2021) — CHINA METHODOLOGY

**Citation**: Lee, L-C., Wang, Y., & Zuo, J. (2021). Water footprint of Chinese tourists: Directions and structure. *Journal of Hydrology*, 603, 127151.

### What They Did

Lee et al. calculated China's TWF using EEIO + TSA for 2017 across 135 sectors (11 direct + 124 indirect tourism sectors).

### Their Formula

```
Direct TWF  = Dwc × Y                        ...(5)
Total TWF   = Dwc × (I-A)⁻¹ × Y             ...(7)
Indirect TWF = Total TWF − Direct TWF         ...(6)

Where:
Dwc  = direct water use coefficient vector (m³/US$) for 135 sectors
       Dwci = Wi / Xi  [water use of sector i / total output of sector i]
(I-A)⁻¹ = Leontief inverse (135×135)
Y    = tourism final demand vector (from TSA, 11 direct sectors; 0 for rest)
```

### Their Data Sources for Water Coefficients
- Agriculture: China Statistical Yearbook 2018 (actual measured data)
- Industry (52 sectors): National Bureau of Statistics of China
- Remaining sectors: Proportional to water supply sector's complete consumption coefficient matrix `(I-A)⁻¹ - I`

### Their Key Results (China 2017)
- Total TWF: 19.51 billion m³ (2.8% of China's total water use)
- Domestic TWF: 16,409 million m³ | Inbound TWF: 3,104 million m³
- Direct TWF per domestic tourist: 136 L/day | Indirect: 1,033 L/day
- Direct TWF per inbound tourist: 810 L/day | Indirect: 6,122 L/day
- Top indirect sectors: Agriculture (74%), Electricity (14%), Petroleum (1%)
- Top direct sector: Accommodation (51% of all direct water)
- Indirect/Direct ratio: ~10:1

### Key Difference from India Study
China had **actual sectoral water census data** from national statistical yearbooks for both agriculture and industry. India does **not** have equivalent service sector operational water data. Hence, India requires activity-based coefficients for direct water (our two-component approach), while Lee et al. could derive all coefficients directly from national statistics.

---

## 6. TWO-COMPONENT FRAMEWORK

```
Total TWF = Indirect TWF (EXIOBASE) + Direct TWF (Activity-Based)

Indirect TWF = W × (I-A)⁻¹ × Y        [supply chain virtual water]
Direct TWF   = Σ (Activity × Coefficient) [on-site operational water]
```

---

## 7. STEP-BY-STEP CALCULATION

### SHARED INFRASTRUCTURE (Used for Both Years)

#### Step 1a: SUT → IO Table (2015-16)
- **Input**: `supply-table-2015-16.csv`, `USE-TABLE-2015-16.csv` (140×66)
- **Method**: Product Technology Assumption (PTA)
- **Output**:
  - `io_matrix_Z_2015_16.csv` — intermediate flows (140×140)
  - `technical_coefficients_A_2015_16.csv` — A matrix (140×140)
  - `leontief_inverse_L_2015_16.csv` — L = (I-A)⁻¹ (140×140)
- **Script**: `step1a_sut_to_io_2015.py`

#### Step 1b: SUT → IO Table (2019-20)
- **Input**: `supply-table-2019-20.csv`, `USE-TABLE-2019-20.csv` (140×66)
- **Method**: Product Technology Assumption (PTA)
- **Output**:
  - `io_matrix_Z_2019_20.csv` — intermediate flows (140×140)
  - `technical_coefficients_A_2019_20.csv` — A matrix (140×140)
  - `leontief_inverse_L_2019_20.csv` — L = (I-A)⁻¹ (140×140)
- **Script**: `step1b_sut_to_io_2019.py`

#### Step 2: EXIOBASE Concordance (Done for Both 2015 and 2022)
- **Input**: EXIOBASE `IOT_2015_ixi/water/F.txt` and `IOT_2022_ixi/water/F.txt`
- **Method**: Map 163 EXIOBASE India sectors → 140 SUT products using concordance table
- **Key aggregations**: 33 petroleum sectors → 1, 14 electricity sectors → 1, 8 coal sectors → 1
- **Output**:
  - `India_Water_Coefficients_2015_Complete.csv`
  - `India_Water_Coefficients_2022_Complete.csv`
  - `water_coefficients_140_products.csv` (concordance-mapped)
- **Script**: `step2_create_concordance.py`

---

### YEAR 2022 CALCULATION

#### Step 3a: Update IO Table to 2022 Using NAS + Construct 2022 Demand Vector
- **Input**: `leontief_inverse_L_2019_20.csv`, NAS 2021-22 sector output indices (Tables 8.1, 8.9, 1.6), `TSATable4-TotalInternalTourismConsumption.csv`
- **Method (two sub-steps)**:
  - **IO update**: Sector output indices from NAS 2021-22 used to scale the 2019-20 A matrix rows and columns, bringing the technical coefficients forward to approximate 2022 production structure. New Leontief inverse L_2022 = (I − A_2022)⁻¹ derived from the updated A matrix.
  - **Demand vector**: TSA 2015-16 spending per sector × sector-specific NAS growth rate → mapped to 140 SUT product IDs → final demand vector Y_2022 (140×1, ₹ crore)
- **Why NAS-based IO update**: Using the 2019-20 IO table unmodified for 2022 ignores real structural shifts in the economy. NAS sector output data provides the best available proxy to update inter-industry coefficients without a published 2022 SUT.
- **Output**: `A_matrix_2022_updated.csv`, `leontief_inverse_L_2022.csv`, `tourism_demand_vector_2022.csv`, `nas_growth_rates.csv`
- **Script**: `step3_construct_tourism_demand_2022.py`

#### Step 4a: Calculate Indirect TWF (2022)
```python
W  = water_coefficients_140_products (from EXIOBASE 2022, mapped to 140 sectors)
L  = leontief_inverse_L_2022         (NAS-updated from 2019-20 SUT — see Step 3a)
Y  = tourism_demand_vector_2022      (TSA 2015-16 × NAS growth rates)

Total_TWF    = W @ L @ Y
Direct_TWF   = W @ Y
Indirect_TWF = Total_TWF - Direct_TWF
```
- **Output**: `twf_2022_complete_sectoral_results.csv`
- **Current result**: ~1.47 billion m³ (indirect virtual water only)
- **Script**: `step4_calculate_twf.py`

#### Step 5a: Calculate Direct Operational Water (2022)
Convert TSA expenditure → physical activities → water consumption:

| Sector | TSA Category | Conversion | Coefficient | Source |
|--------|-------------|------------|-------------|--------|
| Hotels | H&R exp × 60% ÷ avg room rate (₹3,000) | Guest nights | **818 L/night** | CHSB 2022 India, weighted by India hotel mix |
| Restaurants | H&R exp × 40% ÷ avg meal cost (₹250) | Meals served | **32 L/meal** | Lee et al. (2021) |
| Rail | Rail exp ÷ ₹0.5/km fare | Passenger-km | **3.5 L/pax-km** | Transport literature |
| Air | Air exp ÷ ₹8,000/ticket | Passengers | **18 L/passenger** | Aviation studies |

**Sensitivity ranges**:
- Hotels: LOW 563 L (budget segment median) | BASE 818 L (India weighted avg) | HIGH 1,247 L (NonResort UQ)
- Restaurants: LOW 20 L | BASE 32 L | HIGH 45 L
- Transport: ±25%

---

### YEAR 2015 CALCULATION

#### Step 3b: Tourism Demand Vector (2015) — Direct from TSA
- **Input**: `TSATable4-TotalInternalTourismConsumption.csv` (TSA 2015-16)
- **Method**: No scaling needed. TSA 2015-16 IS the 2015 demand vector.
- **Process**: Map TSA 24 product categories → 140 SUT products using concordance
- **Output**: `tourism_demand_vector_2015.csv`
- **Note**: Same concordance mapping used as 2022

#### Step 4b: Calculate Indirect TWF (2015)
```python
W  = water_coefficients_140_products (from EXIOBASE 2015, mapped to 140 sectors)
L  = leontief_inverse_L_2015_16      (structural backbone for 2015)
Y  = tourism_demand_vector_2015      (direct from TSA 2015-16)

Total_TWF   = W @ L @ Y
Direct_TWF  = W @ Y
Indirect_TWF = Total_TWF - Direct_TWF
```
- **Key**: Uses EXIOBASE **2015** water coefficients (not 2022)
- **Key**: Uses **2015-16** Leontief inverse (year-matched SUT available from MoSPI)

#### Step 5b: Calculate Direct Operational Water (2015)
Same approach as 2022 but with 2015-specific coefficients:

| Sector | Coefficient | Derivation |
|--------|-------------|-----------|
| Hotels | **1,251 L/night** | Cornell CHSB 2015 India, Measure 8, median (n=77) |
| Restaurants | **30 L/meal** | Lee et al. (2021) baseline |
| Rail | **3.5 L/pax-km** | Same as 2022 |
| Air | **18 L/passenger** | Same as 2022 |

**Hotel coefficient justification**: CHSB 2015 India sample (n=77) gives a direct India-specific median of 1,251 L/night. Higher than the 2022 weighted average (818 L) because the 2015 sample skews toward classified/larger hotels, whereas the 2022 dataset covers a broader mix including limited-service properties.

---

## 8. COMBINING RESULTS

```
Final TWF (each year) = Indirect TWF + Direct TWF

Direct TWF = Hotels + Restaurants + Rail + Air (+ Water Transport if material)

Report:
- Total TWF (billion m³)
- % Indirect vs % Direct
- Per domestic tourist (L/tourist/day)
- Per inbound tourist (L/tourist/day)
- Change 2015 → 2022 (absolute + %)
```

---

## 9. DIRECTORY STRUCTURE

```
twf-calculation/
│
├── 1-input-data/
│   ├── sut/                          # MoSPI Supply-Use Tables
│   │   ├── supply-table-2015-16.csv  # ✅ Downloaded
│   │   ├── USE-TABLE-2015-16.csv     # ✅ Downloaded
│   │   ├── supply-table-2019-20.csv  # ✅ Downloaded
│   │   └── USE-TABLE-2019-20.csv     # ✅ Downloaded
│   ├── tsa/                          # TSA India 2015-16 (4 tables)
│   ├── exiobase-raw/
│   │   ├── IOT_2015_ixi/             # EXIOBASE 2015 (water/F.txt used)
│   │   ├── IOT_2022_ixi/             # EXIOBASE 2022 (water/F.txt used)
│   │   └── output/                   # Extracted India water coefficients
│   ├── nas/
│   │   ├── 2022/                     # NAS 2021-22 (Tables 8.1, 8.9, 1.6)
│   │   └── 2025/                     # NAS 2025 (validation)
│   ├── tourism-statistics/           # India Tourism Statistics 2022
│   ├── water-coefficients/           # Final mapped coefficients (140 products)
│   └── euro26/                       # Eora26 2017 (verification only — confirms zero service water)
│
├── 2-intermediate-calculations/
│   ├── io-table/                     # Z, A, L matrices (2015-16 and 2019-20)
│   ├── concordance/                  # EXIOBASE 163 → SUT 140 mapping
│   └── demand-vectors/               # NAS-updated A_2022, L_2022 matrices + Y_2022 demand vector + NAS growth rates
│
├── 3-final-results/                  # TWF outputs by sector (2022 done; 2015 pending)
│
├── 4-visualizations/                 # Charts (direct/indirect, top sectors, etc.)
│
├── 5-scripts/
│   ├── step1a_sut_to_io_2015.py      # ⏳ Pending — SUT 2015-16 → IO table
│   ├── step1b_sut_to_io_2019.py      # ✅ Done — SUT 2019-20 → IO table
│   ├── step2_create_concordance.py   # ✅ Done — EXIOBASE → SUT mapping
│   ├── step3_construct_tourism_demand_2022.py  # ✅ Done — 2022 demand vector (Y) from TSA + NAS
│   ├── step4_calculate_twf.py        # ✅ Done — Indirect TWF (2022)
│   ├── step4b_visualize_twf.py       # ✅ Done — Visualizations
│   └── [step5_direct_water.py]       # ⏳ NEXT — Direct operational water (both years)
│
└── 6-documentation/
    ├── README.md                     # This file
    ├── TSA-2015-16.pdf
    ├── china-paper.pdf               # Lee et al. 2021
    └── India Tourism Statistics 2023.pdf
```

---

## 10. SCRIPTS STATUS

| Script | Status | Output |
|--------|--------|--------|
| `step1a_sut_to_io_2015.py` | ⏳ Pending | Z, A, L matrices (140×140) for 2015-16 |
| `step1b_sut_to_io_2019.py` | ✅ Complete | Z, A, L matrices (140×140) for 2019-20 |
| `step2_create_concordance.py` | ✅ Complete | Water coefficients for 140 products (2015 + 2022) |
| `step3_construct_tourism_demand_2022.py` | ✅ Complete | 2022 tourism demand vector Y (140 products) |
| `step4_calculate_twf.py` | ✅ Complete | TWF 2022 indirect: ~1.47 billion m³ |
| `step4b_visualize_twf.py` | ✅ Complete | 7 visualization charts |
| `step5_direct_water.py` | ⏳ Pending | Direct operational water (2015 + 2022) |
| `step6_twf_2015.py` | ⏳ Pending | Full TWF 2015 (indirect + direct) |
| `step7_comparison.py` | ⏳ Pending | 2015 vs 2022 comparison + per-tourist metrics |

---

## 11. DIRECT WATER COEFFICIENTS SUMMARY

### Accommodation

| Year | Coefficient | Source |
|------|-------------|--------|
| 2015 | **1,251 L/occupied room/night** | Cornell CHSB 2015 India, Measure 8, median (n=77) |
| 2022 | **818 L/occupied room/night** | Cornell CHSB 2022 India, Measure 8, weighted by India hotel mix |

**CHSB India Measure 8 — Year Comparison**

| Metric | CHSB 2015 (n=77) | CHSB 2022 (n=215) |
|--------|-----------------|-----------------|
| Low | 75 L | 60 L |
| Lower Quartile | 953 L | 497 L |
| Mean | 1,435 L | 1,026 L |
| **Median / Weighted Avg** | **1,251 L** | **818 L** |
| Upper Quartile | 1,797 L | 1,247 L |
| High | 4,089 L | 11,968 L |

*2015: single India-wide median used directly. 2022: segment medians weighted by India hotel mix (Budget 30%, Mid-range 25%, Upscale 25%, Luxury 18%, Resort 2%).*

### Other Sectors
| Sector | Coefficient | Year | Source |
|--------|-------------|------|--------|
| Restaurants | 30 L/meal | 2015 | Lee et al. (2021) |
| Restaurants | 32 L/meal | 2022 | Lee et al. (2021) |
| Rail | 3.5 L/passenger-km | Both | Transport studies |
| Air | 18 L/passenger | Both | Aviation sustainability studies |
| Water Transport | 20 L/passenger | Both | Maritime studies (if material) |

### Excluded Direct Sectors (with justification)
| Sector | Reason |
|--------|--------|
| Road transport | <1% of direct water; cannot separate tourism vs local use |
| Cultural services | Minimal water use (toilets only, ~2-3 L/visitor) |
| Shopping/Retail | Cannot separate tourism spending from resident spending |
| Recreation | Highly variable; insufficient data |

---

## 12. SENSITIVITY ANALYSIS

Required because direct water uses estimated coefficients, not measured data.

| Scenario | Hotels (L/night) | Restaurants (L/meal) | Transport |
|----------|-----------------|---------------------|-----------|
| LOW | 953 (CHSB LQ) | 20 | −25% |
| BASE | 1,251 (CHSB median) | 32 | As stated |
| HIGH | 1,797 (CHSB UQ) | 45 | +25% |

Direct water is ~10-15% of total TWF, so even ±40% uncertainty in direct coefficients yields only ±4-6% uncertainty in total TWF.

---

## 13. EXPECTED RESULTS

| Metric | 2015 (Expected) | 2022 (Current) |
|--------|----------------|----------------|
| Indirect TWF | ~0.9 billion m³ | ~1.47 billion m³ |
| Direct TWF | ~0.15 billion m³ | ~0.13 billion m³ |
| **Total TWF** | **~1.05 billion m³** | **~1.60 billion m³** |
| Indirect share | ~85% | ~92% |
| Direct share | ~15% | ~8% |
| Top indirect sector | Agriculture | Agriculture |
| Top direct sector | Accommodation | Accommodation |
| Hotel coefficient used | 1,251 L/night (CHSB 2015 median) | 818 L/night (CHSB 2022 weighted) |

---

## 14. KNOWN LIMITATIONS

1. **IO table currency**: No published SUT exists for 2022. The 2019-20 IO table is updated to 2022 using NAS sector output indices — the standard and widely accepted method in EEIO literature when an intervening SUT is unavailable (see Temurshoev & Timmer, 2011; Lenzen et al., 2010). This is methodologically superior to using the 2019-20 structure unmodified, as it incorporates observed sectoral output shifts from national accounts. The residual limitation is that NAS-based updating adjusts coefficients proportionally to output but does not capture changes in the technical composition of inputs within a sector — information only a new SUT survey would provide.
2. **EXIOBASE water base year**: EXIOBASE water data is based on 2011 real measurements, extrapolated to 2015 and 2022. Coefficient changes are driven by economic scaling, not re-measured water intensities.
3. **Direct water estimation**: Activity-based coefficients use international benchmarks (Cornell CHSB, Lee et al.) adapted for India. India-specific operational water census data does not exist.
4. **TSA coverage**: TSA 2015-16 covers only Ministry of Tourism approved/classified hotels (1,459 hotels, 79,879 rooms). The unclassified accommodation sector (estimated 50,000+ budget lodges, dharamshalas, homestays) is not reflected.
5. **Eora26 verified**: Eora26 2017 water satellite (WFN rows 2496-2513) confirmed zero direct water for India Hotels & Restaurants sector — same limitation as EXIOBASE.

---

## 15. REFERENCES

```
Lee, L-C., Wang, Y., & Zuo, J. (2021). Water footprint of Chinese tourists: 
  Directions and structure. Journal of Hydrology, 603, 127151.
  https://doi.org/10.1016/j.jhydrol.2021.127151

Stadler, K., et al. (2018). EXIOBASE 3: Developing a Time Series of Detailed 
  Environmentally Extended Multi-Regional Input-Output Tables. 
  Journal of Industrial Ecology, 22(3), 502-515.

Cornell Hotel Sustainability Benchmarking Index (2022/2023). 
  Center for Hospitality Research, Cornell University.
  https://ecommons.cornell.edu/items/f50b30f1-40ea-4c87-95d0-83c8009f6497

MoSPI (2016). Supply-Use Tables 2015-16. Ministry of Statistics and Programme 
  Implementation, Government of India.

MoSPI (2020). Supply-Use Tables 2019-20. Ministry of Statistics and Programme 
  Implementation, Government of India.

MoSPI (2022). National Accounts Statistics 2021-22. Government of India.

Ministry of Tourism (2016). Tourism Satellite Account India 2015-16. 
  Government of India.

UNWTO (2008). Tourism Satellite Account: Recommended Methodological Framework.
  United Nations World Tourism Organization.
```
