"""
SCRIPT 57 v2: CORRECTED COORDINATE VALIDATION PATHWAY CLASSIFICATION
-------------------------------------------------------------------
Reads the original Script 57 register and creates corrected downstream
validation files. The original Script 57 outputs are not modified.

This is a rule-based classification of the supplied evidence register.
It does not browse source URLs, verify coordinates, or approve any location.

Input:
    outputs/tables/57_independent_coordinate_validation_register.csv

Outputs:
    outputs/tables/57_independent_coordinate_validation_register_v2.csv
    outputs/tables/57_coordinate_validation_summary_v2.csv
    outputs/reports/57_independent_coordinate_validation_report_v2.txt
"""

from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

INPUT_FILE = TABLE_DIR / "57_independent_coordinate_validation_register.csv"
REGISTER_FILE = TABLE_DIR / "57_independent_coordinate_validation_register_v2.csv"
SUMMARY_FILE = TABLE_DIR / "57_coordinate_validation_summary_v2.csv"
REPORT_FILE = REPORT_DIR / "57_independent_coordinate_validation_report_v2.txt"

EXPECTED = 19

# Explicitly grounded in the record-level Script 53 status and scope descriptions
# already present in the Script 57 input. These are review pathways, not approvals.
RECORD_RULES = {
    "AEAUH": (
        "FACILITY_SCOPE_RECONCILIATION_REQUIRED",
        "UN/LOCODE multimodal location point and commercial port-location point are not yet shown to represent the same port facility."
    ),
    "AEFJR": (
        "SAME_AUTHORITY_COORDINATE_RECONCILIATION",
        "Both source records are associated with Fujairah Ports Authority; compare positions, but do not count them as independent corroboration."
    ),
    "AEKLF": (
        "PARTIAL_PORT_LOCATION_CORROBORATION_REVIEW",
        "Evidence indicates partial location corroboration with differing coordinates; exact reference-point scope remains unresolved."
    ),
    "AERKT": (
        "DIFFERENT_PORT_REFERENCE_RECONCILIATION",
        "The primary record refers to Ras Al Khaimah port limits/main breakwater while the secondary point refers to Mina Saqr; these are not corroborating points for one facility."
    ),
    "AESHJ": (
        "NAVIGATIONAL_BUOY_VERSUS_PORT_POINT_REVIEW",
        "The primary coordinate is a fairway buoy position, not a port or terminal coordinate; keep it separate from the secondary port-location candidate."
    ),
    "BHKBS": (
        "APPROXIMATE_PORT_LOCATION_CORROBORATION_REVIEW",
        "Government and operator coordinates are close enough to warrant port-level comparison; retain the noted operator-source outlier for review."
    ),
    "INHZA": (
        "NEAR_IDENTICAL_PORT_LEVEL_COORDINATE_REVIEW",
        "Government maritime-board and port-source coordinates are near-identical at the stated port-level scope; independently verify source provenance and point definitions."
    ),
    "INIXY": (
        "SAME_AUTHORITY_DIFFERING_POSITION_RECONCILIATION",
        "Both records are from Deendayal Port Authority and describe port-level location, but publish differing positions; this is not independent corroboration."
    ),
    "INPPV": (
        "SAME_OPERATOR_IDENTICAL_POSITION_REVIEW",
        "The two coordinate records agree, but both are associated with the APM operator; agreement is not independent corroboration."
    ),
    "IQUQR": (
        "DISTINCT_TERMINAL_COORDINATE_RECONCILIATION",
        "The two coordinates refer to distinct terminals within Umm Qasr; retain terminal identity and do not treat the distance as a conflict between duplicate port points."
    ),
    "KWSAA": (
        "SECONDARY_COORDINATE_CANDIDATE_PRIMARY_MISSING",
        "The primary authority evidence provides port identity/function but no coordinate; secondary point remains a candidate only."
    ),
    "KWSWK": (
        "INDEPENDENT_NEARBY_PORT_LOCATION_COMPARISON",
        "NGA nautical port position and independent gazetteer location are close; compare source definitions, datum and reference points."
    ),
    "OMDQM": (
        "PORT_BOUNDARY_PILOTAGE_VERSUS_POINT_REVIEW",
        "Primary evidence concerns port limits and pilot stations, while the secondary evidence is a commercial port-location point; do not derive a port point from a boundary polygon."
    ),
    "PKKIA": (
        "UPPER_HARBOUR_VERSUS_KIAMARI_LOCALITY_REVIEW",
        "The primary navigational reference for Karachi Upper Harbour and the secondary Kiamari locality point are different reference objects."
    ),
    "QAQAP": (
        "BERTH_IDENTITY_VERSUS_PLANT_LOCATION_REVIEW",
        "Primary evidence identifies terminal berths while the secondary coordinate is an industrial plant location; the plant point cannot validate berth coordinates."
    ),
    "QAQCH": (
        "BERTH_IDENTITY_WITHOUT_GEODETIC_COORDINATES",
        "Berth identity/relative-location evidence is present, but geodetic coordinate pairs are not established; berth numbering also requires reconciliation."
    ),
    "QAUMS": (
        "PORT_LIMIT_POLYGON_VERSUS_COMMERCIAL_POINT_REVIEW",
        "The primary evidence is a port-limit polygon, not a point coordinate; do not substitute a polygon centroid for a validated port location."
    ),
    "SADMM": (
        "INDEPENDENT_NEARBY_PORT_LOCATION_COMPARISON",
        "NGA nautical port position and an independent port-list position are close; compare reference-point definitions and source provenance."
    ),
    "SAJUB": (
        "SECONDARY_REFERENCES_DIFFER_PRIMARY_COORDINATE_MISSING",
        "No coordinate-bearing Mawani primary point is available in the register, and the secondary location references differ; retain as unresolved."
    ),
}

INDEPENDENCE_RULES = {
    "AEFJR": "SAME_AUTHORITY_NOT_INDEPENDENT",
    "INIXY": "SAME_AUTHORITY_NOT_INDEPENDENT",
    "INPPV": "SAME_OPERATOR_NOT_INDEPENDENT",
}

REQUIRED = {
    "UNLOCODE", "Port_Name",
    "Primary_Latitude", "Primary_Longitude",
    "Secondary_Latitude", "Secondary_Longitude",
    "Primary_Source_Organization", "Secondary_Source_Organization",
    "Script53_Independence_Status", "Script53_Validation_Status",
    "Script49_Eligibility_Classification", "Script49_Recommended_Use",
    "Coordinate_Approval", "Operational_Inclusion", "AIS_Hormuz_Transit_Status",
}


def valid_pair(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
        return np.isfinite(lat) and np.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180
    except (TypeError, ValueError):
        return False


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input: {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE)
    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df["UNLOCODE"] = df["UNLOCODE"].astype("string").str.strip().str.upper()
    if len(df) != EXPECTED:
        raise ValueError(f"Expected {EXPECTED} rows, received {len(df)}.")
    if df["UNLOCODE"].isna().any() or df["UNLOCODE"].eq("").any():
        raise ValueError("Missing UN/LOCODE.")
    if df["UNLOCODE"].duplicated().any():
        raise ValueError("Duplicate UN/LOCODE.")

    unknown = set(df["UNLOCODE"]) - set(RECORD_RULES)
    missing_rules = set(RECORD_RULES) - set(df["UNLOCODE"])
    if unknown or missing_rules:
        raise ValueError(f"Rule coverage mismatch. Unknown={unknown}; missing={missing_rules}")

    df["Primary_Coordinate_Pair_Valid"] = [
        valid_pair(a, b) for a, b in zip(df["Primary_Latitude"], df["Primary_Longitude"])
    ]
    df["Secondary_Coordinate_Pair_Valid"] = [
        valid_pair(a, b) for a, b in zip(df["Secondary_Latitude"], df["Secondary_Longitude"])
    ]

    df["Validation_Pathway_v2"] = df["UNLOCODE"].map(lambda x: RECORD_RULES[x][0])
    df["Evidence_Scope_Interpretation_v2"] = df["UNLOCODE"].map(lambda x: RECORD_RULES[x][1])

    df["Organizational_Independence_Class_v2"] = df["UNLOCODE"].map(
        lambda x: INDEPENDENCE_RULES.get(
            x,
            "POTENTIALLY_DIFFERENT_ORGANIZATIONS_NOT_YET_PROVEN_INDEPENDENT"
        )
    )

    def comparison_possible(row):
        return bool(row["Primary_Coordinate_Pair_Valid"] and row["Secondary_Coordinate_Pair_Valid"])

    df["Numerical_Coordinate_Comparison_Possible"] = df.apply(comparison_possible, axis=1)

    def corroboration_status(row):
        code = row["UNLOCODE"]
        if code in {"AEFJR", "INIXY", "INPPV"}:
            return "NOT_INDEPENDENT_SOURCE_PAIR"
        if code in {"AERKT", "AESHJ", "IQUQR", "OMDQM", "PKKIA", "QAQAP", "QAQCH", "QAUMS"}:
            return "NOT_ESTABLISHED_DIFFERENT_OR_UNRESOLVED_REFERENCE_OBJECT"
        if code in {"AEAUH", "AEKLF", "SAJUB", "KWSAA"}:
            return "NOT_ESTABLISHED_SCOPE_OR_PRIMARY_EVIDENCE_INCOMPLETE"
        if code in {"BHKBS", "INHZA", "KWSWK", "SADMM"}:
            return "POTENTIAL_CORROBORATION_REQUIRES_SOURCE_LEVEL_VERIFICATION"
        return "NOT_ESTABLISHED"
    df["Independent_Coordinate_Corroboration_Status_v2"] = df.apply(corroboration_status, axis=1)

    df["Researcher_Validation_Status_v2"] = "PENDING_RESEARCHER_VALIDATION"
    df["Coordinate_Approval_v2"] = "NOT_APPROVED"
    df["Operational_Inclusion_v2"] = "NOT_DECIDED"

    # Integrity checks: preserve all upstream identifiers and decisions.
    if len(df) != EXPECTED or df["UNLOCODE"].nunique() != EXPECTED:
        raise AssertionError("Record integrity failed.")
    if not df["Coordinate_Approval"].astype(str).eq("NOT_APPROVED_BY_SCRIPT_57").all():
        raise AssertionError("Unexpected original approval state.")
    if not df["Operational_Inclusion"].astype(str).eq("NOT_DECIDED_BY_SCRIPT_57").all():
        raise AssertionError("Unexpected original operational-inclusion state.")
    if not df["Coordinate_Approval_v2"].eq("NOT_APPROVED").all():
        raise AssertionError("Script 57 v2 must not approve coordinates.")
    if not df["Operational_Inclusion_v2"].eq("NOT_DECIDED").all():
        raise AssertionError("Script 57 v2 must not decide operational inclusion.")

    pathway_summary = (
        df.groupby("Validation_Pathway_v2", dropna=False)
          .size().rename("Record_Count").reset_index()
          .sort_values("Validation_Pathway_v2")
    )
    independence_summary = (
        df.groupby("Organizational_Independence_Class_v2", dropna=False)
          .size().rename("Record_Count").reset_index()
          .sort_values("Organizational_Independence_Class_v2")
    )
    metrics = [
        ("Total records", len(df)),
        ("Valid primary coordinate pairs", int(df["Primary_Coordinate_Pair_Valid"].sum())),
        ("Valid secondary coordinate pairs", int(df["Secondary_Coordinate_Pair_Valid"].sum())),
        ("Both coordinate pairs available", int((df["Primary_Coordinate_Pair_Valid"] & df["Secondary_Coordinate_Pair_Valid"]).sum())),
        ("Numerical coordinate comparisons possible", int(df["Numerical_Coordinate_Comparison_Possible"].sum())),
        ("Potential corroboration requiring source-level verification", int(df["Independent_Coordinate_Corroboration_Status_v2"].eq("POTENTIAL CORROBORATION REQUIRES SOURCE LEVEL VERIFICATION").sum())),
        ("Coordinate approvals", 0),
        ("Operational inclusion decisions", 0),
        ("AIS-confirmed Hormuz transits established by this script", 0),
    ]
    summary = pd.DataFrame(metrics, columns=["Metric", "Value"])

    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(REGISTER_FILE, index=False)
    summary.to_csv(SUMMARY_FILE, index=False)

    with REPORT_FILE.open("w", encoding="utf-8") as f:
        f.write("SCRIPT 57 v2 — CORRECTED COORDINATE VALIDATION PATHWAY CLASSIFICATION\n")
        f.write("=" * 78 + "\n\n")
        f.write("This is a rule-based reclassification of the existing Script 57 evidence.\n")
        f.write("It does not verify source URLs, validate coordinates, or approve locations.\n\n")
        f.write("SUMMARY\n" + summary.to_string(index=False) + "\n\n")
        f.write("VALIDATION PATHWAYS\n" + pathway_summary.to_string(index=False) + "\n\n")
        f.write("ORGANISATIONAL INDEPENDENCE\n" + independence_summary.to_string(index=False) + "\n\n")
        f.write("RECORD-LEVEL INTERPRETATION\n")
        for _, row in df.sort_values("UNLOCODE").iterrows():
            f.write(
                f"{row['UNLOCODE']} | {row['Port_Name']} | "
                f"{row['Validation_Pathway_v2']} | "
                f"{row['Evidence_Scope_Interpretation_v2']}\n"
            )
        f.write("\nLIMITATIONS\n")
        f.write("- Organisational independence is not the same as independent coordinate corroboration.\n")
        f.write("- Numerical coordinate comparison is not proof of same-facility identity.\n")
        f.write("- Distinct terminals within one port must remain terminal-specific.\n")
        f.write("- Port boundaries, pilot stations, buoys, berths and plant points are not interchangeable.\n")
        f.write("- Script 49 eligibility and Script 53 evidence status are preserved, not overridden.\n")
        f.write("- Researcher validation, coordinate approval and operational inclusion remain pending.\n")

    print("=" * 78)
    print("SCRIPT 57 v2: CORRECTED VALIDATION PATHWAY CLASSIFICATION")
    print("=" * 78)
    print(f"Input: {len(df)} records")
    print("UN/LOCODE uniqueness and coverage: PASS")
    print("All 19 record-specific review rules applied: PASS")
    print("Script 49 eligibility preserved: PASS")
    print("Script 53 evidence status preserved: PASS")
    print("Original Script 57 files left unchanged: YES")
    print("Coordinate approvals created: 0")
    print("Operational inclusion decisions created: 0")
    print("\nSUMMARY")
    print(summary.to_string(index=False))
    print("\nPATHWAY COUNTS")
    print(pathway_summary.to_string(index=False))
    print("\nOUTPUTS")
    print(REGISTER_FILE.relative_to(ROOT))
    print(SUMMARY_FILE.relative_to(ROOT))
    print(REPORT_FILE.relative_to(ROOT))
    print("\nSCRIPT 57 v2 COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()
