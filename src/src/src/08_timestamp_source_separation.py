\
from pathlib import Path
import pandas as pd
import numpy as np


# ============================================================
# SCRIPT 08: TIMESTAMP SOURCE SEPARATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_TABLES = PROJECT_ROOT / "outputs" / "tables"
OUTPUT_REPORTS = PROJECT_ROOT / "outputs" / "reports"

OUTPUT_TABLES.mkdir(parents=True, exist_ok=True)
OUTPUT_REPORTS.mkdir(parents=True, exist_ok=True)


# Use Script 06 integrated datasets
INDIVIDUAL_FILE = (
    DATA_DIR / "06_individual_vessel_port_calls.csv"
)

SCHEDULE_FILE = (
    DATA_DIR / "06_integrated_schedule_vessel_port.csv"
)


# ============================================================
# 1. DATASET-SPECIFIC COLUMN MAPPING
# ============================================================

COLUMN_MAPPING = {

    "INDIVIDUAL": {
        "arrival": {
            "ACTUAL": "ARRI_ACT",
            "ESTIMATED": "ARRI_EST",
            "PLANNED": "ARRI_PLN"
        },

        "departure": {
            "ACTUAL": "DEPA_ACT",
            "ESTIMATED": "DEPA_EST",
            "PLANNED": "DEPA_PLN"
        },

        "imo": "IMO_Normalised",
        "vessel": "vesselName",
        "port": "portName",
        "locode": "UNLOCODE_Normalised",
        "service": "carrierServiceCode",
        "import_voyage": "carrierImportVoyageNumber",
        "export_voyage": "carrierExportVoyageNumber",
        "reference": "Transport_Call_Reference_Normalised",
        "row_id": None
    },

    "SCHEDULE": {
        "arrival": {
            "ACTUAL": "Actual Arrival",
            "ESTIMATED": "Estimated Arrival",
            "PLANNED": "Planned Arrival"
        },

        "departure": {
            "ACTUAL": "Actual Departure",
            "ESTIMATED": "Estimated Departure",
            "PLANNED": "Planned Departure"
        },

        "imo": "IMO_Normalised",
        "vessel": "Vessel Name",
        "port": "Port",
        "locode": "UNLOCODE_Normalised",
        "service": "Carrier Service Code",
        "import_voyage": "Import Voyage Number",
        "export_voyage": "Export Voyage Number",
        "reference": None,
        "row_id": "Source_Row_ID"
    }
}


# ============================================================
# 2. LOAD DATA
# ============================================================

def load_data(file_path):

    if not file_path.exists():
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    df = pd.read_csv(
        file_path,
        low_memory=False
    )

    print(f"\nLoaded: {file_path.name}")
    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns):,}")

    return df


individual = load_data(INDIVIDUAL_FILE)
schedule = load_data(SCHEDULE_FILE)


# ============================================================
# 3. PREPARE SOURCE-SPECIFIC TIMESTAMP ANALYSIS
# ============================================================

def create_source_analysis(df, dataset_name, source):

    df = df.copy()

    mapping = COLUMN_MAPPING[dataset_name]

    arrival_col = mapping["arrival"][source]
    departure_col = mapping["departure"][source]

    required_columns = [
        arrival_col,
        departure_col,
        mapping["imo"],
        mapping["vessel"],
        mapping["port"],
        mapping["locode"]
    ]

    for col in required_columns:

        if col not in df.columns:
            raise KeyError(
                f"{dataset_name}: missing required column '{col}'"
            )

    # Parse timestamps independently.
    arrival = pd.to_datetime(
        df[arrival_col],
        errors="coerce",
        utc=True
    )

    departure = pd.to_datetime(
        df[departure_col],
        errors="coerce",
        utc=True
    )

    result = pd.DataFrame(index=df.index)

    # Dataset information
    result["Source_Dataset"] = dataset_name
    result["Timestamp_Source"] = source

    # Vessel information
    result["IMO_Normalised"] = df[mapping["imo"]]
    result["Vessel_Name"] = df[mapping["vessel"]]

    # Port information
    result["Port_Name"] = df[mapping["port"]]
    result["UNLOCODE"] = df[mapping["locode"]]

    # Voyage information
    for output_col, mapping_key in [
        ("Service_Code", "service"),
        ("Import_Voyage_Number", "import_voyage"),
        ("Export_Voyage_Number", "export_voyage"),
        ("Call_Reference", "reference"),
        ("Source_Row_ID", "row_id")
    ]:

        source_col = mapping[mapping_key]

        if source_col is not None and source_col in df.columns:
            result[output_col] = df[source_col]

    # Source-specific timestamps
    result["Arrival_UTC"] = arrival
    result["Departure_UTC"] = departure

    # Missing timestamp indicators
    result["Missing_Arrival"] = arrival.isna()
    result["Missing_Departure"] = departure.isna()

    result["Complete_Timestamp_Pair"] = (
        arrival.notna() & departure.notna()
    )

    # Port stay duration
    result["Port_Stay_Hours"] = (
        departure - arrival
    ).dt.total_seconds() / 3600

    # Chronology flags
    result["Negative_Port_Stay"] = (
        result["Port_Stay_Hours"] < 0
    )

    result["Zero_Port_Stay"] = (
        result["Port_Stay_Hours"] == 0
    )

    return result.reset_index(drop=True)


# ============================================================
# 4. GENERATE SIX INDEPENDENT DATASETS
# ============================================================

datasets = {
    "INDIVIDUAL": individual,
    "SCHEDULE": schedule
}

analysis_results = {}

for dataset_name, df in datasets.items():

    for source in ["ACTUAL", "ESTIMATED", "PLANNED"]:

        result = create_source_analysis(
            df,
            dataset_name,
            source
        )

        key = f"{dataset_name}_{source}"

        analysis_results[key] = result

        output_file = (
            OUTPUT_TABLES /
            f"08_{key.lower()}_port_stays.csv"
        )

        result.to_csv(
            output_file,
            index=False
        )

        print(f"Saved: {output_file.name}")


# ============================================================
# 5. SOURCE-SPECIFIC QUALITY SUMMARY
# ============================================================

summary_rows = []

for key, df in analysis_results.items():

    complete = df["Complete_Timestamp_Pair"]

    valid_stays = (
        df.loc[complete, "Port_Stay_Hours"]
        .dropna()
    )

    nonnegative_stays = valid_stays[
        valid_stays >= 0
    ]

    summary_rows.append({

        "Dataset_Source": key,

        "Total_Records": len(df),

        "Records_With_Complete_Timestamps": int(
            complete.sum()
        ),

        "Missing_Arrival": int(
            df["Missing_Arrival"].sum()
        ),

        "Missing_Departure": int(
            df["Missing_Departure"].sum()
        ),

        "Negative_Port_Stay": int(
            df["Negative_Port_Stay"].sum()
        ),

        "Zero_Port_Stay": int(
            df["Zero_Port_Stay"].sum()
        ),

        "Valid_Nonnegative_Port_Stays": len(
            nonnegative_stays
        ),

        "Mean_Port_Stay_Hours": (
            nonnegative_stays.mean()
            if len(nonnegative_stays) > 0
            else np.nan
        ),

        "Median_Port_Stay_Hours": (
            nonnegative_stays.median()
            if len(nonnegative_stays) > 0
            else np.nan
        ),

        "Minimum_Port_Stay_Hours": (
            nonnegative_stays.min()
            if len(nonnegative_stays) > 0
            else np.nan
        ),

        "Maximum_Port_Stay_Hours": (
            nonnegative_stays.max()
            if len(nonnegative_stays) > 0
            else np.nan
        ),

        "Unique_Vessels": df[
            "IMO_Normalised"
        ].nunique(),

        "Unique_Ports": df[
            "UNLOCODE"
        ].nunique()
    })


summary = pd.DataFrame(summary_rows)

summary_file = (
    OUTPUT_TABLES /
    "08_timestamp_source_quality_summary.csv"
)

summary.to_csv(
    summary_file,
    index=False
)


# ============================================================
# 6. NEGATIVE PORT-STAY INVESTIGATION
# ============================================================

negative_records = []

for key, df in analysis_results.items():

    anomalies = df[
        df["Negative_Port_Stay"]
    ].copy()

    if not anomalies.empty:
        anomalies["Dataset_Source"] = key
        negative_records.append(anomalies)


if negative_records:

    negative_summary = pd.concat(
        negative_records,
        ignore_index=True
    )

else:

    negative_summary = pd.DataFrame()


negative_file = (
    OUTPUT_TABLES /
    "08_negative_port_stay_investigation.csv"
)

negative_summary.to_csv(
    negative_file,
    index=False
)


# ============================================================
# 7. REPORT
# ============================================================

report_file = (
    OUTPUT_REPORTS /
    "08_timestamp_source_separation_report.txt"
)

with open(
    report_file,
    "w",
    encoding="utf-8"
) as f:

    f.write("=" * 75 + "\n")
    f.write("SCRIPT 08: TIMESTAMP SOURCE SEPARATION\n")
    f.write("=" * 75 + "\n\n")

    f.write(
        "Actual, estimated and planned timestamps "
        "are analysed independently.\n\n"
    )

    f.write(
        "No missing timestamp is substituted "
        "with another timestamp source.\n\n"
    )

    f.write("SOURCE-SPECIFIC QUALITY SUMMARY\n")
    f.write("-" * 75 + "\n\n")

    f.write(
        summary.to_string(
            index=False,
            float_format=lambda x: f"{x:.2f}"
        )
    )

    f.write("\n\nINTERPRETATION NOTES\n")
    f.write("-" * 75 + "\n")

    f.write(
        "1. Actual stay requires actual arrival "
        "and actual departure.\n"
    )

    f.write(
        "2. Estimated stay uses estimated timestamps only.\n"
    )

    f.write(
        "3. Planned stay uses planned timestamps only.\n"
    )

    f.write(
        "4. Negative stays are retained for investigation.\n"
    )

    f.write(
        "5. Mean and median exclude negative durations.\n"
    )

    f.write(
        "6. These calculations do not establish sailing time.\n"
    )

    f.write(
        f"\nTotal negative records across six views: "
        f"{len(negative_summary)}\n"
    )


# ============================================================
# 8. DISPLAY RESULTS
# ============================================================

print("\n" + "=" * 75)
print("SCRIPT 08 COMPLETED SUCCESSFULLY")
print("=" * 75)

print("\nSOURCE-SPECIFIC QUALITY SUMMARY\n")

print(
    summary.to_string(
        index=False,
        float_format=lambda x: f"{x:.2f}"
    )
)

print("\nOUTPUT FILES")
print("-" * 75)

print(f"Summary: {summary_file}")
print(f"Negative records: {negative_file}")
print(f"Report: {report_file}")

print("\nAll six source-specific datasets saved.")

print("\nNext step: inspect the timestamp-source summary.")