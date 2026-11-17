"""
SCRIPT 34: RECOVERY SENSITIVITY VISUALISATION AND STATISTICAL ROBUSTNESS

Reads Script 33 outputs. Does not rerun the simulation.

Analyses:
1. Partial-recovery and fixed-recovery parameter curves.
2. Delay reduction versus maximum port-call concurrency peak.
3. Seed-level variability and descriptive 95% t confidence intervals.
4. Paired comparison against NO_RECOVERY using the same seed.
5. Per-seed policy ranking stability.
6. Mean-level Pareto screening for each disruption scenario.

Important:
- Five seeds provide exploratory evidence, not strong statistical certainty.
- Confidence intervals describe variability across these five simulated seeds;
  they are not confidence intervals for real-world maritime performance.
- Port-call concurrency is not berth occupancy, verified port capacity,
  or a direct measure of congestion.
- Recovery parameters are hypothetical assumptions.
"""

from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import t


# ============================================================
# 1. PATHS AND CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = ROOT / "outputs" / "tables"
FIGURE_DIR = ROOT / "outputs" / "figures"
REPORT_DIR = ROOT / "outputs" / "reports"

FIGURE_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

INPUT_FILES = {
    "combined": TABLE_DIR / "33_recovery_sensitivity_combined_metrics.csv",
    "summary": TABLE_DIR / "33_recovery_sensitivity_scenario_summary.csv",
    "paired": TABLE_DIR / "33_recovery_sensitivity_paired_comparison.csv",
    "rankings": TABLE_DIR / "33_recovery_sensitivity_parameter_rankings.csv",
}

SCENARIOS = ["S1_MILD", "S2_MODERATE", "S3_SEVERE"]
SCENARIO_LABELS = {
    "S1_MILD": "Mild",
    "S2_MODERATE": "Moderate",
    "S3_SEVERE": "Severe",
}

REQUIRED_COMBINED = [
    "Scenario", "Recovery_Policy", "Replication_Seed",
    "Total_Accumulated_Delay_Hours", "Total_Recovered_Hours",
    "Maximum_Port_Peak", "Average_Port_Peak",
    "Average_Port_Concurrency",
]

REQUIRED_PAIRED = [
    "Scenario", "Recovery_Policy", "Replication_Seed",
    "Delay_Saved_Hours", "Delay_Reduction_Percent",
    "Maximum_Port_Peak_Change",
]

# Policies are identified by the names created in Script 33.
PARTIAL_POLICIES = {
    "PARTIAL_RECOVERY_10PCT": 10,
    "PARTIAL_RECOVERY_20PCT": 20,
    "PARTIAL_RECOVERY_25PCT": 25,
    "PARTIAL_RECOVERY_30PCT": 30,
    "PARTIAL_RECOVERY_40PCT": 40,
    "PARTIAL_RECOVERY_50PCT": 50,
}
FIXED_POLICIES = {
    "FIXED_RECOVERY_6H": 6,
    "FIXED_RECOVERY_12H": 12,
    "FIXED_RECOVERY_18H": 18,
    "FIXED_RECOVERY_24H": 24,
}


# ============================================================
# 2. LOAD AND VALIDATE SCRIPT 33 OUTPUTS
# ============================================================

def load_inputs():
    print("\n[1/9] LOADING SCRIPT 33 OUTPUTS")
    print("-" * 82)

    for name, path in INPUT_FILES.items():
        if not path.exists():
            raise FileNotFoundError(
                f"Required Script 33 output not found: {path}\n"
                "Run Script 33 successfully before running Script 34."
            )

    combined = pd.read_csv(INPUT_FILES["combined"])
    summary = pd.read_csv(INPUT_FILES["summary"])
    paired = pd.read_csv(INPUT_FILES["paired"])

    for name, df, required in [
        ("combined", combined, REQUIRED_COMBINED),
        ("paired", paired, REQUIRED_PAIRED),
    ]:
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"{name} output missing columns: {missing}")

    for df in [combined, summary, paired]:
        for col in df.select_dtypes(include="object").columns:
            # Do not change labels; trim accidental whitespace only.
            df[col] = df[col].astype(str).str.strip()

    combined["Replication_Seed"] = pd.to_numeric(
        combined["Replication_Seed"], errors="raise"
    ).astype(int)
    paired["Replication_Seed"] = pd.to_numeric(
        paired["Replication_Seed"], errors="raise"
    ).astype(int)

    numeric_cols = [
        "Total_Accumulated_Delay_Hours", "Total_Recovered_Hours",
        "Maximum_Port_Peak", "Average_Port_Peak",
        "Average_Port_Concurrency",
    ]
    for col in numeric_cols:
        combined[col] = pd.to_numeric(combined[col], errors="coerce")

    paired_numeric = [
        "Delay_Saved_Hours", "Delay_Reduction_Percent",
        "Maximum_Port_Peak_Change",
    ]
    for col in paired_numeric:
        paired[col] = pd.to_numeric(paired[col], errors="coerce")

    if combined[numeric_cols].isna().any().any():
        raise ValueError("Missing/non-numeric values in combined metrics.")
    if paired[paired_numeric].isna().any().any():
        raise ValueError("Missing/non-numeric values in paired metrics.")

    if combined.duplicated(
        ["Scenario", "Recovery_Policy", "Replication_Seed"]
    ).any():
        raise ValueError("Duplicate scenario-policy-seed rows found.")

    if paired.duplicated(
        ["Scenario", "Recovery_Policy", "Replication_Seed"]
    ).any():
        raise ValueError("Duplicate paired comparison rows found.")

    print("Combined replication records:", len(combined))
    print("Scenario summary records:", len(summary))
    print("Paired comparison records:", len(paired))
    print("Scenarios:", sorted(combined["Scenario"].unique()))
    print("Policies:", combined["Recovery_Policy"].nunique())
    print("Seeds:", sorted(combined["Replication_Seed"].unique()))

    return combined, summary, paired


# ============================================================
# 3. CONFIDENCE INTERVAL HELPERS
# ============================================================

def mean_ci(values, confidence=0.95):
    """Return mean and descriptive two-sided Student-t CI."""
    x = pd.Series(values).dropna().astype(float).to_numpy()
    n = len(x)

    if n == 0:
        return np.nan, np.nan, np.nan, 0
    mean = float(np.mean(x))

    if n == 1:
        return mean, np.nan, np.nan, n

    sd = float(np.std(x, ddof=1))
    se = sd / np.sqrt(n)
    critical = float(t.ppf((1 + confidence) / 2, df=n - 1))
    margin = critical * se

    return mean, mean - margin, mean + margin, n


def build_uncertainty_summary(combined, paired):
    rows = []

    metrics = {
        "Total_Accumulated_Delay_Hours": "Accumulated_Delay",
        "Total_Recovered_Hours": "Recovered_Hours",
        "Maximum_Port_Peak": "Maximum_Port_Peak",
        "Average_Port_Peak": "Average_Port_Peak",
    }

    for (scenario, policy), group in combined.groupby(
        ["Scenario", "Recovery_Policy"]
    ):
        for source_col, label in metrics.items():
            mean, low, high, n = mean_ci(group[source_col])
            rows.append({
                "Scenario": scenario,
                "Recovery_Policy": policy,
                "Metric": label,
                "N_Seeds": n,
                "Mean": mean,
                "CI95_Lower": low,
                "CI95_Upper": high,
                "SD_Across_Seeds": (
                    group[source_col].std(ddof=1) if n > 1 else np.nan
                ),
            })

    uncertainty = pd.DataFrame(rows)

    paired_rows = []
    for (scenario, policy), group in paired.groupby(
        ["Scenario", "Recovery_Policy"]
    ):
        for source_col, label in [
            ("Delay_Saved_Hours", "Delay_Saved_Hours"),
            ("Delay_Reduction_Percent", "Delay_Reduction_Percent"),
            ("Maximum_Port_Peak_Change", "Maximum_Port_Peak_Change"),
        ]:
            mean, low, high, n = mean_ci(group[source_col])
            paired_rows.append({
                "Scenario": scenario,
                "Recovery_Policy": policy,
                "Metric": label,
                "N_Paired_Seeds": n,
                "Mean": mean,
                "CI95_Lower": low,
                "CI95_Upper": high,
                "SD_Across_Paired_Seeds": (
                    group[source_col].std(ddof=1) if n > 1 else np.nan
                ),
            })

    paired_uncertainty = pd.DataFrame(paired_rows)
    return uncertainty, paired_uncertainty


# ============================================================
# 4. PER-SEED RANK STABILITY AND PARETO SCREENING
# ============================================================

def build_seed_rank_stability(combined):
    rows = []

    for scenario in SCENARIOS:
        subset = combined[combined["Scenario"] == scenario].copy()
        if subset.empty:
            continue

        for seed, seed_group in subset.groupby("Replication_Seed"):
            # Both objectives are minimised. Rank is descriptive.
            seed_group = seed_group.copy()
            seed_group["Delay_Rank"] = seed_group[
                "Total_Accumulated_Delay_Hours"
            ].rank(method="min", ascending=True)
            seed_group["Peak_Rank"] = seed_group[
                "Maximum_Port_Peak"
            ].rank(method="min", ascending=True)
            seed_group["Rank_Sum"] = (
                seed_group["Delay_Rank"] + seed_group["Peak_Rank"]
            )

            for row in seed_group.itertuples(index=False):
                rows.append({
                    "Scenario": scenario,
                    "Replication_Seed": seed,
                    "Recovery_Policy": row.Recovery_Policy,
                    "Delay_Rank": row.Delay_Rank,
                    "Peak_Rank": row.Peak_Rank,
                    "Rank_Sum": row.Rank_Sum,
                    "Accumulated_Delay_Hours": (
                        row.Total_Accumulated_Delay_Hours
                    ),
                    "Maximum_Port_Peak": row.Maximum_Port_Peak,
                })

    seed_ranks = pd.DataFrame(rows)

    stability_rows = []
    if not seed_ranks.empty:
        for (scenario, policy), group in seed_ranks.groupby(
            ["Scenario", "Recovery_Policy"]
        ):
            mean_rank, low, high, n = mean_ci(group["Rank_Sum"])
            stability_rows.append({
                "Scenario": scenario,
                "Recovery_Policy": policy,
                "Mean_Rank_Sum": mean_rank,
                "Rank_Sum_CI95_Lower": low,
                "Rank_Sum_CI95_Upper": high,
                "Rank_Sum_SD": group["Rank_Sum"].std(ddof=1),
                "Best_Rank_Count": int((group["Rank_Sum"] == group[
                    group["Scenario"].eq(scenario)
                ]["Rank_Sum"].min()).sum()),
                "N_Seeds": n,
            })

    stability = pd.DataFrame(stability_rows)

    # Count scenario/seed winners. Ties are retained as joint winners.
    winner_rows = []
    for (scenario, seed), group in seed_ranks.groupby(
        ["Scenario", "Replication_Seed"]
    ):
        best = group["Rank_Sum"].min()
        winners = group[group["Rank_Sum"] == best]
        for policy in winners["Recovery_Policy"]:
            winner_rows.append({
                "Scenario": scenario,
                "Replication_Seed": seed,
                "Recovery_Policy": policy,
                "Is_Joint_Best": len(winners) > 1,
            })

    winners = pd.DataFrame(winner_rows)
    winner_counts = (
        winners.groupby(["Scenario", "Recovery_Policy"])
        .size().rename("Seed_Win_Count").reset_index()
    )

    stability = stability.merge(
        winner_counts,
        on=["Scenario", "Recovery_Policy"],
        how="left",
    )
    stability["Seed_Win_Count"] = (
        stability["Seed_Win_Count"].fillna(0).astype(int)
    )

    return seed_ranks, stability, winners


def build_pareto_screening(combined):
    rows = []

    for scenario, group in combined.groupby("Scenario"):
        policy_means = (
            group.groupby("Recovery_Policy")
            .agg(
                Mean_Accumulated_Delay_Hours=(
                    "Total_Accumulated_Delay_Hours", "mean"
                ),
                Mean_Maximum_Port_Peak=("Maximum_Port_Peak", "mean"),
                Mean_Average_Port_Peak=("Average_Port_Peak", "mean"),
            )
            .reset_index()
        )

        delay = policy_means[
            "Mean_Accumulated_Delay_Hours"
        ].to_numpy()
        peak = policy_means["Mean_Maximum_Port_Peak"].to_numpy()

        efficient = []
        for i in range(len(policy_means)):
            dominated = False
            for j in range(len(policy_means)):
                if i == j:
                    continue
                no_worse = delay[j] <= delay[i] and peak[j] <= peak[i]
                strictly_better = delay[j] < delay[i] or peak[j] < peak[i]
                if no_worse and strictly_better:
                    dominated = True
                    break
            efficient.append(not dominated)

        policy_means["Pareto_Efficient"] = efficient
        policy_means["Scenario"] = scenario
        rows.append(policy_means)

    return pd.concat(rows, ignore_index=True)


# ============================================================
# 5. FIGURE 1: PARTIAL RECOVERY CURVES
# ============================================================

def plot_partial_recovery(combined):
    fig, axes = plt.subplots(1, 3, figsize=(17, 5), sharey=False)

    for ax, scenario in zip(axes, SCENARIOS):
        subset = combined[
            (combined["Scenario"] == scenario)
            & combined["Recovery_Policy"].isin(PARTIAL_POLICIES)
        ].copy()

        subset["Recovery_Percent"] = subset["Recovery_Policy"].map(
            PARTIAL_POLICIES
        )

        stats = (
            subset.groupby("Recovery_Percent")[
                "Total_Accumulated_Delay_Hours"
            ]
            .agg(["mean", "std", "count"])
            .reset_index()
            .sort_values("Recovery_Percent")
        )
        se = stats["std"] / np.sqrt(stats["count"])
        critical = t.ppf(0.975, df=stats["count"] - 1)
        margin = critical * se

        ax.errorbar(
            stats["Recovery_Percent"],
            stats["mean"],
            yerr=margin,
            marker="o",
            capsize=4,
        )
        ax.set_title(SCENARIO_LABELS[scenario])
        ax.set_xlabel("Partial recovery per transition (%)")
        ax.set_ylabel("Mean accumulated delay (hours)")
        ax.grid(True, alpha=0.3)

    fig.suptitle(
        "Partial Recovery Sensitivity: Accumulated Delay\n"
        "Error bars: descriptive 95% t intervals across five seeds"
    )
    fig.tight_layout()
    path = FIGURE_DIR / "34_partial_recovery_sensitivity.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return path


# ============================================================
# 6. FIGURE 2: FIXED RECOVERY CURVES
# ============================================================

def plot_fixed_recovery(combined):
    fig, axes = plt.subplots(1, 3, figsize=(17, 5), sharey=False)

    for ax, scenario in zip(axes, SCENARIOS):
        subset = combined[
            (combined["Scenario"] == scenario)
            & combined["Recovery_Policy"].isin(FIXED_POLICIES)
        ].copy()

        subset["Recovery_Hours"] = subset["Recovery_Policy"].map(
            FIXED_POLICIES
        )

        stats = (
            subset.groupby("Recovery_Hours")[
                "Total_Accumulated_Delay_Hours"
            ]
            .agg(["mean", "std", "count"])
            .reset_index()
            .sort_values("Recovery_Hours")
        )
        se = stats["std"] / np.sqrt(stats["count"])
        critical = t.ppf(0.975, df=stats["count"] - 1)
        margin = critical * se

        ax.errorbar(
            stats["Recovery_Hours"],
            stats["mean"],
            yerr=margin,
            marker="s",
            capsize=4,
        )
        ax.set_title(SCENARIO_LABELS[scenario])
        ax.set_xlabel("Fixed recovery limit per transition (hours)")
        ax.set_ylabel("Mean accumulated delay (hours)")
        ax.grid(True, alpha=0.3)

    fig.suptitle(
        "Fixed Recovery Sensitivity: Accumulated Delay\n"
        "Error bars: descriptive 95% t intervals across five seeds"
    )
    fig.tight_layout()
    path = FIGURE_DIR / "34_fixed_recovery_sensitivity.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return path


# ============================================================
# 7. FIGURE 3: DELAY-PEAK TRADE-OFF
# ============================================================

def plot_delay_peak_tradeoff(combined, pareto):
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    for ax, scenario in zip(axes, SCENARIOS):
        group = pareto[pareto["Scenario"] == scenario]
        for row in group.itertuples(index=False):
            ax.scatter(
                row.Mean_Maximum_Port_Peak,
                row.Mean_Accumulated_Delay_Hours,
                s=65,
            )
            ax.annotate(
                row.Recovery_Policy.replace("PARTIAL_RECOVERY_", "P").replace(
                    "FIXED_RECOVERY_", "F"
                ).replace("NO_RECOVERY", "None"),
                (row.Mean_Maximum_Port_Peak,
                 row.Mean_Accumulated_Delay_Hours),
                xytext=(5, 4),
                textcoords="offset points",
                fontsize=7,
            )

        efficient = group[group["Pareto_Efficient"]]
        ax.scatter(
            efficient["Mean_Maximum_Port_Peak"],
            efficient["Mean_Accumulated_Delay_Hours"],
            s=150,
            facecolors="none",
            linewidths=1.8,
        )

        ax.set_title(SCENARIO_LABELS[scenario])
        ax.set_xlabel("Mean maximum port-specific peak")
        ax.set_ylabel("Mean accumulated delay (hours)")
        ax.grid(True, alpha=0.3)

    fig.suptitle(
        "Recovery Trade-off: Accumulated Delay vs Port-Call Concurrency Peak\n"
        "Outlined markers indicate mean-level Pareto-efficient policies"
    )
    fig.tight_layout()
    path = FIGURE_DIR / "34_delay_peak_tradeoff.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return path


# ============================================================
# 8. FIGURE 4: SEED-LEVEL RANK STABILITY
# ============================================================

def plot_rank_stability(seed_ranks):
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    for ax, scenario in zip(axes, SCENARIOS):
        subset = seed_ranks[seed_ranks["Scenario"] == scenario]
        if subset.empty:
            continue

        pivot = subset.pivot(
            index="Recovery_Policy",
            columns="Replication_Seed",
            values="Rank_Sum",
        )

        pivot.plot(kind="bar", ax=ax)
        ax.set_title(SCENARIO_LABELS[scenario])
        ax.set_xlabel("Recovery policy")
        ax.set_ylabel("Rank sum (lower is better)")
        ax.tick_params(axis="x", labelrotation=75)
        ax.grid(True, axis="y", alpha=0.3)
        ax.legend(title="Seed", fontsize=7)

    fig.suptitle(
        "Per-Seed Recovery Policy Ranking Stability\n"
        "Rank sum combines delay rank and maximum port-peak rank"
    )
    fig.tight_layout()
    path = FIGURE_DIR / "34_seed_rank_stability.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return path


# ============================================================
# 9. REPORT AND MAIN
# ============================================================

def write_report(
    combined, uncertainty, paired_uncertainty,
    seed_ranks, stability, pareto, figure_paths
):
    report_path = REPORT_DIR / "34_recovery_sensitivity_robustness_report.txt"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("SCRIPT 34: RECOVERY SENSITIVITY VISUALISATION AND ROBUSTNESS\n")
        f.write("=" * 100 + "\n\n")

        f.write("INPUT AND EXPERIMENT COVERAGE\n")
        f.write("-" * 100 + "\n")
        f.write(f"Replication rows: {len(combined)}\n")
        f.write(
            f"Scenarios: {sorted(combined['Scenario'].unique().tolist())}\n"
        )
        f.write(
            f"Seeds: {sorted(combined['Replication_Seed'].unique().tolist())}\n"
        )
        f.write(
            f"Recovery policies: {combined['Recovery_Policy'].nunique()}\n\n"
        )

        f.write("DESCRIPTIVE 95% CONFIDENCE INTERVALS ACROSS SEEDS\n")
        f.write("-" * 100 + "\n")
        f.write(uncertainty.to_string(index=False))
        f.write("\n\nPAIRED COMPARISON AGAINST NO_RECOVERY\n")
        f.write("-" * 100 + "\n")
        f.write(paired_uncertainty.to_string(index=False))
        f.write("\n\nPER-SEED RANK STABILITY\n")
        f.write("-" * 100 + "\n")
        f.write(stability.to_string(index=False))
        f.write("\n\nMEAN-LEVEL PARETO SCREENING\n")
        f.write("-" * 100 + "\n")
        f.write(pareto.to_string(index=False))

        f.write("\n\nFIGURES GENERATED\n")
        f.write("-" * 100 + "\n")
        for path in figure_paths:
            f.write(f"{path.relative_to(ROOT)}\n")

        f.write("\n\nINTERPRETATION AND LIMITATIONS\n")
        f.write("-" * 100 + "\n")
        f.write(
            "1. The confidence intervals are descriptive intervals across "
            "the five simulated seeds. They do not quantify uncertainty "
            "in real-world maritime performance.\n"
        )
        f.write(
            "2. Five seeds are a small exploratory replication set. "
            "Conclusions about policy superiority should be treated cautiously.\n"
        )
        f.write(
            "3. Paired comparisons use the same seed-specific vessel and "
            "disruption-onset selection as the NO_RECOVERY reference.\n"
        )
        f.write(
            "4. Rank sums are descriptive summaries, not validated "
            "multi-objective utility functions.\n"
        )
        f.write(
            "5. Pareto screening uses mean accumulated delay and mean "
            "maximum port-specific peak; it does not prove an operational optimum.\n"
        )
        f.write(
            "6. Port-call concurrency is not berth occupancy, port capacity, "
            "or a direct congestion measure.\n"
        )
        f.write(
            "7. Recovery percentages and fixed-hour limits remain hypothetical "
            "until supported by measured schedule slack or operational evidence.\n"
        )
        f.write(
            "8. No AIS-confirmed Strait of Hormuz transit is inferred by this analysis.\n"
        )

    return report_path


def main():
    print("=" * 86)
    print("SCRIPT 34: RECOVERY SENSITIVITY VISUALISATION AND STATISTICAL ROBUSTNESS")
    print("=" * 86)

    combined, summary, paired = load_inputs()

    print("\n[2/9] VALIDATING SCENARIOS AND PAIRED SEEDS")
    print("-" * 82)

    required_scenarios = set(SCENARIOS)
    actual_scenarios = set(combined["Scenario"].unique())
    if not required_scenarios.issubset(actual_scenarios):
        raise ValueError(
            f"Missing required disruption scenarios: "
            f"{required_scenarios - actual_scenarios}"
        )

    for scenario in SCENARIOS:
        ref = paired[
            (paired["Scenario"] == scenario)
            & (paired["Recovery_Policy"] == "NO_RECOVERY")
        ]
        if ref.empty:
            raise ValueError(f"NO_RECOVERY reference missing for {scenario}.")

        expected_seeds = set(ref["Replication_Seed"])
        scenario_rows = paired[paired["Scenario"] == scenario]
        for policy, group in scenario_rows.groupby("Recovery_Policy"):
            if set(group["Replication_Seed"]) != expected_seeds:
                raise ValueError(
                    f"Unpaired seed set for {scenario}, {policy}."
                )

    print("All disruption scenarios present: PASS")
    print("Paired seed structure: PASS")
    print("NO_RECOVERY references: PASS")

    print("\n[3/9] CALCULATING SEED-LEVEL UNCERTAINTY")
    uncertainty, paired_uncertainty = build_uncertainty_summary(
        combined, paired
    )
    print("Uncertainty rows:", len(uncertainty))
    print("Paired uncertainty rows:", len(paired_uncertainty))

    print("\n[4/9] ANALYSING RANK STABILITY")
    seed_ranks, stability, winners = build_seed_rank_stability(combined)
    print("Seed-level ranking rows:", len(seed_ranks))
    print("Policy stability rows:", len(stability))

    print("\n[5/9] CALCULATING MEAN-LEVEL PARETO SCREENING")
    pareto = build_pareto_screening(combined)
    print(
        pareto[pareto["Pareto_Efficient"]][
            ["Scenario", "Recovery_Policy",
             "Mean_Accumulated_Delay_Hours",
             "Mean_Maximum_Port_Peak"]
        ].to_string(index=False)
    )

    print("\n[6/9] GENERATING FIGURES")
    figure_paths = [
        plot_partial_recovery(combined),
        plot_fixed_recovery(combined),
        plot_delay_peak_tradeoff(combined, pareto),
        plot_rank_stability(seed_ranks),
    ]
    for path in figure_paths:
        print("Saved:", path.relative_to(ROOT))

    print("\n[7/9] SAVING TABLES")
    tables = {
        "34_uncertainty_summary.csv": uncertainty,
        "34_paired_uncertainty_summary.csv": paired_uncertainty,
        "34_seed_level_policy_rankings.csv": seed_ranks,
        "34_policy_rank_stability.csv": stability,
        "34_seed_level_joint_winners.csv": winners,
        "34_mean_level_pareto_screening.csv": pareto,
    }

    for filename, data in tables.items():
        data.to_csv(TABLE_DIR / filename, index=False)
        print("Saved:", TABLE_DIR / filename)

    print("\n[8/9] GENERATING REPORT")
    report_path = write_report(
        combined, uncertainty, paired_uncertainty,
        seed_ranks, stability, pareto, figure_paths
    )
    print("Saved:", report_path)

    print("\n[9/9] FINAL VALIDATION")
    checks = {
        "Uncertainty summaries generated": not uncertainty.empty,
        "Paired uncertainty summaries generated": not paired_uncertainty.empty,
        "Seed-level rankings generated": not seed_ranks.empty,
        "Pareto screening generated": not pareto.empty,
        "Four figures generated": len(figure_paths) == 4
            and all(p.exists() for p in figure_paths),
        "Six tables generated": all(
            (TABLE_DIR / name).exists() for name in tables
        ),
        "Report generated": report_path.exists(),
    }

    for name, passed in checks.items():
        print(f"{name}: {'PASS' if passed else 'FAIL'}")

    if not all(checks.values()):
        raise AssertionError("One or more Script 34 checks failed.")

    print("\nSCRIPT 34 COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()
