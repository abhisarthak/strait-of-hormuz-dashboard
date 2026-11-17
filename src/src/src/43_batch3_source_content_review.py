
"""
SCRIPT 43: BATCH 3 SOURCE-CONTENT REVIEW

Batch 3:
1. INHZA - Hazira
2. INIXY - Deendayal Port (Kandla)
3. INPPV - Pipavav

Input:
41_manual_source_content_verification_register_batch2_preliminary_review.csv

Output:
41_manual_source_content_verification_register_batch3_preliminary_review.csv

Safeguards:
- Updates only the 17 manual-review fields for Batch 3.
- Preserves all other records and columns.
- Does not approve coordinates.
- Does not change operational inclusion decisions.
- Does not modify the input CSV.
"""

import csv
from pathlib import Path
from datetime import date


# ============================================================
# 1. FILE PATHS
# ============================================================

INPUT_FILE = Path(
    "outputs/tables/"
    "41_manual_source_content_verification_register_batch2_preliminary_review.csv"
)

OUTPUT_FILE = Path(
    "outputs/tables/"
    "41_manual_source_content_verification_register_batch3_preliminary_review.csv"
)

TODAY = date.today().isoformat()


# ============================================================
# 2. MANUAL REVIEW FIELDS
# ============================================================

MANUAL_FIELDS = [
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
# 3. BATCH 3 REVIEW DATA
# ============================================================

REVIEWS = {

    # --------------------------------------------------------
    # INHZA - HAZIRA
    # --------------------------------------------------------

    "INHZA": {

        "Source_Content_Review_Status": "IN_PROGRESS",

        "Primary_Source_Content_Verified": "PARTIAL",

        "Secondary_Source_Content_Verified": "PARTIAL",

        "Port_Identity_Claim_Verified": "YES",

        "Facility_Identity_Claim_Verified": "PARTIAL",

        "Geographic_Claim_Verified": "PARTIAL",

        "Coordinate_Claim_Verified": "PARTIAL",

        "Operational_Role_Claim_Verified": "YES",

        "Verified_Claims": (
            "The official Adani Ports Hazira port information identifies "
            "Hazira as a port facility in Gujarat, India. The published "
            "location reference is approximately 21 degrees 06 minutes N "
            "and 72 degrees 37 minutes E. Gujarat Maritime Board also "
            "identifies Adani Hazira Port Pvt Ltd. These sources support "
            "the existence and maritime role of the Hazira port facility."
        ),

        "Unsupported_or_Contradictory_Claims": (
            "The published coordinate is rounded to minutes and its "
            "precise geographic reference scope has not been established. "
            "It may represent a port-level or facility-level reference "
            "rather than a surveyed terminal point. Exact terminal "
            "attribution for every INHZA schedule call is not established. "
            "No AIS-confirmed Hormuz transit is established."
        ),

        "Source_Content_Review_Conclusion": "PARTIALLY_SUPPORTED",

        "Source_Strength_Assessment": "MODERATE",

        "Additional_Source_Required": "YES",

        "Researcher_Review_Status": (
            "PRELIMINARY_DESK_REVIEW_COMPLETED_RESEARCHER_SIGNOFF_REQUIRED"
        ),

        "Researcher_Reviewer": "PRELIMINARY_ASSISTED_REVIEW",

        "Researcher_Review_Date": TODAY,

        "Researcher_Review_Notes": (
            "Supporting source: Gujarat Maritime Board, "
            "https://gmbports.org/adani-hazira-port-pvt-ltd . "
            "The official Adani port information book is referenced "
            "in the existing evidence register. Preserve the source's "
            "published coordinate precision. Do not convert a rounded "
            "port reference into an assumed terminal coordinate. Further "
            "verification of coordinate scope and terminal attribution "
            "is required. Do not approve operational inclusion."
        ),
    },


    # --------------------------------------------------------
    # INIXY - DEENDAYAL PORT / KANDLA
    # --------------------------------------------------------

    "INIXY": {

        "Source_Content_Review_Status": "IN_PROGRESS",

        "Primary_Source_Content_Verified": "YES",

        "Secondary_Source_Content_Verified": "NOT_AVAILABLE",

        "Port_Identity_Claim_Verified": "YES",

        "Facility_Identity_Claim_Verified": "PARTIAL",

        "Geographic_Claim_Verified": "YES",

        "Coordinate_Claim_Verified": "PARTIAL",

        "Operational_Role_Claim_Verified": "YES",

        "Verified_Claims": (
            "The official Deendayal Port Authority source identifies "
            "Deendayal Port, formerly known as Kandla Port, and provides "
            "a published port location reference of 22 degrees "
            "59 minutes 4.93 seconds N and 70 degrees 13 minutes "
            "22.59 seconds E. This supports the port's identity and "
            "location in Gujarat, India."
        ),

        "Unsupported_or_Contradictory_Claims": (
            "The published position is identified as a port location, "
            "but its exact geographic reference point and relationship "
            "to individual terminals or berths have not been established. "
            "It must not be described as a terminal coordinate without "
            "additional evidence. Individual schedule calls and berth "
            "assignments are not independently validated. No "
            "AIS-confirmed Hormuz transit is established."
        ),

        "Source_Content_Review_Conclusion": "PARTIALLY_SUPPORTED",

        "Source_Strength_Assessment": "HIGH",

        "Additional_Source_Required": "YES",

        "Researcher_Review_Status": (
            "PRELIMINARY_DESK_REVIEW_COMPLETED_RESEARCHER_SIGNOFF_REQUIRED"
        ),

        "Researcher_Reviewer": "PRELIMINARY_ASSISTED_REVIEW",

        "Researcher_Review_Date": TODAY,

        "Researcher_Review_Notes": (
            "Official Deendayal Port Authority report is referenced "
            "in the existing evidence register. The source provides "
            "22 degrees 59 minutes 4.93 seconds N and 70 degrees "
            "13 minutes 22.59 seconds E as a port location. Retain "
            "the published precision. Do not assume that the port "
            "reference represents all terminal locations. Further "
            "evidence is required for terminal-level mapping and "
            "coordinate scope. Do not approve operational inclusion."
        ),
    },


    # --------------------------------------------------------
    # INPPV - PIPAVAV
    # --------------------------------------------------------

    "INPPV": {

        "Source_Content_Review_Status": "IN_PROGRESS",

        "Primary_Source_Content_Verified": "PARTIAL",

        "Secondary_Source_Content_Verified": "PARTIAL",

        "Port_Identity_Claim_Verified": "YES",

        "Facility_Identity_Claim_Verified": "PARTIAL",

        "Geographic_Claim_Verified": "PARTIAL",

        "Coordinate_Claim_Verified": "PARTIAL",

        "Operational_Role_Claim_Verified": "YES",

        "Verified_Claims": (
            "APM Terminals' official Pipavav location information "
            "identifies the Pipavav terminal facility in Gujarat, India "
            "and publishes a location reference of approximately "
            "20 degrees 54 minutes N and 71 degrees 30 minutes E. "
            "A separate maritime directory contains a coordinate "
            "candidate of approximately 20.93000 N and 71.51000 E."
        ),

        "Unsupported_or_Contradictory_Claims": (
            "The official source position is rounded to minutes, while "
            "the secondary directory provides a more precise-looking "
            "decimal coordinate. Greater numerical precision does not "
            "establish greater positional accuracy. Coordinate scope "
            "and the relationship between port-level and terminal-level "
            "references remain unresolved. Individual schedule calls "
            "have not been mapped to a specific berth. No AIS-confirmed "
            "Hormuz transit is established."
        ),

        "Source_Content_Review_Conclusion": "PARTIALLY_SUPPORTED",

        "Source_Strength_Assessment": "MODERATE",

        "Additional_Source_Required": "YES",

        "Researcher_Review_Status": (
            "PRELIMINARY_DESK_REVIEW_COMPLETED_RESEARCHER_SIGNOFF_REQUIRED"
        ),

        "Researcher_Reviewer": "PRELIMINARY_ASSISTED_REVIEW",

        "Researcher_Review_Date": TODAY,

        "Researcher_Review_Notes": (
            "Official operator source: "
            "https://www2.apmterminals.com/en/pipavav/about/location . "
            "The secondary coordinate candidate is approximately "
            "20.93000 N and 71.51000 E. Do not prefer the decimal "
            "coordinate merely because it has more digits. Verify "
            "geographic scope and source methodology. Coordinate "
            "approval and terminal-level mapping remain pending. "
            "Do not approve operational inclusion."
        ),
    },
}


# ============================================================
# 4. MAIN FUNCTION
# ============================================================

def main():

    print("\n" + "=" * 68)
    print("SCRIPT 43: BATCH 3 SOURCE-CONTENT REVIEW")
    print("=" * 68)

    # --------------------------------------------------------
    # Check input file
    # --------------------------------------------------------

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found:\n{INPUT_FILE}\n"
            "Run Script 42 successfully before running Script 43."
        )

    # --------------------------------------------------------
    # Read input CSV
    # --------------------------------------------------------

    with INPUT_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        fields = reader.fieldnames
        rows = list(reader)

    if not fields:
        raise ValueError("Input CSV has no header.")

    # --------------------------------------------------------
    # Validate required columns
    # --------------------------------------------------------

    missing_fields = [
        field for field in MANUAL_FIELDS
        if field not in fields
    ]

    if missing_fields:
        raise ValueError(
            f"Required columns missing: {missing_fields}"
        )

    required_columns = [
        "UN_LOCODE",
        "Operational_Inclusion_Decision",
        "Coordinate_Validation_Status",
    ]

    missing_required = [
        field for field in required_columns
        if field not in fields
    ]

    if missing_required:
        raise ValueError(
            f"Required safeguard columns missing: {missing_required}"
        )

    # --------------------------------------------------------
    # Validate records
    # --------------------------------------------------------

    by_code = {
        row.get("UN_LOCODE", "").strip(): row
        for row in rows
    }

    if len(rows) != 19:
        raise ValueError(
            f"Expected 19 records; found {len(rows)}."
        )

    if len(by_code) != 19:
        raise ValueError(
            "Duplicate or blank UN_LOCODE detected."
        )

    # --------------------------------------------------------
    # Update Batch 3 records
    # --------------------------------------------------------

    for code, updates in REVIEWS.items():

        if code not in by_code:
            raise ValueError(
                f"Required record missing: {code}"
            )

        row = by_code[code]

        operational_status = row[
            "Operational_Inclusion_Decision"
        ].strip()

        if operational_status != "PENDING":
            raise ValueError(
                f"{code}: operational decision is not PENDING. "
                "Review the input before proceeding."
            )

        coordinate_status = row[
            "Coordinate_Validation_Status"
        ].strip()

        if coordinate_status not in (
            "PENDING",
            "PENDING_RECONCILIATION"
        ):
            raise ValueError(
                f"{code}: coordinate status is not pending."
            )

        for field in MANUAL_FIELDS:
            row[field] = updates[field]

        print(f"Updated: {code}")

    # --------------------------------------------------------
    # Write output CSV
    # --------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields,
            extrasaction="ignore"
        )

        writer.writeheader()
        writer.writerows(rows)

    # --------------------------------------------------------
    # Read-after-write validation
    # --------------------------------------------------------

    with OUTPUT_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        check_reader = csv.DictReader(f)

        check_fields = check_reader.fieldnames
        check_rows = list(check_reader)

    if check_fields != fields:
        raise ValueError(
            "Output schema differs from input."
        )

    if len(check_rows) != 19:
        raise ValueError(
            "Output record count validation failed."
        )

    check_by_code = {
        row["UN_LOCODE"]: row
        for row in check_rows
    }

    if len(check_by_code) != 19:
        raise ValueError(
            "Output UN_LOCODE uniqueness validation failed."
        )

    # --------------------------------------------------------
    # Validate updated records
    # --------------------------------------------------------

    for code in REVIEWS:

        row = check_by_code[code]

        if row["Source_Content_Review_Status"] != "IN_PROGRESS":
            raise ValueError(
                f"{code}: review status validation failed."
            )

        if row["Operational_Inclusion_Decision"] != "PENDING":
            raise ValueError(
                f"{code}: operational decision changed unexpectedly."
            )

        if row["Coordinate_Validation_Status"] not in (
            "PENDING",
            "PENDING_RECONCILIATION"
        ):
            raise ValueError(
                f"{code}: coordinate status changed unexpectedly."
            )

    # --------------------------------------------------------
    # Validate unchanged records
    # --------------------------------------------------------

    updated_codes = set(REVIEWS)

    for code, original_row in by_code.items():

        if code in updated_codes:
            continue

        output_row = check_by_code[code]

        for field in MANUAL_FIELDS:

            if original_row.get(field, "") != output_row.get(field, ""):
                raise ValueError(
                    f"Unexpected modification: {code}, {field}"
                )

    # --------------------------------------------------------
    # Final report
    # --------------------------------------------------------

    print("\n" + "=" * 68)
    print("SCRIPT 43 COMPLETED SUCCESSFULLY")
    print("=" * 68)

    print("Input records:", len(rows))
    print("Output records:", len(check_rows))
    print("Columns preserved:", len(fields))

    print("\nUPDATED RECORDS:")

    for code in REVIEWS:
        print("-", code)

    print("\nOther records preserved:", len(rows) - len(REVIEWS))

    print("Operational decisions: PENDING")
    print("Coordinate approvals: NONE")

    print("\nOUTPUT FILE:")
    print(OUTPUT_FILE)

    print("\nInput Batch 2 CSV was not modified.")

    print("=" * 68)


if __name__ == "__main__":
    main()
