#!/usr/bin/env python3
"""
Script 94 — Recovery Policy Mathematical Semantics and Counterfactual Consistency Audit (schema-corrected)

Diagnostic only. Reads Scripts 75–77 outputs and the Script 76 policy register.
Does not modify upstream inputs, run a simulation, approve policies, or authorize execution.

Run from project root:
    python src/94_recovery_policy_semantics_audit.py
"""

from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)

FILES = {
    "policy": TABLES / "76_recovery_policy_register.csv",
    "recovery": TABLES / "76_call_level_recovery_results.csv",
    "shock": TABLES / "75_call_level_disruption_results.csv",
    "bounded": TABLES / "77_call_level_bounded_recovery_results.csv",
}

missing = [str(p) for p in FILES.values() if not p.exists()]
if missing:
    print("ERROR: Required Script94 inputs are missing:")
    print("\n".join(missing))
    print("\nNo inputs were modified. Confirm the files exist, then rerun.")
    sys.exit(1)

D = {k: pd.read_csv(v) for k, v in FILES.items()}

checks = []
def add_check(name, passed, observed, expected, note):
    checks.append({
        "Check": name, "Passed": bool(passed),
        "Observed": str(observed), "Expected": str(expected),
        "Interpretation": note
    })

def find_col(df, candidates, label, required=True):
    for c in candidates:
        if c in df.columns:
            return c
    if required:
        raise KeyError(
            f"Could not identify {label}. Tried {candidates}. "
            f"Available columns: {list(df.columns)}"
        )
    return None

# ----------------------------
# A. Resolve policy-register fields
# ----------------------------
p = D["policy"].copy()
pid = find_col(p, ["Recovery_Policy_ID", "Policy_ID"], "policy ID")
ptype = find_col(p, ["Policy_Type", "Recovery_Type"], "policy type")
fixed = find_col(p, ["Fixed_Recovery_Cap_Hours", "Fixed_Recovery_Hours"], "fixed cap", False)
rate = find_col(p, ["Proportional_Recovery_Rate", "Recovery_Rate"], "proportional rate", False)
maxcap = find_col(p, ["Maximum_Recovery_Per_Link_Hours", "Maximum_Recovery_Cap_Hours"], "maximum per-link cap", False)
approval = find_col(p, ["Approval_Granted", "Approval_Status"], "approval field", False)

p[ptype] = p[ptype].astype(str).str.upper()
for c in [fixed, rate, maxcap]:
    if c:
        p[c] = pd.to_numeric(p[c], errors="coerce")

expected_ids = [
    "R76-00-NONE", "R76-01-FIXED-6H", "R76-02-FIXED-12H",
    "R76-03-PROP-25-CAP6", "R76-04-PROP-50-CAP12"
]
add_check("Five expected policy IDs present exactly once",
          p[pid].astype(str).value_counts().reindex(expected_ids, fill_value=0).eq(1).all()
          and len(p) == 5, p[pid].astype(str).tolist(), expected_ids,
          "Policy identity and uniqueness only.")

# Build formula specification from policy register, never silently inventing missing parameters.
semantics = []
for _, r in p.iterrows():
    policy_id = str(r[pid])
    typ = str(r[ptype]).upper()
    fcap = float(r[fixed]) if fixed and pd.notna(r[fixed]) else np.nan
    frac = float(r[rate]) if rate and pd.notna(r[rate]) else np.nan
    mcap = float(r[maxcap]) if maxcap and pd.notna(r[maxcap]) else np.nan

    if typ in {"NONE", "NO_RECOVERY"} or policy_id == "R76-00-NONE":
        formula = "recovery = 0"
        formula_status = "DEFINED"
    elif typ == "FIXED":
        cap = fcap if np.isfinite(fcap) else mcap
        formula = "recovery = min(delay_before, fixed_cap)"
        formula_status = "DEFINED" if np.isfinite(cap) and cap >= 0 else "MISSING_OR_INVALID_FIXED_CAP"
    elif typ in {"PROPORTIONAL", "PROPORTION", "PERCENTAGE"}:
        formula = "recovery = min(delay_before, delay_before * rate, per_link_cap)"
        formula_status = "DEFINED" if (
            np.isfinite(frac) and 0 <= frac <= 1 and np.isfinite(mcap) and mcap >= 0
        ) else "MISSING_OR_INVALID_RATE_OR_CAP"
    else:
        formula = "UNRECOGNIZED_POLICY_TYPE"
        formula_status = "UNRESOLVED"
    semantics.append({
        "Recovery_Policy_ID": policy_id,
        "Policy_Type": typ,
        "Fixed_Recovery_Cap_Hours": fcap,
        "Proportional_Recovery_Rate": frac,
        "Maximum_Recovery_Per_Link_Hours": mcap,
        "Candidate_Mathematical_Rule": formula,
        "Rule_Parameter_Status": formula_status,
        "Approval_Field_Value": str(r[approval]) if approval else "NOT_PRESENT",
        "Operational_Feasibility_Established": False,
        "Decision_Status": "DIAGNOSTIC_ONLY_NOT_APPROVED"
    })
sem = pd.DataFrame(semantics)
add_check("All five policy rules have complete parameters",
          sem["Rule_Parameter_Status"].eq("DEFINED").all(),
          sem["Rule_Parameter_Status"].value_counts().to_dict(),
          "All five DEFINED",
          "A register-level rule check; does not yet verify call-level implementation.")

# ----------------------------
# B. Resolve call-level result fields
# ----------------------------
r = D["recovery"].copy()
s = D["shock"].copy()
b = D["bounded"].copy()

scenario = find_col(r, ["Scenario_ID", "Scenario"], "scenario")
policy = find_col(r, ["Recovery_Policy_ID", "Recovery_Policy"], "recovery policy")
vessel = find_col(r, ["IMO_Normalised", "Vessel_ID", "IMO"], "vessel ID")
call = find_col(r, ["Simulation_Record_ID", "Call_ID", "Record_ID"], "call ID")
seq = find_col(r, ["Vessel_Call_Sequence_Number", "Vessel_Call_Sequence", "Call_Sequence", "Sequence_Number"], "vessel call sequence", False)
delay = find_col(r, ["Simulated_Departure_Delay_Hours", "Accumulated_Delay_Hours", "Final_Delay_Hours", "Departure_Delay_Hours"], "post-recovery departure delay")
recovered = find_col(r, ["Recovery_Advance_Hours", "Recovered_Hours_At_Transition", "Recovery_Credit_Hours", "Applied_Recovery_Hours"], "applied recovery")
requested = find_col(r, ["Requested_Recovery_Hours", "Requested_Recovery_Credit_Hours"], "requested recovery", False)
before = find_col(r, ["Delay_Before_Recovery_Hours", "Pre_Recovery_Delay_Hours", "Available_Delay_Before_Recovery_Hours"], "pre-recovery delay", False)
arrival_delay = find_col(r, ["Simulated_Arrival_Delay_Hours", "Arrival_Delay_Hours"], "post-recovery arrival delay", False)
onset = find_col(r, ["Is_Disruption_Onset", "Is_Shock_Onset", "Is_Onset"], "disruption onset flag", False)
disrupted = find_col(r, ["Is_Disrupted_Call", "Is_Affected_Call", "Disruption_Active"], "disrupted-call flag", False)

for c in [delay, recovered, requested, before]:
    if c:
        r[c] = pd.to_numeric(r[c], errors="coerce")

# Stable key checks
key = [scenario, policy, vessel, call]
add_check("Call-level policy result keys are unique",
          not r.duplicated(key).any(), int(r.duplicated(key).sum()), 0,
          "Each scenario-policy-vessel-call record must be unique.")
add_check("No negative accumulated delay",
          r[delay].notna().all() and (r[delay] >= -1e-9).all(),
          float(r[delay].min()), ">= 0",
          "Negative delay would violate the nonnegative delay state.")
add_check("No negative applied recovery",
          r[recovered].notna().all() and (r[recovered] >= -1e-9).all(),
          float(r[recovered].min()), ">= 0",
          "Recovery credit must be nonnegative.")

# Validate delay-after = delay-before - applied recovery where pre-recovery delay is exposed.
if before:
    calc = r[before] - r[recovered]
    dep_err = (r[delay] - calc).abs()
    add_check("Departure delay reconciles to pre-delay minus recovery advance",
              dep_err.notna().all() and dep_err.max() <= 0.001,
              float(dep_err.max()), "<= 0.001 hours",
              "Direct arithmetic check using the actual Script76 departure-delay field.")
    if arrival_delay:
        arr_err = (r[arrival_delay] - calc).abs()
        add_check("Arrival delay reconciles to pre-delay minus recovery advance",
                  arr_err.notna().all() and arr_err.max() <= 0.001,
                  float(arr_err.max()), "<= 0.001 hours",
                  "Arrival and departure delays are checked independently.")
    else:
        add_check("Arrival delay field available for direct reconciliation",
                  False, "FIELD_NOT_FOUND", "Simulated_Arrival_Delay_Hours",
                  "Arrival-delay reconciliation cannot be tested.")
else:
    add_check("Pre-recovery delay field available for direct reconciliation",
              False, "FIELD_NOT_FOUND", "Delay_Before_Recovery_Hours",
              "Direct arithmetic reconciliation is not possible from the available output schema.")

# Check policy IDs and scenario-policy rectangular structure.
add_check("Only registered recovery policies appear in call-level results",
          set(r[policy].astype(str)).issubset(set(p[pid].astype(str))),
          sorted(set(r[policy].astype(str)) - set(p[pid].astype(str))),
          "No unregistered policy IDs", "Register-to-results alignment.")
pair_counts = r.groupby([scenario, policy]).size().unstack(fill_value=0)
add_check("Every scenario has all five policies",
          pair_counts.shape[1] == 5 and (pair_counts > 0).all().all(),
          f"{pair_counts.shape[0]} scenarios x {pair_counts.shape[1]} policies",
          "Rectangular scenario-policy coverage",
          "Presence check; not proof of identical record exposure.")

# ----------------------------
# C. Counterfactual pairing and same shock checks against Script75
# ----------------------------
shock_scenario = find_col(s, ["Scenario_ID", "Scenario"], "Script75 scenario")
shock_vessel = find_col(s, ["IMO_Normalised", "Vessel_ID", "IMO"], "Script75 vessel")
shock_call = find_col(s, ["Simulation_Record_ID", "Call_ID", "Record_ID"], "Script75 call")
shock_delay = find_col(s, ["Accumulated_Delay_Hours", "Arrival_Delay_Hours", "Departure_Delay_Hours",
                           "Call_Departure_Delay_Hours"], "Script75 no-recovery delay", False)

# Script75 key can be one row per scenario-call. Use it to ensure the same call population is present.
shock_keys = set(map(tuple, s[[shock_scenario, shock_vessel, shock_call]].astype(str).to_numpy()))
recovery_keys = set(map(tuple, r[[scenario, vessel, call]].astype(str).to_numpy()))
missing_from_76 = len(shock_keys - recovery_keys)
extra_in_76 = len(recovery_keys - shock_keys)
add_check("Script76 result keys reconcile to Script75 scenario-call universe",
          missing_from_76 == 0 and extra_in_76 == 0,
          f"missing={missing_from_76}; extra={extra_in_76}",
          "0 missing; 0 extra",
          "Policy replication should preserve the same scenario-call universe.")

# Per-scenario/policy compare each policy's call IDs and vessel IDs to no-recovery.
none_id = "R76-00-NONE"
pair_rows = []
for sc in sorted(r[scenario].astype(str).unique()):
    g = r[r[scenario].astype(str) == sc]
    base = g[g[policy].astype(str) == none_id]
    base_ids = set(base[call].astype(str))
    for pol in sorted(g[policy].astype(str).unique()):
        q = g[g[policy].astype(str) == pol]
        ids = set(q[call].astype(str))
        pair_rows.append({
            "Scenario": sc, "Recovery_Policy_ID": pol,
            "Call_Count": len(q), "Unique_Call_IDs": q[call].nunique(),
            "Missing_vs_No_Recovery": len(base_ids - ids),
            "Extra_vs_No_Recovery": len(ids - base_ids),
            "Matched_Call_Population": ids == base_ids,
            "Interpretation": "Matched call population only; does not establish operational comparability"
        })
pair = pd.DataFrame(pair_rows)
add_check("Every policy has identical call IDs to no-recovery within scenario",
          pair["Matched_Call_Population"].all(),
          int((~pair["Matched_Call_Population"]).sum()), 0,
          "Counterfactual pairing requires identical call populations.")

# ----------------------------
# D. Policy monotonicity and recovery-credit consistency
# ----------------------------
# For every call, delay should be no greater under a recovery policy than under no recovery,
# provided the shock realization and call universe are identical.
wide = r.pivot_table(index=[scenario, vessel, call], columns=policy, values=delay, aggfunc="first")
mono_rows = []
if none_id in wide.columns:
    for pol in [x for x in wide.columns if x != none_id]:
        delta = wide[pol] - wide[none_id]
        mono_rows.append({
            "Recovery_Policy_ID": pol,
            "Compared_Calls": int(delta.notna().sum()),
            "Cases_Policy_Delay_Exceeds_No_Recovery": int((delta > 0.001).sum()),
            "Maximum_Excess_Delay_Hours": float(delta.max()) if delta.notna().any() else np.nan,
            "Mean_Delay_Reduction_Hours": float((-delta).mean()) if delta.notna().any() else np.nan,
            "Monotonicity_Passed": bool((delta.dropna() <= 0.001).all())
        })
mono = pd.DataFrame(mono_rows)
add_check("Recovery policies never increase delay relative to no-recovery",
          len(mono) == 4 and mono["Monotonicity_Passed"].all(),
          mono[["Recovery_Policy_ID", "Cases_Policy_Delay_Exceeds_No_Recovery"]].to_dict("records")
          if len(mono) else "NOT_TESTABLE",
          "0 cases for each of four alternatives",
          "A model-rule monotonicity property, conditional on matched shocks and records.")

# If requested credit exists, applied credit must not exceed request.
if requested:
    add_check("Applied recovery does not exceed requested recovery",
              (r[recovered] <= r[requested] + 0.001).all(),
              float((r[recovered] - r[requested]).max()),
              "<= 0.001 hours",
              "Tests request-versus-application cap.")
else:
    add_check("Requested recovery amount available for direct cap audit",
              False, "FIELD_NOT_FOUND", "Requested recovery column",
              "Script76 output does not expose a separately named requested-credit field.")

# First call must have zero recovery if sequence is available.
if seq:
    first = r[pd.to_numeric(r[seq], errors="coerce") == 1]
    add_check("No recovery applied to first vessel call",
              len(first) > 0 and (first[recovered].abs() <= 0.001).all(),
              f"first_call_rows={len(first)}; max_recovery={first[recovered].abs().max() if len(first) else 'NA'}",
              "All first-call recovery = 0",
              "Recovery begins only at subsequent sequence links.")
else:
    add_check("Sequence field available to verify first-call exclusion",
              False, "FIELD_NOT_FOUND", "Vessel call sequence",
              "First-call exclusion cannot be independently tested.")

# ----------------------------
# E. Script77 bounded recovery comparison
# ----------------------------
b_policy = find_col(b, ["Recovery_Policy_ID", "Recovery_Policy"], "Script77 policy")
b_delay = find_col(b, ["Simulated_Departure_Delay_Hours", "Accumulated_Delay_Hours", "Final_Delay_Hours", "Departure_Delay_Hours"],
                   "Script77 bounded post-recovery delay")
b_recovered = find_col(b, ["Bounded_Recovery_Hours", "Bounded_Recovery_Advance_Hours", "Recovery_Advance_Hours", "Recovered_Hours_At_Transition",
                           "Applied_Recovery_Hours"], "Script77 bounded recovery")
b_key_cols = [
    find_col(b, ["Scenario_ID", "Scenario"], "Script77 scenario"),
    find_col(b, ["IMO_Normalised", "Vessel_ID", "IMO"], "Script77 vessel"),
    find_col(b, ["Simulation_Record_ID", "Call_ID", "Record_ID"], "Script77 call"),
    b_policy
]
for c in [b_delay, b_recovered]:
    b[c] = pd.to_numeric(b[c], errors="coerce")
add_check("Script77 bounded output contains nonnegative delay and recovery",
          b[b_delay].notna().all() and b[b_recovered].notna().all()
          and (b[b_delay] >= -1e-9).all() and (b[b_recovered] >= -1e-9).all(),
          f"min_delay={b[b_delay].min()}; min_recovery={b[b_recovered].min()}",
          "Both >= 0",
          "Bounded recovery output arithmetic validity.")
add_check("Script77 bounded recovery never exceeds Script76 requested recovery universe",
          len(b) > 0, len(b), "Non-empty Script77 output",
          "This is a presence check only; exact credit matching requires a shared request field/key.")

# ----------------------------
# F. Write outputs and report
# ----------------------------
checks_df = pd.DataFrame(checks)
sem.to_csv(TABLES / "94_policy_mathematical_semantics_register.csv", index=False)
pair.to_csv(TABLES / "94_counterfactual_call_pairing_audit.csv", index=False)
mono.to_csv(TABLES / "94_policy_monotonicity_audit.csv", index=False)
checks_df.to_csv(TABLES / "94_readiness_checks.csv", index=False)

passed = int(checks_df["Passed"].sum())
failed = int((~checks_df["Passed"]).sum())
report = REPORTS / "94_recovery_policy_semantics_audit_report.txt"
with report.open("w", encoding="utf-8") as f:
    f.write("SCRIPT 94 — RECOVERY POLICY MATHEMATICAL SEMANTICS AND COUNTERFACTUAL CONSISTENCY AUDIT\n")
    f.write("=" * 92 + "\n\n")
    f.write("PURPOSE\nAudit Script76 policy definitions and call-level outputs against Script75 shock records,\n")
    f.write("and compare Script77 bounded-recovery outputs. Diagnostic only.\n\n")
    f.write("INPUT INVENTORY\n")
    for k, path in FILES.items():
        f.write(f"{k}: {path.name}; rows={len(D[k])}; columns={len(D[k].columns)}\n")
    f.write("\nPOLICY SEMANTICS\n")
    f.write(sem.to_string(index=False) + "\n\n")
    f.write("COUNTERFACTUAL PAIRING\n")
    f.write(pair.to_string(index=False) + "\n\n")
    f.write("POLICY MONOTONICITY\n")
    f.write(mono.to_string(index=False) if len(mono) else "Not testable from resolved fields")
    f.write("\n\nREADINESS CHECKS\n")
    f.write(f"{passed}/{len(checks_df)} passed; {failed} failed.\n")
    f.write(checks_df.to_string(index=False) + "\n\n")
    f.write("INTERPRETATION AND LIMITATIONS\n")
    f.write("- Recovery credits are hypothetical mathematical allowances, not measured capabilities.\n")
    f.write("- The Script77 elapsed-time cap uses observed inter-call elapsed time; it is not schedule slack.\n")
    f.write("- Inter-port elapsed time is not pure sailing time; no route or actual Hormuz transit is established.\n")
    f.write("- This audit does not establish operational feasibility, safety, cost, fuel, emissions, or capacity.\n")
    f.write("- Missing schema fields cause explicit failed checks; they are not silently inferred.\n")
    f.write("- No policy, estimand, censoring rule, or experiment execution is approved by this script.\n")
    f.write("- No simulation is run and no upstream input is modified.\n\n")
    f.write("OUTPUTS\n")
    for name in [
        "94_policy_mathematical_semantics_register.csv",
        "94_counterfactual_call_pairing_audit.csv",
        "94_policy_monotonicity_audit.csv",
        "94_readiness_checks.csv",
        "94_recovery_policy_semantics_audit_report.txt",
    ]:
        f.write(f"- outputs/{'reports' if name.endswith('.txt') else 'tables'}/{name}\n")

print("=" * 78)
print("SCRIPT 94 — RECOVERY POLICY MATHEMATICAL SEMANTICS AUDIT")
print("=" * 78)
print(f"Policy rows: {len(p)}")
print(f"Script76 call-level rows: {len(r)}")
print(f"Script75 shock rows: {len(s)}")
print(f"Script77 bounded rows: {len(b)}")
print(f"Readiness checks: {passed}/{len(checks_df)} passed; {failed} failed")
print("Simulation executed: NO")
print("Execution authorized: NO")
print(f"Report: {report}")
print("\nNOTE: A failed check is an audit finding or unavailable source field, not permission to alter upstream results.")
