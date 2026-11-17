
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

FILE = (
    ROOT / "outputs" / "tables" /
    "08_negative_port_stay_investigation.csv"
)

df = pd.read_csv(FILE, low_memory=False)

print("\nNEGATIVE PORT-STAY RECORDS")
print("=" * 80)

if df.empty:
    print("No negative records found.")
else:
    estimated = df[
        df["Timestamp_Source"].astype(str).str.upper()
        == "ESTIMATED"
    ].copy()

    print(f"Total negative records: {len(df)}")
    print(f"Negative estimated records: {len(estimated)}")

    columns = [
        "Source_Dataset",
        "IMO_Normalised",
        "Vessel_Name",
        "Port_Name",
        "UNLOCODE",
        "Arrival_UTC",
        "Departure_UTC",
        "Port_Stay_Hours",
        "Service_Code",
        "Import_Voyage_Number",
        "Export_Voyage_Number",
        "Call_Reference",
        "Source_Row_ID"
    ]

    available = [
        col for col in columns
        if col in estimated.columns
    ]

    print("\nEstimated anomalies:\n")

    print(
        estimated[available].to_string(index=False)
    )

    output = (
        ROOT / "outputs" / "tables" /
        "08b_negative_estimated_records.csv"
    )

    estimated.to_csv(output, index=False)

    print(f"\nSaved: {output}")