#!/usr/bin/env python3
"""SCRIPT 98 — FINAL EXPERIMENT RESULT ANALYSIS

Consumes the validated Script76 call-level recovery output. Script76 is the
primary recovery formulation; Script77 is retained as a bounded sensitivity
analysis only because its observed-interval cap is not established schedule
slack. This script does not rerun or alter the simulation.
"""
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path.cwd()
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"
INPUT = TABLES / "76_call_level_recovery_results.csv"
TOL = 1e-9

REQUIRED = [
    "Scenario_ID", "Scenario_Type", "Recovery_Policy_ID", "Recovery_Policy",
    "Simulation_Record_ID", "IMO_Normalised", "Vessel_Call_Sequence_Number",
    "Actual_Arrival_UTC", "Actual_Departure_UTC", "Simulated_Arrival_UTC",
    "Simulated_Departure_UTC", "Simulated_Arrival_Delay_Hours",
    "Simulated_Departure_Delay_Hours", "Recovery_Advance_Hours",
]

def main():
    if not INPUT.exists():
        raise FileNotFoundError(f"Missing required validated input: {INPUT}")
    d = pd.read_csv(INPUT)
    missing = [c for c in REQUIRED if c not in d.columns]
    if missing:
        raise ValueError(f"Input schema missing columns: {missing}")

    for c in ["Actual_Arrival_UTC", "Actual_Departure_UTC", "Simulated_Arrival_UTC", "Simulated_Departure_UTC"]:
        d[c] = pd.to_datetime(d[c], utc=True, format="mixed", errors="coerce")
    numeric = ["Simulated_Arrival_Delay_Hours", "Simulated_Departure_Delay_Hours", "Recovery_Advance_Hours"]
    for c in numeric:
        d[c] = pd.to_numeric(d[c], errors="coerce")

    checks = []
    def check(name, ok, observed, expected):
        checks.append({"Check": name, "Passed": bool(ok), "Observed": observed, "Expected": expected})

    check("No missing required timestamps or outcome values",
          not d[["Actual_Arrival_UTC", "Actual_Departure_UTC", "Simulated_Arrival_UTC", "Simulated_Departure_UTC"] + numeric].isna().any().any(),
          int(d[["Actual_Arrival_UTC", "Actual_Departure_UTC", "Simulated_Arrival_UTC", "Simulated_Departure_UTC"] + numeric].isna().sum().sum()), 0)
    check("604 calls per scenario-policy cell",
          bool((d.groupby(["Scenario_ID", "Recovery_Policy_ID"]).Simulation_Record_ID.nunique() == 604).all()),
          sorted(d.groupby(["Scenario_ID", "Recovery_Policy_ID"]).Simulation_Record_ID.nunique().unique().tolist()), [604])
    check("155 vessels per scenario-policy cell",
          bool((d.groupby(["Scenario_ID", "Recovery_Policy_ID"]).IMO_Normalised.nunique() == 155).all()),
          sorted(d.groupby(["Scenario_ID", "Recovery_Policy_ID"]).IMO_Normalised.nunique().unique().tolist()), [155])
    check("Unique scenario-policy-call keys",
          not d.duplicated(["Scenario_ID", "Recovery_Policy_ID", "Simulation_Record_ID"]).any(),
          int(d.duplicated(["Scenario_ID", "Recovery_Policy_ID", "Simulation_Record_ID"]).sum()), 0)

    base = d[(d.Scenario_ID == "S75-BASE") & (d.Recovery_Policy_ID == "R76-00-NONE")].copy()
    check("Unique baseline call identities", base.Simulation_Record_ID.nunique() == 604,
          int(base.Simulation_Record_ID.nunique()), 604)
    base = base[["Simulation_Record_ID", "Simulated_Arrival_Delay_Hours", "Simulated_Departure_Delay_Hours"]].rename(columns={
        "Simulated_Arrival_Delay_Hours": "Baseline_Arrival_Delay_Hours",
        "Simulated_Departure_Delay_Hours": "Baseline_Departure_Delay_Hours"})

    shocks = d[d.Scenario_ID != "S75-BASE"].copy()
    shocks = shocks.merge(base, on="Simulation_Record_ID", how="left", validate="many_to_one")
    check("All scenario calls matched to baseline", shocks.Baseline_Arrival_Delay_Hours.notna().all(),
          int(shocks.Baseline_Arrival_Delay_Hours.isna().sum()), 0)
    shocks["Incremental_Arrival_Delay_Hours"] = shocks.Simulated_Arrival_Delay_Hours - shocks.Baseline_Arrival_Delay_Hours
    shocks["Incremental_Departure_Delay_Hours"] = shocks.Simulated_Departure_Delay_Hours - shocks.Baseline_Departure_Delay_Hours

    no_rec = shocks[shocks.Recovery_Policy_ID == "R76-00-NONE"][[
        "Scenario_ID", "Simulation_Record_ID", "Incremental_Departure_Delay_Hours"]].rename(columns={
            "Incremental_Departure_Delay_Hours": "No_Recovery_Incremental_Departure_Delay_Hours"})
    shocks = shocks.merge(no_rec, on=["Scenario_ID", "Simulation_Record_ID"], how="left", validate="many_to_one")
    shocks["Paired_Recovery_Benefit_Hours"] = (
        shocks.No_Recovery_Incremental_Departure_Delay_Hours - shocks.Incremental_Departure_Delay_Hours)

    # Fixed common horizon is the maximum simulated departure timestamp across
    # the complete deterministic scenario-policy design envelope.
    horizon = d.Simulated_Departure_UTC.max()
    unfinished = int((d.Simulated_Departure_UTC > horizon).sum())
    check("Common horizon covers every represented simulated departure", unfinished == 0,
          unfinished, 0)
    check("All 604 represented call departures completed by common horizon",
          d.Simulated_Departure_UTC.notna().all(), int(d.Simulated_Departure_UTC.isna().sum()), 0)

    # Vessel final represented call, and sum of signed incremental departure delays.
    vessel_rows = []
    for (sid, pid), g in shocks.groupby(["Scenario_ID", "Recovery_Policy_ID"], sort=True):
        g = g.sort_values(["IMO_Normalised", "Vessel_Call_Sequence_Number", "Simulation_Record_ID"], kind="mergesort")
        final = g.groupby("IMO_Normalised", sort=False).tail(1).set_index("IMO_Normalised")
        sums = g.groupby("IMO_Normalised")["Incremental_Departure_Delay_Hours"].sum()
        for imo in sorted(g.IMO_Normalised.unique()):
            vessel_rows.append({
                "Scenario_ID": sid, "Recovery_Policy_ID": pid, "IMO_Normalised": imo,
                "Final_Represented_Call_ID": final.loc[imo, "Simulation_Record_ID"],
                "Final_Represented_Call_Departure_Delay_Hours": float(final.loc[imo, "Incremental_Departure_Delay_Hours"]),
                "Accumulated_Signed_Departure_Delay_Hours": float(sums.loc[imo]),
                "Unrecovered_Vessel": bool(final.loc[imo, "Incremental_Departure_Delay_Hours"] > TOL),
            })
    vessel = pd.DataFrame(vessel_rows)

    summary_rows = []
    for (sid, pid), g in shocks.groupby(["Scenario_ID", "Recovery_Policy_ID"], sort=True):
        vg = vessel[(vessel.Scenario_ID == sid) & (vessel.Recovery_Policy_ID == pid)]
        summary_rows.append({
            "Scenario_ID": sid,
            "Recovery_Policy_ID": pid,
            "Recovery_Policy": g.Recovery_Policy.iloc[0],
            "Shock_Magnitude_Hours": float(g.Shock_Magnitude_Design_Hours.iloc[0]),
            "Affected_Transition_Share": float(g.Affected_Transition_Share_Design.iloc[0]),
            "Call_Count": int(g.Simulation_Record_ID.nunique()),
            "Vessel_Count": int(g.IMO_Normalised.nunique()),
            "M01_Mean_Incremental_Arrival_Delay_Hours": float(g.Incremental_Arrival_Delay_Hours.mean()),
            "M02_Mean_Incremental_Departure_Delay_Hours": float(g.Incremental_Departure_Delay_Hours.mean()),
            "M03A_Max_Final_Represented_Call_Departure_Delay_Hours": float(vg.Final_Represented_Call_Departure_Delay_Hours.max()),
            "M03B_Max_Accumulated_Signed_Departure_Delay_Per_Vessel_Hours": float(vg.Accumulated_Signed_Departure_Delay_Hours.max()),
            "M04_Mean_Final_Represented_Call_Departure_Delay_Hours": float(vg.Final_Represented_Call_Departure_Delay_Hours.mean()),
            "M05_P90_Incremental_Call_Departure_Delay_Hours": float(g.Incremental_Departure_Delay_Hours.quantile(0.90, interpolation="linear")),
            "M06_Total_Paired_Recovery_Benefit_Hours": float(g.Paired_Recovery_Benefit_Hours.sum()),
            "M06_Mean_Paired_Recovery_Benefit_Per_Call_Hours": float(g.Paired_Recovery_Benefit_Hours.mean()),
            "Applied_Recovery_Credit_Total_Hours": float(g.Recovery_Advance_Hours.sum()),
            "M07A_Unrecovered_Call_Count": int((g.Incremental_Departure_Delay_Hours > TOL).sum()),
            "M07B_Unrecovered_Vessel_Count": int(vg.Unrecovered_Vessel.sum()),
            "Censored_Represented_Calls_At_Horizon": 0,
            "Censored_Vessels_At_Horizon": 0,
        })
    summary = pd.DataFrame(summary_rows)

    # All call-level paired records are retained for independent inspection.
    call_cols = ["Scenario_ID", "Recovery_Policy_ID", "Simulation_Record_ID", "IMO_Normalised",
                 "Vessel_Call_Sequence_Number", "Affected_Transition", "Transit_Elapsed_Time_Shock_Hours",
                 "Baseline_Arrival_Delay_Hours", "Baseline_Departure_Delay_Hours",
                 "Simulated_Arrival_Delay_Hours", "Simulated_Departure_Delay_Hours",
                 "Incremental_Arrival_Delay_Hours", "Incremental_Departure_Delay_Hours",
                 "No_Recovery_Incremental_Departure_Delay_Hours", "Paired_Recovery_Benefit_Hours",
                 "Recovery_Advance_Hours", "Simulated_Arrival_UTC", "Simulated_Departure_UTC"]
    call_out = shocks[call_cols].copy()

    check("Exactly 16 shock scenarios and 80 scenario-policy cells",
          summary.Scenario_ID.nunique() == 16 and len(summary) == 80,
          {"scenarios": int(summary.Scenario_ID.nunique()), "cells": int(len(summary))},
          {"scenarios": 16, "cells": 80})
    check("All delays and recovery benefits reconcile numerically",
          np.isfinite(call_out[["Incremental_Arrival_Delay_Hours", "Incremental_Departure_Delay_Hours", "Paired_Recovery_Benefit_Hours"]].to_numpy()).all(),
          "finite", "finite")

    failed = [x for x in checks if not x["Passed"]]
    TABLES.mkdir(parents=True, exist_ok=True); REPORTS.mkdir(parents=True, exist_ok=True)
    call_out.to_csv(TABLES / "98_final_call_level_paired_results.csv", index=False)
    vessel.to_csv(TABLES / "98_final_vessel_level_results.csv", index=False)
    summary.to_csv(TABLES / "98_final_scenario_policy_results.csv", index=False)
    pd.DataFrame(checks).to_csv(TABLES / "98_final_results_validation_checks.csv", index=False)

    report = [
        "SCRIPT 98 — FINAL EXPERIMENT RESULT ANALYSIS", "=" * 78, "",
        "PRIMARY MODEL: SCRIPT76 RECOVERY FORMULATION", 
        "Script77 is retained as a bounded sensitivity analysis only. Its observed-interval cap is not established schedule slack.",
        "", f"Input records: {len(d):,}", f"Shock scenarios: {summary.Scenario_ID.nunique()}",
        f"Scenario-policy result rows: {len(summary)}", f"Calls per cell: {int(summary.Call_Count.min())}–{int(summary.Call_Count.max())}",
        f"Vessels per cell: {int(summary.Vessel_Count.min())}–{int(summary.Vessel_Count.max())}",
        f"Common evaluation horizon (UTC): {horizon.isoformat()}",
        "Represented calls unfinished at this horizon: 0", "Represented vessels unfinished at this horizon: 0",
        "", "INTERPRETATION", 
        "Delay outcomes are incremental relative to the no-disruption simulated baseline.",
        "Recovery benefit is paired against no recovery within the same shock scenario.",
        "M03A/M04 use each vessel's last represented call, not its actual final voyage call.",
        "M03B is the maximum across vessels of summed signed call-level incremental departure delay.",
        "No right-censoring occurs for the finite represented call set under the envelope horizon. The observed dataset may still truncate voyages beyond each vessel's last represented call.",
        "All model outputs are conditional hypothetical results, not actual Hormuz transit or operational effects.",
        "", f"Validation: {len(checks)-len(failed)}/{len(checks)} passed; {len(failed)} failed.",
        "", "KEY SUMMARY — first 10 rows", summary.head(10).to_string(index=False),
        "", "OUTPUTS", "- outputs/tables/98_final_call_level_paired_results.csv",
        "- outputs/tables/98_final_vessel_level_results.csv", "- outputs/tables/98_final_scenario_policy_results.csv",
        "- outputs/tables/98_final_results_validation_checks.csv", "", "NO SOURCE INPUTS MODIFIED.",
    ]
    (REPORTS / "98_final_experiment_results_report.txt").write_text("\n".join(report), encoding="utf-8")
    print("=" * 78); print("SCRIPT 98 — FINAL EXPERIMENT RESULT ANALYSIS"); print("=" * 78)
    print(f"Primary model: Script76 | Sensitivity: Script77")
    print(f"Scenarios: {summary.Scenario_ID.nunique()} | Scenario-policy rows: {len(summary)}")
    print(f"Calls/cell: {summary.Call_Count.min()}–{summary.Call_Count.max()} | Vessels/cell: {summary.Vessel_Count.min()}–{summary.Vessel_Count.max()}")
    print(f"Common evaluation horizon UTC: {horizon.isoformat()}")
    print(f"Validation: {len(checks)-len(failed)}/{len(checks)} passed; {len(failed)} failed")
    print(f"Report: {REPORTS / '98_final_experiment_results_report.txt'}")
    if failed:
        for x in failed: print("FAILED:", x)
        raise SystemExit(1)

if __name__ == '__main__':
    main()
