"""
SCRIPT 49: FINAL PORT EVIDENCE AND OPERATIONAL ELIGIBILITY ASSESSMENT

Purpose
-------
Create a conservative, evidence-led port eligibility assessment by joining:
- Script 38: port identity and operational-inclusion register
- Script 39: coordinate-validation register
- Script 41/47: consolidated source-content review register
- Script 21: observed port-network metrics
- Script 48: consolidated-register quality-audit outputs

This script is READ-ONLY with respect to all input files.

Important methodological safeguards
------------------------------------
1. A Script 48 PASSED result establishes structural consistency only.
2. A port identity claim does not prove that the observed calls map to a
   specific terminal/facility.
3. A port call does not prove Strait of Hormuz transit.
4. Pending coordinates or pending operational decisions cannot be treated
   as approved.
5. Regional ports outside the Persian Gulf screening area are not silently
   promoted to core Persian Gulf nodes.
6. This script produces recommendations for researcher review, not final
   researcher approval.

Outputs
-------
outputs/tables/49_port_eligibility_assessment.csv
outputs/tables/49_port_eligibility_summary.csv
outputs/reports/49_port_eligibility_assessment_report.txt
"""

import csv
from pathlib import Path
from datetime import datetime
from collections import Counter


# ============================================================
# 1. PATHS
# ============================================================

TABLES_DIR = Path("outputs/tables")
REPORTS_DIR = Path("outputs/reports")

FILES = {
    "identity": TABLES_DIR / "38_port_evidence_validation_register.csv",
    "coordinates": TABLES_DIR / "39_port_coordinate_validation_register.csv",
    "source_review": TABLES_DIR / (
        "41_manual_source_content_verification_register_consolidated.csv"
    ),
    "network": TABLES_DIR / "21_port_network_metrics.csv",
    "audit": TABLES_DIR / "48_consolidated_register_quality_audit.csv",
    "record_summary": TABLES_DIR / "48_consolidated_register_record_summary.csv",
}

OUTPUT_FILE = TABLES_DIR / "49_port_eligibility_assessment.csv"
SUMMARY_FILE = TABLES_DIR / "49_port_eligibility_summary.csv"
REPORT_FILE = REPORTS_DIR / "49_port_eligibility_assessment_report.txt"


# ============================================================
# 2. CONFIGURATION
# ============================================================

# These are explicit, conservative approval states. If the upstream
# register uses different labels, the script will retain a pending status
# rather than infer approval.
APPROVED_COORDINATE_STATUSES = {
    "VALIDATED",
    "VERIFIED",
    "APPROVED",
    "ACCEPTED",
    "VALIDATED_PORT_COORDINATE",
    "VALIDATED_TERMINAL_COORDINATE",
}

APPROVED_OPERATIONAL_STATUSES = {
    "APPROVED",
    "INCLUDE",
    "INCLUDED",
    "APPROVED_FOR_CORE_SIMULATION",
    "APPROVED_FOR_REGIONAL_SIMULATION",
}

VERIFIED_IDENTITY_STATUSES = {
    "VERIFIED_PORT_IDENTITY",
    "VERIFIED_CODE_IDENTITY",
    "VERIFIED",
    "APPROVED",
}

PERSIAN_GULF_LABELS = {
    "PERSIAN_GULF",
    "PERSIAN_GULF_PORT_CANDIDATE",
    "PERSIAN_GULF_CONNECTED",
}

REGIONAL_LABELS = {
    "GULF_OF_OMAN",
    "GULF_OF_OMAN_OUTSIDE_GULF_SCREENING",
    "REGIONAL_APPROACH_PORT",
    "ARABIAN_SEA",
    "WIDER_REGIONAL",
    "WIDER_REGIONAL_ALTERNATIVE",
}

OUTPUT_FIELDS = [
    "UN_LOCODE",
    "Port_Name",
    "Validated_Port_Name",
    "Validated_Facility_Name",
    "Country_Code",
    "Geographic_Region",
    "Preliminary_Geographic_Role",
    "Research_Relevance_Screen",
    "Network_Match_Status",
    "Observed_Call_Count",
    "Observed_Vessel_Count",
    "Identity_Validation_Status",
    "Source_Content_Review_Status",
    "Researcher_Review_Status",
    "Coordinate_Validation_Status",
    "Port_Coordinate_Type",
    "Terminal_Coordinate_Type",
    "Port_Coordinate_Present",
    "Terminal_Coordinate_Present",
    "Operational_Inclusion_Decision",
    "AIS_or_Transit_Evidence_Status",
    "Identity_Verified",
    "Coordinates_Approved",
    "Operational_Approval",
    "Network_Observed",
    "Geographic_Class",
    "Eligibility_Classification",
    "Recommended_Use",
    "Blocking_Conditions",
    "Researcher_Action_Required",
    "Assessment_Basis",
]


# ============================================================
# 3. HELPERS
# ============================================================

def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def norm(value):
    return clean(value).upper().replace(" ", "_")


def read_csv(path, required=True):
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Required input file not found: {path}")
        return [], []

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV header missing: {path}")
        return list(reader.fieldnames), list(reader)


def index_records(rows, label, code_field="UN_LOCODE"):
    """Index records using the code field actually present in that input."""
    result = {}
    for row_number, row in enumerate(rows, start=2):
        code = clean(row.get(code_field, ""))
        if not code:
            raise ValueError(
                f"Blank {code_field} in {label}, CSV row {row_number}"
            )
        if code in result:
            raise ValueError(f"Duplicate UN_LOCODE {code} in {label}")
        result[code] = row
    return result


def first_value(*values):
    for value in values:
        value = clean(value)
        if value:
            return value
    return ""


def has_value(value):
    return clean(value).upper() not in {"", "NA", "N/A", "NONE", "NAN", "NULL"}


def truthy_text(value):
    return norm(value) in {"YES", "TRUE", "1", "Y", "PRESENT"}


def coordinate_present(row, lat_field, lon_field):
    return has_value(row.get(lat_field, "")) and has_value(row.get(lon_field, ""))


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def choose_geographic_class(region, role, relevance):
    combined = " ".join([norm(region), norm(role), norm(relevance)])

    if any(label in combined for label in PERSIAN_GULF_LABELS):
        return "PERSIAN_GULF_SCREENING_CANDIDATE"

    if any(label in combined for label in REGIONAL_LABELS):
        return "REGIONAL_OR_APPROACH_AREA"

    if "ARABIAN_SEA" in combined:
        return "REGIONAL_OR_APPROACH_AREA"

    if combined.strip():
        return "GEOGRAPHIC_CLASS_REQUIRES_REVIEW"

    return "GEOGRAPHIC_CLASS_UNKNOWN"


def main():
    print("\n" + "=" * 76)
    print("SCRIPT 49: FINAL PORT EVIDENCE AND OPERATIONAL ELIGIBILITY ASSESSMENT")
    print("=" * 76)

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------
    # Load input registers
    # --------------------------------------------------------

    loaded = {}
    indexes = {}

    for name, path in FILES.items():
        fields, rows = read_csv(path)
        loaded[name] = {"fields": fields, "rows": rows}
        if name in {"identity", "coordinates", "source_review", "network"}:
            indexes[name] = index_records(
                rows, name, code_field=("UNLOCODE" if name == "network" else "UN_LOCODE")
            )

        print(f"{name}: {len(rows)} records, {len(fields)} columns")

    # Script 48 output should contain zero issue rows for a clean audit.
    audit_rows = loaded["audit"]["rows"]
    record_qa_rows = loaded["record_summary"]["rows"]

    # --------------------------------------------------------
    # Validate cross-register coverage
    # --------------------------------------------------------

    base_codes = set(indexes["identity"])
    coverage_issues = []

    for name in ("coordinates", "source_review"):
        other_codes = set(indexes[name])
        if other_codes != base_codes:
            coverage_issues.append(
                f"{name}: missing={sorted(base_codes - other_codes)}, "
                f"extra={sorted(other_codes - base_codes)}"
            )

    if coverage_issues:
        raise ValueError(
            "Port register coverage mismatch. Assessment stopped:\n"
            + "\n".join(coverage_issues)
        )

    # Network is expected to be a subset; unmatched ports are retained.
    # Script 48 must have no issue rows for this assessment run.
    if audit_rows:
        print(
            "\nWARNING: Script 48 audit CSV contains "
            f"{len(audit_rows)} issue rows."
        )
        structural_audit_passed = False
    else:
        structural_audit_passed = True

    qa_by_code = {
        clean(row.get("UN_LOCODE", "")): row
        for row in record_qa_rows
        if clean(row.get("UN_LOCODE", ""))
    }

    results = []

    # --------------------------------------------------------
    # Assess each port
    # --------------------------------------------------------

    for code in sorted(base_codes):
        identity = indexes["identity"][code]
        coordinates = indexes["coordinates"][code]
        source = indexes["source_review"][code]
        network = indexes["network"].get(code, {})
        qa = qa_by_code.get(code, {})

        port_name = first_value(
            identity.get("Port_Name_in_Master"),
            source.get("Port_Name_in_Master"),
            identity.get("Researcher_Validated_Port_Name"),
        )

        validated_port_name = first_value(
            source.get("Researcher_Validated_Port_Name"),
            identity.get("Researcher_Validated_Port_Name"),
        )

        facility_name = first_value(
            source.get("Researcher_Validated_Facility_Name"),
            identity.get("Researcher_Validated_Facility_Name"),
        )

        country_code = first_value(
            identity.get("Country_Code"),
            source.get("Country_Code"),
        )

        region = first_value(
            source.get("Validated_Geographic_Region"),
            identity.get("Preliminary_Geographic_Role"),
            source.get("Preliminary_Geographic_Role"),
        )

        preliminary_role = first_value(
            identity.get("Preliminary_Geographic_Role"),
            source.get("Preliminary_Geographic_Role"),
        )

        relevance = first_value(
            identity.get("Research_Relevance_Screen"),
            source.get("Research_Relevance_Screen"),
        )

        identity_status = first_value(
            source.get("Identity_Validation_Status"),
            identity.get("Identity_Validation_Status"),
        )

        source_status = clean(source.get("Source_Content_Review_Status", ""))
        researcher_status = clean(source.get("Researcher_Review_Status", ""))

        coordinate_status = clean(
            coordinates.get("Coordinate_Validation_Status", "")
        )

        operational_status = first_value(
            source.get("Operational_Inclusion_Decision"),
            identity.get("Operational_Inclusion_Decision"),
        )

        transit_status = first_value(
            source.get("AIS_or_Transit_Evidence_Status"),
            identity.get("AIS_or_Transit_Evidence_Status"),
        )

        network_present = code in indexes["network"]
        network_match_status = (
            "PRESENT_IN_SCRIPT21_NETWORK"
            if network_present
            else "NOT_PRESENT_IN_SCRIPT21_NETWORK"
        )

        observed_calls = first_value(
            network.get("Observed_Call_Count"),
            identity.get("Observed_Call_Count"),
            source.get("Observed_Call_Count"),
        )

        observed_vessels = first_value(
            network.get("Observed_Vessel_Count"),
            identity.get("Observed_Vessel_Count"),
            source.get("Observed_Vessel_Count"),
        )

        port_coordinate = coordinate_present(
            coordinates,
            "Validated_Port_Latitude",
            "Validated_Port_Longitude",
        )

        terminal_coordinate = coordinate_present(
            coordinates,
            "Validated_Terminal_Latitude",
            "Validated_Terminal_Longitude",
        )

        port_coordinate_type = clean(
            coordinates.get("Port_Coordinate_Type", "")
        )
        terminal_coordinate_type = clean(
            coordinates.get("Terminal_Coordinate_Type", "")
        )

        identity_verified = norm(identity_status) in VERIFIED_IDENTITY_STATUSES
        coordinates_approved = norm(coordinate_status) in APPROVED_COORDINATE_STATUSES
        operational_approved = norm(operational_status) in APPROVED_OPERATIONAL_STATUSES

        geographic_class = choose_geographic_class(
            region, preliminary_role, relevance
        )

        blockers = []

        if not identity_verified:
            blockers.append("PORT_IDENTITY_NOT_FULLY_VERIFIED")

        if norm(source_status) in {"", "NOT_REVIEWED", "IN_PROGRESS"}:
            blockers.append("SOURCE_CONTENT_REVIEW_NOT_CLOSED")

        if norm(researcher_status) in {
            "", "NOT_REVIEWED", "AI_ASSISTED_REVIEW_PENDING_RESEARCHER_CONFIRMATION",
            "PRELIMINARY_DESK_REVIEW_COMPLETED_RESEARCHER_SIGNOFF_REQUIRED",
        }:
            blockers.append("RESEARCHER_SIGNOFF_PENDING")

        if not coordinates_approved:
            blockers.append("COORDINATE_VALIDATION_NOT_APPROVED")

        if not port_coordinate:
            blockers.append("VALIDATED_PORT_COORDINATE_NOT_POPULATED")

        if not operational_approved:
            blockers.append("OPERATIONAL_INCLUSION_NOT_APPROVED")

        if not network_present:
            blockers.append("NOT_PRESENT_IN_OBSERVED_SCRIPT21_NETWORK")

        # Never interpret a port call as proof of Strait transit.
        if norm(transit_status) not in {
            "AIS_TRANSIT_CONFIRMED",
            "CONFIRMED_AIS_TRANSIT",
            "TRANSIT_CONFIRMED",
        }:
            blockers.append("NO_CONFIRMED_AIS_TRANSIT_EVIDENCE")

        # Conservative classification hierarchy.
        if (
            structural_audit_passed
            and identity_verified
            and coordinates_approved
            and port_coordinate
            and operational_approved
            and network_present
            and geographic_class == "PERSIAN_GULF_SCREENING_CANDIDATE"
            and norm(source_status) not in {"", "NOT_REVIEWED", "IN_PROGRESS"}
            and norm(researcher_status) in {
                "RESEARCHER_VERIFIED",
                "RESEARCHER_SIGNED_OFF",
                "SIGNED_OFF",
                "COMPLETED",
            }
        ):
            classification = "CORE_SIMULATION_ELIGIBLE_PENDING_FINAL_METHOD_REVIEW"
            recommended_use = "CORE_SIMULATION_CANDIDATE"
            action = "Researcher to confirm final model-boundary and facility mapping."

        elif (
            identity_verified
            and geographic_class in {
                "REGIONAL_OR_APPROACH_AREA",
                "PERSIAN_GULF_SCREENING_CANDIDATE",
            }
        ):
            classification = "REGIONAL_OR_SENSITIVITY_CANDIDATE_PENDING_APPROVAL"
            recommended_use = "REGIONAL_OR_SENSITIVITY_ANALYSIS_ONLY"
            action = (
                "Resolve coordinate, facility attribution and operational "
                "approval before simulation inclusion."
            )

        elif network_present and not identity_verified:
            classification = "DESCRIPTIVE_REFERENCE_ONLY_PENDING_IDENTITY_REVIEW"
            recommended_use = "DESCRIPTIVE_NETWORK_CONTEXT_ONLY"
            action = "Resolve port/code/facility identity before model inclusion."

        elif not network_present:
            classification = "DESCRIPTIVE_REFERENCE_ONLY_NOT_IN_OBSERVED_NETWORK"
            recommended_use = "CONTEXT_ONLY_UNLESS_NEW_MOVEMENT_EVIDENCE"
            action = (
                "Do not add as an observed network node without evidence "
                "linking the source record to the facility and movement."
            )

        else:
            classification = "EXCLUDE_FROM_SIMULATION_PENDING_EVIDENCE"
            recommended_use = "DO_NOT_INCLUDE_IN_CURRENT_SIMULATION"
            action = "Resolve identity, geographic role and evidence gaps."

        assessment_basis = (
            "Classification is a conservative rule-based recommendation "
            "derived from Scripts 21, 38, 39, 41 and 48. It is not a "
            "researcher approval and does not establish Strait transit."
        )

        results.append({
            "UN_LOCODE": code,
            "Port_Name": port_name,
            "Validated_Port_Name": validated_port_name,
            "Validated_Facility_Name": facility_name,
            "Country_Code": country_code,
            "Geographic_Region": region,
            "Preliminary_Geographic_Role": preliminary_role,
            "Research_Relevance_Screen": relevance,
            "Network_Match_Status": network_match_status,
            "Observed_Call_Count": observed_calls,
            "Observed_Vessel_Count": observed_vessels,
            "Identity_Validation_Status": identity_status,
            "Source_Content_Review_Status": source_status,
            "Researcher_Review_Status": researcher_status,
            "Coordinate_Validation_Status": coordinate_status,
            "Port_Coordinate_Type": port_coordinate_type,
            "Terminal_Coordinate_Type": terminal_coordinate_type,
            "Port_Coordinate_Present": "YES" if port_coordinate else "NO",
            "Terminal_Coordinate_Present": "YES" if terminal_coordinate else "NO",
            "Operational_Inclusion_Decision": operational_status,
            "AIS_or_Transit_Evidence_Status": transit_status,
            "Identity_Verified": "YES" if identity_verified else "NO",
            "Coordinates_Approved": "YES" if coordinates_approved else "NO",
            "Operational_Approval": "YES" if operational_approved else "NO",
            "Network_Observed": "YES" if network_present else "NO",
            "Geographic_Class": geographic_class,
            "Eligibility_Classification": classification,
            "Recommended_Use": recommended_use,
            "Blocking_Conditions": ";".join(blockers),
            "Researcher_Action_Required": action,
            "Assessment_Basis": assessment_basis,
        })

    # --------------------------------------------------------
    # Summaries
    # --------------------------------------------------------

    class_counts = Counter(
        row["Eligibility_Classification"] for row in results
    )
    use_counts = Counter(row["Recommended_Use"] for row in results)
    region_counts = Counter(row["Geographic_Class"] for row in results)

    summary_rows = []
    for category, count in sorted(class_counts.items()):
        summary_rows.append({
            "Summary_Type": "ELIGIBILITY_CLASSIFICATION",
            "Category": category,
            "Port_Count": count,
            "Interpretation": (
                "Rule-based recommendation only; researcher approval required."
            ),
        })

    for category, count in sorted(use_counts.items()):
        summary_rows.append({
            "Summary_Type": "RECOMMENDED_USE",
            "Category": category,
            "Port_Count": count,
            "Interpretation": "Proposed use based on current evidence and safeguards.",
        })

    for category, count in sorted(region_counts.items()):
        summary_rows.append({
            "Summary_Type": "GEOGRAPHIC_CLASS",
            "Category": category,
            "Port_Count": count,
            "Interpretation": "Screening classification; not proof of vessel transit.",
        })

    write_csv(OUTPUT_FILE, OUTPUT_FIELDS, results)

    write_csv(
        SUMMARY_FILE,
        ["Summary_Type", "Category", "Port_Count", "Interpretation"],
        summary_rows,
    )

    # --------------------------------------------------------
    # Report
    # --------------------------------------------------------

    lines = [
        "SCRIPT 49: FINAL PORT EVIDENCE AND OPERATIONAL ELIGIBILITY ASSESSMENT",
        "=" * 76,
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Ports assessed: {len(results)}",
        f"Script 48 structural audit clean: {'YES' if structural_audit_passed else 'NO'}",
        "",
        "ELIGIBILITY CLASSIFICATION COUNTS",
    ]

    for category, count in sorted(class_counts.items()):
        lines.append(f"{category}: {count}")

    lines.extend(["", "RECOMMENDED USE COUNTS"])
    for category, count in sorted(use_counts.items()):
        lines.append(f"{category}: {count}")

    lines.extend([
        "",
        "IMPORTANT INTERPRETATION",
        "This assessment is a conservative, rule-based recommendation.",
        "It does not approve ports for operational inclusion.",
        "Pending coordinates and pending operational decisions remain blockers.",
        "Port-call records do not prove Strait of Hormuz transit.",
        "No AIS-confirmed transit is inferred by this script.",
        "Regional/sensitivity candidates must remain distinct from core",
        "Persian Gulf nodes until the research boundary and evidence support inclusion.",
        "",
        "INPUT FILES",
    ])

    for name, path in FILES.items():
        lines.append(f"{name}: {path}")

    lines.extend([
        "",
        "OUTPUT FILES",
        str(OUTPUT_FILE),
        str(SUMMARY_FILE),
        str(REPORT_FILE),
    ])

    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n" + "=" * 76)
    print("SCRIPT 49 COMPLETED")
    print("=" * 76)
    print("Ports assessed:", len(results))
    print("Script 48 audit clean:", structural_audit_passed)
    print("\nEligibility classifications:")
    for category, count in sorted(class_counts.items()):
        print(f"  {category}: {count}")

    print("\nRecommended use:")
    for category, count in sorted(use_counts.items()):
        print(f"  {category}: {count}")

    print("\nOUTPUTS")
    print(OUTPUT_FILE)
    print(SUMMARY_FILE)
    print(REPORT_FILE)
    print("\nInput registers were not modified.")


if __name__ == "__main__":
    main()
