
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

file_path = (
    ROOT / "data" / "processed"
    / "06_integrated_schedule_vessel_port.csv"
)

df = pd.read_csv(file_path, low_memory=False)

print("\nINTEGRATED DATASET: PORT-RELATED COLUMNS")
print("=" * 75)

port_columns = [
    col for col in df.columns
    if "port" in col.lower()
    or "facility" in col.lower()
    or "smdg" in col.lower()
]

print(port_columns)

print("\nSAMPLE RECORDS")
print("=" * 75)

sample = df[
    df["IMO Number"].astype("string").str.replace(
        r"\.0$", "", regex=True
    ).eq("9235531")
]

for col in port_columns:
    print(f"\n{col}")
    print(sample[col].to_string(index=False))

print("\nINSPECTION COMPLETED")
