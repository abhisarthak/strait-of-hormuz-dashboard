
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile
import re

import pandas as pd


# ============================================================
# 1. PROJECT PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent.parent

RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
TABLE_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

for folder in [PROCESSED_DIR, TABLE_DIR, REPORT_DIR]:
    folder.mkdir(parents=True, exist_ok=True)


SCHEDULE_FILE = RAW_DIR / "Combined_Port_Schedules.xlsx"
VESSEL_FILE = RAW_DIR / "active_vessels.csv"
PORT_FILE = RAW_DIR / "active_ports.csv"

ZIP_FILES = list(RAW_DIR.glob("individual_vessels*.zip"))


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def normalize_column_name(name):
    """Make column names comparable, regardless of spaces/case."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def normalize_identifier(series):
    """Normalize text identifiers such as UN/LOCODE."""
    return (
        series.astype("string")
        .str.strip()
        .replace("", pd.NA)
        .str.upper()
    )


def normalize_imo(series):
    """Normalize IMO values across datasets."""
    result = (
        series.astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )

    # Remove trailing .0 caused by numeric CSV/Excel conversion.
    result = result.str.replace(r"\.0$", "", regex=True)

    return result


def normalize_name(series):
    """Normalize names for comparison, retaining original names."""
    return (
        series.astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.upper()
        .replace("", pd.NA)
    )


def find_column(df, possible_names, dataset_name):
    """
    Find a column using case-insensitive, punctuation-insensitive
    matching. Raise a useful error if no match is found.
    """
    available = {
        normalize_column_name(col): col
        for col in df.columns
    }

    for candidate in possible_names:
        key = normalize_column_name(candidate)
        if key in available:
            return available[key]

    raise ValueError(
        f"Could not find the required column in {dataset_name}.\n"
        f"Expected one of: {possible_names}\n"
        f"Available columns: {df.columns.tolist()}"
    )


def unique_values(series):
    """Return distinct non-empty values as a readable string."""
    values = (
        series.dropna()
        .astype(str)
        .str.strip()
    )
    values = sorted(set(v for v in values if v))

    return " | ".join(values) if values else pd.NA


def save_csv(df, filename, folder=PROCESSED_DIR):
    path = folder / filename
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"Saved: {path.relative_to(ROOT)}")


# ============================================================
# 3. LOAD RAW DATASETS
# ============================================================

print("\n" + "=" * 65)
print("STRAIT OF HORMUZ - DATASET INTEGRATION")
print("=" * 65)

for file in [SCHEDULE_FILE, VESSEL_FILE, PORT_FILE]:
    if not file.exists():
        raise FileNotFoundError(f"Missing input file: {file}")

if not ZIP_FILES:
    raise FileNotFoundError(
        "No individual_vessels*.zip file found in data/raw/"
    )

schedules = pd.read_excel(SCHEDULE_FILE)
vessels = pd.read_csv(VESSEL_FILE)
ports = pd.read_csv(PORT_FILE)

print("\nRAW DATASET DIMENSIONS")
print("-" * 65)
print(f"Combined schedules: {schedules.shape}")
print(f"Active vessels:     {vessels.shape}")
print(f"Active ports:       {ports.shape}")


# ============================================================
# 4. IDENTIFY IMPORTANT COLUMNS
# ============================================================

schedule_imo_col = find_column(
    schedules,
    ["IMO number", "IMO Number", "vessel IMO", "vesselIMONumber"],
    "Combined schedules"
)

schedule_locode_col = find_column(
    schedules,
    ["UN Location Code", "UN/LOCODE", "UNLOCODE"],
    "Combined schedules"
)

vessel_imo_col = find_column(
    vessels,
    ["vesselIMONumber", "IMO number", "IMO"],
    "Active vessels"
)

vessel_name_col = find_column(
    vessels,
    ["vesselName", "Vessel Name"],
    "Active vessels"
)

port_locode_col = find_column(
    ports,
    ["UNLocationCode", "UN Location Code", "UNLOCODE"],
    "Active ports"
)


# ============================================================
# 5. CREATE NORMALIZED IDENTIFIERS
# ============================================================

schedules = schedules.copy()
vessels = vessels.copy()
ports = ports.copy()

# Preserve original source row numbers.
schedules["Schedule_Source_Row"] = range(1, len(schedules) + 1)
vessels["Vessel_Master_Source_Row"] = range(1, len(vessels) + 1)
ports["Port_Master_Source_Row"] = range(1, len(ports) + 1)

# Normalize IMO identifiers.
schedules["IMO_Normalised"] = normalize_imo(
    schedules[schedule_imo_col]
)

vessels["IMO_Normalised"] = normalize_imo(
    vessels[vessel_imo_col]
)

# Normalize port identifiers.
schedules["UNLOCODE_Normalised"] = normalize_identifier(
    schedules[schedule_locode_col]
)

ports["UNLOCODE_Normalised"] = normalize_identifier(
    ports[port_locode_col]
)

# Normalize vessel names.
vessels["Vessel_Name_Normalised"] = normalize_name(
    vessels[vessel_name_col]
)

print("\nIMO NORMALIZATION VALIDATION")
print("-" * 60)

print("Schedule:", schedules["IMO_Normalised"].dropna().head(5).tolist())
print("Vessels:", vessels["IMO_Normalised"].dropna().head(5).tolist())

assert not schedules["IMO_Normalised"].dropna().str.endswith(".0").any()
assert not vessels["IMO_Normalised"].dropna().str.endswith(".0").any()

print("IMO normalization passed.")


# ============================================================
# 6. BUILD ONE-ROW-PER-IMO VESSEL LOOKUP
# ============================================================

print("\n" + "=" * 65)
print("VESSEL MASTER INTEGRATION")
print("=" * 65)

valid_vessels = vessels.dropna(
    subset=["IMO_Normalised"]
).copy()

# Aggregate repeated master records by IMO.
# This prevents a schedule row from multiplying during the merge.

aggregation = {
    col: unique_values
    for col in vessels.columns
    if col not in [
        "IMO_Normalised",
        "Vessel_Master_Source_Row",
        vessel_imo_col,
    ]
}

vessel_lookup = (
    valid_vessels
    .groupby("IMO_Normalised", as_index=False)
    .agg(
        **{
            "Vessel_Master_Record_Count": (
                "Vessel_Master_Source_Row", "count"
            ),
            **{
                col: (col, func)
                for col, func in aggregation.items()
            }
        }
    )
)

# Rename aggregated fields to avoid confusion with schedule fields.
rename_vessel_columns = {}

for col in vessel_lookup.columns:
    if col not in [
        "IMO_Normalised",
        "Vessel_Master_Record_Count",
    ]:
        rename_vessel_columns[col] = f"Master_{col}"

vessel_lookup = vessel_lookup.rename(
    columns=rename_vessel_columns
)

save_csv(
    vessel_lookup,
    "06_vessel_master_by_imo.csv"
)

print(f"Vessel master rows: {len(vessels)}")
print(f"Rows with valid IMO: {len(valid_vessels)}")
print(f"Unique IMO lookup rows: {len(vessel_lookup)}")


# ============================================================
# 7. BUILD PORT LOOKUPS
# ============================================================

print("\n" + "=" * 65)
print("PORT MASTER INTEGRATION")
print("=" * 65)

valid_ports = ports.dropna(
    subset=["UNLOCODE_Normalised"]
).copy()

locode_counts = (
    valid_ports.groupby("UNLOCODE_Normalised")
    .size()
    .rename("Port_Master_Record_Count")
    .reset_index()
)

unique_locodes = locode_counts[
    locode_counts["Port_Master_Record_Count"] == 1
]["UNLOCODE_Normalised"]

ambiguous_locodes = locode_counts[
    locode_counts["Port_Master_Record_Count"] > 1
]["UNLOCODE_Normalised"]

# Only unique LOCODEs can be safely joined automatically.
unique_port_lookup = valid_ports[
    valid_ports["UNLOCODE_Normalised"].isin(unique_locodes)
].copy()

# Preserve ambiguous port candidates separately.
ambiguous_port_candidates = valid_ports[
    valid_ports["UNLOCODE_Normalised"].isin(ambiguous_locodes)
].copy()

# Remove the internal source row number from the lookup merge.
port_lookup_columns = [
    col for col in unique_port_lookup.columns
    if col != "Port_Master_Source_Row"
]

unique_port_lookup = unique_port_lookup[
    port_lookup_columns
]

save_csv(
    unique_port_lookup,
    "06_unique_port_lookup.csv"
)

save_csv(
    ambiguous_port_candidates,
    "06_ambiguous_port_candidates.csv"
)

save_csv(
    locode_counts,
    "06_port_locode_frequency.csv",
    TABLE_DIR
)

print(f"Unique LOCODEs: {len(unique_locodes)}")
print(f"Ambiguous LOCODEs: {len(ambiguous_locodes)}")


# ============================================================
# 8. INTEGRATE COMBINED SCHEDULES WITH VESSEL MASTER
# ============================================================

print("\n" + "=" * 65)
print("SCHEDULE + VESSEL MASTER MERGE")
print("=" * 65)

integrated = schedules.merge(
    vessel_lookup,
    on="IMO_Normalised",
    how="left",
    validate="many_to_one",
    indicator="Vessel_Merge_Result"
)

integrated["Vessel_Match_Status"] = (
    integrated["Vessel_Merge_Result"]
    .map({
        "both": "MATCHED",
        "left_only": "NO_VESSEL_MASTER_MATCH"
    })
)

integrated = integrated.drop(
    columns=["Vessel_Merge_Result"]
)

vessel_match_counts = (
    integrated["Vessel_Match_Status"]
    .value_counts(dropna=False)
)

print("\nVessel match results:")
print(vessel_match_counts)


# ============================================================
# 9. INTEGRATE PORT MASTER
# ============================================================

print("\n" + "=" * 65)
print("SCHEDULE + PORT MASTER MERGE")
print("=" * 65)

integrated = integrated.merge(
    unique_port_lookup,
    on="UNLOCODE_Normalised",
    how="left",
    validate="many_to_one",
    suffixes=("", "_PortMaster")
)

ambiguous_code_set = set(ambiguous_locodes)

integrated["Port_Match_Status"] = "NO_PORT_MASTER_MATCH"

integrated.loc[
    integrated["UNLOCODE_Normalised"].isin(unique_locodes),
    "Port_Match_Status"
] = "MATCHED"

integrated.loc[
    integrated["UNLOCODE_Normalised"].isin(ambiguous_code_set),
    "Port_Match_Status"
] = "AMBIGUOUS_PORT_MATCH"

integrated.loc[
    integrated["UNLOCODE_Normalised"].isna(),
    "Port_Match_Status"
] = "MISSING_SCHEDULE_UNLOCODE"

print("\nPort match results:")
print(
    integrated["Port_Match_Status"]
    .value_counts(dropna=False)
)


# ============================================================
# 10. SAVE INTEGRATED SCHEDULE DATASET
# ============================================================

save_csv(
    integrated,
    "06_integrated_schedule_vessel_port.csv"
)

print("\nIntegrated schedule dimensions:", integrated.shape)


# ============================================================
# 11. LOAD AND STANDARDIZE INDIVIDUAL VESSEL FILES
# ============================================================

print("\n" + "=" * 65)
print("INDIVIDUAL VESSEL PORT-CALL DATA")
print("=" * 65)

individual_frames = []

for zip_path in ZIP_FILES:

    print(f"Reading ZIP: {zip_path.name}")

    with ZipFile(zip_path, "r") as archive:

        csv_files = [
            name for name in archive.namelist()
            if name.lower().endswith(".csv")
            and not name.startswith("__MACOSX/")
        ]

        for csv_name in csv_files:

            with archive.open(csv_name) as file:
                individual_df = pd.read_csv(file)

            individual_df.columns = (
                individual_df.columns.astype(str).str.strip()
            )

            individual_df["Individual_Source_File"] = csv_name

            individual_frames.append(individual_df)


if individual_frames:

    individual_calls = pd.concat(
        individual_frames,
        ignore_index=True,
        sort=False
    )

else:
    individual_calls = pd.DataFrame()


# Standardize identifiers where available.
if not individual_calls.empty:

    individual_imo_col = find_column(
        individual_calls,
        [
            "vesselIMO",
            "vesselIMONumber",
            "IMO",
            "IMO number",
        ],
        "Individual vessel files"
    )

    individual_calls["IMO_Normalised"] = normalize_identifier(
        individual_calls[individual_imo_col]
    )

    # Standardize UN/LOCODE if present.
    try:
        individual_locode_col = find_column(
            individual_calls,
            [
                "UNLocationCode",
                "UN Location Code",
                "UNLOCODE",
            ],
            "Individual vessel files"
        )

        individual_calls["UNLOCODE_Normalised"] = (
            normalize_identifier(
                individual_calls[individual_locode_col]
            )
        )

    except ValueError:
        individual_locode_col = None
        individual_calls["UNLOCODE_Normalised"] = pd.NA

    # Keep call references as strings where present.
    try:
        call_reference_col = find_column(
            individual_calls,
            [
                "transportCallReference",
                "transportCallRef",
            ],
            "Individual vessel files"
        )

        individual_calls["Transport_Call_Reference_Normalised"] = (
            individual_calls[call_reference_col]
            .astype("string")
            .str.strip()
        )

    except ValueError:
        call_reference_col = None
        individual_calls["Transport_Call_Reference_Normalised"] = pd.NA

    save_csv(
        individual_calls,
        "06_individual_vessel_port_calls.csv"
    )

    print(
        "Individual port-call records:",
        len(individual_calls)
    )

    print(
        "Unique individual-file IMOs:",
        individual_calls["IMO_Normalised"].nunique()
    )

    print(
        "Unique individual call references:",
        individual_calls[
            "Transport_Call_Reference_Normalised"
        ].nunique()
    )

else:
    print("No individual vessel records found.")

print("\nIMO NORMALIZATION CHECK")
print("-" * 65)

print("Schedule IMO sample:")
print(schedules["IMO_Normalised"].dropna().head(10).tolist())

print("\nVessel master IMO sample:")
print(vessels["IMO_Normalised"].dropna().head(10).tolist())

print("\nIndividual IMO sample:")
print(individual_calls["IMO_Normalised"].dropna().head(10).tolist())

print("\nIndividual IMO data types:")
print(individual_calls["IMO_Normalised"].dtype)

print("\nSchedule IMO data types:")
print(schedules["IMO_Normalised"].dtype)


# ============================================================
# 12. CROSS-DATASET IMO MATCHING SUMMARY
# ============================================================

print("\n" + "=" * 65)
print("CROSS-DATASET IMO MATCHING")
print("=" * 65)

schedule_imos = set(
    schedules["IMO_Normalised"].dropna().unique()
)

master_imos = set(
    vessels["IMO_Normalised"].dropna().unique()
)

if not individual_calls.empty:
    individual_imos = set(
        individual_calls["IMO_Normalised"].dropna().unique()
    )
else:
    individual_imos = set()


comparison_pairs = [
    (
        "Schedule vs Vessel Master",
        schedule_imos,
        master_imos
    ),
    (
        "Schedule vs Individual Files",
        schedule_imos,
        individual_imos
    ),
    (
        "Vessel Master vs Individual Files",
        master_imos,
        individual_imos
    ),
]

comparison_results = []

for name, left, right in comparison_pairs:

    matching = left.intersection(right)

    comparison_results.append({
        "Comparison": name,
        "Left_Unique_IMOs": len(left),
        "Right_Unique_IMOs": len(right),
        "Matching_IMOs": len(matching),
        "Left_Only_IMOs": len(left - right),
        "Right_Only_IMOs": len(right - left),
    })

comparison_df = pd.DataFrame(comparison_results)

save_csv(
    comparison_df,
    "06_cross_dataset_imo_matching.csv",
    TABLE_DIR
)

print(comparison_df.to_string(index=False))


# ============================================================
# 13. INTEGRATION QUALITY REPORT
# ============================================================

report = []

report.append("=" * 70)
report.append("STRAIT OF HORMUZ - DATASET INTEGRATION REPORT")
report.append("=" * 70)

report.append("\n1. RAW DATASET DIMENSIONS")
report.append(f"Combined schedules: {schedules.shape}")
report.append(f"Active vessels: {vessels.shape}")
report.append(f"Active ports: {ports.shape}")

report.append("\n2. VESSEL MASTER")
report.append(f"Total vessel master records: {len(vessels)}")
report.append(f"Valid IMO records: {len(valid_vessels)}")
report.append(f"Unique IMO lookup records: {len(vessel_lookup)}")

report.append("\n3. PORT MASTER")
report.append(f"Total port master records: {len(ports)}")
report.append(f"Unique LOCODEs: {len(unique_locodes)}")
report.append(f"Ambiguous LOCODEs: {len(ambiguous_locodes)}")

report.append("\n4. INTEGRATED SCHEDULE")
report.append(f"Integrated schedule rows: {len(integrated)}")
report.append(f"Integrated schedule columns: {len(integrated.columns)}")

report.append("\nVessel match status:")
report.append(
    integrated["Vessel_Match_Status"]
    .value_counts(dropna=False)
    .to_string()
)

report.append("\nPort match status:")
report.append(
    integrated["Port_Match_Status"]
    .value_counts(dropna=False)
    .to_string()
)

report.append("\n5. CROSS-DATASET IMO MATCHING")
report.append(comparison_df.to_string(index=False))

report.append("\n6. DATA HANDLING DECISIONS")
report.append(
    "- Original raw datasets were not modified."
)
report.append(
    "- Original source columns were retained."
)
report.append(
    "- Normalized identifiers were added as separate columns."
)
report.append(
    "- Repeated vessel master IMO records were aggregated for joining."
)
report.append(
    "- Ambiguous port LOCODEs were not automatically matched."
)
report.append(
    "- Individual vessel port-call records were kept separate."
)
report.append(
    "- Planned, estimated and actual timestamps were not overwritten."
)
report.append(
    "- No actual vessel route through the Strait of Hormuz is inferred."
)

report_text = "\n".join(report)

report_path = REPORT_DIR / "06_dataset_integration_report.txt"

with open(report_path, "w", encoding="utf-8") as file:
    file.write(report_text)

print("\n" + "=" * 70)
print(report_text)
print("\nIntegration files saved successfully.")