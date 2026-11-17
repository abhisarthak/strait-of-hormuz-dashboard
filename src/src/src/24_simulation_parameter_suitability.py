
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# SCRIPT 24
# INTER-PORT SIMULATION PARAMETER SUITABILITY ASSESSMENT
# Strait of Hormuz Research
#
# Inputs:
#   22_transition_pair_statistics.csv
#   22_transition_observation_audit.csv
#   23_port_pair_influence_analysis.csv
#
# Outputs:
#   24_simulation_parameter_suitability.csv
#   24_parameter_method_summary.csv
#   24_parameter_sensitivity_comparison.csv
#   24_simulation_parameter_assessment_report.txt
#
# No historical observations are deleted.
# Recommendations are provisional evidence classifications.
# ============================================================


ROOT = Path(__file__).resolve().parents[1]

TABLE_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

TABLE_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


PAIR_FILE = TABLE_DIR / "22_transition_pair_statistics.csv"
OBSERVATION_FILE = TABLE_DIR / "22_transition_observation_audit.csv"
INFLUENCE_FILE = TABLE_DIR / "23_port_pair_influence_analysis.csv"


# ------------------------------------------------------------
# 1. HELPER FUNCTIONS
# ------------------------------------------------------------

def require_columns(df, columns, filename):
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(
            f"{filename} is missing required columns: {missing}"
        )


def numeric_column(df, column):
    df[column] = pd.to_numeric(df[column], errors="coerce")


def classify_sample(n):
    if n < 3:
        return "VERY_LOW"
    elif n < 6:
        return "LOW"
    elif n < 10:
        return "MODERATE"
    return "HIGHER"


def classify_vessel_diversity(vessel_count):
    if pd.isna(vessel_count):
        return "UNKNOWN"
    elif vessel_count < 3:
        return "LOW"
    elif vessel_count < 6:
        return "MODERATE"
    return "HIGHER"


def classify_variability(cv):
    if pd.isna(cv):
        return "NOT_ASSESSED"
    elif cv < 0.25:
        return "LOW"
    elif cv < 0.50:
        return "MODERATE"
    elif cv < 1.00:
        return "HIGH"
    return "VERY_HIGH"


def recommend_method(row):
    n = row["Sample_Size"]
    vessels = row["Unique_Vessels"]
    cv = row["Coefficient_of_Variation"]

    if n < 3:
        return "ASSUMPTION_REQUIRED"

    if n < 6:
        return "DESCRIPTIVE_EVIDENCE_ONLY"

    if n < 10:
        return "LIMITED_EMPIRICAL_EVIDENCE"

    if vessels < 5:
        return "EMPIRICAL_RESAMPLING_WITH_CAUTION"

    if pd.notna(cv) and cv >= 1:
        return "EMPIRICAL_RESAMPLING_WITH_SENSITIVITY"

    return "EMPIRICAL_RESAMPLING_CANDIDATE"


def confidence_note(row):
    method = row["Recommended_Method"]

    notes = {
        "ASSUMPTION_REQUIRED":
            "Too few observations for reliable empirical distribution estimation.",

        "DESCRIPTIVE_EVIDENCE_ONLY":
            "Small sample; use descriptive statistics and explicit assumptions.",

        "LIMITED_EMPIRICAL_EVIDENCE":
            "Moderate sample; use empirical evidence cautiously and test alternatives.",

        "EMPIRICAL_RESAMPLING_WITH_CAUTION":
            "Sample size is higher, but vessel diversity is limited.",

        "EMPIRICAL_RESAMPLING_WITH_SENSITIVITY":
            "Higher variability; test alternative parameterisations and retain extremes.",

        "EMPIRICAL_RESAMPLING_CANDIDATE":
            "Candidate for empirical resampling; assess representativeness before use.",
    }

    return notes.get(method, "Manual review required.")


# ------------------------------------------------------------
# 2. LOAD INPUT FILES
# ------------------------------------------------------------

print("=" * 70)
print("SCRIPT 24: SIMULATION PARAMETER SUITABILITY ASSESSMENT")
print("=" * 70)

for path in [PAIR_FILE, OBSERVATION_FILE, INFLUENCE_FILE]:
    if not path.exists():
        raise FileNotFoundError(
            f"Required input not found: {path}\n"
            "Run Scripts 22 and 23 first."
        )

pair_stats = pd.read_csv(PAIR_FILE)
observations = pd.read_csv(OBSERVATION_FILE)
influence = pd.read_csv(INFLUENCE_FILE)

print("\n[1/7] INPUT DATA")
print("-" * 45)

print("Pair statistics:", pair_stats.shape)
print("Observation audit:", observations.shape)
print("Influence analysis:", influence.shape)


# ------------------------------------------------------------
# 3. VALIDATE INPUT SCHEMAS
# ------------------------------------------------------------

require_columns(
    pair_stats,
    [
        "Previous_Port",
        "Next_Port",
        "Sample_Size",
        "Unique_Vessels",
        "Mean_Elapsed_Hours",
        "Median_Elapsed_Hours",
        "Std_Elapsed_Hours",
        "P90_Elapsed_Hours",
        "Coefficient_of_Variation",
        "IQR_Outlier_Count",
    ],
    PAIR_FILE.name,
)

require_columns(
    observations,
    [
        "Previous_Port",
        "Next_Port",
        "Elapsed_Hours_Between_Calls",
        "Observation_Valid",
        "IQR_Potential_Outlier",
    ],
    OBSERVATION_FILE.name,
)

require_columns(
    influence,
    [
        "Previous_Port",
        "Next_Port",
        "Original_Mean_Hours",
        "Mean_Without_Flags_Hours",
        "Original_Median_Hours",
        "Median_Without_Flags_Hours",
        "Original_CV",
        "CV_Without_Flags",
    ],
    INFLUENCE_FILE.name,
)

print("Input schemas validated.")


# ------------------------------------------------------------
# 4. NORMALISE AND CONVERT DATA TYPES
# ------------------------------------------------------------

print("\n[2/7] NORMALISING DATA")
print("-" * 45)

for frame in [pair_stats, observations, influence]:
    frame["Previous_Port"] = (
        frame["Previous_Port"].astype("string").str.strip().str.upper()
    )
    frame["Next_Port"] = (
        frame["Next_Port"].astype("string").str.strip().str.upper()
    )

numeric_pair_columns = [
    "Sample_Size",
    "Unique_Vessels",
    "Mean_Elapsed_Hours",
    "Median_Elapsed_Hours",
    "Std_Elapsed_Hours",
    "P90_Elapsed_Hours",
    "Coefficient_of_Variation",
    "IQR_Outlier_Count",
]

for col in numeric_pair_columns:
    numeric_column(pair_stats, col)

for col in [
    "Elapsed_Hours_Between_Calls",
]:
    numeric_column(observations, col)

for col in [
    "Original_Mean_Hours",
    "Mean_Without_Flags_Hours",
    "Original_Median_Hours",
    "Median_Without_Flags_Hours",
    "Original_CV",
    "CV_Without_Flags",
]:
    numeric_column(influence, col)

if pair_stats.duplicated(
    ["Previous_Port", "Next_Port"]
).any():
    raise ValueError("Duplicate directed pairs in pair statistics.")

if influence.duplicated(
    ["Previous_Port", "Next_Port"]
).any():
    raise ValueError("Duplicate directed pairs in influence analysis.")


# ------------------------------------------------------------
# 5. BUILD SUITABILITY ASSESSMENT
# ------------------------------------------------------------

print("\n[3/7] CLASSIFYING SIMULATION PARAMETERS")
print("-" * 45)

assessment = pair_stats.merge(
    influence,
    on=["Previous_Port", "Next_Port"],
    how="left",
    validate="one_to_one",
    indicator=True,
)

assessment["Influence_Match_Status"] = assessment["_merge"].map({
    "both": "MATCHED",
    "left_only": "NO_INFLUENCE_RECORD",
    "right_only": "NOT_APPLICABLE",
})

assessment = assessment.drop(columns=["_merge"])

assessment["Sample_Category"] = (
    assessment["Sample_Size"].apply(classify_sample)
)

assessment["Vessel_Diversity_Category"] = (
    assessment["Unique_Vessels"].apply(classify_vessel_diversity)
)

assessment["Variability_Category"] = (
    assessment["Coefficient_of_Variation"].apply(classify_variability)
)

assessment["Recommended_Method"] = assessment.apply(
    recommend_method,
    axis=1
)

assessment["Method_Explanation"] = assessment.apply(
    confidence_note,
    axis=1
)

assessment["IQR_Flag_Share"] = (
    assessment["IQR_Outlier_Count"]
    / assessment["Sample_Size"].replace(0, np.nan)
)

assessment["Mean_Median_Difference_Hours"] = (
    assessment["Mean_Elapsed_Hours"]
    - assessment["Median_Elapsed_Hours"]
)

assessment["Mean_Median_Ratio"] = (
    assessment["Mean_Elapsed_Hours"]
    / assessment["Median_Elapsed_Hours"].replace(0, np.nan)
)

assessment["Mean_Change_After_IQR_Flags_Hours"] = (
    assessment["Original_Mean_Hours"]
    - assessment["Mean_Without_Flags_Hours"]
)

assessment["Median_Change_After_IQR_Flags_Hours"] = (
    assessment["Original_Median_Hours"]
    - assessment["Median_Without_Flags_Hours"]
)

assessment["CV_Change_After_IQR_Flags"] = (
    assessment["Original_CV"]
    - assessment["CV_Without_Flags"]
)

assessment["Extreme_Influence_Review"] = np.where(
    assessment["IQR_Outlier_Count"] > 0,
    "REVIEW_FLAGGED_OBSERVATIONS",
    "NO_IQR_FLAGS"
)

assessment["Parameter_Status"] = (
    "PROVISIONAL_NOT_YET_VALIDATED_FOR_SIMULATION"
)

assessment["Elapsed_Time_Interpretation"] = (
    "Observed inter-port elapsed time; not pure sailing time"
)

assessment["Hormuz_Transit_Status"] = (
    "NOT_CONFIRMED_BY_PORT_CALL_DATA"
)


# ------------------------------------------------------------
# 6. CREATE PARAMETER METHOD SUMMARY
# ------------------------------------------------------------

print("\n[4/7] SUMMARISING ESTIMATION METHODS")
print("-" * 45)

method_summary = (
    assessment.groupby("Recommended_Method", dropna=False)
    .agg(
        Directed_Port_Pairs=("Previous_Port", "count"),
        Total_Observations=("Sample_Size", "sum"),
        Mean_Of_Pair_Means=("Mean_Elapsed_Hours", "mean"),
        Median_Of_Pair_Medians=("Median_Elapsed_Hours", "median"),
        Average_Unique_Vessels=("Unique_Vessels", "mean"),
    )
    .reset_index()
    .sort_values("Directed_Port_Pairs", ascending=False)
)

method_summary.to_csv(
    TABLE_DIR / "24_parameter_method_summary.csv",
    index=False
)


# ------------------------------------------------------------
# 7. CREATE SENSITIVITY COMPARISON
# ------------------------------------------------------------

print("\n[5/7] PREPARING SENSITIVITY COMPARISON")
print("-" * 45)

sensitivity = assessment[
    [
        "Previous_Port",
        "Next_Port",
        "Sample_Size",
        "Unique_Vessels",
        "Original_Mean_Hours",
        "Mean_Without_Flags_Hours",
        "Original_Median_Hours",
        "Median_Without_Flags_Hours",
        "Original_CV",
        "CV_Without_Flags",
        "Mean_Change_After_IQR_Flags_Hours",
        "Median_Change_After_IQR_Flags_Hours",
        "CV_Change_After_IQR_Flags",
        "Recommended_Method",
    ]
].copy()

sensitivity["Mean_Change_Percentage"] = (
    sensitivity["Mean_Change_After_IQR_Flags_Hours"]
    / sensitivity["Original_Mean_Hours"].replace(0, np.nan)
) * 100

sensitivity["Diagnostic_Only"] = True

sensitivity.to_csv(
    TABLE_DIR / "24_parameter_sensitivity_comparison.csv",
    index=False
)


# ------------------------------------------------------------
# 8. CREATE FINAL SUITABILITY REGISTER
# ------------------------------------------------------------

print("\n[6/7] SAVING SUITABILITY REGISTER")
print("-" * 45)

output_columns = [
    "Previous_Port",
    "Next_Port",
    "Sample_Size",
    "Unique_Vessels",
    "Sample_Category",
    "Vessel_Diversity_Category",
    "Mean_Elapsed_Hours",
    "Median_Elapsed_Hours",
    "P90_Elapsed_Hours",
    "Std_Elapsed_Hours",
    "Coefficient_of_Variation",
    "Variability_Category",
    "IQR_Outlier_Count",
    "IQR_Flag_Share",
    "Mean_Median_Difference_Hours",
    "Mean_Median_Ratio",
    "Mean_Change_After_IQR_Flags_Hours",
    "Median_Change_After_IQR_Flags_Hours",
    "CV_Change_After_IQR_Flags",
    "Extreme_Influence_Review",
    "Recommended_Method",
    "Method_Explanation",
    "Parameter_Status",
    "Elapsed_Time_Interpretation",
    "Hormuz_Transit_Status",
]

suitability = assessment[output_columns].copy()

suitability = suitability.sort_values(
    ["Recommended_Method", "Sample_Size"],
    ascending=[True, False]
)

suitability.to_csv(
    TABLE_DIR / "24_simulation_parameter_suitability.csv",
    index=False
)


# ------------------------------------------------------------
# 9. REPORT AND VALIDATION
# ------------------------------------------------------------

print("\n[7/7] WRITING REPORT")
print("-" * 45)

total_pairs = len(suitability)

if total_pairs != 53:
    print(
        f"WARNING: Expected 53 directed pairs, found {total_pairs}."
    )

if suitability["Sample_Size"].sum() != len(
    observations[
        observations["Observation_Valid"].astype(str).str.lower().isin(
            ["true", "1"]
        )
    ]
):
    print(
        "WARNING: Pair sample counts do not equal valid observation count."
    )

report_path = (
    REPORT_DIR / "24_simulation_parameter_assessment_report.txt"
)

with open(report_path, "w", encoding="utf-8") as report:

    report.write(
        "SIMULATION PARAMETER SUITABILITY ASSESSMENT\n"
    )
    report.write("=" * 65 + "\n\n")

    report.write(f"Directed port pairs assessed: {total_pairs}\n")
    report.write(
        f"Total observations represented: "
        f"{int(suitability['Sample_Size'].sum())}\n\n"
    )

    report.write("ESTIMATION METHOD SUMMARY\n")
    report.write(method_summary.to_string(index=False))

    report.write("\n\nPORT-PAIR SUITABILITY REGISTER\n")
    report.write(
        suitability[
            [
                "Previous_Port",
                "Next_Port",
                "Sample_Size",
                "Unique_Vessels",
                "Recommended_Method",
                "Variability_Category",
            ]
        ].to_string(index=False)
    )

    report.write("\n\nMETHODOLOGICAL LIMITATIONS\n")

    report.write(
        "1. Sample thresholds are project screening rules, not universal standards.\n"
        "2. Higher sample size does not guarantee representativeness.\n"
        "3. Repeated observations from the same vessel may be dependent.\n"
        "4. IQR flags are not automatic data errors.\n"
        "5. Sensitivity statistics excluding flags are diagnostic only.\n"
        "6. Inter-port elapsed times are not pure sailing times.\n"
        "7. Port-call transitions do not establish direct navigable routes.\n"
        "8. No port-call record independently confirms Hormuz transit.\n"
        "9. All parameter classifications are provisional.\n"
    )

print("\n" + "=" * 70)
print("SCRIPT 24 COMPLETED")
print("=" * 70)

print("\nMETHOD SUMMARY:")
print(method_summary.to_string(index=False))

print("\nSUITABILITY COUNTS:")
print(
    suitability["Recommended_Method"]
    .value_counts()
    .to_string()
)

print("\nTOP EMPIRICAL RESAMPLING CANDIDATES:")

print(
    suitability[
        suitability["Recommended_Method"].isin([
            "EMPIRICAL_RESAMPLING_CANDIDATE",
            "EMPIRICAL_RESAMPLING_WITH_CAUTION",
            "EMPIRICAL_RESAMPLING_WITH_SENSITIVITY",
        ])
    ][
        [
            "Previous_Port",
            "Next_Port",
            "Sample_Size",
            "Unique_Vessels",
            "Median_Elapsed_Hours",
            "P90_Elapsed_Hours",
            "Recommended_Method",
        ]
    ].to_string(index=False)
)

print("\nGENERATED FILES:")
print("- outputs/tables/24_simulation_parameter_suitability.csv")
print("- outputs/tables/24_parameter_method_summary.csv")
print("- outputs/tables/24_parameter_sensitivity_comparison.csv")
print("- outputs/reports/24_simulation_parameter_assessment_report.txt")
