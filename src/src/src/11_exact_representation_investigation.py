
from pathlib import Path
import pandas as pd
import numpy as np

# ============================================================
# SCRIPT 11
# EXACT SCHEDULE REPRESENTATION INVESTIGATION
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    ROOT / "data" / "processed"
    / "06_integrated_schedule_vessel_port.csv"
)

REVIEW_FILE = (
    ROOT / "outputs" / "tables"
    / "09d_overlap_investigation_classification.csv"
)

OUTPUT_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------
# 1. LOAD DATA
# ------------------------------------------------------------

schedule = pd.read_csv(INPUT_FILE, low_memory=False)

print("\n" + "=" * 85)
print("SCRIPT 11: EXACT REPRESENTATION INVESTIGATION")
print("=" * 85)

print(f"\nSchedule dimensions: {schedule.shape}")

# Preserve the original CSV row position.
# This is a 1-based data-row position, excluding the header.
schedule["Script11_Source_Row"] = np.arange(1, len(schedule) + 1)


# ------------------------------------------------------------
# 2. STANDARDIZE COLUMN NAMES
# ------------------------------------------------------------

def find_column(data, possible_names, required=True):
    """
    Find a column using case-insensitive matching.
    """

    lookup = {
        str(col).strip().lower(): col
        for col in data.columns
    }

    for name in possible_names:
        key = name.strip().lower()

        if key in lookup:
            return lookup[key]

    if required:
        raise KeyError(
            f"Could not find any of these columns: {possible_names}\n"
            f"Available columns:\n{list(data.columns)}"
        )

    return None


column_map = {
    "IMO": find_column(
        schedule,
        ["IMO Number", "vesselIMO", "vesselIMONumber", "IMO"]
    ),

    "Vessel_Name": find_column(
        schedule,
        ["Vessel Name", "vesselName"],
        required=False
    ),

    "Port_Name": find_column(
        schedule,
        ["portName", "Port Name", "Port"],
        required=False
    ),

    "LOCODE": find_column(
        schedule,
        ["UNLocationCode", "UN Location Code", "LOCODE"],
        required=False
    ),

    "Service": find_column(
    schedule,
    [
        "Carrier Service Code",
        "Carrier Code/Service",
        "carrierCode",
        "Service",
        "Carrier Service",
        "Carrier Service Name",
    ],
    required=False
),

    "Import_Voyage": find_column(
        schedule,
        ["Import Voyage Number", "Import Voyage", "importVoyageNumber"],
        required=False
    ),

    "Export_Voyage": find_column(
        schedule,
        ["Export Voyage Number", "Export Voyage", "exportVoyageNumber"],
        required=False
    ),

    "Planned_Arrival": find_column(
        schedule,
        ["Planned Arrival", "ARRI_PLN"],
        required=False
    ),

    "Planned_Departure": find_column(
        schedule,
        ["Planned Departure", "DEPA_PLN"],
        required=False
    ),

    "Estimated_Arrival": find_column(
        schedule,
        ["Estimated Arrival", "ARRI_EST"],
        required=False
    ),

    "Estimated_Departure": find_column(
        schedule,
        ["Estimated Departure", "DEPA_EST"],
        required=False
    ),

    "Actual_Arrival": find_column(
        schedule,
        ["Actual Arrival", "ARRI_ACT"],
        required=False
    ),

    "Actual_Departure": find_column(
        schedule,
        ["Actual Departure", "DEPA_ACT"],
        required=False
    ),
}

print("\nCOLUMN MAPPING")
for logical_name, source_name in column_map.items():
    print(f"{logical_name:22s}: {source_name}")


# ------------------------------------------------------------
# 3. CREATE STANDARDIZED INVESTIGATION DATASET
# ------------------------------------------------------------

data = pd.DataFrame()

data["Source_Row_Number"] = schedule["Script11_Source_Row"]

data["IMO"] = (
    schedule[column_map["IMO"]]
    .astype("string")
    .str.strip()
    .str.replace(r"\.0$", "", regex=True)
)

optional_fields = [
    "Vessel_Name",
    "Port_Name",
    "LOCODE",
    "Service",
    "Import_Voyage",
    "Export_Voyage",
]

for field in optional_fields:
    source_col = column_map[field]

    if source_col is not None:
        data[field] = (
            schedule[source_col]
            .astype("string")
            .str.strip()
            .replace("", pd.NA)
        )
    else:
        data[field] = pd.NA


# ------------------------------------------------------------
# 4. NORMALIZE TIMESTAMPS TO UTC
# ------------------------------------------------------------

timestamp_fields = [
    "Planned_Arrival",
    "Planned_Departure",
    "Estimated_Arrival",
    "Estimated_Departure",
    "Actual_Arrival",
    "Actual_Departure",
]

for field in timestamp_fields:

    source_col = column_map[field]

    if source_col is None:
        data[field + "_UTC"] = pd.NaT
        continue

    data[field + "_UTC"] = pd.to_datetime(
        schedule[source_col],
        errors="coerce",
        utc=True
    )


# ------------------------------------------------------------
# 5. NORMALIZE TEXT FOR COMPARISON
# ------------------------------------------------------------

text_fields = [
    "IMO",
    "Port_Name",
    "LOCODE",
    "Service",
    "Import_Voyage",
    "Export_Voyage",
]

for field in text_fields:
    data[field] = (
        data[field]
        .astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )


# ------------------------------------------------------------
# 6. DEFINE EXACT REPRESENTATION SIGNATURE
# ------------------------------------------------------------

# Service is intentionally excluded from the signature.
# This allows us to detect the same apparent port call
# represented under different service codes.

signature_fields = [
    "IMO",
    "Port_Name",
    "LOCODE",
    "Import_Voyage",
    "Export_Voyage",
] + [
    field + "_UTC"
    for field in timestamp_fields
]

# Only records with all signature fields available are eligible.
eligible = data.dropna(
    subset=signature_fields
).copy()

print("\nELIGIBILITY")
print(f"Total schedule records: {len(data)}")
print(f"Records with complete signature: {len(eligible)}")
print(
    "Records excluded due to incomplete signature:",
    len(data) - len(eligible)
)


# ------------------------------------------------------------
# 7. IDENTIFY EXACT REPRESENTATION GROUPS
# ------------------------------------------------------------

group_sizes = (
    eligible
    .groupby(signature_fields, dropna=False)
    .size()
    .reset_index(name="Group_Size")
)

duplicate_groups = group_sizes[
    group_sizes["Group_Size"] > 1
].copy()

print("\nEXACT REPRESENTATION GROUPS")
print(f"Groups identified: {len(duplicate_groups)}")
print(
    "Records involved:",
    duplicate_groups["Group_Size"].sum()
    if not duplicate_groups.empty else 0
)

# Attach group IDs to individual source records.
if not duplicate_groups.empty:

    duplicate_groups = duplicate_groups.reset_index(drop=True)

    duplicate_groups["Candidate_Group_ID"] = [
        f"EXACT_{i:03d}"
        for i in range(1, len(duplicate_groups) + 1)
    ]

    candidates = eligible.merge(
        duplicate_groups[
            signature_fields + [
                "Group_Size",
                "Candidate_Group_ID"
            ]
        ],
        on=signature_fields,
        how="inner"
    )

else:

    candidates = pd.DataFrame(
        columns=list(eligible.columns)
        + ["Group_Size", "Candidate_Group_ID"]
    )


# ------------------------------------------------------------
# 8. CLASSIFY EACH CANDIDATE GROUP
# ------------------------------------------------------------

group_classifications = []

for group_id, group in candidates.groupby("Candidate_Group_ID"):

    services = (
        group["Service"]
        .dropna()
        .unique()
        .tolist()
    )

    import_voyages = (
        group["Import_Voyage"]
        .dropna()
        .unique()
        .tolist()
    )

    export_voyages = (
        group["Export_Voyage"]
        .dropna()
        .unique()
        .tolist()
    )

    source_rows = sorted(
        group["Source_Row_Number"].astype(int).tolist()
    )

    if len(services) > 1:
        classification = (
            "PROBABLE_DUPLICATE_REPRESENTATION_DIFFERENT_SERVICE"
        )

    elif len(services) == 1:
        classification = (
            "PROBABLE_DUPLICATE_REPRESENTATION_SAME_SERVICE"
        )

    else:
        classification = "UNRESOLVED_SERVICE_INFORMATION"

    group_classifications.append({
        "Candidate_Group_ID": group_id,
        "IMO": group["IMO"].iloc[0],
        "Vessel_Name": (
            group["Vessel_Name"].dropna().iloc[0]
            if group["Vessel_Name"].notna().any()
            else pd.NA
        ),
        "Port_Name": group["Port_Name"].iloc[0],
        "LOCODE": group["LOCODE"].iloc[0],
        "Group_Size": len(group),
        "Unique_Service_Count": len(services),
        "Services": " | ".join(map(str, services)),
        "Import_Voyages": " | ".join(map(str, import_voyages)),
        "Export_Voyages": " | ".join(map(str, export_voyages)),
        "Source_Rows": " | ".join(map(str, source_rows)),
        "Investigation_Classification": classification,
        "Resolution_Status": "REQUIRES_MANUAL_REVIEW",
    })

group_summary = pd.DataFrame(group_classifications)


# ------------------------------------------------------------
# 9. CHECK IDENTICAL SERVICE AND VOYAGE REPRESENTATIONS
# ------------------------------------------------------------

if not candidates.empty:

    candidates["Service_Voyage_Combination"] = (
        candidates["Service"].fillna("<MISSING>")
        + "|"
        + candidates["Import_Voyage"].fillna("<MISSING>")
        + "|"
        + candidates["Export_Voyage"].fillna("<MISSING>")
    )

    service_voyage_counts = (
        candidates
        .groupby(
            ["Candidate_Group_ID", "Service_Voyage_Combination"],
            dropna=False
        )
        .size()
        .reset_index(name="Same_Service_Voyage_Record_Count")
    )

    candidates = candidates.merge(
        service_voyage_counts,
        on=[
            "Candidate_Group_ID",
            "Service_Voyage_Combination"
        ],
        how="left"
    )

    candidates["Same_Service_Voyage_Representation"] = (
        candidates["Same_Service_Voyage_Record_Count"] > 1
    )


# ------------------------------------------------------------
# 10. CHECK PREVIOUSLY INVESTIGATED VESSELS
# ------------------------------------------------------------

# This is a vessel-level cross-reference only.
# It does NOT establish that the exact source records overlap.

previously_reviewed_imos = {
    "9235531",
    "9263320",
    "9332975",
    "9202259",
    "9235567",
}

if not candidates.empty:

    candidates["Vessel_Reviewed_In_Script09D"] = (
        candidates["IMO"].isin(previously_reviewed_imos)
    )

    group_summary["Vessel_Reviewed_In_Script09D"] = (
        group_summary["IMO"].isin(previously_reviewed_imos)
    )


# ------------------------------------------------------------
# 11. CREATE SOURCE-ROW REVIEW TABLE
# ------------------------------------------------------------

review_columns = [
    "Candidate_Group_ID",
    "Source_Row_Number",
    "IMO",
    "Vessel_Name",
    "Port_Name",
    "LOCODE",
    "Service",
    "Import_Voyage",
    "Export_Voyage",
] + [
    field + "_UTC"
    for field in timestamp_fields
]

if not candidates.empty:

    source_row_review = candidates[
        review_columns
    ].copy()

    source_row_review = source_row_review.sort_values(
        ["Candidate_Group_ID", "Source_Row_Number"]
    )

else:
    source_row_review = pd.DataFrame(columns=review_columns)


# ------------------------------------------------------------
# 12. CREATE FIELD-BY-FIELD COMPARISON
# ------------------------------------------------------------

comparison_rows = []

for group_id, group in candidates.groupby("Candidate_Group_ID"):

    fields_to_compare = [
        "IMO",
        "Vessel_Name",
        "Port_Name",
        "LOCODE",
        "Service",
        "Import_Voyage",
        "Export_Voyage",
    ] + [
        field + "_UTC"
        for field in timestamp_fields
    ]

    for field in fields_to_compare:

        values = (
            group[field]
            .astype("string")
            .fillna("<MISSING>")
            .unique()
            .tolist()
        )

        comparison_rows.append({
            "Candidate_Group_ID": group_id,
            "Field": field,
            "Unique_Value_Count": len(values),
            "Values": " || ".join(values),
            "Field_Matches_Exactly": len(values) == 1,
        })

field_comparison = pd.DataFrame(comparison_rows)


# ------------------------------------------------------------
# 13. ATTACH SCRIPT 09D CASE CROSS-REFERENCE
# ------------------------------------------------------------

if REVIEW_FILE.exists():

    previous_review = pd.read_csv(
        REVIEW_FILE,
        low_memory=False
    )

    print("\nSCRIPT 09D CROSS-REFERENCE")
    print("Columns:", list(previous_review.columns))

    # We use IMO only for a vessel-level reference.
    # No claim of exact source-row overlap is made here.

    if "IMO" in previous_review.columns:

        previous_review["IMO_Normalized"] = (
            previous_review["IMO"]
            .astype("string")
            .str.strip()
            .str.replace(r"\.0$", "", regex=True)
        )

        previous_review = previous_review.drop_duplicates(
            subset=["IMO_Normalized"]
        )

        review_lookup = previous_review[
            ["IMO_Normalized"]
        ].copy()

        if "Case_ID" in previous_review.columns:
            review_lookup["Previous_Case_ID"] = (
                previous_review["Case_ID"]
            )

        if "Classification" in previous_review.columns:
            review_lookup["Previous_Classification"] = (
                previous_review["Classification"]
            )

        if not group_summary.empty:

            group_summary = group_summary.merge(
                review_lookup,
                left_on="IMO",
                right_on="IMO_Normalized",
                how="left"
            )

            group_summary["Previous_09D_Case_Found"] = (
                group_summary["Previous_Case_ID"].notna()
                if "Previous_Case_ID" in group_summary.columns
                else group_summary["IMO"].isin(
                    previously_reviewed_imos
                )
            )

    else:
        print("IMO field not found in Script 09D file.")

else:
    print("\nScript 09D review file not found.")


# ------------------------------------------------------------
# 14. FINAL GROUP REVIEW STATUS
# ------------------------------------------------------------

if not group_summary.empty:

    group_summary["Recommended_Action"] = np.where(
        group_summary["Investigation_Classification"].str.contains(
            "PROBABLE_DUPLICATE",
            na=False
        ),
        "MANUAL_SOURCE_VERIFICATION_BEFORE_ANY_DEDUPLICATION",
        "RETAIN_AND_INVESTIGATE"
    )


# ------------------------------------------------------------
# 15. SAVE OUTPUTS
# ------------------------------------------------------------

group_summary.to_csv(
    OUTPUT_DIR / "11_exact_representation_group_summary.csv",
    index=False
)

source_row_review.to_csv(
    OUTPUT_DIR / "11_exact_representation_source_rows.csv",
    index=False
)

field_comparison.to_csv(
    OUTPUT_DIR / "11_exact_representation_field_comparison.csv",
    index=False
)

candidates.to_csv(
    OUTPUT_DIR / "11_exact_representation_candidate_records.csv",
    index=False
)


# ------------------------------------------------------------
# 16. GENERATE REPORT
# ------------------------------------------------------------

report_path = (
    REPORT_DIR / "11_exact_representation_investigation_report.txt"
)

with open(report_path, "w", encoding="utf-8") as report:

    report.write("=" * 85 + "\n")
    report.write("SCRIPT 11: EXACT REPRESENTATION INVESTIGATION\n")
    report.write("=" * 85 + "\n\n")

    report.write(f"Input records: {len(schedule)}\n")
    report.write(f"Eligible records: {len(eligible)}\n")
    report.write(
        f"Exact representation groups: {len(duplicate_groups)}\n"
    )

    report.write(
        f"Candidate records: {len(candidates)}\n\n"
    )

    report.write("GROUP CLASSIFICATION SUMMARY\n")
    report.write("-" * 85 + "\n")

    if not group_summary.empty:

        report.write(
            group_summary[
                "Investigation_Classification"
            ].value_counts().to_string()
        )

        report.write("\n\nDETAILED GROUP SUMMARY\n")
        report.write("-" * 85 + "\n")

        report.write(
            group_summary.to_string(index=False)
        )

    else:
        report.write(
            "No exact representation groups identified.\n"
        )

    report.write("\n\nMETHODOLOGICAL NOTES\n")
    report.write("-" * 85 + "\n")

    report.write(
        "1. Exact groups are identified using IMO, port name, "
        "LOCODE, import/export voyage and all six timestamps.\n"
    )

    report.write(
        "2. Service code is excluded from the group signature "
        "so that the same apparent call under different services "
        "can be identified.\n"
    )

    report.write(
        "3. Timestamp comparisons are performed after conversion "
        "to UTC.\n"
    )

    report.write(
        "4. Records with incomplete signature fields are excluded "
        "from exact-group detection, but are not deleted from the "
        "source dataset.\n"
    )

    report.write(
        "5. A probable duplicate representation is not proof of "
        "an erroneous source record.\n"
    )

    report.write(
        "6. No original records were deleted or modified.\n"
    )


# ------------------------------------------------------------
# 17. TERMINAL SUMMARY
# ------------------------------------------------------------

print("\n" + "=" * 85)
print("SCRIPT 11 COMPLETED")
print("=" * 85)

print("\nINVESTIGATION SUMMARY")
print(f"Total schedule records: {len(schedule)}")
print(f"Eligible records: {len(eligible)}")
print(f"Exact representation groups: {len(duplicate_groups)}")
print(f"Candidate records: {len(candidates)}")

if not group_summary.empty:

    print("\nCLASSIFICATION SUMMARY")
    print(
        group_summary[
            "Investigation_Classification"
        ].value_counts().to_string()
    )

    print("\nCANDIDATE GROUPS")
    display_columns = [
        "Candidate_Group_ID",
        "IMO",
        "Port_Name",
        "LOCODE",
        "Group_Size",
        "Services",
        "Investigation_Classification",
    ]

    print(
        group_summary[display_columns]
        .to_string(index=False)
    )

print("\nOUTPUT FILES")

print(
    OUTPUT_DIR
    / "11_exact_representation_group_summary.csv"
)

print(
    OUTPUT_DIR
    / "11_exact_representation_source_rows.csv"
)

print(
    OUTPUT_DIR
    / "11_exact_representation_field_comparison.csv"
)

print(
    OUTPUT_DIR
    / "11_exact_representation_candidate_records.csv"
)

print(report_path)

print("\nNo original records were deleted or modified.")