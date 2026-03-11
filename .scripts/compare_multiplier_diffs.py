import pandas as pd
from pathlib import Path
years=[2015,2019,2022]
base=Path('.')
for yr in years:
    old=base/ f'working/3-final-results/indirect-water/indirect_twf_{yr}_multiplier.csv'
    new=base/ f'3-final-results/indirect-water/indirect_twf_{yr}_multiplier.csv'
    if not old.exists():
        print('OLD missing',old)
        continue
    if not new.exists():
        print('NEW missing',new)
        continue
    o=pd.read_csv(old)
    n=pd.read_csv(new)
    key='Category_Name'
    if key not in o.columns or key not in n.columns:
        print('No Category_Name in one of files',yr)
        continue
    m=o.merge(n, on=key, how='outer', suffixes=('_old','_new'))
    print('\nYEAR',yr,'rows_old',len(o),'rows_new',len(n),'merged',len(m))
    check_cols=['Demand_crore','WL_m3_per_crore','Multiplier_Ratio','Multiplier','Scarce_m3']
    for col in check_cols:
        a=col+'_old'
        b=col+'_new'
        if a in m.columns and b in m.columns:
            sa=pd.to_numeric(m[a],errors='coerce')
            sb=pd.to_numeric(m[b],errors='coerce')
            d=(sa-sb).abs().fillna(0)
            cnt=(d>1e-6).sum()
            mx=d.max()
            if cnt>0:
                print(f" {col}: diffs={cnt}, max_diff={mx}")
                top_idx=d.sort_values(ascending=False).index[:5]
                print(m.loc[top_idx,[key,a,b]].to_string(index=False))
    # show rows present only in one side
    only_old=m[m[[c for c in m.columns if c.endswith('_new')]].isnull().all(axis=1)]
    only_new=m[m[[c for c in m.columns if c.endswith('_old')]].isnull().all(axis=1)]
    if not only_old.empty:
        print(' rows only in OLD sample:', only_old[key].head().tolist())
    if not only_new.empty:
        print(' rows only in NEW sample:', only_new[key].head().tolist())
print('\nDone')
