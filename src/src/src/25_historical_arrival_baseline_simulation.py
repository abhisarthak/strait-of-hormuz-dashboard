
from pathlib import Path

import numpy as np
import pandas as pd
import simpy


# ============================================================
# SCRIPT 25
# HISTORICAL-ARRIVAL BASELINE QUEUE SIMULATION
# Strait of Hormuz Research
#
# Replays 604 historical port arrivals.
# Uses observed port-call duration as an occupancy proxy.
# Tests assumed port capacities: 1, 2 and 3.
#
# IMPORTANT:
# - Port capacity values are experimental assumptions.
# - Observed port stay is NOT confirmed berth-processing time.
# - Historical arrivals already contain observed inter-port timing.
# - Inter-port elapsed times are NOT added again in this script.
# - This model does NOT confirm actual Hormuz transits.
# ============================================================


ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    ROOT / "data" / "simulation_inputs"
    / "19_historical_arrival_schedule.csv"
)

OUTPUT_TABLES = ROOT / "outputs" / "tables"
OUTPUT_REPORTS = ROOT / "outputs" / "reports"

OUTPUT_TABLES.mkdir(parents=True, exist_ok=True)
OUTPUT_REPORTS.mkdir(parents=True, exist_ok=True)


CAPACITY_SCENARIOS = [1, 2, 3]


# ------------------------------------------------------------
# 1. LOAD AND VALIDATE DATA
# ------------------------------------------------------------

print("=" * 75)
print("SCRIPT 25: HISTORICAL-ARRIVAL BASELINE QUEUE SIMULATION")
print("=" * 75)

if not INPUT_FILE.exists():
    raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

df = pd.read_csv(INPUT_FILE)

required_columns = [
    "Simulation_Record_ID",
    "IMO_Normalised",
    "UNLOCODE_Normalised",
    "Actual_Arrival_UTC",
    "Actual_Departure_UTC",
    "Actual_Stay_Hours",
]

missing = [c for c in required_columns if c not in df.columns]

if missing:
    raise ValueError(f"Missing required columns: {missing}")

print("\n[1/7] INPUT VALIDATION")
print("-" * 50)

print("Input shape:", df.shape)

df["Actual_Arrival_UTC"] = pd.to_datetime(
    df["Actual_Arrival_UTC"],
    utc=True,
    errors="coerce",
)

df["Actual_Departure_UTC"] = pd.to_datetime(
    df["Actual_Departure_UTC"],
    utc=True,
    errors="coerce",
)

df["Actual_Stay_Hours"] = pd.to_numeric(
    df["Actual_Stay_Hours"],
    errors="coerce",
)

df["UNLOCODE_Normalised"] = (
    df["UNLOCODE_Normalised"]
    .astype("string")
    .str.strip()
    .str.upper()
)

df["Simulation_Record_ID"] = (
    df["Simulation_Record_ID"].astype("string").str.strip()
)

df = df.dropna(
    subset=[
        "Simulation_Record_ID",
        "UNLOCODE_Normalised",
        "Actual_Arrival_UTC",
        "Actual_Stay_Hours",
    ]
).copy()

df = df[
    (df["Actual_Stay_Hours"] > 0)
    & (df["Actual_Stay_Hours"] < 24 * 365)
].copy()

if df.empty:
    raise ValueError("No valid historical records remain.")

if df["Simulation_Record_ID"].duplicated().any():
    raise ValueError("Duplicate Simulation_Record_ID values found.")

df = df.sort_values(
    ["Actual_Arrival_UTC", "Simulation_Record_ID"]
).reset_index(drop=True)

print("Valid records:", len(df))
print("Unique vessels:", df["IMO_Normalised"].nunique())
print("Unique ports:", df["UNLOCODE_Normalised"].nunique())
print("First arrival:", df["Actual_Arrival_UTC"].min())
print("Last arrival:", df["Actual_Arrival_UTC"].max())


# ------------------------------------------------------------
# 2. DEFINE SIMULATION INPUTS
# ------------------------------------------------------------

print("\n[2/7] PREPARING SIMULATION INPUTS")
print("-" * 50)

simulation_start = df["Actual_Arrival_UTC"].min()

df["Arrival_Hours_From_Start"] = (
    df["Actual_Arrival_UTC"] - simulation_start
).dt.total_seconds() / 3600

ports = sorted(df["UNLOCODE_Normalised"].dropna().unique())

port_names = (
    df.groupby("UNLOCODE_Normalised")["Port"]
    .agg(lambda x: x.dropna().iloc[0] if x.notna().any() else "")
    .to_dict()
    if "Port" in df.columns
    else {}
)

print("Simulation start:", simulation_start)
print("Ports:", len(ports))
print("Capacity scenarios:", CAPACITY_SCENARIOS)


# ------------------------------------------------------------
# 3. DEFINE ONE VESSEL ARRIVAL PROCESS
# ------------------------------------------------------------

def vessel_port_process(
    env,
    row,
    resource,
    results,
    queue_tracker,
):
    """
    One vessel arrives at a port, waits for a resource,
    occupies that resource for its observed port-stay duration,
    and then completes the port call.
    """

    arrival_time = float(row["Arrival_Hours_From_Start"])
    duration = float(row["Actual_Stay_Hours"])

    yield env.timeout(max(0, arrival_time - env.now))

    arrival_clock = env.now

    # Number of vessels waiting or about to wait at arrival.
    current_queue = len(resource.queue)

    if resource.count >= resource.capacity:
        current_queue += 1

    queue_tracker["maximum"] = max(
        queue_tracker["maximum"],
        current_queue,
    )

    with resource.request() as request:

        yield request

        service_start = env.now
        waiting_time = service_start - arrival_clock

        yield env.timeout(duration)

        completion_time = env.now

    results.append({
        "Simulation_Record_ID": row["Simulation_Record_ID"],
        "IMO_Normalised": row["IMO_Normalised"],
        "Port": row["UNLOCODE_Normalised"],
        "Arrival_Hours_From_Start": arrival_time,
        "Observed_Port_Stay_Hours": duration,
        "Simulated_Queue_Wait_Hours": waiting_time,
        "Simulated_Start_Hours": service_start,
        "Simulated_Completion_Hours": completion_time,
        "Simulated_Total_Port_Time_Hours": (
            waiting_time + duration
        ),
        "Observed_Arrival_UTC": row["Actual_Arrival_UTC"],
        "Observed_Departure_UTC": row["Actual_Departure_UTC"],
    })


# ------------------------------------------------------------
# 4. RUN ONE CAPACITY SCENARIO
# ------------------------------------------------------------

def run_scenario(data, capacity):
    env = simpy.Environment()

    resources = {
        port: simpy.Resource(env, capacity=capacity)
        for port in ports
    }

    queue_trackers = {
        port: {"maximum": 0}
        for port in ports
    }

    results = []

    for _, row in data.iterrows():
        env.process(
            vessel_port_process(
                env,
                row,
                resources[row["UNLOCODE_Normalised"]],
                results,
                queue_trackers[row["UNLOCODE_Normalised"]],
            )
        )

    env.run()

    result_df = pd.DataFrame(results)

    if len(result_df) != len(data):
        raise RuntimeError(
            f"Scenario capacity {capacity}: "
            f"expected {len(data)} results, got {len(result_df)}"
        )

    return result_df, queue_trackers


# ------------------------------------------------------------
# 5. RUN ALL CAPACITY SCENARIOS
# ------------------------------------------------------------

print("\n[3/7] RUNNING SIMPY SCENARIOS")
print("-" * 50)

all_call_results = []
all_port_results = []
all_scenario_results = []

for capacity in CAPACITY_SCENARIOS:

    print(f"\nRunning assumed capacity = {capacity}")

    call_results, queue_trackers = run_scenario(
        df,
        capacity,
    )

    call_results["Assumed_Port_Capacity"] = capacity

    all_call_results.append(call_results)

    horizon = (
        call_results["Simulated_Completion_Hours"].max()
        - call_results["Arrival_Hours_From_Start"].min()
    )

    total_wait = call_results["Simulated_Queue_Wait_Hours"].sum()

    mean_wait = call_results["Simulated_Queue_Wait_Hours"].mean()

    median_wait = call_results["Simulated_Queue_Wait_Hours"].median()

    p90_wait = call_results["Simulated_Queue_Wait_Hours"].quantile(0.90)

    total_observed_stay = (
        call_results["Observed_Port_Stay_Hours"].sum()
    )

    mean_port_time = (
        call_results["Simulated_Total_Port_Time_Hours"].mean()
    )

    scenario_row = {
        "Assumed_Port_Capacity": capacity,
        "Total_Port_Calls": len(call_results),
        "Total_Queue_Wait_Hours": total_wait,
        "Mean_Queue_Wait_Hours": mean_wait,
        "Median_Queue_Wait_Hours": median_wait,
        "P90_Queue_Wait_Hours": p90_wait,
        "Maximum_Queue_Wait_Hours": (
            call_results["Simulated_Queue_Wait_Hours"].max()
        ),
        "Mean_Total_Port_Time_Hours": mean_port_time,
        "Total_Observed_Port_Stay_Hours": total_observed_stay,
        "Simulation_Horizon_Hours": horizon,
    }

    all_scenario_results.append(scenario_row)

    # Port-level performance
    for port in ports:

        port_calls = call_results[
            call_results["Port"] == port
        ]

        total_occupancy = (
            port_calls["Observed_Port_Stay_Hours"].sum()
        )

        utilization = (
            total_occupancy / (capacity * horizon)
            if horizon > 0
            else np.nan
        )

        all_port_results.append({
            "Assumed_Port_Capacity": capacity,
            "UNLOCODE": port,
            "Port_Name": port_names.get(port, ""),
            "Port_Calls": len(port_calls),
            "Mean_Queue_Wait_Hours": (
                port_calls["Simulated_Queue_Wait_Hours"].mean()
                if len(port_calls) else np.nan
            ),
            "Median_Queue_Wait_Hours": (
                port_calls["Simulated_Queue_Wait_Hours"].median()
                if len(port_calls) else np.nan
            ),
            "P90_Queue_Wait_Hours": (
                port_calls["Simulated_Queue_Wait_Hours"].quantile(0.90)
                if len(port_calls) else np.nan
            ),
            "Maximum_Queue_Length_At_Arrival": (
                queue_trackers[port]["maximum"]
            ),
            "Total_Occupancy_Hours": total_occupancy,
            "Assumed_Capacity": capacity,
            "Simulation_Horizon_Hours": horizon,
            "Estimated_Utilization": utilization,
        })

    print("Completed calls:", len(call_results))
    print(f"Mean queue wait: {mean_wait:.3f} hours")
    print(f"P90 queue wait: {p90_wait:.3f} hours")


# ------------------------------------------------------------
# 6. COMBINE RESULTS AND SAVE OUTPUTS
# ------------------------------------------------------------

print("\n[4/7] COMBINING RESULTS")
print("-" * 50)

all_calls = pd.concat(
    all_call_results,
    ignore_index=True,
)

port_metrics = pd.DataFrame(all_port_results)

scenario_metrics = pd.DataFrame(all_scenario_results)

all_calls.to_csv(
    OUTPUT_TABLES / "25_baseline_call_level_results.csv",
    index=False,
)

port_metrics.to_csv(
    OUTPUT_TABLES / "25_baseline_port_performance.csv",
    index=False,
)

scenario_metrics.to_csv(
    OUTPUT_TABLES / "25_baseline_capacity_comparison.csv",
    index=False,
)


# ------------------------------------------------------------
# 7. VALIDATION AND REPORT
# ------------------------------------------------------------

print("\n[5/7] VALIDATING SIMULATION RESULTS")
print("-" * 50)

checks = {
    "Input calls": len(df),
    "Scenario call results": len(all_calls),
    "Expected scenario results": len(df) * len(CAPACITY_SCENARIOS),
    "Negative queue waits": int(
        (all_calls["Simulated_Queue_Wait_Hours"] < -1e-9).sum()
    ),
    "Missing queue waits": int(
        all_calls["Simulated_Queue_Wait_Hours"].isna().sum()
    ),
    "Missing completion times": int(
        all_calls["Simulated_Completion_Hours"].isna().sum()
    ),
}

for key, value in checks.items():
    print(f"{key}: {value}")

if len(all_calls) != len(df) * len(CAPACITY_SCENARIOS):
    raise RuntimeError("Scenario result count validation failed.")

if checks["Negative queue waits"] > 0:
    raise RuntimeError("Negative queue wait detected.")

if checks["Missing queue waits"] > 0:
    raise RuntimeError("Missing queue wait detected.")


print("\n[6/7] CREATING REPORT")
print("-" * 50)

report_path = (
    OUTPUT_REPORTS / "25_historical_arrival_baseline_report.txt"
)

with open(report_path, "w", encoding="utf-8") as report:

    report.write(
        "HISTORICAL-ARRIVAL BASELINE QUEUE SIMULATION\n"
    )
    report.write("=" * 70 + "\n\n")

    report.write(f"Input records: {len(df)}\n")
    report.write(f"Unique vessels: {df['IMO_Normalised'].nunique()}\n")
    report.write(f"Ports: {len(ports)}\n")
    report.write(f"Capacity scenarios: {CAPACITY_SCENARIOS}\n")
    report.write(f"Simulation start: {simulation_start}\n\n")

    report.write("CAPACITY SCENARIO COMPARISON\n")
    report.write("-" * 70 + "\n")
    report.write(scenario_metrics.to_string(index=False))

    report.write("\n\nMETHODOLOGICAL ASSUMPTIONS\n")
    report.write("-" * 70 + "\n")

    report.write(
        "1. Historical arrival timestamps are replayed as observed.\n"
        "2. Observed port stay is used as a provisional occupancy duration.\n"
        "3. Port capacities 1, 2 and 3 are experimental assumptions.\n"
        "4. Actual port berth capacities are not established by this model.\n"
        "5. Port stay is not confirmed berth-processing time.\n"
        "6. Queue waiting is simulated separately from the occupancy proxy.\n"
        "7. Historical inter-port elapsed times are not added again.\n"
        "8. No direct sailing routes are inferred.\n"
        "9. No actual Hormuz transit is confirmed.\n"
        "10. Results are conditional on the selected capacity assumptions.\n"
    )

    report.write("\n\nMODEL LIMITATIONS\n")
    report.write("-" * 70 + "\n")

    report.write(
        "The historical port-call duration may already contain waiting, "
        "anchorage, operational and other time components. Therefore, "
        "adding simulated queue waiting can result in overlapping time "
        "components. The results must be interpreted as a provisional "
        "queueing experiment, not as validated estimates of actual "
        "port turnaround or berth utilisation.\n"
    )


# ------------------------------------------------------------
# 8. FINAL SUMMARY
# ------------------------------------------------------------

print("\n[7/7] FINAL SCENARIO COMPARISON")
print("=" * 75)

print(
    scenario_metrics[
        [
            "Assumed_Port_Capacity",
            "Total_Port_Calls",
            "Mean_Queue_Wait_Hours",
            "Median_Queue_Wait_Hours",
            "P90_Queue_Wait_Hours",
            "Mean_Total_Port_Time_Hours",
        ]
    ].to_string(index=False)
)

print("\nGENERATED FILES:")
print("- outputs/tables/25_baseline_call_level_results.csv")
print("- outputs/tables/25_baseline_port_performance.csv")
print("- outputs/tables/25_baseline_capacity_comparison.csv")
print("- outputs/reports/25_historical_arrival_baseline_report.txt")

print("\n" + "=" * 75)
print("SCRIPT 25 COMPLETED SUCCESSFULLY")
print("=" * 75)
