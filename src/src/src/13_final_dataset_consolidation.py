
# ============================================================
# SCRIPT 13: FINAL DATASET CONSOLIDATION
# AND ANALYTICAL READINESS ASSESSMENT
# ============================================================

from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import numpy as np


# ============================================================
# 1. PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_TABLES = PROJECT_ROOT / "outputs" / "tables"
OUTPUT_REPORTS = PROJECT_ROOT / "outputs" / "reports"
SIMULATION_INPUTS = PROJECT_ROOT / "data" / "simulation_inputs"

for folder in [
    PROCESSED_DIR,
    OUTPUT_TABLES,
    OUTPUT_REPORTS,
    SIMULATION_INPUTS,
]:
    folder.mkdir(parents=True, exist_ok=True)


SCHEDULE_FILE = (
    PROCESSED_DIR /
    "06_integrated_schedule_vessel_port.csv"
)

INDIVIDUAL_FILE = (
    PROCESSED_DIR /
    "06_individual_vessel_port_calls.csv"
)


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def normalize_imo(value):

    if pd.isna(value):
        return pd.NA

    value = str(value).strip().upper()

    if value.endswith(".0"):
        value = value[:-2]

    return value if value else pd.NA


def normalize_locode(value):

    if pd.isna(value):
        return pd.NA

    value = str(value).strip().upper()

    return value if value else pd.NA


def find_column(df, candidates, required=True):

    """
    Find a column using case-insensitive matching.
    Spaces, underscores and punctuation are ignored.
    """

    def clean(name):
        return "".join(
            char.lower()
            for char in str(name)
            if char.isalnum()
        )

    lookup = {
        clean(column): column
        for column in df.columns
    }

    for candidate in candidates:

        key = clean(candidate)

        if key in lookup:
            return lookup[key]

    if required:
        raise KeyError(
            f"Could not find any of these columns: {candidates}\n"
            f"Available columns: {list(df.columns)}"
        )

    return None


def get_series(df, candidates, required=True):

    column = find_column(
        df,
        candidates,
        required=required
    )

    if column is None:
        return pd.Series(
            pd.NA,
            index=df.index,
            dtype="object"
        )

    return df[column]


def parse_timestamp(series):

    return pd.to_datetime(
        series,
        errors="coerce",
        utc=True
    )


def add_timestamp_analysis(
    df,
    arrival_candidates,
    departure_candidates,
    prefix
):

    arrival_raw = get_series(
        df,
        arrival_candidates
    )

    departure_raw = get_series(
        df,
        departure_candidates
    )

    arrival = parse_timestamp(arrival_raw)
    departure = parse_timestamp(departure_raw)

    df[f"{prefix}_Arrival_UTC"] = arrival
    df[f"{prefix}_Departure_UTC"] = departure

    df[f"{prefix}_Complete"] = (
        arrival.notna() & departure.notna()
    )

    df[f"{prefix}_Stay_Hours"] = (
        departure - arrival
    ).dt.total_seconds() / 3600

    df[f"{prefix}_Negative_Stay"] = (
        df[f"{prefix}_Stay_Hours"] < 0
    )

    df[f"{prefix}_Valid_Chronology"] = (
        df[f"{prefix}_Complete"]
        & ~df[f"{prefix}_Negative_Stay"]
    )

    return df


# ============================================================
# 3. LOAD DATASETS
# ============================================================

print("\n" + "=" * 75)
print("SCRIPT 13: FINAL DATASET CONSOLIDATION")
print("=" * 75)

if not SCHEDULE_FILE.exists():
    raise FileNotFoundError(
        f"Integrated schedule not found: {SCHEDULE_FILE}"
    )

if not INDIVIDUAL_FILE.exists():
    raise FileNotFoundError(
        f"Individual vessel calls not found: {INDIVIDUAL_FILE}"
    )

schedule = pd.read_csv(
    SCHEDULE_FILE,
    low_memory=False
)

individual = pd.read_csv(
    INDIVIDUAL_FILE,
    low_memory=False
)

print("\nINPUT DIMENSIONS")

print("Integrated schedule:", schedule.shape)
print("Individual calls:", individual.shape)


# ============================================================
# 4. STANDARDIZE IDENTIFIERS
# ============================================================

schedule_imo_col = find_column(
    schedule,
    ["IMO Number", "IMO"]
)

schedule_locode_col = find_column(
    schedule,
    ["UNLocationCode", "UN Location Code", "LOCODE"]
)

individual_imo_col = find_column(
    individual,
    ["IMO_Normalised", "vesselIMONumber", "IMO Number", "IMO"]
)

individual_locode_col = find_column(
    individual,
    ["UNLOCODE_Normalised", "UNLocationCode", "UN Location Code", "LOCODE"]
)

schedule["IMO_Analysis"] = (
    schedule[schedule_imo_col].apply(normalize_imo)
)

schedule["LOCODE_Analysis"] = (
    schedule[schedule_locode_col].apply(normalize_locode)
)

individual["IMO_Analysis"] = (
    individual[individual_imo_col].apply(normalize_imo)
)

individual["LOCODE_Analysis"] = (
    individual[individual_locode_col].apply(normalize_locode)
)


# ============================================================
# 5. IDENTIFY VERIFIED REPRESENTATION CANDIDATES
# ============================================================

# These are the 14 source-row positions belonging to the
# seven Script 12 source-verified candidate groups.
#
# They are flagged, NOT deleted.
# They should be reviewed before counting physical port calls.


# ============================================================
# 5. IDENTIFY VERIFIED REPRESENTATION CANDIDATES
# ============================================================

verification_file = (
    OUTPUT_TABLES /
    "12_source_row_verification.csv"
)

if not verification_file.exists():
    raise FileNotFoundError(
        "Script 12 source verification file not found."
    )

verification = pd.read_csv(verification_file)

# Confirm that all 14 source rows passed Script 12.
if len(verification) != 14:
    raise ValueError(
        f"Expected 14 candidate records, found {len(verification)}"
    )

if not (
    verification["Verification_Status"]
    == "ALL_CHECKED_FIELDS_MATCH"
).all():
    raise ValueError(
        "Some candidate records have not passed source verification."
    )

candidate_source_rows = set(
    pd.to_numeric(
        verification["Source_Row_Number"],
        errors="raise"
    ).astype(int)
)

if len(candidate_source_rows) != 14:
    raise ValueError(
        "Expected 14 unique candidate source rows."
    )

# Match candidates against the original schedule row number.
schedule["Exact_Representation_Candidate"] = (
    pd.to_numeric(
        schedule["Schedule_Source_Row"],
        errors="coerce"
    ).isin(candidate_source_rows)
)

print("\nREPRESENTATION CANDIDATE VALIDATION")
print("Verified candidate source rows:", len(candidate_source_rows))
print(
    "Candidates flagged in schedule:",
    int(schedule["Exact_Representation_Candidate"].sum())
)


source_row_col = find_column(
    schedule,
    ["Schedule_Source_Row"],
    required=False
)

if source_row_col is None:

    schedule["Schedule_Source_Row"] = np.arange(
        1,
        len(schedule) + 1
    )

    source_row_col = "Schedule_Source_Row"


schedule["Exact_Representation_Candidate"] = (
    pd.to_numeric(
        schedule[source_row_col],
        errors="coerce"
    ).isin(candidate_source_rows)
)


# ============================================================
# 6. ANALYZE SCHEDULE TIMESTAMPS
# ============================================================

timestamp_definitions = {
    "Planned": (
        ["Planned Arrival"],
        ["Planned Departure"]
    ),
    "Estimated": (
        ["Estimated Arrival"],
        ["Estimated Departure"]
    ),
    "Actual": (
        ["Actual Arrival"],
        ["Actual Departure"]
    ),
}

for prefix, (arrival_cols, departure_cols) in (
    timestamp_definitions.items()
):

    schedule = add_timestamp_analysis(
        schedule,
        arrival_cols,
        departure_cols,
        prefix
    )


# ============================================================
# 7. SCHEDULE DATA-QUALITY FLAGS
# ============================================================

schedule["Missing_IMO"] = (
    schedule["IMO_Analysis"].isna()
)

schedule["Missing_LOCODE"] = (
    schedule["LOCODE_Analysis"].isna()
)

schedule["Missing_Actual_Arrival"] = (
    schedule["Actual_Arrival_UTC"].isna()
)

schedule["Missing_Actual_Departure"] = (
    schedule["Actual_Departure_UTC"].isna()
)

schedule["Missing_Actual_Pair"] = (
    ~schedule["Actual_Complete"]
)

schedule["Actual_Negative_Stay"] = (
    schedule["Actual_Negative_Stay"]
)

schedule["Actual_Baseline_Eligible_Core"] = (
    schedule["Actual_Valid_Chronology"]
    & ~schedule["Missing_IMO"]
    & ~schedule["Missing_LOCODE"]
)

# Conservative eligibility excludes the 14 candidate rows
# until their physical-call interpretation is resolved.

schedule["Actual_Baseline_Eligible_Conservative"] = (
    schedule["Actual_Baseline_Eligible_Core"]
    & ~schedule["Exact_Representation_Candidate"]
)


# ============================================================
# 8. CLASSIFY SCHEDULE RECORDS
# ============================================================

def classify_schedule_record(row):

    if row["Missing_IMO"]:
        return "MISSING_IMO"

    if row["Missing_LOCODE"]:
        return "MISSING_LOCODE"

    if row["Actual_Negative_Stay"]:
        return "INVALID_ACTUAL_CHRONOLOGY"

    if row["Actual_Complete"]:
        if row["Exact_Representation_Candidate"]:
            return "ACTUAL_COMPLETE_REVIEW_REPRESENTATION"
        return "ACTUAL_COMPLETE"

    if row["Estimated_Complete"]:
        return "ESTIMATED_ONLY_OR_INCOMPLETE_ACTUAL"

    if row["Planned_Complete"]:
        return "PLANNED_ONLY"

    return "INSUFFICIENT_TIMESTAMP_INFORMATION"


schedule["Analytical_Record_Status"] = (
    schedule.apply(
        classify_schedule_record,
        axis=1
    )
)


# ============================================================
# 9. ANALYZE INDIVIDUAL VESSEL CALLS
# ============================================================

individual = add_timestamp_analysis(
    individual,
    ["ARRI_ACT", "Actual Arrival", "Actual_Arrival"],
    ["DEPA_ACT", "Actual Departure", "Actual_Departure"],
    "Actual"
)

individual = add_timestamp_analysis(
    individual,
    ["ARRI_EST", "Estimated Arrival", "Estimated_Arrival"],
    ["DEPA_EST", "Estimated Departure", "Estimated_Departure"],
    "Estimated"
)

individual = add_timestamp_analysis(
    individual,
    ["ARRI_PLN", "Planned Arrival", "Planned_Arrival"],
    ["DEPA_PLN", "Planned Departure", "Planned_Departure"],
    "Planned"
)


individual["Missing_IMO"] = (
    individual["IMO_Analysis"].isna()
)

individual["Missing_LOCODE"] = (
    individual["LOCODE_Analysis"].isna()
)

individual["Actual_Baseline_Eligible_Core"] = (
    individual["Actual_Valid_Chronology"]
    & ~individual["Missing_IMO"]
    & ~individual["Missing_LOCODE"]
)

individual["Analytical_Record_Status"] = np.select(
    [
        individual["Missing_IMO"],
        individual["Missing_LOCODE"],
        individual["Actual_Negative_Stay"],
        individual["Actual_Complete"],
        individual["Estimated_Complete"],
        individual["Planned_Complete"],
    ],
    [
        "MISSING_IMO",
        "MISSING_LOCODE",
        "INVALID_ACTUAL_CHRONOLOGY",
        "ACTUAL_COMPLETE",
        "ESTIMATED_ONLY_OR_INCOMPLETE_ACTUAL",
        "PLANNED_ONLY",
    ],
    default="INSUFFICIENT_TIMESTAMP_INFORMATION"
)


# ============================================================
# 10. CREATE ACTUAL-ONLY BASELINE DATASETS
# ============================================================

schedule_actual_baseline = schedule.loc[
    schedule["Actual_Baseline_Eligible_Core"]
].copy()

schedule_actual_baseline_conservative = schedule.loc[
    schedule["Actual_Baseline_Eligible_Conservative"]
].copy()

individual_actual_baseline = individual.loc[
    individual["Actual_Baseline_Eligible_Core"]
].copy()


# ============================================================
# 11. CREATE DATASET QUALITY SUMMARY
# ============================================================

def dataset_summary(df, dataset_name):

    return {
        "Dataset": dataset_name,
        "Total_Records": len(df),
        "Unique_IMOs": df["IMO_Analysis"].nunique(),
        "Unique_LOCODEs": df["LOCODE_Analysis"].nunique(),
        "Missing_IMO": int(df["Missing_IMO"].sum()),
        "Missing_LOCODE": int(df["Missing_LOCODE"].sum()),
        "Actual_Complete_Pairs": int(
            df["Actual_Complete"].sum()
        ),
        "Actual_Valid_Chronology": int(
            df["Actual_Valid_Chronology"].sum()
        ),
        "Actual_Negative_Stays": int(
            df["Actual_Negative_Stay"].sum()
        ),
        "Estimated_Complete_Pairs": int(
            df["Estimated_Complete"].sum()
        ),
        "Planned_Complete_Pairs": int(
            df["Planned_Complete"].sum()
        ),
        "Actual_Baseline_Eligible": int(
            df["Actual_Baseline_Eligible_Core"].sum()
        ),
    }


summary = pd.DataFrame([
    dataset_summary(
        schedule,
        "Integrated Schedule"
    ),
    dataset_summary(
        individual,
        "Individual Vessel Calls"
    ),
])


# ============================================================
# 12. RECORD STATUS DISTRIBUTION
# ============================================================

schedule_status_summary = (
    schedule["Analytical_Record_Status"]
    .value_counts(dropna=False)
    .rename_axis("Record_Status")
    .reset_index(name="Record_Count")
)

individual_status_summary = (
    individual["Analytical_Record_Status"]
    .value_counts(dropna=False)
    .rename_axis("Record_Status")
    .reset_index(name="Record_Count")
)


# ============================================================
# 13. TIMESTAMP COVERAGE SUMMARY
# ============================================================

timestamp_coverage = []

for dataset_name, df in [
    ("Integrated Schedule", schedule),
    ("Individual Vessel Calls", individual),
]:

    for source in ["Planned", "Estimated", "Actual"]:

        arrival_col = f"{source}_Arrival_UTC"
        departure_col = f"{source}_Departure_UTC"

        timestamp_coverage.append({
            "Dataset": dataset_name,
            "Timestamp_Source": source,
            "Total_Records": len(df),
            "Arrival_Available": int(
                df[arrival_col].notna().sum()
            ),
            "Departure_Available": int(
                df[departure_col].notna().sum()
            ),
            "Complete_Pairs": int(
                df[f"{source}_Complete"].sum()
            ),
            "Valid_Chronology": int(
                df[f"{source}_Valid_Chronology"].sum()
            ),
            "Negative_Stays": int(
                df[f"{source}_Negative_Stay"].sum()
            ),
        })

timestamp_coverage_df = pd.DataFrame(
    timestamp_coverage
)


# ============================================================
# 14. EXPORT CONSOLIDATED DATASETS
# ============================================================

schedule.to_csv(
    PROCESSED_DIR /
    "13_final_consolidated_schedule.csv",
    index=False
)

individual.to_csv(
    PROCESSED_DIR /
    "13_final_consolidated_individual_calls.csv",
    index=False
)

schedule_actual_baseline.to_csv(
    SIMULATION_INPUTS /
    "13_schedule_actual_baseline_core.csv",
    index=False
)

schedule_actual_baseline_conservative.to_csv(
    SIMULATION_INPUTS /
    "13_schedule_actual_baseline_conservative.csv",
    index=False
)

individual_actual_baseline.to_csv(
    SIMULATION_INPUTS /
    "13_individual_actual_baseline.csv",
    index=False
)


# ============================================================
# 15. EXPORT SUMMARY TABLES
# ============================================================

summary.to_csv(
    OUTPUT_TABLES /
    "13_dataset_readiness_summary.csv",
    index=False
)

timestamp_coverage_df.to_csv(
    OUTPUT_TABLES /
    "13_timestamp_coverage_summary.csv",
    index=False
)

schedule_status_summary.to_csv(
    OUTPUT_TABLES /
    "13_schedule_record_status_summary.csv",
    index=False
)

individual_status_summary.to_csv(
    OUTPUT_TABLES /
    "13_individual_record_status_summary.csv",
    index=False
)


# ============================================================
# 16. GENERATE ANALYTICAL READINESS REPORT
# ============================================================

report_path = (
    OUTPUT_REPORTS /
    "13_analytical_readiness_report.txt"
)

with open(report_path, "w", encoding="utf-8") as file:

    file.write("=" * 75 + "\n")
    file.write("SCRIPT 13: ANALYTICAL READINESS REPORT\n")
    file.write("=" * 75 + "\n\n")

    file.write(
        f"Generated UTC: "
        f"{datetime.now(timezone.utc).isoformat()}\n\n"
    )

    file.write("1. INPUT DATASET DIMENSIONS\n")
    file.write("-" * 50 + "\n")

    file.write(
        f"Integrated schedule: {schedule.shape}\n"
    )

    file.write(
        f"Individual vessel calls: {individual.shape}\n\n"
    )

    file.write("2. DATASET READINESS SUMMARY\n")
    file.write("-" * 50 + "\n")

    file.write(
        summary.to_string(index=False)
    )

    file.write("\n\n3. TIMESTAMP COVERAGE\n")
    file.write("-" * 50 + "\n")

    file.write(
        timestamp_coverage_df.to_string(index=False)
    )

    file.write("\n\n4. SCHEDULE RECORD STATUS\n")
    file.write("-" * 50 + "\n")

    file.write(
        schedule_status_summary.to_string(index=False)
    )

    file.write("\n\n5. INDIVIDUAL CALL STATUS\n")
    file.write("-" * 50 + "\n")

    file.write(
        individual_status_summary.to_string(index=False)
    )

    file.write("\n\n6. BASELINE DATASET SIZES\n")
    file.write("-" * 50 + "\n")

    file.write(
        f"Schedule baseline - core: "
        f"{len(schedule_actual_baseline)} records\n"
    )

    file.write(
        f"Schedule baseline - conservative: "
        f"{len(schedule_actual_baseline_conservative)} records\n"
    )

    file.write(
        f"Individual actual baseline: "
        f"{len(individual_actual_baseline)} records\n"
    )

    file.write(
        f"Schedule representation candidates flagged: "
        f"{int(schedule['Exact_Representation_Candidate'].sum())}\n"
    )

    file.write("\n\n7. METHODOLOGICAL NOTES\n")
    file.write("-" * 50 + "\n")

    file.write(
        "- Planned, estimated and actual timestamps are kept separate.\n"
    )

    file.write(
        "- Actual baseline eligibility requires a complete, "
        "non-negative actual port stay, IMO and LOCODE.\n"
    )

    file.write(
        "- The core baseline retains representation candidates "
        "but flags them.\n"
    )

    file.write(
        "- The conservative baseline excludes the 14 previously "
        "identified candidate source rows pending physical-call review.\n"
    )

    file.write(
        "- No original records have been deleted.\n"
    )

    file.write(
        "- Actual port calls do not establish the vessel's route "
        "through the Strait of Hormuz.\n"
    )

    file.write(
        "- AIS trajectory or another reliable movement source "
        "is still required to confirm Strait transit.\n"
    )

    file.write("\n" + "=" * 75 + "\n")
    file.write("END OF REPORT\n")
    file.write("=" * 75 + "\n")


# ============================================================
# 17. TERMINAL SUMMARY
# ============================================================

print("\n" + "=" * 75)
print("SCRIPT 13 COMPLETED")
print("=" * 75)

print("\nDATASET READINESS SUMMARY")
print(summary.to_string(index=False))

print("\nTIMESTAMP COVERAGE")
print(timestamp_coverage_df.to_string(index=False))

print("\nBASELINE DATASET SIZES")

print(
    "Schedule core baseline:",
    len(schedule_actual_baseline)
)

print(
    "Schedule conservative baseline:",
    len(schedule_actual_baseline_conservative)
)

print(
    "Individual actual baseline:",
    len(individual_actual_baseline)
)

print("\nFLAGGED REPRESENTATION CANDIDATES:")
print(
    int(schedule["Exact_Representation_Candidate"].sum())
)

print("\nOUTPUT FILES")

print(
    PROCESSED_DIR /
    "13_final_consolidated_schedule.csv"
)

print(
    PROCESSED_DIR /
    "13_final_consolidated_individual_calls.csv"
)

print(
    SIMULATION_INPUTS /
    "13_schedule_actual_baseline_core.csv"
)

print(
    SIMULATION_INPUTS /
    "13_schedule_actual_baseline_conservative.csv"
)

print(
    SIMULATION_INPUTS /
    "13_individual_actual_baseline.csv"
)

print(
    OUTPUT_TABLES /
    "13_dataset_readiness_summary.csv"
)

print(
    OUTPUT_TABLES /
    "13_timestamp_coverage_summary.csv"
)

print(report_path)

print("\nNo original records were deleted or modified.")
print("=" * 75)
