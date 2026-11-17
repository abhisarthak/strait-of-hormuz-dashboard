
from pathlib import Path
import pandas as pd


# ============================================================
# 1. PROJECT PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

SOURCE_FILE = (
    PROCESSED_DIR
    / "06_integrated_schedule_vessel_port.csv"
)

OVERLAP_FILE = (
    OUTPUT_DIR
    / "09_vessel_port_stay_overlaps.csv"
)

TARGET_RECORDS_FILE = (
    OUTPUT_DIR
    / "09c_target_vessel_all_source_records.csv"
)


# ============================================================
# 2. INVESTIGATION CASES
#
# Source row numbers are from Script 09C.
# These are investigation classifications, not corrections.
# ============================================================

CASES = [

    {
        "Case_ID": "OVL_001",
        "IMO": "9235531",
        "Vessel": "MAERSK VIRGINIA",
        "Port": "SALALAH",
        "LOCODE": "OMSLL",
        "Source_Rows": [1239, 1240],
        "Classification": "PROBABLE_DUPLICATE_REPRESENTATION",
        "Actual_Sequence_Status": "VALID",
        "Estimated_Sequence_Status": "VALID",
        "Planned_Sequence_Status": "VALID",
        "Investigation_Reason": (
            "Identical port and all six timestamps, "
            "same import/export voyages, different service codes."
        ),
        "Recommended_Treatment": (
            "Retain both source records; investigate service-code meaning."
        ),
    },

    {
        "Case_ID": "OVL_002",
        "IMO": "9263320",
        "Vessel": "SLS TOPAZ",
        "Port": "SALALAH",
        "LOCODE": "OMSLL",
        "Source_Rows": [1100, 1101],
        "Classification": "PROBABLE_DUPLICATE_REPRESENTATION",
        "Actual_Sequence_Status": "VALID",
        "Estimated_Sequence_Status": "VALID",
        "Planned_Sequence_Status": "VALID",
        "Investigation_Reason": (
            "Identical port and all six timestamps, "
            "same import/export voyages, different service codes."
        ),
        "Recommended_Treatment": (
            "Retain both source records; investigate service-code meaning."
        ),
    },

    {
        "Case_ID": "OVL_003",
        "IMO": "9332975",
        "Vessel": "MAERSK CHICAGO",
        "Port": "KHOR FAKKAN",
        "LOCODE": "AEKLF",
        "Source_Rows": [950, 951],
        "Classification": "PROBABLE_DUPLICATE_REPRESENTATION",
        "Actual_Sequence_Status": "VALID",
        "Estimated_Sequence_Status": "VALID",
        "Planned_Sequence_Status": "VALID",
        "Investigation_Reason": (
            "Identical port and all six timestamps, "
            "same import/export voyages, different service codes."
        ),
        "Recommended_Treatment": (
            "Retain both source records; investigate service-code meaning."
        ),
    },

    {
        "Case_ID": "OVL_004",
        "IMO": "9202259",
        "Vessel": "DUBAI VENTURE",
        "Port": "JEBEL ALI - AJMAN",
        "LOCODE": "AEJEA - AEAJM",
        "Source_Rows": [48, 169],
        "Classification": "PLANNED_ESTIMATED_SCHEDULE_INCONSISTENCY",
        "Actual_Sequence_Status": "VALID",
        "Estimated_Sequence_Status": "OVERLAP_DETECTED",
        "Planned_Sequence_Status": "OVERLAP_DETECTED",
        "Investigation_Reason": (
            "Estimated and planned intervals overlap by three hours "
            "between different ports. Actual departure and subsequent "
            "arrival are chronologically consistent."
        ),
        "Recommended_Treatment": (
            "Retain both records; use actual timestamps for historical "
            "analysis and flag estimated/planned inconsistency."
        ),
    },

    {
        "Case_ID": "OVL_005",
        "IMO": "9235567",
        "Vessel": "MAERSK GAIRLOCH",
        "Port": "KHOR FAKKAN - SOHAR",
        "LOCODE": "AEKLF - OMSOH",
        "Source_Rows": [953, 1868],
        "Classification": "PLANNED_SCHEDULE_INCONSISTENCY",
        "Actual_Sequence_Status": "VALID",
        "Estimated_Sequence_Status": "VALID",
        "Planned_Sequence_Status": "OVERLAP_DETECTED",
        "Investigation_Reason": (
            "Planned intervals overlap by 49 hours between different "
            "ports. Estimated and actual timestamps show chronological "
            "consistency."
        ),
        "Recommended_Treatment": (
            "Retain both records; use actual timestamps for historical "
            "analysis and flag planned schedule inconsistency."
        ),
    },
]


# ============================================================
# 3. LOAD SOURCE DATA
# ============================================================

if not SOURCE_FILE.exists():
    raise FileNotFoundError(SOURCE_FILE)

if not OVERLAP_FILE.exists():
    raise FileNotFoundError(OVERLAP_FILE)

if not TARGET_RECORDS_FILE.exists():
    raise FileNotFoundError(TARGET_RECORDS_FILE)

source_df = pd.read_csv(
    SOURCE_FILE,
    low_memory=False
)

overlap_df = pd.read_csv(
    OVERLAP_FILE,
    low_memory=False
)

target_df = pd.read_csv(
    TARGET_RECORDS_FILE,
    low_memory=False
)


# ============================================================
# 4. NORMALIZE IDENTIFIERS
# ============================================================

def normalize_imo(series):

    result = (
        series.astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )

    return result.str.replace(r"\.0$", "", regex=True)


source_df["Analysis_IMO"] = normalize_imo(
    source_df["IMO Number"]
)

target_df["Analysis_IMO"] = normalize_imo(
    target_df["Analysis_IMO"]
)

source_df.insert(
    0,
    "Source_Row_Number",
    range(1, len(source_df) + 1)
)

source_df["Source_Row_Number"] = (
    source_df["Source_Row_Number"].astype(int)
)

target_df["Source_Row_Number"] = (
    pd.to_numeric(
        target_df["Source_Row_Number"],
        errors="raise"
    ).astype(int)
)


# ============================================================
# 5. CREATE CASE-LEVEL CLASSIFICATION TABLE
# ============================================================

case_df = pd.DataFrame(CASES)

case_df["Number_Of_Source_Rows"] = (
    case_df["Source_Rows"].apply(len)
)

case_df["Resolution_Status"] = "FLAGGED_NOT_CORRECTED"

case_df["Source_Records_Preserved"] = True

case_df["Confirmed_Duplicate"] = False

case_df["Confirmed_Data_Error"] = False

case_df["Final_Validation_Required"] = True


# ============================================================
# 6. VERIFY SOURCE ROWS
# ============================================================

verification_records = []

for case in CASES:

    for row_number in case["Source_Rows"]:

        matched = source_df[
            source_df["Source_Row_Number"] == row_number
        ]

        if matched.empty:
            verification_records.append({
                "Case_ID": case["Case_ID"],
                "Source_Row_Number": row_number,
                "IMO": case["IMO"],
                "Verification_Status": "SOURCE_ROW_NOT_FOUND",
            })

            continue

        actual_imo = matched.iloc[0]["Analysis_IMO"]

        verification_records.append({
            "Case_ID": case["Case_ID"],
            "Source_Row_Number": row_number,
            "IMO": case["IMO"],
            "Actual_Source_IMO": actual_imo,
            "Verification_Status": (
                "VERIFIED"
                if actual_imo == case["IMO"]
                else "IMO_MISMATCH"
            ),
        })


verification_df = pd.DataFrame(verification_records)


# ============================================================
# 7. CREATE ROW-LEVEL REVIEW FLAGS
# ============================================================

row_flags = []

for case in CASES:

    for row_number in case["Source_Rows"]:

        row_flags.append({

            "Case_ID": case["Case_ID"],

            "Source_Row_Number": row_number,

            "IMO": case["IMO"],

            "Vessel": case["Vessel"],

            "Classification": case["Classification"],

            "Actual_Sequence_Status": (
                case["Actual_Sequence_Status"]
            ),

            "Estimated_Sequence_Status": (
                case["Estimated_Sequence_Status"]
            ),

            "Planned_Sequence_Status": (
                case["Planned_Sequence_Status"]
            ),

            "Recommended_Treatment": (
                case["Recommended_Treatment"]
            ),

            "Review_Status": "REQUIRES_FINAL_REVIEW",

            "Delete_Record": False,

            "Modify_Source_Record": False,
        })


row_flags_df = pd.DataFrame(row_flags)


# ============================================================
# 8. ATTACH ORIGINAL SOURCE INFORMATION
# ============================================================

original_columns = [
    "Source_Row_Number",
    "IMO Number",
    "Vessel Name",
    "portName",
    "UNLocationCode",
    "Carrier Service Code",
    "Import Voyage Number",
    "Export Voyage Number",
    "Planned Arrival",
    "Estimated Arrival",
    "Actual Arrival",
    "Planned Departure",
    "Estimated Departure",
    "Actual Departure",
]

available_columns = [
    col for col in original_columns
    if col in source_df.columns
]

row_flags_df = row_flags_df.merge(
    source_df[available_columns],
    on="Source_Row_Number",
    how="left",
    validate="one_to_one"
)


# ============================================================
# 9. VERIFY OVERLAP SOURCE COVERAGE
# ============================================================

# All five investigated cases should be represented
# in the original Script 09 overlap output.

overlap_imos = set(
    normalize_imo(overlap_df["IMO"]).dropna()
)

case_imos = set(case_df["IMO"])

case_df["Present_In_Script_09_Overlaps"] = (
    case_df["IMO"].isin(overlap_imos)
)

# Check source row verification
verification_by_case = (
    verification_df.groupby("Case_ID")[
        "Verification_Status"
    ]
    .apply(
        lambda x: "ALL_VERIFIED"
        if (x == "VERIFIED").all()
        else "REVIEW_REQUIRED"
    )
    .to_dict()
)

case_df["Source_Row_Verification"] = (
    case_df["Case_ID"]
    .map(verification_by_case)
)


# ============================================================
# 10. SAVE OUTPUTS
# ============================================================

case_file = (
    OUTPUT_DIR
    / "09d_overlap_investigation_classification.csv"
)

row_file = (
    OUTPUT_DIR
    / "09d_schedule_record_review_flags.csv"
)

verification_file = (
    OUTPUT_DIR
    / "09d_source_row_verification.csv"
)

case_df.to_csv(case_file, index=False)

row_flags_df.to_csv(row_file, index=False)

verification_df.to_csv(
    verification_file,
    index=False
)


# ============================================================
# 11. GENERATE REPORT
# ============================================================

report = []

report.append(
    "SCRIPT 09D: OVERLAP INVESTIGATION CLASSIFICATION"
)

report.append("=" * 75)

report.append(
    f"Total source schedule records: {len(source_df)}"
)

report.append(
    f"Original Script 09 overlap records: {len(overlap_df)}"
)

report.append(
    f"Underlying investigation cases: {len(case_df)}"
)

report.append(
    f"Source records flagged for review: {len(row_flags_df)}"
)

report.append("")

report.append("CASE CLASSIFICATION SUMMARY")

report.append(
    case_df["Classification"]
    .value_counts()
    .to_string()
)

report.append("")

report.append("SOURCE ROW VERIFICATION")

report.append(
    verification_df[
        "Verification_Status"
    ].value_counts().to_string()
)

report.append("")

report.append("CASE DETAILS")

for _, row in case_df.iterrows():

    report.append("")
    report.append("-" * 75)

    report.append(
        f"Case: {row['Case_ID']}"
    )

    report.append(
        f"IMO: {row['IMO']}"
    )

    report.append(
        f"Vessel: {row['Vessel']}"
    )

    report.append(
        f"Classification: {row['Classification']}"
    )

    report.append(
        f"Source rows: {row['Source_Rows']}"
    )

    report.append(
        f"Actual: {row['Actual_Sequence_Status']}"
    )

    report.append(
        f"Estimated: {row['Estimated_Sequence_Status']}"
    )

    report.append(
        f"Planned: {row['Planned_Sequence_Status']}"
    )

    report.append(
        f"Reason: {row['Investigation_Reason']}"
    )

    report.append(
        f"Treatment: {row['Recommended_Treatment']}"
    )

    report.append(
        f"Verification: {row['Source_Row_Verification']}"
    )


report.extend([
    "",
    "=" * 75,
    "IMPORTANT DATA GOVERNANCE NOTES",
    "=" * 75,
    "1. Original source records have not been deleted.",
    "2. Original source timestamps have not been modified.",
    "3. Probable duplicate representations are not confirmed duplicates.",
    "4. Actual, estimated and planned timestamps remain separate.",
    "5. All classifications are investigation flags.",
    "6. Source row verification must pass before further use.",
    "7. Final deduplication decisions require additional evidence.",
])

report_path = (
    REPORT_DIR
    / "09d_overlap_investigation_report.txt"
)

report_path.write_text(
    "\n".join(report),
    encoding="utf-8"
)


# ============================================================
# 12. TERMINAL SUMMARY
# ============================================================

print("\n" + "=" * 75)
print("SCRIPT 09D COMPLETED")
print("=" * 75)

print("\nCASE CLASSIFICATION")

print(
    case_df[
        [
            "Case_ID",
            "IMO",
            "Classification",
            "Source_Row_Verification",
        ]
    ].to_string(index=False)
)

print("\nCLASSIFICATION COUNTS")

print(
    case_df["Classification"]
    .value_counts()
    .to_string()
)

print("\nSOURCE ROW VERIFICATION")

print(
    verification_df[
        "Verification_Status"
    ].value_counts().to_string()
)

print("\nOUTPUT FILES")

print(case_file)
print(row_file)
print(verification_file)
print(report_path)

print("\nNo original records were modified or deleted.")
