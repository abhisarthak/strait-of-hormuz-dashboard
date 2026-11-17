
"""
SCRIPT 45: BATCH 5 SOURCE-CONTENT REVIEW

Records:
OMDQM - Duqm, Oman
PKKIA - Kiamari / Karachi Harbour, Pakistan
QAQAP - QAPCO, Qatar
QAQCH - Q-Chem, Qatar
QAUMS - Umm Sa'id (Mesaieed), Qatar
SADMM - King Abdulaziz Port, Dammam, Saudi Arabia
SAJUB - Jubail Commercial Port, Saudi Arabia

Input:
41_manual_source_content_verification_register_batch4_preliminary_review.csv

Output:
41_manual_source_content_verification_register_batch5_preliminary_review.csv

This is a preliminary desk-review register.
It does not approve coordinates or operational inclusion.
"""

import csv
from pathlib import Path
from datetime import date


# ============================================================
# 1. FILE PATHS
# ============================================================

INPUT_FILE = Path(
    "outputs/tables/"
    "41_manual_source_content_verification_register_batch4_preliminary_review.csv"
)

OUTPUT_FILE = Path(
    "outputs/tables/"
    "41_manual_source_content_verification_register_batch5_preliminary_review.csv"
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
# 3. BATCH 5 REVIEW DATA
# ============================================================

REVIEWS = {

    # --------------------------------------------------------
    # OMDQM - DUQM, OMAN
    # --------------------------------------------------------

    "OMDQM": {

        "Source_Content_Review_Status": "IN_PROGRESS",
        "Primary_Source_Content_Verified": "YES",
        "Secondary_Source_Content_Verified": "PARTIAL",
        "Port_Identity_Claim_Verified": "YES",
        "Facility_Identity_Claim_Verified": "YES",
        "Geographic_Claim_Verified": "PARTIAL",
        "Coordinate_Claim_Verified": "PARTIAL",
        "Operational_Role_Claim_Verified": "YES",

        "Verified_Claims": (
            "The Port of Duqm is an established commercial port in "
            "the Sultanate of Oman, located on the Arabian Sea coast "
            "in Al Wusta Governorate. The port is associated with "
            "commercial cargo, industrial development and logistics "
            "activities. Its location on the Arabian Sea is "
            "geographically distinct from the Persian Gulf. A port "
            "call at Duqm alone does not establish passage through "
            "the Strait of Hormuz."
        ),

        "Unsupported_or_Contradictory_Claims": (
            "The available port identity evidence does not establish "
            "the precise coordinate scope represented by the existing "
            "UN/LOCODE reference. Port, harbour, terminal and berth "
            "coordinates must be distinguished. The presence of "
            "Duqm in the network does not establish that the vessel "
            "transited Hormuz. The exact facility associated with "
            "each schedule call requires further evidence."
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
            "Review the official Port of Duqm / Asyad Group port "
            "information and the relevant Omani port authority "
            "material. Confirm the exact port identity, operating "
            "entity, geographic scope and coordinate source before "
            "approving coordinates. Duqm is on the Arabian Sea coast; "
            "do not classify it as a Persian Gulf port merely because "
            "it appears in the wider regional shipping network. "
            "No AIS-confirmed Hormuz transit is established. "
            "Operational inclusion remains pending."
        ),
    },


    # --------------------------------------------------------
    # PKKIA - KIAMARI / KARACHI HARBOUR, PAKISTAN
    # --------------------------------------------------------

    "PKKIA": {

        "Source_Content_Review_Status": "IN_PROGRESS",
        "Primary_Source_Content_Verified": "PARTIAL",
        "Secondary_Source_Content_Verified": "PARTIAL",
        "Port_Identity_Claim_Verified": "PARTIAL",
        "Facility_Identity_Claim_Verified": "PARTIAL",
        "Geographic_Claim_Verified": "PARTIAL",
        "Coordinate_Claim_Verified": "PARTIAL",
        "Operational_Role_Claim_Verified": "PARTIAL",

        "Verified_Claims": (
            "Kiamari is associated with Karachi Harbour and the "
            "port facilities administered within the Karachi port "
            "system. Karachi Port Trust is the relevant port "
            "authority for Karachi Port. The existing location "
            "label associates PKKIA with Kiamari / Karachi Harbour."
        ),

        "Unsupported_or_Contradictory_Claims": (
            "The available evidence does not yet establish that "
            "the UN/LOCODE PKKIA identifies one specific terminal "
            "or facility rather than a wider harbour or port area. "
            "Karachi Port Trust facilities and other nearby port "
            "facilities must not be conflated. The exact facility "
            "represented by each schedule call is not established. "
            "The existing coordinate reference requires independent "
            "scope and location verification. No AIS-confirmed "
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
            "Official authority to consult: Karachi Port Trust, "
            "https://kpt.gov.pk/ . Verify whether PKKIA represents "
            "Kiamari, a broader Karachi Harbour location or a "
            "specific facility. Do not automatically equate "
            "Kiamari with every Karachi Port terminal or with "
            "Port Qasim. Obtain a primary source explicitly linking "
            "the code to the facility and its geographic scope. "
            "No coordinate or operational inclusion approval."
        ),
    },


    # --------------------------------------------------------
    # QAQAP - QAPCO, QATAR
    # --------------------------------------------------------

    "QAQAP": {

        "Source_Content_Review_Status": "IN_PROGRESS",
        "Primary_Source_Content_Verified": "PARTIAL",
        "Secondary_Source_Content_Verified": "PARTIAL",
        "Port_Identity_Claim_Verified": "PARTIAL",
        "Facility_Identity_Claim_Verified": "YES",
        "Geographic_Claim_Verified": "PARTIAL",
        "Coordinate_Claim_Verified": "PARTIAL",
        "Operational_Role_Claim_Verified": "YES",

        "Verified_Claims": (
            "QAPCO refers to Qatar Petrochemical Company, an "
            "industrial petrochemical operator in Qatar. Its "
            "industrial activities are associated with the "
            "Mesaieed industrial area. The existing schedule "
            "location code QAQAP is associated with the QAPCO "
            "facility label in the preliminary port register."
        ),

        "Unsupported_or_Contradictory_Claims": (
            "QAPCO is an industrial company / facility identity, "
            "not automatically an independent commercial seaport. "
            "The evidence does not establish whether QAQAP represents "
            "a dedicated jetty, an industrial terminal, a berth "
            "location or a broader port-area reference. The "
            "relationship between QAQAP and the wider Mesaieed "
            "port system must be established before network inclusion. "
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
            "Official company source to review: Qatar Petrochemical "
            "Company (QAPCO), https://www.qapco.com/ . Verify the "
            "company's industrial location, facility ownership and "
            "any dedicated marine loading or unloading infrastructure. "
            "Do not treat the company name as proof of an independent "
            "port. Establish the exact mapping of QAQAP to a jetty, "
            "terminal or port-area location using a primary source "
            "before making a network inclusion decision. "
            "Coordinates and operational inclusion remain pending."
        ),
    },


    # --------------------------------------------------------
    # QAQCH - Q-CHEM, QATAR
    # --------------------------------------------------------

    "QAQCH": {

        "Source_Content_Review_Status": "IN_PROGRESS",
        "Primary_Source_Content_Verified": "PARTIAL",
        "Secondary_Source_Content_Verified": "PARTIAL",
        "Port_Identity_Claim_Verified": "PARTIAL",
        "Facility_Identity_Claim_Verified": "YES",
        "Geographic_Claim_Verified": "PARTIAL",
        "Coordinate_Claim_Verified": "PARTIAL",
        "Operational_Role_Claim_Verified": "YES",

        "Verified_Claims": (
            "Q-Chem refers to Qatar Chemical Company, an industrial "
            "petrochemical operator in Qatar. Its industrial "
            "facilities are associated with the Mesaieed industrial "
            "area. The existing preliminary register associates "
            "QAQCH with the Q-Chem facility label."
        ),

        "Unsupported_or_Contradictory_Claims": (
            "Q-Chem is an industrial company / facility identity, "
            "not automatically an independent commercial seaport. "
            "The available evidence does not establish whether "
            "QAQCH represents a dedicated jetty, a terminal, a "
            "berth or a wider port-area reference. Its relationship "
            "to the Mesaieed port system must be verified. "
            "The exact facility represented by each schedule call "
            "is not established. No AIS-confirmed Hormuz transit "
            "is established."
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
            "Official company source to review: Q-Chem, "
            "https://www.qchem.com/ . Verify the company's "
            "industrial location, facility ownership and marine "
            "loading infrastructure. Do not treat the company "
            "identity as proof of an independent port. Obtain "
            "primary evidence mapping QAQCH to a specific marine "
            "facility or location before network inclusion. "
            "Coordinate approval and operational inclusion remain "
            "pending."
        ),
    },


    # --------------------------------------------------------
    # QAUMS - UMM SA'ID / MESAIEED, QATAR
    # --------------------------------------------------------

    "QAUMS": {

        "Source_Content_Review_Status": "IN_PROGRESS",
        "Primary_Source_Content_Verified": "YES",
        "Secondary_Source_Content_Verified": "PARTIAL",
        "Port_Identity_Claim_Verified": "YES",
        "Facility_Identity_Claim_Verified": "PARTIAL",
        "Geographic_Claim_Verified": "YES",
        "Coordinate_Claim_Verified": "PARTIAL",
        "Operational_Role_Claim_Verified": "YES",

        "Verified_Claims": (
            "Umm Sa'id, also known as Mesaieed, is an established "
            "industrial and commercial port area in Qatar. The "
            "location is associated with industrial cargo, "
            "petrochemical activity and port-related logistics. "
            "The existing UN/LOCODE label QAUMS is associated "
            "with Umm Sa'id / Mesaieed."
        ),

        "Unsupported_or_Contradictory_Claims": (
            "The wider Mesaieed port and industrial area contains "
            "multiple facilities and industrial operators. The "
            "available evidence does not establish which terminal "
            "or berth is represented by each QAUMS schedule call. "
            "A location-level UN/LOCODE coordinate must not be "
            "assumed to be a terminal coordinate. QAPCO and Q-Chem "
            "facility references must not be conflated with the "
            "entire Mesaieed port. No AIS-confirmed Hormuz transit "
            "is established."
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
            "Review official Qatar Ports Management Company "
            "(Mwani Qatar) information: https://www.mwani.com.qa/ . "
            "Verify the official port name, location and operating "
            "role. Distinguish the wider Mesaieed port from "
            "industrial facilities and dedicated jetties operated "
            "by individual companies. Reconcile the existing "
            "UN/LOCODE point with an independently sourced port "
            "coordinate. Do not infer terminal-level call mapping "
            "from the location code alone. Operational inclusion "
            "remains pending."
        ),
    },


    # --------------------------------------------------------
    # SADMM - KING ABDULAZIZ PORT, DAMMAM, SAUDI ARABIA
    # --------------------------------------------------------

    "SADMM": {

        "Source_Content_Review_Status": "IN_PROGRESS",
        "Primary_Source_Content_Verified": "YES",
        "Secondary_Source_Content_Verified": "PARTIAL",
        "Port_Identity_Claim_Verified": "YES",
        "Facility_Identity_Claim_Verified": "YES",
        "Geographic_Claim_Verified": "PARTIAL",
        "Coordinate_Claim_Verified": "PARTIAL",
        "Operational_Role_Claim_Verified": "YES",

        "Verified_Claims": (
            "King Abdulaziz Port is an established commercial port "
            "in Dammam, Saudi Arabia, on the Arabian Gulf coast. "
            "It is operated within the Saudi Ports Authority "
            "(Mawani) port system and serves commercial cargo "
            "and container traffic. The existing UN/LOCODE SADMM "
            "is associated with the Dammam port location."
        ),

        "Unsupported_or_Contradictory_Claims": (
            "The port identity does not establish the exact terminal "
            "or berth represented by every schedule record. The "
            "existing location coordinate requires independent "
            "scope verification and must not automatically be "
            "treated as a terminal coordinate. The existence of "
            "a port call at Dammam does not independently prove "
            "a specific vessel's Strait of Hormuz crossing. "
            "No AIS-confirmed transit is established."
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
            "Official source to review: Saudi Ports Authority "
            "(Mawani), https://mawani.gov.sa/ . Verify the official "
            "port identity, Dammam location, port operator and "
            "commercial role. Reconcile the existing UN/LOCODE "
            "coordinate with a port-level source and distinguish "
            "port coordinates from terminal and berth positions. "
            "Do not infer AIS transit from port-call sequences. "
            "Coordinate approval and operational inclusion remain "
            "pending."
        ),
    },


    # --------------------------------------------------------
    # SAJUB - JUBAIL COMMERCIAL PORT, SAUDI ARABIA
    # --------------------------------------------------------

    "SAJUB": {

        "Source_Content_Review_Status": "IN_PROGRESS",
        "Primary_Source_Content_Verified": "YES",
        "Secondary_Source_Content_Verified": "PARTIAL",
        "Port_Identity_Claim_Verified": "YES",
        "Facility_Identity_Claim_Verified": "PARTIAL",
        "Geographic_Claim_Verified": "PARTIAL",
        "Coordinate_Claim_Verified": "PARTIAL",
        "Operational_Role_Claim_Verified": "YES",

        "Verified_Claims": (
            "Jubail Commercial Port is an established commercial "
            "port in the Jubail area of Saudi Arabia on the Arabian "
            "Gulf coast. The port is part of the Saudi Ports "
            "Authority (Mawani) port system and is distinct in "
            "function and identity from the industrial facilities "
            "and terminals associated with the wider Jubail "
            "industrial complex."
        ),

        "Unsupported_or_Contradictory_Claims": (
            "The available port identity evidence does not establish "
            "which specific terminal or berth is represented by "
            "every SAJUB schedule record. Jubail Commercial Port "
            "must not automatically be conflated with King Fahd "
            "Industrial Port or individual industrial jetties. "
            "The existing UN/LOCODE coordinate requires independent "
            "scope verification. No AIS-confirmed Hormuz transit "
            "is established."
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
            "Official source to review: Saudi Ports Authority "
            "(Mawani), https://mawani.gov.sa/ . Confirm the official "
            "Jubail Commercial Port identity and distinguish it "
            "from King Fahd Industrial Port and other industrial "
            "marine facilities in Jubail. Verify the geographic "
            "scope of the existing UN/LOCODE point independently. "
            "Do not infer a terminal or berth assignment from "
            "the port name alone. Coordinate approval and "
            "operational inclusion remain pending."
        ),
    },
}


# ============================================================
# 4. MAIN FUNCTION
# ============================================================

def main():

    print("\n" + "=" * 68)
    print("SCRIPT 45: BATCH 5 SOURCE-CONTENT REVIEW")
    print("=" * 68)

    # --------------------------------------------------------
    # Check input file
    # --------------------------------------------------------

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found:\n{INPUT_FILE}\n"
            "Run Script 44 successfully before Script 45."
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
    # Validate record count and unique codes
    # --------------------------------------------------------

    if len(rows) != 19:
        raise ValueError(
            f"Expected 19 records; found {len(rows)}."
        )

    by_code = {
        row.get("UN_LOCODE", "").strip(): row
        for row in rows
    }

    if len(by_code) != 19:
        raise ValueError(
            "Duplicate or blank UN_LOCODE detected."
        )

    # --------------------------------------------------------
    # Validate all seven Batch 5 records exist
    # --------------------------------------------------------

    for code in REVIEWS:

        if code not in by_code:
            raise ValueError(
                f"Required Batch 5 record missing: {code}"
            )

    # --------------------------------------------------------
    # Update only Batch 5 records
    # --------------------------------------------------------

    for code, updates in REVIEWS.items():

        row = by_code[code]

        if row["Operational_Inclusion_Decision"].strip() != "PENDING":
            raise ValueError(
                f"{code}: operational inclusion is not PENDING."
            )

        coordinate_status = (
            row["Coordinate_Validation_Status"].strip()
        )

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
    # Write new output; never overwrite Batch 4
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
            "Output schema differs from input schema."
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
    # Verify Batch 5 safeguards
    # --------------------------------------------------------

    for code in REVIEWS:

        row = check_by_code[code]

        if row["Source_Content_Review_Status"] != "IN_PROGRESS":
            raise ValueError(
                f"{code}: source review status validation failed."
            )

        if row["Operational_Inclusion_Decision"] != "PENDING":
            raise ValueError(
                f"{code}: operational inclusion changed unexpectedly."
            )

        if row["Coordinate_Validation_Status"] not in (
            "PENDING",
            "PENDING_RECONCILIATION"
        ):
            raise ValueError(
                f"{code}: coordinate status changed unexpectedly."
            )

    # --------------------------------------------------------
    # Verify other 12 records are unchanged in manual fields
    # --------------------------------------------------------

    updated_codes = set(REVIEWS)

    for code, original_row in by_code.items():

        if code in updated_codes:
            continue

        output_row = check_by_code[code]

        for field in MANUAL_FIELDS:

            if (
                original_row.get(field, "")
                != output_row.get(field, "")
            ):
                raise ValueError(
                    f"Unexpected modification: {code}, {field}"
                )

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    print("\n" + "=" * 68)
    print("SCRIPT 45 COMPLETED SUCCESSFULLY")
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

    print("\nInput Batch 4 CSV was not modified.")

    print("=" * 68)


if __name__ == "__main__":
    main()
