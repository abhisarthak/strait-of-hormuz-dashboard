
"""
SCRIPT 41: MANUAL SOURCE-CONTENT VERIFICATION REGISTER

Purpose
-------
Prepare a structured researcher-review register for the 19 shortlisted
ports/locations using outputs from Scripts 38, 39 and 40.

This script:
1. Reads the Script 38 evidence validation register.
2. Reads the Script 39 coordinate validation register.
3. Optionally reads the Script 40 source evidence audit.
4. Combines records using UN_LOCODE.
5. Creates a manual source-content verification register.
6. Preserves researcher-entered decisions when rerun.
7. Generates a summary report.

IMPORTANT
---------
- No source is automatically verified.
- URL accessibility does not establish evidence validity.
- No coordinates are approved by this script.
- No operational inclusion decisions are changed.
- Scripts 38, 39 and 40 are read-only inputs.
"""

from pathlib import Path
from datetime import date
import csv
import sys


# ============================================================
# 1. PATHS
# ============================================================

ROOT = Path.cwd()

SCRIPT38_FILE = (
    ROOT / "outputs" / "tables" /
    "38_port_evidence_validation_register.csv"
)

SCRIPT39_FILE = (
    ROOT / "outputs" / "tables" /
    "39_port_coordinate_validation_register.csv"
)

SCRIPT40_FILE = (
    ROOT / "outputs" / "tables" /
    "40_source_evidence_audit.csv"
)

OUTPUT_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

OUTPUT_FILE = (
    OUTPUT_DIR / "41_manual_source_content_verification_register.csv"
)

REPORT_FILE = (
    REPORT_DIR / "41_manual_source_content_verification_report.txt"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. CSV UTILITIES
# ============================================================

def read_csv(path, required=True):

    if not path.exists():

        if required:
            raise FileNotFoundError(
                f"Required input file not found:\n{path}"
            )

        print(f"OPTIONAL FILE NOT FOUND: {path.name}")
        return {}

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise ValueError(
                f"CSV has no header: {path.name}"
            )

        records = {}

        for row in reader:

            code = (row.get("UN_LOCODE") or "").strip()

            if not code:
                continue

            if code in records:
                raise ValueError(
                    f"Duplicate UN_LOCODE {code} in {path.name}"
                )

            records[code] = row

    print(
        f"Loaded {len(records)} records: {path.name}"
    )

    return records


def clean(value):

    if value is None:
        return ""

    return str(value).strip()


def combine_unique(*values):

    result = []

    for value in values:

        value = clean(value)

        if not value:
            continue

        # Support multiple URLs separated by semicolons or newlines.
        parts = value.replace("\n", ";").split(";")

        for part in parts:

            part = part.strip()

            if part and part not in result:
                result.append(part)

    return " | ".join(result)


def get(row, field):

    if not row:
        return ""

    return clean(row.get(field, ""))


# ============================================================
# 3. LOAD INPUT REGISTERS
# ============================================================

print("\n" + "=" * 70)
print("SCRIPT 41: MANUAL SOURCE-CONTENT VERIFICATION")
print("=" * 70)

script38 = read_csv(SCRIPT38_FILE, required=True)
script39 = read_csv(SCRIPT39_FILE, required=True)
script40 = read_csv(SCRIPT40_FILE, required=False)

if not script38:
    raise ValueError("Script 38 contains no records.")

if not script39:
    raise ValueError("Script 39 contains no records.")


# ============================================================
# 4. CHECK RECORD CONSISTENCY
# ============================================================

codes38 = set(script38)
codes39 = set(script39)

if codes38 != codes39:

    missing39 = sorted(codes38 - codes39)
    missing38 = sorted(codes39 - codes38)

    raise ValueError(
        "\nUN_LOCODE mismatch between Scripts 38 and 39.\n"
        f"Missing from Script 39: {missing39}\n"
        f"Missing from Script 38: {missing38}"
    )

if script40:

    extra40 = sorted(set(script40) - codes38)

    if extra40:
        print(
            "WARNING: Script 40 contains additional LOCODEs:",
            extra40
        )


# ============================================================
# 5. MANUAL REVIEW FIELDS
# ============================================================

manual_fields = [

    "Source_Content_Review_Status",

    "Primary_Source_Content_Verified",

    "Secondary_Source_Content_Verified",

    "Port_Identity_Claim_Verified",

    "Facility_Identity_Claim_Verified",

    "Geographic_Claim_Verified",

    "Coordinate_Claim_Verified",

    "Operational_Role_Claim_Verified",

    "Verified_Claims",

    "Unsupported_or_Contradictory_Claims",

    "Source_Content_Review_Conclusion",

    "Source_Strength_Assessment",

    "Additional_Source_Required",

    "Researcher_Review_Status",

    "Researcher_Reviewer",

    "Researcher_Review_Date",

    "Researcher_Review_Notes",

]


# ============================================================
# 6. OUTPUT SCHEMA
# ============================================================

output_fields = [

    # Identification
    "UN_LOCODE",
    "Port_Name_in_Master",
    "Researcher_Validated_Port_Name",
    "Researcher_Validated_Facility_Name",
    "Country_Code",

    # Research classification
    "Preliminary_Geographic_Role",
    "Research_Relevance_Screen",
    "Provisional_Facility_Type",
    "Facility_or_Port_System",

    # Network relevance
    "Observed_Call_Count",
    "Observed_Vessel_Count",
    "In_Degree",
    "Out_Degree",
    "Betweenness_Centrality",
    "Network_Match_Status",

    # Identity evidence
    "Identity_Validation_Status",
    "Identity_Evidence_Description",
    "Identity_Evidence_URL",

    # Original source references
    "Primary_Evidence_URL",
    "Independent_Secondary_Evidence_URL",
    "Coordinate_Source_URL",
    "All_Source_URLs",

    # Source accessibility
    "Script40_Metadata_Status",
    "Script40_URL_Audit_Status",
    "Script40_Evidence_Audit_Status",

    # Coordinate evidence
    "Coordinate_Validation_Status",
    "Coordinate_Evidence_Description",
    "Coordinate_Evidence_URL",
    "Original_Coordinate_Assessment",
    "Original_Coordinate_Reference_Type",
    "Port_Terminal_Distinction_Notes",

    # Operational relevance
    "Operational_Role",
    "Operational_Inclusion_Decision",
    "Inclusion_or_Exclusion_Justification",

    # AIS / transit evidence
    "AIS_or_Transit_Evidence_Status",
    "AIS_or_Transit_Evidence_Reference",

    # Existing review information
    "Existing_Researcher_Review_Status",
    "Existing_Researcher_Reviewer_Notes",

    # Manual content verification
    *manual_fields,

    # Audit trail
    "Register_Generated_Date",
    "Verification_Method",
]


# ============================================================
# 7. LOAD EXISTING SCRIPT 41 REGISTER
#    This preserves manual entries across reruns.
# ============================================================

existing_records = {}

if OUTPUT_FILE.exists():

    with OUTPUT_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            code = clean(row.get("UN_LOCODE"))

            if code:
                existing_records[code] = row

    print(
        "\nExisting Script 41 manual entries loaded:",
        len(existing_records)
    )

else:

    print("\nNo previous Script 41 register found.")
    print("A new register will be created.")


# ============================================================
# 8. BUILD THE MANUAL VERIFICATION REGISTER
# ============================================================

output_records = []

for index, code in enumerate(sorted(script38), start=1):

    r38 = script38[code]
    r39 = script39[code]
    r40 = script40.get(code, {})
    old = existing_records.get(code, {})

    print(
        f"\n[{index}/{len(script38)}] Preparing {code}"
    )

    primary_url = get(r38, "Primary_Evidence_URL")
    secondary_url = get(
        r38,
        "Independent_Secondary_Evidence_URL"
    )

    identity_url = get(r38, "Identity_Evidence_URL")
    coordinate_url38 = get(r38, "Coordinate_Evidence_URL")
    coordinate_url39 = get(r39, "Coordinate_Source_URL")

    all_urls = combine_unique(
        primary_url,
        secondary_url,
        identity_url,
        coordinate_url38,
        coordinate_url39
    )

    record = {

        "UN_LOCODE": code,

        "Port_Name_in_Master": get(
            r38, "Port_Name_in_Master"
        ),

        "Researcher_Validated_Port_Name": get(
            r38, "Researcher_Validated_Port_Name"
        ),

        "Researcher_Validated_Facility_Name": get(
            r38, "Researcher_Validated_Facility_Name"
        ),

        "Country_Code": get(r38, "Country_Code"),

        "Preliminary_Geographic_Role": get(
            r38, "Preliminary_Geographic_Role"
        ),

        "Research_Relevance_Screen": get(
            r38, "Research_Relevance_Screen"
        ),

        "Provisional_Facility_Type": get(
            r38, "Provisional_Facility_Type"
        ),

        "Facility_or_Port_System": get(
            r38, "Facility_or_Port_System"
        ),

        "Observed_Call_Count": get(
            r38, "Observed_Call_Count"
        ),

        "Observed_Vessel_Count": get(
            r38, "Observed_Vessel_Count"
        ),

        "In_Degree": get(r38, "In_Degree"),

        "Out_Degree": get(r38, "Out_Degree"),

        "Betweenness_Centrality": get(
            r38, "Betweenness_Centrality"
        ),

        "Network_Match_Status": get(
            r38, "Network_Match_Status"
        ),

        # Identity evidence
        "Identity_Validation_Status": get(
            r38, "Identity_Validation_Status"
        ),

        "Identity_Evidence_Description": get(
            r38, "Identity_Evidence_Description"
        ),

        "Identity_Evidence_URL": identity_url,

        # Source URLs
        "Primary_Evidence_URL": primary_url,

        "Independent_Secondary_Evidence_URL": secondary_url,

        "Coordinate_Source_URL": coordinate_url39,

        "All_Source_URLs": all_urls,

        # Script 40 audit
        "Script40_Metadata_Status": get(
            r40, "Metadata_Status"
        ),

        "Script40_URL_Audit_Status": get(
            r40, "URL_Audit_Status"
        ),

        "Script40_Evidence_Audit_Status": get(
            r40, "Evidence_Audit_Status"
        ),

        # Coordinate evidence
        "Coordinate_Validation_Status": get(
            r38, "Coordinate_Validation_Status"
        ),

        "Coordinate_Evidence_Description": get(
            r38, "Coordinate_Evidence_Description"
        ),

        "Coordinate_Evidence_URL": coordinate_url38,

        "Original_Coordinate_Assessment": get(
            r39, "Original_Coordinate_Assessment"
        ),

        "Original_Coordinate_Reference_Type": get(
            r39, "Original_Coordinate_Reference_Type"
        ),

        "Port_Terminal_Distinction_Notes": get(
            r38, "Port_Terminal_Distinction_Notes"
        ),

        # Operational inclusion
        "Operational_Role": get(
            r38, "Operational_Role"
        ),

        "Operational_Inclusion_Decision": get(
            r38, "Operational_Inclusion_Decision"
        ),

        "Inclusion_or_Exclusion_Justification": get(
            r38, "Inclusion_or_Exclusion_Justification"
        ),

        # Transit
        "AIS_or_Transit_Evidence_Status": get(
            r38, "AIS_or_Transit_Evidence_Status"
        ),

        "AIS_or_Transit_Evidence_Reference": get(
            r38, "AIS_or_Transit_Evidence_Reference"
        ),

        # Existing review
        "Existing_Researcher_Review_Status": get(
            r38, "Researcher_Review_Status"
        ),

        "Existing_Researcher_Reviewer_Notes": get(
            r38, "Researcher_Reviewer_Notes"
        ),

        # Audit trail
        "Register_Generated_Date": date.today().isoformat(),

        "Verification_Method": (
            "MANUAL_RESEARCHER_CONTENT_REVIEW_REQUIRED"
        ),
    }

    # --------------------------------------------------------
    # Preserve manual verification fields from earlier runs.
    # --------------------------------------------------------

    for field in manual_fields:

        record[field] = clean(old.get(field, ""))

    # Existing manual decisions must never be overwritten.
    # Only source-derived fields are refreshed from Scripts 38-40.

    output_records.append(record)


# ============================================================
# 9. WRITE OUTPUT REGISTER
# ============================================================

with OUTPUT_FILE.open(
    "w",
    encoding="utf-8-sig",
    newline=""
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=output_fields,
        extrasaction="ignore"
    )

    writer.writeheader()
    writer.writerows(output_records)


# ============================================================
# 10. VALIDATE OUTPUT
# ============================================================

with OUTPUT_FILE.open(
    "r",
    encoding="utf-8-sig",
    newline=""
) as f:

    reader = csv.DictReader(f)

    written_rows = list(reader)

    if reader.fieldnames != output_fields:
        raise ValueError(
            "Output header validation failed."
        )

    if len(written_rows) != len(script38):
        raise ValueError(
            "Output record count does not match Script 38."
        )

    output_codes = [
        row["UN_LOCODE"] for row in written_rows
    ]

    if len(output_codes) != len(set(output_codes)):
        raise ValueError(
            "Duplicate UN_LOCODE detected in output."
        )

    malformed = [
        row for row in written_rows
        if len(row) != len(output_fields)
    ]

    if malformed:
        raise ValueError(
            "Malformed output rows detected."
        )


# ============================================================
# 11. GENERATE SUMMARY
# ============================================================

total = len(written_rows)

review_status_counts = {}
identity_status_counts = {}
coordinate_status_counts = {}
operational_status_counts = {}

for row in written_rows:

    review = (
        row["Source_Content_Review_Status"]
        or "NOT_REVIEWED"
    )

    identity = (
        row["Identity_Validation_Status"]
        or "NOT_AVAILABLE"
    )

    coordinate = (
        row["Coordinate_Validation_Status"]
        or "NOT_AVAILABLE"
    )

    operational = (
        row["Operational_Inclusion_Decision"]
        or "NOT_AVAILABLE"
    )

    review_status_counts[review] = (
        review_status_counts.get(review, 0) + 1
    )

    identity_status_counts[identity] = (
        identity_status_counts.get(identity, 0) + 1
    )

    coordinate_status_counts[coordinate] = (
        coordinate_status_counts.get(coordinate, 0) + 1
    )

    operational_status_counts[operational] = (
        operational_status_counts.get(operational, 0) + 1
    )


# ============================================================
# 12. WRITE REPORT
# ============================================================

report = []

report.append("=" * 72)
report.append(
    "SCRIPT 41: MANUAL SOURCE-CONTENT VERIFICATION REPORT"
)
report.append("=" * 72)

report.append("")
report.append(f"Generation date: {date.today().isoformat()}")
report.append(f"Total records: {total}")
report.append(f"Output columns: {len(output_fields)}")

report.append("")
report.append("INPUT FILES")
report.append("-" * 72)
report.append(f"Script 38: {SCRIPT38_FILE}")
report.append(f"Script 39: {SCRIPT39_FILE}")
report.append(f"Script 40: {SCRIPT40_FILE}")
report.append("")

report.append("SOURCE-CONTENT REVIEW STATUS")
report.append("-" * 72)

for status, count in sorted(review_status_counts.items()):
    report.append(f"{status}: {count}")

report.append("")
report.append("IDENTITY VALIDATION STATUS")
report.append("-" * 72)

for status, count in sorted(identity_status_counts.items()):
    report.append(f"{status}: {count}")

report.append("")
report.append("COORDINATE VALIDATION STATUS")
report.append("-" * 72)

for status, count in sorted(coordinate_status_counts.items()):
    report.append(f"{status}: {count}")

report.append("")
report.append("OPERATIONAL INCLUSION STATUS")
report.append("-" * 72)

for status, count in sorted(operational_status_counts.items()):
    report.append(f"{status}: {count}")

report.append("")
report.append("IMPORTANT RESEARCH SAFEGUARDS")
report.append("-" * 72)

report.append(
    "1. URL accessibility is not equivalent to content verification."
)

report.append(
    "2. Source metadata completeness does not establish claim validity."
)

report.append(
    "3. No source-content claim has been automatically verified."
)

report.append(
    "4. No coordinates have been approved by Script 41."
)

report.append(
    "5. Operational inclusion decisions have not been changed."
)

report.append(
    "6. Port identity and facility identity must be assessed separately."
)

report.append(
    "7. Port coordinates and terminal coordinates must be distinguished."
)

report.append(
    "8. Port calls do not independently establish Strait of Hormuz transit."
)

report.append("")
report.append("OUTPUT")
report.append("-" * 72)
report.append(str(OUTPUT_FILE))
report.append(str(REPORT_FILE))

report.append("")
report.append("=" * 72)
report.append("SCRIPT 41 COMPLETED SUCCESSFULLY")
report.append("=" * 72)

with REPORT_FILE.open(
    "w",
    encoding="utf-8"
) as f:

    f.write("\n".join(report))


# ============================================================
# 13. FINAL TERMINAL SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("SCRIPT 41 COMPLETED SUCCESSFULLY")
print("=" * 70)

print("Total records:", total)
print("Output columns:", len(output_fields))

print("\nSOURCE CONTENT REVIEW")

for status, count in sorted(review_status_counts.items()):
    print(f"{status}: {count}")

print("\nIDENTITY VALIDATION")

for status, count in sorted(identity_status_counts.items()):
    print(f"{status}: {count}")

print("\nCOORDINATE VALIDATION")

for status, count in sorted(coordinate_status_counts.items()):
    print(f"{status}: {count}")

print("\nOPERATIONAL INCLUSION")

for status, count in sorted(operational_status_counts.items()):
    print(f"{status}: {count}")

print("\nOUTPUT FILES")
print(OUTPUT_FILE)
print(REPORT_FILE)

print("\nOriginal Scripts 38, 39 and 40 registers were not modified.")

print("=" * 70)
