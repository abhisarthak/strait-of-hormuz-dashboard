
from pathlib import Path
import pandas as pd
import numpy as np

# ============================================================
# SCRIPT 12
# SOURCE PROVENANCE AND SERVICE-CODE INVESTIGATION
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

RAW_FILE = (
    ROOT / "data" / "raw"
    / "Combined_Port_Schedules.xlsx"
)

INTEGRATED_FILE = (
    ROOT / "data" / "processed"
    / "06_integrated_schedule_vessel_port.csv"
)

CANDIDATE_FILE = (
    ROOT / "outputs" / "tables"
    / "11_exact_representation_candidate_records.csv"
)

GROUP_FILE = (
    ROOT / "outputs" / "tables"
    / "11_exact_representation_group_summary.csv"
)

OUTPUT_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 1. HELPER FUNCTIONS
# ============================================================

def find_column(data, possible_names, required=True):
    """Find a column using case-insensitive matching."""

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


def normalize_text(value):
    """Normalize text for comparison without changing source data."""

    if pd.isna(value):
        return None

    value = str(value).strip()

    if value == "":
        return None

    return value.upper()


def normalize_imo(value):
    """Normalize IMO values and remove Excel-style .0 suffix."""

    if pd.isna(value):
        return None

    value = str(value).strip().upper()

    if value.endswith(".0"):
        value = value[:-2]

    return value if value else None


def normalize_timestamp(value):
    """Convert timestamps to UTC for comparison."""

    if pd.isna(value):
        return None

    parsed = pd.to_datetime(
        value,
        errors="coerce",
        utc=True
    )

    if pd.isna(parsed):
        return None

    return parsed.isoformat()


def distinct_values(series):
    """Return sorted distinct nonmissing values."""

    values = (
        series.dropna()
        .astype(str)
        .str.strip()
    )

    values = values[values != ""]

    return sorted(values.unique().tolist())


def display_values(values):
    if not values:
        return "<MISSING>"

    return " | ".join(map(str, values))


# ============================================================
# 2. LOAD SOURCE AND PROCESSED DATA
# ============================================================

print("\n" + "=" * 90)
print("SCRIPT 12: SOURCE PROVENANCE AND SERVICE-CODE INVESTIGATION")
print("=" * 90)

for path in [
    RAW_FILE,
    INTEGRATED_FILE,
    CANDIDATE_FILE,
    GROUP_FILE,
]:
    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found:\n{path}"
        )

raw = pd.read_excel(
    RAW_FILE,
    dtype=object
)

integrated = pd.read_csv(
    INTEGRATED_FILE,
    low_memory=False
)

candidates = pd.read_csv(
    CANDIDATE_FILE,
    low_memory=False
)

groups = pd.read_csv(
    GROUP_FILE,
    low_memory=False
)

print("\nINPUT DIMENSIONS")
print(f"Original Excel: {raw.shape}")
print(f"Integrated CSV: {integrated.shape}")
print(f"Candidate rows: {candidates.shape}")
print(f"Candidate groups: {groups.shape}")


# ============================================================
# 3. MAP ORIGINAL SOURCE COLUMNS
# ============================================================

raw_columns = {
    "IMO": find_column(
        raw,
        ["IMO Number", "vesselIMO", "vesselIMONumber"]
    ),

    "Vessel_Name": find_column(
        raw,
        ["Vessel Name", "vesselName"]
    ),

    "Port_Name": find_column(
        raw,
        ["Port", "Port Name", "Port"]
    ),

    "LOCODE": find_column(
        raw,
        ["UNLocationCode", "UN Location Code", "LOCODE"]
    ),

    "Carrier_Code": find_column(
        raw,
        ["Carrier Code"],
        required=False
    ),

    "Service_Code": find_column(
        raw,
        ["Carrier Service Code"],
        required=False
    ),

    "Service_Name": find_column(
        raw,
        ["Carrier Service Name"],
        required=False
    ),

    "Import_Voyage": find_column(
        raw,
        ["Import Voyage Number", "Import Voyage"]
    ),

    "Export_Voyage": find_column(
        raw,
        ["Export Voyage Number", "Export Voyage"]
    ),

    "Planned_Arrival": find_column(
        raw,
        ["Planned Arrival"]
    ),

    "Planned_Departure": find_column(
        raw,
        ["Planned Departure"]
    ),

    "Estimated_Arrival": find_column(
        raw,
        ["Estimated Arrival"]
    ),

    "Estimated_Departure": find_column(
        raw,
        ["Estimated Departure"]
    ),

    "Actual_Arrival": find_column(
        raw,
        ["Actual Arrival"]
    ),

    "Actual_Departure": find_column(
        raw,
        ["Actual Departure"]
    ),
}

print("\nORIGINAL SOURCE COLUMN MAPPING")

for logical_name, source_name in raw_columns.items():
    print(f"{logical_name:22s}: {source_name}")


# ============================================================
# 4. MAP INTEGRATED DATASET COLUMNS
# ============================================================

integrated_columns = {
    "IMO": find_column(
        integrated,
        ["IMO Number", "IMO"]
    ),

    "Vessel_Name": find_column(
        integrated,
        ["Vessel Name"]
    ),

    "Port_Name": find_column(
    integrated,
    ["Port", "Port Name"]
),

    "LOCODE": find_column(
        integrated,
        ["UNLocationCode", "UN Location Code"]
    ),

    "Carrier_Code": find_column(
        integrated,
        ["Carrier Code"],
        required=False
    ),

    "Service_Code": find_column(
        integrated,
        ["Carrier Service Code"],
        required=False
    ),

    "Service_Name": find_column(
        integrated,
        ["Carrier Service Name"],
        required=False
    ),
        "Import_Voyage": find_column(
        integrated,
        ["Import Voyage Number"]
    ),

    "Export_Voyage": find_column(
        integrated,
        ["Export Voyage Number"]
    ),

    "Planned_Arrival": find_column(
        integrated,
        ["Planned Arrival"]
    ),

    "Planned_Departure": find_column(
        integrated,
        ["Planned Departure"]
    ),

    "Estimated_Arrival": find_column(
        integrated,
        ["Estimated Arrival"]
    ),

    "Estimated_Departure": find_column(
        integrated,
        ["Estimated Departure"]
    ),

    "Actual_Arrival": find_column(
        integrated,
        ["Actual Arrival"]
    ),

    "Actual_Departure": find_column(
        integrated,
        ["Actual Departure"]
    ),
}

print("\nINTEGRATED DATASET COLUMN MAPPING")

for logical_name, source_name in integrated_columns.items():
    print(f"{logical_name:22s}: {source_name}")


# ============================================================
# 5. CHECK SOURCE ROW POSITION MAPPING
# ============================================================

# Script 11 Source_Row_Number is a 1-based data-row position,
# excluding the Excel header.
#
# Therefore:
# Source_Row_Number = 1 corresponds to raw.iloc[0].
#
# This positional check assumes that the integrated dataset
# preserved the original schedule row order.

candidates["Source_Row_Number"] = pd.to_numeric(
    candidates["Source_Row_Number"],
    errors="coerce"
)

integrated["Script12_Source_Row"] = np.arange(
    1,
    len(integrated) + 1
)

provenance_results = []
field_results = []

text_comparison_fields = [
    "IMO",
    "Vessel_Name",
    "Port_Name",
    "LOCODE",
    "Import_Voyage",
    "Export_Voyage",
]

timestamp_comparison_fields = [
    "Planned_Arrival",
    "Planned_Departure",
    "Estimated_Arrival",
    "Estimated_Departure",
    "Actual_Arrival",
    "Actual_Departure",
]



# ============================================================
# 6. VERIFY EACH CANDIDATE AGAINST ORIGINAL EXCEL
# ============================================================

# Create a lookup using the original schedule row number.
# This avoids relying on the current row position after merges.

integrated_lookup = integrated.set_index("Schedule_Source_Row")

for _, candidate in candidates.iterrows():

    source_row = int(candidate["Source_Row_Number"])
    group_id = candidate["Candidate_Group_ID"]

    result = {
        "Candidate_Group_ID": group_id,
        "Source_Row_Number": source_row,
        "Excel_Physical_Row": source_row + 1,
        "IMO": candidate["IMO"],
        "Vessel_Name": candidate["Vessel_Name"],
        "Port_Name": candidate["Port_Name"],
        "LOCODE": candidate["LOCODE"],
    }

    # Check whether the source row exists in both datasets.
    if (
        source_row < 1
        or source_row > len(raw)
        or source_row not in integrated_lookup.index
    ):
        result["Verification_Status"] = "SOURCE_ROW_OUT_OF_RANGE"
        result["Fields_Checked"] = 0
        result["Fields_Matched"] = 0
        result["Fields_Mismatched"] = 0

        provenance_results.append(result)
        continue

    original_record = raw.iloc[source_row - 1]
    integrated_record = integrated_lookup.loc[source_row]

    fields_checked = 0
    fields_matched = 0
    fields_mismatched = 0
    mismatches = []

    # --------------------------------------------------------
    # 6A. Compare identifiers and voyage numbers
    # --------------------------------------------------------

    for field in text_comparison_fields:

        raw_col = raw_columns.get(field)
        integrated_col = integrated_columns.get(field)

        if raw_col is None or integrated_col is None:
            continue

        fields_checked += 1

        original_value = original_record[raw_col]
        integrated_value = integrated_record[integrated_col]

        if field == "IMO":
            original_normalized = normalize_imo(original_value)
            integrated_normalized = normalize_imo(integrated_value)
        else:
            original_normalized = normalize_text(original_value)
            integrated_normalized = normalize_text(integrated_value)

        is_match = original_normalized == integrated_normalized

        if is_match:
            fields_matched += 1
        else:
            fields_mismatched += 1
            mismatches.append(field)

        field_results.append({
            "Candidate_Group_ID": group_id,
            "Source_Row_Number": source_row,
            "Field": field,
            "Original_Value": original_value,
            "Candidate_Value": integrated_value,
            "Original_Normalized": original_normalized,
            "Candidate_Normalized": integrated_normalized,
            "Match_Status": "MATCH" if is_match else "MISMATCH",
        })

    # --------------------------------------------------------
    # 6B. Compare six timestamps
    # --------------------------------------------------------

    for field in timestamp_comparison_fields:

        raw_col = raw_columns.get(field)
        integrated_col = integrated_columns.get(field)

        if raw_col is None or integrated_col is None:
            continue

        fields_checked += 1

        original_value = original_record[raw_col]
        integrated_value = integrated_record[integrated_col]

        original_normalized = normalize_timestamp(original_value)
        integrated_normalized = normalize_timestamp(integrated_value)

        is_match = original_normalized == integrated_normalized

        if is_match:
            fields_matched += 1
        else:
            fields_mismatched += 1
            mismatches.append(field)

        field_results.append({
            "Candidate_Group_ID": group_id,
            "Source_Row_Number": source_row,
            "Field": field + "_UTC",
            "Original_Value": original_value,
            "Candidate_Value": integrated_value,
            "Original_Normalized": original_normalized,
            "Candidate_Normalized": integrated_normalized,
            "Match_Status": "MATCH" if is_match else "MISMATCH",
        })

    # --------------------------------------------------------
    # 6C. Compare service fields separately
    # --------------------------------------------------------

    for field in [
        "Carrier_Code",
        "Service_Code",
        "Service_Name",
    ]:

        raw_col = raw_columns.get(field)
        integrated_col = integrated_columns.get(field)

        if raw_col is None or integrated_col is None:
            continue

        fields_checked += 1

        original_value = original_record[raw_col]
        integrated_value = integrated_record[integrated_col]

        original_normalized = normalize_text(original_value)
        integrated_normalized = normalize_text(integrated_value)

        is_match = original_normalized == integrated_normalized

        if is_match:
            fields_matched += 1
        else:
            fields_mismatched += 1
            mismatches.append(field)

        field_results.append({
            "Candidate_Group_ID": group_id,
            "Source_Row_Number": source_row,
            "Field": field,
            "Original_Value": original_value,
            "Candidate_Value": integrated_value,
            "Original_Normalized": original_normalized,
            "Candidate_Normalized": integrated_normalized,
            "Match_Status": "MATCH" if is_match else "MISMATCH",
        })

    # --------------------------------------------------------
    # 6D. Finalize source-row verification
    # --------------------------------------------------------

    if fields_mismatched == 0:
        status = "ALL_CHECKED_FIELDS_MATCH"
    else:
        status = "MISMATCH_REQUIRES_INVESTIGATION"

    result["Fields_Checked"] = fields_checked
    result["Fields_Matched"] = fields_matched
    result["Fields_Mismatched"] = fields_mismatched
    result["Mismatched_Fields"] = " | ".join(mismatches)
    result["Verification_Status"] = status

    provenance_results.append(result)


# Convert results into DataFrames
provenance_df = pd.DataFrame(provenance_results)
field_comparison_df = pd.DataFrame(field_results)



# ============================================================
# 7. INVESTIGATE SERVICE-CODE SEMANTICS
# ============================================================

service_code_col = integrated_columns["Service_Code"]
service_name_col = integrated_columns["Service_Name"]
carrier_code_col = integrated_columns["Carrier_Code"]

if service_code_col is None:
    raise KeyError(
        "Carrier Service Code is missing from integrated dataset."
    )

service_data = integrated.copy()

service_data["Service_Code_Normalized"] = (
    service_data[service_code_col]
    .astype("string")
    .str.strip()
    .str.upper()
    .replace("", pd.NA)
)

if service_name_col is not None:
    service_data["Service_Name_Normalized"] = (
        service_data[service_name_col]
        .astype("string")
        .str.strip()
        .replace("", pd.NA)
    )
else:
    service_data["Service_Name_Normalized"] = pd.NA

if carrier_code_col is not None:
    service_data["Carrier_Code_Normalized"] = (
        service_data[carrier_code_col]
        .astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )
else:
    service_data["Carrier_Code_Normalized"] = pd.NA


# ------------------------------------------------------------
# 7A. Global service-code summary
# ------------------------------------------------------------

service_summary = (
    service_data
    .groupby(
        "Service_Code_Normalized",
        dropna=False
    )
    .agg(
        Record_Count=("Service_Code_Normalized", "size"),
        Unique_Service_Names=(
            "Service_Name_Normalized",
            "nunique"
        ),
        Unique_Carrier_Codes=(
            "Carrier_Code_Normalized",
            "nunique"
        ),
    )
    .reset_index()
)

service_names_lookup = (
    service_data
    .groupby("Service_Code_Normalized")[
        "Service_Name_Normalized"
    ]
    .apply(lambda x: display_values(distinct_values(x)))
    .reset_index(name="Service_Names")
)

carrier_lookup = (
    service_data
    .groupby("Service_Code_Normalized")[
        "Carrier_Code_Normalized"
    ]
    .apply(lambda x: display_values(distinct_values(x)))
    .reset_index(name="Carrier_Codes")
)

service_summary = service_summary.merge(
    service_names_lookup,
    on="Service_Code_Normalized",
    how="left"
).merge(
    carrier_lookup,
    on="Service_Code_Normalized",
    how="left"
)


# ------------------------------------------------------------
# 7B. Candidate-specific service-code comparison
# ------------------------------------------------------------

candidate_service_results = []

for group_id, group in candidates.groupby("Candidate_Group_ID"):

    source_rows = group["Source_Row_Number"].astype(int).tolist()

    group_records = integrated.iloc[
        [row - 1 for row in source_rows]
    ].copy()

    group_records["Source_Row_Number"] = source_rows

    for _, record in group_records.iterrows():

        service_code = record[service_code_col]

        if pd.isna(service_code):
            service_code = None

        if service_name_col is not None:
            service_name = record[service_name_col]
        else:
            service_name = None

        if carrier_code_col is not None:
            carrier_code = record[carrier_code_col]
        else:
            carrier_code = None

        normalized_code = normalize_text(service_code)

        matching_global = service_data[
            service_data["Service_Code_Normalized"]
            == normalized_code
        ] if normalized_code is not None else service_data.iloc[0:0]

        candidate_service_results.append({
            "Candidate_Group_ID": group_id,
            "Source_Row_Number": record["Source_Row_Number"],
            "IMO": record[integrated_columns["IMO"]],
            "Vessel_Name": record[integrated_columns["Vessel_Name"]],
            "Port_Name": record[integrated_columns["Port_Name"]],
            "LOCODE": record[integrated_columns["LOCODE"]],
            "Carrier_Code": carrier_code,
            "Carrier_Service_Code": service_code,
            "Carrier_Service_Name": service_name,
            "Global_Service_Code_Record_Count": len(matching_global),
            "Global_Unique_Service_Names": (
                matching_global["Service_Name_Normalized"]
                .nunique()
            ),
            "Global_Unique_Carrier_Codes": (
                matching_global["Carrier_Code_Normalized"]
                .nunique()
            ),
            "Global_Service_Names": display_values(
                distinct_values(
                    matching_global["Service_Name_Normalized"]
                )
            ),
            "Global_Carrier_Codes": display_values(
                distinct_values(
                    matching_global["Carrier_Code_Normalized"]
                )
            ),
        })


candidate_service_df = pd.DataFrame(
    candidate_service_results
)


# ============================================================
# 8. GROUP-LEVEL CLASSIFICATION
# ============================================================

classification_results = []

for group_id, group in candidates.groupby("Candidate_Group_ID"):

    services = distinct_values(group["Service"])

    source_rows = sorted(
        group["Source_Row_Number"].astype(int).tolist()
    )

    provenance_group = provenance_df[
        provenance_df["Candidate_Group_ID"] == group_id
    ]

    all_source_rows_verified = (
        len(provenance_group) == len(group)
        and provenance_group["Verification_Status"]
        .eq("ALL_CHECKED_FIELDS_MATCH")
        .all()
    )

    if len(services) > 1 and all_source_rows_verified:
        classification = (
            "SOURCE_VERIFIED_EXACT_MATCH_DIFFERENT_SERVICE_CODE"
        )

        resolution = (
            "PENDING_SERVICE_CODE_SEMANTICS_REVIEW"
        )

    elif len(services) > 1:
        classification = (
            "EXACT_MATCH_CANDIDATE_WITH_SOURCE_MISMATCH"
        )

        resolution = "INVESTIGATE_SOURCE_MISMATCH"

    else:
        classification = (
            "SERVICE_CODE_NOT_DISTINCT_OR_INSUFFICIENT"
        )

        resolution = "MANUAL_REVIEW"

    classification_results.append({
        "Candidate_Group_ID": group_id,
        "IMO": group["IMO"].iloc[0],
        "Vessel_Name": group["Vessel_Name"].iloc[0],
        "Port_Name": group["Port_Name"].iloc[0],
        "LOCODE": group["LOCODE"].iloc[0],
        "Group_Size": len(group),
        "Service_Codes": " | ".join(services),
        "Source_Rows": " | ".join(map(str, source_rows)),
        "All_Source_Rows_Verified": all_source_rows_verified,
        "Classification": classification,
        "Resolution_Status": resolution,
        "Records_To_Retain": len(group),
    })


classification_df = pd.DataFrame(classification_results)


# ============================================================
# 9. CHECK SERVICE-CODE NAME VARIABILITY
# ============================================================

if service_name_col is not None:

    service_name_variability = (
        service_data
        .groupby(
            "Service_Code_Normalized",
            dropna=False
        )
        .agg(
            Unique_Service_Names=(
                "Service_Name_Normalized",
                "nunique"
            ),
            Unique_Carrier_Codes=(
                "Carrier_Code_Normalized",
                "nunique"
            ),
            Total_Records=(
                "Service_Code_Normalized",
                "size"
            ),
        )
        .reset_index()
    )

    service_name_variability["Review_Flag"] = np.where(
        service_name_variability["Unique_Service_Names"] > 1,
        "SERVICE_CODE_HAS_MULTIPLE_SERVICE_NAMES",
        "NO_MULTIPLE_SERVICE_NAME_DETECTED"
    )

else:

    service_name_variability = pd.DataFrame(
        columns=[
            "Service_Code_Normalized",
            "Unique_Service_Names",
            "Unique_Carrier_Codes",
            "Total_Records",
            "Review_Flag",
        ]
    )


# ============================================================
# 10. SAVE OUTPUT FILES
# ============================================================

outputs = {
    "12_source_row_verification.csv": provenance_df,

    "12_source_field_comparison.csv": field_comparison_df,

    "12_service_code_investigation.csv": candidate_service_df,

    "12_global_service_code_summary.csv": service_summary,

    "12_service_code_name_variability.csv": service_name_variability,

    "12_duplicate_representation_classification.csv": classification_df,
}

for filename, dataframe in outputs.items():

    dataframe.to_csv(
        OUTPUT_DIR / filename,
        index=False
    )


# ============================================================
# 11. GENERATE REPORT
# ============================================================

report_path = (
    REPORT_DIR
    / "12_source_provenance_report.txt"
)

with open(report_path, "w", encoding="utf-8") as report:

    report.write("=" * 90 + "\n")
    report.write(
        "SCRIPT 12: SOURCE PROVENANCE AND SERVICE-CODE INVESTIGATION\n"
    )
    report.write("=" * 90 + "\n\n")

    report.write("INPUT DATA DIMENSIONS\n")
    report.write("-" * 90 + "\n")

    report.write(f"Original Excel: {raw.shape}\n")
    report.write(f"Integrated CSV: {integrated.shape}\n")
    report.write(f"Candidate records: {len(candidates)}\n")
    report.write(f"Candidate groups: {candidates['Candidate_Group_ID'].nunique()}\n\n")

    report.write("SOURCE ROW VERIFICATION\n")
    report.write("-" * 90 + "\n")

    report.write(
        provenance_df["Verification_Status"]
        .value_counts(dropna=False)
        .to_string()
    )

    report.write("\n\nFIELD-LEVEL VERIFICATION\n")
    report.write("-" * 90 + "\n")

    if not field_comparison_df.empty:

        report.write(
            field_comparison_df["Match_Status"]
            .value_counts(dropna=False)
            .to_string()
        )

    report.write("\n\nGROUP CLASSIFICATION\n")
    report.write("-" * 90 + "\n")

    if not classification_df.empty:

        report.write(
            classification_df[
                [
                    "Candidate_Group_ID",
                    "IMO",
                    "Vessel_Name",
                    "Service_Codes",
                    "All_Source_Rows_Verified",
                    "Classification",
                    "Resolution_Status",
                ]
            ].to_string(index=False)
        )

    report.write("\n\nSERVICE-CODE INVESTIGATION\n")
    report.write("-" * 90 + "\n")

    if not candidate_service_df.empty:

        report.write(
            candidate_service_df[
                [
                    "Candidate_Group_ID",
                    "Source_Row_Number",
                    "Carrier_Code",
                    "Carrier_Service_Code",
                    "Carrier_Service_Name",
                    "Global_Service_Code_Record_Count",
                    "Global_Unique_Service_Names",
                    "Global_Unique_Carrier_Codes",
                ]
            ].to_string(index=False)
        )

    report.write("\n\nMETHODOLOGICAL NOTES\n")
    report.write("-" * 90 + "\n")

    report.write(
        "1. Source row verification uses the original Excel data-row "
        "position corresponding to Script 11 Source_Row_Number.\n"
    )

    report.write(
        "2. This positional verification assumes that the integrated "
        "CSV preserved the original schedule row order.\n"
    )

    report.write(
        "3. The Excel physical row number is the data-row position plus "
        "one, assuming a single header row.\n"
    )

    report.write(
        "4. Timestamp values are normalized to UTC before comparison.\n"
    )

    report.write(
        "5. Service-code statistics describe associations in the "
        "available schedule dataset. They do not establish the formal "
        "meaning of a service code.\n"
    )

    report.write(
        "6. Exact matching records are not automatically treated as "
        "confirmed erroneous duplicates.\n"
    )

    report.write(
        "7. No original records were deleted or modified.\n"
    )


# ============================================================
# 12. TERMINAL SUMMARY
# ============================================================

print("\n" + "=" * 90)
print("SCRIPT 12 COMPLETED")
print("=" * 90)

print("\nSOURCE ROW VERIFICATION")
print(
    provenance_df["Verification_Status"]
    .value_counts(dropna=False)
    .to_string()
)

print("\nFIELD-LEVEL COMPARISON")
print(
    field_comparison_df["Match_Status"]
    .value_counts(dropna=False)
    .to_string()
)

print("\nGROUP CLASSIFICATION")
if not classification_df.empty:
    print(
        classification_df[
            [
                "Candidate_Group_ID",
                "IMO",
                "Service_Codes",
                "All_Source_Rows_Verified",
                "Classification",
            ]
        ].to_string(index=False)
    )

print("\nSERVICE-CODE INVESTIGATION")
if not candidate_service_df.empty:
    print(
        candidate_service_df[
            [
                "Candidate_Group_ID",
                "Carrier_Service_Code",
                "Carrier_Service_Name",
                "Global_Service_Code_Record_Count",
                "Global_Unique_Service_Names",
            ]
        ].to_string(index=False)
    )

print("\nOUTPUT FILES")

for filename in outputs:
    print(OUTPUT_DIR / filename)

print(report_path)

print("\nNo original records were deleted or modified.")