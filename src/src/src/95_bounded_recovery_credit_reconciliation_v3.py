#!/usr/bin/env python3
"""
SCRIPT 95 v3 — SCRIPT76/SCRIPT77 BOUNDED RECOVERY CREDIT RECONCILIATION

Purpose
-------
Record-level diagnostic comparison of Script76 requested/applied recovery and
Script77 bounded recovery. This script does not modify upstream files or run
the simulation.

Important interpretation
------------------------
Script77's elapsed-time cap is a mathematical sensitivity bound based on
observed inter-call elapsed time. It is NOT established schedule slack.
Passing checks do not establish operational feasibility or actual Hormuz transit.
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

R76_RECOVERY_CANDIDATES = [
    "Recovery_Advance_Hours", "Applied_Recovery_Hours",
    "Recovery_Credit_Hours", "Recovery_Hours",
]
R77_REQUESTED_CANDIDATES = [
    "Script76_Requested_Recovery_Hours",
    "Requested_Recovery_Hours", "Requested_Recovery_Advance_Hours",
]
R77_RECOVERY_CANDIDATES = [
    "Script77_Bounded_Recovery_Hours",
    "Bounded_Recovery_Advance_Hours", "Bounded_Recovery_Hours",
    "Recovery_Advance_Hours", "Applied_Recovery_Hours",
    "Recovery_Credit_Hours", "Recovery_Hours",
]
R76_PRE_DELAY_CANDIDATES = ["Delay_Before_Recovery_Hours", "Pre_Recovery_Delay_Hours"]
R77_PRE_DELAY_CANDIDATES = [
    "Script77_Delay_Before_Recovery_Hours",
    "Delay_Before_Recovery_Hours",
    "Pre_Recovery_Delay_Hours",
]
ELAPSED_CANDIDATES = [
    "Observed_Inter_Call_Elapsed_Cap_Hours",
    "Available_Elapsed_Time_Hours",
    "Observed_Inter_Call_Elapsed_Hours",
    "Inter_Call_Elapsed_Hours",
    "Observed_Elapsed_Hours",
]
R77_POST_DELAY_CANDIDATES = [
    "Script77_Departure_Delay_Hours",
    "Post_Recovery_Departure_Delay_Hours",
    "Departure_Delay_After_Recovery_Hours",
    "Simulated_Departure_Delay_Hours",
]


def read_csv(path, label):
    if not path.exists():
        raise FileNotFoundError(f"Missing {label} input: {path}")
    return pd.read_csv(path, low_memory=False)


def pick_column(df, candidates):
    for name in candidates:
        if name in df.columns:
            return name
    return None


def normalized_key(s):
    return s.astype("string").fillna("<NA>").str.strip()


def add_check(rows, name, passed, observed, expected, interpretation):
    rows.append({
        "Check": name,
        "Passed": bool(passed),
        "Observed": str(observed),
        "Expected": str(expected),
        "Interpretation": interpretation,
    })


def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    checks = []
    report = [
        "SCRIPT 95 — SCRIPT76/SCRIPT77 BOUNDED RECOVERY CREDIT RECONCILIATION",
        "=" * 82, "",
        "PURPOSE",
        "Record-level reconciliation of Script76 and Script77 recovery outputs.",
        "Diagnostic only; no simulation, approval, or upstream modification.", "",
    ]

    r76 = read_csv(INPUTS["r76"], "Script76 call-level recovery")
    r77 = read_csv(INPUTS["r77"], "Script77 call-level bounded recovery")

    report += [
        "INPUT INVENTORY",
        f"Script76: {len(r76)} rows; {len(r76.columns)} columns",
        f"Script77: {len(r77)} rows; {len(r77.columns)} columns", "",
        "COLUMN INVENTORY",
        "Script76: " + ", ".join(map(str, r76.columns)),
        "Script77: " + ", ".join(map(str, r77.columns)), "",
    ]

    keymap = {}
    for group, candidates in KEY_GROUPS.items():
        c76 = pick_column(r76, candidates)
        c77 = pick_column(r77, candidates)
        if c76 and c77:
            keymap[group] = (c76, c77)

    required_groups = ["scenario", "policy", "vessel", "call"]
    missing_groups = [g for g in required_groups if g not in keymap]
    add_check(
        checks, "Scenario/policy/vessel/call keys available in both files",
        not missing_groups, missing_groups or "All four key groups found",
        "All four key groups", "Exact record pairing requires shared identifiers."
    )
    if missing_groups:
        report += ["KEY DISCOVERY FAILED", f"Missing key groups: {missing_groups}",
                   "No pairing attempted. Inspect the column inventories above.", ""]
        pd.DataFrame(checks).to_csv(OUT["checks"], index=False)
        OUT["report"].write_text("\n".join(report), encoding="utf-8")
        print("Script95 stopped safely: key columns could not be identified.")
        print("See outputs/reports/95_bounded_recovery_reconciliation_report.txt")
        return 2

    r76 = r76.copy()
    r77 = r77.copy()
    for group, (c76, c77) in keymap.items():
        r76[f"__key_{group}"] = normalized_key(r76[c76])
        r77[f"__key_{group}"] = normalized_key(r77[c77])
    keys = [f"__key_{g}" for g in required_groups]

    duplicate76 = int(r76.duplicated(keys).sum())
    duplicate77 = int(r77.duplicated(keys).sum())
    add_check(checks, "Script76 composite keys unique", duplicate76 == 0,
              duplicate76, 0, "Duplicate keys prevent one-to-one record reconciliation.")
    add_check(checks, "Script77 composite keys unique", duplicate77 == 0,
              duplicate77, 0, "Duplicate keys prevent one-to-one record reconciliation.")

    r76_rec_col = pick_column(r76, R76_RECOVERY_CANDIDATES)
    r77_rec_col = pick_column(r77, R77_RECOVERY_CANDIDATES)
    r77_requested_col = pick_column(r77, R77_REQUESTED_CANDIDATES)
    r76_delay_col = pick_column(r76, R76_PRE_DELAY_CANDIDATES)
    r77_delay_col = pick_column(r77, R77_PRE_DELAY_CANDIDATES)
    elapsed_col = pick_column(r77, ELAPSED_CANDIDATES) or pick_column(r76, ELAPSED_CANDIDATES)
    post_col = pick_column(r77, R77_POST_DELAY_CANDIDATES)

    required_fields = {
        "Script76 recovery": r76_rec_col,
        "Script77 bounded recovery": r77_rec_col,
        "Script77 requested recovery (if exported)": r77_requested_col,
        "Script76 pre-recovery delay": r76_delay_col,
        "Script77 pre-recovery delay": r77_delay_col,
        "Observed inter-call elapsed time": elapsed_col,
    }
    missing_fields = [k for k, v in required_fields.items()
                      if v is None and k != "Script77 requested recovery (if exported)"]
    add_check(checks, "Recovery, pre-delay and elapsed-time fields identified",
              not missing_fields, missing_fields or required_fields,
              "All five fields", "No semantic substitute is silently assumed.")
    if missing_fields:
        report += ["FIELD DISCOVERY FAILED", f"Missing fields: {missing_fields}",
                   "No bounded-credit conclusion can be made until aliases are mapped.", ""]
        pd.DataFrame(checks).to_csv(OUT["checks"], index=False)
        OUT["report"].write_text("\n".join(report), encoding="utf-8")
        print("Script95 stopped safely: required fields not identified.")
        print("Inspect the column inventory in the report and share it.")
        return 2

    left = r76[keys + [r76_rec_col, r76_delay_col]].copy()
    left = left.rename(columns={r76_rec_col: "R76_Recovery_Hours",
                                r76_delay_col: "R76_Pre_Recovery_Delay_Hours"})
    right_cols = keys + [r77_rec_col, r77_delay_col, elapsed_col]
    if r77_requested_col and r77_requested_col not in right_cols:
        right_cols.append(r77_requested_col)
    if post_col and post_col not in right_cols:
        right_cols.append(post_col)
    right = r77[right_cols].copy()
    rename_right = {
        r77_rec_col: "R77_Bounded_Recovery_Hours",
        r77_delay_col: "R77_Pre_Recovery_Delay_Hours",
        elapsed_col: "Observed_Inter_Call_Elapsed_Hours",
    }
    if r77_requested_col:
        rename_right[r77_requested_col] = "R77_Requested_Recovery_Hours"
    right = right.rename(columns=rename_right)
    if post_col:
        right = right.rename(columns={post_col: "R77_Post_Recovery_Departure_Delay_Hours"})

    paired = left.merge(right, on=keys, how="outer", indicator=True, validate="one_to_one")
    matched = paired["_merge"].eq("both")
    missing77 = int(paired["_merge"].eq("left_only").sum())
    extra77 = int(paired["_merge"].eq("right_only").sum())
    add_check(checks, "Script76 and Script77 records pair one-to-one",
              missing77 == 0 and extra77 == 0,
              f"missing_in_77={missing77}; extra_in_77={extra77}",
              "0 missing; 0 extra", "Pairing uses scenario, policy, vessel and call identifiers.")

    numeric_cols = [
        "R76_Recovery_Hours", "R76_Pre_Recovery_Delay_Hours",
        "R77_Bounded_Recovery_Hours", "R77_Pre_Recovery_Delay_Hours",
        "Observed_Inter_Call_Elapsed_Hours",
    ]
    for c in numeric_cols:
        paired[c] = pd.to_numeric(paired[c], errors="coerce")
    paired["Recovery_Reduction_Hours"] = (
        paired["R76_Recovery_Hours"] - paired["R77_Bounded_Recovery_Hours"]
    )
    if "R77_Requested_Recovery_Hours" in paired.columns:
        paired["Requested_vs_R76_Difference_Hours"] = (
            paired["R77_Requested_Recovery_Hours"] - paired["R76_Recovery_Hours"]
        )
    paired["Recovery_Excess_Over_R76_Hours"] = (
        paired["R77_Bounded_Recovery_Hours"] - paired["R76_Recovery_Hours"]
    )
    paired["Elapsed_Time_Cap_Excess_Hours"] = (
        paired["R77_Bounded_Recovery_Hours"] -
        paired["Observed_Inter_Call_Elapsed_Hours"]
    )
    paired["Pre_Delay_Cap_Excess_Hours"] = (
        paired["R77_Bounded_Recovery_Hours"] -
        paired["R77_Pre_Recovery_Delay_Hours"]
    )

    tol = 0.001
    valid = paired.loc[matched].copy()
    nonnegative = (
        valid["R77_Bounded_Recovery_Hours"].notna().all()
        and (valid["R77_Bounded_Recovery_Hours"] >= -tol).all()
    )
    add_check(checks, "Script77 bounded recovery is nonnegative",
              nonnegative, float(valid["R77_Bounded_Recovery_Hours"].min()),
              ">= 0", "Recovery credit cannot be negative.")

    exceeds_r76 = valid["Recovery_Excess_Over_R76_Hours"] > tol
    add_check(checks, "Script77 bounded recovery never exceeds Script76 recovery",
              not exceeds_r76.any(), int(exceeds_r76.sum()), 0,
              "Record-level bounded credit must not exceed original Script76 credit.")
    if "Requested_vs_R76_Difference_Hours" in valid.columns:
        req_err = valid["Requested_vs_R76_Difference_Hours"].abs()
        add_check(checks, "Script77 exported requested recovery matches Script76",
                  bool((req_err <= tol).all()), float(req_err.max()),
                  f"<= {tol} hours",
                  "Direct reconciliation of Script77's exported requested-credit field.")

    exceeds_elapsed = valid["Elapsed_Time_Cap_Excess_Hours"] > tol
    add_check(checks, "Script77 recovery respects observed elapsed-time cap",
              not exceeds_elapsed.any(), int(exceeds_elapsed.sum()), 0,
              "Mathematical elapsed-time bound only; not validated schedule slack.")

    exceeds_delay = valid["Pre_Delay_Cap_Excess_Hours"] > tol
    add_check(checks, "Script77 recovery does not exceed pre-recovery delay",
              not exceeds_delay.any(), int(exceeds_delay.sum()), 0,
              "Recovery cannot exceed delay available before recovery.")

    delay_match = np.isclose(
        valid["R76_Pre_Recovery_Delay_Hours"],
        valid["R77_Pre_Recovery_Delay_Hours"],
        atol=tol, rtol=0, equal_nan=False
    )
    add_check(checks, "Pre-recovery delay agrees across Script76 and Script77",
              bool(delay_match.all()), int((~delay_match).sum()), 0,
              "Same counterfactual record should enter bounded recovery with same delay.")

    if "R77_Post_Recovery_Departure_Delay_Hours" in valid.columns:
        valid["Expected_R77_Post_Delay_Hours"] = (
            valid["R77_Pre_Recovery_Delay_Hours"] -
            valid["R77_Bounded_Recovery_Hours"]
        )
        valid["Post_Delay_Arithmetic_Error_Hours"] = (
            valid["R77_Post_Recovery_Departure_Delay_Hours"] -
            valid["Expected_R77_Post_Delay_Hours"]
        )
        err = valid["Post_Delay_Arithmetic_Error_Hours"].abs()
        add_check(checks, "Script77 post-recovery departure delay arithmetic",
                  bool((err <= tol).all()), float(err.max()), f"<= {tol} hours",
                  "Uses Script77-specific pre-delay field first; checks pre-delay minus bounded recovery against Script77 reported post-delay.")
    else:
        add_check(checks, "Script77 post-recovery delay field available",
                  False, "FIELD_NOT_FOUND", "Post-recovery delay column",
                  "Credit reconciliation can proceed, but post-delay arithmetic remains unverified.")

    paired.drop(columns=["_merge"], inplace=True)
    paired.to_csv(OUT["pair"], index=False)
    checks_df = pd.DataFrame(checks)
    checks_df.to_csv(OUT["checks"], index=False)

    report += [
        "KEY FIELDS",
        str(keymap), "",
        "RECOVERY FIELDS",
        f"Script76 recovery: {r76_rec_col}",
        f"Script77 bounded recovery: {r77_rec_col}",
        f"Script77 requested recovery: {r77_requested_col}",
        f"Script76 pre-delay: {r76_delay_col}",
        f"Script77 pre-delay: {r77_delay_col}",
        f"Elapsed-time cap: {elapsed_col}",
        f"Script77 post-delay: {post_col}", "",
        "PAIRING SUMMARY",
        f"Script76 rows: {len(r76)}",
        f"Script77 rows: {len(r77)}",
        f"Matched rows: {int(matched.sum())}",
        f"Missing in Script77: {missing77}",
        f"Extra in Script77: {extra77}", "",
        "RECOVERY RECONCILIATION SUMMARY",
        f"Maximum Script77 recovery above Script76: {valid['Recovery_Excess_Over_R76_Hours'].max():.6f} hours",
        f"Maximum Script77 recovery above elapsed cap: {valid['Elapsed_Time_Cap_Excess_Hours'].max():.6f} hours",
        f"Maximum Script77 recovery above pre-delay: {valid['Pre_Delay_Cap_Excess_Hours'].max():.6f} hours",
        f"Mean recovery reduction vs Script76: {valid['Recovery_Reduction_Hours'].mean():.6f} hours", "",
        "READINESS CHECKS",
        f"{int(checks_df['Passed'].sum())}/{len(checks_df)} passed; {int((~checks_df['Passed']).sum())} failed.",
        checks_df.to_string(index=False), "",
        "INTERPRETATION AND LIMITATIONS",
        "- Script77 elapsed-time cap is a mathematical sensitivity bound, not established schedule slack.",
        "- Observed inter-call elapsed time may include sailing, anchorage, waiting, operations and data gaps.",
        "- Passing checks do not establish physical or operational feasibility.",
        "- No actual Hormuz transit, route access, port capacity, cost, fuel or emissions is established.",
        "- This script does not approve policies, estimands, censoring or experiment execution.",
        "- No simulation is run and no upstream input is modified.", "",
        "OUTPUTS",
        f"- {OUT['pair'].relative_to(ROOT)}",
        f"- {OUT['checks'].relative_to(ROOT)}",
        f"- {OUT['report'].relative_to(ROOT)}",
    ]
    OUT["report"].write_text("\n".join(report), encoding="utf-8")
    print("=" * 78)
    print("SCRIPT 95 v3 — SCRIPT76/SCRIPT77 BOUNDED RECOVERY CREDIT RECONCILIATION")
    print("=" * 78)
    print(f"Script76 rows: {len(r76)}")
    print(f"Script77 rows: {len(r77)}")
    print(f"Matched rows: {int(matched.sum())}")
    print(f"Readiness checks: {int(checks_df['Passed'].sum())}/{len(checks_df)} passed; "
          f"{int((~checks_df['Passed']).sum())} failed")
    print("Simulation executed: NO")
    print("Execution authorized: NO")
    print(f"Report: {OUT['report']}")
    print("NOTE: This is a diagnostic reconciliation, not operational validation.")
    return 0 if checks_df["Passed"].all() else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"SCRIPT95 ERROR: {type(exc).__name__}: {exc}")
        raise
