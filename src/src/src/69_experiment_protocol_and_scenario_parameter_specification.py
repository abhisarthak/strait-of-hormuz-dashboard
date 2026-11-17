#!/usr/bin/env python3
"""
SCRIPT 69: EXPERIMENT PROTOCOL AND SCENARIO PARAMETER SPECIFICATION REGISTER

Creates an auditable, researcher-editable protocol specification from Scripts 65, 66 and 68.
This is a design-stage artifact only. It does not run a simulation, select disruption magnitudes,
approve experiment scopes, authorize resampling, or modify upstream inputs.

Run from project root:
    python src/69_experiment_protocol_and_scenario_parameter_specification.py

Required inputs:
    outputs/tables/65_parameter_option_register.csv
    outputs/tables/66_experiment_design_matrix.csv
    outputs/tables/68_mechanism_decision_register.csv
    outputs/tables/68_edge_exposure_decision_register.csv
    outputs/tables/68_port_exposure_decision_register.csv
    outputs/tables/68_experiment_scope_decision_matrix.csv

Outputs:
    outputs/tables/69_experiment_protocol_register.csv
    outputs/tables/69_scenario_parameter_specification.csv
    outputs/tables/69_parameter_evidence_summary.csv
    outputs/tables/69_response_metric_protocol.csv
    outputs/tables/69_replication_protocol_options.csv
    outputs/tables/69_protocol_readiness_checks.csv
    outputs/reports/69_experiment_protocol_specification_report.txt

No numeric disruption magnitudes or replication counts are selected. All researcher choices remain pending.
"""

from pathlib import Path
import sys
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"

INPUTS = {
    "parameters": TABLES / "65_parameter_option_register.csv",
    "design": TABLES / "66_experiment_design_matrix.csv",
    "mechanisms": TABLES / "68_mechanism_decision_register.csv",
    "edges": TABLES / "68_edge_exposure_decision_register.csv",
    "ports": TABLES / "68_port_exposure_decision_register.csv",
    "scope": TABLES / "68_experiment_scope_decision_matrix.csv",
}
OUTPUTS = {
    "protocol": TABLES / "69_experiment_protocol_register.csv",
    "scenario": TABLES / "69_scenario_parameter_specification.csv",
    "evidence": TABLES / "69_parameter_evidence_summary.csv",
    "metrics": TABLES / "69_response_metric_protocol.csv",
    "replication": TABLES / "69_replication_protocol_options.csv",
    "checks": TABLES / "69_protocol_readiness_checks.csv",
    "report": REPORTS / "69_experiment_protocol_specification_report.txt",
}

def stop(message):
    print(f"ERROR: {message}")
    sys.exit(1)

def read_input(key):
    path = INPUTS[key]
    if not path.exists():
        stop(f"Missing required input: {path}")
    try:
        return pd.read_csv(path, low_memory=False)
    except Exception as exc:
        stop(f"Unable to read {path.name}: {exc}")

def need(df, cols, name):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        stop(f"{name} missing columns: {missing}")

def bool_series(df, col):
    return df[col].fillna(False).astype(bool)

def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    p65 = read_input("parameters")
    d66 = read_input("design")
    m68 = read_input("mechanisms")
    e68 = read_input("edges")
    p68 = read_input("ports")
    s68 = read_input("scope")

    need(p65, ["Previous_Port", "Next_Port", "Assignment_Classification_64",
               "Parameter_Treatment_65", "Observed_Median_Reference_Hours_65",
               "Observed_P90_Reference_Hours_65", "Observed_Max_Reference_Hours_65",
               "Final_Selected_Value_Hours_65", "Researcher_Decision_Status_65",
               "Empirical_Resampling_Approved_65", "Parametric_Distribution_Approved_65"],
         INPUTS["parameters"].name)
    need(d66, ["Experiment_ID_66", "Experiment_Family_66", "Mechanism_66",
               "Severity_Level_66", "Duration_Level_66", "Onset_Rule_66",
               "Affected_Scope_66", "Recovery_Policy_66", "Port_Service_Response_66",
               "Replication_Design_66", "Status_66", "Required_Approval_66"],
         INPUTS["design"].name)
    need(m68, ["Mechanism", "Researcher_Mechanism_Decision", "Approved_For_Experiment"],
         INPUTS["mechanisms"].name)
    need(e68, ["Previous_Port", "Next_Port", "Researcher_Edge_Decision",
               "Approved_For_Hypothetical_Exposure", "Geographic_Route_Validated_67"],
         INPUTS["edges"].name)
    need(p68, ["UNLOCODE_Normalised", "Researcher_Port_Decision",
               "Approved_For_Hypothetical_Port_Disruption"],
         INPUTS["ports"].name)
    need(s68, ["Experiment_ID", "Disruption_Mechanism", "Researcher_Scope_Decision",
               "Approved_To_Proceed", "Blocking_or_Required_Evidence"],
         INPUTS["scope"].name)

    # Source integrity and cross-register reconciliation.
    if len(p65) != 53 or p65[["Previous_Port", "Next_Port"]].duplicated().any():
        stop("Script65 parameter register must contain 53 unique directed edges.")
    if len(d66) != 5 or d66["Experiment_ID_66"].duplicated().any():
        stop("Script66 design matrix must contain five unique experiment templates.")
    if len(m68) != 4 or m68["Mechanism"].duplicated().any():
        stop("Script68 mechanism register must contain four unique mechanisms.")
    if len(e68) != 53 or e68[["Previous_Port", "Next_Port"]].duplicated().any():
        stop("Script68 edge register must contain 53 unique directed edges.")
    if len(p68) != 19 or p68["UNLOCODE_Normalised"].duplicated().any():
        stop("Script68 port register must contain 19 unique ports.")
    if len(s68) != 5 or s68["Experiment_ID"].duplicated().any():
        stop("Script68 experiment scope matrix must contain five unique templates.")

    p65_keys = set(zip(p65.Previous_Port.astype(str), p65.Next_Port.astype(str)))
    e68_keys = set(zip(e68.Previous_Port.astype(str), e68.Next_Port.astype(str)))
    if p65_keys != e68_keys:
        stop("Script65 and Script68 directed edge sets do not match.")
    if set(d66.Experiment_ID_66.astype(str)) != set(s68.Experiment_ID.astype(str)):
        stop("Script66 and Script68 experiment IDs do not match.")
    if not m68["Approved_For_Experiment"].eq(False).all():
        stop("Unexpected mechanism approval found; manual review required before protocol generation.")
    if not e68["Approved_For_Hypothetical_Exposure"].eq(False).all():
        stop("Unexpected edge exposure approval found; manual review required.")
    if not p68["Approved_For_Hypothetical_Port_Disruption"].eq(False).all():
        stop("Unexpected port exposure approval found; manual review required.")
    if not s68["Approved_To_Proceed"].eq(False).all():
        stop("Unexpected experiment scope approval found; manual review required.")

    # Evidence summary: descriptive statistics are carried forward, never converted into selected parameters.
    evidence = (p65.groupby(["Assignment_Classification_64", "Parameter_Treatment_65"], dropna=False)
                .agg(Directed_Edge_Count=("Previous_Port", "size"),
                     Edges_With_Median_Reference=("Observed_Median_Reference_Hours_65", "count"),
                     Edges_With_P90_Reference=("Observed_P90_Reference_Hours_65", "count"),
                     Edges_With_Max_Reference=("Observed_Max_Reference_Hours_65", "count"),
                     Edges_With_Final_Selected_Value=("Final_Selected_Value_Hours_65", "count"),
                     Edges_With_Resampling_Approval=("Empirical_Resampling_Approved_65", "sum"),
                     Edges_With_Parametric_Approval=("Parametric_Distribution_Approved_65", "sum"))
                .reset_index())
    evidence["Interpretation"] = (
        "Evidence classification only; descriptive reference quantiles are not selected disruption parameters."
    )

    # Explicitly unassigned scenario parameter fields. Factor names derive from Script66 templates.
    scenario_rows = []
    for _, row in d66.iterrows():
        exp = str(row["Experiment_ID_66"])
        mech = str(row["Mechanism_66"])
        scope_row = s68.loc[s68["Experiment_ID"].astype(str) == exp].iloc[0]
        if exp == "E66-00":
            factor_rows = [
                ("Baseline definition", "Historical replay reference", "604-call historical schedule", "NOT_APPLICABLE"),
                ("Observation window", "Common historical window", str(row["Onset_Rule_66"]), "RESEARCHER_CONFIRMATION_REQUIRED"),
            ]
            gate = "BASELINE_REPLAY_CONFIRMATION"
        elif mech == "TRANSIT_ELAPSED_TIME_SHOCK":
            factor_rows = [
                ("Affected process", "Inter-port elapsed time", "Includes sailing, waiting and unobserved operations; not pure sailing time", "DEFINE_OPERATIONAL_INTERPRETATION"),
                ("Shock unit", "Hours or proportional change", "No unit selected", "NOT_SELECTED"),
                ("Severity levels", "Researcher-defined ordered levels", "No numerical values selected", "NOT_SELECTED"),
                ("Duration", "Researcher-defined duration", "No duration selected", "NOT_SELECTED"),
                ("Onset", "Researcher-defined onset rule", "No onset rule selected", "NOT_SELECTED"),
                ("Affected scope", "Explicit edge/vessel list", "No edge or vessel approved", "NOT_APPROVED"),
                ("Recovery policy", "Compare defined recovery policies", "Policy set to be specified", "NOT_SELECTED"),
            ]
            gate = "MECHANISM_AND_EDGE_SCOPE_APPROVAL_REQUIRED"
        elif mech == "NETWORK_ACCESS_RESTRICTION":
            factor_rows = [
                ("Physical route representation", "Validated geographic route graph", "Not established", "BLOCKED"),
                ("Affected route", "Explicit validated route/edge list", "Observed schedule edges are not physical routes", "BLOCKED"),
                ("Alternative paths", "Feasible alternative routes", "Not established", "BLOCKED"),
                ("Severity/duration/onset", "Only after route feasibility", "No values selected", "BLOCKED"),
            ]
            gate = "BLOCKED_PENDING_ROUTE_AND_ALTERNATIVE_FEASIBILITY"
        elif mech == "PORT_SERVICE_DISRUPTION":
            factor_rows = [
                ("Affected service", "Explicit port service/function", "Not defined", "NOT_SELECTED"),
                ("Service-time proxy", "Observed port stay", "Not equivalent to berth processing time", "PROXY_LIMITATION"),
                ("Capacity", "Port/berth capacity", "Evidence unavailable", "BLOCKED_FOR_CAPACITY_CLAIMS"),
                ("Severity levels", "Researcher-defined ordered levels", "No numerical values selected", "NOT_SELECTED"),
                ("Duration/onset", "Researcher-defined", "No values selected", "NOT_SELECTED"),
                ("Affected scope", "Explicit port list", "No port approved", "NOT_APPROVED"),
            ]
            gate = "SERVICE_PROCESS_AND_PORT_SCOPE_EVIDENCE_REQUIRED"
        else:
            factor_rows = [
                ("Component mechanisms", "Individually specified mechanisms", "Single mechanisms not yet approved", "DEFERRED"),
                ("Combined scope", "Explicit component scope", "Not defined", "DEFERRED"),
                ("Interaction rule", "Explicit interaction assumption", "Not defined", "DEFERRED"),
            ]
            gate = "DEFER_UNTIL_SINGLE_MECHANISMS_DEFINED"

        for factor, candidate_definition, evidence_limit, status in factor_rows:
            scenario_rows.append({
                "Experiment_ID": exp,
                "Experiment_Family": row["Experiment_Family_66"],
                "Mechanism": mech,
                "Parameter_or_Design_Factor": factor,
                "Candidate_Definition": candidate_definition,
                "Evidence_or_Limitation": evidence_limit,
                "Script66_Severity_Template": row["Severity_Level_66"],
                "Script66_Duration_Template": row["Duration_Level_66"],
                "Script66_Onset_Template": row["Onset_Rule_66"],
                "Script66_Affected_Scope_Template": row["Affected_Scope_66"],
                "Script66_Recovery_Template": row["Recovery_Policy_66"],
                "Script68_Scope_Decision": scope_row["Researcher_Scope_Decision"],
                "Script68_Approved_To_Proceed": bool(scope_row["Approved_To_Proceed"]),
                "Script69_Factor_Status": status,
                "Researcher_Selected_Value": "",
                "Researcher_Justification": "",
                "Evidence_URL_or_Citation": "",
                "Reviewer": "",
                "Review_Date": "",
                "Protocol_Gate": gate,
            })
    scenario = pd.DataFrame(scenario_rows)

    # Experiment protocol register: no run authorization.
    protocol_rows = []
    for _, row in d66.iterrows():
        exp = str(row["Experiment_ID_66"])
        sc = s68.loc[s68["Experiment_ID"].astype(str) == exp].iloc[0]
        protocol_rows.append({
            "Experiment_ID": exp,
            "Experiment_Family": row["Experiment_Family_66"],
            "Mechanism": row["Mechanism_66"],
            "Script66_Status": row["Status_66"],
            "Script68_Guidance": sc.get("Script68_Conservative_Guidance", ""),
            "Researcher_Scope_Decision": sc["Researcher_Scope_Decision"],
            "Approved_To_Proceed": bool(sc["Approved_To_Proceed"]),
            "Protocol_Status": "SPECIFICATION_PENDING_RESEARCHER_REVIEW",
            "Baseline_Reference": row["Affected_Scope_66"] if exp == "E66-00" else "NOT_APPLICABLE",
            "Exposure_Unit": "",
            "Severity_Levels": "",
            "Duration_Levels": "",
            "Onset_Rule": "",
            "Affected_Edge_or_Port_List": "",
            "Recovery_Policies": row["Recovery_Policy_66"],
            "Replication_Count": "",
            "Random_Seed_Policy": "",
            "Common_Random_Numbers": "",
            "Warmup_or_Observation_Window": row["Onset_Rule_66"],
            "Primary_Outcome": "",
            "Secondary_Outcomes": "",
            "Statistical_Comparison": "",
            "Required_Approval_or_Evidence": row["Required_Approval_66"],
            "Script69_Execution_Authorization": False,
        })
    protocol = pd.DataFrame(protocol_rows)

    # Metric protocol: explicit definitions and caution, including Script66 refinements.
    metric_specs = [
        ("M01", "Mean final delay per affected call", "Call-level", "Mean of final delay over affected calls at the defined observation horizon.", "Specify horizon and treatment of calls arriving after the window.", "PRIMARY_CANDIDATE"),
        ("M02", "Maximum final delay per vessel", "Vessel-level", "Maximum final delay among vessels in the defined cohort.", "Do not confuse with accumulated delay across calls.", "PRIMARY_CANDIDATE"),
        ("M03A", "Maximum final vessel delay", "Vessel-level", "Maximum final delay across vessels at the observation horizon.", "Separate from accumulated delay; define final horizon.", "REQUIRES_SCRIPT66_METRIC_REFINEMENT"),
        ("M03B", "Maximum accumulated delay per vessel", "Vessel-level", "Maximum sum of delay accrued by an individual vessel across its affected calls.", "Do not use call-level sum as a vessel-level measure.", "REQUIRES_SCRIPT66_METRIC_REFINEMENT"),
        ("M04", "Total accumulated call delay", "Call-level aggregate", "Sum of delay over affected calls.", "Not a count of unique delayed vessels.", "SECONDARY_CANDIDATE"),
        ("M05", "Peak concurrent calls", "Network/port time series", "Maximum simultaneous active calls under the replay definition.", "Not berth occupancy or validated physical capacity.", "SECONDARY_CANDIDATE"),
        ("M06", "Time above concurrency threshold", "Network/port time series", "Duration concurrency exceeds a predeclared threshold.", "Threshold and time aggregation must be specified before analysis.", "SECONDARY_CANDIDATE"),
        ("M07A", "Unrecovered calls", "Call-level", "Affected calls not recovered by the defined observation horizon.", "Define recovery criterion and right-censoring at end of window.", "REQUIRES_SCRIPT66_METRIC_REFINEMENT"),
        ("M07B", "Unrecovered vessels", "Vessel-level", "Affected vessels with at least one unrecovered affected call at the defined horizon.", "Define vessel cohort and end-window censoring.", "REQUIRES_SCRIPT66_METRIC_REFINEMENT"),
        ("M08", "Recovery time", "Call/vessel-level", "Elapsed time from disruption onset to meeting the predeclared recovery criterion.", "Specify recovery criterion and handling of never-recovered units.", "SECONDARY_CANDIDATE"),
        ("M09", "Port-level delay distribution", "Port-level", "Distribution of delay across affected calls grouped by port.", "Port call count is not berth capacity or throughput capacity.", "SECONDARY_CANDIDATE"),
        ("M10", "Scenario-level robustness", "Replication-level", "Distribution and uncertainty of outcomes across independent replications.", "Requires selected replication count, seed policy and estimand.", "SECONDARY_CANDIDATE"),
    ]
    metrics = pd.DataFrame(metric_specs, columns=[
        "Metric_ID", "Metric_Name", "Analysis_Unit", "Operational_Definition",
        "Required_Definition_or_Caution", "Protocol_Status"
    ])
    metrics["Researcher_Approved"] = False
    metrics["Primary_or_Secondary_Selection"] = "PENDING_RESEARCHER_DECISION"
    metrics["Aggregation_and_Horizon"] = ""
    metrics["Reviewer"] = ""
    metrics["Review_Date"] = ""

    # Replication options are options, not selections. Script66 says TO_BE_SELECTED.
    replication = pd.DataFrame([
        ("R1", "Deterministic replay", "Single deterministic replay where model and inputs are deterministic.", "Baseline consistency/reference only.", "Not selected; confirm model determinism."),
        ("R2", "Independent random seeds", "Independent replications with predeclared distinct seeds.", "Estimate stochastic outcome variability.", "Replication count and seed list not selected."),
        ("R3", "Common random numbers", "Use matched random streams across policies/scenarios where technically valid.", "Improve paired comparison precision by reducing simulation noise.", "Requires implementation validation; not selected."),
        ("R4", "Paired scenario replications", "Compare policies/scenarios under matched replication seeds.", "Supports paired statistical contrasts.", "Requires common seed design and predeclared estimand."),
    ], columns=["Option_ID", "Replication_Option", "Definition", "Potential_Purpose", "Selection_Status"])
    replication["Researcher_Selected"] = False
    replication["Replication_Count"] = ""
    replication["Seed_Range_or_List"] = ""
    replication["Pairing_Key"] = ""
    replication["Statistical_Analysis_Plan"] = ""
    replication["Researcher_Rationale"] = ""
    replication["Reviewer"] = ""
    replication["Review_Date"] = ""

    # Checks validate preservation and no accidental approval.
    checks = []
    def ck(name, passed, observed, expected, note):
        checks.append({"Check": name, "Passed": bool(passed), "Observed": observed,
                       "Expected": expected, "Interpretation": note})
    ck("Script65 has 53 unique directed edges", len(p65) == 53 and not p65.duplicated(["Previous_Port","Next_Port"]).any(), len(p65), 53, "Parameter evidence coverage.")
    ck("Script68 edge register matches Script65", p65_keys == e68_keys, len(e68_keys), len(p65_keys), "Exact directed-pair match.")
    ck("Script66 contains five experiment templates", len(d66) == 5 and d66.Experiment_ID_66.nunique() == 5, len(d66), 5, "Template completeness.")
    ck("Script68 scope IDs match Script66", set(d66.Experiment_ID_66.astype(str)) == set(s68.Experiment_ID.astype(str)), len(s68), len(d66), "Experiment-level lineage.")
    ck("Four mechanism decisions remain unapproved", len(m68) == 4 and not m68.Approved_For_Experiment.any(), int(m68.Approved_For_Experiment.sum()), 0, "No mechanism approvals imported.")
    ck("All 53 edge exposure decisions remain unapproved", len(e68) == 53 and not e68.Approved_For_Hypothetical_Exposure.any(), int(e68.Approved_For_Hypothetical_Exposure.sum()), 0, "No edge exposure approvals imported.")
    ck("All 19 port exposure decisions remain unapproved", len(p68) == 19 and not p68.Approved_For_Hypothetical_Port_Disruption.any(), int(p68.Approved_For_Hypothetical_Port_Disruption.sum()), 0, "No port exposure approvals imported.")
    ck("All five experiment scopes remain unapproved", len(s68) == 5 and not s68.Approved_To_Proceed.any(), int(s68.Approved_To_Proceed.sum()), 0, "No experiment scope approvals imported.")
    ck("No final Script65 parameter values selected", p65.Final_Selected_Value_Hours_65.isna().all(), int(p65.Final_Selected_Value_Hours_65.notna().sum()), 0, "Observed quantiles remain descriptive references.")
    ck("No empirical resampling approvals", not p65.Empirical_Resampling_Approved_65.fillna(False).astype(bool).any(), int(p65.Empirical_Resampling_Approved_65.fillna(False).sum()), 0, "No resampling authorization.")
    ck("No parametric distribution approvals", not p65.Parametric_Distribution_Approved_65.fillna(False).astype(bool).any(), int(p65.Parametric_Distribution_Approved_65.fillna(False).sum()), 0, "No parametric fitting authorization.")
    ck("Network access restriction remains blocked", s68.loc[s68.Experiment_ID.astype(str)=="E66-02","Script68_Conservative_Guidance"].iloc[0] == "BLOCKED_PENDING_VALIDATED_ROUTE_GRAPH", "BLOCKED_PENDING_VALIDATED_ROUTE_GRAPH", "BLOCKED_PENDING_VALIDATED_ROUTE_GRAPH", "No physical route closure inferred.")
    ck("Compound experiment remains deferred", s68.loc[s68.Experiment_ID.astype(str)=="E66-04","Script68_Conservative_Guidance"].iloc[0] == "DEFERRED", "DEFERRED", "DEFERRED", "No compound mechanism before standalone definitions.")
    ck("Scenario numeric values remain unassigned", scenario["Researcher_Selected_Value"].eq("").all(), int((scenario["Researcher_Selected_Value"]!="").sum()), 0, "No disruption magnitude assigned.")
    ck("Replication choices remain unselected", not replication["Researcher_Selected"].any(), int(replication["Researcher_Selected"].sum()), 0, "Options only; Script66 left design to be selected.")
    ck("No experiment execution authorized", not protocol["Script69_Execution_Authorization"].any(), int(protocol["Script69_Execution_Authorization"].sum()), 0, "This script specifies protocol; it does not execute experiments.")
    check_df = pd.DataFrame(checks)

    protocol.to_csv(OUTPUTS["protocol"], index=False)
    scenario.to_csv(OUTPUTS["scenario"], index=False)
    evidence.to_csv(OUTPUTS["evidence"], index=False)
    metrics.to_csv(OUTPUTS["metrics"], index=False)
    replication.to_csv(OUTPUTS["replication"], index=False)
    check_df.to_csv(OUTPUTS["checks"], index=False)

    passed = int(check_df.Passed.sum())
    report = f"""================================================================================
SCRIPT 69: EXPERIMENT PROTOCOL AND SCENARIO PARAMETER SPECIFICATION
================================================================================

INPUTS
Script65 directed-edge parameter records: {len(p65)}
Script66 experiment templates: {len(d66)}
Script68 mechanism decisions: {len(m68)}
Script68 edge decisions: {len(e68)}
Script68 port decisions: {len(p68)}
Script68 experiment scope decisions: {len(s68)}

OUTPUTS
Experiment protocol rows: {len(protocol)}
Scenario factor specification rows: {len(scenario)}
Parameter evidence summary rows: {len(evidence)}
Response metric specifications: {len(metrics)}
Replication protocol options: {len(replication)}
Readiness checks passed: {passed}/{len(check_df)}

KEY DESIGN CONSTRAINTS
- No disruption magnitudes, duration values, onset values or affected scopes selected.
- No Script65 final parameter values selected.
- No empirical resampling or parametric distributions approved.
- Network access restriction remains blocked pending validated geographic routes and feasible alternatives.
- Port service disruption remains constrained by the absence of berth processing/capacity evidence.
- Compound disruption remains deferred until single mechanisms are separately defined.
- Replication count, seed policy, common random numbers and statistical estimands remain researcher decisions.
- M03 split into maximum final vessel delay and maximum accumulated delay per vessel.
- M07 split into unrecovered calls and unrecovered vessels; end-window censoring must be defined.

INTERPRETATION
This is a protocol specification and decision-support artifact only. It does not run simulation,
select parameter values, approve experiment scope, or modify Script19 inputs.
Observed inter-port elapsed time includes sailing, waiting and unobserved operations; it is not pure sailing time.
Observed port stay is not berth processing time. Historical port-call relationships are not validated physical routes.

MECHANISM / SCOPE APPROVALS: NONE
EDGE / PORT EXPOSURE APPROVALS: NONE
EXPERIMENT EXECUTION AUTHORIZATION: NONE
SIMULATION EXECUTED: NO
SOURCE FILES MODIFIED: NO
SIMULATION INPUTS MODIFIED: NO
"""
    OUTPUTS["report"].write_text(report, encoding="utf-8")

    print("=" * 96)
    print("SCRIPT 69: EXPERIMENT PROTOCOL AND SCENARIO PARAMETER SPECIFICATION")
    print("=" * 96)
    print(f"Edges: {len(p65)} | Experiment templates: {len(d66)} | Scenario factor rows: {len(scenario)}")
    print(f"Readiness checks: {passed}/{len(check_df)} passed")
    for path in OUTPUTS.values():
        print(path.relative_to(ROOT))
    print("DISRUPTION MAGNITUDES SELECTED: NONE")
    print("EXPERIMENT EXECUTION AUTHORIZED: NO")
    print("SCRIPT 69 COMPLETED" if passed == len(check_df) else "SCRIPT 69 COMPLETED WITH FAILED CHECKS")

if __name__ == "__main__":
    main()
