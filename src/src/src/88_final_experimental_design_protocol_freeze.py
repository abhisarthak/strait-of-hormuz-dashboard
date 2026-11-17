#!/usr/bin/env python3
"""Script 88 — Final Experimental Design and Protocol Freeze (proposal only).

This script consolidates the agreed primary mechanism and provisional pilot
factor levels into an auditable design specification. It does NOT approve
edge exposure, calibrate parameters, authorize simulation, or modify upstream
inputs. All numerical levels and recovery policies remain pending review.

Run from the project root:
    python src/88_final_experimental_design_protocol_freeze.py
"""
from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)

INPUTS = {
    "mechanism": TABLES / "68_mechanism_decision_register.csv",
    "edge": TABLES / "68_edge_exposure_decision_register.csv",
    "port": TABLES / "68_port_exposure_decision_register.csv",
    "scope": TABLES / "68_experiment_scope_decision_matrix.csv",
    "parameter": TABLES / "65_researcher_parameter_decision_log.csv",
    "protocol69": TABLES / "69_experiment_protocol_register.csv",
    "recovery76": TABLES / "76_recovery_policy_register.csv",
    "summary75": TABLES / "75_scenario_comparison_summary.csv",
    "summary76": TABLES / "76_scenario_recovery_comparison_summary.csv",
    "summary77": TABLES / "77_scenario_bounded_recovery_summary.csv",
}
missing = [str(p) for p in INPUTS.values() if not p.exists()]
if missing:
    print("ERROR: Required upstream files are missing:")
    print("\n".join(missing))
    sys.exit(1)
D = {k: pd.read_csv(v) for k, v in INPUTS.items()}

# The mechanism choice was explicitly confirmed by the researcher in this chat.
MECHANISM = "TRANSIT_ELAPSED_TIME_SHOCK"
SHOCK_HOURS = [6.0, 12.0, 24.0, 48.0]       # provisional pilot levels
SCOPE_SHARES = [0.10, 0.25, 0.50, 1.00]    # provisional pilot levels
SELECTION_SEED = 8801                      # proposed reproducibility seed
RECOVERY_IDS = [
    "R76-00-NONE", "R76-01-FIXED-6H", "R76-02-FIXED-12H",
    "R76-03-PROP-25-CAP6", "R76-04-PROP-50-CAP12",
]

# Fail closed if upstream decision registers unexpectedly contain approvals.
checks = []
def check(name, passed, observed, expected, note):
    checks.append({"Check": name, "Passed": bool(passed), "Observed": str(observed),
                   "Expected": str(expected), "Interpretation": note})

m = D["mechanism"]
primary = m[m["Mechanism"].astype(str) == MECHANISM]
check("Primary mechanism exists exactly once", len(primary) == 1, len(primary), 1,
      "The selected mechanism must map to one Script68 mechanism row.")
edge = D["edge"]
port = D["port"]
scope = D["scope"]
check("Script68 edge register contains 53 directed edges", len(edge) == 53, len(edge), 53,
      "Structural coverage only; not exposure approval.")
check("Script68 port register contains 19 ports", len(port) == 19, len(port), 19,
      "Structural coverage only; not port exposure approval.")
check("All edge exposure approvals remain false",
      not edge["Approved_For_Hypothetical_Exposure"].fillna(False).astype(bool).any(),
      int(edge["Approved_For_Hypothetical_Exposure"].fillna(False).astype(bool).sum()), 0,
      "Script88 must not silently approve any edge.")
check("All port exposure approvals remain false",
      not port["Approved_For_Hypothetical_Port_Disruption"].fillna(False).astype(bool).any(),
      int(port["Approved_For_Hypothetical_Port_Disruption"].fillna(False).astype(bool).sum()), 0,
      "Port disruption is outside the selected primary mechanism.")
check("All Script68 experiment scopes remain unapproved",
      not scope["Approved_To_Proceed"].fillna(False).astype(bool).any(),
      int(scope["Approved_To_Proceed"].fillna(False).astype(bool).sum()), 0,
      "Mechanism selection is not execution authorization.")
param = D["parameter"]
if "Researcher_Selected_Value_Hours" in param:
    selected_values = param["Researcher_Selected_Value_Hours"].notna().sum()
else:
    selected_values = -1
check("No Script65 final edge parameter values selected", selected_values == 0,
      selected_values, 0, "Observed quantiles remain descriptive references.")
check("Pilot Script75 scenario grid has 17 rows", len(D["summary75"]) == 17,
      len(D["summary75"]), 17, "Pilot design inventory check.")
check("Pilot Script76 scenario-policy grid has 85 rows", len(D["summary76"]) == 85,
      len(D["summary76"]), 85, "Pilot design inventory check.")
check("Pilot Script77 scenario-policy grid has 85 rows", len(D["summary77"]) == 85,
      len(D["summary77"]), 85, "Pilot design inventory check.")
check("All five recovery policies exist",
      set(RECOVERY_IDS).issubset(set(D["recovery76"]["Recovery_Policy_ID"].astype(str))),
      len(set(RECOVERY_IDS).intersection(set(D["recovery76"]["Recovery_Policy_ID"].astype(str)))), 5,
      "Policy identities are inherited from Script76, not validated operational capabilities.")

# Protocol record: mechanism selected, all execution and exposure gates remain pending.
protocol = pd.DataFrame([{
    "Protocol_ID": "P88-PRIMARY-01",
    "Primary_Mechanism": MECHANISM,
    "Researcher_Mechanism_Choice": "CONFIRMED_IN_CURRENT_CONVERSATION",
    "Operational_Interpretation": "Hypothetical additional inter-port departure-to-next-arrival elapsed time",
    "Elapsed_Time_Is_Pure_Sailing_Time": False,
    "Actual_Hormuz_Transit_Established": False,
    "Physical_Route_Interpretation": "NOT_ASSERTED",
    "Baseline": "Existing conservative 604-call historical schedule; unchanged",
    "Transition_Universe": "271 observed distinct-port sequence transitions; not validated physical routes",
    "Exposure_Selection": "Seeded random permutation with nested prefixes; candidate scope shares",
    "Selection_Seed_Proposed": SELECTION_SEED,
    "Shock_Hours_Candidate": ";".join(map(str, SHOCK_HOURS)),
    "Affected_Share_Candidate": ";".join(map(str, SCOPE_SHARES)),
    "Recovery_Policies_Candidate": ";".join(RECOVERY_IDS),
    "Replication_Status": "DETERMINISTIC_PILOT_REPRODUCTION_ONLY; stochastic replication not selected",
    "Primary_Outcome_Candidate": "Vessel final departure delay (hours)",
    "Secondary_Outcomes_Candidate": "Call arrival/departure delay; accumulated vessel delay; unrecovered calls/vessels; recovery credit",
    "Execution_Authorized": False,
    "Edge_Exposure_Approved": False,
    "Numerical_Levels_Approved": False,
    "Recovery_Policies_Approved": False,
    "Supervisor_Review_Status": "PENDING",
    "Protocol_Status": "DRAFT_FOR_RESEARCHER_AND_SUPERVISOR_REVIEW",
}])

# Factor register, explicitly separating proposal from approval.
factors = []
for h in SHOCK_HOURS:
    for share in SCOPE_SHARES:
        factors.append({
            "Scenario_ID": f"P88-S{int(share*100):03d}-H{int(h):02d}",
            "Mechanism": MECHANISM,
            "Shock_Magnitude_Hours": h,
            "Affected_Transition_Share": share,
            "Transition_Universe_Count": 271,
            "Selection_Method": "Seeded random permutation; nested prefixes across shares",
            "Selection_Seed_Proposed": SELECTION_SEED,
            "Interpretation": "Hypothetical additional observed inter-port elapsed time; not pure sailing time",
            "Parameter_Status": "PROVISIONAL_CANDIDATE_NOT_APPROVED",
            "Exposure_Status": "PENDING_EDGE_SCOPE_REVIEW",
            "Execution_Authorized": False,
        })
factor_df = pd.DataFrame(factors)

policies = D["recovery76"].copy()
policies = policies[policies["Recovery_Policy_ID"].astype(str).isin(RECOVERY_IDS)].copy()
policies["Protocol_Status"] = "PROVISIONAL_HYPOTHETICAL_POLICY_NOT_APPROVED"
policies["Operational_Capability_Evidence"] = "NOT_ESTABLISHED"
policies["Execution_Authorized"] = False

matrix = factor_df.merge(policies[["Recovery_Policy_ID", "Recovery_Policy", "Policy_Type",
                                    "Fixed_Recovery_Cap_Hours", "Proportional_Recovery_Rate",
                                    "Maximum_Recovery_Per_Link_Hours", "Protocol_Status"]], how="cross")
matrix["Experiment_Combination_ID"] = matrix["Scenario_ID"] + "__" + matrix["Recovery_Policy_ID"]
matrix["Recovery_Interpretation"] = "Hypothetical delay-reduction credit at subsequent vessel sequence links; feasibility not established"
matrix["Execution_Authorized"] = False

metrics = pd.DataFrame([
    ["M01", "Mean call arrival delay", "Call", "Hours", "Secondary", "Across all 604 calls; state observation-window censoring"],
    ["M02", "Mean call departure delay", "Call", "Hours", "Secondary", "Across all 604 calls; state observation-window censoring"],
    ["M03A", "Maximum final vessel departure delay", "Vessel", "Hours", "Primary candidate", "Maximum across 155 vessels at their final represented call"],
    ["M03B", "Maximum accumulated departure delay per vessel", "Vessel", "Hours", "Secondary", "Keep distinct from maximum final vessel delay"],
    ["M04", "Mean final vessel departure delay", "Vessel", "Hours", "Secondary", "Across represented vessels"],
    ["M05", "P90 call departure delay", "Call", "Hours", "Secondary", "Report quantile definition and zero-delay calls"],
    ["M06", "Total recovery credit", "Call/Vessel", "Hours", "Secondary", "Modelled credit, not observed operational recovery"],
    ["M07A", "Unrecovered call count", "Call", "Count", "Secondary", "Define threshold for unrecovered before final run"],
    ["M07B", "Unrecovered vessel count", "Vessel", "Count", "Secondary", "Define threshold and end-window censoring"],
], columns=["Metric_ID", "Metric", "Aggregation_Level", "Unit", "Priority", "Definition_or_Caveat"])

replication = pd.DataFrame([
    ["RP88-01", "Deterministic reproducibility", "One deterministic replay per fixed scenario/policy", "PROPOSED_FIRST_STAGE", "Confirm exact reproducibility and seed handling", False],
    ["RP88-02", "Stochastic replications", "Only if stochastic components are introduced; count based on pilot variance and precision target", "NOT_SELECTED", "Requires a declared estimand, precision target and variance pilot", False],
    ["RP88-03", "Paired/common random numbers", "Matched streams across policies/scenarios only if stochastic streams exist and implementation is validated", "CONDITIONAL_NOT_SELECTED", "No stochastic streams currently established by the deterministic pilot", False],
], columns=["Option_ID", "Option", "Definition", "Status", "Required_Decision", "Approved"])

limitations = pd.DataFrame([
    ["L01", "Observed elapsed time", "Includes sailing, waiting, anchorage, unobserved operations and data gaps; not pure sailing time."],
    ["L02", "Route semantics", "Observed consecutive port-call links are not validated physical sailing routes."],
    ["L03", "Hormuz transit", "No AIS-confirmed Strait of Hormuz transit established in this dataset."],
    ["L04", "Exposure", "No individual edge or geographic exposure scope is approved by selecting the mechanism."],
    ["L05", "Shock levels", "6/12/24/48 hours are inherited exploratory assumptions, not empirical estimates."],
    ["L06", "Scope shares", "10/25/50/100 percent are experimental coverage levels, not measured exposure probabilities."],
    ["L07", "Recovery", "Recovery credits are hypothetical allowances; no physical capability, safety, fuel, cost or emissions model."],
    ["L08", "Bounded recovery", "Observed inter-call elapsed time is not established schedule slack."],
    ["L09", "Port processes", "Observed port stay is not berth processing time; capacity and berth occupancy unavailable."],
    ["L10", "Validation", "Code consistency and synthetic checks do not constitute physical or operational validation."],
], columns=["Limitation_ID", "Topic", "Required_Qualification"])

out = {
    "88_protocol_register.csv": protocol,
    "88_scenario_factor_register.csv": factor_df,
    "88_scenario_policy_matrix.csv": matrix,
    "88_response_metric_register.csv": metrics,
    "88_replication_decision_register.csv": replication,
    "88_limitation_register.csv": limitations,
    "88_readiness_checks.csv": pd.DataFrame(checks),
}
for name, df in out.items():
    df.to_csv(TABLES / name, index=False)

passed = sum(c["Passed"] for c in checks)
failed = len(checks) - passed
report = f"""SCRIPT 88 — FINAL EXPERIMENTAL DESIGN AND PROTOCOL FREEZE (DRAFT)\n{'='*78}\n\nSTATUS\nPrimary mechanism choice recorded: {MECHANISM}\nReadiness checks: {passed}/{len(checks)} passed; {failed} failed\nProposed disruption scenarios: {len(factor_df)}\nProposed scenario-policy combinations: {len(matrix)}\nResponse metrics specified: {len(metrics)}\n\nRESEARCHER DECISION\nThe researcher confirmed TRANSIT_ELAPSED_TIME_SHOCK as the sole primary\ndisruption mechanism. This does not approve any particular edge, exposure scope,\nnumerical magnitude, recovery policy, or execution.\n\nPROVISIONAL FACTOR LEVELS\nShock magnitudes (hours): {SHOCK_HOURS}\nAffected transition shares: {SCOPE_SHARES}\nProposed selection seed: {SELECTION_SEED}\nTransition universe: 271 observed distinct-port sequence transitions.\nSelection: seeded random permutation with nested prefixes across scope levels.\n\nRECOVERY POLICIES\nFive Script76 policies are retained as provisional hypothetical policy options.\nThey are not measured operational capabilities. Script77's elapsed-time cap is\nnot schedule slack and is not automatically selected as the final rule.\n\nREPLICATION\nFirst stage proposes deterministic reproducibility. No stochastic replication\ncount is selected. Add replications only if stochastic model components are\nintroduced and a precision-based design is justified.\n\nNON-NEGOTIABLE LIMITATIONS\nObserved inter-port elapsed time is not pure sailing time. Observed port-call\nsequences are not validated physical routes. No AIS-confirmed Hormuz transit is\nestablished. No edge/port exposure approvals exist. No network closure, port\ncapacity or compound disruption is included in this primary experiment.\n\nAPPROVAL STATUS\nEdge exposure approvals: 0\nPort exposure approvals: 0\nNumerical levels approved: NO\nRecovery policies approved: NO\nSupervisor review: PENDING\nExperiment execution authorized: NO\nSource inputs modified: NO\nSimulation executed: NO\n\nOUTPUTS\n{chr(10).join('- outputs/tables/' + n for n in out)}\n- outputs/reports/88_final_experimental_design_protocol_freeze_report.txt\n"""
(REPORTS / "88_final_experimental_design_protocol_freeze_report.txt").write_text(report, encoding="utf-8")
print(report)
if failed:
    print("WARNING: One or more readiness checks failed. Review 88_readiness_checks.csv.")
    sys.exit(2)
print("Script 88 completed: draft specification only; no experiment executed or authorized.")
