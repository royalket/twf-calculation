# Tourism Water Footprint (TWF) Calculation for India - 2022

## Overview
This project calculates India's Tourism Water Footprint using Environmentally Extended Input-Output (EEIO) analysis, replicating the methodology from "Water footprint of Chinese tourists" (Journal of Hydrology 603, 2021).

**Total Tourism Revenue 2022:** ₹15.32 lakh crore
- Inbound: ₹1.40 lakh crore (6.44 million tourists)
- Domestic: ₹13.92 lakh crore (1,731 million tourists)

---

## Directory Structure

### 📂 `1-input-data/` - Original Source Data

#### **1.1 Supply-Use Tables (SUT) 2019-20**
**Files:**
- `supply-table-2019-20.csv` (140 products × 66 industries)
- `use-table-2019-20.csv` (140 products × 66 industries)

**Source:** Ministry of Statistics, Government of India

**Purpose:** 
- Shows economic structure of India
- Supply table (V): How much each industry produces of each product
- Use table (U): How much each industry consumes of each product

**Example:**
```
Supply Table (V):
Industry "Hotels" produces:
  - Hotel services: ₹5,80,946 crore
  - Restaurant services: ₹27,930 crore

Use Table (U):
Industry "Hotels" consumes:
  - Food products: ₹8,690 crore
  - Electricity: ₹3,610 crore
  - Water: ₹276 crore
```

**Why needed:** To create Input-Output table showing inter-industry dependencies

---

#### **1.2 Tourism Satellite Account (TSA) 2015-16**
**Files:**
- `tsa-2015-16-total-consumption.csv`
- `tsa-2015-16-inbound.csv`
- `tsa-2015-16-domestic.csv`

**Source:** Ministry of Tourism, Government of India

**Purpose:** 
Shows tourism spending breakdown by category (24 products)

**Example Structure:**
| Product | Amount (₹ crore) | % of Total |
|---------|------------------|------------|
| Accommodation | 47,843 | 5.01% |
| Food & beverages | 1,65,860 | 17.38% |
| Road transport | 2,04,467 | 21.43% |
| Air transport | 74,127 | 7.77% |
| Shopping | 75,385 | 7.90% |
| **TOTAL** | **9,54,379** | **100%** |

**Why needed:** 
We have 2022 total (₹15.32 lakh crore) but NOT the breakdown.
Use 2015-16 percentages applied to 2022 total to estimate sectoral spending.

**Calculation:**
```
Accommodation 2022 = 5.01% × ₹15,32,000 crore = ₹76,753 crore
Food 2022 = 17.38% × ₹15,32,000 crore = ₹2,66,262 crore
```

---

#### **1.3 EXIOBASE Water Coefficients**
**Files:**
- `exiobase-india-2022.csv` (163 sectors)
- `exiobase-india-2015.csv` (163 sectors)
- `exiobase-aggregated.csv` (grouped sectors)

**Source:** EXIOBASE 3.10, Zenodo (Stadler et al., 2024)

**Purpose:** 
Provides water use per unit of economic output for 163 sectors

**Example Values (2022):**
| Sector | Water (m³/₹ crore) |
|--------|-------------------|
| Paddy rice (IN) | 20,458 |
| Wheat (IN.1) | 13,217 |
| Vegetables & fruits (IN.3) | 6,024 |
| Dairy products (IN.39) | 7,281 |
| Hotels (IN.113) | 0 (service) |
| Air transport (IN.119) | 0 (service) |

**Why needed:** 
Core data for water intensity. Services show "0" for DIRECT water but have INDIRECT water through supply chains.

**Units:** m³ per ₹1 crore of output
- Exchange rate used: ₹82.5/EUR (2022 average)

---

#### **1.4 Tourism Statistics 2022**
**Files:**
- `tourism-revenue-2022.csv`
- `tourist-arrivals-2022.csv`

**Source:** India Tourism Statistics 2022, Ministry of Tourism

**Data:**
```
Inbound Tourism:
- FEE: USD 17.611 billion = ₹1,39,935 crore
- Tourists: 6.44 million

Domestic Tourism:
- Revenue: ₹13.92 lakh crore (estimated)
- Tourists: 1,731 million
```

**Why needed:** 
Final demand for tourism sector

---

#### **1.5 National Accounts Statistics (NAS)**
**Files:**
- `gva-by-sector-2022.csv`
- `growth-rates-2019-2022.csv`

**Source:** Ministry of Statistics, NAS 2022

**Purpose:** 
Update IO table from 2019-20 to 2022 using sectoral growth rates

**Example:**
```
Agriculture GVA:
- 2019-20: ₹18.85 lakh crore
- 2021-22: ₹23.48 lakh crore
- Growth factor: 1.246

Use to scale IO coefficients to 2022
```

**Why needed (optional step):** 
Makes IO table more accurate for 2022, but 2019-20 table is acceptable for analysis

---

### 📂 `2-intermediate-calculations/` - Processed Data

#### **2.1 Input-Output Table**
**Files:**
- `io-product-2019-20.csv` (66×66 matrix)
- `technical-coefficients-A.csv` (66×66 matrix)
- `leontief-inverse.csv` (66×66 matrix)

**Calculation Method:**

**Step 1: Convert SUT to IO (Product Technology Assumption)**
```
From Supply (V) and Use (U) tables:

1. Market share matrix:
   D = V × (q̂)^-1
   where q = total product output

2. Product-by-product IO:
   Z = U × D
   (Shows how products buy from products)

3. Technical coefficients:
   A_ij = Z_ij / X_j
   (How much product i needed per ₹ of product j)

4. Leontief inverse:
   L = (I - A)^-1
   (Captures ALL supply chain impacts)
```

**Example A matrix entry:**
```
A[Rice, Hotels] = 0.015
Meaning: Hotels need ₹0.015 of rice for every ₹1 of hotel output
```

**Example Leontief inverse:**
```
L[Rice, Hotels] = 0.042
Meaning: ₹1 of hotel demand triggers ₹0.042 of rice output
(includes direct + all indirect supply chain)
```

**Why needed:** 
The L matrix is the MAGIC that captures indirect water use!

---

#### **2.2 Concordance Table**
**File:** `exiobase-to-sut-mapping.csv`

**Purpose:** 
Map 163 EXIOBASE sectors → 66 India SUT sectors

**Example Mappings:**
| EXIOBASE Sectors | India SUT Sector | Method |
|------------------|------------------|--------|
| IN (Paddy rice) + IN.1 (Wheat) + IN.2 (Cereals) | 01: Paddy | Aggregate |
| IN.3 (Veg & fruits) | 18: Fruits + 19: Vegetables | Split equally |
| IN.113 (Hotels & restaurants) | 53: Hotels & Restaurants | Direct match |
| IN.119 (Air transport) | 48: Air Transport | Direct match |

**Calculation:**
```python
# Aggregate multiple EXIOBASE → 1 SUT
Water_SUT[01] = Water_EXIO[IN] + Water_EXIO[IN.1] + Water_EXIO[IN.2]

# Split 1 EXIOBASE → multiple SUT
Water_SUT[18] = 0.5 × Water_EXIO[IN.3]
Water_SUT[19] = 0.5 × Water_EXIO[IN.3]
```

**Why needed:** 
EXIOBASE (163 sectors) doesn't match India SUT (66 sectors). 
Need concordance to use EXIOBASE water data with India IO table.

---

#### **2.3 Scaled TSA**
**Files:**
- `tsa-2022-structure.csv` (24 products)
- `tourism-demand-vector.csv` (66 sectors)

**Calculation:**
```
Step 1: Scale TSA 2015-16 percentages to 2022 total

Product_2022 = (Product_2015-16 / Total_2015-16) × Total_2022

Example:
Hotels_2022 = (47,843 / 9,54,379) × 15,32,000
            = 0.0501 × 15,32,000
            = ₹76,753 crore

Step 2: Map 24 TSA products → 66 SUT sectors

TSA Product "Accommodation" → SUT Sector 53 "Hotels"
TSA Product "Food services" → SUT Sector 53 "Hotels & Restaurants"
TSA Product "Railway" → SUT Sector 45 "Railway Transport"
```

**Result: Tourism Final Demand Vector (Y)**
```
66×1 vector where only tourism-related sectors have values:

Y[45] = Railway spending
Y[46] = Road transport spending
Y[48] = Air transport spending
Y[53] = Hotels & restaurants spending
...others = 0
```

**Why needed:** 
This is the "Y" in the formula: TWF = Water × L × Y

---

### 📂 `3-final-results/` - TWF Calculations

#### **3.1 Direct Water Footprint**
**File:** `direct-water-footprint.csv`

**Formula:**
```
Direct_TWF = Water_Coefficients × Tourism_Demand

For each sector i:
Direct_TWF_i = Water_i × Y_i
```

**Example Calculation:**
```
Hotels & Restaurants (Sector 53):
Tourism spending: ₹2,66,262 crore
Water coefficient: 0 m³/crore (service sector)
Direct water: 0 m³

BUT food suppliers:
Agriculture spending: ₹0 (not direct)
Will appear in INDIRECT calculation!
```

**Expected Result:**
Most direct water = 0 (services don't use water directly)

---

#### **3.2 Total Water Footprint**
**File:** `total-water-footprint.csv`

**Formula:**
```
Total_TWF = Water_Coefficients × L × Tourism_Demand

In matrix notation:
TWF = W × L × Y

where:
W = 1×66 water coefficient vector
L = 66×66 Leontief inverse
Y = 66×1 tourism demand vector
```

**Example Step-by-Step:**
```
Tourist spends ₹10,000 on hotels

Step 1: L × Y calculates ALL output triggered:
- Hotels: ₹10,000 (direct)
- Rice: ₹150 (indirect - hotel buys food)
- Electricity: ₹360 (indirect - hotel uses power)
- Dairy: ₹80 (indirect - for food)
- Transport: ₹420 (indirect - for supplies)
... 61 more sectors

Step 2: W × (L × Y) multiplies by water coefficients:
- Hotels water: 0 × ₹10,000 = 0
- Rice water: 20,458 × ₹150/10,000,000 = 30.7 m³
- Electricity water: 147 × ₹360/10,000,000 = 0.5 m³
- Dairy water: 7,281 × ₹80/10,000,000 = 5.8 m³

Total for ₹10,000 spending ≈ 37 m³
```

**This is the MAGIC of IO analysis!**

---

#### **3.3 Sectoral Attribution**
**File:** `sectoral-attribution.csv`

Shows which sectors contribute most to TWF

**Expected Results (based on China study):**
| Sector | Contribution % |
|--------|---------------|
| Agriculture (cereals, vegetables) | 60-70% |
| Food manufacturing | 10-15% |
| Electricity | 5-10% |
| Dairy | 3-5% |
| Others | 10-15% |

---

#### **3.4 Per Tourist Metrics**
**File:** `per-tourist-metrics.csv`

**Calculations:**
```
Average per tourist per day:

Inbound tourist:
- Avg spending: ₹1,39,935 cr / 6.44 million = ₹21,733/tourist
- Avg stay: 21 days (estimate)
- Daily spending: ₹21,733 / 21 = ₹1,035/day
- Daily water: (₹1,035 / ₹10,000) × 37 m³ = 3.8 m³ = 3,800 L

Domestic tourist:
- Avg spending: ₹13,92,000 cr / 1,731 million = ₹8,042/tourist
- Avg stay: 3 days (estimate)
- Daily spending: ₹8,042 / 3 = ₹2,681/day
- Daily water: (₹2,681 / ₹10,000) × 37 m³ = 9.9 m³ = 9,900 L
```

**Compare with China study:**
- China inbound: 6,932 L/day
- China domestic: 1,169 L/day

---

### 📂 `5-scripts/` - Calculation Scripts

#### **Execution Order:**
```bash
# Step 1: Convert SUT to IO (5 minutes)
python step1_sut_to_io.py

# Step 2: Update IO to 2022 (optional, 10 minutes)
python step2_update_io_2022.py

# Step 3: Create concordance (2 hours manual work + script)
python step3_create_concordance.py

# Step 4: Scale TSA (2 minutes)
python step4_scale_tsa.py

# Step 5: Calculate TWF (1 minute)
python step5_calculate_twf.py

# Step 6: Generate report (5 minutes)
python step6_generate_report.py
```

---

## Key Concepts Explained

### What is the Leontief Inverse?

**Simple analogy:**
You want to bake 1 cake (final demand).
- Direct: You need flour, eggs, sugar
- Indirect: Flour producer needs wheat (level 2)
- Indirect: Wheat farmer needs fertilizer (level 3)
- Indirect: Fertilizer needs chemicals (level 4)
- ...continues

**The Leontief inverse captures ALL these levels automatically!**

**Mathematical:**
```
X = (I - A)^-1 × Y

where:
I = Identity matrix
A = Technical coefficients (direct requirements)
(I-A)^-1 = Leontief inverse (total requirements including indirect)
Y = Final demand
X = Total output needed
```

---

### Why Services Show Zero Water?

**Direct water:**
- Hotels: 0 (they don't manufacture anything)
- Transport: 0 (moving people, not using water)
- Restaurants: 0 (service only)

**But INDIRECT water is captured:**
- Hotel buys food → Agriculture water
- Restaurant buys ingredients → Food processing water
- Transport uses fuel → Petroleum refining water

**This is why we need IO analysis!**

---

## Data Quality & Limitations

### Assumptions:
1. TSA structure (2015-16) applies to 2022
2. COVID impact assumed normalized by 2022
3. Water coefficients from EXIOBASE (global) represent India
4. IO structure (2019-20) approximates 2022

### Validation Steps:
1. Compare total TWF with China study (proportional to GDP/tourism)
2. Check sector attribution patterns match literature
3. Verify per-tourist numbers are reasonable
4. Test sensitivity to key assumptions

---

## Expected Outcomes

### Total TWF 2022 (rough estimate):
```
Based on ₹15.32 lakh crore spending:
- If 40 m³ per ₹10,000 spending
- Total TWF ≈ 6,128 billion m³

Compare:
- China 2015: 19.51 billion m³ (RMB 4.64 trillion)
- India should be similar magnitude
```

### Key Findings (expected):
1. Indirect water >> Direct water (10-15x larger)
2. Agriculture dominates indirect water (70%)
3. Inbound tourists have higher water footprint per day
4. Hotels trigger most supply chain water

---

## Citation

**Methodology Reference:**
Sun, Y.-Y., & Drakeman, D. (2021). Water footprint of Chinese tourists. *Journal of Hydrology*, 603, 126850.

**Data Sources:**
- EXIOBASE 3.10: Stadler et al. (2024), Zenodo
- SUT 2019-20: Ministry of Statistics, India
- TSA 2015-16: Ministry of Tourism, India
- Tourism Statistics 2022: Ministry of Tourism, India

---

## Contact & Updates

Last updated: [Current Date]
Author: [Your Name]
Purpose: Academic Research / Policy Analysis