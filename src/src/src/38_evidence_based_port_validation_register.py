"""
SCRIPT 38 — EVIDENCE-BASED PORT VALIDATION REGISTER

Purpose
-------
Converts Script 37's preliminary 19-port audit into a researcher-reviewable
validation register. It preserves the Script 37 evidence and network fields,
adds explicit manual-review fields, and generates a validation summary.

Important research safeguards
-----------------------------
1. No port is automatically accepted, rejected, or removed.
2. No coordinates are invented or silently accepted.
3. A port-call record does not prove a Strait of Hormuz transit.
4. Network absence does not prove geographic irrelevance.
5. Port and terminal identities/coordinates must remain distinguishable.
6. Existing researcher-entered decisions are preserved on reruns.

Required inputs
---------------
outputs/tables/37_port_relevance_validation_audit.csv
outputs/tables/37_port_manual_validation_priority.csv

Run from the project root:
    python src/38_evidence_based_port_validation_register.py
"""

from pathlib import Path
from datetime import datetime
import pandas as pd


SCRIPT_NAME = "SCRIPT 38 — EVIDENCE-BASED PORT VALIDATION REGISTER"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TABLES_DIR = PROJECT_ROOT / "outputs" / "tables"
REPORTS_DIR = PROJECT_ROOT / "outputs" / "reports"

AUDIT_FILE = TABLES_DIR / "37_port_relevance_validation_audit.csv"
PRIORITY_FILE = TABLES_DIR / "37_port_manual_validation_priority.csv"

OUTPUT_FILE = TABLES_DIR / "38_port_evidence_validation_register.csv"
SUMMARY_FILE = TABLES_DIR / "38_port_validation_summary.csv"
REPORT_FILE = REPORTS_DIR / "38_port_validation_register_report.txt"


# These are researcher-input fields. Script 38 deliberately leaves decisions
# pending rather than deriving them from preliminary labels.
MANUAL_FIELDS = {
    "Researcher_Validated_Port_Name": "",
    "Researcher_Validated_Facility_Name": "",
    "Validated_Facility_Type": "PENDING_MANUAL_REVIEW",
    "Validated_Geographic_Region": "PENDING_MANUAL_REVIEW",
    "Identity_Validation_Status": "PENDING",
    "Identity_Evidence_Description": "",
    "Identity_Evidence_URL": "",
    "Coordinate_Validation_Status": "PENDING",
    "Validated_Latitude": pd.NA,
    "Validated_Longitude": pd.NA,
    "Validated_Coordinate_Type": "NOT_ASSIGNED",
    "Coordinate_Evidence_Description": "",
    "Coordinate_Evidence_URL": "",
    "Port_Terminal_Distinction_Notes": "",
    "Operational_Role": "PENDING_RESEARCHER_DECISION",
    "Operational_Inclusion_Decision": "PENDING",
    "Inclusion_or_Exclusion_Justification": "",
    "AIS_or_Transit_Evidence_Status": "NOT_VERIFIED",
    "AIS_or_Transit_Evidence_Reference": "",
    "Researcher_Review_Status": "NOT_STARTED",
    "Researcher_Reviewer_Notes": "",
    "Last_Reviewed_Date": "",
}


def stop(message: str) -> None:
    raise SystemExit(f"\nERROR: {message}\n")


def read_csv_checked(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        stop(
            f"Required {label} file not found:\n{path}\n"
            "Check that Script 37 completed and that you are running "
            "this script from the project folder."
        )
    try:
        return pd.read_csv(path)
    except Exception as exc:
        stop(f"Could not read {label} file: {exc}")


def preserve_manual_entries(existing: pd.DataFrame,
                             fresh: pd.DataFrame) -> pd.DataFrame:
    """Preserve researcher-entered values when the script is rerun."""
    key = "UN_LOCODE"
    if key not in existing.columns or key not in fresh.columns:
        return fresh

    manual_columns = [c for c in MANUAL_FIELDS if c in existing.columns]
    if not manual_columns:
        return fresh

    old = existing[[key] + manual_columns].drop_duplicates(key, keep="last")
    fresh = fresh.drop(columns=manual_columns, errors="ignore")
    merged = fresh.merge(old, on=key, how="left", validate="one_to_one")

    for column, default in MANUAL_FIELDS.items():
        if column not in merged.columns:
            merged[column] = default
        else:
            # Fill only missing values; never replace a researcher's entry.
            if isinstance(default, str):
                merged[column] = merged[column].fillna(default)

    return merged


def build_register(audit: pd.DataFrame,
                   priority: pd.DataFrame) -> pd.DataFrame:
    required_audit = {
        "UN_LOCODE",
        "Port_Name_in_Master",
        "Country_Code",
        "Preliminary_Geographic_Role",
        "Identity_Evidence_Assessment",
        "Coordinate_Assessment",
        "Observed_Call_Count",
        "Observed_Vessel_Count",
        "Network_Match_Status",
        "AIS_Transit_Verification",
        "Final_Researcher_Status",
    }
    missing = sorted(required_audit - set(audit.columns))
    if missing:
        stop(f"Script 37 audit is missing expected columns: {missing}")

    if audit["UN_LOCODE"].duplicated().any():
        duplicates = audit.loc[
            audit["UN_LOCODE"].duplicated(keep=False), "UN_LOCODE"
        ].astype(str).tolist()
        stop(f"Duplicate UN/LOCODE keys in audit: {duplicates}")

    # Priority information is attached by UN/LOCODE, without changing the
    # source audit's original fields.
    priority_columns = [
        c for c in [
            "Manual_Review_Priority",
            "Identity_Review_Flag",
            "Coordinate_Review_Flag",
            "Transit_Evidence_Status",
        ]
        if c in priority.columns
    ]

    if "UN_LOCODE" not in priority.columns:
        stop("Priority file does not contain UN_LOCODE.")

    priority_small = priority[["UN_LOCODE"] + priority_columns].drop_duplicates(
        "UN_LOCODE", keep="last"
    )

    register = audit.merge(
        priority_small,
        on="UN_LOCODE",
        how="left",
        suffixes=("", "_priority"),
        validate="one_to_one",
    )

    # Add explicit researcher decision fields.
    for column, default in MANUAL_FIELDS.items():
        register[column] = default

    # Transparent derived workflow flags; these are not validation decisions.
    register["Script38_Review_Queue"] = "REVIEW_REQUIRED"
    register.loc[
        register["Identity_Evidence_Assessment"].astype(str).str.contains(
            "STRONG", case=False, na=False
        ),
        "Script38_Review_Queue",
    ] = "IDENTITY_SUPPORT_RECORDED_STILL_REQUIRES_REVIEW"

    register["Script38_Coordinate_Queue"] = "COORDINATE_REVIEW_REQUIRED"
    register.loc[
        register["Coordinate_Assessment"].astype(str).str.contains(
            "AVAILABLE", case=False, na=False
        ),
        "Script38_Coordinate_Queue",
    ] = "SOURCE_COORDINATE_EVIDENCE_RECORDED_VERIFY_BEFORE_ACCEPTANCE"

    register["Script38_Transit_Queue"] = (
        "AIS_OR_EQUIVALENT_TRANSIT_EVIDENCE_NOT_ESTABLISHED"
    )

    # Keep useful identifiers and source fields at the front.
    front = [
        "UN_LOCODE",
        "Port_Name_in_Master",
        "Country_Code",
        "Preliminary_Geographic_Role",
        "Research_Relevance_Screen",
        "Provisional_Facility_Type",
        "Facility_or_Port_System",
        "Identity_Evidence_Assessment",
        "Coordinate_Assessment",
        "Accepted_Latitude",
        "Accepted_Longitude",
        "Coordinate_Reference_Type",
        "Observed_Call_Count",
        "Observed_Vessel_Count",
        "In_Degree",
        "Out_Degree",
        "Betweenness_Centrality",
        "Network_Match_Status",
        "AIS_Transit_Verification",
        "Primary_Evidence_URL",
        "Independent_Secondary_Evidence_URL",
        "Research_Notes",
        "Manual_Review_Priority",
        "Script38_Review_Queue",
        "Script38_Coordinate_Queue",
        "Script38_Transit_Queue",
    ]
    front = [c for c in front if c in register.columns]
    remaining = [c for c in register.columns if c not in front]
    return register[front + remaining]


def make_summary(register: pd.DataFrame) -> pd.DataFrame:
    rows = []

    def add(metric, category, count):
        rows.append({
            "Metric": metric,
            "Category": str(category),
            "Port_Count": int(count),
        })

    add("Total ports", "All records", len(register))

    for column, metric in [
        ("Preliminary_Geographic_Role", "Preliminary geographic role"),
        ("Identity_Evidence_Assessment", "Identity evidence assessment"),
        ("Coordinate_Assessment", "Coordinate assessment"),
        ("Network_Match_Status", "Network match status"),
        ("Manual_Review_Priority", "Manual review priority"),
        ("Operational_Role", "Researcher operational role"),
        ("Operational_Inclusion_Decision", "Researcher inclusion decision"),
        ("Researcher_Review_Status", "Researcher review status"),
    ]:
        if column in register.columns:
            counts = register[column].fillna("NOT_RECORDED").value_counts()
            for category, count in counts.items():
                add(metric, category, count)

    return pd.DataFrame(rows)


def write_report(register: pd.DataFrame, summary: pd.DataFrame) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    network_col = "Network_Match_Status"
    network_counts = (
        register[network_col].fillna("NOT_RECORDED").value_counts()
        if network_col in register.columns else pd.Series(dtype=int)
    )

    lines = [
        SCRIPT_NAME,
        "=" * 72,
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Project root: {PROJECT_ROOT}",
        "",
        "REGISTER OVERVIEW",
        f"Ports retained: {len(register)}",
        f"Unique UN/LOCODEs: {register['UN_LOCODE'].nunique()}",
        "",
        "NETWORK MATCH STATUS",
    ]

    for category, count in network_counts.items():
        lines.append(f"- {category}: {count}")

    lines += [
        "",
        "RESEARCHER DECISION STATUS",
        "- No port has been automatically accepted or excluded.",
        "- Operational role remains pending researcher decision.",
        "- Inclusion decision remains pending researcher decision.",
        "- Existing manual entries are preserved when rerunning this script.",
        "",
        "RESEARCH SAFEGUARDS",
        "1. Preliminary geographic labels are screening classifications only.",
        "2. Port-call records do not establish a vessel's Strait transit.",
        "3. No AIS transit is confirmed by this script.",
        "4. Network absence does not establish geographic irrelevance.",
        "5. Source coordinates are not accepted as validated coordinates.",
        "6. Port and terminal identities/coordinates must remain distinct.",
        "7. Operational inclusion requires documented researcher justification.",
        "",
        "RECOMMENDED MANUAL WORKFLOW",
        "1. Confirm the port/facility identity using authoritative evidence.",
        "2. Record whether the identity is a port, terminal, or port system.",
        "3. Verify coordinates and explicitly state their reference type.",
        "4. Record evidence descriptions and URLs.",
        "5. Assign geographic region and operational role.",
        "6. Decide core, alternative, pending, or excluded status with reasons.",
        "7. Keep AIS transit verification separate from port-call evidence.",
        "",
        "OUTPUTS",
        str(OUTPUT_FILE),
        str(SUMMARY_FILE),
        str(REPORT_FILE),
        "",
        "SUMMARY TABLE",
        summary.to_string(index=False),
    ]

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    print("\n" + SCRIPT_NAME)
    print("=" * 72)

    audit = read_csv_checked(AUDIT_FILE, "Script 37 audit")
    priority = read_csv_checked(PRIORITY_FILE, "Script 37 priority")

    register = build_register(audit, priority)

    # Preserve manual decisions from a previous Script 38 run.
    if OUTPUT_FILE.exists():
        try:
            previous = pd.read_csv(OUTPUT_FILE)
            register = preserve_manual_entries(previous, register)
            print("Existing researcher-entered fields preserved.")
        except Exception as exc:
            stop(
                "Existing Script 38 register could not be read safely. "
                f"No output was written. Details: {exc}"
            )

    summary = make_summary(register)

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    register.to_csv(OUTPUT_FILE, index=False)
    summary.to_csv(SUMMARY_FILE, index=False)
    write_report(register, summary)

    print("\nSCRIPT 38 COMPLETED")
    print(f"Ports in validation register: {len(register)}")
    print(f"Unique UN/LOCODEs: {register['UN_LOCODE'].nunique()}")
    print("Automatic inclusion/exclusion decisions: 0")
    print("\nSaved:")
    print(f"- {OUTPUT_FILE}")
    print(f"- {SUMMARY_FILE}")
    print(f"- {REPORT_FILE}")
    print("\nNext action:")
    print("Open 38_port_evidence_validation_register.csv and complete")
    print("the researcher review fields using documented evidence.")


if __name__ == "__main__":
    main()
