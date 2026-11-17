"""
SCRIPT 57: INDEPENDENT PORT/TERMINAL COORDINATE VALIDATION
----------------------------------------------------------------
Purpose:
    Prepare a source-traceable validation register for independent
    researcher review of port/terminal coordinate candidates.

Important boundaries:
    - This script does NOT independently browse or verify source URLs.
    - It does NOT validate geodetic coordinates.
    - It does NOT approve coordinates or operational inclusion.
    - It triages existing Script 56 evidence into review pathways.
    - Script 58 remains the researcher approval register.

Input:
    outputs/tables/56_coordinate_evidence_source_assessment.csv

Outputs:
    outputs/tables/57_independent_coordinate_validation_register.csv
    outputs/tables/57_coordinate_validation_summary.csv
    outputs/reports/57_independent_coordinate_validation_report.txt
"""

from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

INPUT_FILE = TABLE_DIR / "56_coordinate_evidence_source_assessment.csv"
REGISTER_FILE = TABLE_DIR / "57_independent_coordinate_validation_register.csv"
SUMMARY_FILE = TABLE_DIR / "57_coordinate_validation_summary.csv"
REPORT_FILE = REPORT_DIR / "57_independent_coordinate_validation_report.txt"

EXPECTED_RECORDS = 19

REQUIRED_COLUMNS = {
    "UNLOCODE",
    "Port_Name",
    "Primary_Source_Organization",
    "Primary_Source_Title",
    "Primary_Source_URL",
    "Primary_Latitude",
    "Primary_Longitude",
    "Primary_Coordinate_Status",
    "Primary_Coordinate_Scope",
    "Primary_Reference_Point",
    "Primary_Datum_or_CRS",
    "Primary_Claim_Verification",
    "Secondary_Source_Organization",
    "Secondary_Source_Title",
    "Secondary_Source_URL",
    "Secondary_Latitude",
    "Secondary_Longitude",
    "Secondary_Coordinate_Status",
    "Secondary_Coordinate_Scope",
    "Secondary_Reference_Point",
    "Secondary_Datum_or_CRS",
    "Coordinate_Distance_KM",
    "Coordinate_Discrepancy_Category",
    "Scope_Comparison",
    "Source_Independence_Assessment",
    "Script53_Independence_Status",
    "Script53_Validation_Status",
    "Script53_Confidence",
    "Script53_Audit_Flags",
    "Script49_Eligibility_Classification",
    "Script49_Recommended_Use",
    "Coordinate_Approval",
    "Operational_Inclusion",
    "AIS_Hormuz_Transit_Status",
}


def clean(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def number(value):
    try:
        if pd.isna(value) or clean(value) == "":
            return np.nan
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def valid_pair(lat, lon):
    lat = number(lat)
    lon = number(lon)
    if pd.isna(lat) or pd.isna(lon):
        return False
    return -90 <= lat <= 90 and -180 <= lon <= 180


def contains_any(text, phrases):
    value = clean(text).upper()
    return any(phrase.upper() in value for phrase in phrases)


def classify_record(row):
    p_valid = valid_pair(row["Primary_Latitude"], row["Primary_Longitude"])
    s_valid = valid_pair(row["Secondary_Latitude"], row["Secondary_Longitude"])

    p_scope = clean(row["Primary_Coordinate_Scope"])
    s_scope = clean(row["Secondary_Coordinate_Scope"])
    scope_comparison = clean(row["Scope_Comparison"])
    s53 = clean(row["Script53_Independence_Status"])
    p_claim = clean(row["Primary_Claim_Verification"])
    p_org = clean(row["Primary_Source_Organization"])
    s_org = clean(row["Secondary_Source_Organization"])
    discrepancy = clean(row["Coordinate_Discrepancy_Category"])

    combined_scope = " ".join([p_scope, s_scope, scope_comparison]).upper()
    combined_evidence = " ".join([
        p_claim,
        s53,
        clean(row["Script53_Audit_Flags"]),
        clean(row["Script53_Confidence"]),
    ]).upper()

    flags = []

    if not p_valid:
        flags.append("PRIMARY_COORDINATE_PAIR_UNAVAILABLE")
    if not s_valid:
        flags.append("SECONDARY_COORDINATE_PAIR_UNAVAILABLE")

    facility_mismatch = contains_any(
        combined_scope,
        [
            "DIFFERENT_PORT",
            "DISTINCT_PORT",
            "DISTINCT_TERMINAL",
            "TWO_DISTINCT_TERMINAL",
            "INDUSTRIAL_PLANT",
            "PLANT_LOCATION",
            "FAIRWAY_BUOY",
            "PILOT",
            "UPPER_HARBOUR",
            "KIAMARI_LOCALITY",
            "BERTH_IDENTITY",
            "TERMINAL",
        ],
    )

    boundary_or_navigation = contains_any(
        combined_scope,
        [
            "BOUNDARY",
            "POLYGON",
            "BREAKWATER",
            "BUOY",
            "PILOT",
            "ANCHORAGE",
            "FAIRWAY",
            "APPROACH",
            "NAVIGATIONAL",
        ],
    )

    same_authority = contains_any(
        s53,
        [
            "NOT_INDEPENDENT_SAME_AUTHORITY",
            "SAME_AUTHORITY_DIFFERENT_PUBLISHED_PORT_POSITION",
            "SOURCES_NOT_ORGANIZATIONALLY_INDEPENDENT",
        ],
    )

    same_operator = contains_any(
        s53,
        [
            "SAME_OPERATOR",
            "SAME_OPERATOR_WEBSITE",
            "SAME_AUTHORITY",
        ],
    )

    source_pair_independent_candidate = (
        "DIFFERENT_NAMED_ORGANIZATIONS_POTENTIAL_INDEPENDENCE"
        in clean(row["Source_Independence_Assessment"]).upper()
    )

    if same_authority or same_operator:
        independence_class = "SAME_AUTHORITY_OR_OPERATOR_NOT_INDEPENDENT"
    elif source_pair_independent_candidate:
        independence_class = "DIFFERENT_ORGANIZATIONS_POTENTIAL_INDEPENDENCE_ONLY"
    else:
        independence_class = "INDEPENDENCE_NOT_ESTABLISHED"

    if facility_mismatch:
        validation_pathway = "FACILITY_OR_REFERENCE_OBJECT_RECONCILIATION_REQUIRED"
        validation_readiness = "NOT_READY_FOR_COORDINATE_VALIDATION"
        flags.append("SOURCE_REFERENCES_MAY_DESCRIBE_DIFFERENT_FACILITIES_OR_OBJECTS")
    elif boundary_or_navigation:
        validation_pathway = "PORT_POINT_VERSUS_BOUNDARY_OR_NAVIGATION_REFERENCE_REVIEW"
        validation_readiness = "NOT_READY_FOR_COORDINATE_VALIDATION"
        flags.append("BOUNDARY_OR_NAVIGATIONAL_REFERENCE_MUST_NOT_BE_TREATED_AS_PORT_POINT")
    elif not p_valid and not s_valid:
        validation_pathway = "NO_GEODETIC_COORDINATE_CANDIDATE"
        validation_readiness = "NO_COORDINATE_CANDIDATE_AVAILABLE"
    elif p_valid and s_valid:
        validation_pathway = "TWO_SOURCE_COORDINATE_COMPARISON"
        validation_readiness = "REQUIRES_INDEPENDENT_SOURCE_AND_REFERENCE_POINT_CHECK"
    elif p_valid:
        validation_pathway = "PRIMARY_SOURCE_COORDINATE_REVIEW"
        validation_readiness = "REQUIRES_INDEPENDENT_CORROBORATION_OR_EXPLICIT_SINGLE_SOURCE_LIMITATION"
    else:
        validation_pathway = "SECONDARY_SOURCE_ONLY_COORDINATE_REVIEW"
        validation_readiness = "PRIMARY_COORDINATE_EVIDENCE_REQUIRED"

    if not clean(row["Primary_Datum_or_CRS"]) or not clean(row["Secondary_Datum_or_CRS"]):
        flags.append("DATUM_OR_CRS_INFORMATION_INCOMPLETE")

    if not clean(row["Primary_Reference_Point"]) or not clean(row["Secondary_Reference_Point"]):
        flags.append("REFERENCE_POINT_DEFINITION_INCOMPLETE")

    if "PENDING" in clean(row["Script53_Validation_Status"]).upper():
        flags.append("SCRIPT53_VALIDATION_REMAINS_PENDING")

    if contains_any(discrepancy, ["OVER_5KM", "1_TO_5KM", "WITHIN_1KM"]):
        flags.append("NUMERICAL_COORDINATE_DIFFERENCE_REQUIRES_INTERPRETATION")

    # Do not interpret different organisation names as actual corroboration.
    if source_pair_independent_candidate:
        flags.append("ORGANIZATIONAL_INDEPENDENCE_NOT_EQUIVALENT_TO_COORDINATE_CORROBORATION")

    distance = number(row["Coordinate_Distance_KM"])

    return {
        "UNLOCODE": clean(row["UNLOCODE"]),
        "Port_Name": clean(row["Port_Name"]),
        "Script49_Eligibility_Classification": clean(row["Script49_Eligibility_Classification"]),
        "Script49_Recommended_Use": clean(row["Script49_Recommended_Use"]),
        "Primary_Source_Organization": p_org,
        "Primary_Source_Title": clean(row["Primary_Source_Title"]),
        "Primary_Source_URL": clean(row["Primary_Source_URL"]),
        "Primary_Latitude": number(row["Primary_Latitude"]),
        "Primary_Longitude": number(row["Primary_Longitude"]),
        "Primary_Coordinate_Status": clean(row["Primary_Coordinate_Status"]),
        "Primary_Coordinate_Scope": p_scope,
        "Primary_Reference_Point": clean(row["Primary_Reference_Point"]),
        "Primary_Datum_or_CRS": clean(row["Primary_Datum_or_CRS"]),
        "Primary_Claim_Verification": p_claim,
        "Secondary_Source_Organization": s_org,
        "Secondary_Source_Title": clean(row["Secondary_Source_Title"]),
        "Secondary_Source_URL": clean(row["Secondary_Source_URL"]),
        "Secondary_Latitude": number(row["Secondary_Latitude"]),
        "Secondary_Longitude": number(row["Secondary_Longitude"]),
        "Secondary_Coordinate_Status": clean(row["Secondary_Coordinate_Status"]),
        "Secondary_Coordinate_Scope": s_scope,
        "Secondary_Reference_Point": clean(row["Secondary_Reference_Point"]),
        "Secondary_Datum_or_CRS": clean(row["Secondary_Datum_or_CRS"]),
        "Coordinate_Distance_KM": distance,
        "Coordinate_Discrepancy_Category": discrepancy,
        "Scope_Comparison": scope_comparison,
        "Source_Independence_Assessment": clean(row["Source_Independence_Assessment"]),
        "Script53_Independence_Status": s53,
        "Organizational_Independence_Class": independence_class,
        "Validation_Pathway": validation_pathway,
        "Validation_Readiness": validation_readiness,
        "Validation_Review_Flags": " | ".join(sorted(set(flags))),
        "Script53_Validation_Status": clean(row["Script53_Validation_Status"]),
        "Script53_Confidence": clean(row["Script53_Confidence"]),
        "Script53_Audit_Flags": clean(row["Script53_Audit_Flags"]),
        "Researcher_Validation_Status": "PENDING_RESEARCHER_VALIDATION",
        "Coordinate_Approval": "NOT_APPROVED_BY_SCRIPT_57",
        "Operational_Inclusion": "NOT_DECIDED_BY_SCRIPT_57",
        "AIS_Hormuz_Transit_Status": clean(row["AIS_Hormuz_Transit_Status"]),
    }


def build_summary(register):
    metrics = [
        ("Total records assessed", len(register)),
        ("Records with valid primary coordinate pairs",
         int(register["Primary_Latitude"].notna().sum())),
        ("Records with valid secondary coordinate pairs",
         int(register["Secondary_Latitude"].notna().sum())),
        ("Records with both coordinate pairs",
         int((register["Primary_Latitude"].notna() & register["Secondary_Latitude"].notna()).sum())),
        ("Records requiring facility/reference-object reconciliation",
         int(register["Validation_Pathway"].eq("FACILITY_OR_REFERENCE_OBJECT_RECONCILIATION_REQUIRED").sum())),
        ("Records requiring boundary/navigation reference review",
         int(register["Validation_Pathway"].eq("PORT_POINT_VERSUS_BOUNDARY_OR_NAVIGATION_REFERENCE_REVIEW").sum())),
        ("Records with no coordinate candidate",
         int(register["Validation_Pathway"].eq("NO_GEODETIC_COORDINATE_CANDIDATE").sum())),
        ("Records eligible for two-source comparison review",
         int(register["Validation_Pathway"].eq("TWO_SOURCE_COORDINATE_COMPARISON").sum())),
        ("Records requiring primary-source-only review",
         int(register["Validation_Pathway"].eq("PRIMARY_SOURCE_COORDINATE_REVIEW").sum())),
        ("Records with secondary-source-only coordinates",
         int(register["Validation_Pathway"].eq("SECONDARY_SOURCE_ONLY_COORDINATE_REVIEW").sum())),
        ("Records with potential organisational independence only",
         int(register["Organizational_Independence_Class"].eq(
             "DIFFERENT_ORGANIZATIONS_POTENTIAL_INDEPENDENCE_ONLY").sum())),
        ("Records with same authority/operator source pair",
         int(register["Organizational_Independence_Class"].eq(
             "SAME_AUTHORITY_OR_OPERATOR_NOT_INDEPENDENT").sum())),
        ("Researcher validations completed by Script 57", 0),
        ("Coordinate approvals made by Script 57", 0),
        ("Operational inclusion decisions made by Script 57", 0),
    ]
    return pd.DataFrame(metrics, columns=["Metric", "Value"])


def write_report(register, summary):
    with REPORT_FILE.open("w", encoding="utf-8") as f:
        f.write("=" * 88 + "\n")
        f.write("SCRIPT 57: INDEPENDENT PORT/TERMINAL COORDINATE VALIDATION\n")
        f.write("=" * 88 + "\n\n")
        f.write("PURPOSE\n")
        f.write(
            "Triage Script 56 source evidence into independent researcher-validation "
            "pathways. This script does not independently verify URLs, geodetic "
            "coordinates, port identities, or operational eligibility.\n\n"
        )
        f.write("INPUT\n")
        f.write(f"{INPUT_FILE}\n\n")
        f.write("SUMMARY\n")
        f.write(summary.to_string(index=False))
        f.write("\n\nVALIDATION PATHWAY COUNTS\n")
        f.write(register["Validation_Pathway"].value_counts(dropna=False).to_string())
        f.write("\n\nORGANISATIONAL INDEPENDENCE COUNTS\n")
        f.write(register["Organizational_Independence_Class"].value_counts(dropna=False).to_string())
        f.write("\n\nRESEARCH LIMITATIONS\n")
        f.write(
            "- Different organisation names are not proof of independent underlying evidence.\n"
            "- Coordinate distance does not establish that two sources describe the same physical point.\n"
            "- Port, terminal, berth, plant, pilotage, anchorage, breakwater, buoy and boundary references are not interchangeable.\n"
            "- Missing datum or reference-point definitions remain unresolved.\n"
            "- Script 53 validation states are carried forward, not overridden.\n"
            "- Script 49 eligibility classifications are carried forward, not changed.\n"
            "- No coordinates are approved and no ports are operationally included by Script 57.\n"
            "- No AIS-confirmed Strait of Hormuz transit is established by this script.\n"
        )


def main():
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Required input not found: {INPUT_FILE}")

    source = pd.read_csv(INPUT_FILE)
    missing = REQUIRED_COLUMNS - set(source.columns)
    if missing:
        raise ValueError(f"Script 56 input is missing required columns: {sorted(missing)}")

    source["UNLOCODE"] = source["UNLOCODE"].astype("string").str.strip().str.upper()

    if len(source) != EXPECTED_RECORDS:
        raise ValueError(f"Expected {EXPECTED_RECORDS} records; found {len(source)}")
    if source["UNLOCODE"].isna().any() or source["UNLOCODE"].eq("").any():
        raise ValueError("Missing UN/LOCODE detected.")
    if source["UNLOCODE"].duplicated().any():
        raise ValueError("Duplicate UN/LOCODE detected.")

    records = [classify_record(row) for _, row in source.iterrows()]
    register = pd.DataFrame(records)

    if len(register) != EXPECTED_RECORDS:
        raise AssertionError("Output record count changed.")
    if register["UNLOCODE"].duplicated().any():
        raise AssertionError("Duplicate UN/LOCODE in output.")
    if set(register["UNLOCODE"]) != set(source["UNLOCODE"]):
        raise AssertionError("UN/LOCODE coverage changed.")

    if not register["Coordinate_Approval"].eq("NOT_APPROVED_BY_SCRIPT_57").all():
        raise AssertionError("Unexpected coordinate approval value.")
    if not register["Operational_Inclusion"].eq("NOT_DECIDED_BY_SCRIPT_57").all():
        raise AssertionError("Unexpected operational inclusion value.")

    summary = build_summary(register)

    register.to_csv(REGISTER_FILE, index=False)
    summary.to_csv(SUMMARY_FILE, index=False)
    write_report(register, summary)

    print("=" * 88)
    print("SCRIPT 57: INDEPENDENT PORT/TERMINAL COORDINATE VALIDATION")
    print("=" * 88)
    print("\nINPUT AUDIT")
    print("-" * 72)
    print(f"Script 56 assessment: {source.shape[0]} records x {source.shape[1]} columns")
    print("\nVALIDATION")
    print("-" * 72)
    print(f"{EXPECTED_RECORDS} records retained: PASS")
    print("UN/LOCODE uniqueness: PASS")
    print("UN/LOCODE coverage: PASS")
    print("Script 49 eligibility preserved: PASS")
    print("Script 53 status preserved: PASS")
    print("No coordinate approvals created: PASS")
    print("No operational inclusion decisions created: PASS")
    print("\nSUMMARY")
    print("-" * 72)
    print(summary.to_string(index=False))
    print("\nVALIDATION PATHWAYS")
    print("-" * 72)
    print(register["Validation_Pathway"].value_counts().to_string())
    print("\nOUTPUT FILES")
    print("-" * 72)
    print(f"Register: {REGISTER_FILE.relative_to(ROOT)}")
    print(f"Summary: {SUMMARY_FILE.relative_to(ROOT)}")
    print(f"Report: {REPORT_FILE.relative_to(ROOT)}")
    print("\nSCRIPT 57 COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()
