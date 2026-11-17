from pathlib import Path
import sys
import pandas as pd

# ============================================================
# SCRIPT 90 — EXPERIMENTAL FACTOR AND POLICY DECISION REGISTER
# Corrected to match the actual Script88/89 CSV schemas.
# Decision-register generation only. No simulation is executed.
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"
TABLES.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

FILES = {
    "protocol": TABLES / "88_protocol_register.csv",
    "factors": TABLES / "88_scenario_factor_register.csv",
    "scenario_policy": TABLES / "88_scenario_policy_matrix.csv",
    "metrics": TABLES / "88_response_metric_register.csv",
    "replication": TABLES / "88_replication_decision_register.csv",
    "limitations": TABLES / "88_limitation_register.csv",
    "scope": TABLES / "89_scenario_scope_summary.csv",
    "selection": TABLES / "89_transition_selection_register.csv",
    "edges": TABLES / "89_edge_evidence_summary.csv",
}
missing = [str(p) for p in FILES.values() if not p.exists()]
if missing:
    print("ERROR — Missing required audited upstream files:")
    print("\n".join(missing))
    sys.exit(1)

D = {k: pd.read_csv(v, low_memory=False) for k, v in FILES.items()}

def require(df, cols, label):
    absent = [c for c in cols if c not in df.columns]
    if absent:
        raise ValueError(f"{label} missing columns: {absent}")

def add_decisions(df, kind):
    x = df.copy()
    x["Decision_Type"] = kind
    x["Researcher_Decision"] = "PENDING"
    x["Researcher_Selected_Value"] = ""
    x["Researcher_Justification"] = ""
    x["Supervisor_Review_Status"] = "PENDING"
    x["Supervisor_Comments"] = ""
    x["Approval_Granted"] = False
    x["Approval_Date"] = ""
    x["Execution_Authorized"] = False
    return x

checks = []
def ck(name, passed, observed, expected, note):
    checks.append({"Check": name, "Passed": bool(passed),
                   "Observed": str(observed), "Expected": str(expected),
                   "Interpretation": note})

protocol = D["protocol"]
factors = D["factors"]
combos = D["scenario_policy"]
metrics = D["metrics"]
replication = D["replication"]
limitations = D["limitations"]
scope = D["scope"]
selection = D["selection"]
edges = D["edges"]

require(protocol, ["Primary_Mechanism", "Execution_Authorized",
                   "Edge_Exposure_Approved", "Numerical_Levels_Approved",
                   "Recovery_Policies_Approved", "Supervisor_Review_Status"],
        "Script88 protocol")
require(factors, ["Scenario_ID", "Mechanism", "Shock_Magnitude_Hours",
                   "Affected_Transition_Share", "Transition_Universe_Count",
                   "Selection_Seed_Proposed", "Parameter_Status",
                   "Exposure_Status", "Execution_Authorized"],
        "Script88 scenario factor register")
require(combos, ["Scenario_ID", "Recovery_Policy_ID", "Recovery_Policy",
                 "Experiment_Combination_ID", "Protocol_Status"],
        "Script88 scenario-policy matrix")
require(metrics, ["Metric_ID", "Metric", "Aggregation_Level", "Unit",
                  "Priority", "Definition_or_Caveat"], "Script88 metrics")
require(replication, ["Option_ID", "Option", "Definition", "Status",
                      "Required_Decision", "Approved"], "Script88 replication")
require(limitations, ["Limitation_ID", "Topic", "Required_Qualification"],
        "Script88 limitations")
require(scope, ["Scope_Scenario_ID", "Affected_Transition_Share",
                "Transition_Universe_Count", "Selected_Transition_Count",
                "Unselected_Transition_Count", "Selection_Seed",
                "Selection_Is_Nested", "Exposure_Approval",
                "Execution_Authorized"], "Script89 scope summary")
require(selection, ["Simulation_Record_ID", "Selection_Rank", "Scope_Share",
                    "Scope_Scenario_ID", "Selected_For_Hypothetical_Sensitivity",
                    "Exposure_Approved", "Execution_Authorized"],
        "Script89 selection register")
require(edges, ["Previous_Port", "Next_Port", "Script68_Edge_Approved",
                "Actual_Hormuz_Exposure_Established_67",
                "Geographic_Route_Validated_67"], "Script89 edge summary")

if len(protocol) != 1:
    raise ValueError("Expected exactly one primary protocol row.")
mechanism = str(protocol.iloc[0]["Primary_Mechanism"])
if mechanism != "TRANSIT_ELAPSED_TIME_SHOCK":
    raise ValueError(f"Unexpected primary mechanism: {mechanism}")

# 1. Factor decision register: preserve all 16 scenario-factor rows.
factor_register = add_decisions(factors, "SCENARIO_FACTOR_LEVEL")
factor_register["Factor_Approval_Status"] = "NOT_APPROVED"
factor_register["Evidence_Status"] = "PROVISIONAL_HYPOTHETICAL_DESIGN"
factor_register["Interpretation_Limit"] = (
    "Additional observed inter-port elapsed time; not pure sailing time, "
    "not empirically calibrated, and not an observed Hormuz disruption."
)
factor_register["Factor_Group"] = "ELAPSED_TIME_SHOCK_AND_TRANSITION_SCOPE"

# 2. Recovery policy register: derive exact five policies from actual matrix.
policy_register = combos[
    ["Recovery_Policy_ID", "Recovery_Policy", "Policy_Type",
     "Fixed_Recovery_Cap_Hours", "Proportional_Recovery_Rate",
     "Maximum_Recovery_Per_Link_Hours", "Recovery_Interpretation"]
].drop_duplicates().sort_values("Recovery_Policy_ID").reset_index(drop=True)
if len(policy_register) != 5:
    raise ValueError(f"Expected five distinct recovery policies; found {len(policy_register)}")
policy_register = add_decisions(policy_register, "RECOVERY_POLICY")
policy_register["Policy_Approval_Status"] = "NOT_APPROVED"
policy_register["Operational_Feasibility_Established"] = False
policy_register["Schedule_Slack_Interpretation_Approved"] = False
policy_register["Policy_Interpretation_Limit"] = (
    "Hypothetical model rule; not a measured operational capability."
)

# 3. Scenario-policy matrix: preserve all 80 combinations.
combo_register = add_decisions(combos, "SCENARIO_POLICY_COMBINATION")
combo_register["Combination_Approval_Status"] = "NOT_APPROVED"
combo_register["Operational_Capability_Claim"] = False

# 4. Response metrics: preserve all nine definitions.
metric_register = add_decisions(metrics, "RESPONSE_METRIC")
metric_register["Metric_Definition_Approval"] = "PENDING"
metric_register["Censoring_Rule_Approval"] = "PENDING"
metric_register["Real_World_Impact_Claim"] = False

# 5. Scope decision register: preserve the four Script89 scope levels.
scope_register = add_decisions(scope, "AFFECTED_TRANSITION_SCOPE")
scope_register["Scope_Approval_Status"] = "NOT_APPROVED"
scope_register["Geographic_Exposure_Evidence"] = "NOT_ESTABLISHED"
scope_register["Scope_Interpretation"] = (
    "Mathematical coverage share over observed schedule transition records; "
    "not share of Hormuz traffic, vessels, or physical routes."
)

# 6. Replication decision register.
replication_register = add_decisions(replication, "REPLICATION_DESIGN")
replication_register["Replication_Design_Approval"] = "PENDING"
replication_register["Current_Interpretation"] = (
    "Deterministic first-stage reproducibility proposed; stochastic replication "
    "count not selected."
)

# 7. Limitations acknowledgement.
limitation_register = limitations.copy()
limitation_register["Researcher_Acknowledgement"] = "PENDING"
limitation_register["Supervisor_Acknowledgement"] = "PENDING"
limitation_register["Limitation_Waiver_Allowed"] = False

# 8. Explicit approval gates.
gate_register = pd.DataFrame([
    ["G01", "Primary mechanism", mechanism, "RESEARCHER_CONFIRMED",
     "Mechanism choice only; not exposure or execution approval."],
    ["G02", "Shock magnitudes", "6, 12, 24, 48 hours", "PENDING",
     "Provisional hypothetical increments."],
    ["G03", "Affected transition shares", "10%, 25%, 50%, 100%", "PENDING",
     "Mathematical coverage levels over 271 observed transition records."],
    ["G04", "Transition selection", "Seed 8801; nested random prefixes", "PENDING",
     "Candidate selection only; no geographic exposure approval."],
    ["G05", "Recovery policies", "Five Script76 policies", "PENDING",
     "Hypothetical rules; operational feasibility not established."],
    ["G06", "Response metrics", "Nine Script88 metrics", "PENDING",
     "Definitions and observation-window censoring require review."],
    ["G07", "Replication", "Deterministic first stage", "PENDING",
     "No stochastic replication count selected."],
    ["G08", "Supervisor review", "Required", "PENDING",
     "Supervisor review remains outstanding."],
    ["G09", "Simulation execution", "Not authorized", "BLOCKED",
     "Execution remains blocked pending explicit approvals."],
], columns=["Gate_ID", "Decision_Area", "Current_Proposal",
            "Current_Status", "Decision_Note"])
gate_register = add_decisions(gate_register, "APPROVAL_GATE")
# Preserve the already-confirmed researcher choice for G01.
# This is a mechanism selection only, not approval of factors or execution.
g01 = gate_register["Gate_ID"] == "G01"
gate_register.loc[g01, "Researcher_Decision"] = "CONFIRMED"
gate_register.loc[g01, "Researcher_Selected_Value"] = mechanism
gate_register.loc[g01, "Researcher_Justification"] = (
    "Researcher confirmed TRANSIT_ELAPSED_TIME_SHOCK as the sole primary "
    "mechanism; this does not approve shock magnitudes, transition exposure, "
    "recovery policies, or simulation execution."
)

# 9. Checks and reconciliations.
unique_scenarios = factors["Scenario_ID"].nunique()
unique_combo_ids = combos["Experiment_Combination_ID"].nunique()
unique_policies = policy_register["Recovery_Policy_ID"].nunique()
unique_metrics = metrics["Metric_ID"].nunique()
unique_scope = scope["Scope_Scenario_ID"].nunique()
transition_count = selection["Simulation_Record_ID"].nunique()
rank_count = selection["Selection_Rank"].nunique()
all_false = lambda s: not s.fillna(False).astype(str).str.lower().isin(
    ["true", "1", "yes"]).any()

ck("Primary mechanism is the agreed mechanism",
   mechanism == "TRANSIT_ELAPSED_TIME_SHOCK", mechanism,
   "TRANSIT_ELAPSED_TIME_SHOCK", "Researcher choice does not authorize execution.")
ck("Sixteen scenario factor rows retained",
   len(factors) == 16 and unique_scenarios == 16,
   f"{len(factors)} rows/{unique_scenarios} IDs", "16 rows/16 IDs",
   "Script88 scenario factor register preserved.")
ck("Eighty unique scenario-policy combinations retained",
   len(combos) == 80 and unique_combo_ids == 80,
   f"{len(combos)} rows/{unique_combo_ids} IDs", "80 rows/80 IDs",
   "All proposed combinations preserved.")
ck("Five distinct recovery policies retained",
   unique_policies == 5, unique_policies, 5,
   "Policy identities and parameter values sourced from Script88.")
ck("Nine response metrics retained",
   len(metrics) == 9 and unique_metrics == 9,
   f"{len(metrics)} rows/{unique_metrics} IDs", "9 rows/9 IDs",
   "Metric definitions preserved exactly.")
ck("Four scope levels retained",
   len(scope) == 4 and unique_scope == 4,
   f"{len(scope)} rows/{unique_scope} IDs", "4 rows/4 IDs",
   "Scope values sourced from Script89.")
ck("Selection register contains 271 unique transition records",
   transition_count == 271, transition_count, 271,
   "Records repeat across four scope levels.")
ck("Selection rank universe has 271 unique ranks",
   rank_count == 271, rank_count, 271,
   "Selection ranks are shared across nested scope levels.")
ck("All 53 directed edges remain unapproved",
   len(edges) == 53 and all_false(edges["Script68_Edge_Approved"]),
   f"{len(edges)} rows; approved={int(edges['Script68_Edge_Approved'].sum())}",
   "53 rows; 0 approved", "No edge exposure approval inferred.")
ck("No actual Hormuz exposure is established",
   all_false(edges["Actual_Hormuz_Exposure_Established_67"]),
   int(edges["Actual_Hormuz_Exposure_Established_67"].sum()), 0,
   "No AIS-confirmed Hormuz exposure claim.")
ck("No geographic route is marked validated",
   all_false(edges["Geographic_Route_Validated_67"]),
   int(edges["Geographic_Route_Validated_67"].sum()), 0,
   "Observed schedule links are not validated physical routes.")
ck("All four scope levels remain unapproved",
   all_false(scope["Exposure_Approval"]),
   int(scope["Exposure_Approval"].sum()), 0,
   "Scope shares remain candidate sensitivity settings.")
ck("No Script90 factor approval granted",
   not factor_register["Approval_Granted"].any(),
   int(factor_register["Approval_Granted"].sum()), 0,
   "Researcher decision fields start pending.")
ck("No Script90 recovery policy approval granted",
   not policy_register["Approval_Granted"].any(),
   int(policy_register["Approval_Granted"].sum()), 0,
   "Policies remain hypothetical options.")
ck("G01 researcher confirmation is carried into decision fields",
   gate_register.loc[gate_register["Gate_ID"] == "G01",
                     "Researcher_Decision"].iloc[0] == "CONFIRMED"
   and gate_register.loc[gate_register["Gate_ID"] == "G01",
                         "Researcher_Selected_Value"].iloc[0] == mechanism,
   gate_register.loc[gate_register["Gate_ID"] == "G01",
                     "Researcher_Decision"].iloc[0],
   "CONFIRMED with selected mechanism",
   "Mechanism choice is recorded without granting execution approval.")
ck("G01 confirmation does not grant approval or execution",
   not bool(gate_register.loc[g01, "Approval_Granted"].iloc[0])
   and not bool(gate_register.loc[g01, "Execution_Authorized"].iloc[0]),
   f"Approval={bool(gate_register.loc[g01, 'Approval_Granted'].iloc[0])}; "
   f"Execution={bool(gate_register.loc[g01, 'Execution_Authorized'].iloc[0])}",
   "Approval=False; Execution=False",
   "Researcher mechanism selection remains distinct from authorization.")
ck("Execution gate remains blocked",
   gate_register.loc[gate_register["Gate_ID"] == "G09",
                     "Current_Status"].iloc[0] == "BLOCKED",
   gate_register.loc[gate_register["Gate_ID"] == "G09",
                     "Current_Status"].iloc[0], "BLOCKED",
   "Script90 does not authorize simulation.")

checks_df = pd.DataFrame(checks)
outputs = {
    "90_factor_decision_register.csv": factor_register,
    "90_recovery_policy_decision_register.csv": policy_register,
    "90_scenario_policy_decision_matrix.csv": combo_register,
    "90_response_metric_decision_register.csv": metric_register,
    "90_scope_decision_register.csv": scope_register,
    "90_replication_decision_register.csv": replication_register,
    "90_limitation_acknowledgement_register.csv": limitation_register,
    "90_approval_gate_register.csv": gate_register,
    "90_readiness_checks.csv": checks_df,
}
for filename, frame in outputs.items():
    frame.to_csv(TABLES / filename, index=False)

passed = int(checks_df["Passed"].sum())
failed = len(checks_df) - passed
report = f"""SCRIPT 90 — EXPERIMENTAL FACTOR AND POLICY DECISION REGISTER
{'='*76}

PURPOSE
Consolidate audited Script88/89 design choices into researcher and supervisor
decision registers. This is not a simulation runner or approval mechanism.

RESEARCH SCOPE
Primary mechanism: {mechanism}
Study framing: general hypothetical inter-port elapsed-time shock experiment,
motivated by potential geopolitical disruption associated with the Strait of Hormuz.
No actual Hormuz route exposure, physical sailing route, or AIS-confirmed transit
is established by this design.

REGISTER INVENTORY
Factor scenario rows: {len(factor_register)}
Distinct recovery policies: {len(policy_register)}
Scenario-policy combinations: {len(combo_register)}
Response metrics: {len(metric_register)}
Affected-transition scope levels: {len(scope_register)}
Transition selection rows: {len(selection)}
Replication options: {len(replication_register)}
Limitations: {len(limitation_register)}
Approval gates: {len(gate_register)}

APPROVAL STATUS
Factor levels approved: 0
Recovery policies approved: 0
Scope levels approved: 0
Supervisor review: PENDING
Simulation execution authorized: NO
Source inputs modified: NO
Simulation executed: NO

READINESS CHECKS
{passed}/{len(checks_df)} passed; {failed} failed.

OUTPUTS
{chr(10).join('- outputs/tables/' + n for n in outputs)}
- outputs/reports/90_experimental_factor_and_policy_decision_register_report.txt

DECISION
All numerical levels, transition scope settings, recovery policies, response
metric definitions, replication choices and execution gates remain subject to
explicit researcher and supervisor review. No approval is granted by Script90.
"""
(REPORTS / "90_experimental_factor_and_policy_decision_register_report.txt").write_text(
    report, encoding="utf-8"
)
print(report)
if failed:
    print("WARNING: One or more checks failed. Do not proceed.")
    sys.exit(2)
print("Script 90 completed: decision-register generation only; no simulation executed.")
