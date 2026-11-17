"""
SCRIPT 85 — PAIRED VOYAGE RECORD AND TIMESTAMP COMPLETENESS AUDIT

Purpose
-------
Inspect all raw workbook records for IMO 9813840, pairing QADOH and QAQCH
records by Import Voyage Number and Export Voyage Number. Preserve all original
workbook fields and compare actual, planned, estimated, and other timestamp-like
columns without substituting one timestamp class for another.

Read-only: no canonical schedule changes, no call identity approvals, no
sailing-time inference, and no operational decisions.

Run from project root:
    python src/85_paired_voyage_record_and_timestamp_completeness_audit.py
"""

from pathlib import Path
import re
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "data" / "raw" / "Combined_Port_Schedules.xlsx"
OUT = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"
OUT.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

TARGET_IMO = "9813840"
PREFIX = "85_"

def norm_imo(x):
    if pd.isna(x):
        return ""
    s = re.sub(r"\.0$", "", str(x).strip())
    return re.sub(r"\D", "", s)

def find_col(df, candidates):
    lower = {str(c).strip().lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    for candidate in candidates:
        for col in df.columns:
            if candidate.lower() in str(col).strip().lower():
                return col
    return None

def save(df, filename):
    df.to_csv(OUT / f"{PREFIX}{filename}.csv", index=False)

if not WORKBOOK.exists():
    raise FileNotFoundError(f"Workbook not found: {WORKBOOK}")

xls = pd.ExcelFile(WORKBOOK)
if len(xls.sheet_names) != 1:
    raise ValueError(f"Expected one previously audited sheet; found {xls.sheet_names}")
sheet = xls.sheet_names[0]
raw = pd.read_excel(WORKBOOK, sheet_name=sheet)

imo_col = find_col(raw, ["IMO Number", "IMO"])
port_col = find_col(raw, ["UN Location Code", "UNLOCODE"])
import_col = find_col(raw, ["Import Voyage Number"])
export_col = find_col(raw, ["Export Voyage Number"])
if any(c is None for c in [imo_col, port_col, import_col, export_col]):
    raise ValueError(
        f"Required fields unresolved: IMO={imo_col}, port={port_col}, "
        f"import={import_col}, export={export_col}"
    )

raw["_Workbook_Excel_Row"] = np.arange(len(raw)) + 2
raw["_IMO_KEY"] = raw[imo_col].map(norm_imo)
raw["_PORT_KEY"] = raw[port_col].astype("string").str.strip().str.upper()
raw["_IMPORT_VOYAGE_KEY"] = raw[import_col].astype("string").str.strip().str.upper()
raw["_EXPORT_VOYAGE_KEY"] = raw[export_col].astype("string").str.strip().str.upper()
v = raw.loc[raw["_IMO_KEY"].eq(TARGET_IMO)].copy()
if len(v) != 32:
    raise ValueError(f"Expected 32 target-vessel rows from Script84; found {len(v)}")
if not v["_Workbook_Excel_Row"].is_unique:
    raise ValueError("Workbook row identifiers are not unique.")

# Identify timestamp-like fields using names only; retain original raw values.
timestamp_cols = [
    c for c in raw.columns
    if any(token in str(c).lower() for token in
           ["arrival", "departure", "eta", "etd", "berth", "time", "date"])
]
# Separate actual fields from planned/estimated/other by column name.
def timestamp_class(col):
    s = str(col).lower()
    if "actual" in s:
        return "ACTUAL"
    if any(x in s for x in ["planned", "plan", "scheduled", "schedule"]):
        return "PLANNED_OR_SCHEDULED"
    if any(x in s for x in ["estimated", "estimate", "eta", "etd"]):
        return "ESTIMATED_OR_ETA_ETD"
    return "OTHER_TIMESTAMP_FIELD"

# Paired records keyed by both voyage columns. The script reports pairing;
# it does not interpret the voyage identifier's operational meaning.
pair_rows = []
for (imp, exp), g in v.groupby(
    ["_IMPORT_VOYAGE_KEY", "_EXPORT_VOYAGE_KEY"], dropna=False, sort=False
):
    ports = sorted(g["_PORT_KEY"].dropna().unique().tolist())
    row = {
        "Import_Voyage_Number": imp,
        "Export_Voyage_Number": exp,
        "Voyage_Fields_Match": bool(str(imp) == str(exp)),
        "Record_Count": len(g),
        "Distinct_Port_Count": len(ports),
        "Ports": ";".join(ports),
        "Workbook_Rows": ";".join(g["_Workbook_Excel_Row"].astype(int).astype(str)),
        "QADOH_Record_Count": int(g["_PORT_KEY"].eq("QADOH").sum()),
        "QAQCH_Record_Count": int(g["_PORT_KEY"].eq("QAQCH").sum()),
    }
    for port in ["QADOH", "QAQCH"]:
        pg = g.loc[g["_PORT_KEY"].eq(port)]
        row[f"{port}_Workbook_Rows"] = ";".join(pg["_Workbook_Excel_Row"].astype(int).astype(str))
        for col in timestamp_cols:
            # Store each port's values without replacing missing actual values.
            vals = pg[col].dropna().astype(str).tolist()
            row[f"{port}__{col}"] = " || ".join(vals)
    pair_rows.append(row)
paired = pd.DataFrame(pair_rows)

# Full raw record extract, retaining every original workbook field.
full_extract = v.sort_values(
    ["_PORT_KEY", "_IMPORT_VOYAGE_KEY", "_Workbook_Excel_Row"],
    kind="mergesort"
).copy()

# Focus on the interval of interest and adjacent paired voyages.
focus_ids = {"649W", "650W", "651W", "652W", "653W", "655W", "656W", "657W", "658W"}
focus = v.loc[
    v["_IMPORT_VOYAGE_KEY"].isin(focus_ids) |
    v["_EXPORT_VOYAGE_KEY"].isin(focus_ids)
].copy()
focus = focus.sort_values(["_Workbook_Excel_Row"], kind="mergesort")

# Timestamp field coverage: per field, count raw non-null values across all
# target-vessel rows and separately by port.
coverage_rows = []
for col in timestamp_cols:
    coverage_rows.append({
        "Source_Column": col,
        "Timestamp_Field_Class": timestamp_class(col),
        "Target_Vessel_NonNull_Count": int(v[col].notna().sum()),
        "Target_Vessel_Null_Count": int(v[col].isna().sum()),
        "QADOH_NonNull_Count": int(v.loc[v["_PORT_KEY"].eq("QADOH"), col].notna().sum()),
        "QAQCH_NonNull_Count": int(v.loc[v["_PORT_KEY"].eq("QAQCH"), col].notna().sum()),
        "Distinct_NonNull_Values": int(v[col].dropna().astype(str).nunique()),
    })
coverage = pd.DataFrame(coverage_rows)

# Summary and checks.
summary = pd.DataFrame([
    ("Target_IMO", TARGET_IMO),
    ("Raw_Target_Vessel_Records", len(v)),
    ("Distinct_Import_Export_Voyage_Pairs", len(paired)),
    ("Voyage_Pairs_With_Two_Records", int(paired["Record_Count"].eq(2).sum())),
    ("Voyage_Pairs_With_QADOH_And_QAQCH", int((paired["QADOH_Record_Count"].eq(1) & paired["QAQCH_Record_Count"].eq(1)).sum())),
    ("Voyage_Field_Mismatch_Records", int((v["_IMPORT_VOYAGE_KEY"] != v["_EXPORT_VOYAGE_KEY"]).sum())),
    ("Timestamp_Like_Source_Columns", len(timestamp_cols)),
    ("Actual_Timestamp_Columns", sum(timestamp_class(c) == "ACTUAL" for c in timestamp_cols)),
    ("Planned_Scheduled_Timestamp_Columns", sum(timestamp_class(c) == "PLANNED_OR_SCHEDULED" for c in timestamp_cols)),
    ("Estimated_ETA_ETD_Timestamp_Columns", sum(timestamp_class(c) == "ESTIMATED_OR_ETA_ETD" for c in timestamp_cols)),
    ("Records_With_Any_Actual_Arrival", int(next((v[c].notna().sum() for c in timestamp_cols if "actual arrival" in str(c).lower()), 0))),
    ("Records_With_Any_Actual_Departure", int(next((v[c].notna().sum() for c in timestamp_cols if "actual departure" in str(c).lower()), 0))),
], columns=["Metric", "Value"])

checks = []
def add_check(cid, desc, observed, expected, passed):
    checks.append({
        "Check_ID": cid, "Description": desc, "Observed": observed,
        "Expected": expected, "Status": "PASS" if bool(passed) else "FAIL"
    })

add_check("C01", "Target vessel record count reconciles to Script84", len(v), 32, len(v) == 32)
add_check("C02", "Every target record has a unique workbook row number", int(v["_Workbook_Excel_Row"].nunique()), len(v), v["_Workbook_Excel_Row"].is_unique)
add_check("C03", "Import and export voyage identifiers match on every target record", int((v["_IMPORT_VOYAGE_KEY"] == v["_EXPORT_VOYAGE_KEY"]).sum()), len(v), (v["_IMPORT_VOYAGE_KEY"] == v["_EXPORT_VOYAGE_KEY"]).all())
add_check("C04", "All paired voyage records are represented in paired register", int(paired["Record_Count"].sum()), len(v), int(paired["Record_Count"].sum()) == len(v))
add_check("C05", "Original target workbook rows are retained in full extract", len(full_extract), len(v), len(full_extract) == len(v))
add_check("C06", "No event identity or operational approvals assigned", 0, 0, True)
checks_df = pd.DataFrame(checks)

save(paired, "paired_voyage_record_register")
save(full_extract, "full_raw_vessel_record_extract")
save(focus, "focus_period_and_adjacent_voyage_records")
save(coverage, "timestamp_field_completeness")
save(summary, "paired_voyage_audit_summary")
save(checks_df, "validation_checks")

report = REPORTS / "85_paired_voyage_record_and_timestamp_completeness_audit.txt"
with report.open("w", encoding="utf-8") as f:
    f.write("SCRIPT 85 — PAIRED VOYAGE RECORD AND TIMESTAMP COMPLETENESS AUDIT\n")
    f.write("=" * 78 + "\n")
    f.write(f"Workbook: {WORKBOOK}\nSheet: {sheet}\nTarget IMO: {TARGET_IMO}\n")
    f.write(f"Raw target-vessel records: {len(v)}\n\n")
    f.write("SOURCE TIMESTAMP FIELDS\n")
    f.write("\n".join(f"- {c} [{timestamp_class(c)}]" for c in timestamp_cols) + "\n\n")
    f.write("SUMMARY\n" + summary.to_string(index=False) + "\n\n")
    f.write("PAIRED VOYAGE REGISTER\n" + paired.to_string(index=False) + "\n\n")
    f.write("TIMESTAMP FIELD COMPLETENESS\n" + coverage.to_string(index=False) + "\n\n")
    f.write("VALIDATION CHECKS\n" + checks_df.to_string(index=False) + "\n\n")
    f.write("INTERPRETATION LIMITATIONS\n")
    f.write("- Pairing by Import/Export Voyage Number is a record-linkage operation only.\n")
    f.write("- The workbook does not itself define the operational meaning of voyage numbers.\n")
    f.write("- Actual, planned, estimated and other timestamp fields are kept separate.\n")
    f.write("- Planned/estimated timestamps are not substitutes for missing actual timestamps.\n")
    f.write("- No row is declared a completed port call solely from its voyage number or port.\n")
    f.write("- No inter-record gap is interpreted as pure sailing time or schedule slack.\n")
    f.write("- No canonical schedule changes or operational approvals are made.\n")

print("SCRIPT 85 — PAIRED VOYAGE RECORD AND TIMESTAMP COMPLETENESS AUDIT")
print("=" * 78)
print(f"Target IMO: {TARGET_IMO}")
print(f"Raw target-vessel records: {len(v)}")
print(f"Paired voyage identifiers: {len(paired)}")
print(f"Pairs with both QADOH and QAQCH records: {(paired['QADOH_Record_Count'].eq(1) & paired['QAQCH_Record_Count'].eq(1)).sum()}")
print(f"Timestamp-like columns: {len(timestamp_cols)}")
print(f"Validation checks passed: {(checks_df.Status == 'PASS').sum()}/{len(checks_df)}")
print(f"Validation checks failed: {(checks_df.Status == 'FAIL').sum()}/{len(checks_df)}")
print("\nOUTPUT FILES")
for name in [
    "85_paired_voyage_record_register.csv",
    "85_full_raw_vessel_record_extract.csv",
    "85_focus_period_and_adjacent_voyage_records.csv",
    "85_timestamp_field_completeness.csv",
    "85_paired_voyage_audit_summary.csv",
    "85_validation_checks.csv",
]:
    print(f"- outputs/tables/{name}")
print("- outputs/reports/85_paired_voyage_record_and_timestamp_completeness_audit.txt")
if (checks_df.Status == "FAIL").any():
    sys.exit("One or more Script85 validation checks failed.")
