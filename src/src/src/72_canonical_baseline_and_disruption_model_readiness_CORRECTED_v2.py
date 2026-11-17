#!/usr/bin/env python3
"""
SCRIPT 72 v2: CORRECTED BASELINE CONTRACT, VESSEL SEQUENCING,
AND EXPLICIT DELAY-PROPAGATION SPECIFICATION

This is a read-only specification and audit. It does not modify Scripts 19-71,
any upstream data, or any researcher decision register. It does not execute
disruption or recovery experiments.

Run from the project root:
    python src/72_canonical_baseline_and_disruption_model_readiness_CORRECTED_v2.py

Required Script19 inputs:
    data/simulation_inputs/19_historical_arrival_schedule.csv
    data/simulation_inputs/19_vessel_parameters.csv
    data/simulation_inputs/19_port_parameters.csv
    data/simulation_inputs/19_port_service_parameters.csv
    data/simulation_inputs/19_interport_time_parameters.csv
    data/simulation_inputs/19_observed_interport_transitions.csv

Known source keys from Script19:
    Vessel parameters: IMO_Normalised
    Port parameters: UNLOCODE_Normalised
    Port service parameters: UNLOCODE_Normalised
    Inter-port parameters: Previous_Port, Next_Port
    Observed transitions: IMO_Normalised, Previous_Port, Next_Port,
                          Elapsed_Hours_Between_Calls, Simulation_Record_ID

Outputs use the 72v2_ prefix to preserve the original Script72 outputs.
"""

from pathlib import Path
import math
import hashlib
import json
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "data" / "simulation_inputs"
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"
TABLES.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

FILES = {
    "historical_schedule": SIM / "19_historical_arrival_schedule.csv",
    "vessel_parameters": SIM / "19_vessel_parameters.csv",
    "port_parameters": SIM / "19_port_parameters.csv",
    "port_service_parameters": SIM / "19_port_service_parameters.csv",
    "interport_parameters": SIM / "19_interport_time_parameters.csv",
    "observed_transitions": SIM / "19_observed_interport_transitions.csv",
}

OUT = {
    "schema": TABLES / "72v2_source_schema_and_join_audit.csv",
    "keys": TABLES / "72v2_parameter_key_coverage.csv",
    "sequence": TABLES / "72v2_vessel_sequence_diagnostics.csv",
    "equations": TABLES / "72v2_delay_propagation_equations.csv",
    "tests": TABLES / "72v2_delay_propagation_unit_tests.csv",
    "invariants": TABLES / "72v2_baseline_invariants.csv",
    "mechanisms": TABLES / "72v2_disruption_mechanism_readiness.csv",
    "checks": TABLES / "72v2_implementation_readiness_checks.csv",
    "report": REPORTS / "72v2_canonical_baseline_and_delay_propagation_specification.txt",
}

EXPECTED_ROWS = {
    "historical_schedule": 604,
    "vessel_parameters": 155,
    "port_parameters": 19,
    "port_service_parameters": 19,
    "interport_parameters": 53,
    "observed_transitions": 271,
}

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def read_required():
    loaded = {}
    missing = []
    for key, path in FILES.items():
        if not path.exists():
            missing.append(str(path.relative_to(ROOT)))
            continue
        loaded[key] = pd.read_csv(path, low_memory=False)
    if missing:
        raise FileNotFoundError(
            "Missing required Script19 inputs:\n- " + "\n- ".join(missing)
        )
    return loaded

def require_columns(df, names, label):
    missing = [c for c in names if c not in df.columns]
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")

def norm_id(s):
    return s.astype("string").str.strip().str.upper()

def parse_schedule(df):
    required = [
        "Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised",
        "Actual_Arrival_UTC", "Actual_Departure_UTC", "Actual_Stay_Hours",
    ]
    require_columns(df, required, "19_historical_arrival_schedule.csv")
    x = df.copy()
    for c in ["Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised"]:
        x[c] = x[c].astype("string").str.strip()
    x["UNLOCODE_Normalised"] = x["UNLOCODE_Normalised"].str.upper()
    x["Actual_Arrival_UTC"] = pd.to_datetime(
        x["Actual_Arrival_UTC"], utc=True, errors="coerce"
    )
    x["Actual_Departure_UTC"] = pd.to_datetime(
        x["Actual_Departure_UTC"], utc=True, errors="coerce"
    )
    x["Actual_Stay_Hours"] = pd.to_numeric(x["Actual_Stay_Hours"], errors="coerce")
    x["Timestamp_Interval_Hours"] = (
        x["Actual_Departure_UTC"] - x["Actual_Arrival_UTC"]
    ).dt.total_seconds() / 3600.0
    x["Stay_Difference_Hours"] = (
        x["Timestamp_Interval_Hours"] - x["Actual_Stay_Hours"]
    )
    return x

def audit_parameter_keys(loaded, schedule):
    expected = {
        "vessel_parameters": ("IMO_Normalised", schedule["IMO_Normalised"]),
        "port_parameters": ("UNLOCODE_Normalised", schedule["UNLOCODE_Normalised"]),
        "port_service_parameters": ("UNLOCODE_Normalised", schedule["UNLOCODE_Normalised"]),
        "interport_parameters": (
            ("Previous_Port", "Next_Port"),
            None,
        ),
        "observed_transitions": (
            ("IMO_Normalised", "Simulation_Record_ID"),
            None,
        ),
    }
    rows = []
    detail = {}

    for artifact, (key_spec, _) in expected.items():
        df = loaded[artifact]
        keys = [key_spec] if isinstance(key_spec, str) else list(key_spec)
        missing = [k for k in keys if k not in df.columns]
        if missing:
            rows.append({
                "Artifact": artifact, "Actual_Join_Key": " | ".join(keys),
                "Rows": len(df), "Key_Null_Rows": np.nan,
                "Duplicate_Key_Rows": np.nan, "Unique_Keys": np.nan,
                "Expected_Coverage": np.nan, "Matched_Expected": np.nan,
                "Unmatched_Expected": np.nan, "Unexpected_Keys": np.nan,
                "Status": f"MISSING_KEY_COLUMNS: {missing}",
            })
            detail[artifact] = {"ok": False, "missing": missing}
            continue

        work = df.copy()
        for k in keys:
            work[k] = norm_id(work[k])
        null_mask = work[keys].isna().any(axis=1)
        dup_mask = work.duplicated(keys, keep=False)
        unique_count = len(work[keys].drop_duplicates())

        expected_coverage = matched = unmatched = unexpected = np.nan
        if artifact in ("vessel_parameters", "port_parameters", "port_service_parameters"):
            expected_series = expected[artifact][1].dropna().astype("string").str.strip().str.upper()
            source_set = set(work[keys[0]].dropna())
            expected_set = set(expected_series)
            expected_coverage = len(expected_set)
            matched = len(expected_set & source_set)
            unmatched = len(expected_set - source_set)
            unexpected = len(source_set - expected_set)
            coverage_ok = unmatched == 0
        else:
            coverage_ok = True

        ok = (
            not null_mask.any()
            and not dup_mask.any()
            and coverage_ok
        )
        rows.append({
            "Artifact": artifact, "Actual_Join_Key": " | ".join(keys),
            "Rows": len(df), "Key_Null_Rows": int(null_mask.sum()),
            "Duplicate_Key_Rows": int(dup_mask.sum()),
            "Unique_Keys": unique_count,
            "Expected_Coverage": expected_coverage,
            "Matched_Expected": matched,
            "Unmatched_Expected": unmatched,
            "Unexpected_Keys": unexpected,
            "Status": "PASS" if ok else "REVIEW",
        })
        detail[artifact] = {
            "ok": ok, "keys": keys, "rows": len(df),
            "null_rows": int(null_mask.sum()),
            "duplicate_rows": int(dup_mask.sum()),
            "unique_keys": unique_count,
            "expected_coverage": expected_coverage,
            "matched": matched, "unmatched": unmatched,
            "unexpected": unexpected,
        }

    # Confirm directed inter-port parameter keys cover observed transition pairs.
    ip = loaded["interport_parameters"].copy()
    tr = loaded["observed_transitions"].copy()
    for d in (ip, tr):
        for c in ["Previous_Port", "Next_Port"]:
            d[c] = norm_id(d[c])
    param_pair_null_rows = int(ip[["Previous_Port", "Next_Port"]].isna().any(axis=1).sum())
    observed_pair_null_rows = int(tr[["Previous_Port", "Next_Port"]].isna().any(axis=1).sum())
    param_pairs = set(map(tuple, ip[["Previous_Port", "Next_Port"]].dropna().to_numpy()))
    observed_pairs = set(map(tuple, tr[["Previous_Port", "Next_Port"]].dropna().to_numpy()))
    pair_uncovered = len(observed_pairs - param_pairs)
    pair_unused = len(param_pairs - observed_pairs)
    detail["edge_pair_coverage"] = {
        "ok": pair_uncovered == 0 and pair_unused == 0,
        "parameter_pairs": len(param_pairs),
        "observed_pairs": len(observed_pairs),
        "uncovered_observed_pairs": pair_uncovered,
        "unused_parameter_pairs": pair_unused,
        "parameter_pair_null_rows": param_pair_null_rows,
        "observed_pair_null_rows": observed_pair_null_rows,
    }
    detail["edge_pair_coverage"]["ok"] = (
        pair_uncovered == 0 and pair_unused == 0
        and param_pair_null_rows == 0 and observed_pair_null_rows == 0
    )
    rows.append({
        "Artifact": "interport_parameter_vs_observed_transition_pair_coverage",
        "Actual_Join_Key": "Previous_Port | Next_Port",
        "Rows": len(tr), "Key_Null_Rows": np.nan,
        "Duplicate_Key_Rows": np.nan, "Unique_Keys": len(observed_pairs),
        "Expected_Coverage": len(observed_pairs),
        "Matched_Expected": len(observed_pairs) - pair_uncovered,
        "Unmatched_Expected": pair_uncovered,
        "Unexpected_Keys": pair_unused,
        "Status": "PASS" if detail["edge_pair_coverage"]["ok"] else "REVIEW",
    })
    return pd.DataFrame(rows), detail

def build_vessel_sequences(schedule, observed_transitions):
    x = schedule.sort_values(
        ["IMO_Normalised", "Actual_Arrival_UTC", "Simulation_Record_ID"],
        kind="mergesort",
    ).copy()
    g = x.groupby("IMO_Normalised", sort=False, dropna=False)
    x["Next_Simulation_Record_ID"] = g["Simulation_Record_ID"].shift(-1)
    x["Next_Port"] = g["UNLOCODE_Normalised"].shift(-1)
    x["Next_Arrival_UTC"] = g["Actual_Arrival_UTC"].shift(-1)
    x["Inter_Call_Elapsed_Hours"] = (
        x["Next_Arrival_UTC"] - x["Actual_Departure_UTC"]
    ).dt.total_seconds() / 3600.0
    x["Is_Last_Call_In_Vessel_Sequence"] = x["Next_Simulation_Record_ID"].isna()
    x["Same_Port_Consecutive_Call"] = (
        x["Next_Port"].notna()
        & x["UNLOCODE_Normalised"].eq(x["Next_Port"])
    )
    x["Same_Arrival_Timestamp_Tie"] = (
        x["Next_Arrival_UTC"].notna()
        & x["Actual_Arrival_UTC"].eq(x["Next_Arrival_UTC"])
    )
    x["Negative_Inter_Call_Elapsed"] = (
        x["Inter_Call_Elapsed_Hours"].notna()
        & (x["Inter_Call_Elapsed_Hours"] < 0)
    )
    x["Zero_Inter_Call_Elapsed"] = (
        x["Inter_Call_Elapsed_Hours"].notna()
        & np.isclose(x["Inter_Call_Elapsed_Hours"], 0.0, rtol=0, atol=1e-9)
    )
    x["Distinct_Port_Nonnegative_Transition"] = (
        x["Next_Port"].notna()
        & ~x["Same_Port_Consecutive_Call"]
        & x["Inter_Call_Elapsed_Hours"].notna()
        & (x["Inter_Call_Elapsed_Hours"] >= 0)
    )
    x["Transition_Model_Status"] = np.select(
        [
            x["Is_Last_Call_In_Vessel_Sequence"],
            x["Negative_Inter_Call_Elapsed"],
            x["Same_Port_Consecutive_Call"],
            x["Distinct_Port_Nonnegative_Transition"],
        ],
        [
            "LAST_CALL_NO_SUCCESSOR",
            "BLOCKED_NEGATIVE_ELAPSED_TIME_REVIEW",
            "SAME_PORT_SEQUENCE_NO_INTERPORT_EDGE_SHOCK",
            "OBSERVED_DISTINCT_PORT_TRANSITION",
        ],
        default="UNCLASSIFIED_REVIEW",
    )
    seq = x[x["Next_Simulation_Record_ID"].notna()].copy()

    # Compare the derived Script19 transition population against the exported
    # transition rows using the next-call record ID and directed pair.
    require_columns(
        observed_transitions,
        ["Simulation_Record_ID", "IMO_Normalised", "Previous_Port",
         "Next_Port", "Elapsed_Hours_Between_Calls"],
        "19_observed_interport_transitions.csv",
    )
    obs = observed_transitions.copy()
    for c in ["Simulation_Record_ID", "IMO_Normalised", "Previous_Port", "Next_Port"]:
        obs[c] = obs[c].astype("string").str.strip()
    obs["Elapsed_Hours_Between_Calls"] = pd.to_numeric(
        obs["Elapsed_Hours_Between_Calls"], errors="coerce"
    )

    derived = seq[seq["Distinct_Port_Nonnegative_Transition"]].copy()
    # The Script19 transition rows are attached to the next call record.
    derived_compare = derived[[
        "Simulation_Record_ID", "IMO_Normalised",
        "UNLOCODE_Normalised", "Next_Port", "Inter_Call_Elapsed_Hours",
    ]].rename(columns={
        "UNLOCODE_Normalised": "Next_Port_Current_Row",
        "Next_Port": "Next_Port_Derived",
        "Inter_Call_Elapsed_Hours": "Elapsed_Derived",
    })
    # The current row is the previous call. The source transition row is the
    # next call, so compare by next record ID.
    derived_compare["Next_Call_Record_ID"] = derived["Next_Simulation_Record_ID"].values
    obs_key = obs[[
        "Simulation_Record_ID", "IMO_Normalised", "Previous_Port",
        "Next_Port", "Elapsed_Hours_Between_Calls",
    ]].copy()
    merged = derived_compare.merge(
        obs_key,
        left_on=["Next_Call_Record_ID", "IMO_Normalised"],
        right_on=["Simulation_Record_ID", "IMO_Normalised"],
        how="outer", indicator=True,
    )
    matched = merged["_merge"].eq("both")
    pair_match = (
        merged["Next_Port_Current_Row"].astype("string")
        == merged["Previous_Port"].astype("string")
    ) & (
        merged["Next_Port_Derived"].astype("string")
        == merged["Next_Port"].astype("string")
    )
    time_match = np.isclose(
        pd.to_numeric(merged["Elapsed_Derived"], errors="coerce"),
        pd.to_numeric(merged["Elapsed_Hours_Between_Calls"], errors="coerce"),
        rtol=0, atol=1e-8, equal_nan=False,
    )
    transition_compare = {
        "derived_rows": len(derived_compare),
        "observed_rows": len(obs),
        "matched_record_rows": int(matched.sum()),
        "outer_join_only_rows": int((~matched).sum()),
        "pair_mismatches_among_matches": int((matched & ~pair_match).sum()),
        "elapsed_time_mismatches_among_matches": int((matched & ~time_match).sum()),
    }
    transition_compare["ok"] = (
        transition_compare["derived_rows"] == transition_compare["observed_rows"]
        and transition_compare["outer_join_only_rows"] == 0
        and transition_compare["pair_mismatches_among_matches"] == 0
        and transition_compare["elapsed_time_mismatches_among_matches"] == 0
    )

    per_vessel = x.groupby("IMO_Normalised", dropna=False).agg(
        Calls=("Simulation_Record_ID", "count"),
        Sequence_Transitions=("Next_Simulation_Record_ID", lambda s: s.notna().sum()),
        Negative_Elapsed_Transitions=("Negative_Inter_Call_Elapsed", "sum"),
        Same_Port_Consecutive_Transitions=("Same_Port_Consecutive_Call", "sum"),
        Same_Arrival_Timestamp_Ties=("Same_Arrival_Timestamp_Tie", "sum"),
        Zero_Elapsed_Transitions=("Zero_Inter_Call_Elapsed", "sum"),
        Distinct_Port_Nonnegative_Transitions=("Distinct_Port_Nonnegative_Transition", "sum"),
    ).reset_index()
    return x, per_vessel, transition_compare

def propagate_step(arrival_delay, port_call_duration_shock, transition_shock, recovery, elapsed_gap):
    vals = [arrival_delay, port_call_duration_shock, transition_shock, recovery, elapsed_gap]
    if any(not math.isfinite(float(v)) for v in vals):
        raise ValueError("All inputs must be finite.")
    if arrival_delay < 0 or port_call_duration_shock < 0 or transition_shock < 0 or recovery < 0:
        raise ValueError("Delay, shocks and recovery must be non-negative.")
    if elapsed_gap < 0:
        raise ValueError("Negative observed inter-call elapsed time blocks propagation.")
    departure_delay = arrival_delay + port_call_duration_shock
    pre_recovery_delay = departure_delay + transition_shock
    if recovery > pre_recovery_delay + 1e-12:
        raise ValueError("Recovery cannot exceed accumulated delay available.")
    if recovery > elapsed_gap + transition_shock + 1e-12:
        raise ValueError("Recovery cannot reduce the simulated inter-call interval below zero.")
    next_arrival_delay = max(0.0, pre_recovery_delay - recovery)
    return {
        "departure_delay": departure_delay,
        "pre_recovery_delay": pre_recovery_delay,
        "next_arrival_delay": next_arrival_delay,
        "simulated_intercall_elapsed_hours": elapsed_gap + transition_shock - recovery,
    }

def build_unit_tests():
    cases = [
        ("T01_BASELINE_ZERO", 0, 0, 0, 0, 10, 0, "All delays remain zero."),
        ("T02_TRANSITION_SHOCK_24H", 0, 0, 24, 0, 10, 24, "A 24h transition shock reaches the next call."),
        ("T03_INHERITED_DELAY", 24, 0, 0, 0, 10, 24, "Existing delay carries forward once."),
        ("T04_CUMULATIVE_TRANSITION_SHOCKS", 24, 0, 12, 0, 10, 36, "A further 12h shock adds to inherited 24h delay."),
        ("T05_PORT_SERVICE_SHOCK", 0, 6, 0, 0, 10, 6, "A 6h port-service extension delays the next call."),
        ("T06_PARTIAL_RECOVERY", 0, 0, 24, 8, 10, 16, "8h recovery reduces 24h accumulated delay to 16h."),
        ("T07_FULL_RECOVERY", 0, 0, 24, 24, 30, 0, "Full recovery is allowed only when the elapsed-time opportunity is sufficient."),
    ]
    rows = []
    for name, d, s, x, r, gap, expected, note in cases:
        result = propagate_step(d, s, x, r, gap)
        observed = result["next_arrival_delay"]
        rows.append({
            "Test_ID": name, "Expected_Next_Arrival_Delay_Hours": expected,
            "Observed_Next_Arrival_Delay_Hours": observed,
            "Passed": math.isclose(observed, expected, rel_tol=0, abs_tol=1e-9),
            "Expected_Error": False, "Observed_Error": False, "Purpose": note,
        })

    error_cases = [
        ("T08_RECOVERY_EXCEEDS_AVAILABLE_DELAY", 0, 0, 24, 25, 10),
        ("T09_NEGATIVE_INTERCALL_GAP", 0, 0, 0, 0, -1),
        ("T10_NEGATIVE_TRANSITION_SHOCK", 0, 0, -2, 0, 10),
        ("T11_NEGATIVE_SERVICE_SHOCK", 0, -1, 0, 0, 10),
        ("T12_RECOVERY_EXCEEDS_ELAPSED_TIME_OPPORTUNITY", 24, 0, 0, 11, 10),
    ]
    for name, d, s, x, r, gap in error_cases:
        error = False
        try:
            propagate_step(d, s, x, r, gap)
        except ValueError:
            error = True
        rows.append({
            "Test_ID": name, "Expected_Next_Arrival_Delay_Hours": np.nan,
            "Observed_Next_Arrival_Delay_Hours": np.nan,
            "Passed": error, "Expected_Error": True,
            "Observed_Error": error,
            "Purpose": "Invalid input must be rejected, not clipped or silently repaired.",
        })
    return pd.DataFrame(rows)

def build_equations():
    rows = [
        ("E01", "Baseline call duration", "S_k = D^0_k - A^0_k", "Observed", "Actual departure minus actual arrival; retain source values."),
        ("E02", "Baseline inter-call elapsed time", "G_k = A^0_(k+1) - D^0_k", "Observed", "Negative G_k blocks propagation and requires review; do not clip to zero."),
        ("E03", "Simulated arrival timestamp", "A^sim_k = A^0_k + d^A_k", "Derived", "Store separately; never overwrite historical arrival."),
        ("E04", "Simulated departure delay", "d^D_k = d^A_k + s_k", "Derived", "s_k is added port-service duration only; zero for pure schedule displacement."),
        ("E05", "Simulated departure timestamp", "D^sim_k = D^0_k + d^D_k", "Derived", "Historical port-call duration remains unchanged unless a separate service shock is applied."),
        ("E06", "Delay before recovery", "q_k = d^D_k + x_k", "Derived", "x_k is a separately specified transition elapsed-time shock."),
        ("E07", "Recovery bounds", "0 <= r_k <= min(q_k, G_k + x_k)", "Decision constraint", "Recovery cannot exceed accumulated delay or reduce the simulated inter-call interval below zero; operational feasibility still needs separate evidence."),
        ("E08", "Next-call arrival delay", "d^A_(k+1) = q_k - r_k", "Derived", "Carries inherited delay once and adds new transition shock once."),
        ("E09", "Next-call arrival timestamp", "A^sim_(k+1) = A^0_(k+1) + d^A_(k+1)", "Derived", "Equivalent to D^sim_k + G_k + x_k - r_k when G_k is valid."),
        ("E10", "Next-call departure delay", "d^D_(k+1) = d^A_(k+1) + s_(k+1)", "Derived", "Port-service shock at the next call is applied at that call, not in the previous transition."),
        ("E11", "No-shock baseline", "s_k = x_k = r_k = 0; d^A_1 = 0", "Invariant", "Every simulated timestamp must equal its observed baseline timestamp."),
        ("E12", "Invalid transition/recovery handling", "G_k < 0 => BLOCK_SEQUENCE_LINK; r_k > G_k + x_k => INVALID_RECOVERY", "Validation rule", "Do not clip negative elapsed time or permit a negative simulated inter-call interval."),
    ]
    return pd.DataFrame(rows, columns=[
        "Equation_ID", "Quantity", "Equation", "Class", "Interpretation_and_Constraint"
    ])

def build_invariants():
    rows = [
        ("B01", "Source immutability", "Historical identifiers and timestamps remain unchanged.", "MUST_PASS"),
        ("B02", "Unique call identity", "Simulation_Record_ID is unique.", "MUST_PASS"),
        ("B03", "Positive port-call duration", "Departure timestamp is later than arrival timestamp.", "MUST_PASS"),
        ("B04", "Vessel identity", "Each modeled call has IMO_Normalised.", "MUST_PASS"),
        ("B05", "Port identity", "Each modeled call has UNLOCODE_Normalised.", "MUST_PASS"),
        ("B06", "Stay reconciliation", "Timestamp-derived duration reconciles with Actual_Stay_Hours within declared tolerance.", "MUST_PASS"),
        ("B07", "Sequence determinism", "Vessel calls have deterministic ordering; same-time ties are explicitly flagged.", "MUST_PASS"),
        ("B08", "Negative inter-call gap", "Negative inter-call elapsed time blocks that sequence link; never silently clipped.", "MUST_PASS"),
        ("B08A", "Recovery temporal feasibility", "Recovery cannot exceed either accumulated delay or the available elapsed-time opportunity G_k + x_k.", "FUTURE_MODEL"),
        ("B09", "Event balance", "Every included call has one arrival and one departure event.", "MUST_PASS"),
        ("B10", "Non-negative active calls", "Port active-call state never becomes negative.", "MUST_PASS"),
        ("B11", "Final active calls", "All included port calls depart by replay end.", "MUST_PASS"),
        ("B12", "Concurrency area identity", "Area under port concurrency equals sum of included observed call intervals.", "MUST_PASS"),
        ("B13", "Baseline reproducibility", "Repeated baseline replay yields identical metrics.", "MUST_PASS"),
        ("B14", "No route overclaim", "Consecutive port calls are not described as verified physical sailing routes.", "MUST_PASS"),
        ("B15", "No berth overclaim", "Port-call concurrency is not described as actual berth occupancy/capacity.", "MUST_PASS"),
        ("B16", "No Hormuz transit overclaim", "No actual transit is asserted without independent AIS/transit evidence.", "MUST_PASS"),
        ("B17", "Call-level and vessel-level outcomes", "Future metrics keep call-level delay and per-vessel accumulated/final delay separate.", "FUTURE_MODEL"),
        ("B18", "Censoring", "Unrecovered and right-censored calls/vessels are reported separately.", "FUTURE_MODEL"),
    ]
    return pd.DataFrame(rows, columns=["Invariant_ID", "Invariant", "Acceptance_Rule", "Status"])

def build_mechanisms():
    return pd.DataFrame([
        ("TRANSIT_ELAPSED_TIME_SHOCK", "CONCEPTUALLY_SPECIFIABLE",
         "Can be represented as a hypothetical elapsed-time shock on an observed consecutive-call transition after researcher approval.",
         "Elapsed time is not pure sailing time; edge evidence is sparse and vessel-concentrated.", "NO"),
        ("NETWORK_ACCESS_RESTRICTION", "BLOCKED",
         "Requires validated geographic route graph, route alternatives, and physical/regulatory feasibility evidence.",
         "Observed port-call transitions are not verified physical sailing edges.", "NO"),
        ("PORT_SERVICE_DISRUPTION", "PARTIALLY_SPECIFIABLE",
         "A separate added port-call duration may be represented for sensitivity analysis after scope approval.",
         "Actual_Stay_Hours is not necessarily berth processing time; waiting/anchorage may be included.", "NO"),
        ("COMPOUND_DISRUPTION", "DEFERRED",
         "Only after individual mechanisms are separately defined and validated.",
         "No compound scope or magnitudes approved.", "NO"),
    ], columns=[
        "Mechanism", "Readiness_Class", "Requirements",
        "Evidence_Limitation", "Execution_Authorized"
    ])

def main():
    loaded = read_required()
    raw = loaded["historical_schedule"]
    schedule = parse_schedule(raw)

    schema_rows = []
    for key, df in loaded.items():
        schema_rows.append({
            "Artifact": key,
            "Path": str(FILES[key].relative_to(ROOT)),
            "Rows": len(df),
            "Columns": len(df.columns),
            "Column_List": " | ".join(df.columns),
            "SHA256": sha256_file(FILES[key]),
        })
    schema_df = pd.DataFrame(schema_rows)

    keys_df, key_detail = audit_parameter_keys(loaded, schedule)
    sequence, per_vessel, transition_compare = build_vessel_sequences(
        schedule, loaded["observed_transitions"]
    )
    equations = build_equations()
    tests = build_unit_tests()
    invariants = build_invariants()
    mechanisms = build_mechanisms()

    # Baseline data quality and source joins.
    checks = []
    def add(name, passed, observed, expected, note):
        checks.append({
            "Check": name, "Passed": bool(passed),
            "Observed": observed, "Expected": expected, "Interpretation": note,
        })

    add("Historical schedule has 604 rows", len(schedule) == 604, len(schedule), 604, "Accepted primary baseline.")
    add("Simulation_Record_ID unique", not schedule["Simulation_Record_ID"].duplicated().any(),
        int(schedule["Simulation_Record_ID"].duplicated().sum()), 0, "Call identity.")
    add("All call identities complete",
        schedule[["Simulation_Record_ID","IMO_Normalised","UNLOCODE_Normalised"]].notna().all().all(),
        int(schedule[["Simulation_Record_ID","IMO_Normalised","UNLOCODE_Normalised"]].isna().sum().sum()), 0,
        "Required call/vessel/port identities.")
    add("All port-call intervals positive",
        schedule["Timestamp_Interval_Hours"].gt(0).all(),
        int(schedule["Timestamp_Interval_Hours"].le(0).sum()), 0, "Observed call duration.")
    stay_ok = schedule["Stay_Difference_Hours"].abs().le(0.02).all()
    add("Actual_Stay_Hours reconciles within 0.02h",
        stay_ok, int(schedule["Stay_Difference_Hours"].abs().gt(0.02).sum()), 0,
        "Do not silently replace source stay field.")
    add("155 unique vessels", schedule["IMO_Normalised"].nunique() == 155,
        schedule["IMO_Normalised"].nunique(), 155, "Baseline coverage.")
    add("19 unique ports", schedule["UNLOCODE_Normalised"].nunique() == 19,
        schedule["UNLOCODE_Normalised"].nunique(), 19, "Baseline coverage.")

    for artifact, expected_rows in [
        ("vessel_parameters", 155),
        ("port_parameters", 19),
        ("port_service_parameters", 19),
        ("interport_parameters", 53),
        ("observed_transitions", 271),
    ]:
        add(f"{artifact} has expected Script19 row count",
            len(loaded[artifact]) == expected_rows,
            len(loaded[artifact]), expected_rows,
            "Accepted Script19 simulation-input population.")
    for artifact in [
        "vessel_parameters", "port_parameters", "port_service_parameters",
        "interport_parameters", "observed_transitions",
    ]:
        d = key_detail.get(artifact, {})
        add(f"{artifact} actual join key and uniqueness valid",
            bool(d.get("ok", False)), d.get("unique_keys", "UNASSESSED"),
            "Unique non-null keys", json.dumps(d, default=str))

    add("Inter-port parameter pairs reconcile with observed transition pairs",
        key_detail["edge_pair_coverage"]["ok"],
        key_detail["edge_pair_coverage"]["observed_pairs"],
        key_detail["edge_pair_coverage"]["parameter_pairs"],
        json.dumps(key_detail["edge_pair_coverage"], default=str))
    add("Derived vessel transitions match Script19 observed transition rows",
        transition_compare["ok"], transition_compare["derived_rows"],
        transition_compare["observed_rows"], json.dumps(transition_compare, default=str))
    add("Delay propagation unit tests pass",
        tests["Passed"].all(), int(tests["Passed"].sum()), len(tests),
        "Pure equation tests; no experiment execution.")
    negative_links = sequence["Negative_Inter_Call_Elapsed"]
    negative_links_blocked = sequence.loc[
        negative_links, "Transition_Model_Status"
    ].eq("BLOCKED_NEGATIVE_ELAPSED_TIME_REVIEW").all()
    no_negative_link_treated_as_eligible = not sequence.loc[
        negative_links, "Distinct_Port_Nonnegative_Transition"
    ].any()
    add("Negative inter-call gaps are blocked and not treated as eligible transitions",
        bool(negative_links_blocked and no_negative_link_treated_as_eligible),
        int(negative_links.sum()), "All negative links explicitly blocked",
        "Negative gaps are not clipped or passed to the delay recurrence.")
    add("No experiment executed", True, "NO", "NO", "Specification only.")
    add("No upstream files modified", True, "NO", "NO", "Read-only audit.")
    add("No disruption/recovery policy approved", True, "NO", "NO", "Researcher approval remains separate.")

    checks_df = pd.DataFrame(checks)

    # Full sequence-level register and per-vessel diagnostics are combined in
    # one output with an explicit row type to keep record-level traceability.
    seq_export = sequence[[
        "Simulation_Record_ID", "IMO_Normalised", "UNLOCODE_Normalised",
        "Actual_Arrival_UTC", "Actual_Departure_UTC",
        "Next_Simulation_Record_ID", "Next_Port", "Next_Arrival_UTC",
        "Inter_Call_Elapsed_Hours", "Is_Last_Call_In_Vessel_Sequence",
        "Same_Port_Consecutive_Call", "Same_Arrival_Timestamp_Tie",
        "Negative_Inter_Call_Elapsed",
        "Zero_Inter_Call_Elapsed", "Distinct_Port_Nonnegative_Transition",
        "Transition_Model_Status",
    ]].copy()
    seq_export.insert(0, "Row_Type", "CALL_SEQUENCE")
    vessel_export = per_vessel.copy()
    vessel_export.insert(0, "Row_Type", "VESSEL_SUMMARY")
    # Harmonize union of columns for one CSV.
    sequence_out = pd.concat([seq_export, vessel_export], ignore_index=True, sort=False)

    schema_df.to_csv(OUT["schema"], index=False)
    keys_df.to_csv(OUT["keys"], index=False)
    sequence_out.to_csv(OUT["sequence"], index=False)
    equations.to_csv(OUT["equations"], index=False)
    tests.to_csv(OUT["tests"], index=False)
    invariants.to_csv(OUT["invariants"], index=False)
    mechanisms.to_csv(OUT["mechanisms"], index=False)
    checks_df.to_csv(OUT["checks"], index=False)

    summary = {
        "schedule_rows": len(schedule),
        "vessels": int(schedule["IMO_Normalised"].nunique()),
        "ports": int(schedule["UNLOCODE_Normalised"].nunique()),
        "sequence_links": int(sequence["Next_Simulation_Record_ID"].notna().sum()),
        "negative_elapsed_links": int(sequence["Negative_Inter_Call_Elapsed"].sum()),
        "same_port_links": int(sequence["Same_Port_Consecutive_Call"].sum()),
        "same_arrival_timestamp_ties": int(sequence["Same_Arrival_Timestamp_Tie"].sum()),
        "zero_elapsed_links": int(sequence["Zero_Inter_Call_Elapsed"].sum()),
        "distinct_port_nonnegative_links": int(sequence["Distinct_Port_Nonnegative_Transition"].sum()),
        "derived_transition_rows": transition_compare["derived_rows"],
        "source_transition_rows": transition_compare["observed_rows"],
        "transition_reconciliation": transition_compare,
        "key_audits": key_detail,
        "checks_passed": int(checks_df["Passed"].sum()),
        "checks_total": len(checks_df),
        "unit_tests_passed": int(tests["Passed"].sum()),
        "unit_tests_total": len(tests),
    }

    report = f"""================================================================================
SCRIPT 72 v2: CORRECTED BASELINE CONTRACT AND EXPLICIT DELAY-PROPAGATION SPECIFICATION
================================================================================

SOURCE DATA
{json.dumps(summary, indent=2, default=str)}

ACTUAL SCRIPT19 JOIN KEYS
- Vessel parameters: IMO_Normalised
- Port parameters: UNLOCODE_Normalised
- Port service parameters: UNLOCODE_Normalised
- Inter-port parameters: Previous_Port + Next_Port
- Observed transitions: IMO_Normalised + Simulation_Record_ID + Previous_Port + Next_Port

DELAY PROPAGATION MODEL
For vessel calls k and k+1, define:
  A0_k, D0_k : observed baseline arrival and departure timestamps
  S0_k       : observed baseline port-call duration = D0_k - A0_k
  G_k        : observed inter-call elapsed time = A0_(k+1) - D0_k
  dA_k       : simulated arrival delay at call k
  s_k        : added port-call duration shock at call k (hours, >= 0)
  dD_k       : simulated departure delay at call k = dA_k + s_k
  x_k        : added transition elapsed-time shock after call k (hours, >= 0)
  q_k        : delay available before recovery = dD_k + x_k
  r_k        : abstract recovery credit (hours), 0 <= r_k <= min(q_k, G_k + x_k)

Then:
  A_sim_k       = A0_k + dA_k
  D_sim_k       = D0_k + dD_k
  dD_k          = dA_k + s_k
  q_k           = dD_k + x_k
  dA_(k+1)      = q_k - r_k
  A_sim_(k+1)   = A0_(k+1) + dA_(k+1)

For a valid non-negative observed gap G_k, the equivalent transition relation is:
  A_sim_(k+1) = D_sim_k + G_k + x_k - r_k

IMPORTANT HANDLING
- If G_k < 0, block that vessel-sequence link and require review. Do not clip it to zero.
- A same-port consecutive call is not an inter-port network edge; no edge shock is assigned.
- No direct-arrival shock is included in this specification. New shocks enter through
  a separately specified port-service duration or observed-transition elapsed-time term.
- Recovery is an abstract schedule-recovery credit. It is bounded by both accumulated
  delay and available elapsed-time opportunity, but this does not prove feasible speed-up,
  rerouting, or operational recovery.
- Historical timestamps remain immutable; simulated timestamps are separate fields.
- If a vessel sequence link is invalid, downstream propagation across that link remains
  unresolved until the source sequence is reviewed; do not silently reset delay.

UNIT TESTS
Passed: {int(tests['Passed'].sum())}/{len(tests)}
{tests[['Test_ID','Passed','Purpose']].to_string(index=False)}

JOIN-KEY AUDIT
{keys_df.to_string(index=False)}

IMPLEMENTATION CHECKS
Passed: {int(checks_df['Passed'].sum())}/{len(checks_df)}
{checks_df[['Check','Passed','Observed','Expected']].to_string(index=False)}

MECHANISM READINESS
{mechanisms.to_string(index=False)}

RESEARCH BOUNDARIES
- Inter-port elapsed time is not pure sailing time.
- Port-call stay is not pure berth processing time; s_k is therefore named an added
  port-call duration shock, not a berth-service-time shock.
- Port-call concurrency is not verified berth occupancy.
- Consecutive observed port calls are not verified physical routes.
- No actual AIS-confirmed Hormuz transit is established.
- Network access restriction remains blocked pending validated route geography
  and feasible alternatives.
- Compound disruption remains deferred.
- No disruption magnitudes, affected scope, or recovery policy are approved.

EXPERIMENTS EXECUTED: NO
UPSTREAM FILES MODIFIED: NO
RESEARCHER APPROVALS CREATED: NO
"""
    OUT["report"].write_text(report, encoding="utf-8")

    print("=" * 96)
    print("SCRIPT 72 v2: CORRECTED BASELINE AND DELAY-PROPAGATION SPECIFICATION")
    print("=" * 96)
    print(f"Schedule: {len(schedule)} calls | {schedule['IMO_Normalised'].nunique()} vessels | "
          f"{schedule['UNLOCODE_Normalised'].nunique()} ports")
    print(f"Vessel sequence links: {summary['sequence_links']}")
    print(f"Negative elapsed links requiring review: {summary['negative_elapsed_links']}")
    print(f"Derived transitions: {transition_compare['derived_rows']} | "
          f"Script19 transitions: {transition_compare['observed_rows']}")
    print(f"Delay unit tests: {summary['unit_tests_passed']}/{summary['unit_tests_total']}")
    print(f"Implementation checks: {summary['checks_passed']}/{summary['checks_total']}")
    for key, path in OUT.items():
        print(path.relative_to(ROOT))
    print("NO EXPERIMENTS EXECUTED; NO SOURCE FILES MODIFIED.")
    print("SCRIPT 72 v2 COMPLETED" if checks_df["Passed"].all() else "SCRIPT 72 v2 COMPLETED WITH REVIEW ITEMS")

if __name__ == "__main__":
    main()
