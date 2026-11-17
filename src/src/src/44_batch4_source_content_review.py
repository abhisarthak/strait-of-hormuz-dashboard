
"""
SCRIPT 44: BATCH 4 SOURCE-CONTENT REVIEW

Batch 4:
IQUQR - Umm Qasr, Iraq
KWSAA - Shuaiba Port, Kuwait
KWSWK - Shuwaikh Port, Kuwait

Input:
41_manual_source_content_verification_register_batch3_preliminary_review.csv

Output:
41_manual_source_content_verification_register_batch4_preliminary_review.csv

Safeguards:
- Updates only the 17 manual-review fields for Batch 4.
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
    "41_manual_source_content_verification_register_batch3_preliminary_review.csv"
)

OUTPUT_FILE = Path(
    "outputs/tables/"
    "41_manual_source_content_verification_register_batch4_preliminary_review.csv"
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
# 3. BATCH 4 REVIEW DATA
# ============================================================

REVIEWS = {

    # --------------------------------------------------------
    # IQUQR - UMM QASR, IRAQ
    # --------------------------------------------------------

    "IQUQR": {

        "Source_Content_Review_Status": "IN_PROGRESS",

        "Primary_Source_Content_Verified": "YES",

        "Secondary_Source_Content_Verified": "PARTIAL",

        "Port_Identity_Claim_Verified": "YES",

        "Facility_Identity_Claim_Verified": "PARTIAL",

        "Geographic_Claim_Verified": "YES",

        "Coordinate_Claim_Verified": "PARTIAL",

        "Operational_Role_Claim_Verified": "YES",

        "Verified_Claims": (
            "ICTSI identifies Basra Gateway Terminal (BGT) as a "
            "multipurpose cargo-handling facility situated in North "
            "Port, Umm Qasr, Basra Province, Iraq. ICTSI describes "
            "Umm Qasr as Iraq's largest port and primary trade link. "
            "BGT handles container, general, project and Ro-Ro cargo. "
            "The available terminal information identifies a "
            "terminal-specific position of approximately 30.0558097 N "
            "and 47.9255077 E. Other terminal operators and facilities "
            "also operate within the wider Umm Qasr port system."
        ),

        "Unsupported_or_Contradictory_Claims": (
            "The BGT coordinate is terminal-specific and must not be "
            "treated as the coordinate of the entire Umm Qasr port. "
            "Umm Qasr includes multiple terminals and port areas, "
            "including North Port and South Port facilities. The "
            "available evidence does not establish which terminal "
            "handled every IQUQR schedule call. The exact geographic "
            "scope of the existing UN/LOCODE reference also requires "
            "reconciliation. No AIS-confirmed Hormuz transit is "
            "established."
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
            "Primary operator source: ICTSI, Basra Gateway Terminal, "
            "https://ictsi.com/our-offering/our-terminals/basra-gateway-terminal . "
            "Additional operator source: https://ictsiiraq.com/ . "
            "ICTSI identifies BGT as a facility in North Port, Umm Qasr. "
            "The terminal position in the available evidence is "
            "approximately 30.0558097 N, 47.9255077 E. Do not assign "
            "this terminal position to the entire Umm Qasr port. "
            "Other terminal operators and facilities exist in the "
            "port system. Obtain terminal-level call mapping before "
            "making facility-specific inclusion or coordinate decisions. "
            "Keep operational inclusion pending."
        ),
    },


    # --------------------------------------------------------
    # KWSAA - SHUAIBA PORT, KUWAIT
    # --------------------------------------------------------

    "KWSAA": {

        "Source_Content_Review_Status": "IN_PROGRESS",

        "Primary_Source_Content_Verified": "YES",

        "Secondary_Source_Content_Verified": "PARTIAL",

        "Port_Identity_Claim_Verified": "YES",

        "Facility_Identity_Claim_Verified": "YES",

        "Geographic_Claim_Verified": "YES",

        "Coordinate_Claim_Verified": "PARTIAL",

        "Operational_Role_Claim_Verified": "YES",

        "Verified_Claims": (
            "Kuwait Ports Authority identifies Shuaiba Port as Kuwait's "
            "primary industrial port, located in the southern part of "
            "the country in Ahmadi Governorate. The Authority describes "
            "its role in handling commercial cargo, heavy equipment, "
            "raw materials and chemicals supporting industrial activity. "
            "The Authority reports 20 berths and identifies the port "
            "as an operating port facility."
        ),

        "Unsupported_or_Contradictory_Claims": (
            "The Kuwait Ports Authority page establishes the port "
            "identity and operational role but does not independently "
            "establish the precise coordinate reference used in the "
            "existing register. The UNECE UN/LOCODE reference of "
            "approximately 29 degrees 02 minutes N and 48 degrees "
            "08 minutes E requires geographic-scope verification. "
            "It must not be assumed to represent a specific terminal "
            "or berth. Individual schedule calls have not been "
            "independently mapped to terminals. No AIS-confirmed "
            "Hormuz transit is established."
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
            "Official source: Kuwait Ports Authority, Shuaiba Port, "
            "https://kpa.gov.kw/en/shuaiba-port/ . The Authority "
            "identifies Shuaiba as an industrial port in Ahmadi "
            "Governorate and describes its cargo-handling role. "
            "The existing UNECE coordinate reference is approximately "
            "29 degrees 02 minutes N and 48 degrees 08 minutes E. "
            "The KPA page does not independently validate that "
            "coordinate. Preserve it as a pending UN/LOCODE reference "
            "until its scope is checked. Do not assume terminal or "
            "berth coordinates. Do not approve operational inclusion."
        ),
    },


    # --------------------------------------------------------
    # KWSWK - SHUWAIKH PORT, KUWAIT
    # --------------------------------------------------------

    "KWSWK": {

        "Source_Content_Review_Status": "IN_PROGRESS",

        "Primary_Source_Content_Verified": "YES",

        "Secondary_Source_Content_Verified": "PARTIAL",

        "Port_Identity_Claim_Verified": "YES",

        "Facility_Identity_Claim_Verified": "YES",

        "Geographic_Claim_Verified": "YES",

        "Coordinate_Claim_Verified": "PARTIAL",

        "Operational_Role_Claim_Verified": "YES",

        "Verified_Claims": (
            "Kuwait Ports Authority identifies Shuwaikh Port as "
            "Kuwait's main commercial port, located in the Shuwaikh "
            "Industrial Area near Kuwait City. The Authority reports "
            "21 berths and describes the port's role in commercial "
            "shipping, storage and distribution. Kuwait Government "
            "Online also describes Shuwaikh as the country's main "
            "commercial port."
        ),

        "Unsupported_or_Contradictory_Claims": (
            "The official sources establish port identity and "
            "commercial role but do not independently verify the "
            "precise coordinate reference in the existing register. "
            "The UNECE UN/LOCODE reference of approximately "
            "29 degrees 21 minutes N and 47 degrees 56 minutes E "
            "requires geographic-scope verification. It should not "
            "be described as a terminal or berth coordinate without "
            "further evidence. Individual schedule calls and berth "
            "assignments have not been independently verified. "
            "No AIS-confirmed Hormuz transit is established."
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
            "Official source: Kuwait Ports Authority, Shuwaikh Port, "
            "https://www.kpa.gov.kw/en/shuwaikh-port/ . Additional "
            "government source: Kuwait Government Online, Sea Transport, "
            "https://e.gov.kw/sites/kgoenglish/Pages/Visitors/"
            "TourismInKuwait/TravellingToKuwaitTravelSurfing.aspx . "
            "Both sources support Shuwaikh's identity as Kuwait's "
            "main commercial port. The existing UNECE reference is "
            "approximately 29 degrees 21 minutes N and 47 degrees "
            "56 minutes E. Preserve it as a pending port-location "
            "reference until its scope is checked. Do not assume "
            "terminal or berth coordinates. Do not approve operational "
            "inclusion."
        ),
    },
}


# ============================================================
# 4. MAIN FUNCTION
# ============================================================

def main():

    print("\n" + "=" * 68)
    print("SCRIPT 44: BATCH 4 SOURCE-CONTENT REVIEW")
    print("=" * 68)

    # --------------------------------------------------------
    # Check input
    # --------------------------------------------------------

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found:\n{INPUT_FILE}\n"
            "Run Script 43 successfully before Script 44."
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
    # Validate columns
    # --------------------------------------------------------

    missing_fields = [
        field for field in MANUAL_FIELDS
        if field not in fields
    ]

    if missing_fields:
        raise ValueError(
            f"Required manual-review columns missing: {missing_fields}"
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
    # Validate record count and uniqueness
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
    # Update only Batch 4 records
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
                f"{code}: operational inclusion is not PENDING."
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
    # Write new output
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
            "Output column schema differs from input."
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
                f"{code}: source review status validation failed."
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
    # Verify all other manual fields remain unchanged
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
    # Final summary
    # --------------------------------------------------------

    print("\n" + "=" * 68)
    print("SCRIPT 44 COMPLETED SUCCESSFULLY")
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

    print("\nInput Batch 3 CSV was not modified.")

    print("=" * 68)


if __name__ == "__main__":
    main()
