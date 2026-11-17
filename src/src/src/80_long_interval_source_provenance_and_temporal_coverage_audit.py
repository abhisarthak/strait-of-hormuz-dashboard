#!/usr/bin/env python3
"""
SCRIPT 80 — LONG-INTERVAL SOURCE PROVENANCE AND TEMPORAL COVERAGE AUDIT

Purpose
-------
Trace the 449 canonical inter-call intervals from Script78/79 back to the
processed Script19 historical schedule and observed-transition register.
Assess record identity, source-row traceability, timestamp agreement, and
whether the available processed registers contain evidence that explains
the components of long elapsed intervals.

Research safeguards
-------------------
* This is a read-only audit. It does not modify upstream data.
* Script19 files are processed research inputs, not the original vendor
  source extract. A Schedule_Source_Row is an internal lineage pointer,
  not proof of original-source completeness.
* The interval from previous departure to current arrival is elapsed time.
  It is not automatically sailing time, waiting time, schedule slack, or
  recoverable time.
* No interval is deleted, winsorized, causally classified, or approved for
  empirical distribution fitting or operational recovery.
* No physical route or actual Strait of Hormuz transit is established.

Run from project root:
    python src/80_long_interval_source_provenance_and_temporal_coverage_audit.py

Expected inputs:
    outputs/tables/78_canonical_intercall_interval_register.csv
    data/simulation_inputs/19_historical_arrival_schedule.csv
    data/simulation_inputs/19_observed_interport_transitions.csv

Outputs:
    outputs/tables/80_interval_source_provenance_register.csv
    outputs/tables/80_long_interval_source_review_queue.csv
    outputs/tables/80_source_row_coverage_summary.csv
    outputs/tables/80_temporal_coverage_diagnostics.csv
    outputs/tables/80_validation_checks.csv
    outputs/reports/80_long_interval_source_provenance_and_temporal_coverage_report.txt
"""

from __future__ import annotations

from pathlib import Path
import sys
import traceback
import pandas as pd
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TABLES = PROJECT_ROOT / "outputs" / "tables"
REPORTS = PROJECT_ROOT / "outputs" / "reports"
SIM_INPUTS = PROJECT_ROOT / "data" / "simulation_inputs"

INPUT_INTERVALS = TABLES / "78_canonical_intercall_interval_register.csv"
INPUT_SCHEDULE = SIM_INPUTS / "19_historical_arrival_schedule.csv"
INPUT_TRANSITIONS = SIM_INPUTS / "19_observed_interport_transitions.csv"

OUT_PROVENANCE = TABLES / "80_interval_source_provenance_register.csv"
OUT_REVIEW = TABLES / "80_long_interval_source_review_queue.csv"
OUT_SOURCE_COVERAGE = TABLES / "80_source_row_coverage_summary.csv"
OUT_TEMPORAL = TABLES / "80_temporal_coverage_diagnostics.csv"
OUT_CHECKS = TABLES / "80_validation_checks.csv"
OUT_REPORT = REPORTS / "80_long_interval_source_provenance_and_temporal_coverage_report.txt"

TOLERANCE_HOURS = 0.02


def require_columns(df: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def read_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required {label} not found: {path}")
    return pd.read_csv(path, low_memory=False)


def parse_utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True)


def add_check(rows: list[dict], check_id: str, description: str,
              observed, expected, passed: bool, severity: str = "ERROR") -> None:
    rows.append({
        "Check_ID": check_id,
        "Description": description,
        "Observed": observed,
        "Expected": expected,
        "Status": "PASS" if bool(passed) else "FAIL",
        "Severity": severity,
    })


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    intervals = read_csv(INPUT_INTERVALS, "Script78 canonical interval register")
    schedule = read_csv(INPUT_SCHEDULE, "Script19 historical arrival schedule")
    transitions = read_csv(INPUT_TRANSITIONS, "Script19 observed inter-port transitions")

    require_columns(intervals, [
        "Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised",
        "Vessel_Call_Sequence_Number", "Previous_Simulation_Record_ID",
        "Previous_Port", "Transition_Type", "Observed_Inter_Call_Elapsed_Hours",
        "Actual_Arrival_UTC", "Previous_Departure_UTC",
    ], "Script78 interval register")
    require_columns(schedule, [
        "Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised",
        "Actual_Arrival_UTC", "Actual_Departure_UTC", "Schedule_Source_Row",
        "Source_Port",
    ], "Script19 historical schedule")
    # Script19 observed-transition register has a different schema from the
    # call schedule. Its port-pair fields are Previous_Port / Next_Port; do not
    # require schedule-only columns such as UNLOCODE_Normalised or Source_Port.
    require_columns(transitions, [
        "Simulation_Record_ID", "IMO_Normalised",
    ], "Script19 observed-transition register")
    transition_port_column = next(
        (c for c in ("Next_Port", "UNLOCODE_Normalised", "Current_Port")
         if c in transitions.columns),
        None,
    )
    transition_arrival_column = next(
        (c for c in ("Actual_Arrival_UTC", "Next_Arrival_UTC", "Arrival_UTC")
         if c in transitions.columns),
        None,
    )
    transition_source_row_column = next(
        (c for c in ("Schedule_Source_Row", "Source_Row")
         if c in transitions.columns),
        None,
    )

    # Canonicalise IDs as strings without changing the source files.
    for frame in (intervals, schedule, transitions):
        for col in ("Simulation_Record_ID", "IMO_Normalised"):
            frame[col] = frame[col].astype("string").str.strip()

    schedule["Actual_Arrival_UTC_parsed"] = parse_utc(schedule["Actual_Arrival_UTC"])
    schedule["Actual_Departure_UTC_parsed"] = parse_utc(schedule["Actual_Departure_UTC"])
    if transition_arrival_column:
        transitions["_Transition_Arrival_UTC_parsed"] = parse_utc(
            transitions[transition_arrival_column]
        )
    else:
        transitions["_Transition_Arrival_UTC_parsed"] = pd.NaT

    # Schedule is the record-level source for both ends of every interval.
    if schedule["Simulation_Record_ID"].duplicated().any():
        dupes = int(schedule["Simulation_Record_ID"].duplicated(keep=False).sum())
        raise ValueError(f"Script19 schedule has duplicate Simulation_Record_ID rows: {dupes}")
    schedule_idx = schedule.set_index("Simulation_Record_ID", drop=False)

    # Transition register may only cover the distinct-port observed transitions.
    transition_counts = transitions["Simulation_Record_ID"].value_counts(dropna=False)
    transition_unique = transitions.drop_duplicates("Simulation_Record_ID").set_index(
        "Simulation_Record_ID", drop=False
    )

    rows = []
    for _, r in intervals.iterrows():
        current_id = r["Simulation_Record_ID"]
        previous_id = r["Previous_Simulation_Record_ID"]
        current = schedule_idx.loc[current_id] if current_id in schedule_idx.index else None
        previous = schedule_idx.loc[previous_id] if pd.notna(previous_id) and previous_id in schedule_idx.index else None
        transition = transition_unique.loc[current_id] if current_id in transition_unique.index else None

        current_arrival = parse_utc(pd.Series([r["Actual_Arrival_UTC"]])).iloc[0]
        previous_departure = parse_utc(pd.Series([r["Previous_Departure_UTC"]])).iloc[0]
        reconstructed = (
            (current_arrival - previous_departure).total_seconds() / 3600
            if pd.notna(current_arrival) and pd.notna(previous_departure) else np.nan
        )

        current_schedule_arrival = current["Actual_Arrival_UTC_parsed"] if current is not None else pd.NaT
        previous_schedule_departure = previous["Actual_Departure_UTC_parsed"] if previous is not None else pd.NaT
        current_arrival_diff = (
            (current_arrival - current_schedule_arrival).total_seconds() / 3600
            if pd.notna(current_arrival) and pd.notna(current_schedule_arrival) else np.nan
        )
        previous_departure_diff = (
            (previous_departure - previous_schedule_departure).total_seconds() / 3600
            if pd.notna(previous_departure) and pd.notna(previous_schedule_departure) else np.nan
        )

        current_source_row = current["Schedule_Source_Row"] if current is not None else pd.NA
        previous_source_row = previous["Schedule_Source_Row"] if previous is not None else pd.NA
        transition_source_row = (
            transition[transition_source_row_column]
            if transition is not None and transition_source_row_column else pd.NA
        )

        current_imo_match = (
            str(current["IMO_Normalised"]) == str(r["IMO_Normalised"])
            if current is not None and pd.notna(current["IMO_Normalised"]) else False
        )
        previous_imo_match = (
            str(previous["IMO_Normalised"]) == str(r["IMO_Normalised"])
            if previous is not None and pd.notna(previous["IMO_Normalised"]) else False
        )
        current_port_match = (
            str(current["UNLOCODE_Normalised"]) == str(r["UNLOCODE_Normalised"])
            if current is not None and pd.notna(current["UNLOCODE_Normalised"]) else False
        )
        previous_port_match = (
            str(previous["UNLOCODE_Normalised"]) == str(r["Previous_Port"])
            if previous is not None and pd.notna(previous["UNLOCODE_Normalised"]) else False
        )

        transition_imo_match = (
            str(transition["IMO_Normalised"]) == str(r["IMO_Normalised"])
            if transition is not None and pd.notna(transition["IMO_Normalised"]) else False
        )
        transition_port_match = (
            str(transition[transition_port_column]) == str(r["UNLOCODE_Normalised"])
            if transition is not None and transition_port_column
            and pd.notna(transition[transition_port_column]) else False
        )
        transition_arrival = (
            transition["_Transition_Arrival_UTC_parsed"]
            if transition is not None else pd.NaT
        )
        transition_arrival_diff = (
            (current_arrival - transition_arrival).total_seconds() / 3600
            if pd.notna(current_arrival) and pd.notna(transition_arrival) else np.nan
        )

        interval_hours = pd.to_numeric(
            pd.Series([r["Observed_Inter_Call_Elapsed_Hours"]]), errors="coerce"
        ).iloc[0]
        schedule_lineage = current is not None and previous is not None
        timestamp_reconciled = (
            pd.notna(current_arrival_diff) and abs(current_arrival_diff) <= TOLERANCE_HOURS
            and pd.notna(previous_departure_diff) and abs(previous_departure_diff) <= TOLERANCE_HOURS
        )
        elapsed_reconciled = (
            pd.notna(reconstructed) and pd.notna(interval_hours)
            and abs(reconstructed - interval_hours) <= TOLERANCE_HOURS
        )

        rows.append({
            "Simulation_Record_ID": current_id,
            "Previous_Simulation_Record_ID": previous_id,
            "IMO_Normalised": r["IMO_Normalised"],
            "Previous_Port": r["Previous_Port"],
            "Current_Port": r["UNLOCODE_Normalised"],
            "Transition_Type": r["Transition_Type"],
            "Call_Sequence_Number": r["Vessel_Call_Sequence_Number"],
            "Observed_Inter_Call_Elapsed_Hours": interval_hours,
            "Observed_Inter_Call_Elapsed_Days": interval_hours / 24 if pd.notna(interval_hours) else np.nan,
            "Current_Schedule_Record_Found": current is not None,
            "Previous_Schedule_Record_Found": previous is not None,
            "Both_Schedule_Records_Found": schedule_lineage,
            "Current_Schedule_Source_Row": current_source_row,
            "Previous_Schedule_Source_Row": previous_source_row,
            "Current_Source_Port": current["Source_Port"] if current is not None else pd.NA,
            "Previous_Source_Port": previous["Source_Port"] if previous is not None else pd.NA,
            "Current_IMO_Match": current_imo_match,
            "Previous_IMO_Match": previous_imo_match,
            "Current_Port_Match": current_port_match,
            "Previous_Port_Match": previous_port_match,
            "Current_Arrival_Timestamp_Difference_Hours": current_arrival_diff,
            "Previous_Departure_Timestamp_Difference_Hours": previous_departure_diff,
            "Schedule_Timestamps_Reconciled": timestamp_reconciled,
            "Reconstructed_Elapsed_Hours": reconstructed,
            "Elapsed_Time_Reconciled": elapsed_reconciled,
            "Current_Record_In_Observed_Transition_Register": transition is not None,
            "Transition_Register_Row_Count_For_Current_ID": int(transition_counts.get(current_id, 0)),
            "Transition_Register_Source_Row": transition_source_row,
            "Transition_Register_IMO_Match": transition_imo_match,
            "Transition_Register_Current_Port_Match": transition_port_match,
            "Transition_Register_Arrival_Difference_Hours": transition_arrival_diff,
            "Above_P95_Flag": bool(r.get("Above_P95_Descriptive_Flag", False)),
            "Extreme_IQR_Flag": bool(r.get("IQR_3_Descriptive_Extreme_Flag", False)),
            "Investigation_Priority_79": r.get("Investigation_Priority", pd.NA),
            "Source_Explains_Interval_Component_79": r.get("Source_Explains_Interval_Component", pd.NA),
            "Cause_Classification_79": r.get("Cause_Classification", pd.NA),
            "Provenance_Assessment": (
                "SCHEDULE_LINEAGE_AND_TIMESTAMPS_RECONCILED"
                if schedule_lineage and timestamp_reconciled and elapsed_reconciled
                else "PARTIAL_OR_UNRECONCILED_LINEAGE_REQUIRES_REVIEW"
            ),
            "Temporal_Component_Attribution": "NOT_IDENTIFIABLE_FROM_AVAILABLE_PROCESSED_FIELDS",
            "Original_Vendor_Source_Verification": "NOT_ESTABLISHED_BY_SCRIPT19_PROCESSED_REGISTERS",
            "Schedule_Slack_Approval": False,
            "Operational_Recovery_Approval": False,
            "Empirical_Distribution_Approval": False,
        })

    provenance = pd.DataFrame(rows)
    if provenance["Simulation_Record_ID"].duplicated().any():
        raise ValueError("Duplicate current call IDs in Script80 provenance output.")

    # Review all P95-or-higher records, preserving the complete record-level evidence.
    review = provenance.loc[
        provenance["Above_P95_Flag"] | provenance["Extreme_IQR_Flag"]
    ].copy()
    review = review.sort_values(
        ["Observed_Inter_Call_Elapsed_Hours", "Simulation_Record_ID"],
        ascending=[False, True]
    )

    # Source-row coverage summaries: these are lineage coverage indicators, not
    # independent validation of the original source provider.
    coverage_rows = []
    for label, mask in [
        ("ALL_CANONICAL_INTERVALS", pd.Series(True, index=provenance.index)),
        ("ABOVE_P95", provenance["Above_P95_Flag"]),
        ("EXTREME_IQR", provenance["Extreme_IQR_Flag"]),
        ("ABOVE_P95_OR_EXTREME_IQR", provenance["Above_P95_Flag"] | provenance["Extreme_IQR_Flag"]),
    ]:
        d = provenance.loc[mask]
        coverage_rows.append({
            "Population": label,
            "Interval_Count": len(d),
            "Both_Schedule_Records_Found": int(d["Both_Schedule_Records_Found"].sum()),
            "Current_Source_Row_Present": int(d["Current_Schedule_Source_Row"].notna().sum()),
            "Previous_Source_Row_Present": int(d["Previous_Schedule_Source_Row"].notna().sum()),
            "Schedule_Timestamps_Reconciled": int(d["Schedule_Timestamps_Reconciled"].sum()),
            "Elapsed_Time_Reconciled": int(d["Elapsed_Time_Reconciled"].sum()),
            "Current_ID_In_Transition_Register": int(d["Current_Record_In_Observed_Transition_Register"].sum()),
            "Transition_Register_IMO_Matches": int(d["Transition_Register_IMO_Match"].sum()),
            "Transition_Register_Port_Matches": int(d["Transition_Register_Current_Port_Match"].sum()),
            "Original_Vendor_Source_Verified_Count": 0,
            "Temporal_Component_Attribution_Count": 0,
            "Schedule_Slack_Approval_Count": 0,
            "Operational_Recovery_Approval_Count": 0,
        })
    source_coverage = pd.DataFrame(coverage_rows)

    # Temporal coverage diagnostics: interval distributions and calendar span.
    interval_num = pd.to_numeric(provenance["Observed_Inter_Call_Elapsed_Hours"], errors="coerce").dropna()
    temporal_rows = []
    for label, mask in [
        ("ALL_CANONICAL_INTERVALS", pd.Series(True, index=provenance.index)),
        ("ABOVE_P95", provenance["Above_P95_Flag"]),
        ("EXTREME_IQR", provenance["Extreme_IQR_Flag"]),
        ("SAME_PORT", provenance["Transition_Type"].astype(str).str.upper().str.contains("SAME")),
        ("DISTINCT_PORT", provenance["Transition_Type"].astype(str).str.upper().str.contains("DISTINCT")),
    ]:
        d = provenance.loc[mask]
        vals = pd.to_numeric(d["Observed_Inter_Call_Elapsed_Hours"], errors="coerce").dropna()
        temporal_rows.append({
            "Population": label,
            "N": len(vals),
            "Mean_Elapsed_Hours": vals.mean() if len(vals) else np.nan,
            "Median_Elapsed_Hours": vals.median() if len(vals) else np.nan,
            "P90_Elapsed_Hours": vals.quantile(0.90) if len(vals) else np.nan,
            "P95_Elapsed_Hours": vals.quantile(0.95) if len(vals) else np.nan,
            "Maximum_Elapsed_Hours": vals.max() if len(vals) else np.nan,
            "Maximum_Elapsed_Days": vals.max() / 24 if len(vals) else np.nan,
            "Records_Over_30_Days": int((vals > 720).sum()),
            "Records_Over_60_Days": int((vals > 1440).sum()),
            "Both_Schedule_Records_Found": int(d["Both_Schedule_Records_Found"].sum()),
            "Timestamp_Reconciliations_Passed": int(d["Schedule_Timestamps_Reconciled"].sum()),
        })

    # Build validation checks after outputs have been constructed.
    checks = []
    n_intervals = len(intervals)
    add_check(checks, "C01", "All Script78 canonical intervals represented",
              len(provenance), n_intervals, len(provenance) == n_intervals)
    add_check(checks, "C02", "Current call IDs unique in provenance register",
              int(provenance["Simulation_Record_ID"].nunique()), n_intervals,
              provenance["Simulation_Record_ID"].nunique() == n_intervals)
    add_check(checks, "C03", "Every current interval call found in Script19 schedule",
              int(provenance["Current_Schedule_Record_Found"].sum()), n_intervals,
              provenance["Current_Schedule_Record_Found"].all())
    add_check(checks, "C04", "Every previous call found in Script19 schedule",
              int(provenance["Previous_Schedule_Record_Found"].sum()), n_intervals,
              provenance["Previous_Schedule_Record_Found"].all())
    add_check(checks, "C05", "Current and previous IMO identities match interval register",
              int((provenance["Current_IMO_Match"] & provenance["Previous_IMO_Match"]).sum()),
              n_intervals,
              (provenance["Current_IMO_Match"] & provenance["Previous_IMO_Match"]).all())
    add_check(checks, "C06", "Current and previous port identities match interval register",
              int((provenance["Current_Port_Match"] & provenance["Previous_Port_Match"]).sum()),
              n_intervals,
              (provenance["Current_Port_Match"] & provenance["Previous_Port_Match"]).all())
    add_check(checks, "C07", "Arrival and previous-departure timestamps reconcile",
              int(provenance["Schedule_Timestamps_Reconciled"].sum()), n_intervals,
              provenance["Schedule_Timestamps_Reconciled"].all())
    add_check(checks, "C08", "Reconstructed elapsed intervals reconcile",
              int(provenance["Elapsed_Time_Reconciled"].sum()), n_intervals,
              provenance["Elapsed_Time_Reconciled"].all())
    add_check(checks, "C09", "No duplicate current call IDs in transition source",
              int((transition_counts > 1).sum()), 0, not (transition_counts > 1).any())
    add_check(checks, "C10", "No approvals or causal attribution introduced",
              int(provenance[["Schedule_Slack_Approval", "Operational_Recovery_Approval",
                              "Empirical_Distribution_Approval"]].to_numpy().sum()),
              0, not provenance[["Schedule_Slack_Approval", "Operational_Recovery_Approval",
                                 "Empirical_Distribution_Approval"]].to_numpy().any())
    add_check(checks, "C11", "All source provenance outputs retain original-vendor verification boundary",
              int((provenance["Original_Vendor_Source_Verification"] ==
                   "NOT_ESTABLISHED_BY_SCRIPT19_PROCESSED_REGISTERS").sum()),
              n_intervals,
              (provenance["Original_Vendor_Source_Verification"] ==
               "NOT_ESTABLISHED_BY_SCRIPT19_PROCESSED_REGISTERS").all(),
              severity="RESEARCH_BOUNDARY")

    checks_df = pd.DataFrame(checks)

    provenance.to_csv(OUT_PROVENANCE, index=False)
    review.to_csv(OUT_REVIEW, index=False)
    source_coverage.to_csv(OUT_SOURCE_COVERAGE, index=False)
    pd.DataFrame(temporal_rows).to_csv(OUT_TEMPORAL, index=False)
    checks_df.to_csv(OUT_CHECKS, index=False)

    passed = int((checks_df["Status"] == "PASS").sum())
    failed = int((checks_df["Status"] == "FAIL").sum())
    report = [
        "SCRIPT 80 — LONG-INTERVAL SOURCE PROVENANCE AND TEMPORAL COVERAGE AUDIT",
        "=" * 78,
        f"Project root: {PROJECT_ROOT}",
        f"Canonical Script78 intervals: {len(intervals)}",
        f"Script19 historical schedule records: {len(schedule)}",
        f"Script19 observed-transition records: {len(transitions)}",
        f"Distinct vessels represented: {provenance['IMO_Normalised'].nunique()}",
        f"Intervals above P95: {int(provenance['Above_P95_Flag'].sum())}",
        f"Extreme IQR intervals: {int(provenance['Extreme_IQR_Flag'].sum())}",
        "",
        "PROVENANCE AND TEMPORAL RECONCILIATION",
        f"Current call records found in Script19 schedule: {int(provenance['Current_Schedule_Record_Found'].sum())}/{len(provenance)}",
        f"Previous call records found in Script19 schedule: {int(provenance['Previous_Schedule_Record_Found'].sum())}/{len(provenance)}",
        f"Both schedule records found: {int(provenance['Both_Schedule_Records_Found'].sum())}/{len(provenance)}",
        f"Current source-row references present: {int(provenance['Current_Schedule_Source_Row'].notna().sum())}/{len(provenance)}",
        f"Previous source-row references present: {int(provenance['Previous_Schedule_Source_Row'].notna().sum())}/{len(provenance)}",
        f"Arrival/departure timestamps reconciled: {int(provenance['Schedule_Timestamps_Reconciled'].sum())}/{len(provenance)}",
        f"Elapsed intervals reconciled: {int(provenance['Elapsed_Time_Reconciled'].sum())}/{len(provenance)}",
        f"Current call IDs in observed-transition register: {int(provenance['Current_Record_In_Observed_Transition_Register'].sum())}/{len(provenance)}",
        "",
        "RESEARCH INTERPRETATION",
        "- Script19 files are processed registers, not the original vendor source extract.",
        "- Schedule_Source_Row is an internal lineage pointer; it does not independently verify original-source completeness.",
        "- A timestamp-reconciled interval remains an observed inter-call elapsed interval.",
        "- Available processed fields do not decompose the interval into sailing, anchorage, waiting, operations, or observation gaps.",
        "- No causal classification, schedule-slack approval, recovery approval, or empirical-distribution approval is made.",
        "- No physical route or actual Strait of Hormuz transit is established.",
        "",
        f"Validation checks passed: {passed}/{len(checks_df)}",
        f"Validation checks failed: {failed}",
        "",
        "CHECK RESULTS",
    ]
    for _, c in checks_df.iterrows():
        report.append(f"{c['Check_ID']} [{c['Status']}] {c['Description']} — observed={c['Observed']}, expected={c['Expected']}")
    report += [
        "",
        "OUTPUT FILES",
        f"- {OUT_PROVENANCE.relative_to(PROJECT_ROOT)}",
        f"- {OUT_REVIEW.relative_to(PROJECT_ROOT)}",
        f"- {OUT_SOURCE_COVERAGE.relative_to(PROJECT_ROOT)}",
        f"- {OUT_TEMPORAL.relative_to(PROJECT_ROOT)}",
        f"- {OUT_CHECKS.relative_to(PROJECT_ROOT)}",
        f"- {OUT_REPORT.relative_to(PROJECT_ROOT)}",
    ]
    OUT_REPORT.write_text("\n".join(report), encoding="utf-8")

    print("\n".join(report))
    if failed:
        raise SystemExit("Script80 validation failed. Review validation checks and outputs.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
