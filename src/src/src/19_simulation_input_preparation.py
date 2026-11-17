
from pathlib import Path
import pandas as pd
import numpy as np

# ============================================================
# SCRIPT 19: SIMULATION INPUT PREPARATION
# Primary baseline: Conservative Schedule Dataset
# Core Schedule: Sensitivity dataset
# Individual Calls: Separate comparison dataset
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

INPUT_DIR = ROOT / "data" / "simulation_inputs"
PROCESSED_DIR = ROOT / "data" / "processed"
TABLE_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

for folder in [INPUT_DIR, TABLE_DIR, REPORT_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

SCHEDULE_FILE = INPUT_DIR / "13_schedule_actual_baseline_conservative.csv"
CORE_FILE = INPUT_DIR / "13_schedule_actual_baseline_core.csv"
INDIVIDUAL_FILE = INPUT_DIR / "13_individual_actual_baseline.csv"

VESSEL_MASTER_FILE = PROCESSED_DIR / "06_vessel_master_by_imo.csv"
PORT_LOOKUP_FILE = PROCESSED_DIR / "06_unique_port_lookup.csv"
PORT_VALIDATION_FILE = PROCESSED_DIR / "18F_final_port_validation_register.csv"


def normalize_id(series):
    """Normalize identifiers without converting missing values to strings."""
    return (
        series.astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.upper()
    )


def load_csv(path):
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return pd.read_csv(path, low_memory=False)


def parse_utc(series):
    return pd.to_datetime(series, errors="coerce", utc=True)


# ------------------------------------------------------------
# 1. LOAD DATA
# ------------------------------------------------------------

print("\n[1/8] Loading datasets...")

schedule = load_csv(SCHEDULE_FILE)
core = load_csv(CORE_FILE)
individual = load_csv(INDIVIDUAL_FILE)
vessel_master = load_csv(VESSEL_MASTER_FILE)
port_lookup = load_csv(PORT_LOOKUP_FILE)
port_validation = load_csv(PORT_VALIDATION_FILE)

required_schedule = [
    "IMO_Normalised",
    "UNLOCODE_Normalised",
    "Vessel Name",
    "Port",
    "Actual_Arrival_UTC",
    "Actual_Departure_UTC",
    "Actual_Stay_Hours",
    "Actual_Complete",
    "Actual_Valid_Chronology",
]

missing = [c for c in required_schedule if c not in schedule.columns]
if missing:
    raise ValueError(f"Schedule dataset missing required columns: {missing}")

# Confirm that the primary dataset contains complete actual calls.
schedule["Actual_Arrival_UTC"] = parse_utc(
    schedule["Actual_Arrival_UTC"]
)
schedule["Actual_Departure_UTC"] = parse_utc(
    schedule["Actual_Departure_UTC"]
)

schedule["IMO_Normalised"] = normalize_id(schedule["IMO_Normalised"])
schedule["UNLOCODE_Normalised"] = normalize_id(
    schedule["UNLOCODE_Normalised"]
)

schedule = schedule[
    schedule["Actual_Arrival_UTC"].notna()
    & schedule["Actual_Departure_UTC"].notna()
    & schedule["Actual_Valid_Chronology"].astype(str).str.lower().eq("true")
].copy()

if schedule.empty:
    raise ValueError("No valid actual schedule calls remain.")

schedule["Actual_Stay_Hours"] = pd.to_numeric(
    schedule["Actual_Stay_Hours"], errors="coerce"
)

# Stable source identifier for traceability.
schedule["Simulation_Record_ID"] = (
    "SCH_" + schedule["Schedule_Source_Row"].astype(str)
)

print("Primary schedule records:", len(schedule))


# ------------------------------------------------------------
# 2. HISTORICAL ARRIVAL SCHEDULE
# ------------------------------------------------------------

print("\n[2/8] Preparing historical schedule...")

historical_columns = [
    "Simulation_Record_ID",
    "IMO_Normalised",
    "Vessel Name",
    "UNLOCODE_Normalised",
    "Port",
    "countryCode",
    "countryName",
    "Carrier Code",
    "Carrier Service Code",
    "Import Voyage Number",
    "Export Voyage Number",
    "Actual_Arrival_UTC",
    "Actual_Departure_UTC",
    "Actual_Stay_Hours",
    "Schedule_Source_Row",
    "Source_Port",
]

historical_columns = [
    c for c in historical_columns if c in schedule.columns
]

historical_schedule = schedule[historical_columns].copy()

historical_schedule = historical_schedule.sort_values(
    ["Actual_Arrival_UTC", "IMO_Normalised"]
)

historical_schedule.to_csv(
    INPUT_DIR / "19_historical_arrival_schedule.csv",
    index=False
)


# ------------------------------------------------------------
# 3. VESSEL PARAMETERS
# ------------------------------------------------------------

print("\n[3/8] Preparing vessel parameters...")

vessel_master["IMO_Normalised"] = normalize_id(
    vessel_master["IMO_Normalised"]
)

vessel_parameters = (
    schedule.groupby("IMO_Normalised", dropna=False)
    .agg(
        observed_vessel_name=("Vessel Name", "first"),
        observed_call_count=("Simulation_Record_ID", "count"),
        observed_port_count=("UNLOCODE_Normalised", "nunique"),
        first_observed_arrival=("Actual_Arrival_UTC", "min"),
        last_observed_arrival=("Actual_Arrival_UTC", "max"),
    )
    .reset_index()
)

master_columns = [
    "IMO_Normalised",
    "Master_carrierVesselCode",
    "Master_vesselName",
    "Master_vesselCallSign",
    "Master_vesselFlagCode",
    "Vessel_Master_Record_Count",
]

master_columns = [
    c for c in master_columns if c in vessel_master.columns
]

vessel_parameters = vessel_parameters.merge(
    vessel_master[master_columns].drop_duplicates("IMO_Normalised"),
    on="IMO_Normalised",
    how="left",
    validate="one_to_one"
)

vessel_parameters["Vessel_Identity_Source"] = "Observed schedule + vessel master"
vessel_parameters["Vessel_Capacity_Status"] = "NOT_AVAILABLE"
vessel_parameters["Vessel_Length_Status"] = "NOT_AVAILABLE"
vessel_parameters["Vessel_Type_Status"] = "NOT_AVAILABLE"

vessel_parameters.to_csv(
    INPUT_DIR / "19_vessel_parameters.csv",
    index=False
)


# ------------------------------------------------------------
# 4. PORT PARAMETERS
# ------------------------------------------------------------

print("\n[4/8] Preparing port parameters...")

port_lookup["UNLOCODE_Normalised"] = normalize_id(
    port_lookup["UNLOCODE_Normalised"]
)

port_summary = (
    schedule.groupby("UNLOCODE_Normalised", dropna=False)
    .agg(
        observed_port_name=("Port", "first"),
        observed_call_count=("Simulation_Record_ID", "count"),
        observed_vessel_count=("IMO_Normalised", "nunique"),
        first_observed_arrival=("Actual_Arrival_UTC", "min"),
        last_observed_arrival=("Actual_Arrival_UTC", "max"),
    )
    .reset_index()
)

lookup_columns = [
    "UNLOCODE_Normalised",
    "countryCode",
    "countryName",
    "cityName",
    "portName",
    "carrierCityGeoID",
]

lookup_columns = [
    c for c in lookup_columns if c in port_lookup.columns
]

port_parameters = port_summary.merge(
    port_lookup[lookup_columns].drop_duplicates(
        "UNLOCODE_Normalised"
    ),
    on="UNLOCODE_Normalised",
    how="left",
    validate="one_to_one"
)

# The 18F register is a review register, not a verified port master.
port_validation["UN_LOCODE"] = normalize_id(
    port_validation["UN_LOCODE"]
)

validation_columns = [
    "UN_LOCODE",
    "18F_Validation_Status",
    "18E_Original_Validation_Status",
    "Validation_Priority",
    "18D_Geographic_Zone",
]

validation_columns = [
    c for c in validation_columns if c in port_validation.columns
]

validation_subset = port_validation[validation_columns].drop_duplicates(
    "UN_LOCODE"
)

port_parameters = port_parameters.merge(
    validation_subset,
    left_on="UNLOCODE_Normalised",
    right_on="UN_LOCODE",
    how="left"
)

port_parameters["Port_Identity_Source"] = (
    "Observed carrier schedule and port lookup"
)
port_parameters["Coordinates_Status"] = "NOT_ESTABLISHED_BY_SCRIPT"
port_parameters["Port_Capacity_Status"] = "NOT_AVAILABLE"
port_parameters["Berth_Capacity_Status"] = "NOT_AVAILABLE"
port_parameters["Hormuz_Transit_Status"] = "NOT_CONFIRMED"

port_parameters.to_csv(
    INPUT_DIR / "19_port_parameters.csv",
    index=False
)


# ------------------------------------------------------------
# 5. EMPIRICAL PORT SERVICE PARAMETERS
# ------------------------------------------------------------

print("\n[5/8] Estimating port service-time distributions...")

valid_stays = schedule[
    schedule["Actual_Stay_Hours"].notna()
    & (schedule["Actual_Stay_Hours"] >= 0)
].copy()

port_service = (
    valid_stays.groupby("UNLOCODE_Normalised")
    ["Actual_Stay_Hours"]
    .agg(
        sample_size="count",
        mean_stay_hours="mean",
        median_stay_hours="median",
        std_stay_hours="std",
        min_stay_hours="min",
        max_stay_hours="max",
    )
    .reset_index()
)

p90 = (
    valid_stays.groupby("UNLOCODE_Normalised")
    ["Actual_Stay_Hours"]
    .quantile(0.90)
    .rename("p90_stay_hours")
    .reset_index()
)

port_service = port_service.merge(
    p90, on="UNLOCODE_Normalised", how="left"
)

port_service["Parameter_Source"] = "Observed actual port-call timestamps"
port_service["Interpretation"] = (
    "Observed port stay; not pure berth processing time"
)
port_service["Distribution_Assumption"] = (
    "Empirical distribution; no parametric fit imposed"
)

port_service.to_csv(
    INPUT_DIR / "19_port_service_parameters.csv",
    index=False
)


# ------------------------------------------------------------
# 6. INTER-PORT ELAPSED TIME PARAMETERS
# ------------------------------------------------------------

print("\n[6/8] Estimating inter-port elapsed times...")

ordered = schedule.sort_values(
    ["IMO_Normalised", "Actual_Arrival_UTC"]
).copy()

ordered["Previous_Port"] = (
    ordered.groupby("IMO_Normalised")["UNLOCODE_Normalised"].shift(1)
)

ordered["Previous_Departure_UTC"] = (
    ordered.groupby("IMO_Normalised")["Actual_Departure_UTC"].shift(1)
)

ordered["Elapsed_Hours_Between_Calls"] = (
    ordered["Actual_Arrival_UTC"]
    - ordered["Previous_Departure_UTC"]
).dt.total_seconds() / 3600

transitions = ordered[
    ordered["Previous_Port"].notna()
    & ordered["Previous_Departure_UTC"].notna()
    & ordered["Elapsed_Hours_Between_Calls"].notna()
    & (ordered["Elapsed_Hours_Between_Calls"] >= 0)
    & (
        ordered["Previous_Port"]
        != ordered["UNLOCODE_Normalised"]
    )
].copy()

transitions = transitions.rename(
    columns={"UNLOCODE_Normalised": "Next_Port"}
)

transitions["Time_Interpretation"] = (
    "Departure-to-next-arrival elapsed time; "
    "includes sailing, waiting and unobserved operations"
)

transitions.to_csv(
    INPUT_DIR / "19_observed_interport_transitions.csv",
    index=False
)

interport_parameters = (
    transitions.groupby(["Previous_Port", "Next_Port"])
    ["Elapsed_Hours_Between_Calls"]
    .agg(
        sample_size="count",
        mean_elapsed_hours="mean",
        median_elapsed_hours="median",
        std_elapsed_hours="std",
        min_elapsed_hours="min",
        max_elapsed_hours="max",
    )
    .reset_index()
)

interport_p90 = (
    transitions.groupby(["Previous_Port", "Next_Port"])
    ["Elapsed_Hours_Between_Calls"]
    .quantile(0.90)
    .rename("p90_elapsed_hours")
    .reset_index()
)

interport_parameters = interport_parameters.merge(
    interport_p90,
    on=["Previous_Port", "Next_Port"],
    how="left"
)

interport_parameters["Parameter_Source"] = (
    "Derived from observed schedule timestamps"
)
interport_parameters["Interpretation"] = (
    "Inter-port elapsed time, not sailing time"
)

interport_parameters.to_csv(
    INPUT_DIR / "19_interport_time_parameters.csv",
    index=False
)


# ------------------------------------------------------------
# 7. DISRUPTION SCENARIO CONFIGURATION
# ------------------------------------------------------------

print("\n[7/8] Creating experimental disruption scenarios...")

scenarios = pd.DataFrame([
    {
        "Scenario_ID": "BASELINE",
        "Scenario_Name": "Normal operation",
        "Capacity_Reduction_Percent": 0,
        "Disruption_Duration_Hours": 0,
        "Scenario_Status": "REFERENCE",
        "Parameter_Provenance": "No disruption imposed",
    },
    {
        "Scenario_ID": "DISRUPTION_25",
        "Scenario_Name": "25 percent capacity reduction",
        "Capacity_Reduction_Percent": 25,
        "Disruption_Duration_Hours": 72,
        "Scenario_Status": "HYPOTHETICAL",
        "Parameter_Provenance": "Experimental assumption",
    },
    {
        "Scenario_ID": "DISRUPTION_50",
        "Scenario_Name": "50 percent capacity reduction",
        "Capacity_Reduction_Percent": 50,
        "Disruption_Duration_Hours": 72,
        "Scenario_Status": "HYPOTHETICAL",
        "Parameter_Provenance": "Experimental assumption",
    },
    {
        "Scenario_ID": "DISRUPTION_75",
        "Scenario_Name": "75 percent capacity reduction",
        "Capacity_Reduction_Percent": 75,
        "Disruption_Duration_Hours": 72,
        "Scenario_Status": "HYPOTHETICAL",
        "Parameter_Provenance": "Experimental assumption",
    },
    {
        "Scenario_ID": "FULL_CLOSURE",
        "Scenario_Name": "Complete closure",
        "Capacity_Reduction_Percent": 100,
        "Disruption_Duration_Hours": 72,
        "Scenario_Status": "HYPOTHETICAL",
        "Parameter_Provenance": "Experimental assumption",
    },
])

scenarios["Affected_Corridor"] = (
    "To be specified after corridor and network definition"
)

scenarios.to_csv(
    INPUT_DIR / "19_disruption_scenarios.csv",
    index=False
)


# ------------------------------------------------------------
# 8. SEPARATE DATASET COMPARISON AND VALIDATION REPORT
# ------------------------------------------------------------

print("\n[8/8] Preparing comparison and validation reports...")

# Do not merge this dataset into the Schedule population.
individual["IMO_Normalised"] = normalize_id(
    individual["IMO_Normalised"]
)
individual["UNLOCODE_Normalised"] = normalize_id(
    individual["UNLOCODE_Normalised"]
)

individual["Actual_Arrival_UTC"] = parse_utc(
    individual["Actual_Arrival_UTC"]
)
individual["Actual_Departure_UTC"] = parse_utc(
    individual["Actual_Departure_UTC"]
)

individual_comparison = individual[
    [
        "IMO_Normalised",
        "vesselName",
        "UNLOCODE_Normalised",
        "portName",
        "Actual_Arrival_UTC",
        "Actual_Departure_UTC",
        "Actual_Stay_Hours",
        "transportCallReference",
        "Individual_Source_File",
    ]
].copy()

individual_comparison.to_csv(
    INPUT_DIR / "19_individual_comparison_schedule.csv",
    index=False
)

core["Actual_Arrival_UTC"] = parse_utc(core["Actual_Arrival_UTC"])
core["Actual_Departure_UTC"] = parse_utc(core["Actual_Departure_UTC"])

dataset_comparison = pd.DataFrame([
    {
        "Dataset": "Schedule Conservative",
        "Records": len(schedule),
        "Unique_Vessels": schedule["IMO_Normalised"].nunique(),
        "Unique_Ports": schedule["UNLOCODE_Normalised"].nunique(),
        "Role": "Primary historical baseline",
    },
    {
        "Dataset": "Schedule Core",
        "Records": len(core),
        "Unique_Vessels": core["IMO_Normalised"].nunique(),
        "Unique_Ports": core["UNLOCODE_Normalised"].nunique(),
        "Role": "Sensitivity comparison",
    },
    {
        "Dataset": "Individual Calls",
        "Records": len(individual),
        "Unique_Vessels": individual["IMO_Normalised"].nunique(),
        "Unique_Ports": individual["UNLOCODE_Normalised"].nunique(),
        "Role": "Separate comparison population",
    },
])

dataset_comparison.to_csv(
    TABLE_DIR / "19_dataset_comparison.csv",
    index=False
)

validation_summary = pd.DataFrame([
    ["Historical schedule records", len(historical_schedule)],
    ["Vessels in primary baseline", len(vessel_parameters)],
    ["Ports in primary baseline", len(port_parameters)],
    ["Port service observations", len(valid_stays)],
    ["Observed inter-port transitions", len(transitions)],
    ["Distinct inter-port pairs", len(interport_parameters)],
    ["Negative inter-port elapsed times excluded", int(
        (ordered["Elapsed_Hours_Between_Calls"] < 0).sum()
    )],
    ["Ports with no verified coordinates from this script", len(port_parameters)],
    ["Disruption scenarios created", len(scenarios)],
], columns=["Metric", "Value"])

validation_summary.to_csv(
    TABLE_DIR / "19_simulation_input_validation_summary.csv",
    index=False
)

with open(
    REPORT_DIR / "19_simulation_input_preparation_notes.txt",
    "w",
    encoding="utf-8"
) as report:
    report.write(
        "SCRIPT 19 - SIMULATION INPUT PREPARATION\n"
        "=========================================\n\n"
        "Primary baseline: conservative schedule actual calls.\n"
        "Core schedule: sensitivity dataset; kept separate.\n"
        "Individual calls: comparison dataset; kept separate.\n\n"
        "Port service time is observed arrival-to-departure duration.\n"
        "It is not necessarily berth processing time.\n\n"
        "Inter-port elapsed time is previous departure to next arrival.\n"
        "It is not pure sailing time and may include waiting or unobserved calls.\n\n"
        "No vessel capacity, port capacity, berth capacity, or sailing speed "
        "has been invented.\n\n"
        "The 18F port validation register remains a pending review register. "
        "Its locations are not treated as independently verified ports.\n\n"
        "Disruption levels and duration are experimental assumptions, "
        "not historical measurements.\n\n"
        "AIS transit exposure through the Strait of Hormuz is not confirmed "
        "by these schedule records.\n"
    )

print("\n" + "=" * 65)
print("SCRIPT 19 COMPLETED")
print("=" * 65)

print("\nDATASET COMPARISON:")
print(dataset_comparison.to_string(index=False))

print("\nVALIDATION SUMMARY:")
print(validation_summary.to_string(index=False))

print("\nCreated simulation input files:")
for path in sorted(INPUT_DIR.glob("19_*")):
    print("-", path.name)

print("\nReports:")
print("-", REPORT_DIR / "19_simulation_input_preparation_notes.txt")
