
from pathlib import Path
import pandas as pd
import zipfile
import io

# ============================================================
# 1. PROJECT PATHS
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"

REPORT_DIR = PROJECT_DIR / "outputs" / "reports"
TABLE_DIR = PROJECT_DIR / "outputs" / "tables"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
TABLE_DIR.mkdir(parents=True, exist_ok=True)

ZIP_PATH = RAW_DIR / "individual_vessels-20261112T213245Z-1-001.zip"

SCHEDULE_PATH = RAW_DIR / "Combined_Port_Schedules.xlsx"
PORT_PATH = RAW_DIR / "active_ports.csv"
VESSEL_PATH = RAW_DIR / "active_vessels.csv"

REPORT_PATH = REPORT_DIR / "02_data_quality_report.txt"

# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def section(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def normalise_identifier(series):
    """
    Convert identifiers into comparable strings.
    Avoid treating missing values as identifiers.
    """
    result = series.astype("string").str.strip().str.upper()

    # Correct Excel-style numeric IDs such as 9224506.0
    result = result.str.replace(r"\.0$", "", regex=True)

    return result.replace("", pd.NA)


def identifier_report(df, column, dataset_name):
    """
    Analyse missing and duplicated identifiers.
    """

    if column not in df.columns:
        return

    values = normalise_identifier(df[column])

    print(f"\n{dataset_name} - {column}")
    print("Total records:", len(df))
    print("Missing identifiers:", values.isna().sum())
    print("Unique identifiers:", values.nunique(dropna=True))
    print("Repeated identifier records:",
          values.duplicated(keep=False).sum())

    duplicates = values[values.duplicated(keep=False)].dropna()

    if not duplicates.empty:
        print("Examples of repeated identifiers:")
        print(duplicates.value_counts().head(10).to_string())


def missing_value_report(df, dataset_name):
    """
    Generate missing-value statistics.
    """

    missing = df.isna().sum()

    result = pd.DataFrame({
        "Dataset": dataset_name,
        "Column": df.columns,
        "Missing_Count": missing.values,
        "Missing_Percentage": (
            missing.values / len(df) * 100
            if len(df) > 0 else 0
        )
    })

    return result


def duplicate_report(df, dataset_name):
    """
    Count exact duplicate records.
    """

    exact = int(df.duplicated().sum())

    print(f"\n{dataset_name}")
    print("Exact duplicate rows:", exact)

    return {
        "Dataset": dataset_name,
        "Rows": len(df),
        "Columns": len(df.columns),
        "Exact_Duplicates": exact
    }


def timestamp_report(df, columns, dataset_name):
    """
    Check timestamp parsing and missing values.
    Does not overwrite original timestamp columns.
    """

    results = []

    for column in columns:

        if column not in df.columns:
            continue

        original = df[column]
        parsed = pd.to_datetime(
            original,
            errors="coerce",
            utc=True,
            format="mixed"
        )

        non_missing = original.notna() & original.astype(
            "string"
        ).str.strip().ne("")

        invalid = non_missing & parsed.isna()

        results.append({
            "Dataset": dataset_name,
            "Column": column,
            "Total_Records": len(df),
            "Missing": int((~non_missing).sum()),
            "Invalid_Timestamps": int(invalid.sum()),
            "Valid_Timestamps": int(parsed.notna().sum())
        })

        print(f"\n{column}")
        print("Missing:", int((~non_missing).sum()))
        print("Invalid timestamps:", int(invalid.sum()))
        print("Valid timestamps:", int(parsed.notna().sum()))

        if invalid.any():
            print("Invalid examples:")
            print(original[invalid].head(5).to_string(index=False))

    return results


# ============================================================
# 3. LOAD MAIN DATASETS
# ============================================================

def load_main_datasets():

    section("LOADING MAIN DATASETS")

    schedules = pd.read_excel(SCHEDULE_PATH)

    ports = pd.read_csv(
        PORT_PATH,
        encoding="utf-8-sig",
        low_memory=False
    )

    vessels = pd.read_csv(
        VESSEL_PATH,
        encoding="utf-8-sig",
        low_memory=False
    )

    print("Port schedules:", schedules.shape)
    print("Active ports:", ports.shape)
    print("Active vessels:", vessels.shape)

    return schedules, ports, vessels


# ============================================================
# 4. MISSING VALUES AND DUPLICATE ANALYSIS
# ============================================================

def analyse_completeness(datasets):

    section("MISSING VALUE ANALYSIS")

    missing_results = []
    duplicate_results = []

    for name, df in datasets.items():

        print(f"\nInspecting: {name}")

        missing_results.append(
            missing_value_report(df, name)
        )

        duplicate_results.append(
            duplicate_report(df, name)
        )

    missing_df = pd.concat(
        missing_results,
        ignore_index=True
    )

    duplicate_df = pd.DataFrame(duplicate_results)

    missing_df.to_csv(
        TABLE_DIR / "02_missing_value_summary.csv",
        index=False
    )

    duplicate_df.to_csv(
        TABLE_DIR / "02_duplicate_summary.csv",
        index=False
    )

    print("\nMissing-value report saved.")
    print("Duplicate report saved.")

    return missing_df, duplicate_df


# ============================================================
# 5. IDENTIFIER QUALITY ANALYSIS
# ============================================================

def analyse_identifiers(schedules, ports, vessels):

    section("IDENTIFIER QUALITY ANALYSIS")

    identifier_report(
        schedules, "IMO Number", "Port Schedules"
    )

    identifier_report(
        schedules, "UN Location Code", "Port Schedules"
    )

    identifier_report(
        ports, "UNLocationCode", "Active Ports"
    )

    identifier_report(
        vessels, "vesselIMONumber", "Active Vessels"
    )

    identifier_report(
        vessels, "carrierVesselCode", "Active Vessels"
    )

    # Cross-dataset IMO matching

    schedule_imo = set(
        normalise_identifier(
            schedules["IMO Number"]
        ).dropna()
    )

    active_imo = set(
        normalise_identifier(
            vessels["vesselIMONumber"]
        ).dropna()
    )

    section("CROSS-DATASET VESSEL MATCHING")

    common_imo = schedule_imo.intersection(active_imo)

    print("Unique schedule IMO values:", len(schedule_imo))
    print("Unique active vessel IMO values:", len(active_imo))
    print("Matching IMO values:", len(common_imo))
    print(
        "Schedule IMO values not in active vessel master:",
        len(schedule_imo - active_imo)
    )

    # Cross-dataset port matching

    schedule_ports = set(
        normalise_identifier(
            schedules["UN Location Code"]
        ).dropna()
    )

    active_ports = set(
        normalise_identifier(
            ports["UNLocationCode"]
        ).dropna()
    )

    common_ports = schedule_ports.intersection(active_ports)

    print("\nUnique schedule port codes:", len(schedule_ports))
    print("Unique active port codes:", len(active_ports))
    print("Matching port codes:", len(common_ports))
    print(
        "Schedule port codes not in active port master:",
        len(schedule_ports - active_ports)
    )


# ============================================================
# 6. TIMESTAMP QUALITY ANALYSIS
# ============================================================

def analyse_schedule_timestamps(schedules):

    section("PORT SCHEDULE TIMESTAMP ANALYSIS")

    schedule_columns = [
        "Planned Arrival",
        "Estimated Arrival",
        "Actual Arrival",
        "Planned Departure",
        "Estimated Departure",
        "Actual Departure"
    ]

    results = timestamp_report(
        schedules,
        schedule_columns,
        "Port Schedules"
    )

    # Check actual departure before actual arrival
    # Only compare records where both timestamps are valid.

    arrival = pd.to_datetime(
        schedules["Actual Arrival"],
        errors="coerce",
        utc=True,
        format="mixed"
    )

    departure = pd.to_datetime(
        schedules["Actual Departure"],
        errors="coerce",
        utc=True,
        format="mixed"
    )

    valid = arrival.notna() & departure.notna()

    invalid_order = valid & (departure < arrival)

    print("\nACTUAL ARRIVAL-DEPARTURE CHRONOLOGY")
    print("Records with both timestamps:", int(valid.sum()))
    print("Departure before arrival:", int(invalid_order.sum()))

    # Compare planned and estimated chronology

    planned_arrival = pd.to_datetime(
        schedules["Planned Arrival"],
        errors="coerce",
        utc=True,
        format="mixed"
    )

    planned_departure = pd.to_datetime(
        schedules["Planned Departure"],
        errors="coerce",
        utc=True,
        format="mixed"
    )

    planned_valid = (
        planned_arrival.notna() &
        planned_departure.notna()
    )

    planned_invalid = (
        planned_valid &
        (planned_departure < planned_arrival)
    )

    print("\nPLANNED ARRIVAL-DEPARTURE CHRONOLOGY")
    print("Records with both timestamps:", int(planned_valid.sum()))
    print("Departure before arrival:", int(planned_invalid.sum()))

    pd.DataFrame(results).to_csv(
        TABLE_DIR / "02_timestamp_quality.csv",
        index=False
    )

    return results


# ============================================================
# 7. INDIVIDUAL VESSEL FILE ANALYSIS
# ============================================================

def analyse_individual_vessels():

    section("INDIVIDUAL VESSEL FILE ANALYSIS")

    if not ZIP_PATH.exists():
        print("ERROR: Vessel ZIP file not found.")
        return

    file_results = []
    all_frames = []
    schema_columns = {}

    with zipfile.ZipFile(ZIP_PATH, "r") as archive:

        csv_files = [
            name for name in archive.namelist()
            if name.lower().endswith(".csv")
        ]

        print("Total vessel files:", len(csv_files))

        for filename in csv_files:

            try:

                with archive.open(filename) as file:

                    df = pd.read_csv(
                        io.BytesIO(file.read()),
                        encoding="utf-8-sig",
                        low_memory=False
                    )

                # Track schema
                schema_columns[filename] = set(df.columns)

                # Add IMO from filename if appropriate
                # Only use numeric filenames as candidate IMO IDs.
                file_id = Path(filename).stem

                if file_id.isdigit():
                    df["archive_file_imo"] = file_id

                df["archive_source_file"] = filename

                all_frames.append(df)

                file_results.append({
                    "File": filename,
                    "Rows": len(df),
                    "Columns": len(df.columns),
                    "Missing_Cells": int(df.isna().sum().sum()),
                    "Exact_Duplicates": int(df.duplicated().sum())
                })

            except Exception as error:

                print(f"Error reading {filename}: {error}")

    summary = pd.DataFrame(file_results)

    summary.to_csv(
        TABLE_DIR / "02_individual_vessel_file_summary.csv",
        index=False
    )

    print("\nINDIVIDUAL FILE SUMMARY")
    print(summary.to_string(index=False))

    print("\nTotal individual vessel records:", summary["Rows"].sum())

    # Schema comparison

    section("VESSEL FILE SCHEMA CONSISTENCY")

    if schema_columns:

        all_columns = set().union(*schema_columns.values())

        schema_rows = []

        for filename, columns in schema_columns.items():

            missing_columns = all_columns - columns
            extra_count = len(columns)

            schema_rows.append({
                "File": filename,
                "Column_Count": extra_count,
                "Missing_Columns": ", ".join(
                    sorted(missing_columns)
                )
            })

            print(
                filename,
                "| Columns:", extra_count,
                "| Missing schema columns:", len(missing_columns)
            )

        pd.DataFrame(schema_rows).to_csv(
            TABLE_DIR / "02_vessel_schema_consistency.csv",
            index=False
        )

        print("\nTotal distinct columns across files:", len(all_columns))

    # Combine files for identifier and timestamp analysis.
    # This is an analysis-only concatenation, not the final master table.

    if all_frames:

        combined = pd.concat(
            all_frames,
            ignore_index=True,
            sort=False
        )

        section("COMBINED INDIVIDUAL VESSEL RECORD ANALYSIS")

        print("Combined rows:", len(combined))
        print("Combined columns:", len(combined.columns))

        if "vesselIMONumber" in combined.columns:
            identifier_report(
                combined,
                "vesselIMONumber",
                "Individual Vessel Records"
            )

        if "UNLocationCode" in combined.columns:
            identifier_report(
                combined,
                "UNLocationCode",
                "Individual Vessel Records"
            )

        if "transportCallReference" in combined.columns:
            identifier_report(
                combined,
                "transportCallReference",
                "Individual Vessel Records"
            )

        vessel_timestamp_columns = [
            "ARRI_EST",
            "ARRI_ACT",
            "ARRI_PLN",
            "DEPA_EST",
            "DEPA_ACT",
            "DEPA_PLN"
        ]

        timestamp_report(
            combined,
            vessel_timestamp_columns,
            "Individual Vessel Records"
        )

        combined.to_csv(
            TABLE_DIR / "02_individual_vessel_combined_quality.csv",
            index=False
        )

        print("\nAnalysis-only combined vessel file saved.")


# ============================================================
# 8. MAIN EXECUTION
# ============================================================

def main():

    section("STRAIT OF HORMUZ - DATA QUALITY ANALYSIS")

    schedules, ports, vessels = load_main_datasets()

    datasets = {
        "Port Schedules": schedules,
        "Active Ports": ports,
        "Active Vessels": vessels
    }

    analyse_completeness(datasets)

    analyse_identifiers(
        schedules,
        ports,
        vessels
    )

    analyse_schedule_timestamps(schedules)

    analyse_individual_vessels()

    section("DATA QUALITY ANALYSIS COMPLETED")

    print("Text report:", REPORT_PATH)
    print("CSV tables:", TABLE_DIR)


# ============================================================
# 9. SAVE COMPLETE TEXT REPORT
# ============================================================

if __name__ == "__main__":

    import contextlib

    with open(
        REPORT_PATH,
        "w",
        encoding="utf-8"
    ) as report:

        with contextlib.redirect_stdout(report):
            main()

    print("DATA QUALITY ANALYSIS COMPLETED SUCCESSFULLY")
    print("\nReport saved at:")
    print(REPORT_PATH)