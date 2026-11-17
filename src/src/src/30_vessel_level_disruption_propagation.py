
"""
SCRIPT 30: VESSEL-LEVEL DISRUPTION PROPAGATION

Purpose:
Simulate a disruption affecting selected vessels and propagate
the resulting schedule delay through their subsequent port calls.

Input:
data/simulation_inputs/19_historical_arrival_schedule.csv

Design:
- Select affected vessels, not independent port calls.
- Select one disruption-onset call per affected vessel.
- Propagate delay to subsequent calls.
- Compare three hypothetical recovery policies.
- Use reproducible random seeds.
- Calculate port concurrency over one common observation window.

Important:
- No vessel is assumed to have crossed the Strait of Hormuz.
- The disruption is hypothetical.
- Inter-port elapsed time is not treated as pure sailing time.
- Recovery policies are sensitivity assumptions, not observed behaviour.
"""

from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# 1. PROJECT PATHS AND CONFIGURATION
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


# Random seeds: same seed is used across scenarios and policies.
SEEDS = [21, 42, 63, 84, 105]


# Scenario assumptions: share of vessels selected and initial delay.
SCENARIOS = {
    "S0_BASELINE": {
        "affected_share": 0.00,
        "initial_delay_hours": 0,
    },
    "S1_MILD": {
        "affected_share": 0.10,
        "initial_delay_hours": 24,
    },
    "S2_MODERATE": {
        "affected_share": 0.25,
        "initial_delay_hours": 72,
    },
    "S3_SEVERE": {
        "affected_share": 0.50,
        "initial_delay_hours": 168,
    },
}


# Hypothetical schedule recovery policies.
RECOVERY_POLICIES = {
    "NO_RECOVERY": {
        "type": "none",
        "value": 0,
    },
    "PARTIAL_RECOVERY_25": {
        "type": "fraction",
        "value": 0.25,
    },
    "FIXED_RECOVERY_12H": {
        "type": "fixed",
        "value": 12,
    },
}


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

    print("\n[1/9] LOADING HISTORICAL SCHEDULE")
    print("-" * 75)

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
            f"Missing required columns: {missing}"
        )

    for col in [
        "Actual_Arrival_UTC",
        "Actual_Departure_UTC",
    ]:
        df[col] = pd.to_datetime(
            df[col],
            utc=True,
            errors="coerce",
        )

    if df[REQUIRED_COLUMNS].isna().any().any():
        raise ValueError(
            "Missing or invalid required input values."
        )

    if df["Simulation_Record_ID"].duplicated().any():
        raise ValueError(
            "Duplicate Simulation_Record_ID values found."
        )

    if df["IMO_Normalised"].astype(str).str.strip().eq("").any():
        raise ValueError("Empty vessel IMO found.")

    if (
        df["Actual_Departure_UTC"]
        <= df["Actual_Arrival_UTC"]
    ).any():
        raise ValueError(
            "Invalid port-call interval found."
        )

    # Recalculate observed stay for consistency checking.
    calculated_stay = (
        df["Actual_Departure_UTC"]
        - df["Actual_Arrival_UTC"]
    ).dt.total_seconds() / 3600

    mismatch = (
        calculated_stay - df["Actual_Stay_Hours"]
    ).abs() > 0.01

    if mismatch.any():
        raise ValueError(
            f"Port-stay mismatch in {mismatch.sum()} records."
        )

    df = df.sort_values(
        ["IMO_Normalised", "Actual_Arrival_UTC"]
    ).reset_index(drop=True)

    print("Valid port calls:", len(df))
    print("Unique vessels:", df["IMO_Normalised"].nunique())
    print("Unique ports:", df["UNLOCODE_Normalised"].nunique())
    print("Port-stay mismatches:", mismatch.sum())

    return df


# ============================================================
# 3. SELECT AFFECTED VESSELS AND DISRUPTION ONSET
# ============================================================

def select_disrupted_vessels(df, scenario, seed):

    settings = SCENARIOS[scenario]

    vessel_ids = sorted(
        df["IMO_Normalised"].astype(str).unique()
    )

    total_vessels = len(vessel_ids)

    affected_count = int(
        round(total_vessels * settings["affected_share"])
    )

    if affected_count == 0:
        return {}

    rng = np.random.default_rng(seed)

    selected_vessels = rng.choice(
        vessel_ids,
        size=affected_count,
        replace=False,
    )

    selected = {}

    for vessel_id in selected_vessels:

        vessel_calls = (
            df[df["IMO_Normalised"].astype(str) == vessel_id]
            .sort_values("Actual_Arrival_UTC")
        )

        # Randomly select the call at which disruption begins.
        onset_position = int(
            rng.integers(0, len(vessel_calls))
        )

        onset_record_id = vessel_calls.iloc[
            onset_position
        ]["Simulation_Record_ID"]

        selected[vessel_id] = {
            "onset_record_id": onset_record_id,
            "onset_position": onset_position,
        }

    return selected


# ============================================================
# 4. CALCULATE RECOVERY BETWEEN SUBSEQUENT CALLS
# ============================================================

def recover_delay(current_delay, policy):

    policy_type = policy["type"]
    value = policy["value"]

    if current_delay <= 0:
        return 0.0

    if policy_type == "none":
        recovered = 0.0

    elif policy_type == "fraction":
        recovered = current_delay * value

    elif policy_type == "fixed":
        recovered = min(current_delay, value)

    else:
        raise ValueError(
            f"Unknown recovery policy: {policy_type}"
        )

    return min(current_delay, recovered)


# ============================================================
# 5. PROPAGATE DISRUPTION THROUGH VESSEL SCHEDULE
# ============================================================

def simulate_vessel_schedule(
    df,
    scenario,
    policy_name,
    seed,
    selected_vessels,
):

    settings = SCENARIOS[scenario]
    policy = RECOVERY_POLICIES[policy_name]

    initial_delay = settings["initial_delay_hours"]

    results = []

    for vessel_id, vessel_calls in df.groupby(
        "IMO_Normalised",
        sort=False,
    ):

        vessel_id = str(vessel_id)

        vessel_calls = (
            vessel_calls
            .sort_values("Actual_Arrival_UTC")
            .reset_index(drop=True)
        )

        is_selected = vessel_id in selected_vessels

        onset_record_id = None
        onset_position = None

        if is_selected:
            onset_record_id = selected_vessels[
                vessel_id
            ]["onset_record_id"]

            onset_position = selected_vessels[
                vessel_id
            ]["onset_position"]

        carried_delay = 0.0
        disruption_started = False

        for position, row in vessel_calls.iterrows():

            record_id = row["Simulation_Record_ID"]

            is_onset_call = (
                is_selected
                and record_id == onset_record_id
            )

            recovered_hours = 0.0

            if is_onset_call:

                disruption_started = True
                carried_delay = float(initial_delay)

            elif disruption_started:

                # Apply recovery only between successive calls.
                recovered_hours = recover_delay(
                    carried_delay,
                    policy,
                )

                carried_delay = max(
                    0.0,
                    carried_delay - recovered_hours,
                )

            call_delay = (
                carried_delay
                if disruption_started
                else 0.0
            )

            shifted_arrival = (
                row["Actual_Arrival_UTC"]
                + pd.Timedelta(hours=call_delay)
            )

            shifted_departure = (
                row["Actual_Departure_UTC"]
                + pd.Timedelta(hours=call_delay)
            )

            results.append({
                "Simulation_Record_ID": record_id,
                "IMO_Normalised": vessel_id,
                "UNLOCODE_Normalised": row[
                    "UNLOCODE_Normalised"
                ],
                "Port": row["Port"],
                "Scenario": scenario,
                "Recovery_Policy": policy_name,
                "Replication_Seed": seed,
                "Is_Selected_Vessel": is_selected,
                "Is_Disrupted_Call": disruption_started,
                "Is_Disruption_Onset": is_onset_call,
                "Onset_Record_ID": onset_record_id,
                "Vessel_Call_Sequence": position + 1,
                "Initial_Disruption_Hours": (
                    initial_delay if is_onset_call else 0
                ),
                "Recovered_Hours_At_Transition": (
                    recovered_hours
                ),
                "Accumulated_Delay_Hours": call_delay,
                "Scenario_Arrival_UTC": shifted_arrival,
                "Scenario_Departure_UTC": shifted_departure,
                "Actual_Arrival_UTC": row[
                    "Actual_Arrival_UTC"
                ],
                "Actual_Departure_UTC": row[
                    "Actual_Departure_UTC"
                ],
            })

    result = pd.DataFrame(results)

    return result


# ============================================================
# 6. VALIDATE PROPAGATED SCHEDULE
# ============================================================

def validate_replication(result, input_df):

    if len(result) != len(input_df):
        raise AssertionError(
            "Call count changed during propagation."
        )

    if result["Simulation_Record_ID"].duplicated().any():
        raise AssertionError(
            "Duplicate call IDs in simulation output."
        )

    if (
        result["Scenario_Departure_UTC"]
        <= result["Scenario_Arrival_UTC"]
    ).any():
        raise AssertionError(
            "Invalid simulated call interval."
        )

    delay_check = (
        result["Scenario_Arrival_UTC"]
        - result["Actual_Arrival_UTC"]
    ).dt.total_seconds() / 3600

    if not np.allclose(
        delay_check,
        result["Accumulated_Delay_Hours"],
        atol=0.001,
    ):
        raise AssertionError(
            "Arrival delay does not match accumulated delay."
        )

    stay_original = (
        result["Actual_Departure_UTC"]
        - result["Actual_Arrival_UTC"]
    ).dt.total_seconds()

    stay_simulated = (
        result["Scenario_Departure_UTC"]
        - result["Scenario_Arrival_UTC"]
    ).dt.total_seconds()

    if not np.allclose(
        stay_original,
        stay_simulated,
        atol=0.001,
    ):
        raise AssertionError(
            "Port-call duration changed during propagation."
        )

    if (result["Accumulated_Delay_Hours"] < 0).any():
        raise AssertionError(
            "Negative accumulated delay found."
        )

    return True


# ============================================================
# 7. PORT CONCURRENCY OVER A COMMON OBSERVATION WINDOW
# ============================================================

def calculate_concurrency(
    port_df,
    window_start,
    window_end,
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

        if departure <= arrival:
            continue

        events.append((arrival, 1))
        events.append((departure, -1))

    if not events:
        return 0, 0.0, 0.0

    event_df = pd.DataFrame(
        events,
        columns=["Timestamp", "Delta"],
    )

    event_df = (
        event_df.groupby("Timestamp", as_index=False)["Delta"]
        .sum()
        .sort_values("Timestamp")
    )

    active = 0
    peak = 0
    area = 0.0
    previous = window_start

    for row in event_df.itertuples(index=False):

        elapsed = (
            row.Timestamp - previous
        ).total_seconds() / 3600

        area += active * elapsed
        active += int(row.Delta)

        if active < 0:
            raise AssertionError(
                "Negative active-call count."
            )

        peak = max(peak, active)
        previous = row.Timestamp

    final_elapsed = (
        window_end - previous
    ).total_seconds() / 3600

    area += active * final_elapsed

    duration = (
        window_end - window_start
    ).total_seconds() / 3600

    mean_concurrency = (
        area / duration if duration > 0 else 0
    )

    return peak, mean_concurrency, area


def calculate_port_metrics(
    all_results,
    window_start,
    window_end,
):

    rows = []

    for (
        scenario,
        policy,
        seed,
        port_code,
    ), group in all_results.groupby(
        [
            "Scenario",
            "Recovery_Policy",
            "Replication_Seed",
            "UNLOCODE_Normalised",
        ]
    ):

        peak, mean_concurrency, area = (
            calculate_concurrency(
                group,
                window_start,
                window_end,
            )
        )

        rows.append({
            "Scenario": scenario,
            "Recovery_Policy": policy,
            "Replication_Seed": seed,
            "UNLOCODE_Normalised": port_code,
            "Port_Name": group["Port"].iloc[0],
            "Port_Calls": len(group),
            "Peak_Concurrent_Calls": peak,
            "Mean_Concurrent_Calls_Common_Window": (
                mean_concurrency
            ),
            "Occupancy_Area_Call_Hours": area,
        })

    return pd.DataFrame(rows)


# ============================================================
# 8. REPLICATION-LEVEL RESULTS
# ============================================================

def calculate_replication_metrics(all_results):

    rows = []

    for (
        scenario,
        policy,
        seed,
    ), group in all_results.groupby(
        ["Scenario", "Recovery_Policy", "Replication_Seed"]
    ):

        affected_calls = group[
            group["Is_Disrupted_Call"]
        ]

        selected_vessels = group[
            group["Is_Selected_Vessel"]
        ]["IMO_Normalised"].nunique()

        affected_vessels = affected_calls[
            "IMO_Normalised"
        ].nunique()

        onset_calls = group[
            group["Is_Disruption_Onset"]
        ]

        rows.append({
            "Scenario": scenario,
            "Recovery_Policy": policy,
            "Replication_Seed": seed,
            "Total_Vessels": group[
                "IMO_Normalised"
            ].nunique(),
            "Selected_Vessels": selected_vessels,
            "Vessels_With_Disrupted_Calls": affected_vessels,
            "Total_Calls": len(group),
            "Disrupted_Calls": len(affected_calls),
            "Disrupted_Call_Share_Percent": (
                len(affected_calls) / len(group) * 100
            ),
            "Disruption_Onset_Calls": len(onset_calls),
            "Total_Accumulated_Delay_Hours": (
                group["Accumulated_Delay_Hours"].sum()
            ),
            "Mean_Delay_Per_Disrupted_Call": (
                affected_calls[
                    "Accumulated_Delay_Hours"
                ].mean()
                if len(affected_calls) else 0
            ),
            "Maximum_Accumulated_Delay_Hours": (
                group["Accumulated_Delay_Hours"].max()
            ),
            "Total_Recovered_Hours": (
                group[
                    "Recovered_Hours_At_Transition"
                ].sum()
            ),
        })

    return pd.DataFrame(rows)


# ============================================================
# 9. SCENARIO AND POLICY SUMMARY
# ============================================================

def create_scenario_summary(
    replication_metrics,
    port_metrics,
):

    port_replication = (
        port_metrics.groupby(
            [
                "Scenario",
                "Recovery_Policy",
                "Replication_Seed",
            ]
        )
        .agg(
            Maximum_Port_Peak=(
                "Peak_Concurrent_Calls",
                "max",
            ),
            Average_Port_Peak=(
                "Peak_Concurrent_Calls",
                "mean",
            ),
            Average_Port_Concurrency=(
                "Mean_Concurrent_Calls_Common_Window",
                "mean",
            ),
        )
        .reset_index()
    )

    combined = replication_metrics.merge(
        port_replication,
        on=[
            "Scenario",
            "Recovery_Policy",
            "Replication_Seed",
        ],
        validate="one_to_one",
    )

    summary = (
        combined.groupby(
            ["Scenario", "Recovery_Policy"]
        )
        .agg(
            Replications=(
                "Replication_Seed",
                "count",
            ),
            Mean_Selected_Vessels=(
                "Selected_Vessels",
                "mean",
            ),
            Mean_Disrupted_Vessels=(
                "Vessels_With_Disrupted_Calls",
                "mean",
            ),
            Mean_Disrupted_Calls=(
                "Disrupted_Calls",
                "mean",
            ),
            Mean_Disrupted_Call_Share_Percent=(
                "Disrupted_Call_Share_Percent",
                "mean",
            ),
            Mean_Total_Accumulated_Delay_Hours=(
                "Total_Accumulated_Delay_Hours",
                "mean",
            ),
            Mean_Delay_Per_Disrupted_Call=(
                "Mean_Delay_Per_Disrupted_Call",
                "mean",
            ),
            Mean_Maximum_Accumulated_Delay_Hours=(
                "Maximum_Accumulated_Delay_Hours",
                "mean",
            ),
            Mean_Total_Recovered_Hours=(
                "Total_Recovered_Hours",
                "mean",
            ),
            Mean_Maximum_Port_Peak=(
                "Maximum_Port_Peak",
                "mean",
            ),
            Mean_Average_Port_Peak=(
                "Average_Port_Peak",
                "mean",
            ),
            Mean_Port_Concurrency=(
                "Average_Port_Concurrency",
                "mean",
            ),
        )
        .reset_index()
    )

    return combined, summary


# ============================================================
# 10. SAVE OUTPUTS AND REPORT
# ============================================================

def save_outputs(
    all_results,
    port_metrics,
    replication_metrics,
    combined_metrics,
    scenario_summary,
    window_start,
    window_end,
):

    print("\n[8/9] SAVING OUTPUTS")
    print("-" * 75)

    outputs = {
        "30_vessel_disruption_call_results.csv": all_results,
        "30_vessel_disruption_port_metrics.csv": port_metrics,
        "30_vessel_disruption_replication_metrics.csv": (
            replication_metrics
        ),
        "30_vessel_disruption_combined_metrics.csv": (
            combined_metrics
        ),
        "30_vessel_disruption_scenario_summary.csv": (
            scenario_summary
        ),
    }

    for filename, data in outputs.items():
        data.to_csv(
            TABLE_DIR / filename,
            index=False,
        )

    report_path = (
        REPORT_DIR
        / "30_vessel_level_disruption_report.txt"
    )

    with open(
        report_path,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            "SCRIPT 30: VESSEL-LEVEL DISRUPTION PROPAGATION\n"
        )
        file.write("=" * 85 + "\n\n")

        file.write("COMMON OBSERVATION WINDOW\n")
        file.write("-" * 85 + "\n")
        file.write(f"Start: {window_start}\n")
        file.write(f"End: {window_end}\n\n")

        file.write("SCENARIO AND RECOVERY POLICY SUMMARY\n")
        file.write("-" * 85 + "\n")
        file.write(
            scenario_summary.to_string(index=False)
        )
        file.write("\n\n")

        file.write("METHODOLOGICAL ASSUMPTIONS\n")
        file.write("-" * 85 + "\n")
        file.write(
            "Disruptions are hypothetical schedule delays.\n"
        )
        file.write(
            "Affected units are vessels, not independent port calls.\n"
        )
        file.write(
            "One disruption-onset call is selected per affected vessel.\n"
        )
        file.write(
            "The delay propagates through subsequent calls.\n"
        )
        file.write(
            "Recovery policies are hypothetical sensitivity assumptions.\n"
        )
        file.write(
            "Inter-port elapsed time is not treated as pure sailing time.\n"
        )
        file.write(
            "No confirmed Strait of Hormuz transit is assumed.\n"
        )
        file.write(
            "Port concurrency is not equivalent to berth occupancy "
            "or verified port capacity.\n"
        )

    print("Saved tables:")
    for filename in outputs:
        print(f"- outputs/tables/{filename}")

    print(
        "- outputs/reports/"
        "30_vessel_level_disruption_report.txt"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 85)
    print("SCRIPT 30: VESSEL-LEVEL DISRUPTION PROPAGATION")
    print("=" * 85)

    df = load_schedule()

    # Select disruption onset once per scenario and seed.
    # The same selected vessels and onset calls are used for
    # every recovery policy in that scenario/seed combination.
    selected_cache = {}

    all_replications = []

    print("\n[2/9] PREPARING VESSEL-LEVEL DISRUPTIONS")
    print("-" * 75)

    for scenario in SCENARIOS:

        for seed in SEEDS:

            selected = select_disrupted_vessels(
                df,
                scenario,
                seed,
            )

            selected_cache[(scenario, seed)] = selected

            print(
                f"{scenario} | Seed {seed} | "
                f"Selected vessels: {len(selected)}"
            )

    print("\n[3/9] RUNNING PROPAGATION EXPERIMENTS")
    print("-" * 75)

    total_runs = (
        len(SCENARIOS)
        * len(RECOVERY_POLICIES)
        * len(SEEDS)
    )

    run_number = 0

    for scenario in SCENARIOS:

        for policy_name in RECOVERY_POLICIES:

            for seed in SEEDS:

                run_number += 1

                print(
                    f"Run {run_number}/{total_runs}: "
                    f"{scenario} | {policy_name} | Seed {seed}"
                )

                selected = selected_cache[
                    (scenario, seed)
                ]

                result = simulate_vessel_schedule(
                    df,
                    scenario,
                    policy_name,
                    seed,
                    selected,
                )

                validate_replication(
                    result,
                    df,
                )

                all_replications.append(result)

    all_results = pd.concat(
        all_replications,
        ignore_index=True,
    )

    print("\n[4/9] CHECKING EXPERIMENT OUTPUT")
    print("-" * 75)

    expected_runs = total_runs
    expected_records = (
        len(df) * expected_runs
    )

    print("Expected runs:", expected_runs)
    print("Actual runs:", all_results[
        [
            "Scenario",
            "Recovery_Policy",
            "Replication_Seed",
        ]
    ].drop_duplicates().shape[0])

    print("Expected call records:", expected_records)
    print("Actual call records:", len(all_results))

    if len(all_results) != expected_records:
        raise AssertionError(
            "Unexpected number of call-level records."
        )

    if all_results[
        "Accumulated_Delay_Hours"
    ].isna().any():
        raise AssertionError(
            "Missing accumulated delays."
        )

    # Fixed global observation window for every scenario,
    # recovery policy and replication.
    print("\n[5/9] ESTABLISHING COMMON OBSERVATION WINDOW")
    print("-" * 75)

    window_start = df[
        "Actual_Arrival_UTC"
    ].min()

    window_end = all_results[
        "Scenario_Departure_UTC"
    ].max()

    print("Window start:", window_start)
    print("Window end:", window_end)

    print("\n[6/9] CALCULATING PORT CONCURRENCY")
    print("-" * 75)

    port_metrics = calculate_port_metrics(
        all_results,
        window_start,
        window_end,
    )

    replication_metrics = calculate_replication_metrics(
        all_results
    )

    combined_metrics, scenario_summary = (
        create_scenario_summary(
            replication_metrics,
            port_metrics,
        )
    )

    print("\n[7/9] FINAL VALIDATION")
    print("-" * 75)

    checks = {
        "Expected number of simulation runs": (
            combined_metrics.shape[0]
            == len(SCENARIOS)
            * len(RECOVERY_POLICIES)
            * len(SEEDS)
        ),
        "No negative accumulated delays": (
            (all_results["Accumulated_Delay_Hours"] >= 0).all()
        ),
        "No negative recovered hours": (
            (all_results["Recovered_Hours_At_Transition"] >= 0).all()
        ),
        "No missing simulated timestamps": (
            all_results[
                [
                    "Scenario_Arrival_UTC",
                    "Scenario_Departure_UTC",
                ]
            ].notna().all().all()
        ),
        "No negative port concurrency": (
            (port_metrics["Peak_Concurrent_Calls"] >= 0).all()
        ),
        "All scenario-policy combinations present": (
            len(scenario_summary)
            == len(SCENARIOS) * len(RECOVERY_POLICIES)
        ),
    }

    for name, passed in checks.items():
        print(f"{name}: {'PASS' if passed else 'FAIL'}")

    if not all(checks.values()):
        raise AssertionError(
            "One or more validation checks failed."
        )

    save_outputs(
        all_results,
        port_metrics,
        replication_metrics,
        combined_metrics,
        scenario_summary,
        window_start,
        window_end,
    )

    print("\n[9/9] FINAL SUMMARY")
    print("=" * 85)

    print(
        scenario_summary.to_string(
            index=False,
            float_format=lambda x: f"{x:.3f}",
        )
    )

    print("\nSCRIPT 30 COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()
