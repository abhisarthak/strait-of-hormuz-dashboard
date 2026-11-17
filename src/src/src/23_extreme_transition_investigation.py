
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# SCRIPT 23
# INVESTIGATION OF POTENTIAL EXTREME INTER-PORT OBSERVATIONS
# Strait of Hormuz Research
#
# Input:
#   22_transition_observation_audit.csv
#
# Outputs:
#   23_extreme_observation_register.csv
#   23_extreme_vessel_investigation.csv
#   23_port_pair_influence_analysis.csv
#   23_vessel_repetition_analysis.csv
#   23_extreme_investigation_summary.csv
#   23_extreme_transition_investigation_report.txt
#
# IMPORTANT:
# No records are deleted or automatically excluded.
# IQR flags are statistical screening indicators only.
# ============================================================


ROOT = Path(__file__).resolve().parents[1]

INPUT_DIR = ROOT / "data" / "simulation_inputs"
TABLE_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

for folder in [TABLE_DIR, REPORT_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

INPUT_FILE = TABLE_DIR / "22_transition_observation_audit.csv"


# ------------------------------------------------------------
# 1. HELPER FUNCTIONS
# ------------------------------------------------------------

def normalize_identifier(series):
    return (
        series.astype("string")
        .str.strip()
        .str.upper()
    )


def first_available_column(df, candidates):
    """Return the first available column from a candidate list."""
    for col in candidates:
        if col in df.columns:
            return col
    return None


def safe_mean(series):
    return pd.to_numeric(series, errors="coerce").mean()


def safe_median(series):
    return pd.to_numeric(series, errors="coerce").median()


def safe_std(series):
    return pd.to_numeric(series, errors="coerce").std()


def safe_cv(series):
    mean_value = safe_mean(series)
    std_value = safe_std(series)

    if pd.isna(mean_value) or mean_value == 0:
        return np.nan

    return std_value / mean_value


def safe_ratio(numerator, denominator):
    if denominator == 0:
        return np.nan
    return numerator / denominator


# ------------------------------------------------------------
# 2. LOAD INPUT
# ------------------------------------------------------------

print("=" * 70)
print("SCRIPT 23: EXTREME TRANSITION INVESTIGATION")
print("=" * 70)

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Input not found: {INPUT_FILE}\n"
        "Run Script 22 first."
    )

df = pd.read_csv(INPUT_FILE, low_memory=False)

required = [
    "Audit_Record_ID",
    "Previous_Port",
    "Next_Port",
    "IMO_Normalised",
    "Elapsed_Hours_Between_Calls",
    "Observation_Valid",
    "IQR_Potential_Outlier",
]

missing = [col for col in required if col not in df.columns]

if missing:
    raise ValueError(
        f"Required columns missing from Script 22 output: {missing}"
    )

print("\n[1/7] INPUT DATA")
print("-" * 45)

print("Input shape:", df.shape)

df["Previous_Port"] = normalize_identifier(df["Previous_Port"])
df["Next_Port"] = normalize_identifier(df["Next_Port"])
df["IMO_Normalised"] = normalize_identifier(df["IMO_Normalised"])

df["Elapsed_Hours_Between_Calls"] = pd.to_numeric(
    df["Elapsed_Hours_Between_Calls"],
    errors="coerce"
)

# Read boolean values robustly.
df["Observation_Valid"] = (
    df["Observation_Valid"].astype(str).str.lower().isin(
        ["true", "1", "yes"]
    )
)

df["IQR_Potential_Outlier"] = (
    df["IQR_Potential_Outlier"].astype(str).str.lower().isin(
        ["true", "1", "yes"]
    )
)

valid = df[
    df["Observation_Valid"]
    & df["Elapsed_Hours_Between_Calls"].notna()
].copy()

extreme = valid[
    valid["IQR_Potential_Outlier"]
].copy()

non_extreme = valid[
    ~valid["IQR_Potential_Outlier"]
].copy()

print("Valid observations:", len(valid))
print("IQR-flagged observations:", len(extreme))
print("Non-flagged observations:", len(non_extreme))


# ------------------------------------------------------------
# 3. IDENTIFY AVAILABLE SOURCE FIELDS
# ------------------------------------------------------------

print("\n[2/7] IDENTIFYING AVAILABLE SOURCE FIELDS")
print("-" * 45)

candidate_columns = {
    "Vessel_Name": [
        "Vessel Name",
        "vesselName",
        "observed_vessel_name",
    ],
    "Previous_Departure": [
        "Previous_Departure_UTC",
        "Previous_Actual_Departure_UTC",
    ],
    "Next_Arrival": [
        "Actual_Arrival_UTC",
        "Next_Arrival_UTC",
    ],
    "Current_Source_Row": [
        "Schedule_Source_Row",
        "Source_Row",
    ],
    "Previous_Source_Row": [
        "Previous_Schedule_Source_Row",
        "Previous_Source_Row",
    ],
    "Service_Code": [
        "Carrier Service Code",
        "carrierServiceCode",
        "Carrier_Service_Code",
    ],
    "Service_Name": [
        "Carrier Service Name",
        "carrierServiceName",
        "Carrier_Service_Name",
    ],
    "Import_Voyage": [
        "Import Voyage Number",
        "carrierImportVoyageNumber",
    ],
    "Export_Voyage": [
        "Export Voyage Number",
        "carrierExportVoyageNumber",
    ],
}

resolved = {
    key: first_available_column(df, candidates)
    for key, candidates in candidate_columns.items()
}

for key, col in resolved.items():
    print(f"{key}: {col if col else 'NOT AVAILABLE'}")

# Parse timestamps when available.

# Parse timestamps in every DataFrame copy.
# valid/extreme/non_extreme were created before this section,
# so converting only df would not update those copies.

previous_departure_col = resolved["Previous_Departure"]
next_arrival_col = resolved["Next_Arrival"]

for frame in [df, valid, extreme, non_extreme]:

    if previous_departure_col:
        frame[previous_departure_col] = pd.to_datetime(
            frame[previous_departure_col],
            errors="coerce",
            utc=True
        )

    if next_arrival_col:
        frame[next_arrival_col] = pd.to_datetime(
            frame[next_arrival_col],
            errors="coerce",
            utc=True
        )

print("\nTimestamp conversion completed.")

if previous_departure_col:
    print(
        "Previous departure datetime:",
        df[previous_departure_col].dtype
    )

if next_arrival_col:
    print(
        "Next arrival datetime:",
        df[next_arrival_col].dtype
    )



# ------------------------------------------------------------
# 4. BUILD EXTREME OBSERVATION REGISTER
# ------------------------------------------------------------

print("\n[3/7] BUILDING EXTREME OBSERVATION REGISTER")
print("-" * 45)

register_columns = [
    "Audit_Record_ID",
    "IMO_Normalised",
    "Previous_Port",
    "Next_Port",
    "Elapsed_Hours_Between_Calls",
    "IQR_Lower_Bound",
    "IQR_Upper_Bound",
    "IQR_Assessment_Status",
    "Simulation_Use_Recommendation",
]

for key in [
    "Vessel_Name",
    "Previous_Departure",
    "Next_Arrival",
    "Current_Source_Row",
    "Previous_Source_Row",
    "Service_Code",
    "Service_Name",
    "Import_Voyage",
    "Export_Voyage",
]:
    col = resolved[key]
    if col:
        register_columns.append(col)

register_columns = [
    col for col in register_columns if col in extreme.columns
]

extreme_register = extreme[register_columns].copy()

# Recalculate timestamp elapsed time as an independent consistency check.
if previous_departure_col and next_arrival_col:

    extreme_register["Timestamp_Difference_Hours"] = (
        (
            extreme[ next_arrival_col ]
            - extreme[ previous_departure_col ]
        ).dt.total_seconds() / 3600
    )

    extreme_register["Timestamp_Check_Difference_Hours"] = (
        extreme_register["Timestamp_Difference_Hours"]
        - extreme_register["Elapsed_Hours_Between_Calls"]
    )

    extreme_register["Timestamp_Consistency_Status"] = np.where(
        extreme_register["Timestamp_Check_Difference_Hours"].abs() <= 0.01,
        "MATCH",
        "REVIEW"
    )

else:
    extreme_register["Timestamp_Consistency_Status"] = (
        "TIMESTAMP_FIELDS_UNAVAILABLE"
    )

extreme_register["Investigation_Status"] = "PENDING_MANUAL_REVIEW"

extreme_register["Automatic_Exclusion"] = False

extreme_register.to_csv(
    TABLE_DIR / "23_extreme_observation_register.csv",
    index=False
)


# ------------------------------------------------------------
# 5. INVESTIGATE VESSEL REPETITION
# ------------------------------------------------------------

print("\n[4/7] INVESTIGATING VESSEL REPETITION")
print("-" * 45)

vessel_group = (
    valid.groupby("IMO_Normalised")
    .agg(
        Total_Transition_Observations=(
            "Audit_Record_ID", "count"
        ),
        Extreme_Observations=(
            "IQR_Potential_Outlier", "sum"
        ),
        Unique_Origin_Ports=(
            "Previous_Port", "nunique"
        ),
        Unique_Destination_Ports=(
            "Next_Port", "nunique"
        ),
        Mean_Elapsed_Hours=(
            "Elapsed_Hours_Between_Calls", "mean"
        ),
        Median_Elapsed_Hours=(
            "Elapsed_Hours_Between_Calls", "median"
        ),
    )
    .reset_index()
)

vessel_group["Extreme_Observation_Share"] = (
    vessel_group["Extreme_Observations"]
    / vessel_group["Total_Transition_Observations"]
)

vessel_group["Has_Extreme_Observation"] = (
    vessel_group["Extreme_Observations"] > 0
)

vessel_group = vessel_group.sort_values(
    ["Extreme_Observations", "Total_Transition_Observations"],
    ascending=False
)

vessel_group.to_csv(
    TABLE_DIR / "23_vessel_repetition_analysis.csv",
    index=False
)

# Attach vessel-level context to each extreme observation.
extreme_vessel = extreme.merge(
    vessel_group,
    on="IMO_Normalised",
    how="left",
    suffixes=("", "_Vessel")
)

extreme_vessel.to_csv(
    TABLE_DIR / "23_extreme_vessel_investigation.csv",
    index=False
)


# ------------------------------------------------------------
# 6. MEASURE INFLUENCE ON PORT-PAIR STATISTICS
# ------------------------------------------------------------

print("\n[5/7] MEASURING EXTREME OBSERVATION INFLUENCE")
print("-" * 45)

influence_records = []

for (origin, destination), group in valid.groupby(
    ["Previous_Port", "Next_Port"]
):

    all_values = group[
        "Elapsed_Hours_Between_Calls"
    ].dropna()

    retained_values = group.loc[
        ~group["IQR_Potential_Outlier"],
        "Elapsed_Hours_Between_Calls"
    ].dropna()

    extreme_count = int(
        group["IQR_Potential_Outlier"].sum()
    )

    mean_all = safe_mean(all_values)
    mean_retained = safe_mean(retained_values)

    median_all = safe_median(all_values)
    median_retained = safe_median(retained_values)

    influence_records.append({

        "Previous_Port": origin,
        "Next_Port": destination,

        "Original_Sample_Size": len(all_values),
        "IQR_Flagged_Count": extreme_count,
        "Non_Flagged_Count": len(retained_values),

        "Original_Mean_Hours": mean_all,
        "Mean_Without_Flags_Hours": mean_retained,

        "Original_Median_Hours": median_all,
        "Median_Without_Flags_Hours": median_retained,

        "Original_CV": safe_cv(all_values),
        "CV_Without_Flags": safe_cv(retained_values),

        "Mean_Change_Hours": (
            mean_all - mean_retained
            if pd.notna(mean_all) and pd.notna(mean_retained)
            else np.nan
        ),

        "Median_Change_Hours": (
            median_all - median_retained
            if pd.notna(median_all) and pd.notna(median_retained)
            else np.nan
        ),

        "Interpretation": (
            "Comparison is diagnostic only; "
            "flagged observations are not automatically excluded"
        ),
    })


influence = pd.DataFrame(influence_records)

influence.to_csv(
    TABLE_DIR / "23_port_pair_influence_analysis.csv",
    index=False
)


# ------------------------------------------------------------
# 7. CREATE SUMMARY AND REPORT
# ------------------------------------------------------------

print("\n[6/7] CREATING INVESTIGATION SUMMARY")
print("-" * 45)

vessels_with_extremes = extreme[
    "IMO_Normalised"
].nunique()

pairs_with_extremes = extreme.groupby(
    ["Previous_Port", "Next_Port"]
).ngroups

timestamp_match_count = np.nan

if "Timestamp_Consistency_Status" in extreme_register.columns:
    timestamp_match_count = int(
        (
            extreme_register["Timestamp_Consistency_Status"]
            == "MATCH"
        ).sum()
    )

summary = [
    ("Total valid transition observations", len(valid)),
    ("Potential IQR extreme observations", len(extreme)),
    ("Non-flagged observations", len(non_extreme)),
    ("Vessels with at least one flagged observation", vessels_with_extremes),
    ("Port pairs with at least one flagged observation", pairs_with_extremes),
    ("Unique vessels in all valid transitions", valid["IMO_Normalised"].nunique()),
    ("Vessels with repeated transition observations", int(
        (vessel_group["Total_Transition_Observations"] > 1).sum()
    )),
    ("Flagged records with matching timestamp calculation", timestamp_match_count),
    ("Automatically excluded observations", 0),
]

summary_df = pd.DataFrame(
    summary,
    columns=["Metric", "Value"]
)

summary_df.to_csv(
    TABLE_DIR / "23_extreme_investigation_summary.csv",
    index=False
)

print(summary_df.to_string(index=False))


# ------------------------------------------------------------
# 8. WRITE RESEARCH REPORT
# ------------------------------------------------------------

print("\n[7/7] WRITING INVESTIGATION REPORT")
print("-" * 45)

report_path = (
    REPORT_DIR / "23_extreme_transition_investigation_report.txt"
)

with open(report_path, "w", encoding="utf-8") as report:

    report.write(
        "EXTREME INTER-PORT TRANSITION INVESTIGATION\n"
    )

    report.write("=" * 65 + "\n\n")

    report.write("SUMMARY\n")

    for metric, value in summary:
        report.write(f"{metric}: {value}\n")

    report.write("\nAVAILABLE SOURCE FIELDS\n")

    for key, col in resolved.items():
        report.write(
            f"{key}: {col if col else 'NOT AVAILABLE'}\n"
        )

    report.write("\nTOP FLAGGED OBSERVATIONS\n")

    report.write(
        extreme_register[
            [
                "Audit_Record_ID",
                "IMO_Normalised",
                "Previous_Port",
                "Next_Port",
                "Elapsed_Hours_Between_Calls",
            ]
        ].to_string(index=False)
    )

    report.write("\n\nTOP VESSELS WITH FLAGGED OBSERVATIONS\n")

    report.write(
        vessel_group.head(15).to_string(index=False)
    )

    report.write("\n\nMETHODOLOGICAL LIMITATIONS\n")

    report.write(
        "1. IQR flags identify statistical extremes, not data errors.\n"
        "2. No observations have been deleted or automatically excluded.\n"
        "3. Repeated observations from one vessel are not independent vessels.\n"
        "4. Timestamp consistency does not establish route validity.\n"
        "5. Long elapsed times may include waiting and unobserved calls.\n"
        "6. A port-call transition does not prove direct sailing.\n"
        "7. Manual source verification is needed before rejecting records.\n"
        "8. The analysis does not confirm Strait of Hormuz transit.\n"
    )

print("\n" + "=" * 70)
print("SCRIPT 23 COMPLETED SUCCESSFULLY")
print("=" * 70)

print("\nFLAGGED OBSERVATION REGISTER:")
print(
    extreme_register[
        [
            "Audit_Record_ID",
            "IMO_Normalised",
            "Previous_Port",
            "Next_Port",
            "Elapsed_Hours_Between_Calls",
        ]
    ].to_string(index=False)
)

print("\nTOP VESSELS WITH EXTREME OBSERVATIONS:")
print(
    vessel_group.head(10).to_string(index=False)
)

print("\nPORT-PAIR INFLUENCE:")
print(
    influence.sort_values(
        "Mean_Change_Hours",
        key=lambda x: x.abs(),
        ascending=False
    ).head(10).to_string(index=False)
)

print("\nGENERATED FILES:")
print("- outputs/tables/23_extreme_observation_register.csv")
print("- outputs/tables/23_extreme_vessel_investigation.csv")
print("- outputs/tables/23_port_pair_influence_analysis.csv")
print("- outputs/tables/23_vessel_repetition_analysis.csv")
print("- outputs/tables/23_extreme_investigation_summary.csv")
print("- outputs/reports/23_extreme_transition_investigation_report.txt")
