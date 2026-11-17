
"""
SCRIPT 31: RECOVERY STRATEGY EVALUATION

Purpose:
Evaluate the recovery policies tested in Script 30.

Comparisons:
1. Recovery policies against NO_RECOVERY.
2. Accumulated delay reduction.
3. Maximum port-specific peak concurrency.
4. Port-level congestion changes.
5. Replication-level variability across random seeds.
6. Scenario impact relative to baseline.

No simulation is rerun.
All inputs are existing Script 30 outputs.
"""

from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# 1. PATHS AND CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

INPUT_DIR = ROOT / "outputs" / "tables"
OUTPUT_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


CALL_FILE = (
    INPUT_DIR
    / "30_vessel_disruption_call_results.csv"
)

PORT_FILE = (
    INPUT_DIR
    / "30_vessel_disruption_port_metrics.csv"
)

REPLICATION_FILE = (
    INPUT_DIR
    / "30_vessel_disruption_replication_metrics.csv"
)

COMBINED_FILE = (
    INPUT_DIR
    / "30_vessel_disruption_combined_metrics.csv"
)


SCENARIOS = [
    "S0_BASELINE",
    "S1_MILD",
    "S2_MODERATE",
    "S3_SEVERE",
]

POLICIES = [
    "NO_RECOVERY",
    "PARTIAL_RECOVERY_25",
    "FIXED_RECOVERY_12H",
]

RECOVERY_POLICIES = [
    "PARTIAL_RECOVERY_25",
    "FIXED_RECOVERY_12H",
]


# ============================================================
# 2. LOAD AND VALIDATE INPUTS
# ============================================================

def load_inputs():

    print("\n[1/8] LOADING SCRIPT 30 OUTPUTS")
    print("-" * 75)

    required_files = [
        CALL_FILE,
        PORT_FILE,
        REPLICATION_FILE,
        COMBINED_FILE,
    ]

    for path in required_files:
        if not path.exists():
            raise FileNotFoundError(
                f"Required Script 30 output missing: {path}"
            )

    calls = pd.read_csv(CALL_FILE)
    ports = pd.read_csv(PORT_FILE)
    replications = pd.read_csv(REPLICATION_FILE)
    combined = pd.read_csv(COMBINED_FILE)

    required_call_columns = [
        "Simulation_Record_ID",
        "IMO_Normalised",
        "UNLOCODE_Normalised",
        "Scenario",
        "Recovery_Policy",
        "Replication_Seed",
        "Accumulated_Delay_Hours",
        "Is_Disrupted_Call",
    ]

    required_port_columns = [
        "Scenario",
        "Recovery_Policy",
        "Replication_Seed",
        "UNLOCODE_Normalised",
        "Port_Name",
        "Peak_Concurrent_Calls",
        "Mean_Concurrent_Calls_Common_Window",
    ]

    required_replication_columns = [
        "Scenario",
        "Recovery_Policy",
        "Replication_Seed",
        "Selected_Vessels",
        "Disrupted_Calls",
        "Total_Accumulated_Delay_Hours",
        "Total_Recovered_Hours",
    ]

    required_combined_columns = [
    "Scenario",
    "Recovery_Policy",
    "Replication_Seed",
    "Maximum_Port_Peak",
    "Average_Port_Peak",
    "Average_Port_Concurrency",
]

    for name, df, required in [
        ("Call results", calls, required_call_columns),
        ("Port results", ports, required_port_columns),
        ("Replication results", replications, required_replication_columns),
        ("Combined results", combined, required_combined_columns),
    ]:

        missing = [
            col for col in required
            if col not in df.columns
        ]

        if missing:
            raise ValueError(
                f"{name} missing columns: {missing}"
            )

    print("Call-level records:", len(calls))
    print("Port-level records:", len(ports))
    print("Replication-level records:", len(replications))
    print("Combined records:", len(combined))

    return calls, ports, replications, combined


# ============================================================
# 3. VALIDATE SCENARIO AND POLICY STRUCTURE
# ============================================================

def validate_structure(
    calls,
    ports,
    replications,
    combined,
):

    print("\n[2/8] VALIDATING SCENARIO STRUCTURE")
    print("-" * 75)

    expected_combinations = {
        (scenario, policy)
        for scenario in SCENARIOS
        for policy in POLICIES
    }

    actual_combinations = set(
        zip(
            replications["Scenario"],
            replications["Recovery_Policy"],
        )
    )

    if actual_combinations != expected_combinations:
        raise ValueError(
            "Missing or unexpected scenario-policy combinations."
        )

    expected_seeds = set(
        replications["Replication_Seed"].unique()
    )

    if len(expected_seeds) != 5:
        raise ValueError(
            f"Expected 5 random seeds, found {len(expected_seeds)}."
        )

    expected_runs = (
        len(SCENARIOS)
        * len(POLICIES)
        * len(expected_seeds)
    )

    if len(replications) != expected_runs:
        raise ValueError(
            "Unexpected replication-level record count."
        )

    if len(combined) != expected_runs:
        raise ValueError(
            "Unexpected combined record count."
        )

    if replications.duplicated(
        ["Scenario", "Recovery_Policy", "Replication_Seed"]
    ).any():
        raise ValueError(
            "Duplicate replication-level records."
        )

    if ports.duplicated(
        [
            "Scenario",
            "Recovery_Policy",
            "Replication_Seed",
            "UNLOCODE_Normalised",
        ]
    ).any():
        raise ValueError(
            "Duplicate port-level records."
        )

    if calls.duplicated(
        [
            "Scenario",
            "Recovery_Policy",
            "Replication_Seed",
            "Simulation_Record_ID",
        ]
    ).any():
        raise ValueError(
            "Duplicate call-level records."
        )

    print("All scenario-policy combinations: PASS")
    print("Five random seeds: PASS")
    print("Replication record count: PASS")
    print("Duplicate checks: PASS")

    return sorted(expected_seeds)


# ============================================================
# 4. COMPARE RECOVERY POLICIES WITH NO RECOVERY
# ============================================================

def calculate_policy_comparison(replications):

    print("\n[3/8] COMPARING RECOVERY POLICIES")
    print("-" * 75)

    reference = replications[
        replications["Recovery_Policy"] == "NO_RECOVERY"
    ][[
        "Scenario",
        "Replication_Seed",
        "Total_Accumulated_Delay_Hours",
        "Total_Recovered_Hours",
        "Disrupted_Calls",
        "Selected_Vessels",
    ]].rename(columns={
        "Total_Accumulated_Delay_Hours": "No_Recovery_Delay_Hours",
        "Total_Recovered_Hours": "No_Recovery_Recovered_Hours",
        "Disrupted_Calls": "No_Recovery_Disrupted_Calls",
        "Selected_Vessels": "No_Recovery_Selected_Vessels",
    })

    comparison = replications.merge(
        reference,
        on=["Scenario", "Replication_Seed"],
        how="left",
        validate="many_to_one",
    )

    comparison["Delay_Reduction_Hours"] = (
        comparison["No_Recovery_Delay_Hours"]
        - comparison["Total_Accumulated_Delay_Hours"]
    )

    comparison["Delay_Reduction_Percent"] = np.where(
        comparison["No_Recovery_Delay_Hours"] > 0,
        (
            comparison["Delay_Reduction_Hours"]
            / comparison["No_Recovery_Delay_Hours"]
        ) * 100,
        0.0,
    )

    comparison["Delay_Reduction_Per_Disrupted_Call"] = np.where(
        comparison["Disrupted_Calls"] > 0,
        (
            comparison["Delay_Reduction_Hours"]
            / comparison["Disrupted_Calls"]
        ),
        0.0,
    )

    comparison["Disrupted_Call_Count_Difference"] = (
        comparison["Disrupted_Calls"]
        - comparison["No_Recovery_Disrupted_Calls"]
    )

    return comparison


# ============================================================
# 5. PORT-LEVEL CONGESTION TRADE-OFF
# ============================================================

def calculate_port_tradeoffs(ports):

    print("\n[4/8] ANALYSING PORT-LEVEL CONGESTION")
    print("-" * 75)

    reference = ports[
        ports["Recovery_Policy"] == "NO_RECOVERY"
    ][[
        "Scenario",
        "Replication_Seed",
        "UNLOCODE_Normalised",
        "Peak_Concurrent_Calls",
        "Mean_Concurrent_Calls_Common_Window",
    ]].rename(columns={
        "Peak_Concurrent_Calls": "No_Recovery_Peak",
        "Mean_Concurrent_Calls_Common_Window": (
            "No_Recovery_Mean_Concurrency"
        ),
    })

    comparison = ports.merge(
        reference,
        on=[
            "Scenario",
            "Replication_Seed",
            "UNLOCODE_Normalised",
        ],
        how="left",
        validate="many_to_one",
    )

    if comparison["No_Recovery_Peak"].isna().any():
        raise ValueError(
            "Missing matching no-recovery port reference."
        )

    comparison["Peak_Change_vs_No_Recovery"] = (
        comparison["Peak_Concurrent_Calls"]
        - comparison["No_Recovery_Peak"]
    )

    comparison["Mean_Concurrency_Change_vs_No_Recovery"] = (
        comparison["Mean_Concurrent_Calls_Common_Window"]
        - comparison["No_Recovery_Mean_Concurrency"]
    )

    comparison["Peak_Increased"] = (
        comparison["Peak_Change_vs_No_Recovery"] > 0
    )

    comparison["Peak_Decreased"] = (
        comparison["Peak_Change_vs_No_Recovery"] < 0
    )

    comparison["Peak_Unchanged"] = (
        comparison["Peak_Change_vs_No_Recovery"] == 0
    )

    return comparison


# ============================================================
# 6. CALCULATE PORT-LEVEL BASELINE IMPACT
# ============================================================

def calculate_baseline_comparison(ports):

    baseline = ports[
        ports["Scenario"] == "S0_BASELINE"
    ][[
        "Recovery_Policy",
        "Replication_Seed",
        "UNLOCODE_Normalised",
        "Peak_Concurrent_Calls",
        "Mean_Concurrent_Calls_Common_Window",
    ]].rename(columns={
        "Peak_Concurrent_Calls": "Baseline_Peak",
        "Mean_Concurrent_Calls_Common_Window": (
            "Baseline_Mean_Concurrency"
        ),
    })

    comparison = ports[
        ports["Scenario"] != "S0_BASELINE"
    ].merge(
        baseline,
        on=[
            "Recovery_Policy",
            "Replication_Seed",
            "UNLOCODE_Normalised",
        ],
        how="left",
        validate="many_to_one",
    )

    if comparison["Baseline_Peak"].isna().any():
        raise ValueError(
            "Missing baseline port reference."
        )

    comparison["Peak_Change_vs_Baseline"] = (
        comparison["Peak_Concurrent_Calls"]
        - comparison["Baseline_Peak"]
    )

    comparison["Mean_Concurrency_Change_vs_Baseline"] = (
        comparison["Mean_Concurrent_Calls_Common_Window"]
        - comparison["Baseline_Mean_Concurrency"]
    )

    return comparison


# ============================================================
# 7. SCENARIO-LEVEL POLICY SUMMARY
# ============================================================

def create_policy_summary(
    comparison,
    combined,
    port_tradeoffs,
):

    print("\n[5/8] BUILDING SCENARIO-LEVEL SUMMARY")
    print("-" * 75)

    rows = []

    for scenario in SCENARIOS:

        for policy in POLICIES:

            group = comparison[
                (comparison["Scenario"] == scenario)
                & (comparison["Recovery_Policy"] == policy)
            ]

            combined_group = combined[
                (combined["Scenario"] == scenario)
                & (combined["Recovery_Policy"] == policy)
            ]

            port_group = port_tradeoffs[
                (port_tradeoffs["Scenario"] == scenario)
                & (port_tradeoffs["Recovery_Policy"] == policy)
            ]

            if group.empty or combined_group.empty:
                raise ValueError(
                    f"Missing results for {scenario}, {policy}"
                )

            seed_port_counts = (
                port_group.groupby("Replication_Seed")
                .agg(
                    Ports_Peak_Increased=(
                        "Peak_Increased",
                        "sum",
                    ),
                    Ports_Peak_Decreased=(
                        "Peak_Decreased",
                        "sum",
                    ),
                    Ports_Peak_Unchanged=(
                        "Peak_Unchanged",
                        "sum",
                    ),
                )
            )

            rows.append({
                "Scenario": scenario,
                "Recovery_Policy": policy,
                "Replications": len(group),

                "Mean_Accumulated_Delay_Hours": (
                    group[
                        "Total_Accumulated_Delay_Hours"
                    ].mean()
                ),

                "Mean_Delay_Reduction_Hours": (
                    group["Delay_Reduction_Hours"].mean()
                ),

                "Mean_Delay_Reduction_Percent": (
                    group["Delay_Reduction_Percent"].mean()
                ),

                "SD_Delay_Reduction_Percent": (
                    group["Delay_Reduction_Percent"].std(ddof=0)
                ),

                "Mean_Total_Recovered_Hours": (
                    group["Total_Recovered_Hours"].mean()
                ),

                "Mean_Maximum_Port_Peak": (
                    combined_group["Maximum_Port_Peak"].mean()
                ),

                "Mean_Average_Port_Peak": (
                    combined_group["Average_Port_Peak"].mean()
                ),

                "Mean_Port_Concurrency": (
    combined_group[
        "Average_Port_Concurrency"
    ].mean()
),

                "Mean_Ports_With_Increased_Peak": (
                    seed_port_counts[
                        "Ports_Peak_Increased"
                    ].mean()
                ),

                "Mean_Ports_With_Decreased_Peak": (
                    seed_port_counts[
                        "Ports_Peak_Decreased"
                    ].mean()
                ),

                "Mean_Ports_With_Unchanged_Peak": (
                    seed_port_counts[
                        "Ports_Peak_Unchanged"
                    ].mean()
                ),

                "Mean_Port_Peak_Change_vs_No_Recovery": (
                    port_group[
                        "Peak_Change_vs_No_Recovery"
                    ].mean()
                ),
            })

    return pd.DataFrame(rows)


# ============================================================
# 8. POLICY RANKING BY SEPARATE OBJECTIVES
# ============================================================

def create_policy_rankings(summary):

    rows = []

    for scenario in SCENARIOS:

        group = summary[
            (summary["Scenario"] == scenario)
            & (summary["Recovery_Policy"] != "NO_RECOVERY")
        ].copy()

        if group.empty:
            continue

        group["Delay_Rank"] = (
            group["Mean_Accumulated_Delay_Hours"]
            .rank(method="min", ascending=True)
        )

        group["Congestion_Rank"] = (
            group["Mean_Maximum_Port_Peak"]
            .rank(method="min", ascending=True)
        )

        group["Ports_Increased_Peak_Rank"] = (
            group["Mean_Ports_With_Increased_Peak"]
            .rank(method="min", ascending=True)
        )

        for row in group.itertuples(index=False):

            rows.append({
                "Scenario": scenario,
                "Recovery_Policy": row.Recovery_Policy,
                "Delay_Rank": row.Delay_Rank,
                "Maximum_Port_Peak_Rank": row.Congestion_Rank,
                "Ports_Increased_Peak_Rank": (
                    row.Ports_Increased_Peak_Rank
                ),
                "Interpretation": (
                    "Separate objective rankings; "
                    "no combined winner assigned."
                ),
            })

    return pd.DataFrame(rows)


# ============================================================
# 9. VALIDATION AND OUTPUTS
# ============================================================

def save_outputs(
    comparison,
    port_tradeoffs,
    baseline_comparison,
    summary,
    rankings,
):

    print("\n[6/8] VALIDATING RESULTS")
    print("-" * 75)

    checks = {
        "All policy comparisons have references": (
            comparison[
                "No_Recovery_Delay_Hours"
            ].notna().all()
        ),

        "No missing port references": (
            port_tradeoffs[
                "No_Recovery_Peak"
            ].notna().all()
        ),

        "All four scenarios present": (
            summary["Scenario"].nunique() == 4
        ),

        "All three policies present": (
            summary["Recovery_Policy"].nunique() == 3
        ),

        "Delay reduction finite": (
            np.isfinite(
                comparison["Delay_Reduction_Hours"]
            ).all()
        ),

        "No unexpected negative delay reduction": (
            (
                comparison["Delay_Reduction_Hours"]
                >= -1e-8
            ).all()
        ),
    }

    for name, passed in checks.items():
        print(f"{name}: {'PASS' if passed else 'FAIL'}")

    if not all(checks.values()):
        raise AssertionError(
            "Script 31 validation failed."
        )

    outputs = {
        "31_policy_replication_comparison.csv": comparison,
        "31_port_recovery_tradeoffs.csv": port_tradeoffs,
        "31_port_baseline_comparison.csv": baseline_comparison,
        "31_recovery_policy_summary.csv": summary,
        "31_recovery_policy_rankings.csv": rankings,
    }

    for filename, data in outputs.items():
        data.to_csv(
            OUTPUT_DIR / filename,
            index=False,
        )

    report_path = (
        REPORT_DIR
        / "31_recovery_strategy_evaluation_report.txt"
    )

    with open(
        report_path,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            "SCRIPT 31: RECOVERY STRATEGY EVALUATION\n"
        )

        file.write("=" * 85 + "\n\n")

        file.write("RECOVERY POLICY SUMMARY\n")
        file.write("-" * 85 + "\n")

        file.write(
            summary.to_string(index=False)
        )

        file.write("\n\nPOLICY RANKINGS BY SEPARATE OBJECTIVES\n")
        file.write("-" * 85 + "\n")

        file.write(
            rankings.to_string(index=False)
        )

        file.write("\n\nMETHODOLOGICAL LIMITATIONS\n")
        file.write("-" * 85 + "\n")

        file.write(
            "Recovery policies are hypothetical sensitivity assumptions.\n"
        )

        file.write(
            "Delay reduction is compared against NO_RECOVERY "
            "for the same scenario and random seed.\n"
        )

        file.write(
            "Port peak comparisons use the same scenario, seed "
            "and port as the NO_RECOVERY reference.\n"
        )

        file.write(
            "Port concurrency is based on recorded port-call intervals, "
            "not verified berth occupancy.\n"
        )

        file.write(
            "No confirmed Strait of Hormuz transit is assumed.\n"
        )

        file.write(
            "Separate rankings do not establish a universally "
            "optimal recovery policy.\n"
        )

    print("\nSaved outputs:")
    for filename in outputs:
        print(f"- outputs/tables/{filename}")

    print(
        "- outputs/reports/"
        "31_recovery_strategy_evaluation_report.txt"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 85)
    print("SCRIPT 31: RECOVERY STRATEGY EVALUATION")
    print("=" * 85)

    calls, ports, replications, combined = load_inputs()

    seeds = validate_structure(
        calls,
        ports,
        replications,
        combined,
    )

    policy_comparison = calculate_policy_comparison(
        replications
    )

    port_tradeoffs = calculate_port_tradeoffs(
        ports
    )

    baseline_comparison = calculate_baseline_comparison(
        ports
    )

    summary = create_policy_summary(
        policy_comparison,
        combined,
        port_tradeoffs,
    )

    rankings = create_policy_rankings(summary)

    print("\n[7/8] FINAL RECOVERY POLICY SUMMARY")
    print("=" * 85)

    print(
        summary.to_string(
            index=False,
            float_format=lambda x: f"{x:.3f}",
        )
    )

    save_outputs(
        policy_comparison,
        port_tradeoffs,
        baseline_comparison,
        summary,
        rankings,
    )

    print("\n[8/8] COMPLETION")
    print("=" * 85)
    print("Random seeds analysed:", seeds)
    print("Scenarios analysed:", len(SCENARIOS))
    print("Recovery policies analysed:", len(POLICIES))
    print("SCRIPT 31 COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()
