#!/usr/bin/env python3
"""
SCRIPT 82 — RAW PORT-SCHEDULE WORKBOOK LINKAGE AND INTERMEDIATE-EVENT AUDIT

Targeted follow-up to Script81. Inspects data/raw/Combined_Port_Schedules.xlsx,
which Script81's schema heuristic did not properly identify because the raw
workbook uses "IMO Number" and contains multiple planned/estimated/actual
timestamp columns.

The script:
* reads all workbook sheets and records their schemas;
* normalises numeric/text IMO values safely;
* links the 23 Script80 long-interval records to raw workbook rows by IMO,
  port, and actual arrival/departure timestamps;
* searches for same-vessel raw workbook events between each interval's
  previous departure and current arrival;
* reports boundary matches and intermediate event candidates separately.

Research safeguards:
* A row match is not proof of source-provider authenticity.
* Intermediate records are candidates, not proof that an interval is invalid.
* No schedule interval is altered, removed, shortened, or reclassified.
* Planned/estimated timestamps are not substituted for actual timestamps.
* No sailing time, schedule slack, recovery, physical route, or Hormuz transit
  is inferred.

Run from project root:
    python src/82_raw_port_schedule_workbook_linkage_and_intermediate_event_audit.py

Inputs:
    data/raw/Combined_Port_Schedules.xlsx
    outputs/tables/80_long_interval_source_review_queue.csv
    outputs/tables/79_long_interval_record_investigation_register.csv

Outputs:
    outputs/tables/82_raw_workbook_sheet_inventory.csv
    outputs/tables/82_long_interval_raw_boundary_linkage.csv
    outputs/tables/82_intermediate_event_candidates.csv
    outputs/tables/82_raw_workbook_vessel_coverage.csv
    outputs/tables/82_validation_checks.csv
    outputs/reports/82_raw_port_schedule_workbook_linkage_and_intermediate_event_audit.txt
"""

from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np
import re
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
RAW_FILE = ROOT / "data" / "raw" / "Combined_Port_Schedules.xlsx"
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"
REVIEW_FILE = TABLES / "80_long_interval_source_review_queue.csv"
SCRIPT79_FILE = TABLES / "79_long_interval_record_investigation_register.csv"

OUT_SHEETS = TABLES / "82_raw_workbook_sheet_inventory.csv"
OUT_BOUNDARY = TABLES / "82_long_interval_raw_boundary_linkage.csv"
OUT_EVENTS = TABLES / "82_intermediate_event_candidates.csv"
OUT_COVERAGE = TABLES / "82_raw_workbook_vessel_coverage.csv"
OUT_CHECKS = TABLES / "82_validation_checks.csv"
OUT_REPORT = REPORTS / "82_raw_port_schedule_workbook_linkage_and_intermediate_event_audit.txt"

TOL_HOURS = 0.02

def norm_imo(value):
    if pd.isna(value):
        return None
    s = str(value).strip()
    if not s:
        return None
    # Excel often stores IMO as numeric, e.g. 9525912.0.
    if re.fullmatch(r"\d+\.0+", s):
        s = s.split(".")[0]
    digits = re.sub(r"\D", "", s)
    return digits if digits else s.upper()

def norm_text(value):
    if pd.isna(value):
        return None
    return str(value).strip().upper()

def find_col(columns, exact_options, contains_options=()):
    norm = {re.sub(r"[^a-z0-9]+", "_", str(c).lower()).strip("_"): c for c in columns}
    for option in exact_options:
        if option in norm:
            return norm[option]
    matches = []
    for c in columns:
        n = re.sub(r"[^a-z0-9]+", "_", str(c).lower()).strip("_")
        if any(token in n for token in contains_options):
            matches.append(c)
    return matches[0] if len(matches) == 1 else None

def utc(series):
    return pd.to_datetime(series, errors="coerce", utc=True)

def check(rows, cid, description, observed, expected, passed):
    rows.append({"Check_ID": cid, "Description": description, "Observed": observed,
                 "Expected": expected, "Status": "PASS" if bool(passed) else "FAIL"})

def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    for p in (RAW_FILE, REVIEW_FILE, SCRIPT79_FILE):
        if not p.exists():
            raise FileNotFoundError(f"Required input not found: {p}")

    review = pd.read_csv(REVIEW_FILE, low_memory=False)
    script79 = pd.read_csv(SCRIPT79_FILE, low_memory=False)
    if len(review) != 23:
        raise ValueError(f"Expected 23 Script80 review records; found {len(review)}")
    required_79 = [
        "Simulation_Record_ID", "IMO_Normalised", "Actual_Arrival_UTC",
        "Previous_Departure_UTC", "Previous_Simulation_Record_ID",
    ]
    missing_79 = [c for c in required_79 if c not in script79.columns]
    if missing_79:
        raise ValueError(f"Script79 interval register missing required columns: {missing_79}")
    if script79["Simulation_Record_ID"].duplicated().any():
        duplicate_count = int(script79["Simulation_Record_ID"].duplicated(keep=False).sum())
        raise ValueError(
            "Script79 interval register is not one row per call ID; "
            f"{duplicate_count} duplicate-key rows found. Resolve the canonical row "
            "before proceeding; do not silently drop duplicates."
        )
    # Script80 deliberately contains lineage checks but not the raw boundary
    # timestamps. Script79's canonical record-level investigation register
    # retains both timestamps, so join it explicitly by current call ID.
    boundary_fields = script79[required_79].copy()
    review = review.merge(
        boundary_fields,
        on="Simulation_Record_ID",
        how="left",
        validate="one_to_one",
        suffixes=("", "_Script79"),
    )
    if review["Previous_Departure_UTC"].isna().any() or review["Actual_Arrival_UTC"].isna().any():
        raise ValueError("One or more Script80 review records could not retrieve interval boundary timestamps from Script79.")
    if (review["IMO_Normalised"].astype("string") !=
        review["IMO_Normalised_Script79"].astype("string")).any():
        raise ValueError("IMO mismatch between Script80 review queue and Script79 interval register.")
    if (review["Previous_Simulation_Record_ID"].astype("string") !=
        review["Previous_Simulation_Record_ID_Script79"].astype("string")).any():
        raise ValueError("Previous call ID mismatch between Script80 and Script79.")

    xls = pd.ExcelFile(RAW_FILE)
    sheet_inventory, raw_parts = [], []
    for sheet in xls.sheet_names:
        df = pd.read_excel(RAW_FILE, sheet_name=sheet)
        sheet_inventory.append({
            "Workbook": str(RAW_FILE.relative_to(ROOT)),
            "Sheet_Name": sheet,
            "Row_Count": len(df),
            "Column_Count": len(df.columns),
            "Columns": " | ".join(map(str, df.columns)),
        })
        if len(df.columns):
            df = df.copy()
            df["_Workbook_Sheet"] = sheet
            df["_Workbook_Row_Number_Excel_Header_Row_1"] = np.arange(len(df)) + 2
            raw_parts.append(df)

    if not raw_parts:
        raise ValueError("No non-empty workbook sheets found.")
    raw = pd.concat(raw_parts, ignore_index=True, sort=False)

    imo_col = find_col(raw.columns, ["imo_number", "imo", "vessel_imo"], ["imo"])
    port_col = find_col(raw.columns, ["un_location_code", "unlocode", "port_code", "port"])
    actual_arr_col = find_col(raw.columns, ["actual_arrival"], ["actual_arrival"])
    actual_dep_col = find_col(raw.columns, ["actual_departure"], ["actual_departure"])
    if not all([imo_col, port_col, actual_arr_col, actual_dep_col]):
        raise ValueError(
            "Could not unambiguously identify IMO, port, actual arrival and actual "
            f"actual departure columns. Detected: IMO={imo_col}, port={port_col}, "
            f"arrival={actual_arr_col}, departure={actual_dep_col}. "
            f"Available columns={list(raw.columns)}"
        )

    raw["_IMO_KEY"] = raw[imo_col].map(norm_imo)
    raw["_PORT_KEY"] = raw[port_col].map(norm_text)
    raw["_ACTUAL_ARRIVAL"] = utc(raw[actual_arr_col])
    raw["_ACTUAL_DEPARTURE"] = utc(raw[actual_dep_col])

    for c in ["Simulation_Record_ID", "Previous_Simulation_Record_ID",
              "IMO_Normalised", "Previous_Port", "Current_Port"]:
        if c not in review.columns:
            raise ValueError(f"Script80 review queue missing {c}")

    boundary_rows, event_rows = [], []
    for _, r in review.iterrows():
        imo = norm_imo(r["IMO_Normalised"])
        prev_port = norm_text(r["Previous_Port"])
        curr_port = norm_text(r["Current_Port"])
        prev_dep = pd.to_datetime(r["Previous_Departure_UTC"], utc=True, errors="coerce")
        curr_arr = pd.to_datetime(r["Actual_Arrival_UTC"], utc=True, errors="coerce")
        current_id = r["Simulation_Record_ID"]
        previous_id = r["Previous_Simulation_Record_ID"]

        vessel_rows = raw[raw["_IMO_KEY"] == imo].copy()
        prev_candidates = vessel_rows[vessel_rows["_PORT_KEY"] == prev_port].copy()
        curr_candidates = vessel_rows[vessel_rows["_PORT_KEY"] == curr_port].copy()

        def nearest_match(candidates, target, col):
            if pd.isna(target) or candidates.empty:
                return None, np.nan
            valid = candidates[candidates[col].notna()].copy()
            if valid.empty:
                return None, np.nan
            valid["_DIFF_H"] = (valid[col] - target).dt.total_seconds().abs() / 3600
            best_idx = valid["_DIFF_H"].idxmin()
            return valid.loc[best_idx], float(valid.loc[best_idx, "_DIFF_H"])

        prev_row, prev_diff = nearest_match(prev_candidates, prev_dep, "_ACTUAL_DEPARTURE")
        curr_row, curr_diff = nearest_match(curr_candidates, curr_arr, "_ACTUAL_ARRIVAL")
        prev_match = prev_row is not None and prev_diff <= TOL_HOURS
        curr_match = curr_row is not None and curr_diff <= TOL_HOURS

        # Intermediate event candidates are raw rows for the same vessel whose
        # actual arrival or departure falls strictly inside the elapsed interval.
        if pd.notna(prev_dep) and pd.notna(curr_arr) and curr_arr >= prev_dep:
            inside = vessel_rows[
                ((vessel_rows["_ACTUAL_ARRIVAL"] > prev_dep) &
                 (vessel_rows["_ACTUAL_ARRIVAL"] < curr_arr)) |
                ((vessel_rows["_ACTUAL_DEPARTURE"] > prev_dep) &
                 (vessel_rows["_ACTUAL_DEPARTURE"] < curr_arr))
            ].copy()
        else:
            inside = vessel_rows.iloc[0:0].copy()

        # Exclude rows that are simply the previous/current boundary matches.
        boundary_indices = set()
        if prev_row is not None:
            boundary_indices.add(prev_row.name)
        if curr_row is not None:
            boundary_indices.add(curr_row.name)
        inside = inside[~inside.index.isin(boundary_indices)]

        boundary_rows.append({
            "Simulation_Record_ID": current_id,
            "Previous_Simulation_Record_ID": previous_id,
            "IMO_Normalised": r["IMO_Normalised"],
            "Previous_Port": r["Previous_Port"],
            "Current_Port": r["Current_Port"],
            "Observed_Inter_Call_Elapsed_Hours": r["Observed_Inter_Call_Elapsed_Hours"],
            "Raw_Workbook_Rows_For_Vessel": len(vessel_rows),
            "Previous_Port_Raw_Row_Candidates": len(prev_candidates),
            "Current_Port_Raw_Row_Candidates": len(curr_candidates),
            "Previous_Departure_Raw_Match": bool(prev_match),
            "Previous_Departure_Nearest_Difference_Hours": prev_diff,
            "Previous_Departure_Raw_Sheet": prev_row["_Workbook_Sheet"] if prev_row is not None else pd.NA,
            "Previous_Departure_Raw_Excel_Row": prev_row["_Workbook_Row_Number_Excel_Header_Row_1"] if prev_row is not None else pd.NA,
            "Current_Arrival_Raw_Match": bool(curr_match),
            "Current_Arrival_Nearest_Difference_Hours": curr_diff,
            "Current_Arrival_Raw_Sheet": curr_row["_Workbook_Sheet"] if curr_row is not None else pd.NA,
            "Current_Arrival_Raw_Excel_Row": curr_row["_Workbook_Row_Number_Excel_Header_Row_1"] if curr_row is not None else pd.NA,
            "Intermediate_Raw_Event_Row_Candidates": len(inside),
            "Intermediate_Raw_Event_Ports": " | ".join(sorted(set(inside["_PORT_KEY"].dropna()))) if len(inside) else "",
            "Boundary_Linkage_Status": (
                "BOTH_BOUNDARIES_MATCH_RAW_WORKBOOK"
                if prev_match and curr_match else
                "CURRENT_BOUNDARY_ONLY_MATCH"
                if curr_match else
                "PREVIOUS_BOUNDARY_ONLY_MATCH"
                if prev_match else
                "NO_EXACT_BOUNDARY_MATCH"
            ),
            "Source_Authenticity_Verified": False,
            "Interval_Cause_Identified": False,
            "Schedule_Slack_Approved": False,
            "Recovery_Approved": False,
        })

        for _, e in inside.iterrows():
            event_rows.append({
                "Current_Interval_Record_ID": current_id,
                "Previous_Interval_Record_ID": previous_id,
                "IMO_Normalised": r["IMO_Normalised"],
                "Interval_Start_Previous_Departure_UTC": prev_dep,
                "Interval_End_Current_Arrival_UTC": curr_arr,
                "Candidate_Intermediate_Port": e[port_col],
                "Candidate_Intermediate_Actual_Arrival_UTC": e["_ACTUAL_ARRIVAL"],
                "Candidate_Intermediate_Actual_Departure_UTC": e["_ACTUAL_DEPARTURE"],
                "Candidate_Workbook_Sheet": e["_Workbook_Sheet"],
                "Candidate_Workbook_Excel_Row": e["_Workbook_Row_Number_Excel_Header_Row_1"],
                "Candidate_Row_Inside_Elapsed_Interval": True,
                "Interpretation": "RAW_WORKBOOK_EVENT_CANDIDATE_REQUIRES_RECORD_LEVEL_REVIEW",
            })

    boundary = pd.DataFrame(boundary_rows)
    events = pd.DataFrame(event_rows)
    coverage = (
        raw.dropna(subset=["_IMO_KEY"]).groupby("_IMO_KEY")
        .agg(Raw_Workbook_Row_Count=("_IMO_KEY", "size"),
             Distinct_Port_Count=("_PORT_KEY", "nunique"),
             First_Actual_Arrival_UTC=("_ACTUAL_ARRIVAL", "min"),
             Last_Actual_Departure_UTC=("_ACTUAL_DEPARTURE", "max"))
        .reset_index().rename(columns={"_IMO_KEY": "IMO_Normalised"})
    )
    target_imo_set = set(review["IMO_Normalised"].map(norm_imo).dropna())
    coverage = coverage[coverage["IMO_Normalised"].isin(target_imo_set)].copy()

    checks = []
    check(checks, "C01", "All 23 Script80 long-interval records processed", len(boundary), 23, len(boundary) == 23)
    check(checks, "C02", "Every review vessel represented in boundary register",
          boundary["IMO_Normalised"].map(norm_imo).nunique(), review["IMO_Normalised"].map(norm_imo).nunique(),
          boundary["IMO_Normalised"].map(norm_imo).nunique() == review["IMO_Normalised"].map(norm_imo).nunique())
    check(checks, "C03", "Boundary match flags are boolean and non-null",
          int(boundary[["Previous_Departure_Raw_Match", "Current_Arrival_Raw_Match"]].notna().all(axis=1).sum()),
          len(boundary), boundary[["Previous_Departure_Raw_Match", "Current_Arrival_Raw_Match"]].notna().all().all())
    check(checks, "C04", "No source authenticity or operational approvals assigned",
          int(boundary[["Source_Authenticity_Verified", "Interval_Cause_Identified",
                        "Schedule_Slack_Approved", "Recovery_Approved"]].to_numpy().sum()),
          0, not boundary[["Source_Authenticity_Verified", "Interval_Cause_Identified",
                           "Schedule_Slack_Approved", "Recovery_Approved"]].to_numpy().any())
    check(checks, "C05", "Intermediate event rows are strictly inside interval bounds",
          int(events["Candidate_Row_Inside_Elapsed_Interval"].sum()) if len(events) else 0,
          len(events), not len(events) or events["Candidate_Row_Inside_Elapsed_Interval"].all())

    checks_df = pd.DataFrame(checks)
    pd.DataFrame(sheet_inventory).to_csv(OUT_SHEETS, index=False)
    boundary.to_csv(OUT_BOUNDARY, index=False)
    events.to_csv(OUT_EVENTS, index=False)
    coverage.to_csv(OUT_COVERAGE, index=False)
    checks_df.to_csv(OUT_CHECKS, index=False)

    passed = int(checks_df["Status"].eq("PASS").sum())
    failed = int(checks_df["Status"].eq("FAIL").sum())
    report = [
        "SCRIPT 82 — RAW PORT-SCHEDULE WORKBOOK LINKAGE AND INTERMEDIATE-EVENT AUDIT",
        "=" * 78,
        f"Workbook: {RAW_FILE.relative_to(ROOT)}",
        f"Sheets inspected: {len(sheet_inventory)}",
        f"Total raw workbook rows scanned: {len(raw)}",
        f"Detected fields: IMO={imo_col}; port={port_col}; actual arrival={actual_arr_col}; actual departure={actual_dep_col}",
        f"Long intervals assessed: {len(boundary)}",
        f"Distinct long-interval vessels: {boundary['IMO_Normalised'].map(norm_imo).nunique()}",
        "Boundary timestamps sourced from Script79 canonical interval register and joined by Simulation_Record_ID.",
        f"Previous departure exact boundary matches (<= {TOL_HOURS}h): {int(boundary['Previous_Departure_Raw_Match'].sum())}",
        f"Current arrival exact boundary matches (<= {TOL_HOURS}h): {int(boundary['Current_Arrival_Raw_Match'].sum())}",
        f"Both-boundary matches: {int(boundary['Boundary_Linkage_Status'].eq('BOTH_BOUNDARIES_MATCH_RAW_WORKBOOK').sum())}",
        f"Intervals with intermediate same-vessel raw row candidates: {int(boundary['Intermediate_Raw_Event_Row_Candidates'].gt(0).sum())}",
        f"Intermediate row candidates: {len(events)}",
        "",
        "INTERPRETATION",
        "- Matching rows establish record-level overlap with the workbook, not source-provider authenticity.",
        "- The workbook is located under data/raw/, but its original provider, extraction date, and transformation history must still be documented.",
        "- Only actual arrival/departure columns are used; planned and estimated timestamps are not substituted.",
        "- Intermediate rows are candidate records for manual review; they do not automatically invalidate a long interval.",
        "- No causal classification, schedule slack, recovery, or empirical parameter approval is made.",
        "- No physical route or actual Strait of Hormuz transit is established.",
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
        f"- {OUT_SHEETS.relative_to(ROOT)}",
        f"- {OUT_BOUNDARY.relative_to(ROOT)}",
        f"- {OUT_EVENTS.relative_to(ROOT)}",
        f"- {OUT_COVERAGE.relative_to(ROOT)}",
        f"- {OUT_CHECKS.relative_to(ROOT)}",
        f"- {OUT_REPORT.relative_to(ROOT)}",
    ]
    OUT_REPORT.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    if failed:
        raise SystemExit("Script82 validation failed.")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
