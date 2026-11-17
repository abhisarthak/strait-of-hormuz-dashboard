from pathlib import Path
import sys
import pandas as pd
import numpy as np

# ============================================================
# SCRIPT 89: TRANSITION EXPOSURE AND SCENARIO SELECTION AUDIT
# Purpose:
#   1. Audit the 271 observed distinct-port sequence transitions.
#   2. Separate observed schedule links from validated routes/exposure.
#   3. Generate deterministic nested candidate selections for Script88.
#   4. Preserve all exposure, parameter and execution approvals as pending.
#
# This script does NOT:
#   - modify the 604-call baseline or upstream inputs;
#   - infer actual Hormuz transit or physical sailing routes;
#   - approve any transition for operational/geographic exposure;
#   - execute a simulation.
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "data" / "simulation_inputs"
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"
TABLES.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

FILES = {
    "schedule": INPUTS / "19_historical_arrival_schedule.csv",
    "transitions": INPUTS / "19_observed_interport_transitions.csv",
    "edge": TABLES / "68_edge_exposure_decision_register.csv",
    "port": TABLES / "68_port_exposure_decision_register.csv",
    "scope": TABLES / "68_experiment_scope_decision_matrix.csv",
    "factor": TABLES / "88_scenario_factor_register.csv",
    "protocol": TABLES / "88_protocol_register.csv",
}

missing = [str(p) for p in FILES.values() if not p.exists()]
if missing:
    print("ERROR: Required upstream files are missing:")
    print("\n".join(missing))
    sys.exit(1)

D = {k: pd.read_csv(v, low_memory=False) for k, v in FILES.items()}

def truth_count(series):
    return int(series.fillna(False).astype(str).str.strip().str.lower()
               .isin(["true", "1", "yes"]).sum())

def norm(series):
    return series.astype("string").str.strip().str.upper()

def check(rows, name, passed, observed, expected, note):
    rows.append({
        "Check": name, "Passed": bool(passed),
        "Observed": str(observed), "Expected": str(expected),
        "Interpretation": note
    })

# ----------------------------
# 1. Validate source structure
# ----------------------------
schedule = D["schedule"].copy()
trans = D["transitions"].copy()
edge = D["edge"].copy()
port = D["port"].copy()
scope = D["scope"].copy()
factor = D["factor"].copy()
protocol = D["protocol"].copy()

required_schedule = [
    "Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised",
    "Actual_Arrival_UTC", "Actual_Departure_UTC"
]
required_trans = [
    "Simulation_Record_ID", "IMO_Normalised", "Previous_Port", "Next_Port",
    "Previous_Departure_UTC", "Actual_Arrival_UTC",
    "Elapsed_Hours_Between_Calls"
]
for label, df, required in [
    ("schedule", schedule, required_schedule),
    ("transitions", trans, required_trans),
]:
    absent = [c for c in required if c not in df.columns]
    if absent:
        raise ValueError(f"{label} missing required columns: {absent}")

# Normalize keys and timestamps without modifying source files.
schedule["Simulation_Record_ID"] = norm(schedule["Simulation_Record_ID"])
trans["Simulation_Record_ID"] = norm(trans["Simulation_Record_ID"])
trans["IMO_Normalised"] = norm(trans["IMO_Normalised"])
trans["Previous_Port"] = norm(trans["Previous_Port"])
trans["Next_Port"] = norm(trans["Next_Port"])
trans["Previous_Departure_UTC"] = pd.to_datetime(
    trans["Previous_Departure_UTC"], errors="coerce", utc=True
)
trans["Actual_Arrival_UTC"] = pd.to_datetime(
    trans["Actual_Arrival_UTC"], errors="coerce", utc=True
)
trans["Elapsed_Hours_Between_Calls"] = pd.to_numeric(
    trans["Elapsed_Hours_Between_Calls"], errors="coerce"
)

checks = []
check(checks, "Conservative historical schedule contains 604 calls",
      len(schedule) == 604, len(schedule), 604,
      "The approved historical baseline remains unchanged.")
check(checks, "Historical schedule call IDs are unique",
      schedule["Simulation_Record_ID"].nunique() == len(schedule),
      schedule["Simulation_Record_ID"].nunique(), len(schedule),
      "Unique call identity is a structural check.")
check(checks, "Observed transition file contains 271 rows",
      len(trans) == 271, len(trans), 271,
      "Candidate universe is the observed distinct-port sequence transition file.")
check(checks, "Transition call IDs are unique",
      trans["Simulation_Record_ID"].nunique() == len(trans),
      trans["Simulation_Record_ID"].nunique(), len(trans),
      "Each transition row should map to one current schedule call.")
check(checks, "All transition rows have previous and next port codes",
      trans[["Previous_Port", "Next_Port"]].notna().all(axis=1).all(),
      int(trans[["Previous_Port", "Next_Port"]].notna().all(axis=1).sum()),
      len(trans), "Missing endpoint identifiers would make pair classification incomplete.")
check(checks, "All transition elapsed intervals are positive and finite",
      trans["Elapsed_Hours_Between_Calls"].notna().all()
      and (trans["Elapsed_Hours_Between_Calls"] > 0).all(),
      int((trans["Elapsed_Hours_Between_Calls"].notna()
           & (trans["Elapsed_Hours_Between_Calls"] > 0)).sum()),
      len(trans), "Positive elapsed intervals are data checks, not sailing-time validation.")

# Link current transition call to baseline schedule record.
schedule_ids = set(schedule["Simulation_Record_ID"].dropna())
transition_ids = set(trans["Simulation_Record_ID"].dropna())
matched_ids = transition_ids.intersection(schedule_ids)
check(checks, "Every transition current-call ID exists in the 604-call schedule",
      len(matched_ids) == len(trans), len(matched_ids), len(trans),
      "This confirms record linkage only; not physical voyage semantics.")

# ----------------------------
# 2. Edge-level evidence and approvals
# ----------------------------
for c in ["Previous_Port", "Next_Port"]:
    if c not in edge.columns:
        raise ValueError(f"Script68 edge register missing {c}")
edge["Previous_Port"] = norm(edge["Previous_Port"])
edge["Next_Port"] = norm(edge["Next_Port"])
edge_key = ["Previous_Port", "Next_Port"]
if edge.duplicated(edge_key).any():
    raise ValueError("Script68 edge register contains duplicate directed edge keys.")

edge_approval_col = "Approved_For_Hypothetical_Exposure"
if edge_approval_col not in edge.columns:
    raise ValueError(f"Script68 edge register missing {edge_approval_col}")

edge["Script68_Edge_Approved"] = (
    edge[edge_approval_col].fillna(False).astype(str).str.lower()
    .isin(["true", "1", "yes"])
)

edge_summary = (
    trans.groupby(edge_key, dropna=False)
    .agg(
        Transition_Record_Count=("Simulation_Record_ID", "size"),
        Distinct_Vessel_Count=("IMO_Normalised", "nunique"),
        Mean_Observed_Elapsed_Hours=("Elapsed_Hours_Between_Calls", "mean"),
        Median_Observed_Elapsed_Hours=("Elapsed_Hours_Between_Calls", "median"),
        Min_Observed_Elapsed_Hours=("Elapsed_Hours_Between_Calls", "min"),
        Max_Observed_Elapsed_Hours=("Elapsed_Hours_Between_Calls", "max"),
    ).reset_index()
)
edge_summary = edge_summary.merge(
    edge[edge_key + [
        "Script68_Edge_Approved", "Researcher_Edge_Decision",
        "Exposure_Review_Status_67", "Actual_Hormuz_Exposure_Established_67",
        "Geographic_Route_Validated_67",
        "Hypothetical_Disruption_Exposure_Approved_67"
    ]].drop_duplicates(edge_key),
    on=edge_key, how="left", validate="one_to_one"
)
edge_summary["Script68_Edge_Register_Match"] = edge_summary[
    "Script68_Edge_Approved"
].notna()
edge_summary["Actual_Hormuz_Exposure_Established_67"] = (
    edge_summary["Actual_Hormuz_Exposure_Established_67"]
    .fillna(False).astype(str).str.lower().isin(["true", "1", "yes"])
)
edge_summary["Geographic_Route_Validated_67"] = (
    edge_summary["Geographic_Route_Validated_67"]
    .fillna(False).astype(str).str.lower().isin(["true", "1", "yes"])
)
edge_summary["Hypothetical_Disruption_Exposure_Approved_67"] = (
    edge_summary["Hypothetical_Disruption_Exposure_Approved_67"]
    .fillna(False).astype(str).str.lower().isin(["true", "1", "yes"])
)
edge_summary["Exposure_Classification"] = (
    "OBSERVED_SCHEDULE_LINK_ONLY_NOT_VALIDATED_ROUTE"
)
edge_summary["Candidate_Use"] = (
    "ELIGIBLE_FOR_HYPOTHETICAL_RANDOM_SELECTION_AUDIT_ONLY"
)
edge_summary["Execution_Authorized"] = False

# ----------------------------
# 3. Port context — descriptive only
# ----------------------------
if "UNLOCODE_Normalised" not in port.columns:
    raise ValueError("Script68 port register missing UNLOCODE_Normalised")
port["UNLOCODE_Normalised"] = norm(port["UNLOCODE_Normalised"])
port_approval_col = "Approved_For_Hypothetical_Port_Disruption"
if port_approval_col not in port.columns:
    raise ValueError(f"Script68 port register missing {port_approval_col}")
port["Script68_Port_Approved"] = (
    port[port_approval_col].fillna(False).astype(str).str.lower()
    .isin(["true", "1", "yes"])
)
port_context = port[[
    "UNLOCODE_Normalised", "observed_port_name",
    "observed_call_count", "observed_vessel_count",
    "Script68_Port_Approved", "Port_Exposure_Review_Status_67",
    "Actual_Hormuz_Exposure_Established_67"
]].copy()
port_context["Interpretation"] = (
    "Descriptive port-call context only; not route or disruption exposure evidence"
)

# ----------------------------
# 4. Deterministic nested selection
# ----------------------------
if len(protocol) != 1:
    raise ValueError("Expected exactly one Script88 primary protocol row.")
seed = int(protocol.iloc[0]["Selection_Seed_Proposed"])
shares = sorted(pd.to_numeric(factor["Affected_Transition_Share"]).unique())
expected_universe = int(pd.to_numeric(
    factor["Transition_Universe_Count"]
).dropna().iloc[0])

if expected_universe != len(trans):
    raise ValueError(
        f"Script88 universe ({expected_universe}) does not match transition rows ({len(trans)})."
    )

# Stable sort before seeded permutation ensures reproducibility across runs.
selection_base = trans[[
    "Simulation_Record_ID", "IMO_Normalised", "Previous_Port", "Next_Port",
    "Previous_Departure_UTC", "Actual_Arrival_UTC",
    "Elapsed_Hours_Between_Calls"
]].copy()
selection_base = selection_base.sort_values(
    ["Simulation_Record_ID", "IMO_Normalised", "Previous_Port", "Next_Port"],
    kind="mergesort"
).reset_index(drop=True)

rng = np.random.default_rng(seed)
permutation = rng.permutation(len(selection_base))
selection_base["Selection_Rank"] = np.empty(len(selection_base), dtype=int)
selection_base.loc[permutation, "Selection_Rank"] = np.arange(1, len(selection_base) + 1)
selection_base["Selection_Seed"] = seed
selection_base["Selection_Method"] = (
    "Seeded random permutation over observed transition records; nested prefixes"
)
selection_base["Selection_Unit"] = (
    "Observed current-call transition record; not unique physical route"
)
selection_base["Geographic_Exposure_Claim"] = "NONE"
selection_base["Actual_Hormuz_Transit_Claim"] = False
selection_base["Execution_Authorized"] = False
selection_base["Exposure_Approved"] = False

selection_rows = []
scenario_counts = []
for share in shares:
    n_select = int(np.floor(expected_universe * float(share) + 0.5))
    selected = selection_base["Selection_Rank"] <= n_select
    scenario_id = f"S89-S{int(round(float(share)*100)):03d}"
    temp = selection_base.copy()
    temp["Scope_Share"] = float(share)
    temp["Selected_Transition_Count"] = n_select
    temp["Scope_Scenario_ID"] = scenario_id
    temp["Selected_For_Hypothetical_Sensitivity"] = selected
    temp["Selection_Status"] = "CANDIDATE_ONLY_NOT_APPROVED"
    selection_rows.append(temp)
    scenario_counts.append({
        "Scope_Scenario_ID": scenario_id,
        "Affected_Transition_Share": float(share),
        "Transition_Universe_Count": expected_universe,
        "Selected_Transition_Count": n_select,
        "Unselected_Transition_Count": expected_universe - n_select,
        "Selection_Seed": seed,
        "Selection_Method": "Seeded random permutation; nested prefixes",
        "Selection_Is_Nested": True,
        "Exposure_Approval": False,
        "Execution_Authorized": False,
        "Interpretation": (
            "Mathematical coverage level for a general hypothetical elapsed-time shock; "
            "not measured Hormuz exposure probability"
        )
    })

selection_register = pd.concat(selection_rows, ignore_index=True)
scenario_summary = pd.DataFrame(scenario_counts)

# Confirm nesting and deterministic selection properties.
ranked = selection_base.sort_values("Selection_Rank")
nested_ok = True
for i in range(1, len(shares)):
    n_prev = int(np.floor(expected_universe * shares[i-1] + 0.5))
    n_curr = int(np.floor(expected_universe * shares[i] + 0.5))
    if n_curr < n_prev:
        nested_ok = False
    prev_ids = set(ranked.head(n_prev)["Simulation_Record_ID"])
    curr_ids = set(ranked.head(n_curr)["Simulation_Record_ID"])
    if not prev_ids.issubset(curr_ids):
        nested_ok = False

check(checks, "All 53 observed directed port pairs match Script68 edge register",
      len(edge_summary) == 53 and edge_summary["Script68_Edge_Register_Match"].all(),
      int(edge_summary["Script68_Edge_Register_Match"].sum()), 53,
      "Pair-level reconciliation does not establish route validity or exposure.")
check(checks, "No Script68 edge exposure approval is present",
      not edge["Script68_Edge_Approved"].any(),
      int(edge["Script68_Edge_Approved"].sum()), 0,
      "No transition can inherit an exposure approval.")
check(checks, "No Script68 port disruption approval is present",
      not port["Script68_Port_Approved"].any(),
      int(port["Script68_Port_Approved"].sum()), 0,
      "Port disruption is outside the primary experiment.")
check(checks, "No Script68 experiment scope is approved",
      "Approved_To_Proceed" in scope.columns
      and truth_count(scope["Approved_To_Proceed"]) == 0,
      truth_count(scope["Approved_To_Proceed"]) if "Approved_To_Proceed" in scope else "MISSING",
      0, "The primary mechanism choice is not execution authorization.")
check(checks, "No observed edge establishes actual Hormuz exposure",
      not edge_summary["Actual_Hormuz_Exposure_Established_67"].any(),
      int(edge_summary["Actual_Hormuz_Exposure_Established_67"].sum()), 0,
      "AIS-confirmed Hormuz transit is not established.")
check(checks, "Nested candidate selections are internally consistent",
      nested_ok, nested_ok, True,
      "Nested random prefixes are reproducible mathematical selections only.")
check(checks, "All candidate selections remain unapproved and unauthorized",
      not selection_register["Exposure_Approved"].any()
      and not selection_register["Execution_Authorized"].any(),
      int(selection_register["Exposure_Approved"].sum()
          + selection_register["Execution_Authorized"].sum()), 0,
      "Script89 cannot grant researcher or supervisor approval.")

# ----------------------------
# 5. Output registers and report
# ----------------------------
checks_df = pd.DataFrame(checks)
outputs = {
    "89_transition_exposure_audit.csv": selection_base.merge(
        edge_summary[edge_key + [
            "Transition_Record_Count", "Distinct_Vessel_Count",
            "Script68_Edge_Register_Match", "Script68_Edge_Approved",
            "Exposure_Review_Status_67", "Exposure_Classification",
            "Actual_Hormuz_Exposure_Established_67",
            "Geographic_Route_Validated_67",
            "Hypothetical_Disruption_Exposure_Approved_67"
        ]], on=edge_key, how="left", validate="many_to_one"
    ),
    "89_edge_evidence_summary.csv": edge_summary,
    "89_port_context_register.csv": port_context,
    "89_transition_selection_register.csv": selection_register,
    "89_scenario_scope_summary.csv": scenario_summary,
    "89_readiness_checks.csv": checks_df,
}
for filename, df in outputs.items():
    df.to_csv(TABLES / filename, index=False)

passed = int(checks_df["Passed"].sum())
failed = len(checks_df) - passed
report = f"""SCRIPT 89 — TRANSITION EXPOSURE AND SCENARIO SELECTION AUDIT
{'='*74}

RESEARCH SCOPE
Primary study: general hypothetical inter-port elapsed-time shock experiment.
Geopolitical motivation: potential disruption associated with the Strait of Hormuz.
No claim is made that selected transitions are actual Hormuz-exposed routes or vessels.

SOURCE INVENTORY
Conservative historical calls: {len(schedule)}
Observed distinct-port sequence transition records: {len(trans)}
Distinct directed port pairs: {len(edge_summary)}
Script68 directed edge register rows: {len(edge)}
Script68 port register rows: {len(port)}

SELECTION DESIGN
Seed: {seed}
Selection unit: observed current-call transition record.
Method: seeded random permutation with nested prefixes.
{scenario_summary.to_string(index=False)}

INTERPRETATION
The 271 records are observed consecutive distinct-port schedule links.
They are not validated physical sailing routes, AIS-confirmed Hormuz transits,
or approved geographic exposure units. Scope shares are mathematical coverage
levels for hypothetical sensitivity analysis, not exposure probabilities.

APPROVAL STATUS
Script68 edge exposure approvals: {int(edge_summary['Script68_Edge_Approved'].sum())}
Script68 port disruption approvals: {int(port['Script68_Port_Approved'].sum())}
Actual Hormuz-exposed directed pairs established: {int(edge_summary['Actual_Hormuz_Exposure_Established_67'].sum())}
Candidate transition selections approved: 0
Execution authorized: NO
Source inputs modified: NO
Simulation executed: NO

READINESS CHECKS
{passed}/{len(checks_df)} passed; {failed} failed.

OUTPUTS
{chr(10).join('- outputs/tables/' + name for name in outputs)}
- outputs/reports/89_transition_exposure_and_selection_audit_report.txt

DECISION
Script89 is an audit and candidate-selection register only. It does not approve
the proposed shock magnitudes, selected transition records, recovery policies,
or simulation execution. Researcher and supervisor review remain necessary.
"""
(REPORTS / "89_transition_exposure_and_selection_audit_report.txt").write_text(
    report, encoding="utf-8"
)
print(report)
if failed:
    print("WARNING: One or more checks failed. Do not proceed to simulation.")
    sys.exit(2)
print("Script 89 completed: audit/register generation only; no simulation executed.")
