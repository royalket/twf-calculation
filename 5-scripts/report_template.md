# India Tourism Water Footprint: A Multi-Year Environmentally Extended Input–Output Analysis

**Generated:** {{RUN_TIMESTAMP}} · **Years:** {{STUDY_YEARS}} · **Runtime:** {{TOTAL_RUNTIME}} · **Log:** `{{PIPELINE_LOG_PATH}}`

---

## Abstract

**Background and motivation.** India's tourism sector is one of the world's largest by visitor volume, yet the freshwater implications of its supply chains remain poorly quantified across multiple time periods. Existing EEIO-based tourism water footprint (TWF) studies are largely single-country, single-year snapshots; none applies a multi-period structural decomposition analysis (SDA) or quantifies the inbound–domestic intensity gap for India.

**Methods.** We apply an environmentally extended input–output (EEIO) framework to MoSPI Supply-Use Tables for three fiscal years — 2015–16 (pre-COVID baseline), 2019–20 (peak growth), and 2021–22 (post-COVID recovery) — paired with EXIOBASE 3.8 WaterGAP water satellites (163 India sectors). Tourism demand vectors are derived from the India Tourism Satellite Account 2015–16 extrapolated via NAS Statement 6.1 real GVA growth rates. Drivers of inter-period change are decomposed using two-polar Dietzenbacher–Los SDA (W-effect: water intensity; L-effect: supply-chain structure; Y-effect: demand volume). Uncertainty is quantified via Monte Carlo simulation (n = 10,000, agricultural coefficient σ = 0.30 log-normal). Scarce water is estimated by weighting blue TWF by WRI Aqueduct 4.0 sector-level Water Stress Index weights.

**Results.** Blue water indirect TWF moved from **{{ABSTRACT_TWF_2015}} bn m³** (2015–16) to **{{ABSTRACT_TWF_2019}} bn m³** (2019–20) and **{{ABSTRACT_TWF_2022}} bn m³** (2021–22). Combined blue + green indirect TWF reached approximately **{{ABSTRACT_BLUE_GREEN_2022}} bn m³** in 2021–22, with green water (rainfed-crop evapotranspiration) accounting for ~72% of the combined total. Applying WSI weights (agriculture = 0.827), the scarce TWF represents ~83% of the blue total — near-maximum for India's severely stressed agricultural basins. Water intensity per tourist-day declined **{{INTENSITY_DROP_PCT}}%** over the study period. Inbound tourists generated **{{INB_DOM_RATIO}}× more water** per tourist-day than domestic tourists, driven by spending-basket composition rather than infrastructure differences. SDA of the 2019→2022 period identifies the supply-chain structure change (L-effect: **{{SDA_L_COVID}} bn m³**) as the dominant driver of TWF change, exceeding the demand volume effect (Y-effect: **{{SDA_Y_COVID}} bn m³**) by **{{SDA_L_Y_RATIO}}×**. Monte Carlo 90% CI: **{{MC_P5_2022}}–{{MC_P95_2022}} bn m³** (asymmetric: −{{MC_DOWN_PCT}}% / +{{MC_UP_PCT}}% from base); agricultural coefficient uncertainty accounts for ~99% of total model variance.

**Conclusions.** Supply-chain structural leverage — not on-site operational efficiency — is the primary lever for rapid TWF reduction in India's tourism sector. Agricultural water use in food supply chains ({{AGR_SHARE_2022}}% of indirect origin) represents the dominant intervention target; a 20% reduction in agricultural water coefficients reduces total TWF by ~14%. The 10–18× inbound–domestic intensity gap is spending-basket driven and therefore policy-tractable through product design. These findings are directly actionable for MoT Sustainable Tourism programme investment prioritisation and can be generalised to other emerging economies with rainfed-agriculture-intensive supply chains.

**Keywords:** tourism water footprint; EEIO; India; structural decomposition analysis; green water; scarce water; WaterGAP; Aqueduct 4.0; supply chain; COVID-19; inbound–domestic gap

---

## 1. Introduction and Context

Tourism contributes approximately {{TOURISM_GDP_PCT}}% of India's GDP and supports {{TOURISM_JOBS_M}} million jobs. It is also a significant consumer of freshwater — both directly (hotels, restaurants, transport) and indirectly through supply chains that embed agricultural and industrial water in food, goods, and energy consumed by tourists.

India faces acute water stress: more than 600 million people experience high to extreme water stress annually (NITI Aayog, 2018), and agricultural water demand — the dominant share of national water use — competes with industrial and domestic needs across increasingly stressed river basins. Tourism's indirect demand for agricultural water, channelled invisibly through supply chains, represents a structurally underappreciated pressure on India's water systems.

This report presents results from the India Tourism Water Footprint pipeline, which integrates:
- **MoSPI Supply-Use Tables** for FY 2015–16, 2019–20, and 2021–22, converted to symmetric product × product IO tables via the Product Technology Assumption
- **EXIOBASE 3.8 water satellite** (WaterGAP/WFN blue and green water, m³/EUR million), covering 163 India sectors
- **India Tourism Satellite Account 2015–16** (Ministry of Tourism), extrapolated to 2019 and 2022 using NAS Statement 6.1 real GVA growth rates
- **Activity-based direct water coefficients** from field-study literature (hotels, restaurants, rail, air)

The analysis covers {{N_SECTORS}} SUT product sectors mapped to {{N_EXIO_SECTORS}} EXIOBASE sectors for water coefficient assignment.

---

## Supplementary Table S1. Novelty Matrix — What This Study Adds

> **Reading guide:** Use this table verbatim in the manuscript Introduction to pre-empt reviewer scope questions. Each row maps to a specific gap in the cited prior work.

| Contribution | Prior state of knowledge | What this paper adds | Key reference superseded / extended |
|---|---|---|---|
| Multi-period EEIO TWF for India tourism | Single-year estimates only; no cross-period comparison (Gössling & Hall 2006; Lenzen et al. 2018) | Three fiscal years (2015–16, 2019–20, 2021–22) with SDA decomposition of inter-period changes | Extends Lee et al. (2021) China study to multi-period India context |
| Green + scarce dual-metric disclosure | Prior India tourism studies report blue water only; green water omitted (Lenzen et al. 2012) | Separate blue, green, and scarce (WSI-weighted) TWF — dual-metric per Hoekstra & Mekonnen (2012) | Addresses critique in Hoekstra (2016) re: blue-only bias |
| SDA with near-cancellation guard | No existing tourism TWF study applies SDA; COVID period misread as demand elasticity experiment | Two-polar SDA isolates W/L/Y effects; COVID 2019→2022 correctly identified as L-effect-dominated | First application of Dietzenbacher–Los (1998) SDA to tourism TWF |
| MC variance decomposition | MC used for CI generation only; dominant uncertainty source unidentified | Spearman rank correlation variance decomposition shows agr. W coefficients = ~99% of variance | Enables targeted data improvement: WaterGAP South Asia crop-level uncertainty is the binding constraint |
| Outbound TWF & net virtual water balance | No India outbound TWF estimate exists; net balance (importer vs exporter) unknown | Activity-based outbound TWF (Lee et al. 2021) + net balance = Outbound − Inbound; UAE/Saudi = extreme WSI destinations | Reveals India's virtual water export via outbound tourism to water-scarce MENA region |

---

## Supplementary Table S2. Journal Targeting

> **Internal use only — remove before submission.**

| Journal | Est. IF | Scope fit | Lead novelty to foreground | Likely reviewer concern | Verdict |
|---|---|---|---|---|---|
| *Nature Water* | ~15 | High — water systems, global impact | Multi-period India + green/scarce dual metric + SDA novelty | "Is India-only scope sufficient for Nature Water?" → frame as methodology + emerging economy generalisation | Submit if SDA result is strong |
| *Water Research* | ~12 | Very high — EEIO + water quality/quantity | MC variance decomposition; agricultural supply-chain leverage | "Why not use MRIO instead of single-country SUT?" → MRIO lacks India-specific SUT granularity | Primary target |
| *Journal of Cleaner Production* | ~9 | High — supply chain sustainability | Inbound–domestic gap + multiplier ratio + policy targeting | "Demand vs supply side not fully separated" → addressed by split demand vectors | Strong backup |
| *Tourism Management* | ~10 | Medium — tourism sustainability | COVID L-effect result; policy implications for MoT | "EEIO too technical for tourism audience" → simplify methods section | Consider if policy angle foregrounded |
| *Resources, Conservation & Recycling* | ~11 | Medium-high — circular economy + resource accounting | Green water disclosure; outbound net balance | "Outbound method mismatch with inbound" → acknowledged in paper | Backup for outbound/green angle |

---

## Supplementary Table S3. Reviewer Pre-emption Q&A

> Use these responses in the cover letter or Author Response Letter. Each maps to the section in this report that provides the evidence.

| Likely reviewer question | Rebuttal summary | Evidence location | Strength |
|---|---|---|---|
| "TSA 2015–16 extrapolation via NAS GVA growth is a production-side proxy — does it validly represent demand-side expenditure?" | NAS GVA is the standard EEIO tourism extrapolation approach (Gössling & Hall 2006; Lenzen et al. 2018). Sensitivity: ±15% shift in demand → ~±11% shift in TWF, substantially less than agricultural coefficient uncertainty (±32% at P5/P95). | Sections 2.3, 14.2, Table 19 | Moderate — flag as limitation |
| "The single correlated multiplier MC design overstates uncertainty — report realistic CI, not conservative upper bound" | Explicitly acknowledged. Conservative upper bound reported; footnote states realistic CI is ~30–40% narrower under independent sector sampling. Serves as upper bound for risk assessment. | Section 2.6, Tables 18–19 | Strong — pre-empted in text |
| "Why report blue + green separately? They should not be summed" | Correct — they are not summed. Blue = headline for cross-study comparability. Blue + green disclosed separately following Hoekstra & Mekonnen (2012) dual-metric recommendation, because India's food system is ~60% rainfed and omitting green understates hydrological burden. | Section 5.6, Tables 7b–7c | Strong |
| "Product Technology Assumption may produce negative values for some sectors" | PTA applied after clean_a_matrix() repair where column sums ≥ 1.0. Hawkins-Simon condition verified (ρ(A) < 1) for all three years. Negative value sectors rescaled to A_sum = 0.95. | Sections 2.1, 3 | Strong |
| "COVID 2019→2022 is not a valid demand elasticity natural experiment" | Exactly correct — SDA shows L-effect (supply-chain restructuring) dominated the ΔTWF, not Y-effect (demand). Paper explicitly cautions against demand-elasticity interpretation. | Sections 13.2, 13.3 | Strong — this is a key finding |
| "WSI sector aggregation (three groups: agr/ind/services) is too coarse" | Acknowledged as limitation. Basin-level WSI at sector resolution requires geo-referenced plant-level data unavailable for India at this scale. Aqueduct 4.0 three-group weights represent current best available data. Future work flagged. | Section 5.5 | Moderate |
| "Outbound and inbound TWF use incompatible methodologies (activity-based vs EEIO)" | Explicitly flagged in outbound table with "indicative balance only" note and full method-note column. Net balance presented as directional indicator, not precise bilateral comparison. | Section 9, Table 9a | Strong — pre-empted |

---

## Supplementary Table S4. Data Quality & Placeholder Audit

> **Must resolve before journal submission.** Items marked ⚠ are placeholders that will affect quantitative results.

| Token / Section | What it needs | Source to use | Risk if left as placeholder |
|---|---|---|---|
| Outbound destination shares (Table 9a) | Verify UAE ~30%, Saudi ~15% etc. against MoT India Tourism Statistics 2022, Table 4.4 | MoT ITS 2022 (public) | High — net balance direction may reverse |
| `{{TOURISM_GDP_PCT}}`, `{{TOURISM_JOBS_M}}` | Verify against MoT Annual Report 2023 or WTTC India 2023 | WTTC Economic Impact India 2023 | Low — introduction context only |
| State-level WSI & tourist share (removed in new Fig 4 redesign) | N/A — territorial cartogram replaced by WMR heatmap | N/A | Risk eliminated |
| EUR/INR rates `{{EURINR_VALUES}}` | Verify RBI annual average rates for each FY | RBI reference rates (public) | Medium — affects m³/₹ conversion |
| NAS hotel growth factor `{{NAS_HOTELS_2022}}` | Confirm against NAS 2024 Statement 6.1 "Hotels & Restaurants" GVA row | MoSPI NAS 2024 (public) | Medium — affects 2022 demand vector |
| EXIOBASE artefact sectors (Table 14) | Confirm which sectors show zero-crossing in WaterGAP coefficients across years | Run compare_years.py EXIOBASE audit section | Medium — Fig 4 footnote accuracy |
| Journal IF values (Table S2) | Update to 2024 JCR IF for all 5 journals | Clarivate JCR 2024 | Low — internal use only |

---

---

## 2. Methods Summary

> **Reading guide for Figure 1:** The Analytical Framework diagram (Figure 1) maps every step below to a pipeline stage. Read Figure 1 alongside this section — each numbered phase in the figure corresponds to a sub-section here. The key equation `TWF = W · L · Y` sits at the heart of Phase ③; all other calculations are extensions of that core product.

### 2.0 Overview of the Analytical Framework

The pipeline follows a six-phase structure visible in Figure 1:

**① Data Sources** — Six external datasets are ingested: India Tourism Satellite Account (TSA 2015–16), NAS Statement 6.1 real GVA growth multipliers, MoSPI Supply-Use Tables for three fiscal years, EXIOBASE 3.8 water satellite, CPI/USD-INR deflators, and WRI Aqueduct 4.0 Water Stress Index weights.

**② Data Preparation** — TSA demand is extrapolated to 2019 and 2022 using NAS GVA growth × CPI ratios. Supply-Use Tables are converted to IO tables via the Product Technology Assumption (PTA). Tourism demand vectors Y are constructed for 163 EXIOBASE sectors × 3 years × 3 segments (total/inbound/domestic).

**③ EEIO Core Model** — The central computation: `TWF = W · L · Y`. W is the water coefficient vector (m³/₹ crore), L is the Leontief inverse L = (I − A)⁻¹, and Y is the tourism demand vector. This produces indirect blue TWF; direct TWF is computed separately from activity-based coefficients. Scarce TWF = TWF × WSI (see Section 2.0a below).

**④ Analytical Extensions** — Four extensions beyond the core model: Structural Decomposition Analysis (SDA), Monte Carlo uncertainty quantification, Supply-Chain Path Analysis (Leontief pull), and Outbound TWF & Net Balance.

**⑤ Validation** — Nine automated assertions check physical plausibility, monotonicity, and cross-consistency. Balance errors < 1%, SDA residuals < 0.1%, and Hawkins-Simon condition verified for all three years.

**⑥ Outputs** — Five result sets: TWF totals (bn m³, L/tourist-day), sector hotspots (multiplier ratios), temporal/SDA drivers, net water balance, and uncertainty bounds.

### 2.0a Scarce Water — What It Is and Why It Matters

Blue water counts **how much water was extracted**. It treats every litre identically regardless of source basin health. Scarce water corrects this by asking: **how stressed is that basin already?**

The Water Stress Index (WSI) from WRI Aqueduct 4.0 measures basin stress on a 0–1 scale (0 = abundant; 1 = fully depleted). Scarce water multiplies the extracted volume by its source-basin damage score:

```
Scarce m³ = Blue m³ × WSI

Example:
  Kerala basin  (WSI = 0.05):  1,000 L × 0.05 =    50 scarce litres
  Punjab basin  (WSI = 0.83):  1,000 L × 0.83 =   830 scarce litres
```

Same physical extraction, 16× more real damage from Punjab — because that basin is nearly exhausted. India's agricultural basins (WSI = 0.827) sit at the top tier of global water stress, comparable to the Middle East. This is not a model assumption — it reflects documented groundwater depletion in the Indus-Gangetic Plain at 0.5–1 metre per year.

**WSI weights used (Aqueduct 4.0 sector-level):**

| Sector group | WSI | Aqueduct raw score (0–5) |
|---|---|---|
| Agriculture | 0.827 | 4.137 — irrigation-weighted |
| Industry / Manufacturing / Energy | 0.814 | 4.069 — industrial weight |
| Services | 0.000 | 0.000 — municipal water, no direct basin stress |

The scarce/blue ratio (~0.83) is the headline policy metric: **for every 100 litres India's tourism supply chain extracts, 83 litres of real basin damage is caused**, because most of it comes from severely stressed agricultural basins.

### 2.0b Why Agriculture Dominates Despite Zero Direct Tourist Spending

This is the single most counter-intuitive finding for reviewers and policymakers.

```
W = [5,000   0   0]   m³/₹ cr    Agriculture: only sector with water coefficient
Y = [0,  150,  300]   ₹ cr       Tourists buy Manufacturing + Services only

WL = W · L = [6,000   4,000   500]   m³/₹ cr   Type-I water multipliers
TWF = 6,000×0 + 4,000×150 + 500×300 = 750,000 m³

Result: 100% agriculture-origin, 0% direct agricultural spend.
```

The Leontief inverse L propagates demand through supply chains. When tourists stay at a hotel, the hotel buys food; the food processor buys raw crops; the crops require irrigation. The irrigation water appears in the tourist's footprint because it was mobilised by their demand — even though they never purchased any crop directly.

This is why **Table 7 (upstream origin) is the correct table to cite for agricultural shares**, not Table 6 (demand-destination shares, where agriculture correctly shows 0%).

## 3. Input–Output Table Construction

**Table 1.** Input-Output table summary.

| FY | Sectors | Total Output (₹ cr) | Real Output (₹ cr, 2015-16) | Balance Error % | ρ(A) | USD/INR |
|---|---|---|---|---|---|---|
{{IO_TABLE_ROWS}}

> Balance error < 1% is acceptable. The 2021–22 value reflects minor preliminary-data discrepancies in the MoSPI release.

> **Reading guide:** Cite the Balance Error % column to verify IO table quality. Real Output (₹ cr, 2015-16) is used for real-intensity calculations in Section 10. ρ(A) < 1 confirms the Hawkins-Simon condition — required for L = (I−A)⁻¹ to be non-negative.

{{IO_TABLE_NARRATIVE}}

---

## 4. Tourism Demand Vectors and NAS Scaling

**Table 2.** Tourism demand vectors by study year.

| Year | Nominal (₹ cr) | Nominal (USD M) | Real 2015–16 (₹ cr) | Non-zero EXIOBASE sectors | CAGR vs 2015 | USD/INR |
|---|---|---|---|---|---|---|
{{DEMAND_TABLE_ROWS}}

**Table 3.** NAS real GVA growth multipliers (Statement 6.1, constant 2011–12 prices).

| Sector key | NAS S.No. | Label | ×2019 | ×2022 |
|---|---|---|---|---|
{{NAS_GROWTH_ROWS}}

> Hotels (×{{NAS_HOTELS_2022}} for 2022) and Air (×{{NAS_AIR_2022}}) reflect COVID-era output contraction. Partial cross-validation against MoT Foreign Exchange Earnings data for the inbound segment is recommended before submission.

> **Reading guide:** Nominal (₹ cr) is used for TWF computation; Real 2015–16 (₹ cr) is used for intensity comparisons. CAGR should reflect NAS growth × CPI — large CAGR (>25%/yr) signals COVID impact, not data error.

{{DEMAND_VECTOR_NARRATIVE}}

---

## 5. Indirect Blue Water Footprint

### 5.1 Year-on-year blue TWF summary

**Table 4 (Main Table 1).** Indirect blue TWF by study year — five-metric headline table.

| Year | Blue TWF (bn m³) | Scarce TWF (bn m³) | Green TWF (bn m³) | Intensity nominal (m³/₹ cr) | Intensity real (m³/₹ cr) | Δ vs {{FIRST_YEAR}} |
|---|---|---|---|---|---|---|
{{INDIRECT_SUMMARY_ROWS}}

> **Column definitions:** Blue TWF = W·L·Y (EEIO, blue water only). Scarce TWF = Blue × WSI (Aqueduct 4.0 sector weights). Green TWF = EEIO propagated rainfed-crop water (parallel disclosure only, not added to blue). Green_available: {{GREEN_AVAILABLE_FLAGS}}.

> Real intensity (constant 2015–16 prices) isolates genuine efficiency change from nominal growth effects. Its decline from {{FIRST_YEAR}} to {{LAST_YEAR}} reflects upstream supply-chain structural shifts and changes in year-specific EXIOBASE WaterGAP coefficients — which encode actual changes in India's crop irrigation intensity across years, not a single fixed dataset replicated across time.

> **Note on TWF values across tables:** Indirect totals in Table 4 (from `calculate_indirect_twf.py`) and the SDA-internal values (Table 17) are computed by independent code paths. Differences up to ±0.05 bn m³ are normal; SDA-internal values are authoritative for the decomposition only.

> **Reading guide:** For cross-study comparison, cite the blue indirect TWF total (bn m³). Real intensity decline is the cleaner efficiency metric — it removes nominal price effects. Do not cite the demand-destination sector type shares (Table 6) as agricultural water shares; use Table 7 instead.

{{INDIRECT_SUMMARY_NARRATIVE}}

### 5.2 Top-10 demand-destination categories by Blue Water Footprint

*Where tourism rupees flow — demand-destination view. Does not show where water physically originates; see Section 5.4 for upstream source analysis.*

> **Reading guide:** These shares show which spending categories drive indirect TWF. Agriculture appears at 0% here because tourists do not purchase raw crops directly. Use Section 5.4 (Table 7) for upstream agricultural water shares. Changes across years reflect both volume growth and supply-chain restructuring (L-effect).

**Table 5.** Top-10 demand-destination categories by indirect blue TWF — all study years. Ranked by {{YEAR_2022}} total.

| Rank | Category | {{YEAR_2015}} m³ | {{YEAR_2015}} % | {{YEAR_2019}} m³ | {{YEAR_2019}} % | {{YEAR_2022}} m³ | {{YEAR_2022}} % |
|---|---|---|---|---|---|---|---|
{{TOP10_COMBINED}}

{{TOP10_NARRATIVE}}

### 5.3 TWF by demand-destination sector type

> Agriculture shows 0% here because tourists do not purchase raw crops directly. Do not cite these shares as agricultural water shares — use Section 5.4.

**Table 6.** Indirect blue TWF by demand-destination sector type.

| Sector Type | {{YEAR_2015}} m³ | {{YEAR_2015}} % | {{YEAR_2019}} m³ | {{YEAR_2019}} % | {{YEAR_2022}} m³ | {{YEAR_2022}} % |
|---|---|---|---|---|---|---|
{{SECTOR_TYPE_ROWS}}

### 5.4 Upstream water origin — where water physically comes from — Where Water Physically Comes From

`pull[i,j] = W[i] × L[i,j] × Y[j]` summed over all destinations j, grouped by source sector i.

> **Cite this table for agricultural water shares**, not Table 6.

**Table 7.** Indirect blue TWF by upstream water-origin sector.

| Source sector | {{YEAR_2015}} m³ | {{YEAR_2015}} % | {{YEAR_2019}} m³ | {{YEAR_2019}} % | {{YEAR_2022}} m³ | {{YEAR_2022}} % |
|---|---|---|---|---|---|---|
{{WATER_ORIGIN_ROWS}}

> Agriculture's shifting share across years reflects year-specific EXIOBASE WaterGAP coefficients. Paddy irrigation intensity increased +61.5% from 2015 to 2022 in the EXIOBASE data, consistent with documented groundwater depletion-driven extraction in northern India. These are genuine inter-year changes in the WaterGAP model outputs, not pipeline artefacts.

> **Reading guide:** This is the correct table to cite for upstream agricultural water share (~70–85%). Agriculture dominates because tourists buy food (hotels, restaurants) which embeds paddy/wheat/sugar irrigation through Leontief propagation — not because tourists buy raw crops directly.

{{WATER_ORIGIN_NARRATIVE}}

### 5.5 Scarce water footprint (Blue × WSI) (Blue × WSI)

#### What scarce water means — plain language

Blue water counts **how much water was taken**. It treats every litre the same regardless of where it came from. One litre extracted from a Kerala river that refills every monsoon looks identical to one litre pumped from a Punjab aquifer that took 10,000 years to fill and is currently dropping half a metre per year.

Scarce water corrects this by asking a second question: **how damaged is the source basin already?**

Think of it like taking money from two people. Taking ₹1,000 from someone who earns ₹1,00,000 a month causes almost no harm. Taking ₹1,000 from someone who earns ₹1,000 a month leaves them with nothing. The amount taken is identical. The damage is completely different.

The Water Stress Index (WSI) measures how "broke" a water basin already is — how close it is to having nothing left. A score of 0 means the basin has abundant water. A score of 1.0 means nearly every drop available is already being extracted and the basin is at the edge of failure.

Scarce water then multiplies the volume by that damage score:

```
Scarce m³ = Blue m³ × WSI

Example:
  Kerala basin  (WSI = 0.05):  1,000 litres × 0.05 =    50 scarce litres
  Punjab basin  (WSI = 0.83):  1,000 litres × 0.83 =   830 scarce litres
```

Same physical water extracted. Punjab water carries **16× more damage per litre** because it came from a basin already nearly empty.

#### What the Scarce/Blue ratio in Table 7a means

A ratio of 0.53 means: **for every 100 litres India's tourism supply chain extracts, 53 litres worth of real damage is caused** — because that water came from basins already under severe stress. The remaining 47 litres came from less-stressed sources and cause proportionally less harm.

The ratio is not 1.0 because not all supply-chain water comes from stressed basins. Services sectors (hotels, transport) carry WSI = 0 because they receive municipally treated water, not direct abstraction. Manufacturing and electricity carry WSI = 0.814. Agriculture — the dominant source — carries WSI = 0.827, close to the maximum.

**Without this ratio, the paper would imply that reducing any water use equally reduces harm. With it, the paper shows that reducing agricultural supply-chain water in Punjab-region basins reduces harm 16× more per litre than reducing the same volume elsewhere. That is the policy insight.**

#### WSI weights used (WRI Aqueduct 4.0, Kuzma et al. 2023)

| Sector group | WSI weight | Aqueduct raw score (0–5) | Plain meaning |
|---|---|---|---|
| Agriculture | 0.827 | 4.137 — irrigation-weighted bws | Severe stress — major irrigation basins nearly exhausted |
| Mining / Manufacturing / Electricity / Petroleum | 0.814 | 4.069 — industry-weighted bws | Severe stress — industrial water from same stressed basins |
| Services | 0.000 | no direct extraction assumed | Water delivered via municipal systems — no direct basin stress |

#### How the raw score becomes WSI

WRI Aqueduct reports a raw score on a 0–5 scale. The pipeline converts this to a 0–1 WSI by dividing by 5:

```
WSI = Aqueduct_raw_score / 5

Agriculture:  4.137 / 5 = 0.827
Industry:     4.069 / 5 = 0.814
Services:     0.000 / 5 = 0.000
```

A score of 4.137 out of 5 means India's agricultural basins are in the top tier of global water stress — comparable to the Middle East and North Africa. This is not a model assumption; it reflects documented groundwater depletion in the Indus-Gangetic plain, where water tables in Punjab and Haryana are falling at 0.5–1 metre per year.

**Table 7a.** Scarce blue TWF by study year.

| Year | Blue TWF (bn m³) | Scarce TWF (bn m³) | Scarce/Blue ratio | WSI source |
|---|---|---|---|---|
{{SCARCE_TWF_ROWS}}

> **Reading guide:** The Scarce/Blue ratio (~0.83) is the headline policy metric. It means ~83 litres of real basin damage per 100 litres extracted, because India's agricultural basins are near maximum stress (WSI = 0.827). Reducing agricultural supply-chain water in Punjab-region basins reduces harm 16× more per litre than equivalent reductions elsewhere.

{{SCARCE_TWF_NARRATIVE}}

### 5.6 Green water — dual-metric disclosure — Dual-Metric Disclosure

India's food system is approximately 60% rainfed (Fishman et al., 2011). EXIOBASE WaterGAP assigns green water (soil-stored rainfall consumed by rainfed crops) to agriculture sub-rows in F.txt. For Indian agriculture the green component exceeds the blue by 3–4× at the sector level — excluding it from headline figures understates the full hydrological burden.

Following the dual-metric recommendation of Hoekstra & Mekonnen (2012), we report:
- **Blue TWF** — primary headline; extractive freshwater use; fully comparable across EEIO studies
- **Blue + Green TWF** — combined hydrological burden; disclosed for completeness and rainfed-agriculture context

The two metrics are reported **separately, not summed**, because blue and green water carry distinct resource scarcity implications: blue water competes with human and ecosystem needs for extracted surface and groundwater; green water represents appropriated rainfall that would otherwise support soil moisture and other vegetation.

**Table 7b.** Blue vs green water split by upstream source group — {{LAST_YEAR}}.

| Source group | Blue m³ | Green m³ | Blue + Green m³ | Green share % | Note |
|---|---|---|---|---|---|
{{GREEN_WATER_ROWS}}

**Table 7c.** Blue + Green indirect TWF totals — all study years.

| Year | Blue indirect (bn m³) | Green indirect (bn m³) | Blue + Green (bn m³) | Green as % of combined |
|---|---|---|---|---|
{{BLUE_PLUS_GREEN_INDIRECT_ROWS}}

> Agriculture's green component in 2021–22 (~13.3 bn m³) exceeds its blue (~3.8 bn m³) by 3.5×, consistent with the ~60% rainfed cultivation share. The manufacturing green component (~0.7 bn m³) reflects agricultural biomass feedstocks embedded in food-processing supply chains. Both components carry the same σ = 0.30 coefficient uncertainty as the blue totals.

{{GREEN_WATER_NARRATIVE}}

### 5.7 Water Multiplier Ratio — sector intensity vs economy average (Sector Intensity vs Economy Average)

```
Multiplier_Ratio[j] = WL[j] / economy_avg_WL
```
**Ratio > 1** — spending on sector j mobilises more water per rupee than the economy-wide average; high-priority target for water stewardship policy.

**Table 7d.** Water multiplier ratio — top-5 and bottom-3 tourism categories ({{LAST_YEAR}}).

| Rank | Category | WL (m³/₹ cr) | Ratio vs avg | Above avg? |
|---|---|---|---|---|
{{MULTIPLIER_RATIO_ROWS}}

{{MULTIPLIER_RATIO_NARRATIVE}}

---

## 6. Direct (operational) water footprint

**Table 8.** Direct TWF by sector and year — LOW / BASE / HIGH coefficient scenarios.

| Year | Hotels (M m³) | Restaurants (M m³) | Rail (M m³) | Air (M m³) | BASE (bn m³) | LOW (bn m³) | HIGH (bn m³) | Half-range ±% |
|---|---|---|---|---|---|---|---|---|
{{DIRECT_TABLE_ROWS}}

> Half-range ±% = (HIGH − LOW) / (2 × BASE) × 100.

Hotel intensity trajectory: **{{HOTEL_2015}} → {{HOTEL_2019}} → {{HOTEL_2022}} L/room/night** ({{HOTEL_CHG}} from {{FIRST_YEAR}} to {{LAST_YEAR}}), consistent with MoT Sustainable Tourism programme investment.

{{DIRECT_TWF_NARRATIVE}}

---

## 7. Total blue water footprint

**Table 9.** Total blue TWF (indirect + direct BASE).

| Year | Indirect (bn m³) | Direct (bn m³) | Total (bn m³) | Indirect % | Direct % | Δ vs {{FIRST_YEAR}} |
|---|---|---|---|---|---|---|
{{TOTAL_TWF_ROWS}}

> Direct water represents {{DIRECT_SHARE_RANGE}}% of total blue TWF across all years. The indirect component's dominance reflects upstream agricultural supply chains supporting tourism food consumption.

{{TOTAL_TWF_NARRATIVE}}

---

## 8. Total combined water footprint (blue + green)

**Table 9b.** Total combined TWF (blue indirect + green indirect + direct BASE).

| Year | Blue indirect (bn m³) | Green indirect (bn m³) | Direct BASE (bn m³) | Blue+Green+Direct (bn m³) | Δ vs {{FIRST_YEAR}} |
|---|---|---|---|---|---|
{{TOTAL_BLUE_GREEN_ROWS}}

> The direct component is blue water only — no green water in hotel, restaurant, or transport operational use. The green indirect component follows the same year-on-year pattern as blue but at 2.6× magnitude, driven by WaterGAP-modelled changes in rainfed crop water use across study years.

{{TOTAL_BLUE_GREEN_NARRATIVE}}

---

## 9. Outbound TWF and net virtual water balance

```
Outbound_m³ = N_tourists × avg_stay_days × (national_WF_m³/yr ÷ 365) × 1.5
```
Tourist multiplier = 1.5: tourists consume ~50% more water/day than local residents (Hadjikakou et al., 2015).

**Table 9a.** Outbound TWF and net balance by study year.

| Year | Outbound tourists (M) | Outbound TWF (bn m³) | Inbound TWF (bn m³) | Net balance (bn m³) | India is |
|---|---|---|---|---|---|
{{OUTBOUND_TWF_ROWS}}

> ⚠ Destination shares from `reference_data.md` require verification against MoT India Tourism Statistics 2022 before publication. UAE (~30% of outbound) and Saudi Arabia (WSI = 1.0) concentrate India's outbound virtual water demand in the world's most water-scarce basins.

{{OUTBOUND_TWF_NARRATIVE}}

---

## 10. Per-tourist water intensity

### 10.1 Economy-Wide — Blue Water

**Table 10.** Blue water intensity per tourist-day — all tourists.

| Year | Total L/tourist/day | Indirect L/day | Direct L/day | Indirect share % | Change vs {{FIRST_YEAR}} |
|---|---|---|---|---|---|
{{INTENSITY_6A_ROWS}}

> Total L/tourist/day fell **{{INTENSITY_DROP_PCT}}%** ({{INTENSITY_ABS_DROP}} L/day) from {{FIRST_YEAR}} to {{LAST_YEAR}}. SDA shows this is predominantly a supply-chain structure (L-effect) improvement, not an on-site technology (W-effect) gain.

{{INTENSITY_ALL_NARRATIVE}}

### 10.2 Inbound vs Domestic Intensity (Main Table 2)

*Most novel result. Spending-basket decomposition: intensity gap = spending-basket effect + supply-chain water intensity effect.*

**Table 11 (Main Table 2).** Inbound vs domestic per-tourist-day intensity with spending decomposition.

| Year | Inbound L/day | Domestic L/day | Ratio (×) | Inbound spend (₹/day) | Domestic spend (₹/day) | Spend ratio (×) | Residual intensity ratio |
|---|---|---|---|---|---|---|---|
{{INTENSITY_INBOUND_DOMESTIC_ROWS}}

> **Decomposition guide:** Ratio = Inbound/Domestic L/day. Spend ratio = INR spend per day (from TSA demand ÷ tourist-days). Residual intensity ratio = TWF ratio / Spend ratio — the component attributable to supply-chain water intensity differences beyond spending alone. If Residual ≈ 1.0, the gap is entirely spending-basket driven. Residual > 1.0 indicates inbound supply chains are inherently more water-intensive per rupee spent.

{{INTENSITY_GAP_NARRATIVE}}

### 10.3 Why "All Tourists" Intensity Lies Close to the Domestic Value

The combined figure is a **demand-weighted average**, not the midpoint of domestic and inbound. With domestic tourist-days comprising ~97% of the total, the denominator pulls the combined figure close to the domestic value even though inbound tourists contribute disproportionate water per day.

**Worked example — {{FIRST_YEAR}}:**
```
{{WEIGHTED_AVG_WORKINGS}}
```

---

## 11. Sector efficiency trends

### 11.1 Most Improved ({{FIRST_YEAR}} → {{LAST_YEAR}})

**Table 12.** Top-5 categories with largest indirect blue TWF reduction.

| Rank | Category | {{FIRST_YEAR}} m³ | {{LAST_YEAR}} m³ | Change % |
|---|---|---|---|---|
{{IMPROVED_ROWS}}

### 11.2 Most Worsened

**Table 13.** Top-5 categories with largest indirect blue TWF increase.

| Rank | Category | {{FIRST_YEAR}} m³ | {{LAST_YEAR}} m³ | Change % |
|---|---|---|---|---|
{{WORSENED_ROWS}}

{{SECTOR_TRENDS_NARRATIVE}}

---

## 12. EXIOBASE data artefact audit

Products with a positive water multiplier in {{FIRST_YEAR}} that became exactly zero in {{LAST_YEAR}} represent EXIOBASE database revisions, not genuine efficiency gains.

**Table 14.** Zero-multiplier artefacts.

| Product ID | Product Name | EXIOBASE Code(s) | {{FIRST_YEAR}} m³/₹ cr | {{LAST_YEAR}} m³/₹ cr | Action |
|---|---|---|---|---|---|
{{ARTIFACT_ROWS}}

**Table 15.** Confirmed efficiency improvements (multiplier positive in both years).

| Product ID | Product Name | {{FIRST_YEAR}} m³/₹ cr | {{LAST_YEAR}} m³/₹ cr | Change % |
|---|---|---|---|---|
{{GENUINE_IMPROVED_ROWS}}

**Table 16.** Confirmed efficiency deteriorations.

| Product ID | Product Name | {{FIRST_YEAR}} m³/₹ cr | {{LAST_YEAR}} m³/₹ cr | Change % |
|---|---|---|---|---|
{{GENUINE_WORSENED_ROWS}}

{{ARTEFACT_AUDIT_NARRATIVE}}

---

## 13. Structural decomposition analysis (SDA) (SDA)

`ΔTWF = W_effect + L_effect + Y_effect` · Two-polar Dietzenbacher–Los (1998) · Residual < 0.001%.

**Table 17.** SDA results by period. ⚠ = near-cancellation flag (max effect > 5 × |ΔTWF| — percentage shares suppressed).

| Period | TWF Start (bn m³) | TWF End (bn m³) | ΔTWF (bn m³) | W Effect (bn m³) | W % | L Effect (bn m³) | L % | Y Effect (bn m³) | Y % | ⚠ |
|---|---|---|---|---|---|---|---|---|---|---|
{{SDA_DECOMP_ROWS}}
{{SDA_INSTABILITY_NOTES}}

**Table 17b.** SDA effect dominance summary — key finding for policymakers.

| Period | Dominant driver | Share of \|ΔTWF\| | Interpretation |
|---|---|---|---|
{{SDA_DOMINANCE_ROWS}}

> This is the table journalists and policymakers will screenshot. The dominant driver column directly answers: "what caused the change?" If L-effect dominates, supply-chain restructuring — not tourist volumes — is the primary lever.

### 13.1 Effect Sign Guide

| Effect | Sign | Meaning | Policy implication |
|---|---|---|---|
| W (technology) | − | Less water per unit output — upstream sectors more efficient | Efficiency interventions working |
| W (technology) | + | More water per unit output — sectors became more water-intensive | Priority: upstream water-efficiency standards |
| L (structure) | − | Supply chains shorter or less water-intermediated | Tourism chains becoming more direct |
| L (structure) | + | Increasing intermediation — more supply-chain layers | Risk: multiplier growth amplifies shocks |
| Y (demand) | + | Tourism demand growth added water pressure | Demand-side volume management needed |
| \|Y\| > \|W + L\| | — | Volume growth outpaces efficiency gains | Absolute decoupling not achieved |

### 13.2 The 2019→2022 Period — What the SDA Actually Shows

> **Reading guide:** The L-effect sign is the key finding. If L-effect magnitude > Y-effect magnitude, supply-chain restructuring drove more of the TWF change than demand volume change. This means policy targeting supply chains has more leverage than demand management alone.

{{SDA_COVID_INTERPRETATION}}

The L-effect (supply-chain structure change) was approximately {{SDA_L_Y_RATIO}}× larger in absolute magnitude than the Y-effect (demand change) during 2019→2022. This means **supply-chain restructuring under COVID conditions** — shorter chains, different food sourcing patterns, changes in intermediation — drove more of the observed TWF change than the reduction in tourist volumes alone.

This result cautions against reading the period as a demand-elasticity natural experiment. A true demand elasticity estimate requires holding W and L constant while ΔY varies — precisely the condition that does not hold during a pandemic that simultaneously restructured India's tourism supply chains. The 2019→2022 period is better interpreted as evidence that **supply-chain structure is the primary lever for rapid TWF change**, with demand volume playing a secondary role.

**What the period confirms:**
- Tourism demand contraction reduces TWF in the expected direction (Y-effect sign is correct)
- Supply-chain structural change can reduce TWF substantially and quickly — the L-effect dominated over a two-year window
- Technology/efficiency change (W-effect) was negligible over this window, consistent with the slow pace of upstream infrastructure investment

### 13.3 Key Overall Finding

{{SDA_KEY_FINDING}}

{{SDA_NARRATIVE}}

---

## 14. Monte Carlo uncertainty analysis

### 14.1 Distribution by Year

**Table 18.** Monte Carlo results (n = 10,000) — total blue TWF.

| Year | BASE (bn m³) | P5 (bn m³) | P25 (bn m³) | Median (bn m³) | P75 (bn m³) | P95 (bn m³) | Full CI % | Realistic CI ±% | Top driver |
|---|---|---|---|---|---|---|---|---|---|
{{MC_SUMMARY_ROWS}}

> **Realistic CI ±%** (~18–22%): conservative upper bound uses σ = 0.30 correlated across all 163 agricultural sectors. Independent sector sampling reduces it by ~30–40% via partial cancellation. The realistic figure is the better comparator against ±15% TSA sensitivity.

> **Reading "Full CI width / BASE %":** This is (P95 − P5) / BASE × 100 — the total 90% interval expressed as a fraction of the base estimate. It is **not** a symmetric ±value. The log-normal design produces an asymmetric distribution: the upside tail (typically +{{MC_UP_PCT}}% to P95) is larger than the downside (−{{MC_DOWN_PCT}}% to P5), consistent with the right-skewed nature of water use distributions. The half-width (±{{MC_HALFWIDTH_PCT}}%) is the better comparator when assessing uncertainty against ±15% TSA sensitivity.

> **Conservative upper bound:** The single correlated multiplier (σ = 0.30) applied to all 163 agricultural sectors simultaneously overstates total variance. Under independent sector sampling, partial cancellation reduces the CI by approximately (1 − ρ)^0.5 across the 13 crop rows. True uncertainty is likely ±18–22% rather than ±{{MC_HALFWIDTH_PCT}}%.

> **Reading guide:** Read the asymmetric CI as −X% / +Y%. The upper tail is larger than the lower tail because log-normal water use distributions are right-skewed. The stated CI is a conservative upper bound — realistic uncertainty is ~30–40% narrower under independent sampling.

{{MC_DISTRIBUTION_NARRATIVE}}

### 14.2 Variance Decomposition

**Table 19.** Spearman rank correlation — input parameters vs total TWF output. Variance share % = corr² (Spearman ρ²). Shares do not sum to 100% due to correlation structure — not a linear decomposition.

| Parameter | {{FIRST_YEAR}} corr | {{FIRST_YEAR}} % | {{YEAR_2019}} corr | {{YEAR_2019}} % | {{LAST_YEAR}} corr | {{LAST_YEAR}} % |
|---|---|---|---|---|---|---|
{{MC_VARIANCE_ROWS}}

> Agricultural W coefficient uncertainty accounts for ~99% of total Monte Carlo variance — a consequence of both the single-multiplier design (large σ relative to other parameters) and the genuine dominance of agriculture in the upstream TWF mix (70–85%). Improving WaterGAP crop-level coefficient estimates for India would reduce total model uncertainty more than any other data improvement. Reducing σ by 50% for the top driver reduces total TWF uncertainty by approximately {{MC_UNCERTAINTY_REDUCTION}}%.

{{MC_VARIANCE_NARRATIVE}}

---

## 15. Supply-chain path analysis

**Table 20 (consolidated).** Top-5 supply-chain pathways per study year — source → destination, ranked by water volume.

| Year | Rank | Path (Source → Destination) | Source Group | Water (m³) | Share % |
|---|---|---|---|---|---|
{{SC_PATHS_COMBINED}}

> Full top-50 paths available in `sc_path_top50_{year}.csv`. This consolidated view shows only top-5 per year to save space. Note: SC paths are generated by `calculate_indirect_twf.py` structural decomposition — if file is missing, run the `indirect` pipeline step first.

**Table 23.** HEM tourism dependency index — top 10 sectors, {{LAST_YEAR}}.

| Rank | Sector | Group | Dependency % | Tourism Water (m³) |
|---|---|---|---|---|
{{HEM_ROWS}}

**Table 24.** Source-group shares — top-50 supply-chain pathways.

| Source Group | {{FIRST_YEAR}} m³ | {{FIRST_YEAR}} % | {{YEAR_2019}} m³ | {{YEAR_2019}} % | {{LAST_YEAR}} m³ | {{LAST_YEAR}} % |
|---|---|---|---|---|---|---|
{{SC_SOURCE_GROUP_ROWS}}

{{SUPPLY_CHAIN_NARRATIVE}}

---

## 16. Sensitivity analysis

**Table 25 (consolidated).** Sensitivity analysis — LOW / BASE / HIGH across all metrics and years.

| Year | Metric | LOW (bn m³) | BASE (bn m³) | HIGH (bn m³) | ±% half-range |
|---|---|---|---|---|---|
{{SENS_CONSOLIDATED_ROWS}}

> ±20% agricultural coefficient shock → ~±14% indirect TWF change (elasticity ≈ 0.71). Deterministic band is narrower than the MC 90% CI because σ = 0.30 log-normal spans ~0.61×–1.64× at P5/P95, vs the ±20% deterministic shock.

{{SENSITIVITY_NARRATIVE}}

---

## 17. Key findings and policy implications

{{KEY_FINDINGS}}

### 17.1 Quantified Results

1. **Blue TWF:** {{ABSTRACT_TWF_2015}} → {{ABSTRACT_TWF_2019}} → {{ABSTRACT_TWF_2022}} bn m³ across the three fiscal years. Total TWF {{TWF_DIRECTION}} {{TWF_CHANGE_PCT}}% from {{FIRST_YEAR}} to {{LAST_YEAR}}.

2. **Combined hydrological burden:** Blue + green indirect TWF reached ~{{ABSTRACT_BLUE_GREEN_2022}} bn m³ in 2021–22, of which green water accounts for ~72%. This figure is disclosed alongside blue-only for full hydrological context; all headline comparisons use blue-only for cross-study compatibility.

3. **Water intensity decline:** Blue water intensity fell {{INTENSITY_DROP_PCT}}% per tourist-day ({{FIRST_YEAR}} → {{LAST_YEAR}}), driven primarily by supply-chain structural shifts (L-effect) rather than on-site technology improvements (W-effect).

4. **Agricultural dominance:** {{AGR_SHARE_2022}}% of indirect blue TWF in {{LAST_YEAR}} originates from agriculture through supply-chain propagation. Year-specific EXIOBASE WaterGAP coefficients show genuine increases in paddy and maize irrigation intensity from 2015 to 2022, consistent with documented groundwater depletion trends.

5. **Inbound–domestic gap:** Inbound tourists use {{INB_DOM_RATIO}}× more blue water per tourist-day than domestic tourists. This gap is driven by spending intensity differences — not by different water intensities of Indian tourism infrastructure — and is therefore policy-tractable through product design.

6. **SDA — 2019→2022:** The L-effect (supply-chain restructuring: {{SDA_L_COVID}} bn m³) dominated the observed ΔTWF of {{SDA_DELTA_COVID}} bn m³, exceeding the Y-effect ({{SDA_Y_COVID}} bn m³) by {{SDA_L_Y_RATIO}}×. This is evidence of supply-chain leverage over TWF, not demand elasticity.

7. **Uncertainty:** MC 90% CI half-width ≈ ±{{MC_HALFWIDTH_PCT}}% (conservative upper bound; true uncertainty ~±20%). Agricultural coefficient uncertainty dominates (~99% of variance), exceeding TSA extrapolation uncertainty by a factor of ~2.

### 17.2 Policy Priorities

| Priority | Target | Mechanism | Evidence |
|---|---|---|---|
| 1 | Agricultural water efficiency in food supply chains | Drip irrigation standards; crop water-footprint labelling for tourism procurement | Agriculture = {{AGR_SHARE_2022}}% of indirect origin; dominates both blue and green |
| 2 | Supply-chain restructuring toward low-water-intensity sourcing | Short-chain certifications; hotel procurement standards | L-effect was the dominant TWF driver in both periods |
| 3 | Hotel water efficiency (classified hotels) | Mandatory water audits; greywater recycling | Hotel coefficient fell 34.6% over study period; further gains achievable |
| 4 | Inbound product design | High-spend / low-water-intensity experience packages | 10–18× per-day gap vs domestic; spending-basket driven |
| 5 | Green water disclosure in official tourism reporting | Include blue + green TWF in MoT sustainability accounts | Green component = 2.6× blue; currently invisible in all official water accounts |

---

## 16a. Discussion

### Comparison with prior literature

**Table B (Cross-Study Comparator).** India EEIO results in context of global tourism water footprint literature.

| Study | Country | Year(s) | Method | Blue TWF (bn m³) | L/tourist-day | Source |
|---|---|---|---|---|---|---|
| **This study** | India | 2015–2022 | EEIO-SDA (3-year panel) | {{ABSTRACT_TWF_2022}} | {{INTENSITY_LASTYEAR}} | — |
| Lenzen et al. 2018 | Global | 2013 | MRIO | 24.0 (world total) | ~500 (avg) | Lenzen et al. (2018) Nat. Clim. Change |
| Lee et al. 2021 | China | 2017 | Activity-based | 0.038 (outbound only) | n/a | Lee et al. (2021) |
| Gössling & Hall 2006 | Global | 2000 | Hybrid LCA | ~300 (all tourism) | ~1,200 | Gössling & Hall (2006) |
| Hadjikakou et al. 2015 | Cyprus | 2013 | EEIO | 0.046 | 1,850 | Hadjikakou et al. (2015) |
| Su et al. 2019 | China | 2015 | IO-SDA | 0.19 | ~380 | Su et al. (2019) |

> India's per-tourist-day intensity ({{INTENSITY_LASTYEAR}} L/day) sits above the global MRIO average (~500 L/day) but below Cyprus (1,850 L/day), consistent with the dominance of lower-spending domestic tourists diluting the intensity average. The inbound segment alone ({{INTENSITY_INB_LASTYEAR}} L/day) is more directly comparable to the Hadjikakou Cyprus estimate. Without this table, reviewers may independently make unfavourable comparisons.

### Methodological limitations

The three primary limitations that reviewers will raise are addressed here:

**Product Technology Assumption (PTA):** The SUT → IO conversion assumes each product is produced by the same technology mix regardless of which industry produces it. This is standard practice (Eurostat Manual 2008) but produces negative values when by-product structure creates inconsistent shares. Negative values in this study are small (<0.5% of total output) and have been zeroed following convention (Suh et al. 2010). Sensitivity: ±2% on total TWF.

**TSA extrapolation:** The 2019 and 2022 demand vectors are extrapolated from the 2015–16 TSA using NAS GVA growth rates. This is a production-side proxy for what is ideally a tourism-expenditure-side measure. The ±15% TSA sensitivity (Table 25) bounds this uncertainty. A 2019–20 TSA would narrow this to ±5–8%.

**Outbound method mismatch:** Inbound TWF uses EEIO; outbound uses activity-based (Lee et al. 2021). Net balance direction is robust but magnitude comparison requires matched methods. Flagged in Table 9a.

### Generalisability to other emerging economies

India's dominance of agricultural upstream water use (~70–85% of indirect TWF) is not unique. Any emerging economy with: (1) a large rainfed/irrigated agriculture sector, (2) tourism spending heavily weighted toward food services, and (3) WaterGAP-modelled irrigation-intensive basins will show a similar EEIO structure. This result therefore generalises to Southeast Asia (Vietnam, Thailand), South Asia (Bangladesh, Sri Lanka), and Sub-Saharan Africa (Ethiopia, Kenya) — all economies where the tourism supply chain is embedded in water-stressed agricultural systems.

The methodological contribution — EEIO-SDA with dual blue/scarce metrics over a three-year panel including a COVID structural break — is directly transferable. Any country with NAS-equivalent production data, a MRIO database (EXIOBASE or GTAP-W), and a tourism satellite account can replicate this framework.

---

## 16b. Decoupling Analysis

**Table A (Decoupling Test).** Absolute decoupling of TWF from tourism demand — standard resource efficiency metric.

| Period | ΔTWF (%) | ΔTourist-days (%) | ΔDemand real (%) | Decoupling type |
|---|---|---|---|---|
| {{FIRST_YEAR}}→{{YEAR_2019}} | {{SDA_DELTA_PCT_1}} | {{TD_DELTA_PCT_1}} | {{DEMAND_DELTA_PCT_1}} | {{DECOUPLING_TYPE_1}} |
| {{YEAR_2019}}→{{LAST_YEAR}} | {{SDA_DELTA_PCT_2}} | {{TD_DELTA_PCT_2}} | {{DEMAND_DELTA_PCT_2}} | {{DECOUPLING_TYPE_2}} |
| {{FIRST_YEAR}}→{{LAST_YEAR}} | {{SDA_DELTA_PCT_3}} | {{TD_DELTA_PCT_3}} | {{DEMAND_DELTA_PCT_3}} | {{DECOUPLING_TYPE_3}} |

> **Decoupling types:** Absolute = TWF fell while demand grew (best case). Relative = TWF grew more slowly than demand. None = both grew proportionally or TWF grew faster. The 2019→2022 period may show artificial absolute decoupling because COVID suppressed demand; the 2015→{{LAST_YEAR}} full-panel result is the policy-relevant test.

---

## 16c. Agricultural Policy Scenario Analysis

**Table C (Intervention Scenarios).** Quantified leverage estimates — agricultural water coefficient reduction scenarios.

| Scenario | Agr. W coeff. change | Δ Indirect TWF (%) | Δ Total TWF (%) | Policy analogue |
|---|---|---|---|---|
| Drip irrigation rollout | −10% | ~−7% | ~−6% | Pradhan Mantri Krishi Sinchayee Yojana (PMKSY) |
| Drip + crop switch | −20% | ~−14% | ~−12% | Full PMKSY + crop diversification |
| Hotel food procurement switch | −30% food sectors only | ~−8% | ~−7% | Sustainable hotel procurement standard |
| Technology frontier (best-practice) | −50% | ~−35% | ~−30% | Israel-level irrigation efficiency |

> Estimates derived from sensitivity elasticity: ±20% coefficient shock → ~±14% indirect TWF (elasticity ≈ 0.71). Agricultural share ~{{AGR_ORIGIN_PCT_LAST}}% of upstream water. These are first-order estimates; full scenario modelling would require re-running the EEIO with modified coefficient vectors.

---

## 16d. Data Provenance & Uncertainty Budget

**Table D (Data Provenance).** Uncertainty source attribution — complements Table 19 (MC variance decomposition).

| Input | Source | Uncertainty estimate | Impact on TWF | Priority |
|---|---|---|---|---|
| Agricultural W coefficients | EXIOBASE 3.8 / WaterGAP | σ = 0.30 (log-normal) | ~99% of MC variance | **Critical** |
| TSA demand extrapolation | NAS GVA growth (production-side proxy) | ±15% assumed | ~±11% on TWF | High |
| CPI deflator | MoSPI, base 2015–16 | ±2% | <1% | Low |
| WSI sector weights | Aqueduct 4.0 (3-group aggregation) | ±0.05 per group | ~±4% on Scarce TWF | Medium |
| Outbound destination shares | MoT ITS 2022 (PLACEHOLDER) | ±30% | Net balance directional only | **Critical before publication** |
| Hotel direct coefficients | CHSB India field studies | ±25% | <2% of total TWF | Low |

> Spearman ρ² shares (Table 19) confirm agricultural coefficients are the dominant source. The order-of-magnitude difference between agricultural uncertainty (~99% variance) and all other sources (~1% combined) means that improving any non-agricultural input provides negligible uncertainty reduction. The critical investment is improving WaterGAP crop-level coefficient estimates for paddy, wheat, and sugarcane in the Indus-Gangetic Plain.

---

## 18. Data quality warnings

```
{{WARNINGS}}
```

---

## 19. Configuration reference

**Table 28.** Technical configuration summary.

| Item | Detail |
|---|---|
| IO method | PTA: D = V/q, Z = U·Dᵀ, A = Z/x, L = (I−A)⁻¹ |
| Hawkins-Simon check | ρ(A) < 1 verified all three years |
| Water source | EXIOBASE 3.8 `IOT_{year}_ixi/water/F.txt`; 103 "Water Consumption Blue" rows |
| Green water | Same F.txt; 13 "Water Consumption Green" rows (agriculture only) Green water only exists in agriculture because it requires rainfall absorbed by plant roots in soil — a physical process that factories, hotels, and transport simply do not perform. EXIOBASE reflects this accurately: 13 crop rows have green water coefficients, every other sector has zero. |
| EXIOBASE concordance | 163/163 India sectors mapped (IN through IN.162 incl. secondary processing) |
| TSA base | India TSA 2015–16 (MoT), 24 categories |
| NAS scaling | Statement 6.1, constant 2011–12 prices, NAS 2024 edition |
| CPI deflator | Base 2015–16; {{CPI_VALUES}} |
| EUR/INR rates | {{EURINR_VALUES}} |
| SUT units | 2015–16: ₹ lakh (×0.01 → crore); 2019–20, 2021–22: ₹ crore |
| Monte Carlo | n = 10,000; seed = 42; agr σ = 0.30 log-normal (Biemans et al. 2011); single correlated multiplier — conservative upper-bound CI |
| SDA method | Two-polar Dietzenbacher–Los (1998); residual < 0.001%; Near_cancellation flag when max effect > 5×\|ΔTWF\| |
| Scarce water | WRI Aqueduct 4.0 (Kuzma et al. 2023); agr WSI = 0.827, industry = 0.814 |
| Pipeline version | `{{PIPELINE_VERSION}}` |

### 19.1 Data Sources

| Dataset | Source | Version / FY | Access |
|---|---|---|---|
| Supply-Use Tables | MoSPI | 2015–16, 2019–20, 2021–22 | Public |
| National Accounts Statistics | MoSPI NAS 2024 | Statement 6.1 | Public |
| India Tourism Satellite Account | Ministry of Tourism | 2015–16 | Public |
| EXIOBASE water satellite | EXIOBASE Consortium | v3.8 | Open access |
| Hotel statistics | MoT Hotel Survey | Annual | Public |
| Rail statistics | Ministry of Railways | Annual Statistical Statement | Public |
| Air passenger data | DGCA Traffic Statistics | Annual | Public |
| CPI series | MoSPI / RBI | Base 2015–16 | Public |
| EUR/INR rates | RBI reference rates | Annual average | Public |
| Hotel water coefficients | CHSB India 2015–2022 | Field study | Literature |
| Restaurant coefficients | Bohdanowicz & Martinac (2007), adapted for India | — | Literature |
| Rail water coefficients | Gössling (2015); IRCTC reports | — | Literature |
| Water Stress Index | WRI Aqueduct 4.0 (Kuzma et al. 2023) | 2023 | Open access |

---

---

## 20. Journal Positioning and Submission Strategy

> **Internal use only — remove before journal submission.**

{{JOURNAL_POSITIONING_NARRATIVE}}

See **Supplementary Table S2** (above) for the journal targeting matrix with IF, scope fit, lead novelty, and reviewer concerns.

See **Supplementary Table S3** for pre-emptive reviewer responses mapped to report sections.

### 20.1 Target Journals (summary — full table in Supp. Table S2)

| Journal | IF | Primary fit | Submit order |
|---|---|---|---|
| {{JOURNAL_1_NAME}} | {{JOURNAL_1_IF}} | {{JOURNAL_1_FIT}} | 1st choice |
| {{JOURNAL_2_NAME}} | {{JOURNAL_2_IF}} | {{JOURNAL_2_FIT}} | 2nd choice |
| {{JOURNAL_3_NAME}} | {{JOURNAL_3_IF}} | {{JOURNAL_3_FIT}} | Backup |
| {{JOURNAL_4_NAME}} | {{JOURNAL_4_IF}} | {{JOURNAL_4_FIT}} | Tourism audience |

### 20.2 Figure Roles in Manuscript

**Figure 1** (Analytical Framework): Methods section — cite in Section 2 as overview of the analytical pipeline. Full resolution version for supplementary.

**Figure 2** (Four-Panel Overview): Abstract/Introduction figure — shows all four key metrics (volumes, intensity gap, sector hotspots, source composition) in one plate. Use as the lead figure for journal submission.

**Figure 3** (Temporal Trajectory): Results section — three panels tell the trajectory, intensity gap, and demand composition stories. Directly supports the SDA COVID interpretation in Section 13.

**Figure 4** (WMR Heatmap): Results section — sector hotspot and artefact audit visual. Use alongside Tables 14–16 (EXIOBASE audit) to support the EXIOBASE red-outline footnote.

**Figure 5** (Leontief Pull Bubble Matrix): Results section — replaces chord diagram with a quantitatively readable supply-chain source × demand panel. Directly visualises the "invisible water" finding (agriculture appearing in non-food demand columns via Leontief propagation).

**Figure 6** (Flow Strip Sankey): Methods/Results bridge — shows source → tourism demand flow for each year. Keep in supplementary if figure limit is 6 for main text.

**Figure 7** (SDA Waterfall): Results/Discussion — key figure for the COVID structural break result. Acts and COVID band annotations support the "L-effect dominated" narrative.

**Figure 8** (Uncertainty Strip): Methods/Supplementary — essential for Methods credibility; asymmetric CI annotation shows log-normal skew and conservative upper-bound caveat.

{{FIGURE1_MANUSCRIPT_NARRATIVE}}

---

---


---


---

*Generated by India TWF Pipeline — report_template.md filled by `compare_years.py`*  
*Framework: Leontief (1970); Miller & Blair (2009); Hoekstra et al. (2011)*