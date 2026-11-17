from pathlib import Path
import pandas as pd
root=Path(__file__).resolve().parents[1]
p=root/'data/simulation/script98_primary.csv'
if not p.exists():
    print('Script 98 primary CSV not yet extracted. See README.')
else:
    d=pd.read_csv(p)
    assert len(d)==80
    assert d.scenario_id.nunique()==16
    assert d.groupby('scenario_id').size().eq(5).all()
    assert d.groupby(['shock_hours','share']).ngroups==16
    print('Script 98 data checks passed.')
s=pd.read_csv(root/'data/simulation/script77_policy_summary.csv')
assert len(s)==5
print('Script 77 policy summary present.')
