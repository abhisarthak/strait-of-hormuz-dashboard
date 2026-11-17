
from pathlib import Path
import pandas as pd
import re

ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = ROOT / "data" / "raw" / "active_vessels.csv"
OUTPUT_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(INPUT_FILE)

# Standardize column names
df.columns = df.columns.str.strip()

# Normalize IMO
df["IMO_Normalised"] = (
    df["vesselIMONumber"]
    .astype("string")
    .str.strip()
)

# Normalize vessel names:
# 1. Remove leading/trailing spaces
# 2. Convert repeated whitespace to one space
# 3. Convert to uppercase
df["Vessel_Name_Normalised"] = (
    df["vesselName"]
    .astype("string")
    .str.strip()
    .str.replace(r"\s+", " ", regex=True)
    .str.upper()
)

# Exclude missing identifiers and names
valid = df.dropna(
    subset=["IMO_Normalised", "Vessel_Name_Normalised"]
).copy()

# Count distinct normalized names per IMO
summary = (
    valid.groupby("IMO_Normalised")
    ["Vessel_Name_Normalised"]
    .nunique()
    .reset_index(name="Unique_Normalised_Names")
)

# Retain only genuine normalized name conflicts
conflict_imos = summary[
    summary["Unique_Normalised_Names"] > 1
]

# Get original names for investigation
details = (
    valid.merge(
        conflict_imos[["IMO_Normalised"]],
        on="IMO_Normalised",
        how="inner"
    )
    .groupby("IMO_Normalised")
    .agg(
        Unique_Original_Names=("vesselName", "nunique"),
        Normalised_Names=(
            "Vessel_Name_Normalised",
            lambda x: "; ".join(sorted(set(x)))
        ),
        Original_Names=(
            "vesselName",
            lambda x: "; ".join(
                sorted(set(x.dropna().astype(str)))
            )
        )
    )
    .reset_index()
)

# Save outputs
summary.to_csv(
    OUTPUT_DIR / "05_vessel_name_normalization_summary.csv",
    index=False
)

details.to_csv(
    OUTPUT_DIR / "05_genuine_vessel_name_conflicts.csv",
    index=False
)

report = [
    "VESSEL NAME NORMALIZATION VALIDATION",
    "=" * 60,
    f"Total active vessel records: {len(df)}",
    f"Unique IMO values: {valid['IMO_Normalised'].nunique()}",
    f"IMOs with multiple normalized names: {len(conflict_imos)}",
    "",
    "Genuine potential name conflicts:"
]

if details.empty:
    report.append("None detected.")
else:
    report.append(details.to_string(index=False))

report_text = "\n".join(report)

with open(
    REPORT_DIR / "05_vessel_name_normalization_report.txt",
    "w",
    encoding="utf-8"
) as f:
    f.write(report_text)

print(report_text)
print("\nFiles saved successfully.")
