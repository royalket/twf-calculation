import pandas as pd
from pathlib import Path
import numpy as np
old_root=Path('old/twf-calculation-main/3-final-results')
new_root=Path('3-final-results')
if not old_root.exists():
    print('Old results directory not found:', old_root)
    raise SystemExit(1)
reports=[]
for old_file in sorted(old_root.rglob('*.csv')):
    rel=old_file.relative_to(old_root)
    new_file=new_root/rel
    rec={'file':str(rel)}
    if not new_file.exists():
        rec['status']='MISSING_NEW'
        reports.append(rec)
        continue
    try:
        old=pd.read_csv(old_file)
        new=pd.read_csv(new_file)
    except Exception as e:
        rec['status']='READ_ERROR'
        rec['error']=str(e)
        reports.append(rec)
        continue
    rec['status']='OK'
    rec['old_rows']=len(old); rec['new_rows']=len(new)
    rec['old_cols']=list(old.columns); rec['new_cols']=list(new.columns)
    common_cols=[c for c in old.columns if c in new.columns]
    rec['common_cols_count']=len(common_cols)
    # numeric diffs
    num_cols=[]
    diffs=[]
    for c in common_cols:
        so = pd.to_numeric(old[c], errors='coerce').astype(float)
        sn = pd.to_numeric(new[c], errors='coerce').astype(float)
        if so.notna().any() or sn.notna().any():
            # compute elementwise by aligning on index; if lengths differ, compare up to min len
            L=min(len(so), len(sn))
            d = (so.iloc[:L].fillna(0.0) - sn.iloc[:L].fillna(0.0)).abs()
            maxd = float(d.max()) if not d.empty else 0.0
            cnt = int((d>1e-6).sum()) if not d.empty else 0
            if cnt>0:
                diffs.append((c,cnt,maxd))
    rec['num_diffs']=len(diffs)
    rec['diffs']=sorted(diffs, key=lambda x: x[2], reverse=True)[:5]
    reports.append(rec)
# Print concise summary
for r in reports:
    if r.get('status')!='OK':
        print(r['file'], r.get('status'), r.get('error',''))
        continue
    if r['num_diffs']>0:
        print(f"DIFF {r['file']}: rows old={r['old_rows']} new={r['new_rows']} cols_old={len(r['old_cols'])} cols_new={len(r['new_cols'])} diffs={r['num_diffs']}")
        for c,cnt,mx in r['diffs']:
            print(f"  - {c}: changed_rows={cnt}, max_abs_diff={mx}")
    else:
        # minor: only report unexpected row/col count differences
        if r['old_rows']!=r['new_rows'] or len(r['old_cols'])!=len(r['new_cols']):
            print(f"CHANGED SHAPE {r['file']}: rows old={r['old_rows']} new={r['new_rows']} cols_old={len(r['old_cols'])} cols_new={len(r['new_cols'])}")
# final counts
print('\nSummary:')
print(' total files checked:', len(reports))
print(' files with diffs:', sum(1 for r in reports if r.get('num_diffs',0)>0))
print(' files missing in new:', sum(1 for r in reports if r.get('status')=='MISSING_NEW'))
print(' files read errors:', sum(1 for r in reports if r.get('status')=='READ_ERROR'))
