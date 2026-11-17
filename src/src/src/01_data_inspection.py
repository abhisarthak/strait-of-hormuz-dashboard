
from pathlib import Path
import pandas as pd
import zipfile
import io
from datetime import datetime

# ============================================================
# 1. PROJECT PATHS
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
REPORT_DIR = PROJECT_DIR / "outputs" / "reports"

REPORT_DIR.mkdir(parents=True, exist_ok=True)

REPORT_PATH = REPORT_DIR / "01_data_inspection_output.txt"

# ============================================================
# 2. DATASET PATHS
# ============================================================

DATASETS = {
    "Port Schedules": RAW_DIR / "Combined_Port_Schedules.xlsx",
    "Active Ports": RAW_DIR / "active_ports.csv",
    "Active Vessels": RAW_DIR / "active_vessels.csv"
}

ZIP_PATH = (
    RAW_DIR /
    "individual_vessels-20261112T213245Z-1-001.zip"
)

# ============================================================
# 3. INSPECTION FUNCTION
# ============================================================

def inspect_dataframe(df, dataset_name):

    print("\n" + "=" * 75)
    print(f"DATASET: {dataset_name}")
    print("=" * 75)

    # Dimensions
    print("\n1. DATASET DIMENSIONS")
    print("Rows:", df.shape[0])
    print("Columns:", df.shape[1])

    # Column names
    print("\n2. COLUMN NAMES")
    for column in df.columns:
        print("-", column)

    # Data types
    print("\n3. DATA TYPES")
    print(df.dtypes.to_string())

    # Missing values
    print("\n4. MISSING VALUES")
    missing = df.isnull().sum()

    missing_report = pd.DataFrame({
        "Missing_Count": missing,
        "Missing_Percentage": (
            missing / len(df) * 100 if len(df) else 0
        )
    })

    print(missing_report.to_string())

    # Duplicates
    print("\n5. DUPLICATE RECORDS")
    print("Exact duplicate rows:", df.duplicated().sum())

    # Unique values
    print("\n6. UNIQUE VALUES")

    for column in df.columns:
        if column.lower() in [
            "imo",
            "imo number",
            "vesselimonumber",
            "un location code",
            "un_locode"
        ]:
            print(
                f"Unique values in {column}:",
                df[column].nunique(dropna=True)
            )

    # Sample records
    print("\n7. FIRST FIVE RECORDS")
    print(df.head().to_string(index=False))

    # Summary statistics
    print("\n8. SUMMARY")
    print(df.describe(include="all").to_string())


# ============================================================
# 4. INSPECT MAIN DATASETS
# ============================================================

def inspect_main_datasets():

    print("\n" + "#" * 75)
    print("MAIN DATASET INSPECTION")
    print("#" * 75)

    for dataset_name, file_path in DATASETS.items():

        print(f"\nChecking file: {file_path.name}")

        if not file_path.exists():
            print("ERROR: FILE NOT FOUND")
            continue

        try:

            if file_path.suffix.lower() == ".xlsx":
                df = pd.read_excel(file_path)

            elif file_path.suffix.lower() == ".csv":
                df = pd.read_csv(
                    file_path,
                    encoding="utf-8-sig",
                    low_memory=False
                )

            else:
                print("Unsupported file format.")
                continue

            inspect_dataframe(df, dataset_name)

        except Exception as error:
            print("ERROR while reading dataset:", error)


# ============================================================
# 5. INSPECT INDIVIDUAL VESSEL ZIP
# ============================================================

def inspect_vessel_zip():

    print("\n" + "#" * 75)
    print("INDIVIDUAL VESSEL DATA INSPECTION")
    print("#" * 75)

    if not ZIP_PATH.exists():
        print("ERROR: ZIP FILE NOT FOUND")
        print("Expected path:", ZIP_PATH)
        return

    try:

        with zipfile.ZipFile(ZIP_PATH, "r") as archive:

            csv_files = [
                name for name in archive.namelist()
                if name.lower().endswith(".csv")
            ]

            print("\nTotal CSV files:", len(csv_files))

            print("\nCSV FILE INVENTORY")

            for filename in csv_files:
                print("-", filename)

            total_records = 0
            vessel_summaries = []

            for filename in csv_files:

                try:

                    with archive.open(filename) as file:

                        df = pd.read_csv(
                            io.BytesIO(file.read()),
                            encoding="utf-8-sig",
                            low_memory=False
                        )

                    total_records += len(df)

                    vessel_summaries.append({
                        "File": filename,
                        "Rows": len(df),
                        "Columns": len(df.columns),
                        "Duplicates": int(df.duplicated().sum()),
                        "Missing_Cells": int(df.isnull().sum().sum())
                    })

                except Exception as error:

                    print(
                        f"\nERROR reading {filename}: {error}"
                    )

            print("\nVESSEL FILE SUMMARY")

            summary_df = pd.DataFrame(vessel_summaries)

            if not summary_df.empty:
                print(summary_df.to_string(index=False))

            print("\nTotal vessel records:", total_records)

            # Inspect first vessel CSV in detail
            if csv_files:

                first_file = csv_files[0]

                print("\nDETAILED INSPECTION OF FIRST VESSEL FILE")
                print("Filename:", first_file)

                with archive.open(first_file) as file:

                    sample_df = pd.read_csv(
                        io.BytesIO(file.read()),
                        encoding="utf-8-sig",
                        low_memory=False
                    )

                inspect_dataframe(
                    sample_df,
                    f"Individual Vessel: {first_file}"
                )

    except zipfile.BadZipFile:
        print("ERROR: The ZIP file is invalid or corrupted.")

    except Exception as error:
        print("ERROR while inspecting ZIP:", error)


# ============================================================
# 6. MAIN EXECUTION
# ============================================================

def main():

    print("=" * 75)
    print("STRAIT OF HORMUZ RESEARCH")
    print("INITIAL DATA INSPECTION REPORT")
    print("=" * 75)

    print("\nGenerated:", datetime.now())
    print("Project directory:", PROJECT_DIR)
    print("Raw data directory:", RAW_DIR)

    inspect_main_datasets()
    inspect_vessel_zip()

    print("\n" + "=" * 75)
    print("DATA INSPECTION COMPLETED")
    print("=" * 75)


# ============================================================
# 7. SAVE REPORT AND DISPLAY OUTPUT
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

    print("DATA INSPECTION COMPLETED SUCCESSFULLY")
    print("\nReport saved at:")
    print(REPORT_PATH)