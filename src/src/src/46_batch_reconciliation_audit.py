
"""
SCRIPT 46: BATCH RECONCILIATION AND CONSOLIDATION AUDIT

Purpose:
Compare the original Script 41 register and preliminary review
registers from Batches 1 to 5.

Important:
- This is an audit only.
- It does not merge records.
- It does not modify any existing register.
- It identifies missing batch files and review-field differences.
- It checks whether Batch 1 findings are present in Batch 5.

Outputs:
1. outputs/tables/46_batch_reconciliation_audit.csv
2. outputs/tables/46_batch_record_coverage.csv
3. outputs/reports/46_batch_reconciliation_audit_report.txt
"""

import csv
from pathlib import Path
from collections import defaultdict
from datetime import datetime


# ============================================================
# 1. PROJECT PATHS
# ============================================================

ROOT = Path(".")

TABLES_DIR = ROOT / "outputs" / "tables"
REPORTS_DIR = ROOT / "outputs" / "reports"

TABLES_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. INPUT FILES
# ============================================================

FILES = {
    "ORIGINAL": (
        "41_manual_source_content_verification_register.csv"
    ),

    "BATCH_1": (
    "41_manual_source_content_verification_register_batch1_reviewed.csv"
),

    "BATCH_2": (
        "41_manual_source_content_verification_register_batch2_preliminary_review.csv"
    ),

    "BATCH_3": (
        "41_manual_source_content_verification_register_batch3_preliminary_review.csv"
    ),

    "BATCH_4": (
        "41_manual_source_content_verification_register_batch4_preliminary_review.csv"
    ),

    "BATCH_5": (
        "41_manual_source_content_verification_register_batch5_preliminary_review.csv"
    ),
}


# ============================================================
# 3. MANUAL REVIEW FIELDS
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
# 4. EXPECTED BATCH RECORDS
# ============================================================

EXPECTED_BATCHES = {

    "BATCH_1": [
        "AEAUH",
        "AEFJR",
        "AEKLF",
        "AERKT",
    ],

    "BATCH_2": [
        "AESHJ",
        "BHKBS",
    ],

    "BATCH_3": [
        "INHZA",
        "INIXY",
        "INPPV",
    ],

    "BATCH_4": [
        "IQUQR",
        "KWSAA",
        "KWSWK",
    ],

    "BATCH_5": [
        "OMDQM",
        "PKKIA",
        "QAQAP",
        "QAQCH",
        "QAUMS",
        "SADMM",
        "SAJUB",
    ],
}


# ============================================================
# 5. OUTPUT FILES
# ============================================================

AUDIT_FILE = (
    TABLES_DIR / "46_batch_reconciliation_audit.csv"
)

COVERAGE_FILE = (
    TABLES_DIR / "46_batch_record_coverage.csv"
)

REPORT_FILE = (
    REPORTS_DIR / "46_batch_reconciliation_audit_report.txt"
)


# ============================================================
# 6. HELPER FUNCTIONS
# ============================================================

def locate_file(filename):
    """
    Find a register file within the project.

    Prefer outputs/tables when multiple copies exist.
    """

    preferred = TABLES_DIR / filename

    if preferred.exists():
        return preferred

    matches = list(ROOT.rglob(filename))

    matches = [
        path for path in matches
        if ".venv" not in path.parts
        and "site-packages" not in path.parts
    ]

    if not matches:
        return None

    if len(matches) > 1:
        print(
            f"\nWARNING: Multiple copies found for {filename}"
        )

        for match in matches:
            print(" ", match)

        print("Using:", matches[0])

    return matches[0]


def read_csv_file(path):

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise ValueError(
                f"No header found in {path}"
            )

        fields = reader.fieldnames
        rows = list(reader)

    return fields, rows


def write_csv(path, fields, rows):

    with path.open(
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


def clean(value):
    return (value or "").strip()


def get_changed_fields(old_row, new_row):

    changed = []

    for field in MANUAL_FIELDS:

        old_value = clean(old_row.get(field, ""))
        new_value = clean(new_row.get(field, ""))

        if old_value != new_value:
            changed.append(field)

    return changed


# ============================================================
# 7. LOAD ALL AVAILABLE REGISTERS
# ============================================================

def main():

    print("\n" + "=" * 72)
    print("SCRIPT 46: BATCH RECONCILIATION AND CONSOLIDATION AUDIT")
    print("=" * 72)

    datasets = {}
    file_paths = {}
    missing_files = []

    for version, filename in FILES.items():

        path = locate_file(filename)

        if path is None:

            missing_files.append(version)

            print(
                f"\nNOT FOUND: {version} - {filename}"
            )

            continue

        fields, rows = read_csv_file(path)

        codes = [
            clean(row.get("UN_LOCODE", ""))
            for row in rows
        ]

        if len(rows) != 19:
            print(
                f"WARNING: {version} contains {len(rows)} "
                "records instead of 19."
            )

        if len(set(codes)) != len(codes):
            raise ValueError(
                f"Duplicate UN_LOCODE found in {version}."
            )

        if any(not code for code in codes):
            raise ValueError(
                f"Blank UN_LOCODE found in {version}."
            )

        missing_columns = [
            field for field in MANUAL_FIELDS
            if field not in fields
        ]

        if missing_columns:
            raise ValueError(
                f"{version} is missing fields: {missing_columns}"
            )

        datasets[version] = {
            "fields": fields,
            "rows": rows,
            "by_code": {
                clean(row["UN_LOCODE"]): row
                for row in rows
            },
        }

        file_paths[version] = path

        print(
            f"\nLoaded {version}: "
            f"{len(rows)} records, {len(fields)} columns"
        )

        print("Path:", path)

    if "ORIGINAL" not in datasets:
        raise FileNotFoundError(
            "Original Script 41 register not found. "
            "Cannot perform a reliable reconciliation."
        )

    if "BATCH_5" not in datasets:
        raise FileNotFoundError(
            "Batch 5 register not found. "
            "Run Script 45 before Script 46."
        )

    # --------------------------------------------------------
    # Validate schema consistency
    # --------------------------------------------------------

    original_fields = datasets["ORIGINAL"]["fields"]

    schema_issues = []

    for version, dataset in datasets.items():

        if dataset["fields"] != original_fields:

            schema_issues.append(version)

            print(
                f"WARNING: Schema differs from ORIGINAL in {version}"
            )

    # --------------------------------------------------------
    # Prepare lookup
    # --------------------------------------------------------

    original = datasets["ORIGINAL"]["by_code"]
    final_batch = datasets["BATCH_5"]["by_code"]

    audit_rows = []
    coverage_rows = []

    # ========================================================
    # 8. RECORD-LEVEL COVERAGE AUDIT
    # ========================================================

    for code in sorted(original):

        original_row = original[code]

        coverage = {
            "UN_LOCODE": code,
        }

        for version in FILES:

            if version not in datasets:
                coverage[version] = "FILE_MISSING"
                continue

            version_row = datasets[version]["by_code"].get(code)

            if version_row is None:
                coverage[version] = "RECORD_MISSING"
                continue

            changed_fields = get_changed_fields(
                original_row,
                version_row
            )

            if changed_fields:
                coverage[version] = "MANUAL_FIELDS_CHANGED"
            else:
                coverage[version] = "NO_MANUAL_FIELD_CHANGE"

        coverage_rows.append(coverage)

    # ========================================================
    # 9. FIELD-LEVEL VERSION AUDIT
    # ========================================================

    for code in sorted(original):

        original_row = original[code]

        final_row = final_batch.get(code)

        if final_row is None:
            raise ValueError(
                f"{code} is missing from Batch 5."
            )

        for field in MANUAL_FIELDS:

            original_value = clean(
                original_row.get(field, "")
            )

            final_value = clean(
                final_row.get(field, "")
            )

            changed_versions = []

            values_by_version = {}

            for version in FILES:

                if version not in datasets:
                    values_by_version[version] = "FILE_MISSING"
                    continue

                row = datasets[version]["by_code"].get(code)

                if row is None:
                    values_by_version[version] = "RECORD_MISSING"
                    continue

                value = clean(row.get(field, ""))

                values_by_version[version] = value

                if value != original_value:
                    changed_versions.append(version)

            if original_value == final_value:
                final_comparison = "SAME_AS_ORIGINAL"
            else:
                final_comparison = "DIFFERS_FROM_ORIGINAL"

            # Identify whether Batch 1's change is present in Batch 5.
            batch1_value = values_by_version.get(
                "BATCH_1",
                "FILE_MISSING"
            )

            if batch1_value == "FILE_MISSING":
                batch1_status = "BATCH1_FILE_MISSING"

            elif batch1_value == "RECORD_MISSING":
                batch1_status = "BATCH1_RECORD_MISSING"

            elif batch1_value == original_value:
                batch1_status = "BATCH1_FIELD_UNCHANGED"

            elif final_value == batch1_value:
                batch1_status = "BATCH1_VALUE_PRESENT_IN_BATCH5"

            else:
                batch1_status = "BATCH1_VALUE_NOT_PRESENT_IN_BATCH5"

            audit_rows.append({

                "UN_LOCODE": code,
                "Field": field,

                "Original_Value": original_value,

                "Batch1_Value": values_by_version.get(
                    "BATCH_1", ""
                ),

                "Batch2_Value": values_by_version.get(
                    "BATCH_2", ""
                ),

                "Batch3_Value": values_by_version.get(
                    "BATCH_3", ""
                ),

                "Batch4_Value": values_by_version.get(
                    "BATCH_4", ""
                ),

                "Batch5_Value": final_value,

                "Versions_Different_From_Original": (
                    ";".join(changed_versions)
                ),

                "Batch1_Reconciliation_Status": batch1_status,

                "Batch5_vs_Original": final_comparison,
            })

    # ========================================================
    # 10. CHECK EXPECTED BATCH RECORDS
    # ========================================================

    expected_batch_issues = []

    for batch, expected_codes in EXPECTED_BATCHES.items():

        if batch not in datasets:

            for code in expected_codes:

                expected_batch_issues.append({
                    "Batch": batch,
                    "UN_LOCODE": code,
                    "Status": "BATCH_FILE_MISSING",
                })

            continue

        batch_codes = datasets[batch]["by_code"]

        for code in expected_codes:

            if code not in batch_codes:

                expected_batch_issues.append({
                    "Batch": batch,
                    "UN_LOCODE": code,
                    "Status": "EXPECTED_RECORD_MISSING",
                })

            else:

                row = batch_codes[code]

                if clean(
                    row.get("Source_Content_Review_Status", "")
                ) == "NOT_REVIEWED":

                    expected_batch_issues.append({
                        "Batch": batch,
                        "UN_LOCODE": code,
                        "Status": "EXPECTED_RECORD_NOT_REVIEWED",
                    })

    # ========================================================
    # 11. BATCH 1 UAE REVIEW RECONCILIATION
    # ========================================================

    batch1_codes = EXPECTED_BATCHES["BATCH_1"]

    batch1_findings = []

    if "BATCH_1" in datasets:

        batch1_data = datasets["BATCH_1"]["by_code"]

        for code in batch1_codes:

            if code not in batch1_data:
                continue

            batch1_row = batch1_data[code]
            batch5_row = final_batch[code]

            changed_fields = get_changed_fields(
                original[code],
                batch1_row
            )

            missing_from_batch5 = []

            different_in_batch5 = []

            for field in changed_fields:

                batch1_value = clean(
                    batch1_row.get(field, "")
                )

                batch5_value = clean(
                    batch5_row.get(field, "")
                )

                original_value = clean(
                    original[code].get(field, "")
                )

                if batch5_value == original_value:
                    missing_from_batch5.append(field)

                elif batch5_value != batch1_value:
                    different_in_batch5.append(field)

            if missing_from_batch5:
                status = "BATCH1_REVIEW_FIELDS_MISSING_FROM_BATCH5"

            elif different_in_batch5:
                status = "BATCH1_REVIEW_FIELDS_DIFFER_FROM_BATCH5"

            elif changed_fields:
                status = "BATCH1_REVIEW_FIELDS_PRESENT_IN_BATCH5"

            else:
                status = "NO_BATCH1_MANUAL_CHANGES_DETECTED"

            batch1_findings.append({

                "UN_LOCODE": code,

                "Batch1_Changed_Field_Count": len(changed_fields),

                "Batch1_Changed_Fields": ";".join(changed_fields),

                "Fields_Missing_From_Batch5": (
                    ";".join(missing_from_batch5)
                ),

                "Fields_Different_In_Batch5": (
                    ";".join(different_in_batch5)
                ),

                "Reconciliation_Status": status,
            })

    else:

        for code in batch1_codes:

            batch1_findings.append({

                "UN_LOCODE": code,

                "Batch1_Changed_Field_Count": "",

                "Batch1_Changed_Fields": "",

                "Fields_Missing_From_Batch5": "",

                "Fields_Different_In_Batch5": "",

                "Reconciliation_Status": "BATCH1_FILE_NOT_AVAILABLE",
            })

    # ========================================================
    # 12. WRITE AUDIT OUTPUTS
    # ========================================================

    write_csv(
        AUDIT_FILE,
        [
            "UN_LOCODE",
            "Field",
            "Original_Value",
            "Batch1_Value",
            "Batch2_Value",
            "Batch3_Value",
            "Batch4_Value",
            "Batch5_Value",
            "Versions_Different_From_Original",
            "Batch1_Reconciliation_Status",
            "Batch5_vs_Original",
        ],
        audit_rows
    )

    coverage_fields = [
        "UN_LOCODE",
        "ORIGINAL",
        "BATCH_1",
        "BATCH_2",
        "BATCH_3",
        "BATCH_4",
        "BATCH_5",
    ]

    write_csv(
        COVERAGE_FILE,
        coverage_fields,
        coverage_rows
    )

    # ========================================================
    # 13. BUILD REPORT
    # ========================================================

    report = []

    report.append("=" * 72)
    report.append("SCRIPT 46: BATCH RECONCILIATION AUDIT REPORT")
    report.append("=" * 72)

    report.append(
        f"Generated: {datetime.now().isoformat(timespec='seconds')}"
    )

    report.append("")

    report.append("1. INPUT FILE STATUS")
    report.append("-" * 72)

    for version in FILES:

        if version in datasets:

            report.append(
                f"{version}: AVAILABLE | {file_paths[version]}"
            )

        else:

            report.append(
                f"{version}: MISSING"
            )

    report.append("")

    report.append("2. SCHEMA VALIDATION")
    report.append("-" * 72)

    report.append(
        f"Original column count: {len(original_fields)}"
    )

    if schema_issues:

        report.append(
            "Schema differences detected in: "
            + ", ".join(schema_issues)
        )

    else:

        report.append(
            "All available registers have matching column schemas."
        )

    report.append("")

    report.append("3. EXPECTED BATCH RECORD COVERAGE")
    report.append("-" * 72)

    for batch, expected_codes in EXPECTED_BATCHES.items():

        if batch not in datasets:

            report.append(
                f"{batch}: FILE MISSING"
            )

            continue

        available_codes = datasets[batch]["by_code"]

        present = [
            code for code in expected_codes
            if code in available_codes
        ]

        report.append(
            f"{batch}: {len(present)}/{len(expected_codes)} "
            f"expected records present"
        )

    report.append("")

    report.append("4. BATCH 1 UAE RECONCILIATION")
    report.append("-" * 72)

    for finding in batch1_findings:

        report.append(
            f"{finding['UN_LOCODE']}: "
            f"{finding['Reconciliation_Status']}"
        )

        if finding["Fields_Missing_From_Batch5"]:

            report.append(
                "  Missing fields: "
                + finding["Fields_Missing_From_Batch5"]
            )

        if finding["Fields_Different_In_Batch5"]:

            report.append(
                "  Different fields: "
                + finding["Fields_Different_In_Batch5"]
            )

    report.append("")

    report.append("5. EXPECTED BATCH ISSUES")
    report.append("-" * 72)

    if expected_batch_issues:

        for issue in expected_batch_issues:

            report.append(
                f"{issue['Batch']} | {issue['UN_LOCODE']} | "
                f"{issue['Status']}"
            )

    else:

        report.append(
            "No missing expected batch records detected."
        )

    report.append("")

    report.append("6. AUDIT SUMMARY")
    report.append("-" * 72)

    report.append(
        f"Field-level audit rows: {len(audit_rows)}"
    )

    report.append(
        f"Record coverage rows: {len(coverage_rows)}"
    )

    report.append(
        f"Missing input files: {len(missing_files)}"
    )

    report.append(
        f"Expected batch coverage issues: {len(expected_batch_issues)}"
    )

    missing_uae_fields = sum(
        len(finding["Fields_Missing_From_Batch5"])
        > 0
        for finding in batch1_findings
    )

    report.append(
        f"UAE records with Batch 1 fields missing from Batch 5: "
        f"{missing_uae_fields}"
    )

    report.append("")

    report.append("7. IMPORTANT LIMITATIONS")
    report.append("-" * 72)

    report.append(
        "This audit compares register values; it does not independently "
        "verify source content."
    )

    report.append(
        "A value matching the Batch 1 register does not prove that the "
        "underlying claim is correct."
    )

    report.append(
        "A missing Batch 1 file prevents a definitive comparison of "
        "Batch 1 against Batch 5."
    )

    report.append(
        "No records were merged or modified by this script."
    )

    report.append(
        "Do not create a consolidated master until the audit findings "
        "have been reviewed."
    )

    report.append("=" * 72)

    REPORT_FILE.write_text(
        "\n".join(report),
        encoding="utf-8"
    )

    # ========================================================
    # 14. TERMINAL SUMMARY
    # ========================================================

    print("\n" + "=" * 72)
    print("SCRIPT 46 COMPLETED SUCCESSFULLY")
    print("=" * 72)

    print("\nAvailable input files:")

    for version in datasets:
        print("-", version)

    print("\nMissing input files:")

    if missing_files:
        for version in missing_files:
            print("-", version)
    else:
        print("None")

    print("\nExpected batch coverage issues:")
    print(len(expected_batch_issues))

    print("\nUAE reconciliation:")

    for finding in batch1_findings:

        print(
            finding["UN_LOCODE"],
            "->",
            finding["Reconciliation_Status"]
        )

    print("\nAudit rows:", len(audit_rows))
    print("Coverage rows:", len(coverage_rows))

    print("\nOUTPUT FILES:")
    print(AUDIT_FILE)
    print(COVERAGE_FILE)
    print(REPORT_FILE)

    print("\nNo existing register was modified.")
    print("No consolidation or merging was performed.")

    print("=" * 72)


if __name__ == "__main__":
    main()
