
from pathlib import Path
import re
import warnings

import numpy as np
import pandas as pd


# ============================================================
# SCRIPT 15B
# SCHEDULE DUPLICATE-REPRESENTATION RESOLUTION
#
# Purpose:
# 1. Load source-verified representation candidates from Script 12.
# 2. Reconstruct groups using operational fields.
# 3. Verify identical operational information and different
#    service identities.
# 4. Create a sequence-ready analytical Schedule dataset.
# 5. Preserve the original records and full source-row mapping.
# 6. Recalculate transitions before and after analytical resolution.
#
# IMPORTANT:
# - Original records are never deleted or overwritten.
# - One representative is selected only for sequence analysis.
# - Service-level information remains in the full annotated data.
# - No timestamps are corrected.
# ============================================================


# ------------------------------------------------------------
# 1. PATHS
# ------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

PROCESSED = ROOT / "data" / "processed"
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"

TABLES.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

SCHEDULE_FILE = (
    PROCESSED / "13_final_consolidated_schedule.csv"
)

VERIFICATION_FILE = (
    TABLES / "12_source_row_verification.csv"
)

# Expected number of source-verified candidate records from Script 12.
EXPECTED_CANDIDATE_RECORDS = 14

# Expected group count based on the seven groups identified earlier.
EXPECTED_GROUPS = 7


# ------------------------------------------------------------
# 2. HELPER FUNCTIONS
# ------------------------------------------------------------

def normalize_column_name(value):
    return re.sub(
        r"[^a-z0-9]",
        "",
        str(value).lower()
    )


def find_column(df, candidates, required=True):
    lookup = {
        normalize_column_name(col): col
        for col in df.columns
    }

    for candidate in candidates:
        key = normalize_column_name(candidate)

        if key in lookup:
            return lookup[key]

    if required:
        raise KeyError(
            f"Could not find any of these columns: {candidates}\n"
            f"Available columns:\n{df.columns.tolist()}"
        )

    return None


def normalize_text(series):
    return (
        series.astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )


def normalize_imo(series):
    result = normalize_text(series)
    return result.str.replace(r"\.0$", "", regex=True)


def normalize_locode(series):
    return normalize_text(series)


def parse_utc(series):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pd.to_datetime(
            series,
            errors="coerce",
            utc=True
        )


def normalized_timestamp_key(series):
    """
    Convert timestamps to consistent UTC strings for matching.

    Missing timestamps receive a stable marker.
    """
    parsed = parse_utc(series)

    result = parsed.dt.strftime("%Y-%m-%dT%H:%M:%S%z")

    return result.fillna("<MISSING>")


def safe_string(value):
    if pd.isna(value):
        return "<MISSING>"

    return str(value).strip().upper()


# ------------------------------------------------------------
# 3. LOAD INPUT DATA
# ------------------------------------------------------------

print("\n" + "=" * 75)
print("SCRIPT 15B: SCHEDULE DUPLICATE-REPRESENTATION RESOLUTION")
print("=" * 75)

if not SCHEDULE_FILE.exists():
    raise FileNotFoundError(SCHEDULE_FILE)

if not VERIFICATION_FILE.exists():
    raise FileNotFoundError(VERIFICATION_FILE)

schedule = pd.read_csv(
    SCHEDULE_FILE,
    low_memory=False
)

verification = pd.read_csv(
    VERIFICATION_FILE,
    low_memory=False
)

print("\nINPUT DATA")
print("-" * 75)
print("Schedule shape:", schedule.shape)
print("Source verification shape:", verification.shape)


# ------------------------------------------------------------
# 4. IDENTIFY REQUIRED COLUMNS
# ------------------------------------------------------------

source_row_col = find_column(
    schedule,
    [
        "Schedule_Source_Row",
        "Source_Row_Number",
        "Source_Row",
    ],
)

imo_col = find_column(
    schedule,
    [
        "IMO_Normalised",
        "IMO_Normalized",
        "IMO Number",
        "IMO",
    ],
)

locode_col = find_column(
    schedule,
    [
        "UNLOCODE_Normalised",
        "UNLOCODE_Normalized",
        "UN Location Code",
        "UN/LOCODE",
        "LOCODE",
    ],
)

port_col = find_column(
    schedule,
    [
        "Port",
        "Source_Port",
        "Port_Name",
    ],
)

service_code_col = find_column(
    schedule,
    [
        "Carrier Service Code",
        "Service Code",
        "Service_Code",
    ],
)

service_name_col = find_column(
    schedule,
    [
        "Carrier Service Name",
        "Service Name",
        "Service_Name",
    ],
    required=False,
)

import_voyage_col = find_column(
    schedule,
    [
        "Import Voyage Number",
        "Import Voyage",
        "Import_Voyage",
    ],
    required=False,
)

export_voyage_col = find_column(
    schedule,
    [
        "Export Voyage Number",
        "Export Voyage",
        "Export_Voyage",
    ],
    required=False,
)

timestamp_candidates = {
    "Planned_Arrival": [
        "Planned Arrival",
        "Planned_Arrival",
    ],
    "Planned_Departure": [
        "Planned Departure",
        "Planned_Departure",
    ],
    "Estimated_Arrival": [
        "Estimated Arrival",
        "Estimated_Arrival",
    ],
    "Estimated_Departure": [
        "Estimated Departure",
        "Estimated_Departure",
    ],
    "Actual_Arrival": [
        "Actual Arrival",
        "Actual_Arrival",
    ],
    "Actual_Departure": [
        "Actual Departure",
        "Actual_Departure",
    ],
}

timestamp_columns = {}

for label, candidates in timestamp_candidates.items():
    timestamp_columns[label] = find_column(
        schedule,
        candidates
    )

verification_row_col = find_column(
    verification,
    [
        "Source_Row_Number",
        "Source_Row",
        "Schedule_Source_Row",
    ],
)

verification_status_col = find_column(
    verification,
    [
        "Verification_Status",
        "Source_Verification_Status",
        "Status",
    ],
)

print("\nIDENTIFIED COLUMNS")
print("-" * 75)

for label, col in [
    ("Source row", source_row_col),
    ("IMO", imo_col),
    ("LOCODE", locode_col),
    ("Port", port_col),
    ("Service code", service_code_col),
    ("Service name", service_name_col),
    ("Import voyage", import_voyage_col),
    ("Export voyage", export_voyage_col),
]:
    print(f"{label}: {col}")

for label, col in timestamp_columns.items():
    print(f"{label}: {col}")


# ------------------------------------------------------------
# 5. VALIDATE SCRIPT 12 SOURCE VERIFICATION
# ------------------------------------------------------------

verification = verification.copy()

verification["_Source_Row"] = pd.to_numeric(
    verification[verification_row_col],
    errors="coerce"
)

if verification["_Source_Row"].isna().any():
    raise ValueError(
        "Some source row numbers in Script 12 verification "
        "could not be converted to integers."
    )

verification["_Source_Row"] = (
    verification["_Source_Row"].astype(int)
)

verification["_Verification_Status"] = (
    verification[verification_status_col]
    .astype("string")
    .str.strip()
    .str.upper()
)

valid_statuses = (
    verification["_Verification_Status"]
    == "ALL_CHECKED_FIELDS_MATCH"
)

if not valid_statuses.all():
    raise ValueError(
        "Not all Script 12 candidate rows passed source verification. "
        "Review 12_source_row_verification.csv before continuing."
    )

candidate_source_rows = set(
    verification["_Source_Row"].tolist()
)

if len(candidate_source_rows) != EXPECTED_CANDIDATE_RECORDS:
    raise ValueError(
        f"Expected {EXPECTED_CANDIDATE_RECORDS} unique source rows, "
        f"but found {len(candidate_source_rows)}."
    )

schedule["_Source_Row_15B"] = pd.to_numeric(
    schedule[source_row_col],
    errors="coerce"
)

schedule["_Source_Row_15B"] = (
    schedule["_Source_Row_15B"].astype("Int64")
)

schedule["Source_Verified_Candidate_15B"] = (
    schedule["_Source_Row_15B"].isin(candidate_source_rows)
)

candidate_records = schedule[
    schedule["Source_Verified_Candidate_15B"]
].copy()

if len(candidate_records) != EXPECTED_CANDIDATE_RECORDS:
    raise ValueError(
        "The candidate source rows from Script 12 do not match "
        "the Schedule dataset. Check source-row provenance."
    )

print("\nSOURCE VERIFICATION")
print("-" * 75)
print("Verified source rows:", len(candidate_source_rows))
print("Matching Schedule records:", len(candidate_records))


# ------------------------------------------------------------
# 6. BUILD OPERATIONAL SIGNATURE
# ------------------------------------------------------------

# These fields define the operational event.
# Service code and service name are deliberately excluded.
#
# The hypothesis being tested:
# Two records describe the same port call if their vessel,
# port, voyage and all six timestamp fields match.

candidate_records = candidate_records.copy()

candidate_records["_IMO_Key"] = normalize_imo(
    candidate_records[imo_col]
)

candidate_records["_LOCODE_Key"] = normalize_locode(
    candidate_records[locode_col]
)

candidate_records["_Port_Key"] = normalize_text(
    candidate_records[port_col]
)

if import_voyage_col is not None:
    candidate_records["_Import_Voyage_Key"] = normalize_text(
        candidate_records[import_voyage_col]
    )
else:
    candidate_records["_Import_Voyage_Key"] = "<COLUMN_NOT_AVAILABLE>"

if export_voyage_col is not None:
    candidate_records["_Export_Voyage_Key"] = normalize_text(
        candidate_records[export_voyage_col]
    )
else:
    candidate_records["_Export_Voyage_Key"] = "<COLUMN_NOT_AVAILABLE>"

signature_columns = [
    "_IMO_Key",
    "_LOCODE_Key",
    "_Port_Key",
    "_Import_Voyage_Key",
    "_Export_Voyage_Key",
]

for label, original_col in timestamp_columns.items():

    key_col = f"_{label}_Key"

    candidate_records[key_col] = normalized_timestamp_key(
        candidate_records[original_col]
    )

    signature_columns.append(key_col)


# Each signature group should contain two records.
grouped = candidate_records.groupby(
    signature_columns,
    dropna=False,
    sort=True,
)

group_summaries = []
group_members = []

group_number = 0

for signature, group in grouped:

    if len(group) < 2:
        raise ValueError(
            "A source-verified candidate did not form a duplicate "
            "operational group. Review its fields."
        )

    if len(group) != 2:
        raise ValueError(
            "A candidate operational signature contains more than "
            "two records. Manual review is required; no records "
            "will be consolidated automatically."
        )

    group_number += 1

    group_id = f"15B_GROUP_{group_number:03d}"

    group = group.sort_values(
        "_Source_Row_15B",
        kind="stable"
    ).copy()

    service_codes = (
        group[service_code_col]
        .astype("string")
        .fillna("<MISSING>")
        .str.strip()
        .unique()
        .tolist()
    )

    if len(service_codes) < 2:
        raise ValueError(
            f"{group_id} does not contain two distinct service codes. "
            "Review the source records."
        )

    representative_row = int(
        group.iloc[0]["_Source_Row_15B"]
    )

    group_rows = group["_Source_Row_15B"].astype(int).tolist()

    # First source row is selected deterministically.
    # This is not a claim that its service identity is superior.
    for _, member in group.iterrows():

        source_row = int(member["_Source_Row_15B"])

        group_members.append({
            "Representation_Group_ID": group_id,
            "IMO": member[imo_col],
            "Vessel_Name": member.get(
                "Vessel Name",
                member.get("vesselName", pd.NA)
            ),
            "LOCODE": member[locode_col],
            "Port": member[port_col],
            "Source_Row": source_row,
            "Service_Code": member[service_code_col],
            "Service_Name": (
                member[service_name_col]
                if service_name_col is not None
                else pd.NA
            ),
            "Import_Voyage": (
                member[import_voyage_col]
                if import_voyage_col is not None
                else pd.NA
            ),
            "Export_Voyage": (
                member[export_voyage_col]
                if export_voyage_col is not None
                else pd.NA
            ),
            "Representative_Source_Row": representative_row,
            "Is_Sequence_Representative": (
                source_row == representative_row
            ),
            "Analytical_Treatment": (
                "RETAIN_FOR_SEQUENCE_ANALYSIS"
                if source_row == representative_row
                else "EXCLUDE_FROM_SEQUENCE_VIEW_ONLY"
            ),
        })

    first = group.iloc[0]

    group_summaries.append({
        "Representation_Group_ID": group_id,
        "IMO": first[imo_col],
        "Vessel_Name": first.get(
            "Vessel Name",
            first.get("vesselName", pd.NA)
        ),
        "LOCODE": first[locode_col],
        "Port": first[port_col],
        "Source_Rows": ";".join(map(str, group_rows)),
        "Service_Codes": ";".join(map(str, service_codes)),
        "Number_Of_Source_Records": len(group),
        "Number_Of_Distinct_Service_Codes": len(service_codes),
        "Operational_Signature_Matches": True,
        "Different_Service_Identity": True,
        "Representative_Source_Row": representative_row,
        "Classification": (
            "SOURCE_VERIFIED_DUPLICATE_REPRESENTATION_"
            "DIFFERENT_SERVICE_CODE"
        ),
    })


group_summary = pd.DataFrame(group_summaries)
group_mapping = pd.DataFrame(group_members)

if len(group_summary) != EXPECTED_GROUPS:
    raise ValueError(
        f"Expected {EXPECTED_GROUPS} groups, "
        f"but reconstructed {len(group_summary)}. "
        "Do not continue until this discrepancy is investigated."
    )

if len(group_mapping) != EXPECTED_CANDIDATE_RECORDS:
    raise ValueError(
        "Group mapping does not contain the expected number "
        "of source records."
    )

print("\nOPERATIONAL SIGNATURE RESULTS")
print("-" * 75)
print("Representation groups:", len(group_summary))
print("Source records in groups:", len(group_mapping))
print("\nGroup summary:")
print(
    group_summary[
        [
            "Representation_Group_ID",
            "IMO",
            "LOCODE",
            "Source_Rows",
            "Service_Codes",
            "Classification",
        ]
    ].to_string(index=False)
)


# ------------------------------------------------------------
# 7. ANNOTATE FULL SCHEDULE WITHOUT DELETING RECORDS
# ------------------------------------------------------------

schedule_annotated = schedule.copy()

schedule_annotated["Representation_Group_ID_15B"] = pd.NA
schedule_annotated["Representation_Class_15B"] = pd.NA
schedule_annotated["Sequence_Representative_15B"] = True
schedule_annotated["Sequence_Exclusion_Reason_15B"] = pd.NA

group_id_by_source = {}
representative_by_source = {}

for _, row in group_mapping.iterrows():

    source_row = int(row["Source_Row"])

    group_id_by_source[source_row] = row[
        "Representation_Group_ID"
    ]

    representative_by_source[source_row] = bool(
        row["Is_Sequence_Representative"]
    )


for index, row in schedule_annotated.iterrows():

    source_value = row["_Source_Row_15B"]

    if pd.isna(source_value):
        continue

    source_row = int(source_value)

    if source_row not in group_id_by_source:
        continue

    schedule_annotated.at[
        index,
        "Representation_Group_ID_15B"
    ] = group_id_by_source[source_row]

    schedule_annotated.at[
        index,
        "Representation_Class_15B"
    ] = (
        "SOURCE_VERIFIED_DUPLICATE_REPRESENTATION_"
        "DIFFERENT_SERVICE_CODE"
    )

    is_representative = representative_by_source[source_row]

    schedule_annotated.at[
        index,
        "Sequence_Representative_15B"
    ] = is_representative

    if not is_representative:
        schedule_annotated.at[
            index,
            "Sequence_Exclusion_Reason_15B"
        ] = (
            "Same operational port call represented under "
            "a different service code; retained in full dataset."
        )


# ------------------------------------------------------------
# 8. CREATE SEQUENCE-READY ANALYTICAL DATASET
# ------------------------------------------------------------

sequence_ready = schedule_annotated[
    schedule_annotated["Sequence_Representative_15B"]
].copy()

# This is a separate analytical view.
# Original schedule_annotated retains all 1,894 records.

expected_sequence_records = (
    len(schedule_annotated) - EXPECTED_GROUPS
)

if len(sequence_ready) != expected_sequence_records:
    raise ValueError(
        f"Expected {expected_sequence_records} sequence records, "
        f"but obtained {len(sequence_ready)}."
    )

print("\nANALYTICAL DATASET")
print("-" * 75)
print("Full annotated Schedule:", len(schedule_annotated))
print("Sequence-ready Schedule:", len(sequence_ready))
print("Records excluded from sequence view:", (
    len(schedule_annotated) - len(sequence_ready)
))


# ------------------------------------------------------------
# 9. RECALCULATE VESSEL TRANSITIONS
# ------------------------------------------------------------

def calculate_transitions(df, dataset_label):

    work = df.copy()

    imo = find_column(
        work,
        [
            "IMO_Normalised",
            "IMO_Normalized",
            "IMO Number",
            "IMO",
        ],
    )

    locode = find_column(
        work,
        [
            "UNLOCODE_Normalised",
            "UNLOCODE_Normalized",
            "UN Location Code",
            "UN/LOCODE",
            "LOCODE",
        ],
    )

    vessel_name = find_column(
        work,
        [
            "Vessel Name",
            "Vessel_Name",
            "vesselName",
        ],
        required=False,
    )

    source_row = find_column(
        work,
        [
            "Schedule_Source_Row",
            "Source_Row_Number",
            "Source_Row",
        ],
    )

    arrival = timestamp_columns["Actual_Arrival"]
    departure = timestamp_columns["Actual_Departure"]

    work["_IMO"] = normalize_imo(work[imo])
    work["_LOCODE"] = normalize_locode(work[locode])
    work["_Arrival_UTC"] = parse_utc(work[arrival])
    work["_Departure_UTC"] = parse_utc(work[departure])

    work["_Source_Row"] = pd.to_numeric(
        work[source_row],
        errors="coerce"
    )

    valid = work[
        work["_IMO"].notna()
        & work["_LOCODE"].notna()
        & work["_Arrival_UTC"].notna()
        & work["_Departure_UTC"].notna()
    ].copy()

    valid = valid.sort_values(
        ["_IMO", "_Arrival_UTC", "_Departure_UTC", "_Source_Row"],
        kind="stable"
    )

    results = []

    for imo_value, group in valid.groupby("_IMO", sort=False):

        group = group.reset_index(drop=True)

        for i in range(len(group) - 1):

            previous = group.iloc[i]
            current = group.iloc[i + 1]

            elapsed = (
                current["_Arrival_UTC"]
                - previous["_Departure_UTC"]
            ).total_seconds() / 3600

            results.append({
                "Dataset": dataset_label,
                "IMO": imo_value,

                "Vessel_Name": (
                    previous[vessel_name]
                    if vessel_name is not None
                    else pd.NA
                ),

                "Previous_Source_Row": previous["_Source_Row"],
                "Current_Source_Row": current["_Source_Row"],

                "Previous_LOCODE": previous["_LOCODE"],
                "Current_LOCODE": current["_LOCODE"],

                "Previous_Departure_UTC": previous["_Departure_UTC"],
                "Current_Arrival_UTC": current["_Arrival_UTC"],

                "Transition_Elapsed_Hours": elapsed,

                "Transition_Type": (
                    "SAME_PORT"
                    if previous["_LOCODE"] == current["_LOCODE"]
                    else "DIFFERENT_PORT"
                ),

                "Negative_Transition": elapsed < 0,
            })

    return pd.DataFrame(results)


transitions_before = calculate_transitions(
    schedule_annotated,
    "Schedule_Before_Resolution"
)

transitions_after = calculate_transitions(
    sequence_ready,
    "Schedule_Sequence_Ready"
)

negative_before = transitions_before[
    transitions_before["Negative_Transition"]
].copy()

negative_after = transitions_after[
    transitions_after["Negative_Transition"]
].copy()

print("\nTRANSITION VALIDATION")
print("-" * 75)
print("Transitions before:", len(transitions_before))
print("Negative transitions before:", len(negative_before))
print("Transitions after:", len(transitions_after))
print("Negative transitions after:", len(negative_after))


# ------------------------------------------------------------
# 10. VALIDATE WHETHER THE SEVEN NEGATIVE TRANSITIONS
#     WERE CAUSED BY THE VERIFIED REPRESENTATION GROUPS
# ------------------------------------------------------------

verified_candidate_pairs = set()

for _, row in group_summary.iterrows():

    source_rows = [
        int(value)
        for value in str(row["Source_Rows"]).split(";")
    ]

    verified_candidate_pairs.add(
        tuple(sorted(source_rows))
    )


negative_pairs_before = set()

for _, row in negative_before.iterrows():

    if pd.isna(row["Previous_Source_Row"]):
        continue

    if pd.isna(row["Current_Source_Row"]):
        continue

    pair = tuple(sorted([
        int(row["Previous_Source_Row"]),
        int(row["Current_Source_Row"]),
    ]))

    negative_pairs_before.add(pair)


negative_pairs_matched = (
    negative_pairs_before & verified_candidate_pairs
)

negative_pairs_unmatched = (
    negative_pairs_before - verified_candidate_pairs
)

validation_summary = pd.DataFrame([
    {
        "Metric": "Original Schedule records",
        "Value": len(schedule_annotated),
    },
    {
        "Metric": "Sequence-ready Schedule records",
        "Value": len(sequence_ready),
    },
    {
        "Metric": "Verified representation groups",
        "Value": len(group_summary),
    },
    {
        "Metric": "Verified representation source records",
        "Value": len(group_mapping),
    },
    {
        "Metric": "Negative transitions before",
        "Value": len(negative_before),
    },
    {
        "Metric": "Negative transitions after",
        "Value": len(negative_after),
    },
    {
        "Metric": "Negative transitions matching verified pairs",
        "Value": len(negative_pairs_matched),
    },
    {
        "Metric": "Negative transitions not matching verified pairs",
        "Value": len(negative_pairs_unmatched),
    },
])


# ------------------------------------------------------------
# 11. OUTPUT FILES
# ------------------------------------------------------------

outputs = {
    "annotated_schedule": (
        PROCESSED
        / "15B_annotated_schedule_all_records.csv"
    ),

    "sequence_ready_schedule": (
        PROCESSED
        / "15B_schedule_sequence_ready.csv"
    ),

    "group_summary": (
        TABLES
        / "15B_duplicate_representation_group_summary.csv"
    ),

    "source_mapping": (
        TABLES
        / "15B_duplicate_representation_source_mapping.csv"
    ),

    "transitions_before": (
        TABLES
        / "15B_transitions_before_resolution.csv"
    ),

    "transitions_after": (
        TABLES
        / "15B_transitions_after_resolution.csv"
    ),

    "negative_before": (
        TABLES
        / "15B_negative_transitions_before.csv"
    ),

    "negative_after": (
        TABLES
        / "15B_negative_transitions_after.csv"
    ),

    "validation_summary": (
        TABLES
        / "15B_validation_summary.csv"
    ),
}

schedule_annotated.to_csv(
    outputs["annotated_schedule"],
    index=False
)

sequence_ready.to_csv(
    outputs["sequence_ready_schedule"],
    index=False
)

group_summary.to_csv(
    outputs["group_summary"],
    index=False
)

group_mapping.to_csv(
    outputs["source_mapping"],
    index=False
)

transitions_before.to_csv(
    outputs["transitions_before"],
    index=False
)

transitions_after.to_csv(
    outputs["transitions_after"],
    index=False
)

negative_before.to_csv(
    outputs["negative_before"],
    index=False
)

negative_after.to_csv(
    outputs["negative_after"],
    index=False
)

validation_summary.to_csv(
    outputs["validation_summary"],
    index=False
)


# ------------------------------------------------------------
# 12. GENERATE REPORT
# ------------------------------------------------------------

report_file = (
    REPORTS
    / "15B_duplicate_representation_resolution_report.txt"
)

with open(report_file, "w", encoding="utf-8") as f:

    f.write("=" * 75 + "\n")
    f.write("SCRIPT 15B: DUPLICATE-REPRESENTATION RESOLUTION REPORT\n")
    f.write("=" * 75 + "\n\n")

    f.write("1. INPUT DATA\n")
    f.write("-" * 75 + "\n")
    f.write(f"Schedule records: {len(schedule)}\n")
    f.write(f"Source-verified candidate records: {len(candidate_records)}\n\n")

    f.write("2. REPRESENTATION GROUPS\n")
    f.write("-" * 75 + "\n")
    f.write(f"Reconstructed groups: {len(group_summary)}\n")
    f.write(f"Source records in groups: {len(group_mapping)}\n\n")
    f.write(group_summary.to_string(index=False))
    f.write("\n\n")

    f.write("3. ANALYTICAL DATASET\n")
    f.write("-" * 75 + "\n")
    f.write(f"Full annotated Schedule: {len(schedule_annotated)}\n")
    f.write(f"Sequence-ready Schedule: {len(sequence_ready)}\n")
    f.write(
        f"Records excluded from sequence view: "
        f"{len(schedule_annotated) - len(sequence_ready)}\n\n"
    )

    f.write("4. TRANSITION VALIDATION\n")
    f.write("-" * 75 + "\n")
    f.write(validation_summary.to_string(index=False))
    f.write("\n\n")

    f.write("5. INTERPRETATION\n")
    f.write("-" * 75 + "\n")
    f.write(
        "Source-verified records with identical operational "
        "signatures and different service codes were grouped.\n"
    )
    f.write(
        "One representative per group was retained in the "
        "sequence-ready analytical dataset.\n"
    )
    f.write(
        "All original Schedule records remain available in the "
        "annotated full dataset.\n"
    )
    f.write(
        "The selected representative is based on the lowest "
        "source-row number, not on service importance.\n"
    )
    f.write(
        "No timestamps were changed and no original records "
        "were deleted.\n"
    )
    f.write(
        "Inter-port elapsed time is not assumed to be sailing time.\n"
    )

    f.write("\n6. OUTPUT FILES\n")
    f.write("-" * 75 + "\n")

    for label, path in outputs.items():
        f.write(f"{label}: {path}\n")

    f.write(f"\nReport: {report_file}\n")


# ------------------------------------------------------------
# 13. FINAL TERMINAL SUMMARY
# ------------------------------------------------------------

print("\n" + "=" * 75)
print("SCRIPT 15B COMPLETED SUCCESSFULLY")
print("=" * 75)

print("\nGROUP SUMMARY")
print("-" * 75)
print(
    group_summary[
        [
            "Representation_Group_ID",
            "IMO",
            "LOCODE",
            "Source_Rows",
            "Service_Codes",
        ]
    ].to_string(index=False)
)

print("\nDATASET SIZES")
print("-" * 75)
print("Full annotated Schedule:", len(schedule_annotated))
print("Sequence-ready Schedule:", len(sequence_ready))

print("\nNEGATIVE TRANSITION CHECK")
print("-" * 75)
print("Before resolution:", len(negative_before))
print("After resolution:", len(negative_after))
print("Matched to verified representation pairs:", len(negative_pairs_matched))
print("Unmatched negative pairs:", len(negative_pairs_unmatched))

print("\nVALIDATION SUMMARY")
print("-" * 75)
print(validation_summary.to_string(index=False))

print("\nOUTPUT FILES")
print("-" * 75)

for label, path in outputs.items():
    print(f"{label}: {path}")

print("\nReport:")
print(report_file)

print("\nOriginal records preserved.")
print("No timestamps corrected.")
print("No original records deleted.")
