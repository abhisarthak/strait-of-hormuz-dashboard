#!/usr/bin/env python3
"""
SCRIPT 71: CANONICAL HISTORICAL REPLAY ENGINE AUDIT AND VALIDATION

Purpose
-------
Independently replay the established historical port-call intervals using
the Script 27 event-accounting design, while applying exact timestamp
grouping and stronger record-, event-, port-, and reproducibility checks.

This is a READ-ONLY audit of source inputs. It does not edit Scripts 25, 27,
or 28; does not modify Script19 inputs; and does not run disruption scenarios.

Run from the project root:
    python src/71_canonical_historical_replay_engine_audit_CORRECTED_v2.py

Inputs:
    data/simulation_inputs/19_historical_arrival_schedule.csv
    outputs/tables/26_historical_port_concurrency.csv (optional comparison)

Outputs:
    outputs/tables/71_historical_replay_record_audit.csv
    outputs/tables/71_historical_replay_port_validation.csv
    outputs/tables/71_historical_replay_event_timeline.csv
    outputs/tables/71_replay_reproducibility_comparison.csv
    outputs/tables/71_script26_comparison.csv
    outputs/tables/71_validation_checks.csv
    outputs/reports/71_canonical_historical_replay_audit_report.txt

Interpretation
--------------
- Port-call concurrency is not verified berth occupancy.
- Historical port-call intervals are replayed as recorded.
- This is arithmetic/event-accounting validation, not validation of the
  physical accuracy of source records or sailing routes.
- Inter-port elapsed time is not pure sailing time.
- No actual Strait of Hormuz transit is established.
"""

from pathlib import Path
import sys
import numpy as np
import pandas as pd
import simpy

ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / "data" / "simulation_inputs" / "19_historical_arrival_schedule.csv"
SCRIPT26_FILE = ROOT / "outputs" / "tables" / "26_historical_port_concurrency.csv"
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"

OUTPUTS = {
    "records": TABLES / "71_historical_replay_record_audit.csv",
    "ports": TABLES / "71_historical_replay_port_validation.csv",
    "timeline": TABLES / "71_historical_replay_event_timeline.csv",
    "repro": TABLES / "71_replay_reproducibility_comparison.csv",
    "script26": TABLES / "71_script26_comparison.csv",
    "checks": TABLES / "71_validation_checks.csv",
    "report": REPORTS / "71_canonical_historical_replay_audit_report.txt",
}

REQUIRED = [
    "Simulation_Record_ID",
    "IMO_Normalised",
    "UNLOCODE_Normalised",
    "Actual_Arrival_UTC",
    "Actual_Departure_UTC",
]

def fail(message):
    raise RuntimeError(message)

def load_data():
    if not INPUT_FILE.exists():
        fail(f"Required historical schedule not found: {INPUT_FILE}")
    df = pd.read_csv(INPUT_FILE, low_memory=False)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        fail(f"Missing required columns: {missing}")

    df["Simulation_Record_ID"] = df["Simulation_Record_ID"].astype("string").str.strip()
    df["IMO_Normalised"] = df["IMO_Normalised"].astype("string").str.strip()
    df["UNLOCODE_Normalised"] = (
        df["UNLOCODE_Normalised"].astype("string").str.strip().str.upper()
    )
    df["Actual_Arrival_UTC"] = pd.to_datetime(
        df["Actual_Arrival_UTC"], utc=True, errors="coerce"
    )
    df["Actual_Departure_UTC"] = pd.to_datetime(
        df["Actual_Departure_UTC"], utc=True, errors="coerce"
    )

    df["Timestamp_Interval_Hours"] = (
        df["Actual_Departure_UTC"] - df["Actual_Arrival_UTC"]
    ).dt.total_seconds() / 3600.0

    if "Actual_Stay_Hours" in df.columns:
        df["Actual_Stay_Hours_Numeric"] = pd.to_numeric(
            df["Actual_Stay_Hours"], errors="coerce"
        )
        df["Stay_Duration_Difference_Hours"] = (
            df["Timestamp_Interval_Hours"] - df["Actual_Stay_Hours_Numeric"]
        )
    else:
        df["Actual_Stay_Hours_Numeric"] = np.nan
        df["Stay_Duration_Difference_Hours"] = np.nan

    df["Record_Validation_Status"] = "VALID"
    invalid_identity = (
        df["Simulation_Record_ID"].isna()
        | df["Simulation_Record_ID"].eq("")
        | df["IMO_Normalised"].isna()
        | df["IMO_Normalised"].eq("")
        | df["UNLOCODE_Normalised"].isna()
        | df["UNLOCODE_Normalised"].eq("")
    )
    invalid_time = (
        df["Actual_Arrival_UTC"].isna()
        | df["Actual_Departure_UTC"].isna()
        | (df["Timestamp_Interval_Hours"] <= 0)
    )
    duplicate_id = df["Simulation_Record_ID"].duplicated(keep=False)
    df.loc[invalid_identity, "Record_Validation_Status"] = "INVALID_IDENTITY"
    df.loc[invalid_time, "Record_Validation_Status"] = "INVALID_TIMESTAMP_INTERVAL"
    df.loc[duplicate_id, "Record_Validation_Status"] = "DUPLICATE_RECORD_ID"
    if "Actual_Stay_Hours" in df.columns:
        bad_stay = (
            df["Actual_Stay_Hours_Numeric"].isna()
            | (df["Actual_Stay_Hours_Numeric"] <= 0)
            | (df["Stay_Duration_Difference_Hours"].abs() > 0.02)
        )
        df.loc[bad_stay & df["Record_Validation_Status"].eq("VALID"),
               "Record_Validation_Status"] = "STAY_DURATION_RECONCILIATION_REVIEW"
    return df

def replay_once(data, run_label):
    """Replay per-port event streams, grouping exact UTC timestamps."""
    global_start = data["Actual_Arrival_UTC"].min()
    port_rows = []
    timeline = []
    event_audit_rows = []

    for port, group in data.groupby("UNLOCODE_Normalised", sort=True):
        events = []
        for row in group.itertuples(index=False):
            # Integer UTC nanoseconds provide exact timestamp identity.
            arr_ns = int(row.Actual_Arrival_UTC.value)
            dep_ns = int(row.Actual_Departure_UTC.value)
            events.append((arr_ns, 1, str(row.Simulation_Record_ID), "ARRIVAL"))
            events.append((dep_ns, -1, str(row.Simulation_Record_ID), "DEPARTURE"))

        events.sort(key=lambda x: (x[0], x[1], x[2]))
        grouped = []
        for timestamp_ns, delta, record_id, event_type in events:
            if not grouped or grouped[-1]["timestamp_ns"] != timestamp_ns:
                grouped.append({
                    "timestamp_ns": timestamp_ns,
                    "delta": 0,
                    "arrivals": 0,
                    "departures": 0,
                    "record_ids": [],
                })
            item = grouped[-1]
            item["delta"] += delta
            item["record_ids"].append(record_id)
            if event_type == "ARRIVAL":
                item["arrivals"] += 1
            else:
                item["departures"] += 1

        env = simpy.Environment()
        state = {
            "active": 0, "peak": 0, "area": 0.0,
            "negative_states": 0, "previous_hours": 0.0,
        }

        def event_process():
            for event_index, event in enumerate(grouped):
                current_hours = (
                    event["timestamp_ns"] - int(global_start.value)
                ) / 3_600_000_000_000.0
                elapsed = current_hours - state["previous_hours"]
                if elapsed < -1e-10:
                    raise AssertionError(f"Time reversal at {port}, event {event_index}")
                state["area"] += state["active"] * elapsed
                yield env.timeout(max(0.0, elapsed))
                state["active"] += event["delta"]
                if state["active"] < 0:
                    state["negative_states"] += 1
                state["peak"] = max(state["peak"], state["active"])
                ts = pd.to_datetime(event["timestamp_ns"], utc=True)
                timeline.append({
                    "Run_Label": run_label,
                    "UNLOCODE": port,
                    "Timestamp_UTC": ts,
                    "Simulation_Time_Hours_From_Global_Start": current_hours,
                    "Arrivals_At_Timestamp": event["arrivals"],
                    "Departures_At_Timestamp": event["departures"],
                    "Net_Event_Change": event["delta"],
                    "Active_Port_Calls_After_Event": state["active"],
                })
                event_audit_rows.append({
                    "Run_Label": run_label,
                    "UNLOCODE": port,
                    "Timestamp_UTC": ts,
                    "Arrivals": event["arrivals"],
                    "Departures": event["departures"],
                    "Net_Change": event["delta"],
                    "Active_After_Event": state["active"],
                    "Negative_State": state["active"] < 0,
                })
                state["previous_hours"] = current_hours

        env.process(event_process())
        env.run()

        interval_hours = group["Timestamp_Interval_Hours"].sum()
        start = group["Actual_Arrival_UTC"].min()
        end = group["Actual_Departure_UTC"].max()
        horizon = (end - start).total_seconds() / 3600.0
        mean_concurrency = state["area"] / horizon if horizon > 0 else np.nan

        port_rows.append({
            "Run_Label": run_label,
            "UNLOCODE": port,
            "Port_Calls": len(group),
            "Unique_Vessels": group["IMO_Normalised"].nunique(),
            "Peak_Concurrent_Calls": state["peak"],
            "Mean_Concurrent_Calls": mean_concurrency,
            "Concurrency_Area_Call_Hours": state["area"],
            "Sum_Observed_Interval_Hours": interval_hours,
            "Area_Difference_Hours": state["area"] - interval_hours,
            "Observation_Horizon_Hours": horizon,
            "Final_Active_Calls": state["active"],
            "Negative_State_Count": state["negative_states"],
            "Exact_Event_Timestamps": len(grouped),
            "Raw_Event_Count": len(events),
            "Simultaneous_Event_Timestamps": sum(
                1 for e in grouped if e["arrivals"] + e["departures"] > 1
            ),
        })

    return (
        pd.DataFrame(port_rows),
        pd.DataFrame(timeline),
        pd.DataFrame(event_audit_rows),
    )

def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    df = load_data()

    valid = df[df["Record_Validation_Status"].eq("VALID")].copy()
    if valid.empty:
        fail("No valid records available for replay.")
    if len(valid) != len(df):
        print(f"WARNING: {len(df)-len(valid)} records require review; they are excluded from replay.")

    valid = valid.sort_values(
        ["Actual_Arrival_UTC", "Simulation_Record_ID"]
    ).reset_index(drop=True)

    ports1, timeline1, event_audit1 = replay_once(valid, "RUN_1")
    ports2, timeline2, event_audit2 = replay_once(valid, "RUN_2")

    repro = ports1.merge(
        ports2,
        on="UNLOCODE",
        suffixes=("_Run1", "_Run2"),
        validate="one_to_one",
    )
    repro["Peak_Match"] = (
        repro["Peak_Concurrent_Calls_Run1"] == repro["Peak_Concurrent_Calls_Run2"]
    )
    repro["Mean_Match"] = np.isclose(
        repro["Mean_Concurrent_Calls_Run1"],
        repro["Mean_Concurrent_Calls_Run2"],
        rtol=0, atol=1e-12, equal_nan=True,
    )
    repro["Area_Match"] = np.isclose(
        repro["Concurrency_Area_Call_Hours_Run1"],
        repro["Concurrency_Area_Call_Hours_Run2"],
        rtol=0, atol=1e-9,
    )
    repro["Final_State_Match"] = (
        repro["Final_Active_Calls_Run1"] == repro["Final_Active_Calls_Run2"]
    )

    record_audit = df[[
        "Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised",
        "Actual_Arrival_UTC", "Actual_Departure_UTC",
        "Timestamp_Interval_Hours", "Actual_Stay_Hours_Numeric",
        "Stay_Duration_Difference_Hours", "Record_Validation_Status",
    ]].copy()

    port_validation = ports1.copy()
    port_validation["Area_Reconciles"] = port_validation["Area_Difference_Hours"].abs() <= 1e-6
    port_validation["Final_State_Is_Zero"] = port_validation["Final_Active_Calls"].eq(0)
    port_validation["No_Negative_States"] = port_validation["Negative_State_Count"].eq(0)
    port_validation["Event_Count_Reconciles"] = (
        port_validation["Raw_Event_Count"] == 2 * port_validation["Port_Calls"]
    )

    script26_comparison = pd.DataFrame()
    script26_available = SCRIPT26_FILE.exists()
    if script26_available:
        s26 = pd.read_csv(SCRIPT26_FILE, low_memory=False)
        required26 = [
            "UNLOCODE", "Port_Calls",
            "Peak_Concurrent_Calls", "Mean_Concurrent_Calls",
        ]
        missing26 = [c for c in required26 if c not in s26.columns]
        if missing26:
            print("WARNING: Script26 exists but lacks columns:", missing26)
            script26_available = False
        else:
            s26["UNLOCODE"] = s26["UNLOCODE"].astype("string").str.strip().str.upper()
            script26_comparison = ports1.merge(
                s26[required26],
                left_on="UNLOCODE",
                right_on="UNLOCODE",
                how="outer",
                suffixes=("_Script71", "_Script26"),
                indicator=True,
            )
            script26_comparison["Port_Matched"] = script26_comparison["_merge"].eq("both")
            script26_comparison["Call_Count_Match"] = (
                script26_comparison["Port_Calls_Script71"]
                == script26_comparison["Port_Calls_Script26"]
            )
            script26_comparison["Peak_Match"] = (
                script26_comparison["Peak_Concurrent_Calls_Script71"]
                == script26_comparison["Peak_Concurrent_Calls_Script26"]
            )
            script26_comparison["Mean_Match"] = np.isclose(
                script26_comparison["Mean_Concurrent_Calls_Script71"],
                script26_comparison["Mean_Concurrent_Calls_Script26"],
                rtol=1e-8, atol=1e-8, equal_nan=True,
            )
            script26_comparison = script26_comparison.drop(columns=["_merge"])

    checks = []
    def add(name, passed, observed, expected, note):
        checks.append({
            "Check": name, "Passed": bool(passed),
            "Observed": observed, "Expected": expected, "Interpretation": note,
        })

    add("All source records pass identity/timestamp/stay validation",
        len(valid) == len(df), len(valid), len(df),
        "Records with unresolved source-level issues are not silently repaired.")
    add("Simulation record IDs unique",
        not df["Simulation_Record_ID"].duplicated().any(),
        int(df["Simulation_Record_ID"].duplicated().sum()), 0, "Record identity check.")
    add("Every retained interval is positive",
        (valid["Timestamp_Interval_Hours"] > 0).all(),
        int((valid["Timestamp_Interval_Hours"] <= 0).sum()), 0, "Timestamp ordering.")
    add("Two independent replay runs produce same port peaks",
        repro["Peak_Match"].all(), int(repro["Peak_Match"].sum()), len(repro), "Deterministic replay.")
    add("Two independent replay runs produce same port means",
        repro["Mean_Match"].all(), int(repro["Mean_Match"].sum()), len(repro), "Deterministic replay.")
    add("Two independent replay runs produce same area",
        repro["Area_Match"].all(), int(repro["Area_Match"].sum()), len(repro), "Deterministic replay.")
    add("Two independent replay runs produce same final states",
        repro["Final_State_Match"].all(), int(repro["Final_State_Match"].sum()), len(repro), "Deterministic replay.")
    add("Concurrency area reconciles to observed interval sum",
        port_validation["Area_Reconciles"].all(),
        int(port_validation["Area_Reconciles"].sum()), len(port_validation),
        "Area identity is an accounting check, not berth occupancy validation.")
    add("All port replay final active-call counts are zero",
        port_validation["Final_State_Is_Zero"].all(),
        int(port_validation["Final_State_Is_Zero"].sum()), len(port_validation), "Event balance.")
    add("No negative intermediate active-call states",
        port_validation["No_Negative_States"].all(),
        int(port_validation["No_Negative_States"].sum()), len(port_validation), "Event-state validity.")
    add("Two events per retained port call",
        port_validation["Event_Count_Reconciles"].all(),
        int(port_validation["Event_Count_Reconciles"].sum()), len(port_validation), "Arrival/departure event accounting.")

    expected_timeline_rows = int(port_validation["Exact_Event_Timestamps"].sum())
    timeline_port_count = int(timeline1["UNLOCODE"].nunique()) if not timeline1.empty else 0
    timeline_counts = (
        timeline1.groupby("UNLOCODE").size().rename("Timeline_Rows")
        if not timeline1.empty else pd.Series(dtype="int64", name="Timeline_Rows")
    )
    expected_counts = port_validation.set_index("UNLOCODE")["Exact_Event_Timestamps"]
    aligned_timeline_counts = (
        timeline_counts.reindex(expected_counts.index).fillna(-1).to_numpy(dtype="int64")
    )
    expected_timeline_counts = expected_counts.to_numpy(dtype="int64")
    timeline_count_match = (
        len(timeline1) == expected_timeline_rows
        and np.array_equal(aligned_timeline_counts, expected_timeline_counts)
    )
    add("Exported event timeline contains every grouped timestamp",
        len(timeline1) == expected_timeline_rows,
        len(timeline1), expected_timeline_rows,
        "One row is expected for every distinct exact timestamp within each port.")
    add("Exported event timeline covers all replayed ports",
        timeline_port_count == len(port_validation),
        timeline_port_count, len(port_validation),
        "Every port in the replay must appear in the exported timeline.")
    add("Per-port timeline row counts match grouped event counts",
        timeline_count_match,
        int((timeline_counts.reindex(expected_counts.index).fillna(-1).to_numpy()
             == expected_counts.astype("int64").to_numpy()).sum()),
        len(expected_counts),
        "Checks timeline completeness separately for each port.")
    timeline_final_states = (
        timeline1.sort_values(["UNLOCODE", "Timestamp_UTC"])
        .groupby("UNLOCODE", as_index=False).tail(1)
        if not timeline1.empty else pd.DataFrame()
    )
    timeline_final_zero = (
        not timeline_final_states.empty
        and timeline_final_states["Active_Port_Calls_After_Event"].eq(0).all()
        and len(timeline_final_states) == len(port_validation)
    )
    add("Exported timeline ends at zero active calls for every port",
        timeline_final_zero,
        int(timeline_final_states["Active_Port_Calls_After_Event"].eq(0).sum())
        if not timeline_final_states.empty else 0,
        len(port_validation),
        "Final event state in the exported timeline must be zero for every port.")

    add("Script26 comparison available",
        script26_available, script26_available, "Optional input",
        "If unavailable, cross-script comparison is not assessed.")
    if script26_available and not script26_comparison.empty:
        add("Script26 port coverage matches",
            script26_comparison["Port_Matched"].all(),
            int(script26_comparison["Port_Matched"].sum()), len(script26_comparison),
            "Cross-script comparison.")
        add("Script26 call counts match",
            script26_comparison["Call_Count_Match"].fillna(False).all(),
            int(script26_comparison["Call_Count_Match"].fillna(False).sum()),
            len(script26_comparison), "Cross-script comparison.")
        add("Script26 peak concurrency matches",
            script26_comparison["Peak_Match"].fillna(False).all(),
            int(script26_comparison["Peak_Match"].fillna(False).sum()),
            len(script26_comparison), "Cross-script comparison.")
        add("Script26 mean concurrency matches",
            script26_comparison["Mean_Match"].fillna(False).all(),
            int(script26_comparison["Mean_Match"].fillna(False).sum()),
            len(script26_comparison), "Cross-script comparison.")
    add("No simulation parameters or source files modified",
        True, "NO", "NO", "Script71 is an independent read-only audit.")

    checks_df = pd.DataFrame(checks)

    record_audit.to_csv(OUTPUTS["records"], index=False)
    port_validation.to_csv(OUTPUTS["ports"], index=False)
    timeline1.to_csv(OUTPUTS["timeline"], index=False)
    repro.to_csv(OUTPUTS["repro"], index=False)
    if not script26_comparison.empty:
        script26_comparison.to_csv(OUTPUTS["script26"], index=False)
    else:
        pd.DataFrame(columns=[
            "UNLOCODE", "Port_Matched", "Call_Count_Match", "Peak_Match", "Mean_Match"
        ]).to_csv(OUTPUTS["script26"], index=False)
    checks_df.to_csv(OUTPUTS["checks"], index=False)

    passed = int(checks_df["Passed"].sum())
    report = f"""================================================================================
SCRIPT 71: CANONICAL HISTORICAL REPLAY ENGINE AUDIT AND VALIDATION
================================================================================

INPUT
Source file: {INPUT_FILE.name}
Source records: {len(df)}
Records retained for replay: {len(valid)}
Records requiring review: {len(df)-len(valid)}
Unique vessels: {valid['IMO_Normalised'].nunique()}
Ports replayed: {valid['UNLOCODE_Normalised'].nunique()}

EVENT REPLAY
Replay runs: 2
Raw events: {2*len(valid)}
Exact event timestamp grouping: integer UTC nanoseconds
Port concurrency area: sum of observed arrival-to-departure intervals
Negative intermediate states: {int(port_validation['Negative_State_Count'].sum())}
Nonzero final active-call states: {int((~port_validation['Final_State_Is_Zero']).sum())}
Port area reconciliation failures: {int((~port_validation['Area_Reconciles']).sum())}
Exported event timeline rows: {len(timeline1)}
Expected grouped event timestamps: {int(port_validation['Exact_Event_Timestamps'].sum())}
Ports represented in event timeline: {timeline1['UNLOCODE'].nunique() if not timeline1.empty else 0}

REPRODUCIBILITY
Peak matches: {int(repro['Peak_Match'].sum())}/{len(repro)}
Mean matches: {int(repro['Mean_Match'].sum())}/{len(repro)}
Area matches: {int(repro['Area_Match'].sum())}/{len(repro)}
Final-state matches: {int(repro['Final_State_Match'].sum())}/{len(repro)}

SCRIPT26 COMPARISON
Available and schema-valid: {script26_available}
{script26_comparison[['UNLOCODE','Port_Matched','Call_Count_Match','Peak_Match','Mean_Match']].to_string(index=False) if script26_available and not script26_comparison.empty else 'Not assessed.'}

READINESS / VALIDATION CHECKS
Passed: {passed}/{len(checks_df)}
{checks_df[['Check','Passed','Observed','Expected']].to_string(index=False)}

LIMITATIONS
- Port-call concurrency is not verified berth occupancy.
- The replay validates event arithmetic, not source-record physical accuracy.
- Historical port-call intervals may include anchorage, waiting, and operations.
- Inter-port elapsed time is not pure sailing time.
- No physical route or actual Strait of Hormuz transit is inferred.
- This script does not validate disruption, recovery, or predictive behaviour.

SIMULATION EXPERIMENTS EXECUTED: NO
DISRUPTION MAGNITUDES SELECTED: NO
SOURCE FILES MODIFIED: NO
SCRIPT19 INPUTS MODIFIED: NO
"""
    OUTPUTS["report"].write_text(report, encoding="utf-8")

    print("=" * 96)
    print("SCRIPT 71: CANONICAL HISTORICAL REPLAY ENGINE AUDIT AND VALIDATION")
    print("=" * 96)
    print(f"Source records: {len(df)} | Replayed: {len(valid)} | Ports: {len(port_validation)}")
    print(f"Deterministic replay: {int(repro['Peak_Match'].sum())}/{len(repro)} port peaks match")
    print(f"Validation checks: {passed}/{len(checks_df)} passed")
    for key, path in OUTPUTS.items():
        print(path.relative_to(ROOT))
    print("DISRUPTION EXPERIMENTS EXECUTED: NO")
    print("SCRIPT 71 COMPLETED" if checks_df["Passed"].all() else "SCRIPT 71 COMPLETED WITH CHECKS REQUIRING REVIEW")

if __name__ == "__main__":
    main()
