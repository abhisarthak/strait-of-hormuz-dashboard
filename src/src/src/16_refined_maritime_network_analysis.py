
from pathlib import Path
import re
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# SCRIPT 16
# REFINED MARITIME NETWORK AND TRANSITION ANALYSIS
#
# Main Schedule input:
#   15B_schedule_sequence_ready.csv
#
# Comparison datasets:
#   13_final_consolidated_individual_calls.csv
#   13_schedule_actual_baseline_core.csv
#   13_schedule_actual_baseline_conservative.csv
#
# Objectives:
# 1. Rebuild vessel sequences after Script 15B.
# 2. Separate same-port and different-port transitions.
# 3. Calculate inter-port elapsed-time distributions.
# 4. Calculate port-level and vessel-level activity.
# 5. Calculate monthly and weekly activity.
# 6. Construct a directed port-transition network.
# 7. Compare Core, Sequence-Ready and Conservative baselines.
# 8. Generate data-quality diagnostics.
#
# IMPORTANT:
# - Schedule and Individual datasets remain separate.
# - No source records are deleted or modified.
# - Inter-port elapsed time is NOT assumed to be sailing time.
# - Port calls do NOT prove Strait of Hormuz transit.
# ============================================================


# ------------------------------------------------------------
# 1. PROJECT PATHS
# ------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

PROCESSED = ROOT / "data" / "processed"
SIMULATION_INPUTS = ROOT / "data" / "simulation_inputs"

TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"
REPORTS = ROOT / "outputs" / "reports"

for folder in [TABLES, FIGURES, REPORTS]:
    folder.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------
# 2. INPUT FILES
# ------------------------------------------------------------

INPUT_FILES = {
    "Schedule_Sequence_Ready": (
        PROCESSED / "15B_schedule_sequence_ready.csv"
    ),

    "Individual": (
        PROCESSED / "13_final_consolidated_individual_calls.csv"
    ),

    "Schedule_Core": (
        SIMULATION_INPUTS / "13_schedule_actual_baseline_core.csv"
    ),

    "Schedule_Conservative": (
        SIMULATION_INPUTS / "13_schedule_actual_baseline_conservative.csv"
    ),
}


# ------------------------------------------------------------
# 3. GENERAL HELPER FUNCTIONS
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


def normalize_imo(series):

    result = (
        series.astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )

    return result.str.replace(r"\.0$", "", regex=True)


def normalize_locode(series):

    return (
        series.astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )


def parse_datetime_utc(series):

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        return pd.to_datetime(
            series,
            errors="coerce",
            utc=True
        )


def get_optional_series(df, candidates):

    col = find_column(
        df,
        candidates,
        required=False
    )

    if col is None:
        return pd.Series(
            pd.NA,
            index=df.index,
            dtype="string"
        )

    return df[col]


# ------------------------------------------------------------
# 4. STANDARDIZE DATASET
# ------------------------------------------------------------

def prepare_dataset(df, dataset_name):

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
        ]
    )

    locode_col = find_column(
        result,
        [
            "UNLOCODE_Normalised",
            "UNLOCODE_Normalized",
            "UN Location Code",
            "UN/LOCODE",
            "UNLocationCode",
            "LOCODE",
        ]
    )

    vessel_col = find_column(
        result,
        [
            "Vessel Name",
            "Vessel_Name",
            "vesselName",
        ],
        required=False
    )

    port_col = find_column(
        result,
        [
            "Port",
            "Source_Port",
            "portName",
            "Port_Name",
        ],
        required=False
    )

    arrival_col = find_column(
        result,
        [
            "Actual Arrival",
            "Actual_Arrival",
            "ARRI_ACT",
        ]
    )

    departure_col = find_column(
        result,
        [
            "Actual Departure",
            "Actual_Departure",
            "DEPA_ACT",
        ]
    )

    source_row_col = find_column(
        result,
        [
            "Schedule_Source_Row",
            "Source_Row_Number",
            "Source_Row",
        ],
        required=False
    )

    service_col = find_column(
        result,
        [
            "Carrier Service Code",
            "Service Code",
            "Service_Code",
        ],
        required=False
    )

    result["Dataset_Analysis"] = dataset_name

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

    result["Service_Code_Analysis"] = (
        result[service_col].astype("string")
        if service_col is not None
        else pd.Series(pd.NA, index=result.index, dtype="string")
    )

    result["Actual_Arrival_UTC"] = parse_datetime_utc(
        result[arrival_col]
    )

    result["Actual_Departure_UTC"] = parse_datetime_utc(
        result[departure_col]
    )

    if source_row_col is not None:
        result["Source_Row_Analysis"] = result[source_row_col]
    else:
        result["Source_Row_Analysis"] = pd.NA

    result["Port_Stay_Hours"] = (
        result["Actual_Departure_UTC"]
        - result["Actual_Arrival_UTC"]
    ).dt.total_seconds() / 3600

    return result


# ------------------------------------------------------------
# 5. BUILD VALID ACTUAL PORT-CALL DATA
# ------------------------------------------------------------

def get_valid_calls(df):

    valid = df[
        df["IMO_Analysis"].notna()
        & df["LOCODE_Analysis"].notna()
        & df["Actual_Arrival_UTC"].notna()
        & df["Actual_Departure_UTC"].notna()
    ].copy()

    valid["Valid_Port_Stay"] = (
        valid["Port_Stay_Hours"] >= 0
    )

    return valid


# ------------------------------------------------------------
# 6. BUILD CHRONOLOGICAL VESSEL SEQUENCES
# ------------------------------------------------------------

def build_vessel_sequences(df):

    valid = get_valid_calls(df)

    valid = valid.sort_values(
        [
            "IMO_Analysis",
            "Actual_Arrival_UTC",
            "Actual_Departure_UTC",
            "Source_Row_Analysis",
        ],
        kind="stable"
    ).copy()

    valid["Call_Sequence_Number"] = (
        valid.groupby("IMO_Analysis").cumcount() + 1
    )

    valid["Previous_LOCODE"] = (
        valid.groupby("IMO_Analysis")["LOCODE_Analysis"].shift(1)
    )

    valid["Previous_Port"] = (
        valid.groupby("IMO_Analysis")["Port_Name_Analysis"].shift(1)
    )

    valid["Previous_Arrival_UTC"] = (
        valid.groupby("IMO_Analysis")["Actual_Arrival_UTC"].shift(1)
    )

    valid["Previous_Departure_UTC"] = (
        valid.groupby("IMO_Analysis")["Actual_Departure_UTC"].shift(1)
    )

    valid["Inter_Port_Elapsed_Hours"] = (
        valid["Actual_Arrival_UTC"]
        - valid["Previous_Departure_UTC"]
    ).dt.total_seconds() / 3600

    
# Classify transitions safely when Previous_LOCODE contains pd.NA.

    valid["Transition_Type"] = "DIFFERENT_PORT"

    first_call_mask = valid["Previous_LOCODE"].isna()

    same_port_mask = (
    valid["Previous_LOCODE"]
    .eq(valid["LOCODE_Analysis"])
    .fillna(False)
)

    valid.loc[first_call_mask, "Transition_Type"] = (
    "FIRST_RECORDED_CALL"
)

    valid.loc[
    ~first_call_mask & same_port_mask,
    "Transition_Type"
] = "SAME_PORT"


    return valid


# ------------------------------------------------------------
# 7. BUILD TRANSITION TABLE
# ------------------------------------------------------------

def build_transition_table(sequence_df):

    transitions = sequence_df[
        sequence_df["Previous_LOCODE"].notna()
    ].copy()

    transitions["Current_LOCODE"] = transitions["LOCODE_Analysis"]

    transitions["Negative_Elapsed_Time"] = (
        transitions["Inter_Port_Elapsed_Hours"] < 0
    )

    transitions["Zero_Elapsed_Time"] = (
        transitions["Inter_Port_Elapsed_Hours"] == 0
    )

    transitions["Positive_Elapsed_Time"] = (
        transitions["Inter_Port_Elapsed_Hours"] > 0
    )

    def classify_transition(row):

        if row["Transition_Type"] == "SAME_PORT":

            if row["Inter_Port_Elapsed_Hours"] < 0:
                return "SAME_PORT_NEGATIVE"

            if row["Inter_Port_Elapsed_Hours"] == 0:
                return "SAME_PORT_ZERO_GAP"

            if row["Inter_Port_Elapsed_Hours"] <= 6:
                return "SAME_PORT_SHORT_GAP"

            if row["Inter_Port_Elapsed_Hours"] <= 48:
                return "SAME_PORT_MODERATE_GAP"

            return "SAME_PORT_LONG_GAP"

        if row["Inter_Port_Elapsed_Hours"] < 0:
            return "DIFFERENT_PORT_NEGATIVE"

        if row["Inter_Port_Elapsed_Hours"] == 0:
            return "DIFFERENT_PORT_ZERO_GAP"

        return "DIFFERENT_PORT_POSITIVE_GAP"

    transitions["Transition_Classification"] = (
        transitions.apply(
            classify_transition,
            axis=1
        )
    )

    transitions["Elapsed_Time_Interpretation"] = (
        "Inter-port elapsed time; not confirmed sailing time"
    )

    return transitions


# ------------------------------------------------------------
# 8. PORT ACTIVITY STATISTICS
# ------------------------------------------------------------

def calculate_port_activity(valid):

    result = (
        valid.groupby(
            ["LOCODE_Analysis", "Port_Name_Analysis"],
            dropna=False
        )
        .agg(
            Port_Calls=("IMO_Analysis", "size"),
            Unique_Vessels=("IMO_Analysis", "nunique"),
            Unique_Services=("Service_Code_Analysis", "nunique"),
            Mean_Port_Stay_Hours=("Port_Stay_Hours", "mean"),
            Median_Port_Stay_Hours=("Port_Stay_Hours", "median"),
            P90_Port_Stay_Hours=(
                "Port_Stay_Hours",
                lambda x: x.quantile(0.90)
            ),
            Minimum_Port_Stay_Hours=("Port_Stay_Hours", "min"),
            Maximum_Port_Stay_Hours=("Port_Stay_Hours", "max"),
        )
        .reset_index()
    )

    result = result.sort_values(
        "Port_Calls",
        ascending=False
    )

    return result


# ------------------------------------------------------------
# 9. VESSEL ACTIVITY STATISTICS
# ------------------------------------------------------------

def calculate_vessel_activity(valid):

    result = (
        valid.groupby(
            "IMO_Analysis",
            dropna=False
        )
        .agg(
            Vessel_Name=("Vessel_Name_Analysis", "first"),
            Recorded_Port_Calls=("LOCODE_Analysis", "size"),
            Unique_Ports=("LOCODE_Analysis", "nunique"),
            Unique_Services=("Service_Code_Analysis", "nunique"),
            Mean_Port_Stay_Hours=("Port_Stay_Hours", "mean"),
            Median_Port_Stay_Hours=("Port_Stay_Hours", "median"),
            First_Recorded_Arrival=("Actual_Arrival_UTC", "min"),
            Last_Recorded_Arrival=("Actual_Arrival_UTC", "max"),
        )
        .reset_index()
    )

    result = result.rename(
        columns={"IMO_Analysis": "IMO"}
    )

    return result.sort_values(
        "Recorded_Port_Calls",
        ascending=False
    )


# ------------------------------------------------------------
# 10. PORT STAY DISTRIBUTION
# ------------------------------------------------------------

def calculate_port_stay_statistics(valid):

    result = (
        valid.groupby(
            ["LOCODE_Analysis", "Port_Name_Analysis"],
            dropna=False
        )["Port_Stay_Hours"]
        .agg(
            Sample_Size="count",
            Mean="mean",
            Median="median",
            Standard_Deviation="std",
            Minimum="min",
            P25=lambda x: x.quantile(0.25),
            P75=lambda x: x.quantile(0.75),
            P90=lambda x: x.quantile(0.90),
            Maximum="max",
        )
        .reset_index()
    )

    result["Sample_Size_Category"] = np.select(
        [
            result["Sample_Size"] < 5,
            result["Sample_Size"] < 15,
            result["Sample_Size"] < 30,
        ],
        [
            "VERY_SMALL_SAMPLE",
            "SMALL_SAMPLE",
            "MODERATE_SAMPLE",
        ],
        default="LARGER_SAMPLE"
    )

    return result.sort_values(
        "Sample_Size",
        ascending=False
    )


# ------------------------------------------------------------
# 11. TRANSITION STATISTICS
# ------------------------------------------------------------

def calculate_transition_statistics(transitions):

    # Separate same-port and different-port movements.
    # Only positive elapsed times are summarized as distributions.

    valid_transitions = transitions[
        transitions["Inter_Port_Elapsed_Hours"] > 0
    ].copy()

    result = (
        valid_transitions.groupby(
            [
                "Transition_Type",
                "Previous_LOCODE",
                "Current_LOCODE",
            ],
            dropna=False
        )["Inter_Port_Elapsed_Hours"]
        .agg(
            Transition_Count="count",
            Mean_Elapsed_Hours="mean",
            Median_Elapsed_Hours="median",
            Standard_Deviation_Hours="std",
            Minimum_Hours="min",
            P25_Hours=lambda x: x.quantile(0.25),
            P75_Hours=lambda x: x.quantile(0.75),
            P90_Hours=lambda x: x.quantile(0.90),
            Maximum_Hours="max",
        )
        .reset_index()
    )

    result["Sample_Size_Category"] = np.select(
        [
            result["Transition_Count"] < 3,
            result["Transition_Count"] < 5,
            result["Transition_Count"] < 10,
        ],
        [
            "VERY_SMALL_SAMPLE",
            "SMALL_SAMPLE",
            "LIMITED_SAMPLE",
        ],
        default="MORE_OBSERVATIONS"
    )

    result["Interpretation"] = (
        "Observed elapsed time, not pure sailing duration"
    )

    return result.sort_values(
        "Transition_Count",
        ascending=False
    )


# ------------------------------------------------------------
# 12. PORT-TO-PORT NETWORK EDGES
# ------------------------------------------------------------

def build_network_edges(transitions):

    different = transitions[
        transitions["Transition_Type"] == "DIFFERENT_PORT"
    ].copy()

    positive = different[
        different["Inter_Port_Elapsed_Hours"] > 0
    ].copy()

    if positive.empty:
        return pd.DataFrame()

    edges = (
        positive.groupby(
            ["Previous_LOCODE", "Current_LOCODE"],
            dropna=False
        )
        .agg(
            Observed_Transitions=("IMO_Analysis", "size"),
            Unique_Vessels=("IMO_Analysis", "nunique"),
            Mean_Elapsed_Hours=("Inter_Port_Elapsed_Hours", "mean"),
            Median_Elapsed_Hours=("Inter_Port_Elapsed_Hours", "median"),
            P90_Elapsed_Hours=(
                "Inter_Port_Elapsed_Hours",
                lambda x: x.quantile(0.90)
            ),
        )
        .reset_index()
    )

    edges["Edge_Interpretation"] = (
        "Observed consecutive port-call relationship; "
        "not a verified direct sailing route"
    )

    return edges.sort_values(
        "Observed_Transitions",
        ascending=False
    )


# ------------------------------------------------------------
# 13. MONTHLY AND WEEKLY ACTIVITY
# ------------------------------------------------------------

def calculate_time_activity(valid):

    work = valid.copy()

    # Convert to timezone-naive UTC solely for calendar grouping.
    # The original UTC timestamps remain unchanged.
    arrival_naive_utc = (
        work["Actual_Arrival_UTC"]
        .dt.tz_convert("UTC")
        .dt.tz_localize(None)
    )

    work["Arrival_Month"] = (
        arrival_naive_utc.dt.to_period("M").astype("string")
    )

    work["Arrival_Week"] = (
        arrival_naive_utc.dt.to_period("W").astype("string")
    )

    monthly = (
        work.groupby("Arrival_Month")
        .agg(
            Port_Calls=("IMO_Analysis", "size"),
            Unique_Vessels=("IMO_Analysis", "nunique"),
            Unique_Ports=("LOCODE_Analysis", "nunique"),
        )
        .reset_index()
    )

    weekly = (
        work.groupby("Arrival_Week")
        .agg(
            Port_Calls=("IMO_Analysis", "size"),
            Unique_Vessels=("IMO_Analysis", "nunique"),
            Unique_Ports=("LOCODE_Analysis", "nunique"),
        )
        .reset_index()
    )

    return monthly, weekly


# ------------------------------------------------------------
# 14. DATASET SUMMARY
# ------------------------------------------------------------

def calculate_dataset_summary(valid, original, sequences, transitions):

    return {
        "Dataset": original["Dataset_Analysis"].iloc[0],
        "Total_Records": len(original),
        "Valid_Actual_Calls": len(valid),
        "Excluded_From_Actual_Analysis": len(original) - len(valid),
        "Unique_Vessels": valid["IMO_Analysis"].nunique(),
        "Unique_Ports": valid["LOCODE_Analysis"].nunique(),
        "Unique_Services": valid["Service_Code_Analysis"].nunique(),
        "Negative_Port_Stays": int(
            (valid["Port_Stay_Hours"] < 0).sum()
        ),
        "Same_Port_Transitions": int(
            (transitions["Transition_Type"] == "SAME_PORT").sum()
        ),
        "Different_Port_Transitions": int(
            (transitions["Transition_Type"] == "DIFFERENT_PORT").sum()
        ),
        "Negative_Inter_Port_Transitions": int(
            transitions["Negative_Elapsed_Time"].sum()
        ),
        "Zero_Inter_Port_Transitions": int(
            transitions["Zero_Elapsed_Time"].sum()
        ),
        "Positive_Inter_Port_Transitions": int(
            transitions["Positive_Elapsed_Time"].sum()
        ),
        "Mean_Port_Stay_Hours": valid["Port_Stay_Hours"].mean(),
        "Median_Port_Stay_Hours": valid["Port_Stay_Hours"].median(),
        "P90_Port_Stay_Hours": valid["Port_Stay_Hours"].quantile(0.90),
    }


# ------------------------------------------------------------
# 15. LOAD ALL DATASETS
# ------------------------------------------------------------

print("\n" + "=" * 75)
print("SCRIPT 16: REFINED MARITIME NETWORK ANALYSIS")
print("=" * 75)

raw_datasets = {}

for dataset_name, path in INPUT_FILES.items():

    if not path.exists():
        raise FileNotFoundError(
            f"Required input file not found: {path}"
        )

    raw_datasets[dataset_name] = pd.read_csv(
        path,
        low_memory=False
    )

    print(
        f"Loaded {dataset_name}: "
        f"{raw_datasets[dataset_name].shape}"
    )

datasets = {}

for dataset_name, raw in raw_datasets.items():

    datasets[dataset_name] = prepare_dataset(
        raw,
        dataset_name
    )


# ------------------------------------------------------------
# 16. RUN ANALYSIS FOR EACH DATASET
# ------------------------------------------------------------

analysis_results = {}
summary_rows = []

for dataset_name, df in datasets.items():

    print("\n" + "=" * 75)
    print(f"ANALYSING: {dataset_name}")
    print("=" * 75)

    valid = get_valid_calls(df)

    sequences = build_vessel_sequences(df)

    transitions = build_transition_table(sequences)

    port_activity = calculate_port_activity(valid)

    vessel_activity = calculate_vessel_activity(valid)

    port_stays = calculate_port_stay_statistics(valid)

    transition_stats = calculate_transition_statistics(
        transitions
    )

    network_edges = build_network_edges(transitions)

    monthly, weekly = calculate_time_activity(valid)

    summary = calculate_dataset_summary(
        valid,
        df,
        sequences,
        transitions
    )

    analysis_results[dataset_name] = {
        "valid": valid,
        "sequences": sequences,
        "transitions": transitions,
        "port_activity": port_activity,
        "vessel_activity": vessel_activity,
        "port_stays": port_stays,
        "transition_stats": transition_stats,
        "network_edges": network_edges,
        "monthly": monthly,
        "weekly": weekly,
    }

    summary_rows.append(summary)

    print("Total records:", len(df))
    print("Valid actual calls:", len(valid))
    print("Unique vessels:", valid["IMO_Analysis"].nunique())
    print("Unique ports:", valid["LOCODE_Analysis"].nunique())
    print("Transitions:", len(transitions))

    print(
        "Same-port transitions:",
        (transitions["Transition_Type"] == "SAME_PORT").sum()
    )

    print(
        "Different-port transitions:",
        (transitions["Transition_Type"] == "DIFFERENT_PORT").sum()
    )

    print(
        "Negative inter-port transitions:",
        transitions["Negative_Elapsed_Time"].sum()
    )


# ------------------------------------------------------------
# 17. SAVE DATASET-SPECIFIC OUTPUTS
# ------------------------------------------------------------

for dataset_name, result in analysis_results.items():

    prefix = f"16_{dataset_name.lower()}"

    output_map = {
        "sequences": result["sequences"],
        "transitions": result["transitions"],
        "port_activity": result["port_activity"],
        "vessel_activity": result["vessel_activity"],
        "port_stays": result["port_stays"],
        "transition_statistics": result["transition_stats"],
        "network_edges": result["network_edges"],
        "monthly_activity": result["monthly"],
        "weekly_activity": result["weekly"],
    }

    for label, frame in output_map.items():

        filename = f"{prefix}_{label}.csv"

        frame.to_csv(
            TABLES / filename,
            index=False
        )

        print("Saved:", filename)


# ------------------------------------------------------------
# 18. CORE VS SEQUENCE-READY VS CONSERVATIVE COMPARISON
# ------------------------------------------------------------

comparison_names = [
    "Schedule_Core",
    "Schedule_Sequence_Ready",
    "Schedule_Conservative",
]

comparison_rows = []

for name in comparison_names:

    result = analysis_results[name]

    valid = result["valid"]
    transitions = result["transitions"]

    comparison_rows.append({
        "Baseline": name,
        "Valid_Actual_Calls": len(valid),
        "Unique_Vessels": valid["IMO_Analysis"].nunique(),
        "Unique_Ports": valid["LOCODE_Analysis"].nunique(),
        "Unique_Services": valid["Service_Code_Analysis"].nunique(),
        "Transition_Count": len(transitions),
        "Same_Port_Transitions": int(
            (transitions["Transition_Type"] == "SAME_PORT").sum()
        ),
        "Different_Port_Transitions": int(
            (transitions["Transition_Type"] == "DIFFERENT_PORT").sum()
        ),
        "Negative_Transitions": int(
            transitions["Negative_Elapsed_Time"].sum()
        ),
        "Mean_Port_Stay_Hours": valid["Port_Stay_Hours"].mean(),
        "Median_Port_Stay_Hours": valid["Port_Stay_Hours"].median(),
        "P90_Port_Stay_Hours": valid["Port_Stay_Hours"].quantile(0.90),
    })

baseline_comparison = pd.DataFrame(comparison_rows)

baseline_comparison.to_csv(
    TABLES / "16_baseline_sensitivity_comparison.csv",
    index=False
)

print("\nBASELINE SENSITIVITY COMPARISON")
print("-" * 75)
print(baseline_comparison.to_string(index=False))


# ------------------------------------------------------------
# 19. REVISED SCHEDULE DIAGNOSTICS
# ------------------------------------------------------------

schedule_result = analysis_results["Schedule_Sequence_Ready"]

schedule_valid = schedule_result["valid"]

schedule_transitions = schedule_result["transitions"]

same_port = schedule_transitions[
    schedule_transitions["Transition_Type"] == "SAME_PORT"
].copy()

different_port = schedule_transitions[
    schedule_transitions["Transition_Type"] == "DIFFERENT_PORT"
].copy()

diagnostics = pd.DataFrame([
    {
        "Diagnostic": "Sequence-ready Schedule input records",
        "Value": len(datasets["Schedule_Sequence_Ready"]),
    },
    {
        "Diagnostic": "Valid actual port calls",
        "Value": len(schedule_valid),
    },
    {
        "Diagnostic": "Unique vessels",
        "Value": schedule_valid["IMO_Analysis"].nunique(),
    },
    {
        "Diagnostic": "Unique ports",
        "Value": schedule_valid["LOCODE_Analysis"].nunique(),
    },
    {
        "Diagnostic": "Same-port transitions",
        "Value": len(same_port),
    },
    {
        "Diagnostic": "Different-port transitions",
        "Value": len(different_port),
    },
    {
        "Diagnostic": "Negative same-port transitions",
        "Value": int(
            (
                same_port["Inter_Port_Elapsed_Hours"] < 0
            ).sum()
        ),
    },
    {
        "Diagnostic": "Negative different-port transitions",
        "Value": int(
            (
                different_port["Inter_Port_Elapsed_Hours"] < 0
            ).sum()
        ),
    },
    {
        "Diagnostic": "Zero different-port transitions",
        "Value": int(
            (
                different_port["Inter_Port_Elapsed_Hours"] == 0
            ).sum()
        ),
    },
    {
        "Diagnostic": "Positive different-port transitions",
        "Value": int(
            (
                different_port["Inter_Port_Elapsed_Hours"] > 0
            ).sum()
        ),
    },
    {
        "Diagnostic": "Negative port stays",
        "Value": int(
            (schedule_valid["Port_Stay_Hours"] < 0).sum()
        ),
    },
])

diagnostics.to_csv(
    TABLES / "16_schedule_sequence_ready_diagnostics.csv",
    index=False
)


# ------------------------------------------------------------
# 20. SAME-PORT TRANSITION INVESTIGATION
# ------------------------------------------------------------

same_port_detail = same_port.copy()

same_port_detail["Same_Port_Elapsed_Hours"] = (
    same_port_detail["Inter_Port_Elapsed_Hours"]
)

same_port_detail["Same_Port_Interpretation"] = np.select(
    [
        same_port_detail["Same_Port_Elapsed_Hours"] < 0,
        same_port_detail["Same_Port_Elapsed_Hours"] == 0,
        same_port_detail["Same_Port_Elapsed_Hours"] <= 6,
        same_port_detail["Same_Port_Elapsed_Hours"] <= 48,
    ],
    [
        "NEGATIVE_TIME_REQUIRES_INVESTIGATION",
        "ZERO_GAP",
        "SHORT_GAP",
        "MODERATE_GAP",
    ],
    default="LONG_GAP_REQUIRES_REVIEW"
)

same_port_detail.to_csv(
    TABLES / "16_schedule_same_port_transition_detail.csv",
    index=False
)


# ------------------------------------------------------------
# 21. DIFFERENT-PORT TRANSITION DETAIL
# ------------------------------------------------------------

different_port_detail = different_port.copy()

different_port_detail["Movement_Interpretation"] = np.select(
    [
        different_port_detail["Inter_Port_Elapsed_Hours"] < 0,
        different_port_detail["Inter_Port_Elapsed_Hours"] == 0,
    ],
    [
        "NEGATIVE_TIME_REQUIRES_INVESTIGATION",
        "ZERO_GAP_REQUIRES_INVESTIGATION",
    ],
    default="POSITIVE_INTER_PORT_ELAPSED_TIME"
)

different_port_detail.to_csv(
    TABLES / "16_schedule_different_port_transition_detail.csv",
    index=False
)


# ------------------------------------------------------------
# 22. CREATE SUMMARY ACROSS ALL DATASETS
# ------------------------------------------------------------

overall_summary = pd.DataFrame(summary_rows)

overall_summary.to_csv(
    TABLES / "16_overall_dataset_summary.csv",
    index=False
)

print("\nOVERALL DATASET SUMMARY")
print("-" * 75)
print(overall_summary.to_string(index=False))


# ------------------------------------------------------------
# 23. VISUALIZATION 1: TOP PORTS
# ------------------------------------------------------------

def save_top_ports_figure(port_activity, filename, title):

    if port_activity.empty:
        return

    top = port_activity.head(15).sort_values(
        "Port_Calls",
        ascending=True
    )

    plt.figure(figsize=(11, 7))

    plt.barh(
        top["LOCODE_Analysis"].astype(str),
        top["Port_Calls"]
    )

    plt.xlabel("Recorded actual port calls")
    plt.ylabel("UN/LOCODE")
    plt.title(title)

    plt.tight_layout()

    plt.savefig(
        FIGURES / filename,
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()


save_top_ports_figure(
    schedule_result["port_activity"],
    "16_schedule_sequence_ready_top_ports.png",
    "Top Ports - Sequence-Ready Schedule"
)

save_top_ports_figure(
    analysis_results["Individual"]["port_activity"],
    "16_individual_top_ports.png",
    "Top Ports - Individual Vessel Calls"
)


# ------------------------------------------------------------
# 24. VISUALIZATION 2: PORT STAY DISTRIBUTION
# ------------------------------------------------------------

def save_port_stay_figure(valid, filename, title):

    values = valid["Port_Stay_Hours"].dropna()

    values = values[
        (values >= 0) & (values <= values.quantile(0.99))
    ]

    if values.empty:
        return

    plt.figure(figsize=(10, 6))

    plt.hist(
        values,
        bins=30
    )

    plt.xlabel("Port stay (hours)")
    plt.ylabel("Frequency")
    plt.title(title)

    plt.tight_layout()

    plt.savefig(
        FIGURES / filename,
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()


save_port_stay_figure(
    schedule_valid,
    "16_schedule_sequence_ready_port_stay_distribution.png",
    "Port Stay Distribution - Sequence-Ready Schedule"
)

save_port_stay_figure(
    analysis_results["Individual"]["valid"],
    "16_individual_port_stay_distribution.png",
    "Port Stay Distribution - Individual Dataset"
)


# ------------------------------------------------------------
# 25. VISUALIZATION 3: INTER-PORT ELAPSED TIME
# ------------------------------------------------------------

def save_elapsed_figure(transitions, filename, title):

    values = transitions.loc[
        (transitions["Transition_Type"] == "DIFFERENT_PORT")
        & (transitions["Inter_Port_Elapsed_Hours"] > 0),
        "Inter_Port_Elapsed_Hours"
    ].dropna()

    # Exclude extreme values only from this visualization.
    # The source data and statistical tables remain unchanged.
    if values.empty:
        return

    upper = values.quantile(0.95)
    plot_values = values[values <= upper]

    plt.figure(figsize=(10, 6))

    plt.hist(
        plot_values,
        bins=30
    )

    plt.xlabel("Inter-port elapsed time (hours)")
    plt.ylabel("Frequency")
    plt.title(title)

    plt.tight_layout()

    plt.savefig(
        FIGURES / filename,
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()


save_elapsed_figure(
    schedule_transitions,
    "16_schedule_different_port_elapsed_distribution.png",
    "Different-Port Inter-Port Elapsed Time - Schedule"
)

save_elapsed_figure(
    analysis_results["Individual"]["transitions"],
    "16_individual_different_port_elapsed_distribution.png",
    "Different-Port Inter-Port Elapsed Time - Individual"
)


# ------------------------------------------------------------
# 26. VISUALIZATION 4: MONTHLY ACTIVITY
# ------------------------------------------------------------

def save_monthly_activity_figure(monthly, filename, title):

    if monthly.empty:
        return

    plt.figure(figsize=(11, 6))

    plt.plot(
        monthly["Arrival_Month"],
        monthly["Port_Calls"],
        marker="o"
    )

    plt.xlabel("Month")
    plt.ylabel("Actual port calls")
    plt.title(title)

    plt.xticks(rotation=45)

    plt.tight_layout()

    plt.savefig(
        FIGURES / filename,
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()


save_monthly_activity_figure(
    schedule_result["monthly"],
    "16_schedule_sequence_ready_monthly_activity.png",
    "Monthly Activity - Sequence-Ready Schedule"
)

save_monthly_activity_figure(
    analysis_results["Individual"]["monthly"],
    "16_individual_monthly_activity.png",
    "Monthly Activity - Individual Dataset"
)


# ------------------------------------------------------------
# 27. GENERATE REPORT
# ------------------------------------------------------------

report_file = (
    REPORTS / "16_refined_maritime_network_analysis_report.txt"
)

with open(report_file, "w", encoding="utf-8") as f:

    f.write("=" * 80 + "\n")
    f.write("SCRIPT 16: REFINED MARITIME NETWORK ANALYSIS\n")
    f.write("=" * 80 + "\n\n")

    f.write("1. INPUT DATASETS\n")
    f.write("-" * 80 + "\n")

    for name, df in datasets.items():
        f.write(
            f"{name}: {len(df)} records\n"
        )

    f.write("\n2. OVERALL DATASET SUMMARY\n")
    f.write("-" * 80 + "\n")
    f.write(overall_summary.to_string(index=False))
    f.write("\n\n")

    f.write("3. BASELINE SENSITIVITY COMPARISON\n")
    f.write("-" * 80 + "\n")
    f.write(baseline_comparison.to_string(index=False))
    f.write("\n\n")

    f.write("4. SEQUENCE-READY SCHEDULE DIAGNOSTICS\n")
    f.write("-" * 80 + "\n")
    f.write(diagnostics.to_string(index=False))
    f.write("\n\n")

    f.write("5. SAME-PORT TRANSITION SUMMARY\n")
    f.write("-" * 80 + "\n")
    f.write(
        same_port_detail[
            "Same_Port_Interpretation"
        ].value_counts().to_string()
    )
    f.write("\n\n")

    f.write("6. DIFFERENT-PORT TRANSITION SUMMARY\n")
    f.write("-" * 80 + "\n")
    f.write(
        different_port_detail[
            "Movement_Interpretation"
        ].value_counts().to_string()
    )
    f.write("\n\n")

    f.write("7. METHODOLOGICAL LIMITATIONS\n")
    f.write("-" * 80 + "\n")

    limitations = [
        "Schedule and Individual datasets are analyzed separately.",
        "The sequence-ready Schedule excludes one representative record "
        "from each of seven source-verified duplicate-representation pairs.",
        "The annotated full Schedule remains preserved.",
        "Inter-port elapsed time is not necessarily pure sailing time.",
        "Elapsed time may include anchorage, waiting, intermediate stops, "
        "data gaps and operational delays.",
        "Same-LOCODE transitions are retained and classified.",
        "Small transition samples should not be treated as reliable "
        "travel-time distributions.",
        "Port calls do not establish whether a vessel crossed the Strait "
        "of Hormuz.",
        "AIS trajectory data is required to verify Strait transit.",
        "The histogram visualization excludes its upper five percent "
        "only for display; analytical tables retain all observations.",
    ]

    for item in limitations:
        f.write(f"- {item}\n")

    f.write("\n8. OUTPUT LOCATIONS\n")
    f.write("-" * 80 + "\n")
    f.write(f"Tables: {TABLES}\n")
    f.write(f"Figures: {FIGURES}\n")
    f.write(f"Report: {report_file}\n")


# ------------------------------------------------------------
# 28. FINAL TERMINAL SUMMARY
# ------------------------------------------------------------

print("\n" + "=" * 75)
print("SCRIPT 16 COMPLETED SUCCESSFULLY")
print("=" * 75)

print("\nREFINED SCHEDULE BASELINE")
print("-" * 75)

print(
    "Sequence-ready records:",
    len(datasets["Schedule_Sequence_Ready"])
)

print(
    "Valid actual calls:",
    len(schedule_valid)
)

print(
    "Unique vessels:",
    schedule_valid["IMO_Analysis"].nunique()
)

print(
    "Unique ports:",
    schedule_valid["LOCODE_Analysis"].nunique()
)

print(
    "Total transitions:",
    len(schedule_transitions)
)

print(
    "Same-port transitions:",
    len(same_port)
)

print(
    "Different-port transitions:",
    len(different_port)
)

print(
    "Negative transitions:",
    int(schedule_transitions["Negative_Elapsed_Time"].sum())
)

print("\nSENSITIVITY COMPARISON")
print("-" * 75)
print(baseline_comparison.to_string(index=False))

print("\nOUTPUT LOCATIONS")
print("-" * 75)
print("Tables:", TABLES)
print("Figures:", FIGURES)
print("Report:", report_file)

print("\nNo original source records were deleted or modified.")
print("Schedule and Individual datasets remain separate.")
print("Inter-port elapsed time is not treated as sailing time.")
