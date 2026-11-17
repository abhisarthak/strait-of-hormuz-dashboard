from pathlib import Path
import json, re
import pandas as pd

POLICIES = {
 "R76-00-NONE":"No recovery",
 "R76-01-FIXED-6H":"Fixed 6h",
 "R76-02-FIXED-12H":"Fixed 12h",
 "R76-03-PROP-25-CAP6":"Proportional 25%, cap 6h",
 "R76-04-PROP-50-CAP12":"Proportional 50%, cap 12h",
}

def load_primary(root: Path) -> pd.DataFrame:
    p = root / "data/simulation/script98_primary.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p)
    df["policy_name"] = df["policy_id"].map(POLICIES)
    return df

def load_script77_summary(root: Path) -> pd.DataFrame:
    p = root / "data/simulation/script77_policy_summary.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p)
    return df

def scenario_filter(df, shock, share):
    return df[(df.shock_hours == shock) & ((df.share-share).abs() < 1e-9)].copy()
