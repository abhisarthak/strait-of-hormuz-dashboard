
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# SCRIPT 22
# INTER-PORT TRANSITION AND ELAPSED-TIME EVIDENCE AUDIT
# Strait of Hormuz Research
#
# Input:
#   19_observed_interport_transitions.csv
#   21_port_connection_metrics.csv
#
# Outputs:
#   22_transition_observation_audit.csv
#   22_transition_pair_statistics.csv
#   22_transition_data_quality_summary.csv
#   22_directional_pair_comparison.csv
#   22_interport_transition_evidence_report.txt
# ============================================================


ROOT = Path(__file__).resolve().parents[1]

INPUT_DIR = ROOT / "data" / "simulation_inputs"
TABLE_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

for folder in [TABLE_DIR, REPORT_DIR]:
    folder.mkdir(parents=True, exist_ok=True)


TRANSITION_FILE = INPUT_DIR / "19_observed_interport_transitions.csv"
NETWORK_EDGE_FILE = TABLE_DIR / "21_port_connection_metrics.csv"


# ------------------------------------------------------------
# 1. HELPER FUNCTIONS
# ------------------------------------------------------------

def normalize_identifier(series):
    return (
        series.astype("string")
        .str.strip()
        .str.upper()
    )


def safe_cv(mean, std):
    if pd.isna(mean) or pd.isna(std) or mean == 0:
        return np.nan
    return std / mean


def sample_category(n):
    if n < 3:
        return "VERY_LOW_SAMPLE"
    elif n < 6:
        return "LOW_SAMPLE"
    elif n < 10:
        return "MODERATE_SAMPLE"
    return "HIGHER_SAMPLE"


def variability_category(cv):
    if pd.isna(cv):
        return "NOT_ASSESSED"
    elif cv < 0.25:
        return "LOW_VARIABILITY"
    elif cv < 0.50:
        return "MODERATE_VARIABILITY"
    elif cv < 1.00:
        return "HIGH_VARIABILITY"
    return "VERY_HIGH_VARIABILITY"


# ------------------------------------------------------------
# 2. LOAD AND VALIDATE DATA
# ------------------------------------------------------------

print("=" * 70)
print("SCRIPT 22: INTER-PORT TRANSITION EVIDENCE AUDIT")
print("=" * 70)

if not TRANSITION_FILE.exists():
    raise FileNotFoundError(
        f"Missing input: {TRANSITION_FILE}"
    )

transitions = pd.read_csv(
    TRANSITION_FILE,
    low_memory=False
)

required_columns = [
    "Previous_Port",
    "Next_Port",
    "Elapsed_Hours_Between_Calls",
    "IMO_Normalised",
]

missing_columns = [
    col for col in required_columns
    if col not in transitions.columns
]

if missing_columns:
    raise ValueError(
        f"Required columns missing: {missing_columns}"
    )

print("\n[1/8] INPUT VALIDATION")
print("-" * 45)

print("Input shape:", transitions.shape)

transitions["Previous_Port"] = normalize_identifier(
    transitions["Previous_Port"]
)

transitions["Next_Port"] = normalize_identifier(
    transitions["Next_Port"]
)

transitions["IMO_Normalised"] = normalize_identifier(
    transitions["IMO_Normalised"]
)

transitions["Elapsed_Hours_Between_Calls"] = pd.to_numeric(
    transitions["Elapsed_Hours_Between_Calls"],
    errors="coerce"
)

# Preserve the original observations.
transitions["Audit_Record_ID"] = [
    f"TR_{i:04d}" for i in range(1, len(transitions) + 1)
]

print(
    "Missing origin:",
    transitions["Previous_Port"].isna().sum()
)

print(
    "Missing destination:",
    transitions["Next_Port"].isna().sum()
)

print(
    "Missing vessel IMO:",
    transitions["IMO_Normalised"].isna().sum()
)

print(
    "Missing elapsed time:",
    transitions["Elapsed_Hours_Between_Calls"].isna().sum()
)


# ------------------------------------------------------------
# 3. IDENTIFY INVALID OBSERVATIONS
# ------------------------------------------------------------

print("\n[2/8] OBSERVATION QUALITY CHECK")
print("-" * 45)

transitions["Invalid_Reason"] = ""

transitions.loc[
    transitions["Previous_Port"].isna(),
    "Invalid_Reason"
] += "MISSING_ORIGIN;"

transitions.loc[
    transitions["Next_Port"].isna(),
    "Invalid_Reason"
] += "MISSING_DESTINATION;"

transitions.loc[
    transitions["Elapsed_Hours_Between_Calls"].isna(),
    "Invalid_Reason"
] += "MISSING_ELAPSED_TIME;"

transitions.loc[
    transitions["Elapsed_Hours_Between_Calls"] < 0,
    "Invalid_Reason"
] += "NEGATIVE_ELAPSED_TIME;"

transitions.loc[
    transitions["Previous_Port"] == transitions["Next_Port"],
    "Invalid_Reason"
] += "SAME_PORT_TRANSITION;"

transitions["Observation_Valid"] = (
    transitions["Invalid_Reason"] == ""
)

valid = transitions[
    transitions["Observation_Valid"]
].copy()

print("Total observations:", len(transitions))
print("Valid observations:", len(valid))
print("Invalid observations:", len(transitions) - len(valid))


# ------------------------------------------------------------
# 4. GROUP BY DIRECTED PORT PAIR
# ------------------------------------------------------------

print("\n[3/8] CALCULATING PORT-PAIR STATISTICS")
print("-" * 45)

pair_records = []

for (origin, destination), group in valid.groupby(
    ["Previous_Port", "Next_Port"]
):

    values = group[
        "Elapsed_Hours_Between_Calls"
    ].dropna()

    n = len(values)

    mean_value = values.mean()
    median_value = values.median()
    std_value = values.std(ddof=1)

    q1 = values.quantile(0.25)
    q3 = values.quantile(0.75)
    iqr = q3 - q1

    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    outlier_count = (
        (values < lower_bound)
        | (values > upper_bound)
    ).sum()

    unique_vessels = group[
        "IMO_Normalised"
    ].nunique()

    repeated_vessel_observations = (
        len(group)
        - unique_vessels
    )

    cv = safe_cv(mean_value, std_value)

    if n >= 4:
        outlier_assessment = "IQR_SCREEN_COMPLETED"
    else:
        outlier_assessment = "INSUFFICIENT_SAMPLE_FOR_IQR"

    pair_records.append({

        "Previous_Port": origin,
        "Next_Port": destination,

        "Sample_Size": n,
        "Unique_Vessels": unique_vessels,

        "Repeated_Vessel_Observations": (
            repeated_vessel_observations
        ),

        "Mean_Elapsed_Hours": mean_value,
        "Median_Elapsed_Hours": median_value,
        "Std_Elapsed_Hours": std_value,

        "Min_Elapsed_Hours": values.min(),
        "Q25_Elapsed_Hours": q1,
        "Q75_Elapsed_Hours": q3,
        "P90_Elapsed_Hours": values.quantile(0.90),
        "P95_Elapsed_Hours": values.quantile(0.95),
        "Max_Elapsed_Hours": values.max(),

        "Coefficient_of_Variation": cv,

        "IQR_Lower_Bound": lower_bound,
        "IQR_Upper_Bound": upper_bound,

        "IQR_Outlier_Count": int(outlier_count),

        "Sample_Category": sample_category(n),

        "Variability_Category": variability_category(cv),

        "Outlier_Assessment": outlier_assessment,

        "Parameter_Interpretation": (
            "Observed inter-port elapsed time; "
            "not pure sailing time"
        ),
    })


pair_stats = pd.DataFrame(pair_records)

pair_stats = pair_stats.sort_values(
    ["Sample_Size", "Mean_Elapsed_Hours"],
    ascending=[False, False]
)

pair_stats.to_csv(
    TABLE_DIR / "22_transition_pair_statistics.csv",
    index=False
)

print("Distinct directed port pairs:", len(pair_stats))


# ------------------------------------------------------------
# 5. FLAG POTENTIAL OUTLIERS AT OBSERVATION LEVEL
# ------------------------------------------------------------

print("\n[4/8] IDENTIFYING POTENTIAL EXTREME OBSERVATIONS")
print("-" * 45)

transitions["IQR_Potential_Outlier"] = False

transitions["IQR_Assessment_Status"] = (
    "NOT_ASSESSED"
)

for _, row in pair_stats.iterrows():

    origin = row["Previous_Port"]
    destination = row["Next_Port"]

    mask = (
        (transitions["Previous_Port"] == origin)
        & (transitions["Next_Port"] == destination)
        & transitions["Observation_Valid"]
    )

    if row["Sample_Size"] < 4:
        transitions.loc[
            mask, "IQR_Assessment_Status"
        ] = "INSUFFICIENT_SAMPLE"

        continue

    lower = row["IQR_Lower_Bound"]
    upper = row["IQR_Upper_Bound"]

    values = transitions.loc[
        mask, "Elapsed_Hours_Between_Calls"
    ]

    outliers = (values < lower) | (values > upper)

    transitions.loc[
        mask, "IQR_Potential_Outlier"
    ] = outliers

    transitions.loc[
        mask, "IQR_Assessment_Status"
    ] = "IQR_SCREEN_COMPLETED"

transitions["Simulation_Use_Recommendation"] = (
    "REQUIRES_REVIEW"
)

transitions.loc[
    ~transitions["Observation_Valid"],
    "Simulation_Use_Recommendation"
] = "EXCLUDE_INVALID_RECORD"

transitions.loc[
    transitions["IQR_Potential_Outlier"],
    "Simulation_Use_Recommendation"
] = "REVIEW_POTENTIAL_EXTREME"

transitions.to_csv(
    TABLE_DIR / "22_transition_observation_audit.csv",
    index=False
)

print(
    "Potential extreme observations:",
    int(transitions["IQR_Potential_Outlier"].sum())
)


# ------------------------------------------------------------
# 6. DIRECTIONAL COMPARISON
# ------------------------------------------------------------

print("\n[5/8] DIRECTIONAL PAIR COMPARISON")
print("-" * 45)

directional_records = []

unique_undirected_pairs = set()

for _, row in pair_stats.iterrows():

    a = row["Previous_Port"]
    b = row["Next_Port"]

    key = tuple(sorted([a, b]))
    unique_undirected_pairs.add(key)

for a, b in sorted(unique_undirected_pairs):

    forward = pair_stats[
        (pair_stats["Previous_Port"] == a)
        & (pair_stats["Next_Port"] == b)
    ]

    reverse = pair_stats[
        (pair_stats["Previous_Port"] == b)
        & (pair_stats["Next_Port"] == a)
    ]

    if forward.empty or reverse.empty:
        status = "ONE_DIRECTION_ONLY"
        forward_mean = (
            forward.iloc[0]["Mean_Elapsed_Hours"]
            if not forward.empty else np.nan
        )
        reverse_mean = (
            reverse.iloc[0]["Mean_Elapsed_Hours"]
            if not reverse.empty else np.nan
        )
        forward_n = (
            int(forward.iloc[0]["Sample_Size"])
            if not forward.empty else 0
        )
        reverse_n = (
            int(reverse.iloc[0]["Sample_Size"])
            if not reverse.empty else 0
        )

    else:
        status = "BOTH_DIRECTIONS_OBSERVED"

        forward_mean = forward.iloc[0]["Mean_Elapsed_Hours"]
        reverse_mean = reverse.iloc[0]["Mean_Elapsed_Hours"]

        forward_n = int(forward.iloc[0]["Sample_Size"])
        reverse_n = int(reverse.iloc[0]["Sample_Size"])

    directional_records.append({

        "Port_A": a,
        "Port_B": b,

        "A_to_B_Sample_Size": forward_n,
        "B_to_A_Sample_Size": reverse_n,

        "A_to_B_Mean_Elapsed_Hours": forward_mean,
        "B_to_A_Mean_Elapsed_Hours": reverse_mean,

        "Mean_Difference_Hours": (
            forward_mean - reverse_mean
            if pd.notna(forward_mean)
            and pd.notna(reverse_mean)
            else np.nan
        ),

        "Directional_Observation_Status": status,

        "Interpretation": (
            "Directional elapsed-time difference is descriptive; "
            "not proof of directional sailing-time difference"
        ),
    })


directional = pd.DataFrame(directional_records)

directional.to_csv(
    TABLE_DIR / "22_directional_pair_comparison.csv",
    index=False
)


# ------------------------------------------------------------
# 7. DATA QUALITY SUMMARY
# ------------------------------------------------------------

print("\n[6/8] CREATING AUDIT SUMMARY")
print("-" * 45)

valid_count = len(valid)
pair_count = len(pair_stats)

summary = [

    ("Total transition records", len(transitions)),

    ("Valid transition records", valid_count),

    ("Invalid transition records", len(transitions) - valid_count),

    ("Unique directed port pairs", pair_count),

    (
        "Unique undirected port pairs",
        len(unique_undirected_pairs)
    ),

    (
        "Unique vessels in valid transitions",
        valid["IMO_Normalised"].nunique()
    ),

    (
        "Potential IQR extreme observations",
        int(transitions["IQR_Potential_Outlier"].sum())
    ),

    (
        "Pairs with fewer than 3 observations",
        int((pair_stats["Sample_Size"] < 3).sum())
    ),

    (
        "Pairs with fewer than 6 observations",
        int((pair_stats["Sample_Size"] < 6).sum())
    ),

    (
        "Pairs with at least 10 observations",
        int((pair_stats["Sample_Size"] >= 10).sum())
    ),

    (
        "Pairs with very high variability",
        int(
            (
                pair_stats["Variability_Category"]
                == "VERY_HIGH_VARIABILITY"
            ).sum()
        )
    ),

    (
        "Pairs with both directions observed",
        int(
            (
                directional["Directional_Observation_Status"]
                == "BOTH_DIRECTIONS_OBSERVED"
            ).sum()
        )
    ),

    (
        "Pairs with only one direction observed",
        int(
            (
                directional["Directional_Observation_Status"]
                == "ONE_DIRECTION_ONLY"
            ).sum()
        )
    ),
]

summary_df = pd.DataFrame(
    summary,
    columns=["Metric", "Value"]
)

summary_df.to_csv(
    TABLE_DIR / "22_transition_data_quality_summary.csv",
    index=False
)


# ------------------------------------------------------------
# 8. COMPARE WITH SCRIPT 21 AGGREGATES
# ------------------------------------------------------------

print("\n[7/8] CROSS-CHECKING SCRIPT 21 RESULTS")
print("-" * 45)

comparison_result = "NOT_PERFORMED"

if NETWORK_EDGE_FILE.exists():

    network_edges = pd.read_csv(NETWORK_EDGE_FILE)

    comparison = pair_stats.merge(
        network_edges[
            [
                "Previous_Port",
                "Next_Port",
                "sample_size",
                "mean_elapsed_hours",
            ]
        ],
        on=["Previous_Port", "Next_Port"],
        how="outer",
        indicator=True,
    )

    matched = comparison[
        comparison["_merge"] == "both"
    ].copy()

    if not matched.empty:

        comparison["Sample_Count_Match"] = (
            comparison["Sample_Size"]
            == comparison["sample_size"]
        )

        comparison["Mean_Time_Match"] = np.isclose(
            comparison["Mean_Elapsed_Hours"],
            comparison["mean_elapsed_hours"],
            rtol=1e-6,
            atol=1e-6,
            equal_nan=True,
        )

        count_matches = int(
            comparison["Sample_Count_Match"].sum()
        )

        mean_matches = int(
            comparison["Mean_Time_Match"].sum()
        )

        comparison_result = (
            f"Sample count matches: {count_matches}; "
            f"mean matches: {mean_matches}"
        )

        print(comparison_result)

    else:
        print("No matching pairs found in Script 21 output.")

else:
    print("Script 21 connection table not found.")


# ------------------------------------------------------------
# 9. SAVE REPORT
# ------------------------------------------------------------

print("\n[8/8] SAVING REPORT")
print("-" * 45)

report_path = (
    REPORT_DIR / "22_interport_transition_evidence_report.txt"
)

with open(report_path, "w", encoding="utf-8") as report:

    report.write(
        "INTER-PORT TRANSITION AND ELAPSED-TIME EVIDENCE AUDIT\n"
    )

    report.write("=" * 65 + "\n\n")

    report.write("INPUT DATA\n")
    report.write(f"Input records: {len(transitions)}\n")
    report.write(f"Valid records: {valid_count}\n")
    report.write(f"Invalid records: {len(transitions) - valid_count}\n\n")

    report.write("PAIR STATISTICS\n")
    report.write(f"Directed port pairs: {pair_count}\n")
    report.write(
        f"Undirected port pairs: {len(unique_undirected_pairs)}\n"
    )

    report.write("\nDATA QUALITY SUMMARY\n")

    for metric, value in summary:
        report.write(f"{metric}: {value}\n")

    report.write("\nSCRIPT 21 CROSS-CHECK\n")
    report.write(comparison_result + "\n")

    report.write("\nMETHODOLOGICAL LIMITATIONS\n")

    report.write(
        "1. Elapsed time is previous port departure to next port arrival.\n"
        "2. It may include sailing, waiting, anchorage and unobserved calls.\n"
        "3. An IQR flag identifies a statistical extreme, not a data error.\n"
        "4. Low sample size limits distribution estimation.\n"
        "5. Repeated vessel observations are not independent vessels.\n"
        "6. Directional differences are descriptive, not causal.\n"
        "7. Port-call transitions do not prove direct maritime routes.\n"
        "8. This audit does not confirm Strait of Hormuz transit.\n"
        "9. No observation is deleted by this script.\n"
    )

print("\n" + "=" * 70)
print("SCRIPT 22 COMPLETED SUCCESSFULLY")
print("=" * 70)

print("\nDATA QUALITY SUMMARY:")
print(summary_df.to_string(index=False))

print("\nTOP 10 PAIRS BY SAMPLE SIZE:")

print(
    pair_stats[
        [
            "Previous_Port",
            "Next_Port",
            "Sample_Size",
            "Unique_Vessels",
            "Median_Elapsed_Hours",
            "Mean_Elapsed_Hours",
            "Coefficient_of_Variation",
            "Sample_Category",
            "Variability_Category",
        ]
    ].head(10).to_string(index=False)
)

print("\nDIRECTIONAL COMPARISON:")
print(
    directional[
        directional["Directional_Observation_Status"]
        == "BOTH_DIRECTIONS_OBSERVED"
    ].sort_values(
        "Mean_Difference_Hours",
        key=lambda x: x.abs(),
        ascending=False
    ).head(10).to_string(index=False)
)

print("\nGENERATED FILES:")
print("- outputs/tables/22_transition_observation_audit.csv")
print("- outputs/tables/22_transition_pair_statistics.csv")
print("- outputs/tables/22_transition_data_quality_summary.csv")
print("- outputs/tables/22_directional_pair_comparison.csv")
print("- outputs/reports/22_interport_transition_evidence_report.txt")
