
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

ZIP_PATH = RAW_DIR / (
    "individual_vessels-20261112T213245Z-1-001.zip"
)

SCHEDULE_PATH = RAW_DIR / "Combined_Port_Schedules.xlsx"
PORT_PATH = RAW_DIR / "active_ports.csv"
VESSEL_PATH = RAW_DIR / "active_vessels.csv"

REPORT_PATH = (
    REPORT_DIR / "03_identifier_schema_validation.txt"
)


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def section(title):
    print("\n" + "=" * 85)
    print(title)
    print("=" * 85)


def clean_id(series):
    """
    Standardise identifier representation for comparison.
    Does not modify original datasets.
    """

    values = series.astype("string").str.strip().str.upper()

    values = values.str.replace(
        r"\.0$",
        "",
        regex=True
    )

    return values.replace("", pd.NA)


def save_table(df, filename):
    path = TABLE_DIR / filename
    df.to_csv(path, index=False)
    print("Saved:", path.name)


# ============================================================
# 3. LOAD MAIN DATASETS
# ============================================================

def load_datasets():

    section("LOADING DATASETS")

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

    print("Schedules:", schedules.shape)
    print("Ports:", ports.shape)
    print("Vessels:", vessels.shape)

    return schedules, ports, vessels


# ============================================================
# 4. VALIDATE VESSEL FILE NAME AGAINST INTERNAL IMO
# ============================================================

def validate_vessel_filenames():

    section("VESSEL FILENAME VS INTERNAL IMO VALIDATION")

    results = []
    all_frames = []

    if not ZIP_PATH.exists():
        print("ERROR: Vessel ZIP file not found.")
        return pd.DataFrame(), pd.DataFrame()

    with zipfile.ZipFile(ZIP_PATH, "r") as archive:

        csv_files = [
            name for name in archive.namelist()
            if name.lower().endswith(".csv")
        ]

        for filename in csv_files:

            file_imo = Path(filename).stem

            try:

                with archive.open(filename) as file:

                    df = pd.read_csv(
                        io.BytesIO(file.read()),
                        encoding="utf-8-sig",
                        low_memory=False
                    )

                # Preserve source filename
                df["archive_file"] = filename

                all_frames.append(df)

                if "vesselIMONumber" not in df.columns:

                    results.append({
                        "File": filename,
                        "Filename_IMO": file_imo,
                        "Internal_IMOs": "",
                        "Unique_Internal_IMOs": 0,
                        "Rows": len(df),
                        "Filename_Matches_Internal": False,
                        "Validation_Status": "IMO_COLUMN_MISSING"
                    })

                    continue

                internal_imo = clean_id(
                    df["vesselIMONumber"]
                )

                unique_imos = sorted(
                    internal_imo.dropna().unique().tolist()
                )

                filename_match = file_imo in unique_imos

                if len(unique_imos) == 0:
                    status = "NO_INTERNAL_IMO"

                elif len(unique_imos) > 1 and filename_match:
                    status = "MULTIPLE_IMOS_FILENAME_PRESENT"

                elif len(unique_imos) > 1:
                    status = "MULTIPLE_IMOS_FILENAME_NOT_PRESENT"

                elif filename_match:
                    status = "MATCH"

                else:
                    status = "MISMATCH"

                results.append({
                    "File": filename,
                    "Filename_IMO": file_imo,
                    "Internal_IMOs": "; ".join(unique_imos),
                    "Unique_Internal_IMOs": len(unique_imos),
                    "Rows": len(df),
                    "Filename_Matches_Internal": filename_match,
                    "Validation_Status": status
                })

            except Exception as error:

                results.append({
                    "File": filename,
                    "Filename_IMO": file_imo,
                    "Internal_IMOs": "",
                    "Unique_Internal_IMOs": 0,
                    "Rows": 0,
                    "Filename_Matches_Internal": False,
                    "Validation_Status": f"READ_ERROR: {error}"
                })

    filename_df = pd.DataFrame(results)

    print("\nFILENAME VALIDATION SUMMARY")

    if not filename_df.empty:

        print(
            filename_df["Validation_Status"]
            .value_counts(dropna=False)
            .to_string()
        )

        print("\nDetailed results:")
        print(filename_df.to_string(index=False))

    combined_df = (
        pd.concat(all_frames, ignore_index=True, sort=False)
        if all_frames else pd.DataFrame()
    )

    save_table(
        filename_df,
        "03_vessel_filename_validation.csv"
    )

    return filename_df, combined_df


# ============================================================
# 5. ACTIVE VESSEL MASTER VALIDATION
# ============================================================

def validate_vessel_master(vessels):

    section("ACTIVE VESSEL MASTER VALIDATION")

    df = vessels.copy()

    df["IMO_Normalised"] = clean_id(
        df["vesselIMONumber"]
    )

    df["Carrier_Code_Normalised"] = clean_id(
        df["carrierVesselCode"]
    )

    # Duplicate IMO groups
    imo_counts = (
        df.dropna(subset=["IMO_Normalised"])
        .groupby("IMO_Normalised")
        .agg(
            Record_Count=("IMO_Normalised", "size"),
            Vessel_Names=("vesselName", lambda x:
                          "; ".join(sorted(set(x.dropna().astype(str))))),
            Carrier_Codes=("carrierVesselCode", lambda x:
                           "; ".join(sorted(set(x.dropna().astype(str)))))
        )
        .reset_index()
    )

    duplicate_imo = imo_counts[
        imo_counts["Record_Count"] > 1
    ]

    print("Duplicate IMO groups:", len(duplicate_imo))

    # Carrier codes mapped to multiple IMOs
    carrier_mapping = (
        df.dropna(subset=["Carrier_Code_Normalised"])
        .groupby("Carrier_Code_Normalised")
        .agg(
            Record_Count=("Carrier_Code_Normalised", "size"),
            Unique_IMOs=("IMO_Normalised", "nunique"),
            IMOs=("IMO_Normalised", lambda x:
                  "; ".join(sorted(set(x.dropna().astype(str))))),
            Vessel_Names=("vesselName", lambda x:
                          "; ".join(sorted(set(x.dropna().astype(str)))))
        )
        .reset_index()
    )

    multiple_imo_codes = carrier_mapping[
        carrier_mapping["Unique_IMOs"] > 1
    ]

    print("Carrier codes mapped to multiple IMOs:",
          len(multiple_imo_codes))

    # Same IMO mapped to different names
    name_mapping = (
        df.dropna(subset=["IMO_Normalised"])
        .groupby("IMO_Normalised")
        .agg(
            Unique_Names=("vesselName", "nunique"),
            Names=("vesselName", lambda x:
                   "; ".join(sorted(set(x.dropna().astype(str)))))
        )
        .reset_index()
    )

    name_conflicts = name_mapping[
        name_mapping["Unique_Names"] > 1
    ]

    print("IMOs with multiple vessel names:", len(name_conflicts))

    save_table(
        duplicate_imo,
        "03_duplicate_vessel_imos.csv"
    )

    save_table(
        multiple_imo_codes,
        "03_carrier_code_multiple_imo.csv"
    )

    save_table(
        name_conflicts,
        "03_vessel_name_conflicts.csv"
    )


# ============================================================
# 6. ACTIVE PORT MASTER VALIDATION
# ============================================================

def validate_port_master(ports):

    section("ACTIVE PORT MASTER VALIDATION")

    df = ports.copy()

    df["LOCODE_Normalised"] = clean_id(
        df["UNLocationCode"]
    )

    port_counts = (
        df.dropna(subset=["LOCODE_Normalised"])
        .groupby("LOCODE_Normalised")
        .agg(
            Record_Count=("LOCODE_Normalised", "size"),
            Port_Names=("portName", lambda x:
                        "; ".join(sorted(set(x.dropna().astype(str))))),
            Countries=("countryCode", lambda x:
                       "; ".join(sorted(set(x.dropna().astype(str)))))
        )
        .reset_index()
    )

    duplicate_ports = port_counts[
        port_counts["Record_Count"] > 1
    ]

    print("Duplicate UN/LOCODE groups:", len(duplicate_ports))

    save_table(
        duplicate_ports,
        "03_duplicate_port_locodes.csv"
    )


# ============================================================
# 7. TRANSPORT CALL REFERENCE VALIDATION
# ============================================================

def validate_transport_calls(combined):

    section("TRANSPORT CALL REFERENCE VALIDATION")

    if combined.empty:
        print("No individual vessel records available.")
        return

    if "transportCallReference" not in combined.columns:
        print("transportCallReference column not found.")
        return

    references = clean_id(
        combined["transportCallReference"]
    )

    duplicate_mask = references.duplicated(keep=False)

    duplicate_rows = combined.loc[
        duplicate_mask
    ].copy()

    print("Total records:", len(combined))
    print("Missing references:", references.isna().sum())
    print("Unique references:", references.nunique(dropna=True))
    print("Rows with repeated references:", duplicate_mask.sum())

    save_table(
        duplicate_rows,
        "03_duplicate_transport_call_references.csv"
    )


# ============================================================
# 8. SCHEMA CONSISTENCY VALIDATION
# ============================================================

def validate_schema():

    section("VESSEL FILE SCHEMA VALIDATION")

    schemas = {}

    with zipfile.ZipFile(ZIP_PATH, "r") as archive:

        csv_files = [
            name for name in archive.namelist()
            if name.lower().endswith(".csv")
        ]

        for filename in csv_files:

            with archive.open(filename) as file:

                df = pd.read_csv(
                    io.BytesIO(file.read()),
                    encoding="utf-8-sig",
                    nrows=0
                )

            schemas[filename] = set(df.columns)

    if not schemas:
        print("No CSV schemas found.")
        return

    all_columns = set().union(*schemas.values())

    results = []

    for filename, columns in schemas.items():

        missing = sorted(all_columns - columns)

        results.append({
            "File": filename,
            "Column_Count": len(columns),
            "Missing_Columns": len(missing),
            "Missing_Column_Names": "; ".join(missing)
        })

    schema_df = pd.DataFrame(results)

    print("Total distinct columns:", len(all_columns))
    print(schema_df.to_string(index=False))

    save_table(
        schema_df,
        "03_schema_validation.csv"
    )


# ============================================================
# 9. CROSS-DATASET VESSEL MATCHING
# ============================================================

def validate_vessel_matching(
    schedules,
    vessels,
    combined
):

    section("CROSS-DATASET VESSEL MATCHING")

    schedule_imo = set(
        clean_id(schedules["IMO Number"]).dropna()
    )

    master_imo = set(
        clean_id(vessels["vesselIMONumber"]).dropna()
    )

    individual_imo = set()

    if not combined.empty and "vesselIMONumber" in combined.columns:

        individual_imo = set(
            clean_id(combined["vesselIMONumber"]).dropna()
        )

    comparisons = [
        {
            "Comparison": "Schedule vs Active Vessel Master",
            "Matching_IMOs": len(schedule_imo & master_imo),
            "Left_Only": len(schedule_imo - master_imo),
            "Right_Only": len(master_imo - schedule_imo)
        },
        {
            "Comparison": "Schedule vs Individual Vessel Files",
            "Matching_IMOs": len(schedule_imo & individual_imo),
            "Left_Only": len(schedule_imo - individual_imo),
            "Right_Only": len(individual_imo - schedule_imo)
        },
        {
            "Comparison": "Active Master vs Individual Vessel Files",
            "Matching_IMOs": len(master_imo & individual_imo),
            "Left_Only": len(master_imo - individual_imo),
            "Right_Only": len(individual_imo - master_imo)
        }
    ]

    comparison_df = pd.DataFrame(comparisons)

    print(comparison_df.to_string(index=False))

    save_table(
        comparison_df,
        "03_vessel_cross_dataset_matching.csv"
    )


# ============================================================
# 10. MAIN EXECUTION
# ============================================================

def main():

    section("STRAIT OF HORMUZ - IDENTIFIER VALIDATION")

    schedules, ports, vessels = load_datasets()

    filename_df, combined = validate_vessel_filenames()

    validate_vessel_master(vessels)

    validate_port_master(ports)

    validate_transport_calls(combined)

    validate_schema()

    validate_vessel_matching(
        schedules,
        vessels,
        combined
    )

    section("VALIDATION COMPLETED")

    print("All validation tables saved in:", TABLE_DIR)


# ============================================================
# 11. SAVE COMPLETE REPORT
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

    print("IDENTIFIER AND SCHEMA VALIDATION COMPLETED")
    print("\nReport saved at:")
    print(REPORT_PATH)