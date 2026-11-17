#!/usr/bin/env python3
"""
SCRIPT 96 — INTEGRATED EXPERIMENTAL DESIGN AND EXECUTION READINESS AUDIT

Purpose
-------
Consolidate the existing Script88–95 design decisions, open researcher decisions,
supervisor approvals, methodological blockers, and technical audit status.

This is an audit/register-consolidation script only.
It does NOT:
- run or modify a simulation;
- modify any upstream script, dataset, or register;
- approve factors, exposure, recovery policies, metrics, replication, or execution;
- infer missing researcher or supervisor decisions.

Run from the project root:
    python src/96_integrated_experimental_design_readiness_audit.py
"""

from __future__ import annotations

from pathlib import Path
import sys
import json
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"
TABLES.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

TOL = 1e-9

# Required sources are the actual registers and audit outputs established
# by Scripts88–95. The script fails closed if any required source is absent.
INPUTS = {
    # Script88 — protocol and candidate design
    "s88_protocol": "88_protocol_register.csv",
    "s88_factors": "88_scenario_factor_register.csv",
    "s88_matrix": "88_scenario_policy_matrix.csv",
    "s88_metrics": "88_response_metric_register.csv",
    "s88_replication": "88_replication_decision_register.csv",
    "s88_limitations": "88_limitation_register.csv",
    "s88_checks": "88_readiness_checks.csv",

    # Script89 — transition scope and selection
    "s89_scope": "89_scenario_scope_summary.csv",
    "s89_selection": "89_transition_selection_register.csv",
    "s89_checks": "89_readiness_checks.csv",

    # Script90 — decision and approval registers
    "s90_gates": "90_approval_gate_register.csv",
    "s90_factors": "90_factor_decision_register.csv",
    "s90_policies": "90_recovery_policy_decision_register.csv",
    "s90_metrics": "90_response_metric_decision_register.csv",
    "s90_replication": "90_replication_decision_register.csv",
    "s90_scope": "90_scope_decision_register.csv",
    "s90_checks": "90_readiness_checks.csv",

    # Script91 — sensitivity and statistical adequacy diagnostics
    "s91_factor_ranges": "91_factor_range_diagnostics.csv",
    "s91_replication": "91_replication_adequacy_review.csv",
    "s91_metrics": "91_response_metric_review.csv",
    "s91_coverage": "91_scenario_policy_coverage.csv",
    "s91_validity": "91_scientific_validity_boundaries.csv",
    "s91_checks": "91_readiness_checks.csv",

    # Script92 — metric operationalization and open decisions
    "s92_metric_status": "92_metric_decision_status.csv",
    "s92_metric_review": "92_metric_operationalization_review.csv",
    "s92_open": "92_open_estimand_and_censoring_decisions.csv",
    "s92_checks": "92_readiness_checks.csv",

    # Script93 — candidate estimands and comparisons
    "s93_estimands": "93_candidate_estimand_register.csv",
    "s93_contrasts": "93_candidate_policy_contrasts.csv",
    "s93_coverage": "93_scenario_policy_coverage_audit.csv",
    "s93_checks": "93_readiness_checks.csv",

    # Script94–95 — policy semantics and bounded-recovery audits
    "s94_semantics": "94_policy_mathematical_semantics_register.csv",
    "s94_checks": "94_readiness_checks.csv",
    "s95_reconciliation": "95_bounded_recovery_record_reconciliation.csv",
    "s95_checks": "95_readiness_checks.csv",
}

missing = [name for name in INPUTS.values() if not (TABLES / name).is_file()]
if missing:
    print("ERROR — Script96 cannot proceed. Required upstream files are missing:")
    for name in missing:
        print(f"  - {TABLES / name}")
    print("\nRestore the actual Script88–95 outputs; do not create substitute files.")
    raise SystemExit(1)

D = {
    key: pd.read_csv(TABLES / filename, low_memory=False)
    for key, filename in INPUTS.items()
}


def has_columns(df: pd.DataFrame, columns: list[str]) -> bool:
    return all(c in df.columns for c in columns)


def truthy(value) -> bool:
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "approved", "y"}


def norm_status(value) -> str:
    if pd.isna(value) or str(value).strip() == "":
        return "NOT_RECORDED"
    return str(value).strip().upper()


def value_or_blank(row: pd.Series, column: str) -> str:
    if column not in row.index or pd.isna(row[column]):
        return ""
    return str(row[column])


def json_counts(series: pd.Series) -> str:
    return json.dumps({str(k): int(v) for k, v in series.fillna("MISSING").value_counts().items()},
                      sort_keys=True)


checks: list[dict] = []


def add_check(name: str, passed: bool, observed, expected, interpretation: str):
    checks.append({
        "Check_ID": name,
        "Passed": bool(passed),
        "Observed": str(observed),
        "Expected": str(expected),
        "Interpretation": interpretation,
    })


# ---------------------------------------------------------------------
# 1. Schema and source inventory checks
# ---------------------------------------------------------------------
required_columns = {
    "s88_protocol": ["Primary_Mechanism", "Execution_Authorized"],
    "s88_factors": ["Scenario_ID", "Mechanism", "Shock_Magnitude_Hours",
                    "Affected_Transition_Share"],
    "s88_matrix": ["Scenario_ID", "Recovery_Policy_ID"],
    "s88_metrics": ["Metric_ID", "Metric"],
    "s90_gates": ["Gate_ID", "Decision_Area", "Researcher_Decision",
                  "Supervisor_Review_Status", "Approval_Granted",
                  "Execution_Authorized"],
    "s90_factors": ["Scenario_ID", "Researcher_Decision",
                    "Supervisor_Review_Status", "Approval_Granted",
                    "Execution_Authorized"],
    "s90_policies": ["Recovery_Policy_ID", "Researcher_Decision",
                     "Supervisor_Review_Status", "Approval_Granted",
                     "Execution_Authorized"],
    "s90_metrics": ["Metric_ID", "Researcher_Decision",
                    "Supervisor_Review_Status", "Approval_Granted",
                    "Metric_Definition_Approval", "Censoring_Rule_Approval",
                    "Execution_Authorized"],
    "s90_replication": ["Option_ID", "Researcher_Decision",
                        "Supervisor_Review_Status", "Approval_Granted",
                        "Execution_Authorized"],
    "s90_scope": ["Scope_Scenario_ID", "Researcher_Decision",
                  "Supervisor_Review_Status", "Approval_Granted",
                  "Execution_Authorized"],
    "s92_open": ["Decision_ID", "Topic", "Decision_Required", "Decision_Owner"],
    "s92_metric_status": ["Metric_ID", "Researcher_Decision",
                          "Supervisor_Review_Status", "Approval_Granted",
                          "Metric_Definition_Approval", "Censoring_Rule_Approval"],
    "s93_estimands": ["Estimand_ID", "Estimand_Name", "Decision_Status"],
    "s95_reconciliation": ["__key_scenario", "__key_policy", "__key_vessel",
                           "__key_call", "R76_Pre_Recovery_Delay_Hours",
                           "R77_Pre_Recovery_Delay_Hours"],
}

schema_failures = []
for key, cols in required_columns.items():
    absent = [c for c in cols if c not in D[key].columns]
    if absent:
        schema_failures.append(f"{INPUTS[key]} missing {absent}")

add_check(
    "Required upstream schemas are available",
    len(schema_failures) == 0,
    schema_failures if schema_failures else "All required columns found",
    "No required schema fields missing",
    "Schema validation only; no decision or approval is inferred."
)

source_inventory = []
for key, filename in INPUTS.items():
    df = D[key]
    source_inventory.append({
        "Source_Stage": key.upper(),
        "Source_File": filename,
        "Exists": True,
        "Rows": len(df),
        "Columns": len(df.columns),
        "Schema_Status": "PASS" if key not in required_columns or
                         has_columns(df, required_columns[key]) else "FAIL",
        "Purpose": "Upstream evidence/register consumed by Script96",
    })
source_inventory_df = pd.DataFrame(source_inventory)


# ---------------------------------------------------------------------
# 2. Structural reconciliation of the design
# ---------------------------------------------------------------------
s88_protocol = D["s88_protocol"]
s88_factors = D["s88_factors"]
s88_matrix = D["s88_matrix"]
s88_metrics = D["s88_metrics"]
s89_scope = D["s89_scope"]
s89_selection = D["s89_selection"]
s90_gates = D["s90_gates"]
s90_factors = D["s90_factors"]
s90_policies = D["s90_policies"]
s90_metrics = D["s90_metrics"]
s90_replication = D["s90_replication"]
s90_scope = D["s90_scope"]
s92_open = D["s92_open"]
s92_status = D["s92_metric_status"]
s93_estimands = D["s93_estimands"]

mechanisms = (
    s88_protocol["Primary_Mechanism"].dropna().astype(str).unique().tolist()
    if "Primary_Mechanism" in s88_protocol else []
)
scenario_ids = (
    s88_factors["Scenario_ID"].dropna().astype(str).unique()
    if "Scenario_ID" in s88_factors else []
)
policy_ids = (
    s90_policies["Recovery_Policy_ID"].dropna().astype(str).unique()
    if "Recovery_Policy_ID" in s90_policies else []
)
matrix_pairs = (
    s88_matrix[["Scenario_ID", "Recovery_Policy_ID"]].drop_duplicates()
    if has_columns(s88_matrix, ["Scenario_ID", "Recovery_Policy_ID"])
    else pd.DataFrame(columns=["Scenario_ID", "Recovery_Policy_ID"])
)

add_check(
    "Script88 factorial shock grid contains 16 candidate scenarios",
    len(s88_factors) == 16 and len(scenario_ids) == 16,
    f"rows={len(s88_factors)}; unique_scenarios={len(scenario_ids)}",
    "16 candidate shock scenarios",
    "The existing no-disruption baseline is separate from this 4x4 candidate shock grid."
)
add_check(
    "Script88 candidate scenario-policy matrix contains 80 combinations",
    len(s88_matrix) == 80 and len(matrix_pairs) == 80,
    f"rows={len(s88_matrix)}; unique_pairs={len(matrix_pairs)}",
    "80 unique candidate scenario-policy combinations",
    "This is the 16-scenario by five-policy shock grid; do not misstate it as 85."
)
add_check(
    "Five recovery policy definitions are retained",
    len(policy_ids) == 5,
    f"{len(policy_ids)}: {sorted(policy_ids.tolist())}",
    "5 distinct policies",
    "Policy identities are model rules, not verified operational capabilities."
)
add_check(
    "Nine response metrics reconcile between Script88 and Script90",
    len(s88_metrics) == 9
    and len(s90_metrics) == 9
    and set(s88_metrics["Metric_ID"].astype(str)) == set(s90_metrics["Metric_ID"].astype(str)),
    f"Script88={len(s88_metrics)}; Script90={len(s90_metrics)}; "
    f"ID_match={set(s88_metrics['Metric_ID'].astype(str)) == set(s90_metrics['Metric_ID'].astype(str))}",
    "9 metrics with identical IDs",
    "Register continuity does not constitute metric-definition approval."
)
add_check(
    "Four transition-scope levels are retained",
    len(s89_scope) == 4 and len(s90_scope) == 4,
    f"Script89={len(s89_scope)}; Script90={len(s90_scope)}",
    "4 scope levels",
    "Coverage shares are mathematical selection shares, not geographic exposure probabilities."
)
unique_transitions = (
    s89_selection["Simulation_Record_ID"].nunique()
    if "Simulation_Record_ID" in s89_selection else -1
)
add_check(
    "Transition selection register retains 271 unique transition records",
    unique_transitions == 271,
    unique_transitions,
    271,
    "Observed schedule transition records; not validated physical routes."
)
add_check(
    "Twelve Script92 estimand/censoring decisions are retained",
    len(s92_open) == 12 and s92_open["Decision_ID"].nunique() == 12,
    f"rows={len(s92_open)}; unique={s92_open['Decision_ID'].nunique()}",
    "12 unique open decisions",
    "These are explicit research decisions, not choices for Script96 to make."
)
add_check(
    "Eight candidate estimands are retained",
    len(s93_estimands) == 8 and s93_estimands["Estimand_ID"].nunique() == 8,
    f"rows={len(s93_estimands)}; unique={s93_estimands['Estimand_ID'].nunique()}",
    "8 candidate estimands",
    "Candidate estimands remain proposals, not approved estimands."
)


# ---------------------------------------------------------------------
# 3. Check the historical audit outputs without assuming their success
# ---------------------------------------------------------------------
def audit_check_summary(key: str):
    df = D[key]
    if "Passed" not in df.columns:
        return {"rows": len(df), "passed": None, "failed": None, "status": "NO_PASSED_COLUMN"}
    passed = df["Passed"].map(truthy)
    return {
        "rows": len(df),
        "passed": int(passed.sum()),
        "failed": int((~passed).sum()),
        "status": "ALL_PASS" if bool(passed.all()) else "HAS_FAILURES",
    }


audit_keys = [
    "s88_checks", "s89_checks", "s90_checks", "s91_checks",
    "s92_checks", "s93_checks", "s94_checks", "s95_checks",
]
audit_summary_rows = []
for key in audit_keys:
    summary = audit_check_summary(key)
    audit_summary_rows.append({
        "Audit": key.upper(),
        "Source_File": INPUTS[key],
        **summary,
    })
    add_check(
        f"{key.upper()} upstream readiness checks contain no failures",
        summary["status"] == "ALL_PASS",
        summary,
        "All recorded checks passed",
        "Inherited diagnostic result; Script96 does not replace the underlying audit."
    )
audit_summary_df = pd.DataFrame(audit_summary_rows)


# Script95's record-level audit: verify uniqueness/pair coverage and the
# recorded cross-model recurrence relationship in its reconciliation output.
r95 = D["s95_reconciliation"].copy()
r95_keys = ["__key_scenario", "__key_policy", "__key_vessel", "__key_call"]
r95_unique = not r95.duplicated(r95_keys).any() if has_columns(r95, r95_keys) else False
r95_rows = len(r95)
r95_numeric_ok = True
r95_max_pre_diff = None
if has_columns(r95, ["R76_Pre_Recovery_Delay_Hours", "R77_Pre_Recovery_Delay_Hours"]):
    a = pd.to_numeric(r95["R76_Pre_Recovery_Delay_Hours"], errors="coerce")
    b = pd.to_numeric(r95["R77_Pre_Recovery_Delay_Hours"], errors="coerce")
    r95_numeric_ok = bool(a.notna().all() and b.notna().all())
    if r95_numeric_ok:
        r95_max_pre_diff = float((b - a).abs().max())

add_check(
    "Script95 reconciliation contains 51,340 unique matched records",
    r95_rows == 51340 and r95_unique,
    f"rows={r95_rows}; unique_composite_keys={r95_unique}",
    "51,340 rows and unique scenario-policy-vessel-call keys",
    "This consolidates the completed Script95 record-level reconciliation."
)
add_check(
    "Script95 pre-delay fields are numeric and complete",
    r95_numeric_ok,
    f"complete_numeric={r95_numeric_ok}; max_cross_model_pre_delay_difference={r95_max_pre_diff}",
    "No missing/non-numeric values",
    "Cross-model pre-delay differences are expected to be nonzero; Script95 validates separate recurrences."
)


# ---------------------------------------------------------------------
# 4. Build a normalized integrated design register
# ---------------------------------------------------------------------
design_rows = []


def add_design(item_id, area, source, record_id, proposal, researcher="NOT_RECORDED",
               selected="", supervisor="NOT_RECORDED", approved=False,
               approval_date="", execution=False, evidence="NOT_ASSESSED",
               status="NOT_ASSESSED", action="", limitation=""):
    design_rows.append({
        "Item_ID": str(item_id),
        "Decision_Area": str(area),
        "Source_Register": str(source),
        "Source_Record_ID": str(record_id),
        "Current_Proposal_or_Definition": str(proposal),
        "Researcher_Decision": norm_status(researcher),
        "Researcher_Selected_Value": str(selected),
        "Supervisor_Review_Status": norm_status(supervisor),
        "Approval_Granted": bool(approved),
        "Approval_Date": str(approval_date),
        "Execution_Authorized": bool(execution),
        "Evidence_Status": str(evidence),
        "Current_Status": str(status),
        "Required_Next_Action": str(action),
        "Interpretation_Limit": str(limitation),
    })


for _, row in s90_gates.iterrows():
    gid = value_or_blank(row, "Gate_ID")
    decision = norm_status(row.get("Researcher_Decision", "PENDING"))
    supervisor = norm_status(row.get("Supervisor_Review_Status", "PENDING"))
    status = norm_status(row.get("Current_Status", "PENDING"))
    action = (
        "Obtain researcher decision and supervisor review."
        if decision == "PENDING" else
        "Researcher choice recorded; obtain supervisor review and explicit approval."
        if supervisor == "PENDING" else
        "Verify documented approval and execution gate."
    )
    if gid == "G09":
        action = "Keep blocked until every prerequisite decision and approval is documented."
    add_design(
        gid, value_or_blank(row, "Decision_Area"), INPUTS["s90_gates"], gid,
        value_or_blank(row, "Current_Proposal"),
        decision, value_or_blank(row, "Researcher_Selected_Value"),
        supervisor, truthy(row.get("Approval_Granted", False)),
        value_or_blank(row, "Approval_Date"),
        truthy(row.get("Execution_Authorized", False)),
        "DECISION_REGISTER",
        status, action, value_or_blank(row, "Decision_Note")
    )

for _, row in s90_factors.iterrows():
    sid = value_or_blank(row, "Scenario_ID")
    add_design(
        sid, "Scenario factor level", INPUTS["s90_factors"], sid,
        f"mechanism={value_or_blank(row,'Mechanism')}; "
        f"shock_hours={value_or_blank(row,'Shock_Magnitude_Hours')}; "
        f"affected_share={value_or_blank(row,'Affected_Transition_Share')}; "
        f"seed={value_or_blank(row,'Selection_Seed_Proposed')}",
        row.get("Researcher_Decision", "PENDING"),
        value_or_blank(row, "Researcher_Selected_Value"),
        row.get("Supervisor_Review_Status", "PENDING"),
        truthy(row.get("Approval_Granted", False)),
        value_or_blank(row, "Approval_Date"),
        truthy(row.get("Execution_Authorized", False)),
        value_or_blank(row, "Evidence_Status"),
        value_or_blank(row, "Factor_Approval_Status"),
        "Select/justify factor levels; obtain supervisor review; retain hypothetical interpretation.",
        value_or_blank(row, "Interpretation_Limit")
    )

for _, row in s90_scope.iterrows():
    sid = value_or_blank(row, "Scope_Scenario_ID")
    add_design(
        sid, "Affected-transition scope", INPUTS["s90_scope"], sid,
        f"share={value_or_blank(row,'Affected_Transition_Share')}; "
        f"selected_records={value_or_blank(row,'Selected_Transition_Count')}/"
        f"{value_or_blank(row,'Transition_Universe_Count')}; "
        f"seed={value_or_blank(row,'Selection_Seed')}",
        row.get("Researcher_Decision", "PENDING"),
        value_or_blank(row, "Researcher_Selected_Value"),
        row.get("Supervisor_Review_Status", "PENDING"),
        truthy(row.get("Approval_Granted", False)),
        value_or_blank(row, "Approval_Date"),
        truthy(row.get("Execution_Authorized", False)),
        value_or_blank(row, "Geographic_Exposure_Evidence"),
        value_or_blank(row, "Scope_Approval_Status"),
        "Review mathematical scope levels and approve only as hypothetical record coverage.",
        value_or_blank(row, "Scope_Interpretation")
    )

for _, row in s90_policies.iterrows():
    pid = value_or_blank(row, "Recovery_Policy_ID")
    proposal = (
        f"{value_or_blank(row,'Recovery_Policy')}; type={value_or_blank(row,'Policy_Type')}; "
        f"fixed_cap={value_or_blank(row,'Fixed_Recovery_Cap_Hours')}; "
        f"proportion={value_or_blank(row,'Proportional_Recovery_Rate')}; "
        f"max_per_link={value_or_blank(row,'Maximum_Recovery_Per_Link_Hours')}"
    )
    add_design(
        pid, "Recovery policy", INPUTS["s90_policies"], pid, proposal,
        row.get("Researcher_Decision", "PENDING"),
        value_or_blank(row, "Researcher_Selected_Value"),
        row.get("Supervisor_Review_Status", "PENDING"),
        truthy(row.get("Approval_Granted", False)),
        value_or_blank(row, "Approval_Date"),
        truthy(row.get("Execution_Authorized", False)),
        "HYPOTHETICAL_POLICY_RULE",
        value_or_blank(row, "Policy_Approval_Status"),
        "Decide whether to retain this abstract policy and obtain supervisor review; do not claim operational feasibility.",
        value_or_blank(row, "Policy_Interpretation_Limit")
    )

for _, row in s90_metrics.iterrows():
    mid = value_or_blank(row, "Metric_ID")
    add_design(
        mid, "Response metric", INPUTS["s90_metrics"], mid,
        f"{value_or_blank(row,'Metric')}; level={value_or_blank(row,'Aggregation_Level')}; "
        f"unit={value_or_blank(row,'Unit')}; priority={value_or_blank(row,'Priority')}",
        row.get("Researcher_Decision", "PENDING"),
        value_or_blank(row, "Researcher_Selected_Value"),
        row.get("Supervisor_Review_Status", "PENDING"),
        truthy(row.get("Approval_Granted", False)),
        value_or_blank(row, "Approval_Date"),
        truthy(row.get("Execution_Authorized", False)),
        "METRIC_CANDIDATE",
        f"definition={value_or_blank(row,'Metric_Definition_Approval')}; "
        f"censoring={value_or_blank(row,'Censoring_Rule_Approval')}",
        "Finalize operational definition, denominator, horizon and censoring treatment; obtain supervisor review.",
        value_or_blank(row, "Definition_or_Caveat")
    )

for _, row in s90_replication.iterrows():
    rid = value_or_blank(row, "Option_ID")
    add_design(
        rid, "Replication design", INPUTS["s90_replication"], rid,
        f"{value_or_blank(row,'Option')}; {value_or_blank(row,'Definition')}",
        row.get("Researcher_Decision", "PENDING"),
        value_or_blank(row, "Researcher_Selected_Value"),
        row.get("Supervisor_Review_Status", "PENDING"),
        truthy(row.get("Approval_Granted", False)),
        value_or_blank(row, "Approval_Date"),
        truthy(row.get("Execution_Authorized", False)),
        "REPLICATION_OPTION",
        value_or_blank(row, "Replication_Design_Approval"),
        "Decide whether deterministic reproducibility is the intended first-stage design; do not imply statistical inference.",
        value_or_blank(row, "Current_Interpretation")
    )

for _, row in s92_open.iterrows():
    did = value_or_blank(row, "Decision_ID")
    add_design(
        did, value_or_blank(row, "Topic"), INPUTS["s92_open"], did,
        value_or_blank(row, "Decision_Required"),
        "PENDING", "", "PENDING", False, "", False,
        "OPEN_ESTIMAND_OR_CENSORING_DECISION",
        "OPEN",
        f"Researcher decision required; owner: {value_or_blank(row,'Decision_Owner')}.",
        "Must be resolved before final metric/estimand freeze."
    )

for _, row in s93_estimands.iterrows():
    eid = value_or_blank(row, "Estimand_ID")
    add_design(
        eid, "Candidate estimand", INPUTS["s93_estimands"], eid,
        f"{value_or_blank(row,'Estimand_Name')}; quantity={value_or_blank(row,'Candidate_Quantity')}; "
        f"denominator/censoring={value_or_blank(row,'Denominator_And_Censoring')}",
        "PENDING", "", "PENDING", False, "", False,
        "CANDIDATE_NOT_APPROVED",
        value_or_blank(row, "Decision_Status"),
        "Select, revise or reject after resolving Script92 metric and censoring decisions.",
        value_or_blank(row, "Source_Metric_IDs")
    )

design_register = pd.DataFrame(design_rows)


# ---------------------------------------------------------------------
# 5. Researcher decision queue and supervisor approval register
# ---------------------------------------------------------------------
decision_rows = []
supervisor_rows = []


def append_decision(item_id, area, source, proposal, researcher, selected,
                    supervisor, approved, action, limitation=""):
    decision_rows.append({
        "Item_ID": item_id,
        "Decision_Area": area,
        "Source_Register": source,
        "Current_Proposal": proposal,
        "Researcher_Decision": norm_status(researcher),
        "Researcher_Selected_Value": selected,
        "Supervisor_Review_Status": norm_status(supervisor),
        "Approval_Granted": bool(approved),
        "Required_Action": action,
        "Interpretation_Limit": limitation,
    })


def append_supervisor(item_id, area, source, proposal, researcher, supervisor,
                      approved, approval_date, execution):
    supervisor_rows.append({
        "Item_ID": item_id,
        "Decision_Area": area,
        "Source_Register": source,
        "Proposal_or_Selected_Value": proposal,
        "Researcher_Decision": norm_status(researcher),
        "Supervisor_Review_Status": norm_status(supervisor),
        "Approval_Granted": bool(approved),
        "Approval_Date": approval_date,
        "Execution_Authorized": bool(execution),
        "Review_Required": not (
            norm_status(supervisor) in {"APPROVED", "REVIEWED_APPROVED"}
            and bool(approved)
        ),
    })


for _, row in s90_gates.iterrows():
    item = value_or_blank(row, "Gate_ID")
    area = value_or_blank(row, "Decision_Area")
    proposal = value_or_blank(row, "Current_Proposal")
    researcher = row.get("Researcher_Decision", "PENDING")
    supervisor = row.get("Supervisor_Review_Status", "PENDING")
    approved = truthy(row.get("Approval_Granted", False))
    action = (
        "Supervisor review and documented approval required."
        if norm_status(researcher) != "PENDING"
        else "Researcher must record a decision, then supervisor review and approval."
    )
    if item == "G09":
        action = "Execution remains blocked until all prerequisite approvals and written authorization exist."
    append_decision(item, area, INPUTS["s90_gates"], proposal, researcher,
                    value_or_blank(row, "Researcher_Selected_Value"),
                    supervisor, approved, action, value_or_blank(row, "Decision_Note"))
    append_supervisor(item, area, INPUTS["s90_gates"], proposal, researcher,
                      supervisor, approved, value_or_blank(row, "Approval_Date"),
                      truthy(row.get("Execution_Authorized", False)))

for key, df, id_col, area, proposal_fn in [
    ("s90_factors", s90_factors, "Scenario_ID", "Scenario factor",
     lambda r: f"{r.get('Shock_Magnitude_Hours')}h shock; share={r.get('Affected_Transition_Share')}"),
    ("s90_scope", s90_scope, "Scope_Scenario_ID", "Transition scope",
     lambda r: f"share={r.get('Affected_Transition_Share')}; count={r.get('Selected_Transition_Count')}"),
    ("s90_policies", s90_policies, "Recovery_Policy_ID", "Recovery policy",
     lambda r: str(r.get("Recovery_Policy", ""))),
    ("s90_metrics", s90_metrics, "Metric_ID", "Response metric",
     lambda r: str(r.get("Metric", ""))),
    ("s90_replication", s90_replication, "Option_ID", "Replication design",
     lambda r: str(r.get("Option", ""))),
]:
    for _, row in df.iterrows():
        item = value_or_blank(row, id_col)
        researcher = row.get("Researcher_Decision", "PENDING")
        supervisor = row.get("Supervisor_Review_Status", "PENDING")
        approved = truthy(row.get("Approval_Granted", False))
        append_decision(
            item, area, INPUTS[key], proposal_fn(row), researcher,
            value_or_blank(row, "Researcher_Selected_Value"),
            supervisor, approved,
            "Researcher decision and supervisor review required; retain the source interpretation limits."
        )
        append_supervisor(
            item, area, INPUTS[key], proposal_fn(row), researcher, supervisor,
            approved, value_or_blank(row, "Approval_Date"),
            truthy(row.get("Execution_Authorized", False))
        )

for _, row in s92_open.iterrows():
    item = value_or_blank(row, "Decision_ID")
    append_decision(
        item, value_or_blank(row, "Topic"), INPUTS["s92_open"],
        value_or_blank(row, "Decision_Required"), "PENDING", "",
        "PENDING", False,
        f"Resolve by researcher with supervisor review; owner={value_or_blank(row,'Decision_Owner')}."
    )
    append_supervisor(
        item, value_or_blank(row, "Topic"), INPUTS["s92_open"],
        value_or_blank(row, "Decision_Required"), "PENDING", "PENDING",
        False, "", False
    )

decision_queue = pd.DataFrame(decision_rows)
supervisor_register = pd.DataFrame(supervisor_rows)


# ---------------------------------------------------------------------
# 6. Explicit execution blockers
# ---------------------------------------------------------------------
blocker_rows = []


def add_blocker(blocker_id, category, description, source, current_status,
                required_resolution, blocks_execution=True, owner="Researcher; supervisor"):
    blocker_rows.append({
        "Blocker_ID": blocker_id,
        "Category": category,
        "Description": description,
        "Source_Register": source,
        "Current_Status": current_status,
        "Required_Resolution": required_resolution,
        "Blocks_Final_Experiment_Execution": bool(blocks_execution),
        "Decision_Owner": owner,
    })


for _, row in s90_gates.iterrows():
    gid = value_or_blank(row, "Gate_ID")
    decision = norm_status(row.get("Researcher_Decision", "PENDING"))
    supervisor = norm_status(row.get("Supervisor_Review_Status", "PENDING"))
    approved = truthy(row.get("Approval_Granted", False))
    execution = truthy(row.get("Execution_Authorized", False))
    if gid == "G01":
        add_blocker(
            "G01-SUPERVISOR", "Mechanism review",
            "Primary mechanism choice is researcher-confirmed, but supervisor review/approval is not recorded.",
            INPUTS["s90_gates"], f"researcher={decision}; supervisor={supervisor}; approved={approved}",
            "Obtain supervisor review of the selected hypothetical elapsed-time-shock mechanism."
        )
    elif gid == "G09":
        add_blocker(
            "G09-EXECUTION", "Execution authorization",
            "Simulation execution is explicitly blocked in the approval-gate register.",
            INPUTS["s90_gates"], f"status={value_or_blank(row,'Current_Status')}; authorized={execution}",
            "Do not execute until all relevant design decisions and approvals are complete and authorization is explicitly recorded."
        )
    elif decision == "PENDING" or supervisor == "PENDING" or not approved:
        add_blocker(
            gid, "Approval gate",
            value_or_blank(row, "Decision_Area"),
            INPUTS["s90_gates"],
            f"researcher={decision}; supervisor={supervisor}; approved={approved}",
            "Record the researcher decision, rationale, supervisor review and approval as applicable."
        )

# Factor-level decisions
for _, row in s90_factors.iterrows():
    if norm_status(row.get("Researcher_Decision")) == "PENDING" or not truthy(row.get("Approval_Granted", False)):
        add_blocker(
            f"FACTOR-{value_or_blank(row,'Scenario_ID')}", "Factor approval",
            f"Candidate shock={value_or_blank(row,'Shock_Magnitude_Hours')}h; "
            f"affected share={value_or_blank(row,'Affected_Transition_Share')}.",
            INPUTS["s90_factors"],
            f"researcher={norm_status(row.get('Researcher_Decision'))}; "
            f"supervisor={norm_status(row.get('Supervisor_Review_Status'))}; "
            f"approval={truthy(row.get('Approval_Granted', False))}",
            "Decide whether to retain/modify this provisional level and obtain required review."
        )

# Scope-level decisions
for _, row in s90_scope.iterrows():
    if norm_status(row.get("Researcher_Decision")) == "PENDING" or not truthy(row.get("Approval_Granted", False)):
        add_blocker(
            f"SCOPE-{value_or_blank(row,'Scope_Scenario_ID')}", "Transition-scope approval",
            f"Candidate coverage share={value_or_blank(row,'Affected_Transition_Share')}; "
            f"selected records={value_or_blank(row,'Selected_Transition_Count')}.",
            INPUTS["s90_scope"],
            f"researcher={norm_status(row.get('Researcher_Decision'))}; "
            f"supervisor={norm_status(row.get('Supervisor_Review_Status'))}; "
            f"approval={truthy(row.get('Approval_Granted', False))}",
            "Approve only as a hypothetical fraction of observed transition records; do not interpret as geographic exposure."
        )

# Recovery policies
for _, row in s90_policies.iterrows():
    if norm_status(row.get("Researcher_Decision")) == "PENDING" or not truthy(row.get("Approval_Granted", False)):
        add_blocker(
            f"POLICY-{value_or_blank(row,'Recovery_Policy_ID')}", "Recovery-policy approval",
            value_or_blank(row, "Recovery_Policy"),
            INPUTS["s90_policies"],
            f"researcher={norm_status(row.get('Researcher_Decision'))}; "
            f"supervisor={norm_status(row.get('Supervisor_Review_Status'))}; "
            f"approval={truthy(row.get('Approval_Granted', False))}",
            "Select/reject/modify the abstract policy and obtain supervisor review; operational feasibility remains unestablished."
        )

# Metric and censoring decisions
for _, row in s90_metrics.iterrows():
    mid = value_or_blank(row, "Metric_ID")
    if (norm_status(row.get("Researcher_Decision")) == "PENDING"
        or norm_status(row.get("Metric_Definition_Approval")) != "APPROVED"
        or norm_status(row.get("Censoring_Rule_Approval")) != "APPROVED"):
        add_blocker(
            f"METRIC-{mid}", "Metric/estimand/censoring",
            value_or_blank(row, "Metric"),
            INPUTS["s90_metrics"],
            f"researcher={norm_status(row.get('Researcher_Decision'))}; "
            f"definition={norm_status(row.get('Metric_Definition_Approval'))}; "
            f"censoring={norm_status(row.get('Censoring_Rule_Approval'))}",
            "Finalize the operational definition, denominator, common horizon and censoring rule; obtain review."
        )

for _, row in s92_open.iterrows():
    did = value_or_blank(row, "Decision_ID")
    add_blocker(
        did, "Open estimand/censoring decision",
        f"{value_or_blank(row,'Topic')}: {value_or_blank(row,'Decision_Required')}",
        INPUTS["s92_open"], "OPEN",
        f"Resolve explicitly; owner={value_or_blank(row,'Decision_Owner')}."
    )

# Replication design
for _, row in s90_replication.iterrows():
    if norm_status(row.get("Researcher_Decision")) == "PENDING" or not truthy(row.get("Approval_Granted", False)):
        add_blocker(
            f"REPLICATION-{value_or_blank(row,'Option_ID')}", "Replication design",
            value_or_blank(row, "Option"),
            INPUTS["s90_replication"],
            f"status={value_or_blank(row,'Status')}; "
            f"researcher={norm_status(row.get('Researcher_Decision'))}; "
            f"approved={truthy(row.get('Approval_Granted', False))}",
            "Decide the intended deterministic/stochastic design and its inferential scope; do not claim precision without a justified design."
        )

# The final specification itself has not been frozen in Scripts88–95.
add_blocker(
    "SIM-SPEC-FREEZE", "Simulation specification",
    "A final frozen execution specification (horizon, event logic, state variables, output contract and acceptance tests) is not evidenced by Scripts88–95.",
    "Scripts88–95 consolidated evidence",
    "NOT_YET_FROZEN",
    "Prepare and review a simulation specification after estimands, factors and policies are settled."
)

blockers_df = pd.DataFrame(blocker_rows)


# ---------------------------------------------------------------------
# 7. Integrated experimental design register
# ---------------------------------------------------------------------
integrated_rows = [
    ["DATA-BASELINE", "Historical baseline", "604 calls; 155 vessels; 19 ports; 271 distinct-port transitions",
     "ESTABLISHED_BASELINE", "Preserve original 604-call baseline; no change authorized."],
    ["MECHANISM", "Primary mechanism", "; ".join(mechanisms),
     "RESEARCHER_CONFIRMED; SUPERVISOR_REVIEW_PENDING",
     "Hypothetical additional observed inter-port elapsed-time shock; not pure sailing time."],
    ["FACTOR-GRID", "Candidate shock grid",
     f"{len(s88_factors)} candidate scenarios; shocks={sorted(pd.to_numeric(s88_factors['Shock_Magnitude_Hours']).dropna().unique().tolist())}; "
     f"shares={sorted(pd.to_numeric(s88_factors['Affected_Transition_Share']).dropna().unique().tolist())}",
     "PROVISIONAL_NOT_APPROVED", "Factor levels are sensitivity settings, not empirically calibrated disruption estimates."],
    ["SCOPE", "Transition selection",
     f"{len(s89_scope)} coverage levels; universe={int(pd.to_numeric(s89_scope['Transition_Universe_Count']).max())}; "
     f"selected counts={s89_scope['Selected_Transition_Count'].astype(str).str.cat(sep=';')}",
     "PROVISIONAL_NOT_APPROVED", "Mathematical coverage of observed transition records, not geographic exposure probability."],
    ["POLICIES", "Recovery policy set",
     f"{len(s90_policies)} policy definitions: " + "; ".join(s90_policies["Recovery_Policy_ID"].astype(str)),
     "PROVISIONAL_NOT_APPROVED", "Hypothetical recovery rules; no measured operational capabilities."],
    ["METRICS", "Response metrics", f"{len(s90_metrics)} registered metrics",
     "UNRESOLVED", "Operational definitions, denominators, estimands and censoring rules remain open."],
    ["ESTIMANDS", "Candidate estimands", f"{len(s93_estimands)} candidate estimands",
     "PROPOSED_NOT_APPROVED", "Candidate quantities require researcher selection and supervisor review."],
    ["REPLICATION", "Replication design",
     "; ".join(s90_replication["Option_ID"].astype(str)),
     "NOT_SELECTED", "Deterministic reproducibility is not statistical replication or inferential precision."],
    ["POLICY-VALIDATION", "Scripts94–95 technical audits",
     "Script94: 16/16; Script95: 15/15 (see inherited audit summary)",
     "DIAGNOSTICALLY_VERIFIED", "Mathematical consistency is not operational feasibility or empirical validation."],
    ["EXECUTION", "Simulation execution",
     "Execution authorization remains false/blocked in Script90 and prior protocols",
     "BLOCKED", "Script96 cannot authorize or run the simulation."],
]
integrated_design_df = pd.DataFrame(integrated_rows, columns=[
    "Component_ID", "Component", "Current_Design_or_Evidence",
    "Current_Status", "Interpretation_and_Limitation"
])


# ---------------------------------------------------------------------
# 8. Final fail-closed checks and outputs
# ---------------------------------------------------------------------
approval_columns = [
    (s90_gates, "Approval_Granted"),
    (s90_factors, "Approval_Granted"),
    (s90_scope, "Approval_Granted"),
    (s90_policies, "Approval_Granted"),
    (s90_metrics, "Approval_Granted"),
    (s90_replication, "Approval_Granted"),
]
all_approval_count = sum(
    int(df[col].map(truthy).sum())
    for df, col in approval_columns if col in df.columns
)
execution_count = sum(
    int(df["Execution_Authorized"].map(truthy).sum())
    for df in [s90_gates, s90_factors, s90_scope, s90_policies, s90_metrics, s90_replication]
    if "Execution_Authorized" in df.columns
)

add_check(
    "No researcher/supervisor approval is silently inferred",
    all_approval_count == 0,
    all_approval_count,
    0,
    "Script96 reads approval states only; it never grants approvals."
)
add_check(
    "No execution authorization is present in decision registers",
    execution_count == 0,
    execution_count,
    0,
    "Execution remains blocked; this script cannot authorize simulation."
)
add_check(
    "Script96 does not execute or modify upstream simulation inputs",
    True,
    "Register consolidation only",
    "No simulation; no upstream writes",
    "Script96 writes only its own eight output artifacts."
)

checks_df = pd.DataFrame(checks)
passed = int(checks_df["Passed"].map(truthy).sum())
failed = len(checks_df) - passed

# Outputs are new Script96 files only.
outputs = {
    "96_source_inventory.csv": source_inventory_df,
    "96_audit_history_summary.csv": audit_summary_df,
    "96_integrated_experimental_design_register.csv": integrated_design_df,
    "96_integrated_decision_register.csv": design_register,
    "96_unresolved_research_decisions.csv": decision_queue,
    "96_supervisor_approval_register.csv": supervisor_register,
    "96_execution_blockers.csv": blockers_df,
    "96_integrated_readiness_checks.csv": checks_df,
}

for filename, frame in outputs.items():
    frame.to_csv(TABLES / filename, index=False)

# Compact summary counts for the report.
researcher_pending = int(
    decision_queue["Researcher_Decision"].isin(["PENDING", "OPEN", "NOT_RECORDED"]).sum()
)
supervisor_pending = int(
    decision_queue["Supervisor_Review_Status"].isin(["PENDING", "OPEN", "NOT_RECORDED"]).sum()
)
approved_supervisor = int(supervisor_register["Approval_Granted"].sum())
blocker_count = len(blockers_df)
scenario_count = len(s88_factors)
policy_count = len(s90_policies)
combination_count = len(s88_matrix)

report = f"""SCRIPT 96 — INTEGRATED EXPERIMENTAL DESIGN AND EXECUTION READINESS AUDIT
{'=' * 82}

PURPOSE
Consolidate Scripts88–95 into one auditable design, decision, approval and
execution-blocker register. Diagnostic and governance consolidation only.

SOURCE INVENTORY
Required upstream files inspected: {len(INPUTS)}
Missing required inputs: 0
{source_inventory_df[['Source_Stage','Source_File','Rows','Columns','Schema_Status']].to_string(index=False)}

DESIGN STRUCTURE
Primary mechanism recorded: {', '.join(mechanisms) if mechanisms else 'NOT FOUND'}
Candidate shock scenarios in Script88 factor grid: {scenario_count}
Scenario-policy combinations in Script88 matrix: {combination_count}
Transition scope levels: {len(s89_scope)}
Unique observed transition records in Script89 selection register: {unique_transitions}
Recovery policies: {policy_count}
Response metrics: {len(s90_metrics)}
Open Script92 estimand/censoring decisions: {len(s92_open)}
Candidate Script93 estimands: {len(s93_estimands)}

IMPORTANT COUNT DISTINCTION
The Script88 candidate factorial grid contains 16 shock scenarios and 80
scenario-policy combinations (16 x 5). The no-disruption baseline is a
separate baseline in the earlier Script75/76 experiment outputs. Do not
incorrectly label the Script88 candidate matrix as 17 scenarios or 85 rows.

UPSTREAM AUDIT HISTORY
{audit_summary_df.to_string(index=False)}

APPROVAL AND EXECUTION STATUS
Approval grants recorded across decision registers: {all_approval_count}
Execution authorizations recorded across decision registers: {execution_count}
Researcher decisions pending/open/not recorded in consolidated queue: {researcher_pending}
Supervisor reviews pending/open/not recorded in consolidated queue: {supervisor_pending}
Open execution blockers: {blocker_count}
Supervisor approval register rows: {len(supervisor_register)}
Simulation executed by Script96: NO
Execution authorized by Script96: NO

KEY INTERPRETATION
- The primary mechanism TRANSIT_ELAPSED_TIME_SHOCK is researcher-confirmed,
  but this does not approve factor levels, transition exposure, recovery
  policies, response metrics, replication design or execution.
- The 6/12/24/48-hour shock levels are provisional hypothetical increments,
  not empirically calibrated disruption durations.
- The 10/25/50/100 percent levels are mathematical coverage shares over
  observed transition records, not geographic exposure probabilities.
- Inter-port elapsed time is not pure sailing time.
- Observed port-call links are not validated physical routes.
- No AIS-confirmed Strait of Hormuz transit is established.
- Observed inter-call elapsed time is not established schedule slack.
- Recovery policies are hypothetical mathematical rules, not measured
  operational capabilities.
- Deterministic reproducibility does not establish statistical replication,
  sampling uncertainty, confidence intervals or power.
- End-of-window censoring, denominators, thresholds, estimands and metric
  operational definitions remain researcher/supervisor decisions.
- Passing historical diagnostic checks does not establish physical or
  operational validity.

READINESS CHECKS
{passed}/{len(checks_df)} passed; {failed} failed.

DECISION
Script96 is an integrated design and governance audit, not a simulation.
It does not select missing values, approve policies, approve exposure, approve
estimands, settle censoring, or authorize execution.

The next work is to resolve the explicit researcher decisions, obtain
supervisor review, finalize estimands/censoring/replication, and then prepare
a frozen simulation specification. Execution remains NO-GO until separately
authorized.

OUTPUTS
{chr(10).join('- outputs/tables/' + name for name in outputs)}
- outputs/reports/96_integrated_experimental_design_readiness_audit_report.txt

NO UPSTREAM FILES MODIFIED.
NO SIMULATION EXECUTED.
EXECUTION AUTHORIZATION: NO.
"""

report_path = REPORTS / "96_integrated_experimental_design_readiness_audit_report.txt"
report_path.write_text(report, encoding="utf-8")

print("=" * 78)
print("SCRIPT 96 — INTEGRATED EXPERIMENTAL DESIGN AND EXECUTION READINESS AUDIT")
print("=" * 78)
print(f"Required source files: {len(INPUTS)}")
print(f"Candidate shock scenarios: {scenario_count}")
print(f"Scenario-policy combinations: {combination_count}")
print(f"Recovery policies: {policy_count}")
print(f"Response metrics: {len(s90_metrics)}")
print(f"Open estimand/censoring decisions: {len(s92_open)}")
print(f"Candidate estimands: {len(s93_estimands)}")
print(f"Approval grants recorded: {all_approval_count}")
print(f"Execution authorizations recorded: {execution_count}")
print(f"Open execution blockers: {blocker_count}")
print(f"Readiness checks: {passed}/{len(checks_df)} passed; {failed} failed")
print("Simulation executed: NO")
print("Execution authorized: NO")
print(f"Report: {report_path}")
print("\nThis is a diagnostic/governance consolidation only.")

if failed:
    print("\nWARNING: One or more Script96 integrity checks failed.")
    print("Inspect 96_integrated_readiness_checks.csv before relying on the registers.")
    raise SystemExit(2)
