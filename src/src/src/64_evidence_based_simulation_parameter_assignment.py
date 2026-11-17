"""
SCRIPT 64: EVIDENCE-BASED SIMULATION PARAMETER ASSIGNMENT REGISTER
==================================================================
Integrates the existing Script 24 parameter-suitability assessment with the
audited Script 62 evidence-strength register and Script 63 distribution/
uncertainty assessment.

This is a decision-support register only. It does NOT:
- alter the 53-edge network;
- approve empirical resampling;
- fit a parametric distribution;
- overwrite Script 19 simulation parameters;
- convert inter-port elapsed time into sailing time.

Required inputs:
    outputs/tables/24_simulation_parameter_suitability.csv
    outputs/tables/62_edge_evidence_reliability_register.csv
    outputs/tables/63_empirical_distribution_assessment.csv

The Script 24 suitability-class column is detected from its actual values. If
the file schema does not contain one unambiguous classification field, the
script stops and reports the available columns rather than guessing.

Outputs:
    outputs/tables/64_evidence_based_parameter_assignment_register.csv
    outputs/tables/64_parameter_assignment_summary.csv
    outputs/tables/64_parameter_assignment_conflicts.csv
    outputs/reports/64_evidence_based_parameter_assignment_report.txt
"""

from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"

S24_FILE = TABLES / "24_simulation_parameter_suitability.csv"
S62_FILE = TABLES / "62_edge_evidence_reliability_register.csv"
S63_FILE = TABLES / "63_empirical_distribution_assessment.csv"

OUT_REGISTER = TABLES / "64_evidence_based_parameter_assignment_register.csv"
OUT_SUMMARY = TABLES / "64_parameter_assignment_summary.csv"
OUT_CONFLICTS = TABLES / "64_parameter_assignment_conflicts.csv"
OUT_REPORT = REPORTS / "64_evidence_based_parameter_assignment_report.txt"

S24_CLASS_VALUES = {
    "EMPIRICAL_RESAMPLING_CANDIDATE",
    "EMPIRICAL_RESAMPLING_WITH_SENSITIVITY",
    "EMPIRICAL_RESAMPLING_WITH_CAUTION",
    "LIMITED_EMPIRICAL_EVIDENCE",
    "DESCRIPTIVE_EVIDENCE_ONLY",
    "ASSUMPTION_REQUIRED",
}


def norm(series):
    return series.astype("string").str.strip().str.upper()


def detect_script24_class_column(df):
    candidates = []
    for col in df.columns:
        vals = set(norm(df[col].dropna()).unique())
        overlap = vals & S24_CLASS_VALUES
        if overlap:
            candidates.append((col, len(overlap), len(vals)))
    if len(candidates) != 1:
        details = "\n".join(
            f"- {c}: recognized classes={n}, distinct non-null values={v}"
            for c, n, v in candidates
        ) or "No column contained the known Script 24 suitability labels."
        raise ValueError(
            "Could not identify exactly one Script 24 suitability-class column.\n"
            f"Detected candidates:\n{details}\n"
            f"Available columns: {list(df.columns)}\n"
            "No outputs were written. Review the actual Script 24 schema."
        )
    return candidates[0][0]


def classify_assignment(row):
    s24 = str(row["Script24_Suitability_Class"]).strip().upper()
    s63 = str(row["Distribution_Representation_Class_63"]).strip().upper()
    n = int(row["Valid_Elapsed_Record_Count"])
    vessels = int(row["Distinct_Vessel_Count"])
    largest_share = row["Largest_Vessel_Share"]
    loo_n = int(row["LOO_Vessel_Count"]) if pd.notna(row["LOO_Vessel_Count"]) else 0
    boot_available = bool(row["Vessel_Cluster_Bootstrap_Available_64"])

    # Preserve the Script 24 decision as the primary parameter-method gate.
    if s24 == "ASSUMPTION_REQUIRED":
        return (
            "ASSUMPTION_REQUIRED_NO_EMPIRICAL_PARAMETER_ASSIGNMENT",
            "Script 24 requires an assumption; later descriptive evidence does not override it."
        )

    if s24 == "DESCRIPTIVE_EVIDENCE_ONLY":
        return (
            "DESCRIPTIVE_ONLY_NOT_FOR_EMPIRICAL_RESAMPLING",
            "Script 24 limits use to descriptive evidence; Script 63 cannot upgrade this gate."
        )

    if s24 == "LIMITED_EMPIRICAL_EVIDENCE":
        return (
            "LIMITED_EMPIRICAL_SUMMARY_WITH_SENSITIVITY_ONLY",
            "Script 24 identifies limited empirical evidence; retain sensitivity analysis and do not infer a stable distribution."
        )

    # These are the only Script 24 classes that can be considered for an
    # empirical distribution candidate, and even then Script 63 can downgrade.
    if s24 in {
        "EMPIRICAL_RESAMPLING_CANDIDATE",
        "EMPIRICAL_RESAMPLING_WITH_SENSITIVITY",
        "EMPIRICAL_RESAMPLING_WITH_CAUTION",
    }:
        if n < 5 or vessels < 3:
            return (
                "INSUFFICIENT_CURRENT_EVIDENCE_ASSUMPTION_OR_SENSITIVITY",
                "Script 24 candidate is downgraded because Script 63 has too few valid records or distinct vessels."
            )
        if s63 == "EMPIRICAL_OR_ROBUST_TAIL_REPRESENTATION_PREFERRED":
            return (
                "EMPIRICAL_TAIL_OR_ROBUST_REPRESENTATION_CANDIDATE",
                "Script 24 permits empirical consideration, but Script 63 indicates skew/tail risk; use only with explicit sensitivity and vessel-cluster uncertainty."
            )
        if s63 == "EMPIRICAL_DISTRIBUTION_CANDIDATE_WITH_VESSEL_CLUSTERING":
            return (
                "EMPIRICAL_DISTRIBUTION_CANDIDATE_WITH_CLUSTER_UNCERTAINTY",
                "Both assessments support cautious empirical consideration; vessel clustering must remain explicit."
            )
        if s63 == "LIMITED_EMPIRICAL_DISTRIBUTION_CANDIDATE":
            return (
                "LIMITED_EMPIRICAL_DISTRIBUTION_CANDIDATE_WITH_SENSITIVITY",
                "Distribution evidence remains limited; empirical use is only a candidate and requires sensitivity analysis."
            )
        if s63 in {
            "DESCRIPTIVE_EMPIRICAL_SUMMARY_ONLY",
            "INSUFFICIENT_FOR_DISTRIBUTION_REPRESENTATION",
        }:
            return (
                "DESCRIPTIVE_OR_ASSUMPTION_BASED_PARAMETER_ONLY",
                "Script 63 does not support distribution representation; do not empirically resample this edge."
            )

    return (
        "MANUAL_RESEARCHER_REVIEW_REQUIRED",
        "The combination of Script 24 and Script 63 classifications is not covered by an automatic assignment rule."
    )


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    for path in [S24_FILE, S62_FILE, S63_FILE]:
        if not path.exists():
            raise FileNotFoundError(f"Required input missing: {path}")

    s24 = pd.read_csv(S24_FILE)
    s62 = pd.read_csv(S62_FILE)
    s63 = pd.read_csv(S63_FILE)

    key_cols = ["Previous_Port", "Next_Port"]
    for label, df in [("Script 24", s24), ("Script 62", s62), ("Script 63", s63)]:
        missing = [c for c in key_cols if c not in df.columns]
        if missing:
            raise ValueError(f"{label} missing directed-pair columns: {missing}")
        df["_origin"] = norm(df["Previous_Port"])
        df["_destination"] = norm(df["Next_Port"])
        if df.duplicated(["_origin", "_destination"]).any():
            raise ValueError(f"{label} contains duplicate directed-pair keys.")

    s24_class_col = detect_script24_class_column(s24)
    s24["Script24_Suitability_Class"] = norm(s24[s24_class_col])

    required62 = [
        "Valid_Elapsed_Record_Count", "Distinct_Vessel_Count",
        "Largest_Vessel_Share", "Evidence_Strength_Tier_62",
    ]
    required63 = [
        "Valid_Transition_Count_63", "Distinct_Vessel_Count_63",
        "Distribution_Representation_Class_63", "LOO_Vessel_Count",
    ]
    for label, df, cols in [
        ("Script 62", s62, required62),
        ("Script 63", s63, required63),
    ]:
        missing = [c for c in cols if c not in df.columns]
        if missing:
            raise ValueError(f"{label} missing required columns: {missing}")

    # Prefix all Script 24 source fields so no information is silently discarded.
    s24_out = s24.drop(columns=key_cols + ["_origin", "_destination"]).copy()
    s24_out = s24_out.add_prefix("S24_")
    s24_out.insert(0, "Next_Port", s24["Next_Port"].astype(str).values)
    s24_out.insert(0, "Previous_Port", s24["Previous_Port"].astype(str).values)

    # Select the audited Script 62/63 fields needed for the assignment decision.
    s62_cols = [
        "Previous_Port", "Next_Port", "Valid_Elapsed_Record_Count",
        "Distinct_Vessel_Count", "Largest_Vessel_Share",
        "Vessel_Concentration_HHI", "Evidence_Strength_Tier_62",
        "IQR_Screen_Outlier_Count", "IQR_Screen_Outlier_Percent",
        "Mean_Elapsed_Hours_Recomputed", "Median_Elapsed_Hours_Recomputed",
        "Std_Elapsed_Hours_Recomputed", "P90_Elapsed_Hours_Recomputed",
        "Max_Elapsed_Hours_Recomputed", "Resampling_Approval",
    ]
    s63_cols = [
        "Previous_Port", "Next_Port", "Distribution_Representation_Class_63",
        "Coefficient_Of_Variation", "Skewness", "P90_to_Median_Ratio",
        "P95_to_Median_Ratio", "Max_LOO_Mean_Change_Hours",
        "Max_LOO_Median_Change_Hours", "Max_LOO_P90_Change_Hours",
        "Mean_Bootstrap_CI95_Lower_Hours", "Mean_Bootstrap_CI95_Upper_Hours",
        "Median_Bootstrap_CI95_Lower_Hours", "Median_Bootstrap_CI95_Upper_Hours",
        "P90_Bootstrap_CI95_Lower_Hours", "P90_Bootstrap_CI95_Upper_Hours",
        "Parametric_Distribution_Fitted", "Automatic_Resampling_Approval",
    ]
    for col in s62_cols + s63_cols:
        if col not in (s62.columns if col in s62.columns else s63.columns):
            raise ValueError(f"Required Script 62/63 field missing: {col}")

    s62_sel = s62[s62_cols].copy()
    s63_sel = s63[s63_cols].copy()
    s62_sel["_origin"] = norm(s62_sel["Previous_Port"])
    s62_sel["_destination"] = norm(s62_sel["Next_Port"])
    s63_sel["_origin"] = norm(s63_sel["Previous_Port"])
    s63_sel["_destination"] = norm(s63_sel["Next_Port"])
    s24_out["_origin"] = norm(s24["Previous_Port"])
    s24_out["_destination"] = norm(s24["Next_Port"])

    merged = s24_out.merge(
        s62_sel.drop(columns=key_cols), on=["_origin", "_destination"],
        how="outer", validate="one_to_one", indicator="_merge62"
    )
    merged = merged.merge(
        s63_sel.drop(columns=key_cols), on=["_origin", "_destination"],
        how="outer", validate="one_to_one", indicator="_merge63"
    )

    merged["Script24_Suitability_Class"] = norm(
        merged["S24_Script24_Suitability_Class"]
    )
    # In case the prefix creates a different field name due to the detected source name,
    # the canonical field above is retained and used for all downstream decisions.
    merged["Vessel_Cluster_Bootstrap_Available_64"] = (
        merged["Mean_Bootstrap_CI95_Lower_Hours"].notna()
        & merged["Mean_Bootstrap_CI95_Upper_Hours"].notna()
    )
    merged["Assignment_Classification_64"] = merged.apply(classify_assignment, axis=1).str[0]
    merged["Assignment_Rationale_64"] = merged.apply(classify_assignment, axis=1).str[1]
    merged["Empirical_Resampling_Approved_64"] = False
    merged["Parametric_Distribution_Approved_64"] = False
    merged["Simulation_Input_Change_Approved_64"] = False
    merged["Elapsed_Time_Is_Pure_Sailing_Time"] = False
    merged["Source_Join_Status_64"] = np.where(
        (merged["_merge62"] == "both") & (merged["_merge63"] == "both"),
        "ALL_THREE_ASSESSMENTS_MATCHED",
        "SOURCE_JOIN_REVIEW_REQUIRED"
    )
    merged = merged.drop(columns=["_merge62", "_merge63", "_origin", "_destination"])

    summary = (
        merged.groupby("Assignment_Classification_64", dropna=False)
        .agg(
            Directed_Edge_Count=("Previous_Port", "size"),
            Median_Valid_Observation_Count=("Valid_Elapsed_Record_Count", "median"),
            Median_Distinct_Vessel_Count=("Distinct_Vessel_Count", "median"),
        )
        .reset_index()
    )
    summary["Empirical_Resampling_Approved"] = False
    summary["Parametric_Distribution_Approved"] = False

    conflicts = merged[
        merged["Source_Join_Status_64"] != "ALL_THREE_ASSESSMENTS_MATCHED"
    ].copy()

    if len(merged) != 53:
        raise ValueError(f"Expected 53 directed pairs after integration; found {len(merged)}.")
    if merged["Source_Join_Status_64"].ne("ALL_THREE_ASSESSMENTS_MATCHED").any():
        raise ValueError("Script 24/62/63 pair join incomplete. Inspect conflict file before proceeding.")

    merged.to_csv(OUT_REGISTER, index=False)
    summary.to_csv(OUT_SUMMARY, index=False)
    conflicts.to_csv(OUT_CONFLICTS, index=False)

    with OUT_REPORT.open("w", encoding="utf-8") as f:
        f.write("=" * 88 + "\n")
        f.write("SCRIPT 64: EVIDENCE-BASED SIMULATION PARAMETER ASSIGNMENT\n")
        f.write("=" * 88 + "\n\n")
        f.write(f"Script 24 class column detected: {s24_class_col}\n")
        f.write(f"Script 24 rows: {len(s24)}\n")
        f.write(f"Script 62 rows: {len(s62)}\n")
        f.write(f"Script 63 rows: {len(s63)}\n")
        f.write(f"Integrated directed pairs: {len(merged)}\n")
        f.write(f"Complete three-source joins: {(merged['Source_Join_Status_64'] == 'ALL_THREE_ASSESSMENTS_MATCHED').sum()}\n\n")
        f.write("ASSIGNMENT CLASSIFICATIONS\n")
        f.write(summary.to_string(index=False))
        f.write("\n\nGUARDRAILS\n")
        f.write(
            "Script 24 is retained as the primary parameter-method suitability gate. "
            "Scripts 62 and 63 can downgrade or qualify its use but cannot silently "
            "upgrade a descriptive-only or assumption-required edge. These assignments "
            "are recommendations for researcher review, not approvals. No empirical "
            "resampling, parametric fitting, simulation input modification, coordinate "
            "approval, operational inclusion or route validation is granted. Inter-port "
            "elapsed time is not pure sailing time.\n"
        )
        f.write("\nSOURCE FILES MODIFIED: NO\n")
        f.write("SIMULATION INPUTS MODIFIED: NO\n")
        f.write("AUTOMATIC RESAMPLING APPROVALS: NONE\n")

    print("=" * 88)
    print("SCRIPT 64: EVIDENCE-BASED SIMULATION PARAMETER ASSIGNMENT")
    print("=" * 88)
    print(f"Script 24 suitability column detected: {s24_class_col}")
    print(f"Integrated directed pairs: {len(merged)}")
    print("\nAssignment classifications:")
    print(merged["Assignment_Classification_64"].value_counts().to_string())
    print("\nAll three source assessments matched: "
          f"{(merged['Source_Join_Status_64'] == 'ALL_THREE_ASSESSMENTS_MATCHED').sum()}/53")
    print("\nOutputs:")
    for p in [OUT_REGISTER, OUT_SUMMARY, OUT_CONFLICTS, OUT_REPORT]:
        print(p.relative_to(ROOT))
    print("\nEMPIRICAL RESAMPLING APPROVALS: NONE")
    print("PARAMETRIC FIT APPROVALS: NONE")
    print("SIMULATION INPUTS MODIFIED: NO")
    print("SCRIPT 64 COMPLETED")


if __name__ == "__main__":
    main()
