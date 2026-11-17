#!/usr/bin/env python3
"""
SCRIPT 72: CANONICAL BASELINE REPLAY SPECIFICATION AND DISRUPTION-MODEL READINESS

Purpose
-------
Create a read-only, evidence-traceable specification for the canonical
historical baseline and the future vessel-level disruption model.

This script does NOT:
- modify Scripts 19, 25, 26, 27, 28, or 30;
- modify any source dataset or upstream register;
- execute a disruption, recovery, routing, or optimization experiment;
- approve disruption magnitudes, affected ports/edges, route closures,
  recovery policies, or operational eligibility;
- infer actual Strait of Hormuz transit.

Run from the project root:
    python src/72_canonical_baseline_and_disruption_model_readiness.py

The script searches known project locations for the accepted source artifacts.
Core Script19 inputs are mandatory. Later audit/register files are optional:
if an optional artifact is absent or its schema is not recognized, the script
records that limitation rather than silently inventing values.

Outputs:
    outputs/tables/72_source_artifact_inventory.csv
    outputs/tables/72_canonical_baseline_data_contract.csv
    outputs/tables/72_vessel_call_representation_specification.csv
    outputs/tables/72_delay_propagation_specification.csv
    outputs/tables/72_baseline_invariants.csv
    outputs/tables/72_disruption_mechanism_readiness.csv
    outputs/tables/72_implementation_readiness_checks.csv
    outputs/reports/72_canonical_baseline_and_disruption_model_readiness.txt

Interpretation
--------------
The observed schedule records port-call intervals. Inter-port elapsed times
are departure-to-next-arrival elapsed times, not pure sailing times. Port-call
concurrency is not verified berth occupancy. No AIS-confirmed Hormuz transit
has been established in the current research evidence.
"""

from pathlib import Path
import sys
import json
import hashlib
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "data" / "simulation_inputs"
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"

for folder in (TABLES, REPORTS):
    folder.mkdir(parents=True, exist_ok=True)

OUT = {
    "inventory": TABLES / "72_source_artifact_inventory.csv",
    "contract": TABLES / "72_canonical_baseline_data_contract.csv",
    "calls": TABLES / "72_vessel_call_representation_specification.csv",
    "propagation": TABLES / "72_delay_propagation_specification.csv",
    "invariants": TABLES / "72_baseline_invariants.csv",
    "mechanisms": TABLES / "72_disruption_mechanism_readiness.csv",
    "checks": TABLES / "72_implementation_readiness_checks.csv",
    "report": REPORTS / "72_canonical_baseline_and_disruption_model_readiness.txt",
}

# Exact known Script19 core artifacts.
CORE_FILES = {
    "historical_schedule": SIM / "19_historical_arrival_schedule.csv",
    "vessel_parameters": SIM / "19_vessel_parameters.csv",
    "port_parameters": SIM / "19_port_parameters.csv",
    "port_service_parameters": SIM / "19_port_service_parameters.csv",
    "interport_parameters": SIM / "19_interport_time_parameters.csv",
    "observed_transitions": SIM / "19_observed_interport_transitions.csv",
}

# Known downstream artifacts. Optional artifacts are located by exact name
# first, then by a conservative prefix/keyword search.
OPTIONAL_CANDIDATES = {
    "network_nodes": [
        TABLES / "61_network_node_integration_manifest.csv",
    ],
    "network_edges": [
        TABLES / "61_network_edge_integration_manifest.csv",
    ],
    "edge_evidence": [
        TABLES / "62_edge_evidence_reliability_register.csv",
    ],
    "parameter_assignment": [
        TABLES / "64_evidence_based_parameter_assignment_register.csv",
    ],
    "exposure_edges": [
        TABLES / "67_edge_exposure_evidence_register.csv",
    ],
    "exposure_ports": [
        TABLES / "67_port_exposure_evidence_register.csv",
    ],
    "exposure_decisions": [
        TABLES / "68_mechanism_decision_register.csv",
    ],
    "edge_exposure_decisions": [
        TABLES / "68_edge_exposure_decision_register.csv",
    ],
    "port_exposure_decisions": [
        TABLES / "68_port_exposure_decision_register.csv",
    ],
    "experiment_scope": [
        TABLES / "68_experiment_scope_decision_matrix.csv",
    ],
    "scenario_parameters": [
        TABLES / "69_scenario_parameter_specification.csv",
    ],
    "protocol": [
        TABLES / "69_experiment_protocol_register.csv",
    ],
    "baseline_validation": [
        TABLES / "71_historical_replay_port_validation.csv",
    ],
    "baseline_records": [
        TABLES / "71_historical_replay_record_audit.csv",
    ],
    "baseline_timeline": [
        TABLES / "71_historical_replay_event_timeline.csv",
    ],
    "baseline_checks": [
        TABLES / "71_validation_checks.csv",
    ],
}

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def read_csv_safe(path):
    return pd.read_csv(path, low_memory=False)

def find_optional(key, paths):
    for p in paths:
        if p.exists():
            return p
    # Conservative fallback: only same Script prefix and distinctive keyword.
    prefix = key.split("_")[0]
    keyword = key.split("_", 1)[1] if "_" in key else key
    matches = sorted(TABLES.glob(f"{prefix}*{keyword}*.csv"))
    return matches[0] if len(matches) == 1 else None

def inventory_artifacts():
    rows = []
    loaded = {}
    for key, path in CORE_FILES.items():
        if path.exists():
            try:
                df = read_csv_safe(path)
                loaded[key] = (path, df)
                rows.append({
                    "Artifact_Key": key, "Path": str(path.relative_to(ROOT)),
                    "Required": True, "Available": True, "Rows": len(df),
                    "Columns": len(df.columns), "Column_List": " | ".join(df.columns),
                    "SHA256": sha256_file(path), "Read_Status": "READ_OK",
                })
            except Exception as exc:
                rows.append({
                    "Artifact_Key": key, "Path": str(path.relative_to(ROOT)),
                    "Required": True, "Available": True, "Rows": np.nan,
                    "Columns": np.nan, "Column_List": "",
                    "SHA256": sha256_file(path), "Read_Status": f"READ_ERROR: {exc}",
                })
        else:
            rows.append({
                "Artifact_Key": key, "Path": str(path.relative_to(ROOT)),
                "Required": True, "Available": False, "Rows": np.nan,
                "Columns": np.nan, "Column_List": "", "SHA256": "",
                "Read_Status": "MISSING_REQUIRED",
            })

    for key, candidates in OPTIONAL_CANDIDATES.items():
        path = find_optional(key, candidates)
        if path and path.exists():
            try:
                df = read_csv_safe(path)
                loaded[key] = (path, df)
                rows.append({
                    "Artifact_Key": key, "Path": str(path.relative_to(ROOT)),
                    "Required": False, "Available": True, "Rows": len(df),
                    "Columns": len(df.columns), "Column_List": " | ".join(df.columns),
                    "SHA256": sha256_file(path), "Read_Status": "READ_OK",
                })
            except Exception as exc:
                rows.append({
                    "Artifact_Key": key, "Path": str(path.relative_to(ROOT)),
                    "Required": False, "Available": True, "Rows": np.nan,
                    "Columns": np.nan, "Column_List": "",
                    "SHA256": sha256_file(path), "Read_Status": f"READ_ERROR: {exc}",
                })
        else:
            rows.append({
                "Artifact_Key": key, "Path": "", "Required": False,
                "Available": False, "Rows": np.nan, "Columns": np.nan,
                "Column_List": "", "SHA256": "", "Read_Status": "OPTIONAL_NOT_FOUND",
            })
    return pd.DataFrame(rows), loaded

def choose_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

def make_contract(loaded):
    specs = [
        ("historical_schedule", "Simulation_Record_ID", "Unique port-call record identifier", "REQUIRED"),
        ("historical_schedule", "IMO_Normalised", "Vessel identity for sequencing calls", "REQUIRED"),
        ("historical_schedule", "UNLOCODE_Normalised", "Port identifier for each observed call", "REQUIRED"),
        ("historical_schedule", "Actual_Arrival_UTC", "Observed port-call arrival timestamp", "REQUIRED"),
        ("historical_schedule", "Actual_Departure_UTC", "Observed port-call departure timestamp", "REQUIRED"),
        ("historical_schedule", "Actual_Stay_Hours", "Observed stay-duration field; reconcile to timestamps", "REQUIRED_IF_PRESENT"),
        ("vessel_parameters", "Vessel_ID", "Vessel parameter identity; exact schema inspected from source", "SOURCE_SCHEMA"),
        ("port_parameters", "UNLOCODE", "Port parameter identity; exact schema inspected from source", "SOURCE_SCHEMA"),
        ("port_service_parameters", "UNLOCODE", "Port service parameter identity; exact schema inspected from source", "SOURCE_SCHEMA"),
        ("interport_parameters", "Previous_Port / Next_Port", "Directed pair parameter identity; exact schema inspected from source", "SOURCE_SCHEMA"),
        ("observed_transitions", "Previous_Port / Next_Port", "Observed consecutive port-call transition", "SOURCE_SCHEMA"),
    ]
    rows = []
    for artifact, field, meaning, status in specs:
        if artifact not in loaded:
            rows.append({
                "Artifact_Key": artifact, "Field_or_Field_Pair": field,
                "Research_Role": meaning, "Contract_Status": "SOURCE_MISSING",
                "Observed_Column": "", "Source_Rows": np.nan,
            })
            continue
        path, df = loaded[artifact]
        candidates = [x.strip() for x in field.split("/") ] if "/" in field else [field]
        found = [c for c in candidates if c in df.columns]
        if status in ("REQUIRED", "REQUIRED_IF_PRESENT"):
            state = "PRESENT" if found else "MISSING_REQUIRED_FIELD"
        elif status == "SOURCE_SCHEMA":
            state = "SCHEMA_INSPECTED" if found else "FIELD_NAME_REQUIRES_SCHEMA_REVIEW"
        else:
            state = "INSPECTED"
        rows.append({
            "Artifact_Key": artifact, "Field_or_Field_Pair": field,
            "Research_Role": meaning, "Contract_Status": state,
            "Observed_Column": " | ".join(found), "Source_Rows": len(df),
        })
    # Add every observed source column, not just anticipated columns.
    for artifact, (path, df) in loaded.items():
        if artifact in ("historical_schedule", "observed_transitions"):
            for c in df.columns:
                rows.append({
                    "Artifact_Key": artifact, "Field_or_Field_Pair": c,
                    "Research_Role": "Observed source field; interpretation must follow source definition",
                    "Contract_Status": "OBSERVED_SOURCE_FIELD",
                    "Observed_Column": c, "Source_Rows": len(df),
                })
    return pd.DataFrame(rows)

def derive_schedule_summary(loaded):
    if "historical_schedule" not in loaded:
        return None, None
    _, df = loaded["historical_schedule"]
    idc = choose_col(df, ["Simulation_Record_ID"])
    imo = choose_col(df, ["IMO_Normalised"])
    port = choose_col(df, ["UNLOCODE_Normalised"])
    arr = choose_col(df, ["Actual_Arrival_UTC"])
    dep = choose_col(df, ["Actual_Departure_UTC"])
    missing = [x for x in [idc, imo, port, arr, dep] if x is None]
    if missing:
        return df, {"schema_valid": False, "missing": missing}

    work = df.copy()
    work[arr] = pd.to_datetime(work[arr], utc=True, errors="coerce")
    work[dep] = pd.to_datetime(work[dep], utc=True, errors="coerce")
    work["__interval_h"] = (work[dep] - work[arr]).dt.total_seconds() / 3600
    valid = (
        work[idc].notna() & work[imo].notna() & work[port].notna()
        & work[arr].notna() & work[dep].notna()
        & (work["__interval_h"] > 0)
    )
    summary = {
        "schema_valid": True,
        "rows": len(work),
        "unique_ids": int(work[idc].nunique(dropna=True)),
        "duplicate_ids": int(work[idc].duplicated().sum()),
        "unique_vessels": int(work[imo].nunique(dropna=True)),
        "unique_ports": int(work[port].nunique(dropna=True)),
        "valid_intervals": int(valid.sum()),
        "invalid_intervals": int((~valid).sum()),
        "valid_port_call_rows": int(valid.sum()),
    }
    return work, summary

def build_call_representation(loaded):
    rows = [
        ("Call_ID", "Simulation_Record_ID", "Stable identity of one observed port call", "SOURCE_OBSERVED"),
        ("Vessel_ID", "IMO_Normalised", "Vessel identity used to order that vessel's observed calls", "SOURCE_OBSERVED"),
        ("Port_ID", "UNLOCODE_Normalised", "Port at which the call is recorded", "SOURCE_OBSERVED"),
        ("Arrival_Time", "Actual_Arrival_UTC", "Observed arrival timestamp; UTC", "SOURCE_OBSERVED"),
        ("Departure_Time", "Actual_Departure_UTC", "Observed departure timestamp; UTC", "SOURCE_OBSERVED"),
        ("Observed_Port_Call_Interval", "Departure_Time - Arrival_Time", "Observed interval; may include waiting, anchorage and port operations", "DERIVED_FROM_OBSERVED"),
        ("Observed_Stay_Field", "Actual_Stay_Hours", "Retain original field and reconcile; do not silently replace", "SOURCE_OBSERVED_IF_PRESENT"),
        ("Vessel_Call_Sequence", "Sort by Vessel_ID, Arrival_Time, Call_ID", "Ordering rule for a vessel's observed port calls; ties require review", "DERIVED_ORDER"),
        ("Next_Observed_Port", "Next row in same Vessel_ID sequence", "Observed next port-call location, not a verified sailing route", "DERIVED_FROM_SEQUENCE"),
        ("Inter_Port_Elapsed_Time", "Next Arrival_Time - Current Departure_Time", "Elapsed time between observed calls; not pure sailing time", "DERIVED_FROM_OBSERVATIONS"),
        ("Disruption_Delay", "Not present in historical baseline", "Separate hypothetical model variable; must never overwrite observed timestamps", "FUTURE_SIMULATED"),
        ("Recovery_Action", "Not present in historical baseline", "Future decision variable; requires explicit policy specification", "FUTURE_DECISION"),
    ]
    return pd.DataFrame(rows, columns=[
        "Canonical_Field", "Source_or_Derivation", "Definition_and_Constraint", "Evidence_Class"
    ])

def build_propagation_spec():
    rows = [
        (1, "Freeze historical baseline", "Keep observed arrival/departure timestamps immutable; create separate simulated timestamp columns.", "MANDATORY", "No baseline mutation."),
        (2, "Order vessel calls", "Within each IMO_Normalised, sort by Actual_Arrival_UTC then Simulation_Record_ID; flag same-time ties and overlapping calls for review.", "MANDATORY", "Observed sequence is not proof of physical route."),
        (3, "Represent inter-call elapsed time", "For consecutive calls, calculate next observed arrival minus current observed departure.", "MANDATORY", "Elapsed time includes unobserved components; not pure sailing time."),
        (4, "Define disruption injection point", "Apply an explicitly approved shock to a defined call, transition, port service, or access condition.", "BLOCKED_PENDING_APPROVAL", "No affected scope or magnitude currently approved."),
        (5, "Propagate vessel delay", "For each vessel in sequence, calculate simulated arrival as the later of baseline arrival plus direct shock and previous simulated departure plus the specified inter-call elapsed-time treatment.", "SPECIFICATION_ONLY", "Requires a defensible transition-time treatment; observed elapsed time is not automatically sailing time."),
        (6, "Preserve call duration", "If the experiment is a pure schedule displacement, shift arrival and departure equally; if service disruption changes stay, define a separate service-time mechanism.", "MECHANISM_DEPENDENT", "Do not combine displacement and service-duration change implicitly."),
        (7, "Apply recovery", "Recovery may alter only explicitly defined simulated timing or decision variables; log action, magnitude, feasibility and affected vessel/call.", "BLOCKED_PENDING_POLICY", "No recovery policy selected by this specification."),
        (8, "Handle end-of-window censoring", "Mark calls/vessels whose downstream sequence extends beyond the observation/simulation horizon; report unrecovered and censored separately.", "MANDATORY_FOR_FUTURE_MODEL", "Avoid treating right-censored outcomes as recovered."),
        (9, "Calculate outcomes", "Report call-level and vessel-level accumulated/final delay separately; distinguish maximum final vessel delay from maximum accumulated delay per vessel.", "MANDATORY_FOR_FUTURE_MODEL", "Do not mix call sums with unique-vessel measures."),
        (10, "Validate", "Check chronological order, non-negative durations, no unintended overlaps, event balance, reproducibility, baseline invariance and explicit scope traceability.", "MANDATORY_FOR_FUTURE_MODEL", "Physical feasibility requires additional evidence."),
    ]
    return pd.DataFrame(rows, columns=[
        "Step", "Stage", "Specification", "Readiness", "Caveat"
    ])

def build_invariants():
    rows = [
        ("B01", "Baseline source immutability", "Observed source timestamps and identifiers remain unchanged.", "MUST_PASS", "Data integrity"),
        ("B02", "Call identity", "Each Simulation_Record_ID is unique.", "MUST_PASS", "Identity"),
        ("B03", "Positive observed interval", "Actual_Departure_UTC is later than Actual_Arrival_UTC.", "MUST_PASS", "Temporal validity"),
        ("B04", "Vessel identity", "Every modeled call has a non-missing IMO_Normalised.", "MUST_PASS", "Sequence integrity"),
        ("B05", "Port identity", "Every modeled call has a non-missing UNLOCODE_Normalised.", "MUST_PASS", "Network integrity"),
        ("B06", "Call duration reconciliation", "Timestamp-derived interval is reconciled with Actual_Stay_Hours; discrepancies remain visible.", "MUST_PASS", "Source consistency"),
        ("B07", "Event balance", "Every included call creates one arrival and one departure event.", "MUST_PASS", "Replay accounting"),
        ("B08", "Non-negative active calls", "Active-call state never becomes negative.", "MUST_PASS", "Replay accounting"),
        ("B09", "Final active calls", "All included calls have departed by the end of replay.", "MUST_PASS", "Replay accounting"),
        ("B10", "Concurrency area identity", "Area under port concurrency equals the sum of included observed call intervals.", "MUST_PASS", "Accounting identity only"),
        ("B11", "Deterministic baseline", "Repeated baseline replay yields identical metrics.", "MUST_PASS", "Reproducibility"),
        ("B12", "No route overclaim", "Consecutive port calls are not described as verified physical sailing routes.", "MUST_PASS", "Interpretation"),
        ("B13", "No berth overclaim", "Port-call concurrency is not labelled actual berth occupancy/capacity.", "MUST_PASS", "Interpretation"),
        ("B14", "No Hormuz transit overclaim", "No actual Hormuz transit is asserted without independent AIS/transit evidence.", "MUST_PASS", "Geographic evidence"),
        ("B15", "Vessel-level delay accounting", "Future experiments report per-vessel accumulated and final delay separately.", "FUTURE_MODEL_REQUIREMENT", "Outcome definition"),
        ("B16", "Censoring treatment", "Unrecovered and right-censored calls/vessels are separately identified.", "FUTURE_MODEL_REQUIREMENT", "Outcome definition"),
    ]
    return pd.DataFrame(rows, columns=[
        "Invariant_ID", "Invariant", "Acceptance_Rule", "Status", "Scope"
    ])

def readiness_mechanisms(loaded):
    rows = [
        ("TRANSIT_ELAPSED_TIME_SHOCK",
         "Observed departure-to-next-arrival elapsed time",
         "CONCEPTUALLY_SPECIFIABLE",
         "Can be modeled as an elapsed-time shock only with explicit scope and magnitude approval.",
         "Not pure sailing time; observed transitions are sparse and vessel-concentrated on many edges.",
         "NO"),
        ("NETWORK_ACCESS_RESTRICTION",
         "Validated physical route/network access and feasible alternatives",
         "BLOCKED",
         "Requires a validated geographic route graph, route alternatives and feasibility evidence.",
         "Observed consecutive port calls are not verified physical sailing edges.",
         "NO"),
        ("PORT_SERVICE_DISRUPTION",
         "Observed port-call interval / service assumptions",
         "PARTIALLY_SPECIFIABLE",
         "A separate service-duration mechanism may be defined, but service time and berth capacity are not established by port-call stay alone.",
         "Potential double counting if waiting/anchorage is already inside observed stay.",
         "NO"),
        ("COMPOUND_DISRUPTION",
         "Combination of individually defined mechanisms",
         "DEFERRED",
         "Define and validate single mechanisms before combining them.",
         "No compound magnitudes or scope approved.",
         "NO"),
    ]
    return pd.DataFrame(rows, columns=[
        "Mechanism", "Evidence_Basis", "Readiness_Class", "Requirements",
        "Evidence_Limitation", "Execution_Authorized"
    ])

def main():
    inventory, loaded = inventory_artifacts()
    contract = make_contract(loaded)
    calls = build_call_representation(loaded)
    propagation = build_propagation_spec()
    invariants = build_invariants()
    mechanisms = readiness_mechanisms(loaded)

    schedule_df, schedule_summary = derive_schedule_summary(loaded)
    checks = []

    def add(name, passed, observed, expected, note):
        checks.append({
            "Check": name, "Passed": bool(passed),
            "Observed": observed, "Expected": expected,
            "Interpretation": note,
        })

    core_missing = [k for k in CORE_FILES if k not in loaded]
    add("All six Script19 core input artifacts available",
        len(core_missing) == 0, 6-len(core_missing), 6,
        "Core input availability; missing files are not inferred.")
    if schedule_summary and schedule_summary.get("schema_valid"):
        add("Historical schedule contains 604 expected calls",
            schedule_summary["rows"] == 604, schedule_summary["rows"], 604,
            "Count check against the accepted Script19 schedule.")
        add("Historical schedule record IDs unique",
            schedule_summary["duplicate_ids"] == 0,
            schedule_summary["duplicate_ids"], 0, "Identity check.")
        add("All historical schedule rows have valid positive intervals",
            schedule_summary["invalid_intervals"] == 0,
            schedule_summary["valid_intervals"], schedule_summary["rows"],
            "Timestamp integrity.")
        add("Historical schedule contains 155 expected vessels",
            schedule_summary["unique_vessels"] == 155,
            schedule_summary["unique_vessels"], 155, "Vessel coverage.")
        add("Historical schedule contains 19 expected ports",
            schedule_summary["unique_ports"] == 19,
            schedule_summary["unique_ports"], 19, "Port coverage.")
    else:
        add("Historical schedule schema recognized", False,
            "MISSING_OR_UNRECOGNIZED", "Required schedule schema",
            str(schedule_summary))

    # Cross-check Script71 accepted outputs, if present.
    if "baseline_records" in loaded:
        _, br = loaded["baseline_records"]
        idc = choose_col(br, ["Simulation_Record_ID"])
        statusc = choose_col(br, ["Record_Validation_Status"])
        add("Script71 record audit contains 604 records",
            len(br) == 604, len(br), 604, "Cross-check of accepted baseline audit.")
        add("Script71 record audit all VALID",
            statusc is not None and br[statusc].astype(str).eq("VALID").all(),
            int(br[statusc].astype(str).eq("VALID").sum()) if statusc else "NO_STATUS_FIELD",
            len(br), "All records must pass the record audit.")
        add("Script71 record audit IDs unique",
            idc is not None and not br[idc].duplicated().any(),
            int(br[idc].duplicated().sum()) if idc else "NO_ID_FIELD",
            0, "Cross-file record identity.")
    else:
        add("Script71 record audit available", False, "NOT_FOUND", "Optional accepted audit",
            "Upload/run output not found in project outputs; this check remains unresolved.")

    if "baseline_validation" in loaded:
        _, bp = loaded["baseline_validation"]
        portc = choose_col(bp, ["UNLOCODE"])
        areac = choose_col(bp, ["Area_Reconciles"])
        finalc = choose_col(bp, ["Final_State_Is_Zero"])
        negc = choose_col(bp, ["No_Negative_States"])
        add("Script71 port validation contains 19 ports",
            len(bp) == 19, len(bp), 19, "Port-level replay validation.")
        add("Script71 port areas reconcile",
            areac is not None and bp[areac].astype(str).str.lower().isin(["true","1"]).all(),
            int(bp[areac].astype(str).str.lower().isin(["true","1"]).sum()) if areac else "NO_FIELD",
            len(bp), "Area under concurrency equals observed interval sum.")
        add("Script71 port final states are zero",
            finalc is not None and bp[finalc].astype(str).str.lower().isin(["true","1"]).all(),
            int(bp[finalc].astype(str).str.lower().isin(["true","1"]).sum()) if finalc else "NO_FIELD",
            len(bp), "All ports close with no active calls.")
        add("Script71 has no negative active-call states",
            negc is not None and bp[negc].astype(str).str.lower().isin(["true","1"]).all(),
            int(bp[negc].astype(str).str.lower().isin(["true","1"]).sum()) if negc else "NO_FIELD",
            len(bp), "Intermediate event states remain non-negative.")
    else:
        add("Script71 port validation available", False, "NOT_FOUND", "Optional accepted audit",
            "Port-level baseline validation was not found.")

    if "baseline_timeline" in loaded:
        _, bt = loaded["baseline_timeline"]
        portc = choose_col(bt, ["UNLOCODE"])
        add("Script71 event timeline has 1,205 grouped timestamps",
            len(bt) == 1205, len(bt), 1205, "Corrected v2 timeline completeness.")
        add("Script71 event timeline covers 19 ports",
            portc is not None and bt[portc].nunique() == 19,
            int(bt[portc].nunique()) if portc else "NO_PORT_FIELD", 19,
            "All port timelines must be exported.")
    else:
        add("Script71 corrected event timeline available", False, "NOT_FOUND", 1205,
            "Corrected Script71 timeline not found in project outputs.")

    # Evidence/approval checks: do not infer researcher approvals from missing fields.
    for key, label in [
        ("edge_exposure_decisions", "Script68 edge exposure decisions"),
        ("port_exposure_decisions", "Script68 port exposure decisions"),
        ("experiment_scope", "Script68 experiment scope decisions"),
    ]:
        available = key in loaded
        add(f"{label} artifact available", available,
            "AVAILABLE" if available else "NOT_FOUND",
            "Optional researcher register",
            "Availability does not mean an exposure or scope is approved.")

    add("No experiment executed by Script72", True, "NO", "NO",
        "Specification/readiness only.")
    add("No source files or upstream registers modified", True, "NO", "NO",
        "Read-only script.")
    add("No disruption scope or magnitude automatically approved", True, "NO", "NO",
        "All execution authorizations remain NO.")

    checks_df = pd.DataFrame(checks)

    inventory.to_csv(OUT["inventory"], index=False)
    contract.to_csv(OUT["contract"], index=False)
    calls.to_csv(OUT["calls"], index=False)
    propagation.to_csv(OUT["propagation"], index=False)
    invariants.to_csv(OUT["invariants"], index=False)
    mechanisms.to_csv(OUT["mechanisms"], index=False)
    checks_df.to_csv(OUT["checks"], index=False)

    passed = int(checks_df["Passed"].sum())
    total = len(checks_df)
    core_ok = len(core_missing) == 0
    summary_text = (
        json.dumps(schedule_summary, indent=2, default=str)
        if schedule_summary else "Historical schedule summary unavailable."
    )
    report = f"""================================================================================
SCRIPT 72: CANONICAL BASELINE REPLAY SPECIFICATION AND DISRUPTION-MODEL READINESS
================================================================================

PURPOSE
Read-only baseline contract and future disruption-model specification.
No disruption or recovery experiment is executed.

HISTORICAL BASELINE
{summary_text}

CORE SCRIPT19 INPUTS AVAILABLE: {6-len(core_missing)}/6
Missing core artifacts: {core_missing if core_missing else 'None'}

DOWNSTREAM EVIDENCE ARTIFACTS
{inventory[inventory['Required'].eq(False)][['Artifact_Key','Available','Rows','Read_Status']].to_string(index=False)}

SPECIFICATION
- Canonical unit: one observed vessel port call.
- Stable call key: Simulation_Record_ID.
- Vessel identity: IMO_Normalised.
- Port identity: UNLOCODE_Normalised.
- Observed timestamps: Actual_Arrival_UTC and Actual_Departure_UTC.
- Port-call interval: departure minus arrival; it may include anchorage, waiting and operations.
- Consecutive port calls define observed inter-port elapsed time, not a verified physical route or pure sailing time.
- Future simulated timestamps must be stored separately from historical timestamps.
- Delay propagation must be vessel-sequence aware and separately report call-level and vessel-level outcomes.
- Unrecovered and right-censored calls/vessels must be distinguished.

DISRUPTION MECHANISM READINESS
{mechanisms.to_string(index=False)}

IMPLEMENTATION READINESS CHECKS
Passed: {passed}/{total}
{checks_df[['Check','Passed','Observed','Expected']].to_string(index=False)}

INTERPRETATION
A passed check means the specified data/structural condition was met. It does not
prove physical route feasibility, berth capacity, service processing time,
geopolitical accessibility, or actual Hormuz transit.

CURRENT RESEARCH BOUNDARIES
- No AIS-confirmed Hormuz transit established.
- Historical port-call concurrency is not verified berth occupancy.
- Inter-port elapsed time is not pure sailing time.
- Network access restriction remains blocked pending validated geographic routes
  and feasible alternatives.
- Port service disruption remains partially specifiable; stay duration alone
  does not identify berth processing time or berth capacity.
- Compound disruption is deferred until individual mechanisms are defined.
- No disruption magnitude, affected scope, recovery policy or execution is approved.

EXPERIMENTS EXECUTED: NO
DISRUPTION MAGNITUDES SELECTED: NO
RECOVERY POLICIES SELECTED: NO
SOURCE FILES MODIFIED: NO
UPSTREAM REGISTERS MODIFIED: NO

SCRIPT 72 STATUS
{'CORE INPUTS AVAILABLE' if core_ok else 'CORE INPUTS INCOMPLETE'}
Validation checks are evidence/readiness indicators, not permission to execute
a disruption experiment.
"""
    OUT["report"].write_text(report, encoding="utf-8")

    print("=" * 96)
    print("SCRIPT 72: CANONICAL BASELINE REPLAY SPECIFICATION AND DISRUPTION-MODEL READINESS")
    print("=" * 96)
    if schedule_summary:
        print(f"Historical schedule: {schedule_summary.get('rows')} rows | "
              f"{schedule_summary.get('unique_vessels')} vessels | "
              f"{schedule_summary.get('unique_ports')} ports")
    print(f"Core Script19 inputs available: {6-len(core_missing)}/6")
    print(f"Readiness checks passed: {passed}/{total}")
    print("No experiments executed; no source files modified.")
    for key, path in OUT.items():
        print(path.relative_to(ROOT))
    print("SCRIPT 72 COMPLETED" if core_ok else "SCRIPT 72 COMPLETED WITH MISSING CORE INPUTS")

if __name__ == "__main__":
    main()
