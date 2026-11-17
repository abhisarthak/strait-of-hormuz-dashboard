#!/usr/bin/env python3
# Script 76 — Controlled Schedule-Recovery Policy Experiment
#
# Run from the project root:
#   python src/76_controlled_schedule_recovery_policy_experiment.py
#
# Reads Script 75's validated call-level disruption scenarios and applies
# explicitly hypothetical, bounded recovery credits at subsequent vessel
# sequence links. This is an abstract schedule-recovery experiment only.
#
# It does NOT model actual vessel speed, fuel use, weather, safety limits,
# port/berth capacity, operational recovery feasibility, or recovery cost.
# It does NOT establish actual Strait of Hormuz transit or route exposure.

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
INPUT_FILE = "75_call_level_disruption_results.csv"

EXPECTED_CALLS = 604
EXPECTED_VESSELS = 155
EXPECTED_SCENARIOS = 17
TOL = 1e-8

# Hypothetical policy definitions. These are design assumptions, not estimates.
POLICIES = [
    {
        "Recovery_Policy_ID": "R76-00-NONE",
        "Recovery_Policy": "No recovery",
        "Policy_Type": "NONE",
        "Fixed_Recovery_Cap_Hours": 0.0,
        "Proportional_Recovery_Rate": 0.0,
        "Maximum_Recovery_Per_Link_Hours": 0.0,
        "Interpretation": "No recovery credit is applied.",
    },
    {
        "Recovery_Policy_ID": "R76-01-FIXED-6H",
        "Recovery_Policy": "Fixed recovery credit, 6h per link",
        "Policy_Type": "FIXED",
        "Fixed_Recovery_Cap_Hours": 6.0,
        "Proportional_Recovery_Rate": 0.0,
        "Maximum_Recovery_Per_Link_Hours": 6.0,
        "Interpretation": "Up to 6h of existing accumulated delay is removed at each subsequent sequence link.",
    },
    {
        "Recovery_Policy_ID": "R76-02-FIXED-12H",
        "Recovery_Policy": "Fixed recovery credit, 12h per link",
        "Policy_Type": "FIXED",
        "Fixed_Recovery_Cap_Hours": 12.0,
        "Proportional_Recovery_Rate": 0.0,
        "Maximum_Recovery_Per_Link_Hours": 12.0,
        "Interpretation": "Up to 12h of existing accumulated delay is removed at each subsequent sequence link.",
    },
    {
        "Recovery_Policy_ID": "R76-03-PROP-25-CAP6",
        "Recovery_Policy": "Proportional recovery, 25%, capped at 6h per link",
        "Policy_Type": "PROPORTIONAL",
        "Fixed_Recovery_Cap_Hours": 0.0,
        "Proportional_Recovery_Rate": 0.25,
        "Maximum_Recovery_Per_Link_Hours": 6.0,
        "Interpretation": "Removes 25% of delay available after the current shock, capped at 6h per link.",
    },
    {
        "Recovery_Policy_ID": "R76-04-PROP-50-CAP12",
        "Recovery_Policy": "Proportional recovery, 50%, capped at 12h per link",
        "Policy_Type": "PROPORTIONAL",
        "Fixed_Recovery_Cap_Hours": 0.0,
        "Proportional_Recovery_Rate": 0.50,
        "Maximum_Recovery_Per_Link_Hours": 12.0,
        "Interpretation": "Removes 50% of delay available after the current shock, capped at 12h per link.",
    },
]


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


def apply_recovery_policy(source: pd.DataFrame, policy: dict[str, Any]) -> pd.DataFrame:
    """Apply bounded abstract recovery at each non-first vessel sequence link."""
    out = source.sort_values(
        ["IMO_Normalised", "Vessel_Call_Sequence_Number", "Simulation_Record_ID"],
        kind="mergesort"
    ).copy()

    arrivals: list[float] = []
    departures: list[float] = []
    recoveries: list[float] = []
    pre_recovery: list[float] = []
    previous_departure_delay: dict[str, float] = {}

    for row in out[[
        "Simulation_Record_ID", "IMO_Normalised", "Transition_Type",
        "Transit_Elapsed_Time_Shock_Hours"
    ]].itertuples(index=False):
        vessel = str(row.IMO_Normalised)
        prior_delay = previous_departure_delay.get(vessel, 0.0)
        shock = float(row.Transit_Elapsed_Time_Shock_Hours)
        delay_before_recovery = prior_delay + shock

        if str(row.Transition_Type) == "FIRST_CALL":
            recovery = 0.0
        elif policy["Policy_Type"] == "FIXED":
            recovery = min(
                delay_before_recovery,
                float(policy["Fixed_Recovery_Cap_Hours"])
            )
        elif policy["Policy_Type"] == "PROPORTIONAL":
            recovery = min(
                delay_before_recovery * float(policy["Proportional_Recovery_Rate"]),
                float(policy["Maximum_Recovery_Per_Link_Hours"])
            )
        else:
            recovery = 0.0

        arrival_delay = max(0.0, delay_before_recovery - recovery)
        departure_delay = arrival_delay

        pre_recovery.append(delay_before_recovery)
        recoveries.append(recovery)
        arrivals.append(arrival_delay)
        departures.append(departure_delay)
        previous_departure_delay[vessel] = departure_delay

    out["Recovery_Policy_ID"] = policy["Recovery_Policy_ID"]
    out["Recovery_Policy"] = policy["Recovery_Policy"]
    out["Delay_Before_Recovery_Hours"] = pre_recovery
    out["Recovery_Advance_Hours"] = recoveries
    out["Simulated_Arrival_Delay_Hours"] = arrivals
    out["Simulated_Departure_Delay_Hours"] = departures

    actual_arrival = pd.to_datetime(out["Actual_Arrival_UTC"], utc=True)
    actual_departure = pd.to_datetime(out["Actual_Departure_UTC"], utc=True)
    out["Simulated_Arrival_UTC"] = actual_arrival + pd.to_timedelta(arrivals, unit="h")
    out["Simulated_Departure_UTC"] = actual_departure + pd.to_timedelta(departures, unit="h")
    return out


def summarize_policy(result: pd.DataFrame, scenario: dict[str, Any],
                     policy: dict[str, Any]) -> dict[str, Any]:
    vessel = result.groupby("IMO_Normalised", sort=False).agg(
        Call_Count=("Simulation_Record_ID", "size"),
        Accumulated_Arrival_Delay_Hours=("Simulated_Arrival_Delay_Hours", "sum"),
        Accumulated_Departure_Delay_Hours=("Simulated_Departure_Delay_Hours", "sum"),
        Maximum_Final_Departure_Delay_Hours=("Simulated_Departure_Delay_Hours", "last"),
        Maximum_Accumulated_Departure_Delay_Hours=("Simulated_Departure_Delay_Hours", "sum"),
    ).reset_index()

    total_delay = float(result["Simulated_Departure_Delay_Hours"].sum())
    # No-recovery comparisons are joined from the explicit no-recovery policy
    # summary after all policy runs have been generated.
    affected_vessels = int(
        result.loc[result["Transit_Elapsed_Time_Shock_Hours"] > 0, "IMO_Normalised"].nunique()
    )
    return {
        **scenario,
        "Recovery_Policy_ID": policy["Recovery_Policy_ID"],
        "Recovery_Policy": policy["Recovery_Policy"],
        "Policy_Type": policy["Policy_Type"],
        "Calls": int(len(result)),
        "Vessels": int(result["IMO_Normalised"].nunique()),
        "Shocked_Transition_Count": int((result["Transit_Elapsed_Time_Shock_Hours"] > 0).sum()),
        "Affected_Vessel_Count": affected_vessels,
        "Total_Recovery_Advance_Hours": float(result["Recovery_Advance_Hours"].sum()),
        "Total_Accumulated_Arrival_Delay_Hours": float(result["Simulated_Arrival_Delay_Hours"].sum()),
        "Total_Accumulated_Departure_Delay_Hours": total_delay,
        "Mean_Call_Departure_Delay_Hours": float(result["Simulated_Departure_Delay_Hours"].mean()),
        "P90_Call_Departure_Delay_Hours": float(result["Simulated_Departure_Delay_Hours"].quantile(0.90)),
        "Maximum_Call_Departure_Delay_Hours": float(result["Simulated_Departure_Delay_Hours"].max()),
        "Maximum_Final_Vessel_Departure_Delay_Hours": float(vessel["Maximum_Final_Departure_Delay_Hours"].max()),
        "Mean_Final_Vessel_Departure_Delay_Hours": float(vessel["Maximum_Final_Departure_Delay_Hours"].mean()),
        "Maximum_Accumulated_Departure_Delay_Per_Vessel_Hours": float(vessel["Maximum_Accumulated_Departure_Delay_Hours"].max()),
        "Total_Vessel_Accumulated_Departure_Delay_Hours": float(vessel["Accumulated_Departure_Delay_Hours"].sum()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.expanduser().resolve()
    tables = root / TABLE_DIR
    reports = root / REPORT_DIR
    reports.mkdir(parents=True, exist_ok=True)

    source_path = tables / INPUT_FILE
    if not source_path.exists():
        raise FileNotFoundError(f"Missing Script 75 call-level output: {source_path}")

    source = pd.read_csv(source_path, low_memory=False)
    required = [
        "Scenario_ID", "Scenario_Type", "Affected_Transition_Share_Design",
        "Shock_Magnitude_Design_Hours", "Simulation_Record_ID", "IMO_Normalised",
        "UNLOCODE_Normalised", "Vessel_Call_Sequence_Number", "Transition_Type",
        "Transit_Elapsed_Time_Shock_Hours", "Actual_Arrival_UTC",
        "Actual_Departure_UTC", "Simulated_Arrival_Delay_Hours",
        "Simulated_Departure_Delay_Hours",
    ]
    require_columns(source, required, "Script 75 call-level disruption output")

    checks: list[dict[str, Any]] = []
    scenario_ids = sorted(source["Scenario_ID"].dropna().unique().tolist())
    call_counts = source.groupby("Scenario_ID")["Simulation_Record_ID"].nunique()
    vessel_counts = source.groupby("Scenario_ID")["IMO_Normalised"].nunique()
    duplicate_call_rows = int(source.duplicated(["Scenario_ID", "Simulation_Record_ID"]).sum())

    add_check(checks, "SOURCE_SCENARIO_COUNT",
              "Script 75 contains the expected 17 scenarios",
              len(scenario_ids) == EXPECTED_SCENARIOS, len(scenario_ids), EXPECTED_SCENARIOS)
    add_check(checks, "SOURCE_CALL_COUNTS",
              "Every source scenario contains 604 unique calls",
              bool((call_counts == EXPECTED_CALLS).all()),
              ";".join(map(str, call_counts.tolist())), EXPECTED_CALLS)
    add_check(checks, "SOURCE_VESSEL_COUNTS",
              "Every source scenario contains 155 unique vessels",
              bool((vessel_counts == EXPECTED_VESSELS).all()),
              ";".join(map(str, vessel_counts.tolist())), EXPECTED_VESSELS)
    add_check(checks, "SOURCE_UNIQUE_SCENARIO_CALL_KEYS",
              "Scenario/call keys are unique",
              duplicate_call_rows == 0, duplicate_call_rows, 0)

    # Validate that Script75's zero-recovery baseline is internally identical.
    base = source.loc[source["Scenario_ID"] == "S75-BASE"].copy()
    baseline_delay_nonzero = int((
        (base["Simulated_Arrival_Delay_Hours"].abs() > TOL)
        | (base["Simulated_Departure_Delay_Hours"].abs() > TOL)
        | (base["Transit_Elapsed_Time_Shock_Hours"].abs() > TOL)
    ).sum())
    add_check(checks, "SCRIPT75_BASELINE_ZERO",
              "Script 75 baseline has zero shock and zero delay",
              baseline_delay_nonzero == 0, baseline_delay_nonzero, 0)

    all_calls: list[pd.DataFrame] = []
    all_vessels: list[pd.DataFrame] = []
    summaries: list[dict[str, Any]] = []
    policy_register = pd.DataFrame(POLICIES)

    scenario_meta = source.groupby("Scenario_ID", sort=False).agg(
        Scenario_Type=("Scenario_Type", "first"),
        Affected_Transition_Share=("Affected_Transition_Share_Design", "first"),
        Shock_Magnitude_Hours=("Shock_Magnitude_Design_Hours", "first"),
    ).reset_index()

    for scenario in scenario_meta.to_dict("records"):
        sid = scenario["Scenario_ID"]
        scenario_source = source.loc[source["Scenario_ID"] == sid].copy()
        scenario_source = scenario_source.sort_values(
            ["IMO_Normalised", "Vessel_Call_Sequence_Number", "Simulation_Record_ID"],
            kind="mergesort"
        )

        for policy in POLICIES:
            result = apply_recovery_policy(scenario_source, policy)
            result["Scenario_Type"] = scenario["Scenario_Type"]
            result["Affected_Transition_Share_Design"] = scenario["Affected_Transition_Share"]
            result["Shock_Magnitude_Design_Hours"] = scenario["Shock_Magnitude_Hours"]

            vessel = result.groupby("IMO_Normalised", sort=False).agg(
                Call_Count=("Simulation_Record_ID", "size"),
                Accumulated_Arrival_Delay_Hours=("Simulated_Arrival_Delay_Hours", "sum"),
                Accumulated_Departure_Delay_Hours=("Simulated_Departure_Delay_Hours", "sum"),
                Maximum_Arrival_Delay_Hours=("Simulated_Arrival_Delay_Hours", "max"),
                Maximum_Departure_Delay_Hours=("Simulated_Departure_Delay_Hours", "max"),
                Final_Departure_Delay_Hours=("Simulated_Departure_Delay_Hours", "last"),
            ).reset_index()
            vessel["Scenario_ID"] = sid
            vessel["Scenario_Type"] = scenario["Scenario_Type"]
            vessel["Recovery_Policy_ID"] = policy["Recovery_Policy_ID"]
            vessel["Recovery_Policy"] = policy["Recovery_Policy"]
            vessel["Affected_Vessel"] = vessel["IMO_Normalised"].isin(
                result.loc[result["Transit_Elapsed_Time_Shock_Hours"] > 0, "IMO_Normalised"].unique()
            )
            all_vessels.append(vessel)

            keep = [
                "Scenario_ID", "Scenario_Type", "Affected_Transition_Share_Design",
                "Shock_Magnitude_Design_Hours", "Recovery_Policy_ID", "Recovery_Policy",
                "Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised",
                "Vessel_Call_Sequence_Number", "Previous_Simulation_Record_ID",
                "Previous_Port", "Transition_Type", "Observed_Inter_Call_Elapsed_Hours",
                "Affected_Transition", "Transit_Elapsed_Time_Shock_Hours",
                "Port_Call_Duration_Shock_Hours", "Actual_Arrival_UTC",
                "Actual_Departure_UTC", "Delay_Before_Recovery_Hours",
                "Recovery_Advance_Hours", "Simulated_Arrival_Delay_Hours",
                "Simulated_Departure_Delay_Hours", "Simulated_Arrival_UTC",
                "Simulated_Departure_UTC",
            ]
            # Older Script75 variants may not carry Affected_Transition.
            if "Affected_Transition" not in result.columns:
                result["Affected_Transition"] = result["Transit_Elapsed_Time_Shock_Hours"] > 0
            if "Port_Call_Duration_Shock_Hours" not in result.columns:
                result["Port_Call_Duration_Shock_Hours"] = 0.0
            all_calls.append(result[keep].copy())
            summaries.append(summarize_policy(result, scenario, policy))

    calls_out = pd.concat(all_calls, ignore_index=True)
    vessels_out = pd.concat(all_vessels, ignore_index=True)
    summary = pd.DataFrame(summaries)

    # Calculate policy savings against the no-recovery policy for the same
    # disruption scenario. Savings are descriptive, not economic benefits.
    no_recovery = summary.loc[
        summary["Recovery_Policy_ID"] == "R76-00-NONE",
        ["Scenario_ID", "Total_Accumulated_Departure_Delay_Hours",
         "Maximum_Final_Vessel_Departure_Delay_Hours"]
    ].rename(columns={
        "Total_Accumulated_Departure_Delay_Hours": "No_Recovery_Total_Accumulated_Delay_Hours",
        "Maximum_Final_Vessel_Departure_Delay_Hours": "No_Recovery_Max_Final_Vessel_Delay_Hours",
    })
    summary = summary.merge(no_recovery, on="Scenario_ID", how="left", validate="many_to_one")
    summary["Accumulated_Delay_Reduction_Hours"] = (
        summary["No_Recovery_Total_Accumulated_Delay_Hours"]
        - summary["Total_Accumulated_Departure_Delay_Hours"]
    )
    summary["Accumulated_Delay_Reduction_Percent"] = np.where(
        summary["No_Recovery_Total_Accumulated_Delay_Hours"] > TOL,
        100.0 * summary["Accumulated_Delay_Reduction_Hours"]
        / summary["No_Recovery_Total_Accumulated_Delay_Hours"],
        0.0,
    )
    summary["Maximum_Final_Vessel_Delay_Reduction_Hours"] = (
        summary["No_Recovery_Max_Final_Vessel_Delay_Hours"]
        - summary["Maximum_Final_Vessel_Departure_Delay_Hours"]
    )

    # Validation: recurrence, non-negativity, recovery caps, zero-shock baseline,
    # and policy dominance (larger recovery allowance cannot increase delay).
    recurrence_failures = 0
    for _, grp in calls_out.groupby(["Scenario_ID", "Recovery_Policy_ID", "IMO_Normalised"], sort=False):
        grp = grp.sort_values("Vessel_Call_Sequence_Number", kind="mergesort")
        prior = 0.0
        for row in grp.itertuples(index=False):
            expected_before = prior + float(row.Transit_Elapsed_Time_Shock_Hours)
            if abs(expected_before - float(row.Delay_Before_Recovery_Hours)) > TOL:
                recurrence_failures += 1
            expected_arrival = max(
                0.0, expected_before - float(row.Recovery_Advance_Hours)
            )
            if abs(expected_arrival - float(row.Simulated_Arrival_Delay_Hours)) > TOL:
                recurrence_failures += 1
            if abs(expected_arrival - float(row.Simulated_Departure_Delay_Hours)) > TOL:
                recurrence_failures += 1
            prior = expected_arrival

    negative_delays = int((
        (calls_out["Simulated_Arrival_Delay_Hours"] < -TOL)
        | (calls_out["Simulated_Departure_Delay_Hours"] < -TOL)
        | (calls_out["Recovery_Advance_Hours"] < -TOL)
    ).sum())
    recovery_over_pre = int((
        calls_out["Recovery_Advance_Hours"] - calls_out["Delay_Before_Recovery_Hours"] > TOL
    ).sum())
    first_call_recovery = int((
        (calls_out["Transition_Type"] == "FIRST_CALL")
        & (calls_out["Recovery_Advance_Hours"].abs() > TOL)
    ).sum())
    no_recovery_mismatch = int((
        calls_out.loc[calls_out["Recovery_Policy_ID"] == "R76-00-NONE",
                      "Recovery_Advance_Hours"].abs() > TOL
    ).sum())

    add_check(checks, "RECURRENCE_RECONCILIATION",
              "All call-level delays reconcile to prior delay + shock - bounded recovery",
              recurrence_failures == 0, recurrence_failures, 0)
    add_check(checks, "NONNEGATIVE_DELAY_AND_RECOVERY",
              "No negative delay or recovery amount",
              negative_delays == 0, negative_delays, 0)
    add_check(checks, "RECOVERY_WITHIN_AVAILABLE_DELAY",
              "Recovery never exceeds delay available before recovery",
              recovery_over_pre == 0, recovery_over_pre, 0)
    add_check(checks, "NO_FIRST_CALL_RECOVERY",
              "No recovery is applied before a vessel's first call",
              first_call_recovery == 0, first_call_recovery, 0)
    add_check(checks, "NO_RECOVERY_POLICY_IDENTITY",
              "No-recovery policy applies zero recovery on every call",
              no_recovery_mismatch == 0, no_recovery_mismatch, 0)

    expected_call_rows = EXPECTED_CALLS * EXPECTED_SCENARIOS * len(POLICIES)
    expected_vessel_rows = EXPECTED_VESSELS * EXPECTED_SCENARIOS * len(POLICIES)
    add_check(checks, "OUTPUT_CALL_ROW_COUNT",
              "Every source call is represented under every scenario and policy",
              len(calls_out) == expected_call_rows, len(calls_out), expected_call_rows)
    add_check(checks, "OUTPUT_VESSEL_ROW_COUNT",
              "Every source vessel is represented under every scenario and policy",
              len(vessels_out) == expected_vessel_rows, len(vessels_out), expected_vessel_rows)
    add_check(checks, "SUMMARY_ROW_COUNT",
              "Every scenario-policy combination has one summary row",
              len(summary) == EXPECTED_SCENARIOS * len(POLICIES),
              len(summary), EXPECTED_SCENARIOS * len(POLICIES))

    # The no-recovery policy must reproduce Script75 exactly for every call.
    no_rec_calls = calls_out.loc[calls_out["Recovery_Policy_ID"] == "R76-00-NONE"]
    source_key = source[[
        "Scenario_ID", "Simulation_Record_ID", "Simulated_Arrival_Delay_Hours",
        "Simulated_Departure_Delay_Hours"
    ]].rename(columns={
        "Simulated_Arrival_Delay_Hours": "Source_Arrival_Delay_Hours",
        "Simulated_Departure_Delay_Hours": "Source_Departure_Delay_Hours",
    })
    nr_compare = no_rec_calls.merge(
        source_key, on=["Scenario_ID", "Simulation_Record_ID"],
        how="outer", validate="one_to_one", indicator=True
    )
    no_rec_mismatches = int((
        (nr_compare["_merge"] != "both")
        | ((nr_compare["Simulated_Arrival_Delay_Hours"] - nr_compare["Source_Arrival_Delay_Hours"]).abs() > TOL)
        | ((nr_compare["Simulated_Departure_Delay_Hours"] - nr_compare["Source_Departure_Delay_Hours"]).abs() > TOL)
    ).sum())
    add_check(checks, "NO_RECOVERY_SCRIPT75_REPRODUCTION",
              "No-recovery policy exactly reproduces Script75 call-level delays",
              no_rec_mismatches == 0, no_rec_mismatches, 0)

    # Test only policy dominance relationships that hold for every possible
    # delay amount. Fixed-6h and proportional-50%-capped-at-12h are deliberately
    # treated as incomparable: either can provide more recovery at different
    # delay levels.
    dominance_pairs = [
        ("R76-01-FIXED-6H", "R76-00-NONE"),
        ("R76-02-FIXED-12H", "R76-00-NONE"),
        ("R76-03-PROP-25-CAP6", "R76-00-NONE"),
        ("R76-04-PROP-50-CAP12", "R76-00-NONE"),
        ("R76-01-FIXED-6H", "R76-03-PROP-25-CAP6"),
        ("R76-02-FIXED-12H", "R76-01-FIXED-6H"),
        ("R76-02-FIXED-12H", "R76-03-PROP-25-CAP6"),
        ("R76-02-FIXED-12H", "R76-04-PROP-50-CAP12"),
        ("R76-04-PROP-50-CAP12", "R76-03-PROP-25-CAP6"),
    ]
    delay_pivot = calls_out.pivot_table(
        index=["Scenario_ID", "Simulation_Record_ID"],
        columns="Recovery_Policy_ID",
        values="Simulated_Departure_Delay_Hours",
        aggfunc="first",
    )
    policy_dominance_rows = []
    for stronger_policy, weaker_policy in dominance_pairs:
        difference = (
            delay_pivot[stronger_policy] - delay_pivot[weaker_policy]
        )
        failures = int((difference > TOL).sum())
        policy_dominance_rows.append({
            "Stronger_Recovery_Policy_ID": stronger_policy,
            "Weaker_Recovery_Policy_ID": weaker_policy,
            "Compared_Scenario_Call_Pairs": int(len(difference)),
            "Monotonicity_Failures": failures,
            "Passed": failures == 0,
            "Interpretation": "Stronger policy must not produce greater call-level delay",
        })
    policy_monotonicity = pd.DataFrame(policy_dominance_rows)
    policy_monotonicity_failures = int((~policy_monotonicity["Passed"]).sum())
    add_check(checks, "POLICY_DOMINANCE_MONOTONICITY",
              "All mathematically comparable recovery-policy pairs obey call-level delay dominance",
              policy_monotonicity_failures == 0,
              policy_monotonicity_failures, 0)

    # Recovery policy register and summary include all assumptions.
    factor_rows = []
    for scenario in scenario_meta.to_dict("records"):
        for policy in POLICIES:
            factor_rows.append({**scenario, **policy})
    factor_register = pd.DataFrame(factor_rows)

    checks_df = pd.DataFrame(checks)
    checks_df["Overall_Status"] = np.where(checks_df["Passed"], "PASS", "FAIL")
    failed = checks_df.loc[~checks_df["Passed"]]

    outputs = {
        "76_recovery_policy_register.csv": policy_register,
        "76_scenario_policy_factor_register.csv": factor_register,
        "76_call_level_recovery_results.csv": calls_out,
        "76_vessel_level_recovery_results.csv": vessels_out,
        "76_scenario_recovery_comparison_summary.csv": summary,
        "76_policy_monotonicity_checks.csv": policy_monotonicity,
        "76_validation_checks.csv": checks_df,
    }
    for filename, frame in outputs.items():
        frame.to_csv(tables / filename, index=False)

    report_lines = [
        "SCRIPT 76 — CONTROLLED SCHEDULE-RECOVERY POLICY EXPERIMENT",
        "=" * 76,
        f"Project root: {root}",
        f"Source: outputs/tables/{INPUT_FILE}",
        f"Source scenarios: {len(scenario_ids)}",
        f"Recovery policies: {len(POLICIES)}",
        f"Scenario-policy combinations: {len(factor_register)}",
        f"Call-level recovery records: {len(calls_out)}",
        f"Vessel-level recovery records: {len(vessels_out)}",
        "",
        "RECOVERY POLICY DESIGN",
        "- No recovery.",
        "- Fixed recovery credit of up to 6 hours per subsequent vessel sequence link.",
        "- Fixed recovery credit of up to 12 hours per subsequent vessel sequence link.",
        "- Proportional recovery of 25% of delay available after the current shock, capped at 6 hours per link.",
        "- Proportional recovery of 50% of delay available after the current shock, capped at 12 hours per link.",
        "- Recovery is applied only after the first call, at each subsequent sequence link, including same-port links.",
        "- Recovery cannot exceed delay available before recovery and cannot create negative delay.",
        "- Fixed-6h and proportional-50%-capped-at-12h policies are not globally ranked against each other.",
        "",
        "CRITICAL INTERPRETATION",
        "- Recovery credits are hypothetical schedule-recovery allowances, not measured operational capabilities.",
        "- The model does not identify whether recovery comes from sailing speed, port operations, schedule buffers, or other mechanisms.",
        "- No fuel, emissions, safety, cost, capacity, berth, or operational feasibility model is included.",
        "- The source disruption shocks are hypothetical additional observed inter-port elapsed time, not pure sailing-time shocks.",
        "- The data do not establish physical routes or actual Strait of Hormuz transit.",
        "",
        f"Validation checks passed: {int(checks_df['Passed'].sum())}/{len(checks_df)}",
        f"Validation checks failed: {len(failed)}",
        "",
        "FAILED CHECKS",
    ]
    if failed.empty:
        report_lines.append("None.")
    else:
        report_lines.extend(
            f"- {r.Check_ID}: observed={r.Observed}; expected={r.Expected}"
            for r in failed.itertuples(index=False)
        )
    report_lines.extend(["", "OUTPUT FILES"])
    report_lines.extend(f"- outputs/tables/{name}" for name in outputs)
    report_lines.append("- outputs/reports/76_controlled_schedule_recovery_policy_experiment_report.txt")

    report_path = reports / "76_controlled_schedule_recovery_policy_experiment_report.txt"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print("\n".join(report_lines))
    if not failed.empty:
        print("\nFAILED: inspect Script 76 outputs before interpreting policies.", file=sys.stderr)
        return 2
    print("\nSUCCESS: Script 76 recovery-policy experiment and validation checks completed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(1)
