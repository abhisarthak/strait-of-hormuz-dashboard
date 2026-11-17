
from pathlib import Path

import pandas as pd
import numpy as np


# ============================================================
# SCRIPT 26
# HISTORICAL PORT CONCURRENCY AND CAPACITY AUDIT
#
# Measures overlapping observed port-call intervals.
#
# IMPORTANT:
# Overlapping port calls are NOT confirmed simultaneous
# berth occupancy. Observed stays may include anchorage,
# waiting and other operational activities.
#
# This is a historical concurrency proxy, not a
# measurement of actual berth capacity.
# ============================================================


ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    ROOT / "data" / "simulation_inputs"
    / "19_historical_arrival_schedule.csv"
)

TABLE_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

TABLE_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

CAPACITY_LEVELS = [1, 2, 3, 4, 5, 10]


# ------------------------------------------------------------
# 1. LOAD AND VALIDATE DATA
# ------------------------------------------------------------

print("=" * 75)
print("SCRIPT 26: HISTORICAL PORT CONCURRENCY AUDIT")
print("=" * 75)

df = pd.read_csv(INPUT_FILE)

required = [
    "Simulation_Record_ID",
    "IMO_Normalised",
    "UNLOCODE_Normalised",
    "Actual_Arrival_UTC",
    "Actual_Departure_UTC",
]

missing = [c for c in required if c not in df.columns]

if missing:
    raise ValueError(f"Missing columns: {missing}")

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

df["UNLOCODE_Normalised"] = (
    df["UNLOCODE_Normalised"]
    .astype("string")
    .str.strip()
    .str.upper()
)

df = df.dropna(
    subset=[
        "Simulation_Record_ID",
        "UNLOCODE_Normalised",
        "Actual_Arrival_UTC",
        "Actual_Departure_UTC",
    ]
).copy()

df["Observed_Interval_Hours"] = (
    df["Actual_Departure_UTC"]
    - df["Actual_Arrival_UTC"]
).dt.total_seconds() / 3600

df = df[df["Observed_Interval_Hours"] > 0].copy()

if df["Simulation_Record_ID"].duplicated().any():
    raise ValueError("Duplicate simulation record IDs found.")

print("\n[1/6] INPUT SUMMARY")
print("-" * 50)

print("Valid port-call intervals:", len(df))
print("Unique vessels:", df["IMO_Normalised"].nunique())
print("Unique ports:", df["UNLOCODE_Normalised"].nunique())


# ------------------------------------------------------------
# 2. CALCULATE CONCURRENCY FOR EACH PORT
# ------------------------------------------------------------

print("\n[2/6] CALCULATING HISTORICAL CONCURRENCY")
print("-" * 50)


def calculate_port_concurrency(port_df):

    events = []

    for _, row in port_df.iterrows():

        # Departure event is ordered before arrival at an
        # identical timestamp. This treats intervals as
        # [arrival, departure), avoiding false overlap
        # at exact boundary times.

        events.append((
            row["Actual_Arrival_UTC"],
            1,
            row["Simulation_Record_ID"],
        ))

        events.append((
            row["Actual_Departure_UTC"],
            -1,
            row["Simulation_Record_ID"],
        ))

    events.sort(key=lambda x: (x[0], x[1]))

    active = 0
    maximum = 0
    area = 0.0

    previous_time = None

    overloaded_hours = {c: 0.0 for c in CAPACITY_LEVELS}
    event_counts = {c: 0 for c in CAPACITY_LEVELS}

    for timestamp, change, record_id in events:

        if previous_time is not None:

            duration = (
                timestamp - previous_time
            ).total_seconds() / 3600

            area += active * duration

            for capacity in CAPACITY_LEVELS:
                if active > capacity:
                    overloaded_hours[capacity] += duration

        active += change

        maximum = max(maximum, active)

        if change == 1:
            for capacity in CAPACITY_LEVELS:
                if active > capacity:
                    event_counts[capacity] += 1

        previous_time = timestamp

    start = port_df["Actual_Arrival_UTC"].min()
    end = port_df["Actual_Departure_UTC"].max()

    horizon = (end - start).total_seconds() / 3600

    mean_concurrency = (
        area / horizon if horizon > 0 else np.nan
    )

    return {
        "Peak_Concurrent_Calls": maximum,
        "Mean_Concurrent_Calls": mean_concurrency,
        "Observed_Concurrency_Area_Hours": area,
        "Observation_Horizon_Hours": horizon,
        "Overloaded_Hours": overloaded_hours,
        "Arrivals_Exceeding_Capacity": event_counts,
    }


port_rows = []
capacity_rows = []

for port, group in df.groupby("UNLOCODE_Normalised"):

    metrics = calculate_port_concurrency(group)

    port_name = (
        group["Port"].dropna().iloc[0]
        if "Port" in group.columns and group["Port"].notna().any()
        else ""
    )

    port_rows.append({
        "UNLOCODE": port,
        "Port_Name": port_name,
        "Port_Calls": len(group),
        "Unique_Vessels": group["IMO_Normalised"].nunique(),
        "Peak_Concurrent_Calls": metrics["Peak_Concurrent_Calls"],
        "Mean_Concurrent_Calls": metrics["Mean_Concurrent_Calls"],
        "Observed_Concurrency_Area_Hours": (
            metrics["Observed_Concurrency_Area_Hours"]
        ),
        "Observation_Horizon_Hours": (
            metrics["Observation_Horizon_Hours"]
        ),
    })

    for capacity in CAPACITY_LEVELS:

        capacity_rows.append({
            "UNLOCODE": port,
            "Port_Name": port_name,
            "Assumed_Capacity": capacity,
            "Peak_Concurrent_Calls": (
                metrics["Peak_Concurrent_Calls"]
            ),
            "Arrivals_Exceeding_Capacity": (
                metrics["Arrivals_Exceeding_Capacity"][capacity]
            ),
            "Hours_With_Concurrency_Above_Capacity": (
                metrics["Overloaded_Hours"][capacity]
            ),
            "Capacity_Accommodates_Observed_Peak": (
                metrics["Peak_Concurrent_Calls"] <= capacity
            ),
        })


port_summary = pd.DataFrame(port_rows)

capacity_comparison = pd.DataFrame(capacity_rows)


# ------------------------------------------------------------
# 3. CLASSIFY OBSERVED CONCURRENCY
# ------------------------------------------------------------

print("\n[3/6] CLASSIFYING PORT CONCURRENCY")
print("-" * 50)


def classify_peak(value):

    if value <= 1:
        return "PEAK_1"
    elif value <= 2:
        return "PEAK_2"
    elif value <= 3:
        return "PEAK_3"
    elif value <= 5:
        return "PEAK_4_TO_5"
    else:
        return "PEAK_ABOVE_5"


port_summary["Concurrency_Category"] = (
    port_summary["Peak_Concurrent_Calls"].apply(classify_peak)
)

port_summary = port_summary.sort_values(
    ["Peak_Concurrent_Calls", "Port_Calls"],
    ascending=[False, False],
)


# ------------------------------------------------------------
# 4. GLOBAL CAPACITY SUMMARY
# ------------------------------------------------------------

print("\n[4/6] GLOBAL CAPACITY COMPARISON")
print("-" * 50)

global_rows = []

for capacity in CAPACITY_LEVELS:

    comparison = capacity_comparison[
        capacity_comparison["Assumed_Capacity"] == capacity
    ]

    global_rows.append({
        "Assumed_Capacity": capacity,
        "Ports_Accommodating_Peak": int(
            comparison["Capacity_Accommodates_Observed_Peak"].sum()
        ),
        "Total_Ports": len(comparison),
        "Ports_Exceeding_Peak_Capacity": int(
            (~comparison["Capacity_Accommodates_Observed_Peak"]).sum()
        ),
        "Total_Arrivals_Exceeding_Capacity": int(
            comparison["Arrivals_Exceeding_Capacity"].sum()
        ),
        "Total_Concurrency_Overload_Hours": (
            comparison["Hours_With_Concurrency_Above_Capacity"].sum()
        ),
    })

global_summary = pd.DataFrame(global_rows)


# ------------------------------------------------------------
# 5. SAVE OUTPUTS
# ------------------------------------------------------------

print("\n[5/6] SAVING OUTPUTS")
print("-" * 50)

port_summary.to_csv(
    TABLE_DIR / "26_historical_port_concurrency.csv",
    index=False,
)

capacity_comparison.to_csv(
    TABLE_DIR / "26_port_capacity_concurrency_comparison.csv",
    index=False,
)

global_summary.to_csv(
    TABLE_DIR / "26_global_capacity_concurrency_summary.csv",
    index=False,
)


# ------------------------------------------------------------
# 6. REPORT
# ------------------------------------------------------------

report_path = (
    REPORT_DIR / "26_historical_port_concurrency_report.txt"
)

with open(report_path, "w", encoding="utf-8") as report:

    report.write("HISTORICAL PORT CONCURRENCY AUDIT\n")
    report.write("=" * 70 + "\n\n")

    report.write(f"Valid intervals: {len(df)}\n")
    report.write(
        f"Ports: {df['UNLOCODE_Normalised'].nunique()}\n"
    )

    report.write("\nPORT CONCURRENCY SUMMARY\n")
    report.write("-" * 70 + "\n")
    report.write(port_summary.to_string(index=False))

    report.write("\n\nGLOBAL CAPACITY COMPARISON\n")
    report.write("-" * 70 + "\n")
    report.write(global_summary.to_string(index=False))

    report.write("\n\nMETHODOLOGICAL LIMITATIONS\n")
    report.write(
        "1. Overlapping port-call intervals are a concurrency proxy.\n"
        "2. They do not establish actual berth occupancy.\n"
        "3. Port stays may include anchorage and waiting.\n"
        "4. Peak concurrency is not verified berth capacity.\n"
        "5. Capacity comparisons are screening experiments only.\n"
        "6. Historical records do not establish confirmed Hormuz transit.\n"
    )


# ------------------------------------------------------------
# FINAL DISPLAY
# ------------------------------------------------------------

print("\n[6/6] FINAL RESULTS")
print("=" * 75)

print("\nPORTS WITH HIGHEST OBSERVED CONCURRENCY:")
print(
    port_summary[
        [
            "UNLOCODE",
            "Port_Name",
            "Port_Calls",
            "Peak_Concurrent_Calls",
            "Mean_Concurrent_Calls",
        ]
    ].head(10).to_string(index=False)
)

print("\nGLOBAL CAPACITY COMPARISON:")
print(global_summary.to_string(index=False))

print("\nGENERATED FILES:")
print("- outputs/tables/26_historical_port_concurrency.csv")
print("- outputs/tables/26_port_capacity_concurrency_comparison.csv")
print("- outputs/tables/26_global_capacity_concurrency_summary.csv")
print("- outputs/reports/26_historical_port_concurrency_report.txt")

print("\n" + "=" * 75)
print("SCRIPT 26 COMPLETED SUCCESSFULLY")
print("=" * 75)
