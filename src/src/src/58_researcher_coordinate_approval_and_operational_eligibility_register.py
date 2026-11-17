"""
SCRIPT 58: RESEARCHER COORDINATE APPROVAL AND OPERATIONAL ELIGIBILITY REGISTER
----------------------------------------------------------------------------
Creates a researcher-facing decision register from the audited Script 57 v2
record-level validation register.

This script:
- Preserves all 19 source records and Script 49 / Script 53 classifications.
- Carries forward Script 57 v2 validation pathways and evidence interpretations.
- Separates coordinate approval from operational inclusion.
- Creates explicit researcher decision fields with PENDING defaults.
- Provides decision guidance, required evidence, and a decision audit trail.
- Does NOT approve coordinates, include ports operationally, or establish AIS
  transit through the Strait of Hormuz.

Input:
    outputs/tables/57_independent_coordinate_validation_register_v2.csv

Outputs:
    outputs/tables/58_researcher_coordinate_approval_register.csv
    outputs/tables/58_researcher_decision_summary.csv
    outputs/reports/58_researcher_coordinate_approval_report.txt

Researcher must manually complete the decision fields in the CSV. Re-run this
script only to regenerate the blank decision template from Script 57 v2; doing
so will overwrite the decision register. Preserve a completed copy separately.
"""

from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

INPUT_FILE = TABLE_DIR / "57_independent_coordinate_validation_register_v2.csv"
REGISTER_FILE = TABLE_DIR / "58_researcher_coordinate_approval_register.csv"
SUMMARY_FILE = TABLE_DIR / "58_researcher_decision_summary.csv"
REPORT_FILE = REPORT_DIR / "58_researcher_coordinate_approval_report.txt"

EXPECTED_RECORDS = 19

REQUIRED_COLUMNS = {
    "UNLOCODE", "Port_Name",
    "Script49_Eligibility_Classification", "Script49_Recommended_Use",
    "Primary_Source_Organization", "Primary_Source_Title", "Primary_Source_URL",
    "Primary_Latitude", "Primary_Longitude", "Primary_Coordinate_Scope",
    "Primary_Reference_Point", "Primary_Datum_or_CRS",
    "Secondary_Source_Organization", "Secondary_Source_Title", "Secondary_Source_URL",
    "Secondary_Latitude", "Secondary_Longitude", "Secondary_Coordinate_Scope",
    "Secondary_Reference_Point", "Secondary_Datum_or_CRS",
    "Coordinate_Distance_KM", "Script53_Independence_Status",
    "Script53_Validation_Status", "Validation_Pathway_v2",
    "Evidence_Scope_Interpretation_v2",
    "Organizational_Independence_Class_v2",
    "Independent_Coordinate_Corroboration_Status_v2",
    "AIS_Hormuz_Transit_Status",
}

# This is guidance for human review, not a recommendation to approve.
REVIEW_GUIDANCE = {
    "AEAUH": (
        "HOLD_FACILITY_IDENTITY_RECONCILIATION",
        "Identify the exact port facility represented by the commercial point and establish whether it is the same object as the UN/LOCODE multimodal point. Do not approve the UN/LOCODE point as a port coordinate by default."
    ),
    "AEFJR": (
        "HOLD_SAME_AUTHORITY_REFERENCE_POINT_RECONCILIATION",
        "Obtain the exact reference-point definitions and resolve the 1.138 km difference. The two sources are not independent."
    ),
    "AEKLF": (
        "HOLD_REFERENCE_POINT_AND_SCOPE_REVIEW",
        "Resolve the approximately 1.998 km difference and confirm whether both sources refer to the same port reference point."
    ),
    "AERKT": (
        "HOLD_DIFFERENT_PORT_IDENTITY",
        "Do not use the Mina Saqr secondary point as a Ras Al Khaimah port coordinate. Identify a coordinate source for the intended Ras Al Khaimah facility if required."
    ),
    "AESHJ": (
        "HOLD_NAVIGATIONAL_OBJECT_MISMATCH",
        "The fairway buoy coordinate is not a port coordinate. Obtain a coordinate for the intended port or terminal reference point."
    ),
    "BHKBS": (
        "CANDIDATE_FOR_RESEARCHER_SOURCE_VERIFICATION",
        "Check the government and operator source pages, exact reference-point definitions, datum, and the noted operator outlier before considering port-level coordinate approval."
    ),
    "INHZA": (
        "CANDIDATE_FOR_RESEARCHER_SOURCE_VERIFICATION",
        "Check the provenance and exact point definitions of the port and government maritime-board coordinates. Near-identical coordinates do not remove the need for source verification."
    ),
    "INIXY": (
        "HOLD_SAME_AUTHORITY_POSITION_RECONCILIATION",
        "Resolve the 3.226 km difference between positions published by the same authority. Do not count the sources as independent."
    ),
    "INPPV": (
        "HOLD_SAME_OPERATOR_SOURCE_LIMITATION",
        "The coordinates are identical but both records are associated with the same operator. Seek an independent authority or nautical source before claiming independent corroboration."
    ),
    "IQUQR": (
        "HOLD_TERMINAL_SPECIFIC_IDENTITY",
        "Identify which terminal is relevant to the research question. Keep the two terminal coordinate references separate; do not average them into a port point."
    ),
    "KWSAA": (
        "HOLD_PRIMARY_COORDINATE_MISSING",
        "The secondary point is a candidate only. Seek a coordinate-bearing primary authority or nautical source, or explicitly document a single-source limitation."
    ),
    "KWSWK": (
        "CANDIDATE_FOR_RESEARCHER_SOURCE_VERIFICATION",
        "Verify the NGA and independent gazetteer source provenance, reference-point definitions and datum before considering approval."
    ),
    "OMDQM": (
        "HOLD_BOUNDARY_VERSUS_POINT_MISMATCH",
        "Do not calculate a centroid or treat port limits/pilot stations as a port point. Obtain an explicitly published point for the intended facility."
    ),
    "PKKIA": (
        "HOLD_REFERENCE_OBJECT_MISMATCH",
        "Resolve whether the research entity is Karachi Upper Harbour, Kiamari locality, or a specific terminal. These are not interchangeable."
    ),
    "QAQAP": (
        "HOLD_BERTH_VERSUS_PLANT_MISMATCH",
        "A plant coordinate cannot approve berth coordinates. Obtain geodetic coordinates for the specific QAPCO berth(s) if berth-level representation is required."
    ),
    "QAQCH": (
        "HOLD_NO_GEODETIC_BERTH_COORDINATE",
        "Resolve berth numbering across the sources and obtain geodetic coordinates. Berth identity or relative location alone is insufficient for coordinate approval."
    ),
    "QAUMS": (
        "HOLD_PORT_POLYGON_NOT_POINT",
        "Do not derive a centroid from the port-limit polygon. Obtain a published point for the intended port/facility and reconcile the commercial point's scope."
    ),
    "SADMM": (
        "CANDIDATE_FOR_RESEARCHER_SOURCE_VERIFICATION",
        "Verify the NGA and independent port-list source provenance, exact point definitions and datum before considering approval."
    ),
    "SAJUB": (
        "HOLD_PRIMARY_COORDINATE_AND_SECONDARY_CONFLICT",
        "Obtain a coordinate-bearing Mawani or other authoritative primary source and reconcile the differing secondary points."
    ),
}


def clean(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def valid_pair(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
        return np.isfinite(lat) and np.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180
    except (TypeError, ValueError):
        return False


def build_register(source):
    records = []
    for _, row in source.iterrows():
        code = clean(row["UNLOCODE"]).upper()
        if code not in REVIEW_GUIDANCE:
            raise ValueError(f"No researcher review guidance defined for {code}")

        guidance_class, guidance = REVIEW_GUIDANCE[code]
        p_valid = valid_pair(row["Primary_Latitude"], row["Primary_Longitude"])
        s_valid = valid_pair(row["Secondary_Latitude"], row["Secondary_Longitude"])

        rec = row.to_dict()
        rec.update({
            "Primary_Coordinate_Pair_Valid_58": p_valid,
            "Secondary_Coordinate_Pair_Valid_58": s_valid,
            "Researcher_Review_Guidance_Class": guidance_class,
            "Researcher_Review_Guidance": guidance,

            # Researcher-controlled coordinate decision fields.
            "Researcher_Coordinate_Decision": "PENDING",
            "Approved_Latitude": np.nan,
            "Approved_Longitude": np.nan,
            "Approved_Coordinate_Reference_Object": "",
            "Approved_Coordinate_Scope": "",
            "Approved_Datum_or_CRS": "",
            "Coordinate_Approval_Evidence_URL": "",
            "Coordinate_Approval_Rationale": "",
            "Coordinate_Reviewer": "",
            "Coordinate_Review_Date": "",

            # Independent operational inclusion decision.
            "Researcher_Operational_Decision": "PENDING",
            "Operational_Inclusion_Rationale": "",
            "Operational_Eligibility_Evidence_URL": "",
            "Operational_Reviewer": "",
            "Operational_Review_Date": "",

            # Separate evidence status: do not infer actual Hormuz transit.
            "AIS_Transit_Evidence_Status": "NOT_ESTABLISHED",
            "AIS_Evidence_Source_URL": "",
            "AIS_Transit_Reviewer": "",
            "AIS_Transit_Review_Date": "",

            "Script58_Record_Status": "PENDING_RESEARCHER_REVIEW",
        })
        records.append(rec)

    return pd.DataFrame(records)


def build_summary(register):
    metrics = [
        ("Total records in researcher register", len(register)),
        ("Coordinate decisions pending", int(register["Researcher_Coordinate_Decision"].eq("PENDING").sum())),
        ("Operational decisions pending", int(register["Researcher_Operational_Decision"].eq("PENDING").sum())),
        ("Records with valid primary coordinate pairs", int(register["Primary_Coordinate_Pair_Valid_58"].sum())),
        ("Records with valid secondary coordinate pairs", int(register["Secondary_Coordinate_Pair_Valid_58"].sum())),
        ("Records with both coordinate pairs", int((register["Primary_Coordinate_Pair_Valid_58"] & register["Secondary_Coordinate_Pair_Valid_58"]).sum())),
        ("Records with hold/reconciliation guidance", int(register["Researcher_Review_Guidance_Class"].str.startswith("HOLD_").sum())),
        ("Records with source-verification candidate guidance", int(register["Researcher_Review_Guidance_Class"].eq("CANDIDATE_FOR_RESEARCHER_SOURCE_VERIFICATION").sum())),
        ("Coordinate approvals made automatically", 0),
        ("Operational inclusion decisions made automatically", 0),
        ("AIS-confirmed Hormuz transits established automatically", 0),
    ]
    return pd.DataFrame(metrics, columns=["Metric", "Value"])


def write_report(register, summary):
    with REPORT_FILE.open("w", encoding="utf-8") as f:
        f.write("=" * 88 + "\n")
        f.write("SCRIPT 58: RESEARCHER COORDINATE APPROVAL AND OPERATIONAL ELIGIBILITY REGISTER\n")
        f.write("=" * 88 + "\n\n")
        f.write("PURPOSE\n")
        f.write(
            "Create a researcher-facing register that separates coordinate approval, "
            "operational inclusion, and AIS transit evidence. All researcher decisions "
            "are initialized as PENDING.\n\n"
        )
        f.write("INPUT\n")
        f.write(f"{INPUT_FILE}\n\n")
        f.write("SUMMARY\n")
        f.write(summary.to_string(index=False))
        f.write("\n\nREVIEW GUIDANCE COUNTS\n")
        f.write(register["Researcher_Review_Guidance_Class"].value_counts().to_string())
        f.write("\n\nRESEARCHER DECISION RULES\n")
        f.write(
            "- Do not approve a coordinate merely because a numeric pair exists.\n"
            "- Do not approve coordinates when the source reference object is unresolved.\n"
            "- Do not treat same-authority/operator sources as independent corroboration.\n"
            "- Do not treat distinct terminals as duplicate points for one facility.\n"
            "- Do not substitute a buoy, berth identity, industrial plant, pilot station, "
            "boundary polygon or polygon centroid for a port point.\n"
            "- Operational inclusion is a separate decision from coordinate approval.\n"
            "- Regional/sensitivity eligibility from Script 49 remains a recommendation "
            "pending researcher approval, not an automatic inclusion decision.\n"
            "- No AIS-confirmed Strait of Hormuz transit is established by Script 58.\n\n"
        )
        f.write("REQUIRED MANUAL FIELDS\n")
        f.write(
            "Researcher_Coordinate_Decision; Approved_Latitude; Approved_Longitude; "
            "Approved_Coordinate_Reference_Object; Approved_Coordinate_Scope; "
            "Approved_Datum_or_CRS; Coordinate_Approval_Evidence_URL; "
            "Coordinate_Approval_Rationale; Coordinate_Reviewer; Coordinate_Review_Date; "
            "Researcher_Operational_Decision; Operational_Inclusion_Rationale; "
            "Operational_Eligibility_Evidence_URL; Operational_Reviewer; "
            "Operational_Review_Date; AIS_Transit_Evidence_Status; AIS_Evidence_Source_URL.\n"
        )


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Required input not found: {INPUT_FILE}")

    source = pd.read_csv(INPUT_FILE)
    missing = REQUIRED_COLUMNS - set(source.columns)
    if missing:
        raise ValueError(f"Script 57 v2 input missing columns: {sorted(missing)}")

    source["UNLOCODE"] = source["UNLOCODE"].astype("string").str.strip().str.upper()
    if len(source) != EXPECTED_RECORDS:
        raise ValueError(f"Expected {EXPECTED_RECORDS} records, found {len(source)}.")
    if source["UNLOCODE"].isna().any() or source["UNLOCODE"].eq("").any():
        raise ValueError("Missing UN/LOCODE.")
    if source["UNLOCODE"].duplicated().any():
        raise ValueError("Duplicate UN/LOCODE.")
    if set(source["UNLOCODE"]) != set(REVIEW_GUIDANCE):
        raise ValueError(
            f"Review guidance coverage mismatch. "
            f"Missing={set(REVIEW_GUIDANCE)-set(source['UNLOCODE'])}; "
            f"Unexpected={set(source['UNLOCODE'])-set(REVIEW_GUIDANCE)}"
        )

    register = build_register(source)

    # Preserve upstream classifications and source statuses exactly.
    for col in [
        "Script49_Eligibility_Classification",
        "Script49_Recommended_Use",
        "Script53_Independence_Status",
        "Script53_Validation_Status",
        "Validation_Pathway_v2",
        "Independent_Coordinate_Corroboration_Status_v2",
    ]:
        if not register[col].fillna("").astype(str).equals(source[col].fillna("").astype(str)):
            raise AssertionError(f"Upstream field changed: {col}")

    if not register["Researcher_Coordinate_Decision"].eq("PENDING").all():
        raise AssertionError("Coordinate decisions must start pending.")
    if not register["Researcher_Operational_Decision"].eq("PENDING").all():
        raise AssertionError("Operational decisions must start pending.")
    if not register["AIS_Transit_Evidence_Status"].eq("NOT_ESTABLISHED").all():
        raise AssertionError("AIS transit status must not be inferred.")

    summary = build_summary(register)

    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    register.to_csv(REGISTER_FILE, index=False)
    summary.to_csv(SUMMARY_FILE, index=False)
    write_report(register, summary)

    print("=" * 88)
    print("SCRIPT 58: RESEARCHER COORDINATE APPROVAL AND OPERATIONAL ELIGIBILITY REGISTER")
    print("=" * 88)
    print(f"\nInput records: {len(source)}")
    print("UN/LOCODE uniqueness and coverage: PASS")
    print("Script 49 classifications preserved: PASS")
    print("Script 53 statuses preserved: PASS")
    print("Script 57 v2 validation pathways preserved: PASS")
    print("Coordinate decisions initialized as PENDING: PASS")
    print("Operational decisions initialized as PENDING: PASS")
    print("AIS transit not inferred: PASS")
    print("\nSUMMARY")
    print(summary.to_string(index=False))
    print("\nREVIEW GUIDANCE")
    print(register["Researcher_Review_Guidance_Class"].value_counts().to_string())
    print("\nOUTPUTS")
    print(REGISTER_FILE.relative_to(ROOT))
    print(SUMMARY_FILE.relative_to(ROOT))
    print(REPORT_FILE.relative_to(ROOT))
    print("\nIMPORTANT: Complete researcher decision fields manually.")
    print("Do not rerun this script over a completed decision register without backing it up.")
    print("\nSCRIPT 58 COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()
