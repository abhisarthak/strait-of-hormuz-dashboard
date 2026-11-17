
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

FILE = (
    ROOT
    / "outputs"
    / "tables"
    / "09_vessel_port_stay_overlaps.csv"
)

df = pd.read_csv(FILE)

if df.empty:
    print("No overlap records found.")
else:
    print("\nTOTAL OVERLAP RECORDS:", len(df))

    print("\nOVERLAPS BY DATASET AND TIMESTAMP SOURCE")
    print(
        df.groupby(
            ["Dataset", "Timestamp_Source", "Overlap_Type"]
        ).size().to_string()
    )

    columns = [
        "Dataset",
        "Timestamp_Source",
        "IMO",
        "First_Port",
        "Second_Port",
        "First_LOCODE",
        "Second_LOCODE",
        "First_Arrival_UTC",
        "First_Departure_UTC",
        "Second_Arrival_UTC",
        "Second_Departure_UTC",
        "Overlap_Hours",
        "Overlap_Type",
        "First_Service",
        "Second_Service",
        "First_Import_Voyage",
        "Second_Import_Voyage",
        "First_Export_Voyage",
        "Second_Export_Voyage",
    ]

    columns = [c for c in columns if c in df.columns]

    print("\nDETAILED OVERLAP RECORDS")

    for index, row in df.iterrows():
        print("\n" + "=" * 75)
        print(f"OVERLAP {index + 1}")
        print("=" * 75)

        for col in columns:
            print(f"{col:35s}: {row[col]}")

    print("\nINSPECTION COMPLETED")
