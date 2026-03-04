# COMPLETE GUIDE: TOURISM WATER FOOTPRINT STUDY FOR INDIA 2024-25
## A Step-by-Step Implementation Manual

---

## TABLE OF CONTENTS

1. [Research Overview](#1-research-overview)
2. [Data Collection Strategy](#2-data-collection-strategy)
3. [Detailed Methodology](#3-detailed-methodology)
4. [Implementation Timeline](#4-implementation-timeline)
5. [Technical Implementation](#5-technical-implementation)
6. [Analysis Framework](#6-analysis-framework)
7. [Expected Outputs](#7-expected-outputs)

---

# 1. RESEARCH OVERVIEW

## 1.1 Research Objective

**Primary Goal:** Calculate the Tourism Water Footprint (TWF) of India for 2024-25, including:
- Direct water consumption by tourists
- Indirect water consumption through supply chains
- Sectoral breakdown of TWF
- Comparison of domestic vs. inbound tourism water impact
- India's outbound tourism water impact on other countries

## 1.2 What is Tourism Water Footprint?

**Definition:** The total volume of freshwater consumed (blue water) directly and indirectly to support tourism activities.

**Components:**
1. **Direct TWF**: Water used directly by tourists
   - Hotel accommodation (showers, toilets, laundry)
   - Restaurants (food preparation, cleaning)
   - Transportation (train cleaning, airport facilities)
   - Recreation (swimming pools, water parks)

2. **Indirect TWF**: Water used in supply chains
   - Agriculture (food production for tourists)
   - Electricity generation (for hotels, transport)
   - Manufacturing (tourism equipment, souvenirs)
   - Construction (hotel buildings, infrastructure)

## 1.3 Research Framework

**Methodology:** Environmentally Extended Input-Output (EEIO) Analysis + Tourism Satellite Account (TSA)

**Key Equation:**
```
Total TWF = Direct Water Coefficient (DWC) × Leontief Inverse × Tourism Final Demand
```

Breaking this down:
- **DWC**: Water used per rupee of output in each sector
- **Leontief Inverse**: Captures all direct + indirect linkages between sectors
- **Tourism Final Demand**: Money spent by tourists on different sectors

---

# 2. DATA COLLECTION STRATEGY

## 2.1 CRITICAL FILES TO DOWNLOAD

### A. FROM NAS 2025 (National Accounts Statistics)

**Base URL:** https://www.mospi.gov.in/publication/national-accounts-statistics-2025

#### **MUST DOWNLOAD - Priority 1:**

| File Name | What It Contains | Why You Need It | Download Link Pattern |
|-----------|------------------|-----------------|----------------------|
| **Statement 1.6** | GVA by economic activity (current & constant prices) | Sectoral outputs for 2019-20 to 2024-25 | Look for "Statement 1.6" Excel icon |
| **Statement 1.6B** | Percentage change in GVA by economic activity | Growth rates for updating IO table | Look for "Statement 1.6B" Excel icon |
| **Statement 7.1** | Output, value added, CE, OS/MI by industry | Detailed sectoral economic data | Look for "Statement 7.1" Excel icon |

#### **SHOULD DOWNLOAD - Priority 2:**

| File Name | What It Contains | Why You Need It |
|-----------|------------------|-----------------|
| **Statement 1.5** | Output by economic activity | Total output values by sector |
| **Statement 8.9** | Trade, repair, hotels & restaurants output | Direct tourism sector data |
| **Statement 8.10** | Transport services output | Transportation TWF |
| **Statement 8.14** | Other services output | Entertainment, culture sectors |
| **Statement 1.12** | Private final consumption expenditure | Tourist consumption patterns |

#### **NICE TO HAVE - Priority 3:**

| File Name | What It Contains | Purpose |
|-----------|------------------|---------|
| **Statement 8.17.2** | Provisional GVA 2024-25 | Latest year validation |
| **Statement 8.18.1** | Quarterly GVA estimates | Seasonality analysis |

### B. FROM SUPPLY USE TABLES

**File:** SUT 2019-20
**Link:** https://mospi.gov.in/sites/default/files/reports_and_publication/statistical_publication/SUT_2019-20_m.xlsx

**What's Inside:**
- **Supply Table**: Which industries produce which products (140 products × 66 industries)
- **Use Table**: Which industries consume which products
- **Margins**: Trade and transport margins
- **Taxes**: Taxes on products

**Why Critical:** This is your base economic structure that you'll update to 2024-25.

### C. FROM TOURISM MINISTRY

| File | Link | What You Get |
|------|------|--------------|
| **TSA 2015-16** | https://tourism.gov.in/sites/default/files/2020-04/011-TSAI.pdf | Tourism expenditure structure by sector |
| **India Tourism Statistics 2024** | https://tourism.gov.in/sites/default/files/2025-02/India%20Tourism%20Data%20Compendium%20key%20highlights%202024.pdf | Number of tourists, revenue data |

### D. FROM WATER RESOURCES

| Source | Link | Data |
|--------|------|------|
| **CGWB 2024** | https://cgwb.gov.in/ | Groundwater use by sector |
| **India WRIS** | https://indiawris.gov.in/wris/#/ | Water availability, consumption data |

---

## 2.2 HOW TO DOWNLOAD FROM NAS 2025

**Step-by-Step Process:**

1. **Go to:** https://www.mospi.gov.in/publication/national-accounts-statistics-2025

2. **Navigate to Chapter 1** (Macro-economic aggregates)

3. **Find Statement 1.6** - Click the Excel icon to download

4. **What the file will contain:**
   ```
   Columns: Financial Years (2011-12, 2012-13, ... 2024-25)
   Rows: Economic Sectors (Agriculture, Manufacturing, etc.)
   Values: GVA in ₹ crores
   ```

5. **Repeat for all Priority 1 files**

---

# 3. DETAILED METHODOLOGY

## 3.1 OVERALL WORKFLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA COLLECTION                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   SUT 2019   │  │   NAS 2025   │  │  Tourism     │      │
│  │   (Base IO)  │  │(Growth Rates)│  │   Data       │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│              STEP 1: CREATE IO TABLE 2024-25                 │
│  • Convert SUT to IO (Product Tech Assumption)               │
│  • Apply growth rates from NAS 2025                          │
│  • Validate with GDP data                                    │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│         STEP 2: CALCULATE WATER COEFFICIENTS                 │
│  • Compile water use data (CGWB)                             │
│  • Match to 66 IO sectors                                    │
│  • Calculate DWC = Water Use / Economic Output               │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│       STEP 3: CREATE TOURISM FINAL DEMAND VECTOR             │
│  • Use TSA 2015-16 structure                                 │
│  • Scale to 2024 tourism revenue                             │
│  • OR conduct primary survey                                 │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│            STEP 4: CALCULATE TWF                             │
│  Direct TWF = DWC × Tourism Demand                           │
│  Total TWF = DWC × (I-A)^-1 × Tourism Demand                 │
│  Indirect TWF = Total TWF - Direct TWF                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              STEP 5: ANALYSIS & INSIGHTS                     │
│  • Sectoral breakdown                                        │
│  • Domestic vs Inbound comparison                            │
│  • Water stress implications                                 │
│  • Policy recommendations                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 3.2 STEP 1: CREATE INPUT-OUTPUT TABLE 2024-25

### Phase A: Understanding SUT 2019-20 Structure

**Download and Open:** SUT_2019-20_m.xlsx

**File Structure:**
```
Sheet 1: Supply Table (Basic Prices)
- Rows: 140 Products
- Columns: 66 Industries + Imports
- Cell values: Production of product i by industry j

Sheet 2: Use Table (Purchasers' Prices)  
- Rows: 140 Products
- Columns: 66 Industries + Final Demand categories
- Cell values: Consumption of product i by industry j

Sheet 3: Margins
- Trade margins
- Transport margins

Sheet 4: Taxes less Subsidies
- Product taxes
- Subsidies
```

### Phase B: Convert SUT to IO Table (2019-20 Base)

**Mathematical Framework:**

**Step B.1: Extract Matrices from SUT**

From the Excel file, extract:
- **V** = Supply matrix (140 products × 66 industries)
- **U** = Use matrix (140 products × 66 industries)
- **q** = Total product output vector (140 × 1)
- **g** = Total industry output vector (66 × 1)

**Step B.2: Create Product-by-Product Table**

Using **Product Technology Assumption (PTA):**

```
Market Share Matrix: D = V × (q̂)^-1
Where q̂ is diagonal matrix of product outputs

Product-by-Product IO: B = U × D
```

**In Excel:**
1. Calculate total product outputs (sum each row of V)
2. Create diagonal matrix q̂ (product outputs on diagonal, zeros elsewhere)
3. Calculate D = V / q (element-wise division)
4. Matrix multiply: B = U × D

**Step B.3: Convert to Industry-by-Industry Table**

```
Industry-by-Industry IO Matrix: Z = D^T × B × (ĝ)^-1 × g
```

**Simplified approach:**
```
Z_ij = Σ(k=1 to 140) [U_ki × V_kj / q_k]
```

This gives you **Z matrix** (66 industries × 66 industries) showing intermediate flows.

### Phase C: Update from 2019-20 to 2024-25

**Step C.1: Extract Growth Rates from NAS 2025**

Open **Statement 1.6B** (Percentage change in GVA)

**You'll see data like:**
```
Industry                           2020-21  2021-22  2022-23  2023-24  2024-25
Agriculture, forestry & fishing      3.3%     3.0%     4.7%     1.4%     4.4%
Mining & quarrying                  -2.4%    11.5%     4.1%     6.9%     4.0%
Manufacturing                       -0.6%     9.9%     1.3%     9.9%     4.6%
...
```

**Step C.2: Calculate Cumulative Growth Factor**

For each sector, calculate:
```
Growth Factor = (1 + g₁) × (1 + g₂) × (1 + g₃) × (1 + g₄) × (1 + g₅)
```

**Example for Agriculture:**
```
GF_Agri = (1 + 0.033) × (1 + 0.030) × (1 + 0.047) × (1 + 0.014) × (1 + 0.044)
GF_Agri = 1.033 × 1.030 × 1.047 × 1.014 × 1.044
GF_Agri = 1.182 (18.2% total growth over 5 years)
```

**Step C.3: Update Industry Outputs**

From **Statement 1.6** or **Statement 7.1**, get GVA for 2019-20:

```
GVA_2024-25 (i) = GVA_2019-20 (i) × Growth_Factor(i)
```

**Step C.4: Update IO Transactions**

**Option 1: Proportional Scaling (Simple)**
```
Z_2024-25 (i,j) = Z_2019-20 (i,j) × √[GF(i) × GF(j)]
```

**Option 2: RAS Method (More Accurate)**

The RAS method adjusts the IO table to match known row and column totals.

**RAS Algorithm:**
1. Start with Z_2019-20
2. Set target row sums = updated industry outputs
3. Set target column sums = updated industry inputs
4. Iterate:
   - Scale rows to match row targets
   - Scale columns to match column targets
   - Repeat until convergence

**Python Implementation:**
```python
def ras_method(Z_base, row_totals_target, col_totals_target, max_iter=100):
    Z = Z_base.copy()
    for iteration in range(max_iter):
        # Row scaling
        row_sums = Z.sum(axis=1)
        r_factors = row_totals_target / row_sums
        Z = Z * r_factors[:, np.newaxis]
        
        # Column scaling
        col_sums = Z.sum(axis=0)
        s_factors = col_totals_target / col_sums
        Z = Z * s_factors
        
        # Check convergence
        if np.allclose(Z.sum(axis=1), row_totals_target) and \
           np.allclose(Z.sum(axis=0), col_totals_target):
            break
    
    return Z
```

**Step C.5: Calculate Technical Coefficients Matrix (A)**

```
A_ij = Z_ij / X_j
```

Where:
- A_ij = Direct requirement coefficient
- Z_ij = Intermediate input from sector i to sector j
- X_j = Total output of sector j

**In Excel:**
```excel
=Intermediate_Input_Cell / Column_Total
```

**Step C.6: Calculate Leontief Inverse (I-A)^-1**

1. Create Identity Matrix I (66×66 with 1s on diagonal)
2. Calculate (I - A)
3. Invert the matrix

**Excel Formula:**
```excel
=MINVERSE(I_minus_A_range)
Enter as array formula: Ctrl+Shift+Enter
```

**Python:**
```python
I = np.eye(66)  # Identity matrix
I_minus_A = I - A.values
L = np.linalg.inv(I_minus_A)  # Leontief inverse
```

---

## 3.3 STEP 2: CALCULATE WATER USE COEFFICIENTS

### Phase A: Compile Water Use Data by Sector

**Sources and Methodology:**

#### **1. Agriculture Sector**

**Data Source:** CGWB Dynamic Groundwater Assessment 2024

**What to Extract:**
- Total agricultural groundwater use: ~208 BCM (2023)
- State-wise breakdown available

**From NAS Statement 8.1.1** (Crop sector output):
- Get total agricultural output 2024-25: ~₹XX lakh crore

**Calculate:**
```
DWC_Agriculture = 208,000 million m³ / Agricultural_Output (₹ crore)
DWC_Agriculture = 208,000 / [Value from NAS Statement 8.1.1]
```

**Example:**
If Agricultural Output = ₹3,000,000 crore
DWC_Agri = 208,000 / 3,000,000 = 0.0693 m³/₹

#### **2. Manufacturing Sectors**

**Challenge:** Limited sectoral water use data

**Solution: Proxy Method**

**Step 1:** Get total industrial water use from CGWB
- Industrial groundwater: ~4 BCM (2023)
- Industrial surface water: Estimate from CWC

**Step 2:** From SUT 2019-20, find water supply sector linkages

**Step 3:** Distribute industrial water proportionally:
```
Water_Use(Manufacturing_i) = Total_Industrial_Water × 
    [Intermediate_Input_from_Water_Sector_to_Industry_i / 
     Total_Intermediate_Water_Supply]
```

**Alternative:** Use international benchmarks
- China's IO water coefficients (from the paper you shared)
- Adjust for India's water productivity

#### **3. Electricity, Gas, Water Supply**

**Data Source:** 
- Central Electricity Authority (CEA) reports
- Statement 8.7 from NAS (sector output)

**Thermal Power Water Use:**
- Typical consumption: 3-4 m³ per MWh
- Get total power generation from CEA
- Calculate total water use

```
DWC_Electricity = (Power_Generation_MWh × 3.5 m³/MWh) / Electricity_Sector_Output
```

#### **4. Construction**

**Estimation Method:**
- Construction typically uses ~0.1-0.2 m³ per ₹1000 of output
- Based on building material production + site use

```
DWC_Construction = 0.00015 m³/₹ (estimated)
```

#### **5. Hotels & Restaurants**

**Direct Measurement Approach:**

**Data from:** 
- PATA (Pacific Asia Travel Association) benchmarks
- Indian hotel industry reports
- TSA 2015-16 (Statement 9: Water consumption)

**Typical Hotel Water Use:**
- 3-star: 300-500 liters/guest/night
- 4-star: 500-800 liters/guest/night
- 5-star: 800-1200 liters/guest/night

**Calculate Average:**
```
Average hotel water = 600 liters/guest/night
Tourist nights from tourism statistics = XX million
Total hotel water = XX million × 600 liters = YY million m³

DWC_Hotels = YY million m³ / Hotel_Sector_Output (from NAS 8.9)
```

#### **6. Transportation Sectors**

**Air Transport:**
- Aircraft water servicing
- Airport facilities
- Minimal compared to output

**Estimate:** 0.00001 m³/₹ (very low)

**Rail Transport:**
- Train washing
- Station facilities
- From Indian Railways water audit reports

**Road Transport:**
- Vehicle washing
- Roadside facilities
- Estimate: 0.00002 m³/₹

#### **7. Other Service Sectors**

**Low Water Intensity:**
- Financial services: 0.00001 m³/₹
- Professional services: 0.00001 m³/₹
- Entertainment: 0.00005 m³/₹

### Phase B: Create Water Extension Matrix

**Final Output: Vector of 66 Water Coefficients**

```
DWC = [DWC₁, DWC₂, DWC₃, ..., DWC₆₆]
```

**Example Structure:**
```
Sector                          DWC (m³/₹)
1. Agriculture                   0.0693
2. Mining                        0.0050
3. Manufacturing - Food          0.0300
4. Manufacturing - Textiles      0.0150
5. Manufacturing - Chemicals     0.0080
...
62. Hotels                       0.0200
63. Restaurants                  0.0180
64. Rail Transport               0.0003
65. Road Transport               0.0002
66. Air Transport                0.0001
```

**Save this as:** `Water_Coefficients_2024-25.xlsx`

---

## 3.4 STEP 3: CREATE TOURISM FINAL DEMAND VECTOR

### Phase A: Understand TSA Structure

**Download:** TSA 2015-16 PDF

**Key Table: Tourism Expenditure by Product/Sector**

**Structure (from TSA):**
```
Tourism Products              Domestic    Inbound    Total
                              (₹ crore)   (₹ crore)  (₹ crore)
1. Accommodation              XX          YY         ZZ
2. Food & beverages           XX          YY         ZZ
3. Railway passenger transport XX         YY         ZZ
4. Road passenger transport   XX          YY         ZZ
5. Air passenger transport    XX          YY         ZZ
6. Water passenger transport  XX          YY         ZZ
7. Transport equipment rental XX          YY         ZZ
8. Travel agency services     XX          YY         ZZ
9. Cultural services          XX          YY         ZZ
10. Recreation & entertainment XX         YY         ZZ
11. Miscellaneous tourism     XX          YY         ZZ
12. Shopping goods            XX          YY         ZZ
TOTAL                         AAAA        BBBB       CCCC
```

### Phase B: Map TSA Sectors to IO Sectors

**Concordance Table (you need to create this):**

| TSA Sector | IO Sector (from SUT 66 industries) | Mapping Notes |
|------------|-------------------------------------|---------------|
| Accommodation | Hotels & restaurants (Sector 55 in NIC) | Direct match |
| Food & beverages | Restaurants, cafes (Sector 56) | Direct match |
| Railway transport | Railway transport (Sector 49.1) | Direct match |
| Road transport | Road transport (Sector 49.2-49.4) | Direct match |
| Air transport | Air transport (Sector 51) | Direct match |
| Cultural services | Creative, arts & entertainment (Sector 90-93) | Aggregated |
| Shopping goods | Wholesale & retail trade (Sector 45-47) | Distributed |

### Phase C: Scale TSA 2015-16 to 2024

**Method 1: Simple Proportional Scaling**

**From Tourism Statistics 2024:**
- Total domestic tourism revenue 2024: ₹15.5 lakh crore
- Total inbound tourism revenue 2024: ₹3.1 lakh crore
- **Total: ₹18.6 lakh crore**

**From TSA 2015-16:**
- Total tourism expenditure 2015-16: ₹XX lakh crore

**Scaling Factor:**
```
SF = 18.6 lakh crore / XX lakh crore = α
```

**Updated Expenditure:**
```
Tourism_Exp_2024 (sector i) = Tourism_Exp_2015-16 (sector i) × α
```

**Method 2: Differential Sector Growth**

More accurate - use sector-specific growth:

```
Tourism_Exp_2024 (i) = Tourism_Exp_2015-16 (i) × 
                       [Sector_Growth_Factor(i)] × 
                       [Tourism_Growth_Factor]
```

Where:
- Sector growth from NAS Statement 1.6B
- Tourism growth from tourist arrival trends

### Phase D: Create Final Demand Vector

**Result: 66×1 Vector**

```
Y_tourism = [y₁, y₂, y₃, ..., y₆₆]ᵀ
```

Where:
- y_i = Tourism expenditure in sector i (₹ crore)
- Most values will be 0 (only ~11 direct tourism sectors)
- Non-zero for: Hotels, Restaurants, Transport, Retail, Entertainment

**Example:**
```
Sector                     Tourism Final Demand (₹ crore)
1. Agriculture             0
2. Mining                  0
3. Food manufacturing      0 (indirect, not final demand)
...
55. Hotels                 XXX,XXX
56. Restaurants            YYY,YYY
49. Rail transport         ZZZ,ZZZ
50. Road transport         AAA,AAA
51. Air transport          BBB,BBB
...
62. Retail trade           CCC,CCC
90. Entertainment          DDD,DDD
All other sectors          0
```

**Save as:** `Tourism_Final_Demand_2024.xlsx`

---

## 3.5 STEP 4: CALCULATE TOURISM WATER FOOTPRINT

### Phase A: Direct TWF Calculation

**Formula:**
```
Direct_TWF_i = DWC_i × Y_tourism_i
```

**For all 11 direct tourism sectors:**

```python
# Python implementation
direct_twf = DWC * Y_tourism

# Example for Hotels sector:
Direct_TWF_Hotels = DWC[55] × Y_tourism[55]
                  = 0.0200 m³/₹ × 200,000 crore
                  = 4,000 million m³
```

**Sum across all sectors:**
```
Total_Direct_TWF = Σ Direct_TWF_i
```

### Phase B: Total TWF Calculation (Direct + Indirect)

**Formula:**
```
Total_TWF = DWC × L × Y_tourism
```

Where:
- DWC = Water coefficient vector (1 × 66)
- L = Leontief inverse matrix (66 × 66)
- Y_tourism = Final demand vector (66 × 1)

**Step-by-step:**

**Step 1:** Matrix multiply L × Y_tourism
```
X_total = L × Y_tourism
```
This gives total output of each sector needed to satisfy tourism demand

**Step 2:** Element-wise multiply with water coefficients
```
TWF_total = DWC ⊙ X_total
```

**In Excel:**
```
1. Calculate L × Y in separate sheet (use MMULT function)
2. Multiply each result by corresponding water coefficient
3. Sum all values
```

**In Python:**
```python
import numpy as np

# Total output required
X_total = L @ Y_tourism  # @ is matrix multiplication

# Water footprint by sector
TWF_by_sector = DWC * X_total

# Total TWF
Total_TWF = np.sum(TWF_by_sector)

# Direct TWF (only direct tourism sectors)
Direct_TWF = np.sum(DWC * Y_tourism)

# Indirect TWF
Indirect_TWF = Total_TWF - Direct_TWF
```

### Phase C: Sectoral Attribution

**Identify which sectors contribute most to indirect TWF:**

```python
# Calculate indirect contribution of each sector
indirect_contribution = DWC * (L @ Y_tourism) - DWC * Y_tourism

# Sort by magnitude
top_sectors = indirect_contribution.sort_values(ascending=False).head(20)
```

**Expected Top Sectors:**
1. Agriculture (food for tourists)
2. Electricity (hotels, transport)
3. Food manufacturing
4. Textiles (hotel linens)
5. Chemicals (cleaning products)
6. Construction (tourism infrastructure)
7. Petroleum products (transport fuel)

---

## 3.6 STEP 5: DOMESTIC VS INBOUND COMPARISON

### Separate Calculations

**Split Tourism Final Demand:**
```
Y_domestic = [Domestic tourist expenditure by sector]
Y_inbound = [Inbound tourist expenditure by sector]
```

**From Tourism Statistics 2024:**
- Domestic: ₹15.5 lakh crore
- Inbound: ₹3.1 lakh crore
- Ratio: ~5:1

**Apply to TSA structure:**
```
Y_domestic (i) = Y_total (i) × (Domestic_share_from_TSA_2015-16)
Y_inbound (i) = Y_total (i) × (Inbound_share_from_TSA_2015-16)
```

**Calculate TWF for Each:**
```
TWF_domestic = DWC × L × Y_domestic
TWF_inbound = DWC × L × Y_inbound
```

**Per Capita/Per Tourist:**
```
TWF_per_domestic_tourist = TWF_domestic / Number_domestic_tourists
TWF_per_inbound_tourist = TWF_inbound / Number_inbound_tourists
```

**Expected Result:** Inbound tourists have higher TWF per capita (similar to China study finding)

---

## 3.7 STEP 6: OUTBOUND TOURISM IMPACT

### Estimation Method

**Challenge:** No data on Indian tourists' water consumption abroad

**Solution:** Use ratio approach (from China paper)

```
Foreign_tourist_TWF = 1.5 × Local_per_capita_WF × Tourist_days
```

**For Each Destination Country:**

**Data Needed:**
- Number of Indian tourists to country X (from tourism statistics)
- Average stay duration (from surveys/reports)
- Local per capita water footprint (from Hoekstra & Mekonnen 2012)

**Calculation:**
```
TWF_India_to_Thailand = 
    (Indian_tourists_to_Thailand) × 
    (Average_stay_days) × 
    (Thailand_per_capita_WF) × 
    1.5

Example:
= 1,500,000 tourists × 
  7 days × 
  3.8 m³/person/day × 
  1.5
= 59,850,000 m³
```

**Net TWF Flow:**
```
Net_TWF = TWF_outbound_India - TWF_inbound_to_India

If positive: India is net water consumer through tourism
If negative: India is net water provider through tourism
```

---

# 4. IMPLEMENTATION TIMELINE

## Month 1-2: Data Collection & Setup

### Week 1-2: Download All Data
- [ ] Download SUT 2019-20
- [ ] Download all NAS 2025 statements (Priority 1 & 2)
- [ ] Download TSA 2015-16
- [ ] Download Tourism Statistics 2024
- [ ] Download CGWB 2024 report
- [ ] Access India WRIS portal

### Week 3-4: Data Organization
- [ ] Create master Excel workbook
- [ ] Set up folder structure
- [ ] Create concordance tables (TSA to IO sectors)
- [ ] Document all data sources
- [ ] Create data dictionary

### Week 5-6: Literature Review
- [ ] Read China TWF paper thoroughly
- [ ] Review other TWF studies (Taiwan, Spain, Australia)
- [ ] Document methodology differences
- [ ] Note key findings for comparison

### Week 7-8: Methodology Finalization
- [ ] Decide on SUT-to-IO conversion method
- [ ] Finalize water coefficient estimation approach
- [ ] Design primary survey (if conducting)
- [ ] Get ethics approval (if needed)

## Month 3-4: IO Table Construction

### Week 9-10: SUT Understanding
- [ ] Fully understand SUT 2019-20 structure
- [ ] Extract all matrices
- [ ] Verify row-column balances
- [ ] Document any data quality issues

### Week 11-12: IO Conversion
- [ ] Convert SUT to IO (2019-20)
- [ ] Calculate technical coefficients
- [ ] Calculate Leontief inverse
- [ ] Validate IO table

### Week 13-14: Update to 2024-25
- [ ] Extract all growth rates from NAS
- [ ] Apply RAS method or proportional scaling
- [ ] Create updated IO table 2024-25
- [ ] Validation against GDP data

### Week 15-16: Quality Checks
- [ ] Row-column balance checks
- [ ] Multiplier reasonableness tests
- [ ] Compare with international IO tables
- [ ] Sensitivity analysis on growth assumptions

## Month 5-6: Water Coefficients & Tourism Data

### Week 17-18: Water Data Compilation
- [ ] Extract agricultural water use
- [ ] Estimate industrial water use
- [ ] Calculate electricity sector water
- [ ] Hotel/restaurant water data
- [ ] All other sectors

### Week 19-20: Water Coefficient Calculation
- [ ] Match water use to 66 sectors
- [ ] Calculate all DWC values
- [ ] Document assumptions
- [ ] Create water extension table

### Week 21-22: Tourism Expenditure
- [ ] Map TSA to IO sectors
- [ ] Scale TSA 2015-16 to 2024
- [ ] OR conduct primary survey
- [ ] Create final demand vector

### Week 23-24: Data Validation
- [ ] Cross-check all data sources
- [ ] Verify calculations
- [ ] Peer review (if possible)
- [ ] Finalize all input data

## Month 7-8: TWF Calculation & Analysis

### Week 25-26: Core Calculations
- [ ] Calculate Direct TWF
- [ ] Calculate Total TWF
- [ ] Calculate Indirect TWF
- [ ] Sectoral breakdowns

### Week 27-28: Comparative Analysis
- [ ] Domestic vs Inbound TWF
- [ ] Per tourist calculations
- [ ] Sectoral attribution analysis
- [ ] Identify high-impact sectors

### Week 29-30: Extended Analysis
- [ ] Outbound tourism impact
- [ ] Water stress overlay
- [ ] Regional breakdowns (if data available)
- [ ] Temporal trends

### Week 31-32: Sensitivity & Validation
- [ ] Sensitivity analysis on key parameters
- [ ] Comparison with bottom-up estimates
- [ ] Validation against literature
- [ ] Document limitations

## Month 9-10: Writing & Visualization

### Week 33-36: Results Writing
- [ ] Write methodology section
- [ ] Present results with tables
- [ ] Create visualizations
- [ ] Interpret findings

### Week 37-40: Complete Paper
- [ ] Introduction
- [ ] Literature review
- [ ] Methodology (detailed)
- [ ] Results
- [ ] Discussion
- [ ] Policy implications
- [ ] Conclusions

---

# 5. TECHNICAL IMPLEMENTATION

## 5.1 Excel Implementation

### Workbook Structure

**Create a master workbook: `TWF_India_2024-25.xlsx`**

**Sheet Organization:**

1. **Data_SUT_2019-20**
   - Paste entire SUT from downloaded file
   
2. **Data_NAS_GVA**
   - Paste Statement 1.6 (GVA by sector)
   
3. **Data_NAS_Growth**
   - Paste Statement 1.6B (Growth rates)
   
4. **Data_Tourism**
   - TSA 2015-16 data (manually entered from PDF)
   - Tourism Statistics 2024
   
5. **Data_Water**
   - Water use by sector
   - Water coefficients
   
6. **Calc_IO_2019-20**
   - Converted IO table base year
   
7. **Calc_Growth_Factors**
   - Cumulative growth calculations
   
8. **Calc_IO_2024-25**
   - Updated IO table
   
9. **Calc_Tech_Coefficients**
   - A matrix (66×66)
   
10. **Calc_Leontief**
    - (I-A)^-1 matrix (66×66)
    
11. **Calc_Tourism_Demand**
    - Final demand vector
    
12. **Results_TWF**
    - All TWF calculations
    
13. **Analysis**
    - Charts, tables, interpretations
    
14. **Documentation**
    - Assumptions, data sources, notes

### Key Excel Formulas

**Growth Factor Calculation:**
```excel
=PRODUCT(1+B2:B6)  // For 5 years of growth rates
```

**Technical Coefficient:**
```excel
=Intermediate_Input / SUMIF($A:$A, A2, $B:$B)  // Divide by column total
```

**Leontief Inverse:**
```excel
=MINVERSE(I_minus_A_range)
// Select 66×66 range, type formula, press Ctrl+Shift+Enter
```

**Matrix Multiplication:**
```excel
=MMULT(Matrix1, Matrix2)
// Array formula: Ctrl+Shift+Enter
```

**TWF Calculation:**
```excel
=SUMPRODUCT(Water_Coefficients, Total_Output)
```

## 5.2 Python Implementation

### Setup

```python
# Required libraries
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.linalg import inv

# For reading Excel files
pip install openpyxl xlrd

# For visualizations
pip install matplotlib seaborn plotly
```

### Complete Python Script

```python
"""
Tourism Water Footprint Calculation for India 2024-25
"""

import pandas as pd
import numpy as np
from scipy.linalg import inv
import matplotlib.pyplot as plt

# ============================================
# STEP 1: LOAD DATA
# ============================================

# Load SUT 2019-20
sut_supply = pd.read_excel('SUT_2019-20_m.xlsx', 
                           sheet_name='Supply_Table')
sut_use = pd.read_excel('SUT_2019-20_m.xlsx', 
                        sheet_name='Use_Table')

# Load NAS growth rates
nas_growth = pd.read_excel('NAS_2025_Statement_1.6B.xlsx',
                           sheet_name='Sheet1')

# Load water use data
water_data = pd.read_excel('Water_Data_Compiled.xlsx')

# Load tourism expenditure
tourism_exp = pd.read_excel('Tourism_Expenditure_2024.xlsx')

# ============================================
# STEP 2: CONVERT SUT TO IO (2019-20)
# ============================================

def sut_to_io_pta(supply_matrix, use_matrix):
    """
    Convert Supply-Use Table to Input-Output Table
    Using Product Technology Assumption (PTA)
    """
    # Calculate market share matrix
    product_outputs = supply_matrix.sum(axis=1)
    D = supply_matrix.div(product_outputs, axis=0)
    
    # Product-by-Product IO
    B = use_matrix @ D.T
    
    # Convert to Industry-by-Industry
    industry_outputs = supply_matrix.sum(axis=0)
    Z = D.T @ B @ np.diag(1/industry_outputs)
    
    return Z

# Convert to IO
io_2019 = sut_to_io_pta(sut_supply, sut_use)

print(f"IO Table 2019-20 shape: {io_2019.shape}")
print(f"Total intermediate consumption: {io_2019.sum().sum():.2f} crores")

# ============================================
# STEP 3: UPDATE IO TABLE TO 2024-25
# ============================================

def calculate_growth_factors(growth_rates_df):
    """
    Calculate cumulative growth factors for 5 years
    """
    # Assuming columns are years 2020-21 to 2024-25
    growth_factors = (1 + growth_rates_df).prod(axis=1)
    return growth_factors

# Calculate growth factors
growth_factors = calculate_growth_factors(nas_growth)

# Update industry outputs
outputs_2019 = io_2019.sum(axis=0)
outputs_2024 = outputs_2019 * growth_factors

# RAS Method for updating IO table
def ras_method(Z_base, row_targets, col_targets, max_iter=100, tolerance=1e-6):
    """
    RAS method to update IO table
    """
    Z = Z_base.copy()
    
    for iteration in range(max_iter):
        # Row scaling
        row_sums = Z.sum(axis=1)
        r_factors = row_targets / (row_sums + 1e-10)
        Z = Z.mul(r_factors, axis=0)
        
        # Column scaling
        col_sums = Z.sum(axis=0)
        s_factors = col_targets / (col_sums + 1e-10)
        Z = Z.mul(s_factors, axis=1)
        
        # Check convergence
        row_error = np.abs(Z.sum(axis=1) - row_targets).max()
        col_error = np.abs(Z.sum(axis=0) - col_targets).max()
        
        if row_error < tolerance and col_error < tolerance:
            print(f"RAS converged in {iteration+1} iterations")
            break
    
    return Z

# Update IO table
io_2024 = ras_method(io_2019, outputs_2024, outputs_2024)

# ============================================
# STEP 4: CALCULATE TECHNICAL COEFFICIENTS
# ============================================

# Technical coefficients matrix
X = io_2024.sum(axis=0)
A = io_2024.div(X, axis=1)

print(f"Technical coefficients matrix shape: {A.shape}")
print(f"Example coefficient (sector 1 to 1): {A.iloc[0,0]:.6f}")

# ============================================
# STEP 5: CALCULATE LEONTIEF INVERSE
# ============================================

# Identity matrix
I = np.eye(len(A))

# I - A
I_minus_A = I - A.values

# Leontief inverse
L = inv(I_minus_A)
L_df = pd.DataFrame(L, columns=A.columns, index=A.index)

print(f"Leontief inverse calculated successfully")
print(f"Average multiplier: {L.mean():.3f}")

# ============================================
# STEP 6: PREPARE WATER COEFFICIENTS
# ============================================

# Create water coefficient vector (66 sectors)
# Match water data to IO sectors

water_coefficients = water_data['DWC'].values  # m³/₹

print(f"Water coefficients: {len(water_coefficients)} sectors")
print(f"Highest water coefficient: {water_coefficients.max():.6f} m³/₹")
print(f"Sector: {water_data.iloc[water_coefficients.argmax()]['Sector']}")

# ============================================
# STEP 7: PREPARE TOURISM FINAL DEMAND
# ============================================

# Create tourism final demand vector (66×1)
Y_tourism = np.zeros(66)

# Fill in tourism sectors from TSA
# Example: Hotels (sector 55), Restaurants (56), etc.
tourism_sector_mapping = {
    55: tourism_exp['Hotels'],
    56: tourism_exp['Restaurants'],
    49: tourism_exp['Rail_Transport'],
    50: tourism_exp['Road_Transport'],
    51: tourism_exp['Air_Transport'],
    # ... add all 11 sectors
}

for sector_idx, value in tourism_sector_mapping.items():
    Y_tourism[sector_idx] = value

print(f"Total tourism final demand: ₹{Y_tourism.sum():.2f} crores")

# ============================================
# STEP 8: CALCULATE TWF
# ============================================

# Total output required for tourism
X_tourism = L @ Y_tourism

# Direct TWF
direct_twf = water_coefficients * Y_tourism
total_direct_twf = direct_twf.sum()

# Total TWF (direct + indirect)
total_twf = water_coefficients * X_tourism
total_twf_sum = total_twf.sum()

# Indirect TWF
indirect_twf = total_twf - direct_twf
total_indirect_twf = indirect_twf.sum()

print("\n" + "="*50)
print("TOURISM WATER FOOTPRINT RESULTS")
print("="*50)
print(f"Direct TWF: {total_direct_twf:,.0f} million m³")
print(f"Indirect TWF: {total_indirect_twf:,.0f} million m³")
print(f"Total TWF: {total_twf_sum:,.0f} million m³")
print(f"Indirect/Direct Ratio: {total_indirect_twf/total_direct_twf:.2f}")

# ============================================
# STEP 9: SECTORAL BREAKDOWN
# ============================================

# Top 10 sectors contributing to TWF
twf_by_sector = pd.DataFrame({
    'Sector': water_data['Sector'],
    'TWF': total_twf,
    'Direct': direct_twf,
    'Indirect': indirect_twf
})

top_10_total = twf_by_sector.nlargest(10, 'TWF')
print("\nTop 10 Sectors by Total TWF:")
print(top_10_total)

top_10_indirect = twf_by_sector.nlargest(10, 'Indirect')
print("\nTop 10 Sectors by Indirect TWF:")
print(top_10_indirect)

# ============================================
# STEP 10: VISUALIZATIONS
# ============================================

# Plot 1: Direct vs Indirect TWF
fig, ax = plt.subplots(figsize=(10, 6))
categories = ['Direct TWF', 'Indirect TWF']
values = [total_direct_twf, total_indirect_twf]
ax.bar(categories, values, color=['#3498db', '#e74c3c'])
ax.set_ylabel('Million m³')
ax.set_title('Direct vs Indirect Tourism Water Footprint')
plt.savefig('twf_direct_indirect.png', dpi=300, bbox_inches='tight')

# Plot 2: Top sectors
fig, ax = plt.subplots(figsize=(12, 8))
top_10_total.plot(x='Sector', y='TWF', kind='barh', ax=ax)
ax.set_xlabel('TWF (million m³)')
ax.set_title('Top 10 Sectors by Tourism Water Footprint')
plt.savefig('twf_top_sectors.png', dpi=300, bbox_inches='tight')

# Plot 3: Pie chart of direct tourism sectors
direct_tourism_sectors = twf_by_sector[twf_by_sector['Direct'] > 0]
fig, ax = plt.subplots(figsize=(10, 10))
ax.pie(direct_tourism_sectors['Direct'], 
       labels=direct_tourism_sectors['Sector'],
       autopct='%1.1f%%')
ax.set_title('Direct TWF by Tourism Sector')
plt.savefig('twf_pie_direct.png', dpi=300, bbox_inches='tight')

# ============================================
# STEP 11: EXPORT RESULTS
# ============================================

# Create results workbook
with pd.ExcelWriter('TWF_Results_2024-25.xlsx') as writer:
    twf_by_sector.to_excel(writer, sheet_name='TWF_by_Sector', index=False)
    top_10_total.to_excel(writer, sheet_name='Top_10_Total', index=False)
    top_10_indirect.to_excel(writer, sheet_name='Top_10_Indirect', index=False)
    
    # Summary statistics
    summary = pd.DataFrame({
        'Metric': ['Direct TWF (million m³)', 
                   'Indirect TWF (million m³)',
                   'Total TWF (million m³)',
                   'Indirect/Direct Ratio',
                   'Total Tourism Expenditure (₹ crores)',
                   'TWF per ₹ crore expenditure (m³)'],
        'Value': [total_direct_twf,
                  total_indirect_twf,
                  total_twf_sum,
                  total_indirect_twf/total_direct_twf,
                  Y_tourism.sum(),
                  total_twf_sum / Y_tourism.sum()]
    })
    summary.to_excel(writer, sheet_name='Summary', index=False)

print("\nResults exported to TWF_Results_2024-25.xlsx")
print("Visualizations saved as PNG files")
```

---

# 6. ANALYSIS FRAMEWORK

## 6.1 Key Metrics to Calculate

### 1. Aggregate Metrics
- Total TWF (million m³)
- Direct TWF (million m³)
- Indirect TWF (million m³)
- TWF as % of total India water consumption
- TWF as % of GDP

### 2. Per Tourist Metrics
- TWF per domestic tourist per day (liters)
- TWF per inbound tourist per day (liters)
- Direct TWF per tourist per day
- Indirect TWF per tourist per day

### 3. Sectoral Metrics
- TWF by direct tourism sector
- TWF by indirect supply sector
- Water intensity by sector (m³/₹)
- Multiplier effects

### 4. Comparative Metrics
- Domestic vs Inbound ratio
- India vs China comparison
- India vs other countries
- Change over time (if multiple years)

## 6.2 Expected Results (Hypotheses)

Based on the China study, expect:

1. **Indirect >> Direct TWF**
   - Ratio of 10:1 to 15:1
   - Agriculture dominates indirect

2. **Inbound > Domestic per tourist**
   - Inbound: 5000-7000 L/tourist/day
   - Domestic: 1000-1500 L/tourist/day

3. **Top Indirect Sectors:**
   - Agriculture (60-70% of indirect)
   - Electricity (10-15%)
   - Food manufacturing (5-10%)

4. **Top Direct Sectors:**
   - Hotels & restaurants (70-80% of direct)
   - Transportation (15-20%)

## 6.3 Policy Implications

**Key Questions to Address:**

1. **Water Conservation:**
   - Which sectors offer greatest water saving potential?
   - What are feasible intervention points?

2. **Sustainable Tourism:**
   - How to balance tourism growth with water constraints?
   - Which tourism models are most water-efficient?

3. **Regional Planning:**
   - Which states/regions face highest TWF stress?
   - How to redirect tourism to water-rich regions?

4. **Technology & Innovation:**
   - Role of water-saving technologies
   - Wastewater recycling potential
   - Rainwater harvesting in tourism sector

---

# 7. EXPECTED OUTPUTS

## 7.1 Academic Paper Structure

**Title:** 
"Tourism Water Footprint of India: An Input-Output Analysis of Direct and Indirect Water Consumption"

**Abstract** (250 words)
- Research problem
- Methodology (EEIO + TSA)
- Key findings
- Policy implications

**1. Introduction**
- Tourism growth in India
- Water scarcity challenges
- Research gap
- Objectives

**2. Literature Review**
- Water footprint concept
- Tourism water studies globally
- India-specific context
- Theoretical framework

**3. Methodology**
- EEIO framework
- Data sources (SUT, NAS, TSA, CGWB)
- SUT to IO conversion
- Water coefficient calculation
- Limitations & assumptions

**4. Results**
- Total TWF (direct + indirect)
- Sectoral breakdown
- Domestic vs inbound
- Per tourist analysis
- Sensitivity analysis

**5. Discussion**
- Interpretation of results
- Comparison with other countries
- Structural insights
- Water stress implications

**6. Policy Recommendations**
- Water conservation strategies
- Sustainable tourism planning
- Technology interventions
- Regional considerations

**7. Conclusions**
- Summary of findings
- Contributions
- Future research

## 7.2 Visualizations to Create

### Figure 1: Direct vs Indirect TWF (Bar Chart)
### Figure 2: Sectoral Breakdown (Stacked Bar)
### Figure 3: Top 10 Contributors (Horizontal Bar)
### Figure 4: Direct Tourism Sectors (Pie Chart)
### Figure 5: Domestic vs Inbound Comparison
### Figure 6: Supply Chain Network (Sankey Diagram)
### Figure 7: TWF Intensity by Sector (Heatmap)
### Figure 8: Water Stress Overlay Map (Geographic)

## 7.3 Tables to Include

**Table 1:** Summary Statistics
**Table 2:** Sectoral TWF Breakdown (66 sectors)
**Table 3:** Direct Tourism Sectors (11 sectors)
**Table 4:** Top 20 Indirect Contributors
**Table 5:** Domestic vs Inbound Comparison
**Table 6:** Per Tourist Metrics
**Table 7:** Sensitivity Analysis Results
**Table 8:** International Comparison

---

# APPENDIX

## A. Concordance Tables

### TSA to IO Sector Mapping
[To be developed based on actual TSA and IO sector classifications]

### NIC to IO Sector Mapping
[Based on NIC 2008 classification used in SUT]

## B. Data Quality Documentation

### Data Completeness Checklist
- [ ] All 66 IO sectors have water coefficients
- [ ] All growth rates extracted
- [ ] Tourism expenditure mapped to sectors
- [ ] Validation completed

### Assumptions Log
1. Technical coefficients remain stable 2019-20 to 2024-25
2. Tourist expenditure patterns from 2015-16 TSA scaled proportionally
3. Water coefficients based on 2023-24 data
4. [Add all assumptions made]

## C. Software Requirements

### Excel
- Microsoft Excel 2016 or later
- Matrix calculation capability
- Solver add-in (optional)

### Python
- Python 3.8+
- NumPy 1.20+
- Pandas 1.3+
- SciPy 1.7+
- Matplotlib 3.4+
- Seaborn 0.11+

## D. Quality Assurance

### Validation Checks
1. Row-column balance in IO table
2. Leontief inverse positive definiteness
3. Multipliers within reasonable range (1-5)
4. TWF results order of magnitude check
5. Comparison with bottom-up estimates

### Peer Review
- Have methodology reviewed
- Results peer-checked
- Calculations independently verified

---

## FINAL CHECKLIST BEFORE SUBMISSION

- [ ] All data sources properly cited
- [ ] Methodology clearly documented
- [ ] Results tables formatted
- [ ] All figures have captions
- [ ] Limitations acknowledged
- [ ] Policy recommendations justified
- [ ] Sensitivity analysis conducted
- [ ] Comparison with literature
- [ ] Abstract written
- [ ] Keywords identified
- [ ] References formatted
- [ ] Supplementary materials prepared
- [ ] Ethical considerations addressed
- [ ] Data availability statement
- [ ] Acknowledgments written

---

**END OF GUIDE**

**Document Version:** 1.0
**Last Updated:** February 2026
**Author:** [Your Name]
**Contact:** [Your Email]

---

## QUICK START SUMMARY

If you want to get started immediately:

**WEEK 1 TASKS:**
1. Download SUT 2019-20
2. Download NAS Statement 1.6 and 1.6B
3. Download TSA 2015-16 PDF
4. Download CGWB 2024 report
5. Set up Excel workbook structure
6. Install Python if using programming approach

**FIRST CALCULATION TO ATTEMPT:**
Convert just the agriculture sector from SUT to IO, calculate its water coefficient, and estimate its contribution to tourism. This will help you understand the full process before scaling to all 66 sectors.

**KEY INSIGHT:**
The methodology seems complex, but it's essentially:
1. Economic structure (IO table)
2. Water intensity (coefficients)
3. Tourism demand (expenditure)
4. Multiply them together!

The devil is in the data compilation details, but the conceptual framework is straightforward.

Good luck with your research!
