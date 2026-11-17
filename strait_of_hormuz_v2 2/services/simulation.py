from pathlib import Path
import pandas as pd

POLICIES = {
    "R76-00-NONE": "No recovery",
    "R76-01-FIXED-6H": "Fixed 6h",
    "R76-02-FIXED-12H": "Fixed 12h",
    "R76-03-PROP-25-CAP6": "Proportional 25%, cap 6h",
    "R76-04-PROP-50-CAP12": "Proportional 50%, cap 12h",
}

def _project_root(root: Path) -> Path:
    """Accept either the V2 app directory or the research project directory."""
    root = Path(root).resolve()
    if (root / "outputs" / "tables").exists():
        return root
    if (root.parent / "outputs" / "tables").exists():
        return root.parent
    return root

def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)

def load_primary(root: Path) -> pd.DataFrame:
    """Load canonical Script 98 scenario-policy results from the original project."""
    project = _project_root(root)
    path = project / "outputs" / "tables" / "98_final_scenario_policy_results.csv"
    df = _read_csv(path)
    if df.empty:
        return df

    rename = {
        "Scenario_ID": "scenario_id",
        "Recovery_Policy_ID": "policy_id",
        "Recovery_Policy": "policy_name",
        "Shock_Magnitude_Hours": "shock_hours",
        "Affected_Transition_Share": "share",
        "M01_Mean_Incremental_Arrival_Delay_Hours": "m01_mean_incremental_arrival_delay_h",
        "M02_Mean_Incremental_Departure_Delay_Hours": "mean_delay",
        "M03A_Max_Final_Represented_Call_Departure_Delay_Hours": "m03a_max_final_call_departure_delay_h",
        "M03B_Max_Accumulated_Signed_Departure_Delay_Per_Vessel_Hours": "m03b_max_accumulated_signed_vessel_delay_h",
        "M04_Mean_Final_Represented_Call_Departure_Delay_Hours": "m04_mean_final_call_departure_delay_h",
        "M05_P90_Incremental_Call_Departure_Delay_Hours": "p90_delay",
        "M06_Total_Paired_Recovery_Benefit_Hours": "m06_total_paired_recovery_benefit_h",
        "M06_Mean_Paired_Recovery_Benefit_Per_Call_Hours": "m06_mean_paired_recovery_benefit_per_call_h",
        "Applied_Recovery_Credit_Total_Hours": "applied_recovery_credit_total_h",
        "M07A_Unrecovered_Call_Count": "unrecovered_calls",
        "M07B_Unrecovered_Vessel_Count": "unrecovered_vessels",
        "Censored_Represented_Calls_At_Horizon": "censored_calls",
        "Censored_Vessels_At_Horizon": "censored_vessels",
        "Call_Count": "call_count",
        "Vessel_Count": "vessel_count",
    }
    df = df.rename(columns=rename)
    if "policy_name" not in df.columns and "policy_id" in df.columns:
        df["policy_name"] = df["policy_id"].map(POLICIES).fillna(df["policy_id"])
    else:
        df["policy_name"] = df["policy_name"].fillna(df["policy_id"].map(POLICIES))
    numeric = [
        "shock_hours", "share", "mean_delay", "p90_delay", "unrecovered_calls",
        "unrecovered_vessels", "m06_total_paired_recovery_benefit_h",
        "m06_mean_paired_recovery_benefit_per_call_h", "call_count", "vessel_count",
    ]
    for col in numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    required = {"scenario_id", "policy_id", "policy_name", "shock_hours", "share", "mean_delay"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Script 98 scenario-policy file is missing required columns: {sorted(missing)}")
    return df

def load_call_level(root: Path) -> pd.DataFrame:
    project = _project_root(root)
    path = project / "outputs" / "tables" / "98_final_call_level_paired_results.csv"
    df = _read_csv(path)
    if df.empty:
        return df
    rename = {
        "Scenario_ID": "scenario_id",
        "Recovery_Policy_ID": "policy_id",
        "Simulation_Record_ID": "simulation_record_id",
        "IMO_Normalised": "imo_normalised",
        "Vessel_Call_Sequence_Number": "vessel_call_sequence_number",
        "Affected_Transition": "affected_transition",
        "Transit_Elapsed_Time_Shock_Hours": "transit_elapsed_time_shock_h",
        "Incremental_Arrival_Delay_Hours": "incremental_arrival_delay_h",
        "Incremental_Departure_Delay_Hours": "incremental_departure_delay_h",
        "No_Recovery_Incremental_Departure_Delay_Hours": "no_recovery_incremental_departure_delay_h",
        "Paired_Recovery_Benefit_Hours": "paired_recovery_benefit_h",
        "Recovery_Advance_Hours": "recovery_advance_h",
    }
    df = df.rename(columns=rename)
    for col in [
        "incremental_arrival_delay_h", "incremental_departure_delay_h",
        "no_recovery_incremental_departure_delay_h", "paired_recovery_benefit_h",
        "recovery_advance_h", "transit_elapsed_time_shock_h",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "affected_transition" in df.columns:
        df["affected_transition"] = df["affected_transition"].astype(str).str.lower().map(
            {"true": True, "false": False, "1": True, "0": False}
        )
    return df

def load_vessel_level(root: Path) -> pd.DataFrame:
    project = _project_root(root)
    path = project / "outputs" / "tables" / "98_final_vessel_level_results.csv"
    df = _read_csv(path)
    if df.empty:
        return df
    rename = {
        "Scenario_ID": "scenario_id",
        "Recovery_Policy_ID": "policy_id",
        "IMO_Normalised": "imo_normalised",
        "Final_Represented_Call_ID": "final_represented_call_id",
        "Final_Represented_Call_Departure_Delay_Hours": "final_call_departure_delay_h",
        "Accumulated_Signed_Departure_Delay_Hours": "accumulated_signed_departure_delay_h",
        "Unrecovered_Vessel": "unrecovered_vessel",
    }
    df = df.rename(columns=rename)
    for col in ["final_call_departure_delay_h", "accumulated_signed_departure_delay_h"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "unrecovered_vessel" in df.columns:
        df["unrecovered_vessel"] = df["unrecovered_vessel"].astype(str).str.lower().map(
            {"true": True, "false": False, "1": True, "0": False}
        )
    return df

def load_validation(root: Path) -> pd.DataFrame:
    project = _project_root(root)
    path = project / "outputs" / "tables" / "98_final_results_validation_checks.csv"
    return _read_csv(path)

def load_script77_summary(root: Path) -> pd.DataFrame:
    path = Path(root) / "data" / "simulation" / "script77_policy_summary.csv"
    return _read_csv(path)

def scenario_filter(df: pd.DataFrame, shock, share) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    shock_mask = (pd.to_numeric(df["shock_hours"], errors="coerce") - float(shock)).abs() < 1e-9
    share_mask = (pd.to_numeric(df["share"], errors="coerce") - float(share)).abs() < 1e-9
    return df[shock_mask & share_mask].copy()
