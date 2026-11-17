"""
SCRIPT 36: Statistical Robustness and Final Visualization
---------------------------------------------------------
Reads Script 35 outputs. Does NOT rerun the simulation.

Analyses:
1. Holm-adjusted p-values for the 90 paired tests.
2. Shapiro-Wilk normality diagnostics and outlier screening for paired differences.
3. Wilcoxon signed-rank sensitivity tests against zero.
4. Confidence-interval tables and plots for paired delay savings.
5. Policy ranking stability heatmap.
6. Delay-versus-maximum-port-peak Pareto visualization.
7. Consolidated thesis-ready results tables and report.

Important:
- Inference concerns simulated outcomes under hypothetical assumptions.
- Port-call concurrency is not verified berth occupancy or port capacity.
- The 30 seeds quantify simulation variability; they do not validate model realism.
"""

from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import shapiro, wilcoxon

ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = ROOT / "outputs" / "tables"
FIGURE_DIR = ROOT / "outputs" / "figures"
REPORT_DIR = ROOT / "outputs" / "reports"

FIGURE_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

INFERENCE_FILE = TABLE_DIR / "35_paired_statistical_inference.csv"
RANK_STABILITY_FILE = TABLE_DIR / "35_policy_rank_stability.csv"
SEED_RANKINGS_FILE = TABLE_DIR / "35_seed_level_policy_rankings.csv"
JOINT_WINNERS_FILE = TABLE_DIR / "35_seed_level_joint_winners.csv"
SCENARIO_SUMMARY_FILE = TABLE_DIR / "35_extended_replication_scenario_summary.csv"
PAIRED_FILE = TABLE_DIR / "35_extended_replication_paired_comparison.csv"
COMBINED_FILE = TABLE_DIR / "35_extended_replication_combined_metrics.csv"

ALPHA = 0.05
EXPECTED_SEEDS = 30
SCENARIOS = ["S1_MILD", "S2_MODERATE", "S3_SEVERE"]
DELAY_METRICS = ["Delay_Saved_Hours", "Delay_Reduction_Percent"]
PEAK_METRIC = "Maximum_Port_Peak_Change"


def require_file(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Required Script 35 output not found: {path}\n"
            "Run Script 35 successfully before running Script 36."
        )


def load_inputs():
    for path in [
        INFERENCE_FILE, RANK_STABILITY_FILE, SEED_RANKINGS_FILE,
        JOINT_WINNERS_FILE, SCENARIO_SUMMARY_FILE, PAIRED_FILE, COMBINED_FILE
    ]:
        require_file(path)

    inference = pd.read_csv(INFERENCE_FILE)
    stability = pd.read_csv(RANK_STABILITY_FILE)
    seed_rankings = pd.read_csv(SEED_RANKINGS_FILE)
    winners = pd.read_csv(JOINT_WINNERS_FILE)
    summary = pd.read_csv(SCENARIO_SUMMARY_FILE)
    paired = pd.read_csv(PAIRED_FILE)
    combined = pd.read_csv(COMBINED_FILE)

    required_inference = {
        "Scenario", "Recovery_Policy", "Metric", "N_Paired_Seeds",
        "Mean_Paired_Difference", "CI95_Lower", "CI95_Upper",
        "P_Value_Two_Sided"
    }
    required_paired = {
        "Scenario", "Recovery_Policy", "Replication_Seed",
        "Delay_Saved_Hours", "Delay_Reduction_Percent",
        "Maximum_Port_Peak_Change"
    }
    required_stability = {
        "Scenario", "Recovery_Policy", "Mean_Rank_Sum",
        "Seed_Win_Percent", "N_Seeds"
    }
    for label, frame, required in [
        ("inference", inference, required_inference),
        ("paired comparison", paired, required_paired),
        ("rank stability", stability, required_stability),
    ]:
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{label} file is missing columns: {sorted(missing)}")

    return inference, stability, seed_rankings, winners, summary, paired, combined


def holm_adjust(p_values):
    """Holm step-down adjusted p-values, preserving input order."""
    p = np.asarray(p_values, dtype=float)
    adjusted = np.full(len(p), np.nan, dtype=float)
    valid_idx = np.where(np.isfinite(p))[0]
    if len(valid_idx) == 0:
        return adjusted

    order_local = np.argsort(p[valid_idx])
    sorted_idx = valid_idx[order_local]
    m = len(sorted_idx)
    sorted_p = p[sorted_idx]

    raw_adjusted = np.array([(m - i) * sorted_p[i] for i in range(m)])
    # Enforce monotonicity of Holm adjusted p-values.
    raw_adjusted = np.maximum.accumulate(raw_adjusted)
    raw_adjusted = np.minimum(raw_adjusted, 1.0)
    adjusted[sorted_idx] = raw_adjusted
    return adjusted


def add_holm_correction(inference):
    out = inference.copy()
    out["P_Value_Holm_Adjusted"] = holm_adjust(out["P_Value_Two_Sided"])
    out["Significant_Holm_0_05"] = out["P_Value_Holm_Adjusted"] < ALPHA
    out["Significant_Unadjusted_0_05"] = out["P_Value_Two_Sided"] < ALPHA
    out["Correction_Family_Size"] = int(out["P_Value_Two_Sided"].notna().sum())
    return out


def paired_diagnostics(paired):
    rows = []
    eligible = paired[
        (paired["Scenario"].isin(SCENARIOS)) &
        (paired["Recovery_Policy"] != "NO_RECOVERY")
    ].copy()

    for (scenario, policy), group in eligible.groupby(
        ["Scenario", "Recovery_Policy"], sort=True
    ):
        for metric in [
            "Delay_Saved_Hours",
            "Delay_Reduction_Percent",
            "Maximum_Port_Peak_Change",
        ]:
            x = pd.to_numeric(group[metric], errors="coerce").dropna().to_numpy(float)
            n = len(x)
            if n == 0:
                continue

            mean = float(np.mean(x))
            sd = float(np.std(x, ddof=1)) if n > 1 else np.nan
            q1, q3 = np.percentile(x, [25, 75])
            iqr = q3 - q1
            lower_fence, upper_fence = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            outlier_count = int(((x < lower_fence) | (x > upper_fence)).sum())

            # Shapiro-Wilk is suitable for the 30 paired differences here.
            if 3 <= n <= 5000 and np.unique(x).size > 2:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    shapiro_stat, shapiro_p = shapiro(x)
                shapiro_stat, shapiro_p = float(shapiro_stat), float(shapiro_p)
            else:
                shapiro_stat, shapiro_p = np.nan, np.nan

            # Wilcoxon signed-rank sensitivity test against zero.
            # If all differences are zero, p=1 and statistic=0 by definition.
            if np.allclose(x, 0):
                wilcoxon_stat, wilcoxon_p = 0.0, 1.0
            else:
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        test = wilcoxon(
                            x, zero_method="wilcox",
                            alternative="two-sided",
                            method="approx"
                        )
                    wilcoxon_stat, wilcoxon_p = float(test.statistic), float(test.pvalue)
                except ValueError:
                    wilcoxon_stat, wilcoxon_p = np.nan, np.nan

            rows.append({
                "Scenario": scenario,
                "Recovery_Policy": policy,
                "Metric": metric,
                "N_Paired_Seeds": n,
                "Mean_Difference": mean,
                "Median_Difference": float(np.median(x)),
                "SD_Difference": sd,
                "Q1": float(q1),
                "Q3": float(q3),
                "IQR": float(iqr),
                "IQR_Outlier_Count": outlier_count,
                "IQR_Outlier_Percent": outlier_count / n * 100,
                "Shapiro_W": shapiro_stat,
                "Shapiro_P_Value": shapiro_p,
                "Shapiro_Reject_Normality_0_05": (
                    bool(shapiro_p < ALPHA) if np.isfinite(shapiro_p) else np.nan
                ),
                "Wilcoxon_Statistic": wilcoxon_stat,
                "Wilcoxon_P_Value": wilcoxon_p,
            })

    out = pd.DataFrame(rows)
    if not out.empty:
        out["Wilcoxon_P_Holm_Adjusted"] = holm_adjust(out["Wilcoxon_P_Value"])
        out["Wilcoxon_Significant_Holm_0_05"] = (
            out["Wilcoxon_P_Holm_Adjusted"] < ALPHA
        )
    return out


def build_ci_summary(inference_holm):
    delay = inference_holm[
        inference_holm["Metric"].isin(DELAY_METRICS)
    ].copy()
    delay["Interpretation"] = np.where(
        delay["CI95_Lower"] > 0,
        "Positive delay saving; CI excludes zero",
        np.where(
            delay["CI95_Upper"] < 0,
            "Negative delay saving; CI excludes zero",
            "CI includes zero"
        )
    )
    return delay.sort_values(["Scenario", "Metric", "Mean_Paired_Difference"],
                             ascending=[True, True, False])


def plot_delay_saving_ci(ci_table):
    for metric, label, filename, x_label in [
        ("Delay_Saved_Hours", "Delay saved (hours)",
         "36_delay_saving_confidence_intervals.png",
         "Mean paired delay saving (hours)"),
        ("Delay_Reduction_Percent", "Delay reduction (%)",
         "36_delay_reduction_confidence_intervals.png",
         "Mean paired delay reduction (%)"),
    ]:
        data = ci_table[ci_table["Metric"] == metric].copy()
        if data.empty:
            continue
        data["Display"] = data["Scenario"].str.replace("S1_", "", regex=False)\
            .str.replace("S2_", "", regex=False)\
            .str.replace("S3_", "", regex=False) + " | " + data["Recovery_Policy"]
        data = data.sort_values(["Scenario", "Mean_Paired_Difference"])
        y = np.arange(len(data))
        means = data["Mean_Paired_Difference"].to_numpy()
        lower = means - data["CI95_Lower"].to_numpy()
        upper = data["CI95_Upper"].to_numpy() - means

        fig_height = max(7, 0.28 * len(data))
        fig, ax = plt.subplots(figsize=(12, fig_height))
        ax.errorbar(means, y, xerr=np.vstack([lower, upper]),
                    fmt="o", capsize=3, linewidth=1)
        ax.axvline(0, linestyle="--", linewidth=1)
        ax.set_yticks(y)
        ax.set_yticklabels(data["Display"])
        ax.set_xlabel(x_label)
        ax.set_title(f"Script 36 — 95% confidence intervals: {label}")
        ax.grid(axis="x", alpha=0.25)
        fig.tight_layout()
        fig.savefig(FIGURE_DIR / filename, dpi=220, bbox_inches="tight")
        plt.close(fig)


def plot_paired_difference_distributions(paired):
    metrics = [
        ("Delay_Saved_Hours", "Delay saved (hours)", "36_delay_saving_distributions.png"),
        ("Delay_Reduction_Percent", "Delay reduction (%)", "36_delay_reduction_distributions.png"),
        ("Maximum_Port_Peak_Change", "Maximum port peak change", "36_peak_change_distributions.png"),
    ]
    for metric, ylabel, filename in metrics:
        fig, axes = plt.subplots(1, 3, figsize=(17, 6), sharey=False)
        for ax, scenario in zip(axes, SCENARIOS):
            sub = paired[
                (paired["Scenario"] == scenario) &
                (paired["Recovery_Policy"] != "NO_RECOVERY")
            ]
            policies = sorted(sub["Recovery_Policy"].unique())
            values = [
                sub.loc[sub["Recovery_Policy"] == policy, metric].dropna().to_numpy()
                for policy in policies
            ]
            ax.boxplot(values, tick_labels=policies, showfliers=True)
            ax.axhline(0, linestyle="--", linewidth=1)
            ax.set_title(scenario)
            ax.set_ylabel(ylabel)
            ax.tick_params(axis="x", rotation=90)
            ax.grid(axis="y", alpha=0.2)
        fig.suptitle(f"Script 36 — Paired difference distributions: {ylabel}")
        fig.tight_layout()
        fig.savefig(FIGURE_DIR / filename, dpi=220, bbox_inches="tight")
        plt.close(fig)


def plot_rank_stability(stability):
    for scenario in SCENARIOS:
        sub = stability[stability["Scenario"] == scenario].copy()
        if sub.empty:
            continue
        pivot = sub.pivot(
            index="Recovery_Policy", columns="Scenario",
            values="Seed_Win_Percent"
        )
        # Single-scenario heatmap; cell value is the percentage of seeds won.
        values = pivot.to_numpy(float)
        fig, ax = plt.subplots(figsize=(7, max(5, 0.42 * len(pivot))))
        im = ax.imshow(values, aspect="auto", vmin=0, vmax=100)
        ax.set_yticks(np.arange(len(pivot.index)))
        ax.set_yticklabels(pivot.index)
        ax.set_xticks([0])
        ax.set_xticklabels([scenario])
        for i, value in enumerate(values[:, 0]):
            ax.text(0, i, f"{value:.1f}%", ha="center", va="center")
        ax.set_title(f"Script 36 — Seed-level joint-winner frequency: {scenario}")
        fig.colorbar(im, ax=ax, label="Seed win percentage")
        fig.tight_layout()
        fig.savefig(
            FIGURE_DIR / f"36_rank_stability_{scenario.lower()}.png",
            dpi=220, bbox_inches="tight"
        )
        plt.close(fig)

    # Combined heatmap for all scenarios.
    pivot = stability.pivot(
        index="Recovery_Policy", columns="Scenario", values="Seed_Win_Percent"
    ).reindex(columns=SCENARIOS)
    fig, ax = plt.subplots(figsize=(10, max(6, 0.42 * len(pivot))))
    im = ax.imshow(pivot.to_numpy(float), aspect="auto", vmin=0, vmax=100)
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            value = pivot.iloc[i, j]
            if pd.notna(value):
                ax.text(j, i, f"{value:.1f}%", ha="center", va="center")
    ax.set_title("Script 36 — Policy joint-winner frequency across seeds")
    fig.colorbar(im, ax=ax, label="Seed win percentage")
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "36_policy_rank_stability_heatmap.png",
                dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_pareto(summary):
    required = {
        "Scenario", "Recovery_Policy",
        "Mean_Total_Accumulated_Delay_Hours", "Mean_Maximum_Port_Peak"
    }
    missing = required - set(summary.columns)
    if missing:
        raise ValueError(f"Scenario summary missing columns for Pareto plot: {sorted(missing)}")

    fig, axes = plt.subplots(1, 3, figsize=(17, 6))
    for ax, scenario in zip(axes, SCENARIOS):
        sub = summary[summary["Scenario"] == scenario].copy()
        if sub.empty:
            continue
        delay_values = sub["Mean_Total_Accumulated_Delay_Hours"].to_numpy(float)
        peak_values = sub["Mean_Maximum_Port_Peak"].to_numpy(float)
        efficient_flags = []
        for i in range(len(sub)):
            dominated = any(
                j != i and delay_values[j] <= delay_values[i]
                and peak_values[j] <= peak_values[i]
                and (delay_values[j] < delay_values[i] or peak_values[j] < peak_values[i])
                for j in range(len(sub))
            )
            efficient_flags.append(not dominated)
        efficient = pd.Series(efficient_flags, index=sub.index)
        for idx, row in sub.iterrows():
            is_efficient = bool(efficient.loc[idx])
            ax.scatter(
                row["Mean_Total_Accumulated_Delay_Hours"],
                row["Mean_Maximum_Port_Peak"],
                marker="o" if is_efficient else "x",
                s=65
            )
            ax.annotate(
                row["Recovery_Policy"].replace("PARTIAL_RECOVERY_", "P").replace(
                    "FIXED_RECOVERY_", "F"
                ).replace("NO_RECOVERY", "None"),
                (row["Mean_Total_Accumulated_Delay_Hours"],
                 row["Mean_Maximum_Port_Peak"]),
                fontsize=7, xytext=(4, 4), textcoords="offset points"
            )
        ax.set_title(scenario)
        ax.set_xlabel("Mean accumulated call-delay hours")
        ax.set_ylabel("Mean maximum port-specific peak")
        ax.grid(alpha=0.25)
    fig.suptitle("Script 36 — Delay versus port-call concurrency trade-off")
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "36_pareto_delay_vs_port_peak.png",
                dpi=220, bbox_inches="tight")
    plt.close(fig)


def build_consolidated_table(summary, stability):
    keys = ["Scenario", "Recovery_Policy"]
    keep_summary = [
        c for c in [
            "Scenario", "Recovery_Policy", "Replications",
            "Mean_Total_Accumulated_Delay_Hours",
            "Mean_Total_Recovered_Hours",
            "Mean_Maximum_Port_Peak", "Mean_Average_Port_Peak",
            "Mean_Average_Port_Concurrency"
        ] if c in summary.columns
    ]
    keep_stability = [
        c for c in [
            "Scenario", "Recovery_Policy", "Mean_Rank_Sum",
            "SD_Rank_Sum", "Best_Rank_Sum_Count",
            "Seed_Win_Count", "Seed_Win_Percent", "N_Seeds"
        ] if c in stability.columns
    ]
    return summary[keep_summary].merge(
        stability[keep_stability], on=keys, how="left", validate="one_to_one"
    )


def write_report(inference_holm, diagnostics, ci_table, consolidated,
                 seed_rankings, winners):
    path = REPORT_DIR / "36_statistical_robustness_report.txt"
    with path.open("w", encoding="utf-8") as f:
        f.write("SCRIPT 36: STATISTICAL ROBUSTNESS AND FINAL VISUALIZATION\n")
        f.write("=" * 100 + "\n\n")
        f.write("INPUTS\n")
        f.write(f"Paired inference rows: {len(inference_holm)}\n")
        f.write(f"Seed-level ranking rows: {len(seed_rankings)}\n")
        f.write(f"Joint-winner rows: {len(winners)}\n")
        f.write(f"Expected seeds per scenario-policy pair: {EXPECTED_SEEDS}\n\n")

        f.write("HOLM-ADJUSTED PAIRED INFERENCE\n" + "-" * 100 + "\n")
        f.write(inference_holm.to_string(index=False) + "\n\n")

        f.write("NORMALITY, OUTLIER AND WILCOXON DIAGNOSTICS\n" + "-" * 100 + "\n")
        f.write(diagnostics.to_string(index=False) + "\n\n")

        f.write("DELAY-SAVING CONFIDENCE INTERVALS\n" + "-" * 100 + "\n")
        f.write(ci_table.to_string(index=False) + "\n\n")

        f.write("CONSOLIDATED SCENARIO / POLICY RESULTS\n" + "-" * 100 + "\n")
        f.write(consolidated.to_string(index=False) + "\n\n")

        f.write("INTERPRETATION AND LIMITATIONS\n" + "-" * 100 + "\n")
        f.write(
            "1. Holm correction controls family-wise error across the 90 Script 35 paired tests.\n"
            "2. Shapiro-Wilk tests assess normality of paired differences; with n=30, interpret "
            "diagnostics alongside plots rather than as a definitive model check.\n"
            "3. IQR flags are descriptive potential outliers, not grounds for automatic removal.\n"
            "4. Wilcoxon signed-rank tests provide a non-parametric sensitivity analysis; "
            "they test paired differences around zero under their own assumptions.\n"
            "5. Confidence intervals and p-values concern simulated outcomes under the specified "
            "hypothetical recovery rules, not observed operational effects.\n"
            "6. The policy rank-sum is descriptive and depends on treating delay and peak rank "
            "as equally weighted objectives.\n"
            "7. Pareto efficiency is limited to the two selected model outputs.\n"
            "8. Maximum port-specific peak concurrency is not berth occupancy, port capacity, "
            "or a validated congestion measure.\n"
            "9. Port-call sequences do not establish continuous voyages or confirmed Strait "
            "of Hormuz crossings. AIS/equivalent movement evidence is still required.\n"
            "10. Higher replication count improves Monte Carlo precision but does not correct "
            "data coverage, parameter, or structural model limitations.\n"
        )
    return path


def main():
    print("=" * 88)
    print("SCRIPT 36: STATISTICAL ROBUSTNESS AND FINAL VISUALIZATION")
    print("=" * 88)
    print("Reading Script 35 outputs; no simulation runs will be repeated.")

    inference, stability, seed_rankings, winners, summary, paired, combined = load_inputs()

    print(f"Paired inference rows: {len(inference)}")
    print(f"Rank stability rows: {len(stability)}")
    print(f"Seed-level ranking rows: {len(seed_rankings)}")
    print(f"Joint-winner rows: {len(winners)}")

    # Validate expected structure.
    if len(inference) != 90:
        raise AssertionError(f"Expected 90 paired tests; found {len(inference)}.")
    if len(seed_rankings) != 990:
        raise AssertionError(f"Expected 990 seed-policy rankings; found {len(seed_rankings)}.")
    if set(SCENARIOS) - set(stability["Scenario"].unique()):
        raise AssertionError("One or more disruption scenarios are missing from rank stability.")

    seed_counts = seed_rankings.groupby(
        ["Scenario", "Recovery_Policy"]
    )["Replication_Seed"].nunique()
    if not seed_counts.eq(EXPECTED_SEEDS).all():
        raise AssertionError("Not every scenario-policy combination has 30 seeds.")

    inference_holm = add_holm_correction(inference)
    diagnostics = paired_diagnostics(paired)
    ci_table = build_ci_summary(inference_holm)
    consolidated = build_consolidated_table(summary, stability)

    # Save analysis tables.
    outputs = {
        "36_holm_adjusted_paired_inference.csv": inference_holm,
        "36_paired_difference_diagnostics.csv": diagnostics,
        "36_delay_saving_confidence_intervals.csv": ci_table,
        "36_consolidated_policy_results.csv": consolidated,
    }
    for name, frame in outputs.items():
        frame.to_csv(TABLE_DIR / name, index=False)

    # Generate figures.
    plot_delay_saving_ci(ci_table)
    plot_paired_difference_distributions(paired)
    plot_rank_stability(stability)
    plot_pareto(summary)

    report_path = write_report(
        inference_holm, diagnostics, ci_table, consolidated,
        seed_rankings, winners
    )

    checks = {
        "90 paired tests loaded": len(inference) == 90,
        "Holm-adjusted p-values generated": inference_holm["P_Value_Holm_Adjusted"].notna().all(),
        "Paired diagnostics generated": len(diagnostics) == 90,
        "30 seeds per scenario-policy combination": seed_counts.eq(EXPECTED_SEEDS).all(),
        "Consolidated results generated": not consolidated.empty,
        "Report saved": report_path.exists(),
        "Four analysis tables saved": all((TABLE_DIR / name).exists() for name in outputs),
        "Final figures generated": len(list(FIGURE_DIR.glob("36_*.png"))) >= 7,
    }

    print("\nVALIDATION")
    for label, passed in checks.items():
        print(f"{label}: {'PASS' if passed else 'FAIL'}")
    if not all(checks.values()):
        raise AssertionError("One or more Script 36 validation checks failed.")

    print("\nHOLM CORRECTION SUMMARY")
    print(
        inference_holm.groupby("Metric").agg(
            Tests=("P_Value_Holm_Adjusted", "size"),
            Significant_Holm=("Significant_Holm_0_05", "sum"),
            Significant_Unadjusted=("Significant_Unadjusted_0_05", "sum")
        ).to_string()
    )

    print("\nWILCOXON SENSITIVITY SUMMARY")
    print(
        diagnostics.groupby("Metric").agg(
            Tests=("Wilcoxon_P_Holm_Adjusted", "size"),
            Significant_Wilcoxon_Holm=("Wilcoxon_Significant_Holm_0_05", "sum")
        ).to_string()
    )

    print("\nSAVED TABLES")
    for name in outputs:
        print(f"- outputs/tables/{name}")
    print("\nSAVED FIGURES")
    for path in sorted(FIGURE_DIR.glob("36_*.png")):
        print(f"- outputs/figures/{path.name}")
    print(f"\nREPORT: outputs/reports/{report_path.name}")
    print("\nSCRIPT 36 COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()
