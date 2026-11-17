"""
SCRIPT 92 — RESPONSE METRIC DEFINITION, ESTIMAND AND CENSORING AUDIT

Reads (does not modify):
  outputs/tables/88_response_metric_register.csv
  outputs/tables/90_response_metric_decision_register.csv

Writes separate Script92 audit artifacts under outputs/tables and outputs/reports.
This is a diagnostic review only. It does not approve metrics or authorize simulation.
"""

from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"
TABLES.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

P88 = TABLES / "88_response_metric_register.csv"
P90 = TABLES / "90_response_metric_decision_register.csv"

if not P88.exists():
    raise FileNotFoundError(f"Required source file not found: {P88}")
if not P90.exists():
    raise FileNotFoundError(f"Required source file not found: {P90}")

m88 = pd.read_csv(P88)
m90 = pd.read_csv(P90)

required88 = [
    "Metric_ID", "Metric", "Aggregation_Level", "Unit", "Priority",
    "Definition_or_Caveat"
]
required90 = required88 + [
    "Decision_Type", "Researcher_Decision", "Researcher_Selected_Value",
    "Researcher_Justification", "Supervisor_Review_Status",
    "Supervisor_Comments", "Approval_Granted", "Approval_Date",
    "Execution_Authorized", "Metric_Definition_Approval",
    "Censoring_Rule_Approval", "Real_World_Impact_Claim"
]
missing88 = [c for c in required88 if c not in m88.columns]
missing90 = [c for c in required90 if c not in m90.columns]
if missing88 or missing90:
    raise ValueError(
        f"Unexpected source schema. Missing in Script88: {missing88}; "
        f"missing in Script90: {missing90}"
    )

# Preserve source terminology and compare Script90's base fields to Script88.
base_fields = required88
left = m88[base_fields].copy().fillna("")
right = m90[base_fields].copy().fillna("")
left["Metric_ID"] = left["Metric_ID"].astype(str)
right["Metric_ID"] = right["Metric_ID"].astype(str)
left = left.sort_values("Metric_ID").reset_index(drop=True)
right = right.sort_values("Metric_ID").reset_index(drop=True)

comparison = left.merge(
    right, on="Metric_ID", how="outer", suffixes=("_88", "_90"),
    indicator=True
)
for col in base_fields:
    if col == "Metric_ID":
        continue
    comparison[f"{col}_matches"] = (
        comparison[f"{col}_88"].fillna("").astype(str)
        == comparison[f"{col}_90"].fillna("").astype(str)
    )
match_cols = [c for c in comparison.columns if c.endswith("_matches")]
comparison["All_Base_Fields_Match"] = (
    comparison["_merge"].eq("both") & comparison[match_cols].all(axis=1)
)

# Metric-by-metric operationalization review. These are audit questions/proposals,
# not approved formulas or changes to the source registers.
review_rows = [
    ["M01", "Mean call arrival delay", "Call-level mean",
     "Define call-level arrival-delay variable and reference timestamp; state whether negative values are retained or truncated at zero.",
     "Specify the eligible-call denominator and how calls whose simulated arrival is not observed by the common horizon are handled.",
     "Do not silently treat missing arrivals as zero delay or drop them."],
    ["M02", "Mean call departure delay", "Call-level mean",
     "Define call-level departure-delay variable and reference timestamp; state whether negative values are retained or truncated at zero.",
     "Specify the eligible-call denominator and treatment of calls with no simulated departure by the common horizon.",
     "Keep distinct from M01; departure delay may include effects occurring after arrival."],
    ["M03A", "Maximum final vessel departure delay", "Vessel-level maximum across final represented calls",
     "For each vessel, identify its final represented call and define departure delay at that call relative to the chosen baseline/reference.",
     "A vessel whose final represented call is unfinished at the horizon is not automatically a completed observation.",
     "Report number of eligible vessels and censored vessels alongside the maximum."],
    ["M03B", "Maximum accumulated departure delay per vessel", "Vessel-level accumulated measure, then maximum",
     "Define whether accumulation is the sum of call-level departure delays, sum of incremental propagated delay, or another explicitly named quantity.",
     "Use a consistent set of observable calls per vessel; identify incomplete sequences.",
     "Do not assume this equals M03A; it can grow across calls and has a different interpretation."],
    ["M04", "Mean final vessel departure delay", "Mean across represented vessels",
     "Define one final-call departure-delay value per vessel and specify the reference schedule.",
     "State the denominator as eligible vessels, with censored/incomplete vessels separately counted.",
     "Avoid weighting vessels with more calls more heavily."],
    ["M05", "P90 call departure delay", "Call-level 90th percentile",
     "Specify quantile convention (for example, pandas linear interpolation), treatment of zero delays, and whether negative delays are retained.",
     "Use the same eligible-call and censoring rule as M02, or explain any difference.",
     "Report the number of eligible calls and the proportion of zero-delay calls."],
    ["M06", "Total recovery credit", "Call/vessel-level total",
     "Define recovery credit as the modelled reduction in delay attributable to the policy, with exact pairing to the no-recovery counterfactual.",
     "Only compare matched scenario, vessel and call records; explain missing or unfinished matched records.",
     "Keep labelled as modelled credit; do not describe it as observed operational recovery."],
    ["M07A", "Unrecovered call count", "Call count",
     "Choose a positive residual-delay threshold and comparison time point; count calls whose residual delay exceeds that threshold.",
     "Exclude or separately classify calls not yet observable at the common horizon; do not classify right-censored calls as recovered.",
     "Threshold and denominator remain researcher decisions."],
    ["M07B", "Unrecovered vessel count", "Vessel count",
     "Define vessel-level unrecovered status (for example, final represented-call residual delay above a chosen threshold); do not infer it from an unspecified call rule.",
     "Vessels whose final represented call is unfinished at the horizon need a separate censored category.",
     "Threshold, vessel aggregation rule and censoring rule remain researcher decisions."],
]

review = pd.DataFrame(review_rows, columns=[
    "Metric_ID", "Metric", "Aggregation_Level_As_Registered",
    "Definition_Required_Before_Execution",
    "Estimand_Denominator_And_Censoring_Requirement",
    "Interpretation_Guardrail"
])

# Audit the decision gates exactly as supplied.
decision = m90[[
    "Metric_ID", "Researcher_Decision", "Researcher_Selected_Value",
    "Supervisor_Review_Status", "Approval_Granted", "Approval_Date",
    "Execution_Authorized", "Metric_Definition_Approval",
    "Censoring_Rule_Approval", "Real_World_Impact_Claim"
]].copy()

for c in ["Researcher_Decision", "Supervisor_Review_Status",
          "Metric_Definition_Approval", "Censoring_Rule_Approval"]:
    decision[c] = decision[c].fillna("").astype(str).str.upper().str.strip()

# A compact inventory of unresolved design choices.
open_items = pd.DataFrame([
    ["D01", "Delay reference", "Define the baseline/reference timestamp used for arrival and departure delay.", "Researcher; supervisor review"],
    ["D02", "Negative/early values", "Decide whether early arrivals/departures remain negative or are truncated at zero.", "Researcher; supervisor review"],
    ["D03", "Call eligibility", "Define which calls enter each call-level denominator.", "Researcher; supervisor review"],
    ["D04", "Vessel eligibility", "Define eligible vessels and the meaning of final represented call.", "Researcher; supervisor review"],
    ["D05", "Accumulated delay", "Define exactly what is accumulated for M03B and whether it is a sum across calls.", "Researcher; supervisor review"],
    ["D06", "P90 convention", "Select and record the quantile algorithm and zero-delay reporting convention.", "Researcher; supervisor review"],
    ["D07", "Recovery credit", "Define matched no-recovery counterfactual, pairing keys and credit calculation.", "Researcher; supervisor review"],
    ["D08", "Unrecovered threshold", "Select threshold, time point and residual-delay rule for M07A/M07B.", "Researcher; supervisor review"],
    ["D09", "Observation horizon", "Set one common simulation observation horizon and sequence-completion rule.", "Researcher; supervisor review"],
    ["D10", "Right-censoring", "Classify unfinished calls/vessels as censored, not recovered or zero-delay by default.", "Researcher; supervisor review"],
    ["D11", "Metric overlap", "Explain the distinct analytical role of M02, M03A, M03B, M04 and M05.", "Researcher; supervisor review"],
    ["D12", "Real-world claims", "Keep outputs conditional on hypothetical model rules; no operational/real-world impact claim without validation.", "Researcher; supervisor review"],
], columns=["Decision_ID", "Topic", "Decision_Required", "Decision_Owner"])

# Readiness checks are deliberately structural. Passing does not mean metrics are approved.
checks = []
def check(name, passed, observed, expected, note):
    checks.append({
        "Check": name, "Passed": bool(passed),
        "Observed": str(observed), "Expected": str(expected), "Note": note
    })

check("Script88 contains nine metric rows", len(m88) == 9, len(m88), 9,
      "Preserves the original register inventory.")
check("Script90 contains nine metric rows", len(m90) == 9, len(m90), 9,
      "Preserves the decision-register inventory.")
check("Metric IDs are unique in Script88", m88["Metric_ID"].is_unique,
      m88["Metric_ID"].nunique(), len(m88), "No duplicate metric identifiers.")
check("Metric IDs are unique in Script90", m90["Metric_ID"].is_unique,
      m90["Metric_ID"].nunique(), len(m90), "No duplicate metric identifiers.")
check("Metric ID sets reconcile", set(m88.Metric_ID) == set(m90.Metric_ID),
      sorted(set(m88.Metric_ID) ^ set(m90.Metric_ID)), "No differences",
      "Both registers must contain the same metric IDs.")
check("All registered base fields match", comparison["All_Base_Fields_Match"].all(),
      int(comparison["All_Base_Fields_Match"].sum()), len(comparison),
      "Script90 must preserve Script88 definitions and caveats.")
check("All metric decisions remain pending",
      decision["Researcher_Decision"].eq("PENDING").all(),
      decision["Researcher_Decision"].value_counts().to_dict(), "PENDING for all",
      "No researcher metric decision is inferred.")
check("All supervisor reviews remain pending",
      decision["Supervisor_Review_Status"].eq("PENDING").all(),
      decision["Supervisor_Review_Status"].value_counts().to_dict(), "PENDING for all",
      "No supervisor approval is inferred.")
check("No metric approval is granted",
      (~m90["Approval_Granted"].fillna(False).astype(bool)).all(),
      int(m90["Approval_Granted"].fillna(False).astype(bool).sum()), 0,
      "Approval state is read, not changed.")
check("No execution authorization is granted",
      (~m90["Execution_Authorized"].fillna(False).astype(bool)).all(),
      int(m90["Execution_Authorized"].fillna(False).astype(bool).sum()), 0,
      "Script92 does not authorize simulation.")
check("Metric-definition approvals remain pending",
      decision["Metric_Definition_Approval"].eq("PENDING").all(),
      decision["Metric_Definition_Approval"].value_counts().to_dict(),
      "PENDING for all", "No metric definition is approved.")
check("Censoring approvals remain pending",
      decision["Censoring_Rule_Approval"].eq("PENDING").all(),
      decision["Censoring_Rule_Approval"].value_counts().to_dict(),
      "PENDING for all", "No censoring rule is approved.")
check("No real-world impact claims are enabled",
      (~m90["Real_World_Impact_Claim"].fillna(False).astype(bool)).all(),
      int(m90["Real_World_Impact_Claim"].fillna(False).astype(bool).sum()), 0,
      "Model outputs remain conditional and hypothetical.")

checks_df = pd.DataFrame(checks)

# Save all outputs separately; do not overwrite Scripts88/90.
outputs = {
    "92_register_reconciliation.csv": comparison,
    "92_metric_operationalization_review.csv": review,
    "92_metric_decision_status.csv": decision,
    "92_open_estimand_and_censoring_decisions.csv": open_items,
    "92_readiness_checks.csv": checks_df,
}
for filename, frame in outputs.items():
    frame.to_csv(TABLES / filename, index=False)

passed = int(checks_df["Passed"].sum())
failed = len(checks_df) - passed
report = f"""SCRIPT 92 — RESPONSE METRIC DEFINITION, ESTIMAND AND CENSORING AUDIT
{'=' * 78}

PURPOSE
Audit the original Script88 response metric register against the Script90
decision register. Identify definition, estimand, denominator and censoring
decisions required before execution. This is not metric approval or simulation.

SOURCE INVENTORY
Script88 metric rows: {len(m88)}
Script90 decision rows: {len(m90)}
Metric IDs in common: {len(set(m88.Metric_ID) & set(m90.Metric_ID))}
Metric IDs unmatched: {len(set(m88.Metric_ID) ^ set(m90.Metric_ID))}

REGISTER RECONCILIATION
Base fields match across both registers: {int(comparison['All_Base_Fields_Match'].sum())}/{len(comparison)}
The original metric names, aggregation levels, units, priorities and caveats
are preserved. No source register was modified.

METRIC INVENTORY
{review[['Metric_ID','Metric']].to_string(index=False)}

KEY AUDIT FINDINGS
1. M01/M02 require an explicit reference timestamp, eligible denominator and
   treatment of negative/early values.
2. M03A is a maximum over vessel final represented calls; unfinished final
   calls must not be treated as completed observations.
3. M03B is distinct from M03A, but its accumulation operator must be explicit.
4. M04 needs one eligible final-call value per vessel to avoid call-count weighting.
5. M05 needs a quantile convention and explicit zero-delay reporting.
6. M06 requires matched policy/no-recovery records; it remains modelled credit,
   not observed operational recovery.
7. M07A/M07B require a threshold, evaluation time and a distinct censored status.
8. A common observation horizon and right-censoring rule are not yet approved.

DECISION STATUS
Researcher decisions pending for all metrics:
{decision['Researcher_Decision'].value_counts().to_dict()}
Supervisor reviews pending for all metrics:
{decision['Supervisor_Review_Status'].value_counts().to_dict()}
Metric-definition approvals granted: {int(m90['Metric_Definition_Approval'].astype(str).str.upper().eq('APPROVED').sum())}
Censoring-rule approvals granted: {int(m90['Censoring_Rule_Approval'].astype(str).str.upper().eq('APPROVED').sum())}
Simulation execution authorized: NO (per source decision register)

READINESS CHECKS
{passed}/{len(checks_df)} passed; {failed} failed.

INTERPRETATION
This audit checks register integrity and exposes unresolved operational definitions.
The proposed requirements in 92_metric_operationalization_review.csv are audit
guidance only, not selected formulas or approved researcher decisions. No metric
has been silently redefined. No empirical, physical-route, Hormuz-transit or
real-world operational claim is supported by this audit.

OUTPUTS
{chr(10).join('- outputs/tables/' + x for x in outputs)}
- outputs/reports/92_response_metric_estimand_censoring_audit_report.txt

DECISION
Script92 is a diagnostic audit only. Researcher and supervisor decisions are
required for the listed estimands, denominators, thresholds and censoring rules.
No simulation was run; no source inputs or prior registers were modified.
"""
report_path = REPORTS / "92_response_metric_estimand_censoring_audit_report.txt"
report_path.write_text(report, encoding="utf-8")

print("SCRIPT 92 — RESPONSE METRIC DEFINITION, ESTIMAND AND CENSORING AUDIT")
print("=" * 78)
print(f"Script88 metric rows: {len(m88)}")
print(f"Script90 decision rows: {len(m90)}")
print(f"Base fields reconciled: {int(comparison['All_Base_Fields_Match'].sum())}/{len(comparison)}")
print(f"Open decision items: {len(open_items)}")
print(f"Readiness checks: {passed}/{len(checks_df)} passed; {failed} failed")
print("Metric approvals granted: 0")
print("Censoring approvals granted: 0")
print("Simulation execution authorized: NO")
print("Simulation executed: NO")
print("Source registers modified: NO")
print(f"Report: {report_path}")
if failed:
    raise SystemExit("Script92 completed with failed readiness checks; inspect outputs.")
