# NEXT STEPS: Tourism Water Footprint Study Implementation Plan

## IMMEDIATE ACTIONS (This Week)

### Action 1: Validate Agriculture Data ✓ DONE
**Status:** Completed
**Result:** 
- Agriculture output: ₹2,279,652 crore
- Water coefficient: 0.0912 m³/₹
- Validation: 99.93% match with CGWB data

### Action 2: Include ALL Agriculture Subsectors
**What to do:**
- Currently only using "Agriculture" column (crop production)
- Need to add: Livestock + Forestry + Fishing
- Expected combined output: ~₹3.3-3.5 lakh crore

**Implementation:**
```python
# Updated calculation
agri_output_total = (
    agriculture_column_1 +  # Crops
    livestock_column_2 +     # Livestock  
    forestry_column_3 +      # Forestry
    fishing_column_4         # Fishing
)
```

### Action 3: Create Full IO Table (Priority 1)
**Time required:** 3-5 days
**Difficulty:** Medium-High

**What you need:**
1. Python script to convert SUT to IO
2. Understanding of Product Technology Assumption (PTA)
3. Matrix operations (NumPy)

**Steps:**
a. Read full Supply Table (140 products × 66 industries)
b. Read full Use Table (140 products × 66 industries)
c. Apply PTA transformation
d. Generate 66×66 IO matrix

**Code framework:**
```python
# Step 1: Calculate market share matrix
V = supply_table  # 140 × 66
q = product_outputs  # 140 × 1
D = V / q  # Element-wise division

# Step 2: Product-by-product IO
U = use_table  # 140 × 66
B = U @ D.T  # Matrix multiplication

# Step 3: Industry-by-industry IO
g = industry_outputs  # 66 × 1
Z = D.T @ B  # 66 × 66 IO matrix
```

**Deliverable:** `io_table_2019_20.csv` (66×66 matrix)

---

## SHORT-TERM ACTIONS (Next 2 Weeks)

### Action 4: Update IO Table to 2024-25
**Time required:** 2-3 days
**Difficulty:** Medium

**Data needed:**
- ✓ NAS Statement 1.6B (growth rates) - HAVE
- ✓ NAS Statement 1.6 (GVA values) - HAVE
- ❌ RAS algorithm implementation - NEED TO CODE

**Steps:**
a. Extract growth rates for all 66 sectors
b. Calculate cumulative growth 2019-20 → 2024-25
c. Apply RAS method to balance IO table
d. Validate updated table

**Deliverable:** `io_table_2024_25.csv`

### Action 5: Calculate Technical Coefficients
**Time required:** 1 day
**Difficulty:** Easy

**Formula:**
```
A = Z / Total_Output (column-wise division)
```

**Deliverable:** `technical_coefficients_2024_25.csv`

### Action 6: Calculate Leontief Inverse
**Time required:** 1 day
**Difficulty:** Easy

**Formula:**
```python
I = np.eye(66)
A = technical_coefficients
L = np.linalg.inv(I - A)
```

**Validation check:**
- Diagonal elements should be > 1 (typically 1.1 to 3.0)
- Off-diagonal should be small (0.001 to 0.5)
- All elements should be positive

**Deliverable:** `leontief_inverse_2024_25.csv`

---

## MEDIUM-TERM ACTIONS (Weeks 3-4)

### Action 7: Compile Water Use Data for All 66 Sectors
**Time required:** 5-7 days
**Difficulty:** High (data availability issues)

**Sectors to prioritize:**

#### High Priority (Direct tourism sectors):
1. Hotels & Restaurants (sector 55, 56)
2. Rail Transport (sector 49.1)
3. Road Transport (sector 49.2-49.4)
4. Air Transport (sector 51)
5. Trade/Retail (sector 52)
6. Recreation & Entertainment (sector 90-93)

**Data sources:**
- Hotels: Industry reports (300-1200 L/guest/night)
- Transport: Indian Railways, Airport Authority reports
- Retail: Estimate based on floor space and employees

#### Medium Priority (Indirect suppliers):
7. Agriculture (DONE)
8. Food Manufacturing (sectors 11-15)
9. Textiles (sector 17)
10. Electricity (sector 42)
11. Water Supply (sector 44)

**Data sources:**
- Manufacturing: Industry water audits, benchmarks
- Electricity: CEA reports (3-4 m³/MWh thermal power)

#### Low Priority (Minimal impact):
12. All other sectors: Use international benchmarks or estimates

**Deliverable:** `water_coefficients_all_sectors_2024_25.csv`

### Action 8: Extract Tourism Expenditure from TSA
**Time required:** 3-4 days
**Difficulty:** Medium (manual data entry from PDF)

**What to do:**
1. Open TSA 2015-16 PDF (you have this: `011-TSAI.pdf`)
2. Find Table: "Tourism Expenditure by Product/Sector"
3. Manually enter data into Excel/CSV
4. Separate: Domestic vs Inbound tourism expenditure

**Expected structure:**
```
Sector                     Domestic (₹cr)  Inbound (₹cr)  Total
Accommodation              50,000          10,000         60,000
Food & Beverages           80,000          8,000          88,000
Rail Transport             30,000          2,000          32,000
Road Transport             60,000          3,000          63,000
Air Transport              20,000          15,000         35,000
Shopping                   100,000         12,000         112,000
...
```

**Deliverable:** `tsa_2015_16_expenditure.csv`

### Action 9: Map TSA Sectors to 66 IO Sectors
**Time required:** 2 days
**Difficulty:** Medium (requires understanding both classifications)

**Create concordance table:**
```
TSA_Sector              IO_Sector_Number  IO_Sector_Name
Accommodation           55                Hotels
Food & Beverages        56                Restaurants & Cafes
Rail Transport          49.1              Railway transport
Road Transport          49.2              Road transport
Air Transport           51                Air transport
Shopping                52                Retail trade
Cultural Services       90-93             Recreation & entertainment
...
```

**Deliverable:** `tsa_to_io_concordance.csv`

### Action 10: Scale Tourism Expenditure to 2024
**Time required:** 1 day
**Difficulty:** Easy

**Data available:**
- ✓ TSA 2015-16 total: Need to extract from PDF
- ✓ Tourism Statistics 2024 total: ₹18.6 lakh crore

**Calculation:**
```
Scaling_Factor = 18.6 lakh crore / TSA_2015_16_Total
Updated_Expenditure_2024 = TSA_Expenditure × Scaling_Factor
```

**Deliverable:** `tourism_final_demand_2024_25.csv` (66×1 vector)

---

## LONG-TERM ACTIONS (Weeks 5-6)

### Action 11: Calculate Direct TWF
**Time required:** 1 day
**Difficulty:** Easy

**Formula:**
```python
Direct_TWF = np.sum(water_coefficients * tourism_demand)
```

**Expected result:** ~5,000-10,000 million m³

### Action 12: Calculate Total TWF
**Time required:** 1 day  
**Difficulty:** Easy

**Formula:**
```python
Total_Output = leontief_inverse @ tourism_demand
Total_TWF = np.sum(water_coefficients * Total_Output)
```

**Expected result:** ~50,000-100,000 million m³

### Action 13: Calculate Indirect TWF
**Time required:** 1 hour
**Difficulty:** Easy

**Formula:**
```python
Indirect_TWF = Total_TWF - Direct_TWF
```

**Expected result:** ~40,000-90,000 million m³

### Action 14: Sectoral Breakdown Analysis
**Time required:** 2-3 days
**Difficulty:** Medium

**Analyses to perform:**
1. Top 10 sectors by TWF contribution
2. Direct vs Indirect by sector
3. Agriculture's share of indirect TWF
4. Domestic vs Inbound comparison
5. Per tourist water footprint

**Deliverables:**
- Tables with rankings
- Bar charts, pie charts
- Sankey diagram (flow visualization)

### Action 15: Sensitivity Analysis
**Time required:** 2 days
**Difficulty:** Medium

**Variables to test:**
- Water coefficients (±20%)
- Tourism demand (±10%)
- Growth rates (±5%)
- Leontief inverse assumptions

**Deliverable:** `sensitivity_analysis_results.csv`

---

## FINAL ACTIONS (Week 7-8)

### Action 16: Write Research Paper
**Time required:** 5-7 days
**Difficulty:** Medium

**Structure:**
1. Introduction (2-3 pages)
2. Literature Review (5-7 pages)
3. Methodology (8-10 pages)
4. Results (10-15 pages)
5. Discussion (5-7 pages)
6. Policy Recommendations (3-5 pages)
7. Conclusions (2-3 pages)

### Action 17: Create Visualizations
**Time required:** 3-4 days
**Difficulty:** Medium

**Required charts:**
1. Direct vs Indirect TWF (bar chart)
2. Sectoral breakdown (stacked bar)
3. Top contributors (horizontal bar)
4. Supply chain network (Sankey)
5. Domestic vs Inbound comparison
6. Water stress map (geographic)
7. Temporal trends
8. Per tourist metrics

### Action 18: Validation & Peer Review
**Time required:** 3-5 days
**Difficulty:** High

**Validation checks:**
- Cross-check with bottom-up estimates
- Compare with international studies
- Sensitivity to assumptions
- Expert review of methodology

---

## DECISION POINTS

### Decision 1: Do We Need Primary Survey?
**Question:** Should we conduct a survey of hotels/restaurants/tourists?

**Pros:**
- More accurate tourism expenditure data
- Current data (2024-25)
- India-specific patterns

**Cons:**
- Time-consuming (2-3 months)
- Expensive (₹5-10 lakh)
- Sample size and representativeness issues

**Recommendation:** 
- Start with TSA 2015-16 scaled to 2024
- If results are published and well-received, conduct survey for follow-up study

### Decision 2: Full 66 Sectors or Simplified?
**Question:** Should we model all 66 sectors or aggregate to ~15-20?

**Full 66 sectors:**
- Pros: More accurate, detailed insights
- Cons: More data requirements, complex

**Aggregated 15-20 sectors:**
- Pros: Easier data collection, faster completion
- Cons: Loss of detail, less precise

**Recommendation:**
- Start with full 66 for IO table (already in SUT)
- Can aggregate later for presentation if needed

### Decision 3: Include Outbound Tourism?
**Question:** Should we calculate water footprint of Indian tourists abroad?

**Pros:**
- Complete picture of India's tourism water impact
- Interesting for policy (net exporter/importer of water)
- Academic contribution

**Cons:**
- Requires data on destination countries
- Estimates will be rough
- Less policy relevance for India

**Recommendation:**
- Include as a separate section
- Use simplified methodology (per capita × tourist days)
- Focus main analysis on domestic + inbound

---

## RESOURCE REQUIREMENTS

### Software
- ✓ Python 3.x (have)
- ✓ Pandas, NumPy, SciPy (have)
- ✓ Matplotlib, Seaborn (have)
- ❌ Excel with Solver add-in (for RAS method alternative)
- ❌ Plotly (for interactive visualizations) - install if needed

### Data
- ✓ SUT 2019-20 (have)
- ✓ NAS 2025 statements (have)
- ✓ TSA 2015-16 PDF (have)
- ✓ Tourism Statistics 2024 (have)
- ❌ CGWB detailed sectoral data (need to download)
- ❌ CEA electricity reports (need to download)
- ❌ Industry water benchmarks (need to research)

### Time
- Full-time: 8-10 weeks
- Part-time (50%): 16-20 weeks
- Part-time (25%): 32-40 weeks

### Expertise
- ✓ Python programming (have)
- ✓ Data analysis (have)
- ✓ Excel skills (have)
- ❌ Input-Output analysis (need to learn - 1-2 weeks)
- ❌ Economic modeling (need to learn - 1-2 weeks)

---

## QUICK START (TODAY)

### What You Can Do Right Now:

1. **Read the guide Section 3.2** - Understand SUT to IO conversion
2. **Start coding IO conversion** - Follow the Python script in guide
3. **Extract TSA data** - Open 011-TSAI.pdf and start manual data entry
4. **Download CGWB report** - Get detailed water use data

### Tomorrow:
1. Complete IO table conversion code
2. Test with agriculture sector (validation)
3. Extract more TSA tables

### This Week:
1. Full 66×66 IO table created
2. Technical coefficients calculated
3. Leontief inverse computed
4. TSA data entered

---

## SUCCESS METRICS

**By End of Week 2:**
- ✓ IO table 2024-25 created
- ✓ Leontief inverse calculated
- ✓ Tourism demand vector ready

**By End of Week 4:**
- ✓ Water coefficients for all 66 sectors
- ✓ Direct TWF calculated
- ✓ Total TWF calculated

**By End of Week 8:**
- ✓ Complete analysis done
- ✓ Paper draft ready
- ✓ Visualizations created
- ✓ Ready for submission

---

## SUPPORT & RESOURCES

### Learning Resources:
1. Miller & Blair (2009) - Input-Output Analysis: Foundations and Extensions
2. OECD Handbook on IO Tables
3. YouTube: "Input-Output Analysis Tutorial"
4. Your guide: Section 3 (Complete methodology)

### Data Sources:
1. MOSPI: https://mospi.gov.in
2. CGWB: https://cgwb.gov.in
3. India WRIS: https://indiawris.gov.in
4. Tourism Ministry: https://tourism.gov.in
5. CEA: https://cea.nic.in

### Tools:
1. Python IO-PAC package (if available)
2. R: ioanalysis package
3. Excel: IO modeling templates

---

## CONCLUSION

You are at the **15% completion mark** of the full study.

**Completed:**
- Data collection and organization
- Agriculture sector test case
- Methodology understanding

**Critical path forward:**
1. Create full IO table (blocks everything else)
2. Get water coefficients (can do in parallel)
3. Get tourism demand (can do in parallel)
4. Calculate TWF (quick once #1-3 done)
5. Analysis and writing

**Estimated time to completion:**
- Optimistic: 6 weeks (full-time)
- Realistic: 10 weeks (full-time)
- With part-time: 20-25 weeks

**Next action:** Start coding the SUT to IO conversion script.

---

**Last Updated:** February 8, 2026
