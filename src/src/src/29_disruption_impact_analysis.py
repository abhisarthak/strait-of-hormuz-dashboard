
"""
SCRIPT 29: DISRUPTION IMPACT ANALYSIS

Analyses Script 28 results using:
1. A common observation window for every scenario and replication.
2. Delay statistics for affected calls only.
3. Port-level peak and time-weighted mean concurrency.
4. Paired comparison against the baseline using the same random seed.
5. Replication-level variability.

Interpretation:
- Disruption assumptions are hypothetical.
- Affected calls are randomly selected, not confirmed Hormuz transits.
- Concurrency is based on recorded port-call intervals, not berth occupancy.
"""

from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# 1. PATHS AND INPUTS
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    ROOT / "outputs" / "tables"
    / "28_disruption_call_level_results.csv"
)

OUTPUT_TABLES = ROOT / "outputs" / "tables"
OUTPUT_REPORTS = ROOT / "outputs" / "reports"

OUTPUT_TABLES.mkdir(parents=True, exist_ok=True)
OUTPUT_REPORTS.mkdir(parents=True, exist_ok=True)

REQUIRED_COLUMNS = [
    "Simulation_Record_ID",
    "IMO_Normalised",
    "UNLOCODE_Normalised",
    "Port",
    "Actual_Arrival_UTC",
    "Actual_Departure_UTC",
    "Scenario_Arrival_UTC",
    "Scenario_Departure_UTC",
    "Is_Affected",
    "Imposed_Delay_Hours",
    "Scenario",
    "Replication_Seed",
]


# ============================================================
# 2. LOAD AND VALIDATE SCRIPT 28 OUTPUT
# ============================================================

def load_data():

    print("\n[1/7] LOADING SCRIPT 28 RESULTS")
    print("-" * 70)

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Script 28 output not found: {INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    missing = [
        col for col in REQUIRED_COLUMNS
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

    datetime_columns = [
        "Actual_Arrival_UTC",
        "Actual_Departure_UTC",
        "Scenario_Arrival_UTC",
        "Scenario_Departure_UTC",
    ]

    for col in datetime_columns:
        df[col] = pd.to_datetime(
            df[col],
            utc=True,
            errors="coerce",
        )

    df["Is_Affected"] = (
        df["Is_Affected"]
        .astype(str)
        .str.lower()
        .map({
            "true": True,
            "false": False,
            "1": True,
            "0": False,
        })
    )

    df["Imposed_Delay_Hours"] = pd.to_numeric(
        df["Imposed_Delay_Hours"],
        errors="coerce",
    )

    df["Replication_Seed"] = pd.to_numeric(
        df["Replication_Seed"],
        errors="coerce",
    )

    if df[REQUIRED_COLUMNS].isna().any().any():
        raise ValueError(
            "Missing or invalid values found in required columns."
        )

    if (
        df["Scenario_Departure_UTC"]
        <= df["Scenario_Arrival_UTC"]
    ).any():
        raise ValueError(
            "Invalid scenario call interval found."
        )

    if (df["Imposed_Delay_Hours"] < 0).any():
        raise ValueError(
            "Negative imposed delay found."
        )

    print("Call-level records:", len(df))
    print("Scenarios:", sorted(df["Scenario"].unique()))
    print("Replications:", sorted(df["Replication_Seed"].unique()))
    print("Unique ports:", df["UNLOCODE_Normalised"].nunique())
    print("Unique vessels:", df["IMO_Normalised"].nunique())

    return df


# ============================================================
# 3. VALIDATE SCENARIO STRUCTURE
# ============================================================

def validate_structure(df):

    print("\n[2/7] VALIDATING SCENARIO STRUCTURE")
    print("-" * 70)

    expected_scenarios = {
        "S0_BASELINE",
        "S1_MILD",
        "S2_MODERATE",
        "S3_SEVERE",
    }

    actual_scenarios = set(df["Scenario"].unique())

    if actual_scenarios != expected_scenarios:
        raise ValueError(
            f"Unexpected scenarios: {actual_scenarios}"
        )

    seeds = sorted(df["Replication_Seed"].unique())

    baseline = df[
        df["Scenario"] == "S0_BASELINE"
    ]

    expected_calls = set(
        baseline["Simulation_Record_ID"].astype(str)
    )

    if baseline.duplicated(
        ["Replication_Seed", "Simulation_Record_ID"]
    ).any():
        raise ValueError(
            "Duplicate baseline call within a replication."
        )

    for scenario in sorted(expected_scenarios):

        scenario_df = df[df["Scenario"] == scenario]

        for seed in seeds:

            subset = scenario_df[
                scenario_df["Replication_Seed"] == seed
            ]

            observed_calls = set(
                subset["Simulation_Record_ID"].astype(str)
            )

            if observed_calls != expected_calls:
                raise ValueError(
                    f"Call population mismatch: {scenario}, seed {seed}"
                )

    # Each scenario/seed combination must have one row per call.
    duplicates = df.duplicated(
        ["Scenario", "Replication_Seed", "Simulation_Record_ID"]
    ).sum()

    if duplicates:
        raise ValueError(
            f"Duplicate scenario call records: {duplicates}"
        )

    print("Scenario structure: PASS")
    print("Call population consistency: PASS")
    print("Unique scenario-call records: PASS")

    return seeds


# ============================================================
# 4. ESTABLISH COMMON OBSERVATION WINDOW
# ============================================================

def establish_common_window(df):

    print("\n[3/7] ESTABLISHING COMMON OBSERVATION WINDOW")
    print("-" * 70)

    baseline = df[
        df["Scenario"] == "S0_BASELINE"
    ]

    # Use original historical timestamps, not shifted timestamps.
    window_start = baseline[
        "Actual_Arrival_UTC"
    ].min()

    baseline_end = baseline[
        "Actual_Departure_UTC"
    ].max()

    # Extend the common window to cover the latest scenario departure.
    scenario_end = df[
        "Scenario_Departure_UTC"
    ].max()

    window_end = max(baseline_end, scenario_end)

    window_hours = (
        window_end - window_start
    ).total_seconds() / 3600

    print("Common window start:", window_start)
    print("Common window end:", window_end)
    print(f"Common window duration: {window_hours:.2f} hours")

    return window_start, window_end, window_hours


# ============================================================
# 5. CALCULATE CONCURRENCY OVER COMMON WINDOW
# ============================================================

def calculate_port_concurrency(
    port_df,
    window_start,
    window_end,
    window_hours,
):

    events = []

    for row in port_df.itertuples(index=False):

        arrival = max(
            row.Scenario_Arrival_UTC,
            window_start,
        )

        departure = min(
            row.Scenario_Departure_UTC,
            window_end,
        )

        # Ignore calls outside the common window.
        if departure <= arrival:
            continue

        events.append((arrival, 1))
        events.append((departure, -1))

    if not events:

        return {
            "Port_Calls_Within_Window": 0,
            "Peak_Concurrent_Calls": 0,
            "Mean_Concurrent_Calls_Common_Window": 0.0,
            "Occupancy_Area_Call_Hours": 0.0,
            "Negative_Active_States": 0,
            "Final_Active_Calls": 0,
        }

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

    active = 0
    peak = 0
    area = 0.0
    negative_states = 0

    previous_time = window_start

    for row in grouped.itertuples(index=False):

        elapsed = (
            row.Timestamp - previous_time
        ).total_seconds() / 3600

        if elapsed < -1e-9:
            raise ValueError(
                "Event timeline is not chronological."
            )

        area += active * elapsed

        active += int(row.Delta)

        if active < 0:
            negative_states += 1

        peak = max(peak, active)

        previous_time = row.Timestamp

    # Account for the final part of the common observation window.
    final_elapsed = (
        window_end - previous_time
    ).total_seconds() / 3600

    area += active * final_elapsed

    mean_concurrency = (
        area / window_hours
        if window_hours > 0
        else 0.0
    )

    return {
        "Port_Calls_Within_Window": len(port_df),
        "Peak_Concurrent_Calls": peak,
        "Mean_Concurrent_Calls_Common_Window": mean_concurrency,
        "Occupancy_Area_Call_Hours": area,
        "Negative_Active_States": negative_states,
        "Final_Active_Calls": active,
    }


def calculate_all_port_metrics(
    df,
    window_start,
    window_end,
    window_hours,
):

    print("\n[4/7] CALCULATING PORT-LEVEL CONCURRENCY")
    print("-" * 70)

    results = []

    for (scenario, seed), group in df.groupby(
        ["Scenario", "Replication_Seed"]
    ):

        for port_code, port_df in group.groupby(
            "UNLOCODE_Normalised"
        ):

            metrics = calculate_port_concurrency(
                port_df,
                window_start,
                window_end,
                window_hours,
            )

            metrics.update({
                "Scenario": scenario,
                "Replication_Seed": seed,
                "UNLOCODE_Normalised": port_code,
                "Port_Name": port_df["Port"].iloc[0],
            })

            results.append(metrics)

    port_metrics = pd.DataFrame(results)

    if port_metrics[
        "Negative_Active_States"
    ].sum() != 0:

        raise AssertionError(
            "Negative active-call states detected."
        )

    if port_metrics[
        "Final_Active_Calls"
    ].sum() != 0:

        raise AssertionError(
            "Nonzero final active-call count detected."
        )

    print("Port-level records:", len(port_metrics))
    print("Negative active-call states: 0")
    print("Nonzero final active calls: 0")

    return port_metrics


# ============================================================
# 6. AFFECTED-CALL DELAY ANALYSIS
# ============================================================

def calculate_delay_metrics(df):

    print("\n[5/7] CALCULATING AFFECTED-CALL DELAY METRICS")
    print("-" * 70)

    rows = []

    for (scenario, seed), group in df.groupby(
        ["Scenario", "Replication_Seed"]
    ):

        affected = group[
            group["Is_Affected"] == True
        ]

        all_calls = group

        delays = affected[
            "Imposed_Delay_Hours"
        ]

        rows.append({
            "Scenario": scenario,
            "Replication_Seed": seed,
            "Total_Calls": len(all_calls),
            "Affected_Calls": len(affected),
            "Affected_Share_Percent": (
                len(affected) / len(all_calls) * 100
            ),
            "Total_Imposed_Delay_Hours": (
                all_calls["Imposed_Delay_Hours"].sum()
            ),
            "Affected_Mean_Delay_Hours": (
                delays.mean() if len(delays) else 0
            ),
            "Affected_Median_Delay_Hours": (
                delays.median() if len(delays) else 0
            ),
            "Affected_P90_Delay_Hours": (
                delays.quantile(0.90) if len(delays) else 0
            ),
            "Affected_Max_Delay_Hours": (
                delays.max() if len(delays) else 0
            ),
            "Unaffected_Calls": (
                len(all_calls) - len(affected)
            ),
        })

    return pd.DataFrame(rows)


# ============================================================
# 7. PAIRED PORT COMPARISON AGAINST BASELINE
# ============================================================

def create_port_comparison(port_metrics):

    baseline = port_metrics[
        port_metrics["Scenario"] == "S0_BASELINE"
    ][[
        "Replication_Seed",
        "UNLOCODE_Normalised",
        "Peak_Concurrent_Calls",
        "Mean_Concurrent_Calls_Common_Window",
    ]].rename(columns={
        "Peak_Concurrent_Calls": "Baseline_Peak",
        "Mean_Concurrent_Calls_Common_Window": "Baseline_Mean",
    })

    comparison = port_metrics.merge(
        baseline,
        on=[
            "Replication_Seed",
            "UNLOCODE_Normalised",
        ],
        how="left",
        validate="many_to_one",
    )

    comparison["Peak_Change"] = (
        comparison["Peak_Concurrent_Calls"]
        - comparison["Baseline_Peak"]
    )

    comparison["Mean_Concurrency_Change"] = (
        comparison["Mean_Concurrent_Calls_Common_Window"]
        - comparison["Baseline_Mean"]
    )

    comparison["Peak_Increased"] = (
        comparison["Peak_Change"] > 0
    )

    return comparison


# ============================================================
# 8. SCENARIO-LEVEL SUMMARY
# ============================================================

def create_scenario_summary(
    delay_metrics,
    port_metrics,
    port_comparison,
):

    rows = []

    for scenario in [
        "S0_BASELINE",
        "S1_MILD",
        "S2_MODERATE",
        "S3_SEVERE",
    ]:

        delay_group = delay_metrics[
            delay_metrics["Scenario"] == scenario
        ]

        port_group = port_metrics[
            port_metrics["Scenario"] == scenario
        ]

        comparison_group = port_comparison[
            port_comparison["Scenario"] == scenario
        ]

        rows.append({
            "Scenario": scenario,
            "Replications": len(delay_group),
            "Mean_Affected_Calls": (
                delay_group["Affected_Calls"].mean()
            ),
            "Mean_Affected_Share_Percent": (
                delay_group["Affected_Share_Percent"].mean()
            ),
            "Mean_Total_Imposed_Delay_Hours": (
                delay_group["Total_Imposed_Delay_Hours"].mean()
            ),
            "Mean_Affected_Call_Delay_Hours": (
                delay_group["Affected_Mean_Delay_Hours"].mean()
            ),
            "Mean_Affected_Median_Delay_Hours": (
                delay_group["Affected_Median_Delay_Hours"].mean()
            ),
            "Mean_Affected_P90_Delay_Hours": (
                delay_group["Affected_P90_Delay_Hours"].mean()
            ),
            "Mean_Max_Port_Peak": (
                port_group["Peak_Concurrent_Calls"].mean()
            ),
            "Mean_Peak_Change": (
                comparison_group["Peak_Change"].mean()
            ),
            "Ports_With_Increased_Peak_Mean": (
                comparison_group.groupby(
                    "Replication_Seed"
                )["Peak_Increased"].sum().mean()
            ),
            "Mean_Concurrency_Common_Window": (
                port_group[
                    "Mean_Concurrent_Calls_Common_Window"
                ].mean()
            ),
            "Mean_Concurrency_Change_Common_Window": (
                comparison_group[
                    "Mean_Concurrency_Change"
                ].mean()
            ),
        })

    return pd.DataFrame(rows)


# ============================================================
# 9. REPLICATION VARIABILITY
# ============================================================

def create_replication_variability(
    delay_metrics,
    port_metrics,
    port_comparison,
):

    merged = delay_metrics.merge(
        port_metrics.groupby(
            ["Scenario", "Replication_Seed"]
        ).agg(
            Maximum_Port_Peak=(
                "Peak_Concurrent_Calls",
                "max",
            ),
            Average_Port_Peak=(
                "Peak_Concurrent_Calls",
                "mean",
            ),
            Average_Port_Mean_Concurrency=(
                "Mean_Concurrent_Calls_Common_Window",
                "mean",
            ),
        ).reset_index(),
        on=["Scenario", "Replication_Seed"],
        validate="one_to_one",
    )

    increased_ports = (
        port_comparison.groupby(
            ["Scenario", "Replication_Seed"]
        )["Peak_Increased"]
        .sum()
        .reset_index(name="Ports_With_Increased_Peak")
    )

    merged = merged.merge(
        increased_ports,
        on=["Scenario", "Replication_Seed"],
        validate="one_to_one",
    )

    rows = []

    metrics = [
        "Total_Imposed_Delay_Hours",
        "Affected_Mean_Delay_Hours",
        "Affected_P90_Delay_Hours",
        "Maximum_Port_Peak",
        "Average_Port_Peak",
        "Average_Port_Mean_Concurrency",
        "Ports_With_Increased_Peak",
    ]

    for scenario, group in merged.groupby("Scenario"):

        for metric in metrics:

            rows.append({
                "Scenario": scenario,
                "Metric": metric,
                "Mean": group[metric].mean(),
                "Standard_Deviation": group[metric].std(ddof=0),
                "Minimum": group[metric].min(),
                "Maximum": group[metric].max(),
            })

    return merged, pd.DataFrame(rows)


# ============================================================
# 10. SAVE OUTPUTS AND REPORT
# ============================================================

def save_outputs(
    delay_metrics,
    port_metrics,
    port_comparison,
    scenario_summary,
    replication_results,
    variability,
    window_start,
    window_end,
    window_hours,
):

    print("\n[6/7] VALIDATING AND SAVING OUTPUTS")
    print("-" * 70)

    if not np.isfinite(
        scenario_summary.select_dtypes(
            include=[np.number]
        ).to_numpy()
    ).all():

        raise AssertionError(
            "Non-finite values found in scenario summary."
        )

    checks = {
        "Common window is positive": window_hours > 0,
        "All scenario summaries present": (
            len(scenario_summary) == 4
        ),
        "All port records have baseline comparison": (
            port_comparison["Baseline_Peak"].notna().all()
        ),
        "No negative concurrency states": (
            port_metrics["Negative_Active_States"].sum() == 0
        ),
        "No nonzero final active calls": (
            port_metrics["Final_Active_Calls"].sum() == 0
        ),
    }

    for name, passed in checks.items():
        print(f"{name}: {'PASS' if passed else 'FAIL'}")

    if not all(checks.values()):
        raise AssertionError(
            "Script 29 validation failed."
        )

    files = {
        "29_affected_call_delay_metrics.csv": delay_metrics,
        "29_common_window_port_metrics.csv": port_metrics,
        "29_port_disruption_comparison.csv": port_comparison,
        "29_disruption_impact_summary.csv": scenario_summary,
        "29_replication_level_results.csv": replication_results,
        "29_replication_variability.csv": variability,
    }

    for filename, data in files.items():
        data.to_csv(
            OUTPUT_TABLES / filename,
            index=False,
        )

    report_path = (
        OUTPUT_REPORTS
        / "29_disruption_impact_analysis_report.txt"
    )

    with open(report_path, "w", encoding="utf-8") as file:

        file.write(
            "SCRIPT 29: DISRUPTION IMPACT ANALYSIS\n"
        )
        file.write("=" * 75 + "\n\n")

        file.write("COMMON OBSERVATION WINDOW\n")
        file.write("-" * 75 + "\n")
        file.write(f"Start: {window_start}\n")
        file.write(f"End: {window_end}\n")
        file.write(f"Duration: {window_hours:.3f} hours\n\n")

        file.write("SCENARIO IMPACT SUMMARY\n")
        file.write("-" * 75 + "\n")
        file.write(
            scenario_summary.to_string(index=False)
        )
        file.write("\n\n")

        file.write("AFFECTED-CALL DELAY METRICS\n")
        file.write("-" * 75 + "\n")
        file.write(
            delay_metrics.to_string(index=False)
        )
        file.write("\n\n")

        file.write("REPLICATION VARIABILITY\n")
        file.write("-" * 75 + "\n")
        file.write(
            variability.to_string(index=False)
        )
        file.write("\n\n")

        file.write("METHODOLOGICAL LIMITATIONS\n")
        file.write("-" * 75 + "\n")
        file.write(
            "All disruption levels and delays are hypothetical assumptions.\n"
        )
        file.write(
            "Affected calls are randomly selected and are not confirmed "
            "Hormuz transits.\n"
        )
        file.write(
            "Concurrency uses historical port-call intervals as "
            "occupancy proxies, not actual berth occupancy.\n"
        )
        file.write(
            "The common window is the same for every scenario and seed. "
            "It starts at the earliest historical arrival and ends at "
            "the latest scenario departure.\n"
        )
        file.write(
            "The model does not yet include rerouting, vessel-level "
            "voyage propagation, or queueing.\n"
        )

    print("\n[7/7] FINAL SCENARIO SUMMARY")
    print("=" * 75)

    print(
        scenario_summary.to_string(
            index=False,
            float_format=lambda x: f"{x:.3f}",
        )
    )

    print("\nGENERATED FILES")
    print("=" * 75)

    for filename in files:
        print(f"- outputs/tables/{filename}")

    print(
        "- outputs/reports/"
        "29_disruption_impact_analysis_report.txt"
    )

    print("\nSCRIPT 29 COMPLETED SUCCESSFULLY")


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 75)
    print("SCRIPT 29: DISRUPTION IMPACT ANALYSIS")
    print("=" * 75)

    df = load_data()

    validate_structure(df)

    window_start, window_end, window_hours = (
        establish_common_window(df)
    )

    port_metrics = calculate_all_port_metrics(
        df,
        window_start,
        window_end,
        window_hours,
    )

    delay_metrics = calculate_delay_metrics(df)

    port_comparison = create_port_comparison(
        port_metrics
    )

    scenario_summary = create_scenario_summary(
        delay_metrics,
        port_metrics,
        port_comparison,
    )

    replication_results, variability = (
        create_replication_variability(
            delay_metrics,
            port_metrics,
            port_comparison,
        )
    )

    save_outputs(
        delay_metrics,
        port_metrics,
        port_comparison,
        scenario_summary,
        replication_results,
        variability,
        window_start,
        window_end,
        window_hours,
    )


if __name__ == "__main__":
    main()
