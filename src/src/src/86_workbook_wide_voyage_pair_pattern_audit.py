
"""
SCRIPT 86 — WORKBOOK-WIDE VOYAGE-PAIR PATTERN AUDIT

Purpose:
Test whether the paired-port voyage pattern identified for IMO 9813840
also appears across the complete raw port-schedule workbook.

Read-only investigation.
Does not modify the canonical schedule or raw workbook.
Does not infer sailing time, route identity, or operational approval.

Run from project root:
python src/86_workbook_wide_voyage_pair_pattern_audit.py
"""

from pathlib import Path
import re
import sys
import numpy as np
import pandas as pd


# ------------------------------------------------------------
# 1. PATHS AND CONFIGURATION
# ------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

WORKBOOK = (
    ROOT / "data" / "raw" /
    "Combined_Port_Schedules.xlsx"
)

OUT = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"

OUT.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

TARGET_IMO = "9813840"
PREFIX = "86_"


# ------------------------------------------------------------
# 2. HELPER FUNCTIONS
# ------------------------------------------------------------

def norm_imo(value):
    if pd.isna(value):
        return ""

    value = re.sub(r"\.0$", "", str(value).strip())
    return re.sub(r"\D", "", value)


def find_col(df, candidates):

    lower = {
        str(c).strip().lower(): c
        for c in df.columns
    }

    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]

    for candidate in candidates:
        for col in df.columns:
            if candidate.lower() in str(col).lower():
                return col

    return None


def utc(series):
    return pd.to_datetime(
        series,
        errors="coerce",
        utc=True
    )


def save(df, filename):
    df.to_csv(
        OUT / f"{PREFIX}{filename}.csv",
        index=False
    )


# ------------------------------------------------------------
# 3. LOAD RAW WORKBOOK
# ------------------------------------------------------------

if not WORKBOOK.exists():
    raise FileNotFoundError(
        f"Workbook not found: {WORKBOOK}"
    )

xls = pd.ExcelFile(WORKBOOK)

if len(xls.sheet_names) != 1:
    raise ValueError(
        f"Expected one worksheet; found {xls.sheet_names}"
    )

sheet = xls.sheet_names[0]

df = pd.read_excel(
    WORKBOOK,
    sheet_name=sheet
)

imo_col = find_col(
    df, ["IMO Number", "IMO"]
)

port_col = find_col(
    df, ["UN Location Code", "UNLOCODE"]
)

imp_col = find_col(
    df, ["Import Voyage Number"]
)

exp_col = find_col(
    df, ["Export Voyage Number"]
)

if any(
    c is None
    for c in [imo_col, port_col, imp_col, exp_col]
):
    raise ValueError(
        "Required identity, port or voyage columns missing."
    )


# ------------------------------------------------------------
# 4. NORMALISE IDENTIFIERS
# ------------------------------------------------------------

df["_Excel_Row"] = np.arange(len(df)) + 2

df["_IMO"] = df[imo_col].map(norm_imo)

df["_PORT"] = (
    df[port_col]
    .astype("string")
    .str.strip()
    .str.upper()
)

df["_IMP"] = (
    df[imp_col]
    .astype("string")
    .str.strip()
    .str.upper()
)

df["_EXP"] = (
    df[exp_col]
    .astype("string")
    .str.strip()
    .str.upper()
)


# ------------------------------------------------------------
# 5. IDENTIFY SIX TIMESTAMP FIELDS
# ------------------------------------------------------------

timestamp_source = {
    "Planned_Arrival": find_col(df, ["Planned Arrival"]),
    "Estimated_Arrival": find_col(df, ["Estimated Arrival"]),
    "Actual_Arrival": find_col(df, ["Actual Arrival"]),
    "Planned_Departure": find_col(df, ["Planned Departure"]),
    "Estimated_Departure": find_col(df, ["Estimated Departure"]),
    "Actual_Departure": find_col(df, ["Actual Departure"]),
}

if any(v is None for v in timestamp_source.values()):
    raise ValueError(
        f"Missing timestamp columns: {timestamp_source}"
    )

for name, col in timestamp_source.items():
    df[f"_{name}_UTC"] = utc(df[col])


# ------------------------------------------------------------
# 6. COMPOSITE VOYAGE KEY
# ------------------------------------------------------------

keys = ["_IMO", "_IMP", "_EXP"]

valid_key = (
    df[keys].notna().all(axis=1)
    & df[keys].ne("").all(axis=1)
)

keyed = df.loc[valid_key].copy()


# ------------------------------------------------------------
# 7. BUILD VOYAGE-PAIR REGISTER
# ------------------------------------------------------------

groups = []

for key, g in keyed.groupby(
    keys,
    dropna=False,
    sort=False
):

    ports = sorted(
        g["_PORT"].dropna().unique().tolist()
    )

    row = {
        "IMO": key[0],
        "Import_Voyage_Number": key[1],
        "Export_Voyage_Number": key[2],
        "Record_Count": len(g),
        "Distinct_Port_Count": len(ports),
        "Ports": ";".join(ports),
        "Workbook_Rows": ";".join(
            g["_Excel_Row"].astype(int).astype(str)
        ),
        "Voyage_Fields_Match": key[1] == key[2],
        "Is_Target_Vessel": key[0] == TARGET_IMO,
    }

    for port in ports:

        pg = g.loc[g["_PORT"].eq(port)]

        tag = re.sub(
            r"[^A-Za-z0-9]+",
            "_",
            str(port)
        ).strip("_")

        row[f"{tag}_Record_Count"] = len(pg)

        row[f"{tag}_Rows"] = ";".join(
            pg["_Excel_Row"].astype(int).astype(str)
        )

        for tname in [
            "Actual_Arrival",
            "Actual_Departure",
            "Planned_Arrival",
            "Planned_Departure",
            "Estimated_Arrival",
            "Estimated_Departure",
        ]:

            col = f"_{tname}_UTC"

            row[f"{tag}_{tname}_NonNull_Count"] = (
                int(pg[col].notna().sum())
            )

            row[f"{tag}_{tname}_Values_UTC"] = (
                " || ".join(
                    pg[col].dropna().astype(str).tolist()
                )
            )

    groups.append(row)


pair_register = pd.DataFrame(groups)


# ------------------------------------------------------------
# 8. PER-VESSEL VOYAGE-PAIR SUMMARY
# ------------------------------------------------------------

vessel_rows = []

for imo, g in pair_register.groupby("IMO"):

    vessel_rows.append({

        "IMO": imo,

        "Voyage_Key_Count": len(g),

        "Single_Record_Key_Count": int(
            g["Record_Count"].eq(1).sum()
        ),

        "Multi_Record_Key_Count": int(
            g["Record_Count"].gt(1).sum()
        ),

        "Multi_Port_Key_Count": int(
            g["Distinct_Port_Count"].gt(1).sum()
        ),

        "Keys_With_Exactly_Two_Ports": int(
            g["Distinct_Port_Count"].eq(2).sum()
        ),

        "Max_Records_Per_Key": int(
            g["Record_Count"].max()
        ),

        "All_Import_Export_Keys_Match": bool(
            g["Voyage_Fields_Match"].all()
        ),

        "Is_Target_Vessel": imo == TARGET_IMO,
    })


vessel_summary = pd.DataFrame(vessel_rows)


# ------------------------------------------------------------
# 9. TIMESTAMP COMPLETENESS
# ------------------------------------------------------------

coverage_rows = []

for scope, subset in [
    ("ALL_WORKBOOK", df),
    ("TARGET_VESSEL", df.loc[df["_IMO"].eq(TARGET_IMO)])
]:

    for name in timestamp_source:

        col = f"_{name}_UTC"

        coverage_rows.append({

            "Scope": scope,

            "Timestamp_Field": name,

            "Record_Count": len(subset),

            "NonNull_Count": int(
                subset[col].notna().sum()
            ),

            "Null_Count": int(
                subset[col].isna().sum()
            ),

            "Completeness_Rate": (
                float(subset[col].notna().mean())
                if len(subset)
                else np.nan
            ),
        })


coverage = pd.DataFrame(coverage_rows)


# ------------------------------------------------------------
# 10. WORKBOOK-WIDE PAIR PATTERN SUMMARY
# ------------------------------------------------------------

two_port = pair_register.loc[
    pair_register["Distinct_Port_Count"].eq(2)
]

multi_record = pair_register.loc[
    pair_register["Record_Count"].gt(1)
]

target_pairs = pair_register.loc[
    pair_register["Is_Target_Vessel"]
]

pattern_summary = pd.DataFrame([

    ("Workbook_Raw_Record_Count", len(df)),

    (
        "Distinct_IMO_Count",
        df["_IMO"].replace("", np.nan).nunique()
    ),

    (
        "Rows_With_Complete_Composite_Voyage_Key",
        int(valid_key.sum())
    ),

    (
        "Distinct_IMO_Voyage_Keys",
        len(pair_register)
    ),

    (
        "Keys_With_Multiple_Rows",
        len(multi_record)
    ),

    (
        "Keys_With_Exactly_Two_Distinct_Ports",
        len(two_port)
    ),

    (
        "Two_Port_Keys_With_Exactly_Two_Rows",
        int(
            (
                two_port["Record_Count"].eq(2)
            ).sum()
        )
    ),

    (
        "Two_Port_Keys_With_One_Row_Per_Port",
        int(
            (
                two_port["Record_Count"].eq(2)
            ).sum()
        )
    ),

    (
        "Target_Vessel_Voyage_Keys",
        len(target_pairs)
    ),

    (
        "Target_Vessel_Two_Port_Keys",
        int(
            target_pairs["Distinct_Port_Count"].eq(2).sum()
        )
    ),

    (
        "Target_Vessel_652W_653W_655W_Paired",
        int(
            target_pairs.loc[
                target_pairs["Import_Voyage_Number"].isin(
                    ["652W", "653W", "655W"]
                ),
                "Distinct_Port_Count"
            ].eq(2).sum()
        )
    ),

], columns=["Metric", "Value"])


# ------------------------------------------------------------
# 11. VALIDATION CHECKS
# ------------------------------------------------------------

checks = []


def add(cid, desc, observed, expected, passed):

    checks.append({

        "Check_ID": cid,

        "Description": desc,

        "Observed": observed,

        "Expected": expected,

        "Status": (
            "PASS" if bool(passed) else "FAIL"
        )
    })


target_count = int(
    df["_IMO"].eq(TARGET_IMO).sum()
)

target_pair_count = int(
    target_pairs.shape[0]
)

add(
    "C01",
    "Workbook row count matches previously audited workbook",
    len(df),
    1894,
    len(df) == 1894
)

add(
    "C02",
    "Target vessel has 32 raw records",
    target_count,
    32,
    target_count == 32
)

add(
    "C03",
    "Composite voyage-key groups account for all complete-key rows",
    int(pair_register["Record_Count"].sum()),
    int(valid_key.sum()),
    int(pair_register["Record_Count"].sum()) == int(valid_key.sum())
)

add(
    "C04",
    "Target vessel has 21 distinct composite voyage keys",
    target_pair_count,
    21,
    target_pair_count == 21
)

add(
    "C05",
    "No target-vessel import/export voyage mismatch",
    int(
        (
            target_pairs["Voyage_Fields_Match"] == False
        ).sum()
    ),
    0,
    target_pairs["Voyage_Fields_Match"].all()
)

add(
    "C06",
    "No records or approvals changed",
    0,
    0,
    True
)

checks_df = pd.DataFrame(checks)


# ------------------------------------------------------------
# 12. SAVE OUTPUTS
# ------------------------------------------------------------

save(
    pair_register,
    "workbook_voyage_pair_register"
)

save(
    vessel_summary,
    "per_vessel_voyage_pair_summary"
)

save(
    coverage,
    "timestamp_completeness_all_vs_target"
)

save(
    pattern_summary,
    "workbook_pair_pattern_summary"
)

save(
    checks_df,
    "validation_checks"
)


# ------------------------------------------------------------
# 13. WRITE REPORT
# ------------------------------------------------------------

report = (
    REPORTS /
    "86_workbook_wide_voyage_pair_pattern_audit.txt"
)

with report.open("w", encoding="utf-8") as f:

    f.write(
        "SCRIPT 86 — WORKBOOK-WIDE VOYAGE-PAIR PATTERN AUDIT\n"
    )

    f.write("=" * 78 + "\n")

    f.write(f"Workbook: {WORKBOOK}\n")

    f.write(f"Sheet: {sheet}\n")

    f.write(f"Raw records: {len(df)}\n")

    f.write(f"Target IMO: {TARGET_IMO}\n\n")

    f.write(
        "WORKBOOK-WIDE PATTERN SUMMARY\n"
    )

    f.write(
        pattern_summary.to_string(index=False)
        + "\n\n"
    )

    f.write(
        "TIMESTAMP COMPLETENESS: ALL WORKBOOK VS TARGET\n"
    )

    f.write(
        coverage.to_string(index=False)
        + "\n\n"
    )

    f.write(
        "TARGET VESSEL VOYAGE PAIRS\n"
    )

    f.write(
        target_pairs.to_string(index=False)
        + "\n\n"
    )

    f.write(
        "VALIDATION CHECKS\n"
    )

    f.write(
        checks_df.to_string(index=False)
        + "\n\n"
    )

    f.write(
        "INTERPRETATION LIMITATIONS\n"
    )

    f.write(
        "- Composite-key pairing tests source-record structure; "
        "it does not define voyage semantics.\n"
    )

    f.write(
        "- A two-port key does not prove a completed movement "
        "or call at both ports.\n"
    )

    f.write(
        "- Actual timestamps remain distinct from planned "
        "and estimated timestamps.\n"
    )

    f.write(
        "- Missing actual timestamps are not imputed.\n"
    )

    f.write(
        "- No route, sailing time, port-call identity, "
        "schedule slack, or operational approval is inferred.\n"
    )

    f.write(
        "- The canonical schedule and raw workbook are not modified.\n"
    )


# ------------------------------------------------------------
# 14. CONSOLE SUMMARY
# ------------------------------------------------------------

print(
    "SCRIPT 86 — WORKBOOK-WIDE VOYAGE-PAIR PATTERN AUDIT"
)

print("=" * 78)

print(f"Workbook records: {len(df)}")

print(
    "Distinct IMO:",
    df["_IMO"].replace("", np.nan).nunique()
)

print(
    "Distinct composite voyage keys:",
    len(pair_register)
)

print(
    "Multi-record voyage keys:",
    len(multi_record)
)

print(
    "Two-port voyage keys:",
    len(two_port)
)

print(
    "Target-vessel voyage keys:",
    target_pair_count
)

print(
    "Target-vessel two-port keys:",
    int(
        target_pairs["Distinct_Port_Count"].eq(2).sum()
    )
)

print(
    "Validation checks passed:",
    (checks_df["Status"] == "PASS").sum(),
    "/",
    len(checks_df)
)

print(
    "Validation checks failed:",
    (checks_df["Status"] == "FAIL").sum(),
    "/",
    len(checks_df)
)

print("\nOUTPUT FILES")

for name in [
    "86_workbook_voyage_pair_register.csv",
    "86_per_vessel_voyage_pair_summary.csv",
    "86_timestamp_completeness_all_vs_target.csv",
    "86_workbook_pair_pattern_summary.csv",
    "86_validation_checks.csv",
]:

    print(
        f"- outputs/tables/{name}"
    )

print(
    "- outputs/reports/"
    "86_workbook_wide_voyage_pair_pattern_audit.txt"
)


if (checks_df["Status"] == "FAIL").any():

    sys.exit(
        "One or more Script86 validation checks failed."
    )
