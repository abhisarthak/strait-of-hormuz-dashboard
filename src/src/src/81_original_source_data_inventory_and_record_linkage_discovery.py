#!/usr/bin/env python3
"""
SCRIPT 81 — ORIGINAL SOURCE DATA INVENTORY AND RECORD-LINKAGE DISCOVERY

Read-only discovery of source-like files under data/ and assessment of whether
they can be linked to the canonical 604-call schedule and Script80's long-
interval review queue.

This script does NOT assume that a file is an original vendor extract merely
because it contains vessel identifiers or timestamps. It records file paths,
schemas, candidate identifier/date/port columns, and observed overlaps.
Manual source-provenance review remains mandatory.

Run from project root:
    python src/81_original_source_data_inventory_and_record_linkage_discovery.py

Expected inputs:
    data/simulation_inputs/19_historical_arrival_schedule.csv
    outputs/tables/80_interval_source_provenance_register.csv
    outputs/tables/80_long_interval_source_review_queue.csv

Outputs:
    outputs/tables/81_source_file_inventory.csv
    outputs/tables/81_source_candidate_assessment.csv
    outputs/tables/81_long_interval_record_linkage_candidates.csv
    outputs/tables/81_source_discovery_checks.csv
    outputs/reports/81_original_source_data_inventory_and_record_linkage_report.txt
"""

from __future__ import annotations

from pathlib import Path
import hashlib
import sys
import traceback
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"

SCHEDULE_PATH = DATA_DIR / "simulation_inputs" / "19_historical_arrival_schedule.csv"
PROVENANCE_PATH = TABLES / "80_interval_source_provenance_register.csv"
REVIEW_PATH = TABLES / "80_long_interval_source_review_queue.csv"

OUT_INVENTORY = TABLES / "81_source_file_inventory.csv"
OUT_CANDIDATES = TABLES / "81_source_candidate_assessment.csv"
OUT_LINKS = TABLES / "81_long_interval_record_linkage_candidates.csv"
OUT_CHECKS = TABLES / "81_source_discovery_checks.csv"
OUT_REPORT = REPORTS / "81_original_source_data_inventory_and_record_linkage_report.txt"

SUPPORTED = {".csv", ".xlsx", ".xls", ".parquet"}
MAX_FILE_MB = 250

ALIASES = {
    "imo": ["imo_normalised", "imo_normalized", "imo", "imo_number", "vessel_imo"],
    "call_id": ["simulation_record_id", "call_id", "port_call_id", "record_id", "schedule_id"],
    "port": ["unlocode_normalised", "unlocode_normalized", "unlocode", "port_code", "port", "port_name"],
    "arrival": ["actual_arrival_utc", "arrival_utc", "arrival_time", "ata", "arrival_date"],
    "departure": ["actual_departure_utc", "departure_utc", "departure_time", "atd", "departure_date"],
    "source_row": ["schedule_source_row", "source_row", "source_row_id", "original_row", "row_number", "source_record_number"],
}

def norm_col(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value)).strip("_")

def detect_column(columns, kind):
    lookup = {norm_col(c): c for c in columns}
    for alias in ALIASES[kind]:
        if alias in lookup:
            return lookup[alias]
    # Conservative fallback: only accept unambiguous names containing key tokens.
    candidates = []
    for c in columns:
        n = norm_col(c)
        if kind == "imo" and "imo" in n:
            candidates.append(c)
        elif kind == "arrival" and "arrival" in n:
            candidates.append(c)
        elif kind == "departure" and "departure" in n:
            candidates.append(c)
        elif kind == "port" and ("unlocode" in n or n.endswith("_port")):
            candidates.append(c)
        elif kind == "call_id" and ("record_id" in n or n.endswith("_call_id")):
            candidates.append(c)
        elif kind == "source_row" and ("source_row" in n or "row_number" in n):
            candidates.append(c)
    return candidates[0] if len(candidates) == 1 else None

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load_file(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            return pd.read_csv(path, low_memory=False)
        except UnicodeDecodeError:
            return pd.read_csv(path, low_memory=False, encoding="latin-1")
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported format: {suffix}")

def clean_set(series):
    return set(series.dropna().astype(str).str.strip().str.upper())

def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    for p in (SCHEDULE_PATH, PROVENANCE_PATH, REVIEW_PATH):
        if not p.exists():
            raise FileNotFoundError(f"Required input not found: {p}")

    schedule = pd.read_csv(SCHEDULE_PATH, low_memory=False)
    provenance = pd.read_csv(PROVENANCE_PATH, low_memory=False)
    review = pd.read_csv(REVIEW_PATH, low_memory=False)

    required = ["Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised",
                "Actual_Arrival_UTC", "Actual_Departure_UTC", "Schedule_Source_Row"]
    missing = [c for c in required if c not in schedule.columns]
    if missing:
        raise ValueError(f"Script19 schedule missing columns: {missing}")
    for c in ["Simulation_Record_ID", "IMO_Normalised"]:
        if c not in provenance.columns:
            raise ValueError(f"Script80 provenance missing {c}")
    if "Simulation_Record_ID" not in review.columns:
        raise ValueError("Script80 review queue missing Simulation_Record_ID")

    target_imos = clean_set(review["IMO_Normalised"])
    target_ids = clean_set(review["Simulation_Record_ID"])
    target_ports = clean_set(review["Current_Port"]) if "Current_Port" in review.columns else set()
    schedule_imos = clean_set(schedule["IMO_Normalised"])
    schedule_ids = clean_set(schedule["Simulation_Record_ID"])

    files = sorted(p for p in DATA_DIR.rglob("*")
                   if p.is_file() and p.suffix.lower() in SUPPORTED)
    inventory_rows, candidate_rows, link_rows = [], [], []

    for path in files:
        rel = str(path.relative_to(ROOT))
        size_mb = path.stat().st_size / (1024 * 1024)
        base = {
            "File_Path": rel,
            "File_Name": path.name,
            "Extension": path.suffix.lower(),
            "Size_MB": round(size_mb, 3),
            "SHA256": sha256_file(path),
            "Scan_Status": "",
            "Row_Count": np.nan,
            "Column_Count": np.nan,
            "Columns": "",
            "Is_Canonical_Simulation_Input": path.resolve() == SCHEDULE_PATH.resolve(),
        }
        if size_mb > MAX_FILE_MB:
            base["Scan_Status"] = f"SKIPPED_SIZE_OVER_{MAX_FILE_MB}MB"
            inventory_rows.append(base)
            continue
        try:
            df = load_file(path)
            cols = list(df.columns)
            base.update({
                "Scan_Status": "SCANNED",
                "Row_Count": len(df),
                "Column_Count": len(cols),
                "Columns": " | ".join(map(str, cols)),
            })
        except Exception as exc:
            base["Scan_Status"] = f"READ_ERROR: {type(exc).__name__}: {exc}"
            inventory_rows.append(base)
            continue
        inventory_rows.append(base)

        detected = {k: detect_column(cols, k) for k in ALIASES}
        imo_col, id_col, port_col = detected["imo"], detected["call_id"], detected["port"]
        imo_overlap = id_overlap = port_overlap = 0
        if imo_col:
            imo_overlap = len(clean_set(df[imo_col]) & target_imos)
        if id_col:
            id_overlap = len(clean_set(df[id_col]) & target_ids)
        if port_col:
            port_overlap = len(clean_set(df[port_col]) & target_ports)

        candidate_score = sum([
            3 if imo_overlap else 0,
            5 if id_overlap else 0,
            1 if port_overlap else 0,
            1 if detected["arrival"] else 0,
            1 if detected["departure"] else 0,
            1 if detected["source_row"] else 0,
        ])
        if path.resolve() == SCHEDULE_PATH.resolve():
            classification = "CANONICAL_PROCESSED_SCHEDULE_NOT_ORIGINAL_SOURCE"
        elif "simulation_inputs" in path.parts:
            classification = "PROCESSED_SIMULATION_INPUT_CANDIDATE"
        elif candidate_score >= 6:
            classification = "HIGHER_LINKAGE_CANDIDATE_REQUIRES_PROVENANCE_REVIEW"
        elif candidate_score >= 3:
            classification = "PARTIAL_LINKAGE_CANDIDATE"
        else:
            classification = "NO_STRONG_LINKAGE_SIGNAL"

        candidate_rows.append({
            "File_Path": rel,
            "Row_Count": len(df),
            "Column_Count": len(cols),
            "IMO_Column": imo_col,
            "Call_ID_Column": id_col,
            "Port_Column": port_col,
            "Arrival_Column": detected["arrival"],
            "Departure_Column": detected["departure"],
            "Source_Row_Column": detected["source_row"],
            "Target_Long_Interval_IMO_Overlap_Count": imo_overlap,
            "Target_Long_Interval_Call_ID_Overlap_Count": id_overlap,
            "Target_Long_Interval_Port_Overlap_Count": port_overlap,
            "Linkage_Score_Heuristic_Not_Validation": candidate_score,
            "Candidate_Classification": classification,
        })

        # Emit record-level links only where a candidate contains target IMO
        # or call IDs. These are discovery hits, not accepted lineage.
        if imo_col or id_col:
            imo_values = df[imo_col].astype("string").str.strip().str.upper() if imo_col else pd.Series(pd.NA, index=df.index)
            id_values = df[id_col].astype("string").str.strip().str.upper() if id_col else pd.Series(pd.NA, index=df.index)
            mask = (imo_values.isin(target_imos) if imo_col else False) | (id_values.isin(target_ids) if id_col else False)
            hit = df.loc[mask]
            for idx, row in hit.iterrows():
                link_rows.append({
                    "Candidate_File_Path": rel,
                    "Candidate_DataFrame_Row_Index": idx,
                    "Candidate_IMO": row[imo_col] if imo_col else pd.NA,
                    "Candidate_Call_ID": row[id_col] if id_col else pd.NA,
                    "Candidate_Port": row[port_col] if port_col else pd.NA,
                    "Candidate_Arrival": row[detected["arrival"]] if detected["arrival"] else pd.NA,
                    "Candidate_Departure": row[detected["departure"]] if detected["departure"] else pd.NA,
                    "Candidate_Source_Row": row[detected["source_row"]] if detected["source_row"] else pd.NA,
                    "Call_ID_Overlap": bool(id_col and str(row[id_col]).strip().upper() in target_ids),
                    "IMO_Overlap": bool(imo_col and str(row[imo_col]).strip().upper() in target_imos),
                    "Linkage_Status": "DISCOVERY_HIT_REQUIRES_SOURCE_PROVENANCE_VERIFICATION",
                })

    inventory = pd.DataFrame(inventory_rows)
    candidates = pd.DataFrame(candidate_rows)
    links = pd.DataFrame(link_rows)

    checks = []
    def check(cid, desc, obs, exp, passed):
        checks.append({"Check_ID": cid, "Description": desc, "Observed": obs,
                       "Expected": exp, "Status": "PASS" if passed else "FAIL"})
    check("C01", "Canonical schedule contains 604 calls", len(schedule), 604, len(schedule) == 604)
    check("C02", "Canonical schedule call IDs unique", schedule["Simulation_Record_ID"].nunique(),
          len(schedule), schedule["Simulation_Record_ID"].nunique() == len(schedule))
    check("C03", "Script80 provenance covers 449 intervals", len(provenance), 449, len(provenance) == 449)
    check("C04", "Review queue IDs are unique", review["Simulation_Record_ID"].nunique(),
          len(review), review["Simulation_Record_ID"].nunique() == len(review))
    check("C05", "Data-directory file inventory includes at least canonical schedule",
          len(inventory), ">=1", len(inventory) >= 1)
    check("C06", "Every scanned file has a recorded scan status",
          int(inventory["Scan_Status"].notna().sum()), len(inventory),
          inventory["Scan_Status"].notna().all())
    check("C07", "Discovery process does not assign source verification",
          int(links["Linkage_Status"].eq("SOURCE_VERIFIED").sum()) if len(links) else 0,
          0, not len(links) or not links["Linkage_Status"].eq("SOURCE_VERIFIED").any())

    checks_df = pd.DataFrame(checks)
    inventory.to_csv(OUT_INVENTORY, index=False)
    candidates.to_csv(OUT_CANDIDATES, index=False)
    links.to_csv(OUT_LINKS, index=False)
    checks_df.to_csv(OUT_CHECKS, index=False)

    passed = int(checks_df["Status"].eq("PASS").sum())
    failed = int(checks_df["Status"].eq("FAIL").sum())
    high = candidates[candidates["Candidate_Classification"].str.startswith("HIGHER")] if len(candidates) else candidates
    report = [
        "SCRIPT 81 — ORIGINAL SOURCE DATA INVENTORY AND RECORD-LINKAGE DISCOVERY",
        "=" * 78,
        f"Project root: {ROOT}",
        f"Files discovered under data/: {len(inventory)}",
        f"Files successfully scanned: {int(inventory['Scan_Status'].eq('SCANNED').sum())}",
        f"Files skipped for size: {int(inventory['Scan_Status'].str.startswith('SKIPPED').sum())}",
        f"Files with read errors: {int(inventory['Scan_Status'].str.startswith('READ_ERROR').sum())}",
        f"Canonical schedule records: {len(schedule)}",
        f"Long-interval review records: {len(review)}",
        f"Candidate datasets assessed: {len(candidates)}",
        f"Higher linkage candidates (heuristic): {len(high)}",
        f"Record-level discovery hits: {len(links)}",
        "",
        "INTERPRETATION",
        "- File discovery and identifier overlap do not establish source authenticity or provenance.",
        "- Processed simulation inputs are distinguished from possible upstream source files.",
        "- DataFrame row indices and source-row fields are reported as clues, not verified lineage.",
        "- Candidate files require human confirmation of provider, extraction date, data dictionary, and transformation history.",
        "- No missing events are inferred solely from gaps between observed calls.",
        "- No interval is shortened, deleted, winsorized, or causally classified.",
        "- No schedule slack, operational recovery, empirical distribution, physical route, or Hormuz transit is approved.",
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
        f"- {OUT_INVENTORY.relative_to(ROOT)}",
        f"- {OUT_CANDIDATES.relative_to(ROOT)}",
        f"- {OUT_LINKS.relative_to(ROOT)}",
        f"- {OUT_CHECKS.relative_to(ROOT)}",
        f"- {OUT_REPORT.relative_to(ROOT)}",
    ]
    OUT_REPORT.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    if failed:
        raise SystemExit("Script81 validation failed.")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
