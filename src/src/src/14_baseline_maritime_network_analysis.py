
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# 1. PROJECT PATHS AND CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
SIMULATION_INPUT_DIR = PROJECT_ROOT / "data" / "simulation_inputs"

TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"
FIGURE_DIR = PROJECT_ROOT / "outputs" / "figures"
REPORT_DIR = PROJECT_ROOT / "outputs" / "reports"

for directory in [TABLE_DIR, FIGURE_DIR, REPORT_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

SCHEDULE_FILE = (
    PROCESSED_DIR / "13_final_consolidated_schedule.csv"
)

INDIVIDUAL_FILE = (
    PROCESSED_DIR / "13_final_consolidated_individual_calls.csv"
)

CORE_FILE = (
    SIMULATION_INPUT_DIR / "13_schedule_actual_baseline_core.csv"
)

CONSERVATIVE_FILE = (
    SIMULATION_INPUT_DIR / "13_schedule_actual_baseline_conservative.csv"
)

REPORT_FILE = REPORT_DIR / "14_baseline_maritime_network_report.txt"

TOP_N_PORTS = 20
TOP_N_VESSELS = 20

warnings.filterwarnings("ignore", category=FutureWarning)


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def load_csv(path):
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    df = pd.read_csv(path, low_memory=False)
    print(f"Loaded: {path.name} | Shape: {df.shape}")
    return df


def find_column(df, candidates, required=True):
    """
    Find a column using case-insensitive matching.
    """

    lookup = {str(col).strip().lower(): col for col in df.columns}

    for candidate in candidates:
        key = candidate.strip().lower()
        if key in lookup:
            return lookup[key]

    if required:
        raise KeyError(
            f"Could not find any of these columns: {candidates}\n"
            f"Available columns:\n{list(df.columns)}"
        )

    return None


def parse_datetime(series):
    """
    Parse timestamps and convert timezone-aware values to UTC.
    Naive timestamps are treated as UTC only if they are already
    stored in the UTC analysis columns produced by Script 13.
    """

    parsed = pd.to_datetime(series, errors="coerce", utc=True)
    return parsed


def prepare_dataset(df, dataset_name):
    """
    Standardise important columns without changing the source data.
    """

    df = df.copy()

    imo_col = find_column(
        df,
        ["IMO_Analysis", "IMO_Normalised", "IMO", "vesselIMO"],
        required=False
    )

    locode_col = find_column(
        df,
        [
            "LOCODE_Analysis",
            "UNLOCODE_Normalised",
            "UNLocationCode",
            "LOCODE"
        ],
        required=False
    )

    arrival_col = find_column(
        df,
        [
            "Actual_Arrival_UTC",
            "Actual Arrival UTC",
            "ARRI_ACT"
        ]
    )

    departure_col = find_column(
        df,
        [
            "Actual_Departure_UTC",
            "Actual Departure UTC",
            "DEPA_ACT"
        ]
    )

    vessel_col = find_column(
        df,
        ["Vessel Name", "vesselName", "Vessel_Name"],
        required=False
    )

    port_col = find_column(
        df,
        ["portName", "Port", "Port_Name", "port_name"],
        required=False
    )

    service_code_col = find_column(
        df,
        [
            "Carrier Service Code",
            "carrierServiceCode",
            "Service_Code",
            "serviceCode"
        ],
        required=False
    )

    service_name_col = find_column(
        df,
        [
            "Carrier Service Name",
            "carrierServiceName",
            "Service_Name",
            "serviceName"
        ],
        required=False
    )

    carrier_col = find_column(
        df,
        ["Carrier Code", "carrierCode", "Carrier_Code"],
        required=False
    )

    # Standardised analytical dataframe
    result = pd.DataFrame(index=df.index)

    result["Source_Record_Index"] = df.index
    result["Dataset"] = dataset_name

    result["IMO"] = (
        df[imo_col].astype("string").str.strip()
        if imo_col else pd.NA
    )

    result["LOCODE"] = (
        df[locode_col].astype("string").str.strip().str.upper()
        if locode_col else pd.NA
    )

    result["Vessel_Name"] = (
        df[vessel_col].astype("string").str.strip()
        if vessel_col else pd.NA
    )

    result["Port_Name"] = (
        df[port_col].astype("string").str.strip()
        if port_col else pd.NA
    )

    result["Service_Code"] = (
        df[service_code_col].astype("string").str.strip()
        if service_code_col else pd.NA
    )

    result["Service_Name"] = (
        df[service_name_col].astype("string").str.strip()
        if service_name_col else pd.NA
    )

    result["Carrier_Code"] = (
        df[carrier_col].astype("string").str.strip()
        if carrier_col else pd.NA
    )

    result["Arrival_UTC"] = parse_datetime(df[arrival_col])
    result["Departure_UTC"] = parse_datetime(df[departure_col])

    result["Port_Stay_Hours"] = (
        result["Departure_UTC"] - result["Arrival_UTC"]
    ).dt.total_seconds() / 3600

    result["Arrival_Month"] = (
        result["Arrival_UTC"].dt.to_period("M").astype("string")
    )

    result["Arrival_Week"] = (
        result["Arrival_UTC"].dt.to_period("W").astype("string")
    )

    result["Arrival_Year"] = result["Arrival_UTC"].dt.year

    # Retain only records with valid actual arrival/departure pairs.
    result["Valid_Actual_Record"] = (
        result["IMO"].notna()
        & result["LOCODE"].notna()
        & result["Arrival_UTC"].notna()
        & result["Departure_UTC"].notna()
        & (result["Port_Stay_Hours"] >= 0)
    )

    print(
        f"{dataset_name}: {len(result)} records | "
        f"Valid actual records: {result['Valid_Actual_Record'].sum()}"
    )

    return result


def save_table(df, filename):
    path = TABLE_DIR / filename
    df.to_csv(path, index=False)
    print(f"Saved table: {path.name}")


def save_figure(filename):
    path = FIGURE_DIR / filename
    plt.tight_layout()
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Saved figure: {path.name}")


def describe_numeric(series):
    clean = pd.to_numeric(series, errors="coerce").dropna()

    if clean.empty:
        return {
            "Count": 0,
            "Mean": np.nan,
            "Median": np.nan,
            "Std": np.nan,
            "Min": np.nan,
            "P25": np.nan,
            "P75": np.nan,
            "P90": np.nan,
            "P95": np.nan,
            "Max": np.nan
        }

    return {
        "Count": len(clean),
        "Mean": clean.mean(),
        "Median": clean.median(),
        "Std": clean.std(),
        "Min": clean.min(),
        "P25": clean.quantile(0.25),
        "P75": clean.quantile(0.75),
        "P90": clean.quantile(0.90),
        "P95": clean.quantile(0.95),
        "Max": clean.max()
    }


# ============================================================
# 3. LOAD DATASETS
# ============================================================

print("\n" + "=" * 70)
print("SCRIPT 14: BASELINE MARITIME NETWORK ANALYSIS")
print("=" * 70)

schedule_raw = load_csv(SCHEDULE_FILE)
individual_raw = load_csv(INDIVIDUAL_FILE)
core_raw = load_csv(CORE_FILE)
conservative_raw = load_csv(CONSERVATIVE_FILE)

schedule = prepare_dataset(
    schedule_raw, "Schedule"
)

individual = prepare_dataset(
    individual_raw, "Individual"
)

core = prepare_dataset(
    core_raw, "Schedule_Core"
)

conservative = prepare_dataset(
    conservative_raw, "Schedule_Conservative"
)


# ============================================================
# 4. FILTER VALID ACTUAL RECORDS
# ============================================================

schedule_valid = schedule[
    schedule["Valid_Actual_Record"]
].copy()

individual_valid = individual[
    individual["Valid_Actual_Record"]
].copy()

core_valid = core[
    core["Valid_Actual_Record"]
].copy()

conservative_valid = conservative[
    conservative["Valid_Actual_Record"]
].copy()

datasets = {
    "Schedule": schedule_valid,
    "Individual": individual_valid
}

print("\nValid actual baseline records:")
for name, data in datasets.items():
    print(f"{name}: {len(data)}")

print(f"Core baseline: {len(core_valid)}")
print(f"Conservative baseline: {len(conservative_valid)}")


# ============================================================
# 5. OVERALL DATASET SUMMARY
# ============================================================

summary_rows = []

for name, data in datasets.items():

    summary_rows.append({
        "Dataset": name,
        "Total_Records": len(
            schedule if name == "Schedule" else individual
        ),
        "Valid_Actual_Records": len(data),
        "Unique_Vessels": data["IMO"].nunique(),
        "Unique_Ports": data["LOCODE"].nunique(),
        "Unique_Vessel_Names": data["Vessel_Name"].nunique(),
        "Unique_Service_Codes": data["Service_Code"].nunique(),
        "Mean_Port_Stay_Hours": data["Port_Stay_Hours"].mean(),
        "Median_Port_Stay_Hours": data["Port_Stay_Hours"].median()
    })

dataset_summary = pd.DataFrame(summary_rows)

save_table(
    dataset_summary,
    "14_overall_dataset_summary.csv"
)


# ============================================================
# 6. PORT-CALL FREQUENCY
# ============================================================

def port_activity(data, dataset_name):

    result = (
        data.groupby("LOCODE", dropna=False)
        .agg(
            Port_Call_Count=("LOCODE", "size"),
            Unique_Vessels=("IMO", "nunique"),
            Mean_Port_Stay_Hours=("Port_Stay_Hours", "mean"),
            Median_Port_Stay_Hours=("Port_Stay_Hours", "median"),
            First_Recorded_Arrival=("Arrival_UTC", "min"),
            Last_Recorded_Departure=("Departure_UTC", "max")
        )
        .reset_index()
        .sort_values("Port_Call_Count", ascending=False)
    )

    result.insert(0, "Dataset", dataset_name)
    return result


schedule_ports = port_activity(schedule_valid, "Schedule")
individual_ports = port_activity(individual_valid, "Individual")

save_table(
    schedule_ports,
    "14_schedule_port_activity.csv"
)

save_table(
    individual_ports,
    "14_individual_port_activity.csv"
)


# Port-call frequency plot
for name, data in datasets.items():

    frequency = (
        data["LOCODE"]
        .value_counts()
        .head(TOP_N_PORTS)
        .sort_values()
    )

    plt.figure(figsize=(11, 7))
    frequency.plot(kind="barh")
    plt.xlabel("Number of actual port calls")
    plt.ylabel("UN/LOCODE")
    plt.title(f"Top {TOP_N_PORTS} Ports by Actual Port Calls - {name}")

    save_figure(f"14_{name.lower()}_top_ports.png")


# ============================================================
# 7. VESSEL ACTIVITY
# ============================================================

def vessel_activity(data, dataset_name):

    result = (
        data.groupby("IMO", dropna=False)
        .agg(
            Vessel_Name=("Vessel_Name", "first"),
            Port_Call_Count=("IMO", "size"),
            Unique_Ports=("LOCODE", "nunique"),
            Unique_Services=("Service_Code", "nunique"),
            Mean_Port_Stay_Hours=("Port_Stay_Hours", "mean"),
            Median_Port_Stay_Hours=("Port_Stay_Hours", "median"),
            First_Recorded_Arrival=("Arrival_UTC", "min"),
            Last_Recorded_Departure=("Departure_UTC", "max")
        )
        .reset_index()
        .sort_values("Port_Call_Count", ascending=False)
    )

    result.insert(0, "Dataset", dataset_name)
    return result


schedule_vessels = vessel_activity(
    schedule_valid, "Schedule"
)

individual_vessels = vessel_activity(
    individual_valid, "Individual"
)

save_table(
    schedule_vessels,
    "14_schedule_vessel_activity.csv"
)

save_table(
    individual_vessels,
    "14_individual_vessel_activity.csv"
)


# ============================================================
# 8. PORT-STAY DISTRIBUTION
# ============================================================

def port_stay_statistics(data, dataset_name):

    result = (
        data.groupby("LOCODE")["Port_Stay_Hours"]
        .apply(lambda x: pd.Series(describe_numeric(x)))
        .unstack()
        .reset_index()
    )

    result.insert(0, "Dataset", dataset_name)
    return result


schedule_stays = port_stay_statistics(
    schedule_valid, "Schedule"
)

individual_stays = port_stay_statistics(
    individual_valid, "Individual"
)

save_table(
    schedule_stays,
    "14_schedule_port_stay_statistics.csv"
)

save_table(
    individual_stays,
    "14_individual_port_stay_statistics.csv"
)


for name, data in datasets.items():

    values = data["Port_Stay_Hours"].dropna()

    plt.figure(figsize=(10, 6))
    plt.hist(values, bins=30, edgecolor="black")
    plt.xlabel("Port stay (hours)")
    plt.ylabel("Number of port calls")
    plt.title(f"Port Stay Distribution - {name}")

    save_figure(f"14_{name.lower()}_port_stay_distribution.png")


# ============================================================
# 9. VESSEL PORT-CALL SEQUENCES
# ============================================================

def build_sequences(data, dataset_name):

    ordered = data.sort_values(
        ["IMO", "Arrival_UTC", "Departure_UTC"]
    ).copy()

    ordered["Previous_LOCODE"] = (
        ordered.groupby("IMO")["LOCODE"].shift(1)
    )

    ordered["Previous_Port_Name"] = (
        ordered.groupby("IMO")["Port_Name"].shift(1)
    )

    ordered["Previous_Arrival_UTC"] = (
        ordered.groupby("IMO")["Arrival_UTC"].shift(1)
    )

    ordered["Previous_Departure_UTC"] = (
        ordered.groupby("IMO")["Departure_UTC"].shift(1)
    )

    ordered["Next_LOCODE"] = (
        ordered.groupby("IMO")["LOCODE"].shift(-1)
    )

    ordered["Inter_Port_Elapsed_Hours"] = (
        ordered["Arrival_UTC"] -
        ordered["Previous_Departure_UTC"]
    ).dt.total_seconds() / 3600

    ordered["Arrival_To_Arrival_Hours"] = (
        ordered["Arrival_UTC"] -
        ordered["Previous_Arrival_UTC"]
    ).dt.total_seconds() / 3600

    ordered["Same_LOCODE_As_Previous"] = (
        ordered["LOCODE"] == ordered["Previous_LOCODE"]
    )

    ordered["Negative_Inter_Port_Elapsed"] = (
        ordered["Inter_Port_Elapsed_Hours"] < 0
    )

    ordered["Dataset"] = dataset_name

    return ordered


schedule_sequences = build_sequences(
    schedule_valid, "Schedule"
)

individual_sequences = build_sequences(
    individual_valid, "Individual"
)

save_table(
    schedule_sequences,
    "14_schedule_vessel_sequences.csv"
)

save_table(
    individual_sequences,
    "14_individual_vessel_sequences.csv"
)


# ============================================================
# 10. INTER-PORT ELAPSED-TIME ANALYSIS
# ============================================================

def inter_port_statistics(data, dataset_name):

    transitions = data[
        data["Previous_LOCODE"].notna()
        & data["Inter_Port_Elapsed_Hours"].notna()
    ].copy()

    transitions["Port_Transition"] = (
        transitions["Previous_LOCODE"].astype(str)
        + " -> "
        + transitions["LOCODE"].astype(str)
    )

    result = (
        transitions.groupby("Port_Transition")
        ["Inter_Port_Elapsed_Hours"]
        .apply(lambda x: pd.Series(describe_numeric(x)))
        .unstack()
        .reset_index()
    )

    result.insert(0, "Dataset", dataset_name)

    return transitions, result


schedule_transitions, schedule_transition_stats = (
    inter_port_statistics(schedule_sequences, "Schedule")
)

individual_transitions, individual_transition_stats = (
    inter_port_statistics(individual_sequences, "Individual")
)

save_table(
    schedule_transitions,
    "14_schedule_inter_port_transitions.csv"
)

save_table(
    individual_transitions,
    "14_individual_inter_port_transitions.csv"
)

save_table(
    schedule_transition_stats,
    "14_schedule_transition_statistics.csv"
)

save_table(
    individual_transition_stats,
    "14_individual_transition_statistics.csv"
)


for name, transitions in [
    ("Schedule", schedule_transitions),
    ("Individual", individual_transitions)
]:

    values = transitions["Inter_Port_Elapsed_Hours"].dropna()
    values = values[values >= 0]

    plt.figure(figsize=(10, 6))
    plt.hist(values, bins=30, edgecolor="black")
    plt.xlabel("Inter-port elapsed time (hours)")
    plt.ylabel("Number of transitions")
    plt.title(f"Inter-Port Elapsed-Time Distribution - {name}")

    save_figure(f"14_{name.lower()}_inter_port_elapsed.png")


# ============================================================
# 11. MONTHLY AND WEEKLY ACTIVITY
# ============================================================

def temporal_activity(data, dataset_name, period_column):

    result = (
        data.groupby(period_column)
        .agg(
            Port_Call_Count=("IMO", "size"),
            Unique_Vessels=("IMO", "nunique"),
            Unique_Ports=("LOCODE", "nunique"),
            Mean_Port_Stay_Hours=("Port_Stay_Hours", "mean")
        )
        .reset_index()
        .sort_values(period_column)
    )

    result.insert(0, "Dataset", dataset_name)
    return result


for name, data in datasets.items():

    monthly = temporal_activity(
        data, name, "Arrival_Month"
    )

    weekly = temporal_activity(
        data, name, "Arrival_Week"
    )

    save_table(
        monthly,
        f"14_{name.lower()}_monthly_activity.csv"
    )

    save_table(
        weekly,
        f"14_{name.lower()}_weekly_activity.csv"
    )

    plt.figure(figsize=(12, 6))
    plt.plot(
        monthly["Arrival_Month"],
        monthly["Port_Call_Count"],
        marker="o"
    )

    plt.xlabel("Month")
    plt.ylabel("Actual port calls")
    plt.title(f"Monthly Actual Port-Call Activity - {name}")
    plt.xticks(rotation=45)

    save_figure(f"14_{name.lower()}_monthly_activity.png")


# ============================================================
# 12. SERVICE-LEVEL ACTIVITY
# ============================================================

def service_activity(data, dataset_name):

    service_data = data[
        data["Service_Code"].notna()
    ].copy()

    if service_data.empty:
        return pd.DataFrame()

    result = (
        service_data.groupby(
            ["Service_Code", "Service_Name"],
            dropna=False
        )
        .agg(
            Port_Call_Count=("IMO", "size"),
            Unique_Vessels=("IMO", "nunique"),
            Unique_Ports=("LOCODE", "nunique"),
            Mean_Port_Stay_Hours=("Port_Stay_Hours", "mean"),
            Median_Port_Stay_Hours=("Port_Stay_Hours", "median")
        )
        .reset_index()
        .sort_values("Port_Call_Count", ascending=False)
    )

    result.insert(0, "Dataset", dataset_name)
    return result


schedule_services = service_activity(
    schedule_valid, "Schedule"
)

individual_services = service_activity(
    individual_valid, "Individual"
)

save_table(
    schedule_services,
    "14_schedule_service_activity.csv"
)

save_table(
    individual_services,
    "14_individual_service_activity.csv"
)


# ============================================================
# 13. CORE VS CONSERVATIVE BASELINE SENSITIVITY
# ============================================================

def baseline_comparison(data, name):

    return {
        "Baseline": name,
        "Records": len(data),
        "Unique_Vessels": data["IMO"].nunique(),
        "Unique_Ports": data["LOCODE"].nunique(),
        "Unique_Services": data["Service_Code"].nunique(),
        "Mean_Port_Stay_Hours": data["Port_Stay_Hours"].mean(),
        "Median_Port_Stay_Hours": data["Port_Stay_Hours"].median(),
        "P90_Port_Stay_Hours": data["Port_Stay_Hours"].quantile(0.90)
    }


sensitivity = pd.DataFrame([
    baseline_comparison(core_valid, "Schedule_Core"),
    baseline_comparison(
        conservative_valid, "Schedule_Conservative"
    )
])

save_table(
    sensitivity,
    "14_core_vs_conservative_baseline.csv"
)


# ============================================================
# 14. DATA QUALITY AND SEQUENCE DIAGNOSTICS
# ============================================================

diagnostic_rows = []

for name, original, valid, sequences in [
    (
        "Schedule",
        schedule,
        schedule_valid,
        schedule_sequences
    ),
    (
        "Individual",
        individual,
        individual_valid,
        individual_sequences
    )
]:

    diagnostic_rows.append({
        "Dataset": name,
        "Total_Records": len(original),
        "Valid_Actual_Records": len(valid),
        "Excluded_From_Actual_Analysis": len(original) - len(valid),
        "Missing_IMO_In_Valid_Set": valid["IMO"].isna().sum(),
        "Missing_LOCODE_In_Valid_Set": valid["LOCODE"].isna().sum(),
        "Negative_Port_Stays": (
            original["Port_Stay_Hours"] < 0
        ).sum(),
        "Same_LOCODE_Consecutive_Records": (
            sequences["Same_LOCODE_As_Previous"].fillna(False).sum()
        ),
        "Negative_Inter_Port_Elapsed": (
            sequences["Negative_Inter_Port_Elapsed"].fillna(False).sum()
        ),
        "Transition_Count": (
            sequences["Previous_LOCODE"].notna().sum()
        )
    })

diagnostics = pd.DataFrame(diagnostic_rows)

save_table(
    diagnostics,
    "14_baseline_diagnostics.csv"
)


# ============================================================
# 15. GENERATE TEXT REPORT
# ============================================================

with open(REPORT_FILE, "w", encoding="utf-8") as report:

    report.write("=" * 75 + "\n")
    report.write("SCRIPT 14: BASELINE MARITIME NETWORK ANALYSIS\n")
    report.write("=" * 75 + "\n\n")

    report.write("1. OVERALL DATASET SUMMARY\n")
    report.write("-" * 75 + "\n")
    report.write(dataset_summary.to_string(index=False))
    report.write("\n\n")

    report.write("2. BASELINE DIAGNOSTICS\n")
    report.write("-" * 75 + "\n")
    report.write(diagnostics.to_string(index=False))
    report.write("\n\n")

    report.write("3. CORE VS CONSERVATIVE BASELINE\n")
    report.write("-" * 75 + "\n")
    report.write(sensitivity.to_string(index=False))
    report.write("\n\n")

    report.write("4. TOP PORTS - SCHEDULE DATASET\n")
    report.write("-" * 75 + "\n")
    report.write(schedule_ports.head(TOP_N_PORTS).to_string(index=False))
    report.write("\n\n")

    report.write("5. TOP PORTS - INDIVIDUAL DATASET\n")
    report.write("-" * 75 + "\n")
    report.write(individual_ports.head(TOP_N_PORTS).to_string(index=False))
    report.write("\n\n")

    report.write("6. TOP VESSELS - SCHEDULE DATASET\n")
    report.write("-" * 75 + "\n")
    report.write(schedule_vessels.head(TOP_N_VESSELS).to_string(index=False))
    report.write("\n\n")

    report.write("7. TOP VESSELS - INDIVIDUAL DATASET\n")
    report.write("-" * 75 + "\n")
    report.write(individual_vessels.head(TOP_N_VESSELS).to_string(index=False))
    report.write("\n\n")

    report.write("8. INTERPRETATION AND LIMITATIONS\n")
    report.write("-" * 75 + "\n")

    report.write(
        "A. Schedule and individual vessel-call datasets are analysed "
        "separately.\n"
    )

    report.write(
        "B. Actual arrival and departure timestamps are used for "
        "actual baseline analysis.\n"
    )

    report.write(
        "C. Negative port stays are excluded from valid actual records.\n"
    )

    report.write(
        "D. Inter-port elapsed time is calculated from previous actual "
        "departure to next actual arrival. It is not necessarily pure "
        "sailing time.\n"
    )

    report.write(
        "E. Repeated consecutive LOCODEs are retained. They may reflect "
        "terminal-level or operational call representations.\n"
    )

    report.write(
        "F. Port-call sequences do not prove that a vessel transited "
        "the Strait of Hormuz. AIS trajectory evidence is required.\n"
    )

    report.write(
        "G. The core and conservative baselines are compared as a "
        "sensitivity analysis. Candidate records are not silently "
        "deleted from the original datasets.\n"
    )

    report.write(
        "H. These descriptive statistics are preliminary calibration "
        "inputs, not yet validated simulation parameters.\n"
    )

print("\n" + "=" * 70)
print("SCRIPT 14 COMPLETED SUCCESSFULLY")
print("=" * 70)

print("\nKey outputs:")
print(f"Tables:  {TABLE_DIR}")
print(f"Figures: {FIGURE_DIR}")
print(f"Report:  {REPORT_FILE}")

print("\nBaseline records:")
print(f"Schedule: {len(schedule_valid)}")
print(f"Individual: {len(individual_valid)}")
print(f"Core: {len(core_valid)}")
print(f"Conservative: {len(conservative_valid)}")
