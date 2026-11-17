#!/usr/bin/env python3
# Script 75 — Controlled Inter-Port Elapsed-Time Shock Experiment
#
# Run from the project root:
#   python src/75_controlled_interport_elapsed_time_shock_experiment.py
#
# Reads Script 73's validated call-level baseline and the Script 19 historical
# schedule. It applies explicitly hypothetical shocks to selected consecutive
# distinct-port vessel transitions and propagates delay through each vessel's
# subsequent calls.
#
# This is NOT a physical route model, pure sailing-time model, berth-capacity
# model, AIS validation, or evidence of actual Strait of Hormuz transit.

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

TABLE_DIR = Path("outputs/tables")
REPORT_DIR = Path("outputs/reports")

S73_FILE = "73_call_level_baseline_propagation_register.csv"
SCHEDULE_FILE = "19_historical_arrival_schedule.csv"

EXPECTED_CALLS = 604
EXPECTED_VESSELS = 155
EXPECTED_PORTS = 19
EXPECTED_LINKS = 449
EXPECTED_INTERPORT = 271
EXPECTED_SAME_PORT = 178

# Explicit experiment design assumptions, not empirical estimates.
SEED = 7501
AFFECTED_TRANSITION_SHARES = [0.10, 0.25, 0.50, 1.00]
SHOCK_HOURS = [6.0, 12.0, 24.0, 48.0]
TOL = 1e-9


def require_columns(df: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def add_check(rows: list[dict[str, Any]], check_id: str, description: str,
              passed: bool, observed: Any, expected: Any,
              severity: str = "ERROR") -> None:
    rows.append({
        "Check_ID": check_id,
        "Description": description,
        "Passed": bool(passed),
        "Observed": str(observed),
        "Expected": str(expected),
        "Severity": severity,
    })


def build_ordered_schedule(schedule: pd.DataFrame) -> pd.DataFrame:
    required = [
        "Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised",
        "Actual_Arrival_UTC", "Actual_Departure_UTC", "Actual_Stay_Hours",
    ]
    require_columns(schedule, required, "Script 19 historical schedule")
    out = schedule.copy()
    out["_arrival"] = pd.to_datetime(out["Actual_Arrival_UTC"], utc=True, errors="coerce")
    out["_departure"] = pd.to_datetime(out["Actual_Departure_UTC"], utc=True, errors="coerce")
    if out[["_arrival", "_departure"]].isna().any().any():
        raise ValueError("Historical schedule contains unparseable UTC timestamps.")
    if out[["Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised"]].isna().any().any():
        raise ValueError("Historical schedule contains missing call/vessel/port identity.")
    if out["Simulation_Record_ID"].duplicated().any():
        raise ValueError("Historical schedule contains duplicate Simulation_Record_ID.")
    if (out["_departure"] <= out["_arrival"]).any():
        raise ValueError("Historical schedule contains non-positive call intervals.")

    out = out.sort_values(
        ["IMO_Normalised", "_arrival", "Simulation_Record_ID"],
        kind="mergesort"
    ).copy()
    grp = out.groupby("IMO_Normalised", sort=False)
    out["Vessel_Call_Sequence_Number"] = grp.cumcount() + 1
    out["Previous_Simulation_Record_ID"] = grp["Simulation_Record_ID"].shift(1)
    out["Previous_Port"] = grp["UNLOCODE_Normalised"].shift(1)
    out["Previous_Departure_UTC"] = grp["_departure"].shift(1)
    out["Observed_Inter_Call_Elapsed_Hours"] = (
        out["_arrival"] - out["Previous_Departure_UTC"]
    ).dt.total_seconds() / 3600.0
    has_previous = out["Previous_Simulation_Record_ID"].notna()
    if (out.loc[has_previous, "Observed_Inter_Call_Elapsed_Hours"] < 0).any():
        raise ValueError("Negative inter-call elapsed time found; refusing to silently repair.")
    out["Transition_Type"] = "FIRST_CALL"
    out.loc[has_previous, "Transition_Type"] = np.where(
        out.loc[has_previous, "UNLOCODE_Normalised"].astype(str).to_numpy()
        == out.loc[has_previous, "Previous_Port"].astype(str).to_numpy(),
        "SAME_PORT_SEQUENCE_LINK",
        "DISTINCT_PORT_INTERPORT_TRANSITION",
    )
    return out


def propagate_scenario(
    ordered: pd.DataFrame,
    shock_by_call: dict[str, float],
    scenario_id: str,
) -> pd.DataFrame:
    """Apply arrival shock at the affected transition's next call."""
    out = ordered.copy()
    arrival_delays: list[float] = []
    departure_delays: list[float] = []
    shock_values: list[float] = []
    previous_departure_delay: dict[str, float] = {}

    for row in out[[
        "Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised"
    ]].itertuples(index=False):
        call_id = str(row.Simulation_Record_ID)
        vessel = str(row.IMO_Normalised)
        shock = float(shock_by_call.get(call_id, 0.0))
        prior = previous_departure_delay.get(vessel, 0.0)
        arrival_delay = prior + shock
        # No port-call duration shock and no recovery in Script 75.
        departure_delay = arrival_delay
        arrival_delays.append(arrival_delay)
        departure_delays.append(departure_delay)
        shock_values.append(shock)
        previous_departure_delay[vessel] = departure_delay

    out["Scenario_ID"] = scenario_id
    out["Transit_Elapsed_Time_Shock_Hours"] = shock_values
    out["Port_Call_Duration_Shock_Hours"] = 0.0
    out["Recovery_Advance_Hours"] = 0.0
    out["Simulated_Arrival_Delay_Hours"] = arrival_delays
    out["Simulated_Departure_Delay_Hours"] = departure_delays
    out["Simulated_Arrival_UTC"] = out["_arrival"] + pd.to_timedelta(
        out["Simulated_Arrival_Delay_Hours"], unit="h"
    )
    out["Simulated_Departure_UTC"] = out["_departure"] + pd.to_timedelta(
        out["Simulated_Departure_Delay_Hours"], unit="h"
    )
    return out


def summarize_scenario(result: pd.DataFrame, scenario: dict[str, Any]) -> dict[str, Any]:
    vessel = result.groupby("IMO_Normalised", dropna=False).agg(
        Call_Count=("Simulation_Record_ID", "size"),
        Accumulated_Arrival_Delay_Hours=("Simulated_Arrival_Delay_Hours", "sum"),
        Accumulated_Departure_Delay_Hours=("Simulated_Departure_Delay_Hours", "sum"),
        Maximum_Arrival_Delay_Hours=("Simulated_Arrival_Delay_Hours", "max"),
        Maximum_Departure_Delay_Hours=("Simulated_Departure_Delay_Hours", "max"),
        Final_Departure_Delay_Hours=("Simulated_Departure_Delay_Hours", "last"),
    ).reset_index()

    affected_vessels = int(
        result.loc[result["Transit_Elapsed_Time_Shock_Hours"] > 0, "IMO_Normalised"].nunique()
    )
    shocked_calls = int((result["Transit_Elapsed_Time_Shock_Hours"] > 0).sum())
    return {
        **scenario,
        "Calls": len(result),
        "Vessels": result["IMO_Normalised"].nunique(),
        "Ports": result["UNLOCODE_Normalised"].nunique(),
        "Shocked_Transition_Count": shocked_calls,
        "Affected_Vessel_Count": affected_vessels,
        "Total_Accumulated_Arrival_Delay_Hours": result["Simulated_Arrival_Delay_Hours"].sum(),
        "Total_Accumulated_Departure_Delay_Hours": result["Simulated_Departure_Delay_Hours"].sum(),
        "Mean_Call_Arrival_Delay_Hours": result["Simulated_Arrival_Delay_Hours"].mean(),
        "Mean_Call_Departure_Delay_Hours": result["Simulated_Departure_Delay_Hours"].mean(),
        "P90_Call_Arrival_Delay_Hours": result["Simulated_Arrival_Delay_Hours"].quantile(0.90),
        "Maximum_Call_Arrival_Delay_Hours": result["Simulated_Arrival_Delay_Hours"].max(),
        "Maximum_Final_Vessel_Departure_Delay_Hours": vessel["Final_Departure_Delay_Hours"].max(),
        "Mean_Final_Vessel_Departure_Delay_Hours": vessel["Final_Departure_Delay_Hours"].mean(),
        "Maximum_Accumulated_Departure_Delay_Per_Vessel_Hours": vessel[
            "Accumulated_Departure_Delay_Hours"
        ].max(),
        "Total_Vessel_Accumulated_Departure_Delay_Hours": vessel[
            "Accumulated_Departure_Delay_Hours"
        ].sum(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.expanduser().resolve()
    tables = root / TABLE_DIR
    reports = root / REPORT_DIR
    reports.mkdir(parents=True, exist_ok=True)

    s73_path = tables / S73_FILE
    schedule_path = root / "data/simulation_inputs" / SCHEDULE_FILE
    if not s73_path.exists():
        raise FileNotFoundError(f"Missing Script 73 baseline output: {s73_path}")
    if not schedule_path.exists():
        raise FileNotFoundError(f"Missing Script 19 historical schedule: {schedule_path}")

    baseline73 = pd.read_csv(s73_path, low_memory=False)
    schedule = pd.read_csv(schedule_path, low_memory=False)
    ordered = build_ordered_schedule(schedule)

    require_columns(
        baseline73,
        ["Simulation_Record_ID", "IMO_Normalised", "Actual_Arrival_UTC",
         "Actual_Departure_UTC", "Simulated_Arrival_UTC",
         "Simulated_Departure_UTC"],
        "Script 73 call-level baseline"
    )
    baseline_compare = ordered[[
        "Simulation_Record_ID", "IMO_Normalised", "Actual_Arrival_UTC",
        "Actual_Departure_UTC"
    ]].merge(
        baseline73[[
            "Simulation_Record_ID", "IMO_Normalised", "Actual_Arrival_UTC",
            "Actual_Departure_UTC", "Simulated_Arrival_UTC",
            "Simulated_Departure_UTC"
        ]],
        on=["Simulation_Record_ID", "IMO_Normalised"],
        how="outer",
        suffixes=("_s19", "_s73"),
        indicator=True,
        validate="one_to_one",
    )
    baseline_key_mismatches = int((baseline_compare["_merge"] != "both").sum())
    source_timestamp_mismatches = int((
        (baseline_compare["Actual_Arrival_UTC_s19"].astype(str)
         != baseline_compare["Actual_Arrival_UTC_s73"].astype(str))
        | (baseline_compare["Actual_Departure_UTC_s19"].astype(str)
           != baseline_compare["Actual_Departure_UTC_s73"].astype(str))
    ).sum())
    baseline_arrival_mismatches = int((
        pd.to_datetime(baseline_compare["Actual_Arrival_UTC_s19"], utc=True)
        != pd.to_datetime(baseline_compare["Simulated_Arrival_UTC"], utc=True)
    ).sum())
    baseline_departure_mismatches = int((
        pd.to_datetime(baseline_compare["Actual_Departure_UTC_s19"], utc=True)
        != pd.to_datetime(baseline_compare["Simulated_Departure_UTC"], utc=True)
    ).sum())

    links = ordered.loc[ordered["Transition_Type"] != "FIRST_CALL"].copy()
    interport = links.loc[
        links["Transition_Type"] == "DISTINCT_PORT_INTERPORT_TRANSITION"
    ].copy()
    same_port = links.loc[
        links["Transition_Type"] == "SAME_PORT_SEQUENCE_LINK"
    ].copy()

    checks: list[dict[str, Any]] = []
    add_check(checks, "S73_SCHEDULE_KEY_RECONCILIATION",
              "Script 19 schedule and Script 73 baseline reconcile by call/vessel identity",
              baseline_key_mismatches == 0, baseline_key_mismatches, 0)
    add_check(checks, "S73_SOURCE_TIMESTAMP_RECONCILIATION",
              "Script 19 and Script 73 source timestamp strings match",
              source_timestamp_mismatches == 0, source_timestamp_mismatches, 0)
    add_check(checks, "S73_BASELINE_ARRIVAL_IDENTITY",
              "Script 73 baseline simulated arrivals equal Script 19 observed arrivals",
              baseline_arrival_mismatches == 0, baseline_arrival_mismatches, 0)
    add_check(checks, "S73_BASELINE_DEPARTURE_IDENTITY",
              "Script 73 baseline simulated departures equal Script 19 observed departures",
              baseline_departure_mismatches == 0, baseline_departure_mismatches, 0)
    add_check(checks, "SOURCE_DIMENSIONS",
              "Historical schedule dimensions match established baseline",
              (len(ordered), ordered["IMO_Normalised"].nunique(),
               ordered["UNLOCODE_Normalised"].nunique()) ==
              (EXPECTED_CALLS, EXPECTED_VESSELS, EXPECTED_PORTS),
              (len(ordered), ordered["IMO_Normalised"].nunique(),
               ordered["UNLOCODE_Normalised"].nunique()),
              (EXPECTED_CALLS, EXPECTED_VESSELS, EXPECTED_PORTS))
    add_check(checks, "SEQUENCE_LINK_COUNTS",
              "Vessel sequence, same-port and inter-port link counts reconcile",
              (len(links), len(same_port), len(interport)) ==
              (EXPECTED_LINKS, EXPECTED_SAME_PORT, EXPECTED_INTERPORT),
              (len(links), len(same_port), len(interport)),
              (EXPECTED_LINKS, EXPECTED_SAME_PORT, EXPECTED_INTERPORT))
    add_check(checks, "NONNEGATIVE_OBSERVED_GAPS",
              "All observed inter-call elapsed times are non-negative",
              bool((links["Observed_Inter_Call_Elapsed_Hours"] >= 0).all()),
              int((links["Observed_Inter_Call_Elapsed_Hours"] < 0).sum()), 0)

    # Deterministic nested selection from the 271 distinct-port transitions.
    interport = interport.sort_values(
        ["IMO_Normalised", "Observed_Inter_Call_Elapsed_Hours",
         "Previous_Simulation_Record_ID", "Simulation_Record_ID"],
        kind="mergesort"
    ).reset_index(drop=True)
    rng = np.random.default_rng(SEED)
    permutation = rng.permutation(len(interport))
    scenario_definitions = [{
        "Scenario_ID": "S75-BASE",
        "Affected_Transition_Share": 0.0,
        "Shock_Magnitude_Hours": 0.0,
        "Selection_Seed": SEED,
        "Scenario_Type": "NO_DISRUPTION_BASELINE",
    }]
    scenario_selections: dict[str, set[str]] = {"S75-BASE": set()}
    for share in AFFECTED_TRANSITION_SHARES:
        count = int(np.ceil(len(interport) * share))
        selected_indices = permutation[:count]
        selected_ids = set(
            interport.iloc[selected_indices]["Simulation_Record_ID"].astype(str)
        )
        for shock in SHOCK_HOURS:
            sid = f"S75-P{int(share * 100):02d}-D{int(shock):02d}"
            scenario_definitions.append({
                "Scenario_ID": sid,
                "Affected_Transition_Share": share,
                "Shock_Magnitude_Hours": shock,
                "Selection_Seed": SEED,
                "Scenario_Type": "HYPOTHETICAL_INTERPORT_ELAPSED_TIME_SHOCK",
            })
            scenario_selections[sid] = selected_ids

    all_calls = []
    all_vessels = []
    all_summaries = []
    shock_register_rows = []
    baseline_result = None

    for scenario in scenario_definitions:
        sid = scenario["Scenario_ID"]
        selected_ids = scenario_selections[sid]
        shock = float(scenario["Shock_Magnitude_Hours"])
        shock_by_call = {call_id: shock for call_id in selected_ids}
        result = propagate_scenario(ordered, shock_by_call, sid)

        # Attach affected-transition identity to every call. A shock is applied
        # to the current call's arrival after its preceding distinct-port link.
        result["Affected_Transition"] = result["Simulation_Record_ID"].astype(str).isin(selected_ids)
        result["Scenario_Type"] = scenario["Scenario_Type"]
        result["Affected_Transition_Share_Design"] = scenario["Affected_Transition_Share"]
        result["Shock_Magnitude_Design_Hours"] = shock

        vessel = result.groupby("IMO_Normalised", dropna=False).agg(
            Call_Count=("Simulation_Record_ID", "size"),
            Accumulated_Arrival_Delay_Hours=("Simulated_Arrival_Delay_Hours", "sum"),
            Accumulated_Departure_Delay_Hours=("Simulated_Departure_Delay_Hours", "sum"),
            Maximum_Arrival_Delay_Hours=("Simulated_Arrival_Delay_Hours", "max"),
            Maximum_Departure_Delay_Hours=("Simulated_Departure_Delay_Hours", "max"),
            Final_Departure_Delay_Hours=("Simulated_Departure_Delay_Hours", "last"),
        ).reset_index()
        vessel["Scenario_ID"] = sid
        vessel["Scenario_Type"] = scenario["Scenario_Type"]
        vessel["Affected_Vessel"] = vessel["IMO_Normalised"].isin(
            result.loc[result["Affected_Transition"], "IMO_Normalised"].unique()
        )
        all_vessels.append(vessel)

        all_calls.append(result[[
            "Scenario_ID", "Scenario_Type", "Affected_Transition_Share_Design",
            "Shock_Magnitude_Design_Hours", "Simulation_Record_ID",
            "IMO_Normalised", "UNLOCODE_Normalised",
            "Vessel_Call_Sequence_Number", "Previous_Simulation_Record_ID",
            "Previous_Port", "Transition_Type",
            "Observed_Inter_Call_Elapsed_Hours", "Affected_Transition",
            "Transit_Elapsed_Time_Shock_Hours",
            "Port_Call_Duration_Shock_Hours", "Recovery_Advance_Hours",
            "Actual_Arrival_UTC", "Actual_Departure_UTC",
            "Simulated_Arrival_UTC", "Simulated_Departure_UTC",
            "Simulated_Arrival_Delay_Hours",
            "Simulated_Departure_Delay_Hours",
        ]].copy())

        all_summaries.append(summarize_scenario(result, scenario))
        for row in interport.itertuples(index=False):
            is_selected = str(row.Simulation_Record_ID) in selected_ids
            shock_register_rows.append({
                "Scenario_ID": sid,
                "IMO_Normalised": row.IMO_Normalised,
                "Previous_Simulation_Record_ID": row.Previous_Simulation_Record_ID,
                "Simulation_Record_ID": row.Simulation_Record_ID,
                "Previous_Port": row.Previous_Port,
                "Next_Port": row.UNLOCODE_Normalised,
                "Observed_Inter_Call_Elapsed_Hours": row.Observed_Inter_Call_Elapsed_Hours,
                "Selected_For_Hypothetical_Shock": is_selected,
                "Applied_Elapsed_Time_Shock_Hours": shock if is_selected else 0.0,
                "Selection_Seed": SEED,
            })
        if sid == "S75-BASE":
            baseline_result = result.copy()

    calls_out = pd.concat(all_calls, ignore_index=True)
    vessels_out = pd.concat(all_vessels, ignore_index=True)
    summary = pd.DataFrame(all_summaries)
    shock_register = pd.DataFrame(shock_register_rows)

    # Scenario-level monotonicity checks: nested affected sets and increasing
    # non-negative shock magnitudes must not reduce aggregate delay.
    monotonicity_rows = []
    for share in AFFECTED_TRANSITION_SHARES:
        subset = summary.loc[summary["Affected_Transition_Share"] == share].sort_values(
            "Shock_Magnitude_Hours"
        )
        vals = subset["Total_Accumulated_Departure_Delay_Hours"].to_numpy()
        monotonicity_rows.append({
            "Monotonicity_Check": f"SHOCK_MAGNITUDE_{int(share*100)}PCT",
            "Passed": bool(np.all(np.diff(vals) >= -TOL)),
            "Observed_Values": ";".join(f"{v:.6f}" for v in vals),
            "Expected": "non-decreasing with shock magnitude",
        })
    for shock in SHOCK_HOURS:
        subset = summary.loc[summary["Shock_Magnitude_Hours"] == shock].sort_values(
            "Affected_Transition_Share"
        )
        vals = subset["Total_Accumulated_Departure_Delay_Hours"].to_numpy()
        monotonicity_rows.append({
            "Monotonicity_Check": f"AFFECTED_SHARE_{int(shock)}H",
            "Passed": bool(np.all(np.diff(vals) >= -TOL)),
            "Observed_Values": ";".join(f"{v:.6f}" for v in vals),
            "Expected": "non-decreasing with affected transition share",
        })
    monotonicity = pd.DataFrame(monotonicity_rows)

    baseline_calls = calls_out.loc[calls_out["Scenario_ID"] == "S75-BASE"].copy()
    baseline_zero_failures = int((
        (baseline_calls["Simulated_Arrival_Delay_Hours"] != 0)
        | (baseline_calls["Simulated_Departure_Delay_Hours"] != 0)
    ).sum())
    scenario_count = len(scenario_definitions)
    expected_call_rows = EXPECTED_CALLS * scenario_count
    expected_vessel_rows = EXPECTED_VESSELS * scenario_count
    negative_simulated_delays = int((
        (calls_out["Simulated_Arrival_Delay_Hours"] < -TOL)
        | (calls_out["Simulated_Departure_Delay_Hours"] < -TOL)
    ).sum())
    no_shock_same_port_shock_rows = int((
        (calls_out["Transition_Type"] == "SAME_PORT_SEQUENCE_LINK")
        & (calls_out["Transit_Elapsed_Time_Shock_Hours"] != 0)
    ).sum())

    add_check(checks, "SCENARIO_COUNT",
              "One baseline plus sixteen hypothetical scenarios are generated",
              scenario_count == 17, scenario_count, 17)
    add_check(checks, "SCENARIO_CALL_ROW_COUNT",
              "Every scenario contains all 604 calls",
              len(calls_out) == expected_call_rows,
              len(calls_out), expected_call_rows)
    add_check(checks, "SCENARIO_VESSEL_ROW_COUNT",
              "Every scenario contains all 155 vessel summaries",
              len(vessels_out) == expected_vessel_rows,
              len(vessels_out), expected_vessel_rows)
    add_check(checks, "BASELINE_ZERO_DELAY",
              "S75 baseline scenario has zero delay on all calls",
              baseline_zero_failures == 0, baseline_zero_failures, 0)
    add_check(checks, "NO_NEGATIVE_SIMULATED_DELAYS",
              "No simulated arrival or departure delay is negative",
              negative_simulated_delays == 0, negative_simulated_delays, 0)
    add_check(checks, "NO_SHOCK_ON_SAME_PORT_LINKS",
              "Hypothetical inter-port shocks are not assigned to same-port links",
              no_shock_same_port_shock_rows == 0,
              no_shock_same_port_shock_rows, 0)
    add_check(checks, "SCENARIO_MONOTONICITY",
              "Aggregate vessel departure delay is non-decreasing with shock magnitude and scope",
              bool(monotonicity["Passed"].all()),
              int((~monotonicity["Passed"]).sum()), 0)

    # Exact nested-selection checks.
    nested_ok = True
    for i, share_a in enumerate(AFFECTED_TRANSITION_SHARES):
        set_a = scenario_selections[
            f"S75-P{int(share_a*100):02d}-D{int(SHOCK_HOURS[0]):02d}"
        ]
        for share_b in AFFECTED_TRANSITION_SHARES[i + 1:]:
            set_b = scenario_selections[
                f"S75-P{int(share_b*100):02d}-D{int(SHOCK_HOURS[0]):02d}"
            ]
            if not set_a.issubset(set_b):
                nested_ok = False
    add_check(checks, "NESTED_AFFECTED_TRANSITION_SELECTION",
              "Affected transition sets are nested as scope increases",
              nested_ok, nested_ok, True)

    checks_df = pd.DataFrame(checks)
    checks_df["Overall_Status"] = np.where(checks_df["Passed"], "PASS", "FAIL")

    # Scenario factor register.
    factor_register = pd.DataFrame(scenario_definitions)
    factor_register["Selection_Method"] = (
        "Seeded random permutation; nested prefixes; distinct-port transitions only"
    )
    factor_register["Interpretation"] = (
        "Hypothetical additional departure-to-next-arrival elapsed time at selected transition"
    )

    outputs = {
        "75_scenario_factor_register.csv": factor_register,
        "75_call_level_disruption_results.csv": calls_out,
        "75_vessel_level_disruption_results.csv": vessels_out,
        "75_scenario_comparison_summary.csv": summary,
        "75_hypothetical_transition_shock_register.csv": shock_register,
        "75_scenario_monotonicity_checks.csv": monotonicity,
        "75_validation_checks.csv": checks_df,
    }
    tables.mkdir(parents=True, exist_ok=True)
    for filename, frame in outputs.items():
        frame.to_csv(tables / filename, index=False)

    failed = checks_df.loc[~checks_df["Passed"]]
    report = [
        "SCRIPT 75 — CONTROLLED INTER-PORT ELAPSED-TIME SHOCK EXPERIMENT",
        "=" * 72,
        f"Project root: {root}",
        f"Historical calls: {len(ordered)}",
        f"Vessels: {ordered['IMO_Normalised'].nunique()}",
        f"Ports: {ordered['UNLOCODE_Normalised'].nunique()}",
        f"Sequence links: {len(links)}",
        f"Same-port links: {len(same_port)}",
        f"Distinct-port transitions: {len(interport)}",
        f"Scenarios: {scenario_count} (1 baseline + 16 hypothetical)",
        f"Call-level scenario records: {len(calls_out)}",
        f"Vessel-level scenario records: {len(vessels_out)}",
        f"Shock selection seed: {SEED}",
        f"Shock magnitudes (hours): {SHOCK_HOURS}",
        f"Affected transition shares: {AFFECTED_TRANSITION_SHARES}",
        "",
        "BASELINE / EXPERIMENT DESIGN",
        "- Shock is applied to the next call's arrival after a selected distinct-port transition.",
        "- The same shock is carried into that call's departure delay; observed port-call duration is unchanged.",
        "- Delay then propagates through the vessel's subsequent calls, including same-port links.",
        "- No recovery policy is applied.",
        "- Selection is deterministic and nested across affected-transition shares.",
        "",
        "IMPORTANT INTERPRETATION",
        "- The shocked quantity is additional observed inter-port elapsed time.",
        "- Observed departure-to-next-arrival elapsed time is not pure sailing time.",
        "- Scenarios and shock magnitudes are hypothetical design assumptions, not empirical estimates.",
        "- The data do not establish physical routes or actual Strait of Hormuz transit.",
        "- No port capacity, berth occupancy, or operational feasibility is inferred.",
        "",
        f"Validation checks passed: {int(checks_df['Passed'].sum())}/{len(checks_df)}",
        f"Validation checks failed: {len(failed)}",
        "",
        "FAILED CHECKS",
    ]
    if failed.empty:
        report.append("None.")
    else:
        report.extend([
            f"- {r.Check_ID}: observed={r.Observed}; expected={r.Expected}"
            for r in failed.itertuples(index=False)
        ])
    report += [
        "",
        "OUTPUT FILES",
        *[f"- outputs/tables/{name}" for name in outputs],
        "- outputs/reports/75_controlled_interport_elapsed_time_shock_experiment_report.txt",
    ]
    report_path = reports / "75_controlled_interport_elapsed_time_shock_experiment_report.txt"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))

    if not failed.empty:
        print("\nFAILED: inspect Script 75 outputs before interpreting scenarios.", file=sys.stderr)
        return 2
    print("\nSUCCESS: Script 75 experiment and validation checks completed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nSCRIPT 75 FAILED: {exc}", file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(1)
