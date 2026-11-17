from pathlib import Path
import sys
import math
import pandas as pd
import numpy as np

# ============================================================
# SCRIPT 91 — EXPERIMENTAL DESIGN SENSITIVITY AND
#              STATISTICAL ADEQUACY REVIEW
#
# Purpose:
#   Challenge the proposed design before simulation execution.
#   Review factor ranges, scope levels, recovery-policy contrasts,
#   response metrics, replication logic, and experiment coverage.
#
# This script is diagnostic only:
#   - no simulation is run;
#   - no factor or policy is approved;
#   - no statistical power claim is made;
#   - no source input is modified.
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"
TABLES.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

FILES = {
    "protocol": TABLES / "88_protocol_register.csv",
    "factors": TABLES / "90_factor_decision_register.csv",
    "policies": TABLES / "90_recovery_policy_decision_register.csv",
    "combinations": TABLES / "90_scenario_policy_decision_matrix.csv",
    "metrics": TABLES / "90_response_metric_decision_register.csv",
    "replication": TABLES / "90_replication_decision_register.csv",
    "scope": TABLES / "90_scope_decision_register.csv",
    "gates": TABLES / "90_approval_gate_register.csv",
    "selection": TABLES / "89_transition_selection_register.csv",
    "edge": TABLES / "89_edge_evidence_summary.csv",
}
missing = [str(p) for p in FILES.values() if not p.exists()]
if missing:
    print("ERROR — Required audited upstream files are missing:")
    print("\n".join(missing))
    sys.exit(1)

D = {k: pd.read_csv(v, low_memory=False) for k, v in FILES.items()}

def require(df, cols, label):
    absent = [c for c in cols if c not in df.columns]
    if absent:
        raise ValueError(f"{label} missing required columns: {absent}")

def as_bool(s):
    return s.fillna(False).astype(str).str.strip().str.lower().isin(
        ["true", "1", "yes"]
    )

checks = []
def ck(name, passed, observed, expected, note):
    checks.append({
        "Check": name, "Passed": bool(passed),
        "Observed": str(observed), "Expected": str(expected),
        "Interpretation": note
    })

protocol = D["protocol"]
factors = D["factors"]
policies = D["policies"]
combos = D["combinations"]
metrics = D["metrics"]
replication = D["replication"]
scope = D["scope"]
gates = D["gates"]
selection = D["selection"]
edges = D["edge"]

require(protocol, ["Primary_Mechanism"], "Protocol")
require(factors, ["Scenario_ID", "Mechanism", "Shock_Magnitude_Hours",
                  "Affected_Transition_Share", "Transition_Universe_Count",
                  "Parameter_Status", "Exposure_Status",
                  "Execution_Authorized"], "Factor register")
require(policies, ["Recovery_Policy_ID", "Recovery_Policy", "Policy_Type",
                   "Fixed_Recovery_Cap_Hours", "Proportional_Recovery_Rate",
                   "Maximum_Recovery_Per_Link_Hours",
                   "Approval_Granted"], "Policy register")
require(combos, ["Scenario_ID", "Recovery_Policy_ID",
                 "Experiment_Combination_ID"], "Combination matrix")
require(metrics, ["Metric_ID", "Metric", "Aggregation_Level", "Unit",
                  "Priority", "Definition_or_Caveat"], "Metric register")
require(replication, ["Option_ID", "Option", "Definition", "Status",
                      "Required_Decision", "Approved"], "Replication register")
require(scope, ["Scope_Scenario_ID", "Affected_Transition_Share",
                "Transition_Universe_Count", "Selected_Transition_Count"],
        "Scope register")
require(gates, ["Gate_ID", "Current_Status", "Researcher_Decision",
                "Approval_Granted", "Execution_Authorized"], "Approval gates")
require(selection, ["Simulation_Record_ID", "Selection_Rank", "Scope_Share",
                    "Scope_Scenario_ID",
                    "Selected_For_Hypothetical_Sensitivity"],
        "Transition selection")
require(edges, ["Previous_Port", "Next_Port",
                "Actual_Hormuz_Exposure_Established_67",
                "Geographic_Route_Validated_67"], "Edge evidence")

if len(protocol) != 1:
    raise ValueError("Expected exactly one primary protocol row.")
primary_mechanism = str(protocol.iloc[0]["Primary_Mechanism"])
if primary_mechanism != "TRANSIT_ELAPSED_TIME_SHOCK":
    raise ValueError(f"Unexpected mechanism: {primary_mechanism}")

# -----------------------------
# A. Factor-range diagnostics
# -----------------------------
shock = sorted(pd.to_numeric(
    factors["Shock_Magnitude_Hours"], errors="raise"
).dropna().unique().tolist())
shares = sorted(pd.to_numeric(
    factors["Affected_Transition_Share"], errors="raise"
).dropna().unique().tolist())
universe_values = pd.to_numeric(
    factors["Transition_Universe_Count"], errors="coerce"
).dropna().unique()
if len(universe_values) != 1:
    raise ValueError("Factor register has inconsistent transition universe counts.")
universe = int(universe_values[0])

factor_rows = []
for i, v in enumerate(shock):
    factor_rows.append({
        "Factor": "Additional observed inter-port elapsed-time shock",
        "Level": v, "Unit": "hours",
        "Relative_To_Minimum": v / min(shock),
        "Adjacent_Level_Ratio": "" if i == 0 else v / shock[i-1],
        "Diagnostic": (
            "Provisional hypothetical increment; not pure sailing time "
            "or empirically calibrated disruption duration"
        ),
        "Approval_Status": "NOT_APPROVED"
    })
for i, v in enumerate(shares):
    n = int(math.floor(universe * v + 0.5))
    ratio = "" if i == 0 else v / shares[i-1]
    factor_rows.append({
        "Factor": "Affected transition record share",
        "Level": v, "Unit": "proportion",
        "Relative_To_Minimum": v / min(shares),
        "Adjacent_Level_Ratio": ratio,
        "Diagnostic": (
            f"Mathematical coverage setting; selects {n} of {universe} "
            "observed transition records, not actual geographic exposure"
        ),
        "Approval_Status": "NOT_APPROVED"
    })
factor_diagnostics = pd.DataFrame(factor_rows)

shock_diagnostics = pd.DataFrame([{
    "Factor": "Elapsed-time shock",
    "Minimum_Hours": min(shock),
    "Maximum_Hours": max(shock),
    "Range_Hours": max(shock) - min(shock),
    "Maximum_To_Minimum_Ratio": max(shock) / min(shock),
    "Number_Of_Levels": len(shock),
    "Equal_Additive_Spacing": len(set(np.diff(shock))) <= 1,
    "Log_Spacing_Equal": (
        len(shock) <= 2 or np.allclose(np.diff(np.log(shock)),
                                      np.diff(np.log(shock))[0])
    ),
    "Scientific_Adequacy_Conclusion": (
        "NOT_ESTABLISHED — four ordered levels permit sensitivity comparisons, "
        "but no empirical calibration or operational validity is demonstrated"
    )
}])

# -----------------------------
# B. Scenario and scope coverage
# -----------------------------
scenario_counts = factors.groupby(
    ["Shock_Magnitude_Hours", "Affected_Transition_Share"],
    dropna=False
).size().reset_index(name="Rows_Per_Factor_Cell")
scope_diagnostics = scope[[
    "Scope_Scenario_ID", "Affected_Transition_Share",
    "Transition_Universe_Count", "Selected_Transition_Count"
]].copy()
scope_diagnostics["Recomputed_Selected_Count"] = scope_diagnostics.apply(
    lambda r: int(math.floor(
        float(r["Transition_Universe_Count"])
        * float(r["Affected_Transition_Share"]) + 0.5
    )), axis=1
)
scope_diagnostics["Count_Reconciles"] = (
    scope_diagnostics["Selected_Transition_Count"]
    == scope_diagnostics["Recomputed_Selected_Count"]
)
scope_diagnostics["Interpretation"] = (
    "Coverage fraction over observed transition records; not vessel, voyage, "
    "traffic, route, or Hormuz exposure fraction"
)

# -----------------------------
# C. Recovery policy contrasts
# -----------------------------
policy_diagnostics = policies[[
    "Recovery_Policy_ID", "Recovery_Policy", "Policy_Type",
    "Fixed_Recovery_Cap_Hours", "Proportional_Recovery_Rate",
    "Maximum_Recovery_Per_Link_Hours", "Recovery_Interpretation",
    "Approval_Granted"
]].copy()
for c in ["Fixed_Recovery_Cap_Hours", "Proportional_Recovery_Rate",
          "Maximum_Recovery_Per_Link_Hours"]:
    policy_diagnostics[c] = pd.to_numeric(
        policy_diagnostics[c], errors="coerce"
    )
policy_diagnostics["Policy_Parameter_Interpretation"] = (
    "Mathematical recovery rule; not observed operational capability"
)
policy_diagnostics["Operational_Feasibility_Established"] = False
policy_diagnostics["Comparability_Comment"] = (
    "Policies differ in rule form and/or cap; comparative outcomes are "
    "conditional on model implementation and do not establish real-world feasibility"
)

# Policy parameter dominance diagnostic: compare fixed cap / max cap where defined.
# Select the relevant cap by policy type. A proportional policy has
# Fixed_Recovery_Cap_Hours == 0 by design, so fillna() would incorrectly
# report zero instead of its Maximum_Recovery_Per_Link_Hours.
policy_type = policy_diagnostics["Policy_Type"].astype(str).str.upper()
policy_diagnostics["Maximum_Recovery_Cap_Available"] = np.select(
    [
        policy_type.eq("NONE"),
        policy_type.eq("FIXED"),
        policy_type.eq("PROPORTIONAL"),
    ],
    [
        0.0,
        policy_diagnostics["Fixed_Recovery_Cap_Hours"].fillna(0.0),
        policy_diagnostics["Maximum_Recovery_Per_Link_Hours"].fillna(0.0),
    ],
    default=np.nan
)
policy_diagnostics["Cap_Comparability_Note"] = (
    "Do not rank policies by cap alone: proportional rules depend on "
    "available delay and link-level constraints."
)

# -----------------------------
# D. Response metric review
# -----------------------------
metric_diagnostics = metrics[[
    "Metric_ID", "Metric", "Aggregation_Level", "Unit",
    "Priority", "Definition_or_Caveat"
]].copy()
metric_diagnostics["Review_Status"] = "REQUIRES_RESEARCHER_REVIEW"
metric_diagnostics["Potential_Overlap_Review"] = ""
metric_diagnostics["Censoring_Concern"] = ""
for idx, row in metric_diagnostics.iterrows():
    text = f"{row['Metric_ID']} {row['Metric']} {row['Definition_or_Caveat']}".lower()
    if any(term in text for term in ["maximum", "max", "accumulated"]):
        metric_diagnostics.loc[idx, "Potential_Overlap_Review"] = (
            "Check distinction between maximum call-level delay, final vessel "
            "departure delay, and maximum accumulated delay per vessel."
        )
    if any(term in text for term in ["unrecover", "end-window", "window", "censor"]):
        metric_diagnostics.loc[idx, "Censoring_Concern"] = (
            "Define end-of-observation-window treatment; incomplete future "
            "sequence may appear unrecovered because it is right-censored."
        )
metric_diagnostics["Real_World_Impact_Claim"] = False

# -----------------------------
# E. Replication adequacy review
# -----------------------------
replication_diagnostics = replication.copy()
replication_diagnostics["Statistical_Inference_Supported_By_Design"] = False
replication_diagnostics["Adequacy_Comment"] = (
    "Deterministic reproducibility supports repeatability of code and outputs, "
    "not sampling uncertainty or confidence intervals. Replication needs a "
    "defined stochastic source and target estimand."
)
replication_diagnostics["Power_Claim"] = "NOT_ASSESSED"
replication_diagnostics["Recommended_Trigger_For_Replications"] = (
    "Introduce a stochastic component or sample uncertainty target, define "
    "estimand and precision criterion, then determine replication count."
)

# -----------------------------
# F. Combination matrix coverage
# -----------------------------
if len(combos) != 80:
    raise ValueError(f"Expected 80 combinations; found {len(combos)}.")
policy_counts = combos.groupby("Scenario_ID")["Recovery_Policy_ID"].nunique()
combo_diagnostics = combos[[
    "Scenario_ID", "Recovery_Policy_ID", "Experiment_Combination_ID"
]].copy()
combo_diagnostics["Policies_Per_Scenario"] = combo_diagnostics[
    "Scenario_ID"
].map(policy_counts)
combo_diagnostics["Full_Five_Policy_Coverage"] = (
    combo_diagnostics["Policies_Per_Scenario"] == 5
)

# -----------------------------
# G. Scientific validity boundaries
# -----------------------------
boundary_rows = [
    ["B01", "Observed inter-port elapsed time", "Not pure sailing time",
     "Do not label the shock as sailing-time delay."],
    ["B02", "Observed port-call sequence", "Not a validated physical route",
     "Do not infer actual route access or Hormuz transit."],
    ["B03", "Transition share", "Not geographic exposure probability",
     "Describe as fraction of observed transition records selected."],
    ["B04", "Recovery cap", "Not established schedule slack",
     "Do not claim operational recoverability from observed intervals."],
    ["B05", "Recovery policy", "Not measured operational capability",
     "Describe as hypothetical model policy."],
    ["B06", "Deterministic execution", "Not statistical replication",
     "Do not report confidence intervals or sampling precision from one deterministic run."],
    ["B07", "Simulation output", "Not empirical validation",
     "Separate internal verification, calibration, and external validation."],
    ["B08", "End-of-window outcomes", "Potential right-censoring",
     "Define common observation horizon and treatment of unfinished vessel sequences."],
]
boundary_register = pd.DataFrame(boundary_rows, columns=[
    "Boundary_ID", "Model_Element", "Evidence_Limit", "Required_Reporting_Control"
])

# -----------------------------
# H. Readiness checks
# -----------------------------
ck("Four shock magnitudes are present",
   shock == [6.0, 12.0, 24.0, 48.0], shock, [6, 12, 24, 48],
   "Presence check only; does not establish calibration.")
ck("Four transition shares are present",
   shares == [0.1, 0.25, 0.5, 1.0], shares, [0.1, 0.25, 0.5, 1.0],
   "Coverage levels are not exposure probabilities.")
ck("Factorial scenario register contains 16 rows",
   len(factors) == 16, len(factors), 16,
   "Four magnitudes crossed with four shares.")
ck("Each magnitude-share cell appears once",
   len(scenario_counts) == 16 and (scenario_counts["Rows_Per_Factor_Cell"] == 1).all(),
   len(scenario_counts), 16, "Checks full 4x4 factor grid.")
ck("Four scope counts reconcile by rounding rule",
   scope_diagnostics["Count_Reconciles"].all(),
   int(scope_diagnostics["Count_Reconciles"].sum()), len(scope_diagnostics),
   "Checks selected counts against 271-record universe.")
ck("Five distinct recovery policies are present",
   policies["Recovery_Policy_ID"].nunique() == 5,
   policies["Recovery_Policy_ID"].nunique(), 5,
   "Policy set is preserved from Script88.")
expected_caps = {
    "R76-00-NONE": 0.0,
    "R76-01-FIXED-6H": 6.0,
    "R76-02-FIXED-12H": 12.0,
    "R76-03-PROP-25-CAP6": 6.0,
    "R76-04-PROP-50-CAP12": 12.0,
}
observed_caps = dict(zip(
    policy_diagnostics["Recovery_Policy_ID"],
    policy_diagnostics["Maximum_Recovery_Cap_Available"]
))
caps_reconcile = all(
    k in observed_caps and np.isclose(observed_caps[k], v)
    for k, v in expected_caps.items()
)
ck("Recovery-policy maximum caps use the correct rule-specific field",
   caps_reconcile, observed_caps, expected_caps,
   "Fixed policies use fixed cap; proportional policies use per-link maximum cap.")
ck("All 16 scenarios have five policies",
   (policy_counts == 5).all() and len(policy_counts) == 16,
   f"{int((policy_counts == 5).sum())}/16", "16/16",
   "Full scenario-policy coverage.")
ck("Eighty unique experiment combinations",
   combos["Experiment_Combination_ID"].nunique() == 80,
   combos["Experiment_Combination_ID"].nunique(), 80,
   "Combination IDs are unique.")
ck("Nine response metrics retained",
   len(metrics) == 9 and metrics["Metric_ID"].nunique() == 9,
   f"{len(metrics)} rows/{metrics['Metric_ID'].nunique()} IDs", "9/9",
   "Metric definitions are preserved.")
ck("Replication design does not claim statistical inference",
   not replication_diagnostics["Statistical_Inference_Supported_By_Design"].any(),
   "False for all options", "False for all options",
   "No power or precision claim is made.")
ck("No actual Hormuz exposure is established",
   not as_bool(edges["Actual_Hormuz_Exposure_Established_67"]).any(),
   int(as_bool(edges["Actual_Hormuz_Exposure_Established_67"]).sum()), 0,
   "No AIS-confirmed exposure evidence.")
ck("No physical routes are marked validated",
   not as_bool(edges["Geographic_Route_Validated_67"]).any(),
   int(as_bool(edges["Geographic_Route_Validated_67"]).sum()), 0,
   "Observed sequence links remain distinct from physical routes.")
ck("No approval or execution gate has been silently granted",
   not as_bool(gates["Approval_Granted"]).any()
   and not as_bool(gates["Execution_Authorized"]).any(),
   f"Approvals={int(as_bool(gates['Approval_Granted']).sum())}; "
   f"execution={int(as_bool(gates['Execution_Authorized']).sum())}",
   "0; 0", "This diagnostic script cannot approve the experiment.")

checks_df = pd.DataFrame(checks)

outputs = {
    "91_factor_range_diagnostics.csv": factor_diagnostics,
    "91_shock_range_summary.csv": shock_diagnostics,
    "91_scope_count_diagnostics.csv": scope_diagnostics,
    "91_recovery_policy_comparability.csv": policy_diagnostics,
    "91_response_metric_review.csv": metric_diagnostics,
    "91_replication_adequacy_review.csv": replication_diagnostics,
    "91_scenario_policy_coverage.csv": combo_diagnostics,
    "91_scientific_validity_boundaries.csv": boundary_register,
    "91_readiness_checks.csv": checks_df,
}
for name, df in outputs.items():
    df.to_csv(TABLES / name, index=False)

passed = int(checks_df["Passed"].sum())
failed = len(checks_df) - passed
report = f"""SCRIPT 91 — EXPERIMENTAL DESIGN SENSITIVITY AND STATISTICAL ADEQUACY REVIEW
{'='*82}

PURPOSE
Challenge the proposed design before execution. This is a diagnostic review,
not a simulation, approval, statistical power analysis, or empirical validation.

RESEARCH FRAMING
Primary mechanism: {primary_mechanism}
Study: general hypothetical inter-port elapsed-time shock experiment, motivated
by potential geopolitical disruption associated with the Strait of Hormuz.
Observed elapsed time is not pure sailing time. The transition shares are
mathematical coverage levels, not actual Hormuz exposure probabilities.

FACTOR RANGE
Shock magnitudes (hours): {shock}
Affected transition shares: {shares}
Transition universe: {universe}
Scenario grid rows: {len(factors)}
Shock maximum/minimum ratio: {max(shock)/min(shock):.3f}
No empirical calibration or operational validity is established.

RECOVERY POLICIES
Distinct policies: {policies['Recovery_Policy_ID'].nunique()}
Policy rules are hypothetical model rules. They are not measured operational
capabilities or evidence of available schedule slack.

SCENARIO COVERAGE
Scenario-policy combinations: {len(combos)}
Scenarios with all five policies: {int((policy_counts == 5).sum())}/16
Response metrics: {len(metrics)}

REPLICATION
Replication options: {len(replication)}
No statistical power, confidence interval, or precision claim is supported
by deterministic reproducibility alone. A replication count requires a defined
stochastic component/uncertainty target, estimand and precision criterion.

KEY METHODOLOGICAL FINDINGS
1. The 6/12/24/48-hour levels are ordered and span a 8-fold range, but are not
   empirically calibrated. They are sensitivity settings, not forecasts.
2. The 10/25/50/100% levels are coverage settings over 271 observed transition
   records. They do not represent actual route or vessel exposure probabilities.
3. Recovery policies differ by rule form and caps. Outcomes must be interpreted
   as conditional comparisons under the specified mathematical rules.
4. Metric definitions require attention to overlap between delay measures and
   right-censoring of unfinished sequences at the observation-window boundary.
5. Deterministic reproducibility is suitable for a deterministic first-stage
   model audit, but does not quantify stochastic uncertainty.
6. No actual Hormuz transit, validated physical route, pure sailing-time shock,
   port capacity or operational recovery feasibility is established.

READINESS CHECKS
{passed}/{len(checks_df)} passed; {failed} failed.

APPROVAL STATUS
No factors approved by Script91.
No policies approved by Script91.
No exposure approved by Script91.
Simulation execution authorized: NO.
Source inputs modified: NO.
Simulation executed: NO.

OUTPUTS
{chr(10).join('- outputs/tables/' + n for n in outputs)}

DECISION
Script91 provides a structured methodological challenge. It does not declare
the experiment scientifically adequate or authorize execution. Researcher and
supervisor decisions remain necessary, particularly on factor calibration,
metric estimands/censoring, recovery-policy interpretation, and whether the
deterministic first stage is sufficient for the intended research questions.
"""
(REPORTS / "91_experimental_design_sensitivity_and_adequacy_report.txt").write_text(
    report, encoding="utf-8"
)
print(report)
if failed:
    print("WARNING: One or more checks failed. Do not proceed.")
    sys.exit(2)
print("Script 91 completed: diagnostic review only; no simulation executed.")
