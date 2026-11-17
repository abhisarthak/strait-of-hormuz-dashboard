#!/usr/bin/env python3
"""SCRIPT95 v4 — bounded recovery reconciliation with separate path audits.

Diagnostic only. Does not modify Scripts76/77, run a simulation, or authorize
experiments. Script76 and Script77 are expected to have different delay paths
because Script77 additionally caps requested recovery by observed elapsed time.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"
INPUTS = {
    "r76": TABLES / "76_call_level_recovery_results.csv",
    "r77": TABLES / "77_call_level_bounded_recovery_results.csv",
}
OUT = {
    "pair": TABLES / "95_bounded_recovery_record_reconciliation.csv",
    "checks": TABLES / "95_readiness_checks.csv",
    "report": REPORTS / "95_bounded_recovery_reconciliation_report.txt",
}
KEY_GROUPS = {
    "scenario": ["Scenario_ID", "Scenario", "Scenario_ID_Design"],
    "policy": ["Recovery_Policy_ID", "Policy_ID"],
    "vessel": ["IMO_Normalised", "IMO", "Vessel_ID"],
    "call": ["Simulation_Record_ID", "Call_ID", "Record_ID"],
}
TOL = 0.001

def read_csv(path, label):
    if not path.exists():
        raise FileNotFoundError(f"Missing {label} input: {path}")
    return pd.read_csv(path, low_memory=False)

def pick_column(df, candidates):
    return next((c for c in candidates if c in df.columns), None)

def normalized_key(s):
    return s.astype("string").fillna("<NA>").str.strip()

def add_check(rows, name, passed, observed, expected, interpretation):
    rows.append({
        "Check": name, "Passed": bool(passed), "Observed": str(observed),
        "Expected": str(expected), "Interpretation": interpretation,
    })

def recurrence_audit(df, label, pre_col, recovery_col, post_col):
    required = ["Scenario_ID", "Recovery_Policy_ID", "IMO_Normalised",
                "Vessel_Call_Sequence_Number", "Transit_Elapsed_Time_Shock_Hours",
                pre_col, recovery_col, post_col]
    missing = [c for c in required if c not in df.columns]
    if missing:
        return {"missing": missing, "pre_fail": None, "post_fail": None,
                "rows": 0, "max_pre": None, "max_post": None}
    x = df[required].copy()
    for c in ["Vessel_Call_Sequence_Number", "Transit_Elapsed_Time_Shock_Hours",
              pre_col, recovery_col, post_col]:
        x[c] = pd.to_numeric(x[c], errors="coerce")
    x = x.sort_values(
        ["Scenario_ID", "Recovery_Policy_ID", "IMO_Normalised",
         "Vessel_Call_Sequence_Number"], kind="mergesort"
    )
    pre_errors, post_errors = [], []
    for _, g in x.groupby(["Scenario_ID", "Recovery_Policy_ID", "IMO_Normalised"],
                          sort=False, dropna=False):
        previous = 0.0
        for row in g.itertuples(index=False, name=None):
            # Use positional mapping to avoid assumptions about pandas' namedtuple
            # field renaming for source column names.
            pass
        for _, row in g.iterrows():
            expected_pre = previous + float(row["Transit_Elapsed_Time_Shock_Hours"])
            actual_pre = float(row[pre_col])
            pre_errors.append(actual_pre - expected_pre)
            expected_post = max(0.0, expected_pre - float(row[recovery_col]))
            actual_post = float(row[post_col])
            post_errors.append(actual_post - expected_post)
            previous = actual_post
    pe = np.asarray(pre_errors, dtype=float)
    qe = np.asarray(post_errors, dtype=float)
    return {
        "missing": [], "pre_fail": int((np.abs(pe) > TOL).sum()),
        "post_fail": int((np.abs(qe) > TOL).sum()), "rows": len(x),
        "max_pre": float(np.max(np.abs(pe))) if len(pe) else 0.0,
        "max_post": float(np.max(np.abs(qe))) if len(qe) else 0.0,
    }

def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    checks, report = [], [
        "SCRIPT 95 v4 — SCRIPT76/SCRIPT77 BOUNDED RECOVERY CREDIT RECONCILIATION",
        "=" * 82, "",
        "PURPOSE",
        "Record-level recovery reconciliation plus separate sequential recurrence audits.",
        "Diagnostic only; no simulation, approval, or upstream modification.", "",
    ]
    r76 = read_csv(INPUTS["r76"], "Script76 call-level recovery")
    r77 = read_csv(INPUTS["r77"], "Script77 call-level bounded recovery")
    report += [
        "INPUT INVENTORY", f"Script76: {len(r76)} rows; {len(r76.columns)} columns",
        f"Script77: {len(r77)} rows; {len(r77.columns)} columns", "",
    ]

    keymap = {}
    for group, candidates in KEY_GROUPS.items():
        a, b = pick_column(r76, candidates), pick_column(r77, candidates)
        if a and b:
            keymap[group] = (a, b)
    required_groups = ["scenario", "policy", "vessel", "call"]
    missing_groups = [g for g in required_groups if g not in keymap]
    add_check(checks, "Scenario/policy/vessel/call keys available in both files",
              not missing_groups, missing_groups or "All four key groups found",
              "All four key groups", "Exact record pairing requires shared identifiers.")
    if missing_groups:
        raise ValueError(f"Missing key groups: {missing_groups}")

    r76, r77 = r76.copy(), r77.copy()
    for group, (a, b) in keymap.items():
        r76[f"__key_{group}"] = normalized_key(r76[a])
        r77[f"__key_{group}"] = normalized_key(r77[b])
    keys = [f"__key_{g}" for g in required_groups]
    d76, d77 = int(r76.duplicated(keys).sum()), int(r77.duplicated(keys).sum())
    add_check(checks, "Script76 composite keys unique", d76 == 0, d76, 0,
              "Duplicate keys prevent one-to-one record reconciliation.")
    add_check(checks, "Script77 composite keys unique", d77 == 0, d77, 0,
              "Duplicate keys prevent one-to-one record reconciliation.")

    c76rec = pick_column(r76, ["Recovery_Advance_Hours", "Applied_Recovery_Hours",
                               "Recovery_Credit_Hours", "Recovery_Hours"])
    c77rec = pick_column(r77, ["Script77_Bounded_Recovery_Hours",
                               "Bounded_Recovery_Advance_Hours", "Bounded_Recovery_Hours"])
    c77req = pick_column(r77, ["Script76_Requested_Recovery_Hours",
                               "Requested_Recovery_Hours", "Requested_Recovery_Advance_Hours"])
    c76pre = pick_column(r76, ["Delay_Before_Recovery_Hours", "Pre_Recovery_Delay_Hours"])
    c77pre = pick_column(r77, ["Script77_Delay_Before_Recovery_Hours",
                               "Delay_Before_Recovery_Hours", "Pre_Recovery_Delay_Hours"])
    elapsed = pick_column(r77, ["Observed_Inter_Call_Elapsed_Cap_Hours",
                                "Available_Elapsed_Time_Hours",
                                "Observed_Inter_Call_Elapsed_Hours"])
    c77post = pick_column(r77, ["Script77_Departure_Delay_Hours",
                                "Simulated_Departure_Delay_Hours"])
    c76post = pick_column(r76, ["Simulated_Departure_Delay_Hours"])
    seq76 = pick_column(r76, ["Vessel_Call_Sequence_Number"])
    seq77 = pick_column(r77, ["Vessel_Call_Sequence_Number"])
    shock76 = pick_column(r76, ["Transit_Elapsed_Time_Shock_Hours"])
    shock77 = pick_column(r77, ["Transit_Elapsed_Time_Shock_Hours"])
    required = [c76rec, c77rec, c76pre, c77pre, elapsed, c77post,
                c76post, seq76, seq77, shock76, shock77]
    if any(v is None for v in required):
        raise ValueError("Missing required recovery/recurrence columns; inspect input schemas.")
    add_check(checks, "Recovery, sequence and recurrence fields identified", True,
              str(required), "All required fields",
              "Both model paths can be audited independently.")

    left_cols = keys + [c76rec, c76pre, c76post, seq76, shock76]
    right_cols = keys + [c77rec, c77pre, elapsed, c77post, seq77, shock77]
    if c77req:
        right_cols.append(c77req)
    left = r76[left_cols].rename(columns={
        c76rec: "R76_Recovery_Hours", c76pre: "R76_Pre_Recovery_Delay_Hours",
        c76post: "R76_Post_Recovery_Departure_Delay_Hours",
        seq76: "R76_Sequence", shock76: "R76_Shock_Hours"})
    right = r77[right_cols].rename(columns={
        c77rec: "R77_Bounded_Recovery_Hours", c77pre: "R77_Pre_Recovery_Delay_Hours",
        elapsed: "Observed_Inter_Call_Elapsed_Hours", c77post: "R77_Post_Recovery_Departure_Delay_Hours",
        seq77: "R77_Sequence", shock77: "R77_Shock_Hours"})
    if c77req:
        right = right.rename(columns={c77req: "R77_Requested_Recovery_Hours"})
    paired = left.merge(right, on=keys, how="outer", indicator=True, validate="one_to_one")
    matched = paired["_merge"].eq("both")
    miss, extra = int((paired["_merge"] == "left_only").sum()), int((paired["_merge"] == "right_only").sum())
    add_check(checks, "Script76 and Script77 records pair one-to-one",
              miss == 0 and extra == 0, f"missing_in_77={miss}; extra_in_77={extra}",
              "0 missing; 0 extra", "Pairing uses scenario, policy, vessel and call identifiers.")
    valid = paired.loc[matched].copy()
    numeric = [c for c in valid.columns if c not in keys + ["_merge"]]
    for c in numeric:
        valid[c] = pd.to_numeric(valid[c], errors="coerce")

    def check_max(name, series, expectation, interpretation, predicate):
        s = pd.to_numeric(series, errors="coerce")
        count = int(predicate(s).sum())
        observed = float(s.max()) if len(s.dropna()) else "N/A"
        add_check(checks, name, count == 0, count, 0, interpretation)

    check_max("Script77 bounded recovery is nonnegative",
              -valid["R77_Bounded_Recovery_Hours"], ">=0",
              "Bounded recovery cannot be negative.",
              lambda s: s > TOL)
    check_max("Script77 bounded recovery never exceeds Script76 recovery",
              valid["R77_Bounded_Recovery_Hours"] - valid["R76_Recovery_Hours"], "<=0",
              "Bounded credit cannot exceed requested/applied Script76 credit.",
              lambda s: s > TOL)
    if "R77_Requested_Recovery_Hours" in valid:
        reqerr = (valid["R77_Requested_Recovery_Hours"] - valid["R76_Recovery_Hours"]).abs()
        add_check(checks, "Script77 exported requested recovery matches Script76",
                  bool((reqerr <= TOL).all()), float(reqerr.max()), f"<= {TOL} hours",
                  "Direct requested-credit reconciliation.")
    check_max("Script77 recovery respects observed elapsed-time cap",
              valid["R77_Bounded_Recovery_Hours"] - valid["Observed_Inter_Call_Elapsed_Hours"],
              "<=0", "Mathematical elapsed-time bound only; not established schedule slack.",
              lambda s: s > TOL)
    check_max("Script77 recovery does not exceed its pre-recovery delay",
              valid["R77_Bounded_Recovery_Hours"] - valid["R77_Pre_Recovery_Delay_Hours"],
              "<=0", "Recovery cannot exceed delay available before recovery.",
              lambda s: s > TOL)

    # Each script has its own recurrence. Do not require cross-script pre-delay
    # equality: prior post-recovery delays differ when Script77's extra cap binds.
    a76 = recurrence_audit(r76, "Script76", c76pre, c76rec, c76post)
    a77 = recurrence_audit(r77, "Script77", c77pre, c77rec, c77post)
    for label, audit in [("Script76", a76), ("Script77", a77)]:
        add_check(checks, f"{label} pre-recovery delay follows its own sequence recurrence",
                  not audit["missing"] and audit["pre_fail"] == 0,
                  f"failures={audit['pre_fail']}; max_abs_error={audit['max_pre']}; missing={audit['missing']}",
                  "0 recurrence failures",
                  "Pre-delay = previous call's post-recovery delay + current shock.")
        add_check(checks, f"{label} post-recovery delay follows its own recovery arithmetic",
                  not audit["missing"] and audit["post_fail"] == 0,
                  f"failures={audit['post_fail']}; max_abs_error={audit['max_post']}; missing={audit['missing']}",
                  "0 arithmetic failures",
                  "Post-delay = max(0, pre-delay - recovery applied by that script).")

    # Verify that the between-model pre-delay difference is carried forward from
    # the previous call's difference, with the same current shock on both paths.
    valid = valid.sort_values(["__key_scenario", "__key_policy", "__key_vessel", "R76_Sequence"],
                              kind="mergesort")
    pre_divergence_errors = []
    shock_mismatch = (valid["R76_Shock_Hours"] - valid["R77_Shock_Hours"]).abs()
    for _, g in valid.groupby(["__key_scenario", "__key_policy", "__key_vessel"], sort=False):
        previous_difference = 0.0
        for _, row in g.iterrows():
            actual_difference = row["R77_Pre_Recovery_Delay_Hours"] - row["R76_Pre_Recovery_Delay_Hours"]
            pre_divergence_errors.append(actual_difference - previous_difference)
            previous_difference = (
                row["R77_Post_Recovery_Departure_Delay_Hours"]
                - row["R76_Post_Recovery_Departure_Delay_Hours"]
            )
    divergence_error = np.asarray(pre_divergence_errors, dtype=float)
    divergence_fail = int((np.abs(divergence_error) > TOL).sum())
    add_check(checks, "Cross-model pre-delay differences reconcile to prior post-delay differences",
              divergence_fail == 0 and bool((shock_mismatch <= TOL).all()),
              f"recurrence_failures={divergence_fail}; shock_mismatches={(shock_mismatch > TOL).sum()}",
              "0 recurrence failures; 0 shock mismatches",
              "The same current shock is added to each model's own previous post-recovery delay.")

    valid["Pre_Delay_Difference_R77_minus_R76_Hours"] = (
        valid["R77_Pre_Recovery_Delay_Hours"] - valid["R76_Pre_Recovery_Delay_Hours"])
    valid["Recovery_Reduction_Hours"] = (
        valid["R76_Recovery_Hours"] - valid["R77_Bounded_Recovery_Hours"])
    valid["Recovery_Excess_Over_R76_Hours"] = (
        valid["R77_Bounded_Recovery_Hours"] - valid["R76_Recovery_Hours"])
    valid["Elapsed_Time_Cap_Excess_Hours"] = (
        valid["R77_Bounded_Recovery_Hours"] - valid["Observed_Inter_Call_Elapsed_Hours"])
    valid["Pre_Delay_Cap_Excess_Hours"] = (
        valid["R77_Bounded_Recovery_Hours"] - valid["R77_Pre_Recovery_Delay_Hours"])
    paired.drop(columns=["_merge"], inplace=True)
    paired.to_csv(OUT["pair"], index=False)
    pd.DataFrame(checks).to_csv(OUT["checks"], index=False)

    report += [
        "PAIRING SUMMARY", f"Script76 rows: {len(r76)}", f"Script77 rows: {len(r77)}",
        f"Matched rows: {int(matched.sum())}", f"Missing in Script77: {miss}",
        f"Extra in Script77: {extra}", "",
        "SEPARATE SEQUENTIAL RECURRENCE AUDITS",
        f"Script76: {a76}", f"Script77: {a77}", "",
        "CROSS-MODEL PATH DIFFERENCE",
        f"Pre-delay mismatches above tolerance: {int((valid['Pre_Delay_Difference_R77_minus_R76_Hours'].abs() > TOL).sum())}",
        f"Mean R77-R76 pre-delay difference: {valid['Pre_Delay_Difference_R77_minus_R76_Hours'].mean():.6f} hours",
        f"Maximum absolute pre-delay difference: {valid['Pre_Delay_Difference_R77_minus_R76_Hours'].abs().max():.6f} hours",
        f"Cross-model recurrence failures: {divergence_fail}",
        f"Shock mismatches: {int((shock_mismatch > TOL).sum())}", "",
        "READINESS CHECKS",
        f"{sum(c['Passed'] for c in checks)}/{len(checks)} passed; {sum(not c['Passed'] for c in checks)} failed.",
        pd.DataFrame(checks).to_string(index=False), "",
        "INTERPRETATION AND LIMITATIONS",
        "- Script76 and Script77 pre-recovery delays are not required to be equal: each follows its own prior post-recovery delay.",
        "- Script77 additionally caps requested recovery by observed inter-call elapsed time; this can cause the two delay paths to diverge.",
        "- Observed inter-call elapsed time may include sailing, anchorage, waiting, operations and data gaps; it is not established schedule slack.",
        "- Passing checks do not establish physical or operational feasibility.",
        "- No actual Hormuz transit, route access, port capacity, cost, fuel or emissions is established.",
        "- This diagnostic does not approve policies, estimands, censoring or experiment execution.",
        "- No simulation is run and no upstream input is modified.", "",
        "OUTPUTS", f"- {OUT['pair'].relative_to(ROOT)}",
        f"- {OUT['checks'].relative_to(ROOT)}", f"- {OUT['report'].relative_to(ROOT)}",
    ]
    OUT["report"].write_text("\n".join(report), encoding="utf-8")
    passed = sum(c["Passed"] for c in checks)
    print("=" * 78)
    print("SCRIPT 95 v4 — SEPARATE SCRIPT76/SCRIPT77 RECURRENCE RECONCILIATION")
    print("=" * 78)
    print(f"Script76 rows: {len(r76)}; Script77 rows: {len(r77)}")
    print(f"Matched rows: {int(matched.sum())}")
    print(f"Readiness checks: {passed}/{len(checks)} passed; {len(checks)-passed} failed")
    print("Simulation executed: NO")
    print("Execution authorized: NO")
    print(f"Report: {OUT['report']}")
    print("Diagnostic only; no operational validation.")
    return 0 if all(c["Passed"] for c in checks) else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"SCRIPT95 ERROR: {type(exc).__name__}: {exc}")
        raise
