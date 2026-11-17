from pathlib import Path
import math
import re
import pandas as pd


# ============================================================
# SCRIPT 56: COORDINATE EVIDENCE SOURCE ASSESSMENT
# CORRECTED VERSION 2 — SCRIPT 54 DATA-LINEAGE RESTORATION
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

INVENTORY_FILE = TABLE_DIR / "55_coordinate_evidence_inventory.csv"
REVIEW_FILE = TABLE_DIR / "55_coordinate_evidence_review_register.csv"
RECONCILIATION_FILE = TABLE_DIR / "54_consolidated_port_identity_coordinate_reconciliation.csv"

OUTPUT_FILE = TABLE_DIR / "56_coordinate_evidence_source_assessment.csv"
SUMMARY_FILE = TABLE_DIR / "56_coordinate_evidence_source_summary.csv"
REPORT_FILE = REPORT_DIR / "56_coordinate_evidence_source_assessment_report.txt"

EXPECTED_RECORDS = 19


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null", "not available"}:
        return ""
    return text


def get_text(row, column):
    return clean_text(row.get(column, ""))


def get_number(row, column):
    value = row.get(column)
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def normalize_organization(value):
    value = clean_text(value).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def valid_coordinate_pair(latitude, longitude):
    return (
        latitude is not None
        and longitude is not None
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


def haversine_km(lat1, lon1, lat2, lon2):
    radius = 6371.0088
    lat1, lon1, lat2, lon2 = map(
        math.radians, [lat1, lon1, lat2, lon2]
    )
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def extract_embedded_field(text, field_name):
    """
    Extract S53 fields embedded in Quality_Audit_Details.
    Values are delimited by the next '| S<number>_' field.
    """
    text = clean_text(text)
    if not text:
        return ""

    pattern = (
        r"(?:^|\s*\|\s*)"
        + re.escape(field_name)
        + r"=(.*?)(?=\s*\|\s*S\d+_|$)"
    )
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""


# ============================================================
# LOAD AND VALIDATE INPUTS
# ============================================================

def load_inputs():
    for path in (INVENTORY_FILE, REVIEW_FILE, RECONCILIATION_FILE):
        if not path.exists():
            raise FileNotFoundError(path)

    inventory = pd.read_csv(INVENTORY_FILE)
    review = pd.read_csv(REVIEW_FILE)
    reconciliation = pd.read_csv(RECONCILIATION_FILE)

    required_inventory = {
        "UNLOCODE",
        "Quality_Audit_Details",
        "S51_Primary_Source_Latitude",
        "S51_Primary_Source_Longitude",
        "S51_Secondary_Source_Latitude",
        "S51_Secondary_Source_Longitude",
        "S51_Primary_Source_Organization_Reviewed",
        "S51_Secondary_Source_Organization_Reviewed",
    }
    required_review = {
        "UNLOCODE",
        "Review_Priority",
        "Researcher_Review_Status",
        "Coordinate_Approval",
        "Operational_Inclusion",
        "AIS_Hormuz_Transit_Status",
    }
    required_reconciliation = {
        "UN_LOCODE",
        "Port_Name_in_Master",
        "Researcher_Validated_Port_Name",
        "Eligibility_Classification_from_Script49",
        "Recommended_Use_from_Script49",
        "Eligibility_Blocking_Conditions_from_Script49",
        "Regional_Sensitivity_Recommendation_Preserved",
        "Operational_Inclusion_Decision",
    }

    missing_inventory = required_inventory - set(inventory.columns)
    missing_review = required_review - set(review.columns)
    missing_reconciliation = required_reconciliation - set(reconciliation.columns)

    if missing_inventory:
        raise ValueError(f"Missing inventory columns: {sorted(missing_inventory)}")
    if missing_review:
        raise ValueError(f"Missing review columns: {sorted(missing_review)}")
    if missing_reconciliation:
        raise ValueError(
            f"Missing Script 54 reconciliation columns: {sorted(missing_reconciliation)}"
        )

    # Normalise join keys without changing the source files.
    for frame, key, name in [
        (inventory, "UNLOCODE", "inventory"),
        (review, "UNLOCODE", "review register"),
        (reconciliation, "UN_LOCODE", "Script 54 reconciliation"),
    ]:
        frame[key] = frame[key].astype("string").str.strip().str.upper()
        if frame[key].isna().any() or frame[key].eq("").any():
            raise ValueError(f"Missing UN/LOCODE in {name}.")
        if frame[key].duplicated().any():
            raise ValueError(f"Duplicate UN/LOCODE in {name}.")

    if len(inventory) != EXPECTED_RECORDS:
        raise ValueError(
            f"Expected {EXPECTED_RECORDS} inventory rows; found {len(inventory)}."
        )
    if len(review) != EXPECTED_RECORDS:
        raise ValueError(
            f"Expected {EXPECTED_RECORDS} review rows; found {len(review)}."
        )
    if len(reconciliation) != EXPECTED_RECORDS:
        raise ValueError(
            f"Expected {EXPECTED_RECORDS} Script 54 rows; found {len(reconciliation)}."
        )

    inventory_codes = set(inventory["UNLOCODE"])
    review_codes = set(review["UNLOCODE"])
    reconciliation_codes = set(reconciliation["UN_LOCODE"])

    if inventory_codes != review_codes:
        raise ValueError("UN/LOCODE coverage differs between Script 55 inputs.")
    if inventory_codes != reconciliation_codes:
        missing_54 = sorted(inventory_codes - reconciliation_codes)
        extra_54 = sorted(reconciliation_codes - inventory_codes)
        raise ValueError(
            "UN/LOCODE coverage differs between Script 54 and Script 55. "
            f"Missing in Script 54: {missing_54}; extra in Script 54: {extra_54}"
        )

    return inventory, review, reconciliation


# ============================================================
# SOURCE AND COORDINATE ASSESSMENT
# ============================================================

def assess_record(row, review_row, reconciliation_row):
    code = clean_text(row["UNLOCODE"])

    # Script 55's Port_Name is blank. Restore it from Script 54 using the
    # exact UN/LOCODE join, preferring the researcher-validated name.
    port_name = (
        get_text(reconciliation_row, "Researcher_Validated_Port_Name")
        or get_text(reconciliation_row, "Port_Name_in_Master")
    )

    script49_eligibility = get_text(
        reconciliation_row, "Eligibility_Classification_from_Script49"
    )
    script49_recommended_use = get_text(
        reconciliation_row, "Recommended_Use_from_Script49"
    )
    script49_blocking_conditions = get_text(
        reconciliation_row, "Eligibility_Blocking_Conditions_from_Script49"
    )
    regional_sensitivity_recommendation = get_text(
        reconciliation_row, "Regional_Sensitivity_Recommendation_Preserved"
    )
    script54_operational_decision = get_text(
        reconciliation_row, "Operational_Inclusion_Decision"
    )

    # Use reviewed source fields, not the older candidate-source fields.
    p_org = get_text(row, "S51_Primary_Source_Organization_Reviewed")
    p_title = get_text(row, "S51_Primary_Source_Title_Reviewed")
    p_url = get_text(row, "S51_Primary_Source_URL_Reviewed")
    p_type = get_text(row, "S51_Primary_Source_Type")
    p_scope = get_text(row, "S51_Primary_Source_Coordinate_Scope")
    p_reference = get_text(row, "S51_Primary_Source_Reference_Point")
    p_datum = get_text(row, "S51_Primary_Source_Datum_or_CRS")
    p_claim = get_text(row, "S51_Primary_Source_Claim_Verification")
    p_evidence = get_text(row, "S51_Primary_Source_Exact_Evidence")

    s_org = get_text(row, "S51_Secondary_Source_Organization_Reviewed")
    s_title = get_text(row, "S51_Secondary_Source_Title_Reviewed")
    s_url = get_text(row, "S51_Secondary_Source_URL_Reviewed")
    s_scope = get_text(row, "S51_Secondary_Source_Coordinate_Scope")
    s_reference = get_text(row, "S51_Secondary_Source_Reference_Point")
    s_datum = get_text(row, "S51_Secondary_Source_Datum_or_CRS")
    s_evidence = get_text(row, "S51_Secondary_Source_Exact_Evidence")

    p_lat = get_number(row, "S51_Primary_Source_Latitude")
    p_lon = get_number(row, "S51_Primary_Source_Longitude")
    s_lat = get_number(row, "S51_Secondary_Source_Latitude")
    s_lon = get_number(row, "S51_Secondary_Source_Longitude")

    p_pair_valid = valid_coordinate_pair(p_lat, p_lon)
    s_pair_valid = valid_coordinate_pair(s_lat, s_lon)

    if p_lat is not None and p_lon is not None and not p_pair_valid:
        p_status = "INVALID_NUMERIC_COORDINATE_RANGE"
    elif p_pair_valid:
        p_status = "NUMERIC_PAIR_PRESENT_NOT_APPROVED"
    else:
        p_status = "PRIMARY_COORDINATE_PAIR_MISSING"

    if s_lat is not None and s_lon is not None and not s_pair_valid:
        s_status = "INVALID_NUMERIC_COORDINATE_RANGE"
    elif s_pair_valid:
        s_status = "NUMERIC_PAIR_PRESENT_NOT_APPROVED"
    else:
        s_status = "SECONDARY_COORDINATE_PAIR_MISSING"

    # Independence assessment is based on reviewed organization fields.
    p_org_norm = normalize_organization(p_org)
    s_org_norm = normalize_organization(s_org)

    if not p_org_norm or not s_org_norm:
        independence = "INDEPENDENCE_NOT_ASSESSABLE"
    elif p_org_norm == s_org_norm:
        independence = "SAME_NAMED_ORGANIZATION_NOT_INDEPENDENT"
    else:
        independence = (
            "DIFFERENT_NAMED_ORGANIZATIONS_POTENTIAL_INDEPENDENCE"
        )

    # Script 53 explicitly assessed independence takes precedence.
    quality_details = get_text(row, "Quality_Audit_Details")
    s53_independence = extract_embedded_field(
        quality_details, "S53_Independent_Corroboration_Status"
    )
    s53_validation = extract_embedded_field(
        quality_details, "S53_Coordinate_Validation_Status"
    )
    s53_confidence = extract_embedded_field(
        quality_details, "S53_Coordinate_Confidence"
    )
    s53_flags = extract_embedded_field(
        quality_details, "S53_Audit_Flags"
    )
    s53_progress = extract_embedded_field(
        quality_details, "S53_Research_Progress_Status"
    )

    # Keep the source-organization comparison separate from Script 53's
    # earlier independence assessment. Different names indicate only
    # potential independence, not proven independent corroboration.
    organization_independence = independence

    # Coordinate distance is only a numerical comparison.
    # It does not establish that both sources describe the same object.
    distance = None
    if p_pair_valid and s_pair_valid:
        distance = haversine_km(p_lat, p_lon, s_lat, s_lon)

    p_scope_norm = normalize_organization(p_scope)
    s_scope_norm = normalize_organization(s_scope)

    if not p_scope or not s_scope:
        scope_comparison = "SCOPE_COMPARISON_INCOMPLETE"
    elif p_scope_norm == s_scope_norm:
        scope_comparison = "SCOPE_DESCRIPTIONS_MATCH"
    else:
        scope_comparison = "DIFFERENT_OR_UNRECONCILED_SCOPE"

    if distance is None:
        discrepancy = "NOT_COMPUTABLE_BOTH_PAIRS_NOT_AVAILABLE"
    elif distance <= 0.1:
        discrepancy = "NEAR_IDENTICAL_POINTS_WITHIN_100M"
    elif distance <= 1:
        discrepancy = "POINTS_DIFFER_WITHIN_1KM"
    elif distance <= 5:
        discrepancy = "POINTS_DIFFER_1_TO_5KM"
    else:
        discrepancy = "POINTS_DIFFER_OVER_5KM"

    source_content_status = get_text(
        row, "S51_Source_Content_Review_Status"
    )
    source_strength = get_text(
        row, "S51_Source_Strength_Assessment"
    )
    conflict_description = get_text(
        row, "S51_Coordinate_Conflict_Description"
    )
    researcher_conclusion = get_text(
        row, "S51_Researcher_Evidence_Conclusion"
    )

    if not p_org and not p_url and not p_evidence:
        evidence_state = "PRIMARY_SOURCE_EVIDENCE_MISSING"
    elif not p_evidence:
        evidence_state = "SOURCE_METADATA_PRESENT_CONTENT_EVIDENCE_MISSING"
    elif source_content_status == "IN_PROGRESS":
        evidence_state = "CONTENT_REVIEW_IN_PROGRESS"
    else:
        evidence_state = "EXISTING_EVIDENCE_REQUIRES_RESEARCHER_REVIEW"

    flags = []

    if not p_pair_valid:
        flags.append("PRIMARY_COORDINATE_PAIR_NOT_VALID")
    if not s_pair_valid:
        flags.append("SECONDARY_COORDINATE_PAIR_NOT_VALID")
    if "NOT_INDEPENDENT" in independence.upper():
        flags.append("NO_INDEPENDENT_SOURCE_CORROBORATION")
    if "POTENTIAL_INDEPENDENCE" in independence.upper():
        flags.append("INDEPENDENCE_NOT_YET_PROVEN")
    if scope_comparison != "SCOPE_DESCRIPTIONS_MATCH":
        flags.append("REFERENCE_SCOPE_REQUIRES_REVIEW")
    if distance is not None and distance > 1:
        flags.append("NUMERICAL_COORDINATE_DIFFERENCE_OVER_1KM")
    if not p_datum or not s_datum:
        flags.append("DATUM_OR_CRS_NOT_FULLY_DOCUMENTED")
    if conflict_description:
        flags.append("EXISTING_COORDINATE_REVIEW_DESCRIPTION_PRESENT")
    if not s53_validation:
        flags.append("SCRIPT53_VALIDATION_STATUS_NOT_EXTRACTED")
    elif "PENDING" in s53_validation.upper():
        flags.append("SCRIPT53_VALIDATION_PENDING")

    if not flags:
        flags.append("MANUAL_REVIEW_STILL_REQUIRED")

    return {
        "UNLOCODE": code,
        "Port_Name": port_name,

        "Primary_Source_Organization": p_org,
        "Primary_Source_Title": p_title,
        "Primary_Source_URL": p_url,
        "Primary_Source_Type": p_type,
        "Primary_Source_Evidence": p_evidence,
        "Primary_Latitude": p_lat,
        "Primary_Longitude": p_lon,
        "Primary_Coordinate_Status": p_status,
        "Primary_Coordinate_Scope": p_scope,
        "Primary_Reference_Point": p_reference,
        "Primary_Datum_or_CRS": p_datum,
        "Primary_Claim_Verification": p_claim,

        "Secondary_Source_Organization": s_org,
        "Secondary_Source_Title": s_title,
        "Secondary_Source_URL": s_url,
        "Secondary_Source_Evidence": s_evidence,
        "Secondary_Latitude": s_lat,
        "Secondary_Longitude": s_lon,
        "Secondary_Coordinate_Status": s_status,
        "Secondary_Coordinate_Scope": s_scope,
        "Secondary_Reference_Point": s_reference,
        "Secondary_Datum_or_CRS": s_datum,

        "Coordinate_Distance_KM": (
            round(distance, 4) if distance is not None else None
        ),
        "Coordinate_Discrepancy_Category": discrepancy,
        "Scope_Comparison": scope_comparison,
        "Source_Independence_Assessment": organization_independence,
        "Script53_Independence_Status": s53_independence,
        "Script53_Validation_Status": s53_validation,
        "Script53_Confidence": s53_confidence,
        "Script53_Audit_Flags": s53_flags,
        "Script53_Research_Progress": s53_progress,

        "Source_Content_Review_Status": source_content_status,
        "Source_Strength_Assessment": source_strength,
        "Evidence_Review_State": evidence_state,
        "Existing_Coordinate_Conflict": conflict_description,
        "Existing_Researcher_Conclusion": researcher_conclusion,

        "Review_Priority": get_text(review_row, "Review_Priority"),
        "Researcher_Review_Status": get_text(
            review_row, "Researcher_Review_Status"
        ),
        "Script49_Eligibility_Classification": script49_eligibility,
        "Script49_Recommended_Use": script49_recommended_use,
        "Script49_Eligibility_Blocking_Conditions": script49_blocking_conditions,
        "Regional_Sensitivity_Recommendation_Preserved": regional_sensitivity_recommendation,
        "Script54_Operational_Inclusion_Decision": script54_operational_decision,

        "Researcher_Review_Flags": " | ".join(flags),

        "Coordinate_Approval": "NOT_APPROVED_BY_SCRIPT_56",
        "Operational_Inclusion": "NOT_DECIDED_BY_SCRIPT_56",
        "AIS_Hormuz_Transit_Status": "NOT_ESTABLISHED_BY_SCRIPT_56",
    }


# ============================================================
# BUILD ASSESSMENT
# ============================================================

def build_assessment(inventory, review, reconciliation):
    review_lookup = review.set_index("UNLOCODE").to_dict("index")
    reconciliation_lookup = reconciliation.set_index("UN_LOCODE").to_dict("index")
    records = []

    for _, row in inventory.iterrows():
        code = clean_text(row["UNLOCODE"])
        records.append(
            assess_record(
                row,
                review_lookup[code],
                reconciliation_lookup[code],
            )
        )

    result = pd.DataFrame(records)

    if len(result) != EXPECTED_RECORDS:
        raise AssertionError("Record count changed.")
    if result["UNLOCODE"].duplicated().any():
        raise AssertionError("Duplicate UNLOCODE in output.")
    if set(result["UNLOCODE"]) != set(inventory["UNLOCODE"]):
        raise AssertionError("UNLOCODE coverage changed.")

    if result["Port_Name"].eq("").any():
        missing = result.loc[result["Port_Name"].eq(""), "UNLOCODE"].tolist()
        raise AssertionError(f"Port names were not restored for: {missing}")

    if result["Script49_Eligibility_Classification"].eq("").any():
        missing = result.loc[
            result["Script49_Eligibility_Classification"].eq(""), "UNLOCODE"
        ].tolist()
        raise AssertionError(f"Script 49 eligibility missing for: {missing}")

    if result["Script49_Recommended_Use"].eq("").any():
        missing = result.loc[
            result["Script49_Recommended_Use"].eq(""), "UNLOCODE"
        ].tolist()
        raise AssertionError(f"Script 49 recommended use missing for: {missing}")

    return result


# ============================================================
# SUMMARY
# ============================================================

def build_summary(result):
    summary = []

    def add(metric, value):
        summary.append({"Metric": metric, "Value": value})

    add("Total records assessed", len(result))
    add(
        "Records with port names restored from Script 54",
        int(result["Port_Name"].ne("").sum())
    )
    add(
        "Records with Script 49 eligibility restored from Script 54",
        int(result["Script49_Eligibility_Classification"].ne("").sum())
    )
    add(
        "Records with Script 49 recommended use restored from Script 54",
        int(result["Script49_Recommended_Use"].ne("").sum())
    )
    add(
        "Records with Script 54 regional sensitivity recommendation populated",
        int(result["Regional_Sensitivity_Recommendation_Preserved"].ne("").sum())
    )
    add(
        "Records with valid primary coordinate pairs",
        int(result["Primary_Coordinate_Status"]
            .eq("NUMERIC_PAIR_PRESENT_NOT_APPROVED").sum())
    )
    add(
        "Records with valid secondary coordinate pairs",
        int(result["Secondary_Coordinate_Status"]
            .eq("NUMERIC_PAIR_PRESENT_NOT_APPROVED").sum())
    )
    add(
        "Records with both coordinate pairs",
        int(result["Coordinate_Distance_KM"].notna().sum())
    )
    add(
        "Records with computable coordinate differences over 1 km",
        int(result["Coordinate_Distance_KM"].gt(1).sum())
    )
    add(
        "Records with same named primary and secondary organization",
        int(result["Source_Independence_Assessment"]
            .eq("SAME_NAMED_ORGANIZATION_NOT_INDEPENDENT").sum())
    )
    add(
        "Records with potential organizational independence",
        int(result["Source_Independence_Assessment"]
            .eq("DIFFERENT_NAMED_ORGANIZATIONS_POTENTIAL_INDEPENDENCE").sum())
    )
    add(
        "Records where source independence cannot be assessed",
        int(result["Source_Independence_Assessment"]
            .eq("INDEPENDENCE_NOT_ASSESSABLE").sum())
    )
    add(
        "Records requiring scope review",
        int(result["Scope_Comparison"]
            .ne("SCOPE_DESCRIPTIONS_MATCH").sum())
    )
    add(
        "Records with existing coordinate review descriptions",
        int(result["Existing_Coordinate_Conflict"].ne("").sum())
    )
    add(
        "Records with Script 53 validation status extracted",
        int(result["Script53_Validation_Status"].ne("").sum())
    )
    add(
        "Records with Script 53 validation status pending",
        int(result["Script53_Validation_Status"]
            .str.contains("PENDING", case=False, na=False).sum())
    )
    add("Coordinate approvals made by Script 56", 0)
    add("Operational inclusion decisions made by Script 56", 0)
    add("AIS-confirmed Hormuz transits established by Script 56", 0)
    add("Upstream files modified", "NO")

    return pd.DataFrame(summary)


# ============================================================
# REPORT
# ============================================================

def write_report(result, summary):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("SCRIPT 56: COORDINATE EVIDENCE SOURCE ASSESSMENT\n")
        f.write("=" * 80 + "\n\n")

        f.write("PURPOSE\n")
        f.write("-" * 80 + "\n")
        f.write(
            "This script assesses reviewed source metadata, source "
            "independence, numerical coordinate differences and reference "
            "scope. It does not validate or approve coordinates.\n\n"
        )

        f.write("INPUTS\n")
        f.write("-" * 80 + "\n")
        f.write(f"{INVENTORY_FILE}\n")
        f.write(f"{REVIEW_FILE}\n\n")

        f.write("SUMMARY\n")
        f.write("-" * 80 + "\n")
        f.write(summary.to_string(index=False))
        f.write("\n\n")

        f.write("RECORD-LEVEL REVIEW\n")
        f.write("-" * 80 + "\n")

        for _, row in result.iterrows():
            f.write(f"\n{row['UNLOCODE']} | {row['Port_Name']}\n")
            f.write(
                f"Primary source: {row['Primary_Source_Organization']}\n"
            )
            f.write(
                f"Secondary source: {row['Secondary_Source_Organization']}\n"
            )
            f.write(
                f"Coordinate distance (km): "
                f"{row['Coordinate_Distance_KM']}\n"
            )
            f.write(
                f"Independence: {row['Source_Independence_Assessment']}\n"
            )
            f.write(f"Scope: {row['Scope_Comparison']}\n")
            f.write(
                f"Script 53 validation: "
                f"{row['Script53_Validation_Status']}\n"
            )
            f.write(
                f"Review flags: {row['Researcher_Review_Flags']}\n"
            )

        f.write("\n\nRESEARCH LIMITATIONS\n")
        f.write("-" * 80 + "\n")

        limitations = [
            "A populated coordinate pair is not automatically a validated coordinate.",
            "Different coordinate values may represent different physical reference points.",
            "Sources from the same organization are not independent organizational corroboration.",
            "Different organization names indicate potential organizational independence only; they do not prove independent underlying evidence or coordinate corroboration.",
            "Port names and Script 49 eligibility fields are restored from Script 54 by exact UN/LOCODE matching; missing or unmatched keys cause the script to stop.",
            "Coordinate distance alone cannot establish whether two sources refer to the same facility.",
            "A port reference point, port limit, terminal, berth and anchorage are distinct geographic objects.",
            "Missing datum or CRS information remains a limitation.",
            "Script 56 makes no coordinate approvals or operational inclusion decisions.",
            "No AIS-confirmed Strait of Hormuz transit is inferred.",
        ]

        for number, limitation in enumerate(limitations, 1):
            f.write(f"{number}. {limitation}\n")

        f.write("\nUPSTREAM FILES MODIFIED: NO\n")
        f.write("COORDINATE APPROVALS MADE: 0\n")
        f.write("OPERATIONAL INCLUSION DECISIONS MADE: 0\n")


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 88)
    print("SCRIPT 56: COORDINATE EVIDENCE SOURCE ASSESSMENT")
    print("CORRECTED VERSION 2 — SCRIPT 54 DATA-LINEAGE RESTORATION")
    print("=" * 88)

    inventory, review, reconciliation = load_inputs()

    print("\nINPUT AUDIT")
    print("-" * 72)
    print(
        f"Script 55 inventory: "
        f"{inventory.shape[0]} records x {inventory.shape[1]} columns"
    )
    print(
        f"Script 55 review register: "
        f"{review.shape[0]} records x {review.shape[1]} columns"
    )
    print(
        f"Script 54 reconciliation: "
        f"{reconciliation.shape[0]} records x {reconciliation.shape[1]} columns"
    )

    result = build_assessment(inventory, review, reconciliation)
    summary = build_summary(result)

    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    result.to_csv(OUTPUT_FILE, index=False)
    summary.to_csv(SUMMARY_FILE, index=False)
    write_report(result, summary)

    print("\nVALIDATION")
    print("-" * 72)
    print("19 records retained: PASS")
    print("UN/LOCODE uniqueness: PASS")
    print("UN/LOCODE coverage across Scripts 54 and 55: PASS")
    print("Port names restored from Script 54: PASS")
    print("Script 49 eligibility and recommended use restored from Script 54: PASS")
    print("Script 54/55 join cardinality: one-to-one, 19/19: PASS")
    print("Reviewed source organization fields used: PASS")
    print("Organization-name independence kept separate from Script 53 status: PASS")
    print("Script 53 embedded quality fields extracted where present: PASS")
    print("Coordinate distances calculated only for valid pairs: PASS")
    print("No coordinate approvals created: PASS")
    print("No operational inclusion decisions created: PASS")
    print("Upstream files modified: NO")

    print("\nSUMMARY")
    print("-" * 72)
    print(summary.to_string(index=False))

    print("\nOUTPUT FILES")
    print("-" * 72)
    print(f"Assessment: {OUTPUT_FILE.relative_to(ROOT)}")
    print(f"Summary: {SUMMARY_FILE.relative_to(ROOT)}")
    print(f"Report: {REPORT_FILE.relative_to(ROOT)}")

    print("\nSCRIPT 56 COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()
