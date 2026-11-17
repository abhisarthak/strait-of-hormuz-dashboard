"""
SCRIPT 50: PORT COORDINATE RESEARCH AND VALIDATION WORKFLOW

Purpose
-------
Create a controlled, researcher-facing coordinate research register for the
19 candidate port/location records. The workflow consolidates existing
coordinate fields from Script 39 with identity/source context from Scripts
38 and 41, and the eligibility recommendation from Script 49.

This script DOES NOT search the web, geocode locations, infer coordinates,
or approve any coordinates. It creates a traceable research worksheet.

Inputs (read-only)
------------------
outputs/tables/39_port_coordinate_validation_register.csv
outputs/tables/38_port_evidence_validation_register.csv
outputs/tables/41_manual_source_content_verification_register_consolidated.csv
outputs/tables/49_port_eligibility_assessment.csv

Outputs
-------
outputs/tables/50_port_coordinate_research_register.csv
outputs/tables/50_port_coordinate_research_summary.csv
outputs/reports/50_port_coordinate_research_workflow_report.txt

Rerun safety
------------
- Input registers are never modified.
- Existing researcher-entered fields in the Script 39 register are retained.
- Existing researcher-entered fields in the Script 50 output are retained on
  rerun, matched by UN_LOCODE.
- Coordinates are never copied from a general port/city candidate or
  automatically promoted to validated status.
"""

import csv
from pathlib import Path
from datetime import date, datetime
from collections import Counter

TABLES_DIR = Path("outputs/tables")
REPORTS_DIR = Path("outputs/reports")

FILES = {
    "coordinates": TABLES_DIR / "39_port_coordinate_validation_register.csv",
    "identity": TABLES_DIR / "38_port_evidence_validation_register.csv",
    "source_review": TABLES_DIR / "41_manual_source_content_verification_register_consolidated.csv",
    "eligibility": TABLES_DIR / "49_port_eligibility_assessment.csv",
}

OUTPUT_FILE = TABLES_DIR / "50_port_coordinate_research_register.csv"
SUMMARY_FILE = TABLES_DIR / "50_port_coordinate_research_summary.csv"
REPORT_FILE = REPORTS_DIR / "50_port_coordinate_research_workflow_report.txt"

# These are researcher-facing fields. The script leaves them blank/defaulted;
# it does not make decisions on the researcher's behalf.
RESEARCH_FIELDS = [
    "Coordinate_Research_Priority",
    "Coordinate_Research_Question",
    "Required_Coordinate_Scope_Check",
    "Port_vs_Terminal_Resolution",
    "Candidate_Source_Review_Status",
    "Primary_Source_Title",
    "Primary_Source_Organization",
    "Primary_Source_URL",
    "Primary_Source_Access_Date",
    "Secondary_Source_Title",
    "Secondary_Source_Organization",
    "Secondary_Source_URL",
    "Secondary_Source_Access_Date",
    "Coordinate_Evidence_Extract",
    "Coordinate_Datum_or_CRS",
    "Coordinate_Reference_Point_Description",
    "Coordinate_Conflict_Notes",
    "Researcher_Coordinate_Decision",
    "Researcher_Validated_Latitude",
    "Researcher_Validated_Longitude",
    "Researcher_Coordinate_Type",
    "Researcher_Coordinate_Scope",
    "Researcher_Confidence",
    "Researcher_Reviewer",
    "Researcher_Review_Date",
    "Researcher_Review_Notes",
]

MANUAL_FIELDS = set(RESEARCH_FIELDS) | {
    "Validated_Port_Latitude", "Validated_Port_Longitude",
    "Port_Coordinate_Type", "Port_Coordinate_Scope",
    "Validated_Terminal_Latitude", "Validated_Terminal_Longitude",
    "Terminal_Name", "Terminal_Coordinate_Type",
    "Coordinate_Source_Organization", "Coordinate_Source_Title",
    "Coordinate_Source_URL", "Coordinate_Source_Access_Date",
    "Coordinate_Evidence_Description", "Coordinate_Validation_Status",
    "Coordinate_Confidence", "Coordinate_Reviewer", "Coordinate_Review_Date",
    "Coordinate_Review_Notes",
}

MISSING = {"", "NA", "N/A", "NONE", "NAN", "NULL"}


def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def norm(value):
    return clean(value).upper().replace(" ", "_")


def read_csv(path):
    if not path.exists():
        raise FileNotFoundError(f"Required input file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV header missing: {path}")
        rows = list(reader)
        return list(reader.fieldnames), rows


def index_by_code(rows, label, code_field="UN_LOCODE"):
    result = {}
    for row_number, row in enumerate(rows, start=2):
        code = clean(row.get(code_field, ""))
        if not code:
            raise ValueError(f"Blank {code_field} in {label}, CSV row {row_number}")
        if code in result:
            raise ValueError(f"Duplicate {code_field} {code} in {label}")
        result[code] = row
    return result


def present(value):
    return clean(value).upper() not in MISSING


def is_pair(lat, lon):
    return present(lat) and present(lon)


def is_number(value):
    try:
        number = float(clean(value))
        return -90 <= number <= 90
    except (TypeError, ValueError):
        return False


def valid_lat_lon(lat, lon):
    try:
        la, lo = float(clean(lat)), float(clean(lon))
        return -90 <= la <= 90 and -180 <= lo <= 180
    except (TypeError, ValueError):
        return False


def first(*values):
    for value in values:
        if present(value):
            return clean(value)
    return ""


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_existing_output():
    if not OUTPUT_FILE.exists():
        return {}, []
    fields, rows = read_csv(OUTPUT_FILE)
    return index_by_code(rows, "existing Script 50 output"), fields


def priority_for(identity, eligibility):
    cls = norm(eligibility.get("Eligibility_Classification", ""))
    network = norm(identity.get("Network_Match_Status", ""))
    identity_status = norm(identity.get("Identity_Validation_Status", ""))
    role = norm(identity.get("Preliminary_Geographic_Role", ""))

    if cls == "REGIONAL_OR_SENSITIVITY_CANDIDATE_PENDING_APPROVAL":
        return "HIGH"
    if "PERSIAN_GULF" in role and identity_status in {
        "VERIFIED_PORT_IDENTITY", "VERIFIED_CODE_IDENTITY"
    }:
        return "HIGH"
    if "PRESENT" in network:
        return "MEDIUM"
    return "LOW"


def scope_check(identity, source):
    facility_type = first(
        identity.get("Validated_Facility_Type"),
        identity.get("Provisional_Facility_Type"),
        source.get("Provisional_Facility_Type"),
    )
    facility_text = (facility_type + " " + first(
        identity.get("Researcher_Validated_Facility_Name"),
        source.get("Researcher_Validated_Facility_Name"),
        identity.get("Facility_or_Port_System"),
    )).upper()

    if any(term in facility_text for term in ["MULTI_FACILITY", "PORT_SYSTEM", "INDUSTRIAL", "CHEM", "QAPCO", "Q-CHEM"]):
        return "RESOLVE_EXACT_FACILITY_BEFORE_ASSIGNING_TERMINAL_COORDINATE"
    if any(term in facility_text for term in ["TERMINAL", "CONTAINER"]):
        return "VERIFY_TERMINAL_IDENTITY_AND_DISTINGUISH_FROM_PORT_REFERENCE_POINT"
    return "DETERMINE_Whether_PORT_CENTROID_OR_TERMINAL_COORDINATE_IS_REQUIRED".upper()


def main():
    print("\n" + "=" * 78)
    print("SCRIPT 50: PORT COORDINATE RESEARCH AND VALIDATION WORKFLOW")
    print("=" * 78)

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    loaded = {}
    indexes = {}
    for name, path in FILES.items():
        fields, rows = read_csv(path)
        loaded[name] = {"fields": fields, "rows": rows}
        indexes[name] = index_by_code(rows, name)
        print(f"{name}: {len(rows)} records, {len(fields)} columns")

    base_codes = set(indexes["coordinates"])
    for name in ("identity", "source_review", "eligibility"):
        codes = set(indexes[name])
        missing = sorted(base_codes - codes)
        extra = sorted(codes - base_codes)
        if missing or extra:
            raise ValueError(
                f"Register coverage mismatch for {name}: missing={missing}, extra={extra}. "
                "No output written."
            )

    existing_by_code, existing_fields = load_existing_output()

    # Preserve all columns from Script 39, then append Script 50 context and
    # workflow fields. This avoids discarding any future/manual Script 39 data.
    output_fields = list(loaded["coordinates"]["fields"])
    context_fields = [
        "Port_Name_in_Master", "Researcher_Validated_Port_Name",
        "Researcher_Validated_Facility_Name", "Country_Code",
        "Preliminary_Geographic_Role", "Research_Relevance_Screen",
        "Provisional_Facility_Type", "Facility_or_Port_System",
        "Identity_Validation_Status", "Identity_Evidence_Description",
        "Identity_Evidence_URL", "Source_Content_Review_Status",
        "Source_Content_Review_Conclusion", "Source_Strength_Assessment",
        "Coordinate_Source_URL_from_Script41", "All_Source_URLs",
        "Network_Match_Status", "Observed_Call_Count", "Observed_Vessel_Count",
        "Eligibility_Classification", "Recommended_Use",
        "Eligibility_Blocking_Conditions",
    ]
    for field in context_fields + RESEARCH_FIELDS:
        if field not in output_fields:
            output_fields.append(field)

    results = []
    for code in sorted(base_codes):
        coord = indexes["coordinates"][code]
        ident = indexes["identity"][code]
        source = indexes["source_review"][code]
        elig = indexes["eligibility"][code]
        old = existing_by_code.get(code, {})

        row = dict(coord)
        row.update({
            "Port_Name_in_Master": first(ident.get("Port_Name_in_Master"), source.get("Port_Name_in_Master")),
            "Researcher_Validated_Port_Name": first(source.get("Researcher_Validated_Port_Name"), ident.get("Researcher_Validated_Port_Name")),
            "Researcher_Validated_Facility_Name": first(source.get("Researcher_Validated_Facility_Name"), ident.get("Researcher_Validated_Facility_Name")),
            "Country_Code": first(ident.get("Country_Code"), source.get("Country_Code")),
            "Preliminary_Geographic_Role": first(ident.get("Preliminary_Geographic_Role"), source.get("Preliminary_Geographic_Role")),
            "Research_Relevance_Screen": first(ident.get("Research_Relevance_Screen"), source.get("Research_Relevance_Screen")),
            "Provisional_Facility_Type": first(ident.get("Provisional_Facility_Type"), source.get("Provisional_Facility_Type")),
            "Facility_or_Port_System": first(ident.get("Facility_or_Port_System"), source.get("Facility_or_Port_System")),
            "Identity_Validation_Status": first(source.get("Identity_Validation_Status"), ident.get("Identity_Validation_Status")),
            "Identity_Evidence_Description": first(source.get("Identity_Evidence_Description"), ident.get("Identity_Evidence_Description")),
            "Identity_Evidence_URL": first(source.get("Identity_Evidence_URL"), ident.get("Identity_Evidence_URL")),
            "Source_Content_Review_Status": source.get("Source_Content_Review_Status", ""),
            "Source_Content_Review_Conclusion": source.get("Source_Content_Review_Conclusion", ""),
            "Source_Strength_Assessment": source.get("Source_Strength_Assessment", ""),
            "Coordinate_Source_URL_from_Script41": source.get("Coordinate_Source_URL", ""),
            "All_Source_URLs": source.get("All_Source_URLs", ""),
            "Network_Match_Status": ident.get("Network_Match_Status", ""),
            "Observed_Call_Count": first(ident.get("Observed_Call_Count"), source.get("Observed_Call_Count")),
            "Observed_Vessel_Count": first(ident.get("Observed_Vessel_Count"), source.get("Observed_Vessel_Count")),
            "Eligibility_Classification": elig.get("Eligibility_Classification", ""),
            "Recommended_Use": elig.get("Recommended_Use", ""),
            "Eligibility_Blocking_Conditions": elig.get("Blocking_Conditions", ""),
        })

        # Script 39 is authoritative for existing validated coordinate fields.
        # Script 50 does not copy any candidate coordinate from other sources.
        port_lat = coord.get("Validated_Port_Latitude", "")
        port_lon = coord.get("Validated_Port_Longitude", "")
        term_lat = coord.get("Validated_Terminal_Latitude", "")
        term_lon = coord.get("Validated_Terminal_Longitude", "")
        port_pair = is_pair(port_lat, port_lon)
        terminal_pair = is_pair(term_lat, term_lon)
        pair_valid = (not port_pair or valid_lat_lon(port_lat, port_lon)) and (not terminal_pair or valid_lat_lon(term_lat, term_lon))

        row["Coordinate_Research_Priority"] = priority_for(ident, elig)
        row["Coordinate_Research_Question"] = (
            "What exact geographic reference point is supported by authoritative evidence, "
            "and does it represent the port, port system, terminal, berth or anchorage?"
        )
        row["Required_Coordinate_Scope_Check"] = scope_check(ident, source)
        row["Port_vs_Terminal_Resolution"] = "PENDING_RESEARCHER_REVIEW"
        row["Candidate_Source_Review_Status"] = "EXISTING_SOURCE_METADATA_REQUIRES_CONTENT_REVIEW"
        row["Primary_Source_Title"] = coord.get("Coordinate_Source_Title", "")
        row["Primary_Source_Organization"] = coord.get("Coordinate_Source_Organization", "")
        row["Primary_Source_URL"] = first(coord.get("Coordinate_Source_URL"), source.get("Coordinate_Source_URL"))
        row["Primary_Source_Access_Date"] = coord.get("Coordinate_Source_Access_Date", "")
        # Do not mislabel general identity sources as coordinate corroboration.
        # A researcher must enter a genuinely independent coordinate source.
        row["Secondary_Source_URL"] = ""
        row["Researcher_Coordinate_Decision"] = "PENDING"
        row["Researcher_Coordinate_Type"] = "NOT_ASSIGNED"
        row["Researcher_Coordinate_Scope"] = "NOT_ASSIGNED"
        row["Researcher_Confidence"] = "NOT_ASSESSED"

        if not pair_valid:
            row["Coordinate_Data_Quality_Flag"] = "INVALID_LATITUDE_OR_LONGITUDE_RANGE"
        elif port_pair or terminal_pair:
            row["Coordinate_Data_Quality_Flag"] = "COORDINATE_PAIR_PRESENT_REQUIRES_SOURCE_AND_SCOPE_REVIEW"
        else:
            row["Coordinate_Data_Quality_Flag"] = "NO_VALIDATED_COORDINATE_PAIR_CURRENTLY_POPULATED"

        # Preserve manual fields already entered in Script 50. Blank generated
        # defaults must never overwrite a nonblank researcher value.
        for field in MANUAL_FIELDS:
            if field in old and present(old.get(field)):
                row[field] = old[field]

        # Do not overwrite a previously entered Script 50 researcher decision.
        if present(old.get("Researcher_Coordinate_Decision", "")):
            row["Researcher_Coordinate_Decision"] = old["Researcher_Coordinate_Decision"]

        # Add QA fields to the schema dynamically.
        results.append(row)

    extra_qa_fields = ["Coordinate_Data_Quality_Flag"]
    for field in extra_qa_fields:
        if field not in output_fields:
            output_fields.append(field)

    # Validate unique keys and report key coordinate/review states.
    if len({r["UN_LOCODE"] for r in results}) != len(results):
        raise ValueError("Duplicate UN_LOCODE found in final Script 50 output.")

    status_counts = Counter(norm(r.get("Coordinate_Validation_Status")) or "BLANK" for r in results)
    decision_counts = Counter(norm(r.get("Researcher_Coordinate_Decision")) or "BLANK" for r in results)
    priority_counts = Counter(norm(r.get("Coordinate_Research_Priority")) for r in results)
    quality_counts = Counter(norm(r.get("Coordinate_Data_Quality_Flag")) for r in results)

    write_csv(OUTPUT_FILE, output_fields, results)

    summary_rows = []
    for label, counter in [
        ("EXISTING_COORDINATE_VALIDATION_STATUS", status_counts),
        ("RESEARCHER_COORDINATE_DECISION", decision_counts),
        ("RESEARCH_PRIORITY", priority_counts),
        ("COORDINATE_DATA_QUALITY", quality_counts),
    ]:
        for category, count in sorted(counter.items()):
            summary_rows.append({
                "Summary_Type": label,
                "Category": category,
                "Port_Count": count,
                "Interpretation": "Descriptive workflow status; no coordinate is automatically approved.",
            })

    summary_fields = ["Summary_Type", "Category", "Port_Count", "Interpretation"]
    write_csv(SUMMARY_FILE, summary_fields, summary_rows)

    lines = [
        "SCRIPT 50: PORT COORDINATE RESEARCH AND VALIDATION WORKFLOW",
        "=" * 78,
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Ports in coordinate register: {len(results)}",
        f"Output columns: {len(output_fields)}",
        f"Existing Script 50 records preserved by UN_LOCODE: {len(set(existing_by_code) & base_codes)}",
        "",
        "EXISTING COORDINATE VALIDATION STATUS",
    ]
    for category, count in sorted(status_counts.items()):
        lines.append(f"{category}: {count}")
    lines.extend(["", "RESEARCH PRIORITY"])
    for category, count in sorted(priority_counts.items()):
        lines.append(f"{category}: {count}")
    lines.extend(["", "COORDINATE DATA QUALITY FLAGS"])
    for category, count in sorted(quality_counts.items()):
        lines.append(f"{category}: {count}")
    lines.extend([
        "",
        "METHODOLOGICAL SAFEGUARDS",
        "1. No coordinates are geocoded, inferred, or automatically approved.",
        "2. Port coordinates and terminal coordinates remain separate.",
        "3. A port/city centroid must not be substituted for a terminal coordinate.",
        "4. Existing source URLs are leads; source content must be reviewed.",
        "5. Coordinate scope, datum/CRS, reference point and source date must be recorded.",
        "6. Conflicting or implausible coordinates must be documented, not silently averaged.",
        "7. Coordinate approval does not establish operational inclusion or AIS-confirmed transit.",
        "8. All input registers were read-only.",
        "",
        "INPUT FILES",
    ])
    for name, path in FILES.items():
        lines.append(f"{name}: {path}")
    lines.extend(["", "OUTPUT FILES", str(OUTPUT_FILE), str(SUMMARY_FILE), str(REPORT_FILE)])
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n" + "=" * 78)
    print("SCRIPT 50 COMPLETED")
    print("=" * 78)
    print("Ports prepared:", len(results))
    print("Output columns:", len(output_fields))
    print("Existing Script 50 records preserved:", len(set(existing_by_code) & base_codes))
    print("\nCoordinate validation status:")
    for category, count in sorted(status_counts.items()):
        print(f"  {category}: {count}")
    print("\nResearch priority:")
    for category, count in sorted(priority_counts.items()):
        print(f"  {category}: {count}")
    print("\nOUTPUTS")
    print(OUTPUT_FILE)
    print(SUMMARY_FILE)
    print(REPORT_FILE)
    print("\nNo coordinates were inferred or approved. Input registers were not modified.")


if __name__ == "__main__":
    main()
