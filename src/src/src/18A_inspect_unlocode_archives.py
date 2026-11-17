
from pathlib import Path
from zipfile import ZipFile
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

ZIP_FILES = {
    "PRODUCTION": ROOT / "data/raw/unlocode/artifacts.zip",
    "PRERELEASE": ROOT / "data/raw/unlocode/unlocode-latest.zip",
}

CSV_FILES = [
    "release/csv/UNLOCODE CodeListPart1.csv",
    "release/csv/UNLOCODE CodeListPart2.csv",
    "release/csv/UNLOCODE CodeListPart3.csv",
]

for dataset_name, zip_path in ZIP_FILES.items():

    print("\n" + "=" * 90)
    print(f"DATASET: {dataset_name}")
    print("=" * 90)

    with ZipFile(zip_path, "r") as archive:

        for csv_file in CSV_FILES:

            print("\n" + "-" * 90)
            print(f"FILE: {csv_file}")
            print("-" * 90)

            with archive.open(csv_file) as file:

                df = pd.read_csv(
                    file,
                    dtype=str,
                    encoding="utf-8-sig",
                    low_memory=False
                )

            print("Shape:", df.shape)

            print("\nColumns:")
            for column in df.columns:
                print(f"  - {column}")

            print("\nFirst 5 records:")
            print(df.head().to_string(index=False))

            # Identify columns potentially related to coordinates
            coordinate_columns = [
                col for col in df.columns
                if any(
                    term in col.lower()
                    for term in [
                        "coord",
                        "lat",
                        "long",
                        "location",
                        "code"
                    ]
                )
            ]

            print("\nPotentially relevant columns:")
            print(coordinate_columns)

print("\n" + "=" * 90)
print("UN/LOCODE ARCHIVE INSPECTION COMPLETED")
print("=" * 90)
