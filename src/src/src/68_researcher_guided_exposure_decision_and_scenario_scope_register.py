#!/usr/bin/env python3
"""
SCRIPT 68: RESEARCHER-GUIDED EXPOSURE DECISION AND SCENARIO SCOPE REGISTER

Purpose
-------
Creates auditable, researcher-editable decision registers from Scripts 61, 66 and 67.
It does NOT approve any port, edge, disruption mechanism, or experiment scope.
All researcher decisions remain PENDING until independently completed by the researcher.

Run from project root:
    python src/68_researcher_guided_exposure_decision_and_scenario_scope_register.py

Inputs (read-only)
------------------
outputs/tables/67_edge_exposure_evidence_register.csv
outputs/tables/67_port_exposure_evidence_register.csv
outputs/tables/67_mechanism_variable_mapping.csv
outputs/tables/67_researcher_exposure_review_log.csv
outputs/tables/67_researcher_port_exposure_review_log.csv
outputs/tables/66_experiment_design_matrix.csv
outputs/tables/61_script59_eligibility_crosswalk.csv

Outputs
-------
outputs/tables/68_mechanism_decision_register.csv
outputs/tables/68_edge_exposure_decision_register.csv
outputs/tables/68_port_exposure_decision_register.csv
outputs/tables/68_experiment_scope_decision_matrix.csv
outputs/tables/68_decision_readiness_checks.csv
outputs/reports/68_researcher_guided_exposure_decision_report.txt

Important distinctions
----------------------
Historical schedule relationship != physical sailing route.
Observed elapsed time != pure sailing time.
Observed port stay != berth processing time.
Descriptive baseline inclusion != operational eligibility.
Operational eligibility != approval for hypothetical exposure.
No AIS-confirmed Hormuz transit is inferred by this script.
"""

from pathlib import Path
import sys
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"

INPUTS = {
    "edges": TABLES / "67_edge_exposure_evidence_register.csv",
    "ports": TABLES / "67_port_exposure_evidence_register.csv",
    "mechanisms": TABLES / "67_mechanism_variable_mapping.csv",
    "edge_review": TABLES / "67_researcher_exposure_review_log.csv",
    "port_review": TABLES / "67_researcher_port_exposure_review_log.csv",
    "experiments": TABLES / "66_experiment_design_matrix.csv",
    "crosswalk": TABLES / "61_script59_eligibility_crosswalk.csv",
}

OUTPUTS = {
    "mechanisms": TABLES / "68_mechanism_decision_register.csv",
    "edges": TABLES / "68_edge_exposure_decision_register.csv",
    "ports": TABLES / "68_port_exposure_decision_register.csv",
    "experiments": TABLES / "68_experiment_scope_decision_matrix.csv",
    "checks": TABLES / "68_decision_readiness_checks.csv",
    "report": REPORTS / "68_researcher_guided_exposure_decision_report.txt",
}

def fail(message):
    print(f"ERROR: {message}")
    sys.exit(1)

def read_csv(key):
    path = INPUTS[key]
    if not path.exists():
        fail(f"Missing required input: {path}")
    try:
        return pd.read_csv(path, low_memory=False)
    except Exception as exc:
        fail(f"Could not read {path.name}: {exc}")

def require_columns(df, columns, filename):
    missing = [c for c in columns if c not in df.columns]
    if missing:
        fail(f"{filename} missing required columns: {missing}")

def truth_count(series):
    return int(series.fillna(False).astype(bool).sum())

def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    edges = read_csv("edges")
    ports = read_csv("ports")
    mechanisms = read_csv("mechanisms")
    edge_review = read_csv("edge_review")
    port_review = read_csv("port_review")
    experiments = read_csv("experiments")
    crosswalk = read_csv("crosswalk")

    require_columns(edges, [
        "Previous_Port", "Next_Port", "Transition_Record_Count_67",
        "Distinct_Vessel_Count_67", "Both_Endpoints_Operationally_Approved_59",
        "Geographic_Route_Validated_67", "Actual_Hormuz_Exposure_Established_67",
        "Hypothetical_Disruption_Exposure_Approved_67", "Exposure_Review_Status_67",
        "Candidate_Use_67", "Origin_Operational_Gate_Class_59_v2",
        "Destination_Operational_Gate_Class_59_v2"
    ], INPUTS["edges"].name)
    require_columns(ports, [
        "UNLOCODE_Normalised", "observed_port_name", "observed_call_count",
        "Script59_Evidence_Record_Present_67", "Operational_Inclusion_Approved_59_v2",
        "AIS_Hormuz_Transit_Independently_Verified_67",
        "Actual_Hormuz_Exposure_Established_67",
        "Hypothetical_Port_Disruption_Approved_67", "Port_Exposure_Review_Status_67"
    ], INPUTS["ports"].name)
    require_columns(mechanisms, ["Mechanism", "Current_Status", "Evidence_Limitation"], INPUTS["mechanisms"].name)
    require_columns(experiments, ["Experiment_ID_66", "Experiment_Family_66", "Mechanism_66", "Status_66", "Required_Approval_66"], INPUTS["experiments"].name)
    require_columns(crosswalk, ["UNLOCODE", "Operational_Inclusion_Approved_59_v2", "May_Enter_Empirical_Baseline_59_v2", "May_Enter_Sensitivity_Model_59_v2"], INPUTS["crosswalk"].name)

    # Confirm review logs align exactly with the evidence registers.
    require_columns(edge_review, ["Previous_Port", "Next_Port"], INPUTS["edge_review"].name)
    require_columns(port_review, ["UNLOCODE_Normalised"], INPUTS["port_review"].name)

    edge_keys = list(zip(edges["Previous_Port"].astype(str), edges["Next_Port"].astype(str)))
    review_edge_keys = list(zip(edge_review["Previous_Port"].astype(str), edge_review["Next_Port"].astype(str)))
    if len(set(edge_keys)) != len(edge_keys):
        fail("Script67 edge evidence register contains duplicate directed pairs.")
    if set(edge_keys) != set(review_edge_keys) or len(edge_keys) != len(review_edge_keys):
        fail("Script67 edge review log does not exactly match edge evidence register.")
    port_ids = ports["UNLOCODE_Normalised"].astype(str)
    review_port_ids = port_review["UNLOCODE_Normalised"].astype(str)
    if port_ids.duplicated().any() or set(port_ids) != set(review_port_ids) or len(port_ids) != len(review_port_ids):
        fail("Script67 port review log does not exactly match port evidence register.")
    if edges[["Previous_Port", "Next_Port"]].isna().any().any():
        fail("Missing endpoint identifiers in edge register.")
    if ports["UNLOCODE_Normalised"].isna().any():
        fail("Missing port identifiers in port register.")

    # Mechanism-level decision register: decisions are deliberately unselected.
    mechanism_rows = []
    mechanism_guidance = {
        "TRANSIT_ELAPSED_TIME_SHOCK": (
            "CONDITIONAL_CANDIDATE_FOR_HYPOTHETICAL_SENSITIVITY",
            "Elapsed-time variable only; it includes sailing, waiting and unobserved operations. "
            "Define shock unit, magnitude, affected scope and interpretation before experiment use."
        ),
        "NETWORK_ACCESS_RESTRICTION": (
            "BLOCKED_UNTIL_ROUTE_AND_ALTERNATIVE_FEASIBILITY_EVIDENCE",
            "Do not remove observed schedule edges as physical routes. Requires a validated geographic route graph "
            "and feasible alternative paths."
        ),
        "PORT_SERVICE_DISRUPTION": (
            "CONDITIONAL_CANDIDATE_WITH_SERVICE_PROXY_LIMITATION",
            "Observed port stay is not berth processing time. Port/berth capacity and service-process evidence "
            "must be established before queue/capacity claims."
        ),
        "COMPOUND_MECHANISM": (
            "DEFER_UNTIL_SINGLE_MECHANISMS_DEFINED",
            "Do not combine mechanisms until each component has an explicit variable, scope, magnitude and "
            "standalone experiment definition."
        ),
    }
    for _, row in mechanisms.iterrows():
        mech = str(row["Mechanism"])
        recommendation, rationale = mechanism_guidance.get(
            mech, ("RESEARCHER_REVIEW_REQUIRED", "No automated mechanism recommendation is defined.")
        )
        mechanism_rows.append({
            "Mechanism": mech,
            "Disrupted_Concept": row.get("Disrupted_Concept", ""),
            "Potential_Model_Variable": row.get("Potential_Model_Variable", ""),
            "Script67_Current_Status": row.get("Current_Status", ""),
            "Script67_Evidence_Limitation": row.get("Evidence_Limitation", ""),
            "Script68_Conservative_Research_Guidance": recommendation,
            "Researcher_Mechanism_Decision": "PENDING_RESEARCHER_DECISION",
            "Approved_For_Experiment": False,
            "Defined_Operational_Interpretation": "",
            "Defined_Exposure_Unit": "",
            "Defined_Disruption_Magnitude": "",
            "Defined_Affected_Scope": "",
            "Alternative_or_Recovery_Assumption": "",
            "Evidence_URL_or_Citation": "",
            "Researcher_Rationale": "",
            "Reviewer": "",
            "Review_Date": "",
        })
    mechanism_out = pd.DataFrame(mechanism_rows)

    # Edge-level researcher decision register.
    edge_out = edges.copy()
    edge_out["Script68_Research_Guidance"] = np.where(
        edge_out["Both_Endpoints_Operationally_Approved_59"].fillna(False).astype(bool)
        & edge_out["Geographic_Route_Validated_67"].fillna(False).astype(bool),
        "ELIGIBILITY_AND_ROUTE_EVIDENCE_PRESENT_REQUIRES_RESEARCHER_REVIEW",
        "DESCRIPTIVE_RELATIONSHIP_ONLY_NO_ROUTE_OR_EXPOSURE_APPROVAL"
    )
    edge_out["Researcher_Edge_Decision"] = "PENDING_RESEARCHER_DECISION"
    edge_out["Approved_For_Hypothetical_Exposure"] = False
    edge_out["Mechanism_Selected"] = ""
    edge_out["Exposure_Interpretation"] = ""
    edge_out["Exposure_Unit"] = ""
    edge_out["Disruption_Magnitude"] = ""
    edge_out["Scope_Justification"] = ""
    edge_out["Feasible_Alternative_Evidence"] = ""
    edge_out["Evidence_URL_or_Citation"] = ""
    edge_out["Researcher_Rationale"] = ""
    edge_out["Reviewer"] = ""
    edge_out["Review_Date"] = ""

    # Port-level researcher decision register.
    port_out = ports.copy()
    port_out["Script68_Research_Guidance"] = np.where(
        port_out["Script59_Evidence_Record_Present_67"].astype("boolean").fillna(False).astype(bool)
        & port_out["Operational_Inclusion_Approved_59_v2"].astype("boolean").fillna(False).astype(bool),
        "OPERATIONAL_EVIDENCE_PRESENT_REQUIRES_SEPARATE_EXPOSURE_REVIEW",
        "DESCRIPTIVE_PORT_CALL_CONTEXT_ONLY_NO_EXPOSURE_APPROVAL"
    )
    port_out["Researcher_Port_Decision"] = "PENDING_RESEARCHER_DECISION"
    port_out["Approved_For_Hypothetical_Port_Disruption"] = False
    port_out["Mechanism_Selected"] = ""
    port_out["Disrupted_Service_or_Function"] = ""
    port_out["Exposure_Unit"] = ""
    port_out["Disruption_Magnitude"] = ""
    port_out["Capacity_or_Service_Evidence_URL"] = ""
    port_out["Scope_Justification"] = ""
    port_out["Researcher_Rationale"] = ""
    port_out["Reviewer"] = ""
    port_out["Review_Date"] = ""

    # Experiment-level scope matrix. Templates remain unapproved.
    experiment_rows = []
    for _, row in experiments.iterrows():
        exp_id = str(row["Experiment_ID_66"])
        mech = str(row.get("Mechanism_66", ""))
        if exp_id == "E66-00":
            guidance = "REFERENCE_BASELINE_ONLY"
            blocker = "Confirm baseline replay and observation-window limitations; no new disruption scope."
        elif mech == "TRANSIT_ELAPSED_TIME_SHOCK":
            guidance = "POTENTIAL_AFTER_MECHANISM_AND_EDGE_SCOPE_DECISIONS"
            blocker = "Define elapsed-time shock, select and justify edges/vessels, preserve elapsed-time interpretation."
        elif mech == "NETWORK_ACCESS_RESTRICTION":
            guidance = "BLOCKED_PENDING_VALIDATED_ROUTE_GRAPH"
            blocker = "Validated geographic routes and feasible alternatives required; schedule edges are not physical routes."
        elif mech == "PORT_SERVICE_DISRUPTION":
            guidance = "POTENTIAL_AFTER_PORT_SERVICE_EVIDENCE"
            blocker = "Define affected service process; observed stay is not berth processing time; capacity evidence absent."
        elif mech == "COMPOUND_MECHANISM":
            guidance = "DEFERRED"
            blocker = "Each component mechanism must first be defined and separately assessed."
        else:
            guidance = "RESEARCHER_REVIEW_REQUIRED"
            blocker = "Clarify mechanism and evidence requirements before scope selection."
        experiment_rows.append({
            "Experiment_ID": exp_id,
            "Experiment_Family": row.get("Experiment_Family_66", ""),
            "Disruption_Mechanism": mech,
            "Script66_Status": row.get("Status_66", ""),
            "Script66_Required_Approval": row.get("Required_Approval_66", ""),
            "Script68_Conservative_Guidance": guidance,
            "Researcher_Scope_Decision": "PENDING_RESEARCHER_DECISION",
            "Approved_To_Proceed": False,
            "Selected_Edge_Count": 0,
            "Selected_Port_Count": 0,
            "Selected_Vessel_Count": 0,
            "Defined_Exposure_Unit": "",
            "Defined_Disruption_Magnitude": "",
            "Recovery_or_Alternative_Assumption": "",
            "Scenario_Rationale": "",
            "Evidence_URL_or_Citation": "",
            "Reviewer": "",
            "Review_Date": "",
            "Blocking_or_Required_Evidence": blocker,
        })
    experiment_out = pd.DataFrame(experiment_rows)

    # Readiness checks test data integrity and conservative defaults, not scientific approval.
    checks = []
    def add_check(name, passed, observed, expected, note):
        checks.append({"Check": name, "Passed": bool(passed), "Observed": observed,
                       "Expected": expected, "Interpretation": note})

    add_check("Unique directed edge pairs", not edges.duplicated(["Previous_Port", "Next_Port"]).any(),
              len(edges), "53 unique pairs", "Structural integrity only.")
    add_check("Unique port identifiers", not ports["UNLOCODE_Normalised"].duplicated().any(),
              len(ports), "19 unique ports", "Structural integrity only.")
    add_check("Edge review log exact key match", set(edge_keys) == set(review_edge_keys) and len(edge_keys)==len(review_edge_keys),
              len(review_edge_keys), len(edge_keys), "Every edge has one review row.")
    add_check("Port review log exact key match", set(port_ids) == set(review_port_ids) and len(port_ids)==len(review_port_ids),
              len(review_port_ids), len(port_ids), "Every port has one review row.")
    add_check("Mechanism register retains all Script67 mechanisms",
              set(mechanism_out["Mechanism"]) == set(mechanisms["Mechanism"]),
              len(mechanism_out), len(mechanisms), "No mechanism omitted.")
    add_check("Experiment matrix retains all Script66 templates",
              set(experiment_out["Experiment_ID"].astype(str)) == set(experiments["Experiment_ID_66"].astype(str)),
              len(experiment_out), len(experiments), "No experiment template omitted.")
    add_check("All edge decisions pending",
              edge_out["Researcher_Edge_Decision"].eq("PENDING_RESEARCHER_DECISION").all(),
              int(edge_out["Researcher_Edge_Decision"].eq("PENDING_RESEARCHER_DECISION").sum()), len(edge_out),
              "No edge is approved by code.")
    add_check("All port decisions pending",
              port_out["Researcher_Port_Decision"].eq("PENDING_RESEARCHER_DECISION").all(),
              int(port_out["Researcher_Port_Decision"].eq("PENDING_RESEARCHER_DECISION").sum()), len(port_out),
              "No port is approved by code.")
    add_check("No edge hypothetical exposure approvals",
              not edge_out["Approved_For_Hypothetical_Exposure"].any(),
              truth_count(edge_out["Approved_For_Hypothetical_Exposure"]), 0,
              "Researcher approval required.")
    add_check("No port hypothetical disruption approvals",
              not port_out["Approved_For_Hypothetical_Port_Disruption"].any(),
              truth_count(port_out["Approved_For_Hypothetical_Port_Disruption"]), 0,
              "Researcher approval required.")
    add_check("No experiment scope approvals",
              not experiment_out["Approved_To_Proceed"].any(),
              truth_count(experiment_out["Approved_To_Proceed"]), 0,
              "Experiment templates remain unapproved.")
    add_check("No actual Hormuz exposure asserted on edges",
              not edges["Actual_Hormuz_Exposure_Established_67"].fillna(False).astype(bool).any(),
              truth_count(edges["Actual_Hormuz_Exposure_Established_67"]), 0,
              "No actual exposure inferred.")
    add_check("No actual Hormuz exposure asserted on ports",
              not ports["Actual_Hormuz_Exposure_Established_67"].fillna(False).astype(bool).any(),
              truth_count(ports["Actual_Hormuz_Exposure_Established_67"]), 0,
              "No actual exposure inferred.")
    add_check("No AIS-confirmed Hormuz transit on ports",
              not ports["AIS_Hormuz_Transit_Independently_Verified_67"].fillna(False).astype(bool).any(),
              truth_count(ports["AIS_Hormuz_Transit_Independently_Verified_67"]), 0,
              "No AIS transit claim inferred.")
    add_check("No Script65 final parameter selections",
              "Final_Selected_Value_Hours_65" in edges.columns
              and edges["Final_Selected_Value_Hours_65"].isna().all(),
              int(edges["Final_Selected_Value_Hours_65"].notna().sum()) if "Final_Selected_Value_Hours_65" in edges else "column absent",
              0, "No parameter values selected in this stage.")
    check_out = pd.DataFrame(checks)

    # Write outputs.
    mechanism_out.to_csv(OUTPUTS["mechanisms"], index=False)
    edge_out.to_csv(OUTPUTS["edges"], index=False)
    port_out.to_csv(OUTPUTS["ports"], index=False)
    experiment_out.to_csv(OUTPUTS["experiments"], index=False)
    check_out.to_csv(OUTPUTS["checks"], index=False)

    passed = int(check_out["Passed"].sum())
    report = f"""================================================================================
SCRIPT 68: RESEARCHER-GUIDED EXPOSURE DECISION AND SCENARIO SCOPE REGISTER
================================================================================

INPUT COUNTS
Directed network edges: {len(edges)}
Ports: {len(ports)}
Mechanisms: {len(mechanisms)}
Experiment templates: {len(experiments)}
Script59 crosswalk records: {len(crosswalk)}

OUTPUT REGISTER COUNTS
Mechanism decision rows: {len(mechanism_out)}
Edge decision rows: {len(edge_out)}
Port decision rows: {len(port_out)}
Experiment scope rows: {len(experiment_out)}

READINESS CHECKS
Passed: {passed}/{len(check_out)}

RESEARCHER DECISION DEFAULTS
Edge decisions pending: {len(edge_out)}
Port decisions pending: {len(port_out)}
Mechanism decisions pending: {len(mechanism_out)}
Experiment scope decisions pending: {len(experiment_out)}
Edge exposure approvals: 0
Port disruption approvals: 0
Experiment scope approvals: 0

CONSERVATIVE MECHANISM GUIDANCE
- Transit elapsed-time shock: possible hypothetical sensitivity only after defining elapsed-time interpretation,
  magnitude, unit and affected edge/vessel scope.
- Network access restriction: blocked until a validated geographic route graph and feasible alternatives exist.
- Port service disruption: requires definition of the disrupted service process; observed port stay is not
  berth processing time and port/berth capacity evidence is unavailable.
- Compound mechanism: deferred until each component is defined and separately assessed.

INTERPRETATION
This script creates researcher-editable decision registers. It does not make scientific, operational,
geographic, geopolitical, or exposure approvals. A pending decision is not an approval.
Historical consecutive port-call relationships are not validated physical sailing routes.
Observed inter-port elapsed time is not pure sailing time. Observed port stay is not berth processing time.
Descriptive baseline inclusion, operational eligibility, and hypothetical exposure approval are distinct gates.

ACTUAL HORMUZ TRANSIT ESTABLISHED: NO
AIS-CONFIRMED HORMUZ TRANSIT ESTABLISHED: NO
HYPOTHETICAL EXPOSURE APPROVALS: NONE
DISRUPTION MAGNITUDES SELECTED: NONE
SOURCE FILES MODIFIED: NO
SIMULATION INPUTS MODIFIED: NO
"""
    OUTPUTS["report"].write_text(report, encoding="utf-8")

    print("=" * 96)
    print("SCRIPT 68: RESEARCHER-GUIDED EXPOSURE DECISION AND SCENARIO SCOPE REGISTER")
    print("=" * 96)
    print(f"Edges: {len(edges)} | Ports: {len(ports)} | Mechanisms: {len(mechanisms)} | Experiments: {len(experiments)}")
    print(f"Readiness checks: {passed}/{len(check_out)} passed")
    for key, path in OUTPUTS.items():
        print(path.relative_to(ROOT))
    print("Edge exposure approvals: NONE")
    print("Port disruption approvals: NONE")
    print("Experiment scope approvals: NONE")
    print("ACTUAL HORMUZ TRANSIT ESTABLISHED: NO")
    print("SCRIPT 68 COMPLETED" if passed == len(check_out) else "SCRIPT 68 COMPLETED WITH FAILED CHECKS")

if __name__ == "__main__":
    main()
