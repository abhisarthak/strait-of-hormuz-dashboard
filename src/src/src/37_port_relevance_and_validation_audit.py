"""Script 37: Port relevance and validation audit for the Strait of Hormuz thesis.

This is a screening/audit script, NOT an AIS transit validator. It preserves the
existing researcher assessments and does not infer that any vessel crossed Hormuz.

Run from the project root:
    python src/37_port_relevance_and_validation_audit.py

Input files are located recursively by filename. Put the following files anywhere
inside the project if they are not already present:
    19_location_preliminary_evidence_register.csv
    21_port_network_metrics.csv
    18F3_locode_evidence_validation_register(1).csv (optional)

Outputs are written to outputs/tables and outputs/reports.
"""
from pathlib import Path
import sys
import pandas as pd

ROOT = Path.cwd()
TABLE_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"


def locate(filename: str, required: bool = True):
    matches = list(ROOT.rglob(filename))
    # Prefer a file outside outputs if duplicate copies exist, then shortest path.
    matches.sort(key=lambda p: ("outputs" in p.parts, len(p.parts)))
    if not matches:
        if required:
            raise FileNotFoundError(
                f"Could not find {filename} under {ROOT}. Copy it into the project, "
                "for example data/processed/, then rerun this script."
            )
        return None
    if len(matches) > 1:
        print(f"NOTE: multiple copies of {filename}; using {matches[0]}")
    return matches[0]


def clean_text(series):
    return series.fillna("").astype(str).str.strip()


def main():
    evidence_path = locate("19_location_preliminary_evidence_register.csv")
    network_path = locate("21_port_network_metrics.csv")
    validation_path = locate("18F3_locode_evidence_validation_register(1).csv", required=False)

    ports = pd.read_csv(evidence_path)
    network = pd.read_csv(network_path)
    validation = pd.read_csv(validation_path) if validation_path else None

    required_cols = {
        "UN_LOCODE", "Port_Name_in_Master", "Country_Code",
        "Provisional_Facility_Type", "Preliminary_Geographic_Role",
        "Identity_Evidence_Assessment", "Coordinate_Assessment",
        "AIS_Transit_Verification", "Final_Researcher_Status"
    }
    missing = required_cols - set(ports.columns)
    if missing:
        raise ValueError(f"Port evidence register is missing columns: {sorted(missing)}")
    if not {"UNLOCODE", "Observed_Call_Count", "Observed_Vessel_Count"}.issubset(network.columns):
        raise ValueError("Script 21 network metrics file has an unexpected schema.")

    ports["UN_LOCODE"] = clean_text(ports["UN_LOCODE"])
    network["UNLOCODE"] = clean_text(network["UNLOCODE"])
    if ports["UN_LOCODE"].duplicated().any():
        dupes = ports.loc[ports["UN_LOCODE"].duplicated(False), "UN_LOCODE"].tolist()
        raise ValueError(f"Duplicate LOCODEs in preliminary register: {dupes}")
    if network["UNLOCODE"].duplicated().any():
        raise ValueError("Duplicate LOCODEs in Script 21 network metrics.")

    keep_network = [c for c in ["UNLOCODE", "Observed_Call_Count", "Observed_Vessel_Count",
                                "In_Degree", "Out_Degree", "Betweenness_Centrality"]
                    if c in network.columns]
    result = ports.merge(network[keep_network], left_on="UN_LOCODE", right_on="UNLOCODE",
                         how="left", validate="one_to_one")
    result.drop(columns=["UNLOCODE"], inplace=True, errors="ignore")

    if validation is not None:
        validation["UN_LOCODE"] = clean_text(validation["UN_LOCODE"])
        cols = [c for c in ["UN_LOCODE", "LOCODE_Identity_Verification",
                            "Coordinate_Verification_Status", "Independent_Corroboration_Status",
                            "Final_Researcher_Decision"] if c in validation.columns]
        result = result.merge(validation[cols], on="UN_LOCODE", how="left", validate="one_to_one")

    # These are screening labels based only on the existing preliminary register.
    def relevance(role):
        role = str(role).strip().upper()
        if role == "PERSIAN_GULF":
            return "PERSIAN_GULF_PORT_CANDIDATE"
        if role == "GULF_OF_OMAN":
            return "GULF_OF_OMAN_OUTSIDE_GULF_SCREENING"
        if role == "ARABIAN_SEA_OUTSIDE_HORMUZ":
            return "ARABIAN_SEA_OUTSIDE_HORMUZ_SCREENING"
        if role in {"ARABIAN_SEA", "GULF_OF_KUTCH"}:
            return "WIDER_REGIONAL_OR_ALTERNATIVE_PORT_CANDIDATE"
        return "ROLE_REQUIRES_MANUAL_REVIEW"

    result["Research_Relevance_Screen"] = result["Preliminary_Geographic_Role"].map(relevance)
    result["Identity_Review_Flag"] = result["Identity_Evidence_Assessment"].apply(
        lambda x: "REVIEW_IDENTITY" if "PARTIAL" in str(x).upper() else "IDENTITY_SUPPORT_RECORDED"
    )
    result["Coordinate_Review_Flag"] = result["Coordinate_Assessment"].apply(
        lambda x: "COORDINATE_REVIEW_REQUIRED" if any(k in str(x).upper() for k in
            ["PENDING", "REQUIRED", "UNRESOLVED", "INVALID", "REFERENCE_ONLY", "SEPARATE", "DISTINCTION"])
        else "COORDINATE_EVIDENCE_RECORDED_NOT_INDEPENDENTLY_CONFIRMED"
    )
    result["Transit_Evidence_Status"] = "NOT_VERIFIED_AIS_OR_EQUIVALENT_REQUIRED"
    result["Network_Match_Status"] = result["Observed_Call_Count"].apply(
        lambda x: "PRESENT_IN_SCRIPT21_NETWORK" if pd.notna(x) else "NOT_PRESENT_IN_SCRIPT21_NETWORK"
    )

    # Preserve source order and all original evidence fields.
    result["Observed_Call_Count"] = pd.to_numeric(result["Observed_Call_Count"], errors="coerce")
    result["Observed_Vessel_Count"] = pd.to_numeric(result["Observed_Vessel_Count"], errors="coerce")

    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = TABLE_DIR / "37_port_relevance_validation_audit.csv"
    out_priority = TABLE_DIR / "37_port_manual_validation_priority.csv"
    out_report = REPORT_DIR / "37_port_relevance_validation_audit_report.txt"

    result.to_csv(out_csv, index=False)
    priority_cols = [c for c in ["UN_LOCODE", "Port_Name_in_Master", "Country_Code",
        "Provisional_Facility_Type", "Preliminary_Geographic_Role", "Research_Relevance_Screen",
        "Observed_Call_Count", "Observed_Vessel_Count", "Identity_Evidence_Assessment",
        "Identity_Review_Flag", "Coordinate_Assessment", "Coordinate_Review_Flag",
        "AIS_Transit_Verification", "Transit_Evidence_Status", "Final_Researcher_Status"]
        if c in result.columns]
    priority = result[priority_cols].copy()
    priority["Manual_Review_Priority"] = "MEDIUM"
    priority.loc[priority["Identity_Review_Flag"] == "REVIEW_IDENTITY", "Manual_Review_Priority"] = "HIGH"
    priority.loc[priority["Coordinate_Review_Flag"] == "COORDINATE_REVIEW_REQUIRED", "Manual_Review_Priority"] = "HIGH"
    priority.loc[priority["Provisional_Facility_Type"].astype(str).str.contains("FACILITY|CITY|SYSTEM", case=False, na=False),
                 "Manual_Review_Priority"] = "HIGH"
    priority.to_csv(out_priority, index=False)

    role_counts = result["Research_Relevance_Screen"].value_counts(dropna=False).to_dict()
    identity_counts = result["Identity_Evidence_Assessment"].value_counts(dropna=False).to_dict()
    coordinate_counts = result["Coordinate_Assessment"].value_counts(dropna=False).to_dict()
    network_matches = int(result["Observed_Call_Count"].notna().sum())
    report = [
        "SCRIPT 37 — PORT RELEVANCE AND VALIDATION AUDIT",
        "=" * 58,
        f"Ports in preliminary evidence register: {len(ports)}",
        f"Ports matched to Script 21 network metrics: {network_matches}",
        f"Ports without a Script 21 network match: {len(ports) - network_matches}",
        "",
        "RESEARCH RELEVANCE SCREEN (preliminary geographic labels only):",
    ]
    report += [f"- {k}: {v}" for k, v in role_counts.items()]
    report += ["", "IDENTITY EVIDENCE ASSESSMENT:"]
    report += [f"- {k}: {v}" for k, v in identity_counts.items()]
    report += ["", "COORDINATE ASSESSMENT:"]
    report += [f"- {k}: {v}" for k, v in coordinate_counts.items()]
    report += [
        "", "CRITICAL INTERPRETATION:",
        "1. Geographic-role labels are preliminary screening categories, not validated routes.",
        "2. A Persian Gulf port call does not prove that a vessel crossed the Strait of Hormuz.",
        "3. No AIS transit is confirmed by this script; AIS/equivalent evidence remains required.",
        "4. Network call counts describe the analysed port-call dataset, not total port traffic.",
        "5. Coordinate evidence is not converted into accepted coordinates or treated as validated.",
        "6. This script does not remove ports, alter source records, or infer direct navigable legs.",
        "", "OUTPUTS:", str(out_csv), str(out_priority), str(out_report),
    ]
    out_report.write_text("\n".join(report), encoding="utf-8")

    print("\nSCRIPT 37 COMPLETED")
    print(f"Ports audited: {len(result)}")
    print(f"Matched to Script 21 network: {network_matches}/{len(result)}")
    print("\nPreliminary relevance screen:")
    for k, v in role_counts.items():
        print(f"  {k}: {v}")
    print("\nImportant: this is a screening audit, not route or AIS validation.")
    print(f"Saved: {out_csv}")
    print(f"Saved: {out_priority}")
    print(f"Saved: {out_report}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
