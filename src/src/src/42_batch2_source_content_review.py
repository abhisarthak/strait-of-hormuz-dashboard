import csv
from pathlib import Path
from datetime import date

INPUT = Path(
    "outputs/tables/"
    "41_manual_source_content_verification_register.csv"
)

OUTPUT = Path(
    "outputs/tables/"
    "41_manual_source_content_verification_register_batch2_preliminary_review.csv"
)

TODAY = date.today().isoformat()

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

REVIEWS = {
    "AESHJ": {
        "Source_Content_Review_Status": "IN_PROGRESS",
        "Primary_Source_Content_Verified": "PARTIAL",
        "Secondary_Source_Content_Verified": "NOT_AVAILABLE",
        "Port_Identity_Claim_Verified": "PARTIAL",
        "Facility_Identity_Claim_Verified": "PARTIAL",
        "Geographic_Claim_Verified": "PARTIAL",
        "Coordinate_Claim_Verified": "NO",
        "Operational_Role_Claim_Verified": "PARTIAL",
        "Verified_Claims": (
            "Sharjah Ports Authority identifies three distinct ports: "
            "Port Khalid, Hamriyah Port and Khorfakkan. It describes "
            "Port Khalid as multipurpose, Hamriyah as a deepwater port "
            "and Khorfakkan as an east-coast container/transshipment hub."
        ),
        "Unsupported_or_Contradictory_Claims": (
            "The sources do not establish which facility corresponds "
            "to the AESHJ schedule calls. The 10 calls and 3 vessels "
            "are not mapped to a specific Sharjah facility. Khorfakkan "
            "is geographically distinct from the Gulf-coast facilities. "
            "No facility-specific coordinate has been validated. "
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
            "Official source: https://sharjahports.gov.ae/ . "
            "Additional official source: https://sharjahports.gov.ae/leadership . "
            "These sources establish the distinct port facilities and "
            "their roles, but do not identify which facility handled "
            "the AESHJ calls. Keep identity and facility attribution "
            "PARTIAL. Obtain schedule-provider facility mapping, "
            "port-agent records, terminal-specific call records or AIS "
            "evidence. Do not approve coordinates or operational inclusion."
        ),
    },

    "BHKBS": {
        "Source_Content_Review_Status": "IN_PROGRESS",
        "Primary_Source_Content_Verified": "YES",
        "Secondary_Source_Content_Verified": "YES",
        "Port_Identity_Claim_Verified": "YES",
        "Facility_Identity_Claim_Verified": "PARTIAL",
        "Geographic_Claim_Verified": "YES",
        "Coordinate_Claim_Verified": "PARTIAL",
        "Operational_Role_Claim_Verified": "YES",
        "Verified_Claims": (
            "APM Terminals Bahrain's KBSP Port Information guide "
            "identifies Khalifa Bin Salman Port, Hidd, Bahrain and "
            "UN Locator number BHKBS. It publishes 26 degrees 12 minutes "
            "N, 50 degrees 37 minutes E. Bahrain's Ministry of "
            "Transportation and Telecommunications identifies the port "
            "and its operating facilities. The APM Terminals Bahrain "
            "Ports Tariff also identifies BHKBS and publishes a separate "
            "port position of 26 degrees 10.9 minutes N, 50 degrees "
            "43.1 minutes E."
        ),
        "Unsupported_or_Contradictory_Claims": (
            "The two operator documents publish different coordinate "
            "positions. Their precise geographic scopes have not been "
            "reconciled. Neither coordinate should be selected "
            "automatically. The five dataset calls and one vessel have "
            "not been independently validated against berth or terminal "
            "records. No AIS-confirmed Hormuz transit is established."
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
            "APM Terminals Bahrain KBSP Port Information: "
            "https://www.apmterminals.com/bahrain/-/media/mainsite/"
            "africa-and-middle-east/Bahrain/About-us/"
            "kbsp-port-information-160724.pdf?rev=636372f26f4e40caad3e6a04ffbf2095 . "
            "Government source: https://www.mtt.gov.bh/khalifa-bin-salman-port . "
            "Additional APM Ports Tariff: "
            "https://www.apmterminals.com/bahrain/-/media/mainsite/"
            "africa-and-middle-east/Bahrain/About-us/"
            "BahrainPortsTariff2023V001.pdf?rev=2d2598ca53eb4b9d815fb0ae6f442d00 . "
            "The guide and tariff give different positions. Preserve both "
            "and investigate their scope before coordinate approval. "
            "Port identity is strongly supported, but terminal mapping "
            "and individual call provenance remain pending. Do not change "
            "operational inclusion from PENDING."
        ),
    },
}


def main():
    if not INPUT.exists():
        raise FileNotFoundError(
            f"Input not found: {INPUT}\n"
            "Check that Script 41 generated its CSV in outputs/tables."
        )

    with INPUT.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)

    if not fields:
        raise ValueError("Input CSV has no header.")

    missing = [field for field in MANUAL_FIELDS if field not in fields]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    by_code = {row.get("UN_LOCODE", "").strip(): row for row in rows}

    if len(by_code) != len(rows):
        raise ValueError("Duplicate or blank UN_LOCODE found.")

    for code, updates in REVIEWS.items():
        if code not in by_code:
            raise ValueError(f"Missing required record: {code}")

        row = by_code[code]

        if row.get("Operational_Inclusion_Decision", "").strip() != "PENDING":
            raise ValueError(
                f"{code}: operational decision is not PENDING. "
                "Review before proceeding."
            )

        # Update only the manual-review columns.
        for field in MANUAL_FIELDS:
            row[field] = updates[field]

        print(f"Updated: {code}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    # Verify the output.
    with OUTPUT.open("r", encoding="utf-8-sig", newline="") as f:
        check = list(csv.DictReader(f))

    assert len(check) == 19, "Record count changed."
    assert len({r["UN_LOCODE"] for r in check}) == 19

    checked = {r["UN_LOCODE"]: r for r in check}

    for code in REVIEWS:
        assert checked[code]["Operational_Inclusion_Decision"] == "PENDING"
        assert checked[code]["Coordinate_Validation_Status"] in (
            "PENDING", "PENDING_RECONCILIATION"
        )

    print("\n" + "=" * 65)
    print("SCRIPT 42 COMPLETED SUCCESSFULLY")
    print("=" * 65)
    print("Input records:", len(rows))
    print("Output records:", len(check))
    print("Columns preserved:", len(fields))
    print("Updated: AESHJ, BHKBS")
    print("Other records preserved:", len(check) - 2)
    print("Operational decisions: PENDING")
    print("Coordinate approvals: NONE")
    print("Output:", OUTPUT)
    print("Original input CSV was not modified.")
    print("=" * 65)


if __name__ == "__main__":
    main()
