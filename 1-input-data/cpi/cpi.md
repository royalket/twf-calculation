# PERFECT! Now I can calculate exact CPI values for your study.

---

## **CALCULATING ANNUAL CPI FOR FINANCIAL YEARS**

### **Financial Year = April to March**

```
2015-16 = Apr 2015 to Mar 2016
2019-20 = Apr 2019 to Mar 2020
2021-22 = Apr 2021 to Mar 2022
```

---

## **CALCULATION:**

### **CPI 2015-16:**

```
Month          CPI Value
─────────────────────────
Apr 2015       120.7
May 2015       121.6
Jun 2015       123.0
Jul 2015       123.6
Aug 2015       124.8
Sep 2015       125.4
Oct 2015       126.1
Nov 2015       126.6
Dec 2015       126.1
Jan 2016       126.3
Feb 2016       126.0
Mar 2016       126.0

Average = (120.7 + 121.6 + 123.0 + 123.6 + 124.8 + 125.4 + 
           126.1 + 126.6 + 126.1 + 126.3 + 126.0 + 126.0) / 12
        = 1,496.2 / 12
        = 124.68
        ≈ 124.7
```

---

### **CPI 2019-20:**

```
Month          CPI Value
─────────────────────────
Apr 2019       141.2
May 2019       142.0
Jun 2019       142.9
Jul 2019       144.2
Aug 2019       145.0
Sep 2019       145.8
Oct 2019       147.2
Nov 2019       148.6
Dec 2019       150.4
Jan 2020       150.2
Feb 2020       149.1
Mar 2020       148.6

Average = (141.2 + 142.0 + 142.9 + 144.2 + 145.0 + 145.8 + 
           147.2 + 148.6 + 150.4 + 150.2 + 149.1 + 148.6) / 12
        = 1,755.2 / 12
        = 146.27
        ≈ 146.3
```

---

### **CPI 2021-22:**

```
Month          CPI Value
─────────────────────────
Apr 2021       157.8
May 2021       160.4
Jun 2021       161.3
Jul 2021       162.5
Aug 2021       162.9
Sep 2021       163.2
Oct 2021       165.5
Nov 2021       166.7
Dec 2021       166.2
Jan 2022       165.7
Feb 2022       166.1
Mar 2022       167.7

Average = (157.8 + 160.4 + 161.3 + 162.5 + 162.9 + 163.2 + 
           165.5 + 166.7 + 166.2 + 165.7 + 166.1 + 167.7) / 12
        = 1,966.0 / 12
        = 163.83
        ≈ 163.8
```

---

## **SUMMARY:**

```python
CPI_DATA = {
    '2015-16': 124.7,  # Apr 2015 - Mar 2016
    '2019-20': 146.3,  # Apr 2019 - Mar 2020
    '2021-22': 163.8,  # Apr 2021 - Mar 2022
}
```

---

## **INFLATION RATES:**

### **2015-16 → 2019-20:**
```
CPI Adjustment = 146.3 / 124.7 = 1.173 (17.3% cumulative inflation)
Annual Rate = (1.173)^(1/4) - 1 = 4.1% per year
```

### **2015-16 → 2021-22:**
```
CPI Adjustment = 163.8 / 124.7 = 1.313 (31.3% cumulative inflation)
Annual Rate = (1.313)^(1/6) - 1 = 4.7% per year
```

### **2019-20 → 2021-22:**
```
CPI Adjustment = 163.8 / 146.3 = 1.120 (12.0% cumulative inflation)
Annual Rate = (1.120)^(1/2) - 1 = 5.8% per year (higher due to COVID supply shocks)
```

---
