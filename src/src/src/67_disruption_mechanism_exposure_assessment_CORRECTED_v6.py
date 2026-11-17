"""
SCRIPT 67: DISRUPTION MECHANISM AND OPERATIONAL EXPOSURE ASSESSMENT
==================================================================
Builds an evidence-traceable exposure review register for the 53 observed
directed inter-port relationships. It distinguishes observed schedule
transitions from hypothetical disruption exposure.

This is an assessment and review-register stage only.

It does NOT:
- establish actual Strait of Hormuz transit;
- infer geographic routes from consecutive port calls;
- infer route feasibility or network-access restrictions;
- approve any port, edge, vessel or disruption scope for simulation;
- infer that Persian Gulf screening or regional proximity proves exposure;
- assign disruption magnitudes, probabilities or affected-scope selections;
- modify any upstream source or simulation input.

Required inputs:
    outputs/tables/65_parameter_option_register.csv
    outputs/tables/66_experiment_design_matrix.csv
    outputs/tables/61_network_edge_integration_manifest.csv
    outputs/tables/59_operational_network_eligibility_register_v2.csv
    data/simulation_inputs/19_observed_interport_transitions.csv
    data/simulation_inputs/19_historical_arrival_schedule.csv
    data/simulation_inputs/19_port_parameters.csv

Outputs:
    outputs/tables/67_edge_exposure_evidence_register.csv
    outputs/tables/67_port_exposure_evidence_register.csv
    outputs/tables/67_mechanism_variable_mapping.csv
    outputs/tables/67_researcher_exposure_review_log.csv
    outputs/tables/67_exposure_readiness_checks.csv
    outputs/reports/67_disruption_mechanism_exposure_assessment_report.txt
"""

from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
SIM = ROOT / "data" / "simulation_inputs"
REPORTS = ROOT / "outputs" / "reports"

INPUTS = {
    "s65": TABLES / "65_parameter_option_register.csv",
    "s66": TABLES / "66_experiment_design_matrix.csv",
    "s61": TABLES / "61_network_edge_integration_manifest.csv",
    "s61_crosswalk": TABLES / "61_script59_eligibility_crosswalk.csv",
    "transitions": SIM / "19_observed_interport_transitions.csv",
    "schedule": SIM / "19_historical_arrival_schedule.csv",
    "ports": SIM / "19_port_parameters.csv",
}

OUT_EDGE = TABLES / "67_edge_exposure_evidence_register.csv"
OUT_PORT = TABLES / "67_port_exposure_evidence_register.csv"
OUT_MECHANISM = TABLES / "67_mechanism_variable_mapping.csv"
OUT_DECISION = TABLES / "67_researcher_exposure_review_log.csv"
OUT_CHECKS = TABLES / "67_exposure_readiness_checks.csv"
OUT_REPORT = REPORTS / "67_disruption_mechanism_exposure_assessment_report.txt"


def require(df, columns, label):
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def norm(s):
    return s.astype("string").str.strip().str.upper()


def as_bool(s):
    return s.astype("string").fillna("false").str.strip().str.lower().isin(
        {"true", "1", "yes", "y"}
    )


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    for label, path in INPUTS.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing {label} input: {path}")

    s65 = pd.read_csv(INPUTS["s65"])
    s66 = pd.read_csv(INPUTS["s66"])
    s61 = pd.read_csv(INPUTS["s61"])
    s59 = pd.read_csv(INPUTS["s61_crosswalk"])
    trans = pd.read_csv(INPUTS["transitions"])
    schedule = pd.read_csv(INPUTS["schedule"])
    ports = pd.read_csv(INPUTS["ports"])

    require(s65, [
        "Previous_Port", "Next_Port", "Assignment_Classification_64",
        "Parameter_Treatment_65", "Researcher_Decision_Status_65",
        "Final_Selected_Value_Hours_65", "Empirical_Resampling_Approved_65"
    ], "Script65")
    require(s66, ["Experiment_ID_66", "Mechanism_66", "Affected_Scope_66", "Status_66"],
            "Script66")
    require(s61, ["Previous_Port", "Next_Port", "Observed_Transition_Record_Count",
                  "Integration_Disposition"], "Script61")
    require(s59, [
        "UNLOCODE", "Port_Name", "Operational_Gate_Class_59_v2",
        "Operational_Gate_Status_59_v2", "May_Enter_Empirical_Baseline_59_v2",
        "May_Enter_Sensitivity_Model_59_v2",
        "AIS_Transit_Independently_Verified"
    ], "Script61 Script59 eligibility crosswalk")
    require(trans, [
        "IMO_Normalised", "Previous_Port", "Next_Port",
        "Previous_Departure_UTC", "Actual_Arrival_UTC",
        "Elapsed_Hours_Between_Calls", "Actual_Baseline_Eligible_Conservative",
        "Time_Interpretation"
    ], "Script19 observed transitions")
    require(schedule, [
        "Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised",
        "Actual_Arrival_UTC", "Actual_Departure_UTC"
    ], "Script19 historical schedule")
    require(ports, [
        "UNLOCODE_Normalised", "observed_port_name", "observed_call_count",
        "Port_Capacity_Status", "Berth_Capacity_Status", "Hormuz_Transit_Status"
    ], "Script19 port parameters")

    # Normalize keys and validate uniqueness of source master tables.
    for df, a, b in [(s65, "Previous_Port", "Next_Port"),
                     (s61, "Previous_Port", "Next_Port"),
                     (trans, "Previous_Port", "Next_Port")]:
        df["_origin"] = norm(df[a])
        df["_destination"] = norm(df[b])
    s59["_port"] = norm(s59["UNLOCODE"])
    ports["_port"] = norm(ports["UNLOCODE_Normalised"])
    schedule["_port"] = norm(schedule["UNLOCODE_Normalised"])

    if s65.duplicated(["_origin", "_destination"]).any():
        raise ValueError("Script65 contains duplicate directed edges.")
    if s61.duplicated(["_origin", "_destination"]).any():
        raise ValueError("Script61 contains duplicate directed edges.")
    if s59["_port"].duplicated().any() or ports["_port"].duplicated().any():
        raise ValueError("Port-level master input contains duplicate port identifiers.")
    if schedule["Simulation_Record_ID"].duplicated().any():
        raise ValueError("Historical schedule contains duplicate record IDs.")

    s65_pairs = set(zip(s65["_origin"], s65["_destination"]))
    s61_pairs = set(zip(s61["_origin"], s61["_destination"]))
    trans_pairs = set(zip(trans["_origin"], trans["_destination"]))
    if len(s65) != 53 or len(s61) != 53:
        raise ValueError(f"Expected 53 Script65/61 edges; found {len(s65)}/{len(s61)}.")
    if s65_pairs != s61_pairs:
        raise ValueError("Script65 and Script61 directed edge sets do not match.")
    if not trans_pairs.issubset(s65_pairs):
        raise ValueError("Observed transition contains a directed edge absent from the 53-edge network.")

    # Summarize transition evidence; no route or Hormuz exposure is inferred.
    trans["_elapsed_numeric"] = pd.to_numeric(trans["Elapsed_Hours_Between_Calls"], errors="coerce")
    trans["_imo"] = trans["IMO_Normalised"].astype("string").str.strip()
    valid_trans = trans[
        trans["_imo"].notna()
        & trans["_imo"].ne("")
        & trans["_elapsed_numeric"].notna()
        & (trans["_elapsed_numeric"] >= 0)
    ].copy()

    edge_obs = valid_trans.groupby(["_origin", "_destination"]).agg(
        Transition_Record_Count_67=("_elapsed_numeric", "size"),
        Distinct_Vessel_Count_67=("_imo", "nunique"),
        Mean_Observed_Elapsed_Hours_67=("_elapsed_numeric", "mean"),
        Median_Observed_Elapsed_Hours_67=("_elapsed_numeric", "median"),
        P90_Observed_Elapsed_Hours_67=(" _elapsed_numeric".strip(), lambda x: x.quantile(0.90)),
        Max_Observed_Elapsed_Hours_67=("_elapsed_numeric", "max"),
        Conservative_Baseline_Eligible_Records_67=("Actual_Baseline_Eligible_Conservative", lambda x: as_bool(x).sum())
    ).reset_index()

    edge = s65.merge(
        s61[["_origin", "_destination", "Observed_Transition_Record_Count",
             "Integration_Disposition"]],
        on=["_origin", "_destination"], how="left", validate="one_to_one"
    ).merge(
        edge_obs, on=["_origin", "_destination"], how="left", validate="one_to_one"
    )

    port_lookup = s59[[
        "_port", "Port_Name", "Script49_Eligibility_Classification",
        "Script49_Recommended_Use", "Operational_Gate_Class_59_v2",
        "Operational_Gate_Status_59_v2", "May_Enter_Empirical_Baseline_59_v2",
        "May_Enter_Sensitivity_Model_59_v2",
        "AIS_Transit_Independently_Verified",
        "Operational_Inclusion_Approved_59_v2"
    ]].copy()
    port_lookup = port_lookup.rename(columns={
        c: f"Origin_{c}" for c in port_lookup.columns if c != "_port"
    })
    edge = edge.merge(port_lookup, left_on="_origin", right_on="_port",
                      how="left", validate="many_to_one").drop(columns=["_port"])
    port_lookup_dest = s59[[
        "_port", "Port_Name", "Script49_Eligibility_Classification",
        "Script49_Recommended_Use", "Operational_Gate_Class_59_v2",
        "Operational_Gate_Status_59_v2", "May_Enter_Empirical_Baseline_59_v2",
        "May_Enter_Sensitivity_Model_59_v2",
        "AIS_Transit_Independently_Verified",
        "Operational_Inclusion_Approved_59_v2"
    ]].copy()
    port_lookup_dest = port_lookup_dest.rename(columns={
        c: f"Destination_{c}" for c in port_lookup_dest.columns if c != "_port"
    })
    edge = edge.merge(port_lookup_dest, left_on="_destination", right_on="_port",
                      how="left", validate="many_to_one").drop(columns=["_port"])

    edge["Observed_Transition_Exists_67"] = edge["Transition_Record_Count_67"].fillna(0).gt(0)
    edge["Both_Endpoints_Operationally_Approved_59"] = (
        as_bool(edge["Origin_Operational_Inclusion_Approved_59_v2"])
        & as_bool(edge["Destination_Operational_Inclusion_Approved_59_v2"])
    )
    edge["Hormuz_Transit_Independently_Verified_At_Both_Endpoints_59"] = (
        as_bool(edge["Origin_AIS_Transit_Independently_Verified"])
        & as_bool(edge["Destination_AIS_Transit_Independently_Verified"])
    )
    edge["Geographic_Route_Validated_67"] = False
    edge["Actual_Hormuz_Exposure_Established_67"] = False
    edge["Hypothetical_Disruption_Exposure_Approved_67"] = False
    edge["Exposure_Review_Status_67"] = "PENDING_RESEARCHER_REVIEW"
    edge["Exposure_Evidence_Interpretation_67"] = (
        "Observed consecutive port-call relationship only; not a verified sailing route, "
        "Hormuz transit, geographic exposure or operationally feasible connection."
    )
    edge["Candidate_Use_67"] = np.where(
        edge["Observed_Transition_Exists_67"],
        "OBSERVED_NETWORK_RELATIONSHIP_FOR_DESCRIPTIVE_REVIEW_ONLY",
        "NETWORK_PARAMETER_EDGE_WITHOUT_VALID_TRANSITION_SUMMARY"
    )

    # Port register joins all 19 nodes with Script59 evidence.
    port = ports.merge(
        s59[[
            "_port", "Port_Name", "Script49_Eligibility_Classification",
            "Script49_Recommended_Use", "Operational_Gate_Class_59_v2",
            "Operational_Gate_Status_59_v2", "May_Enter_Empirical_Baseline_59_v2",
            "May_Enter_Sensitivity_Model_59_v2",
            "AIS_Transit_Independently_Verified",
            "Operational_Inclusion_Approved_59_v2",
            "Coordinate_Approval_v2", "Operational_Inclusion_v2",
            "Already_Present_In_Observed_Network", "Script61_Integration_Disposition"
        ]],
        left_on="_port", right_on="_port", how="left", validate="one_to_one"
    )
    port["Script59_Evidence_Record_Present_67"] = port["Operational_Gate_Status_59_v2"].notna()
    port["Operational_Gate_Status_59_v2"] = port["Operational_Gate_Status_59_v2"].fillna(
        "NO_SCRIPT59_CROSSWALK_RECORD_FOR_THIS_OBSERVED_NETWORK_NODE"
    )
    port["Operational_Gate_Class_59_v2"] = port["Operational_Gate_Class_59_v2"].fillna(
        "NO_SCRIPT59_CROSSWALK_RECORD"
    )
    port["AIS_Transit_Independently_Verified"] = port["AIS_Transit_Independently_Verified"].astype("string").fillna("false")
    port["Observed_Schedule_Calls_67"] = port["observed_call_count"]
    port["Observed_Schedule_Vessels_67"] = port.get("observed_vessel_count", np.nan)
    port["Port_Capacity_Evidence_Available_67"] = (
        ~port["Port_Capacity_Status"].astype(str).str.upper().isin(["NOT_AVAILABLE", "NAN", ""])
    )
    port["Berth_Capacity_Evidence_Available_67"] = (
        ~port["Berth_Capacity_Status"].astype(str).str.upper().isin(["NOT_AVAILABLE", "NAN", ""])
    )
    port["AIS_Hormuz_Transit_Independently_Verified_67"] = as_bool(
        port["AIS_Transit_Independently_Verified"]
    )
    port["Actual_Hormuz_Exposure_Established_67"] = False
    port["Hypothetical_Port_Disruption_Approved_67"] = False
    port["Port_Exposure_Review_Status_67"] = "PENDING_RESEARCHER_REVIEW"
    port["Port_Exposure_Interpretation_67"] = (
        "Observed port-call activity and Script59 eligibility evidence do not establish "
        "Hormuz transit, disruption exposure, port capacity or berth capacity."
    )

    mechanisms = pd.DataFrame([
        ["TRANSIT_ELAPSED_TIME_SHOCK", "Inter-port elapsed time", "Elapsed_Hours_Between_Calls / Script19 inter-port elapsed-time parameters", "Observed departure-to-next-arrival elapsed time", "Includes sailing, waiting and unobserved operations; not pure sailing time.", "HYPOTHETICAL_MECHANISM_ONLY"],
        ["NETWORK_ACCESS_RESTRICTION", "Edge availability / accessibility", "Requires explicit validated route/edge representation and feasible alternatives", "No validated geographic route graph established", "Do not delete or block observed schedule edges as if they were physical routes.", "BLOCKED_PENDING_ROUTE_AND_FEASIBILITY_EVIDENCE"],
        ["PORT_SERVICE_DISRUPTION", "Port service or stay duration", "Actual_Stay_Hours / Script19 port service descriptive parameters", "Observed arrival-to-departure stay duration", "Not berth processing time; port/berth capacity unavailable.", "HYPOTHETICAL_MECHANISM_ONLY"],
        ["COMPOUND_MECHANISM", "Two or more separately defined mechanisms", "Combination of separately specified variables", "No combined mechanism calibrated", "Define and assess each mechanism independently before combining.", "DEFERRED"],
    ], columns=[
        "Mechanism", "Disrupted_Concept", "Potential_Model_Variable",
        "Available_Observed_Representation", "Evidence_Limitation", "Current_Status"
    ])

    # Decision log for all edges and ports. No approval is granted by this script.
    edge_decision = edge[[
        "Previous_Port", "Next_Port", "Transition_Record_Count_67",
        "Distinct_Vessel_Count_67", "Assignment_Classification_64",
        "Parameter_Treatment_65", "Origin_Operational_Gate_Status_59_v2",
        "Destination_Operational_Gate_Status_59_v2"
    ]].copy()
    edge_decision["Researcher_Exposure_Decision"] = "PENDING"
    edge_decision["Approved_Hypothetical_Mechanism"] = ""
    edge_decision["Approved_Exposure_Rationale"] = ""
    edge_decision["Evidence_Reference"] = ""
    edge_decision["Reviewer"] = ""
    edge_decision["Review_Date"] = ""
    edge_decision["Approval_Granted_By_Script67"] = False

    port_decision = port[[
        "UNLOCODE_Normalised", "observed_port_name",
        "Operational_Gate_Class_59_v2", "Operational_Gate_Status_59_v2",
        "AIS_Hormuz_Transit_Independently_Verified_67",
        "Script59_Evidence_Record_Present_67"
    ]].copy()
    port_decision["Researcher_Port_Exposure_Decision"] = "PENDING"
    port_decision["Approved_Hypothetical_Mechanism"] = ""
    port_decision["Approved_Exposure_Rationale"] = ""
    port_decision["Evidence_Reference"] = ""
    port_decision["Reviewer"] = ""
    port_decision["Review_Date"] = ""
    port_decision["Approval_Granted_By_Script67"] = False

    checks = []
    def ck(name, passed, observed, expected):
        checks.append({"Check": name, "Passed": bool(passed),
                       "Observed": str(observed), "Expected": str(expected)})

    ck("Script65 edge count", len(s65) == 53, len(s65), 53)
    ck("Script61 edge count", len(s61) == 53, len(s61), 53)
    ck("Script65 and Script61 edge sets match", s65_pairs == s61_pairs, len(s65_pairs & s61_pairs), 53)
    ck("Observed transition rows", len(trans) == 271, len(trans), 271)
    ck("Transition pairs contained in observed network", trans_pairs.issubset(s65_pairs), len(trans_pairs - s65_pairs), 0)
    ck("Port evidence register has 19 nodes", len(port) == 19, len(port), 19)
    ck("Script59 crosswalk coverage matches 12 known network nodes",
       int(port["Script59_Evidence_Record_Present_67"].sum()) == 12,
       int(port["Script59_Evidence_Record_Present_67"].sum()), 12)
    ck("No actual Hormuz edge exposure asserted", not edge["Actual_Hormuz_Exposure_Established_67"].any(), int(edge["Actual_Hormuz_Exposure_Established_67"].sum()), 0)
    ck("No hypothetical edge scope approved", not edge["Hypothetical_Disruption_Exposure_Approved_67"].any(), int(edge["Hypothetical_Disruption_Exposure_Approved_67"].sum()), 0)
    ck("No actual Hormuz port exposure asserted", not port["Actual_Hormuz_Exposure_Established_67"].any(), int(port["Actual_Hormuz_Exposure_Established_67"].sum()), 0)
    ck("No hypothetical port scope approved", not port["Hypothetical_Port_Disruption_Approved_67"].any(), int(port["Hypothetical_Port_Disruption_Approved_67"].sum()), 0)
    ck("All researcher edge decisions pending", edge_decision["Researcher_Exposure_Decision"].eq("PENDING").all(), int(edge_decision["Researcher_Exposure_Decision"].eq("PENDING").sum()), 53)
    ck("All researcher port decisions pending", port_decision["Researcher_Port_Exposure_Decision"].eq("PENDING").all(), int(port_decision["Researcher_Port_Exposure_Decision"].eq("PENDING").sum()), 19)
    ck("No selected parameter values in Script65", s65["Final_Selected_Value_Hours_65"].isna().all(), int(s65["Final_Selected_Value_Hours_65"].notna().sum()), 0)

    check_df = pd.DataFrame(checks)
    if not check_df["Passed"].all():
        raise ValueError("Script67 readiness check failed; inspect source data and joins:\\n" + check_df.loc[~check_df["Passed"]].to_string(index=False))

    # Drop internal normalized keys from user-facing outputs.
    edge = edge.drop(columns=["_origin", "_destination"])
    port = port.drop(columns=["_port"])
    edge.to_csv(OUT_EDGE, index=False)
    port.to_csv(OUT_PORT, index=False)
    mechanisms.to_csv(OUT_MECHANISM, index=False)
    edge_decision.to_csv(OUT_DECISION, index=False)
    # Keep port decision log as a separate companion output.
    OUT_PORT_DECISION = TABLES / "67_researcher_port_exposure_review_log.csv"
    port_decision.to_csv(OUT_PORT_DECISION, index=False)
    check_df.to_csv(OUT_CHECKS, index=False)

    with OUT_REPORT.open("w", encoding="utf-8") as f:
        f.write("=" * 96 + "\n")
        f.write("SCRIPT 67: DISRUPTION MECHANISM AND OPERATIONAL EXPOSURE ASSESSMENT\n")
        f.write("=" * 96 + "\n\n")
        f.write(f"Directed network edges: {len(edge)}\n")
        f.write(f"Ports: {len(port)}\n")
        f.write(f"Observed transition records: {len(trans)}\n")
        f.write(f"Edges with observed transition records: {int(edge['Observed_Transition_Exists_67'].sum())}\n")
        f.write(f"Distinct vessel transitions summarized: {int(edge['Distinct_Vessel_Count_67'].fillna(0).sum())} edge-vessel counts (not unique network vessels)\n")
        f.write(f"Mechanisms mapped: {len(mechanisms)}\n")
        f.write(f"Edge researcher review rows: {len(edge_decision)}\n")
        f.write(f"Port researcher review rows: {len(port_decision)}\n\n")
        f.write("READINESS CHECKS\n")
        f.write(check_df.to_string(index=False))
        f.write("\n\nMECHANISM STATUS\n")
        f.write(mechanisms.to_string(index=False))
        f.write("\n\nINTERPRETATION AND LIMITATIONS\n")
        f.write(
            "Observed consecutive port-call records establish historical schedule relationships only. "
            "They do not establish actual sailing routes, route feasibility, geographic exposure to "
            "the Strait of Hormuz, or actual transit through the Strait. Port identity/coordinate "
            "review and Script59 operational eligibility are retained as separate evidence gates. "
            "No port or edge is approved for hypothetical disruption exposure by this script. "
            "Inter-port elapsed time includes sailing, waiting and unobserved operations. Port stay "
            "is not berth processing time; port and berth capacity are unavailable. A network-access "
            "restriction cannot be implemented as physical route closure without validated route "
            "and alternative-path evidence.\n"
        )
        f.write("\nSOURCE FILES MODIFIED: NO\n")
        f.write("SIMULATION INPUTS MODIFIED: NO\n")
        f.write("ACTUAL HORMUZ TRANSIT ESTABLISHED: NO\n")
        f.write("HYPOTHETICAL EXPOSURE APPROVALS: NONE\n")
        f.write("DISRUPTION MAGNITUDES SELECTED: NONE\n")

    print("=" * 96)
    print("SCRIPT 67: DISRUPTION MECHANISM AND OPERATIONAL EXPOSURE ASSESSMENT")
    print("=" * 96)
    print(f"Network edges: {len(edge)} | Ports: {len(port)} | Transition records: {len(trans)}")
    print(f"Edges with observed transitions: {int(edge['Observed_Transition_Exists_67'].sum())}")
    print(f"Mechanisms mapped: {len(mechanisms)}")
    print(f"Readiness checks: {int(check_df['Passed'].sum())}/{len(check_df)} passed")
    print("\nOutputs:")
    for p in [OUT_EDGE, OUT_PORT, OUT_MECHANISM, OUT_DECISION,
              TABLES / "67_researcher_port_exposure_review_log.csv",
              OUT_CHECKS, OUT_REPORT]:
        print(p.relative_to(ROOT))
    print("\nACTUAL HORMUZ TRANSIT ESTABLISHED: NO")
    print("HYPOTHETICAL EXPOSURE APPROVALS: NONE")
    print("SCRIPT 67 COMPLETED")


if __name__ == "__main__":
    main()
