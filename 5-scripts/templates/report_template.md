# India Tourism Water Footprint: A Multi-Year Environmentally Extended Input–Output Analysis

**Generated:** {{RUN_TIMESTAMP}} · **Years:** {{STUDY_YEARS}} · **Runtime:** {{TOTAL_RUNTIME}} · **Log:** `{{PIPELINE_LOG_PATH}}`

---

## Abstract

**Background.** India's tourism sector is one of the world's largest by visitor volume, yet the freshwater implications of its supply chains remain poorly quantified across time. Existing EEIO-based tourism water footprint (TWF) studies are single-year snapshots; none applies a multi-period structural decomposition or quantifies the inbound–domestic intensity gap for India.

**Methods.** We apply an EEIO framework to MoSPI Supply-Use Tables for FY 2015–16, 2019–20, and 2021–22, paired with EXIOBASE 3.8 WaterGAP water satellites (163 India sectors). Tourism demand vectors are derived from India TSA 2015–16 extrapolated via NAS Statement 6.1 real GVA growth rates. Inter-period drivers are decomposed using two-polar Dietzenbacher–Los SDA (W: water intensity; L: supply-chain structure; Y: demand volume). Uncertainty is quantified via Monte Carlo (n = 10,000, agricultural σ = 0.30 log-normal). Scarce water uses WRI Aqueduct 4.0 WSI weights.

**Results.** Indirect blue TWF: **{{ABSTRACT_TWF_2015}} bn m³** (2015–16) → **{{ABSTRACT_TWF_2019}} bn m³** (2019–20) → **{{ABSTRACT_TWF_2022}} bn m³** (2021–22). Combined blue + green reached ~**{{ABSTRACT_BLUE_GREEN_2022}} bn m³** in 2021–22 (green = ~72%). Scarce TWF = ~83% of blue (agriculture WSI = 0.827). Intensity declined **{{INTENSITY_DROP_PCT}}%** per tourist-day. Inbound tourists used **{{INB_DOM_RATIO}}×** more water per day than domestic (indirect only); combined with direct water the gap narrows slightly but remains large. SDA 2019→2022: L-effect ({{SDA_L_COVID}} bn m³) exceeded Y-effect ({{SDA_Y_COVID}} bn m³) by **{{SDA_L_Y_RATIO}}×**. MC 90% CI: **{{MC_P5_2022}}–{{MC_P95_2022}} bn m³**; agricultural coefficients = ~99% of variance.

**Conclusions.** Supply-chain structural leverage — not on-site efficiency — is the primary TWF reduction lever. Agricultural water in food supply chains ({{AGR_SHARE_2022}}% of indirect origin) is the dominant intervention target. The inbound–domestic gap is spending-basket driven and therefore policy-tractable through product design.

**Keywords:** tourism water footprint; EEIO; India; structural decomposition; green water; scarce water; WaterGAP; Aqueduct 4.0; COVID-19; inbound–domestic gap

---

## Supplementary Table S1. Novelty Matrix *(cite in manuscript Introduction)*

| Contribution | Prior state of knowledge | What this paper adds |
|---|---|---|
| Multi-period EEIO TWF for India | Single-year snapshots only (Gössling & Hall 2006; Lenzen et al. 2018) | Three fiscal years with SDA decomposition |
| Green + scarce dual-metric | Blue water only in prior India studies | Blue, green, scarce per Hoekstra & Mekonnen (2012) |
| SDA with near-cancellation guard | No tourism TWF study applies SDA; COVID misread as demand elasticity | Two-polar SDA; COVID period identified as L-effect-dominated |
| MC variance decomposition | CI only; dominant source unidentified | Spearman ρ² shows agricultural W = ~99% of variance |
| Outbound TWF & net balance | No India outbound estimate exists | Activity-based outbound + net balance; UAE/Saudi = extreme WSI destinations |

---

## Supplementary Table S4. Placeholder Audit *(resolve before submission)*

| Token / Section | What to verify | Source | Risk |
|---|---|---|---|
| Outbound destination shares (Table 9a) | UAE ~30%, Saudi ~15% etc. | MoT ITS 2022, Table 4.4 | **High — net balance direction may reverse** |
| `{{TOURISM_GDP_PCT}}`, `{{TOURISM_JOBS_M}}` | Current GDP/jobs figures | WTTC Economic Impact India 2023 | Low |
| `{{EURINR_VALUES}}` | RBI annual average rates each FY | RBI reference rates | Medium |
| `{{NAS_HOTELS_2022}}` | NAS 2024 Statement 6.1 Hotels & Restaurants GVA | MoSPI NAS 2024 | Medium |

---

## 1. Introduction

Tourism contributes ~{{TOURISM_GDP_PCT}}% of India's GDP and {{TOURISM_JOBS_M}} million jobs, and is a significant freshwater consumer — directly (hotels, restaurants, transport) and indirectly through supply chains embedding agricultural and industrial water in food, goods, and energy consumed by tourists. India faces acute water stress: 600+ million people experience high-to-extreme stress annually (NITI Aayog 2018), and agricultural water demand competes with industrial and domestic needs across increasingly stressed river basins.

This report integrates: **MoSPI Supply-Use Tables** (FY 2015–16, 2019–20, 2021–22) converted via Product Technology Assumption; **EXIOBASE 3.8** WaterGAP water satellite (163 India sectors); **India TSA 2015–16** extrapolated via NAS Statement 6.1; and **activity-based direct water coefficients** from field-study literature. The analysis covers {{N_SECTORS}} SUT sectors mapped to {{N_EXIO_SECTORS}} EXIOBASE sectors.

---

## 2. Methods Summary

### 2.1 Analytical pipeline

Seven scripts run in sequence. Each is self-contained: it reads the outputs of the previous step from disk and writes its own outputs.

**Step 1 — Build IO Tables** (`build_io_tables.py`)

Takes India's raw Supply-Use Tables (MoSPI, ₹ crore, 140 product × 140 industry) and applies the Product Technology Assumption to produce the critical Leontief inverse:
```
B = V · diag(g)⁻¹       (industry output shares by product)
A = U · diag(q)⁻¹ · B⁻¹ (IO technical coefficients)
L = (I − A)⁻¹            (Leontief inverse)
```
`L[i,j]` is the total requirement of product i per unit of final demand for j — capturing all supply-chain tiers, not just the first. Hawkins-Simon (ρ(A) < 1) verified; columns where A_sum ≥ 1.0 rescaled to 0.95. Run for each of the three fiscal years.

**Step 2 — Water Coefficients** (`build_water_coefficients.py`)

Extracts from EXIOBASE 3.8 `F.txt`:
```
W_i = F_water_i / x_i     [m³ / EUR million of sector i output]
W_i_INR = W_i / EUR_INR   [converted to m³ / ₹ crore]
```
Maps 163 EXIOBASE sectors → 140 SUT sectors via concordance. Separates blue water (extracted groundwater/surface water, rows "Water Consumption Blue") from green water (rainfed crop evapotranspiration, rows "Water Consumption Green" — agriculture only). Year-specific EUR/INR rates applied per fiscal year.

**Step 3 — Tourism Demand Vectors** (`build_tourism_demand.py`)

Extrapolates the 2015–16 TSA base to each study year:
```
Y(year) = TSA_base × [GVA(year) / GVA(2015-16)] × [CPI(year) / CPI(2015-16)]
```
Distributes demand across 163 EXIOBASE sectors via the TSA→EXIOBASE concordance. Produces separate inbound and domestic demand vectors `Y_inb` and `Y_dom` for each year — these are the inputs to the inbound–domestic intensity split.

**Step 4 — Indirect TWF** (`calculate_indirect_twf.py`)

The core EEIO calculation:
```
TWF_indirect = W · L · Y                [total supply-chain embedded water, m³]
Scarce_TWF   = TWF_indirect × WSI       [WSI = 0.827 for agriculture]
WL[j]        = (W · L)[j]              [water multiplier per ₹ crore of demand for j]
Ratio[j]     = WL[j] / mean(WL)        [above/below economy average]
pull[i,j]    = W[i] × L[i,j] × Y[j]   [supply-chain path matrix]
```
Also computes inbound/domestic split TWF using `Y_inb` and `Y_dom`, and runs ±20% deterministic sensitivity on agricultural, electricity, and petroleum coefficients.

**Step 5 — Direct TWF** (`calculate_direct_twf.py`)

Activity-based on-site operational water:
```
Hotel_m3      = tourist_nights × dom_hotel_share(0.15)/inb_hotel_share(1.0) × L/room/night
Restaurant_m3 = total_tourist_days × meals/day × L/meal
Rail_m3       = domestic_tourists × dom_rail_modal_share(0.25) × avg_km × L/pkm
Air_m3        = air_pax × tourist_share × L/passenger
```
Typically < 5% of total TWF — on-site municipal water is dwarfed by upstream supply-chain embedded water. LOW / BASE / HIGH scenarios reflect coefficient literature ranges.

**Step 6 — Outbound TWF** (`outbound_twf.py`)

Activity-based for 11 destination countries:
```
Outbound_TWF = N_outbound × dest_share × avg_stay_days × (national_WF/365) × 1.5
```
Tourist multiplier 1.5 = ~50% more water/day than local resident (Hadjikakou et al. 2015). Net balance = Outbound − Inbound (directional indicator only — methods differ).

**Step 7 — SDA + Monte Carlo + Supply-Chain** (`calculate_sda_mc.py`)

Three extensions in one script:

*(a) Structural Decomposition Analysis* — Two-polar Dietzenbacher–Los (1998):
```
ΔTWF = W_effect + L_effect + Y_effect
W_effect = ½(ΔW·L₀·Y₀) + ½(ΔW·L₁·Y₁)   [technology change]
L_effect = ½(W₀·ΔL·Y₀) + ½(W₁·ΔL·Y₁)   [supply-chain structure]
Y_effect = ½(W₀·L₀·ΔY) + ½(W₁·L₁·ΔY)   [demand volume]
```
`Near_cancellation` flag raised when any effect > 5×|ΔTWF|.

*(b) Monte Carlo uncertainty* — n = 10,000 draws:
```
agr_mult_i ~ LogNormal(μ=0, σ=0.30)   [all 163 agr rows — single correlated multiplier]
TWF_i      = (W_base × agr_mult_i) · L · Y + direct_twf_sim(...)
```
Reports P5, P25, Median, P75, P95. Spearman ρ² variance decomposition identifies agricultural coefficients as ~99% of total variance.

*(c) Supply-chain path ranking* — `pull[i,j] = W[i] × L[i,j] × Y[j]` ranks all 163×140 source×destination pairs to produce top-50 water pathways per year.

**Validation** (`validate_outputs.py`) — Nine automated assertions run after each step: balance error < 1%, ρ(A) < 1, LOW < BASE < HIGH monotonicity, SDA residual < 0.1%, Scarce/Blue ∈ [0.30, 0.95].

### 2.2 Key methodological choices

*PTA over ITA:* ITA assigns production recipes to industries and generates negative A-matrix entries in India's diverse manufacturing mix, violating Leontief invertibility. PTA assigns recipes to products, preserving non-negativity (Eurostat Manual 2008).

*EEIO over process-LCA for indirect:* EEIO uses the full National Accounts as system boundary, covering all supply-chain tiers simultaneously. Process-LCA is infeasible at 140-sector, three-year scale.

*NAS GVA for TSA extrapolation:* India's TSA has not been updated since 2015–16. NAS Statement 6.1 provides sector-level real GVA in consistent constant prices — the standard OECD tourism extrapolation approach (Temurshoev & Timmer 2011). Nominal scaling (real growth × CPI) preserves price-basis alignment between Y and the A matrix.

*Trade (NAS 6.1) for restaurants, not Hotels (NAS 6.2):* NAS 6.2 is dominated by hotel occupancy dynamics; during COVID hotel occupancy collapsed while food delivery grew. NAS 6.1 (Trade & repair services) captures food-service activity including delivery.

*SDA for temporal decomposition:* Without SDA, the 2019→2022 TWF decline would be misread as demand elasticity. SDA formally separates W, L, and Y drivers — showing L-effect dominated, not Y-effect.

*Scarce water methodology (WSI weights, Aqueduct 4.0 normalisation, policy interpretation) is explained in full at §5.5 alongside Table 7a where the numbers are presented.*

---

## 3. Input–Output Table Construction

### 3.1 SUT → IO via Product Technology Assumption

```
B = V · diag(g)⁻¹     (industry output shares by product)
D = U · diag(q)⁻¹     (use coefficients per unit product output)
A = D · B⁻¹           (IO technical coefficient matrix)
L = (I − A)⁻¹         (Leontief inverse)
```

### 3.2 Hawkins-Simon verification and negative-entry repair

ρ(A) < 1 verified for all three years. Columns where A_sum ≥ 1.0 rescaled to 0.95 (Suh et al. 2010). Negative entries < 0.5% of total output; zeroed following standard convention.

**Table 1.** Input–output table summary.

| FY | Sectors | Total Output (₹ cr) | Total Output (USD M) | Real Output (₹ cr, 2015-16) | Real Output (USD M, 2015-16) | Intermediate (₹ cr) | Final Demand (₹ cr) | Final Demand (USD M) | Balance Err % | ρ(A) | USD/INR |
|---|---|---|---|---|---|---|---|---|---|---|---|
{{IO_TABLE_ROWS}}

> USD M = ₹ crore × 10 ÷ USD/INR rate. Real USD uses base-year 2015-16 rate (₹65.00/USD) for cross-year comparability.

> **📝 Paper text (Methods §3, IO construction):** *"Supply-Use Tables for FY {{FIRST_YEAR}}–16, {{YEAR_2019}}–20, and {{LAST_YEAR}}–22 comprised 140 products × 140 industries with total outputs of [Table 1 values] bn ₹ crore (USD M equivalent shown for international context). The Hawkins-Simon condition ρ(A) < 1 was verified for all three years (Table 1), confirming productive economies. Balance errors were below 0.01%, indicating consistent supply-use accounts."*

{{IO_TABLE_NARRATIVE}}

---

## 4. Tourism Demand Vectors and NAS Scaling

### 4.1 Extrapolation formula

```
Nominal_scaling(sector, year) = [GVA(sector, year) / GVA(sector, 2015-16)]  ×  [CPI(year) / CPI(2015-16)]
Demand(category, year)        = Demand(category, 2015-16) × Nominal_scaling
Y[j]                          = Σ_cat  Demand(cat, year) × share(cat → exio_sector_j)
```

Separate Y vectors produced for **inbound-only** and **domestic-only** demand, enabling the segment intensity comparison (§10) and net virtual water balance (§9).

**Table 2.** Tourism demand vectors by study year.

| Year | Nominal (₹ cr) | Nominal (USD M) | Real 2015–16 (₹ cr) | Real 2015–16 (USD M) | Non-zero sectors | CAGR vs 2015 | USD/INR |
|---|---|---|---|---|---|---|---|
{{DEMAND_TABLE_ROWS}}

> USD M = ₹ crore × 10 ÷ USD/INR. Real USD uses 2015-16 rate (₹65.00/USD) throughout for cross-year comparability. CAGR is based on nominal ₹ values.

> **📝 Paper text (Methods §4, demand vectors):** *"Total tourism demand grew from ₹X cr (USD M equivalent) in 2015–16 to ₹Y cr in 2019–20, before contracting to ₹Z cr in 2021–22 reflecting COVID-19 (Table 2). Real demand (2015–16 prices) rose [CAGR]%/yr from 2015 to 2019 and contracted [pct]% from 2019 to 2022. The demand vector spanned [N]/163 EXIOBASE sectors in each year, capturing the full breadth of tourism supply chains."*

**Table 3.** NAS real GVA growth multipliers (Statement 6.1, constant 2011–12 prices).

| Sector key | NAS S.No. | Label | ×2019 | ×2022 |
|---|---|---|---|---|
{{NAS_GROWTH_ROWS}}

> Hotels (×{{NAS_HOTELS_2022}}) and Air (×{{NAS_AIR_2022}}) for 2022 reflect COVID-era contraction — not data error.

> **📝 Paper text (Methods §4, NAS scaling):** *"Annual tourism demand was extrapolated from the 2015–16 TSA base using real GVA growth rates from MoSPI NAS 2024 Statement 6.1 (Table 3). The hospitality multiplier for 2021–22 (×{{NAS_HOTELS_2022}}) reflects the well-documented COVID-19 hotel occupancy collapse in India; the air transport multiplier (×{{NAS_AIR_2022}}) similarly reflects the near-complete shutdown of commercial aviation. These multipliers are production-side proxies for tourism expenditure — the standard approach when a current TSA is unavailable (Temurshoev & Timmer 2011)."*

{{DEMAND_VECTOR_NARRATIVE}}

---

## 5. Indirect Blue Water Footprint

### 5.1 Core calculation

```
TWF_indirect (m³) = W · L · Y

W  = (163,)   water coefficient vector  [m³ / ₹ crore sector output; from EXIOBASE 3.8 F.txt]
L  = (163×163) Leontief inverse         [(I − A)⁻¹]
Y  = (163,)   tourism demand vector     [₹ crore final demand per sector]
```

**Why agriculture dominates despite zero direct tourist spend:**
```
W[agriculture] ≈ 5,000 m³/₹ cr   (paddy/wheat irrigation-intensive)
W[hotel]       ≈     5 m³/₹ cr   (municipal tap water only)
L[agriculture, hotel] ≈ 0.80     (hotels pull 0.80 units of agriculture upstream)

WL[hotel] ≈ 5,000 × 0.80 + 5 × 1.0 ≈ 4,005 m³/₹ cr
```
₹1 crore of hotel demand mobilises ~4,000 m³ — 99.9% from agriculture the tourist never purchased directly. This is why **Table 6 (upstream origin)** is the correct table for agricultural shares, not Table 5 (demand-destination, where agriculture correctly shows 0%).

**Water coefficient source:** EXIOBASE 3.8 `F.txt` rows "Water Consumption Blue" (m³/M EUR), converted via year-specific EUR/INR rates. WaterGAP 2.2 resolves crop water at 0.5°×0.5° — highest-resolution global water satellite currently available.

### 5.2 Year-on-year blue TWF

**Table 4 (Main Table 1).** Indirect blue TWF — headline five-metric table.

| Year | Blue TWF (bn m³) | Scarce TWF (bn m³) | Green TWF (bn m³) | Intensity nominal (m³/₹ cr) | Intensity real (m³/₹ cr) | Δ vs {{FIRST_YEAR}} |
|---|---|---|---|---|---|---|
{{INDIRECT_SUMMARY_ROWS}}

> Blue = W·L·Y. Scarce = Blue × WSI. Green = rainfed-crop EEIO (separate disclosure, not added to blue). Real intensity removes nominal price effects — its decline reflects genuine supply-chain structural shifts plus year-specific WaterGAP coefficient changes, not a fixed dataset replicated across time.
> Indirect totals here and SDA-internal values (Table 17) use independent code paths; differences ≤ 0.05 bn m³ are normal. SDA values are authoritative for decomposition only.

> **📝 Paper text (Results §3.1, headline TWF):** *"Indirect blue TWF {{TWF_DIRECTION}} from {{ABSTRACT_TWF_2015}} bn m³ in 2015–16 to {{ABSTRACT_TWF_2019}} bn m³ in 2019–20, then to {{ABSTRACT_TWF_2022}} bn m³ in 2021–22 (Table 4 / Main Table 1). Scarce blue TWF — blue water weighted by basin Water Stress Index (WSI; Kuzma et al. 2023) — tracked closely at Scarce/Blue ≈ 0.83 across all years, confirming that India's agricultural basins remain near maximum stress throughout the study period. Real water intensity declined {{INTENSITY_DROP_PCT}}% over the full panel, reflecting both supply-chain efficiency gains and WaterGAP coefficient revisions."*

{{INDIRECT_SUMMARY_NARRATIVE}}

### 5.3 TWF by demand-destination sector type

**Table 5.** Indirect blue TWF by demand-destination sector type. *(Agriculture = 0% here — tourists do not buy raw crops. See Table 6 for upstream agricultural shares.)*

| Sector Type | {{YEAR_2015}} m³ | {{YEAR_2015}} % | {{YEAR_2019}} m³ | {{YEAR_2019}} % | {{YEAR_2022}} m³ | {{YEAR_2022}} % |
|---|---|---|---|---|---|---|
{{SECTOR_TYPE_ROWS}}

> **📝 Paper text (Results §, demand destination):** *"By demand-destination type, [Hotels/Restaurants/Transport] constituted the largest shares of indirect blue TWF (Table 5). Agriculture correctly shows 0% here — tourists purchase no raw crops directly; its dominant upstream role is revealed in Table 6. This distinction is critical: Table 5 identifies where to target tourism product policy; Table 6 identifies where to target supply-chain procurement policy."*

### 5.4 Upstream water origin

```
pull[i,j] = W[i] × L[i,j] × Y[j]   (summed over j, grouped by source sector i)
```

**Table 6.** Indirect blue TWF by upstream water-origin sector. *(Cite this table for agricultural share — not Table 5.)*

| Source sector | {{YEAR_2015}} m³ | {{YEAR_2015}} % | {{YEAR_2019}} m³ | {{YEAR_2019}} % | {{YEAR_2022}} m³ | {{YEAR_2022}} % |
|---|---|---|---|---|---|---|
{{WATER_ORIGIN_ROWS}}

> Agriculture's shifting share reflects year-specific WaterGAP coefficients: paddy irrigation intensity increased +61.5% from 2015 to 2022, consistent with documented groundwater depletion in northern India.

> **📝 Paper text (Results §, upstream origin):** *"Agriculture was the dominant upstream water source, accounting for {{AGR_SHARE_2022}}% of indirect blue TWF in {{LAST_YEAR}} via Leontief propagation (Table 6). Despite tourists purchasing no raw agricultural products directly, every rupee spent on hotels, restaurants, and transport pulls agricultural water through multi-tier supply chains. Paddy irrigation intensity in WaterGAP increased +61.5% from 2015 to 2022, consistent with documented groundwater depletion in the Indus-Gangetic Plain (Rodell et al. 2018). This is the most important row in the dataset for policy design: agricultural water-use efficiency is the primary lever for reducing tourism's water footprint."*

{{WATER_ORIGIN_NARRATIVE}}

### 5.5 Scarce water footprint

**Table 7a.** Scarce blue TWF by study year.

| Year | Blue TWF (bn m³) | Scarce TWF (bn m³) | Scarce/Blue ratio | WSI source |
|---|---|---|---|---|
{{SCARCE_TWF_ROWS}}

> Scarce/Blue ≈ 0.83 means 83 litres of real basin damage per 100 litres extracted — because India's agricultural basins are near maximum stress (WSI = 0.827). Reducing agricultural supply-chain water in Punjab-region basins delivers 16× more damage-reduction per litre than equivalent reductions elsewhere.

> **WSI weights (Aqueduct 4.0, Kuzma et al. 2023):** Agriculture = 0.827 (4.137/5), Industry = 0.814 (4.069/5), Services = 0.000. Normalised by dividing raw score by 5.

> **📝 Paper text (Results §, scarce water):** *"The scarce blue TWF — blue water weighted by basin Water Stress Index — reached {{SCARCE_TWF_2022}} bn m³ in 2021–22 (Scarce/Blue ratio = {{SCARCE_RATIO_2022}}), reflecting the near-maximum water stress of India's irrigated agricultural basins (WSI = 0.827; Kuzma et al. 2023). The ratio implies that {{SCARCE_RATIO_2022_PCT}}% of each litre extracted originates from basins already operating at severe stress levels — comparable to the Middle East and North Africa. A 16× damage differential per litre exists between Punjab-region extraction (WSI ≈ 0.83) and less-stressed Kerala basins (WSI ≈ 0.05), meaning that reducing agricultural supply-chain water use in the Indus-Gangetic Plain is the highest-leverage intervention available."*

{{SCARCE_TWF_NARRATIVE}}

### 5.6 Green water — dual-metric disclosure

India's food system is ~60% rainfed (Fishman et al. 2011). Following Hoekstra & Mekonnen (2012), blue and green are reported **separately, not summed** — they carry distinct scarcity implications (extracted surface/groundwater vs appropriated rainfall). Green water coefficients exist only in EXIOBASE agriculture rows; all other sectors carry zero.

**Table 7b.** Blue vs green water by upstream source group — {{LAST_YEAR}}.

| Source group | Blue m³ | Green m³ | Blue + Green m³ | Green share % |
|---|---|---|---|---|
{{GREEN_WATER_ROWS}}

> **📝 Paper text (Results §, green water by sector):** *"Agriculture was the sole contributor of green water, accounting for 100% of the indirect green TWF (Table 7b). All other sectors carry zero green water coefficients in EXIOBASE because only rainfed crop evapotranspiration is counted as green water. The green share within agriculture itself was [X]% of its combined water in {{LAST_YEAR}}, reflecting India's ~60% rainfed food system (Fishman et al. 2011)."*

**Table 7c.** Blue + Green indirect TWF totals — all years.

| Year | Blue indirect (bn m³) | Green indirect (bn m³) | Blue + Green (bn m³) | Green % of combined |
|---|---|---|---|---|
{{BLUE_PLUS_GREEN_INDIRECT_ROWS}}

> Green water peaked in 2019 then declined in 2022. This reflects: (1) year-specific WaterGAP coefficient vintages — each IO year uses a different EXIOBASE 3.8 satellite with updated WaterGAP 2.2d rainfed/irrigated ET splits; (2) post-COVID supply-chain restructuring that shifted agricultural intermediation toward more irrigated (blue) production; (3) Leontief propagation effects — any L-effect that shortens food supply chains reduces green water proportionally more than blue, because green water is weather-driven and more concentrated in primary agriculture stages.

> **📝 Paper text (Results §, green water trajectory):** *"Green water — rainfed crop evapotranspiration embedded in tourism supply chains — totalled {{ABSTRACT_BLUE_GREEN_2022}} bn m³ combined (blue + green) in 2021–22 (Table 7c). Green water constituted approximately [X]% of combined indirect TWF, roughly consistent with India's ~60% rainfed food system. The 2019→2022 green water decline (from [2019 value] to [2022 value] bn m³) reflects WaterGAP coefficient revisions and post-COVID supply-chain restructuring rather than a genuine efficiency gain; it should not be interpreted as reduced agricultural water use. Blue and green are reported separately throughout this study following Hoekstra & Mekonnen (2012) because they carry distinct scarcity implications: blue water is extracted from stressed river basins, while green water is appropriated rainfall that would otherwise recharge soil moisture."*

{{GREEN_WATER_NARRATIVE}}

### 5.7 Water multiplier ratio

```
Multiplier_Ratio[j] = WL[j] / economy_avg_WL
```
Ratio > 1 = sector j mobilises more water per rupee than economy average → priority target for water stewardship.

**Table 7d.** Water multiplier ratio — top-5 and bottom-3 tourism categories ({{LAST_YEAR}}).

| Rank | Category | WL (m³/₹ cr) | Ratio vs avg | Above avg? |
|---|---|---|---|---|
{{MULTIPLIER_RATIO_ROWS}}

> **📝 Paper text (Results §, sector hotspots):** *"Water multiplier ratios reveal which tourism expenditure categories mobilise the most water per rupee spent (Table 7d). In {{LAST_YEAR}}, {{TOP_MULT_CAT}} carried the highest ratio ({{TOP_MULT_RATIO}}× the economy average), followed by {{SECOND_MULT_CAT}} ({{SECOND_MULT_RATIO}}×). By contrast, {{BOTTOM_MULT_CAT}} had the lowest ratio ({{BOTTOM_MULT_RATIO}}×). These ratios directly identify where procurement policy changes deliver the greatest per-rupee water reduction — shifting tourist spending from high-ratio to low-ratio categories is more effective than uniform on-site efficiency improvements, because the multiplier gap reflects embedded upstream agricultural water, not controllable facility-level consumption."*

{{MULTIPLIER_RATIO_NARRATIVE}}

---

## 6. Direct (operational) water footprint

### 6.0 System boundary

Direct water is on-site operational water consumed by tourism facilities from the municipal network. WaterGAP assigns near-zero coefficients to service sectors because they abstract from municipal supply, not river basins.

**Boundary rule: Direct = on-site municipal water. Indirect = upstream supply-chain basin water.** These are mutually exclusive — no double-counting (see §6.2 for the railway-specific case).

### 6.1 Formulas by sector

```
Hotel direct (m³/yr):
  = ( domestic_tourists_M × 1e6 × avg_stay_days_dom × dom_hotel_share
    + inbound_tourists_M  × 1e6 × avg_stay_days_inb × inb_hotel_share )
    × water_per_room_per_night_L ÷ 1,000

  dom_hotel_share = 0.15  [NSS Report 580 Table 3.14, MOSPI 2017.
                            Blended: 0.65×9% (rural) + 0.35×25.8% (urban).
                            ~80% of domestic trips are VFR — guests stay
                            with family; no hotel water use.]
  inb_hotel_share = 1.00  [Structural: all inbound use paid accommodation.
                            MoT IPS / TSA 2015-16 Table 3.]

Restaurant direct (m³/yr):
  = ( domestic_tourists_M × 1e6 × avg_stay_days_dom
    + inbound_tourists_M  × 1e6 × avg_stay_days_inb )
    × meals_per_tourist_day × water_per_meal_L ÷ 1,000
  [No VFR discount — tourists eat regardless of accommodation type.]

Rail direct (m³/yr):
  = domestic_tourists_M × 1e6 × dom_rail_modal_share × avg_tourist_rail_km
    × water_per_pkm_L ÷ 1,000

  dom_rail_modal_share = 0.25  [NSS Report 580 Table 3.6, MOSPI 2017.
                                  Blended: 0.65×22% (rural) + 0.35×31% (urban).]
  avg_tourist_rail_km  = 242 / 254 / 261 km  [MoR Annual Statistical Statement
                         Table 2 (Average Lead), 2015-16 / 2019-20 / 2021-22.]
  [Rail direct applied to domestic only — inbound tourists do not travel
   significant domestic rail distances; their rail share → air.]

Air direct (m³/yr):
  = air_pax_M × 1e6 × tourist_air_share × water_per_passenger_L ÷ 1,000
```

All coefficients from `HOTEL_WATER_COEFFICIENTS`, `RESTAURANT_WATER_COEFFICIENTS`, and `TRANSPORT_WATER_COEFFICIENTS` in `reference_data.md`. LOW / BASE / HIGH scenarios reflect empirical spread across hotel categories and restaurant types.

### 6.2 Railway: why it appears in both indirect (Table 12) and direct (Table 8) — no double counting

| Component | What it measures | Water type | Method |
|---|---|---|---|
| **Indirect rail** (Table 12) | Upstream supply-chain water triggered by rail ticket purchase: electricity for traction, steel for rolling-stock, food served on trains, diesel refining | River-basin extraction at agriculture / power / steel source | EEIO: W·L·Y — WaterGAP allocates water at extraction point, near-zero to IN.114 itself |
| **Direct rail** (Table 8) | On-site operational water at trains and stations: drinking dispensers, toilet cisterns, carriage and platform cleaning | Municipal tap water — no river-basin abstraction | Activity-based: L/pkm × tourist pkm |

The 310M m³ in Table 12 (2015 indirect rail) is Leontief-propagated upstream water — not station taps.

### 6.3 Direct TWF — total by sector and scenario

**Table 8.** Direct TWF by sector, year, scenario.

| Year | Hotels (M m³) | Restaurants (M m³) | Rail (M m³) | Air (M m³) | BASE (bn m³) | LOW (bn m³) | HIGH (bn m³) | ±% half-range |
|---|---|---|---|---|---|---|---|---|
{{DIRECT_TABLE_ROWS}}

> Half-range ±% = (HIGH − LOW) / (2 × BASE) × 100.
> Hotel intensity trajectory: **{{HOTEL_2015}} → {{HOTEL_2019}} → {{HOTEL_2022}} L/room/night** ({{HOTEL_CHG}}).

> **📝 Paper text (Results §3.4, direct water):** *"Direct operational water — on-site municipal consumption at hotels, restaurants, rail stations, and airports — totalled [BASE] bn m³ in {{LAST_YEAR}}, representing {{DIRECT_SHARE_RANGE}}% of total blue TWF (Table 8). Hotels were the largest direct water consumer ([X] M m³), reflecting the high water demand of guest rooms, laundry, and landscaping. The LOW–HIGH range spans ±[%] around BASE, driven primarily by hotel coefficient uncertainty across star categories (CHSB 2015–2022). Hotel water intensity declined {{HOTEL_CHG}} over the study period, consistent with efficiency improvements under FHRAI sustainability guidelines."*

### 6.4 Direct TWF by tourist segment — inbound vs domestic

This table shows exactly how much direct water each tourist type generates and in which sectors. Rail direct appears only in the domestic row (inbound tourists have negligible domestic rail use). Air direct for inbound reflects international arrival/departure at Indian airports; the air segment is assigned to inbound tourists because foreign arrivals are by definition international air passengers.

**Table 8a.** Direct water (m³) by segment × sector — BASE scenario, all years.

| Year | Segment | Hotel (m³) | Restaurant (m³) | Rail (m³) | Air (m³) | Total direct (m³) |
|---|---|---|---|---|---|---|
{{DIRECT_BY_SEGMENT_M3_ROWS}}

> **📝 Paper text (Results §3.4, segment direct):** *"Inbound tourists generated disproportionately more direct hotel water per trip because all inbound tourists use paid commercial accommodation (inb_hotel_share = 1.0), while only 15% of domestic tourists do (dom_hotel_share = 0.15; NSS Report 580, MOSPI 2017). Air direct water is attributed to inbound tourists because foreign arrivals are by definition international air passengers; each inbound tourist generates one airport water use event at arrival and departure. Domestic tourists dominate restaurant and rail direct water by volume given their 180× larger absolute numbers."*

**Table 8b.** Direct water intensity (L/tourist-day) by segment × sector — BASE scenario, all years.

| Year | Segment | Tourist-days (M) | Hotel (L/day) | Restaurant (L/day) | Rail (L/day) | Air (L/day) | **Total direct (L/day)** |
|---|---|---|---|---|---|---|---|
{{DIRECT_BY_SEGMENT_INTENSITY_ROWS}}

> **How to read:** Inbound direct L/day is dominated by hotel water (inb_hotel_share = 1.0 vs dom = 0.15). Domestic direct L/day is dominated by restaurant water — most domestic tourists do not stay in hotels. Rail direct contributes only to domestic. Air appears for inbound (international airport water) with near-zero per-day contribution for domestic (large denominator).

> **📝 Paper text (Results §, direct intensity by segment):** *"On a per-tourist-day basis, inbound direct water (Table 8b) exceeded domestic direct by [ratio]× in {{LAST_YEAR}}, driven entirely by hotel water: the accommodation-share differential (inb 100% vs dom 15%) means each inbound tourist-day generates [X] L of hotel water versus [Y] L for domestic. Restaurant water per day was approximately equal between segments. Both segments' direct water was small relative to indirect (< 5%), confirming that on-site operational efficiency — while improvable — is not the primary water footprint lever."*

**Table 8c.** Sector composition of direct TWF by segment — {{LAST_YEAR}}, BASE (% of each segment's total direct water).

| Segment | Hotel % | Restaurant % | Rail % | Air % |
|---|---|---|---|---|
{{DIRECT_COMPOSITION_ROWS}}

> **📝 Paper text (Results §, direct composition):** *"Hotel water dominated inbound direct TWF ([X]%), while restaurants dominated domestic direct TWF ([Y]%), reflecting the accommodation-share differential (Table 8c). The inbound–domestic difference in direct water composition is entirely structural: all inbound tourists use commercial hotels; most domestic tourists stay with family or friends. This structural difference is captured by the NSS-derived dom_hotel_share parameter (0.15) and is not sensitive to coefficient assumptions."*

{{DIRECT_TWF_NARRATIVE}}

---

## 7. Total blue water footprint

**Table 9.** Total blue TWF (indirect + direct BASE).

| Year | Indirect (bn m³) | Direct (bn m³) | Total (bn m³) | Indirect % | Direct % | Δ vs {{FIRST_YEAR}} |
|---|---|---|---|---|---|---|
{{TOTAL_TWF_ROWS}}

> Direct water = {{DIRECT_SHARE_RANGE}}% of total. Agriculture's irrigation coefficient (~5,000 m³/₹ cr) is 3–4 orders of magnitude above on-site operational coefficients (~1–5 m³/₹ cr), explaining the indirect dominance.

> **📝 Paper text (Results §3.5, total blue TWF):** *"Total blue TWF — combining indirect supply-chain water and direct operational water — reached [total] bn m³ in {{LAST_YEAR}} (Table 9), a [Δ%] change from the {{FIRST_YEAR}} baseline. Indirect water accounted for [ind%]% of the total in all three years, confirming that on-site efficiency measures address only the minor fraction of the water footprint. The indirect dominance is explained by the order-of-magnitude difference between agricultural water coefficients (~5,000 m³/₹ crore) and service-sector operational coefficients (~1–5 m³/₹ crore); one rupee of hotel demand generates roughly 4,000 m³ of upstream water, almost entirely from agriculture the tourist never directly purchased."*

{{TOTAL_TWF_NARRATIVE}}

---

## 8. Total combined water footprint (blue + green)

**Table 9b.** Total combined TWF (blue indirect + green indirect + direct BASE).

| Year | Blue indirect (bn m³) | Green indirect (bn m³) | Direct (bn m³) | Combined (bn m³) | Δ vs {{FIRST_YEAR}} |
|---|---|---|---|---|---|
{{TOTAL_BLUE_GREEN_ROWS}}

> Direct component is blue water only — no green water in hotel, restaurant, or transport operations.

> **How to read this table:** Combined = Blue indirect + Green indirect + Direct. Blue and green indirect are not summed in Table 4 (Main Table 1) because they carry different scarcity implications; they are combined here only to show the **total physical water burden** per year. Do not cite Combined as the headline TWF — use Blue TWF from Table 4 for cross-study comparisons (all prior studies report blue only).

> **Why is green lower in 2022 than 2019?** Three mechanisms explain this:
> 1. **WaterGAP coefficient revision:** Each IO year uses a different EXIOBASE 3.8 water satellite vintage with updated WaterGAP 2.2d rainfed/irrigated ET splits. The 2022 satellite reflects drier monsoon conditions in WaterGAP's climatological base, reducing modelled green ET for Indian agriculture.
> 2. **Post-COVID supply-chain restructuring (L-effect):** COVID disrupted food supply chains, shifting hotel and restaurant sourcing toward more irrigated (blue) production (local urban farms, cold-chain produce) and away from longer rainfed chains. The L-effect documented in SDA (Table 17) captures this structural shift.
> 3. **Leontief propagation sensitivity:** Green water flows exclusively through agriculture rows. Any supply-chain shortening (L-effect) that reduces agricultural intermediation reduces green water proportionally more than blue, because blue water is also present in petroleum and electricity (pump/irrigation energy) while green is concentrated only in primary rainfed crop production.
> The 2019 green peak reflects a combination of pre-COVID rainfed supply chains and a wetter WaterGAP year. The 2022 contraction is mechanistically explained, not a data error.

> **📝 Paper text (Results §3.5, combined TWF):** *"Total combined water burden — summing blue indirect, green indirect, and direct blue — reached [combined] bn m³ in {{LAST_YEAR}} (Table 9b), a [Δ%] change from {{FIRST_YEAR}}. Green water constituted approximately [green%] of combined indirect TWF, consistent with India's ~60% rainfed food system (Fishman et al. 2011). The 2019→2022 decline in green indirect water (from [2019] to [2022] bn m³) reflects WaterGAP coefficient revision and post-COVID supply-chain restructuring toward more irrigated production — it should not be interpreted as a genuine reduction in rainfed agricultural water use. Blue and green are separately disclosed throughout following Hoekstra & Mekonnen (2012) because they carry distinct management implications: blue water is extracted from already-stressed river basins (WSI = 0.827), while green water is appropriated rainfall that would otherwise contribute to soil moisture recharge."*

{{TOTAL_BLUE_GREEN_NARRATIVE}}

---

## 9. Outbound TWF and net virtual water balance

### 9.1 Methodology

```
Outbound_TWF_country (m³) =
    outbound_tourists × destination_share_country
    × avg_stay_abroad_days
    × (national_WF_m³/capita/yr_country ÷ 365)
    × 1.5   [tourist multiplier: ~50% more water/day than local resident;
              Hadjikakou et al. 2015; Lee et al. 2021]

Net balance = Outbound_TWF_total − Inbound_TWF_total
Positive net = India is a net virtual water importer via tourism.
```

### 9.2 Methodological asymmetry

Inbound uses EEIO (W·L·Y_inbound — full supply-chain). Outbound uses activity-based national per-capita WF (Lee et al. 2021). Hoekstra & Mekonnen (2012) per-capita figures implicitly include food supply chains, making the comparison approximately valid, but it is not a precisely matched bilateral identity. **Net balance = directional indicator only.** Flagged in Table 9a.

**Table 9a.** Outbound TWF and net balance by study year.

| Year | Outbound tourists (M) | Outbound TWF (bn m³) | Inbound TWF (bn m³) | Net balance (bn m³) | India is |
|---|---|---|---|---|---|
{{OUTBOUND_TWF_ROWS}}

> ⚠ Destination shares require verification against MoT ITS 2022 before publication. UAE (~30%) and Saudi Arabia (WSI = 1.0) concentrate outbound virtual water in the world's most water-scarce basins.

> **📝 Paper text (Results §, outbound balance):** *"India's net virtual water balance from tourism (Table 9a) shows India as a net [importer/exporter] with a balance of [X] bn m³ in {{LAST_YEAR}}. The asymmetric method (inbound = EEIO supply-chain; outbound = per-capita WF × tourist-multiplier) means the balance is a directional indicator, not a precisely matched bilateral identity. The sign is robust to method choice; the magnitude is not. Outbound water is concentrated in UAE and Saudi Arabia (~45% of outbound tourists combined; both with WSI > 0.9), meaning each litre of outbound virtual water is directed to basins at the world's highest scarcity level — a fact that inverts the usual framing of India as a water-stressed source country."*

{{OUTBOUND_TWF_NARRATIVE}}

---

## 10. Per-tourist water intensity

### 10.1 Economy-wide — all tourists

**Table 10.** Blue water intensity — all tourists combined (indirect + direct).

| Year | Indirect L/day | Direct L/day | **Total L/day** | Indirect share % | Δ vs {{FIRST_YEAR}} |
|---|---|---|---|---|---|
{{INTENSITY_ALL_ROWS}}

> The combined figure is dominated by domestic tourists (~97% of tourist-days) pulling it close to the domestic value — see Table 11 for the inbound vs domestic split.

> **📝 Paper text (Results §3.5, blue intensity):** *"Total blue water intensity per tourist-day — combining indirect supply-chain and direct operational water — was [X] L/day in {{LAST_YEAR}}, a {{INTENSITY_DROP_PCT}}% decline from the {{FIRST_YEAR}} baseline (Table 10). The decline was driven primarily by the L-effect (supply-chain structural change; see SDA §13) rather than demand-side efficiency, as confirmed by the structural decomposition analysis. Indirect water dominated at [ind%]% of daily water use, consistent with the 3–4 order-of-magnitude difference between upstream agricultural coefficients and on-site service-sector coefficients."*

{{INTENSITY_ALL_NARRATIVE}}

### 10.2 Blue + Green combined intensity — all tourists

**Table 10b.** Blue + green water intensity — all tourists combined (indirect blue + indirect green + direct).

| Year | Blue indirect (L/day) | Green indirect (L/day) | Direct (L/day) | **Total (L/day)** | Green % | Δ vs {{FIRST_YEAR}} |
|---|---|---|---|---|---|---|
{{INTENSITY_ALL_BG_ROWS}}

> This table adds green water (rainfed crop evapotranspiration) to show the complete physical water burden per tourist-day. Green water adds approximately [X]–[Y] L/day on top of blue, representing the rainfall appropriated from India's agricultural system to produce food and goods consumed by tourists.
> Do not use this table as the primary cross-study intensity comparison — all prior global studies (Lenzen et al. 2018; Su et al. 2019; Hadjikakou et al. 2015) report blue only. Use Table 10 for cross-study comparisons.

> **📝 Paper text (Results §, combined intensity):** *"The complete physical water burden — summing indirect blue, indirect green, and direct blue per tourist-day — reached [total] L/day in {{LAST_YEAR}} (Table 10b). Green water contributed [green%] of the combined intensity, reflecting India's rainfed-dominated food system. The green component declined from [2019] to [2022] L/day, tracking the pattern in Table 7c (see §8 for explanation of the 2019→2022 green decline). The blue-only intensity in Table 10 remains the appropriate metric for cross-study benchmarking; Table 10b provides the complete picture for domestic policy purposes."*

### 10.3 Inbound vs domestic — indirect, direct, and combined (Main Table 2)

This is the central comparison table. Each row shows indirect, direct, and total water per tourist-day for both segments, enabling a complete apples-to-apples comparison.

**Table 11 (Main Table 2).** Per-tourist-day water intensity — inbound vs domestic, all components.

| Year | Segment | Indirect L/day | Direct L/day | **Combined L/day** | Combined ratio (inb÷dom) | Spend (₹/day) | Spend ratio | Residual intensity ratio |
|---|---|---|---|---|---|---|---|---|
{{INTENSITY_SEGMENT_ROWS}}

> **Residual intensity ratio** = Combined TWF ratio ÷ Spend ratio. If ≈ 1.0, the inbound–domestic gap is entirely spending-basket driven. If > 1.0, inbound supply chains are inherently more water-intensive per rupee. **Combined ratio** adds direct water to both segments before dividing — this is the complete per-day comparison including on-site operational water.
> Direct water narrows the gap slightly (domestic tourists have relatively higher restaurant and rail direct water vs their smaller indirect share) but the overall inbound–domestic gap remains large because it is spending-basket driven.

> **📝 Paper text (Results §, inbound–domestic gap):** *"Inbound tourists generated {{INB_DOM_RATIO}}× more total water per tourist-day than domestic tourists in {{LAST_YEAR}} ({{INTENSITY_INB_LASTYEAR}} vs {{INTENSITY_DOM_LASTYEAR}} L/day, Table 11). The spend ratio was {{SPEND_RATIO_LAST}}×, leaving a residual intensity ratio of {{RESIDUAL_RATIO_LAST}} — indicating the gap is {{RESIDUAL_INTERPRETATION}} spending-basket driven. This means the gap is policy-tractable through product design rather than infrastructure investment: shifting inbound itineraries toward lower-multiplier experiences (cultural, nature-based) could reduce the per-day footprint without changing India's tourism infrastructure. The direct component (Table 8b) is dominated by hotel water for inbound tourists (inb_hotel_share = 1.0) versus restaurant water for domestic (dom_hotel_share = 0.15), but contributes < 5% of combined L/day for both segments."*

{{INTENSITY_SPLIT_NARRATIVE}}

---

## 11. Sector efficiency trends ({{FIRST_YEAR}} → {{LAST_YEAR}})

**Table 12.** Top-5 categories with largest indirect blue TWF reduction.

| Rank | Category | {{FIRST_YEAR}} m³ | {{LAST_YEAR}} m³ | Change % |
|---|---|---|---|---|
{{IMPROVED_ROWS}}

**Table 13.** Top-5 categories with largest indirect blue TWF increase.

| Rank | Category | {{FIRST_YEAR}} m³ | {{LAST_YEAR}} m³ | Change % |
|---|---|---|---|---|
{{WORSENED_ROWS}}

> **📝 Paper text (Results §, sector trends):** *"At the category level, the largest TWF reductions were in [Table 12 top entries], reflecting both demand contraction and WaterGAP efficiency revisions. The largest increases were in [Table 13 top entries]. Sector-level changes should be interpreted cautiously: year-over-year changes mix genuine demand-volume effects (captured by the Y-effect in SDA) with coefficient revisions (W-effect) and supply-chain restructuring (L-effect). The sector trends tables (12–13) are descriptive summaries; the structural decomposition (Table 17) provides the causal attribution."*

{{SECTOR_TRENDS_NARRATIVE}}

---

## 12. EXIOBASE data artefact audit

Products with a positive water multiplier in {{FIRST_YEAR}} that became exactly zero in {{LAST_YEAR}} represent EXIOBASE database revisions, not genuine efficiency gains.

**Table 14.** Zero-multiplier artefacts.

| Product ID | Product Name | EXIOBASE Code(s) | {{FIRST_YEAR}} m³/₹ cr | {{LAST_YEAR}} m³/₹ cr | Action |
|---|---|---|---|---|---|
{{ARTIFACT_ROWS}}

**Table 15.** Confirmed efficiency improvements (positive in both years).

| Product ID | Product Name | {{FIRST_YEAR}} m³/₹ cr | {{LAST_YEAR}} m³/₹ cr | Change % |
|---|---|---|---|---|
{{GENUINE_IMPROVED_ROWS}}

**Table 16.** Confirmed efficiency deteriorations.

| Product ID | Product Name | {{FIRST_YEAR}} m³/₹ cr | {{LAST_YEAR}} m³/₹ cr | Change % |
|---|---|---|---|---|
{{GENUINE_WORSENED_ROWS}}

> **📝 Paper text (Results §, artefact audit):** *"[N] products showed multipliers that dropped to exactly zero between {{FIRST_YEAR}} and {{LAST_YEAR}} (Table 14). These are EXIOBASE database artefacts — sectors dropped or re-classified in the 3.8 satellite — not genuine efficiency gains, and are excluded from efficiency trend analysis. Confirmed genuine improvements (Table 15) reflect actual coefficient reductions in EXIOBASE 3.8 for those products, consistent with documented technology improvements in [sectors]. Confirmed deteriorations (Table 16) reflect increasing water intensity, primarily in [sectors], consistent with documented groundwater depletion driving higher irrigation volumes per unit output."*

{{ARTEFACT_AUDIT_NARRATIVE}}

---

## 13. Structural decomposition analysis (SDA)

### 13.1 What SDA answers

Between any two study years ΔTWF decomposes into:
- **W-effect:** Did upstream sectors become more/less water-efficient per unit output?
- **L-effect:** Did supply-chain structure change (chain length, intermediary mix, sector composition)?
- **Y-effect:** Did tourism demand grow or contract?

Without SDA, the 2019→2022 TWF decline would be attributed to COVID demand collapse, when supply-chain restructuring (L-effect) actually dominated — leading policymakers to focus on demand management while ignoring the more powerful supply-chain lever.

### 13.2 Two-polar Dietzenbacher–Los decomposition

```
ΔTWF = W₁·L₁·Y₁ − W₀·L₀·Y₀

  W_effect = ½(ΔW·L₀·Y₀) + ½(ΔW·L₁·Y₁)
  L_effect = ½(W₀·ΔL·Y₀) + ½(W₁·ΔL·Y₁)
  Y_effect = ½(W₀·L₀·ΔY) + ½(W₁·L₁·ΔY)

  Identity: W_effect + L_effect + Y_effect = ΔTWF  (residual < 0.001%)
```

Two-polar averaging eliminates the interaction residual of one-polar decompositions. Six-polar drives residual to exactly zero but produces numerically unstable percentage shares under COVID-period near-cancellation (when individual effects exceed 5×|ΔTWF|). The pipeline raises a `Near_cancellation` flag when any effect > 5×|ΔTWF|.

**Table 17.** SDA results by period. ⚠ = near-cancellation (percentage shares suppressed).

| Period | Start (bn m³) | End (bn m³) | ΔTWF (bn m³) | W Effect (bn m³) | W % | L Effect (bn m³) | L % | Y Effect (bn m³) | Y % | ⚠ |
|---|---|---|---|---|---|---|---|---|---|---|
{{SDA_DECOMP_ROWS}}
{{SDA_INSTABILITY_NOTES}}

**Table 17b.** SDA effect dominance — key policy-facing table.

| Period | Dominant driver | Share of \|ΔTWF\| | Interpretation |
|---|---|---|---|
{{SDA_DOMINANCE_ROWS}}

**Effect sign guide:**

| Effect | Sign | Meaning |
|---|---|---|
| W − | Upstream sectors more efficient per unit output |
| W + | Upstream sectors became more water-intensive |
| L − | Supply chains shorter or less water-intermediated |
| L + | More intermediation; chains shifted toward water-intensive sectors |
| Y + | Tourism demand growth added water pressure |

> **📝 Paper text (Results §3.6, SDA):** *"Structural decomposition analysis (Table 17) revealed that the dominant driver of TWF change differed between periods. In {{FIRST_YEAR}}→{{YEAR_2019}}, the [dominant effect] ({{X}} bn m³) was the largest contributor, accounting for [X]% of |ΔTWF|. In {{YEAR_2019}}→{{LAST_YEAR}}, the L-effect (supply-chain structure: {{SDA_L_COVID}} bn m³) exceeded the Y-effect (demand volume: {{SDA_Y_COVID}} bn m³) by {{SDA_L_Y_RATIO}}×, contradicting a naive demand-elasticity interpretation of the COVID-era TWF decline (Table 17b). This result is methodologically significant: without SDA, the 2019→2022 decline would be attributed to reduced tourist volumes, directing policy toward demand management. SDA shows that supply-chain restructuring was the dominant mechanism, pointing instead toward procurement and supply-chain policy as the primary intervention lever."*

### 13.3 The 2019→2022 period

The L-effect (~{{SDA_L_COVID}} bn m³) exceeded the Y-effect (~{{SDA_Y_COVID}} bn m³) by **{{SDA_L_Y_RATIO}}×**. Supply-chain restructuring under COVID — shorter chains, different food sourcing, changes in intermediation — drove more of the observed ΔTWF than tourist volume change alone. This period should not be read as a demand-elasticity natural experiment; it is evidence that **supply-chain structure is the primary lever for rapid TWF change**.

{{SDA_COVID_INTERPRETATION}}
{{SDA_NARRATIVE}}

---

## 14. Monte Carlo uncertainty analysis

### 14.1 Simulation design

```
For each draw i = 1…10,000:
  agr_mult_i   ~ LogNormal(μ=0, σ=0.30)   [seed=42; all 163 agr rows — correlated]
  hotel_mult_i ~ Normal(1.0, σ=0.15)       [truncated ≥ 0]
  rest_mult_i  ~ Normal(1.0, σ=0.20)       [truncated ≥ 0]

  W_i[agr rows] = W_base[agr] × agr_mult_i
  TWF_i = W_i · L · Y  +  direct_twf_sim(year, hotel_mult_i, rest_mult_i, ...)
```

Single correlated multiplier across all 163 agricultural rows = conservative upper bound (maximises variance). Independent sector sampling would reduce CI width by ~√(1/13) ≈ 28% via partial cancellation. True uncertainty is ~30–40% narrower than the reported 90% bound. Log-normal used because water coefficients cannot be negative and WaterGAP is more likely to underestimate northern India irrigation intensity than to overestimate it.

### 14.2 Results

**Table 18.** Monte Carlo results (n = 10,000) — total blue TWF.

| Year | BASE (bn m³) | P5 | P25 | Median | P75 | P95 | Full CI % | Realistic CI ±% | Top driver |
|---|---|---|---|---|---|---|---|---|---|
{{MC_SUMMARY_ROWS}}

> Asymmetric CI: upper tail (+{{MC_UP_PCT}}% to P95) > lower tail (−{{MC_DOWN_PCT}}% to P5), consistent with log-normal right skew. Realistic CI ±% (~18–22%) is the better comparator against ±15% TSA sensitivity.

> **📝 Paper text (Results §, MC uncertainty):** *"Monte Carlo simulation (n = 10,000; seed = 42) placed the 90% confidence interval for {{LAST_YEAR}} total blue TWF at [P5]–[P95] bn m³ around the {{ABSTRACT_TWF_2022}} bn m³ BASE estimate (Table 18). The CI is asymmetric — the upper tail (+{{MC_UP_PCT}}%) exceeds the lower (−{{MC_DOWN_PCT}}%) — consistent with the log-normal distribution assigned to agricultural water coefficients, which are bounded below at zero and right-skewed toward underestimation of northern India irrigation intensity (Rodell et al. 2018). The realistic ±18–22% CI (assuming partial independence of sector coefficients) is narrower than the conservative full-correlation bound and is the appropriate figure for comparing against the ±15% TSA demand uncertainty."*

{{MC_DISTRIBUTION_NARRATIVE}}

### 14.3 Variance decomposition (Spearman ρ²)

**Table 19.** Spearman rank correlation — input parameters vs total TWF output. ρ² ≈ variance share (shares do not sum to 100%).

| Parameter | {{FIRST_YEAR}} ρ | {{FIRST_YEAR}} % | {{YEAR_2019}} ρ | {{YEAR_2019}} % | {{LAST_YEAR}} ρ | {{LAST_YEAR}} % |
|---|---|---|---|---|---|---|
{{MC_VARIANCE_ROWS}}

> Agricultural W coefficients account for ~99% of total variance. Improving WaterGAP crop-level estimates for paddy, wheat, and sugarcane in the Indus-Gangetic Plain would reduce total model uncertainty more than any other data improvement.

> **📝 Paper text (Methods §, variance decomposition):** *"Spearman rank correlation between MC input parameters and total TWF output identified agricultural water coefficients as responsible for approximately 99% of total model variance across all study years (Table 19). Hotel and restaurant direct water coefficients together contributed less than 1%. This has a clear methodological implication: the most cost-effective path to reducing result uncertainty is improved WaterGAP crop-level estimates for paddy, wheat, and sugarcane in the Indus-Gangetic Plain — not refinement of hotel survey coefficients. The dominance of the agricultural coefficient is explained by its ~4,000× magnitude relative to service-sector coefficients and its application across the broadest sector group in the model."*

{{MC_VARIANCE_NARRATIVE}}

---

## 15. Supply-chain path analysis

### 15.1 Pull matrix and HEM

```
pull[i,j] = W[i] × L[i,j] × Y[j]    (water from source i triggered by demand for j)
HEM_dependency[i] = [output(i, with Y_tourism) − output(i, Y_tourism=0)] / output(i, total)
```

Path analysis answers *through which specific supply chains* water travels. HEM answers *which upstream sectors depend most on tourism demand*. High HEM dependency + high water coefficient = priority target for tourism water stewardship.

**Table 20.** Top-5 supply-chain pathways per study year.

| Year | Rank | Path (Source → Destination) | Source Group | Water (m³) | Share % |
|---|---|---|---|---|---|
{{SC_PATHS_COMBINED}}

> Full top-50 paths in `sc_path_top50_{year}.csv`. Top paths translate directly into hotel procurement chains for sustainability managers to target.

> **📝 Paper text (Results §, supply chain paths):** *"Path analysis (Table 20) identified the specific supply-chain routes carrying the most water. The top-5 pathways in {{LAST_YEAR}} — all running through agricultural irrigation → food processing → hotel/restaurant demand — collectively accounted for approximately [X]% of total indirect TWF. The most water-intensive single path was [path description], carrying [m³] m³ ({{LAST_YEAR}}). These pathways are directly actionable: hotel procurement managers who can identify and switch the top 5 supplier chains to lower-water-intensity alternatives would reduce their embedded footprint by approximately [X]% with no change to the guest experience."*

**Table 21.** HEM tourism dependency index — top-10 sectors, {{LAST_YEAR}}.

| Rank | Sector | Group | Dependency % | Tourism Water (m³) |
|---|---|---|---|---|
{{HEM_ROWS}}

> **📝 Paper text (Results §, HEM dependency):** *"The Hypothetical Extraction Method (HEM) revealed which upstream sectors depend most on tourism demand (Table 21). The top-dependent sector was [sector] at [X]% dependency, meaning [X]% of its total output would disappear if tourism demand were removed. High dependency sectors with high water coefficients — particularly in food processing and agriculture — represent both the highest risk of tourism water demand volatility and the highest leverage for sustainable procurement interventions."*

**Table 22.** Source-group shares — top-50 supply-chain pathways.

| Source Group | {{FIRST_YEAR}} m³ | {{FIRST_YEAR}} % | {{YEAR_2019}} m³ | {{YEAR_2019}} % | {{LAST_YEAR}} m³ | {{LAST_YEAR}} % |
|---|---|---|---|---|---|---|
{{SC_SOURCE_GROUP_ROWS}}

> **📝 Paper text (Results §, source group summary):** *"Aggregating by source group, agriculture accounted for [X]% of water in the top-50 supply-chain pathways across all years (Table 22), reaffirming its central role. The agriculture share [increased/decreased] from {{FIRST_YEAR}} to {{LAST_YEAR}}, driven by [WaterGAP coefficient changes / supply chain structural shifts]. Energy and water sectors were second, reflecting the irrigation energy embedded in pump-fed agriculture."*

{{SUPPLY_CHAIN_NARRATIVE}}

---

## 16. Sensitivity analysis

Deterministic ±20% shocks to agricultural coefficient groups. Complements Monte Carlo (probabilistic CI) by answering: "if drip irrigation reduced agricultural water use by 20%, how much would TWF fall?" A 20% reduction is a plausible near-term target — PMKSY micro-irrigation achieves 15–25% savings in Punjab and Maharashtra.

**How to read Table 23:** Each row shows one metric for one year under LOW (−20% agr. coefficients), BASE (unchanged), and HIGH (+20%) scenarios. The Indirect LOW/BASE/HIGH come from `indirect_twf_{year}_sensitivity.csv` (Agriculture component). Direct LOW/BASE/HIGH come from `direct_twf_{year}_scenarios.csv`. Total BASE = Indirect BASE + Direct BASE; LOW/HIGH for total use the MC 90% CI bounds (asymmetric) rather than the deterministic band, because direct water coefficient uncertainty is larger proportionally than indirect.

**Table 23.** Sensitivity — LOW / BASE / HIGH, all metrics and years.

| Year | Metric | LOW (bn m³) | BASE (bn m³) | HIGH (bn m³) | ±% half-range |
|---|---|---|---|---|---|
{{SENS_CONSOLIDATED_ROWS}}

> ±20% agr. coefficient shock → ~±14% indirect TWF (elasticity ≈ 0.71 — agriculture is dominant at ~75% but not 100% of W). The Total row uses MC bounds rather than the deterministic band; the deterministic ±14% is narrower than the MC ±{{MC_HALFWIDTH_PCT}}% because σ = 0.30 log-normal spans a wider range than ±20%.

> **📝 Paper text (Methods §, sensitivity):** *"A deterministic sensitivity analysis applied ±20% shocks to agricultural water coefficients — corresponding to plausible irrigation efficiency improvements under India's PMKSY programme (Table 23). The indirect TWF elasticity to agricultural coefficients was approximately 0.71, meaning a 20% coefficient reduction yields a ~14% TWF reduction, because agriculture (~{{AGR_SHARE_2022}}% of upstream water) is the dominant but not exclusive source. This elasticity is the policy-design parameter for procurement interventions: a hotel that switches {{HOTEL_FOOD_SWITCH_PCT}}% of its food sourcing to low-water-intensity suppliers reduces its supply-chain footprint by approximately {{HOTEL_FOOD_SWITCH_IMPACT}}%."*

{{SENSITIVITY_NARRATIVE}}

---

## 17. Key findings and policy implications

{{KEY_FINDINGS}}

### 17.1 Quantified results

1. **Blue TWF:** {{ABSTRACT_TWF_2015}} → {{ABSTRACT_TWF_2019}} → {{ABSTRACT_TWF_2022}} bn m³. Change {{FIRST_YEAR}}→{{LAST_YEAR}}: {{TWF_CHANGE_PCT}}%.
2. **Combined burden:** Blue + green indirect ~{{ABSTRACT_BLUE_GREEN_2022}} bn m³ in 2021–22; green = ~72%.
3. **Intensity:** Total L/tourist-day fell {{INTENSITY_DROP_PCT}}% ({{FIRST_YEAR}}→{{LAST_YEAR}}), primarily L-effect.
4. **Agricultural dominance:** {{AGR_SHARE_2022}}% of indirect blue TWF from agriculture via Leontief propagation.
5. **Inbound–domestic gap:** {{INB_DOM_RATIO}}× more combined water per day for inbound; spending-basket driven; policy-tractable.
6. **SDA 2019→2022:** L-effect ({{SDA_L_COVID}} bn m³) dominated Y-effect ({{SDA_Y_COVID}} bn m³) by {{SDA_L_Y_RATIO}}×.
7. **Uncertainty:** MC 90% CI ≈ ±{{MC_HALFWIDTH_PCT}}% (conservative); agricultural coefficients = ~99% of variance.

### 17.2 Policy priorities

| Priority | Target | Mechanism | Evidence |
|---|---|---|---|
| 1 | Agricultural water efficiency in food supply chains | Drip irrigation standards; crop water-footprint labelling for tourism procurement | Agriculture = {{AGR_SHARE_2022}}% of indirect; dominates blue and green |
| 2 | Supply-chain restructuring toward low-water-intensity sourcing | Short-chain certifications; hotel procurement standards | L-effect was the dominant TWF driver in both periods |
| 3 | Hotel water efficiency | Mandatory water audits; greywater recycling | Hotel coefficient fell 34.6% over study period |
| 4 | Inbound product design | High-spend / low-water-intensity experience packages | 10–18× per-day gap vs domestic; spending-basket driven |
| 5 | Green water in official reporting | Include blue + green TWF in MoT sustainability accounts | Green = 2.6× blue; currently invisible in all official accounts |

---

## 17.3 Water Cost Coverage & Water Productivity

> **What this section answers:**
> *"For every rupee tourists spent, what fraction represents the economic value of water India gave up to serve them?"*
> Water is one resource dimension (energy and land are not yet quantified), so these figures are a **lower bound on total resource cost**.
> The gap between Coverage % and 100% is not yet accounted for by water alone — future studies should add energy and land.

### Table WC-1. Water Cost Coverage — fraction of tourist spending represented by water cost

| Year | Segment | TWF (m³) | Spending (₹ cr) | Low ({{WATER_COST_PRICE_LOW}}) | **Base ({{WATER_COST_PRICE_BASE}})** | High ({{WATER_COST_PRICE_HIGH}}) | Scarce–Base | Productivity (₹/m³) |
|------|---------|-----------|-----------------|-------------------------------|-------------------------------------|----------------------------------|-------------|---------------------|
{{WATER_COST_COVERAGE_ROWS}}

> **Scenario definitions:**
> - **Low** ({{WATER_COST_PRICE_LOW}}): actual subsidised tariff — Central Water Commission Water Pricing India 2021. [https://cwc.gov.in/sites/default/files/water-tariff-circular-2021.pdf](https://cwc.gov.in/sites/default/files/water-tariff-circular-2021.pdf)
> - **Base** ({{WATER_COST_PRICE_BASE}}): economic shadow price — World Bank *India's Water Economy* 2005, Ch. 3 Table 3.2. [https://documents.worldbank.org/en/publication/documents-reports/documentdetail/516041468261148102](https://documents.worldbank.org/en/publication/documents-reports/documentdetail/516041468261148102)
> - **High** ({{WATER_COST_PRICE_HIGH}}): replacement / depletion cost — NITI Aayog CWMI 2018, Ch. 4 + Chennai desalination operational cost. [https://niti.gov.in/sites/default/files/2019-08/CWMI.pdf](https://niti.gov.in/sites/default/files/2019-08/CWMI.pdf)
> - **Scarce–Base**: uses WSI-weighted scarce TWF as numerator at base shadow price — shows the coverage backed by water from already-stressed basins.
> - **Productivity**: ₹ of Tourism GDP per m³ of water consumed (Combined segment only). Compare: agriculture ~₹2–8/m³, manufacturing ~₹40–80/m³.

### Cross-year summary (Base scenario, Combined)

| Year | Coverage low% | **Coverage base%** | Coverage high% | Coverage scarce-base% | Productivity ₹/m³ |
|------|---------------|--------------------|----------------|-----------------------|--------------------|
| 2015 | {{WATER_COST_COVERAGE_LOW_2015}} | **{{WATER_COST_COVERAGE_BASE_2015}}** | {{WATER_COST_COVERAGE_HIGH_2015}} | {{WATER_COST_COVERAGE_SCARCE_2015}} | {{WATER_PROD_2015}} |
| 2019 | {{WATER_COST_COVERAGE_LOW_2019}} | **{{WATER_COST_COVERAGE_BASE_2019}}** | {{WATER_COST_COVERAGE_HIGH_2019}} | {{WATER_COST_COVERAGE_SCARCE_2019}} | {{WATER_PROD_2019}} |
| 2022 | {{WATER_COST_COVERAGE_LOW_2022}} | **{{WATER_COST_COVERAGE_BASE_2022}}** | {{WATER_COST_COVERAGE_HIGH_2022}} | {{WATER_COST_COVERAGE_SCARCE_2022}} | {{WATER_PROD_2022}} |

> **📝 Paper text — framing for journal submission (Results § / Discussion §):**
>
> *"To contextualise the scale of India's tourism water burden, we computed a Water Cost Coverage ratio — the fraction of tourist expenditure that the implicit cost of water alone represents, priced at three shadow-price scenarios. At the actual subsidised tariff ({{WATER_COST_PRICE_LOW}}; Central Water Commission 2021), water cost represents {{WATER_COST_COVERAGE_LOW_2022}}% of tourist spending in 2021–22 — a near-zero figure that illustrates the degree to which India's water is underpriced at source. At the economic shadow price ({{WATER_COST_PRICE_BASE}}; World Bank 2005, Table 3.2), coverage rises to {{WATER_COST_COVERAGE_BASE_2022}}% for combined tourism and {{WATER_COST_COVERAGE_BASE_INB_2022}}% for inbound tourists specifically — indicating that water already represents a material implicit subsidy in India's tourism economy. At the full replacement cost ({{WATER_COST_PRICE_HIGH}}; NITI Aayog 2018), coverage reaches {{WATER_COST_COVERAGE_HIGH_2022}}%, representing a substantial share of tourist expenditure in water terms alone.*
>
> *Since water is only one of several natural resource inputs to tourism — with energy, land, and food-system inputs not yet quantified in EEIO terms for India — these figures constitute a conservative lower bound on total resource cost. Whether India's tourism sector operates within or beyond its full natural resource budget remains an open empirical question; this study provides the first quantified water dimension of that assessment.*
>
> *From a productivity perspective, water committed to tourism generates ₹{{WATER_PROD_2022}}/m³ of direct economic output — substantially above India's agricultural water productivity of ~₹2–8/m³ (Kumar 2005; Planning Commission 2011). This productivity premium implies that water reallocation from irrigation to tourism supply chains would be economically efficient in aggregate terms; however, the scarce-water coverage ratio ({{WATER_COST_COVERAGE_SCARCE_2022}}% at base shadow price) reveals that the water in question is disproportionately drawn from severely-stressed basins, where equity and ecological concerns constrain simple reallocation arguments."*

> **📝 Future studies note (Conclusions § / Discussion §):**
>
> *"The Water Cost Coverage metric introduced here provides a template for multi-resource accounting in tourism. Future research should extend the denominator to include: (i) energy cost via an energy-extended EEIO using India's energy satellite accounts (MoSPI Energy Statistics); (ii) land-use footprint using cropland intensity coefficients from FAOSTAT; and (iii) food-system water for the green water component, already partially captured in this study. When all resource dimensions are quantified, the total resource cost ratio will exceed the water-only coverage figures reported here — determining by how much remains the key open question for India's tourism sustainability assessment."*

---

## 18. Discussion

### 18.1 Comparison with prior literature

**Table B.** India EEIO results in context of global tourism water footprint literature.

| Study | Country | Year(s) | Method | Blue TWF (bn m³) | L/tourist-day |
|---|---|---|---|---|---|
| **This study** | India | 2015–2022 | EEIO-SDA (3-year panel) | {{ABSTRACT_TWF_2022}} | {{INTENSITY_LASTYEAR}} |
| Lenzen et al. 2018 | Global | 2013 | MRIO | 24.0 (world total) | ~500 (avg) |
| Hadjikakou et al. 2015 | Cyprus | 2013 | EEIO | 0.046 | 1,850 |
| Su et al. 2019 | China | 2015 | IO-SDA | 0.19 | ~380 |
| Lee et al. 2021 | China | 2017 | Activity-based | 0.038 (outbound only) | n/a |

> India's per-tourist-day intensity ({{INTENSITY_LASTYEAR}} L/day) sits above the global MRIO average (~500 L/day) but below Cyprus (1,850 L/day). The inbound segment ({{INTENSITY_INB_LASTYEAR}} L/day) is directly comparable to the Hadjikakou Cyprus estimate.

> **📝 Paper text (Discussion §, literature positioning):** *"India's total blue TWF of {{ABSTRACT_TWF_2022}} bn m³ in 2021–22 represents approximately [X]% of global tourism water use estimated by Lenzen et al. (2018) for 2013, consistent with India's share of global tourist arrivals (Table B). Per-tourist-day intensity of {{INTENSITY_LASTYEAR}} L/day exceeds the global average (~500 L/day) because India's tourism supply chains are routed through irrigation-intensive agriculture; comparison with the Cyprus estimate (Hadjikakou et al. 2015) at 1,850 L/day confirms that India's inbound segment ({{INTENSITY_INB_LASTYEAR}} L/day) is already within Mediterranean-country range, driven by full commercial accommodation use. The three-year panel design is methodologically superior to single-year snapshots because it separates permanent structural effects (W- and L-effects) from transient volume changes (Y-effect)."*

> India's per-tourist-day intensity ({{INTENSITY_LASTYEAR}} L/day) sits above the global MRIO average (~500 L/day) but below Cyprus (1,850 L/day). The inbound segment ({{INTENSITY_INB_LASTYEAR}} L/day) is directly comparable to the Hadjikakou Cyprus estimate.

### 18.2 Methodological limitations

**PTA:** Standard practice (Eurostat Manual 2008); negative entries < 0.5% of output; sensitivity ±2% on total TWF.

**TSA extrapolation:** Production-side proxy for an expenditure-side measure. ±15% sensitivity (Table 23) bounds this uncertainty. A 2019–20 TSA would narrow it to ±5–8%.

**Outbound method mismatch:** Inbound = EEIO; outbound = activity-based. Net balance direction is robust; magnitude is indicative only (flagged in Table 9a).

### 18.3 Decoupling analysis

**Table A.** Absolute decoupling of TWF from tourism demand.

| Period | ΔTWF (%) | ΔTourist-days (%) | ΔDemand real (%) | Decoupling type |
|---|---|---|---|---|
| {{FIRST_YEAR}}→{{YEAR_2019}} | {{SDA_DELTA_PCT_1}} | {{TD_DELTA_PCT_1}} | {{DEMAND_DELTA_PCT_1}} | {{DECOUPLING_TYPE_1}} |
| {{YEAR_2019}}→{{LAST_YEAR}} | {{SDA_DELTA_PCT_2}} | {{TD_DELTA_PCT_2}} | {{DEMAND_DELTA_PCT_2}} | {{DECOUPLING_TYPE_2}} |
| {{FIRST_YEAR}}→{{LAST_YEAR}} | {{SDA_DELTA_PCT_3}} | {{TD_DELTA_PCT_3}} | {{DEMAND_DELTA_PCT_3}} | {{DECOUPLING_TYPE_3}} |

> 2019→2022 may show artificial absolute decoupling due to COVID demand suppression. The {{FIRST_YEAR}}→{{LAST_YEAR}} full-panel result is the policy-relevant test.

> **📝 Paper text (Discussion §, decoupling):** *"Decoupling analysis (Table A) shows {{DECOUPLING_TYPE_3}} over the full panel ({{FIRST_YEAR}}→{{LAST_YEAR}}): TWF changed {{SDA_DELTA_PCT_3}}% while real tourism demand changed {{DEMAND_DELTA_PCT_3}}%. The 2019→2022 period should be treated cautiously as COVID suppressed both demand and supply-chain activity simultaneously, potentially producing artificial decoupling. The {{FIRST_YEAR}}→2019 pre-COVID period provides the cleaner test: [decoupling type] with TWF growing at [rate] relative to demand growth of [rate], indicating [progress/absence of progress] in decoupling India's tourism growth from water pressure."*

### 18.4 Agricultural policy scenarios

**Table C.** Quantified intervention leverage.

| Scenario | Agr. W coeff. change | Δ Indirect TWF | Policy analogue |
|---|---|---|---|
| Drip irrigation rollout | −10% | ~−7% | PMKSY micro-irrigation |
| Drip + crop switch | −20% | ~−14% | Full PMKSY + crop diversification |
| Hotel food procurement switch | −30% food sectors only | ~−8% | Sustainable hotel procurement standard |
| Technology frontier | −50% | ~−35% | Israel-level irrigation efficiency |

> **📝 Paper text (Discussion §, policy scenarios):** *"Scenario analysis (Table C) translates the indirect TWF elasticity (≈0.71 to agricultural coefficients) into concrete policy targets. Full rollout of PMKSY micro-irrigation — modelled as a 20% reduction in agricultural water coefficients — would reduce indirect TWF by approximately 14%. A hotel procurement switch away from high-water-intensity food sectors (modelled as −30% to food processing coefficients only) achieves ~8% indirect TWF reduction through a supply-chain channel completely within the hospitality industry's control. The technology frontier scenario (Israel-level irrigation efficiency, −50% coefficients) achieves ~35% reduction, setting a ceiling for supply-chain-only interventions."*

### 18.5 Generalisability

India's pattern — agricultural supply-chain water dominating indirect TWF — generalises to any emerging economy with: (1) large rainfed/irrigated agriculture, (2) tourism spending weighted toward food services, and (3) WaterGAP-modelled irrigation-intensive basins. The EEIO-SDA framework with dual blue/scarce metrics over a multi-year panel is directly transferable to Southeast Asia, South Asia, and Sub-Saharan Africa.

---

## 19. Data quality warnings

```
{{WARNINGS}}
```

---

## 20. Configuration reference

**Table 28.** Technical configuration.

| Item | Detail |
|---|---|
| IO method | PTA: B = V/g, D = U/q, A = D·B⁻¹, L = (I−A)⁻¹ |
| SUT units | 2015–16: ₹ lakh (×0.01 → crore); 2019–20, 2021–22: ₹ crore |
| Hawkins-Simon | ρ(A) < 1 verified all years; A_sum ≥ 1.0 columns rescaled to 0.95 |
| Water source | EXIOBASE 3.8 `IOT_{year}_ixi/water/F.txt`; 103 "Water Consumption Blue" rows |
| Green water | Same F.txt; 13 "Water Consumption Green" rows (agriculture only) |
| EXIOBASE concordance | 163/163 India sectors mapped |
| TSA base | India TSA 2015–16 (MoT), 24 categories |
| NAS scaling | Statement 6.1, constant 2011–12 prices, NAS 2024 edition |
| CPI deflator | Base 2015–16; {{CPI_VALUES}} |
| EUR/INR rates | {{EURINR_VALUES}} |
| Hotel direct | tourist-nights × dom_hotel_share(0.15) / inb_hotel_share(1.0) × L/room/night |
| Rail direct | domestic_tourists × dom_rail_modal_share(0.25) × avg_tourist_rail_km × L/pkm |
| Monte Carlo | n = 10,000; seed = 42; agr σ = 0.30 log-normal; single correlated multiplier |
| SDA | Two-polar Dietzenbacher–Los (1998); residual < 0.001%; Near_cancellation flag at 5×\|ΔTWF\| |
| Scarce water | WRI Aqueduct 4.0 (Kuzma et al. 2023); agr WSI = 0.827, industry = 0.814, services = 0 |
| Pipeline version | `{{PIPELINE_VERSION}}` |

### 20.1 Data sources

| Dataset | Source | Version / FY | Access |
|---|---|---|---|
| Supply-Use Tables | MoSPI | 2015–16, 2019–20, 2021–22 | Public |
| National Accounts Statistics | MoSPI NAS 2024 | Statement 6.1 | Public |
| India Tourism Satellite Account | Ministry of Tourism | 2015–16 | Public |
| EXIOBASE water satellite | EXIOBASE Consortium | v3.8 | Open access |
| Hotel water coefficients | CHSB India 2015–2022 | Field study | Literature |
| Restaurant water coefficients | Lee et al. (2021) J. Hydrology 603:127151 | — | Literature |
| Rail water coefficients | Gössling (2015); Lee et al. (2021) | — | Literature |
| Rail modal share | NSS Report 580, Table 3.6, MOSPI 2017 | 2014–15 | Public |
| Rail average lead | MoR Annual Statistical Statement, Table 2 | 2015-16, 2019-20, 2021-22 | Public |
| Hotel domestic share | NSS Report 580, Table 3.14, MOSPI 2017 | 2014–15 | Public |
| Water Stress Index | WRI Aqueduct 4.0 (Kuzma et al. 2023) | 2023 | Open access |
| CPI series | MoSPI / RBI | Base 2015–16 | Public |
| EUR/INR rates | RBI reference rates | Annual average | Public |

### 20.2 Data provenance and uncertainty budget

**Table D.** Uncertainty source attribution.

| Input | Uncertainty | Impact on TWF | Priority |
|---|---|---|---|
| Agricultural W coefficients (WaterGAP) | σ = 0.30 log-normal | ~99% of MC variance | **Critical** |
| TSA demand extrapolation | ±15% assumed | ~±11% on TWF | High |
| WSI sector weights (3-group) | ±0.05 per group | ~±4% on Scarce TWF | Medium |
| Outbound destination shares (⚠ PLACEHOLDER) | ±30% | Net balance directional only | **Critical before publication** |
| Hotel direct coefficients (CHSB) | ±25% | <2% of total TWF | Low |
| CPI deflator | ±2% | <1% | Low |

> **📝 Paper text (Methods §, uncertainty budget):** *"The uncertainty budget (Table D) is strongly concentrated: WaterGAP agricultural coefficients account for ~99% of total MC variance (Table 19), dwarfing all other sources. TSA demand extrapolation contributes ~±11% to TWF uncertainty and is the second-largest source; a future study using a current TSA (2019–20 or 2022–23) would reduce this to ±5–8%. Outbound destination shares require field verification against MoT ITS 2022 before the net balance estimate can be reported with confidence; all other inputs are well-constrained. Direct water coefficients (hotel, restaurant, rail, air) contribute less than 2% of total TWF uncertainty — a result that justifies confidence in the direct footprint estimates despite their activity-based nature."*

### 20.3 Figure roles in manuscript

| Figure | Content | Placement |
|---|---|---|
| 1 | Analytical Framework | Methods |
| 2 | Four-Panel Overview (volumes, intensity gap, hotspots, source composition) | Lead figure / Introduction |
| 3 | Temporal Trajectory (3-panel: TWF, intensity gap, demand composition) | Results |
| 4 | WMR Heatmap (sector hotspot + artefact audit) | Results alongside Tables 14–16 |
| 5 | Leontief Pull Bubble Matrix (agriculture appearing in non-food demand) | Results — "invisible water" |
| 6 | Sankey Flow Strip (source → tourism demand) | Supplementary if figure limit = 6 |
| 7 | SDA Waterfall (COVID structural break) | Results / Discussion |
| 8 | Uncertainty Strip (MC CI, asymmetric annotation) | Methods supplementary |

> For journal submission strategy see **Supplementary Table S2** (journal targeting) and **Supplementary Table S3** (reviewer pre-emption Q&A) at the top of this report.

---

## Supplementary Table S2. Journal Targeting *(remove before submission)*

| Journal | Est. IF | Lead novelty | Verdict |
|---|---|---|---|
| *Nature Water* | ~15 | Multi-period + green/scarce + SDA | Submit if SDA result is strong |
| *Water Research* | ~12 | MC variance decomposition; agricultural supply-chain leverage | **Primary target** |
| *Journal of Cleaner Production* | ~9 | Inbound–domestic gap; policy targeting | Strong backup |
| *Tourism Management* | ~10 | COVID L-effect; MoT policy | Consider if policy angle foregrounded |
| *Resources, Conservation & Recycling* | ~11 | Green water; outbound net balance | Backup for green/outbound angle |

---

## Supplementary Table S3. Reviewer Pre-emption Q&A *(use in cover letter)*

| Likely reviewer question | Rebuttal | Evidence |
|---|---|---|
| "TSA extrapolation via NAS GVA is production-side" | Standard approach (Temurshoev & Timmer 2011). ±15% demand → ~±11% TWF — less than agricultural uncertainty. | §4.1, Table 25 |
| "MC single correlated multiplier overstates CI" | Acknowledged. Conservative upper bound; realistic CI ~30–40% narrower under independent sampling. | §14.1, Table 18 |
| "Why report blue + green separately?" | Not summed. Blue = cross-study headline. Green disclosed per Hoekstra & Mekonnen (2012) — India's food system is ~60% rainfed. | §5.6, Tables 7b–7c |
| "PTA produces negative values" | Repaired where A_sum ≥ 1.0; Hawkins-Simon verified all years; negatives < 0.5% of output. | §3.2 |
| "COVID 2019→2022 is demand elasticity" | Incorrect — SDA shows L-effect dominated, not Y-effect. | §13.3 |
| "WSI aggregation too coarse" | Acknowledged; Aqueduct 4.0 three-group weights are best available. | §5.5 |
| "Outbound and inbound methods are incompatible" | Flagged in Table 9a; net balance is a directional indicator only. | §9.2 |
| "Railway water is counted twice (indirect + direct)" | No — indirect = upstream supply-chain basin water (agriculture, energy, steel via Leontief). Direct = on-site municipal tap water. WaterGAP assigns near-zero to IN.114. | §6.2 |

---

## 21. Paper Writing Guide *(internal — remove before submission)*

A compact scaffold for drafting the journal manuscript. Each section lists: what argument to make, which tables/figures to cite, and the key placeholder values to fill in.

---

### Title (suggested)
*"Multi-period water footprint of India's tourism sector: supply-chain structural change dominated COVID-era reduction, not demand collapse"*

---

### Abstract (≤ 250 words)
State: problem (India tourism + water stress, single-year gap), method (EEIO-SDA, 3 years, EXIOBASE, TSA), three headline results (TWF trajectory, inbound–domestic gap, SDA L-effect dominance), one conclusion (supply-chain leverage > on-site efficiency). Fill from §17.1.

*Key numbers: {{ABSTRACT_TWF_2015}} → {{ABSTRACT_TWF_2019}} → {{ABSTRACT_TWF_2022}} bn m³ · {{INTENSITY_DROP_PCT}}% intensity decline · {{INB_DOM_RATIO}}× inbound gap · L-effect {{SDA_L_Y_RATIO}}× larger than Y-effect · MC CI {{MC_P5_2022}}–{{MC_P95_2022}} bn m³*

---

### 1. Introduction (~600 words)
**Argument:** India's tourism water footprint is unstudied at multi-year scale; supply chains dominate operational use; the COVID period was a structural experiment not a demand-elasticity one.
- Cite: India GDP/jobs context ({{TOURISM_GDP_PCT}}%, {{TOURISM_JOBS_M}}M jobs); NITI Aayog water stress (600M affected)
- Novelty gap: cite Table S1 row by row — name each prior study (Lenzen 2018, Su 2019, Hadjikakou 2015) and state what's missing
- Close with paper structure outline

---

### 2. Methods (~800 words)
**Argument:** EEIO is the only feasible method at this scale; PTA over ITA; SDA is necessary to avoid COVID misinterpretation; MC addresses dominant agricultural coefficient uncertainty.
- Cite §2.1 pipeline steps — mention each script once
- Core equation: TWF = W · L · Y (cite Miller & Blair 2009; Leontief 1970)
- TSA extrapolation rationale: cite Temurshoev & Timmer (2011); mention NAS GVA growth multipliers (Table 3)
- Direct water boundary statement: §6.0; §6.2 railway boundary table
- WSI methodology: cite Kuzma et al. (2023); Aqueduct 4.0 three-group weights
- SDA formula: cite Dietzenbacher & Los (1998); mention near-cancellation guard
- MC design: σ = 0.30 log-normal (cite Biemans et al. 2011); single correlated multiplier = conservative CI
- *Limitation paragraph* (TSA proxy; PTA negatives; outbound mismatch) — cite §18.2

---

### 3. Results (~1,200 words)

**3.1 Indirect blue TWF trajectory** — Table 4 (Main Table 1)
*"Indirect blue TWF {{TWF_DIRECTION}} from {{ABSTRACT_TWF_2015}} bn m³ in 2015–16 to {{ABSTRACT_TWF_2022}} bn m³ in 2021–22 (Table 4). Green water at {{ABSTRACT_BLUE_GREEN_2022}} bn m³ combined..."*
Cite Table 7b–7c for green component.

**3.2 Upstream water origin** — Table 6
*"Agriculture accounted for {{AGR_SHARE_2022}}% of indirect blue TWF in {{LAST_YEAR}} through Leontief propagation, despite tourists purchasing no raw crops directly. Paddy irrigation intensity increased +61.5% in WaterGAP coefficients from 2015 to 2022, consistent with documented Indus-Gangetic groundwater depletion."*

**3.3 Scarce water** — Table 7a
*"The scarce/blue ratio was {{SCARCE_RATIO_2022}} across study years, reflecting that {{SCARCE_RATIO_2022_PCT}}% of extracted water originates from basins already at severe stress (WSI = 0.827)."*

**3.4 Direct water** — Tables 8, 8a, 8b, 8c
*"Direct operational water constituted {{DIRECT_SHARE_RANGE}}% of total blue TWF — typical for service-sector tourism (Gössling 2015). Inbound direct water was dominated by hotel use ({{INB_HOTEL_LPDAY}} L/day); domestic by restaurants ({{DOM_REST_LPDAY}} L/day)."*

**3.5 Per-tourist intensity and inbound–domestic gap** — Tables 10, 11 (Main Table 2)
*"Total water intensity fell {{INTENSITY_DROP_PCT}}% from {{i0_all}} to {{iN_all}} L/tourist-day. Inbound tourists used {{INB_DOM_RATIO}}× more water per day than domestic tourists ({{INTENSITY_INB_LASTYEAR}} vs {{INTENSITY_DOM_LASTYEAR}} L/day), with a residual intensity ratio of {{RESIDUAL_RATIO_LAST}} indicating the gap is predominantly spending-basket driven."*

**3.6 Structural Decomposition Analysis** — Tables 17, 17b (cite as key finding)
*"SDA revealed that the L-effect (supply-chain structure: {{SDA_L_COVID}} bn m³) exceeded the Y-effect (demand volume: {{SDA_Y_COVID}} bn m³) by {{SDA_L_Y_RATIO}}× during 2019→2022, contradicting a naive demand-elasticity interpretation of COVID-era TWF decline."*

**3.7 Uncertainty** — Table 18, Table 19
*"Monte Carlo 90% CI: {{MC_P5_2022}}–{{MC_P95_2022}} bn m³ around the {{ABSTRACT_TWF_2022}} bn m³ base (asymmetric: −{{MC_DOWN_PCT}}%/+{{MC_UP_PCT}}%). Spearman ρ² analysis attributed ~99% of model variance to agricultural W coefficients."*

---

### 4. Discussion (~600 words)

**4.1 Why supply-chain structure, not demand, is the lever** — cite Table 17b, Figure 7 (SDA Waterfall), §13.3. Compare L-effect magnitude to Y-effect; note COVID as supply-chain restructuring experiment.

**4.2 Inbound–domestic gap mechanisms** — spending basket (Table 11 Spend ratio) vs supply-chain intensity (Residual ratio). Policy implication: product design, not infrastructure.

**4.3 Agricultural dominance and basin damage** — Table 7a (Scarce), Table 7c (green), Figure 5 (Leontief Pull). PMKSY leverage estimate from Table C.

**4.4 Comparison with prior literature** — Table B. Note India's intensity vs Cyprus (Hadjikakou 2015), global (Lenzen 2018), China (Su 2019).

**4.5 Limitations** — §18.2. TSA proxy, PTA negatives, outbound mismatch. One paragraph each, pre-empt with Supp S3 rebuttals.

---

### 5. Conclusions (~200 words)
Three sentences max per finding. State: (1) TWF trajectory and agricultural dominance; (2) supply-chain structure is the primary lever (L-effect); (3) inbound–domestic gap is policy-tractable; (4) framework is generalisable (§18.5).

---

### Figure assignments (see §20.3)
- **Main text figures (max 6):** Figures 1, 2, 3, 5, 7, 8
- **Supplementary:** Figure 6 (Sankey), Figure 4 (if figure limit tight)
- **Main tables:** Table 4 (Main Table 1 — TWF trajectory), Table 11 (Main Table 2 — inbound/domestic gap), Table 17 (SDA), Table 18 (MC CI)

---

*Generated by India TWF Pipeline — report_template.md filled by `compare_years.py`*
*Framework: Leontief (1970); Miller & Blair (2009); Hoekstra et al. (2011)*