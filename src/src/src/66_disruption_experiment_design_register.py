"""
SCRIPT 66: DISRUPTION EXPERIMENT DESIGN REGISTER
================================================
Creates a controlled, auditable design framework for the next simulation
experiments. It uses the completed Script65 evidence register and existing
Script19 network/schedule inputs.

This is a design stage, NOT a simulation execution stage.

It does NOT:
- assign disruption magnitudes, probabilities, or affected-port selections;
- assume a real Strait of Hormuz closure or any actual transit exposure;
- declare any observed port or edge operationally validated;
- create rerouting paths or infer route feasibility;
- modify Scripts 19, 25, 28-36, or any upstream data;
- fit distributions, approve resampling, or change simulation parameters.

Required inputs:
    outputs/tables/65_parameter_option_register.csv
    outputs/tables/65_scenario_design_framework.csv
    data/simulation_inputs/19_historical_arrival_schedule.csv
    data/simulation_inputs/19_port_parameters.csv
    data/simulation_inputs/19_port_service_parameters.csv
    data/simulation_inputs/19_interport_time_parameters.csv

Outputs:
    outputs/tables/66_disruption_factor_register.csv
    outputs/tables/66_experiment_design_matrix.csv
    outputs/tables/66_response_metric_specification.csv
    outputs/tables/66_replication_protocol.csv
    outputs/tables/66_design_readiness_checks.csv
    outputs/reports/66_disruption_experiment_design_report.txt
"""

from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
SIM = ROOT / "data" / "simulation_inputs"
REPORTS = ROOT / "outputs" / "reports"

INPUTS = {
    "s65_options": TABLES / "65_parameter_option_register.csv",
    "s65_scenarios": TABLES / "65_scenario_design_framework.csv",
    "schedule": SIM / "19_historical_arrival_schedule.csv",
    "ports": SIM / "19_port_parameters.csv",
    "services": SIM / "19_port_service_parameters.csv",
    "edges": SIM / "19_interport_time_parameters.csv",
}

OUT_FACTORS = TABLES / "66_disruption_factor_register.csv"
OUT_MATRIX = TABLES / "66_experiment_design_matrix.csv"
OUT_METRICS = TABLES / "66_response_metric_specification.csv"
OUT_REPLICATION = TABLES / "66_replication_protocol.csv"
OUT_CHECKS = TABLES / "66_design_readiness_checks.csv"
OUT_REPORT = REPORTS / "66_disruption_experiment_design_report.txt"

PAIR = ["Previous_Port", "Next_Port"]


def require(df, columns, label):
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def normalized(series):
    return series.astype("string").str.strip().str.upper()


def unique_nonnull(series):
    return int(series.dropna().nunique())


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    for label, path in INPUTS.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing {label} input: {path}")

    s65 = pd.read_csv(INPUTS["s65_options"])
    s65_scenarios = pd.read_csv(INPUTS["s65_scenarios"])
    schedule = pd.read_csv(INPUTS["schedule"])
    ports = pd.read_csv(INPUTS["ports"])
    services = pd.read_csv(INPUTS["services"])
    edges = pd.read_csv(INPUTS["edges"])

    require(s65, PAIR + [
        "Assignment_Classification_64", "Parameter_Treatment_65",
        "Valid_Elapsed_Record_Count", "Distinct_Vessel_Count",
        "Final_Selected_Value_Hours_65", "Researcher_Decision_Status_65",
        "Empirical_Resampling_Approved_65", "Script19_Inputs_Modified_65"
    ], "Script65 parameter option register")
    require(s65_scenarios, ["Scenario_ID_65", "Scenario_Name_65", "Numerical_Value_Status_65"],
            "Script65 scenario framework")
    require(schedule, [
        "Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised",
        "Actual_Arrival_UTC", "Actual_Departure_UTC", "Actual_Stay_Hours"
    ], "Script19 historical schedule")
    require(ports, ["UNLOCODE_Normalised", "observed_call_count", "Port_Capacity_Status",
                    "Berth_Capacity_Status", "Hormuz_Transit_Status"],
            "Script19 port parameters")
    require(services, ["UNLOCODE_Normalised", "sample_size", "mean_stay_hours",
                       "median_stay_hours", "p90_stay_hours", "Interpretation"],
            "Script19 port service parameters")
    require(edges, PAIR + ["sample_size", "mean_elapsed_hours", "median_elapsed_hours",
                           "p90_elapsed_hours", "Interpretation"],
            "Script19 inter-port parameters")

    # Validate identities and the historical schedule without inferring route feasibility.
    for label, df, col in [
        ("schedule", schedule, "Simulation_Record_ID"),
        ("ports", ports, "UNLOCODE_Normalised"),
        ("services", services, "UNLOCODE_Normalised"),
    ]:
        if df[col].isna().any() or df[col].astype(str).str.strip().eq("").any():
            raise ValueError(f"{label} contains blank {col}.")
    if schedule["Simulation_Record_ID"].duplicated().any():
        raise ValueError("Schedule contains duplicate Simulation_Record_ID.")
    if ports["UNLOCODE_Normalised"].duplicated().any():
        raise ValueError("Port parameter table contains duplicate port IDs.")
    if services["UNLOCODE_Normalised"].duplicated().any():
        raise ValueError("Port service table contains duplicate port IDs.")
    if edges.duplicated(PAIR).any():
        raise ValueError("Inter-port parameter table contains duplicate directed edges.")

    schedule["UNLOCODE_Normalised"] = normalized(schedule["UNLOCODE_Normalised"])
    ports["UNLOCODE_Normalised"] = normalized(ports["UNLOCODE_Normalised"])
    services["UNLOCODE_Normalised"] = normalized(services["UNLOCODE_Normalised"])
    s65["_origin"] = normalized(s65["Previous_Port"])
    s65["_destination"] = normalized(s65["Next_Port"])
    edges["_origin"] = normalized(edges["Previous_Port"])
    edges["_destination"] = normalized(edges["Next_Port"])

    node_ids = set(ports["UNLOCODE_Normalised"])
    schedule_nodes = set(schedule["UNLOCODE_Normalised"])
    edge_pairs = set(zip(edges["_origin"], edges["_destination"]))
    s65_pairs = set(zip(s65["_origin"], s65["_destination"]))
    if len(s65) != 53 or len(edges) != 53:
        raise ValueError(f"Expected 53 edges in Script65 and Script19; got {len(s65)} and {len(edges)}.")
    if s65_pairs != edge_pairs:
        raise ValueError("Script65 and Script19 directed edge sets do not match.")
    if not schedule_nodes.issubset(node_ids):
        raise ValueError("Historical schedule contains ports absent from Script19 port parameter table.")
    if not set(edges["_origin"]).union(set(edges["_destination"])).issubset(node_ids):
        raise ValueError("An edge endpoint is absent from Script19 port parameter table.")

    # The factors are definitions and researcher-input slots, not selected values.
    factors = pd.DataFrame([
        {
            "Factor_ID_66": "F01",
            "Factor_Name_66": "Disruption mechanism",
            "Definition_66": "What operational process is hypothetically affected.",
            "Permissible_Design_Levels_66": "TRANSIT_ELAPSED_TIME_SHOCK; NETWORK_ACCESS_RESTRICTION; PORT_SERVICE_DISRUPTION; COMPOUND_MECHANISM",
            "Current_Selection_66": "NOT_SELECTED",
            "Researcher_Input_Required_66": "Select one mechanism and define the causal interpretation.",
            "Evidence_Status_66": "HYPOTHETICAL_DESIGN_ONLY",
            "Guardrail_66": "Do not infer actual Strait closure, transit exposure, or route infeasibility."
        },
        {
            "Factor_ID_66": "F02",
            "Factor_Name_66": "Disruption severity",
            "Definition_66": "Magnitude of the selected mechanism.",
            "Permissible_Design_Levels_66": "RESEARCHER_DEFINED_LEVELS",
            "Current_Selection_66": "NOT_SET",
            "Researcher_Input_Required_66": "Specify levels and units appropriate to the mechanism.",
            "Evidence_Status_66": "NO_MAGNITUDES_ASSIGNED",
            "Guardrail_66": "Do not reuse prior exploratory delay magnitudes as calibrated estimates."
        },
        {
            "Factor_ID_66": "F03",
            "Factor_Name_66": "Disruption duration",
            "Definition_66": "Length of time the hypothetical disruption remains active.",
            "Permissible_Design_Levels_66": "RESEARCHER_DEFINED_DURATION_LEVELS",
            "Current_Selection_66": "NOT_SET",
            "Researcher_Input_Required_66": "Specify duration levels and time unit.",
            "Evidence_Status_66": "NO_DURATIONS_ASSIGNED",
            "Guardrail_66": "Duration is distinct from the delay imposed on an individual call."
        },
        {
            "Factor_ID_66": "F04",
            "Factor_Name_66": "Onset timing",
            "Definition_66": "When the hypothetical disruption begins relative to the observation window.",
            "Permissible_Design_Levels_66": "EARLY; MIDDLE; LATE; RESEARCHER_DEFINED",
            "Current_Selection_66": "NOT_SET",
            "Researcher_Input_Required_66": "Define onset rule and common comparison window.",
            "Evidence_Status_66": "DESIGN_CHOICE_REQUIRED",
            "Guardrail_66": "Do not choose onset to manufacture a desired outcome."
        },
        {
            "Factor_ID_66": "F05",
            "Factor_Name_66": "Affected network scope",
            "Definition_66": "Which nodes, edges, calls, or vessel movements are exposed in the experiment.",
            "Permissible_Design_Levels_66": "EDGE_SUBSET; NODE_SUBSET; VESSEL_SUBSET; NETWORK_WIDE",
            "Current_Selection_66": "NOT_SELECTED",
            "Researcher_Input_Required_66": "Provide an explicit, evidence-traceable inclusion list.",
            "Evidence_Status_66": "PENDING_RESEARCHER_AND_OPERATIONAL_REVIEW",
            "Guardrail_66": "The 19-node observed network is not a validated Hormuz route network; do not equate geographic proximity with exposure."
        },
        {
            "Factor_ID_66": "F06",
            "Factor_Name_66": "Recovery policy",
            "Definition_66": "Operational response applied after disruption.",
            "Permissible_Design_Levels_66": "NO_RECOVERY; FIXED_RECOVERY; PARTIAL_RECOVERY; RESEARCHER_DEFINED",
            "Current_Selection_66": "NOT_SELECTED",
            "Researcher_Input_Required_66": "Define policy rule, trigger, constraints and resource assumptions.",
            "Evidence_Status_66": "PRIOR_EXPLORATORY_POLICIES_EXIST",
            "Guardrail_66": "Recovery performance is conditional on the prior model assumptions; do not call it an operational recommendation."
        },
        {
            "Factor_ID_66": "F07",
            "Factor_Name_66": "Port service response",
            "Definition_66": "Whether disruption changes port-call stay/service duration.",
            "Permissible_Design_Levels_66": "UNCHANGED; INCREASED; CAPACITY_CONSTRAINED; RESEARCHER_DEFINED",
            "Current_Selection_66": "NOT_SELECTED",
            "Researcher_Input_Required_66": "Separate observed port stay from any assumed service-time response.",
            "Evidence_Status_66": "OBSERVED_STAY_DESCRIPTIVE_ONLY",
            "Guardrail_66": "Observed port stay is not pure berth processing time; port and berth capacities are unavailable."
        },
        {
            "Factor_ID_66": "F08",
            "Factor_Name_66": "Randomness and replication",
            "Definition_66": "Stochastic replication and paired random-stream control.",
            "Permissible_Design_Levels_66": "DETERMINISTIC; STOCHASTIC_PAIRED; STOCHASTIC_UNPAIRED",
            "Current_Selection_66": "NOT_SELECTED",
            "Researcher_Input_Required_66": "Set replication count, seed policy and common-random-number policy.",
            "Evidence_Status_66": "PROTOCOL_REQUIRED",
            "Guardrail_66": "Replication count is not a substitute for structural or external validation."
        }
    ])

    # Experiment families are deliberately unparameterized.
    matrix = pd.DataFrame([
        {
            "Experiment_ID_66": "E66-00", "Experiment_Family_66": "Baseline replay",
            "Mechanism_66": "NONE", "Severity_Level_66": "NOT_APPLICABLE",
            "Duration_Level_66": "NOT_APPLICABLE", "Onset_Rule_66": "COMMON_HISTORICAL_WINDOW",
            "Affected_Scope_66": "EXISTING_604_CALL_HISTORICAL_SCHEDULE",
            "Recovery_Policy_66": "AS_DEFINED_IN_BASELINE_MODEL",
            "Port_Service_Response_66": "UNCHANGED",
            "Replication_Design_66": "DETERMINISTIC_OR_EXISTING_BASELINE_PROTOCOL",
            "Status_66": "REFERENCE_CASE_NOT_NEWLY_CALIBRATED",
            "Required_Approval_66": "Confirm baseline model and observation-window limitations."
        },
        {
            "Experiment_ID_66": "E66-01", "Experiment_Family_66": "Inter-port elapsed-time shock",
            "Mechanism_66": "TRANSIT_ELAPSED_TIME_SHOCK", "Severity_Level_66": "NOT_SET",
            "Duration_Level_66": "NOT_SET", "Onset_Rule_66": "NOT_SET",
            "Affected_Scope_66": "EXPLICIT_EDGE_OR_VESSEL_LIST_REQUIRED",
            "Recovery_Policy_66": "COMPARE_DEFINED_POLICIES",
            "Port_Service_Response_66": "UNCHANGED",
            "Replication_Design_66": "TO_BE_SELECTED",
            "Status_66": "DESIGN_TEMPLATE_ONLY",
            "Required_Approval_66": "Define shock units, exposure list and why elapsed time is the affected process."
        },
        {
            "Experiment_ID_66": "E66-02", "Experiment_Family_66": "Network access restriction",
            "Mechanism_66": "NETWORK_ACCESS_RESTRICTION", "Severity_Level_66": "NOT_SET",
            "Duration_Level_66": "NOT_SET", "Onset_Rule_66": "NOT_SET",
            "Affected_Scope_66": "EXPLICIT_EDGE_LIST_REQUIRED",
            "Recovery_Policy_66": "COMPARE_DEFINED_POLICIES",
            "Port_Service_Response_66": "UNCHANGED",
            "Replication_Design_66": "TO_BE_SELECTED",
            "Status_66": "BLOCKED_PENDING_NETWORK_FEASIBILITY_EVIDENCE",
            "Required_Approval_66": "Demonstrate affected edge meaning and feasible alternatives before modelling closure or rerouting."
        },
        {
            "Experiment_ID_66": "E66-03", "Experiment_Family_66": "Port service disruption",
            "Mechanism_66": "PORT_SERVICE_DISRUPTION", "Severity_Level_66": "NOT_SET",
            "Duration_Level_66": "NOT_SET", "Onset_Rule_66": "NOT_SET",
            "Affected_Scope_66": "EXPLICIT_PORT_LIST_REQUIRED",
            "Recovery_Policy_66": "COMPARE_DEFINED_POLICIES",
            "Port_Service_Response_66": "NOT_SET",
            "Replication_Design_66": "TO_BE_SELECTED",
            "Status_66": "DESIGN_TEMPLATE_ONLY",
            "Required_Approval_66": "Separate port-stay assumptions from berth capacity and validate port scope."
        },
        {
            "Experiment_ID_66": "E66-04", "Experiment_Family_66": "Compound disruption",
            "Mechanism_66": "COMPOUND_MECHANISM",
            "Severity_Level_66": "NOT_SET", "Duration_Level_66": "NOT_SET",
            "Onset_Rule_66": "NOT_SET",
            "Affected_Scope_66": "EXPLICIT_SCOPE_LIST_REQUIRED",
            "Recovery_Policy_66": "COMPARE_DEFINED_POLICIES",
            "Port_Service_Response_66": "NOT_SET",
            "Replication_Design_66": "TO_BE_SELECTED",
            "Status_66": "DEFER_UNTIL_SINGLE_MECHANISMS_DEFINED",
            "Required_Approval_66": "Define individual mechanisms first; avoid confounding their effects."
        }
    ])

    metrics = pd.DataFrame([
        ["M01", "Call-level accumulated delay", "Sum of delay across affected calls in the defined analysis window", "Hours", "Primary schedule-impact metric", "Not unique-vessel delay; disclose call weighting."],
        ["M02", "Final vessel delay", "Delay at the final observed/simulated call for each vessel", "Hours", "Vessel-level impact", "Report distribution across vessels, not only maximum."],
        ["M03", "Maximum vessel delay", "Maximum final or accumulated vessel delay, clearly specified", "Hours", "Tail-impact metric", "Sensitive to late-window disruption onset."],
        ["M04", "Peak concurrent calls", "Maximum simultaneous active calls in the defined network/window", "Calls", "Network activity indicator", "Not berth occupancy or validated congestion."],
        ["M05", "Time above concurrency threshold", "Duration network concurrency exceeds a predeclared threshold", "Hours", "Network activity persistence", "Threshold must be justified and is not berth capacity."],
        ["M06", "Recovery completion time", "Time from disruption onset until the selected recovery criterion is met", "Hours", "Recovery performance", "Define criterion before running experiments."],
        ["M07", "Unrecovered calls/vessels", "Count remaining outside the recovery criterion at the end of the window", "Count", "Residual impact", "Define denominator and treatment of right-censoring."],
        ["M08", "Port-level delay distribution", "Delay summarized by port using consistent aggregation", "Hours", "Spatial heterogeneity", "Distinguish per-port mean from pooled network mean."],
        ["M09", "Scenario feasibility flags", "Count of decisions violating explicitly modelled constraints", "Count", "Model feasibility", "Only meaningful if constraints and operational evidence exist."],
        ["M10", "Economic impact", "Cost of delay, diversion, fuel or service disruption", "Currency / unit", "Optional future outcome", "Not computable without defensible cost and route/fuel inputs."],
        ["M11", "Emissions impact", "Change in emissions from additional time, speed or rerouting", "CO2e", "Optional future sustainability outcome", "Not computable without vessel, fuel, speed and route data."]
    ], columns=["Metric_ID_66", "Metric_Name_66", "Operational_Definition_66", "Unit_66",
                "Role_66", "Interpretation_Guardrail_66"])

    replication = pd.DataFrame([
        ["R01", "Paired scenario comparisons", "Use identical seed identifiers and aligned random streams across policies/scenarios where stochastic components are shared.", "RECOMMENDED", "Must verify random-stream alignment in implementation."],
        ["R02", "Replication count", "Choose based on pilot variance and Monte Carlo precision; report standard errors or confidence intervals.", "NOT_SET", "Do not assume prior 30-replication design is automatically adequate."],
        ["R03", "Seed register", "Store every seed and map it to scenario, policy and replication.", "REQUIRED", "Reproducibility requirement."],
        ["R04", "Warm-up and observation window", "Use a common declared analysis window; justify any warm-up or truncation.", "REQUIRED", "Historical schedule spans a finite observed window."],
        ["R05", "Uncertainty reporting", "Report means plus dispersion/intervals and paired differences where applicable.", "REQUIRED", "Separate Monte Carlo uncertainty from data/model uncertainty."],
        ["R06", "Sensitivity design", "Vary one factor at a time initially; use factorial/interaction design only after factor levels are justified.", "RECOMMENDED", "Avoid confounding disruption mechanism, scope and recovery policy."],
        ["R07", "Model validation", "Document conceptual, input, implementation and output validation separately.", "REQUIRED", "Replication does not validate structural assumptions."]
    ], columns=["Protocol_ID_66", "Protocol_Element_66", "Specification_66", "Status_66", "Caveat_66"])

    # Readiness checks: design artifacts should be complete, while selections remain intentionally blank.
    checks = []
    def ck(name, passed, observed, expected):
        checks.append({"Check": name, "Passed": bool(passed),
                       "Observed": str(observed), "Expected": str(expected)})

    ck("Script65 edge count", len(s65) == 53, len(s65), 53)
    ck("Script19 inter-port edge count", len(edges) == 53, len(edges), 53)
    ck("Script65 and Script19 edge sets match", s65_pairs == edge_pairs, len(s65_pairs & edge_pairs), 53)
    ck("Historical schedule rows", len(schedule) == 604, len(schedule), 604)
    ck("Unique historical schedule IDs", schedule["Simulation_Record_ID"].is_unique,
       schedule["Simulation_Record_ID"].nunique(), len(schedule))
    ck("All schedule ports represented in port parameters", schedule_nodes.issubset(node_ids),
       len(schedule_nodes - node_ids), 0)
    ck("All edge endpoints represented in port parameters",
       set(edges["_origin"]).union(set(edges["_destination"])).issubset(node_ids),
       len(set(edges["_origin"]).union(set(edges["_destination"])) - node_ids), 0)
    ck("Script65 decisions still pending",
       s65["Researcher_Decision_Status_65"].astype(str).eq("PENDING_RESEARCHER_REVIEW").all(),
       int(s65["Researcher_Decision_Status_65"].astype(str).eq("PENDING_RESEARCHER_REVIEW").sum()), 53)
    ck("No final parameter values selected",
       s65["Final_Selected_Value_Hours_65"].isna().all(),
       int(s65["Final_Selected_Value_Hours_65"].notna().sum()), 0)
    ck("No resampling approvals",
       ~s65["Empirical_Resampling_Approved_65"].fillna(False).astype(bool).any(),
       int(s65["Empirical_Resampling_Approved_65"].fillna(False).astype(bool).sum()), 0)
    ck("No disruption magnitudes assigned", matrix["Severity_Level_66"].isin(["NOT_SET", "NOT_APPLICABLE"]).all(),
       int((~matrix["Severity_Level_66"].isin(["NOT_SET", "NOT_APPLICABLE"])).sum()), 0)
    ck("No affected scope approved", matrix["Affected_Scope_66"].astype(str).str.contains("REQUIRED|EXISTING_604_CALL", regex=True).all(),
       int(matrix["Affected_Scope_66"].astype(str).str.contains("REQUIRED|EXISTING_604_CALL", regex=True).sum()), len(matrix))
    ck("Metrics have definitions", metrics["Operational_Definition_66"].notna().all(),
       int(metrics["Operational_Definition_66"].notna().sum()), len(metrics))
    ck("Replication protocol has no arbitrary count", not replication["Specification_66"].str.contains(r"\b30\b", regex=True).any(),
       int(replication["Specification_66"].str.contains(r"\b30\b", regex=True).sum()), 0)

    check_df = pd.DataFrame(checks)
    if not check_df["Passed"].all():
        raise ValueError("Script66 design readiness check failed; inspect source schemas and logic.")

    # Save deliverables; no source inputs are overwritten.
    factors.to_csv(OUT_FACTORS, index=False)
    matrix.to_csv(OUT_MATRIX, index=False)
    metrics.to_csv(OUT_METRICS, index=False)
    replication.to_csv(OUT_REPLICATION, index=False)
    check_df.to_csv(OUT_CHECKS, index=False)

    with OUT_REPORT.open("w", encoding="utf-8") as f:
        f.write("=" * 96 + "\n")
        f.write("SCRIPT 66: DISRUPTION EXPERIMENT DESIGN REGISTER\n")
        f.write("=" * 96 + "\n\n")
        f.write(f"Script65 parameter-option edges: {len(s65)}\n")
        f.write(f"Script19 directed edges: {len(edges)}\n")
        f.write(f"Historical schedule calls: {len(schedule)}\n")
        f.write(f"Observed network nodes: {len(node_ids)}\n")
        f.write(f"Disruption factors defined: {len(factors)}\n")
        f.write(f"Experiment families: {len(matrix)}\n")
        f.write(f"Response metrics specified: {len(metrics)}\n")
        f.write(f"Replication protocol elements: {len(replication)}\n\n")
        f.write("READINESS CHECKS\n")
        f.write(check_df.to_string(index=False))
        f.write("\n\nKEY INTERPRETATION\n")
        f.write(
            "Script66 creates a design framework only. It assigns no disruption magnitude, "
            "duration, probability, onset, affected edge/port, or recovery parameter. A "
            "network-access restriction experiment is blocked pending evidence for edge meaning "
            "and feasible alternatives. The observed 19-node network and 53 directed pairs are "
            "historical schedule relationships, not a validated geographic route network. "
            "Observed port stay is not berth processing time; capacity fields are unavailable. "
            "Concurrency is not berth occupancy. No actual Hormuz transit is established. "
            "Economic and emissions metrics require additional defensible inputs.\n"
        )
        f.write("\nSOURCE FILES MODIFIED: NO\n")
        f.write("SIMULATION INPUTS MODIFIED: NO\n")
        f.write("DISRUPTION MAGNITUDES SELECTED: NONE\n")
        f.write("AFFECTED PORTS/EDGES APPROVED: NONE\n")
        f.write("SIMULATION EXECUTED: NO\n")

    print("=" * 96)
    print("SCRIPT 66: DISRUPTION EXPERIMENT DESIGN REGISTER")
    print("=" * 96)
    print(f"Historical schedule calls: {len(schedule)}")
    print(f"Network nodes: {len(node_ids)} | Directed edges: {len(edges)}")
    print(f"Disruption factors: {len(factors)}")
    print(f"Experiment families: {len(matrix)}")
    print(f"Response metrics: {len(metrics)}")
    print(f"Replication protocol elements: {len(replication)}")
    print(f"Readiness checks: {int(check_df['Passed'].sum())}/{len(check_df)} passed")
    print("\nOutputs:")
    for p in [OUT_FACTORS, OUT_MATRIX, OUT_METRICS, OUT_REPLICATION, OUT_CHECKS, OUT_REPORT]:
        print(p.relative_to(ROOT))
    print("\nDISRUPTION MAGNITUDES SELECTED: NONE")
    print("AFFECTED PORTS/EDGES APPROVED: NONE")
    print("SIMULATION EXECUTED: NO")
    print("SCRIPT 66 COMPLETED")


if __name__ == "__main__":
    main()
