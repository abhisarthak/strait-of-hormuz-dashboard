
from pathlib import Path

import pandas as pd
import numpy as np
import simpy


# ============================================================
# SCRIPT 27
# SIMPY HISTORICAL SCHEDULE REPLAY AND BASELINE VALIDATION
#
# Purpose:
# 1. Replay historical port-call arrivals and departures.
# 2. Calculate time-varying concurrent port calls.
# 3. Calculate peak and average concurrency.
# 4. Compare results against Script 26.
# 5. Validate observed occupancy intervals.
#
# IMPORTANT:
# - No hypothetical berth capacity is imposed.
# - No artificial queue waiting is introduced.
# - Observed port-call intervals are replayed as recorded.
# - Concurrency is NOT verified berth occupancy.
# - This is a historical replay, not a predictive model.
# ============================================================


ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    ROOT / "data" / "simulation_inputs"
    / "19_historical_arrival_schedule.csv"
)

SCRIPT26_FILE = (
    ROOT / "outputs" / "tables"
    / "26_historical_port_concurrency.csv"
)

TABLE_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

TABLE_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------
# 1. LOAD AND VALIDATE INPUT DATA
# ------------------------------------------------------------

print("=" * 75)
print("SCRIPT 27: SIMPY HISTORICAL SCHEDULE REPLAY")
print("=" * 75)

if not INPUT_FILE.exists():
    raise FileNotFoundError(f"Missing input: {INPUT_FILE}")

if not SCRIPT26_FILE.exists():
    raise FileNotFoundError(
        "Script 26 output not found. "
        "Run Script 26 first."
    )

df = pd.read_csv(INPUT_FILE)

required_columns = [
    "Simulation_Record_ID",
    "IMO_Normalised",
    "UNLOCODE_Normalised",
    "Actual_Arrival_UTC",
    "Actual_Departure_UTC",
]

missing = [
    column for column in required_columns
    if column not in df.columns
]

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

if df.empty:
    raise ValueError("No valid port-call intervals.")

if df["Simulation_Record_ID"].duplicated().any():
    raise ValueError("Duplicate simulation record IDs found.")

print("\n[1/7] INPUT VALIDATION")
print("-" * 50)

print("Valid port calls:", len(df))
print("Unique vessels:", df["IMO_Normalised"].nunique())
print("Unique ports:", df["UNLOCODE_Normalised"].nunique())


# ------------------------------------------------------------
# 2. ESTABLISH GLOBAL SIMULATION CLOCK
# ------------------------------------------------------------

print("\n[2/7] PREPARING SIMULATION CLOCK")
print("-" * 50)

global_start = df["Actual_Arrival_UTC"].min()

df["Arrival_Hours"] = (
    df["Actual_Arrival_UTC"] - global_start
).dt.total_seconds() / 3600

df["Departure_Hours"] = (
    df["Actual_Departure_UTC"] - global_start
).dt.total_seconds() / 3600

df = df.sort_values(
    ["Arrival_Hours", "Simulation_Record_ID"]
).reset_index(drop=True)

print("Global simulation start:", global_start)
print("Global final departure:", df["Actual_Departure_UTC"].max())


# ------------------------------------------------------------
# 3. CREATE SIMPY PORT REPLAY PROCESS
# ------------------------------------------------------------

def replay_one_port(port_df, port_code, port_name):
    """
    Replays one port's historical arrivals and departures.

    All events with the same timestamp are processed together.
    This avoids artificial peaks caused by event ordering at
    identical timestamps.

    A positive delta represents an arrival.
    A negative delta represents a departure.
    """

    env = simpy.Environment()

    events = []

    for _, row in port_df.iterrows():

        events.append({
            "time": float(row["Arrival_Hours"]),
            "delta": 1,
            "record_id": row["Simulation_Record_ID"],
            "event_type": "ARRIVAL",
        })

        events.append({
            "time": float(row["Departure_Hours"]),
            "delta": -1,
            "record_id": row["Simulation_Record_ID"],
            "event_type": "DEPARTURE",
        })

    events = sorted(
        events,
        key=lambda x: (x["time"], x["delta"])
    )

    # Group events occurring at identical timestamps.
    grouped_events = []

    for event in events:

        if (
            not grouped_events
            or not np.isclose(
                grouped_events[-1]["time"],
                event["time"],
                atol=1e-9,
            )
        ):
            grouped_events.append({
                "time": event["time"],
                "delta": 0,
                "arrivals": 0,
                "departures": 0,
            })

        grouped_events[-1]["delta"] += event["delta"]

        if event["event_type"] == "ARRIVAL":
            grouped_events[-1]["arrivals"] += 1
        else:
            grouped_events[-1]["departures"] += 1

    state = {
        "active": 0,
        "peak": 0,
        "area": 0.0,
        "previous_time": None,
        "timeline": [],
        "negative_state_detected": False,
    }

    def event_replay():

        for event in grouped_events:

            event_time = event["time"]

            if state["previous_time"] is None:

                yield env.timeout(event_time)

            else:

                elapsed = event_time - state["previous_time"]

                if elapsed < -1e-9:
                    raise RuntimeError(
                        f"Time reversal detected at {port_code}"
                    )

                state["area"] += (
                    state["active"] * elapsed
                )

                yield env.timeout(max(0, elapsed))

            state["active"] += event["delta"]

            if state["active"] < 0:
                state["negative_state_detected"] = True

            state["peak"] = max(
                state["peak"],
                state["active"],
            )

            state["timeline"].append({
                "UNLOCODE": port_code,
                "Port_Name": port_name,
                "Simulation_Time_Hours": event_time,
                "Event_Arrivals": event["arrivals"],
                "Event_Departures": event["departures"],
                "Active_Port_Calls": state["active"],
            })

            state["previous_time"] = event_time

    env.process(event_replay())
    env.run()

    start = grouped_events[0]["time"]
    end = grouped_events[-1]["time"]

    horizon = end - start

    mean_concurrency = (
        state["area"] / horizon
        if horizon > 0
        else np.nan
    )

    expected_area = port_df["Observed_Interval_Hours"].sum()

    return {
        "UNLOCODE": port_code,
        "Port_Name": port_name,
        "Port_Calls": len(port_df),
        "Unique_Vessels": port_df["IMO_Normalised"].nunique(),
        "Peak_Concurrent_Calls": state["peak"],
        "Mean_Concurrent_Calls": mean_concurrency,
        "Concurrency_Area_Hours": state["area"],
        "Expected_Interval_Hours": expected_area,
        "Area_Difference_Hours": (
            state["area"] - expected_area
        ),
        "Observation_Horizon_Hours": horizon,
        "Final_Active_Calls": state["active"],
        "Negative_State_Detected": (
            state["negative_state_detected"]
        ),
    }, state["timeline"]


# ------------------------------------------------------------
# 4. REPLAY ALL PORTS
# ------------------------------------------------------------

print("\n[3/7] RUNNING SIMPY HISTORICAL REPLAY")
print("-" * 50)

port_results = []
all_timeline = []

for port_code, group in df.groupby("UNLOCODE_Normalised"):

    port_name = (
        group["Port"].dropna().iloc[0]
        if "Port" in group.columns
        and group["Port"].notna().any()
        else ""
    )

    result, timeline = replay_one_port(
        group,
        port_code,
        port_name,
    )

    port_results.append(result)
    all_timeline.extend(timeline)

    print(
        f"{port_code}: "
        f"{result['Port_Calls']} calls | "
        f"Peak concurrency: "
        f"{result['Peak_Concurrent_Calls']}"
    )


replay_summary = pd.DataFrame(port_results)

event_timeline = pd.DataFrame(all_timeline)


# ------------------------------------------------------------
# 5. VALIDATE AGAINST SCRIPT 26
# ------------------------------------------------------------

print("\n[4/7] COMPARING AGAINST SCRIPT 26")
print("-" * 50)

script26 = pd.read_csv(SCRIPT26_FILE)

script26["UNLOCODE"] = (
    script26["UNLOCODE"]
    .astype("string")
    .str.strip()
    .str.upper()
)

comparison = replay_summary.merge(
    script26[
        [
            "UNLOCODE",
            "Port_Calls",
            "Peak_Concurrent_Calls",
            "Mean_Concurrent_Calls",
        ]
    ],
    on="UNLOCODE",
    how="outer",
    suffixes=("_Replay", "_Script26"),
    indicator=True,
)

comparison["Peak_Match"] = (
    comparison["Peak_Concurrent_Calls_Replay"]
    == comparison["Peak_Concurrent_Calls_Script26"]
)

comparison["Call_Count_Match"] = (
    comparison["Port_Calls_Replay"]
    == comparison["Port_Calls_Script26"]
)

comparison["Mean_Concurrency_Difference"] = (
    comparison["Mean_Concurrent_Calls_Replay"]
    - comparison["Mean_Concurrent_Calls_Script26"]
)

comparison["Mean_Concurrency_Match"] = np.isclose(
    comparison["Mean_Concurrent_Calls_Replay"],
    comparison["Mean_Concurrent_Calls_Script26"],
    rtol=1e-8,
    atol=1e-8,
    equal_nan=True,
)

comparison["Port_Match_Status"] = comparison["_merge"].map({
    "both": "MATCHED_PORT",
    "left_only": "MISSING_FROM_SCRIPT26",
    "right_only": "MISSING_FROM_REPLAY",
})

comparison = comparison.drop(columns=["_merge"])

peak_matches = int(comparison["Peak_Match"].fillna(False).sum())
call_matches = int(
    comparison["Call_Count_Match"].fillna(False).sum()
)
mean_matches = int(
    comparison["Mean_Concurrency_Match"].fillna(False).sum()
)


# ------------------------------------------------------------
# 6. VALIDATE INTERVAL REPLAY
# ------------------------------------------------------------

print("\n[5/7] VALIDATING INTERVAL REPLAY")
print("-" * 50)

negative_states = int(
    replay_summary["Negative_State_Detected"].sum()
)

nonzero_final_states = int(
    (replay_summary["Final_Active_Calls"] != 0).sum()
)

area_errors = int(
    (
        replay_summary["Area_Difference_Hours"].abs()
        > 1e-6
    ).sum()
)

print("Ports with matching peak concurrency:",
      peak_matches, "/", len(comparison))

print("Ports with matching call counts:",
      call_matches, "/", len(comparison))

print("Ports with matching mean concurrency:",
      mean_matches, "/", len(comparison))

print("Negative active-call states:", negative_states)
print("Ports with nonzero final active calls:", nonzero_final_states)
print("Ports with occupancy-area mismatch:", area_errors)


# ------------------------------------------------------------
# 7. SAVE OUTPUTS
# ------------------------------------------------------------

print("\n[6/7] SAVING OUTPUTS")
print("-" * 50)

replay_summary.to_csv(
    TABLE_DIR / "27_simpy_historical_replay_summary.csv",
    index=False,
)

event_timeline.to_csv(
    TABLE_DIR / "27_simpy_historical_event_timeline.csv",
    index=False,
)

comparison.to_csv(
    TABLE_DIR / "27_script26_script27_validation.csv",
    index=False,
)


# ------------------------------------------------------------
# 8. WRITE REPORT
# ------------------------------------------------------------

report_path = (
    REPORT_DIR / "27_simpy_historical_replay_report.txt"
)

with open(report_path, "w", encoding="utf-8") as report:

    report.write(
        "SIMPY HISTORICAL SCHEDULE REPLAY AND VALIDATION\n"
    )
    report.write("=" * 75 + "\n\n")

    report.write(f"Historical port calls: {len(df)}\n")
    report.write(
        f"Unique vessels: {df['IMO_Normalised'].nunique()}\n"
    )
    report.write(
        f"Ports replayed: {len(replay_summary)}\n"
    )

    report.write("\nVALIDATION AGAINST SCRIPT 26\n")
    report.write("-" * 75 + "\n")

    report.write(f"Peak concurrency matches: {peak_matches}\n")
    report.write(f"Call count matches: {call_matches}\n")
    report.write(f"Mean concurrency matches: {mean_matches}\n")

    report.write("\nPORT-LEVEL REPLAY RESULTS\n")
    report.write("-" * 75 + "\n")

    report.write(
        replay_summary[
            [
                "UNLOCODE",
                "Port_Calls",
                "Peak_Concurrent_Calls",
                "Mean_Concurrent_Calls",
                "Concurrency_Area_Hours",
                "Final_Active_Calls",
            ]
        ].to_string(index=False)
    )

    report.write("\n\nMETHODOLOGICAL LIMITATIONS\n")
    report.write("-" * 75 + "\n")

    report.write(
        "1. Historical arrival and departure timestamps are replayed.\n"
        "2. No artificial queue delay is introduced.\n"
        "3. No hypothetical port capacity is imposed.\n"
        "4. Concurrent port-call intervals are not verified berth occupancy.\n"
        "5. Observed port stay may include anchorage and waiting.\n"
        "6. Replay validation confirms arithmetic and event consistency,\n"
        "   not the physical accuracy of the original records.\n"
        "7. No actual Strait of Hormuz transit is confirmed.\n"
        "8. This replay is a descriptive baseline, not a forecast.\n"
    )


# ------------------------------------------------------------
# 9. FINAL VALIDATION STATUS
# ------------------------------------------------------------

print("\n[7/7] FINAL VALIDATION")
print("=" * 75)

checks_passed = (
    peak_matches == len(comparison)
    and call_matches == len(comparison)
    and mean_matches == len(comparison)
    and negative_states == 0
    and nonzero_final_states == 0
    and area_errors == 0
    and comparison["Port_Match_Status"].eq("MATCHED_PORT").all()
)

print("Peak concurrency matches:", peak_matches)
print("Call count matches:", call_matches)
print("Mean concurrency matches:", mean_matches)
print("Negative states:", negative_states)
print("Nonzero final active calls:", nonzero_final_states)
print("Area mismatches:", area_errors)

print("\nTOP PORTS BY REPLAYED PEAK CONCURRENCY:")

print(
    replay_summary.sort_values(
        "Peak_Concurrent_Calls",
        ascending=False,
    )[
        [
            "UNLOCODE",
            "Port_Name",
            "Port_Calls",
            "Peak_Concurrent_Calls",
            "Mean_Concurrent_Calls",
        ]
    ].head(10).to_string(index=False)
)

print("\nGENERATED FILES:")
print("- outputs/tables/27_simpy_historical_replay_summary.csv")
print("- outputs/tables/27_simpy_historical_event_timeline.csv")
print("- outputs/tables/27_script26_script27_validation.csv")
print("- outputs/reports/27_simpy_historical_replay_report.txt")

print("\n" + "=" * 75)

if checks_passed:
    print("SCRIPT 27 COMPLETED: ALL VALIDATION CHECKS PASSED")
else:
    print("SCRIPT 27 COMPLETED: REVIEW VALIDATION WARNINGS")

print("=" * 75)
