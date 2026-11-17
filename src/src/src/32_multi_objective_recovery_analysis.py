
"""
SCRIPT 32: MULTI-OBJECTIVE RECOVERY STRATEGY ANALYSIS

Purpose
-------
Evaluate vessel recovery policies using two objectives:
1. Minimise accumulated vessel schedule delay.
2. Minimise maximum port-call concurrency.

The analysis:
- Reads Script 31 recovery policy summary.
- Compares policies within each disruption scenario.
- Calculates improvements against NO_RECOVERY.
- Identifies Pareto-efficient policies.
- Examines delay/concurrency trade-offs.
- Produces tables, figures, and a text report.

Important:
Port concurrency is a temporal overlap proxy. It is NOT verified
berth occupancy, physical port capacity, or actual congestion.

All recovery parameters remain hypothetical.
"""

from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# 1. PATHS AND CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    ROOT
    / "outputs"
    / "tables"
    / "31_recovery_policy_summary.csv"
)

TABLE_DIR = ROOT / "outputs" / "tables"
FIGURE_DIR = ROOT / "outputs" / "figures"
REPORT_DIR = ROOT / "outputs" / "reports"

TABLE_DIR.mkdir(parents=True, exist_ok=True)
FIGURE_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

POLICY_ORDER = [
    "NO_RECOVERY",
    "PARTIAL_RECOVERY_25",
    "FIXED_RECOVERY_12H",
]

SCENARIO_ORDER = [
    "S0_BASELINE",
    "S1_MILD",
    "S2_MODERATE",
    "S3_SEVERE",
]

# Primary objectives:
# Both must be minimised.
DELAY_OBJECTIVE = "Mean_Accumulated_Delay_Hours"
PEAK_OBJECTIVE = "Mean_Maximum_Port_Peak"

# Additional diagnostic metrics.
ADDITIONAL_METRICS = [
    "Mean_Delay_Reduction_Percent",
    "Mean_Average_Port_Peak",
    "Mean_Ports_With_Increased_Peak",
    "Mean_Ports_With_Decreased_Peak",
    "Mean_Ports_With_Unchanged_Peak",
    "Mean_Port_Peak_Change_vs_No_Recovery",
    "Mean_Total_Recovered_Hours",
]


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def print_section(number, title):
    print("\n" + "=" * 78)
    print(f"[{number}] {title}")
    print("=" * 78)


def save_csv(df, filename):
    path = TABLE_DIR / filename
    df.to_csv(path, index=False)
    print(f"Saved: {path.relative_to(ROOT)}")


def safe_percentage(numerator, denominator):
    if pd.isna(denominator) or denominator == 0:
        return np.nan
    return (numerator / denominator) * 100


# ============================================================
# 3. LOAD AND VALIDATE INPUT
# ============================================================

def load_data():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Script 31 input file not found:\n{INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    required_columns = [
        "Scenario",
        "Recovery_Policy",
        "Replications",
        "Mean_Accumulated_Delay_Hours",
        "Mean_Delay_Reduction_Hours",
        "Mean_Delay_Reduction_Percent",
        "Mean_Maximum_Port_Peak",
        "Mean_Average_Port_Peak",
        "Mean_Ports_With_Increased_Peak",
        "Mean_Ports_With_Decreased_Peak",
        "Mean_Ports_With_Unchanged_Peak",
        "Mean_Port_Peak_Change_vs_No_Recovery",
        "Mean_Total_Recovered_Hours",
    ]

    missing = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            "Script 31 summary is missing required columns:\n"
            f"{missing}\n\n"
            "Actual columns:\n"
            f"{df.columns.tolist()}"
        )

    if df.duplicated(
        subset=["Scenario", "Recovery_Policy"]
    ).any():
        raise ValueError(
            "Duplicate scenario-policy combinations found."
        )

    numeric_columns = [
        col for col in required_columns
        if col not in ["Scenario", "Recovery_Policy"]
    ]

    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if df[numeric_columns].isna().any().any():
        bad = df[numeric_columns].isna().sum()
        bad = bad[bad > 0]

        raise ValueError(
            "Missing or non-numeric values found:\n"
            f"{bad.to_dict()}"
        )

    expected_scenarios = set(SCENARIO_ORDER)
    expected_policies = set(POLICY_ORDER)

    actual_scenarios = set(df["Scenario"])
    actual_policies = set(df["Recovery_Policy"])

    if actual_scenarios != expected_scenarios:
        raise ValueError(
            "Unexpected scenario set.\n"
            f"Expected: {expected_scenarios}\n"
            f"Found: {actual_scenarios}"
        )

    if actual_policies != expected_policies:
        raise ValueError(
            "Unexpected recovery policy set.\n"
            f"Expected: {expected_policies}\n"
            f"Found: {actual_policies}"
        )

    expected_rows = len(SCENARIO_ORDER) * len(POLICY_ORDER)

    if len(df) != expected_rows:
        raise ValueError(
            f"Expected {expected_rows} summary rows, "
            f"but found {len(df)}."
        )

    return df


# ============================================================
# 4. CALCULATE IMPROVEMENT AGAINST NO RECOVERY
# ============================================================

def calculate_policy_improvements(df):

    records = []

    for scenario in SCENARIO_ORDER:

        scenario_df = df[
            df["Scenario"] == scenario
        ].copy()

        baseline_rows = scenario_df[
            scenario_df["Recovery_Policy"] == "NO_RECOVERY"
        ]

        if len(baseline_rows) != 1:
            raise ValueError(
                f"NO_RECOVERY reference missing or duplicated "
                f"for {scenario}"
            )

        baseline = baseline_rows.iloc[0]

        for _, row in scenario_df.iterrows():

            delay_saved = (
                baseline[DELAY_OBJECTIVE]
                - row[DELAY_OBJECTIVE]
            )

            peak_change = (
                row[PEAK_OBJECTIVE]
                - baseline[PEAK_OBJECTIVE]
            )

            average_peak_change = (
                row["Mean_Average_Port_Peak"]
                - baseline["Mean_Average_Port_Peak"]
            )

            increased_ports_change = (
                row["Mean_Ports_With_Increased_Peak"]
                - baseline["Mean_Ports_With_Increased_Peak"]
            )

            record = {
                "Scenario": scenario,
                "Recovery_Policy": row["Recovery_Policy"],
                "Replications": row["Replications"],

                "Accumulated_Delay_Hours":
                    row[DELAY_OBJECTIVE],

                "Delay_Saved_vs_No_Recovery_Hours":
                    delay_saved,

                "Delay_Reduction_Percent_vs_No_Recovery":
                    safe_percentage(
                        delay_saved,
                        baseline[DELAY_OBJECTIVE]
                    ),

                "Maximum_Port_Peak":
                    row[PEAK_OBJECTIVE],

                "Maximum_Port_Peak_Change_vs_No_Recovery":
                    peak_change,

                "Average_Port_Peak":
                    row["Mean_Average_Port_Peak"],

                "Average_Port_Peak_Change_vs_No_Recovery":
                    average_peak_change,

                "Ports_With_Increased_Peak":
                    row["Mean_Ports_With_Increased_Peak"],

                "Change_in_Ports_With_Increased_Peak":
                    increased_ports_change,

                "Ports_With_Decreased_Peak":
                    row["Mean_Ports_With_Decreased_Peak"],

                "Ports_With_Unchanged_Peak":
                    row["Mean_Ports_With_Unchanged_Peak"],

                "Total_Recovered_Hours":
                    row["Mean_Total_Recovered_Hours"],
            }

            records.append(record)

    result = pd.DataFrame(records)

    return result


# ============================================================
# 5. PARETO EFFICIENCY
# ============================================================

def is_dominated(candidate, alternatives):

    """
    A candidate is dominated if another policy:
    - has equal or lower accumulated delay,
    - has equal or lower maximum port peak,
    - and is strictly better on at least one objective.
    """

    candidate_delay = candidate[DELAY_OBJECTIVE]
    candidate_peak = candidate[PEAK_OBJECTIVE]

    for _, other in alternatives.iterrows():

        if (
            other[DELAY_OBJECTIVE] <= candidate_delay
            and other[PEAK_OBJECTIVE] <= candidate_peak
            and (
                other[DELAY_OBJECTIVE] < candidate_delay
                or other[PEAK_OBJECTIVE] < candidate_peak
            )
        ):
            return True

    return False


def identify_pareto_policies(df):

    records = []

    for scenario in SCENARIO_ORDER:

        scenario_df = df[
            df["Scenario"] == scenario
        ].copy()

        for index, candidate in scenario_df.iterrows():

            alternatives = scenario_df.drop(index=index)

            dominated = is_dominated(
                candidate,
                alternatives
            )

            records.append({
                "Scenario": scenario,
                "Recovery_Policy": candidate["Recovery_Policy"],
                "Accumulated_Delay_Hours":
                    candidate[DELAY_OBJECTIVE],
                "Maximum_Port_Peak":
                    candidate[PEAK_OBJECTIVE],
                "Pareto_Efficient": not dominated,
            })

    return pd.DataFrame(records)


# ============================================================
# 6. SCENARIO-LEVEL POLICY RANKING
# ============================================================

def create_rankings(df, pareto_df):

    merged = df.merge(
        pareto_df[
            [
                "Scenario",
                "Recovery_Policy",
                "Pareto_Efficient",
            ]
        ],
        on=["Scenario", "Recovery_Policy"],
        how="left",
        validate="one_to_one",
    )

    merged["Delay_Rank"] = (
        merged.groupby("Scenario")[DELAY_OBJECTIVE]
        .rank(method="min", ascending=True)
    )

    merged["Peak_Rank"] = (
        merged.groupby("Scenario")[PEAK_OBJECTIVE]
        .rank(method="min", ascending=True)
    )

    # This rank sum is a descriptive comparison only.
    # It is not an optimisation objective or an operational recommendation.
    merged["Two_Objective_Rank_Sum"] = (
        merged["Delay_Rank"] + merged["Peak_Rank"]
    )

    merged["Exploratory_Rank"] = (
        merged.groupby("Scenario")["Two_Objective_Rank_Sum"]
        .rank(method="min", ascending=True)
    )

    merged["Exploratory_Rank_Note"] = (
        "Equal rank weighting; descriptive sensitivity only"
    )

    return merged.sort_values(
        ["Scenario", "Exploratory_Rank", "Recovery_Policy"]
    )


# ============================================================
# 7. CREATE POLICY TRADE-OFF CLASSIFICATION
# ============================================================

def classify_tradeoffs(df):

    records = []

    for _, row in df.iterrows():

        delay_saved = row[
            "Delay_Saved_vs_No_Recovery_Hours"
        ]

        peak_change = row[
            "Maximum_Port_Peak_Change_vs_No_Recovery"
        ]

        if row["Recovery_Policy"] == "NO_RECOVERY":
            classification = "REFERENCE_POLICY"

        elif delay_saved > 0 and peak_change < 0:
            classification = "DELAY_REDUCED_AND_PEAK_IMPROVED"

        elif delay_saved > 0 and peak_change == 0:
            classification = "DELAY_REDUCED_PEAK_UNCHANGED"

        elif delay_saved > 0 and peak_change > 0:
            classification = "DELAY_REDUCED_BUT_PEAK_INCREASED"

        elif delay_saved == 0 and peak_change < 0:
            classification = "PEAK_IMPROVED_WITHOUT_DELAY_REDUCTION"

        elif delay_saved == 0 and peak_change > 0:
            classification = "PEAK_INCREASED_WITHOUT_DELAY_REDUCTION"

        else:
            classification = "NO_CLEAR_IMPROVEMENT"

        records.append({
            "Scenario": row["Scenario"],
            "Recovery_Policy": row["Recovery_Policy"],
            "Tradeoff_Classification": classification,
            "Delay_Saved_Hours":
                delay_saved,
            "Maximum_Port_Peak_Change":
                peak_change,
        })

    return pd.DataFrame(records)


# ============================================================
# 8. PLOT DELAY VS PORT PEAK
# ============================================================

def create_pareto_plot(df, pareto_df):

    fig, axes = plt.subplots(
        2, 2,
        figsize=(14, 10)
    )

    axes = axes.flatten()

    markers = {
        "NO_RECOVERY": "o",
        "PARTIAL_RECOVERY_25": "s",
        "FIXED_RECOVERY_12H": "^",
    }

    for i, scenario in enumerate(SCENARIO_ORDER):

        ax = axes[i]

        scenario_df = df[
            df["Scenario"] == scenario
        ]

        scenario_pareto = pareto_df[
            pareto_df["Scenario"] == scenario
        ]

        for _, row in scenario_df.iterrows():

            policy = row["Recovery_Policy"]

            pareto_status = scenario_pareto[
                scenario_pareto["Recovery_Policy"] == policy
            ]["Pareto_Efficient"].iloc[0]

            ax.scatter(
                row[DELAY_OBJECTIVE],
                row[PEAK_OBJECTIVE],
                marker=markers.get(policy, "o"),
                s=130,
                label=policy,
                edgecolors="black",
                linewidths=0.7,
            )

            label = policy.replace("_", "\n")

            if pareto_status:
                label += "\n(Pareto)"

            ax.annotate(
                label,
                (
                    row[DELAY_OBJECTIVE],
                    row[PEAK_OBJECTIVE],
                ),
                xytext=(7, 7),
                textcoords="offset points",
                fontsize=8,
            )

        ax.set_title(scenario)
        ax.set_xlabel("Mean accumulated delay (hours)")
        ax.set_ylabel("Mean maximum port-specific peak")
        ax.grid(True, alpha=0.3)

    fig.suptitle(
        "Recovery Policy Trade-offs: Delay vs Port Peak Concurrency",
        fontsize=14,
    )

    fig.tight_layout()

    output = FIGURE_DIR / "32_pareto_recovery_tradeoffs.png"

    fig.savefig(
        output,
        dpi=300,
        bbox_inches="tight"
    )

    plt.close(fig)

    print(f"Saved figure: {output.relative_to(ROOT)}")


# ============================================================
# 9. WRITE REPORT
# ============================================================

def write_report(
    source_df,
    improvement_df,
    pareto_df,
    ranking_df,
    tradeoff_df,
):

    report_path = (
        REPORT_DIR
        / "32_multi_objective_recovery_analysis_report.txt"
    )

    lines = []

    lines.append("=" * 78)
    lines.append("SCRIPT 32: MULTI-OBJECTIVE RECOVERY STRATEGY ANALYSIS")
    lines.append("=" * 78)

    lines.append("")
    lines.append("1. PURPOSE")
    lines.append("-" * 78)
    lines.append(
        "Evaluate recovery policies using two minimisation objectives:"
    )
    lines.append(
        "  a. Mean accumulated vessel schedule delay."
    )
    lines.append(
        "  b. Mean maximum port-specific peak concurrency."
    )

    lines.append("")
    lines.append("2. INPUT")
    lines.append("-" * 78)
    lines.append(str(INPUT_FILE))
    lines.append(f"Summary records: {len(source_df)}")
    lines.append(f"Scenarios: {source_df['Scenario'].nunique()}")
    lines.append(f"Policies: {source_df['Recovery_Policy'].nunique()}")

    lines.append("")
    lines.append("3. POLICY IMPROVEMENTS VS NO RECOVERY")
    lines.append("-" * 78)

    display_columns = [
        "Scenario",
        "Recovery_Policy",
        "Delay_Saved_vs_No_Recovery_Hours",
        "Delay_Reduction_Percent_vs_No_Recovery",
        "Maximum_Port_Peak_Change_vs_No_Recovery",
        "Average_Port_Peak_Change_vs_No_Recovery",
    ]

    lines.append(
        improvement_df[display_columns]
        .round(3)
        .to_string(index=False)
    )

    lines.append("")
    lines.append("4. PARETO-EFFICIENT POLICIES")
    lines.append("-" * 78)

    for scenario in SCENARIO_ORDER:

        subset = pareto_df[
            (pareto_df["Scenario"] == scenario)
            & (pareto_df["Pareto_Efficient"])
        ]

        policies = subset["Recovery_Policy"].tolist()

        lines.append(
            f"{scenario}: {', '.join(policies) if policies else 'None'}"
        )

    lines.append("")
    lines.append("5. TWO-OBJECTIVE RANKING")
    lines.append("-" * 78)

    ranking_columns = [
        "Scenario",
        "Recovery_Policy",
        "Delay_Rank",
        "Peak_Rank",
        "Two_Objective_Rank_Sum",
        "Pareto_Efficient",
    ]

    lines.append(
        ranking_df[ranking_columns]
        .round(3)
        .to_string(index=False)
    )

    lines.append("")
    lines.append("6. TRADE-OFF CLASSIFICATION")
    lines.append("-" * 78)

    lines.append(
        tradeoff_df.to_string(index=False)
    )

    lines.append("")
    lines.append("7. METHODOLOGICAL INTERPRETATION")
    lines.append("-" * 78)

    lines.append(
        "Pareto efficiency identifies policies for which no alternative "
        "policy is at least as good on both selected objectives and "
        "strictly better on one."
    )

    lines.append(
        "A Pareto-efficient policy is not automatically the operationally "
        "best policy. Selection requires operational preferences, "
        "constraints, and validated cost or capacity information."
    )

    lines.append(
        "The maximum port-specific peak is a temporal overlap indicator "
        "derived from port-call intervals. It is not verified berth "
        "occupancy or physical port capacity."
    )

    lines.append(
        "The recovery rules are hypothetical assumptions. The observed "
        "inter-port elapsed times are not pure sailing times and do not "
        "establish actual recoverable schedule slack."
    )

    lines.append(
        "The underlying call sequences do not independently confirm "
        "Strait of Hormuz transits. No actual route or AIS crossing "
        "is inferred by this analysis."
    )

    lines.append("")
    lines.append("8. LIMITATIONS")
    lines.append("-" * 78)
    lines.append(
        "- Only three recovery policies are compared."
    )
    lines.append(
        "- Only two objectives are used for Pareto analysis."
    )
    lines.append(
        "- Port concurrency is a proxy, not a capacity measure."
    )
    lines.append(
        "- No verified AIS trajectories or Strait crossings are used."
    )
    lines.append(
        "- Recovery fractions and fixed recovery hours are hypothetical."
    )
    lines.append(
        "- The equal-rank sum is descriptive and not a validated "
        "multi-objective optimisation function."
    )

    lines.append("")
    lines.append("=" * 78)
    lines.append("END OF SCRIPT 32 REPORT")
    lines.append("=" * 78)

    report_path.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )

    print(f"Saved report: {report_path.relative_to(ROOT)}")


# ============================================================
# 10. MAIN
# ============================================================

def main():

    print("=" * 78)
    print("SCRIPT 32: MULTI-OBJECTIVE RECOVERY STRATEGY ANALYSIS")
    print("=" * 78)

    # Step 1
    print_section("1/8", "LOADING SCRIPT 31 RESULTS")

    df = load_data()

    print(f"Summary records: {len(df)}")
    print(f"Scenarios: {df['Scenario'].nunique()}")
    print(f"Recovery policies: {df['Recovery_Policy'].nunique()}")

    # Step 2
    print_section("2/8", "CALCULATING POLICY IMPROVEMENTS")

    improvement_df = calculate_policy_improvements(df)

    print(
        improvement_df[
            [
                "Scenario",
                "Recovery_Policy",
                "Delay_Saved_vs_No_Recovery_Hours",
                "Delay_Reduction_Percent_vs_No_Recovery",
                "Maximum_Port_Peak_Change_vs_No_Recovery",
            ]
        ].round(3).to_string(index=False)
    )

    # Step 3
    print_section("3/8", "IDENTIFYING PARETO-EFFICIENT POLICIES")

    pareto_df = identify_pareto_policies(df)

    print(
        pareto_df.to_string(index=False)
    )

    # Step 4
    print_section("4/8", "CREATING POLICY RANKINGS")

    ranking_df = create_rankings(
        df,
        pareto_df
    )

    print(
        ranking_df[
            [
                "Scenario",
                "Recovery_Policy",
                "Delay_Rank",
                "Peak_Rank",
                "Two_Objective_Rank_Sum",
                "Pareto_Efficient",
            ]
        ].round(3).to_string(index=False)
    )

    # Step 5
    print_section("5/8", "CLASSIFYING RECOVERY TRADE-OFFS")

    tradeoff_df = classify_tradeoffs(
        improvement_df
    )

    print(
        tradeoff_df.to_string(index=False)
    )

    # Step 6
    print_section("6/8", "VALIDATING RESULTS")

    checks = {
        "All four scenarios present":
            set(df["Scenario"]) == set(SCENARIO_ORDER),

        "All three policies present":
            set(df["Recovery_Policy"]) == set(POLICY_ORDER),

        "Exactly 12 summary records":
            len(df) == 12,

        "No negative accumulated delays":
            (df[DELAY_OBJECTIVE] >= 0).all(),

        "No negative maximum port peaks":
            (df[PEAK_OBJECTIVE] >= 0).all(),

        "All Pareto classifications assigned":
            pareto_df["Pareto_Efficient"].notna().all(),

        "All ranking records assigned":
            ranking_df["Exploratory_Rank"].notna().all(),

        "No missing policy improvements":
            improvement_df[
                [
                    "Delay_Saved_vs_No_Recovery_Hours",
                    "Maximum_Port_Peak_Change_vs_No_Recovery",
                ]
            ].notna().all().all(),
    }

    for name, passed in checks.items():
        print(f"{name}: {'PASS' if passed else 'FAIL'}")

    if not all(checks.values()):
        raise RuntimeError(
            "One or more validation checks failed."
        )

    # Step 7
    print_section("7/8", "SAVING TABLES AND FIGURES")

    save_csv(
        improvement_df,
        "32_policy_improvement_comparison.csv"
    )

    save_csv(
        pareto_df,
        "32_pareto_efficiency_results.csv"
    )

    save_csv(
        ranking_df,
        "32_multi_objective_policy_rankings.csv"
    )

    save_csv(
        tradeoff_df,
        "32_recovery_tradeoff_classification.csv"
    )

    create_pareto_plot(
        df,
        pareto_df
    )

    # Step 8
    print_section("8/8", "GENERATING FINAL REPORT")

    write_report(
        df,
        improvement_df,
        pareto_df,
        ranking_df,
        tradeoff_df,
    )

    print("\n" + "=" * 78)
    print("SCRIPT 32 COMPLETED SUCCESSFULLY")
    print("=" * 78)

    print("\nOUTPUT FILES:")
    print("- outputs/tables/32_policy_improvement_comparison.csv")
    print("- outputs/tables/32_pareto_efficiency_results.csv")
    print("- outputs/tables/32_multi_objective_policy_rankings.csv")
    print("- outputs/tables/32_recovery_tradeoff_classification.csv")
    print("- outputs/figures/32_pareto_recovery_tradeoffs.png")
    print("- outputs/reports/32_multi_objective_recovery_analysis_report.txt")


if __name__ == "__main__":
    main()
