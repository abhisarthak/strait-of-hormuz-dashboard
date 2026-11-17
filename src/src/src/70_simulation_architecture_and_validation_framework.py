#!/usr/bin/env python3
"""
SCRIPT 70: SIMULATION IMPLEMENTATION ARCHITECTURE AND MODEL VALIDATION FRAMEWORK

Read-only architecture discovery and validation-planning audit.
Scans existing Python source files and the established Script19 simulation inputs.
It does NOT edit source files, run simulations, change parameters, or authorize experiments.

Run from project root:
    python src/70_simulation_architecture_and_validation_framework.py

Required project structure:
    src/
    data/simulation_inputs/

Expected Script19 inputs:
    19_historical_arrival_schedule.csv
    19_vessel_parameters.csv
    19_port_parameters.csv
    19_port_service_parameters.csv
    19_interport_time_parameters.csv
    19_observed_interport_transitions.csv

Outputs:
    outputs/tables/70_source_code_inventory.csv
    outputs/tables/70_simulation_component_evidence.csv
    outputs/tables/70_baseline_data_contract.csv
    outputs/tables/70_model_validation_requirements.csv
    outputs/tables/70_architecture_readiness_checks.csv
    outputs/reports/70_simulation_architecture_and_validation_report.txt

Interpretation:
- Static source-code signatures are evidence of implementation constructs, not proof of runtime correctness.
- A missing signature does not prove a feature is absent if it is implemented indirectly or in another language.
- Validation requirements are proposed checks, not passed model-validation results.
- Historical port-call relationships are not physical routes; elapsed time is not pure sailing time.
"""

from pathlib import Path
import ast
import re
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SIM_INPUTS = ROOT / "data" / "simulation_inputs"
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"

EXPECTED_INPUTS = {
    "historical_schedule": ("19_historical_arrival_schedule.csv", 604,
        ["IMO_Normalised", "UNLOCODE_Normalised", "Actual_Arrival_UTC", "Actual_Departure_UTC"]),
    "vessel_parameters": ("19_vessel_parameters.csv", 155,
        ["IMO_Normalised"]),
    "port_parameters": ("19_port_parameters.csv", 19,
        ["UNLOCODE_Normalised"]),
    "port_service_parameters": ("19_port_service_parameters.csv", 19,
        ["UNLOCODE_Normalised"]),
    "interport_time_parameters": ("19_interport_time_parameters.csv", 53,
        ["Previous_Port", "Next_Port"]),
    "observed_interport_transitions": ("19_observed_interport_transitions.csv", 271,
        ["Previous_Port", "Next_Port"]),
}

OUTPUTS = {
    "inventory": TABLES / "70_source_code_inventory.csv",
    "components": TABLES / "70_simulation_component_evidence.csv",
    "data": TABLES / "70_baseline_data_contract.csv",
    "validation": TABLES / "70_model_validation_requirements.csv",
    "checks": TABLES / "70_architecture_readiness_checks.csv",
    "report": REPORTS / "70_simulation_architecture_and_validation_report.txt",
}

SIGNATURES = {
    "SimPy import": r"(^|\n)\s*(import\s+simpy|from\s+simpy\s+import)",
    "Environment": r"\b(simpy\.)?Environment\s*\(",
    "Resource": r"\b(simpy\.)?Resource\s*\(",
    "PriorityResource": r"\b(simpy\.)?PriorityResource\s*\(",
    "PreemptiveResource": r"\b(simpy\.)?PreemptiveResource\s*\(",
    "process": r"\.process\s*\(",
    "timeout": r"\.timeout\s*\(",
    "resource request": r"\.request\s*\(",
    "resource release": r"\.release\s*\(",
    "yield event": r"\byield\b",
    "random seed": r"(random\.seed|np\.random\.seed|numpy\.random\.seed|default_rng\s*\()",
    "NetworkX": r"(^|\n)\s*(import\s+networkx|from\s+networkx\s+import)",
    "shortest path": r"(shortest_path|all_simple_paths|single_source_dijkstra|dijkstra_path)",
    "pandas": r"(^|\n)\s*(import\s+pandas|from\s+pandas\s+import)",
    "validation/assertions": r"\b(assert|validate|validation|check_)\b",
    "event calendar": r"(heapq|PriorityQueue|event_calendar|event_queue)",
    "arrival/departure event": r"(arrival_time|departure_time|Arrival_Time|Departure_Time)",
    "vessel-level aggregation": r"(groupby\s*\([^)]*[Vv]essel|Vessel_ID)",
    "port-level aggregation": r"(groupby\s*\([^)]*[Pp]ort|Port_Code)",
}

def stop(message):
    print(f"ERROR: {message}")
    sys.exit(1)

def read_csv(path):
    try:
        return pd.read_csv(path, low_memory=False)
    except Exception as exc:
        stop(f"Unable to read {path}: {exc}")

def normalize_columns(df):
    return {str(c).strip().lower().replace(" ", "_"): c for c in df.columns}

def find_column(df, candidates):
    norm = normalize_columns(df)
    for candidate in candidates:
        key = candidate.lower().replace(" ", "_")
        if key in norm:
            return norm[key]
    return None

def scan_python(path):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return "", [], f"READ_ERROR: {exc}"
    try:
        ast.parse(text)
        syntax = "PARSE_OK"
    except SyntaxError as exc:
        syntax = f"SYNTAX_ERROR_LINE_{exc.lineno}"
    found = [name for name, pattern in SIGNATURES.items()
             if re.search(pattern, text, flags=re.MULTILINE)]
    return text, found, syntax

def classify_script(path, text):
    name = path.name.lower()
    if "simulation" in name or "replay" in name or "disruption" in name or "recovery" in name:
        return "SIMULATION_OR_EXPERIMENT"
    if "network" in name or "route" in name or "graph" in name:
        return "NETWORK_ANALYSIS"
    if "validation" in name or "audit" in name or "readiness" in name:
        return "VALIDATION_OR_AUDIT"
    if "parameter" in name or "scenario" in name:
        return "PARAMETER_OR_SCENARIO"
    if "visual" in name or "plot" in name:
        return "VISUALIZATION"
    if re.search(r"\bsimpy\b|\bEnvironment\s*\(|\bResource\s*\(", text):
        return "SIMULATION_OR_EXPERIMENT"
    return "OTHER"

def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    if not SRC.exists():
        stop(f"Source directory not found: {SRC}")
    if not SIM_INPUTS.exists():
        stop(f"Simulation input directory not found: {SIM_INPUTS}")

    py_files = sorted(SRC.glob("*.py"))
    if not py_files:
        stop(f"No Python source files found in {SRC}")

    inventory_rows = []
    component_rows = []
    for path in py_files:
        text, found, syntax = scan_python(path)
        inventory_rows.append({
            "Source_File": path.name,
            "Bytes": path.stat().st_size,
            "Line_Count": len(text.splitlines()),
            "Syntax_Status": syntax,
            "Architecture_Category": classify_script(path, text),
            "Detected_Signatures": "; ".join(found),
            "SimPy_Import_Detected": "SimPy import" in found,
            "Environment_Detected": "Environment" in found,
            "Resource_Detected": any(x in found for x in ["Resource", "PriorityResource", "PreemptiveResource"]),
            "Random_Seed_Detected": "random seed" in found,
            "NetworkX_Detected": "NetworkX" in found,
        })
        for signature in SIGNATURES:
            component_rows.append({
                "Source_File": path.name,
                "Architecture_Category": classify_script(path, text),
                "Component_or_Signature": signature,
                "Detected": signature in found,
                "Evidence_Type": "STATIC_SOURCE_SIGNATURE",
                "Interpretation": "Signature detected in source; runtime behavior is not established."
                    if signature in found else
                    "Signature not detected in this file; indirect implementation remains possible."
            })

    inventory = pd.DataFrame(inventory_rows)
    components = pd.DataFrame(component_rows)

    data_rows = []
    data_frames = {}
    for key, (filename, expected_rows, required_candidates) in EXPECTED_INPUTS.items():
        path = SIM_INPUTS / filename
        exists = path.exists()
        if exists:
            df = read_csv(path)
            data_frames[key] = df
            norm_cols = normalize_columns(df)
            missing = []
            resolved = {}
            for candidate in required_candidates:
                col = find_column(df, [candidate])
                if col is None:
                    missing.append(candidate)
                else:
                    resolved[candidate] = col
            data_rows.append({
                "Dataset_Key": key,
                "File_Name": filename,
                "Exists": True,
                "Observed_Rows": len(df),
                "Expected_Rows_From_Established_Pipeline": expected_rows,
                "Row_Count_Matches": len(df) == expected_rows,
                "Required_Columns": "; ".join(required_candidates),
                "Missing_Required_Columns": "; ".join(missing),
                "Resolved_Columns": "; ".join(f"{k}={v}" for k,v in resolved.items()),
                "Read_Status": "READ_OK" if not missing else "MISSING_REQUIRED_COLUMNS",
                "Interpretation": "Input contract check only; not proof of semantic validity."
            })
        else:
            data_rows.append({
                "Dataset_Key": key, "File_Name": filename, "Exists": False,
                "Observed_Rows": None, "Expected_Rows_From_Established_Pipeline": expected_rows,
                "Row_Count_Matches": False, "Required_Columns": "; ".join(required_candidates),
                "Missing_Required_Columns": "; ".join(required_candidates), "Resolved_Columns": "",
                "Read_Status": "FILE_MISSING",
                "Interpretation": "Required input not found at expected project path."
            })
    data_contract = pd.DataFrame(data_rows)

    # Requirements are explicit future validation obligations, not assertions that the model already passes.
    validation_rows = [
        ("V70-01", "Baseline reproducibility", "Replay the same historical input with deterministic settings and compare key outputs across repeated runs.", "Run-level", "Historical replay outputs and fixed configuration", "REQUIRED_BEFORE_EXPERIMENTS", "Not evaluated by this read-only script."),
        ("V70-02", "Schedule integrity", "Every call has valid vessel/port identifiers; arrival precedes departure; no unexplained duplicate call identifiers.", "Call-level", "Historical schedule", "REQUIRED", "Do not silently repair source records."),
        ("V70-03", "Event ordering", "At equal timestamps, event tie-breaking is explicit and deterministic; arrival/departure ordering is documented.", "Event-level", "Simulation event log", "REQUIRED", "Affects queue and concurrency calculations."),
        ("V70-04", "Time conservation", "For each call, simulated final time equals baseline time plus explicitly applied delay components.", "Call-level", "Call event log", "REQUIRED", "Keep baseline and induced delay separate."),
        ("V70-05", "Vessel delay propagation", "Delay propagation follows the declared vessel sequence and does not double-count the same delay.", "Vessel-level", "Vessel event history", "REQUIRED", "Separate call-level sum from vessel-level accumulated delay."),
        ("V70-06", "Resource queue validity", "If SimPy resources are used, requests/releases balance and resource capacity is explicit.", "Resource-level", "Resource event log and model config", "CONDITIONAL", "Do not interpret a hypothetical resource capacity as observed berth capacity."),
        ("V70-07", "Network transition validity", "A transition used for schedule replay must exist in the historical schedule evidence; it must not be represented as a physical route without independent route evidence.", "Transition-level", "Observed transitions and route evidence", "REQUIRED", "Schedule edge is not a geographic route."),
        ("V70-08", "Parameter provenance", "Every stochastic input is traceable to an approved empirical source or explicitly documented assumption.", "Parameter-level", "Parameter register and scenario config", "REQUIRED", "Script65 values remain unselected."),
        ("V70-09", "Randomness reproducibility", "Each replication records seed, random stream policy, and scenario/policy pairing key.", "Replication-level", "Run manifest", "REQUIRED_FOR_STOCHASTIC_RUNS", "Common random numbers require implementation verification."),
        ("V70-10", "End-window censoring", "Calls/vessels not recovered by the observation horizon are flagged as censored rather than assigned an invented recovery time.", "Call/vessel-level", "Run horizon and recovery status", "REQUIRED", "Define cohort and horizon before measuring unrecovered units."),
        ("V70-11", "Metric unit consistency", "Call-level, vessel-level, port-level and network-level metrics use distinct aggregation units.", "Metric-level", "Metric output tables", "REQUIRED", "M03 and M07 refinements from Script66/69 must be retained."),
        ("V70-12", "Extreme-value diagnostics", "Outliers and tail observations are investigated and reported; no automatic deletion or winsorization without justification.", "Parameter-level", "Transition observations and diagnostics", "REQUIRED", "IQR flags are investigation prompts only."),
        ("V70-13", "Scenario isolation", "Baseline and each disruption mechanism are independently configurable; compound scenarios are disabled until component mechanisms are validated.", "Scenario-level", "Scenario configuration", "REQUIRED", "Access restriction remains blocked; compound mechanism deferred."),
        ("V70-14", "Input immutability", "Experiment execution reads immutable source inputs and writes outputs to a separate run directory.", "Run-level", "File hashes and output manifest", "REQUIRED", "No source mutation."),
        ("V70-15", "Statistical inference", "Estimand, paired/unpaired design, confidence interval, multiplicity correction and sensitivity analyses are predeclared.", "Experiment-level", "Statistical analysis plan", "REQUIRED_BEFORE_INFERENCE", "Replication protocol remains unselected."),
    ]
    validation = pd.DataFrame(validation_rows, columns=[
        "Validation_ID", "Validation_Domain", "Required_Test_or_Control", "Analysis_Unit",
        "Evidence_Required", "Priority", "Research_Caution"
    ])
    validation["Current_Status"] = "NOT_ASSESSED_BY_SCRIPT70"
    validation["Observed_Result"] = ""
    validation["Researcher_Reviewer"] = ""
    validation["Review_Date"] = ""

    # Readiness checks cover static discovery and input contract only.
    checks = []
    def add(name, passed, observed, expected, note):
        checks.append({"Check": name, "Passed": bool(passed), "Observed": observed,
                       "Expected": expected, "Interpretation": note})
    add("Source directory contains Python files", len(py_files) > 0, len(py_files), ">0",
        "Inventory is limited to top-level src/*.py files.")
    add("All discovered Python files parse", inventory["Syntax_Status"].eq("PARSE_OK").all(),
        int(inventory["Syntax_Status"].eq("PARSE_OK").sum()), len(inventory),
        "AST parse check; does not execute code.")
    add("Historical schedule exists and row count matches",
        bool(data_contract.loc[data_contract.Dataset_Key=="historical_schedule","Row_Count_Matches"].iloc[0]),
        data_contract.loc[data_contract.Dataset_Key=="historical_schedule","Observed_Rows"].iloc[0], 604,
        "Row count check only.")
    add("Vessel parameter input exists and row count matches",
        bool(data_contract.loc[data_contract.Dataset_Key=="vessel_parameters","Row_Count_Matches"].iloc[0]),
        data_contract.loc[data_contract.Dataset_Key=="vessel_parameters","Observed_Rows"].iloc[0], 155,
        "Row count check only.")
    add("Port parameter input exists and row count matches",
        bool(data_contract.loc[data_contract.Dataset_Key=="port_parameters","Row_Count_Matches"].iloc[0]),
        data_contract.loc[data_contract.Dataset_Key=="port_parameters","Observed_Rows"].iloc[0], 19,
        "Row count check only.")
    add("Port service input exists and row count matches",
        bool(data_contract.loc[data_contract.Dataset_Key=="port_service_parameters","Row_Count_Matches"].iloc[0]),
        data_contract.loc[data_contract.Dataset_Key=="port_service_parameters","Observed_Rows"].iloc[0], 19,
        "Row count check only.")
    add("Inter-port parameter input exists and row count matches",
        bool(data_contract.loc[data_contract.Dataset_Key=="interport_time_parameters","Row_Count_Matches"].iloc[0]),
        data_contract.loc[data_contract.Dataset_Key=="interport_time_parameters","Observed_Rows"].iloc[0], 53,
        "Pair count and semantic suitability require separate audit.")
    add("Observed transition input exists and row count matches",
        bool(data_contract.loc[data_contract.Dataset_Key=="observed_interport_transitions","Row_Count_Matches"].iloc[0]),
        data_contract.loc[data_contract.Dataset_Key=="observed_interport_transitions","Observed_Rows"].iloc[0], 271,
        "Transition records are not physical route validation.")
    add("Architecture scan includes SimPy evidence column", "SimPy import" in SIGNATURES,
        "STATIC_SOURCE_SIGNATURE", "SimPy import signature",
        "Detected signature is not proof of model correctness.")
    add("Validation requirements remain unassessed",
        validation["Current_Status"].eq("NOT_ASSESSED_BY_SCRIPT70").all(),
        validation["Current_Status"].nunique(), 1,
        "This script does not claim runtime validation.")
    add("No simulation execution performed", True, "NO", "NO",
        "Read-only static scan and input contract check.")
    add("No source or simulation input modified", True, "NO", "NO",
        "Outputs are written only to outputs/tables and outputs/reports.")
    checks_df = pd.DataFrame(checks)

    inventory.to_csv(OUTPUTS["inventory"], index=False)
    components.to_csv(OUTPUTS["components"], index=False)
    data_contract.to_csv(OUTPUTS["data"], index=False)
    validation.to_csv(OUTPUTS["validation"], index=False)
    checks_df.to_csv(OUTPUTS["checks"], index=False)

    simpy_files = inventory.loc[inventory["SimPy_Import_Detected"], "Source_File"].tolist()
    env_files = inventory.loc[inventory["Environment_Detected"], "Source_File"].tolist()
    resource_files = inventory.loc[inventory["Resource_Detected"], "Source_File"].tolist()
    passed = int(checks_df.Passed.sum())
    report = f"""================================================================================
SCRIPT 70: SIMULATION IMPLEMENTATION ARCHITECTURE AND MODEL VALIDATION FRAMEWORK
================================================================================

SOURCE DISCOVERY
Top-level Python files scanned: {len(py_files)}
Files passing Python AST parse: {int(inventory.Syntax_Status.eq('PARSE_OK').sum())}
Files with SimPy import signature: {len(simpy_files)}
Files with Environment constructor signature: {len(env_files)}
Files with Resource constructor signature: {len(resource_files)}
SimPy import files: {', '.join(simpy_files) if simpy_files else 'NONE_DETECTED'}
Environment files: {', '.join(env_files) if env_files else 'NONE_DETECTED'}
Resource files: {', '.join(resource_files) if resource_files else 'NONE_DETECTED'}

SCRIPT19 INPUT CONTRACT
{data_contract[['Dataset_Key','File_Name','Exists','Observed_Rows','Expected_Rows_From_Established_Pipeline','Read_Status']].to_string(index=False)}

VALIDATION FRAMEWORK
Validation requirements defined: {len(validation)}
Runtime/model validation status: NOT ASSESSED
The requirements are future validation obligations, not passed tests.

READINESS CHECKS
Passed: {passed}/{len(checks_df)}

IMPORTANT LIMITATIONS
- Static source signatures do not establish runtime correctness.
- Source scan covers top-level Python files in src only.
- A missing signature does not prove a feature is absent if implemented indirectly.
- Historical port-call relationships are not validated physical sailing routes.
- Inter-port elapsed time is not pure sailing time.
- Port stay is not berth processing time.
- No actual Hormuz transit or geographic exposure is inferred.

SIMULATION EXECUTED: NO
MODEL VALIDATION CLAIMED: NO
EXPERIMENT AUTHORIZED: NO
SOURCE FILES MODIFIED: NO
SIMULATION INPUTS MODIFIED: NO
"""
    OUTPUTS["report"].write_text(report, encoding="utf-8")

    print("=" * 96)
    print("SCRIPT 70: SIMULATION IMPLEMENTATION ARCHITECTURE AND MODEL VALIDATION FRAMEWORK")
    print("=" * 96)
    print(f"Python files scanned: {len(py_files)}")
    print(f"SimPy import signatures: {len(simpy_files)} | Environment: {len(env_files)} | Resource: {len(resource_files)}")
    print(f"Readiness checks: {passed}/{len(checks_df)} passed")
    for path in OUTPUTS.values():
        print(path.relative_to(ROOT))
    print("SIMULATION EXECUTED: NO")
    print("MODEL VALIDATION CLAIMED: NO")
    print("SCRIPT 70 COMPLETED" if passed == len(checks_df) else "SCRIPT 70 COMPLETED WITH FAILED CHECKS")

if __name__ == "__main__":
    main()
