
from pathlib import Path
import pandas as pd

# ============================================================
# 1. PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    ROOT
    / "data"
    / "processed"
    / "06_integrated_schedule_vessel_port.csv"
)

OUTPUT_DIR = ROOT / "outputs" / "tables"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. TARGET VESSELS
# ============================================================

TARGET_IMOS = [
    "9235531",
    "9263320",
    "9332975",
    "9202259",
    "9235567",
]


# ============================================================
# 3. LOAD DATA
# ============================================================

df = pd.read_csv(INPUT_FILE, low_memory=False)

df.insert(
    0,
    "Source_Row_Number",
    range(1, len(df) + 1)
)


# ============================================================
# 4. NORMALIZE IMO
# ============================================================

def normalize_imo(series):

    result = (
        series.astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )

    return result.str.replace(r"\.0$", "", regex=True)


imo_col = "IMO Number"

if imo_col not in df.columns:
    raise ValueError(
        f"Expected column '{imo_col}' not found. "
        f"Available columns: {list(df.columns)}"
    )

df["Analysis_IMO"] = normalize_imo(df[imo_col])


# ============================================================
# 5. SELECT TARGET RECORDS
# ============================================================

target_df = df[
    df["Analysis_IMO"].isin(TARGET_IMOS)
].copy()

print("\n" + "=" * 80)
print("OVERLAP SOURCE RECORD INVESTIGATION")
print("=" * 80)

print("Total schedule records:", len(df))
print("Target vessel records:", len(target_df))

print("\nRECORD COUNT BY IMO")

print(
    target_df.groupby("Analysis_IMO")
    .size()
    .to_string()
)


# ============================================================
# 6. SELECT RELEVANT ORIGINAL COLUMNS
# ============================================================

preferred_columns = [
    "Source_Row_Number",
    "Analysis_IMO",
    "Vessel Name",
    "vesselName",
    "portName",
    "UNLocationCode",
    "Country",
    "Source Port",
    "Carrier Service Code",
    "Import Voyage Number",
    "Export Voyage Number",
    "Planned Arrival",
    "Estimated Arrival",
    "Actual Arrival",
    "Planned Departure",
    "Estimated Departure",
    "Actual Departure",
    "Dummy Vessel",
]

available_columns = [
    col for col in preferred_columns
    if col in target_df.columns
]

# Retain every original field in the CSV export.
target_df.to_csv(
    OUTPUT_DIR / "09c_target_vessel_all_source_records.csv",
    index=False
)


# ============================================================
# 7. PRINT COMPLETE SOURCE RECORDS
# ============================================================

for imo in TARGET_IMOS:

    vessel_df = target_df[
        target_df["Analysis_IMO"] == imo
    ].copy()

    print("\n" + "=" * 80)
    print(f"IMO: {imo}")
    print("=" * 80)

    print("Number of source records:", len(vessel_df))

    if vessel_df.empty:
        print("No records found.")
        continue

    display_columns = [
        col for col in available_columns
        if col != "Analysis_IMO"
    ]

    print(
        vessel_df[display_columns]
        .to_string(index=False)
    )


# ============================================================
# 8. IDENTIFY EXACT DUPLICATE CANDIDATES
# ============================================================

timestamp_columns = [
    "Planned Arrival",
    "Estimated Arrival",
    "Actual Arrival",
    "Planned Departure",
    "Estimated Departure",
    "Actual Departure",
]

voyage_columns = [
    "Import Voyage Number",
    "Export Voyage Number",
]

identity_columns = [
    "Analysis_IMO",
    "portName",
    "UNLocationCode",
] + voyage_columns + timestamp_columns

identity_columns = [
    col for col in identity_columns
    if col in target_df.columns
]

# Candidate groups share IMO, port, voyage identifiers,
# and every available timestamp field.
duplicate_candidates = target_df[
    target_df.duplicated(
        subset=identity_columns,
        keep=False
    )
].copy()

duplicate_candidates = duplicate_candidates.sort_values(
    ["Analysis_IMO", "Source_Row_Number"]
)

duplicate_candidates.to_csv(
    OUTPUT_DIR / "09c_exact_overlap_candidate_records.csv",
    index=False
)

print("\n" + "=" * 80)
print("EXACT OVERLAP CANDIDATES")
print("=" * 80)

print("Candidate records:", len(duplicate_candidates))

if not duplicate_candidates.empty:

    print(
        duplicate_candidates[
            available_columns
        ].to_string(index=False)
    )

else:
    print("No exact matching groups found.")


# ============================================================
# 9. SUMMARY BY VESSEL, PORT AND SERVICE
# ============================================================

summary_columns = [
    "Analysis_IMO",
    "portName",
    "UNLocationCode",
    "Carrier Service Code",
    "Import Voyage Number",
    "Export Voyage Number",
]

summary_columns = [
    col for col in summary_columns
    if col in target_df.columns
]

summary = (
    target_df.groupby(
        summary_columns,
        dropna=False
    )
    .agg(
        Record_Count=("Source_Row_Number", "size"),
        Source_Row_Numbers=(
            "Source_Row_Number",
            lambda x: ", ".join(map(str, x))
        )
    )
    .reset_index()
)

summary.to_csv(
    OUTPUT_DIR / "09c_vessel_port_service_summary.csv",
    index=False
)

print("\n" + "=" * 80)
print("VESSEL / PORT / SERVICE SUMMARY")
print("=" * 80)

print(summary.to_string(index=False))


# ============================================================
# 10. FINAL
# ============================================================

print("\n" + "=" * 80)
print("SCRIPT 09C COMPLETED")
print("=" * 80)

print("\nSaved files:")

print(
    OUTPUT_DIR
    / "09c_target_vessel_all_source_records.csv"
)

print(
    OUTPUT_DIR
    / "09c_exact_overlap_candidate_records.csv"
)

print(
    OUTPUT_DIR
    / "09c_vessel_port_service_summary.csv"
)

print("\nNo original records were modified or deleted.")
