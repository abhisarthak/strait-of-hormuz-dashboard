
from pathlib import Path
from itertools import combinations

import pandas as pd
import numpy as np


# ============================================================
# 1. PROJECT PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUT_TABLES = ROOT / "outputs" / "tables"
OUTPUT_REPORTS = ROOT / "outputs" / "reports"

OUTPUT_TABLES.mkdir(parents=True, exist_ok=True)
OUTPUT_REPORTS.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. INPUT FILES
# ============================================================

INPUT_FILES = {
    "INDIVIDUAL": DATA_PROCESSED / "06_individual_vessel_port_calls.csv",
    "SCHEDULE": DATA_PROCESSED / "06_integrated_schedule_vessel_port.csv",
}


# ============================================================
# 3. COLUMN DETECTION
#    Supports different column naming conventions.
# ============================================================

def normalize_column_name(name):
    """Convert a column name to lowercase alphanumeric form."""
    return "".join(ch.lower() for ch in str(name) if ch.isalnum())


def find_column(df, candidates, required=False):
    """
    Find a column using possible alternative names.
    Matching ignores spaces, underscores and capitalization.
    """
    lookup = {
        normalize_column_name(col): col
        for col in df.columns
    }

    for candidate in candidates:
        key = normalize_column_name(candidate)

        if key in lookup:
            return lookup[key]

    if required:
        raise ValueError(
            f"Required column not found. Tried: {candidates}\n"
            f"Available columns: {list(df.columns)}"
        )

    return None


COLUMN_CANDIDATES = {
    "imo": [
        "vesselIMO",
        "vesselIMONumber",
        "IMO",
        "IMO_Number",
        "IMO_Normalised",
        "IMO_Normalized",
        "IMO_Number_Normalised",
    ],

    "vessel_name": [
        "vesselName",
        "Vessel_Name",
        "Vessel",
        "Vessel Name",
    ],

    "port_name": [
        "portName",
        "Port_Name",
        "Port",
        "Facility_Name",
        "Facility",
        "port",
    ],

    "locode": [
        "UNLocationCode",
        "UNLOCODE",
        "UN_Location_Code",
        "LOCODE",
    ],

    "service": [
        "carrierServiceCode",
        "Carrier_Service_Code",
        "Service_Code",
        "Service",
        "serviceCode",
    ],

    "import_voyage": [
        "importVoyageNumber",
        "Import_Voyage_Number",
        "Import_Voyage",
        "Import_Voyage_No",
    ],

    "export_voyage": [
        "exportVoyageNumber",
        "Export_Voyage_Number",
        "Export_Voyage",
        "Export_Voyage_No",
    ],

    "call_reference": [
        "transportCallReference",
        "Transport_Call_Reference",
        "Call_Reference",
    ],

    "actual_arrival": [
        "ARRI_ACT",
        "Actual_Arrival",
        "ActualArrival",
        "actualArrival",
    ],

    "actual_departure": [
        "DEPA_ACT",
        "Actual_Departure",
        "ActualDeparture",
        "actualDeparture",
    ],

    "estimated_arrival": [
        "ARRI_EST",
        "Estimated_Arrival",
        "EstimatedArrival",
        "estimatedArrival",
    ],

    "estimated_departure": [
        "DEPA_EST",
        "Estimated_Departure",
        "EstimatedDeparture",
        "estimatedDeparture",
    ],

    "planned_arrival": [
        "ARRI_PLN",
        "Planned_Arrival",
        "PlannedArrival",
        "plannedArrival",
    ],

    "planned_departure": [
        "DEPA_PLN",
        "Planned_Departure",
        "PlannedDeparture",
        "plannedDeparture",
    ],
}


TIMESTAMP_SOURCES = {
    "ACTUAL": ("actual_arrival", "actual_departure"),
    "ESTIMATED": ("estimated_arrival", "estimated_departure"),
    "PLANNED": ("planned_arrival", "planned_departure"),
}


# ============================================================
# 4. GENERAL HELPERS
# ============================================================

def normalize_imo(series):
    """Normalize IMO values without changing the original column."""
    result = (
        series.astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )

    result = result.str.replace(r"\.0$", "", regex=True)

    return result


def clean_text(series):
    """Standardize text for grouping and comparison."""
    return (
        series.astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )


def load_and_prepare(dataset_name, file_path):
    """Load a dataset and create standardized analysis columns."""

    if not file_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {file_path}"
        )

    df = pd.read_csv(file_path, low_memory=False)

    print("\n" + "=" * 75)
    print(f"LOADING {dataset_name}")
    print("=" * 75)
    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns):,}")

    # Detect source columns
    detected = {}

    for key, candidates in COLUMN_CANDIDATES.items():
        detected[key] = find_column(
            df,
            candidates,
            required=(key == "imo")
        )

    print("\nDetected columns:")

    for key, value in detected.items():
        if value is not None:
            print(f"{key:20s}: {value}")

    # Preserve original columns; create standardized columns separately.
    df["Analysis_IMO"] = normalize_imo(df[detected["imo"]])

    if detected["vessel_name"]:
        df["Analysis_Vessel_Name"] = clean_text(
            df[detected["vessel_name"]]
        )
    else:
        df["Analysis_Vessel_Name"] = pd.NA

    if detected["port_name"]:
        df["Analysis_Port_Name"] = clean_text(
            df[detected["port_name"]]
        )
    else:
        df["Analysis_Port_Name"] = pd.NA

    if detected["locode"]:
        df["Analysis_LOCODE"] = clean_text(
            df[detected["locode"]]
        )
    else:
        df["Analysis_LOCODE"] = pd.NA

    if detected["service"]:
        df["Analysis_Service"] = clean_text(
            df[detected["service"]]
        )
    else:
        df["Analysis_Service"] = pd.NA

    if detected["import_voyage"]:
        df["Analysis_Import_Voyage"] = clean_text(
            df[detected["import_voyage"]]
        )
    else:
        df["Analysis_Import_Voyage"] = pd.NA

    if detected["export_voyage"]:
        df["Analysis_Export_Voyage"] = clean_text(
            df[detected["export_voyage"]]
        )
    else:
        df["Analysis_Export_Voyage"] = pd.NA

    if detected["call_reference"]:
        df["Analysis_Call_Reference"] = df[
            detected["call_reference"]
        ].astype("string")
    else:
        df["Analysis_Call_Reference"] = pd.NA

    # Parse timestamp columns independently.
    for source, (arrival_key, departure_key) in TIMESTAMP_SOURCES.items():

        arrival_col = detected[arrival_key]
        departure_col = detected[departure_key]

        if arrival_col:
            df[f"{source}_Arrival_UTC"] = pd.to_datetime(
                df[arrival_col],
                errors="coerce",
                utc=True
            )
        else:
            df[f"{source}_Arrival_UTC"] = pd.NaT

        if departure_col:
            df[f"{source}_Departure_UTC"] = pd.to_datetime(
                df[departure_col],
                errors="coerce",
                utc=True
            )
        else:
            df[f"{source}_Departure_UTC"] = pd.NaT

    return df, detected


# ============================================================
# 5. BUILD SOURCE-SPECIFIC CHRONOLOGICAL SEQUENCES
# ============================================================

def build_sequences(df, dataset_name, source):

    arrival_col = f"{source}_Arrival_UTC"
    departure_col = f"{source}_Departure_UTC"

    work = df.copy()

    work["Timestamp_Source"] = source
    work["Dataset"] = dataset_name

    work["Sequence_Eligible"] = (
        work["Analysis_IMO"].notna()
        & work[arrival_col].notna()
        & work[departure_col].notna()
        & (work[departure_col] >= work[arrival_col])
    )

    # Keep all records, including incomplete and anomalous ones.
    work = work.sort_values(
        ["Analysis_IMO", arrival_col, departure_col],
        na_position="last"
    ).copy()

    work["Sequence_Number"] = (
        work.groupby("Analysis_IMO", dropna=True)
        .cumcount() + 1
    )

    work["Previous_Port"] = (
        work.groupby("Analysis_IMO", dropna=True)[
            "Analysis_Port_Name"
        ].shift(1)
    )

    work["Previous_LOCODE"] = (
        work.groupby("Analysis_IMO", dropna=True)[
            "Analysis_LOCODE"
        ].shift(1)
    )

    work["Previous_Arrival_UTC"] = (
        work.groupby("Analysis_IMO", dropna=True)[
            arrival_col
        ].shift(1)
    )

    work["Previous_Departure_UTC"] = (
        work.groupby("Analysis_IMO", dropna=True)[
            departure_col
        ].shift(1)
    )

    work["Hours_Between_Previous_Departure_And_Arrival"] = (
        work[arrival_col] - work["Previous_Departure_UTC"]
    ).dt.total_seconds() / 3600

    work["Hours_Between_Consecutive_Arrivals"] = (
        work[arrival_col] - work["Previous_Arrival_UTC"]
    ).dt.total_seconds() / 3600

    work["Same_Consecutive_Port"] = (
        work["Analysis_Port_Name"].notna()
        & work["Previous_Port"].notna()
        & (
            work["Analysis_Port_Name"]
            == work["Previous_Port"]
        )
    )

    work["Same_Consecutive_LOCODE"] = (
        work["Analysis_LOCODE"].notna()
        & work["Previous_LOCODE"].notna()
        & (
            work["Analysis_LOCODE"]
            == work["Previous_LOCODE"]
        )
    )

    # A negative gap indicates a possible temporal overlap.
    work["Negative_Inter_Port_Gap"] = (
        work["Hours_Between_Previous_Departure_And_Arrival"] < 0
    )

    # A gap is not sailing time. It may include waiting or other operations.
    work["Gap_Interpretation"] = (
        "TIME_BETWEEN_RECORDED_PORT_CALLS_NOT_SAILING_TIME"
    )

    return work


# ============================================================
# 6. IDENTIFY OVERLAPPING PORT-STAY INTERVALS
# ============================================================

def find_overlaps(sequence_df, dataset_name, source):

    arrival_col = f"{source}_Arrival_UTC"
    departure_col = f"{source}_Departure_UTC"

    eligible = sequence_df[
        sequence_df["Sequence_Eligible"]
    ].copy()

    overlap_records = []

    for imo, group in eligible.groupby("Analysis_IMO"):

        group = group.sort_values(arrival_col)

        records = group.to_dict("records")

        # Compare calls belonging to the same vessel.
        # An overlap exists when the next arrival is earlier
        # than the previous call's departure.
        for i, j in combinations(range(len(records)), 2):

            first = records[i]
            second = records[j]

            first_arrival = first[arrival_col]
            first_departure = first[departure_col]

            second_arrival = second[arrival_col]
            second_departure = second[departure_col]

            # Since sorted by arrival, no later interval can
            # overlap once its arrival is after the first departure.
            if second_arrival >= first_departure:
                break

            overlap_start = max(
                first_arrival,
                second_arrival
            )

            overlap_end = min(
                first_departure,
                second_departure
            )

            overlap_hours = (
                overlap_end - overlap_start
            ).total_seconds() / 3600

            if overlap_hours <= 0:
                continue

            first_port = first.get("Analysis_Port_Name")
            second_port = second.get("Analysis_Port_Name")

            first_locode = first.get("Analysis_LOCODE")
            second_locode = second.get("Analysis_LOCODE")

            same_port = (
                pd.notna(first_port)
                and pd.notna(second_port)
                and first_port == second_port
            )

            same_locode = (
                pd.notna(first_locode)
                and pd.notna(second_locode)
                and first_locode == second_locode
            )

            if same_locode:
                overlap_type = "SAME_LOCODE_OVERLAP"
            elif same_port:
                overlap_type = "SAME_PORT_NAME_OVERLAP"
            else:
                overlap_type = "DIFFERENT_PORT_OVERLAP"

            overlap_records.append({

                "Dataset": dataset_name,
                "Timestamp_Source": source,
                "IMO": imo,

                "First_Call_Reference": first.get(
                    "Analysis_Call_Reference"
                ),

                "Second_Call_Reference": second.get(
                    "Analysis_Call_Reference"
                ),

                "First_Port": first_port,
                "Second_Port": second_port,

                "First_LOCODE": first_locode,
                "Second_LOCODE": second_locode,

                "First_Arrival_UTC": first_arrival,
                "First_Departure_UTC": first_departure,

                "Second_Arrival_UTC": second_arrival,
                "Second_Departure_UTC": second_departure,

                "Overlap_Start_UTC": overlap_start,
                "Overlap_End_UTC": overlap_end,

                "Overlap_Hours": round(overlap_hours, 3),

                "Overlap_Type": overlap_type,

                "First_Service": first.get("Analysis_Service"),
                "Second_Service": second.get("Analysis_Service"),

                "First_Import_Voyage": first.get(
                    "Analysis_Import_Voyage"
                ),

                "Second_Import_Voyage": second.get(
                    "Analysis_Import_Voyage"
                ),

                "First_Export_Voyage": first.get(
                    "Analysis_Export_Voyage"
                ),

                "Second_Export_Voyage": second.get(
                    "Analysis_Export_Voyage"
                ),

                "Investigation_Status": "FLAGGED_NOT_CORRECTED",
            })

    return pd.DataFrame(overlap_records)


# ============================================================
# 7. VOYAGE AND SERVICE CONSISTENCY
# ============================================================

def build_voyage_consistency(df, dataset_name, source):

    arrival_col = f"{source}_Arrival_UTC"
    departure_col = f"{source}_Departure_UTC"

    eligible = df[
        df["Analysis_IMO"].notna()
        & df[arrival_col].notna()
        & df[departure_col].notna()
        & (df[departure_col] >= df[arrival_col])
    ].copy()

    group_columns = ["Analysis_IMO"]

    summary = (
        eligible.groupby(group_columns)
        .agg(
            Record_Count=("Analysis_IMO", "size"),

            Unique_Port_Names=(
                "Analysis_Port_Name",
                "nunique"
            ),

            Unique_LOCODEs=(
                "Analysis_LOCODE",
                "nunique"
            ),

            Unique_Services=(
                "Analysis_Service",
                "nunique"
            ),

            Unique_Import_Voyages=(
                "Analysis_Import_Voyage",
                "nunique"
            ),

            Unique_Export_Voyages=(
                "Analysis_Export_Voyage",
                "nunique"
            ),

            First_Arrival_UTC=(arrival_col, "min"),

            Last_Arrival_UTC=(arrival_col, "max"),

            First_Departure_UTC=(departure_col, "min"),

            Last_Departure_UTC=(departure_col, "max"),
        )
        .reset_index()
    )

    summary = summary.rename(
        columns={"Analysis_IMO": "IMO"}
    )

    summary["Dataset"] = dataset_name
    summary["Timestamp_Source"] = source

    # These counts indicate diversity, not necessarily errors.
    summary["Multiple_Services_Flag"] = (
        summary["Unique_Services"] > 1
    )

    summary["Multiple_Import_Voyages_Flag"] = (
        summary["Unique_Import_Voyages"] > 1
    )

    summary["Multiple_Export_Voyages_Flag"] = (
        summary["Unique_Export_Voyages"] > 1
    )

    summary["Investigation_Status"] = "REVIEW_IF_REQUIRED"

    return summary


# ============================================================
# 8. REPEATED CONSECUTIVE PORT CALLS
# ============================================================

def build_repeated_port_flags(sequence_df, dataset_name, source):

    repeated = sequence_df[
        sequence_df["Same_Consecutive_Port"]
        | sequence_df["Same_Consecutive_LOCODE"]
    ].copy()

    if repeated.empty:
        return repeated

    repeated["Dataset"] = dataset_name
    repeated["Timestamp_Source"] = source

    repeated["Repeated_Call_Classification"] = np.where(
        repeated["Same_Consecutive_LOCODE"],
        "SAME_CONSECUTIVE_LOCODE",
        "SAME_PORT_NAME_DIFFERENT_OR_MISSING_LOCODE"
    )

    repeated["Investigation_Status"] = "FLAGGED_NOT_DELETED"

    return repeated


# ============================================================
# 9. PORT TRANSITION SUMMARY
# ============================================================

def build_transition_summary(sequence_df, dataset_name, source):

    valid = sequence_df[
        sequence_df["Sequence_Eligible"]
        & sequence_df["Previous_Port"].notna()
        & sequence_df["Analysis_Port_Name"].notna()
    ].copy()

    if valid.empty:
        return pd.DataFrame()

    summary = (
        valid.groupby(
            [
                "Previous_Port",
                "Analysis_Port_Name",
                "Previous_LOCODE",
                "Analysis_LOCODE",
            ],
            dropna=False
        )
        .agg(
            Transition_Count=("Analysis_IMO", "size"),
            Unique_Vessels=("Analysis_IMO", "nunique"),
            Median_Recorded_Gap_Hours=(
                "Hours_Between_Previous_Departure_And_Arrival",
                "median"
            ),
            Mean_Recorded_Gap_Hours=(
                "Hours_Between_Previous_Departure_And_Arrival",
                "mean"
            ),
        )
        .reset_index()
    )

    summary = summary.rename(
        columns={
            "Previous_Port": "From_Port",
            "Analysis_Port_Name": "To_Port",
            "Previous_LOCODE": "From_LOCODE",
            "Analysis_LOCODE": "To_LOCODE",
        }
    )

    summary["Dataset"] = dataset_name
    summary["Timestamp_Source"] = source

    summary["Gap_Interpretation"] = (
        "RECORDED_TIME_GAP_NOT_SAILING_TIME"
    )

    return summary


# ============================================================
# 10. DATASET QUALITY SUMMARY
# ============================================================

def build_quality_summary(df, dataset_name, source):

    arrival_col = f"{source}_Arrival_UTC"
    departure_col = f"{source}_Departure_UTC"

    complete_pairs = (
        df[arrival_col].notna()
        & df[departure_col].notna()
    )

    negative_stays = (
        complete_pairs
        & (df[departure_col] < df[arrival_col])
    )

    valid_stays = (
        complete_pairs
        & (df[departure_col] >= df[arrival_col])
    )

    durations = (
        df.loc[valid_stays, departure_col]
        - df.loc[valid_stays, arrival_col]
    ).dt.total_seconds() / 3600

    return {
        "Dataset": dataset_name,
        "Timestamp_Source": source,

        "Total_Records": len(df),

        "Unique_Vessels": df["Analysis_IMO"].nunique(),

        "Missing_IMO": df["Analysis_IMO"].isna().sum(),

        "Missing_Arrival": df[arrival_col].isna().sum(),

        "Missing_Departure": df[departure_col].isna().sum(),

        "Complete_Pairs": int(complete_pairs.sum()),

        "Negative_Port_Stays": int(negative_stays.sum()),

        "Valid_Nonnegative_Port_Stays": int(valid_stays.sum()),

        "Repeated_Consecutive_Port_Records": int(
            (
                (
                    df["Analysis_Port_Name"]
                    == df.groupby("Analysis_IMO")[
                        "Analysis_Port_Name"
                    ].shift(1)
                )
                & df["Analysis_Port_Name"].notna()
            ).sum()
        ),

        "Mean_Port_Stay_Hours": (
            round(durations.mean(), 3)
            if len(durations) else np.nan
        ),

        "Median_Port_Stay_Hours": (
            round(durations.median(), 3)
            if len(durations) else np.nan
        ),
    }


# ============================================================
# 11. MAIN EXECUTION
# ============================================================

def main():

    all_quality = []
    all_overlaps = []
    all_voyage_summaries = []
    all_repeated_calls = []
    all_transitions = []

    report_lines = []

    report_lines.append(
        "SCRIPT 09: VOYAGE CONSISTENCY AND VESSEL OVERLAP ANALYSIS"
    )

    report_lines.append("=" * 75)

    for dataset_name, file_path in INPUT_FILES.items():

        df, detected = load_and_prepare(
            dataset_name,
            file_path
        )

        for source in TIMESTAMP_SOURCES:

            print("\n" + "-" * 75)
            print(f"{dataset_name} | {source}")
            print("-" * 75)

            sequence = build_sequences(
                df,
                dataset_name,
                source
            )

            # ------------------------------------------------
            # 11A. Save chronological sequences
            # ------------------------------------------------

            sequence_file = (
                OUTPUT_TABLES
                / f"09_{dataset_name.lower()}_{source.lower()}_sequences.csv"
            )

            sequence.to_csv(
                sequence_file,
                index=False
            )

            # ------------------------------------------------
            # 11B. Find overlapping port-stay intervals
            # ------------------------------------------------

            overlaps = find_overlaps(
                sequence,
                dataset_name,
                source
            )

            if not overlaps.empty:
                all_overlaps.append(overlaps)

            # ------------------------------------------------
            # 11C. Voyage/service consistency
            # ------------------------------------------------

            voyage_summary = build_voyage_consistency(
                df,
                dataset_name,
                source
            )

            if not voyage_summary.empty:
                all_voyage_summaries.append(voyage_summary)

            # ------------------------------------------------
            # 11D. Repeated consecutive port calls
            # ------------------------------------------------

            repeated = build_repeated_port_flags(
                sequence,
                dataset_name,
                source
            )

            if not repeated.empty:
                all_repeated_calls.append(repeated)

            # ------------------------------------------------
            # 11E. Port transition summary
            # ------------------------------------------------

            transitions = build_transition_summary(
                sequence,
                dataset_name,
                source
            )

            if not transitions.empty:
                all_transitions.append(transitions)

            # ------------------------------------------------
            # 11F. Quality summary
            # ------------------------------------------------

            quality = build_quality_summary(
                df,
                dataset_name,
                source
            )

            all_quality.append(quality)

            # ------------------------------------------------
            # 11G. Terminal output
            # ------------------------------------------------

            print(
                f"Total records: {len(df):,}"
            )

            print(
                f"Vessels: {df['Analysis_IMO'].nunique():,}"
            )

            print(
                f"Eligible sequence records: "
                f"{sequence['Sequence_Eligible'].sum():,}"
            )

            print(
                f"Overlapping port-stay pairs: {len(overlaps):,}"
            )

            print(
                f"Repeated consecutive port calls: {len(repeated):,}"
            )

            print(
                f"Port transitions: {len(transitions):,}"
            )

            print(
                f"Voyage summary records: {len(voyage_summary):,}"
            )

            report_lines.extend([
                "",
                f"DATASET: {dataset_name}",
                f"TIMESTAMP SOURCE: {source}",
                f"Total records: {len(df):,}",
                f"Unique vessels: {df['Analysis_IMO'].nunique():,}",
                (
                    "Eligible sequence records: "
                    f"{sequence['Sequence_Eligible'].sum():,}"
                ),
                f"Overlapping port-stay pairs: {len(overlaps):,}",
                f"Repeated consecutive port calls: {len(repeated):,}",
                f"Port transitions: {len(transitions):,}",
            ])

    # ========================================================
    # 12. COMBINE AND SAVE OUTPUT TABLES
    # ========================================================

    def combine_and_save(dataframes, filename):

        if dataframes:
            result = pd.concat(
                dataframes,
                ignore_index=True
            )
        else:
            result = pd.DataFrame()

        result.to_csv(
            OUTPUT_TABLES / filename,
            index=False
        )

        return result

    quality_df = pd.DataFrame(all_quality)

    quality_df.to_csv(
        OUTPUT_TABLES / "09_timestamp_source_quality_summary.csv",
        index=False
    )

    overlaps_df = combine_and_save(
        all_overlaps,
        "09_vessel_port_stay_overlaps.csv"
    )

    voyage_df = combine_and_save(
        all_voyage_summaries,
        "09_voyage_service_consistency_summary.csv"
    )

    repeated_df = combine_and_save(
        all_repeated_calls,
        "09_repeated_consecutive_port_calls.csv"
    )

    transitions_df = combine_and_save(
        all_transitions,
        "09_port_transition_summary.csv"
    )

    # ========================================================
    # 13. FINAL REPORT
    # ========================================================

    report_lines.extend([
        "",
        "=" * 75,
        "FINAL OUTPUT SUMMARY",
        "=" * 75,
        f"Overlap records: {len(overlaps_df):,}",
        f"Voyage summary records: {len(voyage_df):,}",
        f"Repeated port-call records: {len(repeated_df):,}",
        f"Port transition records: {len(transitions_df):,}",
        "",
        "IMPORTANT INTERPRETATION NOTES:",
        "1. Actual, estimated and planned timestamps are analysed separately.",
        "2. Overlaps are flags for investigation, not automatic data errors.",
        "3. Repeated port calls are not automatically duplicates.",
        "4. Time gaps between port calls are not assumed to be sailing time.",
        "5. Port-call sequences do not establish actual vessel routes.",
        "6. No source records have been deleted or corrected.",
        "7. AIS or equivalent trajectory data is required to verify Hormuz transit.",
    ])

    report_text = "\n".join(report_lines)

    report_path = (
        OUTPUT_REPORTS
        / "09_voyage_consistency_and_overlap_report.txt"
    )

    report_path.write_text(
        report_text,
        encoding="utf-8"
    )

    # ========================================================
    # 14. FINAL TERMINAL SUMMARY
    # ========================================================

    print("\n" + "=" * 75)
    print("SCRIPT 09 COMPLETED")
    print("=" * 75)

    print("\nQUALITY SUMMARY")
    print(quality_df.to_string(index=False))

    print("\nOVERLAP CLASSIFICATION")

    if not overlaps_df.empty:
        print(
            overlaps_df["Overlap_Type"]
            .value_counts()
            .to_string()
        )
    else:
        print("No overlapping intervals found.")

    print("\nOUTPUT FILES")
    print(f"Tables: {OUTPUT_TABLES}")
    print(f"Report: {report_path}")

    print("\nNo original records were modified or deleted.")


if __name__ == "__main__":
    main()
