#!/usr/bin/env python3
import pandas as pd
import sys
old='old/twf-calculation-main/3-final-results/indirect-water/indirect_twf_2015_structural.csv'
new='3-final-results/indirect-water/indirect_twf_2015_structural.csv'

O=pd.read_csv(old)
N=pd.read_csv(new)
print('OLD shape',O.shape)
print('NEW shape',N.shape)
print('\nOLD columns:', O.columns.tolist())
print('\nNEW columns:', N.columns.tolist())
print('\nOLD sample rows:')
print(O.head().to_string(index=False))
print('\nNEW sample rows:')
print(N.head().to_string(index=False))
key_cols=[c for c in ['Category_ID','Category_Name','Source_ID','Source_Name','Source_Group'] if c in O.columns and c in N.columns]
print('\nCommon key cols:', key_cols)
if key_cols:
    ok=set(tuple(r) for r in O[key_cols].astype(str).values)
    nk=set(tuple(r) for r in N[key_cols].astype(str).values)
    print('only_old_count',len(ok-nk),'only_new_count',len(nk-ok))
    # print counts of unique source id if present
    if 'Source_ID' in O.columns and 'Source_ID' in N.columns:
        print('unique sources old', O['Source_ID'].nunique(), 'new', N['Source_ID'].nunique())
# numeric summary differences for all matching numeric columns
num_cols=[]
for c in O.columns:
    if c in N.columns and c not in key_cols:
        # try numeric
        if pd.api.types.is_numeric_dtype(O[c]) or pd.api.types.is_numeric_dtype(N[c]):
            num_cols.append(c)

print('\nNumeric columns considered:', num_cols)

# compute pairwise diffs by merging on keys
merge=O.merge(N, on=key_cols, suffixes=('_old','_new'), how='outer', indicator=True)

def maxabs(row):
    mx=0.0
    for b in num_cols:
        a=row.get(b+'_old')
        c=row.get(b+'_new')
        try:
            a=float(a) if pd.notnull(a) else 0.0
            c=float(c) if pd.notnull(c) else 0.0
            v=abs(a-c)
            if v>mx:
                mx=v
        except Exception:
            continue
    return mx

merge['max_abs_diff']=merge.apply(maxabs, axis=1)
total_rows=len(merge)
diff_rows=(merge['max_abs_diff']>0).sum()
print(f"\ntotal_rows,{total_rows}")
print(f"rows_with_numeric_diff,{diff_rows}")
print(f"numeric_columns_compared,{len(num_cols)}")

print('\nTOP_DIFFS')
res=merge.sort_values('max_abs_diff', ascending=False).head(20)
display_cols = key_cols + [f'{b}_old' for b in num_cols] + [f'{b}_new' for b in num_cols] + ['max_abs_diff']
print(res[display_cols].to_csv(index=False))
