# India Tourism Energy Footprint
## Multi-Year Environmentally Extended Input–Output Analysis

> **Generated:** {{RUN_TIMESTAMP}} · **Study Years:** {{STUDY_YEARS}} · **Runtime:** {{TOTAL_RUNTIME}}
> **Log:** `{{PIPELINE_LOG_PATH}}`

---

## Abstract

India's tourism sector embeds substantial energy demand in supply chains spanning electricity generation, petroleum refining, and manufacturing. This study applies an EEIO framework to MoSPI Supply-Use Tables for FY 2015–16, 2019–20, and 2021–22, paired with EXIOBASE 3.8 energy satellites (163 India sectors), estimating the indirect tourism energy footprint (IEF) across three periods spanning pre-COVID growth and recovery.

Tourism demand vectors are derived from India TSA 2015–16 extrapolated via NAS Statement 6.1 real GVA growth rates. Outbound energy is estimated from WTO departure statistics and per-tourist energy averages for key destination countries.

### Key Metrics at a Glance

| Metric | {{FIRST_YEAR}} | {{YEAR_2019}} | {{LAST_YEAR}} |
|--------|---------------|--------------|--------------|
| Indirect primary IEF (TJ) | **{{ABSTRACT_IEF_2015}}** | **{{ABSTRACT_IEF_2019}}** | **{{ABSTRACT_IEF_2022}}** |
| Fossil energy share (%) | — | — | **{{EMISSION_PCT_2022}}%** |
| Energy intensity change vs {{FIRST_YEAR}} | — | — | **−{{INTENSITY_DROP_PCT}}%** per ₹ cr |
| Outbound IEF (TJ) | — | — | **{{OUTBOUND_IEF_2022}}** |
| Net balance (TJ) | — | — | **{{NET_IEF_2022}}** ({{NET_BALANCE_DIRECTION}}) |

> **Sensitivity:** ±20% on electricity coefficients shifts total IEF by **{{ELEC_SENSITIVITY_PCT}}%**.

**Keywords:** tourism energy footprint · EEIO · India · indirect energy · fossil energy · outbound energy · COVID-19 · energy intensity

---

## 1. Introduction

Tourism contributes ~{{TOURISM_GDP_PCT}}% of India's GDP and is a significant energy consumer — directly (transport, accommodation) and indirectly through supply chains embedding electricity, petroleum, and industrial energy.

India's rapid electrification and petroleum dependency mean that supply-chain energy is a material climate risk in the tourism sector. This study covers **{{N_SECTORS}} SUT sectors** mapped to **{{N_EXIO_SECTORS}} EXIOBASE sectors** across three fiscal years:

- **2015–16** — pre-COVID baseline
- **2019–20** — peak year
- **2021–22** — post-COVID recovery

---

## 2. Methods

### 2.1 EEIO Framework

Supply-Use Tables (MoSPI, 140 products × 140 industries) are converted to IO tables via the **Product Technology Assumption (PTA)**:

```
B = V · diag(g)⁻¹        (industry output shares by product)
A = U · diag(q)⁻¹ · B⁻¹  (IO technical coefficients)
L = (I − A)⁻¹             (Leontief inverse)
```

The core EEIO identity for energy is:

```
IEF_indirect = E_final × L × Y    [MJ; total supply-chain embedded primary energy]
IEF_emission = E_fossil × L × Y   [MJ; fossil fuel portion only]
```

where **E_final** (140×140 diagonal) contains sector final energy intensities from EXIOBASE 3.8 (MJ/₹ crore), **E_fossil** contains emission-energy intensities, **L** is the Leontief inverse, and **Y** (140×1) is the tourism final demand vector.

### 2.2 Tourism Demand Vectors

India's TSA has not been updated since 2015–16. Demand vectors are extrapolated using NAS Statement 6.1 real GVA growth rates (constant 2011–12 prices). Separate inbound (Y_inb) and domestic (Y_dom) vectors are produced for each year.

### 2.3 Energy Coefficients

Final energy coefficients are extracted from EXIOBASE 3.8 energy satellite rows for India:
- `Final_Primary_MJ` — final primary energy use per ₹ crore of sectoral output
- `Emission_MJ` — fossil-fuel combustion portion (scope 1 + upstream scope 2)

### 2.4 Outbound Energy

```
Net_IEF = Outbound_IEF − Inbound_IEF_indirect
```

A **positive** net balance indicates India is a net energy *importer* via tourism (Indian tourists abroad consume more than inbound tourists consume in India).

---

## 3. Results

### 3.1 Cross-Year Indirect Energy Footprint

**Table 1. Indirect tourism energy footprint across study years.**

| FY | Primary IEF (TJ) | Primary IEF (PJ) | Outbound (TJ) | Net (TJ) | Emission % | Intensity (MJ/₹ cr) | Δ vs {{FIRST_YEAR}} |
|----|----------------:|----------------:|-------------:|---------:|-----------:|-------------------:|---------------------|
{{MAIN_TABLE_1_ROWS}}

> **Net balance** = Outbound − Inbound indirect.  Positive = India is a net energy *importer* via tourism.

{{TOTAL_IEF_NARRATIVE}}

---

### 3.2 Top Energy Sectors by Year

**Table 2. Top-10 upstream energy sectors (demand-destination view), ranked by {{LAST_YEAR}} Final Primary MJ.**

| Rank | Category | {{FIRST_YEAR}} TJ | {{FIRST_YEAR}} % | {{YEAR_2019}} TJ | {{YEAR_2019}} % | {{LAST_YEAR}} TJ | {{LAST_YEAR}} % |
|-----:|----------|------------------:|-----------------:|----------------:|-----------------:|----------------:|-----------------:|
{{TOP10_COMBINED}}

> Electricity and petroleum supply chains typically dominate due to high energy intensity coefficients propagated via the Leontief multiplier through food-processing, manufacturing, and transport sectors.

<details>
<summary>▶ Per-year detail (click to expand)</summary>

#### {{FIRST_YEAR}}
| Rank | Category | Final Primary (TJ) | Emission (TJ) | Energy % | Fossil % | Intensity (MJ/₹ cr) |
|-----:|----------|-----------------:|--------------:|---------:|---------:|-------------------:|
{{TOP10_2015}}

#### {{YEAR_2019}}
| Rank | Category | Final Primary (TJ) | Emission (TJ) | Energy % | Fossil % | Intensity (MJ/₹ cr) |
|-----:|----------|-----------------:|--------------:|---------:|---------:|-------------------:|
{{TOP10_2019}}

#### {{LAST_YEAR}}
| Rank | Category | Final Primary (TJ) | Emission (TJ) | Energy % | Fossil % | Intensity (MJ/₹ cr) |
|-----:|----------|-----------------:|--------------:|---------:|---------:|-------------------:|
{{TOP10_2022}}

</details>

---

### 3.3 Energy by Source Group (Upstream Origin)

**Table 3. Indirect energy by supply-chain source group.**

| Source Group | {{FIRST_YEAR}} TJ | {{FIRST_YEAR}} % | {{YEAR_2019}} TJ | {{YEAR_2019}} % | {{LAST_YEAR}} TJ | {{LAST_YEAR}} % |
|--------------|------------------:|-----------------:|----------------:|-----------------:|----------------:|-----------------:|
{{ENERGY_ORIGIN_ROWS}}

> Electricity and petroleum dominate. Manufacturing embeds energy via purchased inputs.

---

### 3.4 Inbound vs Domestic Split

**Table 4. Indirect energy split by tourist segment.**

| FY | Type | Final Primary (TJ) | Emission (TJ) | Demand (₹ cr) | IEF/₹ cr (MJ) |
|----|------|-----------------:|--------------:|-------------:|-------------:|
{{SPLIT_ROWS}}

{{SPLIT_NARRATIVE}}

---

### 3.5 Fossil Energy Share

**Table 5. Emission (fossil) energy share by year.**

| FY | Final Primary (TJ) | Emission (TJ) | Emission % | Change vs {{FIRST_YEAR}} |
|----|-----------------:|--------------:|-----------:|------------------------:|
{{EMISSION_ROWS}}

> A declining emission share indicates renewable energy penetration in the upstream economy; an increasing share indicates fossil lock-in.

---

## 4. Sensitivity Analysis

**Table 6. ±20% sensitivity on key energy coefficients.**

| FY | Component | Scenario | Total IEF (TJ) | Total IEF (GJ) | Δ% |
|----|-----------|----------|---------------:|---------------:|---:|
{{SENSITIVITY_ROWS}}

> A 20% reduction in electricity energy intensity (e.g. through renewable energy growth) would reduce total IEF by approximately **{{ELEC_SENSITIVITY_PCT}}%**, reflecting India's high coal-to-electricity share in EXIOBASE.

---

## 5. Cross-Year Intensity

**Table 7. Energy intensity per ₹ crore of tourism demand.**

| FY | Intensity (MJ/₹ cr) | Change vs {{FIRST_YEAR}} | Tourism Demand (₹ cr) | USD/INR |
|----|-------------------:|------------------------:|---------------------:|--------:|
{{INTENSITY_ROWS}}

> Declining intensity reflects supply-chain energy efficiency improvements and shifts in tourism demand composition toward lower-energy service sectors.

---

## 6. Key Findings

{{KEY_FINDINGS}}

---

## 7. Run Diagnostics

| Metric | Value |
|--------|-------|
| Steps requested | {{STEPS_REQUESTED}} |
| Steps completed | {{STEPS_COMPLETED}} |
| Steps failed / skipped | {{STEPS_FAILED_SKIPPED}} |
| Total runtime | {{TOTAL_RUNTIME}} |
| Pipeline log | `{{PIPELINE_LOG_PATH}}` |

{{WARNINGS}}

---

## Supplementary Tables

<details>
<summary>▶ E1 – IO Summary</summary>

| FY | Products | Total Output (₹ cr) | Total Output (USD M) | Balance Error % | Spectral Radius | USD/INR |
|----|--------:|-------------------:|--------------------:|---------------:|---------------:|--------:|
{{IO_TABLE_ROWS}}

</details>

<details>
<summary>▶ E2 – Tourism Demand Vectors</summary>

| FY | Nominal (₹ cr) | Nominal (USD M) | Real 2015–16 (₹ cr) | Real 2015–16 (USD M) | Non-zero sectors | CAGR vs {{FIRST_YEAR}} | USD/INR |
|----|--------------:|----------------:|--------------------:|--------------------:|-----------------:|----------------------:|--------:|
{{DEMAND_TABLE_ROWS}}

</details>

<details>
<summary>▶ E3 – NAS GVA Growth Rates</summary>

| Sector key | NAS S.No. | NAS label | ×{{YEAR_2019}} | ×{{LAST_YEAR}} |
|------------|-----------|-----------|---------------:|---------------:|
{{NAS_GROWTH_ROWS}}

</details>

<details>
<summary>▶ E4 – Indirect Energy Summary (All Years)</summary>

| FY | Primary IEF (TJ) | Primary IEF (bn MJ) | Emission MJ | Emission % | Intensity (MJ/₹ cr) | Inbound (bn MJ) | Domestic (bn MJ) | Top Sector | USD/INR |
|----|----------------:|--------------------:|------------:|-----------:|-------------------:|----------------:|-----------------:|------------|--------:|
{{INDIRECT_SUMMARY_ROWS}}

</details>

<details>
<summary>▶ E5 – Per-Year Category Detail</summary>

#### {{FIRST_YEAR}}
| Rank | Category | Category Type | Final Primary (MJ) | Emission (MJ) | Demand (₹ cr) | Energy % | Fossil % | Intensity (MJ/₹ cr) |
|-----:|----------|--------------|------------------:|--------------:|-------------:|---------:|---------:|-------------------:|
{{CATEGORY_ROWS_2015}}

#### {{YEAR_2019}}
| Rank | Category | Category Type | Final Primary (MJ) | Emission (MJ) | Demand (₹ cr) | Energy % | Fossil % | Intensity (MJ/₹ cr) |
|-----:|----------|--------------|------------------:|--------------:|-------------:|---------:|---------:|-------------------:|
{{CATEGORY_ROWS_2019}}

#### {{LAST_YEAR}}
| Rank | Category | Category Type | Final Primary (MJ) | Emission (MJ) | Demand (₹ cr) | Energy % | Fossil % | Intensity (MJ/₹ cr) |
|-----:|----------|--------------|------------------:|--------------:|-------------:|---------:|---------:|-------------------:|
{{CATEGORY_ROWS_2022}}

</details>

<details>
<summary>▶ E6 – Sensitivity Detail</summary>

| FY | Component | Scenario | Total IEF (MJ) | Total IEF (GJ) | Total IEF (TJ) | Δ% |
|----|-----------|----------|---------------:|---------------:|---------------:|---:|
{{SENSITIVITY_DETAIL_ROWS}}

</details>

<details>
<summary>▶ E7 – Outbound Energy</summary>

| FY | Outbound tourists (M) | Outbound IEF (TJ) | Inbound IEF (TJ) | Net IEF (TJ) | Direction |
|----|---------------------:|------------------:|-----------------:|-------------:|-----------|
{{OUTBOUND_ROWS}}

</details>

---

*Generated by `compare.py` · Study years: {{STUDY_YEARS}} · Formula: `IEF = E × L × Y  (MJ/₹ crore)`*
