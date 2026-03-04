# India Tourism Water Footprint (TWF) Pipeline

**Method:** Environmentally Extended Input-Output Analysis (EEIO) + Activity-Based Direct Water  
**Study years:** 2015, 2019, 2022 (fiscal years 2015-16, 2019-20, 2021-22)  
**Reference:** Lee et al. (2021) *Water footprint of Chinese tourists.* J. Hydrology 603:127151

---

## Table of Contents

1. [Core formula and what every term means](#1-core-formula-and-what-every-term-means)
2. [Why two components?](#2-why-two-components-the-eeio-zero-service-problem)
3. [Data sources](#3-data-sources)
4. [Directory structure](#4-directory-structure)
5. [Pipeline — 8 steps](#5-pipeline--8-steps)
6. [Step 1 — Build IO tables](#6-step-1--build-io-tables)
7. [Step 2 — Water coefficients](#7-step-2--water-coefficients)
8. [Step 3 — Tourism demand](#8-step-3--tourism-demand)
9. [Step 4 — Indirect TWF](#9-step-4--indirect-twf)
10. [Step 5 — Direct TWF](#10-step-5--direct-twf)
11. [Step 6 — SDA + Monte Carlo + Supply-Chain](#11-step-6--sda--monte-carlo--supply-chain)
12. [Step 7 — Visualise](#12-step-7--visualise)
13. [Step 8 — Cross-year comparison](#13-step-8--cross-year-comparison)
14. [Concordance design: EXIOBASE 163 → SUT 140](#14-concordance-design-exiobase-163--sut-140)
15. [Demand-destination vs source-sector views](#15-demand-destination-vs-source-sector-views)
16. [Expected results and benchmarks](#16-expected-results-and-benchmarks)
17. [Sensitivity and uncertainty](#17-sensitivity-and-uncertainty)
18. [Running the pipeline](#18-running-the-pipeline)

---

## 1. Core formula and what every term means

### Indirect TWF

```
TWF_indirect = W @ L @ Y                         [units: m³]

W[i]     = water coefficient of sector i          [m³ per ₹ crore of output]
           Source: EXIOBASE 3 F.txt (WaterGAP + WFN measurements)
           mapped from EXIOBASE 163 sectors → SUT 140 products via concordance

L[i,j]   = Leontief inverse element (i,j)         [₹ crore of sector i needed
           = (I − A)^{-1}                          per ₹ crore of final demand j]
           Built from MoSPI SUT via Product Technology Assumption (PTA)

Y[j]     = tourism final demand for product j      [₹ crore]
           Built from TSA 2015-16 expenditure shares × NAS growth rates
```

**Step-by-step example** (3 sectors, to make it concrete):

```
W  = [5000,    0,    0]   # only Agriculture extracts water (m³/crore)
L  = [[1.20, 0.80, 0.10], # L[agr,food]: 1 crore of food demand
      [0.30, 1.50, 0.20], #   needs 0.80 crore of agr input
      [0.40, 0.60, 1.30]]
Y  = [0, 150, 300]        # tourists buy Food (150 cr) and Services (300 cr)
                          # not raw Agriculture (0 cr)

Step 1:  WL  = W @ L
             = [5000×1.20 + 0×0.30 + 0×0.40,  …,  …]
             = [6000, 4000, 500]   # m³ water multiplier per crore of demand

Step 2:  TWF = WL * Y  (element-wise)
             = [6000×0, 4000×150, 500×300]
             = [0, 600,000, 150,000]  m³

Total TWF_indirect = 750,000 m³

Key insight: Agriculture column in Y is 0 (tourists don't buy raw paddy),
but agricultural water (W[agr]=5000) propagates through L into every
sector that uses agricultural inputs — here captured in Food (600,000 m³).
```

### Pull matrix — structural decomposition

The full matrix `pull[i,j] = W[i] × L[i,j] × Y[j]` (shape 140×140) tells you **exactly which upstream sector `i` supplied water for each tourism demand `j`**:

- Sum across columns (Σⱼ): water extracted FROM sector i by all tourism → source-sector view
- Sum across rows (Σᵢ): total water triggered BY tourism demand j → demand-destination view

Both views sum to the same total TWF. They answer different questions.

### Direct TWF

```
TWF_direct = Σ (activity_volume × coefficient)

Hotel:       room_nights × occupancy_rate × L/room/night  → m³
Restaurant:  tourist_days × meals/day × L/meal           → m³
Rail:        pkm × tourist_share × L/pkm                 → m³
Air:         passengers × tourist_share × L/pax          → m³
```

### Total TWF

```
TWF_total = TWF_indirect + TWF_direct
```

Indirect typically accounts for 85–92% of total; direct 8–15%.

---

## 2. Why two components? The EEIO zero-service problem

EXIOBASE measures **physical water abstraction** — water pumped from aquifers and rivers. Service sectors (hotels, airlines, restaurants) show **zero** in EXIOBASE by design: they do not extract groundwater.

Their water use is entirely:
- **Upstream** — embedded in goods they buy: food, electricity, linens, fuel (captured by indirect TWF via the Leontief multiplier)
- **Operational** — on-site tap water, kitchens, bathrooms (captured by direct TWF via activity coefficients)

This was verified against EXIOBASE 3, Eora26, and WIOD: all report zero or near-zero extraction coefficients for hospitality and transport worldwide. The solution is to use both methods together.

**Why not just use activity data for everything?**  
Activity-based methods only capture what hotels and restaurants use directly. They completely miss the 5,000–800,000 m³/crore of agricultural water embedded upstream in every meal, every linen, every agricultural input. The Lee et al. (2021) structural analysis found food sector TWF is 99% indirect, 1% direct — the upstream signal dominates by orders of magnitude.

---

## 3. Data sources

| Data | Source | Notes |
|---|---|---|
| IO table | MoSPI Supply-Use Tables (SUT) | 2015-16, 2019-20, 2021-22 |
| Water coefficients | EXIOBASE 3 `F.txt` | WaterGAP + WFN; India row (`IN`) |
| Tourism demand base | Tourism Satellite Account 2015-16, MoT India | 24 TSA categories |
| Tourism demand extrapolation | NAS GVA (Statement 6.1, 2011-12 prices) | No TSA beyond 2015-16 |
| Tourist volumes, occupancy | MoT India Annual Report | Used in direct TWF |
| Hotel water use | CHSB India survey (base), Lee et al. 2021 | L/room/night |
| Restaurant water use | Lee et al. (2021) | L/meal |
| Transport water use | IPCC / literature | L/passenger-km |
| EUR→INR exchange rate | RBI / ECB annual averages | For EXIOBASE conversion |
| CPI deflation | MoSPI (base 2015-16) | Real demand comparisons |

---

## 4. Directory structure

```
project-root/
├── 1-input-data/
│   ├── sut/                   MoSPI Supply-Use Tables (xlsx)
│   ├── exiobase-raw/          EXIOBASE 3 F.txt, Z.txt etc.
│   └── nas/2025/              NAS GVA Statement 6.1 tables
│
├── 2-intermediate-calculations/
│   ├── io-table/              A matrix, L matrix, balance checks per year
│   ├── concordance/           EXIOBASE→SUT mappings, W_140 vectors
│   ├── tourism-demand/        Y_163, Y_140 demand vectors
│   ├── tsa-demand/            TSA scaled expenditure by category
│   └── nas-segregation/       NAS growth multipliers per sector
│
├── 3-final-results/
│   ├── indirect-water/        Per-year structural + intensity + sensitivity CSVs
│   ├── direct-water/          Activity-based direct water per year
│   ├── comparison/            Cross-year totals, intensity, benchmarks
│   ├── sda/                   SDA decomposition CSVs + summaries
│   ├── monte-carlo/           MC simulation CSVs + variance decomposition
│   ├── supply-chain/          Path rankings, HEM, per-year Markdown reports
│   └── visualisation/         All charts (PNG)
│
├── 5-scripts/
│   ├── main.py                Pipeline orchestrator
│   ├── config.py              All paths, constants, DIRS
│   ├── utils.py               Logger, Timer, CSV helpers, validation
│   ├── reference_data.md      Single source of truth for all empirical data
│   ├── build_io_tables.py     Step 1: SUT → PTA → L
│   ├── build_water_coefficients.py   Step 2: EXIOBASE → W_140
│   ├── build_tourism_demand.py       Step 3: TSA × NAS → Y_140
│   ├── calculate_indirect_twf.py     Step 4: W × L × Y + structural
│   ├── calculate_direct_twf.py       Step 5: activity-based direct water
│   ├── calculate_sda_mc.py           Step 6: SDA + Monte Carlo + supply-chain
│   ├── visualise_results.py          Step 7: all charts
│   └── compare_years.py              Step 8: cross-year report
│
└── logs/                      Timestamped logs for every run
```

---

## 5. Pipeline — 8 steps

```
build_io ─────────────────────────────────────────────────────┐
water_coefficients ───────────────────────────────────────────┤
tourism_demand ───────────────────────────────────────────────┤
                                                              ↓
                                                        indirect_twf
                                                              │
                                                        direct_twf
                                                              │
                                                           sda_mc
                                                              │
                                                          visualise
                                                              │
                                                           compare
```

Steps 1–3 are independent and can run in any order. Steps 4–8 depend on all preceding steps.

---

## 6. Step 1 — Build IO tables

**Script:** `build_io_tables.py`  
**Output:** `2-intermediate-calculations/io-table/{year}/io_L_{tag}.csv`

### SUT → IO via Product Technology Assumption (PTA)

MoSPI publishes **rectangular** Supply-Use Tables, not square IO tables. PTA converts them:

```
1. D = V × diag(1/q)        Market share matrix
                             D[i,j] = share of product i supplied by industry j
                             V = supply matrix, q = total product supply

2. Z = U × D^T              Intermediate demand matrix
                             U = use matrix (products × industries)
                             Z[i,j] = product i used per unit of product j output

3. A = Z × diag(1/x)        Technical coefficients
                             A[i,j] = crore of product i per crore of product j total output

4. L = (I − A)^{-1}         Leontief inverse
                             L[i,j] = total crore of sector i required (directly + indirectly)
                             per crore of final demand for product j
```

### What L[i,j] actually means

`L[Agriculture, Food Mfg] = 1.8` means: to deliver ₹1 crore of food to final demand, the economy requires ₹1.8 crore of agricultural output (₹1 direct + ₹0.8 through all indirect supply chains).

### Validation checks run automatically

- A-matrix column sums < 1 (Hawkins-Simon: economy is productive)
- Spectral radius ρ(A) < 1 (Leontief inverse converges)
- Balance: row sums of Z × x match column sums (IO identity)
- Cross-year A-matrix stability: column-sum drift flagged if > 30%

**Unit note:** 2015-16 SUT is published in ₹ lakh; converted to ₹ crore (`×0.01`). 2019-20 and 2021-22 are already in ₹ crore.

---

## 7. Step 2 — Water coefficients

**Script:** `build_water_coefficients.py`  
**Output:** `2-intermediate-calculations/concordance/water_coefficients_140_{tag}.csv`

### EXIOBASE extraction

EXIOBASE 3 `F.txt` contains water abstraction in m³ per EUR of output for 163 sectors × 49 countries. India row = `IN`.

```
W_exiobase[i]  [m³/EUR]   for EXIOBASE sector i, India
```

### Unit conversion: EUR → ₹ crore

```
W_inr[i]  = W_exiobase[i] × EUR_INR_rate × 1e7
                             ↑              ↑
                        EUR→INR rate    1 crore = 1e7 units
                        (annual avg)
```

Example: If `W_exiobase[paddy rice] = 3.5 m³/EUR` and EUR/INR = 85:
```
W_inr[paddy] = 3.5 × 85 × 1e7 = 2,975,000,000 m³/crore
```
Paddy rice in India requires ~3 billion m³ of water per ₹ crore of output — this enormous number drives the entire result.

### Concordance: EXIOBASE 163 → SUT 140

A handcrafted mapping file assigns each EXIOBASE sector to one or more SUT product IDs. Many-to-many relationships are permitted; demand is split equally across mapped SUT products.

Products with no EXIOBASE match receive `W = 0` (zero direct water coefficient). They still receive water indirectly via L — the Leontief multiplier propagates agricultural water backward through all supply chains.

Concordance self-check enforced at load time:
- Each EXIOBASE sector appears in exactly one category (no double-counting)
- Demand conservation: Y_140.sum() within 2% of Y_163.sum()

---

## 8. Step 3 — Tourism demand

**Script:** `build_tourism_demand.py`  
**Output:** `2-intermediate-calculations/tourism-demand/Y_tourism_{year}.csv` (163-sector demand)

### TSA base (2015-16)

The Tourism Satellite Account 2015-16 (Ministry of Tourism) provides expenditure in ₹ crore for 24 categories across 163 EXIOBASE sectors, split into inbound and domestic:

```
TSA 2015-16 total ≈ ₹8,10,000 crore (domestic + inbound combined)
```

24 categories include:
- **Characteristic** (11): Accommodation, Food services, Rail, Road, Air, Water transport,
  Equipment rental, Travel agencies, Cultural, Sports, Health
- **Connected** (8): Garments, Processed food, Alcohol, Consumer goods, Footwear, Cosmetics, Gems, Books
- **Imputed** (5): Vacation homes, Social transfers, FISIM, Guest houses, Imputed food

### Extrapolation to 2019 and 2022

No TSA exists beyond 2015-16. Each TSA category is scaled using NAS GVA growth rates at constant 2011-12 prices:

```
Y_category[year] = Y_category[2015] × (GVA_sector[year] / GVA_sector[2015-16])

Example for Hotels in 2019:
  GVA_Hotels_2019-20 = ₹2,85,000 crore (NAS Statement 6.1)
  GVA_Hotels_2015-16 = ₹2,07,000 crore
  Growth rate = 2,85,000 / 2,07,000 = 1.377
  Y_Hotels[2019] = Y_Hotels[2015] × 1.377
```

Growth rates are bounded to [0.1, 3.0] — values outside this range trigger a config validation error, which would indicate a data entry error in `reference_data.md`.

---

## 9. Step 4 — Indirect TWF

**Script:** `calculate_indirect_twf.py`  
**Outputs:** 5 CSVs per year in `3-final-results/indirect-water/`

### Main computation

```python
W_140  = load_sut_water(year)          # (140,) m³/crore
L      = load_leontief(year)           # (140,140)
Y_163  = load_y_tourism(year)          # (163,) crore — 163 EXIOBASE sectors
Y_140  = map_y_to_sut(Y_163, conc)    # (140,) crore — mapped to SUT
WL     = W_140 @ L                    # (140,) m³/crore multiplier
TWF    = WL * Y_140                   # (140,) m³ per product
```

`WL[j]` = total water (direct + all indirect supply chains) required per ₹ crore of tourism demand for product j. This is the full Leontief water multiplier.

### Structural decomposition

```python
pull[i,j] = W[i] * L[i,j] * Y[j]     # (140,140) matrix

Source sector view: pull.sum(axis=1)   # total water EXTRACTED from sector i
Destination view:   pull.sum(axis=0)   # total water TRIGGERED by demand j
```

Saved as `indirect_twf_{year}_structural.csv` with columns:
`Tourism_Category, Total_Water_m3, From_Agriculture_m3, From_Agriculture_pct, From_Mining_m3, From_Electricity_m3, From_Petroleum_m3, From_Manufacturing_m3, From_Services_m3`

### Sensitivity: ±20% agriculture

Agriculture typically contributes 60–80% of indirect TWF. A ±20% range on agricultural water coefficients produces LOW/BASE/HIGH scenarios:

```
W_agr_low  = W_agr × 0.80
W_agr_high = W_agr × 1.20
```

Literature suggests ±30–50% uncertainty is more realistic for WaterGAP estimates (Step 6 Monte Carlo uses proper distributions).

### Why Agriculture shows 0% in the demand-destination view

See [Section 15](#15-demand-destination-vs-source-sector-views) for the full explanation. Short answer: tourists buy Food Manufacturing products, not raw paddy — agricultural water is embedded inside food categories through L.

---

## 10. Step 5 — Direct TWF

**Script:** `calculate_direct_twf.py`  
**Output:** `3-final-results/direct-water/direct_twf_{year}.csv`

### Calculation

```
Hotel:       classified_rooms × occupancy_rate × 365 × L/room/night ÷ 1000
Restaurant:  (dom_tourists_M×1e6 × avg_stay_dom + inb_tourists_M×1e6 × avg_stay_inb)
             × meals_per_tourist_day × L/meal ÷ 1000
Rail:        rail_pkm_B × 1e9 × tourist_rail_share × L/pkm ÷ 1000
Air:         air_pax_M × 1e6 × tourist_air_share × L/pax ÷ 1000
```

All coefficients have LOW/BASE/HIGH scenarios. All empirical values live in `reference_data.md` (single source of truth).

### Coefficient sources and values (BASE)

| Activity | Coefficient | Source |
|---|---|---|
| Hotel | ~80–120 L/room/night (year-dependent) | CHSB India survey + Lee 2021 |
| Restaurant | ~15–20 L/meal | Lee et al. (2021) |
| Rail | 3.5 L/passenger-km | IPCC / GHG Protocol |
| Air | 18 L/passenger-km | Lee et al. (2021) |
| Water transport | 20 L/passenger-km | Literature estimate |

---

## 11. Step 6 — SDA + Monte Carlo + Supply-Chain

**Script:** `calculate_sda_mc.py`  
**Outputs:** `3-final-results/sda/`, `monte-carlo/`, `supply-chain/`

Three distinct analyses that all need the same W, L, Y inputs — combined for efficiency.

---

### 11a. Structural Decomposition Analysis (SDA)

**Question:** Why did indirect TWF change between years — efficiency, supply-chain restructuring, or demand growth?

**Method: Two-polar decomposition**

For year-pair (0→1), ΔTWF = W_effect + L_effect + Y_effect with no residual:

```
W_effect = 0.5 × [(ΔW @ L₀ @ Y₀) + (ΔW @ L₁ @ Y₁)]   # technology change
L_effect = 0.5 × [(W₀ @ ΔL @ Y₀) + (W₁ @ ΔL @ Y₁)]   # structure change
Y_effect = 0.5 × [(W₀ @ L₀ @ ΔY) + (W₁ @ L₁ @ ΔY)]   # demand change

where ΔW = W₁ − W₀,  ΔL = L₁ − L₀,  ΔY = Y₁ − Y₀
```

The two-polar form (averaging start-year and end-year weights) eliminates the residual that plagues single-polar decompositions.

**Example interpretation:**
```
2015→2019:  W_effect = −0.02 bn m³  (−8% of |ΔTWF|)  — modest efficiency gain
            L_effect = +0.05 bn m³  (+20%)             — supply chains became more water-intensive
            Y_effect = +0.22 bn m³  (+88%)             — demand growth dominated

Policy implication: TWF grew primarily because tourists increased, not because of worsening technology.
```

**Outputs:**
- `sda/sda_decomposition_{y0}_{y1}.csv` — full decomposition per period
- `sda/sda_summary_all_periods.csv` — consolidated
- `sda/sda_{y0}_{y1}_summary.txt` — human-readable

---

### 11b. Monte Carlo Sensitivity

**Question:** What is the true uncertainty range around our point estimates?

The ±20% agriculture scenario (Step 4) treats uncertainty as a uniform box — too simple for publication. Monte Carlo samples from proper probability distributions simultaneously across all uncertain inputs.

**Distributions assigned** (10,000 draws, seed=42):

| Parameter | Distribution | Parameters | Rationale |
|---|---|---|---|
| Agricultural water coefficients | Log-normal | μ=0, σ=0.30 on log scale | WaterGAP documented ±30–40% (1σ) |
| Hotel coefficients | Log-normal | μ=0, σ=0.25 | CHSB small sample, right-skewed |
| Restaurant coefficients | Normal | mean=1, sd=0.15 | Lee et al. (2021) range |
| Domestic tourist volumes | Normal | mean=1, sd=0.08 | MoT ±8% uncertainty |
| Inbound tourist volumes | Normal | mean=1, sd=0.05 | MoT ±5% |
| Rail/Air coefficients | Normal | mean=1, sd=0.20 | Literature range |

**What the outputs tell you:**

```
Year 2019:   BASE = 0.2850 bn m³
             5th pct  = 0.1920 bn m³   (−33%)
             Median   = 0.2840 bn m³   (≈BASE, confirms lognormal centring)
             95th pct = 0.4210 bn m³   (+48%)
             → Report as: 0.285 bn m³ [0.192–0.421, 90% CI]
```

**Variance decomposition** (Spearman rank correlation between each input and output):

Agricultural water coefficients typically account for 70–80% of total output variance — meaning better agricultural water measurement would most reduce uncertainty. Hotel coefficients are a distant second (~5–8%).

**Outputs:**
- `monte_carlo/mc_results_{year}.csv` — all 10,000 simulation rows
- `monte_carlo/mc_summary_all_years.csv` — percentiles + top uncertainty source
- `monte_carlo/mc_variance_decomposition.csv` — Spearman rank correlations and variance shares

---

### 11c. Supply-Chain Path Analysis + HEM

**Question:** Which specific source→destination pathways carry the most water?

**Path analysis:**

```python
pull[i,j] = W[i] * L[i,j] * Y[j]    # (140×140) matrix

Top path example:
  i = paddy rice,   j = Food Manufacturing category
  pull[paddy, food] = 5000 × 1.8 × 150 = 1,350,000 m³
  → "Paddy Rice → Processed Fruit/Veg accounts for 23.7% of indirect TWF"
```

All 140×140 = 19,600 cells are ranked; top 50 saved per year.

**Hypothetical Extraction Method (HEM):**

```
x_tourism[i] = Σⱼ L[i,j] × Y[j]        # sector i's tourism-driven output requirement

Dependency_index[i] = x_tourism[i] / Σₖ x_tourism[k]  × 100%
```

High dependency = sector is heavily reliant on tourism-driven demand. A large COVID shock to Y would most damage high-dependency sectors.

**Supply-chain Markdown reports:**

Per-year `.md` files written directly to `supply_chain/` with interpretation notes — ready to embed in policy briefs.

---

## 12. Step 7 — Visualise

**Script:** `visualise_results.py`  
**Output:** `3-final-results/visualisation/` (PNG files)

| Chart | File | What it shows |
|---|---|---|
| SDA waterfall | `waterfall_sda_{y0}_{y1}.png` | W/L/Y effects as floating bars |
| MC violin | `violin_monte_carlo.png` | Full TWF distribution per year with BASE dot |
| Water origin stacked bar | `stacked_bar_water_origin.png` | Source-sector shares (Agriculture dominates) |
| Top-10 horizontal bar | `horizontal_bar_top10_{year}.png` | Categories by water volume + intensity diamonds |
| Slope graph | `slope_per_tourist.png` | L/tourist/day domestic vs inbound 2015–2022 |
| Supply-chain path bar | `sc_paths_ranked_{year}.png` | Top-20 source→destination pairs |
| MC variance pie | `mc_variance_pie.png` | Which inputs drive output uncertainty |
| Total TWF trend | `total_twf_trend.png` | Trend line + MC 5th–95th CI band |
| Sector type stacked | `sector_type_stacked.png` | Demand-destination view across years |

Charts are independent — one failure does not abort the rest.

---

## 13. Step 8 — Cross-year comparison

**Script:** `compare_years.py`  
**Output:** `3-final-results/comparison/run_report_{timestamp}.md`

Reads all output CSVs and fills a template (`report_template.md`) with computed values. Sections:

1. Macro context (GDP, tourist arrivals, exchange rates)
2. Water coefficients — top-10 per year
3. Tourism demand — TSA categories and totals
4. Indirect TWF — by category, source sector, intensity
5. Direct TWF — by activity, by scenario
6. Total TWF — combined, per-tourist intensity
7. Cross-year comparison tables
8. Sensitivity scenarios (LOW/BASE/HIGH)
9. IO table properties (A matrix, spectral radius)
10. **SDA decomposition** — W/L/Y effect table across periods
11. **Monte Carlo** — uncertainty percentiles + variance decomposition table
12. **Supply-chain paths** — top-10 paths per year + HEM dependency table
13. Key findings (auto-generated from data)
14. Data quality warnings (from log files)
15. Method notes

---

## 14. Concordance design: EXIOBASE 163 → SUT 140

EXIOBASE uses 163 global product categories; MoSPI SUT uses 140 Indian products. The concordance bridges them.

**Structure of concordance CSV:**

| Column | Content |
|---|---|
| `Category_ID` | 1–75 (TSA-aligned groupings) |
| `Category_Name` | Human-readable (e.g., "Paddy Rice", "Hotels & Restaurants") |
| `Category_Type` | Agriculture / Manufacturing / Services / etc. |
| `EXIOBASE_Sectors` | Comma-separated EXIOBASE codes (e.g., `IN.1, IN.2`) |
| `SUT_Product_IDs` | Comma-separated MoSPI product IDs (e.g., `1, 2, 3`) |

**Mapping logic in `map_y_to_sut()`:**

```python
for category in concordance:
    demand = Σ Y_163[exio_sectors]           # sum demand for all matched EXIOBASE sectors
    per_product = demand / len(sut_ids)      # split equally across mapped SUT products
    Y_140[sut_ids] += per_product            # accumulate
```

Conservation check: Y_140.sum() must be within 2% of Y_163.sum(). If not, the mapping has gaps that need investigation.

**Why 75 concordance categories but 140 SUT products?**

Multiple SUT products can share a concordance category. For example, "Cereal grains" might cover SUT products 1 (paddy), 2 (wheat), 3 (maize) — all lumped under one EXIOBASE sector. The concordance split distributes demand equally within a category.

---

## 15. Demand-destination vs source-sector views

This is the most important conceptual point in the model.

**The Agriculture = 0% paradox explained:**

```
Water coefficients (W):
  Paddy rice:   842,712 m³/crore  ← enormous
  Wheat:        233,305 m³/crore  ← large
  Hotels & Rest:      0 m³/crore  ← zero (EXIOBASE by design)

Tourism demand (Y):
  Paddy rice:         0 crore  ← tourists don't buy raw paddy
  Hotels & Rest:  7,500 crore  ← tourists buy hotel stays
  Processed F&V: 13,000 crore  ← tourists buy processed food

TWF[j] = WL[j] × Y[j]:
  Paddy rice:   WL[paddy] × 0         = 0 m³
  Processed F&V: WL[food] × 13,000 crore ← large (because WL[food] includes
                                             agricultural water embedded in L)
```

**The pull matrix resolves it:**

```
pull[paddy, food] = W[paddy] × L[paddy,food] × Y[food]
                  = 842,712 × 1.8 × 13,000
                  = ~19.7 billion m³  ← agricultural water, but attributed to food

Source-sector view (sum rows of pull):
  Agriculture:  65–75% of indirect TWF  (this is the physically correct answer)
  Services:     20–25%
  Manufacturing: 5–10%
  ...

Demand-destination view (sum columns of pull, grouped by Y category):
  Agriculture:   0%  (no direct tourism demand for raw crops)
  Food Mfg:     35%  (but all of food's water is actually from agriculture)
  Services:     48%  (hotels, transport)
  ...
```

**Which view to report:**
- **Source-sector view** → "Where should water policy intervene?" → Agricultural irrigation efficiency
- **Demand-destination view** → "Which tourism products are most water-intensive?" → Food-heavy tourism vs cultural tourism

Both views are reported. The report template explicitly notes the Agriculture = 0 in the demand-destination table and directs readers to the source-sector table for the physical extraction story.

---

## 16. Expected results and benchmarks

### India estimates (indicative ranges — actual values depend on data year)

| Metric | Approximate range |
|---|---|
| Total indirect TWF | 0.15 – 0.35 bn m³/year |
| Direct TWF | 0.01 – 0.04 bn m³/year |
| Total TWF | 0.18 – 0.40 bn m³/year |
| TWF as % of national water use (~761 bn m³) | 0.02 – 0.05% |
| Per domestic tourist per day | 800 – 2,000 L |
| Per inbound tourist per day | 4,000 – 8,000 L |
| Indirect/direct ratio | 8:1 to 12:1 |
| Agriculture share of indirect (source-sector) | 60 – 78% |

### Benchmark comparison — Lee et al. China 2017

| Metric | China 2017 | India (expected) |
|---|---|---|
| Total TWF | 19.51 bn m³ | 0.18–0.40 bn m³ |
| Per domestic tourist/day | 1,169 L | 800–2,000 L |
| Per inbound tourist/day | 6,932 L | 4,000–8,000 L |
| Agriculture share indirect | ~74% | 60–78% |
| Indirect/direct ratio | ~10:1 | 8–12:1 |

India's lower absolute total reflects smaller tourism volumes (~1.8 bn domestic vs China's ~5 bn). Per-tourist intensity is similar in order of magnitude — a good sign for the model.

If per-tourist intensity falls outside the globally observed range of 200–6,000 L/tourist/day for EEIO approaches, it indicates a data or modelling issue.

---

## 17. Sensitivity and uncertainty

### Three layers of uncertainty analysis

| Layer | Method | Where |
|---|---|---|
| Scenario | LOW/BASE/HIGH on direct coefficients and ±20% agr indirect | Steps 4–5 |
| Monte Carlo | 10,000 draws, log-normal/normal distributions | Step 6 |
| SDA | Attributing change to W / L / Y components | Step 6 |

### What dominates uncertainty

MC variance decomposition consistently shows agricultural water coefficients account for **~70–80% of total output variance**. This means:

1. The single most impactful improvement to this model would be better Indian agricultural water data (field surveys rather than WaterGAP estimates)
2. Reducing hotel/restaurant coefficient uncertainty has minimal effect on total TWF estimate range
3. Tourist volume uncertainty (±5–8%) is a small contributor relative to coefficient uncertainty

### Reporting convention

From the MC results, report:
```
"Total TWF 2019: 0.285 bn m³ [90% CI: 0.192–0.421 bn m³]"
```
The wide range honestly reflects WaterGAP data limitations, not model problems.

---

## 18. Running the pipeline

### Prerequisites

```bash
pip install pandas numpy matplotlib
```

### Full pipeline

```bash
python main.py --all
```

### Individual steps

```bash
python main.py --step build_io
python main.py --step water_coefficients
python main.py --step tourism_demand
python main.py --step indirect_twf
python main.py --step direct_twf
python main.py --step sda_mc
python main.py --step visualise
python main.py --step compare
```

### Multiple steps

```bash
python main.py --step build_io water_coefficients tourism_demand
```

### Interactive menu

```bash
python main.py
```

### Log files

Every step writes a timestamped log to `5-scripts/logs/`:
```
logs/build_io_tables_1706123456.log
logs/build_water_coefficients_1706123789.log
logs/build_tourism_demand_1706124012.log
logs/indirect_twf_1706124567.log
logs/calculate_sda_mc_1706124890.log
logs/visualise_results_1706125001.log
logs/pipeline_run_1706125200.log
```

Logs capture all coefficient values, matrix properties, balance check results, and warnings. Use them for audit trails and debugging.

### Adding a new study year

1. Add the year's SUT to `1-input-data/sut/`
2. Add the year to `STUDY_YEARS` and `YEARS` in `config.py`
3. Add GVA data column to `reference_data.md` § NAS_GVA_CONSTANT
4. Re-run `--all`

No other code changes required — all scripts iterate over `STUDY_YEARS`.

---

## Design principles

- **Single source of truth:** All empirical numbers in `reference_data.md`. Never hardcode a coefficient in a script.
- **No business logic in main.py:** Pure orchestration only. Every analysis lives in its dedicated module.
- **Template-driven reporting:** All report values come from CSVs via `{{PLACEHOLDER}}` substitution. Nothing hardcoded in the report.
- **Conservation checks everywhere:** Y mapping, IO balance, and matrix properties are validated at every step with explicit pass/fail logging.
- **Independent chart failures:** One broken chart in `visualise_results.py` does not block the rest.
- **STUDY_YEARS-driven:** Add a year in one place (`config.py`); all 8 scripts pick it up automatically.

---

*Last updated: 2026-02-21 | Pipeline version: 3.0 (8-step pipeline with SDA + MC + supply-chain)*