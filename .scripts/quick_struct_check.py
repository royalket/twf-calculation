#!/usr/bin/env python3
import pandas as pd
old='old/twf-calculation-main/3-final-results/indirect-water/indirect_twf_2015_structural.csv'
new='3-final-results/indirect-water/indirect_twf_2015_structural.csv'
O=pd.read_csv(old)
N=pd.read_csv(new)
O['Water_m3']=pd.to_numeric(O['Water_m3'],errors='coerce').fillna(0)
N['Water_m3']=pd.to_numeric(N['Water_m3'],errors='coerce').fillna(0)
print('TOT_OLD',O['Water_m3'].sum())
print('TOT_NEW',N['Water_m3'].sum())
agg=(O.groupby('Category_ID')['Water_m3'].sum()-N.groupby('Category_ID')['Water_m3'].sum()).abs()
print('\nTOP 5 CATEGORIES BY ABSOLUTE DIFF')
print(agg.sort_values(ascending=False).head(5).to_string())
