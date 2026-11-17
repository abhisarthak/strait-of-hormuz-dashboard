
"""
SCRIPT 47: CONTROLLED SOURCE-REVIEW BATCH CONSOLIDATION

Base register:
Batch 5

Source register:
Recovered Batch 1 (reviewed)

Purpose:
Restore the four missing UAE reviews from Batch 1 into a new
copy of Batch 5.

Merge rules:
1. Copy only the 17 manual-review fields.
2. Update only AEAUH, AEFJR, AEKLF and AERKT.
3. Copy a Batch 1 value only if Batch 5 still has the original value.
4. If Batch 5 already has the Batch 1 value, leave it unchanged.
5. If Batch 5 contains a different later value, flag a conflict.
6. Never overwrite original or batch checkpoint files.
7. Preserve all other records and columns.
8. Preserve coordinate and operational inclusion decisions.

Outputs:
- 41_manual_source_content_verification_register_consolidated.csv
- 47_consolidation_merge_log.csv
- 47_consolidation_report.txt

If conflicts are detected, the consolidated master is NOT created.
"""

import csv
from pathlib import Path
from datetime import datetime


# ============================================================
# 1. INPUT AND OUTPUT PATHS
# ============================================================

TABLES_DIR = Path("outputs/tables")
REPORTS_DIR = Path("outputs/reports")

ORIGINAL_FILE = (
    TABLES_DIR /
    "41_manual_source_content_verification_register.csv"
)

BATCH1_FILE = (
    TABLES_DIR /
    "41_manual_source_content_verification_register_batch1_reviewed.csv"
)

BATCH5_FILE = (
    TABLES_DIR /
    "41_manual_source_content_verification_register_batch5_preliminary_review.csv"
)

OUTPUT_FILE = (
    TABLES_DIR /
    "41_manual_source_content_verification_register_consolidated.csv"
)

LOG_FILE = (
    TABLES_DIR /
    "47_consolidation_merge_log.csv"
)

REPORT_FILE = (
    REPORTS_DIR /
    "47_consolidation_report.txt"
)


# ============================================================
# 2. RECORDS TO RESTORE FROM BATCH 1
# ============================================================

BATCH1_CODES = [
    "AEAUH",
    "AEFJR",
    "AEKLF",
    "AERKT",
]


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
# 4. HELPER FUNCTIONS
# ============================================================

def read_register(path):

    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found:\n{path}"
        )

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise ValueError(
                f"Missing CSV header: {path}"
            )

        fields = reader.fieldnames
        rows = list(reader)

    return fields, rows


def clean(value):
    return (value or "").strip()


def index_by_code(rows):

    result = {}

    for row in rows:

        code = clean(row.get("UN_LOCODE", ""))

        if not code:
            raise ValueError(
                "Blank UN_LOCODE detected."
            )

        if code in result:
            raise ValueError(
                f"Duplicate UN_LOCODE detected: {code}"
            )

        result[code] = row

    return result


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


# ============================================================
# 5. MAIN FUNCTION
# ============================================================

def main():

    print("\n" + "=" * 72)
    print("SCRIPT 47: CONTROLLED SOURCE-REVIEW BATCH CONSOLIDATION")
    print("=" * 72)

    TABLES_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Load all three source registers
    # --------------------------------------------------------

    original_fields, original_rows = read_register(
        ORIGINAL_FILE
    )

    batch1_fields, batch1_rows = read_register(
        BATCH1_FILE
    )

    batch5_fields, batch5_rows = read_register(
        BATCH5_FILE
    )

    original = index_by_code(original_rows)
    batch1 = index_by_code(batch1_rows)
    batch5 = index_by_code(batch5_rows)

    print("\nINPUT REGISTERS LOADED")

    print("Original:", len(original_rows), "records")
    print("Batch 1:", len(batch1_rows), "records")
    print("Batch 5:", len(batch5_rows), "records")

    # --------------------------------------------------------
    # Validate record counts
    # --------------------------------------------------------

    if (
        len(original_rows) != 19
        or len(batch1_rows) != 19
        or len(batch5_rows) != 19
    ):
        raise ValueError(
            "All three registers must contain exactly 19 records."
        )

    if not (
        set(original)
        == set(batch1)
        == set(batch5)
    ):
        raise ValueError(
            "UN_LOCODE sets differ across the three registers."
        )

    # --------------------------------------------------------
    # Validate schemas
    # --------------------------------------------------------

    if not (
        original_fields
        == batch1_fields
        == batch5_fields
    ):
        raise ValueError(
            "Column schemas differ. Consolidation stopped."
        )

    if len(original_fields) != 57:
        raise ValueError(
            f"Expected 57 columns; found {len(original_fields)}."
        )

    missing_fields = [
        field for field in MANUAL_FIELDS
        if field not in original_fields
    ]

    if missing_fields:
        raise ValueError(
            f"Manual fields missing: {missing_fields}"
        )

    print("Columns:", len(original_fields))
    print("Schema validation: PASSED")

    # --------------------------------------------------------
    # Validate target records
    # --------------------------------------------------------

    for code in BATCH1_CODES:

        if code not in original:
            raise ValueError(
                f"{code} missing from original register."
            )

        if code not in batch1:
            raise ValueError(
                f"{code} missing from Batch 1."
            )

        if code not in batch5:
            raise ValueError(
                f"{code} missing from Batch 5."
            )

    # --------------------------------------------------------
    # Start with a copy of Batch 5
    # --------------------------------------------------------

    consolidated_rows = [
        row.copy()
        for row in batch5_rows
    ]

    consolidated = index_by_code(
        consolidated_rows
    )

    # --------------------------------------------------------
    # Validate operational and coordinate safeguards
    # --------------------------------------------------------

    for code in BATCH1_CODES:

        row = consolidated[code]

        if clean(
            row.get("Operational_Inclusion_Decision", "")
        ) != "PENDING":

            raise ValueError(
                f"{code}: operational decision is not PENDING. "
                "Review manually before consolidation."
            )

        coordinate_status = clean(
            row.get("Coordinate_Validation_Status", "")
        )

        if coordinate_status not in (
            "PENDING",
            "PENDING_RECONCILIATION"
        ):

            raise ValueError(
                f"{code}: unexpected coordinate status "
                f"{coordinate_status}."
            )

    # --------------------------------------------------------
    # Controlled merge
    # --------------------------------------------------------

    merge_log = []
    conflicts = []

    total_copied = 0
    total_already_present = 0
    total_unchanged_in_batch1 = 0

    for code in BATCH1_CODES:

        original_row = original[code]
        batch1_row = batch1[code]
        target_row = consolidated[code]

        copied_count = 0
        already_present_count = 0
        unchanged_count = 0

        for field in MANUAL_FIELDS:

            original_value = clean(
                original_row.get(field, "")
            )

            batch1_value = clean(
                batch1_row.get(field, "")
            )

            batch5_value = clean(
                batch5[code].get(field, "")
            )

            # Batch 1 did not change this field.
            if batch1_value == original_value:

                status = "BATCH1_UNCHANGED"

                unchanged_count += 1
                total_unchanged_in_batch1 += 1

            # Batch 1 changed the field, and Batch 5 still
            # has the original value. Safe to restore.
            elif batch5_value == original_value:

                target_row[field] = batch1_row[field]

                status = "RESTORED_FROM_BATCH1"

                copied_count += 1
                total_copied += 1

            # Batch 1 and Batch 5 already agree.
            elif batch5_value == batch1_value:

                status = "ALREADY_PRESENT_IN_BATCH5"

                already_present_count += 1
                total_already_present += 1

            # Both versions differ from the original and
            # from each other. Do not guess which is correct.
            else:

                status = "CONFLICT_REQUIRES_MANUAL_REVIEW"

                conflicts.append({
                    "UN_LOCODE": code,
                    "Field": field,
                    "Original_Value": original_value,
                    "Batch1_Value": batch1_value,
                    "Batch5_Value": batch5_value,
                })

            merge_log.append({

                "UN_LOCODE": code,
                "Field": field,
                "Original_Value": original_value,
                "Batch1_Value": batch1_value,
                "Batch5_Value": batch5_value,
                "Merge_Status": status,
            })

        print(
            f"\n{code}: "
            f"{copied_count} restored, "
            f"{already_present_count} already present, "
            f"{unchanged_count} unchanged in Batch 1"
        )

    # --------------------------------------------------------
    # Write merge log
    # --------------------------------------------------------

    log_fields = [
        "UN_LOCODE",
        "Field",
        "Original_Value",
        "Batch1_Value",
        "Batch5_Value",
        "Merge_Status",
    ]

    write_csv(
        LOG_FILE,
        log_fields,
        merge_log
    )

    # --------------------------------------------------------
    # Stop if conflicts exist
    # --------------------------------------------------------

    if conflicts:

        report = []

        report.append(
            "SCRIPT 47: CONSOLIDATION STOPPED"
        )

        report.append("=" * 72)

        report.append(
            f"Conflicts detected: {len(conflicts)}"
        )

        report.append(
            "No consolidated master was created."
        )

        report.append(
            "Review the conflict entries in the merge log."
        )

        REPORT_FILE.write_text(
            "\n".join(report),
            encoding="utf-8"
        )

        print("\nCONSOLIDATION STOPPED")

        print("Conflicts:", len(conflicts))

        for conflict in conflicts:

            print(
                conflict["UN_LOCODE"],
                conflict["Field"]
            )

        print("\nMerge log:", LOG_FILE)
        print("Report:", REPORT_FILE)

        print(
            "\nNo existing register was modified."
        )

        raise RuntimeError(
            "Conflicts require manual review. "
            "No consolidated master created."
        )

    # --------------------------------------------------------
    # Validate all records and safeguards
    # --------------------------------------------------------

    if len(consolidated_rows) != 19:
        raise ValueError(
            "Consolidated record count validation failed."
        )

    if len(consolidated_rows[0]) != 57:
        raise ValueError(
            "Consolidated schema validation failed."
        )

    for code in BATCH1_CODES:

        row = consolidated[code]

        if row["Operational_Inclusion_Decision"] != "PENDING":
            raise ValueError(
                f"{code}: operational decision changed."
            )

        if row["Coordinate_Validation_Status"] not in (
            "PENDING",
            "PENDING_RECONCILIATION"
        ):
            raise ValueError(
                f"{code}: coordinate status changed."
            )

    # --------------------------------------------------------
    # Verify all other 15 records remain identical to Batch 5
    # --------------------------------------------------------

    for code in consolidated:

        if code in BATCH1_CODES:
            continue

        original_batch5_row = batch5[code]
        consolidated_row = consolidated[code]

        for field in original_fields:

            if (
                original_batch5_row.get(field, "")
                != consolidated_row.get(field, "")
            ):

                raise ValueError(
                    f"Unexpected modification to {code}, {field}"
                )

    # --------------------------------------------------------
    # Write consolidated master
    # --------------------------------------------------------

    write_csv(
        OUTPUT_FILE,
        original_fields,
        consolidated_rows
    )

    # --------------------------------------------------------
    # Read-after-write verification
    # --------------------------------------------------------

    check_fields, check_rows = read_register(
        OUTPUT_FILE
    )

    check = index_by_code(check_rows)

    if check_fields != original_fields:
        raise ValueError(
            "Output columns differ from expected schema."
        )

    if len(check_rows) != 19:
        raise ValueError(
            "Output record count is incorrect."
        )

    for code in BATCH1_CODES:

        for field in MANUAL_FIELDS:

            expected = consolidated[code].get(field, "")
            actual = check[code].get(field, "")

            if expected != actual:

                raise ValueError(
                    f"Read-after-write failure: {code}, {field}"
                )

    # --------------------------------------------------------
    # Generate report
    # --------------------------------------------------------

    report = []

    report.append("=" * 72)
    report.append("SCRIPT 47: CONSOLIDATION REPORT")
    report.append("=" * 72)

    report.append(
        f"Generated: {datetime.now().isoformat(timespec='seconds')}"
    )

    report.append("")

    report.append("INPUTS")
    report.append("-" * 72)
    report.append(str(ORIGINAL_FILE))
    report.append(str(BATCH1_FILE))
    report.append(str(BATCH5_FILE))

    report.append("")

    report.append("CONSOLIDATION METHOD")
    report.append("-" * 72)
    report.append(
        "Batch 5 used as the base register."
    )
    report.append(
        "Only the 17 manual-review fields were considered."
    )
    report.append(
        "Only four UAE records were eligible for restoration."
    )
    report.append(
        "Batch 1 values were copied only where Batch 5 retained "
        "the original value."
    )
    report.append(
        "No conflicting values were detected."
    )

    report.append("")

    report.append("MERGE SUMMARY")
    report.append("-" * 72)
    report.append(
        f"Fields restored from Batch 1: {total_copied}"
    )
    report.append(
        f"Fields already present in Batch 5: "
        f"{total_already_present}"
    )
    report.append(
        f"Fields unchanged in Batch 1: "
        f"{total_unchanged_in_batch1}"
    )
    report.append(
        f"Conflicts: {len(conflicts)}"
    )

    report.append("")

    report.append("RECORDS RESTORED")
    report.append("-" * 72)

    for code in BATCH1_CODES:
        report.append(code)

    report.append("")

    report.append("VALIDATION")
    report.append("-" * 72)
    report.append("Records: 19")
    report.append("Columns: 57")
    report.append("Operational inclusion: PENDING")
    report.append("Coordinate approvals: NONE")
    report.append("Other 15 records: unchanged from Batch 5")
    report.append("Read-after-write verification: PASSED")

    report.append("")

    report.append("OUTPUT FILES")
    report.append("-" * 72)
    report.append(str(OUTPUT_FILE))
    report.append(str(LOG_FILE))

    report.append("")
    report.append(
        "Original and Batch 1-5 checkpoint files were not modified."
    )

    report.append("=" * 72)

    REPORT_FILE.write_text(
        "\n".join(report),
        encoding="utf-8"
    )

    # --------------------------------------------------------
    # Terminal summary
    # --------------------------------------------------------

    print("\n" + "=" * 72)
    print("SCRIPT 47 COMPLETED SUCCESSFULLY")
    print("=" * 72)

    print("\nRecords:", len(check_rows))
    print("Columns:", len(check_fields))

    print("Fields restored:", total_copied)

    print(
        "Fields already present:",
        total_already_present
    )

    print(
        "Fields unchanged in Batch 1:",
        total_unchanged_in_batch1
    )

    print("Conflicts:", len(conflicts))

    print("\nOperational inclusion: PENDING")
    print("Coordinate approvals: NONE")

    print("\nCONSOLIDATED MASTER:")
    print(OUTPUT_FILE)

    print("\nMERGE LOG:")
    print(LOG_FILE)

    print("\nREPORT:")
    print(REPORT_FILE)

    print("\nAll original checkpoint files preserved.")

    print("=" * 72)


if __name__ == "__main__":
    main()
