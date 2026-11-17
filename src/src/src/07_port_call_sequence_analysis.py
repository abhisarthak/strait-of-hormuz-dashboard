
from pathlib import Path
import re
import warnings

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# ============================================================
# 1. PROJECT PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent.parent

PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_DIR = ROOT / "outputs"

TABLE_DIR = OUTPUT_DIR / "tables"
REPORT_DIR = OUTPUT_DIR / "reports"
FIGURE_DIR = OUTPUT_DIR / "figures"

for folder in [TABLE_DIR, REPORT_DIR, FIGURE_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

INDIVIDUAL_FILE = (
    PROCESSED_DIR / "06_individual_vessel_port_calls.csv"
)

SCHEDULE_FILE = (
    PROCESSED_DIR / "06_integrated_schedule_vessel_port.csv"
)


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def normalize_column_name(name):
    """Normalize column names for flexible matching."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def find_column(df, candidates):
    """
    Find a column using normalized candidate names.
    Returns None if no candidate exists.
    """
    available = {
        normalize_column_name(col): col
        for col in df.columns
    }

    for candidate in candidates:
        key = normalize_column_name(candidate)

        if key in available:
            return available[key]

    return None


def find_timestamp_column(df, candidates, source_name):
    col = find_column(df, candidates)

    if col is None:
        print(
            f"WARNING: {source_name} timestamp column not found."
        )

    return col


def normalize_identifier(series):
    """Standardize IMO and other identifiers."""
    result = (
        series.astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )

    result = result.str.replace(r"\.0$", "", regex=True)

    return result


def normalize_port(series):
    """Standardize port names for comparison."""
    return (
        series.astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .replace("", pd.NA)
    )


def parse_timestamp(series):
    """
    Parse timestamps with mixed formats and convert to UTC.
    Original source columns remain untouched.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        return pd.to_datetime(
            series,
            errors="coerce",
            utc=True,
            format="mixed"
        )


def save_csv(df, filename):
    path = TABLE_DIR / filename

    df.to_csv(
        path,
        index=False,
        encoding="utf-8-sig"
    )

    print(f"Saved: {path.relative_to(ROOT)}")


def format_hours(value):
    if pd.isna(value):
        return "NA"

    return round(float(value), 2)


# ============================================================
# 3. STANDARDIZE A DATASET
# ============================================================

def prepare_port_calls(df, dataset_name, dataset_type):
    """
    Convert either source dataset into a common analytical
    port-call structure.

    Original columns are retained.
    """

    print("\n" + "=" * 70)
    print(f"PREPARING: {dataset_name}")
    print("=" * 70)

    df = df.copy()

    df["Source_Dataset"] = dataset_name
    df["Source_Row_ID"] = range(1, len(df) + 1)

    # --------------------------------------------------------
    # Identify vessel IMO
    # --------------------------------------------------------

    imo_col = find_column(
        df,
        [
            "vesselIMONumber",
            "vesselIMO",
            "IMO number",
            "IMO Number",
            "IMO",
        ]
    )

    if imo_col is None:
        raise ValueError(
            f"IMO column not found in {dataset_name}. "
            f"Available columns: {df.columns.tolist()}"
        )

    df["IMO_Normalised"] = normalize_identifier(
        df[imo_col]
    )

    # --------------------------------------------------------
    # Identify vessel name
    # --------------------------------------------------------

    vessel_name_col = find_column(
        df,
        [
            "vesselName",
            "Vessel Name",
            "Master_vesselName",
        ]
    )

    if vessel_name_col:
        df["Analysis_Vessel_Name"] = normalize_port(
            df[vessel_name_col]
        )
    else:
        df["Analysis_Vessel_Name"] = pd.NA

    # --------------------------------------------------------
    # Identify port name
    # --------------------------------------------------------

    port_col = find_column(
        df,
        [
            "port",
            "portName",
            "Port",
            "Port Name",
            "cityName",
        ]
    )

    if port_col is not None:
        df["Analysis_Port_Name"] = normalize_port(
            df[port_col]
        )
    else:
        df["Analysis_Port_Name"] = pd.NA

    # --------------------------------------------------------
    # Identify UN/LOCODE
    # --------------------------------------------------------

    locode_col = find_column(
        df,
        [
            "UNLOCODE_Normalised",
            "UNLocationCode",
            "UN Location Code",
            "UNLOCODE",
        ]
    )

    if locode_col is not None:
        df["Analysis_UNLOCODE"] = normalize_identifier(
            df[locode_col]
        )
    else:
        df["Analysis_UNLOCODE"] = pd.NA

    # --------------------------------------------------------
    # Identify actual, estimated and planned timestamps
    # --------------------------------------------------------

    if dataset_type == "individual":

        arrival_candidates = {
            "Actual": [
                "ARRI_ACT",
                "Arrival Actual",
            ],
            "Estimated": [
                "ARRI_EST",
                "Arrival Estimated",
            ],
            "Planned": [
                "ARRI_PLN",
                "Arrival Planned",
            ],
        }

        departure_candidates = {
            "Actual": [
                "DEPA_ACT",
                "Departure Actual",
            ],
            "Estimated": [
                "DEPA_EST",
                "Departure Estimated",
            ],
            "Planned": [
                "DEPA_PLN",
                "Departure Planned",
            ],
        }

    else:

        arrival_candidates = {
            "Actual": [
                "Actual Arrival",
                "Actual Arrival Date",
                "Arrival Actual",
                "ATA",
            ],
            "Estimated": [
                "Estimated Arrival",
                "Estimated Arrival Date",
                "Arrival Estimated",
                "ETA",
            ],
            "Planned": [
                "Planned Arrival",
                "Planned Arrival Date",
                "Arrival Planned",
                "PTA",
            ],
        }

        departure_candidates = {
            "Actual": [
                "Actual Departure",
                "Actual Departure Date",
                "Departure Actual",
                "ATD",
            ],
            "Estimated": [
                "Estimated Departure",
                "Estimated Departure Date",
                "Departure Estimated",
                "ETD",
            ],
            "Planned": [
                "Planned Departure",
                "Planned Departure Date",
                "Departure Planned",
                "PTD",
            ],
        }

    # Find and parse the original timestamp fields.
    timestamp_columns = {}

    for source, candidates in arrival_candidates.items():

        col = find_timestamp_column(
            df,
            candidates,
            f"{dataset_name} {source} arrival"
        )

        timestamp_columns[f"Arrival_{source}"] = col

        if col:
            df[f"Arrival_{source}_UTC"] = parse_timestamp(
                df[col]
            )
        else:
            df[f"Arrival_{source}_UTC"] = pd.NaT

    for source, candidates in departure_candidates.items():

        col = find_timestamp_column(
            df,
            candidates,
            f"{dataset_name} {source} departure"
        )

        timestamp_columns[f"Departure_{source}"] = col

        if col:
            df[f"Departure_{source}_UTC"] = parse_timestamp(
                df[col]
            )
        else:
            df[f"Departure_{source}_UTC"] = pd.NaT

    # --------------------------------------------------------
    # Choose analysis timestamps
    # Priority: Actual > Estimated > Planned
    # --------------------------------------------------------

    arrival_priority = [
        "Arrival_Actual_UTC",
        "Arrival_Estimated_UTC",
        "Arrival_Planned_UTC",
    ]

    departure_priority = [
        "Departure_Actual_UTC",
        "Departure_Estimated_UTC",
        "Departure_Planned_UTC",
    ]

    df["Analysis_Arrival_UTC"] = df[
        arrival_priority
    ].bfill(axis=1).iloc[:, 0]

    df["Analysis_Departure_UTC"] = df[
        departure_priority
    ].bfill(axis=1).iloc[:, 0]

    df["Analysis_Arrival_Source"] = np.select(
        [
            df["Arrival_Actual_UTC"].notna(),
            df["Arrival_Estimated_UTC"].notna(),
            df["Arrival_Planned_UTC"].notna(),
        ],
        [
            "ACTUAL",
            "ESTIMATED",
            "PLANNED",
        ],
        default="MISSING"
    )

    df["Analysis_Departure_Source"] = np.select(
        [
            df["Departure_Actual_UTC"].notna(),
            df["Departure_Estimated_UTC"].notna(),
            df["Departure_Planned_UTC"].notna(),
        ],
        [
            "ACTUAL",
            "ESTIMATED",
            "PLANNED",
        ],
        default="MISSING"
    )

    # --------------------------------------------------------
    # Call reference
    # --------------------------------------------------------

    reference_col = find_column(
        df,
        [
            "transportCallReference",
            "transportCallRef",
            "Transport Call Reference",
        ]
    )

    if reference_col:
        df["Analysis_Call_Reference"] = (
            df[reference_col].astype("string").str.strip()
        )
    else:
        df["Analysis_Call_Reference"] = pd.NA

    # --------------------------------------------------------
    # Port-call level validation
    # --------------------------------------------------------

    df["Missing_IMO"] = df["IMO_Normalised"].isna()

    df["Missing_Arrival"] = (
        df["Analysis_Arrival_UTC"].isna()
    )

    df["Missing_Departure"] = (
        df["Analysis_Departure_UTC"].isna()
    )

    df["Arrival_After_Departure"] = (
        df["Analysis_Arrival_UTC"]
        > df["Analysis_Departure_UTC"]
    )

    df["Port_Stay_Hours"] = (
        df["Analysis_Departure_UTC"]
        - df["Analysis_Arrival_UTC"]
    ).dt.total_seconds() / 3600

    df["Negative_Port_Stay"] = (
        df["Port_Stay_Hours"] < 0
    )

    df["Missing_Port"] = (
        df["Analysis_Port_Name"].isna()
        & df["Analysis_UNLOCODE"].isna()
    )

    print("Rows:", len(df))
    print("Unique IMOs:", df["IMO_Normalised"].nunique())
    print("Missing IMOs:", df["Missing_IMO"].sum())
    print("Missing arrivals:", df["Missing_Arrival"].sum())
    print("Missing departures:", df["Missing_Departure"].sum())

    return df


# ============================================================
# 4. RECONSTRUCT VESSEL PORT-CALL SEQUENCES
# ============================================================

def reconstruct_sequences(df, dataset_name):

    print("\n" + "=" * 70)
    print(f"RECONSTRUCTING SEQUENCES: {dataset_name}")
    print("=" * 70)

    valid = df.dropna(
        subset=["IMO_Normalised"]
    ).copy()

    # A vessel sequence requires an arrival timestamp.
    sequence_data = valid.dropna(
        subset=["Analysis_Arrival_UTC"]
    ).copy()

    sequence_data = sequence_data.sort_values(
        [
            "IMO_Normalised",
            "Analysis_Arrival_UTC",
            "Source_Row_ID",
        ]
    ).reset_index(drop=True)

    # Sequence number for each vessel.
    sequence_data["Port_Call_Sequence"] = (
        sequence_data.groupby("IMO_Normalised")
        .cumcount() + 1
    )

    # Previous port-call information.
    sequence_data["Previous_Port"] = (
        sequence_data.groupby("IMO_Normalised")[
            "Analysis_Port_Name"
        ].shift(1)
    )

    sequence_data["Previous_UNLOCODE"] = (
        sequence_data.groupby("IMO_Normalised")[
            "Analysis_UNLOCODE"
        ].shift(1)
    )

    sequence_data["Previous_Arrival_UTC"] = (
        sequence_data.groupby("IMO_Normalised")[
            "Analysis_Arrival_UTC"
        ].shift(1)
    )

    sequence_data["Previous_Departure_UTC"] = (
        sequence_data.groupby("IMO_Normalised")[
            "Analysis_Departure_UTC"
        ].shift(1)
    )

    # Time between previous departure and current arrival.
    sequence_data["Inter_Port_Gap_Hours"] = (
        sequence_data["Analysis_Arrival_UTC"]
        - sequence_data["Previous_Departure_UTC"]
    ).dt.total_seconds() / 3600

    # Time between previous arrival and current arrival.
    sequence_data["Arrival_To_Arrival_Hours"] = (
        sequence_data["Analysis_Arrival_UTC"]
        - sequence_data["Previous_Arrival_UTC"]
    ).dt.total_seconds() / 3600

    # Flag potential chronology issues.
    sequence_data["Negative_Inter_Port_Gap"] = (
        sequence_data["Inter_Port_Gap_Hours"] < 0
    )

    # Consecutive records with the same port code.
    same_locode = (
        sequence_data["Analysis_UNLOCODE"].notna()
        & sequence_data["Previous_UNLOCODE"].notna()
        & (
            sequence_data["Analysis_UNLOCODE"]
            == sequence_data["Previous_UNLOCODE"]
        )
    )

    same_port_name = (
        sequence_data["Analysis_Port_Name"].notna()
        & sequence_data["Previous_Port"].notna()
        & (
            sequence_data["Analysis_Port_Name"]
            == sequence_data["Previous_Port"]
        )
    )

    sequence_data["Same_Consecutive_Port"] = (
        same_locode | same_port_name
    )

    # Sequence output columns.
    sequence_columns = [
        "Source_Dataset",
        "Source_Row_ID",
        "IMO_Normalised",
        "Analysis_Vessel_Name",
        "Port_Call_Sequence",
        "Analysis_Port_Name",
        "Analysis_UNLOCODE",
        "Analysis_Call_Reference",
        "Analysis_Arrival_UTC",
        "Analysis_Arrival_Source",
        "Analysis_Departure_UTC",
        "Analysis_Departure_Source",
        "Port_Stay_Hours",
        "Previous_Port",
        "Previous_UNLOCODE",
        "Previous_Arrival_UTC",
        "Previous_Departure_UTC",
        "Inter_Port_Gap_Hours",
        "Arrival_To_Arrival_Hours",
        "Negative_Inter_Port_Gap",
        "Same_Consecutive_Port",
    ]

    sequence_output = sequence_data[
        sequence_columns
    ].copy()

    # --------------------------------------------------------
    # Vessel-level summary
    # --------------------------------------------------------

    vessel_summary = (
        sequence_data.groupby("IMO_Normalised")
        .agg(
            Port_Call_Count=("Source_Row_ID", "count"),
            First_Arrival=("Analysis_Arrival_UTC", "min"),
            Last_Arrival=("Analysis_Arrival_UTC", "max"),
            Unique_Port_Names=(
                "Analysis_Port_Name", "nunique"
            ),
            Unique_UNLOCODEs=(
                "Analysis_UNLOCODE", "nunique"
            ),
            Mean_Port_Stay_Hours=(
                "Port_Stay_Hours", "mean"
            ),
            Median_Port_Stay_Hours=(
                "Port_Stay_Hours", "median"
            ),
            Negative_Port_Stays=(
                "Negative_Port_Stay", "sum"
            ),
            Negative_Inter_Port_Gaps=(
                "Negative_Inter_Port_Gap", "sum"
            ),
        )
        .reset_index()
    )

    vessel_summary["Port_Sequence"] = (
        sequence_data.groupby("IMO_Normalised")[
            "Analysis_Port_Name"
        ]
        .apply(
            lambda s: " -> ".join(
                s.fillna("UNKNOWN").astype(str)
            )
        )
        .values
    )

    # --------------------------------------------------------
    # Port-to-port transition summary
    # --------------------------------------------------------

    transitions = sequence_data.dropna(
        subset=[
            "Previous_UNLOCODE",
            "Analysis_UNLOCODE",
            "Inter_Port_Gap_Hours",
        ]
    ).copy()

    transition_summary = (
        transitions.groupby(
            ["Previous_UNLOCODE", "Analysis_UNLOCODE"],
            dropna=False
        )
        .agg(
            Transition_Count=("IMO_Normalised", "size"),
            Unique_Vessels=("IMO_Normalised", "nunique"),
            Mean_Inter_Port_Gap_Hours=(
                "Inter_Port_Gap_Hours", "mean"
            ),
            Median_Inter_Port_Gap_Hours=(
                "Inter_Port_Gap_Hours", "median"
            ),
            Minimum_Inter_Port_Gap_Hours=(
                "Inter_Port_Gap_Hours", "min"
            ),
            Maximum_Inter_Port_Gap_Hours=(
                "Inter_Port_Gap_Hours", "max"
            ),
        )
        .reset_index()
    )

    transition_summary = transition_summary.sort_values(
        "Transition_Count",
        ascending=False
    )

    # --------------------------------------------------------
    # Anomaly records
    # --------------------------------------------------------

    anomalies = sequence_data[
        (
            sequence_data["Negative_Port_Stay"]
            | sequence_data["Negative_Inter_Port_Gap"]
            | sequence_data["Missing_Port"]
        )
    ].copy()

    # --------------------------------------------------------
    # Save outputs
    # --------------------------------------------------------

    prefix = (
        "07_individual"
        if "Individual" in dataset_name
        else "07_schedule"
    )

    save_csv(
        sequence_output,
        f"{prefix}_port_call_sequences.csv"
    )

    save_csv(
        vessel_summary,
        f"{prefix}_vessel_sequence_summary.csv"
    )

    save_csv(
        transition_summary,
        f"{prefix}_port_transition_summary.csv"
    )

    save_csv(
        anomalies,
        f"{prefix}_sequence_anomalies.csv"
    )

    # --------------------------------------------------------
    # Dataset statistics
    # --------------------------------------------------------

    stats = {
        "Dataset": dataset_name,
        "Total_Records": len(df),
        "Records_With_IMO": len(valid),
        "Records_With_Arrival": len(sequence_data),
        "Unique_Vessels": sequence_data[
            "IMO_Normalised"
        ].nunique(),
        "Records_Without_Arrival": int(
            valid["Analysis_Arrival_UTC"].isna().sum()
        ),
        "Records_With_Missing_IMO": int(
            df["Missing_IMO"].sum()
        ),
        "Records_With_Missing_Departure": int(
            df["Missing_Departure"].sum()
        ),
        "Negative_Port_Stays": int(
            sequence_data["Negative_Port_Stay"].sum()
        ),
        "Negative_Inter_Port_Gaps": int(
            sequence_data["Negative_Inter_Port_Gap"].sum()
        ),
        "Same_Consecutive_Port_Records": int(
            sequence_data["Same_Consecutive_Port"].sum()
        ),
        "Anomaly_Records": len(anomalies),
    }

    print("\nDATASET SUMMARY")

    for key, value in stats.items():
        print(f"{key}: {value}")

    return {
        "sequence": sequence_output,
        "vessels": vessel_summary,
        "transitions": transition_summary,
        "anomalies": anomalies,
        "stats": stats,
        "all_calls": df,
    }


# ============================================================
# 5. VISUALIZATIONS
# ============================================================

def create_visualizations(result, prefix, dataset_name):

    sequence = result["sequence"]
    vessels = result["vessels"]
    transitions = result["transitions"]

    if sequence.empty:
        print(f"No sequence data available for {dataset_name}")
        return

    # --------------------------------------------------------
    # Figure 1: Port-call count distribution
    # --------------------------------------------------------

    plt.figure(figsize=(10, 6))

    plt.hist(
        vessels["Port_Call_Count"],
        bins=20,
        edgecolor="black"
    )

    plt.xlabel("Number of Port Calls")
    plt.ylabel("Number of Vessels")
    plt.title(f"Port-call Count Distribution - {dataset_name}")

    plt.tight_layout()

    plt.savefig(
        FIGURE_DIR / f"{prefix}_port_call_distribution.png",
        dpi=300
    )

    plt.close()

    # --------------------------------------------------------
    # Figure 2: Port-stay duration distribution
    # --------------------------------------------------------

    stay_values = sequence[
        "Port_Stay_Hours"
    ].dropna()

    stay_values = stay_values[
        (stay_values >= 0) & (stay_values <= 24 * 90)
    ]

    if not stay_values.empty:

        plt.figure(figsize=(10, 6))

        plt.hist(
            stay_values,
            bins=30,
            edgecolor="black"
        )

        plt.xlabel("Port Stay Duration (Hours)")
        plt.ylabel("Number of Port Calls")
        plt.title(f"Port Stay Distribution - {dataset_name}")

        plt.tight_layout()

        plt.savefig(
            FIGURE_DIR / f"{prefix}_port_stay_distribution.png",
            dpi=300
        )

        plt.close()

    # --------------------------------------------------------
    # Figure 3: Most frequent port transitions
    # --------------------------------------------------------

    top_transitions = transitions.head(15).copy()

    if not top_transitions.empty:

        top_transitions["Transition"] = (
            top_transitions["Previous_UNLOCODE"]
            + " -> "
            + top_transitions["Analysis_UNLOCODE"]
        )

        top_transitions = top_transitions.sort_values(
            "Transition_Count"
        )

        plt.figure(figsize=(11, 7))

        plt.barh(
            top_transitions["Transition"],
            top_transitions["Transition_Count"]
        )

        plt.xlabel("Number of Observed Transitions")
        plt.ylabel("Port Transition (UN/LOCODE)")
        plt.title(f"Most Frequent Port Transitions - {dataset_name}")

        plt.tight_layout()

        plt.savefig(
            FIGURE_DIR / f"{prefix}_top_port_transitions.png",
            dpi=300
        )

        plt.close()

    print(f"Visualizations saved for {dataset_name}")


# ============================================================
# 6. MAIN EXECUTION
# ============================================================

print("\n" + "=" * 70)
print("STRAIT OF HORMUZ - PORT-CALL SEQUENCE ANALYSIS")
print("=" * 70)


# ------------------------------------------------------------
# Load datasets
# ------------------------------------------------------------

if not INDIVIDUAL_FILE.exists():
    raise FileNotFoundError(INDIVIDUAL_FILE)

if not SCHEDULE_FILE.exists():
    raise FileNotFoundError(SCHEDULE_FILE)

individual_raw = pd.read_csv(
    INDIVIDUAL_FILE,
    low_memory=False
)

schedule_raw = pd.read_csv(
    SCHEDULE_FILE,
    low_memory=False
)

print("\nINPUT DATASET DIMENSIONS")
print("-" * 70)

print("Individual vessel calls:", individual_raw.shape)
print("Integrated schedules:", schedule_raw.shape)


# ------------------------------------------------------------
# Prepare both datasets separately
# ------------------------------------------------------------

individual_prepared = prepare_port_calls(
    individual_raw,
    "Individual Vessel Port Calls",
    "individual"
)

schedule_prepared = prepare_port_calls(
    schedule_raw,
    "Combined Port Schedules",
    "schedule"
)


# ------------------------------------------------------------
# Reconstruct sequences
# ------------------------------------------------------------

individual_result = reconstruct_sequences(
    individual_prepared,
    "Individual Vessel Port Calls"
)

schedule_result = reconstruct_sequences(
    schedule_prepared,
    "Combined Port Schedules"
)


# ------------------------------------------------------------
# Create visualizations
# ------------------------------------------------------------

create_visualizations(
    individual_result,
    "07_individual",
    "Individual Vessel Port Calls"
)

create_visualizations(
    schedule_result,
    "07_schedule",
    "Combined Port Schedules"
)


# ============================================================
# 7. COMBINED DATASET SUMMARY REPORT
# ============================================================

report = []

report.append("=" * 70)
report.append("STRAIT OF HORMUZ - PORT-CALL SEQUENCE ANALYSIS REPORT")
report.append("=" * 70)

for result in [
    individual_result,
    schedule_result,
]:

    stats = result["stats"]

    report.append("\n")
    report.append("-" * 70)
    report.append(stats["Dataset"].upper())
    report.append("-" * 70)

    for key, value in stats.items():

        if key != "Dataset":
            report.append(f"{key}: {value}")

    report.append("\nTop port transitions:")

    report.append(
        result["transitions"]
        .head(10)
        .to_string(index=False)
    )

    report.append("\nSample vessel sequences:")

    report.append(
        result["vessels"]
        .head(10)
        .to_string(index=False)
    )


report_text = "\n".join(report)

report_path = REPORT_DIR / "07_port_call_sequence_analysis_report.txt"

with open(
    report_path,
    "w",
    encoding="utf-8"
) as file:

    file.write(report_text)


# ============================================================
# 8. SAVE COMBINED QUALITY SUMMARY
# ============================================================

quality_summary = pd.DataFrame([
    individual_result["stats"],
    schedule_result["stats"],
])

save_csv(
    quality_summary,
    "07_port_call_quality_summary.csv"
)

print("\n" + "=" * 70)
print(report_text)

print("\n" + "=" * 70)
print("SCRIPT 07 COMPLETED SUCCESSFULLY")
print("=" * 70)

print("\nReports saved in:")
print(REPORT_DIR)

print("\nTables saved in:")
print(TABLE_DIR)

print("\nFigures saved in:")
print(FIGURE_DIR)