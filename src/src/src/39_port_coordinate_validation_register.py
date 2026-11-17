
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import date

# ============================================================
# SCRIPT 39
# PORT COORDINATE VALIDATION REGISTER
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "tables"
    / "38_port_evidence_validation_register.csv"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "tables"
    / "39_port_coordinate_validation_register.csv"
)

REPORT_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "reports"
    / "39_port_coordinate_validation_report.txt"
)

# ============================================================
# 1. DIRECTORY AND INPUT CHECKS
# ============================================================

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Input file not found: {INPUT_FILE}"
    )

source = pd.read_csv(
    INPUT_FILE,
    encoding="utf-8-sig"
)

if len(source) != 19:
    raise ValueError(
        f"Expected 19 port records, found {len(source)}"
    )

if len(source.columns) != 57:
    raise ValueError(
        f"Expected 57 source columns, found {len(source.columns)}"
    )

required_columns = [
    "UN_LOCODE",
    "Port_Name_in_Master",
    "Country_Code",
    "Preliminary_Geographic_Role",
    "Research_Relevance_Screen",
    "Coordinate_Assessment",
    "Accepted_Latitude",
    "Accepted_Longitude",
    "Coordinate_Reference_Type",
    "Researcher_Validated_Port_Name",
    "Researcher_Validated_Facility_Name",
    "Coordinate_Validation_Status",
    "Validated_Latitude",
    "Validated_Longitude",
    "Validated_Coordinate_Type",
    "Coordinate_Evidence_Description",
    "Coordinate_Evidence_URL",
    "Port_Terminal_Distinction_Notes",
    "Researcher_Review_Status",
    "Researcher_Reviewer_Notes",
]

missing = [
    col for col in required_columns
    if col not in source.columns
]

if missing:
    raise ValueError(
        f"Required columns missing from Script 38: {missing}"
    )

if source["UN_LOCODE"].isna().any():
    raise ValueError("Missing UN_LOCODE values detected.")

if source["UN_LOCODE"].duplicated().any():
    raise ValueError("Duplicate UN_LOCODE values detected.")

# ============================================================
# 2. LOAD EXISTING SCRIPT 39 IF IT ALREADY EXISTS
#    This preserves manually entered coordinate evidence.
# ============================================================

existing = None

if OUTPUT_FILE.exists():
    existing = pd.read_csv(
        OUTPUT_FILE,
        encoding="utf-8-sig",
        dtype=str,
        keep_default_na=False
    )

    if "UN_LOCODE" not in existing.columns:
        raise ValueError(
            "Existing Script 39 output has no UN_LOCODE column."
        )

    if existing["UN_LOCODE"].duplicated().any():
        raise ValueError(
            "Duplicate UN_LOCODE values in existing Script 39 output."
        )

# ============================================================
# 3. DEFINE SCRIPT 39 REGISTER
# ============================================================

register_columns = [
    # Port identity and geography
    "UN_LOCODE",
    "Port_Name_in_Master",
    "Researcher_Validated_Port_Name",
    "Researcher_Validated_Facility_Name",
    "Country_Code",
    "Preliminary_Geographic_Role",
    "Research_Relevance_Screen",

    # Original coordinate evidence
    "Original_Coordinate_Assessment",
    "Original_Accepted_Latitude",
    "Original_Accepted_Longitude",
    "Original_Coordinate_Reference_Type",
    "Original_Researcher_Coordinate_Status",
    "Original_Validated_Latitude",
    "Original_Validated_Longitude",
    "Original_Validated_Coordinate_Type",
    "Original_Coordinate_Evidence_Description",
    "Original_Coordinate_Evidence_URL",
    "Port_Terminal_Distinction_Notes",

    # Independently validated PORT coordinates
    "Validated_Port_Latitude",
    "Validated_Port_Longitude",
    "Port_Coordinate_Type",
    "Port_Coordinate_Scope",

    # Independently validated TERMINAL coordinates
    "Validated_Terminal_Latitude",
    "Validated_Terminal_Longitude",
    "Terminal_Name",
    "Terminal_Coordinate_Type",

    # Evidence and provenance
    "Coordinate_Source_Organization",
    "Coordinate_Source_Title",
    "Coordinate_Source_URL",
    "Coordinate_Source_Access_Date",
    "Coordinate_Evidence_Description",

    # Validation decision
    "Coordinate_Validation_Status",
    "Coordinate_Confidence",
    "Coordinate_Reviewer",
    "Coordinate_Review_Date",
    "Coordinate_Review_Notes",
]

# ============================================================
# 4. BUILD INITIAL REGISTER FROM SCRIPT 38
# ============================================================

records = []

for _, row in source.iterrows():

    record = {
        "UN_LOCODE": row["UN_LOCODE"],
        "Port_Name_in_Master": row["Port_Name_in_Master"],
        "Researcher_Validated_Port_Name":
            row["Researcher_Validated_Port_Name"],
        "Researcher_Validated_Facility_Name":
            row["Researcher_Validated_Facility_Name"],
        "Country_Code": row["Country_Code"],
        "Preliminary_Geographic_Role":
            row["Preliminary_Geographic_Role"],
        "Research_Relevance_Screen":
            row["Research_Relevance_Screen"],

        "Original_Coordinate_Assessment":
            row["Coordinate_Assessment"],
        "Original_Accepted_Latitude":
            row["Accepted_Latitude"],
        "Original_Accepted_Longitude":
            row["Accepted_Longitude"],
        "Original_Coordinate_Reference_Type":
            row["Coordinate_Reference_Type"],
        "Original_Researcher_Coordinate_Status":
            row["Coordinate_Validation_Status"],
        "Original_Validated_Latitude":
            row["Validated_Latitude"],
        "Original_Validated_Longitude":
            row["Validated_Longitude"],
        "Original_Validated_Coordinate_Type":
            row["Validated_Coordinate_Type"],
        "Original_Coordinate_Evidence_Description":
            row["Coordinate_Evidence_Description"],
        "Original_Coordinate_Evidence_URL":
            row["Coordinate_Evidence_URL"],
        "Port_Terminal_Distinction_Notes":
            row["Port_Terminal_Distinction_Notes"],

        # New manual fields: deliberately left blank
        "Validated_Port_Latitude": "",
        "Validated_Port_Longitude": "",
        "Port_Coordinate_Type": "",
        "Port_Coordinate_Scope": "",

        "Validated_Terminal_Latitude": "",
        "Validated_Terminal_Longitude": "",
        "Terminal_Name": "",
        "Terminal_Coordinate_Type": "",

        "Coordinate_Source_Organization": "",
        "Coordinate_Source_Title": "",
        "Coordinate_Source_URL": "",
        "Coordinate_Source_Access_Date": "",
        "Coordinate_Evidence_Description": "",

        "Coordinate_Validation_Status": "PENDING",
        "Coordinate_Confidence": "NOT_ASSESSED",
        "Coordinate_Reviewer": "",
        "Coordinate_Review_Date": "",
        "Coordinate_Review_Notes": "",
    }

    records.append(record)

register = pd.DataFrame(
    records,
    columns=register_columns
)

# ============================================================
# 5. PRESERVE EXISTING MANUAL SCRIPT 39 WORK
# ============================================================

manual_columns = [
    col for col in register_columns
    if col not in [
        "UN_LOCODE",
        "Port_Name_in_Master",
        "Researcher_Validated_Port_Name",
        "Researcher_Validated_Facility_Name",
        "Country_Code",
        "Preliminary_Geographic_Role",
        "Research_Relevance_Screen",
        "Original_Coordinate_Assessment",
        "Original_Accepted_Latitude",
        "Original_Accepted_Longitude",
        "Original_Coordinate_Reference_Type",
        "Original_Researcher_Coordinate_Status",
        "Original_Validated_Latitude",
        "Original_Validated_Longitude",
        "Original_Validated_Coordinate_Type",
        "Original_Coordinate_Evidence_Description",
        "Original_Coordinate_Evidence_URL",
        "Port_Terminal_Distinction_Notes",
    ]
]

if existing is not None:

    existing_codes = set(existing["UN_LOCODE"])
    source_codes = set(register["UN_LOCODE"])

    unexpected = existing_codes - source_codes

    if unexpected:
        raise ValueError(
            f"Existing Script 39 contains unknown ports: {unexpected}"
        )

    existing_indexed = existing.set_index("UN_LOCODE")

    for i, row in register.iterrows():

        code = row["UN_LOCODE"]

        if code not in existing_indexed.index:
            continue

        old = existing_indexed.loc[code]

        for col in manual_columns:

            if col in existing.columns:
                register.at[i, col] = old[col]

# ============================================================
# 6. DATA QUALITY VALIDATION
# ============================================================

def is_blank(value):
    return (
        pd.isna(value)
        or str(value).strip() == ""
    )


def numeric_value(value):
    if is_blank(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


quality_issues = []

for i, row in register.iterrows():

    code = row["UN_LOCODE"]

    # Port coordinate pair
    lat = numeric_value(row["Validated_Port_Latitude"])
    lon = numeric_value(row["Validated_Port_Longitude"])

    if (lat is None) != (lon is None):
        quality_issues.append(
            f"{code}: incomplete port coordinate pair."
        )

    if lat is not None and not -90 <= lat <= 90:
        quality_issues.append(
            f"{code}: port latitude outside valid range."
        )

    if lon is not None and not -180 <= lon <= 180:
        quality_issues.append(
            f"{code}: port longitude outside valid range."
        )

    # Terminal coordinate pair
    tlat = numeric_value(row["Validated_Terminal_Latitude"])
    tlon = numeric_value(row["Validated_Terminal_Longitude"])

    if (tlat is None) != (tlon is None):
        quality_issues.append(
            f"{code}: incomplete terminal coordinate pair."
        )

    if tlat is not None and not -90 <= tlat <= 90:
        quality_issues.append(
            f"{code}: terminal latitude outside valid range."
        )

    if tlon is not None and not -180 <= tlon <= 180:
        quality_issues.append(
            f"{code}: terminal longitude outside valid range."
        )

    # A verified coordinate must have a complete evidence trail.
    status = str(
        row["Coordinate_Validation_Status"]
    ).strip().upper()

    if status == "VERIFIED":

        required_evidence = [
            "Validated_Port_Latitude",
            "Validated_Port_Longitude",
            "Port_Coordinate_Type",
            "Port_Coordinate_Scope",
            "Coordinate_Source_Organization",
            "Coordinate_Source_URL",
            "Coordinate_Evidence_Description",
            "Coordinate_Reviewer",
            "Coordinate_Review_Date",
        ]

        missing_evidence = [
            field for field in required_evidence
            if is_blank(row[field])
        ]

        if missing_evidence:
            quality_issues.append(
                f"{code}: VERIFIED status has missing evidence: "
                f"{missing_evidence}"
            )

# ============================================================
# 7. SAVE REGISTER
# ============================================================

register.to_csv(
    OUTPUT_FILE,
    index=False,
    encoding="utf-8-sig"
)

# ============================================================
# 8. GENERATE SUMMARY REPORT
# ============================================================

status_counts = (
    register["Coordinate_Validation_Status"]
    .value_counts(dropna=False)
    .to_dict()
)

confidence_counts = (
    register["Coordinate_Confidence"]
    .value_counts(dropna=False)
    .to_dict()
)

report = []

report.append("=" * 65)
report.append("SCRIPT 39: PORT COORDINATE VALIDATION REPORT")
report.append("=" * 65)

report.append("")
report.append(f"Execution date: {date.today()}")
report.append(f"Input records: {len(source)}")
report.append(f"Output records: {len(register)}")
report.append(f"Output columns: {len(register.columns)}")

report.append("")
report.append("COORDINATE VALIDATION STATUS")
report.append("-" * 40)

for status, count in status_counts.items():
    report.append(f"{status}: {count}")

report.append("")
report.append("COORDINATE CONFIDENCE")
report.append("-" * 40)

for confidence, count in confidence_counts.items():
    report.append(f"{confidence}: {count}")

report.append("")
report.append("COORDINATE DATA COMPLETENESS")
report.append("-" * 40)

port_coordinates = (
    register["Validated_Port_Latitude"].ne("")
    & register["Validated_Port_Longitude"].ne("")
).sum()

terminal_coordinates = (
    register["Validated_Terminal_Latitude"].ne("")
    & register["Validated_Terminal_Longitude"].ne("")
).sum()

report.append(
    f"Ports with coordinate pairs: {port_coordinates}"
)

report.append(
    f"Terminals with coordinate pairs: {terminal_coordinates}"
)

report.append("")
report.append("QUALITY CONTROL")
report.append("-" * 40)

if quality_issues:
    report.append(
        f"Quality issues identified: {len(quality_issues)}"
    )

    for issue in quality_issues:
        report.append(f"- {issue}")
else:
    report.append(
        "No coordinate-format or evidence-completeness issues detected."
    )

report.append("")
report.append("METHODOLOGICAL LIMITATIONS")
report.append("-" * 40)

report.append(
    "1. This script creates a validation register; it does not "
    "independently verify coordinates."
)

report.append(
    "2. Blank coordinates are intentional and must be researched."
)

report.append(
    "3. Port and terminal coordinates must remain separate."
)

report.append(
    "4. A valid latitude/longitude range does not prove geographic accuracy."
)

report.append(
    "5. Coordinate validation does not establish AIS-confirmed "
    "Strait of Hormuz transit."
)

report.append(
    "6. Original Script 38 evidence is preserved in separate columns."
)

report.append("")
report.append("OUTPUT FILES")
report.append("-" * 40)

report.append(str(OUTPUT_FILE))
report.append(str(REPORT_FILE))

report.append("")
report.append("=" * 65)
report.append("END OF SCRIPT 39 REPORT")
report.append("=" * 65)

REPORT_FILE.write_text(
    "\n".join(report),
    encoding="utf-8"
)

# ============================================================
# 9. FINAL TERMINAL SUMMARY
# ============================================================

print("\n" + "=" * 60)
print("SCRIPT 39 COMPLETED")
print("=" * 60)

print("Input records:", len(source))
print("Output records:", len(register))
print("Output columns:", len(register.columns))

print("\nCOORDINATE VALIDATION STATUS")

for status, count in status_counts.items():
    print(f"{status}: {count}")

print("\nPORT COORDINATE PAIRS:", port_coordinates)
print("TERMINAL COORDINATE PAIRS:", terminal_coordinates)

print("\nQUALITY ISSUES:", len(quality_issues))

for issue in quality_issues:
    print("WARNING:", issue)

print("\nOUTPUTS:")
print(OUTPUT_FILE)
print(REPORT_FILE)

print("\nIMPORTANT:")
print("No coordinates were automatically approved.")
print("Manual evidence validation is still required.")

print("\nALL 19 PORTS TRANSFERRED TO SCRIPT 39.")
