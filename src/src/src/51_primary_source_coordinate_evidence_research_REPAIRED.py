"""SCRIPT 51 (REPAIRED): PRIMARY-SOURCE COORDINATE EVIDENCE RESEARCH REGISTER

Builds a researcher-facing evidence register from Script 50, while safely
migrating an earlier Script 51 output if it contains malformed concatenated
column names. Existing manual entries under correctly named columns are kept.
Legacy malformed columns are retained under Legacy_Malformed_* names; their
contents are NOT guessed or silently split.

This script does not browse, geocode, infer coordinates, or approve evidence.
"""

import csv
from pathlib import Path
from datetime import datetime
from collections import Counter

TABLES_DIR = Path("outputs/tables")
REPORTS_DIR = Path("outputs/reports")
INPUT_FILE = TABLES_DIR / "50_port_coordinate_research_register.csv"
OUTPUT_FILE = TABLES_DIR / "51_primary_source_coordinate_evidence_register.csv"
SUMMARY_FILE = TABLES_DIR / "51_coordinate_evidence_research_summary.csv"
REPORT_FILE = REPORTS_DIR / "51_primary_source_coordinate_evidence_research_report.txt"
BACKUP_FILE = TABLES_DIR / "51_primary_source_coordinate_evidence_register_pre_repair.csv"

MISSING = {"", "NA", "N/A", "NONE", "NAN", "NULL"}

# These fields represent researcher-entered review, not inherited source metadata.
MANUAL_FIELDS = [
    "Research_Progress_Status",
    "Primary_Source_Organization_Reviewed", "Primary_Source_Title_Reviewed",
    "Primary_Source_URL_Reviewed", "Primary_Source_Access_Date_Reviewed",
    "Primary_Source_Type", "Primary_Source_Exact_Evidence",
    "Primary_Source_Coordinate_Text", "Primary_Source_Latitude",
    "Primary_Source_Longitude", "Primary_Source_Datum_or_CRS",
    "Primary_Source_Reference_Point", "Primary_Source_Coordinate_Scope",
    "Primary_Source_Claim_Verification",
    "Secondary_Source_Organization_Reviewed", "Secondary_Source_Title_Reviewed",
    "Secondary_Source_URL_Reviewed", "Secondary_Source_Access_Date_Reviewed",
    "Secondary_Source_Exact_Evidence", "Secondary_Source_Latitude",
    "Secondary_Source_Longitude", "Secondary_Source_Datum_or_CRS",
    "Secondary_Source_Reference_Point", "Secondary_Source_Coordinate_Scope",
    "Independent_Corroboration_Status", "Coordinate_Conflict_Description",
    "Researcher_Evidence_Conclusion", "Researcher_Recommended_Coordinate_Type",
    "Researcher_Recommended_Coordinate_Scope", "Researcher_Recommended_Latitude",
    "Researcher_Recommended_Longitude", "Researcher_Confidence",
    "Researcher_Reviewer", "Researcher_Review_Date", "Researcher_Review_Notes",
]

GENERATED_FIELDS = [
    "Evidence_Research_Status", "Evidence_Research_Priority",
    "Evidence_Research_Target_Name", "Evidence_Research_Country_Code",
    "Evidence_Research_Geographic_Context", "Evidence_Research_Guidance",
    "Coordinate_Scope_Research_Question", "Required_Primary_Evidence",
    "Required_Independent_Corroboration", "Research_Query_Port_Authority",
    "Research_Query_Government_Source", "Research_Query_Terminal_Source",
    "Research_Query_UNLOCODE_Crosscheck", "Research_Query_Geographic_Check",
    "Evidence_Review_QA_Status", "Source_Metadata_Availability",
    "Candidate_Primary_Source_Organization", "Candidate_Primary_Source_Title",
    "Candidate_Primary_Source_URL", "Candidate_Primary_Source_Access_Date",
    "Candidate_Source_Content_Review_Status", "Legacy_Malformed_Column_Notes",
]

# Known malformed headers observed in the user's diagnostic export.
KNOWN_MALFORMED = {
    "Validated_Terminal_LatitudeValidated_Terminal_Longitude":
        "Legacy_Malformed_Validated_Terminal_LatitudeValidated_Terminal_Longitude",
    "Evidence_Review_QA_StatusResearch_Progress_Status":
        "Legacy_Malformed_Evidence_Review_QA_StatusResearch_Progress_Status",
    "Primary_Source_Claim_VerificationSecondary_Source_Organization_Reviewed":
        "Legacy_Malformed_Primary_Source_Claim_VerificationSecondary_Source_Organization_Reviewed",
}


def clean(value):
    return "" if value is None else str(value).strip()


def present(value):
    return clean(value).upper() not in MISSING


def norm(value):
    return clean(value).upper().replace(" ", "_")


def read_csv(path):
    if not path.exists():
        raise FileNotFoundError(f"Required input file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"CSV header missing: {path}")
        fields = list(reader.fieldnames)
        rows = list(reader)
    return fields, rows


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def index_by_code(rows, label):
    out = {}
    for line_no, row in enumerate(rows, start=2):
        code = clean(row.get("UN_LOCODE"))
        if not code:
            raise ValueError(f"Blank UN_LOCODE in {label}, CSV row {line_no}")
        if code in out:
            raise ValueError(f"Duplicate UN_LOCODE {code} in {label}")
        out[code] = row
    return out


def first(*values):
    for value in values:
        if present(value):
            return clean(value)
    return ""


def make_queries(row):
    name = first(row.get("Researcher_Validated_Facility_Name"),
                 row.get("Researcher_Validated_Port_Name"),
                 row.get("Port_Name_in_Master"), row.get("Port_Name"))
    country = first(row.get("Country_Code"))
    code = clean(row.get("UN_LOCODE"))
    geo = first(row.get("Geographic_Region"), row.get("Preliminary_Geographic_Role"))
    suffix = f" {country}" if country else ""
    return {
        "Research_Query_Port_Authority": f'"{name}" official port authority coordinates{suffix}',
        "Research_Query_Government_Source": f'"{name}" official government port location latitude longitude{suffix}',
        "Research_Query_Terminal_Source": f'"{name}" terminal official location coordinates{suffix}',
        "Research_Query_UNLOCODE_Crosscheck": f'"{code}" UN/LOCODE location identity coordinates',
        "Research_Query_Geographic_Check": f'"{name}" port location map {geo}'.strip(),
    }


def source_guidance(row):
    text = " ".join(clean(row.get(k)) for k in [
        "Provisional_Facility_Type", "Facility_or_Port_System",
        "Researcher_Validated_Facility_Name"]).upper()
    if any(x in text for x in ["INDUSTRIAL", "CHEM", "QAPCO", "Q-CHEM", "ALUMINIUM"]):
        return ("Prioritise the named facility/operator and relevant port authority; verify whether "
                "the location is an industrial terminal, jetty or wider port system.")
    if any(x in text for x in ["MULTI", "PORT_SYSTEM", "HARBOUR", "HARBOR"]):
        return ("Prioritise the official port authority and facility-specific operator; resolve "
                "the exact port/facility before recording a terminal point.")
    return ("Prioritise the official port authority or government maritime/transport source; "
            "use an operator source for terminal-specific coordinates.")


def derived_qa(row):
    p_url = first(row.get("Primary_Source_URL_Reviewed"))
    s_url = first(row.get("Secondary_Source_URL_Reviewed"))
    p_lat, p_lon = row.get("Primary_Source_Latitude", ""), row.get("Primary_Source_Longitude", "")
    s_lat, s_lon = row.get("Secondary_Source_Latitude", ""), row.get("Secondary_Source_Longitude", "")
    if not p_url:
        return "SOURCE_METADATA_AVAILABLE_CONTENT_REVIEW_PENDING" if present(row.get("Candidate_Primary_Source_URL")) else "PRIMARY_SOURCE_NOT_ENTERED"
    if not s_url:
        return "SECONDARY_SOURCE_NOT_ENTERED"
    if not (present(p_lat) and present(p_lon)):
        return "PRIMARY_COORDINATE_PAIR_INCOMPLETE"
    if not (present(s_lat) and present(s_lon)):
        return "SECONDARY_COORDINATE_PAIR_INCOMPLETE"
    try:
        pla, plo, sla, slo = map(float, [p_lat, p_lon, s_lat, s_lon])
    except (TypeError, ValueError):
        return "COORDINATE_NOT_NUMERIC"
    if not (-90 <= pla <= 90 and -180 <= plo <= 180 and -90 <= sla <= 90 and -180 <= slo <= 180):
        return "COORDINATE_OUT_OF_RANGE"
    return "COORDINATE_PAIRS_FORMAT_VALID_REQUIRES_MANUAL_SOURCE_AND_SCOPE_REVIEW"


def main():
    print("\n" + "=" * 78)
    print("SCRIPT 51 (REPAIRED): PRIMARY-SOURCE COORDINATE EVIDENCE RESEARCH REGISTER")
    print("=" * 78)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    input_fields, input_rows = read_csv(INPUT_FILE)
    input_index = index_by_code(input_rows, "Script 50 input")
    print(f"script50: {len(input_rows)} records, {len(input_fields)} columns")

    old_fields, old_rows = ([], [])
    if OUTPUT_FILE.exists():
        old_fields, old_rows = read_csv(OUTPUT_FILE)
    old_index = index_by_code(old_rows, "existing Script 51 output") if old_rows else {}

    # Preserve a byte-level copy of the pre-repair output before replacing it.
    if OUTPUT_FILE.exists() and not BACKUP_FILE.exists():
        BACKUP_FILE.write_bytes(OUTPUT_FILE.read_bytes())

    # Canonical field list: preserve Script 50 fields, but do not perpetuate
    # malformed merged headers as active schema fields.
    fields = []
    for field in input_fields:
        if field in KNOWN_MALFORMED:
            legacy = KNOWN_MALFORMED[field]
            if legacy not in fields:
                fields.append(legacy)
        elif field not in fields:
            fields.append(field)
    for field in list(KNOWN_MALFORMED.values()) + GENERATED_FIELDS + MANUAL_FIELDS:
        if field not in fields:
            fields.append(field)

    results = []
    legacy_detected = []
    for code in sorted(input_index):
        base = dict(input_index[code])
        old = dict(old_index.get(code, {}))
        row = {}

        # Copy ordinary Script 50 fields, migrating known malformed headers to
        # explicitly named legacy columns without guessing their contents.
        for key, value in base.items():
            if key in KNOWN_MALFORMED:
                legacy_key = KNOWN_MALFORMED[key]
                row[legacy_key] = clean(value)
                legacy_detected.append(f"Script50:{key}")
            else:
                row[key] = value

        # Carry forward malformed old-output values as raw legacy audit fields.
        for key, value in old.items():
            if key in KNOWN_MALFORMED:
                legacy_key = KNOWN_MALFORMED[key]
                if present(value):
                    row[legacy_key] = clean(value)
                legacy_detected.append(f"ExistingScript51:{key}")

        name = first(base.get("Researcher_Validated_Facility_Name"),
                     base.get("Researcher_Validated_Port_Name"),
                     base.get("Port_Name_in_Master"), base.get("Port_Name"))
        priority = norm(base.get("Coordinate_Research_Priority")) or "UNRANKED"
        candidate_org = first(base.get("Primary_Source_Organization"), base.get("Coordinate_Source_Organization"),
                              old.get("Primary_Source_Organization"), old.get("Coordinate_Source_Organization"),
                              old.get("Candidate_Primary_Source_Organization"))
        candidate_title = first(base.get("Primary_Source_Title"), base.get("Coordinate_Source_Title"),
                                old.get("Primary_Source_Title"), old.get("Coordinate_Source_Title"),
                                old.get("Candidate_Primary_Source_Title"))
        candidate_url = first(base.get("Primary_Source_URL"), base.get("Coordinate_Source_URL"),
                              old.get("Primary_Source_URL"), old.get("Coordinate_Source_URL"),
                              old.get("Candidate_Primary_Source_URL"))
        candidate_date = first(base.get("Primary_Source_Access_Date"), base.get("Coordinate_Source_Access_Date"),
                               old.get("Primary_Source_Access_Date"), old.get("Coordinate_Source_Access_Date"),
                               old.get("Candidate_Primary_Source_Access_Date"))
        source_status = first(base.get("Source_Content_Review_Status"), "NOT_REVIEWED")
        metadata_available = any(map(present, [candidate_org, candidate_title, candidate_url]))

        row.update({
            "Evidence_Research_Status": "SOURCE_METADATA_AVAILABLE_CONTENT_REVIEW_PENDING" if metadata_available else "NOT_YET_RESEARCHED",
            "Evidence_Research_Priority": priority,
            "Evidence_Research_Target_Name": name,
            "Evidence_Research_Country_Code": clean(base.get("Country_Code")),
            "Evidence_Research_Geographic_Context": first(base.get("Geographic_Region"), base.get("Preliminary_Geographic_Role")),
            "Evidence_Research_Guidance": source_guidance(base),
            "Coordinate_Scope_Research_Question": first(base.get("Required_Coordinate_Scope_Check"),
                "Determine whether the study requires a port reference point, terminal, berth or anchorage."),
            "Required_Primary_Evidence": ("A source controlled by the port authority, government maritime/transport agency, "
                "or facility operator that explicitly identifies the location and coordinate reference point."),
            "Required_Independent_Corroboration": ("A separate authoritative source identifying the same facility/reference point; "
                "do not count copied text or mirrored datasets as independent corroboration."),
            **make_queries(base),
            "Source_Metadata_Availability": "AVAILABLE_NOT_CONTENT_VERIFIED" if metadata_available else "NO_SOURCE_METADATA_FOUND",
            "Candidate_Primary_Source_Organization": candidate_org,
            "Candidate_Primary_Source_Title": candidate_title,
            "Candidate_Primary_Source_URL": candidate_url,
            "Candidate_Primary_Source_Access_Date": candidate_date,
            "Candidate_Source_Content_Review_Status": source_status,
            "Legacy_Malformed_Column_Notes": ";".join(sorted(set(legacy_detected))) if legacy_detected else "",
        })

        # Preserve all properly named manual fields from prior Script 51.
        for field in MANUAL_FIELDS:
            if present(old.get(field)):
                row[field] = old[field]

        # Preserve a prior explicit progress state. Otherwise reflect metadata
        # availability without claiming that content has been reviewed.
        if present(old.get("Research_Progress_Status")):
            row["Research_Progress_Status"] = old["Research_Progress_Status"]
        else:
            row["Research_Progress_Status"] = "SOURCE_METADATA_IDENTIFIED_REVIEW_PENDING" if metadata_available else "NOT_YET_RESEARCHED"

        # A previously reviewed URL belongs only in *_Reviewed fields if a
        # researcher had explicitly entered it there; candidate URLs stay separate.
        row["Evidence_Review_QA_Status"] = derived_qa(row)
        if present(old.get("Evidence_Review_QA_Status")) and old.get("Evidence_Review_QA_Status") not in {
            "PRIMARY_SOURCE_NOT_ENTERED", "NOT_REVIEWED", "SOURCE_METADATA_AVAILABLE_CONTENT_REVIEW_PENDING"
        }:
            row["Evidence_Review_QA_Status"] = old["Evidence_Review_QA_Status"]

        results.append(row)

    codes = [clean(r.get("UN_LOCODE")) for r in results]
    if len(codes) != len(set(codes)):
        raise ValueError("Duplicate UN_LOCODE in output. No files written.")
    if set(codes) != set(input_index):
        raise ValueError("Output UN/LOCODE coverage differs from Script 50. No files written.")

    # Ensure no malformed active headers survive.
    for bad in KNOWN_MALFORMED:
        if bad in fields:
            raise ValueError(f"Malformed column header remains active: {bad}")

    status_counts = Counter(norm(r.get("Evidence_Research_Status")) or "BLANK" for r in results)
    priority_counts = Counter(norm(r.get("Evidence_Research_Priority")) or "BLANK" for r in results)
    qa_counts = Counter(norm(r.get("Evidence_Review_QA_Status")) or "BLANK" for r in results)
    metadata_counts = Counter(norm(r.get("Source_Metadata_Availability")) or "BLANK" for r in results)
    preserved = len(set(old_index) & set(input_index))
    malformed_count = sum(1 for f in input_fields + old_fields if f in KNOWN_MALFORMED)

    write_csv(OUTPUT_FILE, fields, results)
    summary = []
    for group, counter in [("RESEARCH_STATUS", status_counts), ("RESEARCH_PRIORITY", priority_counts),
                           ("EVIDENCE_REVIEW_QA", qa_counts), ("SOURCE_METADATA_AVAILABILITY", metadata_counts)]:
        for category, count in sorted(counter.items()):
            summary.append({"Summary_Type": group, "Category": category, "Port_Count": count,
                            "Interpretation": "Workflow tracking only; metadata availability is not content verification or coordinate approval."})
    write_csv(SUMMARY_FILE, ["Summary_Type", "Category", "Port_Count", "Interpretation"], summary)

    report = [
        "SCRIPT 51 (REPAIRED): PRIMARY-SOURCE COORDINATE EVIDENCE RESEARCH REGISTER",
        "=" * 78,
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Script 50 input records: {len(input_rows)}",
        f"Script 51 output records: {len(results)}",
        f"Output columns: {len(fields)}",
        f"Existing Script 51 records matched by UN_LOCODE: {preserved}",
        f"Malformed headers detected and migrated to legacy fields: {malformed_count}",
        "",
        "SOURCE METADATA AVAILABILITY",
    ]
    report += [f"{k}: {v}" for k, v in sorted(metadata_counts.items())]
    report += ["", "RESEARCH STATUS COUNTS"] + [f"{k}: {v}" for k, v in sorted(status_counts.items())]
    report += ["", "RESEARCH PRIORITY COUNTS"] + [f"{k}: {v}" for k, v in sorted(priority_counts.items())]
    report += ["", "EVIDENCE QA COUNTS"] + [f"{k}: {v}" for k, v in sorted(qa_counts.items())]
    report += [
        "", "MIGRATION AND METHODOLOGICAL NOTES",
        "1. Known malformed concatenated headers are moved to Legacy_Malformed_* fields.",
        "2. Legacy combined cell contents are retained verbatim and are not guessed or split.",
        "3. Existing candidate source metadata is surfaced separately from researcher-reviewed evidence.",
        "4. Candidate URLs and titles do not count as source-content verification.",
        "5. Properly named researcher-entered review fields are preserved by UN_LOCODE.",
        "6. No coordinates are inferred, copied into validated fields, or approved.",
        "7. Search prompts are not web research; this script does not browse or geocode.",
        "8. Coordinate range checks do not establish geographic correctness.",
        "9. Port-call records do not establish vessel transit through the Strait of Hormuz.",
        "", f"INPUT: {INPUT_FILE}", f"BACKUP: {BACKUP_FILE if BACKUP_FILE.exists() else 'Not required'}",
        "OUTPUTS:", str(OUTPUT_FILE), str(SUMMARY_FILE), str(REPORT_FILE),
    ]
    REPORT_FILE.write_text("\n".join(report) + "\n", encoding="utf-8")

    print("\n" + "=" * 78)
    print("SCRIPT 51 REPAIR COMPLETED")
    print("=" * 78)
    print("Ports prepared:", len(results))
    print("Output columns:", len(fields))
    print("Existing Script 51 records matched:", preserved)
    print("Malformed headers migrated:", malformed_count)
    print("\nSource metadata availability:")
    for k, v in sorted(metadata_counts.items()): print(f"  {k}: {v}")
    print("\nResearch status:")
    for k, v in sorted(status_counts.items()): print(f"  {k}: {v}")
    print("\nEvidence QA:")
    for k, v in sorted(qa_counts.items()): print(f"  {k}: {v}")
    print("\nOUTPUTS")
    print(OUTPUT_FILE)
    print(SUMMARY_FILE)
    print(REPORT_FILE)
    if BACKUP_FILE.exists(): print("Backup:", BACKUP_FILE)
    print("\nNo coordinates were inferred or approved. Input register was not modified.")


if __name__ == "__main__":
    main()
