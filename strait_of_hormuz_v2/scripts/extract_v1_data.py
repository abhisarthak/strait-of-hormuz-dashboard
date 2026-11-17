"""Extract the exact Script 98 JSON array embedded in the existing V1 HTML dashboard."""
from pathlib import Path
import re, json, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "data/simulation/v1_dashboard.html"
if not source.exists():
    raise SystemExit("Place Strait_of_Hormuz_Interactive_Simulation_Dashboard.html at data/simulation/v1_dashboard.html")

html = source.read_text(encoding="utf-8")
match = re.search(r"const DATA = (\\[.*?\\]);", html, flags=re.S)
if not match:
    raise SystemExit("Could not locate the embedded const DATA array in the V1 dashboard.")
rows = json.loads(match.group(1))
df = pd.DataFrame(rows)
required = ["Scenario_ID","Recovery_Policy_ID","Shock_Magnitude_Hours","Affected_Transition_Share",
            "M02_Mean_Incremental_Departure_Delay_Hours","M05_P90_Incremental_Call_Departure_Delay_Hours",
            "M07A_Unrecovered_Call_Count","M07B_Unrecovered_Vessel_Count"]
missing = [c for c in required if c not in df]
if missing:
    raise SystemExit(f"V1 data is missing required fields: {missing}")
out = pd.DataFrame({
 "scenario_id":df["Scenario_ID"],
 "policy_id":df["Recovery_Policy_ID"],
 "shock_hours":df["Shock_Magnitude_Hours"],
 "share":df["Affected_Transition_Share"],
 "mean_delay":df["M02_Mean_Incremental_Departure_Delay_Hours"],
 "p90_delay":df["M05_P90_Incremental_Call_Departure_Delay_Hours"],
 "unrecovered_calls":df["M07A_Unrecovered_Call_Count"],
 "unrecovered_vessels":df["M07B_Unrecovered_Vessel_Count"],
})
if len(out) != 80 or out["scenario_id"].nunique() != 16:
    raise SystemExit(f"Expected 80 scenario-policy rows and 16 scenarios; got {len(out)} rows / {out.scenario_id.nunique()} scenarios.")
out.to_csv(ROOT / "data/simulation/script98_primary.csv",index=False)
print("Extracted 80 exact Script 98 primary scenario-policy rows.")
