
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

FILE = (
    ROOT / "outputs" / "tables"
    / "12_source_field_comparison.csv"
)

df = pd.read_csv(FILE, low_memory=False)

mismatches = df[
    df["Match_Status"] == "MISMATCH"
].copy()

print("\n" + "=" * 80)
print("SCRIPT 12A: SOURCE MISMATCH DIAGNOSTIC")
print("=" * 80)

print("\nTOTAL MISMATCHES:", len(mismatches))

print("\nMISMATCHES BY FIELD")
print(
    mismatches["Field"]
    .value_counts(dropna=False)
    .to_string()
)

print("\nDETAILED MISMATCH RECORDS")

columns = [
    "Candidate_Group_ID",
    "Source_Row_Number",
    "Field",
    "Original_Value",
    "Candidate_Value",
    "Original_Normalized",
    "Candidate_Normalized",
]

print(
    mismatches[columns]
    .to_string(index=False)
)

print("\nMISMATCHES BY GROUP")
print(
    mismatches.groupby("Candidate_Group_ID")
    .size()
    .to_string()
)

print("\nDIAGNOSTIC COMPLETED")
