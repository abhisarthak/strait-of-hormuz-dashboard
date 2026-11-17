"""
SCRIPT 62: NETWORK EVIDENCE STRENGTH AND PARAMETER RELIABILITY AUDIT
====================================================================
Read-only audit of the 53 existing directed inter-port pairs using the 271
observed transition records and Script 19 inter-port parameter table.

The script measures:
- transition count and distinct vessel count per directed pair;
- vessel concentration (largest vessel share and HHI);
- elapsed-time distribution and dispersion;
- potential extreme observations using a descriptive IQR screen;
- consistency of independently recomputed statistics with Script 19 parameters.

Important:
Elapsed_Hours_Between_Calls is departure-to-next-arrival elapsed time. It includes
sailing, waiting and unobserved operations; it is NOT pure sailing time.

This is an evidence-strength audit, not a route validation or a decision to
resample. Threshold-based evidence tiers are transparent screening labels only.
They do not override Script 24's parameter suitability assessment.

Inputs:
    outputs/tables/21_port_connection_metrics.csv
    data/simulation_inputs/19_observed_interport_transitions.csv
    data/simulation_inputs/19_interport_time_parameters.csv

Outputs:
    outputs/tables/62_edge_evidence_reliability_register.csv
    outputs/tables/62_vessel_concentration_audit.csv
    outputs/tables/62_parameter_reconciliation.csv
    outputs/tables/62_evidence_tier_summary.csv
    outputs/reports/62_network_evidence_strength_report.txt
"""

from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
SIM = ROOT / "data" / "simulation_inputs"
REPORTS = ROOT / "outputs" / "reports"

EDGE_FILE = TABLES / "21_port_connection_metrics.csv"
TRANSITION_FILE = SIM / "19_observed_interport_transitions.csv"
PARAMETER_FILE = SIM / "19_interport_time_parameters.csv"

OUT_REGISTER = TABLES / "62_edge_evidence_reliability_register.csv"
OUT_VESSEL = TABLES / "62_vessel_concentration_audit.csv"
OUT_RECON = TABLES / "62_parameter_reconciliation.csv"
OUT_SUMMARY = TABLES / "62_evidence_tier_summary.csv"
OUT_REPORT = REPORTS / "62_network_evidence_strength_report.txt"

# Transparent descriptive screening tiers. These are not automatic approvals.
def evidence_tier(n, vessels, largest_share):
    if n >= 10 and vessels >= 5 and largest_share <= 0.50:
        return "RELATIVELY_STRONGER_EMPIRICAL_EVIDENCE"
    if n >= 5 and vessels >= 3:
        return "LIMITED_MULTI_VESSEL_EVIDENCE"
    if n >= 2:
        return "SPARSE_EVIDENCE"
    return "SINGLE_OBSERVATION_ONLY"


def normalized_pair(df, a, b):
    return (
        df[a].astype("string").str.strip().str.upper(),
        df[b].astype("string").str.strip().str.upper(),
    )


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    for path in [EDGE_FILE, TRANSITION_FILE, PARAMETER_FILE]:
        if not path.exists():
            raise FileNotFoundError(f"Required input missing: {path}")

    edges = pd.read_csv(EDGE_FILE)
    transitions = pd.read_csv(TRANSITION_FILE)
    params = pd.read_csv(PARAMETER_FILE)

    required = {
        "edges": (edges, ["Previous_Port", "Next_Port"]),
        "transitions": (
            transitions,
            ["Previous_Port", "Next_Port", "IMO_Normalised",
             "Elapsed_Hours_Between_Calls", "Time_Interpretation"]
        ),
        "parameters": (
            params,
            ["Previous_Port", "Next_Port", "sample_size",
             "mean_elapsed_hours", "median_elapsed_hours",
             "std_elapsed_hours", "min_elapsed_hours",
             "max_elapsed_hours", "p90_elapsed_hours"]
        ),
    }
    for label, (df, cols) in required.items():
        missing = [c for c in cols if c not in df.columns]
        if missing:
            raise ValueError(f"{label} missing required columns: {missing}")

    for df in [edges, transitions, params]:
        df["_origin"] = df["Previous_Port"].astype("string").str.strip().str.upper()
        df["_destination"] = df["Next_Port"].astype("string").str.strip().str.upper()

    values = pd.to_numeric(
        transitions["Elapsed_Hours_Between_Calls"], errors="coerce"
    )
    transitions["_elapsed"] = values
    transitions["_imo"] = (
        transitions["IMO_Normalised"].astype("string").str.strip().str.upper()
    )
    transitions["_valid_elapsed"] = (
        transitions["_elapsed"].notna()
        & np.isfinite(transitions["_elapsed"])
        & (transitions["_elapsed"] >= 0)
    )

    if edges.duplicated(["_origin", "_destination"]).any():
        raise ValueError("Duplicate directed pairs found in Script 21 edge file.")
    if params.duplicated(["_origin", "_destination"]).any():
        raise ValueError("Duplicate directed pairs found in Script 19 parameter file.")

    edge_pairs = set(zip(edges["_origin"], edges["_destination"]))
    parameter_pairs = set(zip(params["_origin"], params["_destination"]))
    transition_pairs = set(zip(
        transitions.loc[transitions["_origin"].notna(), "_origin"],
        transitions.loc[transitions["_origin"].notna(), "_destination"]
    ))
    if edge_pairs != parameter_pairs:
        raise ValueError("Network edge pairs and inter-port parameter pairs differ.")

    rows = []
    vessel_rows = []
    for origin, destination in sorted(edge_pairs):
        group = transitions[
            (transitions["_origin"] == origin)
            & (transitions["_destination"] == destination)
        ].copy()
        valid = group.loc[group["_valid_elapsed"]]
        n_records = len(group)
        n_valid = len(valid)
        n_invalid = n_records - n_valid
        vessel_counts = (
            valid.loc[valid["_imo"].notna() & (valid["_imo"] != "")]
            .groupby("_imo").size().sort_values(ascending=False)
        )
        n_vessels = int(vessel_counts.size)
        shares = vessel_counts / vessel_counts.sum() if vessel_counts.sum() else pd.Series(dtype=float)
        largest_share = float(shares.iloc[0]) if len(shares) else np.nan
        hhi = float((shares ** 2).sum()) if len(shares) else np.nan

        x = valid["_elapsed"].astype(float)
        if n_valid:
            q1, q3 = x.quantile([0.25, 0.75])
            iqr = q3 - q1
            lower = max(0.0, q1 - 1.5 * iqr)
            upper = q3 + 1.5 * iqr
            outlier_count = int(((x < lower) | (x > upper)).sum())
            outlier_pct = 100 * outlier_count / n_valid
            stats = {
                "Mean_Elapsed_Hours_Recomputed": x.mean(),
                "Median_Elapsed_Hours_Recomputed": x.median(),
                "Std_Elapsed_Hours_Recomputed": x.std(ddof=1) if n_valid > 1 else np.nan,
                "Min_Elapsed_Hours_Recomputed": x.min(),
                "P90_Elapsed_Hours_Recomputed": x.quantile(0.90),
                "Max_Elapsed_Hours_Recomputed": x.max(),
                "IQR_Elapsed_Hours": iqr,
                "IQR_Lower_Screen_Hours": lower,
                "IQR_Upper_Screen_Hours": upper,
                "IQR_Screen_Outlier_Count": outlier_count,
                "IQR_Screen_Outlier_Percent": outlier_pct,
            }
        else:
            stats = {k: np.nan for k in [
                "Mean_Elapsed_Hours_Recomputed", "Median_Elapsed_Hours_Recomputed",
                "Std_Elapsed_Hours_Recomputed", "Min_Elapsed_Hours_Recomputed",
                "P90_Elapsed_Hours_Recomputed", "Max_Elapsed_Hours_Recomputed",
                "IQR_Elapsed_Hours", "IQR_Lower_Screen_Hours",
                "IQR_Upper_Screen_Hours", "IQR_Screen_Outlier_Count",
                "IQR_Screen_Outlier_Percent"
            ]}
            outlier_count = 0

        tier = evidence_tier(n_valid, n_vessels, largest_share)
        p = params[
            (params["_origin"] == origin) & (params["_destination"] == destination)
        ].iloc[0]

        rows.append({
            "Previous_Port": origin,
            "Next_Port": destination,
            "Transition_Record_Count": n_records,
            "Valid_Elapsed_Record_Count": n_valid,
            "Invalid_Elapsed_Record_Count": n_invalid,
            "Distinct_Vessel_Count": n_vessels,
            "Largest_Vessel_Record_Count": int(vessel_counts.iloc[0]) if len(vessel_counts) else 0,
            "Largest_Vessel_Share": largest_share,
            "Vessel_Concentration_HHI": hhi,
            "Vessel_Concentration_Interpretation": (
                "HIGH_SINGLE_VESSEL_CONCENTRATION" if pd.notna(largest_share) and largest_share > 0.50
                else "MODERATE_OR_DISTRIBUTED" if pd.notna(largest_share)
                else "NOT_ASSESSABLE"
            ),
            **stats,
            "Evidence_Strength_Tier_62": tier,
            "Resampling_Approval": "NOT_GRANTED_BY_SCRIPT_62",
            "Elapsed_Time_Interpretation": (
                "Departure-to-next-arrival elapsed time; includes sailing, waiting "
                "and unobserved operations; not pure sailing time."
            ),
            "Script19_Parameter_Sample_Size": int(p["sample_size"]),
            "Script19_Parameter_Source": p.get("Parameter_Source", ""),
        })

        for imo, count in vessel_counts.items():
            vessel_rows.append({
                "Previous_Port": origin,
                "Next_Port": destination,
                "IMO_Normalised": imo,
                "Transition_Record_Count_For_Vessel": int(count),
                "Share_Of_Valid_Edge_Observations": float(count / vessel_counts.sum()),
            })

    register = pd.DataFrame(rows).sort_values(
        ["Transition_Record_Count", "Previous_Port", "Next_Port"],
        ascending=[False, True, True]
    )

    # Compare independently recomputed edge statistics against Script 19 parameters.
    reconciliation = register[[
        "Previous_Port", "Next_Port", "Valid_Elapsed_Record_Count",
        "Mean_Elapsed_Hours_Recomputed", "Median_Elapsed_Hours_Recomputed",
        "Std_Elapsed_Hours_Recomputed", "Min_Elapsed_Hours_Recomputed",
        "Max_Elapsed_Hours_Recomputed", "P90_Elapsed_Hours_Recomputed"
    ]].merge(
        params[[
            "Previous_Port", "Next_Port", "sample_size", "mean_elapsed_hours",
            "median_elapsed_hours", "std_elapsed_hours", "min_elapsed_hours",
            "max_elapsed_hours", "p90_elapsed_hours"
        ]],
        on=["Previous_Port", "Next_Port"], how="left", validate="one_to_one"
    )
    reconciliation["Sample_Size_Match"] = (
        reconciliation["Valid_Elapsed_Record_Count"] == reconciliation["sample_size"]
    )
    metric_pairs = [
        ("Mean_Elapsed_Hours_Recomputed", "mean_elapsed_hours", "Mean"),
        ("Median_Elapsed_Hours_Recomputed", "median_elapsed_hours", "Median"),
        ("Std_Elapsed_Hours_Recomputed", "std_elapsed_hours", "Std"),
        ("Min_Elapsed_Hours_Recomputed", "min_elapsed_hours", "Min"),
        ("Max_Elapsed_Hours_Recomputed", "max_elapsed_hours", "Max"),
        ("P90_Elapsed_Hours_Recomputed", "p90_elapsed_hours", "P90"),
    ]
    for recomputed, stored, label in metric_pairs:
        reconciliation[f"{label}_Absolute_Difference"] = (
            reconciliation[recomputed] - reconciliation[stored]
        ).abs()
    diff_cols = [f"{label}_Absolute_Difference" for _, _, label in metric_pairs]
    reconciliation["All_Stored_Statistics_Match_Within_0_02h"] = (
        reconciliation[diff_cols].fillna(0).le(0.02).all(axis=1)
    )
    reconciliation["Reconciliation_Status"] = np.where(
        reconciliation["Sample_Size_Match"]
        & reconciliation["All_Stored_Statistics_Match_Within_0_02h"],
        "PASS",
        "REVIEW_REQUIRED"
    )

    tier_summary = (
        register.groupby("Evidence_Strength_Tier_62", dropna=False)
        .agg(
            Directed_Edge_Count=("Previous_Port", "size"),
            Total_Valid_Transition_Records=("Valid_Elapsed_Record_Count", "sum"),
            Median_Distinct_Vessel_Count=("Distinct_Vessel_Count", "median"),
        )
        .reset_index()
    )

    # Add explicit non-inferential guardrails.
    tier_summary["Tier_Is_Automatic_Resampling_Approval"] = False
    tier_summary["Tier_Is_Route_Validation"] = False

    register.to_csv(OUT_REGISTER, index=False)
    pd.DataFrame(vessel_rows).to_csv(OUT_VESSEL, index=False)
    reconciliation.to_csv(OUT_RECON, index=False)
    tier_summary.to_csv(OUT_SUMMARY, index=False)

    tier_counts = register["Evidence_Strength_Tier_62"].value_counts().to_dict()
    recon_pass = int(reconciliation["Reconciliation_Status"].eq("PASS").sum())
    recon_fail = int(reconciliation["Reconciliation_Status"].ne("PASS").sum())
    one_vessel_edges = int((register["Distinct_Vessel_Count"] <= 1).sum())
    high_concentration_edges = int(
        (register["Largest_Vessel_Share"] > 0.50).sum()
    )
    sparse_edges = int(
        register["Evidence_Strength_Tier_62"].isin(
            ["SPARSE_EVIDENCE", "SINGLE_OBSERVATION_ONLY"]
        ).sum()
    )

    with OUT_REPORT.open("w", encoding="utf-8") as f:
        f.write("=" * 88 + "\n")
        f.write("SCRIPT 62: NETWORK EVIDENCE STRENGTH AND PARAMETER RELIABILITY AUDIT\n")
        f.write("=" * 88 + "\n\n")
        f.write("SOURCE COUNTS\n")
        f.write(f"- Network directed edges: {len(edges)}\n")
        f.write(f"- Observed transition records: {len(transitions)}\n")
        f.write(f"- Script 19 inter-port parameter rows: {len(params)}\n")
        f.write(f"- Directed pairs audited: {len(register)}\n\n")
        f.write("EVIDENCE TIERS (SCREENING ONLY)\n")
        for tier, count in tier_counts.items():
            f.write(f"- {tier}: {count} edges\n")
        f.write("\nVESSEL DIVERSITY AND CONCENTRATION\n")
        f.write(f"- Edges with <=1 distinct vessel: {one_vessel_edges}\n")
        f.write(f"- Edges where largest vessel contributes >50%: {high_concentration_edges}\n")
        f.write(f"- Sparse or single-observation edges: {sparse_edges}\n")
        f.write("\nPARAMETER RECONCILIATION\n")
        f.write(f"- Rows passing sample/statistic reconciliation: {recon_pass}\n")
        f.write(f"- Rows requiring review: {recon_fail}\n")
        f.write("\nINTERPRETATION\n")
        f.write(
            "Evidence tiers are descriptive screens based on valid observation count, "
            "distinct vessel count and largest-vessel share. They do not reproduce or "
            "replace Script 24's parameter suitability decisions and do not authorize "
            "empirical resampling. IQR flags are investigation prompts, not grounds for "
            "automatic deletion. Repeated observations from the same vessel are not "
            "independent vessel replications. Elapsed time is departure-to-next-arrival "
            "time and includes sailing, waiting and unobserved operations; it is not "
            "pure sailing time. No route, port capacity, coordinate or Hormuz transit "
            "validation is performed.\n"
        )
        f.write("\nOVERALL PARAMETER RECONCILIATION: ")
        f.write("PASS\n" if recon_fail == 0 else "REVIEW REQUIRED\n")

    print("=" * 88)
    print("SCRIPT 62: NETWORK EVIDENCE STRENGTH AND PARAMETER RELIABILITY AUDIT")
    print("=" * 88)
    print(f"Directed edges audited: {len(register)}")
    print(f"Observed transition records: {len(transitions)}")
    print("\nEvidence tier counts:")
    print(register["Evidence_Strength_Tier_62"].value_counts().to_string())
    print("\nKey diagnostics:")
    print(f"Edges with <=1 distinct vessel: {one_vessel_edges}")
    print(f"Edges with largest-vessel share >50%: {high_concentration_edges}")
    print(f"Parameter reconciliations passing: {recon_pass}/{len(reconciliation)}")
    print(f"Parameter reconciliations requiring review: {recon_fail}")
    print("\nOutputs:")
    for path in [OUT_REGISTER, OUT_VESSEL, OUT_RECON, OUT_SUMMARY, OUT_REPORT]:
        print(path.relative_to(ROOT))
    print("\nSOURCE FILES MODIFIED: NO")
    print("RESAMPLING APPROVALS GRANTED: NO")
    print("SCRIPT 62 COMPLETED")


if __name__ == "__main__":
    main()
