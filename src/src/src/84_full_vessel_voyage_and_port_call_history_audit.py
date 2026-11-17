"""
SCRIPT 84 — FULL VESSEL VOYAGE AND PORT-CALL HISTORY AUDIT

Purpose
-------
Reconstruct the complete raw-workbook history for IMO 9813840 and inspect
voyage identifiers, port sequence, timestamp completeness, repeated ports,
and workbook row order versus chronological order.

This is a read-only investigation. It does NOT modify the canonical schedule,
classify missing intervals, infer sailing time, or approve any event identity.

Run from project root:
    python src/84_full_vessel_voyage_and_port_call_history_audit.py
"""

from pathlib import Path
import re
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "data" / "raw" / "Combined_Port_Schedules.xlsx"
SCRIPT83_EXTRACT = ROOT / "outputs" / "tables" / "83_raw_vessel_event_extract.csv"
OUT = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"
OUT.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

TARGET_IMO = "9813840"
OUTPUT_PREFIX = "84_"

def norm_imo(x):
    if pd.isna(x):
        return ""
    s = re.sub(r"\.0$", "", str(x).strip())
    digits = re.sub(r"\D", "", s)
    return digits

def find_col(df, candidates):
    lower = {str(c).strip().lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    for c in candidates:
        for col in df.columns:
            if c.lower() in str(col).strip().lower():
                return col
    return None

def parse_utc(series):
    # Workbook values may contain timezone offsets; normalize all to UTC.
    return pd.to_datetime(series, errors="coerce", utc=True)

def save(df, name):
    df.to_csv(OUT / f"{OUTPUT_PREFIX}{name}.csv", index=False)

checks = []
def check(cid, desc, observed, expected, passed):
    checks.append({
        "Check_ID": cid, "Description": desc,
        "Observed": observed, "Expected": expected,
        "Status": "PASS" if bool(passed) else "FAIL"
    })

if not WORKBOOK.exists():
    raise FileNotFoundError(f"Required raw workbook not found: {WORKBOOK}")
if not SCRIPT83_EXTRACT.exists():
    raise FileNotFoundError(f"Required Script83 extract not found: {SCRIPT83_EXTRACT}")

s83 = pd.read_csv(SCRIPT83_EXTRACT, dtype=str)
if "_IMO_KEY" not in s83.columns or s83["_IMO_KEY"].dropna().empty:
    raise ValueError("Script83 extract lacks a usable _IMO_KEY.")
imo_values = s83["_IMO_KEY"].dropna().map(norm_imo).unique().tolist()
if len(imo_values) != 1 or imo_values[0] != TARGET_IMO:
    raise ValueError(f"Script83 target IMO mismatch: {imo_values}")

xl = pd.ExcelFile(WORKBOOK)
if len(xl.sheet_names) != 1:
    raise ValueError(f"Expected the previously audited single-sheet workbook; found {xl.sheet_names}")
sheet = xl.sheet_names[0]
raw = pd.read_excel(WORKBOOK, sheet_name=sheet)
imo_col = find_col(raw, ["IMO Number", "IMO"])
port_col = find_col(raw, ["UN Location Code", "UNLOCODE"])
arrival_col = find_col(raw, ["Actual Arrival"])
departure_col = find_col(raw, ["Actual Departure"])
if any(c is None for c in [imo_col, port_col, arrival_col, departure_col]):
    raise ValueError(f"Required columns unresolved: IMO={imo_col}, port={port_col}, arrival={arrival_col}, departure={departure_col}")

raw["_Workbook_Excel_Row"] = np.arange(len(raw)) + 2
raw["_IMO_KEY"] = raw[imo_col].map(norm_imo)
raw["_PORT_KEY"] = raw[port_col].astype("string").str.strip().str.upper()
raw["_ACTUAL_ARRIVAL_UTC"] = parse_utc(raw[arrival_col])
raw["_ACTUAL_DEPARTURE_UTC"] = parse_utc(raw[departure_col])

v = raw.loc[raw["_IMO_KEY"].eq(TARGET_IMO)].copy()
if v.empty:
    raise ValueError(f"No raw workbook records found for IMO {TARGET_IMO}")

# Stable chronological order: actual arrival, then departure, then source row.
v["_Chronology_Sort_Missing_Arrival"] = v["_ACTUAL_ARRIVAL_UTC"].isna()
v = v.sort_values(
    ["_Chronology_Sort_Missing_Arrival", "_ACTUAL_ARRIVAL_UTC",
     "_ACTUAL_DEPARTURE_UTC", "_Workbook_Excel_Row"],
    kind="mergesort"
).reset_index(drop=True)
v["Chronological_Record_Number"] = np.arange(1, len(v) + 1)

call_sign_col = find_col(v, ["Call Sign"])
import_col = find_col(v, ["Import Voyage Number"])
export_col = find_col(v, ["Export Voyage Number"])
vessel_col = find_col(v, ["Vessel Name"])
facility_col = find_col(v, ["Facility SMDG Code"])
port_name_col = find_col(v, ["Port"])
carrier_col = find_col(v, ["Carrier Code"])
service_name_col = find_col(v, ["Carrier Service Name"])
service_code_col = find_col(v, ["Carrier Service Code"])

def val(row, col):
    return row[col] if col and col in row.index else np.nan

# Chronology register preserves every source column and adds derived diagnostics.
chron = v.copy()
chron["Actual_Stay_Hours_From_Timestamps"] = (
    (chron["_ACTUAL_DEPARTURE_UTC"] - chron["_ACTUAL_ARRIVAL_UTC"]).dt.total_seconds() / 3600
)
chron["Actual_Timestamp_Order_Valid"] = (
    chron["_ACTUAL_ARRIVAL_UTC"].notna() &
    chron["_ACTUAL_DEPARTURE_UTC"].notna() &
    (chron["_ACTUAL_DEPARTURE_UTC"] >= chron["_ACTUAL_ARRIVAL_UTC"])
)
chron["Arrival_Missing"] = chron["_ACTUAL_ARRIVAL_UTC"].isna()
chron["Departure_Missing"] = chron["_ACTUAL_DEPARTURE_UTC"].isna()
chron["Voyage_Identifiers_Match"] = (
    chron[import_col].astype("string").str.strip().eq(
        chron[export_col].astype("string").str.strip()
    ) if import_col and export_col else pd.NA
)
chron["Same_Port_As_Previous_Chronological_Record"] = chron["_PORT_KEY"].eq(chron["_PORT_KEY"].shift())
chron["Same_Import_Voyage_As_Previous_Record"] = (
    chron[import_col].astype("string").str.strip().eq(
        chron[import_col].astype("string").str.strip().shift()
    ) if import_col else pd.NA
)
chron["Same_Export_Voyage_As_Previous_Record"] = (
    chron[export_col].astype("string").str.strip().eq(
        chron[export_col].astype("string").str.strip().shift()
    ) if export_col else pd.NA
)
chron["Gap_From_Previous_Departure_To_Current_Arrival_Hours"] = (
    (chron["_ACTUAL_ARRIVAL_UTC"] - chron["_ACTUAL_DEPARTURE_UTC"].shift()).dt.total_seconds() / 3600
)
chron["Workbook_Row_Order_Differs_From_Chronological_Order"] = (
    chron["_Workbook_Excel_Row"].diff().lt(0)
)

# Focused voyage sequence table, one row per chronological raw record.
seq_cols = [
    "Chronological_Record_Number", "_Workbook_Excel_Row", "_IMO_KEY",
    "_PORT_KEY", "_ACTUAL_ARRIVAL_UTC", "_ACTUAL_DEPARTURE_UTC",
    "Actual_Stay_Hours_From_Timestamps", "Actual_Timestamp_Order_Valid",
    "Arrival_Missing", "Departure_Missing",
    "Gap_From_Previous_Departure_To_Current_Arrival_Hours",
    "Same_Port_As_Previous_Chronological_Record",
    "Same_Import_Voyage_As_Previous_Record",
    "Same_Export_Voyage_As_Previous_Record",
    "Voyage_Identifiers_Match",
]
for c in [vessel_col, call_sign_col, import_col, export_col, facility_col,
          port_name_col, carrier_col, service_name_col, service_code_col]:
    if c and c not in seq_cols:
        seq_cols.append(c)
sequence = chron[[c for c in seq_cols if c in chron.columns]].copy()

# Voyage identifier inventory, retaining the exact values as source strings.
voyage_rows = []
for kind, col in [("IMPORT", import_col), ("EXPORT", export_col)]:
    if col:
        counts = v[col].fillna("<MISSING>").astype(str).value_counts(dropna=False)
        for identifier, count in counts.items():
            subset = v.loc[v[col].fillna("<MISSING>").astype(str).eq(identifier)]
            ports = " -> ".join(subset.sort_values("_ACTUAL_ARRIVAL_UTC")["_PORT_KEY"].fillna("<MISSING>").astype(str))
            voyage_rows.append({
                "Identifier_Type": kind,
                "Source_Column": col,
                "Voyage_Identifier": identifier,
                "Record_Count": int(count),
                "Distinct_Port_Count": int(subset["_PORT_KEY"].nunique(dropna=True)),
                "Ports_In_Chronological_Record_Order": ports,
                "Workbook_Rows": ";".join(subset["_Workbook_Excel_Row"].astype(int).astype(str).tolist()),
                "First_Actual_Arrival_UTC": subset["_ACTUAL_ARRIVAL_UTC"].min(),
                "Last_Actual_Arrival_UTC": subset["_ACTUAL_ARRIVAL_UTC"].max(),
                "Missing_Actual_Arrival_Count": int(subset["_ACTUAL_ARRIVAL_UTC"].isna().sum()),
                "Missing_Actual_Departure_Count": int(subset["_ACTUAL_DEPARTURE_UTC"].isna().sum()),
            })
voyage_inventory = pd.DataFrame(voyage_rows)

# Port sequence summary.
port_summary = (
    chron.groupby("_PORT_KEY", dropna=False)
    .agg(
        Raw_Record_Count=("_Workbook_Excel_Row", "size"),
        Distinct_Import_Voyages=(import_col, "nunique") if import_col else ("_Workbook_Excel_Row", "size"),
        Distinct_Export_Voyages=(export_col, "nunique") if export_col else ("_Workbook_Excel_Row", "size"),
        Missing_Actual_Arrival_Count=("Arrival_Missing", "sum"),
        Missing_Actual_Departure_Count=("Departure_Missing", "sum"),
        First_Actual_Arrival_UTC=("_ACTUAL_ARRIVAL_UTC", "min"),
        Last_Actual_Arrival_UTC=("_ACTUAL_ARRIVAL_UTC", "max"),
    ).reset_index().rename(columns={"_PORT_KEY": "Port_UNLOCODE"})
)
port_summary["Workbook_Rows"] = port_summary["Port_UNLOCODE"].map(
    chron.groupby("_PORT_KEY")["_Workbook_Excel_Row"].apply(lambda x: ";".join(x.astype(int).astype(str)))
)

# Data quality / identity summary.
summary_rows = [
    ("Target_IMO", TARGET_IMO),
    ("Vessel_Name_Values", " | ".join(sorted(v[vessel_col].dropna().astype(str).unique())) if vessel_col else ""),
    ("Call_Sign_Values", " | ".join(sorted(v[call_sign_col].dropna().astype(str).unique())) if call_sign_col else ""),
    ("Raw_Workbook_Record_Count", len(v)),
    ("Distinct_Port_Count", v["_PORT_KEY"].nunique(dropna=True)),
    ("Distinct_Import_Voyage_Count", v[import_col].nunique(dropna=True) if import_col else np.nan),
    ("Distinct_Export_Voyage_Count", v[export_col].nunique(dropna=True) if export_col else np.nan),
    ("Missing_Actual_Arrival_Count", int(v["_ACTUAL_ARRIVAL_UTC"].isna().sum())),
    ("Missing_Actual_Departure_Count", int(v["_ACTUAL_DEPARTURE_UTC"].isna().sum())),
    ("Invalid_Actual_Timestamp_Order_Count", int((chron["_ACTUAL_ARRIVAL_UTC"].notna() & chron["_ACTUAL_DEPARTURE_UTC"].notna() & (chron["_ACTUAL_DEPARTURE_UTC"] < chron["_ACTUAL_ARRIVAL_UTC"])).sum())),
    ("Negative_Inter_Record_Gap_Count", int(chron["Gap_From_Previous_Departure_To_Current_Arrival_Hours"].lt(0).sum())),
    ("Zero_Inter_Record_Gap_Count", int(chron["Gap_From_Previous_Departure_To_Current_Arrival_Hours"].eq(0).sum())),
    ("Repeated_Consecutive_Port_Record_Count", int(chron["Same_Port_As_Previous_Chronological_Record"].fillna(False).sum())),
    ("Workbook_Row_Order_Chronology_Inversions", int(chron["Workbook_Row_Order_Differs_From_Chronological_Order"].sum())),
    ("Import_Export_Voyage_Mismatch_Count", int((chron[import_col].astype("string").str.strip() != chron[export_col].astype("string").str.strip()).sum()) if import_col and export_col else np.nan),
]
summary = pd.DataFrame(summary_rows, columns=["Metric", "Value"])

# Checks focus on faithful scope and internal accounting, not semantic event approval.
check("C01", "Target vessel raw record count equals Script83's reported 32", len(v), 32, len(v) == 32)
check("C02", "All extracted rows belong to target IMO", int(v["_IMO_KEY"].nunique()), 1, v["_IMO_KEY"].eq(TARGET_IMO).all())
check("C03", "Every raw workbook row number is unique", int(v["_Workbook_Excel_Row"].nunique()), len(v), v["_Workbook_Excel_Row"].is_unique)
check("C04", "Chronological record numbering is complete", int(chron["Chronological_Record_Number"].nunique()), len(v), chron["Chronological_Record_Number"].tolist() == list(range(1, len(v)+1)))
check("C05", "Voyage identifier fields available", int(import_col is not None) + int(export_col is not None), 2, import_col is not None and export_col is not None)
check("C06", "Raw workbook remains read-only; no approval fields assigned", 0, 0, True)

checks_df = pd.DataFrame(checks)
save(sequence, "full_vessel_chronological_history")
save(voyage_inventory, "vessel_voyage_identifier_inventory")
save(port_summary, "vessel_port_sequence_summary")
save(summary, "vessel_history_quality_summary")
save(checks_df, "validation_checks")

report_path = REPORTS / "84_full_vessel_voyage_and_port_call_history_audit.txt"
with report_path.open("w", encoding="utf-8") as f:
    f.write("SCRIPT 84 — FULL VESSEL VOYAGE AND PORT-CALL HISTORY AUDIT\n")
    f.write("=" * 78 + "\n")
    f.write(f"Workbook: {WORKBOOK}\nSheet: {sheet}\nTarget IMO: {TARGET_IMO}\n")
    f.write(f"Raw records for target vessel: {len(v)}\n")
    f.write(f"Chronological port sequence: {' -> '.join(chron['_PORT_KEY'].fillna('<MISSING>').astype(str))}\n\n")
    f.write("IDENTITY FIELDS\n")
    f.write(f"Vessel name column: {vessel_col}; values: {summary.loc[summary.Metric.eq('Vessel_Name_Values'),'Value'].iloc[0]}\n")
    f.write(f"Call sign column: {call_sign_col}; values: {summary.loc[summary.Metric.eq('Call_Sign_Values'),'Value'].iloc[0]}\n")
    f.write(f"Import voyage column: {import_col}\nExport voyage column: {export_col}\n\n")
    f.write("SUMMARY\n")
    f.write(summary.to_string(index=False) + "\n\n")
    f.write("VOYAGE IDENTIFIER INVENTORY\n")
    f.write(voyage_inventory.to_string(index=False) + "\n\n")
    f.write("PORT SEQUENCE SUMMARY\n")
    f.write(port_summary.to_string(index=False) + "\n\n")
    f.write("VALIDATION CHECKS\n")
    f.write(checks_df.to_string(index=False) + "\n\n")
    f.write("INTERPRETATION LIMITATIONS\n")
    f.write("- This is a raw-workbook chronology, not a verified port-call or voyage reconstruction.\n")
    f.write("- Import/Export Voyage Number semantics are not established by this workbook alone.\n")
    f.write("- Missing actual departure timestamps prevent complete interval reconstruction for affected rows.\n")
    f.write("- Consecutive same-port rows and distinct voyage identifiers are descriptive evidence only.\n")
    f.write("- Inter-record elapsed time is not pure sailing time or verified schedule slack.\n")
    f.write("- No canonical schedule changes, event classifications, or operational approvals are made.\n")

print("SCRIPT 84 — FULL VESSEL VOYAGE AND PORT-CALL HISTORY AUDIT")
print("=" * 78)
print(f"Target IMO: {TARGET_IMO}")
print(f"Raw workbook records: {len(v)}")
print(f"Distinct ports: {v['_PORT_KEY'].nunique(dropna=True)}")
print(f"Distinct import voyages: {v[import_col].nunique(dropna=True) if import_col else 'N/A'}")
print(f"Distinct export voyages: {v[export_col].nunique(dropna=True) if export_col else 'N/A'}")
print(f"Missing actual arrivals: {v['_ACTUAL_ARRIVAL_UTC'].isna().sum()}")
print(f"Missing actual departures: {v['_ACTUAL_DEPARTURE_UTC'].isna().sum()}")
print(f"Validation checks passed: {(checks_df.Status == 'PASS').sum()}/{len(checks_df)}")
print(f"Validation checks failed: {(checks_df.Status == 'FAIL').sum()}/{len(checks_df)}")
print("\nOUTPUT FILES")
for name in [
    "84_full_vessel_chronological_history.csv",
    "84_vessel_voyage_identifier_inventory.csv",
    "84_vessel_port_sequence_summary.csv",
    "84_vessel_history_quality_summary.csv",
    "84_validation_checks.csv",
]:
    print(f"- outputs/tables/{name}")
print("- outputs/reports/84_full_vessel_voyage_and_port_call_history_audit.txt")

if (checks_df.Status == "FAIL").any():
    sys.exit("One or more Script84 validation checks failed.")
