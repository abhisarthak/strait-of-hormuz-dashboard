#!/usr/bin/env python3
# Script 74 — Delay Propagation Engine Verification and Controlled Unit Tests
# Run from project root:
#   python src/74_delay_propagation_engine_verification.py
# This verifies the Script 73 zero-shock baseline and tests synthetic positive
# shocks/recovery. It does not model physical routes, actual Hormuz transit,
# berth capacity, or real disruption events.

from __future__ import annotations
import argparse
import sys
import traceback
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

TABLE_DIR = Path("outputs/tables")
REPORT_DIR = Path("outputs/reports")
S73_FILE = "73_call_level_baseline_propagation_register.csv"
REQUIRED_S73 = [
    "Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised",
    "Simulated_Arrival_Delay_Hours", "Simulated_Departure_Delay_Hours",
    "Arrival_Timestamp_Match", "Departure_Timestamp_Match",
]
TOL = 1e-9


def propagate_vessel_sequence(
    calls: pd.DataFrame,
    transit_shocks: dict[str, float] | None = None,
    port_call_shocks: dict[str, float] | None = None,
    recovery_advances: dict[str, float] | None = None,
    initial_departure_delay: float = 0.0,
) -> pd.DataFrame:
    # For call k:
    # arrival_delay[k] = previous_departure_delay + transit_shock[k]
    # pre_recovery_departure[k] = arrival_delay[k] + port_call_shock[k]
    # recovery_applied[k] = min(requested_recovery, pre_recovery_departure)
    # departure_delay[k] = pre_recovery_departure[k] - recovery_applied[k]
    transit_shocks = transit_shocks or {}
    port_call_shocks = port_call_shocks or {}
    recovery_advances = recovery_advances or {}
    required = ["Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised"]
    missing = [c for c in required if c not in calls.columns]
    if missing:
        raise ValueError(f"Missing sequence columns: {missing}")
    if calls.empty:
        raise ValueError("A vessel sequence cannot be empty.")
    if calls["Simulation_Record_ID"].isna().any():
        raise ValueError("Simulation_Record_ID cannot be null.")
    if calls["Simulation_Record_ID"].duplicated().any():
        raise ValueError("Simulation_Record_ID must be unique within a sequence.")
    previous = float(initial_departure_delay)
    if not np.isfinite(previous) or previous < 0:
        raise ValueError("Initial departure delay must be finite and non-negative.")

    records = []
    for row in calls.itertuples(index=False):
        call_id = str(row.Simulation_Record_ID)
        vessel = str(row.IMO_Normalised)
        port = str(row.UNLOCODE_Normalised)
        transit = float(transit_shocks.get(call_id, 0.0))
        port_shock = float(port_call_shocks.get(call_id, 0.0))
        requested_recovery = float(recovery_advances.get(call_id, 0.0))
        for label, value in [
            ("transit shock", transit),
            ("port-call shock", port_shock),
            ("recovery advance", requested_recovery),
        ]:
            if not np.isfinite(value) or value < 0:
                raise ValueError(f"{label} for {call_id} must be finite and non-negative.")

        arrival_delay = previous + transit
        pre_recovery_departure = arrival_delay + port_shock
        recovery_applied = min(requested_recovery, pre_recovery_departure)
        departure_delay = pre_recovery_departure - recovery_applied
        records.append({
            "Simulation_Record_ID": call_id,
            "IMO_Normalised": vessel,
            "UNLOCODE_Normalised": port,
            "Previous_Departure_Delay_Hours": previous,
            "Transit_Elapsed_Time_Shock_Hours": transit,
            "Simulated_Arrival_Delay_Hours": arrival_delay,
            "Port_Call_Duration_Shock_Hours": port_shock,
            "Pre_Recovery_Departure_Delay_Hours": pre_recovery_departure,
            "Recovery_Requested_Hours": requested_recovery,
            "Recovery_Applied_Hours": recovery_applied,
            "Simulated_Departure_Delay_Hours": departure_delay,
        })
        previous = departure_delay

    result = pd.DataFrame(records)
    if (result[["Simulated_Arrival_Delay_Hours",
                "Simulated_Departure_Delay_Hours"]] < -TOL).any().any():
        raise AssertionError("Propagation produced a negative delay.")
    return result


def sequence(vessel: str, calls: list[tuple[str, str]]) -> pd.DataFrame:
    return pd.DataFrame([
        {"Simulation_Record_ID": call_id, "IMO_Normalised": vessel,
         "UNLOCODE_Normalised": port}
        for call_id, port in calls
    ])


def check_close(actual: float, expected: float, label: str) -> None:
    if not np.isclose(actual, expected, atol=TOL, rtol=0):
        raise AssertionError(f"{label}: got {actual}; expected {expected}")


def run_test(test_id: str, description: str, fn) -> dict[str, Any]:
    try:
        detail = fn()
        return {"Test_ID": test_id, "Description": description,
                "Passed": True, "Observed": detail, "Error": ""}
    except Exception as exc:
        return {"Test_ID": test_id, "Description": description,
                "Passed": False, "Observed": "FAIL",
                "Error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.expanduser().resolve()
    tables = root / TABLE_DIR
    reports = root / REPORT_DIR
    reports.mkdir(parents=True, exist_ok=True)
    baseline_path = tables / S73_FILE
    if not baseline_path.exists():
        raise FileNotFoundError(
            f"Missing {baseline_path}. Run Script 73 successfully first.")
    baseline = pd.read_csv(baseline_path, low_memory=False)
    missing = [c for c in REQUIRED_S73 if c not in baseline.columns]
    if missing:
        raise ValueError(f"Script 73 output missing columns: {missing}")

    regression = []
    def add_regression(cid, description, passed, observed, expected):
        regression.append({
            "Check_ID": cid, "Description": description,
            "Passed": bool(passed), "Observed": str(observed),
            "Expected": str(expected),
        })

    add_regression("S73_CALL_COUNT", "Script 73 has 604 call rows",
                   len(baseline) == 604, len(baseline), 604)
    add_regression("S73_UNIQUE_CALL_IDS", "Call IDs are unique",
                   baseline["Simulation_Record_ID"].is_unique,
                   baseline["Simulation_Record_ID"].nunique(), len(baseline))
    for col in ["Simulated_Arrival_Delay_Hours",
                "Simulated_Departure_Delay_Hours"]:
        vals = pd.to_numeric(baseline[col], errors="coerce")
        add_regression(f"S73_ZERO_{col.upper()}",
                       f"{col} are all exactly zero",
                       bool(vals.notna().all() and (vals == 0).all()),
                       int((vals.fillna(np.inf) != 0).sum()), 0)
    for col in ["Arrival_Timestamp_Match", "Departure_Timestamp_Match"]:
        vals = baseline[col].astype(str).str.strip().str.lower()
        count_true = int(vals.isin(["true", "1"]).sum())
        add_regression(f"S73_{col.upper()}",
                       f"{col} is true for all calls",
                       count_true == len(vals), count_true, len(vals))
    regression_df = pd.DataFrame(regression)

    tests = []

    def t01():
        out = propagate_vessel_sequence(sequence(
            "V1", [("A1", "P1"), ("A2", "P2"), ("A3", "P2")]))
        check_close(out["Simulated_Arrival_Delay_Hours"].abs().max(), 0, "arrival")
        check_close(out["Simulated_Departure_Delay_Hours"].abs().max(), 0, "departure")
        return "All delays zero across three calls"

    def t02():
        out = propagate_vessel_sequence(
            sequence("V1", [("B1", "P1"), ("B2", "P2"), ("B3", "P3")]),
            transit_shocks={"B2": 24})
        assert np.allclose(out["Simulated_Arrival_Delay_Hours"], [0, 24, 24])
        assert np.allclose(out["Simulated_Departure_Delay_Hours"], [0, 24, 24])
        return "24 h transit shock at B2 persists through B3"

    def t03():
        out = propagate_vessel_sequence(
            sequence("V1", [("C1", "P1"), ("C2", "P2"), ("C3", "P3")]),
            port_call_shocks={"C2": 12})
        assert np.allclose(out["Simulated_Departure_Delay_Hours"], [0, 12, 12])
        return "12 h port-call duration shock at C2 propagates to C3"

    def t04():
        out = propagate_vessel_sequence(
            sequence("V1", [("D1", "P1"), ("D2", "P2"), ("D3", "P3")]),
            transit_shocks={"D2": 10, "D3": 7},
            port_call_shocks={"D2": 5})
        assert np.allclose(out["Simulated_Arrival_Delay_Hours"], [0, 10, 22])
        assert np.allclose(out["Simulated_Departure_Delay_Hours"], [0, 15, 22])
        return "Arrival [0,10,22]; departure [0,15,22]"

    def t05():
        out = propagate_vessel_sequence(
            sequence("V1", [("E1", "P1"), ("E2", "P1"), ("E3", "P2")]),
            port_call_shocks={"E1": 8})
        assert np.allclose(out["Simulated_Departure_Delay_Hours"], [8, 8, 8])
        return "8 h delay persists across same-port and next-port links"

    def t06():
        a = propagate_vessel_sequence(
            sequence("VA", [("F1", "P1"), ("F2", "P2")]),
            transit_shocks={"F2": 18})
        b = propagate_vessel_sequence(
            sequence("VB", [("G1", "P1"), ("G2", "P2")]))
        check_close(a.iloc[-1]["Simulated_Departure_Delay_Hours"], 18, "VA")
        check_close(b.iloc[-1]["Simulated_Departure_Delay_Hours"], 0, "VB")
        return "18 h shock on VA leaves VB unaffected"

    def t07():
        out = propagate_vessel_sequence(
            sequence("V1", [("H1", "P1"), ("H2", "P2"), ("H3", "P3")]),
            transit_shocks={"H2": 24}, recovery_advances={"H2": 6})
        assert np.allclose(out["Simulated_Departure_Delay_Hours"], [0, 18, 18])
        return "24 h shock less 6 h recovery leaves 18 h"

    def t08():
        out = propagate_vessel_sequence(
            sequence("V1", [("I1", "P1"), ("I2", "P2")]),
            recovery_advances={"I1": 20, "I2": 5})
        assert (out["Simulated_Departure_Delay_Hours"] >= 0).all()
        check_close(out.iloc[0]["Recovery_Applied_Hours"], 0, "applied recovery")
        return "Recovery is capped at available delay; no negative delay"

    def t09():
        try:
            propagate_vessel_sequence(
                sequence("V1", [("J1", "P1")]), transit_shocks={"J1": -1})
        except ValueError:
            return "Negative shock rejected"
        raise AssertionError("Negative shock was accepted")

    def t10():
        try:
            propagate_vessel_sequence(
                sequence("V1", [("K1", "P1")]), recovery_advances={"K1": -1})
        except ValueError:
            return "Negative recovery rejected"
        raise AssertionError("Negative recovery was accepted")

    specs = [
        ("T01", "Zero-shock identity", t01),
        ("T02", "Single transit shock propagation", t02),
        ("T03", "Port-call duration shock propagation", t03),
        ("T04", "Multiple shocks accumulate across calls", t04),
        ("T05", "Same-port sequence propagation", t05),
        ("T06", "Vessel sequences are independent", t06),
        ("T07", "Recovery reduces propagated delay", t07),
        ("T08", "Recovery cannot create negative delay", t08),
        ("T09", "Negative disruption input rejected", t09),
        ("T10", "Negative recovery input rejected", t10),
    ]
    for tid, desc, fn in specs:
        tests.append(run_test(tid, desc, fn))
    tests_df = pd.DataFrame(tests)

    test_spec = pd.DataFrame([
        ["T01", "All shocks/recovery zero", "All call delays zero"],
        ["T02", "24 h transit shock at call 2", "Call 2 onward: 24 h"],
        ["T03", "12 h port-call shock at call 2", "Call 2 departure onward: 12 h"],
        ["T04", "10 h transit + 5 h port-call at call 2; 7 h transit at call 3",
         "Arrival [0,10,22]; departure [0,15,22]"],
        ["T05", "8 h port-call shock at first of two same-port calls",
         "Departure delays [8,8,8]"],
        ["T06", "18 h shock on vessel A only", "Vessel B remains at zero"],
        ["T07", "24 h shock and 6 h recovery", "Residual delay 18 h"],
        ["T08", "Recovery requested with zero delay", "Applied recovery zero"],
        ["T09", "Negative shock", "ValueError"],
        ["T10", "Negative recovery", "ValueError"],
    ], columns=["Test_ID", "Test_Input", "Expected_Result"])

    regression_df["Overall_Status"] = np.where(regression_df["Passed"], "PASS", "FAIL")
    tests_df["Overall_Status"] = np.where(tests_df["Passed"], "PASS", "FAIL")
    overall = bool(regression_df["Passed"].all() and tests_df["Passed"].all())

    tables.mkdir(parents=True, exist_ok=True)
    regression_df.to_csv(tables / "74_script73_baseline_regression_checks.csv", index=False)
    tests_df.to_csv(tables / "74_delay_propagation_unit_test_results.csv", index=False)
    test_spec.to_csv(tables / "74_delay_propagation_test_specification.csv", index=False)

    failed = []
    failed += [
        f"- {r.Check_ID}: observed={r.Observed}; expected={r.Expected}"
        for r in regression_df.loc[~regression_df["Passed"]].itertuples(index=False)]
    failed += [
        f"- {r.Test_ID}: {r.Error or r.Observed}"
        for r in tests_df.loc[~tests_df["Passed"]].itertuples(index=False)]

    report = [
        "SCRIPT 74 — DELAY PROPAGATION ENGINE VERIFICATION",
        "=" * 66,
        f"Project root: {root}",
        f"Script 73 baseline rows checked: {len(baseline)}",
        f"Script 73 regression checks: {int(regression_df['Passed'].sum())}/{len(regression_df)}",
        f"Synthetic unit tests: {int(tests_df['Passed'].sum())}/{len(tests_df)}",
        f"Total checks: {int(regression_df['Passed'].sum() + tests_df['Passed'].sum())}/{len(regression_df) + len(tests_df)}",
        f"Overall status: {'PASS' if overall else 'FAIL'}",
        "",
        "RECURRENCE TESTED",
        "arrival_delay[k] = previous_departure_delay[k-1] + transit_shock[k]",
        "pre_recovery_departure[k] = arrival_delay[k] + port_call_duration_shock[k]",
        "recovery_applied[k] = min(recovery_requested[k], pre_recovery_departure[k])",
        "departure_delay[k] = pre_recovery_departure[k] - recovery_applied[k]",
        "",
        "LIMITATIONS",
        "- Synthetic shock values are test inputs, not empirically estimated magnitudes.",
        "- Transit elapsed-time shock is not automatically a pure sailing-time shock.",
        "- Port-call duration shock is not automatically a berth-processing shock.",
        "- Bounded recovery is a mathematical constraint, not proof of operational feasibility.",
        "- This script does not run a disruption experiment on the historical 604 calls.",
        "- No physical route, Hormuz transit, berth capacity, or actual recovery capability is inferred.",
        "",
        "FAILED CHECKS",
    ] + (failed if failed else ["None."]) + [
        "",
        "OUTPUTS",
        "- outputs/tables/74_script73_baseline_regression_checks.csv",
        "- outputs/tables/74_delay_propagation_unit_test_results.csv",
        "- outputs/tables/74_delay_propagation_test_specification.csv",
        "- outputs/reports/74_delay_propagation_engine_verification_report.txt",
    ]
    report_path = reports / "74_delay_propagation_engine_verification_report.txt"
    report_path.write_text("\\n".join(report) + "\\n", encoding="utf-8")
    print("\\n".join(report))
    if not overall:
        print("\\nFAILED: inspect outputs before proceeding.", file=sys.stderr)
        return 2
    print("\\nSUCCESS: Script 74 baseline regression and synthetic tests passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\\nSCRIPT 74 FAILED: {exc}", file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(1)
