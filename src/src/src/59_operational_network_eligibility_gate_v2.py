"""
SCRIPT 59 v2: OPERATIONAL NETWORK ELIGIBILITY GATE — REPORTING CORRECTION
-------------------------------------------------------------------------
Reads Script 58 researcher decisions and creates a corrected downstream gate.
The original Script 59 files are not overwritten.

Corrections:
- Descriptive context is restricted to Script 49 descriptive-reference classes.
- Regional/sensitivity candidates are explicitly labelled as candidates, not
  descriptive-context records and not admitted simulation nodes.
- AIS transit is never independently verified by this script, regardless of
  a status label or URL in the researcher register.

Input:
    outputs/tables/58_researcher_coordinate_approval_register.csv

Outputs:
    outputs/tables/59_operational_network_eligibility_register_v2.csv
    outputs/tables/59_operational_network_eligibility_summary_v2.csv
    outputs/reports/59_operational_network_eligibility_report_v2.txt
"""

from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

INPUT_FILE = TABLE_DIR / "58_researcher_coordinate_approval_register.csv"
REGISTER_FILE = TABLE_DIR / "59_operational_network_eligibility_register_v2.csv"
SUMMARY_FILE = TABLE_DIR / "59_operational_network_eligibility_summary_v2.csv"
REPORT_FILE = REPORT_DIR / "59_operational_network_eligibility_report_v2.txt"

EXPECTED = 19

REQUIRED = {
    "UNLOCODE", "Port_Name",
    "Script49_Eligibility_Classification", "Script49_Recommended_Use",
    "Researcher_Coordinate_Decision", "Approved_Latitude", "Approved_Longitude",
    "Approved_Coordinate_Reference_Object", "Approved_Coordinate_Scope",
    "Approved_Datum_or_CRS", "Researcher_Operational_Decision",
    "AIS_Transit_Evidence_Status", "AIS_Evidence_Source_URL",
}


def clean(value):
    return "" if pd.isna(value) else str(value).strip()


def valid_pair(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
        return np.isfinite(lat) and np.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180
    except (TypeError, ValueError):
        return False


def classify(row):
    eligibility = clean(row["Script49_Eligibility_Classification"]).upper()
    recommended = clean(row["Script49_Recommended_Use"]).upper()
    coordinate_decision = clean(row["Researcher_Coordinate_Decision"]).upper()
    operational_decision = clean(row["Researcher_Operational_Decision"]).upper()

    coord_pair_valid = valid_pair(row["Approved_Latitude"], row["Approved_Longitude"])
    coordinate_approved = (
        coordinate_decision in {"APPROVED", "APPROVED_WITH_LIMITATIONS"}
        and coord_pair_valid
        and bool(clean(row["Approved_Coordinate_Reference_Object"]))
        and bool(clean(row["Approved_Coordinate_Scope"]))
        and bool(clean(row["Approved_Datum_or_CRS"]))
    )
    operational_approved = operational_decision in {
        "APPROVED", "APPROVED_FOR_OPERATIONAL_NETWORK"
    }

    is_descriptive = eligibility.startswith("DESCRIPTIVE_REFERENCE_ONLY")
    is_regional_candidate = eligibility.startswith("REGIONAL_OR_SENSITIVITY_CANDIDATE")
    is_identity_pending = "PENDING_IDENTITY_REVIEW" in eligibility
    is_outside_observed = "NOT_IN_OBSERVED_NETWORK" in eligibility

    reasons = []
    if is_identity_pending:
        gate_class = "DESCRIPTIVE_ONLY_IDENTITY_REVIEW_REQUIRED"
        gate_status = "NOT_ELIGIBLE_FOR_OPERATIONAL_NETWORK_UNDER_CURRENT_CLASSIFICATION"
        reasons.append("Script 49 requires identity review; descriptive context only.")
    elif is_outside_observed:
        gate_class = "OUTSIDE_OBSERVED_NETWORK_MOVEMENT_EVIDENCE_REQUIRED"
        gate_status = "NOT_ELIGIBLE_FOR_EMPIRICAL_BASELINE_UNDER_CURRENT_EVIDENCE"
        reasons.append("Script 49 places this record outside the observed network.")
        reasons.append("New movement evidence and formal eligibility reassessment are required.")
    elif is_regional_candidate:
        gate_class = "REGIONAL_SENSITIVITY_CANDIDATE"
        if not coordinate_approved:
            reasons.append("Researcher coordinate approval is incomplete or lacks required reference metadata.")
        if not operational_approved:
            reasons.append("Researcher operational inclusion decision is incomplete.")
        gate_status = (
            "ELIGIBLE_FOR_RESEARCHER_FINAL_NETWORK_REVIEW"
            if coordinate_approved and operational_approved
            else "PENDING_COORDINATE_AND_OPERATIONAL_APPROVAL"
        )
    else:
        gate_class = "UNMAPPED_OR_UNRECOGNIZED_SCRIPT49_CLASS"
        gate_status = "BLOCKED_PENDING_CLASSIFICATION_REVIEW"
        reasons.append("Script 49 eligibility class does not match a defined gate rule.")

    if clean(row["AIS_Transit_Evidence_Status"]).upper() not in {"AIS_CONFIRMED", "CONFIRMED"}:
        reasons.append("AIS-confirmed Strait of Hormuz transit is not established in the researcher register.")

    return pd.Series({
        "Operational_Gate_Class_59_v2": gate_class,
        "Operational_Gate_Status_59_v2": gate_status,
        "Operational_Gate_Reason_59_v2": " | ".join(reasons),
        "Coordinate_Approved_For_Gate_59_v2": coordinate_approved,
        "Operational_Inclusion_Approved_59_v2": operational_approved,
        "Approved_Coordinate_Pair_Valid_59_v2": coord_pair_valid,

        # These are mutually meaningful use categories, not a universal True flag.
        "Descriptive_Context_Class_59_v2": is_descriptive,
        "Regional_Sensitivity_Candidate_Only_59_v2": is_regional_candidate,
        "Outside_Observed_Network_59_v2": is_outside_observed,

        # No automatic node admission by this gate.
        "May_Enter_Empirical_Baseline_59_v2": False,
        "May_Enter_Sensitivity_Model_59_v2": False,

        # AIS evidence can be flagged for review but never verified by this script.
        "AIS_Transit_Status_Reported_As_Confirmed_59_v2": (
            clean(row["AIS_Transit_Evidence_Status"]).upper()
            in {"AIS_CONFIRMED", "CONFIRMED"}
        ),
        "AIS_Evidence_URL_Provided_59_v2": bool(clean(row["AIS_Evidence_Source_URL"])),
        "AIS_Hormuz_Transit_Independently_Verified_By_Script59_v2": False,
        "AIS_Transit_Requires_Independent_Review_59_v2": True,
    })


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Required input not found: {INPUT_FILE}")
    source = pd.read_csv(INPUT_FILE)
    missing = REQUIRED - set(source.columns)
    if missing:
        raise ValueError(f"Missing Script 58 columns: {sorted(missing)}")

    source["UNLOCODE"] = source["UNLOCODE"].astype("string").str.strip().str.upper()
    if len(source) != EXPECTED:
        raise ValueError(f"Expected {EXPECTED} records, found {len(source)}.")
    if source["UNLOCODE"].isna().any() or source["UNLOCODE"].eq("").any():
        raise ValueError("Missing UN/LOCODE.")
    if source["UNLOCODE"].duplicated().any():
        raise ValueError("Duplicate UN/LOCODE.")

    result = pd.concat([source.copy(), source.apply(classify, axis=1)], axis=1)

    # Preserve source classifications and researcher decisions.
    for col in [
        "Script49_Eligibility_Classification",
        "Script49_Recommended_Use",
        "Researcher_Coordinate_Decision",
        "Researcher_Operational_Decision",
        "AIS_Transit_Evidence_Status",
        "AIS_Evidence_Source_URL",
    ]:
        if not result[col].fillna("").astype(str).equals(source[col].fillna("").astype(str)):
            raise AssertionError(f"Source field changed: {col}")

    # Gate invariants.
    if result["May_Enter_Empirical_Baseline_59_v2"].any():
        raise AssertionError("No empirical baseline node may be admitted by Script 59 v2.")
    if result["May_Enter_Sensitivity_Model_59_v2"].any():
        raise AssertionError("No sensitivity node may be admitted automatically.")
    if result["AIS_Hormuz_Transit_Independently_Verified_By_Script59_v2"].any():
        raise AssertionError("Script 59 cannot independently verify AIS transit.")

    # Mutually exclusive Script 49 usage groups: 6+3 descriptive records,
    # 10 regional/sensitivity candidates.
    if int(result["Descriptive_Context_Class_59_v2"].sum()) != 9:
        raise AssertionError("Expected 9 Script 49 descriptive-reference records.")
    if int(result["Regional_Sensitivity_Candidate_Only_59_v2"].sum()) != 10:
        raise AssertionError("Expected 10 regional/sensitivity candidates.")
    if int(result["Outside_Observed_Network_59_v2"].sum()) != 3:
        raise AssertionError("Expected 3 records outside the observed network.")

    summary_rows = [
        ("Total records assessed", len(result)),
        ("Script 49 descriptive-reference records", int(result["Descriptive_Context_Class_59_v2"].sum())),
        ("Regional/sensitivity candidates only", int(result["Regional_Sensitivity_Candidate_Only_59_v2"].sum())),
        ("Outside observed network; movement evidence required", int(result["Outside_Observed_Network_59_v2"].sum())),
        ("Pending coordinate and operational approval", int(result["Operational_Gate_Status_59_v2"].eq("PENDING_COORDINATE_AND_OPERATIONAL_APPROVAL").sum())),
        ("Eligible for researcher final network review", int(result["Operational_Gate_Status_59_v2"].eq("ELIGIBLE_FOR_RESEARCHER_FINAL_NETWORK_REVIEW").sum())),
        ("Empirical baseline nodes admitted", int(result["May_Enter_Empirical_Baseline_59_v2"].sum())),
        ("Sensitivity model nodes admitted", int(result["May_Enter_Sensitivity_Model_59_v2"].sum())),
        ("AIS transits independently verified by Script 59", int(result["AIS_Hormuz_Transit_Independently_Verified_By_Script59_v2"].sum())),
    ]
    summary = pd.DataFrame(summary_rows, columns=["Metric", "Value"])

    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(REGISTER_FILE, index=False)
    summary.to_csv(SUMMARY_FILE, index=False)

    with REPORT_FILE.open("w", encoding="utf-8") as f:
        f.write("SCRIPT 59 v2 — OPERATIONAL NETWORK ELIGIBILITY GATE\n")
        f.write("=" * 72 + "\n\n")
        f.write(summary.to_string(index=False))
        f.write("\n\nGATE STATUS COUNTS\n")
        f.write(result["Operational_Gate_Status_59_v2"].value_counts().to_string())
        f.write("\n\nRESEARCH LIMITATIONS\n")
        f.write(
            "- Descriptive reference, regional/sensitivity candidate, and outside-observed-network classes are kept distinct.\n"
            "- No nodes are admitted to the empirical baseline or sensitivity model.\n"
            "- Coordinate approval and operational inclusion remain separate researcher decisions.\n"
            "- A status label and URL do not constitute independent AIS transit verification.\n"
            "- No simulation network or upstream file is modified.\n"
        )

    print("=" * 78)
    print("SCRIPT 59 v2: OPERATIONAL NETWORK ELIGIBILITY GATE")
    print("=" * 78)
    print(f"Input records: {len(source)}")
    print("UN/LOCODE uniqueness and coverage: PASS")
    print("Script 49 classifications preserved: PASS")
    print("Script 58 researcher decisions preserved: PASS")
    print("9 descriptive-reference records correctly classified: PASS")
    print("10 regional/sensitivity candidates correctly classified: PASS")
    print("3 outside-observed-network records correctly classified: PASS")
    print("No empirical or sensitivity nodes admitted: PASS")
    print("AIS transit not independently verified: PASS")
    print("\nSUMMARY")
    print(summary.to_string(index=False))
    print("\nGATE STATUS COUNTS")
    print(result["Operational_Gate_Status_59_v2"].value_counts().to_string())
    print("\nOUTPUTS")
    print(REGISTER_FILE.relative_to(ROOT))
    print(SUMMARY_FILE.relative_to(ROOT))
    print(REPORT_FILE.relative_to(ROOT))
    print("\nSCRIPT 59 v2 COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()
