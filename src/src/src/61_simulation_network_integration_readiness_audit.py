"""
SCRIPT 61: SIMULATION NETWORK INTEGRATION READINESS AUDIT
=========================================================
Read-only integration audit using the actual Script 19, Script 21 and Script 59
source files.

This script:
- validates node, edge, transition, service, vessel and historical schedule keys;
- compares the Script 59 eligibility register against the existing 19-node network;
- distinguishes already-present locations from candidate locations not in the
  observed network;
- records that Script 59 currently approves no empirical-baseline or sensitivity
  model additions and verifies no independently confirmed AIS Hormuz transit;
- creates audit manifests only. It does NOT add/remove nodes or edges, alter
  simulation inputs, approve coordinates, or change upstream files.

Run from project root:
    python src/61_simulation_network_integration_readiness_audit.py

Required inputs:
    outputs/tables/21_port_network_metrics.csv
    outputs/tables/21_port_connection_metrics.csv
    data/simulation_inputs/19_observed_interport_transitions.csv
    data/simulation_inputs/19_interport_time_parameters.csv
    data/simulation_inputs/19_port_parameters.csv
    data/simulation_inputs/19_port_service_parameters.csv
    data/simulation_inputs/19_vessel_parameters.csv
    data/simulation_inputs/19_historical_arrival_schedule.csv
    outputs/tables/59_operational_network_eligibility_register_v2.csv

Outputs:
    outputs/tables/61_network_node_integration_manifest.csv
    outputs/tables/61_network_edge_integration_manifest.csv
    outputs/tables/61_script59_eligibility_crosswalk.csv
    outputs/tables/61_integration_readiness_checks.csv
    outputs/reports/61_simulation_network_integration_readiness_report.txt
"""

from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
SIM = ROOT / "data" / "simulation_inputs"
REPORTS = ROOT / "outputs" / "reports"

INPUTS = {
    "nodes": TABLES / "21_port_network_metrics.csv",
    "edges": TABLES / "21_port_connection_metrics.csv",
    "transitions": SIM / "19_observed_interport_transitions.csv",
    "interport": SIM / "19_interport_time_parameters.csv",
    "ports": SIM / "19_port_parameters.csv",
    "service": SIM / "19_port_service_parameters.csv",
    "vessels": SIM / "19_vessel_parameters.csv",
    "schedule": SIM / "19_historical_arrival_schedule.csv",
    "eligibility": TABLES / "59_operational_network_eligibility_register_v2.csv",
}

OUT_NODE = TABLES / "61_network_node_integration_manifest.csv"
OUT_EDGE = TABLES / "61_network_edge_integration_manifest.csv"
OUT_GATE = TABLES / "61_script59_eligibility_crosswalk.csv"
OUT_CHECKS = TABLES / "61_integration_readiness_checks.csv"
OUT_REPORT = REPORTS / "61_simulation_network_integration_readiness_report.txt"


def require_columns(df, cols, label):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{label}: missing required columns: {missing}")


def clean_series(series):
    return series.astype("string").str.strip().str.upper()


def keyset(df, a, b):
    return set(zip(clean_series(df[a]).dropna(), clean_series(df[b]).dropna()))


def add_check(checks, name, passed, observed, expected, interpretation):
    checks.append({
        "Check": name,
        "Status": "PASS" if passed else "REVIEW_REQUIRED",
        "Observed": observed,
        "Expected": expected,
        "Interpretation": interpretation,
    })


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)

    missing_files = [str(p) for p in INPUTS.values() if not p.exists()]
    if missing_files:
        raise FileNotFoundError(
            "Required input file(s) not found. No outputs written:\n- "
            + "\n- ".join(missing_files)
        )

    data = {k: pd.read_csv(v) for k, v in INPUTS.items()}

    require_columns(data["nodes"], ["UNLOCODE", "Port_Name"], "network nodes")
    require_columns(data["edges"], ["Previous_Port", "Next_Port"], "network edges")
    require_columns(data["transitions"], ["Previous_Port", "Next_Port", "IMO_Normalised",
                                          "Elapsed_Hours_Between_Calls"], "observed transitions")
    require_columns(data["interport"], ["Previous_Port", "Next_Port"], "inter-port parameters")
    require_columns(data["ports"], ["UNLOCODE_Normalised"], "port parameters")
    require_columns(data["service"], ["UNLOCODE_Normalised"], "port service parameters")
    require_columns(data["vessels"], ["IMO_Normalised"], "vessel parameters")
    require_columns(data["schedule"], ["Simulation_Record_ID", "IMO_Normalised",
                                       "UNLOCODE_Normalised", "Actual_Arrival_UTC",
                                       "Actual_Departure_UTC", "Actual_Stay_Hours"],
                    "historical schedule")
    require_columns(data["eligibility"], ["UNLOCODE", "Script49_Eligibility_Classification",
                                          "Operational_Gate_Class_59_v2",
                                          "May_Enter_Empirical_Baseline_59_v2",
                                          "May_Enter_Sensitivity_Model_59_v2",
                                          "AIS_Hormuz_Transit_Independently_Verified_By_Script59_v2"],
                    "Script 59 eligibility register")

    nodes, edges = data["nodes"], data["edges"]
    transitions, interport = data["transitions"], data["interport"]
    ports, service, vessels, schedule = (
        data["ports"], data["service"], data["vessels"], data["schedule"]
    )
    gate = data["eligibility"]

    node_codes = set(clean_series(nodes["UNLOCODE"]).dropna())
    port_codes = set(clean_series(ports["UNLOCODE_Normalised"]).dropna())
    service_codes = set(clean_series(service["UNLOCODE_Normalised"]).dropna())
    schedule_codes = set(clean_series(schedule["UNLOCODE_Normalised"]).dropna())
    vessel_codes = set(clean_series(vessels["IMO_Normalised"]).dropna())
    schedule_vessels = set(clean_series(schedule["IMO_Normalised"]).dropna())

    edge_pairs = keyset(edges, "Previous_Port", "Next_Port")
    interport_pairs = keyset(interport, "Previous_Port", "Next_Port")
    transition_pairs = keyset(transitions, "Previous_Port", "Next_Port")

    gate_codes = set(clean_series(gate["UNLOCODE"]).dropna())
    gate_in_network = gate_codes & node_codes
    gate_outside_network = gate_codes - node_codes

    # Build node manifest from existing network nodes, preserving source metrics.
    node_manifest = nodes.copy()
    node_manifest["Present_In_Port_Parameters"] = clean_series(
        node_manifest["UNLOCODE"]
    ).isin(port_codes)
    node_manifest["Present_In_Service_Parameters"] = clean_series(
        node_manifest["UNLOCODE"]
    ).isin(service_codes)
    node_manifest["Present_In_Historical_Schedule"] = clean_series(
        node_manifest["UNLOCODE"]
    ).isin(schedule_codes)
    node_manifest["Integration_Disposition"] = np.where(
        node_manifest["Present_In_Port_Parameters"]
        & node_manifest["Present_In_Service_Parameters"]
        & node_manifest["Present_In_Historical_Schedule"],
        "EXISTING_HISTORICAL_NETWORK_NODE",
        "REVIEW_SOURCE_KEY_OR_COVERAGE",
    )
    node_manifest["Coordinate_Approval_Inferred"] = False
    node_manifest["Operational_Approval_Inferred"] = False

    # Edge manifest: preserve the directed edge list and attach parameter/transition counts.
    trans_counts = (
        transitions.assign(
            _origin=clean_series(transitions["Previous_Port"]),
            _destination=clean_series(transitions["Next_Port"]),
        )
        .groupby(["_origin", "_destination"], dropna=False)
        .size()
        .rename("Observed_Transition_Record_Count")
        .reset_index()
    )
    edge_manifest = edges.copy()
    edge_manifest["_origin"] = clean_series(edge_manifest["Previous_Port"])
    edge_manifest["_destination"] = clean_series(edge_manifest["Next_Port"])
    edge_manifest["Present_In_Interport_Parameters"] = [
        (a, b) in interport_pairs for a, b in zip(
            edge_manifest["_origin"], edge_manifest["_destination"]
        )
    ]
    edge_manifest["Observed_Transition_Pair"] = [
        (a, b) in transition_pairs for a, b in zip(
            edge_manifest["_origin"], edge_manifest["_destination"]
        )
    ]
    edge_manifest = edge_manifest.merge(
        trans_counts, on=["_origin", "_destination"], how="left", validate="one_to_one"
    )
    edge_manifest["Observed_Transition_Record_Count"] = (
        edge_manifest["Observed_Transition_Record_Count"].fillna(0).astype(int)
    )
    edge_manifest["Integration_Disposition"] = np.where(
        edge_manifest["Present_In_Interport_Parameters"]
        & edge_manifest["Observed_Transition_Pair"],
        "EXISTING_OBSERVED_DIRECTED_EDGE",
        "REVIEW_EDGE_PARAMETER_OR_TRANSITION_MISMATCH",
    )
    edge_manifest = edge_manifest.drop(columns=["_origin", "_destination"])

    # Crosswalk Script 59 decisions to the actual 19-node observed network.
    gate_manifest = gate.copy()
    gate_manifest["_code"] = clean_series(gate_manifest["UNLOCODE"])
    gate_manifest["Already_Present_In_Observed_Network"] = gate_manifest["_code"].isin(node_codes)
    gate_manifest["Candidate_Not_In_Observed_Network"] = ~gate_manifest[
        "Already_Present_In_Observed_Network"
    ]
    gate_manifest["Script59_Empirical_Baseline_Admission"] = (
        gate_manifest["May_Enter_Empirical_Baseline_59_v2"].fillna(False).astype(bool)
    )
    gate_manifest["Script59_Sensitivity_Admission"] = (
        gate_manifest["May_Enter_Sensitivity_Model_59_v2"].fillna(False).astype(bool)
    )
    gate_manifest["AIS_Transit_Independently_Verified"] = (
        gate_manifest[
            "AIS_Hormuz_Transit_Independently_Verified_By_Script59_v2"
        ].fillna(False).astype(bool)
    )
    gate_manifest["Script61_Integration_Disposition"] = np.select(
        [
            gate_manifest["Already_Present_In_Observed_Network"],
            gate_manifest["Candidate_Not_In_Observed_Network"]
            & gate_manifest["Script59_Sensitivity_Admission"],
            gate_manifest["Candidate_Not_In_Observed_Network"],
        ],
        [
            "ALREADY_IN_BASELINE_NETWORK_NO_DUPLICATE_NODE",
            "SENSITIVITY_ADMISSION_FLAGGED_REQUIRES_RESEARCHER_REVIEW",
            "NOT_ADMITTED_PENDING_RESEARCHER_APPROVAL_AND_MOVEMENT_EVIDENCE",
        ],
        default="REVIEW_REQUIRED",
    )
    gate_manifest = gate_manifest.drop(columns=["_code"])

    checks = []
    add_check(checks, "Unique network node identifiers",
              len(node_codes) == len(nodes), len(node_codes), len(nodes),
              "Each network node row should have a unique non-empty UN/LOCODE.")
    add_check(checks, "Network nodes match port parameter identifiers",
              node_codes == port_codes, len(node_codes & port_codes),
              f"{len(node_codes)} matching identifiers",
              "Checks node inventory against Script 19 port parameters.")
    add_check(checks, "Network nodes match port service identifiers",
              node_codes == service_codes, len(node_codes & service_codes),
              f"{len(node_codes)} matching identifiers",
              "Checks node inventory against Script 19 port service parameters.")
    add_check(checks, "Historical schedule uses existing network nodes",
              schedule_codes <= node_codes, len(schedule_codes - node_codes), 0,
              "Any schedule location outside the existing network requires review.")
    add_check(checks, "Network edges match inter-port parameter pairs",
              edge_pairs == interport_pairs, len(edge_pairs & interport_pairs),
              f"{len(edge_pairs)} matching directed pairs",
              "Direction is preserved: Previous_Port to Next_Port.")
    add_check(checks, "Network edges match observed transition pairs",
              edge_pairs == transition_pairs, len(edge_pairs & transition_pairs),
              f"{len(edge_pairs)} matching directed pairs",
              "Pair presence does not mean every edge has equal evidence strength.")
    add_check(checks, "Unique directed edge pairs",
              len(edge_pairs) == len(edges), len(edge_pairs), len(edges),
              "No duplicate directed pairs should exist in the network edge table.")
    add_check(checks, "Observed transition endpoints are network nodes",
              all(a in node_codes and b in node_codes for a, b in transition_pairs),
              len([p for p in transition_pairs if p[0] not in node_codes or p[1] not in node_codes]),
              0, "All observed transition endpoints should map to the network node set.")
    add_check(checks, "Schedule vessel identifiers match vessel parameters",
              schedule_vessels <= vessel_codes, len(schedule_vessels - vessel_codes), 0,
              "Checks schedule IMOs against the Script 19 vessel parameter table.")
    add_check(checks, "Historical schedule record identifiers unique",
              schedule["Simulation_Record_ID"].is_unique,
              int(schedule["Simulation_Record_ID"].nunique()), len(schedule),
              "Each historical schedule record should have a unique simulation ID.")
    arrivals = pd.to_datetime(schedule["Actual_Arrival_UTC"], utc=True, errors="coerce")
    departures = pd.to_datetime(schedule["Actual_Departure_UTC"], utc=True, errors="coerce")
    invalid_chronology = int((departures < arrivals).sum())
    missing_time = int((arrivals.isna() | departures.isna()).sum())
    add_check(checks, "Historical schedule timestamp chronology",
              invalid_chronology == 0 and missing_time == 0,
              f"negative durations={invalid_chronology}; missing/unparseable pairs={missing_time}",
              "0; 0", "This checks timestamp validity, not route or transit validity.")
    stay = pd.to_numeric(schedule["Actual_Stay_Hours"], errors="coerce")
    computed_stay = (departures - arrivals).dt.total_seconds() / 3600
    stay_diff = (stay - computed_stay).abs()
    stay_mismatch = int((stay_diff > 0.02).sum())
    add_check(checks, "Stored stay hours reconcile with timestamps",
              stay_mismatch == 0, stay_mismatch, 0,
              "Tolerance is 0.02 hours to allow rounding in stored duration.")
    add_check(checks, "Script 59 candidate register unique identifiers",
              gate["UNLOCODE"].nunique() == len(gate), gate["UNLOCODE"].nunique(), len(gate),
              "Script 59 must contain one decision row per location.")
    add_check(checks, "Script 59 empirical baseline admissions",
              int(gate_manifest["Script59_Empirical_Baseline_Admission"].sum()) == 0,
              int(gate_manifest["Script59_Empirical_Baseline_Admission"].sum()), 0,
              "No candidate is admitted to the empirical baseline in the current register.")
    add_check(checks, "Script 59 sensitivity admissions",
              int(gate_manifest["Script59_Sensitivity_Admission"].sum()) == 0,
              int(gate_manifest["Script59_Sensitivity_Admission"].sum()), 0,
              "No candidate is admitted to the sensitivity model in the current register.")
    add_check(checks, "Independently verified AIS Hormuz transit flags",
              int(gate_manifest["AIS_Transit_Independently_Verified"].sum()) == 0,
              int(gate_manifest["AIS_Transit_Independently_Verified"].sum()), 0,
              "No AIS-confirmed Hormuz transit is established by the current register.")

    checks_df = pd.DataFrame(checks)
    node_manifest.to_csv(OUT_NODE, index=False)
    edge_manifest.to_csv(OUT_EDGE, index=False)
    gate_manifest.to_csv(OUT_GATE, index=False)
    checks_df.to_csv(OUT_CHECKS, index=False)

    all_pass = checks_df["Status"].eq("PASS").all()
    with OUT_REPORT.open("w", encoding="utf-8") as f:
        f.write("=" * 88 + "\n")
        f.write("SCRIPT 61: SIMULATION NETWORK INTEGRATION READINESS AUDIT\n")
        f.write("=" * 88 + "\n\n")
        f.write("SOURCE FILE COUNTS\n")
        for key, df in data.items():
            f.write(f"- {INPUTS[key].relative_to(ROOT)}: {len(df):,} rows, {len(df.columns)} columns\n")
        f.write("\nNETWORK SNAPSHOT\n")
        f.write(f"- Existing network nodes: {len(nodes)}\n")
        f.write(f"- Existing directed edges: {len(edges)}\n")
        f.write(f"- Observed transition records: {len(transitions)}\n")
        f.write(f"- Unique observed transition pairs: {len(transition_pairs)}\n")
        f.write(f"- Historical schedule records: {len(schedule)}\n")
        f.write(f"- Unique vessels in schedule: {len(schedule_vessels)}\n")
        f.write("\nSCRIPT 59 CROSSWALK\n")
        f.write(f"- Eligibility-register locations: {len(gate)}\n")
        f.write(f"- Already present in observed network: {len(gate_in_network)}\n")
        f.write(f"- Not present in observed network: {len(gate_outside_network)}\n")
        f.write(f"- Empirical baseline admissions: {int(gate_manifest['Script59_Empirical_Baseline_Admission'].sum())}\n")
        f.write(f"- Sensitivity model admissions: {int(gate_manifest['Script59_Sensitivity_Admission'].sum())}\n")
        f.write(f"- Independently verified AIS Hormuz transit flags: {int(gate_manifest['AIS_Transit_Independently_Verified'].sum())}\n")
        f.write("\nLOCATIONS IN SCRIPT 59 NOT PRESENT IN THE OBSERVED NETWORK\n")
        if gate_outside_network:
            f.write(", ".join(sorted(gate_outside_network)) + "\n")
        else:
            f.write("None\n")
        f.write("\nVALIDATION CHECKS\n")
        f.write(checks_df.to_string(index=False))
        f.write("\n\nINTERPRETATION AND LIMITATIONS\n")
        f.write(
            "A PASS indicates structural consistency among the supplied files; it does not "
            "validate real-world sailing routes, berth capacity, physical feasibility, port "
            "coordinates, geopolitical accessibility, or actual Strait of Hormuz transit. "
            "Observed inter-port elapsed time is not pure sailing time. Script 59 currently "
            "admits no additional location to either the empirical baseline or sensitivity "
            "model. The integration manifests are review artifacts only and do not alter "
            "the existing network or simulation inputs.\n"
        )
        f.write("\nOVERALL STRUCTURAL AUDIT: " + ("PASS" if all_pass else "REVIEW REQUIRED") + "\n")

    print("=" * 88)
    print("SCRIPT 61: SIMULATION NETWORK INTEGRATION READINESS AUDIT")
    print("=" * 88)
    print(f"Nodes: {len(nodes)} | Directed edges: {len(edges)}")
    print(f"Observed transition records: {len(transitions)}")
    print(f"Historical schedule records: {len(schedule)}")
    print(f"Script 59 locations already in network: {len(gate_in_network)}")
    print(f"Script 59 locations outside network: {len(gate_outside_network)}")
    print(f"Empirical baseline admissions: {int(gate_manifest['Script59_Empirical_Baseline_Admission'].sum())}")
    print(f"Sensitivity admissions: {int(gate_manifest['Script59_Sensitivity_Admission'].sum())}")
    print("\nCHECK RESULTS")
    print(checks_df[["Check", "Status", "Observed", "Expected"]].to_string(index=False))
    print("\nOUTPUTS")
    for p in [OUT_NODE, OUT_EDGE, OUT_GATE, OUT_CHECKS, OUT_REPORT]:
        print(p.relative_to(ROOT))
    print("\nSOURCE FILES MODIFIED: NO")
    print("NETWORK NODES/EDGES ADDED OR REMOVED: NO")
    print("SCRIPT 61 COMPLETED")


if __name__ == "__main__":
    main()
