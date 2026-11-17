"""
SCRIPT 65: RESEARCHER-GUIDED PARAMETER SELECTION AND SCENARIO DESIGN
===================================================================
Builds a transparent parameter-option register and scenario-design framework
from the completed Script 64 evidence assignment and original Script 19
inter-port elapsed-time parameters.

This script is a planning and decision-support step. It does NOT:
- choose final simulation parameter values;
- fit or select a probability distribution;
- approve empirical resampling;
- convert inter-port elapsed time into pure sailing time;
- change Script 19 inputs or any upstream source;
- approve route feasibility, Hormuz transit, or port operational inclusion.

Required inputs:
    outputs/tables/64_evidence_based_parameter_assignment_register.csv
    data/simulation_inputs/19_interport_time_parameters.csv
    outputs/tables/63_vessel_cluster_bootstrap_uncertainty.csv
    outputs/tables/63_leave_one_vessel_out_sensitivity.csv

Outputs:
    outputs/tables/65_parameter_option_register.csv
    outputs/tables/65_scenario_design_framework.csv
    outputs/tables/65_researcher_parameter_decision_log.csv
    outputs/tables/65_parameter_selection_readiness_checks.csv
    outputs/reports/65_researcher_guided_parameter_scenario_design_report.txt
"""

from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
SIM_INPUTS = ROOT / "data" / "simulation_inputs"
REPORTS = ROOT / "outputs" / "reports"

FILES = {
    "s64": TABLES / "64_evidence_based_parameter_assignment_register.csv",
    "s19": SIM_INPUTS / "19_interport_time_parameters.csv",
    "bootstrap": TABLES / "63_vessel_cluster_bootstrap_uncertainty.csv",
    "loo": TABLES / "63_leave_one_vessel_out_sensitivity.csv",
}

OUT_OPTIONS = TABLES / "65_parameter_option_register.csv"
OUT_SCENARIOS = TABLES / "65_scenario_design_framework.csv"
OUT_DECISIONS = TABLES / "65_researcher_parameter_decision_log.csv"
OUT_CHECKS = TABLES / "65_parameter_selection_readiness_checks.csv"
OUT_REPORT = REPORTS / "65_researcher_guided_parameter_scenario_design_report.txt"

KEY = ["Previous_Port", "Next_Port"]


def pair_key(df, require_unique=True):
    out = df.copy()
    out["_origin"] = out["Previous_Port"].astype("string").str.strip().str.upper()
    out["_destination"] = out["Next_Port"].astype("string").str.strip().str.upper()
    if require_unique and out.duplicated(["_origin", "_destination"]).any():
        raise ValueError("Duplicate directed-pair key detected.")
    return out


def require_columns(df, cols, label):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def safe_bool(value):
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes"}


def evidence_treatment(row):
    cls = str(row["Assignment_Classification_64"])
    if cls == "ASSUMPTION_REQUIRED_NO_EMPIRICAL_PARAMETER_ASSIGNMENT":
        return (
            "EXPLICIT_ASSUMPTION_REQUIRED",
            "No empirical parameter assignment. Researcher must define and justify a scenario value or range."
        )
    if cls == "DESCRIPTIVE_ONLY_NOT_FOR_EMPIRICAL_RESAMPLING":
        return (
            "DESCRIPTIVE_REFERENCE_ONLY",
            "Observed statistics may be reported as context; do not use this edge as an empirical random-time generator."
        )
    if cls == "LIMITED_EMPIRICAL_SUMMARY_WITH_SENSITIVITY_ONLY":
        return (
            "SUMMARY_BASED_SENSITIVITY_CANDIDATE",
            "Consider a small, explicitly justified sensitivity set informed by descriptive statistics; do not claim a fitted distribution."
        )
    if cls == "EMPIRICAL_TAIL_OR_ROBUST_REPRESENTATION_CANDIDATE":
        return (
            "TAIL_STRESS_SCENARIO_CANDIDATE",
            "Observed upper quantiles and maxima may inform stress-test design; tail representation remains a researcher decision and not an approved resampling method."
        )
    if cls == "EMPIRICAL_DISTRIBUTION_CANDIDATE_WITH_CLUSTER_UNCERTAINTY":
        return (
            "CLUSTER_UNCERTAINTY_SCENARIO_CANDIDATE",
            "Consider vessel-cluster uncertainty in scenario design; bootstrap intervals are exploratory and do not establish population representativeness."
        )
    return (
        "MANUAL_REVIEW_REQUIRED",
        "Classification not recognized; researcher review required."
    )


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    for name, path in FILES.items():
        if not path.exists():
            raise FileNotFoundError(f"Required {name} input not found: {path}")

    s64 = pd.read_csv(FILES["s64"])
    s19 = pd.read_csv(FILES["s19"])
    boot = pd.read_csv(FILES["bootstrap"])
    loo = pd.read_csv(FILES["loo"])

    require_columns(s64, KEY + [
        "Assignment_Classification_64", "Assignment_Rationale_64",
        "Valid_Elapsed_Record_Count", "Distinct_Vessel_Count",
        "Mean_Elapsed_Hours_Recomputed", "Median_Elapsed_Hours_Recomputed",
        "P90_Elapsed_Hours_Recomputed", "Max_Elapsed_Hours_Recomputed",
        "Distribution_Representation_Class_63",
        "Mean_Bootstrap_CI95_Lower_Hours", "Mean_Bootstrap_CI95_Upper_Hours",
        "Median_Bootstrap_CI95_Lower_Hours", "Median_Bootstrap_CI95_Upper_Hours",
        "P90_Bootstrap_CI95_Lower_Hours", "P90_Bootstrap_CI95_Upper_Hours",
        "Empirical_Resampling_Approved_64", "Parametric_Distribution_Approved_64",
        "Simulation_Input_Change_Approved_64", "Elapsed_Time_Is_Pure_Sailing_Time",
        "Source_Join_Status_64"
    ], "Script 64 register")
    require_columns(s19, KEY + [
        "sample_size", "mean_elapsed_hours", "median_elapsed_hours",
        "std_elapsed_hours", "min_elapsed_hours", "max_elapsed_hours",
        "p90_elapsed_hours", "Parameter_Source", "Interpretation"
    ], "Script 19 inter-port parameters")
    require_columns(boot, KEY + [
        "Distinct_Vessel_Clusters", "Bootstrap_Replicates", "Bootstrap_Unit",
        "Mean_Bootstrap_CI95_Lower_Hours", "Mean_Bootstrap_CI95_Upper_Hours",
        "Median_Bootstrap_CI95_Lower_Hours", "Median_Bootstrap_CI95_Upper_Hours",
        "P90_Bootstrap_CI95_Lower_Hours", "P90_Bootstrap_CI95_Upper_Hours",
        "Interpretation"
    ], "Script 63 bootstrap")
    require_columns(loo, KEY + [
        "Omitted_IMO", "Remaining_Record_Count", "Remaining_Vessel_Count",
        "LOO_Mean_Absolute_Change_Hours", "LOO_Median_Absolute_Change_Hours",
        "LOO_P90_Absolute_Change_Hours"
    ], "Script 63 leave-one-vessel-out")

    s64k = pair_key(s64, require_unique=True)
    s19k = pair_key(s19, require_unique=True)
    bootk = pair_key(boot, require_unique=True)
    look = pair_key(loo, require_unique=False)
    if len(s64k) != 53 or len(s19k) != 53:
        raise ValueError(f"Expected 53 Script64 and Script19 directed pairs; got {len(s64k)} and {len(s19k)}.")
    s64pairs = set(zip(s64k["_origin"], s64k["_destination"]))
    s19pairs = set(zip(s19k["_origin"], s19k["_destination"]))
    if s64pairs != s19pairs:
        raise ValueError("Script 64 and Script 19 directed-pair sets do not match.")

    # One-to-one join of the 53-edge master register to the original Script 19 parameters.
    s19_fields = [
        "sample_size", "mean_elapsed_hours", "median_elapsed_hours",
        "std_elapsed_hours", "min_elapsed_hours", "max_elapsed_hours",
        "p90_elapsed_hours", "Parameter_Source", "Interpretation"
    ]
    options = s64k.merge(
        s19k[["_origin", "_destination"] + s19_fields],
        on=["_origin", "_destination"], how="left", validate="one_to_one",
        suffixes=("", "_Script19"), indicator="_s19_join"
    )
    options["Script19_Parameter_Join_Status_65"] = np.where(
        options["_s19_join"].eq("both"), "MATCHED", "MISSING"
    )
    options = options.drop(columns=["_s19_join"])

    # Summarize sensitivity diagnostics without interpreting them as approvals.
    loo_summary = look.groupby(["_origin", "_destination"]).agg(
        LOO_Vessel_Exclusions_65=("Omitted_IMO", "nunique"),
        LOO_Max_Mean_Change_Hours_65=("LOO_Mean_Absolute_Change_Hours", "max"),
        LOO_Max_Median_Change_Hours_65=("LOO_Median_Absolute_Change_Hours", "max"),
        LOO_Max_P90_Change_Hours_65=("LOO_P90_Absolute_Change_Hours", "max"),
        LOO_Min_Remaining_Vessel_Count_65=("Remaining_Vessel_Count", "min")
    ).reset_index()
    options = options.merge(
        loo_summary, on=["_origin", "_destination"], how="left", validate="one_to_one"
    )

    boot_fields = [
        "Distinct_Vessel_Clusters", "Bootstrap_Replicates", "Bootstrap_Unit",
        "Mean_Bootstrap_CI95_Lower_Hours", "Mean_Bootstrap_CI95_Upper_Hours",
        "Median_Bootstrap_CI95_Lower_Hours", "Median_Bootstrap_CI95_Upper_Hours",
        "P90_Bootstrap_CI95_Lower_Hours", "P90_Bootstrap_CI95_Upper_Hours",
        "Interpretation"
    ]
    boot_join = bootk[["_origin", "_destination"] + boot_fields].rename(
        columns={c: f"{c}_Bootstrap63" for c in boot_fields}
    )
    options = options.merge(
        boot_join, on=["_origin", "_destination"], how="left",
        validate="one_to_one", indicator="_boot_join"
    )
    options["Bootstrap_Evidence_Available_65"] = options["_boot_join"].eq("both")
    options = options.drop(columns=["_boot_join"])

    treatment = options.apply(evidence_treatment, axis=1)
    options["Parameter_Treatment_65"] = [x[0] for x in treatment]
    options["Researcher_Guidance_65"] = [x[1] for x in treatment]

    # Make explicit which observed summaries can be used as references.
    options["Observed_Median_Reference_Hours_65"] = options["Median_Elapsed_Hours_Recomputed"]
    options["Observed_P90_Reference_Hours_65"] = options["P90_Elapsed_Hours_Recomputed"]
    options["Observed_Max_Reference_Hours_65"] = options["Max_Elapsed_Hours_Recomputed"]
    options["Median_Reference_Use_65"] = np.where(
        options["Parameter_Treatment_65"].eq("EXPLICIT_ASSUMPTION_REQUIRED"),
        "NOT_AVAILABLE_AS_EMPIRICAL_PARAMETER",
        "DESCRIPTIVE_REFERENCE_ONLY_UNLESS_RESEARCHER_APPROVES"
    )
    options["P90_Reference_Use_65"] = np.where(
        options["Parameter_Treatment_65"].isin([
            "TAIL_STRESS_SCENARIO_CANDIDATE",
            "CLUSTER_UNCERTAINTY_SCENARIO_CANDIDATE"
        ]),
        "POTENTIAL_STRESS_REFERENCE_NOT_A_SELECTED_PARAMETER",
        "DESCRIPTIVE_REFERENCE_ONLY"
    )
    options["Final_Selected_Value_Hours_65"] = np.nan
    options["Final_Selected_Method_65"] = "NOT_SELECTED"
    options["Researcher_Decision_Status_65"] = "PENDING_RESEARCHER_REVIEW"
    options["Researcher_Justification_65"] = ""
    options["Empirical_Resampling_Approved_65"] = False
    options["Parametric_Distribution_Approved_65"] = False
    options["Script19_Inputs_Modified_65"] = False

    # Scenario templates are intentionally methodological, not numerical prescriptions.
    scenario_rows = [
        {
            "Scenario_ID_65": "S65-BASE",
            "Scenario_Name_65": "Historical-reference baseline",
            "Purpose_65": "Establish a reference case using the existing historical replay framework.",
            "Parameter_Basis_65": "Existing Script19 parameters retained unchanged",
            "Treatment_65": "No new parameter selection in Script65",
            "Required_Researcher_Decision_65": "Confirm baseline definition and state its observational limitations",
            "Numerical_Value_Status_65": "NOT_ASSIGNED",
            "Interpretation_Guardrail_65": "Historical inter-port elapsed times are not pure sailing times and do not establish Hormuz transit."
        },
        {
            "Scenario_ID_65": "S65-CENTRAL",
            "Scenario_Name_65": "Central sensitivity case",
            "Purpose_65": "Explore a central alternative where evidence permits descriptive summary-based sensitivity.",
            "Parameter_Basis_65": "Researcher-selected summary reference, potentially median; edge-specific eligibility applies",
            "Treatment_65": "Sensitivity only; no distribution fitting or automatic resampling",
            "Required_Researcher_Decision_65": "Select eligible edges, value, rationale and whether the value represents elapsed time or another component",
            "Numerical_Value_Status_65": "NOT_ASSIGNED",
            "Interpretation_Guardrail_65": "Do not use descriptive-only or assumption-required edges as empirically generated random times."
        },
        {
            "Scenario_ID_65": "S65-UPPER",
            "Scenario_Name_65": "Upper-tail stress case",
            "Purpose_65": "Test resilience to elevated inter-port elapsed-time conditions.",
            "Parameter_Basis_65": "Observed P90 / P95 / maximum references where available and suitable",
            "Treatment_65": "Stress-test reference only; no claim that observed quantile is a forecast",
            "Required_Researcher_Decision_65": "Choose stress statistic and eligible edges; document whether stress is deterministic or stochastic",
            "Numerical_Value_Status_65": "NOT_ASSIGNED",
            "Interpretation_Guardrail_65": "Tail statistics can be unstable and may reflect waiting or unobserved operations as well as sailing."
        },
        {
            "Scenario_ID_65": "S65-UNCERTAINTY",
            "Scenario_Name_65": "Vessel-cluster uncertainty case",
            "Purpose_65": "Reflect uncertainty from a limited number of observed vessels.",
            "Parameter_Basis_65": "Script63 vessel-cluster bootstrap intervals and leave-one-vessel-out diagnostics",
            "Treatment_65": "Exploratory uncertainty envelope, only for edges with diagnostics",
            "Required_Researcher_Decision_65": "Decide how uncertainty enters the experiment and acknowledge cluster-count limitations",
            "Numerical_Value_Status_65": "NOT_ASSIGNED",
            "Interpretation_Guardrail_65": "Bootstrap intervals do not establish population representativeness or authorize resampling."
        },
        {
            "Scenario_ID_65": "S65-ASSUMPTION",
            "Scenario_Name_65": "Explicit assumption stress case",
            "Purpose_65": "Represent edges for which empirical evidence is inadequate for parameter assignment.",
            "Parameter_Basis_65": "Transparent researcher-defined assumptions and sensitivity bounds",
            "Treatment_65": "Assumption-based; source and rationale must be documented",
            "Required_Researcher_Decision_65": "Specify value/range, rationale, plausible bounds and sensitivity plan",
            "Numerical_Value_Status_65": "NOT_ASSIGNED",
            "Interpretation_Guardrail_65": "Never present an assumed value as observed or empirically validated."
        }
    ]
    scenarios = pd.DataFrame(scenario_rows)

    # One decision-log row per edge; blank fields are deliberate researcher inputs.
    decisions = options[KEY + [
        "Assignment_Classification_64", "Parameter_Treatment_65",
        "Valid_Elapsed_Record_Count", "Distinct_Vessel_Count",
        "Observed_Median_Reference_Hours_65", "Observed_P90_Reference_Hours_65",
        "Observed_Max_Reference_Hours_65", "Bootstrap_Evidence_Available_65"
    ]].copy()
    for col in [
        "Researcher_Selected_Scenario_ID", "Researcher_Selected_Value_Hours",
        "Researcher_Selected_Method", "Assumption_Lower_Bound_Hours",
        "Assumption_Upper_Bound_Hours", "Researcher_Justification",
        "Supervisor_Review_Status", "Supervisor_Comments"
    ]:
        decisions[col] = ""
    decisions["Decision_Status"] = "PENDING"
    decisions["Approval_Granted_By_Script65"] = False

    checks = []
    def add_check(name, passed, observed, expected):
        checks.append({
            "Check": name, "Passed": bool(passed),
            "Observed": str(observed), "Expected": str(expected)
        })

    add_check("Script64 edge count", len(s64k) == 53, len(s64k), 53)
    add_check("Script19 edge count", len(s19k) == 53, len(s19k), 53)
    add_check("Script64 and Script19 pair sets match", s64pairs == s19pairs,
              len(s64pairs.intersection(s19pairs)), 53)
    add_check("All Script19 parameters joined", options["Script19_Parameter_Join_Status_65"].eq("MATCHED").all(),
              int(options["Script19_Parameter_Join_Status_65"].eq("MATCHED").sum()), 53)
    add_check("No source join gaps in Script64", options["Source_Join_Status_64"].eq("ALL_THREE_ASSESSMENTS_MATCHED").all(),
              int(options["Source_Join_Status_64"].eq("ALL_THREE_ASSESSMENTS_MATCHED").sum()), 53)
    add_check("No empirical resampling approvals", not options["Empirical_Resampling_Approved_64"].map(safe_bool).any(),
              int(options["Empirical_Resampling_Approved_64"].map(safe_bool).sum()), 0)
    add_check("No parametric fitting approvals", not options["Parametric_Distribution_Approved_64"].map(safe_bool).any(),
              int(options["Parametric_Distribution_Approved_64"].map(safe_bool).sum()), 0)
    add_check("No selected values assigned", options["Final_Selected_Value_Hours_65"].isna().all(),
              int(options["Final_Selected_Value_Hours_65"].notna().sum()), 0)
    add_check("No Script19 input modifications", not options["Script19_Inputs_Modified_65"].any(),
              int(options["Script19_Inputs_Modified_65"].sum()), 0)
    add_check("Decision log has one row per edge", len(decisions) == 53, len(decisions), 53)

    check_df = pd.DataFrame(checks)
    if not check_df["Passed"].all():
        raise ValueError("One or more Script65 readiness checks failed. No outputs written.")

    # Retain normalized helper keys only for internal joins; exclude from deliverables.
    options = options.drop(columns=["_origin", "_destination"])
    decisions.to_csv(OUT_DECISIONS, index=False)
    options.to_csv(OUT_OPTIONS, index=False)
    scenarios.to_csv(OUT_SCENARIOS, index=False)
    check_df.to_csv(OUT_CHECKS, index=False)

    with OUT_REPORT.open("w", encoding="utf-8") as f:
        f.write("=" * 92 + "\n")
        f.write("SCRIPT 65: RESEARCHER-GUIDED PARAMETER SELECTION AND SCENARIO DESIGN\n")
        f.write("=" * 92 + "\n\n")
        f.write(f"Script64 directed edges: {len(s64k)}\n")
        f.write(f"Script19 parameter edges: {len(s19k)}\n")
        f.write(f"Script63 bootstrap-supported edges: {int(options['Bootstrap_Evidence_Available_65'].sum())}\n")
        f.write(f"Scenario templates created: {len(scenarios)}\n")
        f.write(f"Researcher decision-log rows: {len(decisions)}\n\n")
        f.write("PARAMETER TREATMENT COUNTS\n")
        f.write(options["Parameter_Treatment_65"].value_counts().to_string())
        f.write("\n\nREADINESS CHECKS\n")
        f.write(check_df.to_string(index=False))
        f.write("\n\nRESEARCH GUARDRAILS\n")
        f.write(
            "No final parameter values or methods were selected. No probability distribution "
            "was fitted. No empirical resampling was approved. Script19 inputs were not changed. "
            "Observed departure-to-next-arrival elapsed time includes sailing, waiting and "
            "unobserved operations and is not pure sailing time. Cluster-bootstrap intervals "
            "are exploratory and do not establish population representativeness. Scenario "
            "templates are design prompts, not calibrated disruption magnitudes or operational "
            "forecasts. No Hormuz transit, route feasibility, coordinate or port inclusion "
            "approval is made by this script.\n"
        )
        f.write("\nSOURCE FILES MODIFIED: NO\n")
        f.write("SCRIPT19 SIMULATION INPUTS MODIFIED: NO\n")
        f.write("FINAL PARAMETER VALUES SELECTED: NONE\n")
        f.write("EMPIRICAL RESAMPLING APPROVALS: NONE\n")

    print("=" * 92)
    print("SCRIPT 65: RESEARCHER-GUIDED PARAMETER SELECTION AND SCENARIO DESIGN")
    print("=" * 92)
    print(f"Integrated edges: {len(options)}")
    print(f"Scenario templates: {len(scenarios)}")
    print(f"Researcher decision rows: {len(decisions)}")
    print("\nParameter treatment counts:")
    print(options["Parameter_Treatment_65"].value_counts().to_string())
    print("\nReadiness checks:")
    print(f"{int(check_df['Passed'].sum())}/{len(check_df)} passed")
    print("\nOutputs:")
    for path in [OUT_OPTIONS, OUT_SCENARIOS, OUT_DECISIONS, OUT_CHECKS, OUT_REPORT]:
        print(path.relative_to(ROOT))
    print("\nFINAL PARAMETER VALUES SELECTED: NONE")
    print("SCRIPT19 INPUTS MODIFIED: NO")
    print("SCRIPT 65 COMPLETED")


if __name__ == "__main__":
    main()
