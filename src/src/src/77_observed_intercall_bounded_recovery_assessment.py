#!/usr/bin/env python3
# Script 77 — Observed Inter-Call Elapsed-Time-Bounded Recovery Assessment
#
# Run from project root:
#   python src/77_observed_intercall_bounded_recovery_assessment.py
#
# This script takes Script 76's requested abstract recovery credits and caps
# them by the observed elapsed interval from the previous call's departure
# to the current call's arrival.
#
# IMPORTANT: this observed interval is NOT established schedule slack. It may
# include sailing, anchorage, waiting, operational time, and data gaps. The
# cap is a conservative mathematical sensitivity bound, not proof of physical
# or operational recovery feasibility. No AIS-confirmed Hormuz transit,
# physical route, berth capacity, fuel, emissions, or safety inference.

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
INPUT_FILE = "76_call_level_recovery_results.csv"
TOL = 1e-8
EXPECTED_SCENARIOS = 17
EXPECTED_POLICIES = 5
EXPECTED_CALLS = 604
EXPECTED_VESSELS = 155

POLICY_ORDER = [
    "R76-00-NONE",
    "R76-01-FIXED-6H",
    "R76-02-FIXED-12H",
    "R76-03-PROP-25-CAP6",
    "R76-04-PROP-50-CAP12",
]


def require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"Script 76 input is missing required columns: {missing}")


def add_check(rows: list[dict[str, Any]], check_id: str, description: str,
              passed: bool, observed: Any, expected: Any) -> None:
    rows.append({
        "Check_ID": check_id,
        "Description": description,
        "Passed": bool(passed),
        "Observed": str(observed),
        "Expected": str(expected),
        "Overall_Status": "PASS" if passed else "FAIL",
    })


def calculate_bounded_recovery(group: pd.DataFrame) -> pd.DataFrame:
    """Recalculate recovery using min(Script76 request, observed elapsed cap)."""
    g = group.sort_values(
        ["IMO_Normalised", "Vessel_Call_Sequence_Number", "Simulation_Record_ID"],
        kind="mergesort"
    ).copy()

    bounded_recovery = []
    available_interval = []
    requested_recovery = []
    delay_before = []
    arrival_delay = []
    previous_departure_delay: dict[str, float] = {}

    for row in g[[
        "IMO_Normalised", "Transition_Type", "Transit_Elapsed_Time_Shock_Hours",
        "Recovery_Advance_Hours", "Observed_Inter_Call_Elapsed_Hours"
    ]].itertuples(index=False):
        vessel_id = str(row.IMO_Normalised)
        prior_delay = previous_departure_delay.get(vessel_id, 0.0)
        transition = str(row.Transition_Type)
        shock = float(row.Transit_Elapsed_Time_Shock_Hours)
        requested = float(row.Recovery_Advance_Hours)

        if transition == "FIRST_CALL":
            interval_cap = 0.0
            recovery = 0.0
        else:
            raw_interval = row.Observed_Inter_Call_Elapsed_Hours
            interval_cap = 0.0 if pd.isna(raw_interval) else max(0.0, float(raw_interval))
            recovery = min(requested, interval_cap, prior_delay + shock)

        before = prior_delay + shock
        after = max(0.0, before - recovery)

        available_interval.append(interval_cap)
        requested_recovery.append(requested)
        bounded_recovery.append(recovery)
        delay_before.append(before)
        arrival_delay.append(after)
        previous_departure_delay[vessel_id] = after

    g["Observed_Inter_Call_Elapsed_Cap_Hours"] = available_interval
    g["Script76_Requested_Recovery_Hours"] = requested_recovery
    g["Script77_Bounded_Recovery_Hours"] = bounded_recovery
    g["Script77_Recovery_Capped_Hours"] = (
        g["Script76_Requested_Recovery_Hours"] - g["Script77_Bounded_Recovery_Hours"]
    ).clip(lower=0)
    g["Script77_Delay_Before_Recovery_Hours"] = delay_before
    g["Script77_Arrival_Delay_Hours"] = arrival_delay
    g["Script77_Departure_Delay_Hours"] = arrival_delay

    actual_arrival = pd.to_datetime(g["Actual_Arrival_UTC"], utc=True)
    actual_departure = pd.to_datetime(g["Actual_Departure_UTC"], utc=True)
    g["Script77_Simulated_Arrival_UTC"] = actual_arrival + pd.to_timedelta(arrival_delay, unit="h")
    g["Script77_Simulated_Departure_UTC"] = actual_departure + pd.to_timedelta(arrival_delay, unit="h")
    return g

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.expanduser().resolve()
    tables = root / TABLE_DIR
    reports = root / REPORT_DIR
    reports.mkdir(parents=True, exist_ok=True)

    input_path = tables / INPUT_FILE
    if not input_path.exists():
        raise FileNotFoundError(f"Missing Script76 input: {input_path}")

    df = pd.read_csv(input_path, low_memory=False)
    required = [
        "Scenario_ID", "Scenario_Type", "Affected_Transition_Share_Design",
        "Shock_Magnitude_Design_Hours", "Recovery_Policy_ID", "Recovery_Policy",
        "Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised",
        "Vessel_Call_Sequence_Number", "Previous_Simulation_Record_ID",
        "Previous_Port", "Transition_Type", "Observed_Inter_Call_Elapsed_Hours",
        "Transit_Elapsed_Time_Shock_Hours", "Actual_Arrival_UTC",
        "Actual_Departure_UTC", "Delay_Before_Recovery_Hours",
        "Recovery_Advance_Hours", "Simulated_Arrival_Delay_Hours",
        "Simulated_Departure_Delay_Hours",
    ]
    require_columns(df, required)

    checks: list[dict[str, Any]] = []
    scenarios = df["Scenario_ID"].nunique()
    policies = df["Recovery_Policy_ID"].nunique()
    duplicate_keys = int(df.duplicated(
        ["Scenario_ID", "Recovery_Policy_ID", "Simulation_Record_ID"]
    ).sum())
    scenario_counts = df.groupby(["Scenario_ID", "Recovery_Policy_ID"]).agg(
        calls=("Simulation_Record_ID", "nunique"),
        vessels=("IMO_Normalised", "nunique"),
    )

    add_check(checks, "SOURCE_SCENARIOS", "Expected 17 disruption scenarios",
              scenarios == EXPECTED_SCENARIOS, scenarios, EXPECTED_SCENARIOS)
    add_check(checks, "SOURCE_POLICIES", "Expected five recovery policies",
              policies == EXPECTED_POLICIES, policies, EXPECTED_POLICIES)
    add_check(checks, "SOURCE_CALLS_AND_VESSELS",
              "Each scenario-policy group contains 604 calls and 155 vessels",
              bool(((scenario_counts.calls == EXPECTED_CALLS)
                    & (scenario_counts.vessels == EXPECTED_VESSELS)).all()),
              f"calls={scenario_counts.calls.min()}..{scenario_counts.calls.max()}; "
              f"vessels={scenario_counts.vessels.min()}..{scenario_counts.vessels.max()}",
              "604 calls; 155 vessels per group")
    add_check(checks, "UNIQUE_SOURCE_KEYS", "Scenario-policy-call keys are unique",
              duplicate_keys == 0, duplicate_keys, 0)

    results = []
    for _, group in df.groupby(["Scenario_ID", "Recovery_Policy_ID"], sort=False):
        results.append(calculate_bounded_recovery(group))
    out = pd.concat(results, ignore_index=True)

    # Independent recurrence check.
    recurrence_failures = 0
    for _, group in out.groupby(
        ["Scenario_ID", "Recovery_Policy_ID", "IMO_Normalised"], sort=False
    ):
        group = group.sort_values("Vessel_Call_Sequence_Number", kind="mergesort")
        previous = 0.0
        for row in group.itertuples(index=False):
            before = previous + float(row.Transit_Elapsed_Time_Shock_Hours)
            if abs(before - float(row.Script77_Delay_Before_Recovery_Hours)) > TOL:
                recurrence_failures += 1
            after = max(0.0, before - float(row.Script77_Bounded_Recovery_Hours))
            if abs(after - float(row.Script77_Arrival_Delay_Hours)) > TOL:
                recurrence_failures += 1
            previous = after

    cap_violations = int((
        out["Script77_Bounded_Recovery_Hours"]
        - out["Observed_Inter_Call_Elapsed_Cap_Hours"] > TOL
    ).sum())
    available_delay_violations = int((
        out["Script77_Bounded_Recovery_Hours"]
        - out["Script77_Delay_Before_Recovery_Hours"] > TOL
    ).sum())
    negative_values = int((
        (out["Script77_Bounded_Recovery_Hours"] < -TOL)
        | (out["Script77_Arrival_Delay_Hours"] < -TOL)
        | (out["Script77_Departure_Delay_Hours"] < -TOL)
    ).sum())
    first_call_recovery = int((
        (out["Transition_Type"] == "FIRST_CALL")
        & (out["Script77_Bounded_Recovery_Hours"].abs() > TOL)
    ).sum())
    no_recovery = out[out["Recovery_Policy_ID"] == "R76-00-NONE"]
    no_recovery_nonzero = int((
        no_recovery["Script77_Bounded_Recovery_Hours"].abs() > TOL
    ).sum())

    add_check(checks, "RECURRENCE", "Delay recurrence reconciles for every vessel call",
              recurrence_failures == 0, recurrence_failures, 0)
    add_check(checks, "ELAPSED_INTERVAL_CAP", "Recovery never exceeds observed inter-call elapsed cap",
              cap_violations == 0, cap_violations, 0)
    add_check(checks, "AVAILABLE_DELAY_CAP", "Recovery never exceeds delay available before recovery",
              available_delay_violations == 0, available_delay_violations, 0)
    add_check(checks, "NONNEGATIVE", "Recovery and resulting delays are non-negative",
              negative_values == 0, negative_values, 0)
    add_check(checks, "FIRST_CALL", "No recovery is applied to a vessel's first call",
              first_call_recovery == 0, first_call_recovery, 0)
    add_check(checks, "NO_RECOVERY_IDENTITY", "No-recovery policy remains unchanged",
              no_recovery_nonzero == 0, no_recovery_nonzero, 0)

    # Script77 must not produce greater delay than Script76 for the same
    # scenario-policy-call because the only change is an additional recovery cap.
    comparison = out.merge(
        df[["Scenario_ID", "Recovery_Policy_ID", "Simulation_Record_ID",
            "Simulated_Arrival_Delay_Hours", "Simulated_Departure_Delay_Hours"]].rename(
                columns={
                    "Simulated_Arrival_Delay_Hours": "Script76_Arrival_Delay_Hours",
                    "Simulated_Departure_Delay_Hours": "Script76_Departure_Delay_Hours",
                }
            ),
        on=["Scenario_ID", "Recovery_Policy_ID", "Simulation_Record_ID"],
        how="outer", validate="one_to_one", indicator=True,
    )
    key_mismatch = int((comparison["_merge"] != "both").sum())
    delay_decreases = int((
        comparison["Script77_Departure_Delay_Hours"]
        - comparison["Script76_Departure_Delay_Hours"] < -TOL
    ).sum())
    add_check(checks, "SOURCE_KEY_RECONCILIATION", "Script77 records reconcile one-to-one with Script76",
              key_mismatch == 0, key_mismatch, 0)
    add_check(checks, "NO_DELAY_DECREASE_VS_76",
              "Restricting recovery cannot produce less delay than Script76",
              delay_decreases == 0, delay_decreases, 0)

    # Aggregation by scenario and policy.
    vessel = out.groupby(
        ["Scenario_ID", "Recovery_Policy_ID", "IMO_Normalised"], sort=False
    ).agg(
        Call_Count=("Simulation_Record_ID", "size"),
        Accumulated_Arrival_Delay_Hours=("Script77_Arrival_Delay_Hours", "sum"),
        Accumulated_Departure_Delay_Hours=("Script77_Departure_Delay_Hours", "sum"),
        Final_Departure_Delay_Hours=("Script77_Departure_Delay_Hours", "last"),
        Maximum_Departure_Delay_Hours=("Script77_Departure_Delay_Hours", "max"),
    ).reset_index()

    summary = out.groupby(
        ["Scenario_ID", "Scenario_Type", "Affected_Transition_Share_Design",
         "Shock_Magnitude_Design_Hours", "Recovery_Policy_ID", "Recovery_Policy"],
        sort=False,
    ).agg(
        Calls=("Simulation_Record_ID", "nunique"),
        Vessels=("IMO_Normalised", "nunique"),
        Shocked_Transitions=("Transit_Elapsed_Time_Shock_Hours",
                             lambda s: int((s > 0).sum())),
        Total_Requested_Recovery_Hours=("Script76_Requested_Recovery_Hours", "sum"),
        Total_Bounded_Recovery_Hours=("Script77_Bounded_Recovery_Hours", "sum"),
        Total_Recovery_Capped_Hours=("Script77_Recovery_Capped_Hours", "sum"),
        Total_Accumulated_Arrival_Delay_Hours=("Script77_Arrival_Delay_Hours", "sum"),
        Total_Accumulated_Departure_Delay_Hours=("Script77_Departure_Delay_Hours", "sum"),
        Mean_Call_Departure_Delay_Hours=("Script77_Departure_Delay_Hours", "mean"),
        P90_Call_Departure_Delay_Hours=("Script77_Departure_Delay_Hours",
                                        lambda s: s.quantile(0.90)),
        Maximum_Call_Departure_Delay_Hours=("Script77_Departure_Delay_Hours", "max"),
    ).reset_index()

    vessel_summary = vessel.groupby(
        ["Scenario_ID", "Recovery_Policy_ID"], sort=False
    ).agg(
        Total_Vessel_Accumulated_Departure_Delay_Hours=(
            "Accumulated_Departure_Delay_Hours", "sum"),
        Maximum_Final_Vessel_Departure_Delay_Hours=("Final_Departure_Delay_Hours", "max"),
        Mean_Final_Vessel_Departure_Delay_Hours=("Final_Departure_Delay_Hours", "mean"),
        Maximum_Accumulated_Departure_Delay_Per_Vessel_Hours=(
            "Accumulated_Departure_Delay_Hours", "max"),
    ).reset_index()
    summary = summary.merge(
        vessel_summary, on=["Scenario_ID", "Recovery_Policy_ID"],
        how="left", validate="one_to_one"
    )

    # Compare Script77 bounded outcome with Script76 requested-credit outcome.
    script76_summary = df.groupby(
        ["Scenario_ID", "Recovery_Policy_ID"], sort=False
    )["Simulated_Departure_Delay_Hours"].sum().rename(
        "Script76_Total_Accumulated_Departure_Delay_Hours"
    ).reset_index()
    summary = summary.merge(
        script76_summary, on=["Scenario_ID", "Recovery_Policy_ID"],
        how="left", validate="one_to_one"
    )
    summary["Accumulated_Delay_Increase_vs_Script76_Hours"] = (
        summary["Total_Accumulated_Departure_Delay_Hours"]
        - summary["Script76_Total_Accumulated_Departure_Delay_Hours"]
    )

    # Measure requested recovery credits that were constrained by the interval cap.
    requested_positive = out["Script76_Requested_Recovery_Hours"] > TOL
    capped_positive = out["Script77_Recovery_Capped_Hours"] > TOL
    requested_count = int(requested_positive.sum())
    capped_count = int(capped_positive.sum())
    capped_records = out.loc[capped_positive].copy()

    add_check(checks, "OUTPUT_CALL_ROWS", "Call-level output has 51,340 records",
              len(out) == EXPECTED_CALLS * EXPECTED_SCENARIOS * EXPECTED_POLICIES,
              len(out), EXPECTED_CALLS * EXPECTED_SCENARIOS * EXPECTED_POLICIES)
    add_check(checks, "OUTPUT_VESSEL_ROWS", "Vessel-level output has 13,175 records",
              len(vessel) == EXPECTED_VESSELS * EXPECTED_SCENARIOS * EXPECTED_POLICIES,
              len(vessel), EXPECTED_VESSELS * EXPECTED_SCENARIOS * EXPECTED_POLICIES)
    add_check(checks, "SUMMARY_ROWS", "Summary has 85 scenario-policy combinations",
              len(summary) == EXPECTED_SCENARIOS * EXPECTED_POLICIES,
              len(summary), EXPECTED_SCENARIOS * EXPECTED_POLICIES)

    # Policy comparison register; deliberately avoids a universal ranking.
    policy_comparison = summary[[
        "Scenario_ID", "Scenario_Type", "Affected_Transition_Share_Design",
        "Shock_Magnitude_Design_Hours", "Recovery_Policy_ID", "Recovery_Policy",
        "Total_Requested_Recovery_Hours", "Total_Bounded_Recovery_Hours",
        "Total_Recovery_Capped_Hours", "Total_Accumulated_Departure_Delay_Hours",
        "Maximum_Final_Vessel_Departure_Delay_Hours",
        "Maximum_Accumulated_Departure_Delay_Per_Vessel_Hours",
        "Script76_Total_Accumulated_Departure_Delay_Hours",
        "Accumulated_Delay_Increase_vs_Script76_Hours",
    ]].copy()

    validation = pd.DataFrame(checks)
    failed = validation.loc[~validation["Passed"]]

    out.to_csv(tables / "77_call_level_bounded_recovery_results.csv", index=False)
    vessel.to_csv(tables / "77_vessel_level_bounded_recovery_results.csv", index=False)
    summary.to_csv(tables / "77_scenario_bounded_recovery_summary.csv", index=False)
    policy_comparison.to_csv(tables / "77_recovery_policy_comparison.csv", index=False)
    capped_records.to_csv(tables / "77_recovery_cap_binding_records.csv", index=False)
    validation.to_csv(tables / "77_validation_checks.csv", index=False)

    report = [
        "SCRIPT 77 — OBSERVED INTER-CALL ELAPSED-TIME-BOUNDED RECOVERY ASSESSMENT",
        "=" * 82,
        f"Project root: {root}",
        f"Source: outputs/tables/{INPUT_FILE}",
        f"Scenarios: {scenarios}",
        f"Policies: {policies}",
        f"Scenario-policy combinations: {len(summary)}",
        f"Call-level records: {len(out)}",
        f"Vessel-level records: {len(vessel)}",
        "",
        "METHOD",
        "- Reuses Script76's requested recovery credits.",
        "- Caps recovery at the non-negative observed interval from previous departure to current arrival.",
        "- Also caps recovery at delay available before recovery.",
        "- No recovery is applied to a vessel's first call.",
        "- Delay is propagated through the ordered vessel sequence.",
        "",
        "CRITICAL INTERPRETATION",
        "- Observed inter-call elapsed time is NOT established schedule slack.",
        "- It may contain sailing, anchorage, waiting, operational time, and data gaps.",
        "- The cap is a mathematical upper-bound sensitivity test, not proof of physical recovery feasibility.",
        "- No route, AIS-confirmed Strait of Hormuz transit, berth capacity, safety, fuel, emissions, or cost is inferred.",
        "",
        f"Records with positive requested recovery: {requested_count}",
        f"Records where the elapsed-time cap binds: {capped_count}",
        f"Share of requested-positive records capped: "
        f"{(100*capped_count/requested_count if requested_count else 0):.2f}%",
        f"Total requested recovery: {out['Script76_Requested_Recovery_Hours'].sum():.6f} hours",
        f"Total bounded recovery: {out['Script77_Bounded_Recovery_Hours'].sum():.6f} hours",
        f"Total recovery constrained by cap: {out['Script77_Recovery_Capped_Hours'].sum():.6f} hours",
        "",
        f"Validation checks passed: {int(validation['Passed'].sum())}/{len(validation)}",
        f"Validation checks failed: {len(failed)}",
        "",
        "FAILED CHECKS",
    ]
    if failed.empty:
        report.append("None.")
    else:
        report.extend(
            f"- {r.Check_ID}: observed={r.Observed}; expected={r.Expected}"
            for r in failed.itertuples(index=False)
        )
    report.extend(["", "OUTPUT FILES"])
    report.extend([
        "- outputs/tables/77_call_level_bounded_recovery_results.csv",
        "- outputs/tables/77_vessel_level_bounded_recovery_results.csv",
        "- outputs/tables/77_scenario_bounded_recovery_summary.csv",
        "- outputs/tables/77_recovery_policy_comparison.csv",
        "- outputs/tables/77_recovery_cap_binding_records.csv",
        "- outputs/tables/77_validation_checks.csv",
        "- outputs/reports/77_observed_intercall_bounded_recovery_assessment_report.txt",
    ])
    report_path = reports / "77_observed_intercall_bounded_recovery_assessment_report.txt"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    if not failed.empty:
        print("\nFAILED: do not interpret Script77 results until corrected.", file=sys.stderr)
        return 2
    print("\nSUCCESS: Script77 bounded recovery assessment completed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(1)
