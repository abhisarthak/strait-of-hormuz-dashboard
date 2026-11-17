
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime

# ============================================================
# SCRIPT 87
# INTEGRATED SIMULATION INPUT AND DESIGN READINESS AUDIT
#
# Purpose:
# 1. Audit the six core Script19 simulation inputs.
# 2. Reconcile historical transitions against the baseline.
# 3. Check vessel, port and parameter coverage.
# 4. Inventory experimental-design registers (Scripts 65-69).
# 5. Produce a read-only readiness assessment.
#
# This script does NOT:
# - Modify source files or historical inputs.
# - Change the 604-call baseline.
# - Approve disruption mechanisms or scopes.
# - Select new disruption parameters.
# - Execute a simulation.
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

INPUT_DIR = ROOT / "data" / "simulation_inputs"
TABLE_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

TABLE_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_PREFIX = "87_"

FILES = {
    "baseline": INPUT_DIR / "19_historical_arrival_schedule.csv",
    "vessels": INPUT_DIR / "19_vessel_parameters.csv",
    "ports": INPUT_DIR / "19_port_parameters.csv",
    "service": INPUT_DIR / "19_port_service_parameters.csv",
    "interport": INPUT_DIR / "19_interport_time_parameters.csv",
    "transitions": INPUT_DIR / "19_observed_interport_transitions.csv",
}

EXPECTED = {
    "baseline_rows": 604,
    "vessels": 155,
    "ports": 19,
    "service_parameters": 19,
    "interport_pairs": 53,
    "transitions": 271,
}


def load_csv(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Required input is missing: {path}"
        )
    return pd.read_csv(path, low_memory=False)


def normalize(series):
    return (
        series.astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.upper()
    )


def utc(series):
    return pd.to_datetime(
        series,
        errors="coerce",
        utc=True
    )


def add_check(rows, name, observed, expected, passed, note=""):
    rows.append({
        "Check": name,
        "Observed": str(observed),
        "Expected": str(expected),
        "Passed": bool(passed),
        "Note": note,
    })


def compare_numeric(a, b, tolerance=1e-5):
    if pd.isna(a) and pd.isna(b):
        return True
    if pd.isna(a) or pd.isna(b):
        return False
    return abs(float(a) - float(b)) <= tolerance


print("=" * 75)
print("SCRIPT 87 — INTEGRATED SIMULATION READINESS AUDIT")
print("=" * 75)

# ------------------------------------------------------------
# 1. LOAD SIX CORE INPUTS
# ------------------------------------------------------------

print("\n[1/8] Loading six core simulation inputs...")

data = {
    key: load_csv(path)
    for key, path in FILES.items()
}

baseline = data["baseline"].copy()
vessels = data["vessels"].copy()
ports = data["ports"].copy()
service = data["service"].copy()
interport = data["interport"].copy()
transitions = data["transitions"].copy()

checks = []

# ------------------------------------------------------------
# 2. NORMALIZE IDENTITIES AND TIMESTAMPS
# ------------------------------------------------------------

print("[2/8] Checking baseline identities and timestamps...")

required_baseline = [
    "Simulation_Record_ID",
    "IMO_Normalised",
    "UNLOCODE_Normalised",
    "Actual_Arrival_UTC",
    "Actual_Departure_UTC",
]

missing_columns = [
    c for c in required_baseline
    if c not in baseline.columns
]

if missing_columns:
    raise ValueError(
        f"Baseline missing required columns: {missing_columns}"
    )

baseline["Simulation_Record_ID"] = normalize(
    baseline["Simulation_Record_ID"]
)
baseline["IMO_Normalised"] = normalize(
    baseline["IMO_Normalised"]
)
baseline["UNLOCODE_Normalised"] = normalize(
    baseline["UNLOCODE_Normalised"]
)

baseline["Actual_Arrival_UTC"] = utc(
    baseline["Actual_Arrival_UTC"]
)
baseline["Actual_Departure_UTC"] = utc(
    baseline["Actual_Departure_UTC"]
)

baseline["Recomputed_Stay_Hours"] = (
    baseline["Actual_Departure_UTC"]
    - baseline["Actual_Arrival_UTC"]
).dt.total_seconds() / 3600

baseline["Recomputed_Stay_Hours"] = (
    baseline["Recomputed_Stay_Hours"].round(8)
)

unique_ids = baseline["Simulation_Record_ID"].nunique()
unique_vessels = baseline["IMO_Normalised"].nunique()
unique_ports = baseline["UNLOCODE_Normalised"].nunique()

positive_intervals = (
    baseline["Recomputed_Stay_Hours"] >= 0
).all()

add_check(
    checks,
    "Baseline record count",
    len(baseline),
    EXPECTED["baseline_rows"],
    len(baseline) == EXPECTED["baseline_rows"]
)

add_check(
    checks,
    "Unique simulation record IDs",
    unique_ids,
    len(baseline),
    unique_ids == len(baseline)
)

add_check(
    checks,
    "Unique vessel count",
    unique_vessels,
    EXPECTED["vessels"],
    unique_vessels == EXPECTED["vessels"]
)

add_check(
    checks,
    "Unique port count",
    unique_ports,
    EXPECTED["ports"],
    unique_ports == EXPECTED["ports"]
)

add_check(
    checks,
    "Actual timestamps complete",
    int(
        baseline[
            [
                "Actual_Arrival_UTC",
                "Actual_Departure_UTC"
            ]
        ].isna().sum().sum()
    ),
    0,
    baseline[
        [
            "Actual_Arrival_UTC",
            "Actual_Departure_UTC"
        ]
    ].notna().all().all()
)

add_check(
    checks,
    "Non-negative observed port-call intervals",
    int((baseline["Recomputed_Stay_Hours"] < 0).sum()),
    0,
    positive_intervals
)

# ------------------------------------------------------------
# 3. VESSEL AND PORT PARAMETER COVERAGE
# ------------------------------------------------------------

print("[3/8] Checking vessel and port parameter coverage...")

vessel_key = "IMO_Normalised"
port_key = "UNLOCODE_Normalised"

for frame in [vessels]:
    frame[vessel_key] = normalize(frame[vessel_key])

for frame in [ports, service]:
    frame[port_key] = normalize(frame[port_key])

baseline_vessel_set = set(
    baseline["IMO_Normalised"].dropna()
)

parameter_vessel_set = set(
    vessels["IMO_Normalised"].dropna()
)

baseline_port_set = set(
    baseline["UNLOCODE_Normalised"].dropna()
)

parameter_port_set = set(
    ports["UNLOCODE_Normalised"].dropna()
)

service_port_set = set(
    service["UNLOCODE_Normalised"].dropna()
)

add_check(
    checks,
    "Vessel parameter row count",
    len(vessels),
    EXPECTED["vessels"],
    len(vessels) == EXPECTED["vessels"]
)

add_check(
    checks,
    "Unique vessel parameter keys",
    vessels[vessel_key].nunique(),
    len(vessels),
    vessels[vessel_key].nunique() == len(vessels)
)

add_check(
    checks,
    "All baseline vessels represented",
    len(baseline_vessel_set - parameter_vessel_set),
    0,
    baseline_vessel_set.issubset(parameter_vessel_set)
)

add_check(
    checks,
    "Port parameter row count",
    len(ports),
    EXPECTED["ports"],
    len(ports) == EXPECTED["ports"]
)

add_check(
    checks,
    "Unique port parameter keys",
    ports[port_key].nunique(),
    len(ports),
    ports[port_key].nunique() == len(ports)
)

add_check(
    checks,
    "All baseline ports represented",
    len(baseline_port_set - parameter_port_set),
    0,
    baseline_port_set.issubset(parameter_port_set)
)

add_check(
    checks,
    "Port service parameter row count",
    len(service),
    EXPECTED["service_parameters"],
    len(service) == EXPECTED["service_parameters"]
)

add_check(
    checks,
    "All baseline ports have service parameters",
    len(baseline_port_set - service_port_set),
    0,
    baseline_port_set.issubset(service_port_set)
)

# ------------------------------------------------------------
# 4. RECOMPUTE PORT SERVICE STATISTICS
# ------------------------------------------------------------

print("[4/8] Recomputing observed port service statistics...")

service_checks = []

for port_code, group in baseline.groupby(
    "UNLOCODE_Normalised"
):

    values = group["Recomputed_Stay_Hours"].dropna()

    row = service[
        service["UNLOCODE_Normalised"] == port_code
    ]

    if len(row) != 1:
        service_checks.append({
            "Port": port_code,
            "Baseline_Count": len(values),
            "Parameter_Count": len(row),
            "Mean_Match": False,
            "Median_Match": False,
            "Min_Match": False,
            "Max_Match": False,
        })
        continue

    row = row.iloc[0]

    service_checks.append({
        "Port": port_code,
        "Baseline_Count": len(values),
        "Parameter_Count": int(row["sample_size"]),
        "Mean_Match": compare_numeric(
            values.mean(), row["mean_stay_hours"]
        ),
        "Median_Match": compare_numeric(
            values.median(), row["median_stay_hours"]
        ),
        "Min_Match": compare_numeric(
            values.min(), row["min_stay_hours"]
        ),
        "Max_Match": compare_numeric(
            values.max(), row["max_stay_hours"]
        ),
    })

service_audit = pd.DataFrame(service_checks)

service_audit.to_csv(
    TABLE_DIR / f"{OUTPUT_PREFIX}service_reconciliation.csv",
    index=False
)

service_stats_match = (
    service_audit[
        [
            "Mean_Match",
            "Median_Match",
            "Min_Match",
            "Max_Match",
        ]
    ].all().all()
)

add_check(
    checks,
    "Port service statistics reconcile",
    int(service_stats_match),
    1,
    service_stats_match,
    "Recomputed from baseline actual arrival/departure timestamps."
)

# ------------------------------------------------------------
# 5. RECOMPUTE OBSERVED INTER-PORT TRANSITIONS
# ------------------------------------------------------------

print("[5/8] Reconstructing historical vessel transitions...")

ordered = baseline.sort_values(
    [
        "IMO_Normalised",
        "Actual_Arrival_UTC",
        "Simulation_Record_ID",
    ]
).copy()

ordered["Previous_Port"] = (
    ordered.groupby("IMO_Normalised")[
        "UNLOCODE_Normalised"
    ].shift(1)
)

ordered["Previous_Departure_UTC"] = (
    ordered.groupby("IMO_Normalised")[
        "Actual_Departure_UTC"
    ].shift(1)
)

ordered["Previous_Record_ID"] = (
    ordered.groupby("IMO_Normalised")[
        "Simulation_Record_ID"
    ].shift(1)
)

ordered["Elapsed_Hours_Between_Calls"] = (
    ordered["Actual_Arrival_UTC"]
    - ordered["Previous_Departure_UTC"]
).dt.total_seconds() / 3600

reconstructed = ordered[
    ordered["Previous_Port"].notna()
    & ordered["Previous_Departure_UTC"].notna()
    & ordered["Elapsed_Hours_Between_Calls"].notna()
    & (ordered["Elapsed_Hours_Between_Calls"] >= 0)
    & (
        ordered["Previous_Port"]
        != ordered["UNLOCODE_Normalised"]
    )
].copy()

# Prepare keys for comparison.
transition_required = [
    "Simulation_Record_ID",
    "Previous_Port",
    "Next_Port",
    "Previous_Departure_UTC",
    "Elapsed_Hours_Between_Calls",
]

missing_transition_columns = [
    c for c in transition_required
    if c not in transitions.columns
]

if missing_transition_columns:
    raise ValueError(
        "Transition input missing required columns: "
        f"{missing_transition_columns}"
    )

reconstructed = reconstructed.rename(
    columns={
        "UNLOCODE_Normalised": "Next_Port"
    }
)

reconstructed["Simulation_Record_ID"] = normalize(
    reconstructed["Simulation_Record_ID"]
)
transitions["Simulation_Record_ID"] = normalize(
    transitions["Simulation_Record_ID"]
)

reconstructed["Previous_Port"] = normalize(
    reconstructed["Previous_Port"]
)
reconstructed["Next_Port"] = normalize(
    reconstructed["Next_Port"]
)

transitions["Previous_Port"] = normalize(
    transitions["Previous_Port"]
)
transitions["Next_Port"] = normalize(
    transitions["Next_Port"]
)

reconstructed["Previous_Departure_UTC"] = utc(
    reconstructed["Previous_Departure_UTC"]
)
transitions["Previous_Departure_UTC"] = utc(
    transitions["Previous_Departure_UTC"]
)

reconstructed["Elapsed_Hours_Between_Calls"] = pd.to_numeric(
    reconstructed["Elapsed_Hours_Between_Calls"],
    errors="coerce"
)

transitions["Elapsed_Hours_Between_Calls"] = pd.to_numeric(
    transitions["Elapsed_Hours_Between_Calls"],
    errors="coerce"
)

compare_columns = [
    "Simulation_Record_ID",
    "Previous_Port",
    "Next_Port",
    "Previous_Departure_UTC",
    "Elapsed_Hours_Between_Calls",
]

reconstructed_keys = reconstructed[compare_columns].copy()
transition_keys = transitions[compare_columns].copy()

reconstructed_keys = reconstructed_keys.sort_values(
    "Simulation_Record_ID"
).reset_index(drop=True)

transition_keys = transition_keys.sort_values(
    "Simulation_Record_ID"
).reset_index(drop=True)

same_row_count = (
    len(reconstructed_keys) == len(transition_keys)
)

transition_exact_match = False

if same_row_count:
    transition_exact_match = (
        reconstructed_keys["Simulation_Record_ID"].equals(
            transition_keys["Simulation_Record_ID"]
        )
        and reconstructed_keys["Previous_Port"].equals(
            transition_keys["Previous_Port"]
        )
        and reconstructed_keys["Next_Port"].equals(
            transition_keys["Next_Port"]
        )
        and reconstructed_keys["Previous_Departure_UTC"].equals(
            transition_keys["Previous_Departure_UTC"]
        )
        and np.allclose(
            reconstructed_keys[
                "Elapsed_Hours_Between_Calls"
            ].to_numpy(dtype=float),
            transition_keys[
                "Elapsed_Hours_Between_Calls"
            ].to_numpy(dtype=float),
            atol=1e-6,
            rtol=0
        )
    )

add_check(
    checks,
    "Observed transition row count",
    len(transitions),
    EXPECTED["transitions"],
    len(transitions) == EXPECTED["transitions"]
)

add_check(
    checks,
    "Reconstructed transition row count",
    len(reconstructed),
    EXPECTED["transitions"],
    len(reconstructed) == EXPECTED["transitions"]
)

add_check(
    checks,
    "Transition register reconciles to baseline",
    transition_exact_match,
    True,
    transition_exact_match,
    "Compared current call, previous port, next port, "
    "previous departure and elapsed time."
)

# ------------------------------------------------------------
# 6. INTER-PORT PARAMETER RECONCILIATION
# ------------------------------------------------------------

print("[6/8] Checking directed inter-port parameters...")

expected_pairs = (
    transitions.groupby(["Previous_Port", "Next_Port"])
    ["Elapsed_Hours_Between_Calls"]
    .agg(
        sample_size="count",
        mean_elapsed_hours="mean",
        median_elapsed_hours="median",
        min_elapsed_hours="min",
        max_elapsed_hours="max",
    )
    .reset_index()
)

actual_pairs = interport.copy()

actual_pairs["Previous_Port"] = normalize(
    actual_pairs["Previous_Port"]
)
actual_pairs["Next_Port"] = normalize(
    actual_pairs["Next_Port"]
)

pair_reconciliation = expected_pairs.merge(
    actual_pairs,
    on=["Previous_Port", "Next_Port"],
    how="outer",
    suffixes=("_recomputed", "_input"),
    indicator=True
)

pair_reconciliation["Pair_Present_Both"] = (
    pair_reconciliation["_merge"] == "both"
)

for metric in [
    "sample_size",
    "mean_elapsed_hours",
    "median_elapsed_hours",
    "min_elapsed_hours",
    "max_elapsed_hours",
]:
    pair_reconciliation[f"{metric}_Match"] = [
        compare_numeric(a, b)
        for a, b in zip(
            pair_reconciliation[f"{metric}_recomputed"],
            pair_reconciliation[f"{metric}_input"]
        )
    ]

pair_reconciliation.to_csv(
    TABLE_DIR / f"{OUTPUT_PREFIX}interport_reconciliation.csv",
    index=False
)

pairs_match = (
    pair_reconciliation["Pair_Present_Both"].all()
    and pair_reconciliation[
        [
            "sample_size_Match",
            "mean_elapsed_hours_Match",
            "median_elapsed_hours_Match",
            "min_elapsed_hours_Match",
            "max_elapsed_hours_Match",
        ]
    ].all().all()
)

add_check(
    checks,
    "Directed inter-port pair count",
    len(interport),
    EXPECTED["interport_pairs"],
    len(interport) == EXPECTED["interport_pairs"]
)

add_check(
    checks,
    "Inter-port parameter statistics reconcile",
    int(pairs_match),
    1,
    pairs_match
)

# ------------------------------------------------------------
# 7. EXPERIMENT DESIGN REGISTER INVENTORY
# ------------------------------------------------------------

print("[7/8] Inventorying existing experiment-design artifacts...")

design_rows = []

for folder in [TABLE_DIR, REPORT_DIR]:

    for script_no in range(65, 70):

        matches = sorted(
            folder.glob(f"{script_no}_*")
        )

        for path in matches:

            design_rows.append({
                "Script": script_no,
                "Directory": str(path.parent.relative_to(ROOT)),
                "Filename": path.name,
                "Exists": path.exists(),
                "Size_Bytes": path.stat().st_size,
            })

design_inventory = pd.DataFrame(design_rows)

if design_inventory.empty:
    design_inventory = pd.DataFrame(
        columns=[
            "Script",
            "Directory",
            "Filename",
            "Exists",
            "Size_Bytes",
        ]
    )

design_inventory.to_csv(
    TABLE_DIR / f"{OUTPUT_PREFIX}design_register_inventory.csv",
    index=False
)

# This inventory does not imply approval.
add_check(
    checks,
    "Design-register inventory generated",
    len(design_inventory),
    "Inventory created",
    True,
    "File presence is not equivalent to researcher approval."
)

# ------------------------------------------------------------
# 8. FINAL AUDIT AND REPORT
# ------------------------------------------------------------

print("[8/8] Preparing final readiness report...")

check_df = pd.DataFrame(checks)

check_df.to_csv(
    TABLE_DIR / f"{OUTPUT_PREFIX}readiness_checks.csv",
    index=False
)

total_checks = len(check_df)
passed_checks = int(check_df["Passed"].sum())
failed_checks = total_checks - passed_checks

baseline_ready = (
    len(baseline) == EXPECTED["baseline_rows"]
    and unique_ids == len(baseline)
    and unique_vessels == EXPECTED["vessels"]
    and unique_ports == EXPECTED["ports"]
    and positive_intervals
)

input_reconciliation_ready = (
    baseline_ready
    and service_stats_match
    and transition_exact_match
    and pairs_match
    and len(vessels) == EXPECTED["vessels"]
    and len(ports) == EXPECTED["ports"]
    and len(service) == EXPECTED["service_parameters"]
    and len(interport) == EXPECTED["interport_pairs"]
    and len(transitions) == EXPECTED["transitions"]
)

with open(
    REPORT_DIR / f"{OUTPUT_PREFIX}integrated_readiness_report.txt",
    "w",
    encoding="utf-8"
) as f:

    f.write(
        "SCRIPT 87 — INTEGRATED SIMULATION READINESS AUDIT\n"
        + "=" * 65 + "\n\n"
    )

    f.write(
        f"Execution timestamp: {datetime.now().isoformat()}\n\n"
    )

    f.write("CORE INPUT COUNTS\n")
    f.write("-" * 65 + "\n")

    for key, frame in data.items():
        f.write(f"{key}: {len(frame)} rows\n")

    f.write("\nBASELINE SUMMARY\n")
    f.write("-" * 65 + "\n")
    f.write(f"Historical calls: {len(baseline)}\n")
    f.write(f"Unique IDs: {unique_ids}\n")
    f.write(f"Vessels: {unique_vessels}\n")
    f.write(f"Ports: {unique_ports}\n")
    f.write(
        f"Negative port-call intervals: "
        f"{int((baseline['Recomputed_Stay_Hours'] < 0).sum())}\n"
    )

    f.write("\nTRANSITION RECONCILIATION\n")
    f.write("-" * 65 + "\n")
    f.write(f"Input transition rows: {len(transitions)}\n")
    f.write(f"Reconstructed rows: {len(reconstructed)}\n")
    f.write(f"Exact reconciliation: {transition_exact_match}\n")

    f.write("\nINTER-PORT RECONCILIATION\n")
    f.write("-" * 65 + "\n")
    f.write(f"Input directed pairs: {len(interport)}\n")
    f.write(f"Recomputed directed pairs: {len(expected_pairs)}\n")
    f.write(f"Parameter reconciliation: {pairs_match}\n")

    f.write("\nEXPERIMENT DESIGN REGISTER INVENTORY\n")
    f.write("-" * 65 + "\n")

    if len(design_inventory):
        f.write(
            design_inventory.to_string(index=False) + "\n"
        )
    else:
        f.write("No Script65-69 artifacts found in output folders.\n")

    f.write("\nREADINESS CHECKS\n")
    f.write("-" * 65 + "\n")
    f.write(check_df.to_string(index=False) + "\n")

    f.write("\nFINAL STATUS\n")
    f.write("-" * 65 + "\n")
    f.write(f"Checks passed: {passed_checks}/{total_checks}\n")
    f.write(f"Checks failed: {failed_checks}/{total_checks}\n")
    f.write(f"Baseline structural readiness: {baseline_ready}\n")
    f.write(
        "Input reconciliation readiness: "
        f"{input_reconciliation_ready}\n"
    )

    f.write("\nRESEARCH LIMITATIONS\n")
    f.write("-" * 65 + "\n")
    f.write(
        "- Inter-port elapsed time is not pure sailing time.\n"
        "- Port stay is not necessarily berth processing time.\n"
        "- Port parameters do not establish physical port capacity.\n"
        "- Historical port-call links do not establish verified routes.\n"
        "- No AIS-confirmed Hormuz transit is established.\n"
        "- Design-register presence does not imply researcher approval.\n"
        "- No disruption or recovery experiment is executed by Script87.\n"
        "- No source files or simulation inputs are modified.\n"
    )

print("\n" + "=" * 75)
print("SCRIPT 87 COMPLETED")
print("=" * 75)

print(f"Checks passed: {passed_checks}/{total_checks}")
print(f"Checks failed: {failed_checks}/{total_checks}")
print("Baseline structural readiness:", baseline_ready)
print("Input reconciliation readiness:", input_reconciliation_ready)

print("\nGenerated files:")
print(
    TABLE_DIR / f"{OUTPUT_PREFIX}readiness_checks.csv"
)
print(
    TABLE_DIR / f"{OUTPUT_PREFIX}service_reconciliation.csv"
)
print(
    TABLE_DIR / f"{OUTPUT_PREFIX}interport_reconciliation.csv"
)
print(
    TABLE_DIR / f"{OUTPUT_PREFIX}design_register_inventory.csv"
)
print(
    REPORT_DIR / f"{OUTPUT_PREFIX}integrated_readiness_report.txt"
)

print("\nNo source data or simulation inputs were modified.")
print("No experiment was executed.")
