#!/usr/bin/env python3
"""
SCRIPT 97 — RESEARCH DECISION RESOLUTION FRAMEWORK
Governance/template generator only. Does not make researcher decisions,
supervisor approvals, or execution authorizations.
"""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"
TABLES.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

INPUTS = {
    "open_decisions": TABLES / "92_open_estimand_and_censoring_decisions.csv",
    "metric_register": TABLES / "90_response_metric_decision_register.csv",
    "policy_register": TABLES / "90_recovery_policy_decision_register.csv",
    "replication_register": TABLES / "90_replication_decision_register.csv",
    "estimands": TABLES / "93_candidate_estimand_register.csv",
    "approval_gates": TABLES / "90_approval_gate_register.csv",
}

def read_csv(path, label):
    if not path.exists():
        raise FileNotFoundError(
            f"Required input missing for {label}: {path}\n"
            "Copy the exact upstream output into outputs/tables/; do not create "
            "or rename a substitute file."
        )
    return pd.read_csv(path)

def require_columns(df, cols, label):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{label}: missing required columns: {missing}")

def main():
    src = {k: read_csv(v, k) for k, v in INPUTS.items()}
    require_columns(src["open_decisions"],
                    ["Decision_ID", "Topic", "Decision_Required", "Decision_Owner"],
                    "92 open decisions")
    require_columns(src["metric_register"],
                    ["Metric_ID", "Metric", "Aggregation_Level", "Definition_or_Caveat"],
                    "90 metric register")
    require_columns(src["policy_register"],
                    ["Recovery_Policy_ID", "Recovery_Policy", "Policy_Type",
                     "Recovery_Interpretation", "Policy_Interpretation_Limit"],
                    "90 policy register")
    require_columns(src["replication_register"],
                    ["Option_ID", "Option", "Definition", "Required_Decision"],
                    "90 replication register")
    require_columns(src["estimands"],
                    ["Estimand_ID"], "93 candidate estimands")
    require_columns(src["approval_gates"],
                    ["Gate_ID", "Decision_Area", "Current_Proposal"], "90 approval gates")

    # Recommendations are advisory prompts only. No selected value is populated.
    recommendations = {
        "D01": ("Use actual arrival/departure timestamps as the observed baseline reference, "
                "with the corresponding historical call timestamp as the comparison point. "
                "Keep missing actual timestamps missing; do not substitute planned/estimated times."),
        "D02": ("Retain signed delay values for the primary descriptive record, but report "
                "nonnegative delay as a separately defined sensitivity view if early events occur. "
                "Do not silently clip values."),
        "D03": ("Use a common, explicitly defined eligible-call cohort across paired policy "
                "comparisons. Exclude only records that fail predeclared timestamp/sequence "
                "requirements, and report exclusions and denominators."),
        "D04": ("Define a vessel as eligible only when its final represented call can be "
                "evaluated within the common observation horizon. Distinguish the last "
                "represented call in the dataset from a vessel's true final voyage call."),
        "D05": ("Keep M03B distinct from final-call delay: define it as the sum of call-level "
                "departure delays across eligible calls for each vessel, if cumulative burden "
                "is the intended construct. Label it accumulated call-delay, not final delay."),
        "D06": ("Predeclare a named quantile convention (for example, NumPy/pandas linear "
                "interpolation) and include zero-delay calls in the eligible cohort. Report "
                "the denominator and quantile method."),
        "D07": ("Pair each recovered scenario-policy call with its no-recovery counterpart "
                "using stable scenario, policy-comparison, vessel and call identifiers. "
                "Define credit as paired no-recovery delay minus recovered delay; retain "
                "negative differences rather than hiding countervailing outcomes."),
        "D08": ("Do not finalize an unrecovered threshold until the delay reference and "
                "observation horizon are fixed. A defensible candidate is residual delay > 0 "
                "at the defined evaluation time, with threshold sensitivity reported."),
        "D09": ("Use one common, predeclared observation horizon for all scenarios and policies. "
                "Specify whether completion means all represented calls or all eligible vessel "
                "sequences have reached their evaluation point."),
        "D10": ("Treat unfinished calls/vessels at the horizon as right-censored or incomplete, "
                "not as recovered or zero-delay. Report their counts and apply a declared "
                "estimand-specific handling rule."),
        "D11": ("Separate the metrics by construct: M02 average call-level departure burden; "
                "M03A worst vessel final-call outcome; M03B cumulative call-level burden per "
                "vessel; M04 average vessel final-call outcome; M05 upper-tail call-level burden."),
        "D12": ("Restrict conclusions to conditional outputs of the specified hypothetical "
                "model. Do not claim actual Hormuz exposure, operational feasibility, real-world "
                "delay reduction or causal impact without independent evidence and validation."),
    }

    dependencies = {
        "D01": "D03, D04, D05, D07, D08, D11",
        "D02": "D05, D06, D08, D11",
        "D03": "D04, D06, D07, D09, D10",
        "D04": "D09, D10, D11",
        "D05": "D02, D03, D04, D09, D10",
        "D06": "D02, D03, D09, D10",
        "D07": "D01, D03, D09, D10",
        "D08": "D01, D02, D09, D10",
        "D09": "D03, D04, D05, D06, D07, D08, D10",
        "D10": "D03, D04, D07, D08, D09",
        "D11": "D01, D02, D03, D04, D05, D06, D09, D10",
        "D12": "All decisions; governs interpretation and reporting",
    }

    decision_rows = []
    for _, r in src["open_decisions"].iterrows():
        did = str(r["Decision_ID"])
        decision_rows.append({
            "Decision_ID": did,
            "Topic": r["Topic"],
            "Decision_Required": r["Decision_Required"],
            "Decision_Owner": r["Decision_Owner"],
            "Advisory_Recommendation_NOT_A_DECISION": recommendations.get(did, ""),
            "Recommendation_Rationale_or_Caution": (
                "Methodological recommendation for discussion only; verify against the "
                "actual model implementation and supervisor guidance."
            ),
            "Dependencies": dependencies.get(did, ""),
            "Researcher_Decision": "PENDING",
            "Researcher_Selected_Value": "",
            "Researcher_Justification": "",
            "Supervisor_Review_Status": "PENDING",
            "Supervisor_Comments": "",
            "Approval_Granted": False,
            "Approval_Date": "",
            "Execution_Authorized": False,
            "Decision_Status": "OPEN_NOT_APPROVED",
        })
    decisions = pd.DataFrame(decision_rows)

    metric_rows = []
    for _, r in src["metric_register"].iterrows():
        metric_rows.append({
            "Metric_ID": r["Metric_ID"],
            "Metric": r["Metric"],
            "Aggregation_Level": r["Aggregation_Level"],
            "Existing_Definition_or_Caveat": r["Definition_or_Caveat"],
            "Operational_Definition_Selected": "",
            "Denominator_and_Eligibility_Rule": "",
            "Observation_Timepoint": "",
            "Censoring_Rule": "",
            "Researcher_Decision": "PENDING",
            "Supervisor_Review_Status": "PENDING",
            "Approval_Granted": False,
            "Execution_Authorized": False,
        })
    metrics = pd.DataFrame(metric_rows)

    policy_rows = []
    for _, r in src["policy_register"].iterrows():
        policy_rows.append({
            "Recovery_Policy_ID": r["Recovery_Policy_ID"],
            "Recovery_Policy": r["Recovery_Policy"],
            "Policy_Type": r["Policy_Type"],
            "Existing_Interpretation": r["Recovery_Interpretation"],
            "Interpretation_Limit": r["Policy_Interpretation_Limit"],
            "Researcher_Decision": "PENDING",
            "Researcher_Selected_Value": "",
            "Researcher_Justification": "",
            "Supervisor_Review_Status": "PENDING",
            "Supervisor_Comments": "",
            "Approval_Granted": False,
            "Operational_Feasibility_Established": False,
            "Execution_Authorized": False,
        })
    policies = pd.DataFrame(policy_rows)

    replication_rows = []
    for _, r in src["replication_register"].iterrows():
        replication_rows.append({
            "Option_ID": r["Option_ID"],
            "Option": r["Option"],
            "Definition": r["Definition"],
            "Required_Decision": r["Required_Decision"],
            "Researcher_Decision": "PENDING",
            "Researcher_Selected_Value": "",
            "Researcher_Justification": "",
            "Supervisor_Review_Status": "PENDING",
            "Supervisor_Comments": "",
            "Approval_Granted": False,
            "Execution_Authorized": False,
        })
    replications = pd.DataFrame(replication_rows)

    out = {
        "97_research_decision_resolution_register.csv": decisions,
        "97_metric_operationalization_decision_register.csv": metrics,
        "97_recovery_policy_decision_register.csv": policies,
        "97_replication_decision_register.csv": replications,
    }
    for name, df in out.items():
        df.to_csv(TABLES / name, index=False)

    report = [
        "SCRIPT 97 — RESEARCH DECISION RESOLUTION FRAMEWORK",
        "=" * 78,
        "",
        "PURPOSE",
        "Generate editable decision registers for researcher and supervisor review.",
        "This script does not decide, approve, authorize or execute the experiment.",
        "",
        f"Open estimand/censoring decisions imported: {len(decisions)}",
        f"Response metrics imported: {len(metrics)}",
        f"Recovery policies imported: {len(policies)}",
        f"Replication options imported: {len(replications)}",
        "",
        "GOVERNANCE STATUS",
        "All researcher decisions remain PENDING.",
        "All supervisor reviews remain PENDING.",
        "All approval grants remain FALSE.",
        "All execution authorizations remain FALSE.",
        "",
        "IMPORTANT",
        "The advisory recommendations are not decisions. The researcher must select,",
        "justify and document values; supervisor review must be recorded separately.",
        "Do not infer approval from generated files or successful script execution.",
        "",
        "OUTPUTS",
        *[f"- outputs/tables/{name}" for name in out],
        "",
        "NO UPSTREAM FILES MODIFIED.",
        "NO SIMULATION EXECUTED.",
        "EXECUTION AUTHORIZATION: NO.",
    ]
    report_path = REPORTS / "97_research_decision_resolution_framework_report.txt"
    report_path.write_text("\n".join(report), encoding="utf-8")

    print("=" * 78)
    print("SCRIPT 97 — RESEARCH DECISION RESOLUTION FRAMEWORK")
    print("=" * 78)
    print(f"Open decisions: {len(decisions)}")
    print(f"Metrics: {len(metrics)}")
    print(f"Recovery policies: {len(policies)}")
    print(f"Replication options: {len(replications)}")
    print("Researcher decisions populated: 0")
    print("Supervisor approvals recorded: 0")
    print("Execution authorized: NO")
    print(f"Report: {report_path}")
    print("Governance/template generation only; no simulation executed.")

if __name__ == "__main__":
    main()
