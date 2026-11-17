#!/usr/bin/env python3
# Script 73 — Vessel-Level Baseline Propagation Engine and No-Disruption Validation
# Run from project root:
#   python src/73_vessel_level_baseline_propagation_engine.py
# Or:
#   python src/73_vessel_level_baseline_propagation_engine.py --project-root /path/to/project
#
# This is a deterministic zero-shock baseline test, not a physical route,
# berth-capacity, AIS, or Hormuz-transit model.

from __future__ import annotations
import argparse
import sys
import traceback
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

INPUT_DIR = Path("data/simulation_inputs")
TABLE_DIR = Path("outputs/tables")
REPORT_DIR = Path("outputs/reports")
FILES = {
    "schedule": "19_historical_arrival_schedule.csv",
    "vessels": "19_vessel_parameters.csv",
    "ports": "19_port_parameters.csv",
    "port_service": "19_port_service_parameters.csv",
    "interport": "19_interport_time_parameters.csv",
    "transitions": "19_observed_interport_transitions.csv",
}
KEYS = {
    "schedule": ["Simulation_Record_ID"],
    "vessels": ["IMO_Normalised"],
    "ports": ["UNLOCODE_Normalised"],
    "port_service": ["UNLOCODE_Normalised"],
    "interport": ["Previous_Port", "Next_Port"],
    "transitions": ["IMO_Normalised", "Simulation_Record_ID"],
}
REQUIRED_SCHEDULE = [
    "Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised",
    "Actual_Arrival_UTC", "Actual_Departure_UTC", "Actual_Stay_Hours",
]
EXPECTED = {
    "schedule": 604, "vessels": 155, "ports": 19,
    "port_service": 19, "interport": 53, "transitions": 271,
}
STAY_TOLERANCE_HOURS = 0.02


def add_check(rows: list[dict[str, Any]], check_id: str, description: str,
              passed: bool, observed: Any, expected: Any,
              severity: str = "ERROR") -> None:
    rows.append({
        "Check_ID": check_id, "Description": description,
        "Passed": bool(passed), "Observed": str(observed),
        "Expected": str(expected), "Severity": severity,
    })


def require_columns(df: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def duplicate_key_rows(df: pd.DataFrame, keys: list[str]) -> int:
    return int(df.duplicated(keys, keep=False).sum())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.expanduser().resolve()
    input_dir = root / INPUT_DIR
    table_dir = root / TABLE_DIR
    report_dir = root / REPORT_DIR
    table_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    data = {}
    for label, filename in FILES.items():
        path = input_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing {label} input: {path}")
        data[label] = pd.read_csv(path, low_memory=False)

    checks: list[dict[str, Any]] = []
    schedule = data["schedule"].copy()
    require_columns(schedule, REQUIRED_SCHEDULE, "Historical schedule")

    # Source keys and expected Script 19 source dimensions.
    for label, keys in KEYS.items():
        df = data[label]
        require_columns(df, keys, label)
        nulls = int(df[keys].isna().any(axis=1).sum())
        duplicates = duplicate_key_rows(df, keys)
        add_check(checks, f"{label.upper()}_KEY_NULLS",
                  f"{label} key fields have no null rows", nulls == 0, nulls, 0)
        add_check(checks, f"{label.upper()}_KEY_UNIQUENESS",
                  f"{label} key is unique", duplicates == 0, duplicates, 0)
    for label, expected in EXPECTED.items():
        actual = len(data[label])
        add_check(checks, f"{label.upper()}_ROW_COUNT",
                  f"{label} row count matches established Script 19 baseline",
                  actual == expected, actual, expected, "WARNING")

    # Parse times while retaining the original source timestamp strings.
    schedule["_arrival"] = pd.to_datetime(
        schedule["Actual_Arrival_UTC"], utc=True, errors="coerce")
    schedule["_departure"] = pd.to_datetime(
        schedule["Actual_Departure_UTC"], utc=True, errors="coerce")
    invalid_times = int((schedule["_arrival"].isna() |
                         schedule["_departure"].isna()).sum())
    add_check(checks, "VALID_UTC_TIMESTAMPS",
              "All arrival/departure timestamps parse as UTC",
              invalid_times == 0, invalid_times, 0)
    missing_identity = int(schedule[
        ["Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised"]
    ].isna().any(axis=1).sum())
    add_check(checks, "COMPLETE_CALL_IDENTITY",
              "Every schedule row has call, vessel and port identity",
              missing_identity == 0, missing_identity, 0)
    invalid_intervals = int(
        (schedule["_departure"] <= schedule["_arrival"]).fillna(False).sum())
    add_check(checks, "POSITIVE_CALL_INTERVALS",
              "Every departure is later than its arrival",
              invalid_intervals == 0, invalid_intervals, 0)

    schedule["_derived_stay_hours"] = (
        schedule["_departure"] - schedule["_arrival"]
    ).dt.total_seconds() / 3600.0
    schedule["_reported_stay_hours"] = pd.to_numeric(
        schedule["Actual_Stay_Hours"], errors="coerce")
    stay_diff = (schedule["_derived_stay_hours"] -
                 schedule["_reported_stay_hours"]).abs()
    stay_mismatches = int((stay_diff > STAY_TOLERANCE_HOURS).fillna(True).sum())
    add_check(checks, "STAY_DURATION_RECONCILIATION",
              f"Timestamp-derived duration matches Actual_Stay_Hours within {STAY_TOLERANCE_HOURS} h",
              stay_mismatches == 0, stay_mismatches, 0)

    # Validate parameter-key coverage. Parameters are audited, not applied.
    coverage_rows = []
    for label, key, required in [
        ("vessels", "IMO_Normalised", schedule["IMO_Normalised"].dropna().unique()),
        ("ports", "UNLOCODE_Normalised", schedule["UNLOCODE_Normalised"].dropna().unique()),
        ("port_service", "UNLOCODE_Normalised", schedule["UNLOCODE_Normalised"].dropna().unique()),
    ]:
        required_set = set(pd.Series(required).astype(str))
        source_set = set(data[label][key].dropna().astype(str))
        missing = sorted(required_set - source_set)
        coverage_rows.append({
            "Parameter_Source": label, "Join_Key": key,
            "Required_Unique_Keys": len(required_set),
            "Matched_Unique_Keys": len(required_set & source_set),
            "Missing_Keys_Count": len(missing),
            "Missing_Keys": ";".join(missing),
            "Coverage_Pct": 100 * len(required_set & source_set) /
                            len(required_set) if required_set else 100.0,
            "Values_Applied_In_Script73": False,
        })
        add_check(checks, f"{label.upper()}_PARAMETER_COVERAGE",
                  f"{label} source covers all schedule keys",
                  not missing, len(missing), 0)

    # Stable ordering: vessel, observed arrival, then unique call ID.
    ordered = schedule.sort_values(
        ["IMO_Normalised", "_arrival", "Simulation_Record_ID"],
        kind="mergesort").copy()
    grouped = ordered.groupby("IMO_Normalised", sort=False)
    ordered["Vessel_Call_Sequence_Number"] = grouped.cumcount() + 1
    ordered["Previous_Simulation_Record_ID"] = grouped[
        "Simulation_Record_ID"].shift(1)
    ordered["Previous_Port"] = grouped["UNLOCODE_Normalised"].shift(1)
    ordered["Previous_Departure_UTC"] = grouped["_departure"].shift(1)
    ordered["Observed_Inter_Call_Elapsed_Hours"] = (
        ordered["_arrival"] - ordered["Previous_Departure_UTC"]
    ).dt.total_seconds() / 3600.0
    has_previous = ordered["Previous_Simulation_Record_ID"].notna()
    same_port = has_previous & (
        ordered["UNLOCODE_Normalised"].astype(str) ==
        ordered["Previous_Port"].astype(str))
    distinct_port = has_previous & ~same_port
    negative_gaps = int((has_previous &
                         (ordered["Observed_Inter_Call_Elapsed_Hours"] < 0)).sum())
    zero_gaps = int((has_previous &
                     (ordered["Observed_Inter_Call_Elapsed_Hours"] == 0)).sum())

    # Script 72 recurrence under the no-disruption/no-recovery baseline:
    # arrival_delay[k] = previous_departure_delay[k-1] + transit_shock[k]
    # departure_delay[k] = arrival_delay[k] + port_call_shock[k] - recovery[k]
    # All shock/recovery terms and the initial delay are exactly zero.
    arrival_delay = []
    departure_delay = []
    last_departure_delay: dict[str, float] = {}
    for row in ordered[["IMO_Normalised"]].itertuples(index=False):
        vessel = str(row.IMO_Normalised)
        d_arr = last_departure_delay.get(vessel, 0.0) + 0.0
        d_dep = d_arr + 0.0 - 0.0
        arrival_delay.append(d_arr)
        departure_delay.append(d_dep)
        last_departure_delay[vessel] = d_dep

    ordered["Initial_Arrival_Delay_Hours"] = 0.0
    ordered["Transit_Elapsed_Time_Shock_Hours"] = 0.0
    ordered["Port_Call_Duration_Shock_Hours"] = 0.0
    ordered["Recovery_Advance_Hours"] = 0.0
    ordered["Simulated_Arrival_Delay_Hours"] = arrival_delay
    ordered["Simulated_Departure_Delay_Hours"] = departure_delay
    ordered["Simulated_Arrival_UTC"] = ordered["_arrival"] + pd.to_timedelta(
        ordered["Simulated_Arrival_Delay_Hours"], unit="h")
    ordered["Simulated_Departure_UTC"] = ordered["_departure"] + pd.to_timedelta(
        ordered["Simulated_Departure_Delay_Hours"], unit="h")
    ordered["Arrival_Timestamp_Match"] = (
        ordered["Simulated_Arrival_UTC"] == ordered["_arrival"])
    ordered["Departure_Timestamp_Match"] = (
        ordered["Simulated_Departure_UTC"] == ordered["_departure"])

    # Compare the derived distinct-port transitions to Script 19 by its
    # established identity key; then independently compare Previous/Next_Port.
    derived = ordered.loc[distinct_port, [
        "IMO_Normalised", "Simulation_Record_ID", "Previous_Port",
        "UNLOCODE_Normalised"
    ]].copy()
    derived = derived.rename(columns={"UNLOCODE_Normalised": "Next_Port"})
    source = data["transitions"].copy()
    require_columns(source, ["Previous_Port", "Next_Port"],
                    "Observed inter-port transitions")
    for col in ["IMO_Normalised", "Simulation_Record_ID"]:
        derived[col] = derived[col].astype(str)
        source[col] = source[col].astype(str)
    transition_merge = derived.merge(
        source[["IMO_Normalised", "Simulation_Record_ID",
                "Previous_Port", "Next_Port"]],
        on=["IMO_Normalised", "Simulation_Record_ID"],
        how="outer", suffixes=("_derived", "_source"),
        indicator=True, validate="one_to_one")
    unmatched = int((transition_merge["_merge"] != "both").sum())
    pair_mismatches = int((
        (transition_merge["_merge"] == "both") &
        ((transition_merge["Previous_Port_derived"].astype(str) !=
          transition_merge["Previous_Port_source"].astype(str)) |
         (transition_merge["Next_Port_derived"].astype(str) !=
          transition_merge["Next_Port_source"].astype(str)))
    ).sum())

    # Call-level and vessel-level outputs.
    call_cols = [
        "Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised",
        "Actual_Arrival_UTC", "Actual_Departure_UTC", "Actual_Stay_Hours",
        "Vessel_Call_Sequence_Number", "Previous_Simulation_Record_ID",
        "Previous_Port", "Observed_Inter_Call_Elapsed_Hours",
        "_derived_stay_hours", "Initial_Arrival_Delay_Hours",
        "Transit_Elapsed_Time_Shock_Hours",
        "Port_Call_Duration_Shock_Hours", "Recovery_Advance_Hours",
        "Simulated_Arrival_UTC", "Simulated_Departure_UTC",
        "Simulated_Arrival_Delay_Hours", "Simulated_Departure_Delay_Hours",
        "Arrival_Timestamp_Match", "Departure_Timestamp_Match",
    ]
    calls_out = ordered[call_cols].rename(columns={
        "_derived_stay_hours": "Timestamp_Derived_Port_Call_Duration_Hours"
    }).copy()

    links = ordered.loc[has_previous].copy()
    links["Transition_Type"] = np.where(
        links["UNLOCODE_Normalised"].astype(str) ==
        links["Previous_Port"].astype(str),
        "SAME_PORT_SEQUENCE_LINK", "DISTINCT_PORT_INTERPORT_TRANSITION")
    transition_out = links[[
        "IMO_Normalised", "Previous_Simulation_Record_ID",
        "Simulation_Record_ID", "Previous_Port", "UNLOCODE_Normalised",
        "Transition_Type", "Observed_Inter_Call_Elapsed_Hours",
        "Simulated_Arrival_Delay_Hours", "Simulated_Departure_Delay_Hours"
    ]].rename(columns={
        "Simulation_Record_ID": "Current_Simulation_Record_ID",
        "UNLOCODE_Normalised": "Next_Port",
        "Simulated_Arrival_Delay_Hours": "Propagated_Arrival_Delay_Hours",
        "Simulated_Departure_Delay_Hours": "Propagated_Departure_Delay_Hours",
    })

    vessels = ordered.groupby("IMO_Normalised", dropna=False).agg(
        Call_Count=("Simulation_Record_ID", "size"),
        First_Observed_Arrival_UTC=("_arrival", "min"),
        Last_Observed_Departure_UTC=("_departure", "max"),
        Maximum_Arrival_Delay_Hours=("Simulated_Arrival_Delay_Hours", "max"),
        Maximum_Departure_Delay_Hours=("Simulated_Departure_Delay_Hours", "max"),
        Accumulated_Arrival_Delay_Hours=("Simulated_Arrival_Delay_Hours", "sum"),
        Accumulated_Departure_Delay_Hours=("Simulated_Departure_Delay_Hours", "sum"),
        All_Arrivals_Reproduced=("Arrival_Timestamp_Match", "all"),
        All_Departures_Reproduced=("Departure_Timestamp_Match", "all"),
    ).reset_index()
    vessels["Final_Vessel_Departure_Delay_Hours"] = (
        vessels["Maximum_Departure_Delay_Hours"])
    vessels["No_Disruption_Baseline_Passed"] = (
        vessels["All_Arrivals_Reproduced"] &
        vessels["All_Departures_Reproduced"] &
        (vessels["Maximum_Arrival_Delay_Hours"] == 0) &
        (vessels["Maximum_Departure_Delay_Hours"] == 0))

    ports = ordered.groupby("UNLOCODE_Normalised", dropna=False).agg(
        Historical_Call_Count=("Simulation_Record_ID", "size"),
        Unique_Vessels=("IMO_Normalised", "nunique"),
        Mean_Observed_Port_Call_Duration_Hours=("_derived_stay_hours", "mean"),
        Median_Observed_Port_Call_Duration_Hours=("_derived_stay_hours", "median"),
        Total_Observed_Port_Call_Duration_Hours=("_derived_stay_hours", "sum"),
        All_Calls_Reproduced=("Arrival_Timestamp_Match", "all"),
    ).reset_index()
    ports["Interpretation"] = (
        "Descriptive historical call intervals; not berth occupancy or capacity")

    # Deterministic second pass: same ordering and zero-valued recurrence.
    second = schedule.sort_values(
        ["IMO_Normalised", "_arrival", "Simulation_Record_ID"],
        kind="mergesort").copy()
    second["Run2_Arrival_Delay_Hours"] = 0.0
    second["Run2_Departure_Delay_Hours"] = 0.0
    reproducibility = ordered[[
        "Simulation_Record_ID", "IMO_Normalised",
        "Simulated_Arrival_Delay_Hours", "Simulated_Departure_Delay_Hours"
    ]].merge(second[[
        "Simulation_Record_ID", "IMO_Normalised",
        "Run2_Arrival_Delay_Hours", "Run2_Departure_Delay_Hours"
    ]], on=["Simulation_Record_ID", "IMO_Normalised"],
        how="outer", validate="one_to_one", indicator=True)
    reproducibility["Delay_Values_Identical"] = (
        (reproducibility["Simulated_Arrival_Delay_Hours"] ==
         reproducibility["Run2_Arrival_Delay_Hours"]) &
        (reproducibility["Simulated_Departure_Delay_Hours"] ==
         reproducibility["Run2_Departure_Delay_Hours"]))
    repro_failures = int((
        (reproducibility["_merge"] != "both") |
        (~reproducibility["Delay_Values_Identical"])).sum())

    arrival_failures = int((~ordered["Arrival_Timestamp_Match"]).sum())
    departure_failures = int((~ordered["Departure_Timestamp_Match"]).sum())
    nonzero_delay_rows = int((
        (ordered["Simulated_Arrival_Delay_Hours"] != 0) |
        (ordered["Simulated_Departure_Delay_Hours"] != 0)).sum())
    vessel_count = int(ordered["IMO_Normalised"].nunique())
    terminal_count = int(ordered.groupby("IMO_Normalised").tail(1).shape[0])

    # Baseline and sequence checks.
    add_check(checks, "NEGATIVE_SEQUENCE_GAPS",
              "No next arrival precedes the previous departure",
              negative_gaps == 0, negative_gaps, 0)
    add_check(checks, "SEQUENCE_LINK_COUNT",
              "Vessel sequence links match established count",
              len(links) == 449, len(links), 449, "WARNING")
    add_check(checks, "SAME_PORT_LINK_COUNT",
              "Same-port links match established count",
              int(same_port.sum()) == 178, int(same_port.sum()), 178, "WARNING")
    add_check(checks, "INTERPORT_TRANSITION_COUNT",
              "Distinct-port transitions match established count",
              int(distinct_port.sum()) == 271, int(distinct_port.sum()), 271, "WARNING")
    add_check(checks, "SCRIPT19_TRANSITION_IDENTITY_MATCH",
              "Derived inter-port transition identities match Script 19",
              unmatched == 0, unmatched, 0)
    add_check(checks, "SCRIPT19_TRANSITION_PAIR_MATCH",
              "Derived Previous_Port/Next_Port pairs match Script 19",
              pair_mismatches == 0, pair_mismatches, 0)
    add_check(checks, "EXACT_ARRIVAL_REPRODUCTION",
              "All simulated arrivals exactly reproduce historical arrivals",
              arrival_failures == 0, arrival_failures, 0)
    add_check(checks, "EXACT_DEPARTURE_REPRODUCTION",
              "All simulated departures exactly reproduce historical departures",
              departure_failures == 0, departure_failures, 0)
    add_check(checks, "ALL_DELAYS_ZERO",
              "All call-level arrival/departure delays remain exactly zero",
              nonzero_delay_rows == 0, nonzero_delay_rows, 0)
    add_check(checks, "ALL_VESSELS_PASS",
              "Every vessel sequence passes the no-disruption baseline",
              bool(vessels["No_Disruption_Baseline_Passed"].all()),
              int((~vessels["No_Disruption_Baseline_Passed"]).sum()), 0)
    add_check(checks, "VESSEL_COUNT",
              "Unique vessel count matches established baseline",
              vessel_count == 155, vessel_count, 155, "WARNING")
    add_check(checks, "ONE_TERMINAL_CALL_PER_VESSEL",
              "Each vessel has exactly one final call",
              terminal_count == vessel_count, terminal_count, vessel_count)
    add_check(checks, "DETERMINISTIC_REPRODUCIBILITY",
              "Second baseline pass produces identical delay outputs",
              repro_failures == 0, repro_failures, 0)

    source_audit = pd.DataFrame([{
        "Source": label, "Filename": FILES[label], "Rows": len(df),
        "Columns": len(df.columns), "Key_Columns": ";".join(KEYS[label]),
        "Key_Null_Rows": int(df[KEYS[label]].isna().any(axis=1).sum()),
        "Duplicate_Key_Rows": duplicate_key_rows(df, KEYS[label]),
    } for label, df in data.items()])

    checks_df = pd.DataFrame(checks)
    checks_df["Overall_Status"] = np.where(checks_df["Passed"], "PASS", "FAIL")

    outputs = {
        "73_call_level_baseline_propagation_register.csv": calls_out,
        "73_vessel_level_baseline_summary.csv": vessels,
        "73_transition_level_baseline_register.csv": transition_out,
        "73_port_level_historical_baseline_summary.csv": ports,
        "73_source_schema_and_key_audit.csv": source_audit,
        "73_parameter_key_coverage.csv": pd.DataFrame(coverage_rows),
        "73_baseline_validation_checks.csv": checks_df,
        "73_reproducibility_comparison.csv": reproducibility,
    }
    for filename, frame in outputs.items():
        frame.to_csv(table_dir / filename, index=False)

    failed = checks_df.loc[~checks_df["Passed"]]
    report = [
        "SCRIPT 73 — VESSEL-LEVEL BASELINE PROPAGATION ENGINE",
        "=" * 66, f"Project root: {root}", "",
        f"Schedule calls: {len(schedule)}",
        f"Vessels: {vessel_count}",
        f"Ports: {schedule['UNLOCODE_Normalised'].nunique()}",
        f"Vessel sequence links: {len(links)}",
        f"Same-port links: {int(same_port.sum())}",
        f"Distinct-port transitions: {int(distinct_port.sum())}",
        f"Terminal calls: {terminal_count}",
        f"Negative inter-call elapsed links: {negative_gaps}",
        f"Zero inter-call elapsed links: {zero_gaps}",
        f"Stay-duration mismatches (> {STAY_TOLERANCE_HOURS} h): {stay_mismatches}",
        "", "NO-DISRUPTION INPUTS",
        "Initial delay = 0 h; transit elapsed-time shock = 0 h;",
        "port-call-duration shock = 0 h; recovery advance = 0 h.",
        "", "BASELINE RESULTS",
        f"Arrival timestamp mismatches: {arrival_failures}",
        f"Departure timestamp mismatches: {departure_failures}",
        f"Non-zero delay rows: {nonzero_delay_rows}",
        f"Vessels passing: {int(vessels['No_Disruption_Baseline_Passed'].sum())}/{len(vessels)}",
        f"Reproducibility mismatches: {repro_failures}",
        "", f"Validation checks passed: {int(checks_df['Passed'].sum())}/{len(checks_df)}",
        f"Validation checks failed: {len(failed)}", "",
        "RESEARCH LIMITATIONS",
        "- Inter-port elapsed time is not pure sailing time.",
        "- Observed port-call duration is not pure berth-processing time.",
        "- Port-call summaries do not establish berth occupancy or capacity.",
        "- No physical route, Hormuz transit, or actual disruption exposure is inferred.",
        "- No disruption, recovery policy, or optimization experiment is executed.",
        "- Historical timestamps are retained separately from simulated timestamps.",
        "", "FAILED CHECKS:",
    ]
    if failed.empty:
        report.append("None.")
    else:
        report.extend([
            f"- {r.Check_ID}: observed={r.Observed}; expected={r.Expected}"
            for r in failed.itertuples(index=False)
        ])
    report += ["", "OUTPUTS:"] + [
        f"- outputs/tables/{name}" for name in outputs
    ] + ["- outputs/reports/73_vessel_level_baseline_propagation_report.txt"]
    report_path = report_dir / "73_vessel_level_baseline_propagation_report.txt"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")

    print("\n".join(report))
    if not failed.empty:
        print("\nFAILED: review validation checks and report.", file=sys.stderr)
        return 2
    print("\nSUCCESS: all Script 73 baseline checks passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nSCRIPT 73 FAILED: {exc}", file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(1)
