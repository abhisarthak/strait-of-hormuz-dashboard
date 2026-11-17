
from pathlib import Path
import pandas as pd

# ============================================================
# SCRIPT 08C: INSPECT ORIGINAL ANOMALY SOURCE RECORDS
# ============================================================

ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / "data" / "processed"
OUTPUT_DIR = ROOT / "outputs" / "tables"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FILES = {
    "INDIVIDUAL": DATA_DIR / "06_individual_vessel_port_calls.csv",
    "SCHEDULE": DATA_DIR / "06_integrated_schedule_vessel_port.csv"
}

TARGET_IMOS = ["9416006", "9289192"]


def normalize_imo(series):
    return (
        series.astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )


all_results = []

for dataset_name, file_path in FILES.items():

    print("\n" + "=" * 90)
    print(dataset_name)
    print("=" * 90)

    df = pd.read_csv(file_path, low_memory=False)

    imo_col = "IMO_Normalised"

    df[imo_col] = normalize_imo(df[imo_col])

    filtered = df[
        df[imo_col].isin(TARGET_IMOS)
    ].copy()

    if dataset_name == "INDIVIDUAL":

        columns = [
            "source_file",
            "IMO_Normalised",
            "vesselName",
            "portName",
            "UNLocationCode",
            "carrierServiceCode",
            "carrierImportVoyageNumber",
            "carrierExportVoyageNumber",
            "ARRI_PLN",
            "ARRI_EST",
            "ARRI_ACT",
            "DEPA_PLN",
            "DEPA_EST",
            "DEPA_ACT",
            "transportCallReference",
            "Individual_Source_File"
        ]

    else:

        columns = [
            "Source_Port",
            "Source_Row_ID",
            "IMO_Normalised",
            "Vessel Name",
            "Port",
            "UN Location Code",
            "Carrier Service Code",
            "Import Voyage Number",
            "Export Voyage Number",
            "Planned Arrival",
            "Estimated Arrival",
            "Actual Arrival",
            "Planned Departure",
            "Estimated Departure",
            "Actual Departure",
            "Vessel_Match_Status",
            "Port_Match_Status"
        ]

    available = [
        col for col in columns
        if col in filtered.columns
    ]

    print("Matching records:", len(filtered))

    if filtered.empty:
        print("No matching records found.")
        continue

    print(
        filtered[available].to_string(index=False)
    )

    filtered["Inspection_Dataset"] = dataset_name
    all_results.append(filtered)

    output_file = (
        OUTPUT_DIR /
        f"08c_{dataset_name.lower()}_anomaly_source_records.csv"
    )

    filtered.to_csv(output_file, index=False)

    print("\nSaved:", output_file)


# ============================================================
# COMBINED INVESTIGATION FILE
# ============================================================

if all_results:

    combined = pd.concat(
        all_results,
        ignore_index=True,
        sort=False
    )

    combined_file = (
        OUTPUT_DIR /
        "08c_combined_anomaly_source_records.csv"
    )

    combined.to_csv(combined_file, index=False)

    print("\n" + "=" * 90)
    print("INSPECTION COMPLETED")
    print("=" * 90)

    print("Combined records:", len(combined))
    print("Combined file:", combined_file)

else:
    print("\nNo matching records were found.")