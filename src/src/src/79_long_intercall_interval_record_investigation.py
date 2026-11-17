#!/usr/bin/env python3
"""
SCRIPT 79 — LONG INTERVAL RECORD-LEVEL INVESTIGATION

Run from project root:
    python src/79_long_intercall_interval_record_investigation.py

Input:
    outputs/tables/78_canonical_intercall_interval_register.csv

Purpose:
    Investigate long observed inter-call intervals at record, vessel and
    port-pair levels. Preserve all records and distinguish observable facts
    from explanations that the current dataset cannot establish.

Important:
    This script does not infer sailing time, anchorage time, waiting time,
    schedule slack, AIS route, disruption cause, or operational recoverability.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

INPUT = "78_canonical_intercall_interval_register.csv"
TOL = 1e-8
EXPECTED_LINKS = 449
EXPECTED_SAME = 178
EXPECTED_DISTINCT = 271


def add_check(rows, check_id, description, passed, observed, expected):
    rows.append({
        "Check_ID": check_id,
        "Description": description,
        "Passed": bool(passed),
        "Observed": str(observed),
        "Expected": str(expected),
        "Status": "PASS" if passed else "FAIL",
    })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.expanduser().resolve()
    tables = root / "outputs" / "tables"
    reports = root / "outputs" / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    source_path = tables / INPUT
    if not source_path.exists():
        raise FileNotFoundError(f"Missing Script78 canonical interval register: {source_path}")

    df = pd.read_csv(source_path, low_memory=False)
    required = [
        "Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised",
        "Vessel_Call_Sequence_Number", "Previous_Simulation_Record_ID",
        "Previous_Port", "Transition_Type", "Observed_Inter_Call_Elapsed_Hours",
        "Actual_Arrival_UTC", "Actual_Departure_UTC",
        "Previous_Departure_UTC", "Reconstructed_Inter_Call_Elapsed_Hours",
        "Long_Interval_Classification", "Above_P90_Descriptive_Flag",
        "Above_P95_Descriptive_Flag", "Above_P99_Descriptive_Flag",
        "IQR_1_5_Descriptive_Outlier_Flag", "IQR_3_Descriptive_Extreme_Flag",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Script78 input missing required columns: {missing}")

    # The Script78 file contains only non-first links, and should contain one
    # canonical row per historical transition.
    df["Observed_Inter_Call_Elapsed_Hours"] = pd.to_numeric(
        df["Observed_Inter_Call_Elapsed_Hours"], errors="coerce"
    )
    df["Previous_Port"] = df["Previous_Port"].fillna("UNKNOWN").astype(str)
    df["UNLOCODE_Normalised"] = df["UNLOCODE_Normalised"].fillna("UNKNOWN").astype(str)
    df["IMO_Normalised"] = df["IMO_Normalised"].astype(str)
    df["Simulation_Record_ID"] = df["Simulation_Record_ID"].astype(str)
    df["Previous_Simulation_Record_ID"] = df["Previous_Simulation_Record_ID"].astype(str)

    # Recalculate global distribution thresholds from the canonical interval
    # population. Flags are diagnostic only and are never exclusion criteria.
    values = df["Observed_Inter_Call_Elapsed_Hours"].dropna()
    q1, q3 = values.quantile([0.25, 0.75])
    iqr = q3 - q1
    p90, p95, p99 = values.quantile([0.90, 0.95, 0.99])
    upper_fence = q3 + 1.5 * iqr
    extreme_fence = q3 + 3.0 * iqr

    # Recompute flags independently, then compare with Script78's stored flags.
    df["Recomputed_Above_P90"] = df["Observed_Inter_Call_Elapsed_Hours"] > p90
    df["Recomputed_Above_P95"] = df["Observed_Inter_Call_Elapsed_Hours"] > p95
    df["Recomputed_Above_P99"] = df["Observed_Inter_Call_Elapsed_Hours"] > p99
    df["Recomputed_IQR_1_5_Flag"] = df["Observed_Inter_Call_Elapsed_Hours"] > upper_fence
    df["Recomputed_IQR_3_Flag"] = df["Observed_Inter_Call_Elapsed_Hours"] > extreme_fence

    flag_mismatch = 0
    for stored, recomputed in [
        ("Above_P90_Descriptive_Flag", "Recomputed_Above_P90"),
        ("Above_P95_Descriptive_Flag", "Recomputed_Above_P95"),
        ("Above_P99_Descriptive_Flag", "Recomputed_Above_P99"),
        ("IQR_1_5_Descriptive_Outlier_Flag", "Recomputed_IQR_1_5_Flag"),
        ("IQR_3_Descriptive_Extreme_Flag", "Recomputed_IQR_3_Flag"),
    ]:
        a = df[stored].fillna(False).astype(bool)
        b = df[recomputed].fillna(False).astype(bool)
        flag_mismatch += int((a != b).sum())

    # Add transparent record-level investigation fields.
    df["Port_Pair"] = df["Previous_Port"] + " -> " + df["UNLOCODE_Normalised"]
    df["Interval_Hours_Recomputed"] = (
        pd.to_numeric(df["Reconstructed_Inter_Call_Elapsed_Hours"], errors="coerce")
    )
    df["Interval_Days"] = df["Observed_Inter_Call_Elapsed_Hours"] / 24.0
    df["Investigation_Priority"] = np.select(
        [
            df["Recomputed_IQR_3_Flag"],
            df["Recomputed_IQR_1_5_Flag"],
            df["Recomputed_Above_P95"],
            df["Recomputed_Above_P90"],
        ],
        ["P1_EXTREME_STATISTICAL_FLAG", "P2_UPPER_IQR_FLAG",
         "P3_ABOVE_P95", "P4_ABOVE_P90"],
        default="P5_NO_SELECTED_LONG_INTERVAL_FLAG",
    )
    df["Repeated_Port_Pair_Observation_Count"] = df.groupby(
        ["Previous_Port", "UNLOCODE_Normalised"]
    )["Simulation_Record_ID"].transform("count")
    df["Vessel_Interval_Observation_Count"] = df.groupby(
        "IMO_Normalised"
    )["Simulation_Record_ID"].transform("count")
    df["Same_Vessel_Same_Pair_Observation_Count"] = df.groupby(
        ["IMO_Normalised", "Previous_Port", "UNLOCODE_Normalised"]
    )["Simulation_Record_ID"].transform("count")
    df["Previous_Call_ID_Available"] = (
        df["Previous_Simulation_Record_ID"].notna()
        & df["Previous_Simulation_Record_ID"].ne("")
        & df["Previous_Simulation_Record_ID"].ne("nan")
    )
    df["Current_Arrival_Available"] = pd.to_datetime(
        df["Actual_Arrival_UTC"], utc=True, errors="coerce"
    ).notna()
    df["Previous_Departure_Available"] = pd.to_datetime(
        df["Previous_Departure_UTC"], utc=True, errors="coerce"
    ).notna()
    df["Source_Explains_Interval_Component"] = False
    df["Cause_Classification"] = "UNRESOLVED_WITH_AVAILABLE_FIELDS"
    df["Schedule_Slack_Approval"] = "NOT_APPROVED"
    df["Operational_Recovery_Approval"] = "NOT_APPROVED"
    df["Researcher_Action"] = np.select(
        [
            df["Recomputed_IQR_3_Flag"],
            df["Recomputed_IQR_1_5_Flag"],
            df["Recomputed_Above_P95"],
        ],
        [
            "Inspect source provenance and original call timestamps; do not infer cause",
            "Review record and compare with other observations for this vessel and pair",
            "Retain and review as a high-interval observation",
        ],
        default="Retain as observed; no special long-interval flag",
    )

    # Summary by transition type.
    type_rows = []
    for transition_type, grp in df.groupby("Transition_Type", dropna=False):
        s = grp["Observed_Inter_Call_Elapsed_Hours"].dropna()
        type_rows.append({
            "Transition_Type": transition_type,
            "Records": len(grp),
            "Vessels": grp["IMO_Normalised"].nunique(),
            "Mean_Hours": s.mean(),
            "Median_Hours": s.median(),
            "P90_Hours": s.quantile(.90),
            "P95_Hours": s.quantile(.95),
            "Maximum_Hours": s.max(),
            "Above_Global_P90_Count": int(grp["Recomputed_Above_P90"].sum()),
            "Upper_IQR_Flag_Count": int(grp["Recomputed_IQR_1_5_Flag"].sum()),
            "Extreme_IQR_Flag_Count": int(grp["Recomputed_IQR_3_Flag"].sum()),
        })
    type_summary = pd.DataFrame(type_rows)

    # Port-pair level investigation. Distinguish sample size and vessel count.
    pair_summary = df.groupby(
        ["Previous_Port", "UNLOCODE_Normalised", "Transition_Type"],
        dropna=False
    ).agg(
        Transition_Count=("Simulation_Record_ID", "size"),
        Distinct_Vessels=("IMO_Normalised", "nunique"),
        Mean_Elapsed_Hours=("Observed_Inter_Call_Elapsed_Hours", "mean"),
        Median_Elapsed_Hours=("Observed_Inter_Call_Elapsed_Hours", "median"),
        P90_Elapsed_Hours=("Observed_Inter_Call_Elapsed_Hours", lambda s: s.quantile(.90)),
        P95_Elapsed_Hours=("Observed_Inter_Call_Elapsed_Hours", lambda s: s.quantile(.95)),
        Maximum_Elapsed_Hours=("Observed_Inter_Call_Elapsed_Hours", "max"),
        Above_Global_P90_Count=("Recomputed_Above_P90", "sum"),
        Upper_IQR_Flag_Count=("Recomputed_IQR_1_5_Flag", "sum"),
        Extreme_IQR_Flag_Count=("Recomputed_IQR_3_Flag", "sum"),
    ).reset_index()
    pair_summary["Port_Pair"] = (
        pair_summary["Previous_Port"] + " -> " + pair_summary["UNLOCODE_Normalised"]
    )
    pair_summary["Evidence_Caution"] = np.select(
        [
            pair_summary["Distinct_Vessels"] <= 1,
            pair_summary["Transition_Count"] < 5,
            pair_summary["Distinct_Vessels"] < 3,
        ],
        [
            "SINGLE_VESSEL_EVIDENCE_ONLY",
            "VERY_SMALL_TRANSITION_SAMPLE",
            "LIMITED_VESSEL_DIVERSITY",
        ],
        default="DESCRIPTIVE_MULTI_VESSEL_EVIDENCE",
    )
    pair_summary["Cause_Classification"] = "UNRESOLVED_WITH_AVAILABLE_FIELDS"
    pair_summary["Schedule_Slack_Approval"] = "NOT_APPROVED"

    # Vessel-level recurrence summary.
    vessel_summary = df.groupby("IMO_Normalised", dropna=False).agg(
        Inter_Call_Transition_Count=("Simulation_Record_ID", "size"),
        Distinct_Port_Pairs=("Port_Pair", "nunique"),
        Same_Port_Link_Count=("Transition_Type", lambda s: int((s == "SAME_PORT_SEQUENCE_LINK").sum())),
        Distinct_Port_Link_Count=("Transition_Type", lambda s: int((s == "DISTINCT_PORT_INTERPORT_TRANSITION").sum())),
        Mean_Elapsed_Hours=("Observed_Inter_Call_Elapsed_Hours", "mean"),
        Median_Elapsed_Hours=("Observed_Inter_Call_Elapsed_Hours", "median"),
        Maximum_Elapsed_Hours=("Observed_Inter_Call_Elapsed_Hours", "max"),
        Above_Global_P90_Count=("Recomputed_Above_P90", "sum"),
        Upper_IQR_Flag_Count=("Recomputed_IQR_1_5_Flag", "sum"),
        Extreme_IQR_Flag_Count=("Recomputed_IQR_3_Flag", "sum"),
    ).reset_index()
    vessel_summary["Evidence_Caution"] = np.where(
        vessel_summary["Inter_Call_Transition_Count"] == 1,
        "SINGLE_INTERVAL_ONLY",
        np.where(vessel_summary["Inter_Call_Transition_Count"] < 3,
                 "VERY_SMALL_WITHIN_VESSEL_SAMPLE",
                 "REPEATED_WITHIN_VESSEL_OBSERVATIONS"),
    )
    vessel_summary["Cause_Classification"] = "UNRESOLVED_WITH_AVAILABLE_FIELDS"

    # Extreme records and all records above P95 as separate review queues.
    review_queue = df.loc[
        df["Recomputed_Above_P95"]
    ].sort_values(
        ["Observed_Inter_Call_Elapsed_Hours", "IMO_Normalised"],
        ascending=[False, True]
    ).copy()

    # Link consistency: each previous-call ID should be present as a call ID in
    # the canonical register. This validates sequence linkage, not route truth.
    call_ids = set(df["Simulation_Record_ID"])
    missing_previous_ids = int((~df["Previous_Simulation_Record_ID"].isin(call_ids)).sum())
    # The previous call can be outside this interval-only register if it is a
    # vessel's first call; inspect by joining only when present in this file.
    # Therefore this is diagnostic, not a hard failure.
    previous_id_match_count = int(df["Previous_Simulation_Record_ID"].isin(call_ids).sum())

    checks = []
    add_check(checks, "CANONICAL_LINK_COUNT", "All 449 canonical sequence links are retained",
              len(df) == EXPECTED_LINKS, len(df), EXPECTED_LINKS)
    add_check(checks, "UNIQUE_CURRENT_CALLS", "Current call IDs are unique",
              df["Simulation_Record_ID"].nunique() == EXPECTED_LINKS,
              df["Simulation_Record_ID"].nunique(), EXPECTED_LINKS)
    add_check(checks, "TRANSITION_TYPE_COUNTS", "Same-port and distinct-port links reconcile",
              int((df["Transition_Type"] == "SAME_PORT_SEQUENCE_LINK").sum()) == EXPECTED_SAME
              and int((df["Transition_Type"] == "DISTINCT_PORT_INTERPORT_TRANSITION").sum()) == EXPECTED_DISTINCT,
              f"same={(df['Transition_Type']=='SAME_PORT_SEQUENCE_LINK').sum()}; distinct={(df['Transition_Type']=='DISTINCT_PORT_INTERPORT_TRANSITION').sum()}",
              f"same={EXPECTED_SAME}; distinct={EXPECTED_DISTINCT}")
    add_check(checks, "GLOBAL_FLAG_RECALCULATION", "All five stored global statistical flags reproduce",
              flag_mismatch == 0, flag_mismatch, 0)
    add_check(checks, "TIMESTAMP_INTERVAL_RECONCILIATION", "Reconstructed interval values match observed values within 0.02h",
              int((df["Elapsed_Time_Reconciliation_Difference_Hours"].abs() > 0.02).sum()) == 0
              if "Elapsed_Time_Reconciliation_Difference_Hours" in df.columns else
              int((df["Interval_Hours_Recomputed"] - df["Observed_Inter_Call_Elapsed_Hours"]).abs().gt(.02).sum()) == 0,
              int((df["Interval_Hours_Recomputed"] - df["Observed_Inter_Call_Elapsed_Hours"]).abs().gt(.02).sum()), 0)
    add_check(checks, "NO_CAUSE_AUTOMATION", "No interval cause is automatically assigned",
              bool((df["Cause_Classification"] == "UNRESOLVED_WITH_AVAILABLE_FIELDS").all()),
              df["Cause_Classification"].nunique(), 1)
    add_check(checks, "NO_SLACK_APPROVAL", "No schedule-slack approval is granted",
              bool((df["Schedule_Slack_Approval"] == "NOT_APPROVED").all()),
              df["Schedule_Slack_Approval"].nunique(), 1)
    add_check(checks, "NO_OPERATIONAL_RECOVERY_APPROVAL", "No operational recovery approval is granted",
              bool((df["Operational_Recovery_Approval"] == "NOT_APPROVED").all()),
              df["Operational_Recovery_Approval"].nunique(), 1)

    checks_df = pd.DataFrame(checks)
    failed = checks_df.loc[~checks_df["Passed"]]

    outputs = {
        "79_long_interval_record_investigation_register.csv": df,
        "79_long_interval_review_queue_above_p95.csv": review_queue,
        "79_port_pair_long_interval_investigation.csv": pair_summary,
        "79_vessel_long_interval_investigation.csv": vessel_summary,
        "79_transition_type_investigation_summary.csv": type_summary,
        "79_validation_checks.csv": checks_df,
    }
    for filename, frame in outputs.items():
        frame.to_csv(tables / filename, index=False)

    report_lines = [
        "SCRIPT 79 — LONG INTERVAL RECORD-LEVEL INVESTIGATION",
        "=" * 78,
        f"Project root: {root}",
        f"Input: outputs/tables/{INPUT}",
        f"Canonical inter-call records: {len(df)}",
        f"Distinct vessels represented: {df['IMO_Normalised'].nunique()}",
        f"Distinct port pairs: {pair_summary.shape[0]}",
        f"Records above global P95: {len(review_queue)}",
        f"Upper IQR flags: {int(df['Recomputed_IQR_1_5_Flag'].sum())}",
        f"Extreme IQR flags: {int(df['Recomputed_IQR_3_Flag'].sum())}",
        f"Stored/recomputed flag mismatches: {flag_mismatch}",
        f"Previous call IDs found in interval-only register: {previous_id_match_count}",
        f"Previous call IDs not found in interval-only register: {missing_previous_ids}",
        "",
        "INVESTIGATION PRINCIPLES",
        "- Every canonical interval is retained; no deletion or winsorization is performed.",
        "- P95 and IQR thresholds are statistical review flags, not causal classifications.",
        "- Port-pair and vessel recurrence are descriptive evidence only.",
        "- The current fields do not identify sailing, anchorage, waiting, operational, or data-gap components.",
        "- No schedule slack or operational recovery is approved.",
        "- No physical route or actual Strait of Hormuz transit is established.",
        "",
        f"Validation checks passed: {int(checks_df['Passed'].sum())}/{len(checks_df)}",
        f"Validation checks failed: {len(failed)}",
        "",
        "FAILED CHECKS",
        "None." if failed.empty else "\n".join(
            f"- {r.Check_ID}: observed={r.Observed}; expected={r.Expected}"
            for r in failed.itertuples(index=False)
        ),
        "",
        "OUTPUT FILES",
    ]
    report_lines.extend(f"- outputs/tables/{name}" for name in outputs)
    report_lines.append("- outputs/reports/79_long_interval_record_level_investigation_report.txt")
    report_path = reports / "79_long_interval_record_level_investigation_report.txt"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print("\n".join(report_lines))
    if not failed.empty:
        print("\nFAILED: inspect Script79 outputs before interpretation.", file=sys.stderr)
        return 2
    print("\nSUCCESS: Script79 long-interval investigation completed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(1)
