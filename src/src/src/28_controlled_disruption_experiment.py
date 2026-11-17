
"""
SCRIPT 28: CONTROLLED DISRUPTION SCENARIO EXPERIMENT

Purpose
-------
Apply hypothetical schedule delays to a reproducibly selected proportion
of historical port calls, replay the modified schedule using SimPy, and
measure the resulting changes in port-call concurrency.

Important interpretation
-------------------------
1. Disruption percentages and delays are experimental assumptions.
2. Affected calls are randomly selected; they are NOT identified as
   confirmed Strait of Hormuz transits.
3. Arrival and departure are shifted equally, preserving observed
   port-stay duration.
4. This script does not model rerouting, sailing-time changes, berth
   capacity, or actual vessel queues.
5. Historical port-call intervals are used as occupancy proxies only.
"""

from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import simpy


# ============================================================
# 1. PROJECT PATHS AND EXPERIMENT SETTINGS
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

RANDOM_SEEDS = [21, 42, 63, 84, 105]

# Each scenario is a hypothetical experimental assumption.
SCENARIOS = [
    {
        "Scenario": "S0_BASELINE",
        "Affected_Percentage": 0,
        "Delay_Hours": 0,
    },
    {
        "Scenario": "S1_MILD",
        "Affected_Percentage": 10,
        "Delay_Hours": 24,
    },
    {
        "Scenario": "S2_MODERATE",
        "Affected_Percentage": 25,
        "Delay_Hours": 72,
    },
    {
        "Scenario": "S3_SEVERE",
        "Affected_Percentage": 50,
        "Delay_Hours": 168,
    },
]

REQUIRED_COLUMNS = [
    "Simulation_Record_ID",
    "IMO_Normalised",
    "UNLOCODE_Normalised",
    "Port",
    "Actual_Arrival_UTC",
    "Actual_Departure_UTC",
    "Actual_Stay_Hours",
]


# ============================================================
# 2. LOAD AND VALIDATE HISTORICAL SCHEDULE
# ============================================================

def load_schedule():

    print("\n[1/8] LOADING HISTORICAL SCHEDULE")
    print("-" * 65)

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    missing = [
        col for col in REQUIRED_COLUMNS
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Required columns missing: {missing}"
        )

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

    df = df.dropna(
        subset=[
            "Simulation_Record_ID",
            "UNLOCODE_Normalised",
            "Actual_Arrival_UTC",
            "Actual_Departure_UTC",
            "Actual_Stay_Hours",
        ]
    ).copy()

    df = df[
        (df["Actual_Departure_UTC"] >
         df["Actual_Arrival_UTC"])
        &
        (df["Actual_Stay_Hours"] > 0)
    ].copy()

    if df.empty:
        raise ValueError("No valid historical port calls remain.")

    if df["Simulation_Record_ID"].duplicated().any():
        raise ValueError(
            "Simulation_Record_ID must be unique."
        )

    calculated_stay = (
        df["Actual_Departure_UTC"]
        - df["Actual_Arrival_UTC"]
    ).dt.total_seconds() / 3600

    mismatch = np.abs(
        calculated_stay - df["Actual_Stay_Hours"]
    ) > 0.02

    print(f"Valid port calls: {len(df)}")
    print(
        "Unique vessels:",
        df["IMO_Normalised"].nunique()
    )
    print(
        "Unique ports:",
        df["UNLOCODE_Normalised"].nunique()
    )
    print(
        "Port-stay timestamp mismatches:",
        int(mismatch.sum())
    )

    return df.reset_index(drop=True)


# ============================================================
# 3. CREATE DISRUPTED SCHEDULE
# ============================================================

def create_disrupted_schedule(
    historical,
    scenario,
    seed,
):

    df = historical.copy()

    percentage = scenario["Affected_Percentage"]
    delay_hours = scenario["Delay_Hours"]

    df["Is_Affected"] = False
    df["Imposed_Delay_Hours"] = 0.0

    rng = np.random.default_rng(seed)

    number_affected = int(
        round(len(df) * percentage / 100)
    )

    if number_affected > 0:

        selected_indices = rng.choice(
            df.index.to_numpy(),
            size=number_affected,
            replace=False,
        )

        df.loc[selected_indices, "Is_Affected"] = True

        df.loc[
            selected_indices,
            "Imposed_Delay_Hours"
        ] = delay_hours

    df["Scenario_Arrival_UTC"] = (
        df["Actual_Arrival_UTC"]
        + pd.to_timedelta(
            df["Imposed_Delay_Hours"],
            unit="h",
        )
    )

    df["Scenario_Departure_UTC"] = (
        df["Actual_Departure_UTC"]
        + pd.to_timedelta(
            df["Imposed_Delay_Hours"],
            unit="h",
        )
    )

    df["Scenario"] = scenario["Scenario"]
    df["Replication_Seed"] = seed

    # Validation: port-stay duration must remain unchanged.
    original_duration = (
        df["Actual_Departure_UTC"]
        - df["Actual_Arrival_UTC"]
    )

    disrupted_duration = (
        df["Scenario_Departure_UTC"]
        - df["Scenario_Arrival_UTC"]
    )

    if not original_duration.equals(disrupted_duration):
        raise AssertionError(
            "Disruption unexpectedly changed port-stay duration."
        )

    return df


# ============================================================
# 4. SIMPY EVENT-BASED PORT REPLAY
# ============================================================

def replay_one_port(port_df):

    """
    Replay arrival and departure events for one port.

    All events with identical timestamps are grouped together.
    The net change is applied simultaneously to avoid artificial
    concurrency peaks caused by event ordering.
    """

    events = []

    for row in port_df.itertuples(index=False):

        arrival = row.Scenario_Arrival_UTC
        departure = row.Scenario_Departure_UTC

        events.append((arrival, 1))
        events.append((departure, -1))

    event_df = pd.DataFrame(
        events,
        columns=["Timestamp", "Delta"],
    )

    grouped = (
        event_df.groupby("Timestamp", as_index=False)["Delta"]
        .sum()
        .sort_values("Timestamp")
        .reset_index(drop=True)
    )

    start_time = grouped["Timestamp"].min()

    active_calls = 0
    peak_concurrency = 0
    occupancy_area = 0.0
    negative_states = 0

    timeline = []

    env = simpy.Environment()

    def event_replay():

        nonlocal active_calls
        nonlocal peak_concurrency
        nonlocal occupancy_area
        nonlocal negative_states

        previous_time = 0.0

        for row in grouped.itertuples(index=False):

            current_time = (
                row.Timestamp - start_time
            ).total_seconds() / 3600

            elapsed = current_time - previous_time

            if elapsed < -1e-9:
                raise AssertionError(
                    "Event timestamps are not chronological."
                )

            occupancy_area += active_calls * elapsed

            yield env.timeout(max(0.0, elapsed))

            active_calls += int(row.Delta)

            if active_calls < 0:
                negative_states += 1

            peak_concurrency = max(
                peak_concurrency,
                active_calls,
            )

            timeline.append({
                "Timestamp": row.Timestamp,
                "Active_Calls": active_calls,
            })

            previous_time = current_time

        return

    env.process(event_replay())
    env.run()

    if active_calls != 0:
        raise AssertionError(
            "Final active-call count is not zero."
        )

    total_period = (
        grouped["Timestamp"].max()
        - grouped["Timestamp"].min()
    ).total_seconds() / 3600

    mean_concurrency = (
        occupancy_area / total_period
        if total_period > 0
        else 0.0
    )

    return {
        "Port_Calls": len(port_df),
        "Peak_Concurrent_Calls": peak_concurrency,
        "Mean_Concurrent_Calls": mean_concurrency,
        "Occupancy_Area_Call_Hours": occupancy_area,
        "Observation_Period_Hours": total_period,
        "Negative_Active_Call_States": negative_states,
        "Final_Active_Calls": active_calls,
    }, timeline


# ============================================================
# 5. REPLAY ALL PORTS IN A SCENARIO
# ============================================================

def replay_scenario(disrupted_df):

    port_results = []
    event_timelines = []

    for port_code, port_df in disrupted_df.groupby(
        "UNLOCODE_Normalised"
    ):

        port_metrics, timeline = replay_one_port(port_df)

        port_metrics["UNLOCODE_Normalised"] = port_code

        port_metrics["Port_Name"] = (
            port_df["Port"].iloc[0]
        )

        port_results.append(port_metrics)

        for event in timeline:
            event_timelines.append({
                "UNLOCODE_Normalised": port_code,
                **event,
            })

    port_results_df = pd.DataFrame(port_results)

    timeline_df = pd.DataFrame(event_timelines)

    return port_results_df, timeline_df


# ============================================================
# 6. RUN BASELINE AND DISRUPTION EXPERIMENTS
# ============================================================

def run_experiments(historical):

    print("\n[2/8] RUNNING CONTROLLED DISRUPTION EXPERIMENTS")
    print("-" * 65)

    all_call_results = []
    all_port_results = []
    all_replication_results = []
    all_timelines = []

    total_runs = len(SCENARIOS) * len(RANDOM_SEEDS)
    run_number = 0

    for scenario in SCENARIOS:

        for seed in RANDOM_SEEDS:

            run_number += 1

            print(
                f"\nRun {run_number}/{total_runs}: "
                f"{scenario['Scenario']} | Seed {seed}"
            )

            disrupted = create_disrupted_schedule(
                historical,
                scenario,
                seed,
            )

            port_metrics, timeline = replay_scenario(
                disrupted
            )

            disrupted["Scenario_Total_Delay_Hours"] = (
                disrupted["Imposed_Delay_Hours"]
            )

            all_call_results.append(disrupted)

            port_metrics["Scenario"] = scenario["Scenario"]
            port_metrics["Replication_Seed"] = seed

            all_port_results.append(port_metrics)

            timeline["Scenario"] = scenario["Scenario"]
            timeline["Replication_Seed"] = seed

            all_timelines.append(timeline)

            total_delay = disrupted[
                "Imposed_Delay_Hours"
            ].sum()

            mean_delay = disrupted[
                "Imposed_Delay_Hours"
            ].mean()

            p90_delay = disrupted[
                "Imposed_Delay_Hours"
            ].quantile(0.90)

            affected_calls = int(
                disrupted["Is_Affected"].sum()
            )

            replication_results = {
                "Scenario": scenario["Scenario"],
                "Replication_Seed": seed,
                "Affected_Percentage": scenario[
                    "Affected_Percentage"
                ],
                "Assumed_Delay_Hours": scenario[
                    "Delay_Hours"
                ],
                "Total_Calls": len(disrupted),
                "Affected_Calls": affected_calls,
                "Actual_Affected_Share_Percent": (
                    affected_calls / len(disrupted) * 100
                ),
                "Total_Imposed_Delay_Hours": total_delay,
                "Mean_Imposed_Delay_Hours": mean_delay,
                "P90_Imposed_Delay_Hours": p90_delay,
                "Mean_Port_Peak_Concurrency": (
                    port_metrics[
                        "Peak_Concurrent_Calls"
                    ].mean()
                ),
                "Maximum_Port_Peak_Concurrency": (
                    port_metrics[
                        "Peak_Concurrent_Calls"
                    ].max()
                ),
                "Mean_Port_Concurrency": (
                    port_metrics[
                        "Mean_Concurrent_Calls"
                    ].mean()
                ),
                "Total_Negative_States": (
                    port_metrics[
                        "Negative_Active_Call_States"
                    ].sum()
                ),
                "Total_Final_Active_Calls": (
                    port_metrics[
                        "Final_Active_Calls"
                    ].sum()
                ),
            }

            all_replication_results.append(
                replication_results
            )

    calls_df = pd.concat(
        all_call_results,
        ignore_index=True,
    )

    ports_df = pd.concat(
        all_port_results,
        ignore_index=True,
    )

    replications_df = pd.DataFrame(
        all_replication_results
    )

    timelines_df = pd.concat(
        all_timelines,
        ignore_index=True,
    )

    return (
        calls_df,
        ports_df,
        replications_df,
        timelines_df,
    )


# ============================================================
# 7. SUMMARISE RESULTS
# ============================================================

def summarise_results(
    historical,
    calls_df,
    ports_df,
    replications_df,
):

    print("\n[3/8] CREATING SCENARIO SUMMARY")
    print("-" * 65)

    # Baseline port-level metrics from the same replay engine.
    baseline = replications_df[
        replications_df["Scenario"] == "S0_BASELINE"
    ].copy()

    # Baseline is identical across seeds. Use its mean as reference.
    baseline_peak = baseline[
        "Maximum_Port_Peak_Concurrency"
    ].mean()

    baseline_mean = baseline[
        "Mean_Port_Concurrency"
    ].mean()

    baseline_total_delay = baseline[
        "Total_Imposed_Delay_Hours"
    ].mean()

    summary_rows = []

    for scenario_name, group in replications_df.groupby(
        "Scenario",
        sort=False,
    ):

        summary_rows.append({
            "Scenario": scenario_name,
            "Replications": len(group),
            "Mean_Affected_Calls": group[
                "Affected_Calls"
            ].mean(),
            "Mean_Affected_Share_Percent": group[
                "Actual_Affected_Share_Percent"
            ].mean(),
            "Mean_Total_Imposed_Delay_Hours": group[
                "Total_Imposed_Delay_Hours"
            ].mean(),
            "SD_Total_Imposed_Delay_Hours": group[
                "Total_Imposed_Delay_Hours"
            ].std(ddof=0),
            "Mean_Call_Delay_Hours": group[
                "Mean_Imposed_Delay_Hours"
            ].mean(),
            "Mean_P90_Call_Delay_Hours": group[
                "P90_Imposed_Delay_Hours"
            ].mean(),
            "Mean_Max_Port_Peak_Concurrency": group[
                "Maximum_Port_Peak_Concurrency"
            ].mean(),
            "Change_Max_Peak_vs_Baseline": (
                group[
                    "Maximum_Port_Peak_Concurrency"
                ].mean() - baseline_peak
            ),
            "Mean_Port_Concurrency": group[
                "Mean_Port_Concurrency"
            ].mean(),
            "Change_Mean_Port_Concurrency": (
                group[
                    "Mean_Port_Concurrency"
                ].mean() - baseline_mean
            ),
            "All_Replays_Valid": (
                group["Total_Negative_States"].sum() == 0
                and group["Total_Final_Active_Calls"].sum() == 0
            ),
        })

    summary_df = pd.DataFrame(summary_rows)

    # Port-level comparison against the baseline for each seed.
    baseline_ports = ports_df[
        ports_df["Scenario"] == "S0_BASELINE"
    ][[
        "Replication_Seed",
        "UNLOCODE_Normalised",
        "Peak_Concurrent_Calls",
        "Mean_Concurrent_Calls",
    ]].rename(columns={
        "Peak_Concurrent_Calls": "Baseline_Peak",
        "Mean_Concurrent_Calls": "Baseline_Mean",
    })

    port_comparison = ports_df.merge(
        baseline_ports,
        on=[
            "Replication_Seed",
            "UNLOCODE_Normalised",
        ],
        how="left",
        validate="many_to_one",
    )

    port_comparison["Peak_Concurrency_Change"] = (
        port_comparison["Peak_Concurrent_Calls"]
        - port_comparison["Baseline_Peak"]
    )

    port_comparison["Mean_Concurrency_Change"] = (
        port_comparison["Mean_Concurrent_Calls"]
        - port_comparison["Baseline_Mean"]
    )

    return summary_df, port_comparison


# ============================================================
# 8. SAVE OUTPUTS AND REPORT
# ============================================================

def save_outputs(
    historical,
    calls_df,
    ports_df,
    replications_df,
    timelines_df,
    summary_df,
    port_comparison,
):

    print("\n[4/8] VALIDATING EXPERIMENT OUTPUTS")
    print("-" * 65)

    expected_runs = len(SCENARIOS) * len(RANDOM_SEEDS)

    expected_call_results = (
        len(historical) * expected_runs
    )

    checks = {
        "Expected replication runs": (
            len(replications_df) == expected_runs
        ),
        "Expected call-level records": (
            len(calls_df) == expected_call_results
        ),
        "No negative active-call states": (
            ports_df["Negative_Active_Call_States"].sum() == 0
        ),
        "No nonzero final active calls": (
            ports_df["Final_Active_Calls"].sum() == 0
        ),
        "No missing imposed delays": (
            calls_df["Imposed_Delay_Hours"].notna().all()
        ),
        "No negative imposed delays": (
            (calls_df["Imposed_Delay_Hours"] >= 0).all()
        ),
    }

    for name, passed in checks.items():
        print(f"{name}: {'PASS' if passed else 'FAIL'}")

    if not all(checks.values()):
        raise AssertionError(
            "One or more experiment validation checks failed."
        )

    print("\n[5/8] SAVING TABLES")
    print("-" * 65)

    calls_df.to_csv(
        OUTPUT_TABLES
        / "28_disruption_call_level_results.csv",
        index=False,
    )

    ports_df.to_csv(
        OUTPUT_TABLES
        / "28_disruption_port_performance.csv",
        index=False,
    )

    replications_df.to_csv(
        OUTPUT_TABLES
        / "28_disruption_replication_results.csv",
        index=False,
    )

    summary_df.to_csv(
        OUTPUT_TABLES
        / "28_disruption_scenario_summary.csv",
        index=False,
    )

    port_comparison.to_csv(
        OUTPUT_TABLES
        / "28_disruption_port_comparison.csv",
        index=False,
    )

    timelines_df.to_csv(
        OUTPUT_TABLES
        / "28_disruption_event_timeline.csv",
        index=False,
    )

    print("\n[6/8] WRITING EXPERIMENT REPORT")
    print("-" * 65)

    report_path = (
        OUTPUT_REPORTS
        / "28_controlled_disruption_experiment_report.txt"
    )

    with open(report_path, "w", encoding="utf-8") as file:

        file.write(
            "SCRIPT 28: CONTROLLED DISRUPTION EXPERIMENT\n"
        )
        file.write("=" * 75 + "\n\n")

        file.write("EXPERIMENT DESIGN\n")
        file.write("-" * 75 + "\n")
        file.write(
            "Historical schedule calls: "
            f"{len(historical)}\n"
        )
        file.write(
            "Unique vessels: "
            f"{historical['IMO_Normalised'].nunique()}\n"
        )
        file.write(
            "Unique ports: "
            f"{historical['UNLOCODE_Normalised'].nunique()}\n"
        )
        file.write(
            f"Random seeds: {RANDOM_SEEDS}\n"
        )
        file.write(
            f"Total replications: {len(replications_df)}\n\n"
        )

        file.write("SCENARIO SUMMARY\n")
        file.write("-" * 75 + "\n")
        file.write(
            summary_df.to_string(index=False)
        )
        file.write("\n\n")

        file.write("INTERPRETATION AND LIMITATIONS\n")
        file.write("-" * 75 + "\n")
        file.write(
            "Disruption percentages and delay durations are "
            "hypothetical experimental assumptions.\n"
        )
        file.write(
            "Affected calls are selected randomly and are not "
            "confirmed Strait of Hormuz transits.\n"
        )
        file.write(
            "Arrival and departure timestamps are shifted equally, "
            "preserving observed port-stay duration.\n"
        )
        file.write(
            "Concurrency is calculated from port-call time intervals "
            "and does not establish berth occupancy or port capacity.\n"
        )
        file.write(
            "This experiment does not simulate vessel rerouting, "
            "sailing-time changes, or queue formation.\n"
        )
        file.write(
            "Results are conditional on the selected historical "
            "schedule and experimental assumptions.\n"
        )

    print("\n[7/8] FINAL SCENARIO SUMMARY")
    print("=" * 75)

    print(
        summary_df.to_string(
            index=False,
            float_format=lambda x: f"{x:.3f}",
        )
    )

    print("\n[8/8] OUTPUT FILES")
    print("=" * 75)

    output_files = [
        "28_disruption_call_level_results.csv",
        "28_disruption_port_performance.csv",
        "28_disruption_replication_results.csv",
        "28_disruption_scenario_summary.csv",
        "28_disruption_port_comparison.csv",
        "28_disruption_event_timeline.csv",
    ]

    for name in output_files:
        print(f"- outputs/tables/{name}")

    print(
        "- outputs/reports/"
        "28_controlled_disruption_experiment_report.txt"
    )

    print("\nSCRIPT 28 COMPLETED SUCCESSFULLY")


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 75)
    print("SCRIPT 28: CONTROLLED DISRUPTION SCENARIO EXPERIMENT")
    print("=" * 75)

    historical = load_schedule()

    (
        calls_df,
        ports_df,
        replications_df,
        timelines_df,
    ) = run_experiments(historical)

    summary_df, port_comparison = summarise_results(
        historical,
        calls_df,
        ports_df,
        replications_df,
    )

    save_outputs(
        historical,
        calls_df,
        ports_df,
        replications_df,
        timelines_df,
        summary_df,
        port_comparison,
    )


if __name__ == "__main__":
    main()
