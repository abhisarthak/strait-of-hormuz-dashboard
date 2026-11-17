
from pathlib import Path
import re
import warnings

import numpy as np
import pandas as pd


# ============================================================
# SCRIPT 15
# Transition and Strait of Hormuz Relevance Investigation
#
# Sections:
# 1. Investigate negative schedule transitions.
# 2. Separate same-port and different-port transitions.
# 3. Identify Gulf-region vessels and their full sequences.
# 4. Create an AIS trajectory verification register.
#
# IMPORTANT:
# - No original records are deleted.
# - No timestamps are automatically corrected.
# - Inter-port elapsed time is NOT assumed to be sailing time.
# - Port calls do NOT prove Strait of Hormuz transit.
# ============================================================


# -----------------------------
# 1. PROJECT PATHS
# -----------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_RAW = PROJECT_ROOT / "data" / "raw"

OUTPUT_TABLES = PROJECT_ROOT / "outputs" / "tables"
OUTPUT_REPORTS = PROJECT_ROOT / "outputs" / "reports"

OUTPUT_TABLES.mkdir(parents=True, exist_ok=True)
OUTPUT_REPORTS.mkdir(parents=True, exist_ok=True)

SCHEDULE_FILE = DATA_PROCESSED / "13_final_consolidated_schedule.csv"
INDIVIDUAL_FILE = DATA_PROCESSED / "13_final_consolidated_individual_calls.csv"

PORT_LOOKUP_FILE = DATA_PROCESSED / "06_unique_port_lookup.csv"
AMBIGUOUS_PORT_FILE = DATA_PROCESSED / "06_ambiguous_port_candidates.csv"


# -----------------------------
# 2. CONFIGURATION
# -----------------------------

# Initial curated LOCODE list based on ports already identified
# in the research dataset and other relevant Gulf/approach ports.
#
# Edit this list after reviewing the port master.
#
# Salalah is an Arabian Sea / Gulf of Oman approach-area port,
# NOT a Persian Gulf port and NOT inside the Strait.

GULF_CORE_PORTS = {
    "AEJEA": "Jebel Ali",
    "AEKLF": "Khor Fakkan",
    "AEFJR": "Fujairah",
    "AEAUH": "Abu Dhabi",
    "BHBAH": "Bahrain",
    "KWKWI": "Kuwait",
    "QAHMD": "Hamad Port",
    "QARLF": "Ras Laffan",
    "QAMES": "Mesaieed",
    "IQUQR": "Umm Qasr",
    "OMSOH": "Sohar",
}

STRAIT_APPROACH_PORTS = {
    "OMSLL": "Salalah",
    "OMMCT": "Muscat",
}

# The two categories are kept separate to avoid treating every
# Omani port as a Persian Gulf port.


# -----------------------------
# 3. GENERAL HELPER FUNCTIONS
# -----------------------------

def normalize_column_name(value):
    """Normalize column names for flexible matching."""
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def find_column(df, candidates, required=True):
    """
    Find a column using a list of possible names.

    Matching ignores spaces, underscores, punctuation and case.
    """
    normalized_columns = {
        normalize_column_name(col): col
        for col in df.columns
    }

    for candidate in candidates:
        key = normalize_column_name(candidate)

        if key in normalized_columns:
            return normalized_columns[key]

    if required:
        raise KeyError(
            f"Could not find any of these columns: {candidates}\n"
            f"Available columns:\n{df.columns.tolist()}"
        )

    return None


def get_column(df, candidates, default=pd.NA):
    """Return a column if available, otherwise a default Series."""
    col = find_column(df, candidates, required=False)

    if col is None:
        return pd.Series(default, index=df.index)

    return df[col]


def normalize_imo(series):
    """Normalize IMO values without changing the original column."""
    result = (
        series.astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )

    result = result.str.replace(r"\.0$", "", regex=True)

    return result


def normalize_locode(series):
    """Normalize UN/LOCODE values."""
    return (
        series.astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )


def parse_datetime_utc(series):
    """
    Convert timestamps to UTC.

    Explicit timezone offsets are respected.
    Naive timestamps are interpreted as UTC for consistency
    with the previous project analysis.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        return pd.to_datetime(
            series,
            errors="coerce",
            utc=True
        )


def prepare_dataset(df, dataset_name):
    """
    Create a standardized working copy.

    Original columns are retained. Standardized analytical
    columns are added separately.
    """

    result = df.copy()

    imo_col = find_column(
        result,
        [
            "IMO_Normalised",
            "IMO_Normalized",
            "IMO Number",
            "IMO",
            "vesselIMO",
            "vesselIMONumber",
        ],
    )

    locode_col = find_column(
        result,
        [
            "UNLOCODE_Normalised",
            "UNLOCODE_Normalized",
            "UN Location Code",
            "UNLocationCode",
            "LOCODE",
        ],
    )

    vessel_col = find_column(
        result,
        [
            "Vessel Name",
            "vesselName",
            "Vessel_Name",
        ],
        required=False,
    )

    port_col = find_column(
        result,
        [
            "Port",
            "Source_Port",
            "portName",
            "Port_Name",
        ],
        required=False,
    )

    arrival_col = find_column(
        result,
        [
            "Actual Arrival",
            "Actual_Arrival",
            "ARRI_ACT",
            "ActualArrival",
        ],
    )

    departure_col = find_column(
        result,
        [
            "Actual Departure",
            "Actual_Departure",
            "DEPA_ACT",
            "ActualDeparture",
        ],
    )

    result["Dataset_Name"] = dataset_name

    result["IMO_Analysis"] = normalize_imo(
        result[imo_col]
    )

    result["LOCODE_Analysis"] = normalize_locode(
        result[locode_col]
    )

    result["Vessel_Name_Analysis"] = (
        result[vessel_col].astype("string")
        if vessel_col is not None
        else pd.Series(pd.NA, index=result.index, dtype="string")
    )

    result["Port_Name_Analysis"] = (
        result[port_col].astype("string")
        if port_col is not None
        else pd.Series(pd.NA, index=result.index, dtype="string")
    )

    result["Actual_Arrival_UTC"] = parse_datetime_utc(
        result[arrival_col]
    )

    result["Actual_Departure_UTC"] = parse_datetime_utc(
        result[departure_col]
    )

    # Preserve source-level identifiers where available.
    source_row_col = find_column(
        result,
        [
            "Schedule_Source_Row",
            "Source_Row_Number",
            "Source_Row",
        ],
        required=False,
    )

    if source_row_col is not None:
        result["Source_Row_Analysis"] = result[source_row_col]
    else:
        result["Source_Row_Analysis"] = pd.NA

    call_ref_col = find_column(
        result,
        [
            "transportCallReference",
            "Transport Call Reference",
            "transport_call_reference",
        ],
        required=False,
    )

    if call_ref_col is not None:
        result["Transport_Call_Reference_Analysis"] = result[call_ref_col]
    else:
        result["Transport_Call_Reference_Analysis"] = pd.NA

    result["Port_Stay_Hours_Analysis"] = (
        result["Actual_Departure_UTC"]
        - result["Actual_Arrival_UTC"]
    ).dt.total_seconds() / 3600

    return result


def valid_actual_calls(df):
    """Return records with IMO, LOCODE and complete actual timestamps."""

    valid = df[
        df["IMO_Analysis"].notna()
        & df["LOCODE_Analysis"].notna()
        & df["Actual_Arrival_UTC"].notna()
        & df["Actual_Departure_UTC"].notna()
    ].copy()

    return valid


def make_transition_records(df):
    """
    Construct chronological transitions within each vessel.

    Records are ordered by actual arrival time.
    The transition elapsed time is calculated as:

        Next arrival - Previous departure

    This is inter-port elapsed time, not necessarily sailing time.
    """

    valid = valid_actual_calls(df)

    valid = valid.sort_values(
        ["IMO_Analysis", "Actual_Arrival_UTC", "Actual_Departure_UTC"],
        kind="stable",
    ).copy()

    records = []

    for imo, group in valid.groupby("IMO_Analysis", sort=False):

        group = group.reset_index(drop=False)

        for i in range(len(group) - 1):

            previous = group.iloc[i]
            current = group.iloc[i + 1]

            previous_departure = previous["Actual_Departure_UTC"]
            current_arrival = current["Actual_Arrival_UTC"]

            elapsed_hours = (
                current_arrival - previous_departure
            ).total_seconds() / 3600

            previous_locode = previous["LOCODE_Analysis"]
            current_locode = current["LOCODE_Analysis"]

            same_port = previous_locode == current_locode

            if same_port:
                transition_type = "SAME_PORT"
            else:
                transition_type = "DIFFERENT_PORT"

            records.append({
                "Dataset": previous["Dataset_Name"],
                "IMO": imo,
                "Vessel_Name": previous["Vessel_Name_Analysis"],

                "Previous_Source_Row": previous["Source_Row_Analysis"],
                "Current_Source_Row": current["Source_Row_Analysis"],

                "Previous_Call_Reference":
                    previous["Transport_Call_Reference_Analysis"],
                "Current_Call_Reference":
                    current["Transport_Call_Reference_Analysis"],

                "Previous_Port": previous["Port_Name_Analysis"],
                "Previous_LOCODE": previous_locode,
                "Previous_Arrival_UTC": previous["Actual_Arrival_UTC"],
                "Previous_Departure_UTC": previous_departure,

                "Current_Port": current["Port_Name_Analysis"],
                "Current_LOCODE": current_locode,
                "Current_Arrival_UTC": current_arrival,
                "Current_Departure_UTC":
                    current["Actual_Departure_UTC"],

                "Transition_Type": transition_type,
                "Inter_Port_Elapsed_Hours": elapsed_hours,

                "Negative_Transition": elapsed_hours < 0,
                "Zero_Transition": elapsed_hours == 0,

                "Interpretation":
                    "Inter-port elapsed time; not confirmed sailing time",
            })

    return pd.DataFrame(records)


# -----------------------------
# 4. LOAD INPUT DATA
# -----------------------------

print("\n" + "=" * 70)
print("SCRIPT 15: TRANSITION AND HORMUZ RELEVANCE INVESTIGATION")
print("=" * 70)

if not SCHEDULE_FILE.exists():
    raise FileNotFoundError(
        f"Schedule file not found: {SCHEDULE_FILE}"
    )

if not INDIVIDUAL_FILE.exists():
    raise FileNotFoundError(
        f"Individual calls file not found: {INDIVIDUAL_FILE}"
    )

schedule_raw = pd.read_csv(
    SCHEDULE_FILE,
    low_memory=False
)

individual_raw = pd.read_csv(
    INDIVIDUAL_FILE,
    low_memory=False
)

print("\nINPUT DATA")
print("-" * 70)
print("Schedule shape:", schedule_raw.shape)
print("Individual calls shape:", individual_raw.shape)

schedule = prepare_dataset(
    schedule_raw,
    "Schedule"
)

individual = prepare_dataset(
    individual_raw,
    "Individual"
)

print("Standardized Schedule shape:", schedule.shape)
print("Standardized Individual shape:", individual.shape)


# ============================================================
# SECTION 1
# INVESTIGATE THE SEVEN NEGATIVE SCHEDULE TRANSITIONS
# ============================================================

print("\n" + "=" * 70)
print("SECTION 1: NEGATIVE SCHEDULE TRANSITIONS")
print("=" * 70)

schedule_transitions = make_transition_records(schedule)

negative_transitions = schedule_transitions[
    schedule_transitions["Negative_Transition"]
].copy()


def classify_negative_transition(row):
    """
    Preliminary classification only.
    It does not claim the underlying cause is confirmed.
    """

    if row["Previous_LOCODE"] == row["Current_LOCODE"]:
        return "SAME_PORT_NEGATIVE_TRANSITION"

    if (
        pd.notna(row["Previous_Source_Row"])
        and pd.notna(row["Current_Source_Row"])
    ):
        return "DIFFERENT_PORT_NEGATIVE_TRANSITION_WITH_SOURCE_ROWS"

    return "DIFFERENT_PORT_NEGATIVE_TRANSITION"


if not negative_transitions.empty:

    negative_transitions["Preliminary_Classification"] = (
        negative_transitions.apply(
            classify_negative_transition,
            axis=1
        )
    )

    negative_transitions["Investigation_Status"] = (
        "REQUIRES_MANUAL_SOURCE_REVIEW"
    )

    negative_transitions["Correction_Applied"] = False

else:
    negative_transitions["Preliminary_Classification"] = pd.Series(
        dtype="string"
    )
    negative_transitions["Investigation_Status"] = pd.Series(
        dtype="string"
    )
    negative_transitions["Correction_Applied"] = pd.Series(
        dtype="bool"
    )


negative_file = (
    OUTPUT_TABLES
    / "15_negative_transition_investigation.csv"
)

negative_transitions.to_csv(
    negative_file,
    index=False
)

print("Total Schedule transitions:", len(schedule_transitions))
print("Negative Schedule transitions:", len(negative_transitions))

if len(negative_transitions) != 7:
    print(
        "NOTE: Script 14 reported seven negative transitions. "
        "This script found a different count. Check timestamp "
        "selection, sorting and source dataset versions."
    )

print("\nNegative transition details:")
if not negative_transitions.empty:
    print(
        negative_transitions[
            [
                "IMO",
                "Vessel_Name",
                "Previous_LOCODE",
                "Current_LOCODE",
                "Previous_Departure_UTC",
                "Current_Arrival_UTC",
                "Inter_Port_Elapsed_Hours",
                "Previous_Source_Row",
                "Current_Source_Row",
            ]
        ].to_string(index=False)
    )
else:
    print("No negative transitions found.")


# ============================================================
# SECTION 2
# SEPARATE SAME-PORT AND DIFFERENT-PORT TRANSITIONS
# ============================================================

print("\n" + "=" * 70)
print("SECTION 2: SAME-PORT AND DIFFERENT-PORT TRANSITIONS")
print("=" * 70)

individual_transitions = make_transition_records(individual)

# Keep the Schedule and Individual datasets separate.
same_port_schedule = schedule_transitions[
    schedule_transitions["Transition_Type"] == "SAME_PORT"
].copy()

different_port_schedule = schedule_transitions[
    schedule_transitions["Transition_Type"] == "DIFFERENT_PORT"
].copy()

same_port_individual = individual_transitions[
    individual_transitions["Transition_Type"] == "SAME_PORT"
].copy()

different_port_individual = individual_transitions[
    individual_transitions["Transition_Type"] == "DIFFERENT_PORT"
].copy()


# Add a cautious interpretation for same-port transitions.
def classify_same_port_transition(row):

    elapsed = row["Inter_Port_Elapsed_Hours"]

    if elapsed < 0:
        return "NEGATIVE_SAME_PORT_TRANSITION"

    if elapsed == 0:
        return "ZERO_GAP_SAME_PORT_TRANSITION"

    if elapsed <= 6:
        return "SHORT_GAP_SAME_PORT_TRANSITION"

    if elapsed <= 48:
        return "MODERATE_GAP_SAME_PORT_TRANSITION"

    return "LONG_GAP_SAME_PORT_TRANSITION"


for frame in [same_port_schedule, same_port_individual]:
    frame["Same_Port_Classification"] = frame.apply(
        classify_same_port_transition,
        axis=1
    )


# Different-port transitions are not automatically sailing legs.
for frame in [different_port_schedule, different_port_individual]:
    frame["Movement_Classification"] = np.where(
        frame["Negative_Transition"],
        "NEGATIVE_ELAPSED_TIME_REQUIRES_INVESTIGATION",
        "DIFFERENT_PORT_MOVEMENT_REQUIRES_ROUTE_VALIDATION",
    )


same_schedule_file = (
    OUTPUT_TABLES / "15_schedule_same_port_transitions.csv"
)

different_schedule_file = (
    OUTPUT_TABLES / "15_schedule_different_port_transitions.csv"
)

same_individual_file = (
    OUTPUT_TABLES / "15_individual_same_port_transitions.csv"
)

different_individual_file = (
    OUTPUT_TABLES / "15_individual_different_port_transitions.csv"
)

same_port_schedule.to_csv(same_schedule_file, index=False)
different_port_schedule.to_csv(different_schedule_file, index=False)

same_port_individual.to_csv(same_individual_file, index=False)
different_port_individual.to_csv(different_individual_file, index=False)


transition_summary = pd.DataFrame([
    {
        "Dataset": "Schedule",
        "Total_Transitions": len(schedule_transitions),
        "Same_Port_Transitions": len(same_port_schedule),
        "Different_Port_Transitions": len(different_port_schedule),
        "Negative_Transitions": int(
            schedule_transitions["Negative_Transition"].sum()
        ),
    },
    {
        "Dataset": "Individual",
        "Total_Transitions": len(individual_transitions),
        "Same_Port_Transitions": len(same_port_individual),
        "Different_Port_Transitions": len(different_port_individual),
        "Negative_Transitions": int(
            individual_transitions["Negative_Transition"].sum()
        ),
    },
])

transition_summary.to_csv(
    OUTPUT_TABLES / "15_transition_classification_summary.csv",
    index=False
)

print("\nTransition classification summary:")
print(transition_summary.to_string(index=False))


# ============================================================
# SECTION 3
# GULF-REGION VESSELS AND CHRONOLOGICAL SEQUENCES
# ============================================================

print("\n" + "=" * 70)
print("SECTION 3: GULF-REGION VESSEL INVESTIGATION")
print("=" * 70)


def classify_port_region(locode):
    """
    Initial curated regional classification.

    This is a research screening list, not a complete geographical
    database. Review and expand it using the port master.
    """

    if pd.isna(locode):
        return "UNKNOWN"

    locode = str(locode).strip().upper()

    if locode in GULF_CORE_PORTS:
        return "GULF_CORE"

    if locode in STRAIT_APPROACH_PORTS:
        return "STRAIT_APPROACH"

    return "OUTSIDE_INITIAL_SCREENING_LIST"


individual["Regional_Category"] = (
    individual["LOCODE_Analysis"].apply(classify_port_region)
)

individual["Regional_Port_Flag"] = individual[
    "Regional_Category"
].isin(
    ["GULF_CORE", "STRAIT_APPROACH"]
)

# Identify candidate vessel IMOs using all individual records,
# not only records with complete actual timestamps.
candidate_imos = set(
    individual.loc[
        individual["Regional_Port_Flag"],
        "IMO_Analysis"
    ].dropna().unique()
)

gulf_vessel_calls = individual[
    individual["Regional_Port_Flag"]
].copy()

gulf_vessel_calls = gulf_vessel_calls.sort_values(
    ["IMO_Analysis", "Actual_Arrival_UTC"],
    kind="stable"
)

# Retrieve all available records for every candidate vessel.
# This includes calls outside the Gulf region.
gulf_candidate_sequences = individual[
    individual["IMO_Analysis"].isin(candidate_imos)
].copy()

gulf_candidate_sequences = gulf_candidate_sequences.sort_values(
    ["IMO_Analysis", "Actual_Arrival_UTC"],
    kind="stable"
)

gulf_vessel_calls.to_csv(
    OUTPUT_TABLES / "15_gulf_region_vessel_calls.csv",
    index=False
)

gulf_candidate_sequences.to_csv(
    OUTPUT_TABLES / "15_gulf_candidate_vessel_sequences.csv",
    index=False
)


# Build vessel-level summary.
gulf_summary_rows = []

for imo, group in gulf_candidate_sequences.groupby(
    "IMO_Analysis",
    dropna=True
):

    group = group.sort_values(
        "Actual_Arrival_UTC",
        kind="stable"
    )

    regional_calls = group[group["Regional_Port_Flag"]]

    valid_arrivals = group["Actual_Arrival_UTC"].dropna()

    gulf_summary_rows.append({
        "IMO": imo,

        "Vessel_Name": (
            group["Vessel_Name_Analysis"].dropna().iloc[0]
            if group["Vessel_Name_Analysis"].notna().any()
            else pd.NA
        ),

        "Total_Recorded_Calls": len(group),

        "Gulf_Core_Calls": int(
            (group["Regional_Category"] == "GULF_CORE").sum()
        ),

        "Strait_Approach_Calls": int(
            (group["Regional_Category"] == "STRAIT_APPROACH").sum()
        ),

        "Unique_Recorded_Ports": group[
            "LOCODE_Analysis"
        ].nunique(),

        "First_Recorded_Actual_Arrival_UTC": (
            valid_arrivals.min()
            if not valid_arrivals.empty
            else pd.NaT
        ),

        "Last_Recorded_Actual_Arrival_UTC": (
            valid_arrivals.max()
            if not valid_arrivals.empty
            else pd.NaT
        ),

        "Regional_LOCODES": "; ".join(
            sorted(
                regional_calls["LOCODE_Analysis"]
                .dropna()
                .unique()
                .tolist()
            )
        ),

        "AIS_Verification_Required": True,

        "Transit_Confirmed": False,

        "Note": (
            "Gulf-region port call identifies a candidate vessel only; "
            "AIS trajectory is required to establish Strait transit."
        ),
    })


gulf_vessel_summary = pd.DataFrame(gulf_summary_rows)

gulf_vessel_summary.to_csv(
    OUTPUT_TABLES / "15_gulf_candidate_vessel_summary.csv",
    index=False
)

# Create an explicit port screening reference file.
port_screening_rows = []

for locode, port_name in GULF_CORE_PORTS.items():
    port_screening_rows.append({
        "LOCODE": locode,
        "Port_Name": port_name,
        "Screening_Category": "GULF_CORE",
        "Inside_Persian_Gulf_Screening": True,
        "AIS_Transit_Proof": False,
    })

for locode, port_name in STRAIT_APPROACH_PORTS.items():
    port_screening_rows.append({
        "LOCODE": locode,
        "Port_Name": port_name,
        "Screening_Category": "STRAIT_APPROACH",
        "Inside_Persian_Gulf_Screening": False,
        "AIS_Transit_Proof": False,
    })

port_screening = pd.DataFrame(port_screening_rows)

port_screening.to_csv(
    OUTPUT_TABLES / "15_initial_gulf_port_screening_reference.csv",
    index=False
)

print("Candidate vessel count:", len(candidate_imos))
print("Gulf-region call records:", len(gulf_vessel_calls))
print("Full candidate vessel sequence records:", len(gulf_candidate_sequences))

print("\nGulf candidate vessel summary:")
if not gulf_vessel_summary.empty:
    print(
        gulf_vessel_summary[
            [
                "IMO",
                "Vessel_Name",
                "Total_Recorded_Calls",
                "Gulf_Core_Calls",
                "Strait_Approach_Calls",
                "Unique_Recorded_Ports",
            ]
        ].to_string(index=False)
    )
else:
    print("No candidate vessels found using the initial port screening list.")


# ============================================================
# SECTION 4
# AIS TRAJECTORY VERIFICATION REGISTER
# ============================================================

print("\n" + "=" * 70)
print("SECTION 4: AIS TRAJECTORY VERIFICATION REGISTER")
print("=" * 70)

# Use Individual dataset movements for the initial AIS register.
# Only different-LOCODE movements are included.
#
# Movements with at least one endpoint in the initial Gulf or
# Strait-approach screening list are flagged for AIS review.

ais_register = different_port_individual.copy()

ais_register["Previous_Regional_Category"] = (
    ais_register["Previous_LOCODE"].apply(classify_port_region)
)

ais_register["Current_Regional_Category"] = (
    ais_register["Current_LOCODE"].apply(classify_port_region)
)

ais_register["Previous_Is_Gulf_Core"] = (
    ais_register["Previous_Regional_Category"] == "GULF_CORE"
)

ais_register["Current_Is_Gulf_Core"] = (
    ais_register["Current_Regional_Category"] == "GULF_CORE"
)

ais_register["Previous_Is_Strait_Approach"] = (
    ais_register["Previous_Regional_Category"] == "STRAIT_APPROACH"
)

ais_register["Current_Is_Strait_Approach"] = (
    ais_register["Current_Regional_Category"] == "STRAIT_APPROACH"
)

ais_register["AIS_Review_Required"] = (
    ais_register["Previous_Regional_Category"].isin(
        ["GULF_CORE", "STRAIT_APPROACH"]
    )
    |
    ais_register["Current_Regional_Category"].isin(
        ["GULF_CORE", "STRAIT_APPROACH"]
    )
)

ais_register = ais_register[
    ais_register["AIS_Review_Required"]
].copy()


def classify_ais_review_priority(row):

    previous_core = row["Previous_Is_Gulf_Core"]
    current_core = row["Current_Is_Gulf_Core"]

    previous_approach = row["Previous_Is_Strait_Approach"]
    current_approach = row["Current_Is_Strait_Approach"]

    if previous_core and current_core:
        return "REGIONAL_GULF_MOVEMENT"

    if previous_core != current_core:
        return "HIGH_PRIORITY_GULF_BOUNDARY_MOVEMENT"

    if previous_approach or current_approach:
        return "STRAIT_APPROACH_MOVEMENT"

    return "REVIEW"


ais_register["AIS_Review_Priority"] = ais_register.apply(
    classify_ais_review_priority,
    axis=1
)

# Add fields to be completed only after obtaining and examining AIS.
ais_register["AIS_Data_Source"] = pd.NA
ais_register["AIS_Data_Available"] = "NOT_YET_CHECKED"
ais_register["AIS_Coverage_Start_UTC"] = pd.NaT
ais_register["AIS_Coverage_End_UTC"] = pd.NaT
ais_register["Strait_Crossing_Status"] = "NOT_VERIFIED"
ais_register["Crossing_Time_UTC"] = pd.NaT
ais_register["AIS_Evidence_Reference"] = pd.NA

ais_register["Verification_Instructions"] = (
    "Retrieve AIS positions for this IMO between the recorded "
    "departure and next arrival; inspect whether the trajectory "
    "crosses the Strait of Hormuz."
)

ais_register["Important_Limitation"] = (
    "Port-call endpoints alone cannot establish the vessel's route."
)

ais_register_file = (
    OUTPUT_TABLES / "15_AIS_trajectory_verification_register.csv"
)

ais_register.to_csv(
    ais_register_file,
    index=False
)

print("Different-port Individual transitions:", len(different_port_individual))
print("Movements flagged for AIS review:", len(ais_register))

if not ais_register.empty:
    print("\nAIS review priority summary:")
    print(
        ais_register["AIS_Review_Priority"]
        .value_counts(dropna=False)
        .to_string()
    )


# ============================================================
# 5. OVERALL SUMMARY TABLE
# ============================================================

overall_summary = pd.DataFrame([
    {
        "Metric": "Schedule valid actual calls",
        "Value": len(valid_actual_calls(schedule)),
    },
    {
        "Metric": "Schedule transitions",
        "Value": len(schedule_transitions),
    },
    {
        "Metric": "Negative Schedule transitions",
        "Value": len(negative_transitions),
    },
    {
        "Metric": "Schedule same-port transitions",
        "Value": len(same_port_schedule),
    },
    {
        "Metric": "Schedule different-port transitions",
        "Value": len(different_port_schedule),
    },
    {
        "Metric": "Individual valid actual calls",
        "Value": len(valid_actual_calls(individual)),
    },
    {
        "Metric": "Individual transitions",
        "Value": len(individual_transitions),
    },
    {
        "Metric": "Individual same-port transitions",
        "Value": len(same_port_individual),
    },
    {
        "Metric": "Individual different-port transitions",
        "Value": len(different_port_individual),
    },
    {
        "Metric": "Gulf candidate vessels",
        "Value": len(candidate_imos),
    },
    {
        "Metric": "Gulf-region call records",
        "Value": len(gulf_vessel_calls),
    },
    {
        "Metric": "Full candidate vessel sequence records",
        "Value": len(gulf_candidate_sequences),
    },
    {
        "Metric": "AIS movements requiring review",
        "Value": len(ais_register),
    },
])

overall_summary.to_csv(
    OUTPUT_TABLES / "15_overall_investigation_summary.csv",
    index=False
)


# ============================================================
# 6. GENERATE TEXT REPORT
# ============================================================

report_file = (
    OUTPUT_REPORTS / "15_transition_and_hormuz_relevance_report.txt"
)

with open(report_file, "w", encoding="utf-8") as f:

    f.write("=" * 75 + "\n")
    f.write("SCRIPT 15: TRANSITION AND HORMUZ RELEVANCE INVESTIGATION\n")
    f.write("=" * 75 + "\n\n")

    f.write("1. INPUT DATA\n")
    f.write("-" * 75 + "\n")
    f.write(f"Schedule input shape: {schedule_raw.shape}\n")
    f.write(f"Individual input shape: {individual_raw.shape}\n\n")

    f.write("2. NEGATIVE SCHEDULE TRANSITIONS\n")
    f.write("-" * 75 + "\n")
    f.write(f"Schedule transitions: {len(schedule_transitions)}\n")
    f.write(f"Negative transitions: {len(negative_transitions)}\n")
    f.write("No timestamps were automatically corrected.\n")
    f.write("No source records were deleted.\n\n")

    f.write("3. TRANSITION CLASSIFICATION\n")
    f.write("-" * 75 + "\n")
    f.write(transition_summary.to_string(index=False))
    f.write("\n\n")

    f.write("4. GULF-REGION VESSEL INVESTIGATION\n")
    f.write("-" * 75 + "\n")
    f.write(f"Candidate vessel count: {len(candidate_imos)}\n")
    f.write(f"Gulf-region call records: {len(gulf_vessel_calls)}\n")
    f.write(
        "Full candidate sequence records: "
        f"{len(gulf_candidate_sequences)}\n\n"
    )

    f.write("Initial Gulf-core port screening list:\n")
    for locode, name in GULF_CORE_PORTS.items():
        f.write(f"  {locode}: {name}\n")

    f.write("\nInitial Strait-approach screening list:\n")
    for locode, name in STRAIT_APPROACH_PORTS.items():
        f.write(f"  {locode}: {name}\n")

    f.write("\n5. AIS VERIFICATION REGISTER\n")
    f.write("-" * 75 + "\n")
    f.write(
        f"Movements flagged for AIS review: {len(ais_register)}\n"
    )
    f.write("No Strait crossings have been confirmed by this script.\n\n")

    f.write("6. METHODOLOGICAL LIMITATIONS\n")
    f.write("-" * 75 + "\n")
    f.write(
        "- A port call does not prove that a vessel crossed the Strait.\n"
    )
    f.write(
        "- Port-to-port elapsed time is not necessarily sailing time.\n"
    )
    f.write(
        "- AIS trajectory data is required to establish actual crossing.\n"
    )
    f.write(
        "- The initial Gulf port list is curated and not exhaustive.\n"
    )
    f.write(
        "- Same-LOCODE transitions are retained and not automatically deleted.\n"
    )
    f.write(
        "- Negative transitions are flagged, not automatically corrected.\n"
    )
    f.write(
        "- Schedule and Individual datasets are analyzed separately.\n"
    )

    f.write("\n7. OUTPUT FILES\n")
    f.write("-" * 75 + "\n")

    output_files = [
        "15_negative_transition_investigation.csv",
        "15_schedule_same_port_transitions.csv",
        "15_schedule_different_port_transitions.csv",
        "15_individual_same_port_transitions.csv",
        "15_individual_different_port_transitions.csv",
        "15_transition_classification_summary.csv",
        "15_gulf_region_vessel_calls.csv",
        "15_gulf_candidate_vessel_sequences.csv",
        "15_gulf_candidate_vessel_summary.csv",
        "15_initial_gulf_port_screening_reference.csv",
        "15_AIS_trajectory_verification_register.csv",
        "15_overall_investigation_summary.csv",
    ]

    for filename in output_files:
        f.write(f"- outputs/tables/{filename}\n")

print("\n" + "=" * 70)
print("SCRIPT 15 COMPLETED")
print("=" * 70)

print("\nMAIN OUTPUTS")
print("-" * 70)

print("Negative transition investigation:")
print(negative_file)

print("\nGulf candidate vessel summary:")
print(OUTPUT_TABLES / "15_gulf_candidate_vessel_summary.csv")

print("\nAIS verification register:")
print(ais_register_file)

print("\nOverall report:")
print(report_file)

print("\nAll original source records have been preserved.")
