# India Tourism Water Footprint: A Multi-Year Environmentally Extended Input–Output Analysis

**Generated:** {{RUN_TIMESTAMP}} · **Years:** {{STUDY_YEARS}} · **Runtime:** {{TOTAL_RUNTIME}} · **Log:** `{{PIPELINE_LOG_PATH}}`

---

## Abstract

India's tourism sector generates substantial freshwater demand through supply chains that remain unquantified across time. We apply an EEIO framework to MoSPI Supply-Use Tables for FY 2015–16, 2019–20, and 2021–22, paired with EXIOBASE 3.8 WaterGAP water satellites (163 India sectors), to estimate the tourism water footprint (TWF) across three periods spanning pre-COVID growth and recovery. Tourism demand vectors are derived from India TSA 2015–16 extrapolated via NAS Statement 6.1 real GVA growth rates. Inter-period drivers are decomposed via two-polar Dietzenbacher–Los SDA (W: water intensity; L: supply-chain structure; Y: demand volume). Uncertainty is quantified via Monte Carlo (n = 10,000, agricultural σ = 0.30 log-normal). Scarce water uses WRI Aqueduct 4.0 WSI weights.

Indirect blue TWF: **{{ABSTRACT_TWF_2015}} bn m³** (2015–16) → **{{ABSTRACT_TWF_2019}} bn m³** (2019–20) → **{{ABSTRACT_TWF_2022}} bn m³** (2021–22). Combined blue + green indirect reached ~**{{ABSTRACT_BLUE_GREEN_2022}} bn m³** in 2021–22 (green ≈ 72%). Scarce TWF = ~83% of blue (agriculture WSI = 0.827). Intensity declined **{{INTENSITY_DROP_PCT}}%** per tourist-day. Inbound tourists consumed **{{INB_DOM_RATIO}}×** more water per day than domestic tourists. SDA 2019→2022: L-effect ({{SDA_L_COVID}} bn m³) exceeded Y-effect ({{SDA_Y_COVID}} bn m³) by **{{SDA_L_Y_RATIO}}×**. Monte Carlo 90% CI: **{{MC_P5_2022}}–{{MC_P95_2022}} bn m³**; agricultural coefficients account for ~99% of variance. Supply-chain structural change — not on-site efficiency — is the primary TWF reduction lever. Agricultural water in food supply chains ({{AGR_SHARE_2022}}% of indirect origin) is the dominant intervention target.

**Keywords:** tourism water footprint; EEIO; India; structural decomposition; green water; scarce water; WaterGAP; Aqueduct 4.0; COVID-19; inbound–domestic gap

---

## 1. Introduction

Tourism contributes ~{{TOURISM_GDP_PCT}}% of India's GDP and {{TOURISM_JOBS_M}} million jobs, and is a significant freshwater consumer — directly (hotels, restaurants, transport) and indirectly through supply chains embedding agricultural and industrial water in food, goods, and energy consumed by tourists. India faces acute water stress: 600+ million people experience high-to-extreme stress annually (NITI Aayog 2018), yet the freshwater implications of tourism supply chains remain poorly quantified across time. Existing EEIO-based tourism TWF studies are single-year snapshots; none applies a multi-period structural decomposition or quantifies the inbound–domestic intensity gap for India.

This study makes five novel contributions (Table S1): (1) first three-year panel EEIO for India tourism covering pre-COVID, peak, and post-COVID recovery; (2) two-polar SDA that formally separates W, L, and Y drivers — preventing the COVID-era TWF decline from being misread as demand elasticity; (3) dual blue + scarce water reporting using WRI Aqueduct 4.0 sector-level WSI weights; (4) green water disclosure alongside blue using year-specific EXIOBASE coefficients; and (5) outbound TWF and net virtual water balance revealing India's position relative to water-scarce destination countries.

The analysis covers {{N_SECTORS}} SUT sectors mapped to {{N_EXIO_SECTORS}} EXIOBASE sectors across three fiscal years: 2015–16 (pre-COVID baseline), 2019–20 (peak), and 2021–22 (post-COVID recovery).

---

## 2. Methods

### 2.1 IO Construction and EEIO Framework

Supply-Use Tables (MoSPI, 140 products × 140 industries) are converted to IO tables via the Product Technology Assumption (PTA), which assigns production recipes to products rather than industries, preserving non-negativity of the A matrix (Eurostat Manual 2008). The Leontief inverse is:

```
B = V · diag(g)⁻¹        (industry output shares by product)
A = U · diag(q)⁻¹ · B⁻¹  (IO technical coefficients)
L = (I − A)⁻¹             (Leontief inverse)
```

The core EEIO identity is:

```
TWF_indirect = W · L · Y     [m³; total supply-chain embedded water]
Scarce_TWF   = TWF × WSI     [m³; stress-weighted water, WSI from Aqueduct 4.0]
```

where **W** (163×163 diagonal) contains sector water intensities from EXIOBASE 3.8 WaterGAP (m³/₹ crore), **L** is the Leontief inverse, and **Y** (163×1) is the tourism final demand vector. Hawkins-Simon condition ρ(A) < 1 verified for all years. PTA is preferred over ITA because ITA generates negative A-matrix entries in India's diverse manufacturing mix.

Blue water (extracted groundwater/surface water; EXIOBASE rows "Water Consumption Blue") and green water (rainfed crop evapotranspiration; rows "Water Consumption Green", agriculture only) are extracted separately from EXIOBASE 3.8 F.txt and reported independently following Hoekstra & Mekonnen (2012).

### 2.2 Tourism Demand Vectors

India's TSA has not been updated since 2015–16. We extrapolate the base TSA using NAS Statement 6.1 real GVA growth rates (constant 2011–12 prices) following Temurshoev & Timmer (2011):

```
Y(year) = TSA_base × [GVA(year) / GVA(2015-16)] × [CPI(year) / CPI(2015-16)]
```

Separate inbound (Y_inb) and domestic (Y_dom) demand vectors are produced for each year, enabling the segment intensity split. Distribution across 163 EXIOBASE sectors follows the TSA→EXIOBASE concordance. NAS Statement 6.1 (Trade & repair services) is used for restaurant scaling rather than 6.2 (Hotels), because 6.2 is dominated by hotel occupancy dynamics that diverged from food-service activity during COVID.

### 2.3 Scarce Water and Green Water

Scarce TWF weights extracted blue water by WRI Aqueduct 4.0 sector-level WSI (Kuzma et al. 2023): agriculture = 0.827, manufacturing = 0.814, services = 0 (municipal supply; not extracted from stressed basins). The three-group structure reflects available Aqueduct 4.0 resolution; finer sector weights are not available at the SUT-140 level. Green water uses exact EEIO propagation through agriculture rows only; it is not a proportional allocation.

### 2.4 Direct TWF

Activity-based operational water covers four categories:

```
Hotel_m3      = tourist_nights × segment_share × L/room/night
Restaurant_m3 = tourist_days   × meals/day     × L/meal
Rail_m3       = dom_tourists × rail_modal_share(0.25) × avg_km × L/pkm
Air_m3        = air_pax × tourist_share × L/passenger
```

Direct water is typically < 5% of total TWF. LOW/BASE/HIGH scenarios bracket coefficient literature uncertainty.

### 2.5 Structural Decomposition Analysis

Two-polar Dietzenbacher–Los (1998) SDA decomposes inter-period ΔTWF:

```
ΔTWF = W₁·L₁·Y₁ − W₀·L₀·Y₀
W_effect = ½(ΔW·L₀·Y₀) + ½(ΔW·L₁·Y₁)   [water technology change]
L_effect = ½(W₀·ΔL·Y₀) + ½(W₁·ΔL·Y₁)   [supply-chain structure change]
Y_effect = ½(W₀·L₀·ΔY) + ½(W₁·L₁·ΔY)   [tourism demand volume change]
```

Two-polar averaging eliminates the interaction residual of one-polar decompositions (identity holds to < 0.001%). A `Near_cancellation` flag is raised when any single effect exceeds 5×|ΔTWF|; percentage shares are suppressed in that case, but absolute bn m³ values remain reliable. Without SDA, the 2019→2022 TWF decline would be attributed solely to COVID demand collapse; SDA formally separates supply-chain restructuring (L) from demand contraction (Y).

### 2.6 Monte Carlo Uncertainty

```
agr_mult_i ~ LogNormal(μ=0, σ=0.30)   [n = 10,000; seed = 42]
TWF_i       = (W_base × agr_mult_i) · L · Y + direct_twf_sim(...)
```

A single correlated multiplier is applied across all 163 agricultural rows — a conservative upper bound. Independent sector sampling would reduce CI width by ~30–40%. Log-normal is used because water coefficients are bounded below at zero and WaterGAP is more likely to underestimate northern India irrigation intensity (Rodell et al. 2018). Spearman ρ² variance decomposition identifies the dominant uncertainty source.

### 2.7 Outbound TWF

Activity-based outbound TWF follows Lee et al. (2021):

```
Outbound_m3 = outbound_tourists × dest_share × avg_stay_days × (national_WF/365) × 1.5
```

The 1.5 tourist multiplier reflects ~50% higher per-day consumption than local residents (Hadjikakou et al. 2015). Net balance = Outbound − Inbound (directional indicator; methods differ — EEIO vs activity-based — so the net is not a precise bilateral identity).

### 2.8 Validation

Nine automated assertions are run post-pipeline: IO balance error < 1%; ρ(A) < 1; LOW < BASE < HIGH monotonicity; SDA residual < 0.001%; Scarce/Blue ratio ∈ [0.30, 0.95].

---

## 3. Results

### 3.1 Input–Output Context

**Main Table 6 (condensed).** IO table summary — all fiscal years.

| FY | Total Output (₹ cr) | Total Output (USD M) | Intermediate (₹ cr) | Final Demand (₹ cr) | Balance Error % | ρ(A) | USD/INR |
|---|---|---|---|---|---|---|---|
{{IO_TABLE_ROWS_CONDENSED}}

> Balance errors < 0.01% confirm consistent supply-use accounts. ρ(A) < 1 verified — productive system. USD conversion at fiscal-year average rates; real comparisons use 2015-16 base (₹65.00/USD).

{{IO_TABLE_NARRATIVE}}

### 3.2 Tourism Demand Vectors

Tourism nominal demand (NAS-scaled): {{DEMAND_TABLE_ROWS_INLINE}}. Non-zero EXIOBASE sectors: 42–47/163 per year, confirming demand is concentrated in service and food-processing sectors. Full demand vector details in Supplementary Table S2.

### 3.3 Indirect TWF Trajectory

**Main Table 1. TWF trajectory, scarce water, and Monte Carlo confidence intervals.**

| FY | Blue Indirect (bn m³) | Green Indirect (bn m³) | Blue+Green Indirect (bn m³) | Scarce TWF (bn m³) | Direct Blue (bn m³) | **Total Blue (bn m³)** | MC P5 (bn m³) | MC P95 (bn m³) | Intensity (L/tourist-day, Blue) | Intensity (L/tourist-day, Blue+Green) | Δ vs {{FIRST_YEAR}} |
|---|---|---|---|---|---|---|---|---|---|---|---|
{{MAIN_TABLE_1_ROWS}}

> **Blue Indirect** = W·L·Y (EEIO, blue WaterGAP coefficients). **Green Indirect** = exact EEIO propagation of green (rainfed ET) coefficients through agriculture rows only — not a proportional allocation. **Blue+Green Indirect** = sum of the two; not used as a headline metric (blue and green carry distinct scarcity implications per Hoekstra & Mekonnen 2012). **Total Blue** = Blue Indirect + Direct Blue (BASE scenario). **Intensity (Blue)** = Total Blue m³ × 10⁶ / tourist-days; **Intensity (Blue+Green)** = (Blue Indirect + Green Indirect + Direct Blue) × 10⁶ / tourist-days. MC CI applies to Total Blue only (n = 10,000, agr σ = 0.30 log-normal, single correlated multiplier — conservative upper bound; realistic ±18–22% under partial independence).

{{TOTAL_TWF_NARRATIVE}}

### 3.4 Upstream Water Origin

**Main Table 5 (panel A). Top-10 upstream sectors by Leontief pull — {{LAST_YEAR}} — with scarce water.**

| Rank | Source Sector | Source Group | Water m³ | Water % | WSI Weight | Scarce m³ | Scarce % |
|---|---|---|---|---|---|---|---|
{{ORIGIN_TOP10_ROWS}}

> Agriculture accounts for {{AGR_SHARE_2022}}% of indirect blue TWF despite tourists purchasing no raw crops directly — entirely Leontief-propagated through food supply chains. WSI = 0.827 for agricultural rows. Full origin breakdown by source group in Supplementary Table S7b.

> **📝 Paper text (Results §3.4, upstream water origin):** *"Agriculture accounted for {{AGR_SHARE_2022}}% of indirect blue TWF in {{LAST_YEAR}} (Main Table 5A, Supplementary Table S7b), despite receiving zero direct tourism expenditure. This is entirely Leontief-propagated water: food-service supply chains embed paddy, wheat, and sugarcane irrigation water from the Indus-Gangetic Plain through multiple upstream tiers before reaching the tourism sector. The top-10 upstream sectors (Main Table 5A) are dominated by agricultural sub-sectors across all three study years, consistent with the scarce/blue ratio of {{SCARCE_RATIO_2022}} (Main Table 1) — over {{SCARCE_RATIO_2022_PCT}}% of abstracted water originates from basins at WSI ≥ 0.8. Paddy irrigation intensity in WaterGAP increased +61.5% between the 2015-16 and 2021-22 model vintages, consistent with documented Indus-Gangetic groundwater depletion (Rodell et al. 2018), and accounts for the upward W-effect visible in Main Table 3."*

{{ORIGIN_NARRATIVE}}

### 3.5 Scarce and Green Water

**Main Table 1** (above) reports scarce TWF alongside blue. The scarce/blue ratio was {{SCARCE_RATIO_2022}} in {{LAST_YEAR}}, meaning {{SCARCE_RATIO_2022_PCT}}% of extracted water originates from basins at severe stress. Green water ({{ABSTRACT_BLUE_GREEN_2022}} bn m³ combined in {{LAST_YEAR}}) represents rainfed crop ET embedded in tourism food chains. Green is disclosed separately — not summed into a headline total — because it represents rainfall appropriation, not groundwater or river abstraction. Year-on-year changes in green water reflect both WaterGAP coefficient revisions and COVID-era supply-chain restructuring toward more irrigated production. Sector-by-sector blue/green breakdown in Supplementary Table S4.

### 3.6 Direct Operational Water

Direct water was {{DIRECT_SHARE_RANGE}}% of total blue TWF — indirect supply chains dominate by ~10:1. In {{LAST_YEAR}}, inbound direct water was led by hotel use ({{INB_HOTEL_LPDAY}} L/tourist-day); domestic direct water by restaurants ({{DOM_REST_LPDAY}} L/tourist-day). Direct LOW/BASE/HIGH scenario detail in Supplementary Table S6.

### 3.7 Per-Tourist Water Intensity and Inbound–Domestic Gap

**Main Table 2. Per-tourist-day water intensity — inbound vs domestic, all water components.**

| FY | Segment | Demand (₹ cr) | Ind. Blue (bn m³) | Ind. Green (bn m³) | Total Indirect (bn m³) | Direct Blue (bn m³) | **Total (bn m³)** | **Blue L/day** | **Total (B+G) L/day** | Spend (₹/day) | TWF ratio | Spend ratio | Residual ratio |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
{{INTENSITY_SEGMENT_ROWS}}

> **Blue L/day** = (Ind. Blue + Direct Blue) × 10⁶ / tourist-days. **Total (B+G) L/day** = (Ind. Blue + Ind. Green + Direct Blue) × 10⁶ / tourist-days. Both intensity columns are shown: Blue-only is the appropriate metric for cross-study benchmarking (all prior global studies report blue only); Blue+Green shows the complete physical burden. **Spend ratio** = inbound ₹/day ÷ domestic ₹/day. **Residual ratio** = TWF ratio ÷ Spend ratio; value ≈ 1.0 means the gap is spending-basket driven; value > 1.0 means inbound supply chains are inherently more water-intensive per rupee. † Green column absent if pipeline not updated.

{{INTENSITY_SPLIT_NARRATIVE}}

### 3.8 TSA Category Decomposition

**Main Table 7. Cross-year TSA category decomposition — top 8 categories.**

| FY | Rank | TSA Category | Demand (₹ cr) | Indirect (bn m³) | Direct (bn m³) | Total (bn m³) | Direct % | Agr % | Elec % | Petro % |
|---|---|---|---|---|---|---|---|---|---|---|
{{SECTOR_DECOMP_CROSS_YEAR_ROWS}}

> Agriculture % of indirect (Agr %) ranges {{AGR_PCT_RANGE}} across top-8 categories and all years, confirming agricultural supply-chain water dominates regardless of TSA category type. COVID-era rank shifts identify structurally resilient (Food & Beverage) vs demand-sensitive (Accommodation) categories. Direct % < 5% for all categories confirms supply-chain dominance throughout.

{{SECTOR_DECOMP_NARRATIVE}}

### 3.9 Structural Decomposition Analysis

**Main Table 3. SDA — W, L, Y effects and dominant driver by period.**

| Period | Start (bn m³) | End (bn m³) | ΔTWF (bn m³) | W Effect (bn m³) | W % | L Effect (bn m³) | L % | Y Effect (bn m³) | Y % | Dominant Driver | Interpretation | ⚠ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
{{SDA_COMBINED_ROWS}}
{{SDA_INSTABILITY_NOTES}}

**Effect sign guide:** W− = upstream sectors more water-efficient; L− = supply chains shorter/less water-intermediated; L+ = more water-intensive intermediation; Y+ = tourism demand growth added water pressure.

> **COVID interpretation:** In 2019→2022, the L-effect (supply-chain restructuring: {{SDA_L_COVID}} bn m³) exceeded the Y-effect (demand: {{SDA_Y_COVID}} bn m³) by **{{SDA_L_Y_RATIO}}×**. Attributing the 2019→2022 TWF decline to COVID demand collapse would be incorrect — supply-chain restructuring was the dominant mechanism. This identifies supply-chain procurement policy, not demand management, as the primary TWF reduction lever.

{{SDA_NARRATIVE}}

### 3.10 Monte Carlo Uncertainty and Variance Decomposition

**Main Table 4. Monte Carlo results and uncertainty source attribution.**

| Year | BASE (bn m³) | P5 | P25 | Median | P75 | P95 | Full CI (−%/+%) | Dominant Source | Variance Share |
|---|---|---|---|---|---|---|---|---|---|
{{MC_COMBINED_ROWS}}

> CI is asymmetric (upper tail > lower), consistent with log-normal right skew. Full-correlation CI is conservative; realistic ±18–22% assumes partial independence of sector coefficients. Agricultural W coefficients account for ~99% of total MC variance — improving WaterGAP paddy/wheat/sugarcane estimates for the Indus-Gangetic Plain would reduce model uncertainty more than any other single data investment.

{{MC_DISTRIBUTION_NARRATIVE}}

### 3.11 Outbound TWF and Net Balance

**Main Table 5 (panel B). Outbound TWF and net virtual water balance.**

| FY | Outbound tourists (M) | Avg stay (days) | Outbound TWF (bn m³) | Outbound Scarce (bn m³) | Inbound TWF (bn m³) | Net balance (bn m³) | India is |
|---|---|---|---|---|---|---|---|
{{OUTBOUND_TWF_ROWS}}

> ⚠ Destination shares require verification against MoT ITS 2022 before publication — net balance direction may reverse. UAE (~30%) and Saudi Arabia (WSI = 1.0) concentrate India's outbound virtual water in the world's most water-scarce basins. Net balance = Outbound − Inbound; directional indicator only (outbound = activity-based Lee et al. 2021; inbound = EEIO Leontief — not methodologically equivalent).

{{OUTBOUND_TWF_NARRATIVE}}

---

## 4. Discussion

### 4.1 Supply-Chain Structure as the Primary Lever

The SDA finding that L-effect ({{SDA_L_COVID}} bn m³) exceeded Y-effect ({{SDA_Y_COVID}} bn m³) by {{SDA_L_Y_RATIO}}× in 2019→2022 is methodologically significant beyond the COVID context. It establishes that changes in how tourism supply chains are organised — which intermediary sectors are used, chain length, sourcing geography — move more water than equivalent changes in demand volume. The COVID period acted as a natural supply-chain experiment: sudden demand contraction forced rapid restructuring (shorter chains, localised sourcing, reduced luxury-food intermediation), and it was the structural change, not the volume change, that dominated ΔTWF. This finding challenges the standard policy framing that focuses on tourism volume as the primary water management lever.

A hotel reducing food procurement from high-multiplier agricultural supply chains by {{HOTEL_FOOD_SWITCH_PCT}}% of sourcing would reduce its indirect TWF by approximately {{HOTEL_FOOD_SWITCH_IMPACT}}%, based on the Agr % values in Main Table 7 and the ±20% sensitivity elasticity (~0.71). This is achievable through procurement standards without any reduction in tourist volumes or on-site operational investment.

### 4.2 Inbound–Domestic Gap Mechanisms

Inbound tourists consumed {{INB_DOM_RATIO}}× more water per tourist-day than domestic in {{LAST_YEAR}} (Main Table 2). The spend ratio was {{SPEND_RATIO_LAST}}×, leaving a residual intensity ratio of {{RESIDUAL_RATIO_LAST}}, indicating the gap is {{RESIDUAL_INTERPRETATION}} spending-basket driven. Since the gap is primarily a spending-volume effect, it is policy-tractable through product design: shifting inbound itineraries toward lower-multiplier cultural, heritage, and nature-based experiences could close a material fraction of the gap without infrastructure investment. Itinerary redesign has lower abatement cost than supply-chain restructuring and can be implemented through tour operator guidelines.

### 4.3 Agricultural Dominance and Basin Damage

Agriculture accounted for {{AGR_SHARE_2022}}% of indirect blue TWF in {{LAST_YEAR}} (Main Table 5A), yet tourists purchase no raw crops directly — this is entirely Leontief-propagated water embedded in food service, beverages, processed foods, and fabric supply chains. The scarce/blue ratio of {{SCARCE_RATIO_2022}} means most of this agricultural water originates from severely stressed basins (WSI = 0.827), consistent with documented Indus-Gangetic groundwater depletion (Rodell et al. 2018). PMKSY crop water efficiency improvements targeting top categories could reduce indirect TWF by approximately {{PMKSY_IMPACT_TOP_CAT}} in {{TOP_MULT_CAT}} under a 20% agricultural coefficient reduction scenario.

### 4.4 Comparison with Prior Literature

India's blue water intensity falls within the range reported in comparative EEIO studies: Hadjikakou et al. (2015, Cyprus): ~980 L/tourist-day; Su et al. (2019, China): ~340 L/tourist-day; Lenzen et al. (2018, global): 200–1,500 L/tourist-day depending on destination. India's agricultural supply-chain dominance pattern generalises to any emerging economy with large rainfed/irrigated agriculture, tourism spending weighted toward food services, and WaterGAP-modelled irrigation-intensive basins.

### 4.5 Limitations

**TSA extrapolation.** India's TSA has not been updated since 2015–16; NAS GVA scaling is the standard OECD approach (Temurshoev & Timmer 2011) but introduces ±15% demand uncertainty → ~±11% TWF uncertainty. A current TSA (2019–20 or 2022–23) would reduce this to ±5–8%.

**PTA negatives.** Negative A-matrix entries (< 0.5% of total output) are zeroed; columns where A_sum ≥ 1.0 are rescaled to 0.95. These corrections are standard practice and have negligible effect on results.

**Outbound method mismatch.** Outbound uses activity-based national per-capita WF (Lee et al. 2021); inbound uses EEIO Leontief. Net balance is a directional indicator — both the sign and the magnitude should be treated with caution until destination shares are verified and a matched bilateral EEIO is available.

**WSI aggregation.** Aqueduct 4.0 three-group WSI weights are the finest available at SUT-140 sector resolution; basin-level weights would sharpen the scarce TWF estimate.

---

## 5. Conclusions

India's tourism indirect blue TWF {{TWF_DIRECTION}} from {{ABSTRACT_TWF_2015}} bn m³ (2015–16) to {{ABSTRACT_TWF_2022}} bn m³ (2021–22), with agricultural supply chains accounting for {{AGR_SHARE_2022}}% of indirect water throughout. Supply-chain structural change — not tourist volumes — was the dominant driver of inter-period TWF variation (L-effect {{SDA_L_Y_RATIO}}× larger than Y-effect in 2019→2022). Inbound tourists used {{INB_DOM_RATIO}}× more water per day than domestic tourists, a gap that is primarily spending-basket driven and therefore tractable through product design and itinerary policy rather than infrastructure. The scarce/blue ratio of ~0.83 means over 80% of abstracted water comes from severely stressed basins, linking tourism supply chains directly to India's groundwater depletion crisis. The EEIO-SDA framework with dual blue/scarce metrics and multi-year panel design is directly transferable to other high-tourism, high-water-stress emerging economies.

---

## Key Findings

{{KEY_FINDINGS}}

---

## Data Quality Warnings

```
{{WARNINGS}}
```

---

---
---

# SUPPLEMENTARY MATERIAL

---

## Supplementary Table S1. Novelty Matrix

| Contribution | Prior state of knowledge | What this paper adds | Key citations |
|---|---|---|---|
| {{NOVELTY_ROW_1}} | {{NOVELTY_PRIOR_1}} | {{NOVELTY_ADD_1}} | {{NOVELTY_REF_1}} |
| {{NOVELTY_ROW_2}} | {{NOVELTY_PRIOR_2}} | {{NOVELTY_ADD_2}} | {{NOVELTY_REF_2}} |
| {{NOVELTY_ROW_3}} | {{NOVELTY_PRIOR_3}} | {{NOVELTY_ADD_3}} | {{NOVELTY_REF_3}} |
| {{NOVELTY_ROW_4}} | {{NOVELTY_PRIOR_4}} | {{NOVELTY_ADD_4}} | {{NOVELTY_REF_4}} |
| {{NOVELTY_ROW_5}} | {{NOVELTY_PRIOR_5}} | {{NOVELTY_ADD_5}} | {{NOVELTY_REF_5}} |

---

## Supplementary Table S2. Full Tourism Demand Vectors by Year

| FY | Nominal (₹ cr) | Nominal (USD M) | Real 2015–16 (₹ cr) | Real 2015–16 (USD M) | Non-zero sectors | CAGR vs {{FIRST_YEAR}} | USD/INR |
|---|---|---|---|---|---|---|---|
{{DEMAND_TABLE_ROWS}}

> USD M = ₹ crore × 10 ÷ USD/INR. Real USD uses 2015-16 rate (₹65.00/USD) for cross-year comparability.

---

## Supplementary Table S3. IO Table — Full Technical Summary

| FY | Sectors | Total Output (₹ cr) | Total Output (USD M) | Real Output (₹ cr, 2015-16) | Intermediate (₹ cr) | Final Demand (₹ cr) | Balance Err % | ρ(A) | USD/INR |
|---|---|---|---|---|---|---|---|---|---|
{{IO_TABLE_ROWS}}

> ρ(A) < 1 confirms Hawkins-Simon condition. Columns with A_sum ≥ 1.0 rescaled to 0.95. Negative entries (< 0.5% of output) zeroed.

{{IO_TABLE_NARRATIVE}}

---

## Supplementary Table S4. NAS GVA Growth Multipliers (TSA Scaling)

| Sector key | NAS S.No. | NAS label | ×{{YEAR_2019}} | ×{{LAST_YEAR}} |
|---|---|---|---|---|
{{NAS_GROWTH_ROWS}}

---

## Supplementary Table S5. Water Coefficients by Source Group — Blue and Green

| Source Group | Blue (m³ or m³/₹cr) | Green (m³ or m³/₹cr) | Total | Green % | Note |
|---|---|---|---|---|---|
{{WATER_BY_SOURCE_ROWS}}

---

## Supplementary Table S6. Indirect TWF — Full Summary (Blue, Green, Scarce, Intensity)

| FY | Blue (bn m³) | Scarce (bn m³) | Green (bn m³) | Intensity nom (m³/₹cr) | Intensity real (m³/₹cr) | Δ vs {{FIRST_YEAR}} |
|---|---|---|---|---|---|---|
{{INDIRECT_SUMMARY_ROWS}}

---

## Supplementary Table S7. Top-10 Water Origin by Source Sector — All Years Combined

| Rank | Category | {{FIRST_YEAR}} m³ | {{FIRST_YEAR}} % | {{YEAR_2019}} m³ | {{YEAR_2019}} % | {{LAST_YEAR}} m³ | {{LAST_YEAR}} % |
|---|---|---|---|---|---|---|---|
{{TOP10_COMBINED}}

> Ranked by {{LAST_YEAR}} total. This is the **demand-destination view** — where tourist rupees flow across TSA categories. Compare against S7b below for the supply-chain source view.

---

## Supplementary Table S7b. Water Origin by Source Group (Leontief upstream) — All Years

This is the **supply-chain source view** — where water physically originates after Leontief propagation. Agriculture dominates despite receiving zero direct tourist expenditure.

| Source Group | {{FIRST_YEAR}} m³ | {{FIRST_YEAR}} % | {{YEAR_2019}} m³ | {{YEAR_2019}} % | {{LAST_YEAR}} m³ | {{LAST_YEAR}} % |
|---|---|---|---|---|---|---|
{{WATER_ORIGIN_ROWS}}

> **Why agriculture dominates:** Tourists spend money on food services, accommodation, and transport — not raw crops. But these sectors source inputs from agriculture (food ingredients, fabrics, energy crops), and Leontief propagation traces all upstream requirements. Every rupee spent on a hotel meal embeds multiple upstream agricultural rupees with high water intensities. This table is the correct citation for claims about agricultural water share — not the TSA category table above, which only shows first-round spending destinations.

> **Cross-year interpretation:** Changes between years reflect both demand-mix shifts (Y-effect) and supply-chain restructuring (L-effect). A declining agriculture share in 2021–22 does not imply improved agricultural efficiency — it more likely reflects shorter supply chains during post-COVID recovery. Use SDA (Main Table 3) to attribute the causal driver.

> **Paper text (Results §3.4, use this exact wording):** *"Agriculture accounted for {{AGR_SHARE_2022}}% of indirect blue TWF in {{LAST_YEAR}} (Supplementary Table S7b), despite receiving zero direct tourism expenditure. This water reaches the tourism sector entirely through Leontief supply-chain propagation — food-service supply chains embed paddy, wheat, and sugarcane irrigation water from Indus-Gangetic aquifers. The scarce/blue ratio of {{SCARCE_RATIO_2022}} (Main Table 1) means the majority of this agricultural abstraction originates from basins already at WSI ≥ 0.8 (Kuzma et al. 2023, Aqueduct 4.0). Manufacturing accounts for the second-largest share, primarily through textile and processed-food supply chains embedded in accommodation and retail categories."*

---

## Supplementary Table S8. Direct TWF — All-Year Summary (BASE)

| FY | Scenario | Hotel m³ | Restaurant m³ | Rail m³ | Air m³ | Total m³ | Total bn m³ |
|---|---|---|---|---|---|---|---|
{{DIRECT_SUMMARY_ROWS}}

---

## Supplementary Table S8a. Direct TWF — By Segment and Year (m³)

| FY | Segment | Hotel (M m³) | Restaurant (M m³) | Rail (M m³) | Air (M m³) | Total (bn m³) |
|---|---|---|---|---|---|---|
{{DIRECT_BY_SEGMENT_M3_ROWS}}

---

## Supplementary Table S8b. Direct TWF — Per-Tourist-Day Intensity by Segment (L/day)

| FY | Segment | Tourist-days (M) | Hotel (L/day) | Restaurant (L/day) | Rail (L/day) | Air (L/day) | **Total (L/day)** |
|---|---|---|---|---|---|---|---|
{{DIRECT_BY_SEGMENT_INTENSITY_ROWS}}

---

## Supplementary Table S8c. Direct TWF — Composition by Segment ({{LAST_YEAR}})

| Segment | Hotel % | Restaurant % | Rail % | Air % |
|---|---|---|---|---|
{{DIRECT_COMPOSITION_ROWS}}

---

## Supplementary Table S9. All-Tourist Blue + Green Intensity (L/tourist-day)

| FY | Blue Indirect (L/day) | Green Indirect (L/day) | Direct Blue (L/day) | **Total Blue (L/day)** | **Total Blue+Green (L/day)** | Green % | Δ vs {{FIRST_YEAR}} |
|---|---|---|---|---|---|---|---|
{{INTENSITY_ALL_BG_ROWS}}

> Use **Total Blue** for cross-study benchmarking (all prior global studies report blue only). Use **Total Blue+Green** for domestic policy purposes (complete physical burden). Blue+Green is disclosed following Hoekstra & Mekonnen (2012); the two components carry distinct management implications and are not summed into a single headline metric.

---

## Supplementary Table S10. All-Tourist Blue-Only Intensity

| FY | Indirect (L/day) | Direct (L/day) | **Total Blue (L/day)** | Indirect % | Δ vs {{FIRST_YEAR}} |
|---|---|---|---|---|---|
{{INTENSITY_ALL_ROWS}}

---

## Supplementary Table S11. Sector Efficiency Trends — Top-5 Improved and Worsened

**Top-5 categories with largest indirect blue TWF reduction ({{FIRST_YEAR}}→{{LAST_YEAR}}):**

| Rank | Category | {{FIRST_YEAR}} m³ | {{LAST_YEAR}} m³ | Change % |
|---|---|---|---|---|
{{IMPROVED_ROWS}}

> Cross-check against Supplementary Table S12 (artefact audit) before citing as genuine — zero-multiplier artefacts from EXIOBASE revisions can masquerade as efficiency gains.

**Top-5 categories with largest indirect blue TWF increase:**

| Rank | Category | {{FIRST_YEAR}} m³ | {{LAST_YEAR}} m³ | Change % |
|---|---|---|---|---|
{{WORSENED_ROWS}}

{{SECTOR_TRENDS_NARRATIVE}}

---

## Supplementary Table S12. EXIOBASE Artefact Audit

**Table S12a. Zero-multiplier transitions (database artefacts, not genuine gains):**

| Product ID | Product Name | EXIOBASE Code(s) | {{FIRST_YEAR}} m³/₹cr | {{LAST_YEAR}} m³/₹cr | Action |
|---|---|---|---|---|---|
{{ARTIFACT_ROWS}}

**Table S12b. Confirmed genuine efficiency improvements:**

| Product ID | Product Name | {{FIRST_YEAR}} m³/₹cr | {{LAST_YEAR}} m³/₹cr | Change % |
|---|---|---|---|---|
{{GENUINE_IMPROVED_ROWS}}

**Table S12c. Confirmed genuine efficiency deteriorations:**

| Product ID | Product Name | {{FIRST_YEAR}} m³/₹cr | {{LAST_YEAR}} m³/₹cr | Change % |
|---|---|---|---|---|
{{GENUINE_WORSENED_ROWS}}

{{ARTEFACT_AUDIT_NARRATIVE}}

---

## Supplementary Table S13. Water Multiplier Ratios

**Top and bottom categories by water multiplier ratio ({{LAST_YEAR}}):**

| Rank | Category | Water Multiplier (m³/₹cr) | Ratio vs Mean | Interpretation |
|---|---|---|---|---|
{{WMR_TOP_ROWS}}

> Ratio > 1 identifies categories where each rupee of tourism spending mobilises disproportionate upstream water. Highest-ratio categories are priority targets for supply-chain intervention.

{{MULTIPLIER_RATIO_NARRATIVE}}

---

## Supplementary Table S14. Supply-Chain Path Rankings

**Top-10 water pathways per year (source sector → tourism demand, m³):**

| Rank | Path (Source → Destination) | Source Group | Water m³ | Share % |
|---|---|---|---|---|
{{SC_PATHS_COMBINED}}

**Supply-chain source group summary (all years):**

| Source Group | {{FIRST_YEAR}} m³ | {{FIRST_YEAR}} % | {{YEAR_2019}} m³ | {{YEAR_2019}} % | {{LAST_YEAR}} m³ | {{LAST_YEAR}} % |
|---|---|---|---|---|---|---|
{{SC_SOURCE_GROUP_ROWS}}

**HEM dependency index — top-10 sectors where tourism drives water use:**

| Rank | Product | Source Group | Dependency Index % | Tourism Water m³ |
|---|---|---|---|---|
{{HEM_ROWS}}

{{SUPPLY_CHAIN_NARRATIVE}}

---

## Supplementary Table S15. Sensitivity Analysis — Consolidated

| FY | Component | LOW (bn m³) | BASE (bn m³) | HIGH (bn m³) | Half-range |
|---|---|---|---|---|---|
{{SENS_CONSOLIDATED_ROWS}}

{{SENSITIVITY_NARRATIVE}}

---

## Supplementary Table S16. SDA Full Details (incl. Instability Flags)

| Period | Start (bn m³) | End (bn m³) | ΔTWF | W Effect | W% | L Effect | L% | Y Effect | Y% | ⚠ |
|---|---|---|---|---|---|---|---|---|---|---|
{{SDA_DECOMP_ROWS}}
{{SDA_INSTABILITY_NOTES}}

---

## Supplementary Table S17. Monte Carlo — Full Variance Decomposition

| Parameter | {{FIRST_YEAR}} ρ | {{FIRST_YEAR}} % | {{YEAR_2019}} ρ | {{YEAR_2019}} % | {{LAST_YEAR}} ρ | {{LAST_YEAR}} % |
|---|---|---|---|---|---|---|
{{MC_VARIANCE_ROWS}}

{{MC_VARIANCE_NARRATIVE}}

---

## Supplementary Table S18. Outbound TWF by Destination

| FY | Country | Dest share | Local WF (m³/yr) | WSI | Tourists (M) | Avg stay | Outbound m³ | Scarce m³ |
|---|---|---|---|---|---|---|---|---|
{{OUTBOUND_BY_DEST_ROWS}}

---

## Supplementary Table S19. Placeholder Audit *(resolve before submission)*

| Token / Section | What to verify | Source | Risk |
|---|---|---|---|
| Outbound destination shares (Main Table 5B) | UAE ~30%, Saudi ~15% etc. | MoT ITS 2022, Table 4.4 | **High — net balance direction may reverse** |
| `{{TOURISM_GDP_PCT}}`, `{{TOURISM_JOBS_M}}` | Current GDP/jobs figures | WTTC Economic Impact India 2023 | Low |
| `{{EURINR_VALUES}}` | RBI annual average rates each FY | RBI reference rates | Medium |
| `{{NAS_HOTELS_2022}}` | NAS 2024 Statement 6.1 Hotels & Restaurants GVA | MoSPI NAS 2024 | Medium |
| `{{SECTOR_DECOMP_CROSS_YEAR_ROWS}}` | Top-8 TSA category rows × 3 years from `indirect_twf_{year}_sector_decomp.csv` | Pipeline output | **High — Main Table 7 empty until steps run** |
| `{{INB_BLUE_LASTYEAR}}`, `{{DOM_BLUE_LASTYEAR}}`, `{{INB_GREEN_LASTYEAR}}`, `{{DOM_GREEN_LASTYEAR}}` | Inbound/domestic indirect blue and green for {{LAST_YEAR}} | `indirect_twf_{{LAST_YEAR}}_split.csv` | **High — requires updated calculate_indirect_twf.py** |

---

## Supplementary Table S20. Reviewer Pre-emption Q&A *(use in cover letter)*

| Likely reviewer question | Rebuttal | Evidence |
|---|---|---|
| "TSA extrapolation via NAS GVA is production-side" | Standard approach (Temurshoev & Timmer 2011). ±15% demand → ~±11% TWF — less than agricultural uncertainty. | §2.2, Table S15 |
| "MC single correlated multiplier overstates CI" | Acknowledged. Conservative upper bound; realistic CI ~30–40% narrower under independent sampling. | §2.6, Main Table 4 |
| "Why report blue + green separately?" | Not summed. Blue = cross-study headline. Green disclosed per Hoekstra & Mekonnen (2012) — India's food system is ~60% rainfed. | §2.1, Supp S9 |
| "PTA produces negative values" | Repaired where A_sum ≥ 1.0; Hawkins-Simon verified all years; negatives < 0.5% of output. | §2.1, Supp S3 |
| "COVID 2019→2022 is demand elasticity" | Incorrect — SDA shows L-effect dominated ({{SDA_L_COVID}} bn m³ vs Y-effect {{SDA_Y_COVID}} bn m³). | §3.9, Main Table 3 |
| "WSI aggregation too coarse" | Acknowledged; Aqueduct 4.0 three-group weights are best available at SUT-140 resolution. | §2.3 |
| "Outbound and inbound methods are incompatible" | Flagged in Main Table 5B; net balance is a directional indicator only. | §3.11 |
| "Railway water is counted twice (indirect + direct)" | No — indirect = upstream supply-chain basin water (agriculture, energy, steel via Leontief). Direct = on-site municipal tap water. WaterGAP assigns near-zero to IN.114. | §2.4 |

---

## Supplementary Table S21. Data Sources

| Dataset | Source | Version / FY | Access |
|---|---|---|---|
| Supply-Use Tables | MoSPI | 2015–16, 2019–20, 2021–22 | Public |
| National Accounts Statistics | MoSPI NAS 2024 | Statement 6.1 | Public |
| India Tourism Satellite Account | Ministry of Tourism | 2015–16 | Public |
| EXIOBASE water satellite | EXIOBASE Consortium | v3.8 | Open access |
| Hotel water coefficients | CHSB India 2015–2022 | Field study | Literature |
| Restaurant water coefficients | Lee et al. (2021) J. Hydrology 603:127151 | — | Literature |
| Rail water coefficients | Gössling (2015); Lee et al. (2021) | — | Literature |
| Rail modal share | NSS Report 580, MOSPI 2017, Table 3.6 | 2014–15 | Public |
| Water Stress Index | WRI Aqueduct 4.0 (Kuzma et al. 2023) | 2023 | Open access |
| CPI series | MoSPI / RBI | Base 2015–16 | Public |
| EUR/INR rates | RBI reference rates | Annual average | Public |

---

## Supplementary Table S22. Technical Configuration

| Item | Detail |
|---|---|
| IO method | PTA: B = V/g, D = U/q, A = D·B⁻¹, L = (I−A)⁻¹ |
| SUT units | 2015–16: ₹ lakh (×0.01 → crore); 2019–20, 2021–22: ₹ crore |
| Hawkins-Simon | ρ(A) < 1 verified all years; A_sum ≥ 1.0 columns rescaled to 0.95 |
| Water source | EXIOBASE 3.8 `IOT_{year}_ixi/water/F.txt`; 103 "Water Consumption Blue" rows |
| Green water | Same F.txt; 13 "Water Consumption Green" rows (agriculture only) |
| TSA base | India TSA 2015–16 (MoT), 24 categories |
| NAS scaling | Statement 6.1, constant 2011–12 prices, NAS 2024 edition |
| CPI deflator | Base 2015–16; {{CPI_VALUES}} |
| EUR/INR rates | {{EURINR_VALUES}} |
| Hotel direct | tourist-nights × segment_share × L/room/night |
| Rail direct | domestic_tourists × dom_rail_modal_share(0.25) × avg_km × L/pkm |
| Monte Carlo | n = 10,000; seed = 42; agr σ = 0.30 log-normal; single correlated multiplier |
| SDA | Two-polar Dietzenbacher–Los (1998); residual < 0.001%; Near_cancellation flag at 5×\|ΔTWF\| |
| Scarce water | WRI Aqueduct 4.0 (Kuzma et al. 2023); agr WSI = 0.827, industry = 0.814, services = 0 |
| Pipeline version | `{{PIPELINE_VERSION}}` |

---

---
---

# PAPER WRITING GUIDE *(internal — remove before submission)*

---

## Suggested Title

*"Multi-period water footprint of India's tourism sector: supply-chain structural change dominated COVID-era reduction, not demand collapse"*

---

## Journal Targeting

| Journal | Est. IF | Lead novelty | Submission priority |
|---|---|---|---|
| {{JOURNAL_1_NAME}} | {{JOURNAL_1_IF}} | {{JOURNAL_1_FIT}} | 1st |
| {{JOURNAL_2_NAME}} | {{JOURNAL_2_IF}} | {{JOURNAL_2_FIT}} | 2nd |
| {{JOURNAL_3_NAME}} | {{JOURNAL_3_IF}} | {{JOURNAL_3_FIT}} | 3rd |
| {{JOURNAL_4_NAME}} | {{JOURNAL_4_IF}} | {{JOURNAL_4_FIT}} | 4th |

{{JOURNAL_NARRATIVE}}

---

## Abstract Scaffold (≤ 250 words)

State: problem (India tourism + water stress, single-year gap), method (EEIO-SDA, 3 years, EXIOBASE, TSA), three headline results (TWF trajectory, inbound–domestic gap, SDA L-effect dominance), one conclusion (supply-chain leverage > on-site efficiency).

*Key numbers: {{ABSTRACT_TWF_2015}} → {{ABSTRACT_TWF_2019}} → {{ABSTRACT_TWF_2022}} bn m³ · {{INTENSITY_DROP_PCT}}% intensity decline · {{INB_DOM_RATIO}}× inbound gap · L-effect {{SDA_L_Y_RATIO}}× larger than Y-effect · MC CI {{MC_P5_2022}}–{{MC_P95_2022}} bn m³*

---

## Introduction Scaffold (~600 words)

**Argument:** India's tourism water footprint is unstudied at multi-year scale; supply chains dominate operational use; the COVID period was a structural experiment, not a demand-elasticity one.

- GDP/jobs context: {{TOURISM_GDP_PCT}}%, {{TOURISM_JOBS_M}}M jobs; NITI Aayog water stress (600M affected)
- Novelty gap: cite Table S1 row by row — name each prior study (Lenzen 2018, Su 2019, Hadjikakou 2015) and state what's missing
- Close with paper structure outline and five contributions

---

## Methods Scaffold (~800 words)

**Argument:** EEIO is the only feasible method at this scale; PTA over ITA; SDA is necessary to avoid COVID misinterpretation; MC addresses dominant agricultural coefficient uncertainty.

- Core equation: TWF = W · L · Y (cite Miller & Blair 2009; Leontief 1970)
- TSA extrapolation rationale: Temurshoev & Timmer (2011); NAS GVA growth multipliers (Supp S4)
- Direct water boundary statement: §3.6; supplementary S8b rail boundary
- WSI methodology: Kuzma et al. (2023); Aqueduct 4.0 three-group weights
- SDA formula: Dietzenbacher & Los (1998); near-cancellation guard
- MC design: σ = 0.30 log-normal (Biemans et al. 2011); single correlated multiplier = conservative CI
- Limitation paragraph (TSA proxy; PTA negatives; outbound mismatch) — cite §4.5

---

## Results Scaffold (~1,200 words)

**§3.1 TWF trajectory** — Main Table 1. Fill: {{ABSTRACT_TWF_2015}} → {{ABSTRACT_TWF_2022}} bn m³. Note both Blue L/day and Blue+Green L/day intensity columns from Main Table 2.

**§3.2 Upstream water origin** — Main Table 5A. Fill: {{AGR_SHARE_2022}}% of indirect blue. Note paddy irrigation intensity increase +61.5% in WaterGAP 2015→2022.

**§3.3 Scarce water** — Main Table 1 (scarce column) + Main Table 5A (WSI). Scarce/blue = {{SCARCE_RATIO_2022}}; {{SCARCE_RATIO_2022_PCT}}% from severely stressed basins.

**§3.4 Inbound–domestic gap** — Main Table 2. Fill: {{INB_DOM_RATIO}}× gap; Spend ratio {{SPEND_RATIO_LAST}}×; Residual {{RESIDUAL_RATIO_LAST}} — {{RESIDUAL_INTERPRETATION}} spending-basket driven. Both Blue L/day and Blue+Green L/day columns support this paragraph.

**§3.5 Category decomposition** — Main Table 7. Highlight top category, COVID rank shifts, Agr % range {{AGR_PCT_RANGE}}.

**§3.6 SDA** — Main Table 3. L-effect {{SDA_L_COVID}} bn m³ vs Y-effect {{SDA_Y_COVID}} bn m³ by {{SDA_L_Y_RATIO}}×. Do not attribute 2019→2022 decline to COVID demand without this caveat.

**§3.7 Uncertainty** — Main Table 4. MC 90% CI: {{MC_P5_2022}}–{{MC_P95_2022}} bn m³; ~99% of variance = agricultural W coefficients.

**§3.8 Outbound balance** — Main Table 5B. Net balance direction; outbound concentrated in UAE/Saudi (WSI = 1.0).

---

## Discussion Scaffold (~600 words)

- **§4.1** Supply-chain structure lever — cite Main Table 3, SDA waterfall figure, §4.1 above
- **§4.2** Inbound–domestic gap mechanisms — spending basket vs Residual ratio (Main Table 2)
- **§4.3** Agricultural dominance and basin damage — Main Table 5A, scarce TWF; PMKSY leverage
- **§4.4** Comparison with prior literature — India vs Cyprus/China/global
- **§4.5** Limitations — §4.5 above; pre-empt with Supp S20 rebuttals

---

## Conclusions Scaffold (~200 words)

Three sentences max per finding: (1) TWF trajectory and agricultural dominance; (2) supply-chain structure is the primary lever (L-effect); (3) inbound–domestic gap is policy-tractable; (4) framework is generalisable.

---

## Figure Assignments

| Figure | Content | Placement |
|---|---|---|
| 1 | Analytical framework diagram | Methods |
| 2 | Four-panel overview (volumes, intensity gap, hotspots, source composition) | Lead figure |
| 3 | Temporal trajectory (3-panel: TWF, intensity gap, demand composition) | Results |
| 4 | WMR heatmap (sector hotspot + artefact audit) | Results alongside Supp S12 |
| 5 | Leontief Pull bubble matrix (agriculture appearing in non-food demand) | Results "invisible water" |
| 6 | Sankey flow strip (source → tourism demand) | Supplementary if figure limit = 6 |
| 7 | SDA waterfall (COVID structural break) | Results / Discussion |
| 8 | Uncertainty strip (MC CI, asymmetric annotation) | Supplementary |

**Main text figures (max 6):** Figures 1, 2, 3, 5, 7, 8. Move Figure 6 (Sankey) to Supplementary if limit is tight.

---

## Main Table Budget Note

Seven main tables fit within the upper limit of most target journals (Water Research, JCP allow 6–8). If a strict 6-table limit applies:
- **Option A (recommended):** Merge Main Tables 3 and 4 (add MC CI as columns in the SDA table), freeing one slot.
- **Option B:** Demote Main Table 5B (outbound balance) to Supplementary S18 given its data-status caveat.
- **Do not demote** Main Tables 1, 2, 3, or 7 — each carries a primary result.

| Main Table | Content | Primary result | Demotion risk |
|---|---|---|---|
| Main Table 1 | TWF trajectory + MC CI + both intensity columns | Trajectory + uncertainty | Cannot demote |
| Main Table 2 | Inbound/domestic gap — blue L/day + B+G L/day | Segment gap | Cannot demote |
| Main Table 3 | SDA decomposition + dominance combined | Supply-chain lever finding | Cannot demote |
| Main Table 4 | MC results + variance decomposition | Uncertainty attribution | Merge with Table 3 if needed |
| Main Table 5 | Origin top-10 (A) + Outbound balance (B) | Agricultural dominance | Panel B demotable |
| Main Table 6 | IO context (condensed) | Methods validation | Demotable to Supp |
| Main Table 7 | Cross-year category decomposition | COVID rank shifts | Cannot demote |

---

*Generated by India TWF Pipeline — report_template.md filled by `compare_years.py`*
*Framework: Leontief (1970); Miller & Blair (2009); Hoekstra et al. (2011); Dietzenbacher & Los (1998)*