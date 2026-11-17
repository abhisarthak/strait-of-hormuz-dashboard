
from pathlib import Path
import pandas as pd
import numpy as np


# ============================================================
# 1. PROJECT PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

SOURCE_FILE = (
    PROCESSED_DIR /
    "06_integrated_schedule_vessel_port.csv"
)

INDIVIDUAL_FILE = (
    PROCESSED_DIR /
    "06_individual_vessel_port_calls.csv"
)

REVIEW_FLAGS_FILE = (
    OUTPUT_DIR /
    "09d_schedule_record_review_flags.csv"
)


# ============================================================
# 2. LOAD DATA
# ============================================================

schedule = pd.read_csv(
    SOURCE_FILE,
    low_memory=False
)

individual = pd.read_csv(
    INDIVIDUAL_FILE,
    low_memory=False
)

review_flags = pd.read_csv(
    REVIEW_FLAGS_FILE,
    low_memory=False
)


# ============================================================
# 3. HELPER FUNCTIONS
# ============================================================

def normalize_text(series):

    return (
        series.astype("string")
        .str.strip()
        .str.upper()
        .str.replace(r"\s+", " ", regex=True)
        .replace("", pd.NA)
    )


def normalize_imo(series):

    result = normalize_text(series)

    return result.str.replace(
        r"\.0$", "",
        regex=True
    )


def parse_datetime(series):

    return pd.to_datetime(
        series,
        errors="coerce",
        utc=True
    )


def first_existing_column(df, candidates):

    for col in candidates:
        if col in df.columns:
            return col

    return None


# ============================================================
# 4. STANDARDIZE SCHEDULE DATA
# ============================================================

schedule = schedule.copy()

schedule.insert(
    0,
    "Source_Row_Number",
    range(1, len(schedule) + 1)
)

# Identify columns safely
schedule_imo = first_existing_column(
    schedule,
    ["IMO Number", "vesselIMONumber", "IMO"]
)

schedule_name = first_existing_column(
    schedule,
    ["Vessel Name", "vesselName"]
)

schedule_port = first_existing_column(
    schedule,
    ["portName", "Port Name", "Port"]
)

schedule_locode = first_existing_column(
    schedule,
    ["UNLocationCode", "UN Location Code"]
)

schedule_service = first_existing_column(
    schedule,
    ["Carrier Service Code", "carrierServiceCode"]
)

schedule_import = first_existing_column(
    schedule,
    ["Import Voyage Number", "importVoyageNumber"]
)

schedule_export = first_existing_column(
    schedule,
    ["Export Voyage Number", "exportVoyageNumber"]
)

required = [
    schedule_imo,
    schedule_name,
    schedule_port,
    schedule_locode,
]

if any(col is None for col in required):
    raise ValueError(
        "Required schedule columns were not found. "
        f"Available columns: {schedule.columns.tolist()}"
    )


schedule["Analysis_IMO"] = normalize_imo(
    schedule[schedule_imo]
)

schedule["Analysis_Vessel_Name"] = normalize_text(
    schedule[schedule_name]
)

schedule["Analysis_Port_Name"] = normalize_text(
    schedule[schedule_port]
)

schedule["Analysis_LOCODE"] = normalize_text(
    schedule[schedule_locode]
)

schedule["Analysis_Service"] = (
    normalize_text(schedule[schedule_service])
    if schedule_service
    else pd.NA
)

schedule["Analysis_Import_Voyage"] = (
    normalize_text(schedule[schedule_import])
    if schedule_import
    else pd.NA
)

schedule["Analysis_Export_Voyage"] = (
    normalize_text(schedule[schedule_export])
    if schedule_export
    else pd.NA
)


# ============================================================
# 5. CREATE SOURCE-SPECIFIC TIMESTAMPS
# ============================================================

timestamp_columns = {
    "ACTUAL": (
        "Actual Arrival",
        "Actual Departure"
    ),
    "ESTIMATED": (
        "Estimated Arrival",
        "Estimated Departure"
    ),
    "PLANNED": (
        "Planned Arrival",
        "Planned Departure"
    ),
}

# Resolve alternate timestamp column names if necessary
timestamp_candidates = {
    "Actual Arrival": [
        "Actual Arrival",
        "actualArrival"
    ],
    "Actual Departure": [
        "Actual Departure",
        "actualDeparture"
    ],
    "Estimated Arrival": [
        "Estimated Arrival",
        "estimatedArrival"
    ],
    "Estimated Departure": [
        "Estimated Departure",
        "estimatedDeparture"
    ],
    "Planned Arrival": [
        "Planned Arrival",
        "plannedArrival"
    ],
    "Planned Departure": [
        "Planned Departure",
        "plannedDeparture"
    ],
}

resolved_timestamps = {}

for logical_name, candidates in timestamp_candidates.items():

    resolved_timestamps[logical_name] = (
        first_existing_column(schedule, candidates)
    )

    if resolved_timestamps[logical_name] is None:
        raise ValueError(
            f"Missing timestamp column: {logical_name}"
        )


for logical_name, actual_column in resolved_timestamps.items():

    schedule[logical_name.replace(" ", "_") + "_UTC"] = (
        parse_datetime(schedule[actual_column])
    )


# ============================================================
# 6. CREATE A COMMON SOURCE-RECORD TABLE
# ============================================================

common_columns = [
    "Source_Row_Number",
    "Analysis_IMO",
    "Analysis_Vessel_Name",
    "Analysis_Port_Name",
    "Analysis_LOCODE",
    "Analysis_Service",
    "Analysis_Import_Voyage",
    "Analysis_Export_Voyage",
]

base = schedule[common_columns].copy()

for source_name in ["ACTUAL", "ESTIMATED", "PLANNED"]:

    # Convert ACTUAL -> Actual, ESTIMATED -> Estimated, etc.
    timestamp_prefix = source_name.title()

    arrival_col = f"{timestamp_prefix}_Arrival_UTC"
    departure_col = f"{timestamp_prefix}_Departure_UTC"
    
    temp = base.copy()

    temp["Timestamp_Source"] = source_name

    temp["Arrival_UTC"] = schedule[arrival_col]

    temp["Departure_UTC"] = schedule[departure_col]

    temp = temp.dropna(
        subset=[
            "Analysis_IMO",
            "Arrival_UTC",
            "Departure_UTC",
        ]
    )

    temp["Port_Stay_Hours"] = (
        temp["Departure_UTC"] -
        temp["Arrival_UTC"]
    ).dt.total_seconds() / 3600

    temp = temp[
        temp["Port_Stay_Hours"] >= 0
    ].copy()

    if source_name == "ACTUAL":
        temp["Historical_Usability"] = "ACTUAL_TIMESTAMP"
    elif source_name == "ESTIMATED":
        temp["Historical_Usability"] = "ESTIMATED_TIMESTAMP"
    else:
        temp["Historical_Usability"] = "PLANNED_TIMESTAMP"

    if source_name == "ACTUAL":
        actual_source = temp
    elif source_name == "ESTIMATED":
        estimated_source = temp
    else:
        planned_source = temp


# ============================================================
# 7. INVESTIGATE CONSECUTIVE SAME-PORT RECORDS
# ============================================================

def detect_repeated_calls(df):

    if df.empty:
        return pd.DataFrame()

    df = df.sort_values(
        [
            "Analysis_IMO",
            "Arrival_UTC",
            "Departure_UTC",
            "Source_Row_Number",
        ]
    ).copy()

    grouped = df.groupby(
        "Analysis_IMO",
        sort=False
    )

    df["Previous_Port"] = grouped[
        "Analysis_Port_Name"
    ].shift(1)

    df["Previous_LOCODE"] = grouped[
        "Analysis_LOCODE"
    ].shift(1)

    df["Previous_Departure_UTC"] = grouped[
        "Departure_UTC"
    ].shift(1)

    df["Previous_Source_Row"] = grouped[
        "Source_Row_Number"
    ].shift(1)

    df["Previous_Service"] = grouped[
        "Analysis_Service"
    ].shift(1)

    df["Previous_Import_Voyage"] = grouped[
        "Analysis_Import_Voyage"
    ].shift(1)

    df["Previous_Export_Voyage"] = grouped[
        "Analysis_Export_Voyage"
    ].shift(1)

    df["Gap_Between_Calls_Hours"] = (
        df["Arrival_UTC"] -
        df["Previous_Departure_UTC"]
    ).dt.total_seconds() / 3600

    df["Same_Port_Name"] = (
        df["Analysis_Port_Name"] ==
        df["Previous_Port"]
    )

    df["Same_LOCODE"] = (
        df["Analysis_LOCODE"] ==
        df["Previous_LOCODE"]
    )

    df["Same_Port_Name"] = (
        df["Same_Port_Name"].fillna(False)
    )

    df["Same_LOCODE"] = (
        df["Same_LOCODE"].fillna(False)
    )

    # A repeated port call is defined by consecutive
    # chronological records at the same port name OR LOCODE.

    df["Repeated_Port_Call"] = (
        df["Same_Port_Name"] |
        df["Same_LOCODE"]
    )

    repeated = df[
        df["Repeated_Port_Call"]
    ].copy()

    if repeated.empty:
        return repeated

    # --------------------------------------------------------
    # 7A. Classify evidence
    # --------------------------------------------------------

    same_voyage = (
        repeated["Analysis_Import_Voyage"].notna() &
        (
            repeated["Analysis_Import_Voyage"] ==
            repeated["Previous_Import_Voyage"]
        ) &
        repeated["Analysis_Export_Voyage"].notna() &
        (
            repeated["Analysis_Export_Voyage"] ==
            repeated["Previous_Export_Voyage"]
        )
    )

    same_service = (
        repeated["Analysis_Service"].notna() &
        (
            repeated["Analysis_Service"] ==
            repeated["Previous_Service"]
        )
    )

    same_locode = repeated["Same_LOCODE"]

    same_port_name = repeated["Same_Port_Name"]

    repeated["Investigation_Classification"] = (
        "UNRESOLVED_REPEATED_PORT_CALL"
    )

    repeated.loc[
        same_locode & same_service & same_voyage,
        "Investigation_Classification"
    ] = "SAME_PORT_SAME_SERVICE_SAME_VOYAGE"

    repeated.loc[
        same_locode & ~same_service,
        "Investigation_Classification"
    ] = "SAME_LOCODE_DIFFERENT_SERVICE"

    repeated.loc[
        same_port_name & ~same_locode,
        "Investigation_Classification"
    ] = "SAME_PORT_NAME_DIFFERENT_LOCODE"

    repeated.loc[
        same_locode & same_service & ~same_voyage,
        "Investigation_Classification"
    ] = "SAME_PORT_SAME_SERVICE_VOYAGE_CHANGE"

    # --------------------------------------------------------
    # 7B. Add interpretation notes
    # --------------------------------------------------------

    interpretation = {
        "SAME_PORT_SAME_SERVICE_SAME_VOYAGE":
            "Could represent repeated calls, schedule revisions, "
            "or duplicate representations. Requires further review.",

        "SAME_LOCODE_DIFFERENT_SERVICE":
            "Same port location under different services. "
            "May reflect service changes or duplicate representations.",

        "SAME_PORT_NAME_DIFFERENT_LOCODE":
            "Port name matches but LOCODE differs. "
            "Investigate terminal and port-code mapping.",

        "SAME_PORT_SAME_SERVICE_VOYAGE_CHANGE":
            "Same port and service with changed voyage identifiers. "
            "May represent distinct calls or schedule revisions.",

        "UNRESOLVED_REPEATED_PORT_CALL":
            "Insufficient evidence for a definitive classification.",
    }

    repeated["Investigation_Notes"] = (
        repeated["Investigation_Classification"]
        .map(interpretation)
    )

    repeated["Delete_Record"] = False
    repeated["Merge_Records"] = False
    repeated["Manual_Review_Required"] = True

    return repeated


# ============================================================
# 8. RUN INVESTIGATION FOR ALL THREE SOURCES
# ============================================================

actual_repeated = detect_repeated_calls(
    actual_source
)

estimated_repeated = detect_repeated_calls(
    estimated_source
)

planned_repeated = detect_repeated_calls(
    planned_source
)


# ============================================================
# 9. COMBINE RESULTS
# ============================================================

repeated_all = pd.concat(
    [
        actual_repeated,
        estimated_repeated,
        planned_repeated,
    ],
    ignore_index=True
)

if not repeated_all.empty:

    repeated_all = repeated_all.sort_values(
        [
            "Timestamp_Source",
            "Analysis_IMO",
            "Arrival_UTC",
        ]
    )


# ============================================================
# 10. CREATE VESSEL-LEVEL SUMMARY
# ============================================================

if not repeated_all.empty:

    vessel_summary = (
        repeated_all.groupby(
            [
                "Timestamp_Source",
                "Analysis_IMO",
                "Analysis_Vessel_Name",
            ],
            dropna=False
        )
        .agg(
            Repeated_Consecutive_Calls=(
                "Source_Row_Number",
                "count"
            ),
            Unique_Ports=(
                "Analysis_Port_Name",
                "nunique"
            ),
            Unique_LOCODES=(
                "Analysis_LOCODE",
                "nunique"
            ),
            First_Repeated_Call=(
                "Arrival_UTC",
                "min"
            ),
            Last_Repeated_Call=(
                "Arrival_UTC",
                "max"
            ),
        )
        .reset_index()
    )

else:

    vessel_summary = pd.DataFrame()


# ============================================================
# 11. CREATE PORT-LEVEL SUMMARY
# ============================================================

if not repeated_all.empty:

    port_summary = (
        repeated_all.groupby(
            [
                "Timestamp_Source",
                "Analysis_Port_Name",
                "Analysis_LOCODE",
            ],
            dropna=False
        )
        .agg(
            Repeated_Call_Records=(
                "Source_Row_Number",
                "count"
            ),
            Unique_Vessels=(
                "Analysis_IMO",
                "nunique"
            ),
        )
        .reset_index()
        .sort_values(
            "Repeated_Call_Records",
            ascending=False
        )
    )

else:

    port_summary = pd.DataFrame()


# ============================================================
# 12. CHECK EXACT SOURCE-RECORD MATCHES
# ============================================================

# Exact comparison is based on the available identifying
# fields and all six timestamp fields.
#
# This is a candidate flag, not proof of a duplicate.

identity_columns = [
    "Analysis_IMO",
    "Analysis_LOCODE",
    "Analysis_Import_Voyage",
    "Analysis_Export_Voyage",
    "Actual_Arrival_UTC",
    "Actual_Departure_UTC",
    "Estimated_Arrival_UTC",
    "Estimated_Departure_UTC",
    "Planned_Arrival_UTC",
    "Planned_Departure_UTC",
]

available_identity_columns = [
    col for col in identity_columns
    if col in schedule.columns
]

schedule["Exact_Representation_Group"] = (
    schedule.groupby(
        available_identity_columns,
        dropna=False
    ).ngroup()
)

schedule["Exact_Representation_Count"] = (
    schedule.groupby(
        "Exact_Representation_Group"
    )["Source_Row_Number"]
    .transform("count")
)

schedule["Exact_Representation_Candidate"] = (
    schedule["Exact_Representation_Count"] > 1
)


# ============================================================
# 13. ATTACH EXISTING 09D REVIEW FLAGS
# ============================================================

if not review_flags.empty:

    review_row_numbers = set(
        pd.to_numeric(
            review_flags["Source_Row_Number"],
            errors="coerce"
        ).dropna().astype(int)
    )

    repeated_all["Previously_Flagged_In_09D"] = (
        repeated_all["Source_Row_Number"]
        .isin(review_row_numbers)
    )

else:

    repeated_all["Previously_Flagged_In_09D"] = False


# ============================================================
# 14. SAVE OUTPUTS
# ============================================================

repeated_file = (
    OUTPUT_DIR /
    "10_repeated_port_call_investigation.csv"
)

vessel_file = (
    OUTPUT_DIR /
    "10_repeated_port_call_vessel_summary.csv"
)

port_file = (
    OUTPUT_DIR /
    "10_repeated_port_call_port_summary.csv"
)

exact_file = (
    OUTPUT_DIR /
    "10_exact_schedule_representation_candidates.csv"
)

schedule_flags_file = (
    OUTPUT_DIR /
    "10_schedule_exact_representation_flags.csv"
)

repeated_all.to_csv(
    repeated_file,
    index=False
)

vessel_summary.to_csv(
    vessel_file,
    index=False
)

port_summary.to_csv(
    port_file,
    index=False
)

schedule[
    [
        "Source_Row_Number",
        "Analysis_IMO",
        "Analysis_Vessel_Name",
        "Analysis_Port_Name",
        "Analysis_LOCODE",
        "Analysis_Service",
        "Analysis_Import_Voyage",
        "Analysis_Export_Voyage",
        "Exact_Representation_Group",
        "Exact_Representation_Count",
        "Exact_Representation_Candidate",
    ]
].to_csv(
    schedule_flags_file,
    index=False
)

schedule[
    schedule["Exact_Representation_Candidate"]
].to_csv(
    exact_file,
    index=False
)


# ============================================================
# 15. GENERATE REPORT
# ============================================================

report = []

report.append(
    "SCRIPT 10: REPEATED CONSECUTIVE PORT CALL INVESTIGATION"
)

report.append("=" * 85)

report.append(
    f"Original schedule records: {len(schedule)}"
)

report.append(
    f"Individual vessel records: {len(individual)}"
)

report.append("")

report.append("REPEATED CONSECUTIVE CALL COUNTS")

for source_name, df in [
    ("ACTUAL", actual_repeated),
    ("ESTIMATED", estimated_repeated),
    ("PLANNED", planned_repeated),
]:

    report.append(
        f"{source_name}: {len(df)} repeated consecutive records"
    )

report.append("")

report.append("CLASSIFICATION SUMMARY")

if not repeated_all.empty:

    report.append(
        repeated_all[
            "Investigation_Classification"
        ]
        .value_counts()
        .to_string()
    )

else:

    report.append("No repeated consecutive port calls detected.")

report.append("")

report.append("TOP PORTS WITH REPEATED CALL RECORDS")

if not port_summary.empty:

    report.append(
        port_summary.head(15).to_string(index=False)
    )

report.append("")

report.append("TOP VESSELS WITH REPEATED CALL RECORDS")

if not vessel_summary.empty:

    report.append(
        vessel_summary.sort_values(
            "Repeated_Consecutive_Calls",
            ascending=False
        ).head(15).to_string(index=False)
    )

report.append("")

report.append("EXACT REPRESENTATION CANDIDATES")

report.append(
    f"Candidate source rows: "
    f"{int(schedule['Exact_Representation_Candidate'].sum())}"
)

report.append("")

report.append("DATA GOVERNANCE")

report.append(
    "1. All source records are retained."
)

report.append(
    "2. No automatic deletion or merging has been performed."
)

report.append(
    "3. Actual, estimated and planned sequences are analyzed separately."
)

report.append(
    "4. Same-port consecutive records are not automatically duplicates."
)

report.append(
    "5. Same LOCODE does not prove that two calls are the same event."
)

report.append(
    "6. Exact representation candidates require manual validation."
)

report.append(
    "7. Port-name and LOCODE differences require separate investigation."
)

report_path = (
    REPORT_DIR /
    "10_repeated_port_call_investigation_report.txt"
)

report_path.write_text(
    "\n".join(report),
    encoding="utf-8"
)


# ============================================================
# 16. TERMINAL OUTPUT
# ============================================================

print("\n" + "=" * 85)
print("SCRIPT 10 COMPLETED")
print("=" * 85)

print("\nREPEATED CONSECUTIVE PORT CALLS")

print(
    f"Actual:    {len(actual_repeated)}"
)

print(
    f"Estimated: {len(estimated_repeated)}"
)

print(
    f"Planned:   {len(planned_repeated)}"
)

print("\nCLASSIFICATION SUMMARY")

if not repeated_all.empty:

    print(
        repeated_all[
            "Investigation_Classification"
        ].value_counts().to_string()
    )

else:

    print("No repeated calls found.")

print("\nEXACT REPRESENTATION CANDIDATES")

print(
    schedule[
        "Exact_Representation_Candidate"
    ].sum()
)

print("\nOUTPUT FILES")

print(repeated_file)
print(vessel_file)
print(port_file)
print(exact_file)
print(schedule_flags_file)
print(report_path)

print("\nNo original records were deleted or modified.")