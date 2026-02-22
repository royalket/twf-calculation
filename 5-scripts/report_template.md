# India Tourism Water Footprint — Run Report

> **Auto-generated** by the pipeline at the end of each successful `compare` step.
> All numbers are read directly from output CSVs — nothing is hardcoded.
> Re-run `python main.py --all` to refresh.

---

## Run Metadata

| Field | Value |
|---|---|
| Generated | {{RUN_TIMESTAMP}} |
| Study years | {{STUDY_YEARS}} |
| Steps requested | {{STEPS_REQUESTED}} |
| Steps completed | {{STEPS_COMPLETED}} |
| Steps failed / skipped | {{STEPS_FAILED_SKIPPED}} |
| Total runtime | {{TOTAL_RUNTIME}} |
| Pipeline log | `{{PIPELINE_LOG_PATH}}` |

---

## 1. IO Table Summary

Built from MoSPI Supply-Use Tables via Product Technology Assumption (PTA):
`D = V/q`, `Z = U·Dᵀ`, `A = Z/x`, `L = (I−A)⁻¹`

| FY | Products | Total Output (Rs cr) | Real Output (Rs cr 2015-16) | Intermediate (Rs cr) | Final Demand (Rs cr) | Balance Error % | ρ(A) |
|---|---|---|---|---|---|---|---|
{{IO_TABLE_ROWS}}

ρ(A) < 1 confirms the Hawkins-Simon condition holds for all years.

---

## 2. Tourism Demand  (TSA → NAS-scaled → EXIOBASE Y)

TSA 2015-16 extrapolated to 2019 and 2022 using NAS Statement 6.1 real GVA
growth (constant 2011-12 prices), multiplied by CPI deflator to get nominal
Rs crore consistent with the SUT data.

| Year | Nominal (Rs cr) | Real 2015-16 (Rs cr) | Non-zero EXIOBASE sectors | CAGR nominal vs 2015 |
|---|---|---|---|---|
{{DEMAND_TABLE_ROWS}}

### NAS real GVA growth multipliers applied

Source: MoSPI NAS 2024, Statement 6.1, constant 2011-12 prices.

| Sector key | NAS S.No. | Label | ×2019 | ×2022 |
|---|---|---|---|---|
{{NAS_GROWTH_ROWS}}

---

## 3. Indirect TWF  (W × L × Y)

Water embedded in tourism supply chains via the Leontief model.

### 3.1 Year-on-year summary

| Year | Total (bn m³) | Intensity (m³/Rs cr nominal) | Intensity (m³/Rs cr real) | Tourism Demand (Rs cr) | Δ vs {{FIRST_YEAR}} |
|---|---|---|---|---|---|
{{INDIRECT_SUMMARY_ROWS}}

### 3.2 Top-10 categories by water footprint — {{YEAR_2015}}

| Rank | Category | Total Water (m³) | Share % |
|---|---|---|---|
{{TOP10_2015}}

### 3.3 Top-10 categories — {{YEAR_2019}}

| Rank | Category | Total Water (m³) | Share % |
|---|---|---|---|
{{TOP10_2019}}

### 3.4 Top-10 categories — {{YEAR_2022}}

| Rank | Category | Total Water (m³) | Share % |
|---|---|---|---|
{{TOP10_2022}}

### 3.5 By sector type — where tourism demand lands

> **Interpretation note:** Agriculture shows 0 here because tourists do not
> purchase raw crops directly. Agricultural water is embedded inside the Food
> Manufacturing categories (34–50% of total) through Leontief supply-chain
> propagation. Section 3.6 shows where water physically *originates*.

| Sector Type | {{YEAR_2015}} m³ | {{YEAR_2015}} % | {{YEAR_2019}} m³ | {{YEAR_2019}} % | {{YEAR_2022}} m³ | {{YEAR_2022}} % |
|---|---|---|---|---|---|---|
{{SECTOR_TYPE_ROWS}}

### 3.6 By source sector — where water physically originates

Structural decomposition: `pull[i,j] = W[i] × L[i,j] × Y[j]` summed over all
tourism-demand destinations j, then grouped by the *upstream* sector i.

**Use this table — not 3.5 — when citing agricultural water share in publications.**
Agriculture here accounts for the true upstream extraction (typically 60–80 % of
indirect TWF) that flows through supply chains before reaching Food Manufacturing.

Source files: `indirect_twf_{year}_structural.csv`

| Source sector | {{YEAR_2015}} m³ | {{YEAR_2015}} % | {{YEAR_2019}} m³ | {{YEAR_2019}} % | {{YEAR_2022}} m³ | {{YEAR_2022}} % |
|---|---|---|---|---|---|---|
{{WATER_ORIGIN_ROWS}}

---

## 4. Direct TWF  (Activity-Based)

Operational water at point of use, estimated from activity data and
field-study coefficients (LOW / BASE / HIGH scenarios).

| Year | Hotels (M m³) | Restaurants (M m³) | Rail (M m³) | Air (M m³) | BASE (bn m³) | LOW (bn m³) | HIGH (bn m³) |
|---|---|---|---|---|---|---|---|
{{DIRECT_TABLE_ROWS}}

Hotel coefficient: {{HOTEL_2015}} → {{HOTEL_2019}} → {{HOTEL_2022}} L/room/night
({{HOTEL_CHG}} from {{FIRST_YEAR}} to {{LAST_YEAR}}, CHSB India data).

---

## 5. Total TWF  (Indirect + Direct BASE)

| Year | Indirect (bn m³) | Direct (bn m³) | Total (bn m³) | Indirect % | Direct % | Δ vs {{FIRST_YEAR}} |
|---|---|---|---|---|---|---|
{{TOTAL_TWF_ROWS}}

---

## 6. Per-Tourist Water Intensity

| Year | All tourists (L/day) | Domestic (L/day) | Inbound (L/day) | Dom tourists (M) | Inbound tourists (M) |
|---|---|---|---|---|---|
{{INTENSITY_ROWS}}

Allocation method: total water split proportionally by tourist-days
(domestic share × total m³ / dom tourist-days, and similarly for inbound).

---

## 7. Sector Efficiency Trends  ({{FIRST_YEAR}} → {{LAST_YEAR}}, indirect TWF)

### Most improved — indirect water fell most

| Rank | Category | {{FIRST_YEAR}} m³ | {{LAST_YEAR}} m³ | Change % |
|---|---|---|---|---|
{{IMPROVED_ROWS}}

### Most worsened — indirect water rose most

| Rank | Category | {{FIRST_YEAR}} m³ | {{LAST_YEAR}} m³ | Change % |
|---|---|---|---|---|
{{WORSENED_ROWS}}

---

## 8. Type I Multiplier — EXIOBASE Data Artefacts

Products whose multiplier was positive in {{FIRST_YEAR}} but became **exactly zero**
in {{LAST_YEAR}}. These are **not** genuine efficiency gains — they are EXIOBASE
database revisions where the upstream water coefficient was set to zero.
A genuine improvement stays > 0 in both years.

| Product ID | Product Name | EXIOBASE Code(s) | {{FIRST_YEAR}} m³/Rs cr | {{LAST_YEAR}} m³/Rs cr | Change % | Action |
|---|---|---|---|---|---|---|
{{ARTIFACT_ROWS}}

To investigate: compare the code(s) above between
`IOT_{{FIRST_YEAR}}_ixi/water/F.txt` and `IOT_{{LAST_YEAR}}_ixi/water/F.txt`.
If the zero reflects a data gap, impute using an adjacent year or sector average.

### Genuine top-5 improvements  (multiplier > 0 in both years)

| Product ID | Product Name | {{FIRST_YEAR}} m³/Rs cr | {{LAST_YEAR}} m³/Rs cr | Change % |
|---|---|---|---|---|
{{GENUINE_IMPROVED_ROWS}}

### Genuine top-5 deteriorations  (multiplier increased)

| Product ID | Product Name | {{FIRST_YEAR}} m³/Rs cr | {{LAST_YEAR}} m³/Rs cr | Change % |
|---|---|---|---|---|
{{GENUINE_WORSENED_ROWS}}

---

## 9. Sensitivity Analysis

### 9.1 Indirect TWF — ±20 % agricultural water coefficients

| Year | LOW (bn m³) | BASE (bn m³) | HIGH (bn m³) | Range ±% |
|---|---|---|---|---|
{{SENS_INDIRECT_ROWS}}

### 9.2 Direct TWF — coefficient scenarios

| Year | LOW (bn m³) | BASE (bn m³) | HIGH (bn m³) | Range ±% |
|---|---|---|---|---|
{{SENS_DIRECT_ROWS}}

### 9.3 Combined total  (indirect + direct, LOW / BASE / HIGH)

| Year | LOW (bn m³) | BASE (bn m³) | HIGH (bn m³) |
|---|---|---|---|
{{SENS_TOTAL_ROWS}}

---

## 10. Structural Decomposition Analysis (SDA)

Decomposes the change in indirect TWF between year-pairs into three drivers
using the two-polar decomposition method (eliminates residual term):

- **W effect** — change in water coefficients (technology / efficiency improvement)
- **L effect** — change in Leontief inverse (supply-chain structure / intermediation)
- **Y effect** — change in tourism demand (volume growth + composition shift)

`ΔTWF = W_effect + L_effect + Y_effect`  (residual < 0.01% confirms decomposition identity)

### 10.1 Decomposition by period

| Period | TWF Start (bn m³) | TWF End (bn m³) | ΔTWF (bn m³) | W Effect (bn m³) | W % | L Effect (bn m³) | L % | Y Effect (bn m³) | Y % |
|---|---|---|---|---|---|---|---|---|---|
{{SDA_DECOMP_ROWS}}

### 10.2 Interpretation

- A **negative W effect** means water technology improved (less water per unit output).
- A **negative L effect** means supply chains became less water-intensive.
- A **positive Y effect** means tourism demand growth added water pressure.

If Y effect dominates, policy priority is demand-side management (tourist volumes, product mix).
If W effect is small or positive, efficiency interventions in upstream sectors are needed.

See `sda/` for full CSV outputs and `waterfall_sda_{year}.png` for waterfall charts.

---

## 11. Monte Carlo Sensitivity Analysis

10,000 simulations sampling from probability distributions for all uncertain inputs.
Agricultural water coefficients: log-normal (σ=0.30). Hotel coefficients: log-normal (σ=0.25).
Tourist volumes: normal (σ=8% domestic, 5% inbound). Transport coefficients: normal (σ=20%).

### 11.1 Uncertainty distribution by year

| Year | BASE (bn m³) | P5 (bn m³) | P25 (bn m³) | Median (bn m³) | P75 (bn m³) | P95 (bn m³) | Range ±% | Top uncertainty source |
|---|---|---|---|---|---|---|---|---|
{{MC_SUMMARY_ROWS}}

### 11.2 Variance decomposition — what drives uncertainty most?

| Parameter | {{FIRST_YEAR}} corr | {{FIRST_YEAR}} share % | {{YEAR_2019}} corr | {{YEAR_2019}} share % | {{LAST_YEAR}} corr | {{LAST_YEAR}} share % |
|---|---|---|---|---|---|---|
{{MC_VARIANCE_ROWS}}

> **Note:** Spearman rank correlation between each input parameter and total TWF output.
> Share % = corr². Parameters dominating variance are priorities for better data collection.

See `monte_carlo/` for full simulation CSVs and `violin_monte_carlo.png` / `mc_variance_pie.png`.

---

## 12. Supply-Chain Path Analysis

### 12.1 Top-10 dominant pathways — {{FIRST_YEAR}}

Source → Destination pairs ranked by water contribution.

| Rank | Path (Source → Destination) | Source Group | Water (m³) | Share % |
|---|---|---|---|---|
{{SC_PATHS_2015}}

### 12.2 Top-10 dominant pathways — {{YEAR_2019}}

| Rank | Path (Source → Destination) | Source Group | Water (m³) | Share % |
|---|---|---|---|---|
{{SC_PATHS_2019}}

### 12.3 Top-10 dominant pathways — {{LAST_YEAR}}

| Rank | Path (Source → Destination) | Source Group | Water (m³) | Share % |
|---|---|---|---|---|
{{SC_PATHS_2022}}

### 12.4 Hypothetical Extraction Method — Top-10 tourism-dependent sectors ({{LAST_YEAR}})

> Dependency Index = sector's tourism-driven output as % of all tourism-driven output.
> High values mean the sector's viability depends heavily on tourism demand.

| Rank | Sector | Group | Dependency Index % | Tourism Water (m³) |
|---|---|---|---|---|
{{HEM_ROWS}}

### 12.5 Source-group water shares (top-50 paths)

| Source Group | {{FIRST_YEAR}} m³ | {{FIRST_YEAR}} % | {{YEAR_2019}} m³ | {{YEAR_2019}} % | {{LAST_YEAR}} m³ | {{LAST_YEAR}} % |
|---|---|---|---|---|---|---|
{{SC_SOURCE_GROUP_ROWS}}

See `supply_chain/` for full CSVs and per-year Markdown reports.
See `sc_paths_ranked_{year}.png` for ranked pathway bar charts.

---

## 13. Key Findings

{{KEY_FINDINGS}}

---

## 14. Data Quality Warnings

Warnings and errors recorded across all step log files from this run.

```
{{WARNINGS}}
```

---

## 15. Method and Configuration Notes

| Item | Detail |
|---|---|
| IO method | PTA: D = V/q, Z = U·Dᵀ, A = Z/x, L = (I−A)⁻¹ |
| Water source | EXIOBASE 3.8 F.txt, WaterGAP/WFN blue water, m³/EUR million → m³/Rs crore |
| TSA base | India TSA 2015-16 (MoT), 24 categories |
| NAS scaling | Statement 6.1, constant 2011-12 prices, NAS 2024 edition |
| CPI (base 2015-16) | {{CPI_VALUES}} |
| EUR/INR rates | {{EURINR_VALUES}} |
| SUT units | 2015-16: Rs lakh (×0.01 → crore) / 2019-20 and 2021-22: Rs crore |
| Reference | Lee et al. (2021) J. Hydrology 603:127151 |
| Data file | reference_data.md — all empirical constants with source citations |

---

*Generated by India TWF Pipeline — report_template.md filled by compare_years.py*
