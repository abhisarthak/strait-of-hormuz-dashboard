"""
SCRIPT 63: EMPIRICAL PARAMETER DISTRIBUTION AND UNCERTAINTY ASSESSMENT
======================================================================
Purpose
-------
Assess the empirical distribution of departure-to-next-arrival elapsed time
for each of the 53 existing directed inter-port pairs.

The script:
1. Recomputes distributional descriptors from the 271 observed transitions.
2. Reports quantiles, skewness, coefficient of variation and tail ratios.
3. Performs leave-one-vessel-out sensitivity analysis where feasible.
4. Performs a vessel-cluster bootstrap for selected edges, preserving all
   observations belonging to each sampled vessel.
5. Assigns a cautious distribution-representation suitability class.
6. Does NOT fit or impose a normal/lognormal/gamma distribution.
7. Does NOT approve empirical resampling or change simulation inputs.

Interpretation safeguard
------------------------
Elapsed_Hours_Between_Calls is the interval from previous-port departure to
next-port arrival. It may include sailing, waiting and unobserved operations.
It is not pure sailing time.

Cluster bootstrap
-----------------
Vessels, not individual transitions, are the resampling units. Bootstrap
intervals are produced only when an edge has at least 3 distinct vessels and
at least 5 valid transition records. They are exploratory uncertainty summaries,
not proof that vessels are a random sample of all traffic.

Inputs
------
data/simulation_inputs/19_observed_interport_transitions.csv
outputs/tables/62_edge_evidence_reliability_register.csv

Outputs
-------
outputs/tables/63_empirical_distribution_assessment.csv
outputs/tables/63_leave_one_vessel_out_sensitivity.csv
outputs/tables/63_vessel_cluster_bootstrap_uncertainty.csv
outputs/tables/63_distribution_suitability_summary.csv
outputs/reports/63_empirical_parameter_distribution_report.txt
"""

from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "data" / "simulation_inputs"
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"

TRANSITION_FILE = SIM / "19_observed_interport_transitions.csv"
SCRIPT62_FILE = TABLES / "62_edge_evidence_reliability_register.csv"

OUT_DIST = TABLES / "63_empirical_distribution_assessment.csv"
OUT_LOO = TABLES / "63_leave_one_vessel_out_sensitivity.csv"
OUT_BOOT = TABLES / "63_vessel_cluster_bootstrap_uncertainty.csv"
OUT_SUMMARY = TABLES / "63_distribution_suitability_summary.csv"
OUT_REPORT = REPORTS / "63_empirical_parameter_distribution_report.txt"

BOOTSTRAP_REPLICATES = 2000
RANDOM_SEED = 6302026
MIN_VESSELS_FOR_BOOTSTRAP = 3
MIN_RECORDS_FOR_BOOTSTRAP = 5


def norm_text(series):
    return series.astype("string").str.strip().str.upper()


def safe_cv(mean, std):
    if pd.isna(mean) or pd.isna(std) or mean == 0:
        return np.nan
    return std / mean


def distribution_class(n, vessels, skew, cv, q90_q50):
    # These are representation-readiness screens, not fitted distribution claims.
    if n < 3 or vessels < 2:
        return "INSUFFICIENT_FOR_DISTRIBUTION_REPRESENTATION"
    if n < 5 or vessels < 3:
        return "DESCRIPTIVE_EMPIRICAL_SUMMARY_ONLY"
    if n < 10 or vessels < 4:
        return "LIMITED_EMPIRICAL_DISTRIBUTION_CANDIDATE"
    if pd.notna(skew) and abs(skew) > 2:
        return "EMPIRICAL_OR_ROBUST_TAIL_REPRESENTATION_PREFERRED"
    if pd.notna(q90_q50) and q90_q50 > 2.5:
        return "EMPIRICAL_OR_ROBUST_TAIL_REPRESENTATION_PREFERRED"
    if pd.notna(cv) and cv > 1:
        return "EMPIRICAL_OR_ROBUST_TAIL_REPRESENTATION_PREFERRED"
    return "EMPIRICAL_DISTRIBUTION_CANDIDATE_WITH_VESSEL_CLUSTERING"


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    for p in [TRANSITION_FILE, SCRIPT62_FILE]:
        if not p.exists():
            raise FileNotFoundError(f"Required input missing: {p}")

    transitions = pd.read_csv(TRANSITION_FILE)
    script62 = pd.read_csv(SCRIPT62_FILE)

    required_t = [
        "Previous_Port", "Next_Port", "IMO_Normalised",
        "Elapsed_Hours_Between_Calls"
    ]
    required_62 = [
        "Previous_Port", "Next_Port", "Valid_Elapsed_Record_Count",
        "Distinct_Vessel_Count", "Evidence_Strength_Tier_62"
    ]
    for label, df, cols in [
        ("transitions", transitions, required_t),
        ("Script 62 register", script62, required_62),
    ]:
        missing = [c for c in cols if c not in df.columns]
        if missing:
            raise ValueError(f"{label} missing columns: {missing}")

    transitions["_origin"] = norm_text(transitions["Previous_Port"])
    transitions["_destination"] = norm_text(transitions["Next_Port"])
    transitions["_imo"] = norm_text(transitions["IMO_Normalised"])
    transitions["_elapsed"] = pd.to_numeric(
        transitions["Elapsed_Hours_Between_Calls"], errors="coerce"
    )
    transitions = transitions[
        transitions["_origin"].notna()
        & transitions["_destination"].notna()
        & transitions["_imo"].notna()
        & (transitions["_imo"] != "")
        & transitions["_elapsed"].notna()
        & np.isfinite(transitions["_elapsed"])
        & (transitions["_elapsed"] >= 0)
    ].copy()

    script62["_origin"] = norm_text(script62["Previous_Port"])
    script62["_destination"] = norm_text(script62["Next_Port"])
    if script62.duplicated(["_origin", "_destination"]).any():
        raise ValueError("Script 62 contains duplicate directed pairs.")

    rng = np.random.default_rng(RANDOM_SEED)
    dist_rows, loo_rows, boot_rows = [], [], []

    for _, edge in script62.iterrows():
        origin, destination = edge["_origin"], edge["_destination"]
        g = transitions[
            (transitions["_origin"] == origin)
            & (transitions["_destination"] == destination)
        ].copy()

        x = g["_elapsed"].astype(float)
        vessel_groups = {
            imo: grp["_elapsed"].astype(float).to_numpy()
            for imo, grp in g.groupby("_imo")
        }
        n = len(x)
        v = len(vessel_groups)

        if n:
            q05, q10, q25, q50, q75, q90, q95 = x.quantile(
                [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
            )
            mean, median = x.mean(), x.median()
            std = x.std(ddof=1) if n > 1 else np.nan
            skew = x.skew() if n >= 3 else np.nan
            cv = safe_cv(mean, std)
            q90_q50 = q90 / q50 if q50 > 0 else np.nan
            q95_q50 = q95 / q50 if q50 > 0 else np.nan
            iqr = q75 - q25
            tail_share = float((x > q90).mean())
        else:
            q05 = q10 = q25 = q50 = q75 = q90 = q95 = np.nan
            mean = median = std = skew = cv = q90_q50 = q95_q50 = iqr = tail_share = np.nan

        cls = distribution_class(n, v, skew, cv, q90_q50)
        dist_rows.append({
            "Previous_Port": origin,
            "Next_Port": destination,
            "Valid_Transition_Count_63": n,
            "Distinct_Vessel_Count_63": v,
            "Mean_Elapsed_Hours": mean,
            "Median_Elapsed_Hours": median,
            "Std_Elapsed_Hours": std,
            "Coefficient_Of_Variation": cv,
            "Skewness": skew,
            "P05_Elapsed_Hours": q05,
            "P10_Elapsed_Hours": q10,
            "P25_Elapsed_Hours": q25,
            "P50_Elapsed_Hours": q50,
            "P75_Elapsed_Hours": q75,
            "P90_Elapsed_Hours": q90,
            "P95_Elapsed_Hours": q95,
            "IQR_Elapsed_Hours": iqr,
            "P90_to_Median_Ratio": q90_q50,
            "P95_to_Median_Ratio": q95_q50,
            "Observed_Max_Elapsed_Hours": x.max() if n else np.nan,
            "Share_Above_Empirical_P90": tail_share,
            "Distribution_Representation_Class_63": cls,
            "Parametric_Distribution_Fitted": False,
            "Automatic_Resampling_Approval": False,
            "Script62_Evidence_Tier": edge["Evidence_Strength_Tier_62"],
            "Elapsed_Time_Interpretation": (
                "Departure-to-next-arrival elapsed time; includes sailing, waiting "
                "and unobserved operations; not pure sailing time."
            ),
        })

        # Leave-one-vessel-out: remove all records from one vessel at a time.
        if v >= 2 and n >= 3:
            base_mean = x.mean()
            base_median = x.median()
            base_p90 = x.quantile(0.90)
            for omitted_imo, omitted_values in vessel_groups.items():
                remaining = np.concatenate([
                    vals for imo, vals in vessel_groups.items()
                    if imo != omitted_imo
                ]) if v > 1 else np.array([])
                if len(remaining):
                    loo_rows.append({
                        "Previous_Port": origin,
                        "Next_Port": destination,
                        "Omitted_IMO": omitted_imo,
                        "Omitted_Record_Count": len(omitted_values),
                        "Remaining_Record_Count": len(remaining),
                        "Remaining_Vessel_Count": v - 1,
                        "Baseline_Mean_Hours": base_mean,
                        "LOO_Mean_Hours": float(np.mean(remaining)),
                        "LOO_Mean_Absolute_Change_Hours": float(abs(np.mean(remaining) - base_mean)),
                        "LOO_Median_Hours": float(np.median(remaining)),
                        "LOO_Median_Absolute_Change_Hours": float(abs(np.median(remaining) - base_median)),
                        "LOO_P90_Hours": float(np.quantile(remaining, 0.90)),
                        "LOO_P90_Absolute_Change_Hours": float(abs(np.quantile(remaining, 0.90) - base_p90)),
                        "Sensitivity_Method": "Leave one vessel out; remove all that vessel's edge observations",
                    })

        # Vessel-cluster bootstrap: sample vessel clusters with replacement.
        if v >= MIN_VESSELS_FOR_BOOTSTRAP and n >= MIN_RECORDS_FOR_BOOTSTRAP:
            imos = list(vessel_groups.keys())
            boot_means, boot_medians, boot_p90s = [], [], []
            for _rep in range(BOOTSTRAP_REPLICATES):
                sampled = rng.choice(imos, size=len(imos), replace=True)
                sample_values = np.concatenate([vessel_groups[imo] for imo in sampled])
                boot_means.append(float(np.mean(sample_values)))
                boot_medians.append(float(np.median(sample_values)))
                boot_p90s.append(float(np.quantile(sample_values, 0.90)))

            def ci(values):
                return np.quantile(values, [0.025, 0.975])

            mean_lo, mean_hi = ci(boot_means)
            median_lo, median_hi = ci(boot_medians)
            p90_lo, p90_hi = ci(boot_p90s)
            boot_rows.append({
                "Previous_Port": origin,
                "Next_Port": destination,
                "Distinct_Vessel_Clusters": v,
                "Transition_Record_Count": n,
                "Bootstrap_Replicates": BOOTSTRAP_REPLICATES,
                "Bootstrap_Unit": "Vessel cluster; all edge observations for sampled vessel retained",
                "Mean_Point_Estimate_Hours": mean,
                "Mean_Bootstrap_CI95_Lower_Hours": mean_lo,
                "Mean_Bootstrap_CI95_Upper_Hours": mean_hi,
                "Median_Point_Estimate_Hours": median,
                "Median_Bootstrap_CI95_Lower_Hours": median_lo,
                "Median_Bootstrap_CI95_Upper_Hours": median_hi,
                "P90_Point_Estimate_Hours": q90,
                "P90_Bootstrap_CI95_Lower_Hours": p90_lo,
                "P90_Bootstrap_CI95_Upper_Hours": p90_hi,
                "Interpretation": (
                    "Exploratory cluster-bootstrap uncertainty; few vessel clusters "
                    "may make intervals unstable and do not establish population representativeness."
                ),
            })

    dist = pd.DataFrame(dist_rows)
    loo = pd.DataFrame(loo_rows)
    boot = pd.DataFrame(boot_rows)

    # Summarize LOO sensitivity per edge.
    if not loo.empty:
        loo_summary = loo.groupby(["Previous_Port", "Next_Port"]).agg(
            LOO_Vessel_Count=("Omitted_IMO", "nunique"),
            Max_LOO_Mean_Change_Hours=("LOO_Mean_Absolute_Change_Hours", "max"),
            Max_LOO_Median_Change_Hours=("LOO_Median_Absolute_Change_Hours", "max"),
            Max_LOO_P90_Change_Hours=("LOO_P90_Absolute_Change_Hours", "max"),
        ).reset_index()
        dist = dist.merge(loo_summary, on=["Previous_Port", "Next_Port"], how="left")
    else:
        dist["LOO_Vessel_Count"] = 0
        dist["Max_LOO_Mean_Change_Hours"] = np.nan
        dist["Max_LOO_Median_Change_Hours"] = np.nan
        dist["Max_LOO_P90_Change_Hours"] = np.nan

    if not boot.empty:
        dist = dist.merge(
            boot[["Previous_Port", "Next_Port", "Mean_Bootstrap_CI95_Lower_Hours",
                  "Mean_Bootstrap_CI95_Upper_Hours", "Median_Bootstrap_CI95_Lower_Hours",
                  "Median_Bootstrap_CI95_Upper_Hours", "P90_Bootstrap_CI95_Lower_Hours",
                  "P90_Bootstrap_CI95_Upper_Hours"]],
            on=["Previous_Port", "Next_Port"], how="left"
        )

    summary = (
        dist.groupby("Distribution_Representation_Class_63", dropna=False)
        .agg(
            Directed_Edge_Count=("Previous_Port", "size"),
            Total_Valid_Transitions=("Valid_Transition_Count_63", "sum"),
            Median_Vessel_Count=("Distinct_Vessel_Count_63", "median"),
        )
        .reset_index()
    )
    summary["Automatic_Resampling_Approval"] = False
    summary["Parametric_Fit_Approved"] = False

    dist.to_csv(OUT_DIST, index=False)
    loo.to_csv(OUT_LOO, index=False)
    boot.to_csv(OUT_BOOT, index=False)
    summary.to_csv(OUT_SUMMARY, index=False)

    loo_edges = dist["LOO_Vessel_Count"].fillna(0).gt(0).sum()
    bootstrap_edges = len(boot)
    with OUT_REPORT.open("w", encoding="utf-8") as f:
        f.write("=" * 88 + "\n")
        f.write("SCRIPT 63: EMPIRICAL PARAMETER DISTRIBUTION AND UNCERTAINTY ASSESSMENT\n")
        f.write("=" * 88 + "\n\n")
        f.write(f"Directed edges assessed: {len(dist)}\n")
        f.write(f"Valid observed transition records: {len(transitions)}\n")
        f.write(f"Edges with leave-one-vessel-out analysis: {loo_edges}\n")
        f.write(f"Leave-one-vessel-out rows: {len(loo)}\n")
        f.write(f"Edges with vessel-cluster bootstrap: {bootstrap_edges}\n")
        f.write(f"Bootstrap replicates per eligible edge: {BOOTSTRAP_REPLICATES}\n\n")
        f.write("DISTRIBUTION REPRESENTATION CLASSES\n")
        f.write(summary.to_string(index=False))
        f.write("\n\nMETHODOLOGICAL LIMITATIONS\n")
        f.write(
            "No parametric distribution is fitted. The classification is a cautious "
            "screen based on sample size, vessel count, skewness and tail ratios. "
            "Leave-one-vessel-out results show sensitivity to the removal of each "
            "observed vessel, not external validity. The cluster bootstrap samples "
            "vessels as clusters but may be unstable when the number of vessels is "
            "small. It does not establish that observed vessels are representative "
            "of the target population. Elapsed time includes sailing, waiting and "
            "unobserved operations and is not pure sailing time. No resampling or "
            "operational approval is granted.\n"
        )
        f.write("\nSOURCE FILES MODIFIED: NO\n")
        f.write("SIMULATION INPUTS MODIFIED: NO\n")
        f.write("AUTOMATIC RESAMPLING APPROVALS: NONE\n")

    print("=" * 88)
    print("SCRIPT 63: EMPIRICAL PARAMETER DISTRIBUTION AND UNCERTAINTY ASSESSMENT")
    print("=" * 88)
    print(f"Directed edges assessed: {len(dist)}")
    print(f"Valid observed transition records: {len(transitions)}")
    print("\nDistribution representation classes:")
    print(dist["Distribution_Representation_Class_63"].value_counts().to_string())
    print(f"\nEdges with leave-one-vessel-out analysis: {loo_edges}")
    print(f"Leave-one-vessel-out rows: {len(loo)}")
    print(f"Edges with vessel-cluster bootstrap: {bootstrap_edges}")
    print(f"Bootstrap replicates per eligible edge: {BOOTSTRAP_REPLICATES}")
    print("\nOutputs:")
    for p in [OUT_DIST, OUT_LOO, OUT_BOOT, OUT_SUMMARY, OUT_REPORT]:
        print(p.relative_to(ROOT))
    print("\nPARAMETRIC DISTRIBUTIONS FITTED: NO")
    print("AUTOMATIC RESAMPLING APPROVALS: NONE")
    print("SOURCE FILES MODIFIED: NO")
    print("SCRIPT 63 COMPLETED")


if __name__ == "__main__":
    main()
