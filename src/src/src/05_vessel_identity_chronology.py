
from pathlib import Path
from zipfile import ZipFile
import pandas as pd
import numpy as np

# ============================================================
# SCRIPT 05: VESSEL IDENTITY AND CHRONOLOGICAL INVESTIGATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ZIP_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "individual_vessels-20261112T213245Z-1-001.zip"
)

ACTIVE_VESSELS_PATH = (
    PROJECT_ROOT / "data" / "raw" / "active_vessels.csv"
)

OUTPUT_TABLES = PROJECT_ROOT / "outputs" / "tables"
OUTPUT_REPORTS = PROJECT_ROOT / "outputs" / "reports"

OUTPUT_TABLES.mkdir(parents=True, exist_ok=True)
OUTPUT_REPORTS.mkdir(parents=True, exist_ok=True)

# Six files identified in Script 04
AFFECTED_FILES = [
    "individual_vessels/9307011.csv",
    "individual_vessels/9315020.csv",
    "individual_vessels/9306079.csv",
    "individual_vessels/9732307.csv",
    "individual_vessels/9948803.csv",
    "individual_vessels/9634672.csv",
]

ARRIVAL_COLUMNS = ["ARRI_ACT", "ARRI_EST", "ARRI_PLN"]
DEPARTURE_COLUMNS = ["DEPA_ACT", "DEPA_EST", "DEPA_PLN"]

TIMESTAMP_COLUMNS = ARRIVAL_COLUMNS + DEPARTURE_COLUMNS


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def find_column(df, possible_names):
    """Find a column using case-insensitive matching."""
    lookup = {str(col).strip().lower(): col for col in df.columns}

    for name in possible_names:
        if name.lower() in lookup:
            return lookup[name.lower()]

    return None


def clean_imo(series):
    """Normalize IMO values without converting missing values to strings."""
    return (
        series.astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )


def parse_timestamp(series):
    """
    Parse timestamps into UTC for comparison.
    Original timestamp strings remain preserved in the raw columns.
    Naive timestamps are interpreted as UTC by pandas here.
    Their actual source timezone has not yet been verified.
    """
    return pd.to_datetime(series, errors="coerce", utc=True)


def read_csv_from_zip(zip_file, filename):
    """Read a CSV from the ZIP, trying common encodings."""
    for encoding in ["utf-8", "utf-8-sig", "cp1252", "latin1"]:
        try:
            with zip_file.open(filename) as file:
                return pd.read_csv(file, encoding=encoding)
        except UnicodeDecodeError:
            continue

    raise ValueError(f"Could not decode {filename}")


def first_existing_value(row, columns):
    """Return the first non-null value from a list of columns."""
    for col in columns:
        if col in row.index and pd.notna(row[col]):
            return row[col], col

    return pd.NaT, None


# ============================================================
# 1. LOAD ACTIVE VESSEL MASTER
# ============================================================

print("\n" + "=" * 70)
print("SCRIPT 05: VESSEL IDENTITY AND CHRONOLOGY INVESTIGATION")
print("=" * 70)

active_vessels = pd.read_csv(ACTIVE_VESSELS_PATH, dtype="string")

master_imo_col = find_column(
    active_vessels,
    ["vesselIMONumber", "imo", "vesselIMO", "vessel_imo", "imoNumber"]
)

master_name_col = find_column(
    active_vessels,
    ["vesselName", "vessel_name", "name", "shipName"]
)

if master_imo_col is None:
    raise ValueError(
        "Could not identify IMO column in active_vessels.csv. "
        f"Available columns: {list(active_vessels.columns)}"
    )

active_vessels["_IMO_KEY"] = clean_imo(active_vessels[master_imo_col])

if master_name_col:
    active_vessels["_MASTER_VESSEL_NAME"] = (
        active_vessels[master_name_col].astype("string").str.strip()
    )
else:
    active_vessels["_MASTER_VESSEL_NAME"] = pd.NA

master_imo_set = set(active_vessels["_IMO_KEY"].dropna())


# ============================================================
# 2. READ THE SIX AFFECTED FILES
# ============================================================

all_records = []

with ZipFile(ZIP_PATH, "r") as zip_file:

    available_files = set(zip_file.namelist())

    for filename in AFFECTED_FILES:

        if filename not in available_files:
            print(f"WARNING: File not found in ZIP: {filename}")
            continue

        df = read_csv_from_zip(zip_file, filename)

        # Find IMO column
        imo_col = find_column(
    df,
    [
        "vesselIMONumber",
        "vesselIMO",
        "vessel_imo",
        "imo",
        "imoNumber"
    ]
)

        if imo_col is None:
            print(f"WARNING: No IMO column in {filename}")
            continue

        # Find vessel name column
        name_col = find_column(
    df,
    [
        "vesselName",
        "vessel_name",
        "name",
        "shipName"
    ]
)

        # Find port code column
        port_col = find_column(
            df,
            ["UNLocationCode", "unLocationCode", "portCode", "locode"]
        )

        # Find call reference column
        call_col = find_column(
            df,
            ["transportCallReference", "transport_call_reference"]
        )

        # Preserve original file and row information
        df["Source_File"] = filename
        df["Source_Row_Number"] = range(1, len(df) + 1)

        df["Filename_IMO"] = Path(filename).stem
        df["Internal_IMO"] = clean_imo(df[imo_col])

        if name_col:
            df["Vessel_Name"] = (
                df[name_col].astype("string").str.strip()
            )
        else:
            df["Vessel_Name"] = pd.NA

        if port_col:
            df["Port_Code"] = (
                df[port_col].astype("string").str.strip()
            )
        else:
            df["Port_Code"] = pd.NA

        if call_col:
            df["Transport_Call_Reference"] = df[call_col]
        else:
            df["Transport_Call_Reference"] = pd.NA

        df["Identity_Match_Status"] = np.where(
            df["Internal_IMO"].eq(df["Filename_IMO"]),
            "FILENAME_MATCH",
            "SECONDARY_IMO"
        )

        df["In_Active_Vessel_Master"] = (
            df["Internal_IMO"].isin(master_imo_set)
        )

        # Attach active master vessel names, if available
        master_names = (
            active_vessels[
                ["_IMO_KEY", "_MASTER_VESSEL_NAME"]
            ]
            .dropna(subset=["_IMO_KEY"])
            .drop_duplicates("_IMO_KEY")
            .set_index("_IMO_KEY")["_MASTER_VESSEL_NAME"]
        )

        df["Active_Master_Vessel_Name"] = (
            df["Internal_IMO"].map(master_names)
        )

        # Preserve original timestamps and create parsed timestamps
        for col in TIMESTAMP_COLUMNS:
            if col in df.columns:
                df[f"{col}_PARSED"] = parse_timestamp(df[col])
            else:
                df[f"{col}_PARSED"] = pd.NaT

        # Define an analysis arrival and departure using
        # actual > estimated > planned priority
        analysis_arrivals = df.apply(
            lambda row: first_existing_value(
                row,
                [f"{c}_PARSED" for c in ARRIVAL_COLUMNS]
            ),
            axis=1
        )

        df["Analysis_Arrival"] = [
            item[0] for item in analysis_arrivals
        ]

        df["Analysis_Arrival_Source"] = [
            item[1].replace("_PARSED", "") if item[1] else None
            for item in analysis_arrivals
        ]

        analysis_departures = df.apply(
            lambda row: first_existing_value(
                row,
                [f"{c}_PARSED" for c in DEPARTURE_COLUMNS]
            ),
            axis=1
        )

        df["Analysis_Departure"] = [
            item[0] for item in analysis_departures
        ]

        df["Analysis_Departure_Source"] = [
            item[1].replace("_PARSED", "") if item[1] else None
            for item in analysis_departures
        ]

        all_records.append(df)

        print(
            f"Loaded {filename}: {len(df)} records, "
            f"{df['Internal_IMO'].nunique()} internal IMOs"
        )


if not all_records:
    raise ValueError("No affected CSV files were loaded.")

records = pd.concat(all_records, ignore_index=True)


# ============================================================
# 3. ROW-LEVEL TIMESTAMP QUALITY CHECKS
# ============================================================

records["Arrival_After_Departure"] = (
    records["Analysis_Arrival"].notna()
    & records["Analysis_Departure"].notna()
    & (
        records["Analysis_Arrival"]
        > records["Analysis_Departure"]
    )
)

records["Missing_Analysis_Arrival"] = (
    records["Analysis_Arrival"].isna()
)

records["Missing_Analysis_Departure"] = (
    records["Analysis_Departure"].isna()
)

records["Negative_Port_Stay"] = records["Arrival_After_Departure"]


# ============================================================
# 4. CHRONOLOGICAL ANALYSIS BY IMO
# ============================================================

chronology_results = []
imo_summary_results = []

for (source_file, imo), group in records.groupby(
    ["Source_File", "Internal_IMO"],
    dropna=False
):

    group = group.sort_values(
        "Analysis_Arrival",
        na_position="last"
    ).copy()

    valid_arrivals = group["Analysis_Arrival"].dropna()

    if len(valid_arrivals) > 1:
        time_differences = valid_arrivals.diff().dropna()
        negative_gaps = int((time_differences < pd.Timedelta(0)).sum())
    else:
        negative_gaps = 0

    # Record chronological sequence
    for sequence_number, (_, row) in enumerate(
        group.iterrows(), start=1
    ):

        chronology_results.append({
            "Source_File": source_file,
            "Internal_IMO": imo,
            "Sequence_Number": sequence_number,
            "Vessel_Name": row["Vessel_Name"],
            "Port_Code": row["Port_Code"],
            "Transport_Call_Reference": row[
                "Transport_Call_Reference"
            ],
            "Analysis_Arrival": row["Analysis_Arrival"],
            "Analysis_Arrival_Source": row[
                "Analysis_Arrival_Source"
            ],
            "Analysis_Departure": row["Analysis_Departure"],
            "Analysis_Departure_Source": row[
                "Analysis_Departure_Source"
            ],
            "Arrival_After_Departure": row[
                "Arrival_After_Departure"
            ],
        })

    # First and last recorded arrival/departure
    first_arrival = (
        valid_arrivals.min() if len(valid_arrivals) else pd.NaT
    )

    last_arrival = (
        valid_arrivals.max() if len(valid_arrivals) else pd.NaT
    )

    valid_departures = group["Analysis_Departure"].dropna()

    first_departure = (
        valid_departures.min()
        if len(valid_departures)
        else pd.NaT
    )

    last_departure = (
        valid_departures.max()
        if len(valid_departures)
        else pd.NaT
    )

    names = sorted(
        group["Vessel_Name"].dropna().unique().tolist()
    )

    ports = sorted(
        group["Port_Code"].dropna().unique().tolist()
    )

    imo_summary_results.append({
        "Source_File": source_file,
        "Internal_IMO": imo,
        "Filename_IMO": group["Filename_IMO"].iloc[0],
        "Record_Count": len(group),
        "Vessel_Names": "; ".join(names),
        "Port_Count": len(ports),
        "Port_Codes": "; ".join(ports),
        "First_Analysis_Arrival": first_arrival,
        "Last_Analysis_Arrival": last_arrival,
        "First_Analysis_Departure": first_departure,
        "Last_Analysis_Departure": last_departure,
        "Missing_Arrival_Count": int(
            group["Missing_Analysis_Arrival"].sum()
        ),
        "Missing_Departure_Count": int(
            group["Missing_Analysis_Departure"].sum()
        ),
        "Arrival_After_Departure_Count": int(
            group["Arrival_After_Departure"].sum()
        ),
        "Negative_Chronological_Gaps": negative_gaps,
        "In_Active_Vessel_Master": bool(
            group["In_Active_Vessel_Master"].all()
        ),
        "Identity_Match_Status": (
            "FILENAME_MATCH"
            if imo == group["Filename_IMO"].iloc[0]
            else "SECONDARY_IMO"
        ),
    })


# ============================================================
# 5. CHECK OVERLAPPING PORT-CALL INTERVALS
# ============================================================

overlap_results = []

for source_file, file_group in records.groupby("Source_File"):

    # Compare calls belonging to different IMOs only
    file_group = file_group.dropna(
        subset=["Internal_IMO", "Analysis_Arrival", "Analysis_Departure"]
    ).copy()

    file_group = file_group.sort_values("Analysis_Arrival")

    rows = file_group.to_dict("records")

    for i in range(len(rows)):
        first = rows[i]

        for j in range(i + 1, len(rows)):
            second = rows[j]

            if first["Internal_IMO"] == second["Internal_IMO"]:
                continue

            # Two intervals overlap if each starts before the
            # other interval ends.
            overlap = (
                first["Analysis_Arrival"]
                < second["Analysis_Departure"]
                and second["Analysis_Arrival"]
                < first["Analysis_Departure"]
            )

            if overlap:
                overlap_results.append({
                    "Source_File": source_file,
                    "IMO_1": first["Internal_IMO"],
                    "Vessel_Name_1": first["Vessel_Name"],
                    "Port_1": first["Port_Code"],
                    "Call_Reference_1": first[
                        "Transport_Call_Reference"
                    ],
                    "Arrival_1": first["Analysis_Arrival"],
                    "Departure_1": first["Analysis_Departure"],
                    "IMO_2": second["Internal_IMO"],
                    "Vessel_Name_2": second["Vessel_Name"],
                    "Port_2": second["Port_Code"],
                    "Call_Reference_2": second[
                        "Transport_Call_Reference"
                    ],
                    "Arrival_2": second["Analysis_Arrival"],
                    "Departure_2": second["Analysis_Departure"],
                    "Overlap_Note": (
                        "Different IMOs have overlapping "
                        "analysis intervals; review source data."
                    ),
                })


# ============================================================
# 6. CHECK TIMESTAMP PARSING AND TIMEZONE PATTERNS
# ============================================================

timestamp_quality_results = []

for col in TIMESTAMP_COLUMNS:

    if col in records.columns:
        original = records[col]
        parsed = records[f"{col}_PARSED"]

        timestamp_quality_results.append({
            "Timestamp_Column": col,
            "Total_Rows": len(records),
            "Non_Missing_Original": int(original.notna().sum()),
            "Successfully_Parsed": int(parsed.notna().sum()),
            "Failed_Parsing": int(
                (original.notna() & parsed.isna()).sum()
            ),
            "Missing_Original": int(original.isna().sum()),
            "Sample_Original_Values": " | ".join(
                original.dropna().astype(str).head(5).tolist()
            ),
        })


# ============================================================
# 7. SAVE OUTPUT TABLES
# ============================================================

chronology_df = pd.DataFrame(chronology_results)
imo_summary_df = pd.DataFrame(imo_summary_results)
overlap_df = pd.DataFrame(overlap_results)
timestamp_quality_df = pd.DataFrame(timestamp_quality_results)

records.to_csv(
    OUTPUT_TABLES / "05_affected_vessel_row_level.csv",
    index=False
)

chronology_df.to_csv(
    OUTPUT_TABLES / "05_vessel_chronological_sequence.csv",
    index=False
)

imo_summary_df.to_csv(
    OUTPUT_TABLES / "05_vessel_imo_chronology_summary.csv",
    index=False
)

overlap_df.to_csv(
    OUTPUT_TABLES / "05_overlapping_port_call_intervals.csv",
    index=False
)

timestamp_quality_df.to_csv(
    OUTPUT_TABLES / "05_timestamp_parsing_quality.csv",
    index=False
)


# ============================================================
# 8. GENERATE TEXT REPORT
# ============================================================

report = []

report.append("=" * 75)
report.append("SCRIPT 05: VESSEL IDENTITY AND CHRONOLOGY INVESTIGATION")
report.append("=" * 75)

report.append(f"\nTotal records investigated: {len(records)}")
report.append(
    f"Source files successfully loaded: "
    f"{records['Source_File'].nunique()}"
)
report.append(
    f"Distinct internal IMOs: "
    f"{records['Internal_IMO'].nunique()}"
)

report.append("\n\n1. IDENTITY MATCH SUMMARY")
report.append("-" * 75)

identity_counts = records["Identity_Match_Status"].value_counts()

for status, count in identity_counts.items():
    report.append(f"{status}: {count}")

report.append(
    "\nRecords with IMO found in active vessel master: "
    f"{int(records['In_Active_Vessel_Master'].sum())}"
)

report.append(
    "Records with IMO not found in active vessel master: "
    f"{int((~records['In_Active_Vessel_Master']).sum())}"
)

report.append("\n\n2. IMO-LEVEL CHRONOLOGY SUMMARY")
report.append("-" * 75)

for _, row in imo_summary_df.iterrows():
    report.append(
        f"\nFile: {row['Source_File']}"
        f"\nIMO: {row['Internal_IMO']}"
        f"\nIdentity: {row['Identity_Match_Status']}"
        f"\nRecords: {row['Record_Count']}"
        f"\nVessel names: {row['Vessel_Names']}"
        f"\nPorts: {row['Port_Count']}"
        f"\nFirst arrival: {row['First_Analysis_Arrival']}"
        f"\nLast arrival: {row['Last_Analysis_Arrival']}"
        f"\nMissing arrivals: {row['Missing_Arrival_Count']}"
        f"\nMissing departures: {row['Missing_Departure_Count']}"
        f"\nArrival after departure: "
        f"{row['Arrival_After_Departure_Count']}"
    )

report.append("\n\n3. TIMESTAMP PARSING QUALITY")
report.append("-" * 75)

for _, row in timestamp_quality_df.iterrows():
    report.append(
        f"\n{row['Timestamp_Column']}:"
        f"\nNon-missing original: {row['Non_Missing_Original']}"
        f"\nSuccessfully parsed: {row['Successfully_Parsed']}"
        f"\nFailed parsing: {row['Failed_Parsing']}"
        f"\nMissing original: {row['Missing_Original']}"
        f"\nSample values: {row['Sample_Original_Values']}"
    )

report.append("\n\n4. OVERLAPPING PORT-CALL INTERVALS")
report.append("-" * 75)
report.append(
    f"Potential overlaps between different IMOs: {len(overlap_df)}"
)

report.append(
    "\nNote: Overlapping intervals are flags for investigation, "
    "not automatic proof of incorrect records."
)

report.append(
    "\n\n5. IMPORTANT TIMESTAMP ASSUMPTION"
)
report.append("-" * 75)
report.append(
    "Analysis_Arrival and Analysis_Departure use actual timestamps "
    "first, then estimated, then planned timestamps."
)
report.append(
    "Pandas parsed timestamps with utc=True. Naive timestamps are "
    "treated as UTC for comparison. The original source timezone "
    "has not been independently verified."
)
report.append(
    "Do not interpret the resulting UTC values as confirmed UTC "
    "until the source timezone convention is established."
)

report.append("\n\n6. OUTPUT FILES")
report.append("-" * 75)

for filename in [
    "05_affected_vessel_row_level.csv",
    "05_vessel_chronological_sequence.csv",
    "05_vessel_imo_chronology_summary.csv",
    "05_overlapping_port_call_intervals.csv",
    "05_timestamp_parsing_quality.csv",
]:
    report.append(str(OUTPUT_TABLES / filename))

report_text = "\n".join(report)

report_path = (
    OUTPUT_REPORTS / "05_vessel_identity_chronology_report.txt"
)

report_path.write_text(report_text, encoding="utf-8")


# ============================================================
# 9. PRINT FINAL SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("SCRIPT 05 COMPLETED SUCCESSFULLY")
print("=" * 70)

print(f"\nTotal records investigated: {len(records)}")
print(f"Distinct internal IMOs: {records['Internal_IMO'].nunique()}")

print("\nIdentity status:")
print(identity_counts.to_string())

print(
    "\nRecords with arrival after departure:",
    int(records["Arrival_After_Departure"].sum())
)

print(
    "Records missing analysis arrival:",
    int(records["Missing_Analysis_Arrival"].sum())
)

print(
    "Records missing analysis departure:",
    int(records["Missing_Analysis_Departure"].sum())
)

print(
    "Potential overlaps between different IMOs:",
    len(overlap_df)
)

print("\nFiles saved:")
print(f"Report: {report_path}")
print(f"Tables: {OUTPUT_TABLES}")

print("\nNext step: inspect the generated report and CSV outputs.")
