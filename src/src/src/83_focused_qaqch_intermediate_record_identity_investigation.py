#!/usr/bin/env python3
"""
SCRIPT 83 — FOCUSED QAQCH INTERMEDIATE-RECORD IDENTITY INVESTIGATION

Purpose
-------
Investigate the same-vessel intermediate rows identified by Script82 without
changing the canonical schedule. The script uses the Script82 candidate and
boundary registers to identify the target interval, then extracts every raw
workbook row for that vessel whose actual arrival/departure touches or falls
inside the interval.

The investigation is deliberately descriptive:
* preserves all workbook columns in the extracted raw-row register;
* compares IMO, port, actual timestamps, voyage/reference identifiers and
  planned/estimated timestamps where available;
* checks duplicate-like records and repeated actual-arrival timestamps;
* does not decide that a candidate is a genuine omitted port call.

Run from project root:
    python src/83_focused_qachq_intermediate_record_identity_investigation.py

Inputs:
    data/raw/Combined_Port_Schedules.xlsx
    outputs/tables/82_intermediate_event_candidates.csv
    outputs/tables/82_long_interval_raw_boundary_linkage.csv

Outputs:
    outputs/tables/83_target_interval_investigation_register.csv
    outputs/tables/83_raw_vessel_event_extract.csv
    outputs/tables/83_candidate_record_comparison.csv
    outputs/tables/83_validation_checks.csv
    outputs/reports/83_focused_qachq_intermediate_record_identity_investigation.txt

No upstream data are modified.
"""

from __future__ import annotations
from pathlib import Path
import re
import sys
import traceback
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW_FILE = ROOT / "data" / "raw" / "Combined_Port_Schedules.xlsx"
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"

CANDIDATES_FILE = TABLES / "82_intermediate_event_candidates.csv"
BOUNDARY_FILE = TABLES / "82_long_interval_raw_boundary_linkage.csv"

OUT_TARGET = TABLES / "83_target_interval_investigation_register.csv"
OUT_EXTRACT = TABLES / "83_raw_vessel_event_extract.csv"
OUT_COMPARE = TABLES / "83_candidate_record_comparison.csv"
OUT_CHECKS = TABLES / "83_validation_checks.csv"
OUT_REPORT = REPORTS / "83_focused_qachq_intermediate_record_identity_investigation.txt"

TOL_HOURS = 0.02


def norm_imo(value):
    if pd.isna(value):
        return None
    s = str(value).strip()
    if re.fullmatch(r"\d+\.0+", s):
        s = s.split(".")[0]
    digits = re.sub(r"\D", "", s)
    return digits or s.upper() or None


def norm_text(value):
    if pd.isna(value):
        return None
    return str(value).strip().upper()


def norm_col(value):
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def find_col(columns, exact=(), contains=()):
    mapping = {norm_col(c): c for c in columns}
    for name in exact:
        if name in mapping:
            return mapping[name]
    found = [c for c in columns if any(token in norm_col(c) for token in contains)]
    return found[0] if len(found) == 1 else None


def to_utc(value):
    return pd.to_datetime(value, errors="coerce", utc=True)


def add_check(rows, cid, description, observed, expected, passed):
    rows.append({
        "Check_ID": cid,
        "Description": description,
        "Observed": observed,
        "Expected": expected,
        "Status": "PASS" if bool(passed) else "FAIL",
    })


def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    for p in (RAW_FILE, CANDIDATES_FILE, BOUNDARY_FILE):
        if not p.exists():
            raise FileNotFoundError(f"Required input not found: {p}")

    candidates = pd.read_csv(CANDIDATES_FILE, low_memory=False)
    boundary = pd.read_csv(BOUNDARY_FILE, low_memory=False)
    if candidates.empty:
        raise ValueError("Script82 intermediate-event candidate register is empty; no focused anomaly to investigate.")

    required_c = [
        "Current_Interval_Record_ID", "Previous_Interval_Record_ID", "IMO_Normalised",
        "Interval_Start_Previous_Departure_UTC", "Interval_End_Current_Arrival_UTC",
        "Candidate_Intermediate_Port", "Candidate_Intermediate_Actual_Arrival_UTC",
        "Candidate_Intermediate_Actual_Departure_UTC", "Candidate_Workbook_Sheet",
        "Candidate_Workbook_Excel_Row",
    ]
    missing = [c for c in required_c if c not in candidates.columns]
    if missing:
        raise ValueError(f"Script82 candidate register missing required fields: {missing}")

    # One target interval should be represented by the candidate rows.
    interval_ids = candidates["Current_Interval_Record_ID"].dropna().astype(str).unique()
    if len(interval_ids) != 1:
        raise ValueError(
            "Expected one anomalous interval for focused review, found "
            f"{len(interval_ids)}: {list(interval_ids)}. Do not silently merge anomalies."
        )
    current_id = interval_ids[0]
    b = boundary[boundary["Simulation_Record_ID"].astype(str) == current_id]
    if len(b) != 1:
        raise ValueError(f"Expected exactly one Script82 boundary row for {current_id}; found {len(b)}")
    b = b.iloc[0]

    imo = norm_imo(b["IMO_Normalised"])
    start = to_utc(b["Previous_Departure_UTC"]) if "Previous_Departure_UTC" in b else to_utc(
        candidates.iloc[0]["Interval_Start_Previous_Departure_UTC"]
    )
    end = to_utc(b["Current_Arrival_UTC"]) if "Current_Arrival_UTC" in b else to_utc(
        candidates.iloc[0]["Interval_End_Current_Arrival_UTC"]
    )
    if pd.isna(start) or pd.isna(end) or end <= start:
        raise ValueError(f"Invalid target interval boundaries: start={start}, end={end}")

    sheet = str(candidates.iloc[0]["Candidate_Workbook_Sheet"])
    xls = pd.ExcelFile(RAW_FILE)
    if sheet not in xls.sheet_names:
        raise ValueError(f"Candidate worksheet {sheet!r} not found in raw workbook sheets {xls.sheet_names}")
    raw = pd.read_excel(RAW_FILE, sheet_name=sheet)
    raw["_Workbook_Sheet"] = sheet
    raw["_Workbook_Excel_Row"] = np.arange(len(raw)) + 2

    imo_col = find_col(raw.columns, exact=("imo_number", "imo"), contains=("imo",))
    port_col = find_col(raw.columns, exact=("un_location_code", "unlocode", "port_code"), contains=("un_location_code", "unlocode"))
    arr_col = find_col(raw.columns, exact=("actual_arrival",), contains=("actual_arrival",))
    dep_col = find_col(raw.columns, exact=("actual_departure",), contains=("actual_departure",))
    if not all((imo_col, port_col, arr_col, dep_col)):
        raise ValueError(f"Required raw columns not identified: IMO={imo_col}, port={port_col}, arrival={arr_col}, departure={dep_col}")

    raw["_IMO_KEY"] = raw[imo_col].map(norm_imo)
    raw["_PORT_KEY"] = raw[port_col].map(norm_text)
    raw["_ACTUAL_ARRIVAL_UTC"] = pd.to_datetime(raw[arr_col], errors="coerce", utc=True)
    raw["_ACTUAL_DEPARTURE_UTC"] = pd.to_datetime(raw[dep_col], errors="coerce", utc=True)

    vessel = raw[raw["_IMO_KEY"] == imo].copy()
    # Include rows with either actual arrival or departure inside the interval,
    # plus the exact boundary rows nearest the start and end.
    in_window = vessel[
        ((vessel["_ACTUAL_ARRIVAL_UTC"] >= start) & (vessel["_ACTUAL_ARRIVAL_UTC"] <= end)) |
        ((vessel["_ACTUAL_DEPARTURE_UTC"] >= start) & (vessel["_ACTUAL_DEPARTURE_UTC"] <= end))
    ].copy()

    def nearest_row(frame, col, target):
        valid = frame[frame[col].notna()].copy()
        if valid.empty:
            return None
        valid["_ABS_DIFF_H"] = (valid[col] - target).dt.total_seconds().abs() / 3600
        return valid.loc[valid["_ABS_DIFF_H"].idxmin()]

    prev_boundary = nearest_row(vessel, "_ACTUAL_DEPARTURE_UTC", start)
    curr_boundary = nearest_row(vessel, "_ACTUAL_ARRIVAL_UTC", end)
    boundary_indices = set()
    if prev_boundary is not None:
        boundary_indices.add(prev_boundary.name)
    if curr_boundary is not None:
        boundary_indices.add(curr_boundary.name)

    # Full source rows are retained, with audit columns appended.
    extract = in_window.copy()
    extract["Is_Previous_Boundary_Row"] = extract.index.isin(
        [prev_boundary.name] if prev_boundary is not None else []
    )
    extract["Is_Current_Boundary_Row"] = extract.index.isin(
        [curr_boundary.name] if curr_boundary is not None else []
    )
    extract["Is_Script82_Intermediate_Candidate_Row"] = extract["_Workbook_Excel_Row"].isin(
        pd.to_numeric(candidates["Candidate_Workbook_Excel_Row"], errors="coerce").dropna().astype(int)
    )
    extract["Hours_From_Previous_Departure_To_Actual_Arrival"] = (
        (extract["_ACTUAL_ARRIVAL_UTC"] - start).dt.total_seconds() / 3600
    )
    extract["Hours_From_Previous_Departure_To_Actual_Departure"] = (
        (extract["_ACTUAL_DEPARTURE_UTC"] - start).dt.total_seconds() / 3600
    )
    extract = extract.sort_values(
        ["_ACTUAL_ARRIVAL_UTC", "_ACTUAL_DEPARTURE_UTC", "_Workbook_Excel_Row"],
        na_position="last"
    )

    # Detect likely event-identification fields without asserting their meaning.
    voyage_cols = [c for c in raw.columns if any(t in norm_col(c) for t in
                   ("voyage", "call", "visit", "rotation", "reference", "sequence", "berth", "terminal", "status"))]
    compare_cols = list(dict.fromkeys(
        [imo_col, port_col, arr_col, dep_col] + voyage_cols
    ))
    compare_rows = []
    for _, c in candidates.iterrows():
        rownum = int(c["Candidate_Workbook_Excel_Row"])
        rr = raw[raw["_Workbook_Excel_Row"] == rownum]
        if len(rr) != 1:
            raise ValueError(f"Candidate workbook row {rownum} resolves to {len(rr)} rows, expected one.")
        raw_row = rr.iloc[0]
        record = {
            "Current_Interval_Record_ID": current_id,
            "Candidate_Workbook_Excel_Row": rownum,
            "Candidate_Intermediate_Port": c["Candidate_Intermediate_Port"],
            "Candidate_Intermediate_Actual_Arrival_UTC": c["Candidate_Intermediate_Actual_Arrival_UTC"],
            "Candidate_Intermediate_Actual_Departure_UTC": c["Candidate_Intermediate_Actual_Departure_UTC"],
            "Same_IMO_As_Target_Vessel": norm_imo(raw_row[imo_col]) == imo,
            "Same_Port_As_Previous_Boundary": norm_text(raw_row[port_col]) == norm_text(b["Previous_Port"]),
            "Same_Port_As_Current_Boundary": norm_text(raw_row[port_col]) == norm_text(b["Current_Port"]),
            "Actual_Arrival_Inside_Interval": bool(pd.notna(raw_row["_ACTUAL_ARRIVAL_UTC"]) and start < raw_row["_ACTUAL_ARRIVAL_UTC"] < end),
            "Actual_Departure_Inside_Interval": bool(pd.notna(raw_row["_ACTUAL_DEPARTURE_UTC"]) and start < raw_row["_ACTUAL_DEPARTURE_UTC"] < end),
            "Potential_Duplicate_Actual_Arrival_Count": int(
                (raw["_IMO_KEY"].eq(imo) &
                 raw["_PORT_KEY"].eq(norm_text(raw_row[port_col])) &
                 raw["_ACTUAL_ARRIVAL_UTC"].eq(raw_row["_ACTUAL_ARRIVAL_UTC"])).sum()
            ) if pd.notna(raw_row["_ACTUAL_ARRIVAL_UTC"]) else 0,
            "Potential_Duplicate_Actual_Departure_Count": int(
                (raw["_IMO_KEY"].eq(imo) &
                 raw["_PORT_KEY"].eq(norm_text(raw_row[port_col])) &
                 raw["_ACTUAL_DEPARTURE_UTC"].eq(raw_row["_ACTUAL_DEPARTURE_UTC"])).sum()
            ) if pd.notna(raw_row["_ACTUAL_DEPARTURE_UTC"]) else 0,
            "Interpretation": "CANDIDATE_EVENT_REQUIRES_MANUAL_IDENTITY_AND_VOYAGE_REVIEW",
        }
        for col in compare_cols:
            record[f"Raw_{norm_col(col)}"] = raw_row[col]
        compare_rows.append(record)

    target = pd.DataFrame([{
        "Current_Interval_Record_ID": current_id,
        "Previous_Interval_Record_ID": b["Previous_Simulation_Record_ID"],
        "IMO_Normalised": b["IMO_Normalised"],
        "Previous_Port": b["Previous_Port"],
        "Current_Port": b["Current_Port"],
        "Interval_Start_Previous_Departure_UTC": start,
        "Interval_End_Current_Arrival_UTC": end,
        "Observed_Inter_Call_Elapsed_Hours": b["Observed_Inter_Call_Elapsed_Hours"],
        "Raw_Workbook_Sheet": sheet,
        "Raw_Workbook_Rows_For_Vessel": len(vessel),
        "Raw_Workbook_Rows_Touching_Interval": len(in_window),
        "Script82_Intermediate_Candidate_Rows": len(candidates),
        "Voyage_Or_Event_Identifier_Columns_Found": " | ".join(map(str, voyage_cols)),
        "Raw_Workbook_Provider_Verified": False,
        "Intermediate_Event_Identity_Resolved": False,
        "Canonical_Schedule_Change_Approved": False,
    }])

    checks = []
    add_check(checks, "C01", "Exactly one target interval investigated", len(target), 1, len(target) == 1)
    add_check(checks, "C02", "All Script82 candidate rows represented in comparison",
              len(compare_rows), len(candidates), len(compare_rows) == len(candidates))
    add_check(checks, "C03", "All Script82 candidate workbook row numbers resolve uniquely",
              len(compare_rows), len(candidates), len(compare_rows) == len(candidates))
    add_check(checks, "C04", "Extract contains only target vessel IMO",
              int(extract["_IMO_KEY"].eq(imo).sum()), len(extract),
              extract["_IMO_KEY"].eq(imo).all())
    add_check(checks, "C05", "No schedule modifications or approvals assigned",
              int(target[["Raw_Workbook_Provider_Verified", "Intermediate_Event_Identity_Resolved",
                          "Canonical_Schedule_Change_Approved"]].to_numpy().sum()),
              0, not target[["Raw_Workbook_Provider_Verified", "Intermediate_Event_Identity_Resolved",
                             "Canonical_Schedule_Change_Approved"]].to_numpy().any())

    compare = pd.DataFrame(compare_rows)
    checks_df = pd.DataFrame(checks)
    target.to_csv(OUT_TARGET, index=False)
    extract.to_csv(OUT_EXTRACT, index=False)
    compare.to_csv(OUT_COMPARE, index=False)
    checks_df.to_csv(OUT_CHECKS, index=False)

    passed = int(checks_df["Status"].eq("PASS").sum())
    failed = int(checks_df["Status"].eq("FAIL").sum())
    report = [
        "SCRIPT 83 — FOCUSED QAQCH INTERMEDIATE-RECORD IDENTITY INVESTIGATION",
        "=" * 78,
        f"Target current call ID: {current_id}",
        f"Previous call ID: {b['Previous_Simulation_Record_ID']}",
        f"Vessel IMO: {imo}",
        f"Port sequence: {b['Previous_Port']} -> {b['Current_Port']}",
        f"Interval start: {start}",
        f"Interval end: {end}",
        f"Observed elapsed hours: {b['Observed_Inter_Call_Elapsed_Hours']}",
        f"Raw workbook rows for target vessel: {len(vessel)}",
        f"Rows with actual arrival/departure within interval: {len(in_window)}",
        f"Script82 candidate rows re-inspected: {len(candidates)}",
        f"Potential voyage/event identifier columns: {voyage_cols}",
        "",
        "RESEARCH INTERPRETATION",
        "- The extract is a faithful copy of raw workbook rows selected by vessel and actual-time window.",
        "- Workbook row numbers are Excel row numbers including the header row.",
        "- Matching IMO, port and timestamps do not establish that a row is a distinct port call.",
        "- Voyage/reference/status fields require interpretation against the workbook's data dictionary and source-provider documentation.",
        "- Planned/estimated timestamps are displayed only as raw fields and are not used to replace actual timestamps.",
        "- No canonical schedule modification, causal classification, schedule-slack approval, or recovery approval is made.",
        "",
        f"Validation checks passed: {passed}/{len(checks_df)}",
        f"Validation checks failed: {failed}",
        "",
        "CHECK RESULTS",
    ]
    for _, r in checks_df.iterrows():
        report.append(f"{r['Check_ID']} [{r['Status']}] {r['Description']} — observed={r['Observed']}, expected={r['Expected']}")
    report += [
        "",
        "OUTPUT FILES",
        f"- {OUT_TARGET.relative_to(ROOT)}",
        f"- {OUT_EXTRACT.relative_to(ROOT)}",
        f"- {OUT_COMPARE.relative_to(ROOT)}",
        f"- {OUT_CHECKS.relative_to(ROOT)}",
        f"- {OUT_REPORT.relative_to(ROOT)}",
    ]
    OUT_REPORT.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    if failed:
        raise SystemExit("Script83 validation failed.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
