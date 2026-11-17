"""
SCRIPT 48: CONSOLIDATED REGISTER QUALITY AUDIT

Purpose:
Read-only quality audit of the consolidated 19-port source-review
register (Script 41 / Script 47), the original Script 41 register,
and the separate Script 39 coordinate-validation register.

Checks:
1. Record count and UN/LOCODE uniqueness.
2. Expected 57-column schema and original-schema preservation.
3. Completeness of the 17 manual-review fields.
4. Researcher/source-review status consistency.
5. Coordinate and operational-inclusion safeguards.
6. Preservation/consistency of all five batch checkpoints.
7. Complete batch coverage.
8. Preservation of all non-manual fields against the original register.

Inputs are never modified.

Outputs:
- outputs/tables/48_consolidated_register_quality_audit.csv
- outputs/tables/48_consolidated_register_record_summary.csv
- outputs/tables/48_batch_checkpoint_consistency.csv
- outputs/reports/48_consolidated_register_quality_report.txt
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

MASTER_FILE = (
    TABLES_DIR
    / "41_manual_source_content_verification_register_consolidated.csv"
)

ORIGINAL_FILE = (
    TABLES_DIR
    / "41_manual_source_content_verification_register.csv"
)

COORDINATE_REGISTER_FILE = (
    TABLES_DIR
    / "39_port_coordinate_validation_register.csv"
)

BATCH_FILES = {
    "BATCH_1": {
        "file": "41_manual_source_content_verification_register_batch1_reviewed.csv",
        "codes": ["AEAUH", "AEFJR", "AEKLF", "AERKT"],
    },
    "BATCH_2": {
        "file": "41_manual_source_content_verification_register_batch2_preliminary_review.csv",
        "codes": ["AESHJ", "BHKBS"],
    },
    "BATCH_3": {
        "file": "41_manual_source_content_verification_register_batch3_preliminary_review.csv",
        "codes": ["INHZA", "INIXY", "INPPV"],
    },
    "BATCH_4": {
        "file": "41_manual_source_content_verification_register_batch4_preliminary_review.csv",
        "codes": ["IQUQR", "KWSAA", "KWSWK"],
    },
    "BATCH_5": {
        "file": "41_manual_source_content_verification_register_batch5_preliminary_review.csv",
        "codes": ["OMDQM", "PKKIA", "QAQAP", "QAQCH", "QAUMS", "SADMM", "SAJUB"],
    },
}


# ============================================================
# 2. EXPECTED SCHEMA AND SAFEGUARDS
# ============================================================

EXPECTED_RECORDS = 19
EXPECTED_COLUMNS = 57

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

COORDINATE_FIELDS = [
    "Validated_Port_Latitude",
    "Validated_Port_Longitude",
    "Validated_Terminal_Latitude",
    "Validated_Terminal_Longitude",
]

SAFE_COORDINATE_STATUSES = {
    "PENDING",
    "PENDING_RECONCILIATION",
}

SAFE_OPERATIONAL_STATUSES = {"PENDING"}

AUDIT_FILE = TABLES_DIR / "48_consolidated_register_quality_audit.csv"
RECORD_SUMMARY_FILE = TABLES_DIR / "48_consolidated_register_record_summary.csv"
CHECKPOINT_FILE = TABLES_DIR / "48_batch_checkpoint_consistency.csv"
REPORT_FILE = REPORTS_DIR / "48_consolidated_register_quality_report.txt"


# ============================================================
# 3. HELPERS
# ============================================================

def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def read_csv(path):
    if not path.exists():
        raise FileNotFoundError(f"Required file not found:\n{path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)

        if not reader.fieldnames:
            raise ValueError(f"CSV header missing: {path}")

        fields = list(reader.fieldnames)
        rows = list(reader)

    return fields, rows


def index_records(rows, source_name):
    indexed = {}

    for row_number, row in enumerate(rows, start=2):
        code = clean(row.get("UN_LOCODE", ""))

        if not code:
            raise ValueError(
                f"Blank UN_LOCODE found in {source_name}, CSV row {row_number}."
            )

        if code in indexed:
            raise ValueError(
                f"Duplicate UN_LOCODE {code} found in {source_name}."
            )

        indexed[code] = row

    return indexed


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def add_issue(issues, code, category, field, value, severity, message):
    issues.append({
        "UN_LOCODE": code,
        "Issue_Category": category,
        "Field": field,
        "Current_Value": value,
        "Severity": severity,
        "Issue_Description": message,
    })


def status_for_record(record_issues):
    if any(item["Severity"] == "CRITICAL" for item in record_issues):
        return "CRITICAL"
    if any(item["Severity"] == "HIGH" for item in record_issues):
        return "REQUIRES_REVIEW"
    if record_issues:
        return "CHECK"
    return "PASSED"


def write_report(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ============================================================
# 4. MAIN
# ============================================================

def main():
    print("\n" + "=" * 72)
    print("SCRIPT 48: CONSOLIDATED REGISTER QUALITY AUDIT")
    print("=" * 72)

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------
    # Load all three registers
    # --------------------------------------------------------

    master_fields, master_rows = read_csv(MASTER_FILE)
    original_fields, original_rows = read_csv(ORIGINAL_FILE)
    coordinate_fields, coordinate_rows = read_csv(COORDINATE_REGISTER_FILE)

    master = index_records(master_rows, "CONSOLIDATED_MASTER")
    original = index_records(original_rows, "ORIGINAL_REGISTER")
    coordinate_master = index_records(coordinate_rows, "COORDINATE_REGISTER")

    print("\nINPUTS LOADED")
    print(f"Consolidated master: {len(master_rows)} records, {len(master_fields)} columns")
    print(f"Original register:   {len(original_rows)} records, {len(original_fields)} columns")
    print(f"Coordinate register: {len(coordinate_rows)} records, {len(coordinate_fields)} columns")

    # Do not continue with incomplete coordinate coverage.
    if set(coordinate_master) != set(master):
        missing_coordinates = sorted(set(master) - set(coordinate_master))
        extra_coordinates = sorted(set(coordinate_master) - set(master))
        raise ValueError(
            "UN_LOCODE mismatch between consolidated master and Script 39 "
            f"coordinate register. Missing coordinate records: {missing_coordinates}; "
            f"extra coordinate records: {extra_coordinates}"
        )

    issues = []
    record_summary = []
    checkpoint_results = []

    # --------------------------------------------------------
    # Check 1: record count and identity
    # --------------------------------------------------------

    if len(master_rows) != EXPECTED_RECORDS:
        add_issue(
            issues, "ALL", "STRUCTURAL", "RECORD_COUNT", len(master_rows),
            "CRITICAL", f"Expected {EXPECTED_RECORDS} records."
        )

    if len(master) != len(master_rows):
        add_issue(
            issues, "ALL", "STRUCTURAL", "UN_LOCODE_UNIQUENESS",
            len(master), "CRITICAL", "Duplicate or invalid UN_LOCODE detected."
        )

    if set(master) != set(original):
        for code in sorted(set(original) - set(master)):
            add_issue(
                issues, code, "RECORD_COVERAGE", "UN_LOCODE", "MISSING",
                "CRITICAL", "Record from original register is missing."
            )
        for code in sorted(set(master) - set(original)):
            add_issue(
                issues, code, "RECORD_COVERAGE", "UN_LOCODE", "UNEXPECTED",
                "CRITICAL", "Record is not present in original register."
            )

    # --------------------------------------------------------
    # Check 2: schema
    # --------------------------------------------------------

    if len(master_fields) != EXPECTED_COLUMNS:
        add_issue(
            issues, "ALL", "STRUCTURAL", "COLUMN_COUNT", len(master_fields),
            "CRITICAL", f"Expected {EXPECTED_COLUMNS} columns."
        )

    if master_fields != original_fields:
        add_issue(
            issues, "ALL", "STRUCTURAL", "SCHEMA", "DIFFERENT",
            "CRITICAL", "Consolidated schema differs from original register."
        )

    required_master_fields = MANUAL_FIELDS + [
        "UN_LOCODE",
        "Operational_Inclusion_Decision",
    ]
    missing_master_columns = [
        field for field in required_master_fields if field not in master_fields
    ]

    for field in missing_master_columns:
        add_issue(
            issues, "ALL", "STRUCTURAL", field, "MISSING_COLUMN",
            "CRITICAL", "Required column is absent from consolidated register."
        )

    required_coordinate_fields = [
        "UN_LOCODE",
        "Coordinate_Validation_Status",
    ] + COORDINATE_FIELDS

    missing_coordinate_columns = [
        field for field in required_coordinate_fields
        if field not in coordinate_fields
    ]

    for field in missing_coordinate_columns:
        add_issue(
            issues, "ALL", "COORDINATE_SCHEMA", field, "MISSING_COLUMN",
            "CRITICAL", "Required coordinate field is absent from Script 39 register."
        )

    if missing_master_columns or missing_coordinate_columns:
        raise ValueError(
            "Required columns are missing. Audit stopped to avoid invalid checks. "
            f"Master missing: {missing_master_columns}; "
            f"coordinate register missing: {missing_coordinate_columns}"
        )

    # --------------------------------------------------------
    # Check 3: batch checkpoints and checkpoint consistency
    # --------------------------------------------------------

    batch_expected_codes = set()

    for batch_name, config in BATCH_FILES.items():
        batch_path = TABLES_DIR / config["file"]
        expected_codes = config["codes"]
        batch_expected_codes.update(expected_codes)

        try:
            batch_fields, batch_rows = read_csv(batch_path)
            batch = index_records(batch_rows, batch_name)
        except FileNotFoundError:
            add_issue(
                issues, "ALL", "CHECKPOINT", batch_name, "FILE_MISSING",
                "CRITICAL", "Batch checkpoint file is missing."
            )
            checkpoint_results.append({
                "Batch": batch_name,
                "Expected_Records": len(expected_codes),
                "Records_Found": 0,
                "Records_Compared": 0,
                "Fields_Compared": 0,
                "Mismatched_Fields": 0,
                "Missing_Expected_Codes": ";".join(expected_codes),
                "Checkpoint_Status": "FILE_MISSING",
            })
            continue

        if batch_fields != master_fields:
            add_issue(
                issues, "ALL", "CHECKPOINT", batch_name, "SCHEMA_MISMATCH",
                "CRITICAL", "Batch schema differs from consolidated master."
            )

        missing_codes = [code for code in expected_codes if code not in batch]
        compared_records = 0
        compared_fields = 0
        mismatch_count = 0

        for code in expected_codes:
            if code not in batch or code not in master:
                continue

            compared_records += 1
            batch_row = batch[code]
            master_row = master[code]

            for field in MANUAL_FIELDS:
                compared_fields += 1
                batch_value = clean(batch_row.get(field, ""))
                master_value = clean(master_row.get(field, ""))

                if batch_value != master_value:
                    mismatch_count += 1
                    add_issue(
                        issues, code, "CHECKPOINT_CONSISTENCY", field,
                        master_value, "HIGH",
                        f"{batch_name} value differs from consolidated master."
                    )

        for code in missing_codes:
            add_issue(
                issues, code, "CHECKPOINT", batch_name, "RECORD_MISSING",
                "CRITICAL", "Expected reviewed record is missing from checkpoint."
            )

        if missing_codes:
            checkpoint_status = "RECORDS_MISSING"
        elif mismatch_count:
            checkpoint_status = "VALUE_MISMATCH"
        elif compared_records != len(expected_codes):
            checkpoint_status = "INCOMPLETE_COMPARISON"
        else:
            checkpoint_status = "MATCHED"

        checkpoint_results.append({
            "Batch": batch_name,
            "Expected_Records": len(expected_codes),
            "Records_Found": len(batch),
            "Records_Compared": compared_records,
            "Fields_Compared": compared_fields,
            "Mismatched_Fields": mismatch_count,
            "Missing_Expected_Codes": ";".join(missing_codes),
            "Checkpoint_Status": checkpoint_status,
        })

        print(
            f"{batch_name}: {checkpoint_status} "
            f"({compared_records}/{len(expected_codes)} expected records)"
        )

    # --------------------------------------------------------
    # Check 4: batch coverage
    # --------------------------------------------------------

    if batch_expected_codes != set(master):
        uncovered = sorted(set(master) - batch_expected_codes)
        unexpected = sorted(batch_expected_codes - set(master))

        for code in uncovered:
            add_issue(
                issues, code, "BATCH_COVERAGE", "UN_LOCODE",
                "NO_EXPECTED_BATCH", "HIGH",
                "Record is not assigned to any of the five batches."
            )

        for code in unexpected:
            add_issue(
                issues, code, "BATCH_COVERAGE", "UN_LOCODE",
                "NOT_IN_MASTER", "CRITICAL",
                "Batch includes a code absent from the consolidated master."
            )

    # --------------------------------------------------------
    # Check 5: per-record completeness and safeguards
    # --------------------------------------------------------

    for code in sorted(master):
        row = master[code]
        coordinate_row = coordinate_master[code]
        record_issue_start = len(issues)

        blank_manual_fields = []

        for field in MANUAL_FIELDS:
            value = clean(row.get(field, ""))
            if not value:
                blank_manual_fields.append(field)
                add_issue(
                    issues, code, "MANUAL_FIELD_COMPLETENESS", field,
                    "BLANK", "HIGH", "Manual-review field is blank."
                )

        source_status = clean(row.get("Source_Content_Review_Status", ""))
        if source_status in ("", "NOT_REVIEWED"):
            add_issue(
                issues, code, "REVIEW_STATUS", "Source_Content_Review_Status",
                source_status, "HIGH",
                "Source-content review has not been recorded."
            )

        researcher_status = clean(row.get("Researcher_Review_Status", ""))
        if researcher_status in ("", "NOT_REVIEWED"):
            add_issue(
                issues, code, "RESEARCHER_REVIEW", "Researcher_Review_Status",
                researcher_status, "HIGH",
                "Researcher review status is missing or not reviewed."
            )

        # Coordinate checks use Script 39, not Script 41.
        coordinate_status = clean(
            coordinate_row.get("Coordinate_Validation_Status", "")
        )

        if coordinate_status not in SAFE_COORDINATE_STATUSES:
            add_issue(
                issues, code, "COORDINATE_SAFEGUARD",
                "Coordinate_Validation_Status", coordinate_status,
                "CRITICAL",
                "Coordinate status is not an approved pending state."
            )

        nonblank_coordinates = []
        for field in COORDINATE_FIELDS:
            coordinate_value = clean(coordinate_row.get(field, ""))
            if coordinate_value:
                nonblank_coordinates.append(field)
                add_issue(
                    issues, code, "COORDINATE_SAFEGUARD", field,
                    coordinate_value, "CRITICAL",
                    "Validated coordinate is populated while coordinate "
                    "approval remains pending."
                )

        operational_status = clean(
            row.get("Operational_Inclusion_Decision", "")
        )
        if operational_status not in SAFE_OPERATIONAL_STATUSES:
            add_issue(
                issues, code, "OPERATIONAL_SAFEGUARD",
                "Operational_Inclusion_Decision", operational_status,
                "CRITICAL", "Operational decision is not PENDING."
            )

        # Preserve per-record issue status after all checks for this code.
        this_record_issues = [
            issue for issue in issues[record_issue_start:]
            if issue["UN_LOCODE"] == code
        ]

        record_summary.append({
            "UN_LOCODE": code,
            "Manual_Fields_Expected": len(MANUAL_FIELDS),
            "Manual_Fields_Blank": len(blank_manual_fields),
            "Blank_Manual_Field_Names": ";".join(blank_manual_fields),
            "Source_Content_Review_Status": source_status,
            "Researcher_Review_Status": researcher_status,
            "Coordinate_Validation_Status": coordinate_status,
            "Nonblank_Validated_Coordinate_Fields": ";".join(nonblank_coordinates),
            "Operational_Inclusion_Decision": operational_status,
            "Record_QA_Status": status_for_record(this_record_issues),
            "Record_Issue_Count": len(this_record_issues),
        })

    # --------------------------------------------------------
    # Check 6: non-manual field preservation
    # --------------------------------------------------------

    manual_field_set = set(MANUAL_FIELDS)
    nonmanual_fields = [
        field for field in original_fields
        if field not in manual_field_set
    ]

    nonmanual_mismatch_count = 0

    for code in sorted(set(master) & set(original)):
        master_row = master[code]
        original_row = original[code]

        for field in nonmanual_fields:
            original_value = clean(original_row.get(field, ""))
            master_value = clean(master_row.get(field, ""))

            if original_value != master_value:
                nonmanual_mismatch_count += 1
                add_issue(
                    issues, code, "NONMANUAL_FIELD_PRESERVATION",
                    field, master_value, "CRITICAL",
                    "A non-manual field differs from the original register."
                )

    # --------------------------------------------------------
    # Check 7: final summaries and outputs
    # --------------------------------------------------------

    severity_counts = Counter(issue["Severity"] for issue in issues)
    category_counts = Counter(issue["Issue_Category"] for issue in issues)
    record_status_counts = Counter(
        row["Record_QA_Status"] for row in record_summary
    )
    checkpoint_status_counts = Counter(
        row["Checkpoint_Status"] for row in checkpoint_results
    )

    if severity_counts["CRITICAL"]:
        overall_status = "CRITICAL_ISSUES_FOUND"
    elif severity_counts["HIGH"]:
        overall_status = "REQUIRES_REVIEW"
    elif issues:
        overall_status = "CHECK_WARNINGS"
    else:
        overall_status = "PASSED"

    audit_fields = [
        "UN_LOCODE",
        "Issue_Category",
        "Field",
        "Current_Value",
        "Severity",
        "Issue_Description",
    ]

    record_summary_fields = [
        "UN_LOCODE",
        "Manual_Fields_Expected",
        "Manual_Fields_Blank",
        "Blank_Manual_Field_Names",
        "Source_Content_Review_Status",
        "Researcher_Review_Status",
        "Coordinate_Validation_Status",
        "Nonblank_Validated_Coordinate_Fields",
        "Operational_Inclusion_Decision",
        "Record_QA_Status",
        "Record_Issue_Count",
    ]

    checkpoint_fields = [
        "Batch",
        "Expected_Records",
        "Records_Found",
        "Records_Compared",
        "Fields_Compared",
        "Mismatched_Fields",
        "Missing_Expected_Codes",
        "Checkpoint_Status",
    ]

    write_csv(AUDIT_FILE, audit_fields, issues)
    write_csv(RECORD_SUMMARY_FILE, record_summary_fields, record_summary)
    write_csv(CHECKPOINT_FILE, checkpoint_fields, checkpoint_results)

    report_lines = [
        "SCRIPT 48: CONSOLIDATED REGISTER QUALITY AUDIT",
        "=" * 72,
        f"Audit timestamp: {datetime.now().isoformat(timespec='seconds')}",
        f"Overall status: {overall_status}",
        "",
        "INPUTS",
        f"Consolidated master: {MASTER_FILE}",
        f"Original register: {ORIGINAL_FILE}",
        f"Coordinate register: {COORDINATE_REGISTER_FILE}",
        "",
        "STRUCTURAL SUMMARY",
        f"Master records: {len(master_rows)} (expected {EXPECTED_RECORDS})",
        f"Master columns: {len(master_fields)} (expected {EXPECTED_COLUMNS})",
        f"Unique master UN/LOCODEs: {len(master)}",
        f"Coordinate records: {len(coordinate_rows)}",
        f"Manual fields checked: {len(MANUAL_FIELDS)}",
        f"Non-manual fields compared: {len(nonmanual_fields)}",
        f"Non-manual field mismatches: {nonmanual_mismatch_count}",
        "",
        "ISSUE SUMMARY",
        f"Total issues: {len(issues)}",
        f"Critical: {severity_counts['CRITICAL']}",
        f"High: {severity_counts['HIGH']}",
        f"Medium: {severity_counts['MEDIUM']}",
        f"Low: {severity_counts['LOW']}",
        "",
        "ISSUES BY CATEGORY",
    ]

    for category, count in sorted(category_counts.items()):
        report_lines.append(f"{category}: {count}")

    report_lines.extend([
        "",
        "RECORD QA STATUS",
    ])
    for status, count in sorted(record_status_counts.items()):
        report_lines.append(f"{status}: {count}")

    report_lines.extend([
        "",
        "BATCH CHECKPOINT STATUS",
    ])
    for status, count in sorted(checkpoint_status_counts.items()):
        report_lines.append(f"{status}: {count}")

    report_lines.extend([
        "",
        "COORDINATE SAFEGUARD",
        "Coordinate validation was checked against Script 39.",
        "No coordinate was approved by this audit.",
        "",
        "INTERPRETATION",
        "A PASSED result indicates structural consistency and preservation checks passed.",
        "It does not independently verify the factual correctness of source claims,",
        "port identity, facility mapping, coordinates, or operational relevance.",
        "Preliminary desk review is not equivalent to researcher sign-off.",
        "",
        "OUTPUTS",
        str(AUDIT_FILE),
        str(RECORD_SUMMARY_FILE),
        str(CHECKPOINT_FILE),
        str(REPORT_FILE),
    ])

    write_report(REPORT_FILE, report_lines)

    print("\n" + "=" * 72)
    print("SCRIPT 48 COMPLETED")
    print("=" * 72)
    print("Overall status:", overall_status)
    print("Total issues:", len(issues))
    print("Critical:", severity_counts["CRITICAL"])
    print("High:", severity_counts["HIGH"])
    print("Record QA:", dict(record_status_counts))
    print("Non-manual mismatches:", nonmanual_mismatch_count)
    print("\nOUTPUTS")
    print(AUDIT_FILE)
    print(RECORD_SUMMARY_FILE)
    print(CHECKPOINT_FILE)
    print(REPORT_FILE)
    print("\nInput registers were not modified.")


if __name__ == "__main__":
    main()
