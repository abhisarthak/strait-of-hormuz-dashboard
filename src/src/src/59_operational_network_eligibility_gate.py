"""
SCRIPT 59: OPERATIONAL NETWORK ELIGIBILITY GATE
----------------------------------------------
Purpose:
    Translate the audited Script 58 researcher register into a controlled
    operational-network eligibility assessment.

    This is a gate/register only. It does NOT modify the simulation network,
    add nodes, create edges, or approve coordinates.

Input:
    outputs/tables/58_researcher_coordinate_approval_register.csv

Outputs:
    outputs/tables/59_operational_network_eligibility_register.csv
    outputs/tables/59_operational_network_eligibility_summary.csv
    outputs/reports/59_operational_network_eligibility_report.txt

Gate principles:
    1. Coordinate approval and operational inclusion are separate decisions.
    2. Both must be explicitly approved before a candidate can pass the gate.
    3. Script 49 descriptive-only classes remain descriptive-only unless
       upstream evidence and eligibility classifications are formally revised.
    4. Regional/sensitivity candidates are not assumed to be observed-network
       nodes or actual Strait of Hormuz transits.
    5. No changes are made to upstream files or simulation inputs.
"""

from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

INPUT_FILE = TABLE_DIR / "58_researcher_coordinate_approval_register.csv"
REGISTER_FILE = TABLE_DIR / "59_operational_network_eligibility_register.csv"
SUMMARY_FILE = TABLE_DIR / "59_operational_network_eligibility_summary.csv"
REPORT_FILE = REPORT_DIR / "59_operational_network_eligibility_report.txt"

EXPECTED_RECORDS = 19

REQUIRED_COLUMNS = {
    "UNLOCODE",
    "Port_Name",
    "Script49_Eligibility_Classification",
    "Script49_Recommended_Use",
    "Researcher_Coordinate_Decision",
    "Approved_Latitude",
    "Approved_Longitude",
    "Approved_Coordinate_Reference_Object",
    "Approved_Coordinate_Scope",
    "Approved_Datum_or_CRS",
    "Researcher_Operational_Decision",
    "AIS_Transit_Evidence_Status",
    "AIS_Evidence_Source_URL",
    "Script58_Record_Status",
}


def clean(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def valid_pair(lat, lon):
    try:
        lat = float(lat)
        lon = float(lon)
        return (
            np.isfinite(lat)
            and np.isfinite(lon)
            and -90 <= lat <= 90
            and -180 <= lon <= 180
        )
    except (TypeError, ValueError):
        return False


def classify_gate(row):
    eligibility = clean(row["Script49_Eligibility_Classification"]).upper()
    recommended_use = clean(row["Script49_Recommended_Use"]).upper()
    coord_decision = clean(row["Researcher_Coordinate_Decision"]).upper()
    operational_decision = clean(row["Researcher_Operational_Decision"]).upper()

    approved_pair = valid_pair(row["Approved_Latitude"], row["Approved_Longitude"])
    coordinate_approved = coord_decision in {
        "APPROVED", "APPROVED_WITH_LIMITATIONS"
    } and approved_pair

    operational_approved = operational_decision in {
        "APPROVED", "APPROVED_FOR_OPERATIONAL_NETWORK"
    }

    identity_pending = "PENDING_IDENTITY_REVIEW" in eligibility
    regional_candidate = "REGIONAL_OR_SENSITIVITY_CANDIDATE" in eligibility
    descriptive_not_observed = "NOT_IN_OBSERVED_NETWORK" in eligibility

    reasons = []

    if identity_pending:
        gate_class = "DESCRIPTIVE_ONLY_IDENTITY_REVIEW_REQUIRED"
        gate_status = "NOT_ELIGIBLE_FOR_OPERATIONAL_NETWORK_UNDER_CURRENT_CLASSIFICATION"
        reasons.append("Script 49 requires identity review; descriptive context only.")
    elif descriptive_not_observed:
        gate_class = "OUTSIDE_OBSERVED_NETWORK_MOVEMENT_EVIDENCE_REQUIRED"
        gate_status = "NOT_ELIGIBLE_FOR_EMPIRICAL_BASELINE_UNDER_CURRENT_EVIDENCE"
        reasons.append("Script 49 places this record outside the observed network.")
        reasons.append("New movement evidence and formal eligibility reassessment are required.")
    elif regional_candidate:
        gate_class = "REGIONAL_SENSITIVITY_CANDIDATE"
        if not coordinate_approved:
            reasons.append("Researcher coordinate approval is not complete.")
        if not operational_approved:
            reasons.append("Researcher operational inclusion decision is not complete.")
        if not approved_pair:
            reasons.append("Approved coordinate pair is missing or invalid.")
        if not clean(row["Approved_Coordinate_Reference_Object"]):
            reasons.append("Approved coordinate reference object is not specified.")
        if not clean(row["Approved_Coordinate_Scope"]):
            reasons.append("Approved coordinate scope is not specified.")
        if not clean(row["Approved_Datum_or_CRS"]):
            reasons.append("Approved datum/CRS is not specified.")

        if (
            coordinate_approved
            and operational_approved
            and approved_pair
            and clean(row["Approved_Coordinate_Reference_Object"])
            and clean(row["Approved_Coordinate_Scope"])
            and clean(row["Approved_Datum_or_CRS"])
        ):
            gate_status = "ELIGIBLE_FOR_RESEARCHER_FINAL_NETWORK_REVIEW"
        else:
            gate_status = "PENDING_COORDINATE_AND_OPERATIONAL_APPROVAL"
    else:
        gate_class = "UNMAPPED_OR_UNRECOGNIZED_SCRIPT49_CLASS"
        gate_status = "BLOCKED_PENDING_CLASSIFICATION_REVIEW"
        reasons.append("Script 49 eligibility class does not match an approved gate rule.")

    # A passed eligibility gate is not equivalent to confirmed Hormuz transit.
    if clean(row["AIS_Transit_Evidence_Status"]).upper() not in {
        "AIS_CONFIRMED", "CONFIRMED"
    }:
        reasons.append("AIS-confirmed Strait of Hormuz transit is not established.")

    return pd.Series({
        "Operational_Gate_Class_59": gate_class,
        "Operational_Gate_Status_59": gate_status,
        "Operational_Gate_Reason_59": " | ".join(reasons),
        "Coordinate_Approved_For_Gate_59": coordinate_approved,
        "Operational_Inclusion_Approved_59": operational_approved,
        "Approved_Coordinate_Pair_Valid_59": approved_pair,
        "May_Enter_Empirical_Baseline_59": False,
        "May_Enter_Sensitivity_Model_59": False,
        "May_Enter_Descriptive_Context_59": (
            identity_pending or descriptive_not_observed or regional_candidate
        ),
        "AIS_Hormuz_Transit_Established_59": (
            clean(row["AIS_Transit_Evidence_Status"]).upper()
            in {"AIS_CONFIRMED", "CONFIRMED"}
            and bool(clean(row["AIS_Evidence_Source_URL"]))
        ),
    })


def build_summary(register):
    metrics = [
        ("Total records assessed", len(register)),
        ("Regional/sensitivity candidates", int(
            register["Operational_Gate_Class_59"].eq("REGIONAL_SENSITIVITY_CANDIDATE").sum()
        )),
        ("Descriptive-only identity review records", int(
            register["Operational_Gate_Class_59"].eq("DESCRIPTIVE_ONLY_IDENTITY_REVIEW_REQUIRED").sum()
        )),
        ("Outside observed network; movement evidence required", int(
            register["Operational_Gate_Class_59"].eq("OUTSIDE_OBSERVED_NETWORK_MOVEMENT_EVIDENCE_REQUIRED").sum()
        )),
        ("Pending coordinate and operational approval", int(
            register["Operational_Gate_Status_59"].eq("PENDING_COORDINATE_AND_OPERATIONAL_APPROVAL").sum()
        )),
        ("Eligible for researcher final network review", int(
            register["Operational_Gate_Status_59"].eq("ELIGIBLE_FOR_RESEARCHER_FINAL_NETWORK_REVIEW").sum()
        )),
        ("Empirical baseline nodes admitted by Script 59", int(
            register["May_Enter_Empirical_Baseline_59"].sum()
        )),
        ("Sensitivity model nodes admitted by Script 59", int(
            register["May_Enter_Sensitivity_Model_59"].sum()
        )),
        ("Descriptive context records", int(
            register["May_Enter_Descriptive_Context_59"].sum()
        )),
        ("AIS-confirmed Hormuz transits established", int(
            register["AIS_Hormuz_Transit_Established_59"].sum()
        )),
        ("Simulation network files modified", 0),
    ]
    return pd.DataFrame(metrics, columns=["Metric", "Value"])


def write_report(register, summary):
    with REPORT_FILE.open("w", encoding="utf-8") as f:
        f.write("=" * 88 + "\n")
        f.write("SCRIPT 59: OPERATIONAL NETWORK ELIGIBILITY GATE\n")
        f.write("=" * 88 + "\n\n")
        f.write("PURPOSE\n")
        f.write(
            "Assess whether each Script 58 record satisfies the documented "
            "preconditions for operational network consideration. Script 59 "
            "does not modify the simulation network or approve any location.\n\n"
        )
        f.write("SUMMARY\n")
        f.write(summary.to_string(index=False))
        f.write("\n\nGATE STATUS COUNTS\n")
        f.write(register["Operational_Gate_Status_59"].value_counts().to_string())
        f.write("\n\nRECORD-LEVEL GATE\n")
        cols = [
            "UNLOCODE", "Port_Name", "Script49_Eligibility_Classification",
            "Operational_Gate_Class_59", "Operational_Gate_Status_59",
            "Operational_Gate_Reason_59",
        ]
        f.write(register[cols].to_string(index=False))
        f.write("\n\nRESEARCH LIMITATIONS\n")
        f.write(
            "- Regional/sensitivity candidacy is not proof of actual Hormuz transit.\n"
            "- A coordinate pair is not approved merely because it is numerically valid.\n"
            "- Coordinate approval and operational inclusion are separate researcher decisions.\n"
            "- Descriptive-only classes are not promoted by Script 59.\n"
            "- Empirical baseline membership requires separate movement evidence and review.\n"
            "- Script 59 does not add nodes or edges, alter network topology, or change simulation inputs.\n"
        )


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Required input not found: {INPUT_FILE}")

    source = pd.read_csv(INPUT_FILE)
    missing = REQUIRED_COLUMNS - set(source.columns)
    if missing:
        raise ValueError(f"Missing required Script 58 columns: {sorted(missing)}")

    source["UNLOCODE"] = source["UNLOCODE"].astype("string").str.strip().str.upper()
    if len(source) != EXPECTED_RECORDS:
        raise ValueError(f"Expected {EXPECTED_RECORDS} records; found {len(source)}.")
    if source["UNLOCODE"].isna().any() or source["UNLOCODE"].eq("").any():
        raise ValueError("Missing UN/LOCODE.")
    if source["UNLOCODE"].duplicated().any():
        raise ValueError("Duplicate UN/LOCODE.")

    result = source.copy()
    gate = result.apply(classify_gate, axis=1)
    result = pd.concat([result, gate], axis=1)

    # Preserve upstream decision and eligibility data.
    for col in [
        "Script49_Eligibility_Classification",
        "Script49_Recommended_Use",
        "Researcher_Coordinate_Decision",
        "Researcher_Operational_Decision",
        "AIS_Transit_Evidence_Status",
    ]:
        if not result[col].fillna("").astype(str).equals(source[col].fillna("").astype(str)):
            raise AssertionError(f"Upstream field changed: {col}")

    if result["May_Enter_Empirical_Baseline_59"].any():
        raise AssertionError("Script 59 must not admit empirical baseline nodes.")
    if result["May_Enter_Sensitivity_Model_59"].any():
        raise AssertionError("Script 59 must not admit sensitivity nodes automatically.")
    if result["Operational_Gate_Status_59"].eq(
        "ELIGIBLE_FOR_RESEARCHER_FINAL_NETWORK_REVIEW"
    ).any():
        # With current all-pending Script 58 input, no record should pass.
        if source["Researcher_Coordinate_Decision"].astype(str).str.upper().eq("PENDING").all():
            raise AssertionError("Unexpected gate pass while all coordinate decisions are pending.")

    summary = build_summary(result)

    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(REGISTER_FILE, index=False)
    summary.to_csv(SUMMARY_FILE, index=False)
    write_report(result, summary)

    print("=" * 88)
    print("SCRIPT 59: OPERATIONAL NETWORK ELIGIBILITY GATE")
    print("=" * 88)
    print(f"\nInput records: {len(source)}")
    print("UN/LOCODE uniqueness and coverage: PASS")
    print("Script 49 eligibility preserved: PASS")
    print("Script 58 researcher decisions preserved: PASS")
    print("No empirical baseline nodes admitted: PASS")
    print("No sensitivity nodes admitted automatically: PASS")
    print("No simulation network files modified: PASS")
    print("\nSUMMARY")
    print(summary.to_string(index=False))
    print("\nGATE STATUS COUNTS")
    print(result["Operational_Gate_Status_59"].value_counts().to_string())
    print("\nOUTPUTS")
    print(REGISTER_FILE.relative_to(ROOT))
    print(SUMMARY_FILE.relative_to(ROOT))
    print(REPORT_FILE.relative_to(ROOT))
    print("\nSCRIPT 59 COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()
