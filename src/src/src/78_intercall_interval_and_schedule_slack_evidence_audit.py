#!/usr/bin/env python3
"""
SCRIPT 78 — OBSERVED INTER-CALL INTERVAL AND SCHEDULE-SLACK EVIDENCE AUDIT

Run from project root:
    python src/78_intercall_interval_and_schedule_slack_evidence_audit.py

Input:
    outputs/tables/77_call_level_bounded_recovery_results.csv

This script extracts one canonical historical record per vessel call from
Script77's scenario/policy-expanded file, using S75-BASE + R76-00-NONE.
It classifies observed inter-call elapsed intervals descriptively. It does
NOT label any interval as verified schedule slack or operationally recoverable.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

INPUT = "77_call_level_bounded_recovery_results.csv"
TOL = 1e-8
EXPECTED_CALLS = 604
EXPECTED_VESSELS = 155
EXPECTED_LINKS = 449
EXPECTED_SAME_PORT = 178
EXPECTED_DISTINCT_PORT = 271

REQUIRED = [
    "Scenario_ID", "Recovery_Policy_ID", "Simulation_Record_ID",
    "IMO_Normalised", "UNLOCODE_Normalised", "Vessel_Call_Sequence_Number",
    "Previous_Simulation_Record_ID", "Previous_Port", "Transition_Type",
    "Observed_Inter_Call_Elapsed_Hours", "Actual_Arrival_UTC",
    "Actual_Departure_UTC",
]


def add_check(rows, check_id, description, passed, observed, expected):
    rows.append({
        "Check_ID": check_id,
        "Description": description,
        "Passed": bool(passed),
        "Observed": str(observed),
        "Expected": str(expected),
        "Status": "PASS" if passed else "FAIL",
    })


def safe_quantile(series, q):
    s = pd.to_numeric(series, errors="coerce").dropna()
    return float(s.quantile(q)) if len(s) else np.nan


def describe_intervals(df, group_cols):
    rows = []
    grouped = [((), df)] if not group_cols else df.groupby(group_cols, dropna=False, sort=True)
    for key, grp in grouped:
        if not isinstance(key, tuple):
            key = (key,)
        vals = pd.to_numeric(grp["Observed_Inter_Call_Elapsed_Hours"], errors="coerce").dropna()
        row = {c: v for c, v in zip(group_cols, key)}
        row.update({
            "Transition_Count": int(len(grp)),
            "Distinct_Vessel_Count": int(grp["IMO_Normalised"].nunique()),
            "Distinct_Port_Pair_Count": int(
                grp.loc[grp["Transition_Type"] == "DISTINCT_PORT_INTERPORT_TRANSITION",
                        ["Previous_Port", "UNLOCODE_Normalised"]]
                .drop_duplicates().shape[0]
            ),
            "Valid_Interval_Count": int(len(vals)),
            "Mean_Elapsed_Hours": float(vals.mean()) if len(vals) else np.nan,
            "Median_Elapsed_Hours": float(vals.median()) if len(vals) else np.nan,
            "P75_Elapsed_Hours": safe_quantile(vals, 0.75),
            "P90_Elapsed_Hours": safe_quantile(vals, 0.90),
            "P95_Elapsed_Hours": safe_quantile(vals, 0.95),
            "P99_Elapsed_Hours": safe_quantile(vals, 0.99),
            "Maximum_Elapsed_Hours": float(vals.max()) if len(vals) else np.nan,
            "Minimum_Elapsed_Hours": float(vals.min()) if len(vals) else np.nan,
        })
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.expanduser().resolve()
    table_dir = root / "outputs" / "tables"
    report_dir = root / "outputs" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    path = table_dir / INPUT
    if not path.exists():
        raise FileNotFoundError(f"Required Script77 output not found: {path}")

    expanded = pd.read_csv(path, low_memory=False)
    missing = [c for c in REQUIRED if c not in expanded.columns]
    if missing:
        raise ValueError(f"Input missing required columns: {missing}")

    # One canonical baseline/no-recovery row per historical call.
    canonical = expanded.loc[
        (expanded["Scenario_ID"] == "S75-BASE")
        & (expanded["Recovery_Policy_ID"] == "R76-00-NONE")
    ].copy()
    canonical = canonical.sort_values(
        ["IMO_Normalised", "Vessel_Call_Sequence_Number", "Simulation_Record_ID"],
        kind="mergesort"
    ).reset_index(drop=True)

    checks = []
    add_check(checks, "CANONICAL_ROW_COUNT", "Canonical baseline contains 604 calls",
              len(canonical) == EXPECTED_CALLS, len(canonical), EXPECTED_CALLS)
    add_check(checks, "UNIQUE_CALL_IDS", "Canonical call IDs are unique",
              canonical["Simulation_Record_ID"].nunique() == EXPECTED_CALLS,
              canonical["Simulation_Record_ID"].nunique(), EXPECTED_CALLS)
    add_check(checks, "UNIQUE_VESSELS", "Canonical vessel count is 155",
              canonical["IMO_Normalised"].nunique() == EXPECTED_VESSELS,
              canonical["IMO_Normalised"].nunique(), EXPECTED_VESSELS)

    # Check ordering and independently reconstruct elapsed time from timestamps.
    canonical["Actual_Arrival_UTC_Parsed"] = pd.to_datetime(
        canonical["Actual_Arrival_UTC"], utc=True, errors="coerce"
    )
    canonical["Actual_Departure_UTC_Parsed"] = pd.to_datetime(
        canonical["Actual_Departure_UTC"], utc=True, errors="coerce"
    )
    canonical["Previous_Departure_UTC"] = canonical.groupby(
        "IMO_Normalised", sort=False
    )["Actual_Departure_UTC_Parsed"].shift(1)
    canonical["Reconstructed_Inter_Call_Elapsed_Hours"] = (
        canonical["Actual_Arrival_UTC_Parsed"] - canonical["Previous_Departure_UTC"]
    ).dt.total_seconds() / 3600.0
    canonical["Elapsed_Time_Reconciliation_Difference_Hours"] = (
        canonical["Reconstructed_Inter_Call_Elapsed_Hours"]
        - pd.to_numeric(canonical["Observed_Inter_Call_Elapsed_Hours"], errors="coerce")
    )

    nonfirst = canonical["Transition_Type"].ne("FIRST_CALL")
    timestamp_missing = int((
        nonfirst & (
            canonical["Actual_Arrival_UTC_Parsed"].isna()
            | canonical["Previous_Departure_UTC"].isna()
        )
    ).sum())
    elapsed_mismatch = int((
        nonfirst
        & canonical["Elapsed_Time_Reconciliation_Difference_Hours"].abs().gt(0.02)
    ).sum())
    negative_elapsed = int((
        nonfirst
        & canonical["Reconstructed_Inter_Call_Elapsed_Hours"].lt(-TOL)
    ).sum())
    zero_elapsed = int((
        nonfirst
        & canonical["Reconstructed_Inter_Call_Elapsed_Hours"].abs().le(TOL)
    ).sum())

    add_check(checks, "TIMESTAMP_AVAILABILITY", "All non-first links have both required timestamps",
              timestamp_missing == 0, timestamp_missing, 0)
    add_check(checks, "ELAPSED_RECONCILIATION", "Reconstructed elapsed intervals match Script77 within 0.02h",
              elapsed_mismatch == 0, elapsed_mismatch, 0)
    add_check(checks, "NONNEGATIVE_ELAPSED", "No negative reconstructed inter-call intervals",
              negative_elapsed == 0, negative_elapsed, 0)

    first_count = int((canonical["Transition_Type"] == "FIRST_CALL").sum())
    same_count = int((canonical["Transition_Type"] == "SAME_PORT_SEQUENCE_LINK").sum())
    distinct_count = int((canonical["Transition_Type"] == "DISTINCT_PORT_INTERPORT_TRANSITION").sum())
    links = same_count + distinct_count
    add_check(checks, "SEQUENCE_LINK_COUNT", "There are 449 non-first vessel sequence links",
              links == EXPECTED_LINKS, links, EXPECTED_LINKS)
    add_check(checks, "SAME_PORT_LINK_COUNT", "Same-port sequence links reconcile to 178",
              same_count == EXPECTED_SAME_PORT, same_count, EXPECTED_SAME_PORT)
    add_check(checks, "DISTINCT_PORT_LINK_COUNT", "Distinct-port transitions reconcile to 271",
              distinct_count == EXPECTED_DISTINCT_PORT, distinct_count, EXPECTED_DISTINCT_PORT)
    add_check(checks, "FIRST_CALL_COUNT", "There is one first call per vessel",
              first_count == EXPECTED_VESSELS, first_count, EXPECTED_VESSELS)

    # Descriptive, distribution-derived outlier flags. These are not operational
    # thresholds, slack determinations, or exclusion rules.
    intervals = canonical.loc[nonfirst].copy()
    intervals["Observed_Inter_Call_Elapsed_Hours"] = pd.to_numeric(
        intervals["Observed_Inter_Call_Elapsed_Hours"], errors="coerce"
    )
    valid = intervals["Observed_Inter_Call_Elapsed_Hours"].notna()
    intervals["Interval_Validity"] = np.where(valid, "VALID_NUMERIC_INTERVAL", "MISSING_INTERVAL")

    q1 = safe_quantile(intervals.loc[valid, "Observed_Inter_Call_Elapsed_Hours"], 0.25)
    q3 = safe_quantile(intervals.loc[valid, "Observed_Inter_Call_Elapsed_Hours"], 0.75)
    iqr = q3 - q1 if pd.notna(q1) and pd.notna(q3) else np.nan
    upper_1_5 = q3 + 1.5 * iqr if pd.notna(iqr) else np.nan
    upper_3 = q3 + 3.0 * iqr if pd.notna(iqr) else np.nan
    p90 = safe_quantile(intervals.loc[valid, "Observed_Inter_Call_Elapsed_Hours"], 0.90)
    p95 = safe_quantile(intervals.loc[valid, "Observed_Inter_Call_Elapsed_Hours"], 0.95)
    p99 = safe_quantile(intervals.loc[valid, "Observed_Inter_Call_Elapsed_Hours"], 0.99)

    x = intervals["Observed_Inter_Call_Elapsed_Hours"]
    intervals["Above_P90_Descriptive_Flag"] = x.gt(p90)
    intervals["Above_P95_Descriptive_Flag"] = x.gt(p95)
    intervals["Above_P99_Descriptive_Flag"] = x.gt(p99)
    intervals["IQR_1_5_Descriptive_Outlier_Flag"] = x.gt(upper_1_5)
    intervals["IQR_3_Descriptive_Extreme_Flag"] = x.gt(upper_3)
    intervals["Long_Interval_Classification"] = np.select(
        [x.gt(upper_3), x.gt(upper_1_5), x.gt(p90)],
        ["EXTREME_IQR_FLAG", "UPPER_IQR_FLAG", "ABOVE_P90_ONLY"],
        default="NOT_FLAGGED_BY_SELECTED_RULES"
    )
    intervals["Schedule_Slack_Status"] = "NOT_ESTABLISHED_FROM_AVAILABLE_DATA"
    intervals["Operational_Recovery_Status"] = "NOT_ASSESSED"
    intervals["Interpretation_Note"] = (
        "Observed departure-to-next-arrival elapsed time; may include sailing, "
        "anchorage, waiting, operations and data gaps; not verified schedule slack."
    )

    # Same-port and distinct-port distributions, plus port-pair summaries.
    type_summary = describe_intervals(intervals, ["Transition_Type"])
    overall_summary = describe_intervals(intervals, [])
    pair_summary = describe_intervals(
        intervals.loc[intervals["Transition_Type"] == "DISTINCT_PORT_INTERPORT_TRANSITION"],
        ["Previous_Port", "UNLOCODE_Normalised"]
    )
    vessel_summary = describe_intervals(intervals, ["IMO_Normalised"])

    cap_summary = pd.DataFrame([{
        "Statistic": "Valid non-first intervals",
        "Value": int(valid.sum()),
        "Unit": "records",
        "Interpretation": "Observed elapsed intervals; not verified slack",
    }, {
        "Statistic": "Q1",
        "Value": q1,
        "Unit": "hours",
        "Interpretation": "Distribution descriptor only",
    }, {
        "Statistic": "Median",
        "Value": safe_quantile(x, 0.50),
        "Unit": "hours",
        "Interpretation": "Distribution descriptor only",
    }, {
        "Statistic": "Q3",
        "Value": q3,
        "Unit": "hours",
        "Interpretation": "Distribution descriptor only",
    }, {
        "Statistic": "P90",
        "Value": p90,
        "Unit": "hours",
        "Interpretation": "Distribution descriptor only",
    }, {
        "Statistic": "P95",
        "Value": p95,
        "Unit": "hours",
        "Interpretation": "Distribution descriptor only",
    }, {
        "Statistic": "P99",
        "Value": p99,
        "Unit": "hours",
        "Interpretation": "Distribution descriptor only",
    }, {
        "Statistic": "IQR upper fence (Q3 + 1.5 IQR)",
        "Value": upper_1_5,
        "Unit": "hours",
        "Interpretation": "Statistical flag only; not a removal threshold",
    }, {
        "Statistic": "IQR extreme fence (Q3 + 3 IQR)",
        "Value": upper_3,
        "Unit": "hours",
        "Interpretation": "Statistical flag only; not a removal threshold",
    }])

    add_check(checks, "NO_SLACK_AUTOMATIC_APPROVAL",
              "No interval is automatically approved as schedule slack",
              bool((intervals["Schedule_Slack_Status"] == "NOT_ESTABLISHED_FROM_AVAILABLE_DATA").all()),
              intervals["Schedule_Slack_Status"].nunique(), 1)
    add_check(checks, "NO_OPERATIONAL_RECOVERY_APPROVAL",
              "No interval is automatically approved for operational recovery",
              bool((intervals["Operational_Recovery_Status"] == "NOT_ASSESSED").all()),
              intervals["Operational_Recovery_Status"].nunique(), 1)

    checks_df = pd.DataFrame(checks)
    failed = checks_df.loc[~checks_df["Passed"]]

    outputs = {
        "78_canonical_intercall_interval_register.csv": intervals,
        "78_intercall_interval_distribution_by_type.csv": type_summary,
        "78_distinct_port_pair_interval_summary.csv": pair_summary,
        "78_vessel_intercall_interval_summary.csv": vessel_summary,
        "78_interval_distribution_thresholds.csv": cap_summary,
        "78_validation_checks.csv": checks_df,
    }
    for filename, frame in outputs.items():
        frame.to_csv(table_dir / filename, index=False)

    report = [
        "SCRIPT 78 — OBSERVED INTER-CALL INTERVAL AND SCHEDULE-SLACK EVIDENCE AUDIT",
        "=" * 84,
        f"Project root: {root}",
        f"Input: outputs/tables/{INPUT}",
        f"Canonical calls: {len(canonical)}",
        f"Vessels: {canonical['IMO_Normalised'].nunique()}",
        f"First calls: {first_count}",
        f"Same-port links: {same_count}",
        f"Distinct-port transitions: {distinct_count}",
        f"Valid non-first elapsed intervals: {int(valid.sum())}",
        f"Missing interval values: {int((~valid).sum())}",
        f"Negative reconstructed intervals: {negative_elapsed}",
        f"Zero reconstructed intervals: {zero_elapsed}",
        f"Timestamp reconciliation mismatches (>0.02h): {elapsed_mismatch}",
        "",
        "DISTRIBUTION-BASED FLAGS (DESCRIPTIVE ONLY)",
        f"Q1: {q1:.6f} h",
        f"Median: {safe_quantile(x, 0.50):.6f} h",
        f"Q3: {q3:.6f} h",
        f"P90: {p90:.6f} h",
        f"P95: {p95:.6f} h",
        f"P99: {p99:.6f} h",
        f"Upper IQR fence (Q3 + 1.5 IQR): {upper_1_5:.6f} h",
        f"Extreme IQR fence (Q3 + 3 IQR): {upper_3:.6f} h",
        f"Above P90: {int(intervals['Above_P90_Descriptive_Flag'].sum())}",
        f"Above P95: {int(intervals['Above_P95_Descriptive_Flag'].sum())}",
        f"Above P99: {int(intervals['Above_P99_Descriptive_Flag'].sum())}",
        f"Upper IQR flags: {int(intervals['IQR_1_5_Descriptive_Outlier_Flag'].sum())}",
        f"Extreme IQR flags: {int(intervals['IQR_3_Descriptive_Extreme_Flag'].sum())}",
        "",
        "CRITICAL INTERPRETATION",
        "- Inter-call elapsed time is the observed interval from previous call departure to current call arrival.",
        "- It may include sailing, anchorage, waiting, port operations and data gaps.",
        "- Distribution thresholds are descriptive flags, not evidence of available schedule slack.",
        "- No interval is approved as schedule slack or operationally recoverable time.",
        "- No interval is deleted or winsorized; all source records are retained.",
        "- This analysis does not establish physical routes or actual Strait of Hormuz transit.",
        "",
        f"Validation checks passed: {int(checks_df['Passed'].sum())}/{len(checks_df)}",
        f"Validation checks failed: {len(failed)}",
        "",
        "FAILED CHECKS",
    ]
    report.append("None." if failed.empty else "\n".join(
        f"- {r.Check_ID}: observed={r.Observed}; expected={r.Expected}"
        for r in failed.itertuples(index=False)
    ))
    report.extend(["", "OUTPUT FILES"])
    report.extend(f"- outputs/tables/{name}" for name in outputs)
    report.append("- outputs/reports/78_intercall_interval_and_schedule_slack_evidence_audit_report.txt")

    report_path = report_dir / "78_intercall_interval_and_schedule_slack_evidence_audit_report.txt"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    if not failed.empty:
        print("\nFAILED: inspect outputs before interpretation.", file=sys.stderr)
        return 2
    print("\nSUCCESS: Script 78 interval evidence audit completed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(1)
