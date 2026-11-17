#!/usr/bin/env python3
"""
Script 53 — Batch coordinate evidence quality audit.

Reads the Script 51 master register and creates:
  outputs/tables/53_coordinate_evidence_quality_audit.csv
  outputs/tables/53_coordinate_evidence_summary.csv
  outputs/reports/53_coordinate_evidence_quality_audit_report.txt

This script is read-only with respect to the Script 51 master register.
It does not approve coordinates, alter evidence, or assign port eligibility.
"""

from pathlib import Path
from datetime import datetime
import re
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "outputs" / "tables" / "51_primary_source_coordinate_evidence_register.csv"
OUT_TABLES = ROOT / "outputs" / "tables"
OUT_REPORTS = ROOT / "outputs" / "reports"

EXPECTED_CODES = {
    "AEAUH", "AEFJR", "AEKLF", "AERKT", "AESHJ", "BHKBS",
    "INHZA", "INIXY", "INPPV", "IQUQR", "KWSAA", "KWSWK",
    "OMDQM", "PKKIA", "QAQAP", "QAQCH", "QAUMS", "SADMM", "SAJUB",
}

REQUIRED_COLUMNS = [
    "UN_LOCODE", "Port_Name_in_Master",
    "Primary_Source_Organization_Reviewed", "Primary_Source_Coordinate_Scope",
    "Primary_Source_Latitude", "Primary_Source_Longitude",
    "Secondary_Source_Organization_Reviewed", "Secondary_Source_Coordinate_Scope",
    "Secondary_Source_Latitude", "Secondary_Source_Longitude",
    "Independent_Corroboration_Status", "Coordinate_Validation_Status",
    "Coordinate_Confidence", "Research_Progress_Status",
]

COORD_FIELDS = [
    ("Primary", "Primary_Source_Latitude", "Primary_Source_Longitude"),
    ("Secondary", "Secondary_Source_Latitude", "Secondary_Source_Longitude"),
]

def clean(value):
    if pd.isna(value):
        return ""
    return str(value).strip()

def is_blank(value):
    return clean(value) == ""

def as_float(value):
    if is_blank(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return "INVALID"

def add_issue(issues, severity, code):
    issues.append((severity, code))

def main():
    if not MASTER.exists():
        raise FileNotFoundError(f"Master register not found: {MASTER}")

    OUT_TABLES.mkdir(parents=True, exist_ok=True)
    OUT_REPORTS.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(MASTER, dtype={"UN_LOCODE": "string"})
    missing_columns = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_columns:
        raise ValueError("Required columns missing from master: " + ", ".join(missing_columns))

    if df["UN_LOCODE"].duplicated().any():
        dupes = df.loc[df["UN_LOCODE"].duplicated(keep=False), "UN_LOCODE"].astype(str).tolist()
        raise ValueError(f"Duplicate UN_LOCODE values found; audit stopped: {dupes}")

    audit_rows = []
    for _, row in df.iterrows():
        code = clean(row.get("UN_LOCODE"))
        port_name = clean(row.get("Port_Name_in_Master"))
        issues = []
        notes = []

        p_org = clean(row.get("Primary_Source_Organization_Reviewed"))
        p_scope = clean(row.get("Primary_Source_Coordinate_Scope"))
        s_org = clean(row.get("Secondary_Source_Organization_Reviewed"))
        s_scope = clean(row.get("Secondary_Source_Coordinate_Scope"))
        corroboration = clean(row.get("Independent_Corroboration_Status")).upper()
        validation = clean(row.get("Coordinate_Validation_Status")).upper()
        confidence = clean(row.get("Coordinate_Confidence")).upper()
        progress = clean(row.get("Research_Progress_Status")).upper()

        # Source metadata / likely malformed concatenation checks.
        for label, org, scope in [
            ("PRIMARY", p_org, p_scope),
            ("SECONDARY", s_org, s_scope),
        ]:
            if not org:
                add_issue(issues, "HIGH", f"{label}_SOURCE_ORGANIZATION_MISSING")
            if not scope:
                add_issue(issues, "MEDIUM", f"{label}_COORDINATE_SCOPE_MISSING")
            # Catch a scope-like token accidentally appended to an organization cell.
            if re.search(r"(PORT_|TERMINAL_|BERTH_|BUOY_|LOCATION_|GAZETTEER_|NAUTICAL_)", org):
                add_issue(issues, "HIGH", f"{label}_ORGANIZATION_FIELD_MAY_CONTAIN_CONCATENATED_SCOPE")
                notes.append(f"{label.lower()} organization field contains a scope-like token; inspect CSV field alignment.")

        # Coordinate pair integrity and geographic ranges.
        coord_presence = {}
        for label, lat_col, lon_col in COORD_FIELDS:
            lat = as_float(row.get(lat_col))
            lon = as_float(row.get(lon_col))
            if lat == "INVALID" or lon == "INVALID":
                add_issue(issues, "HIGH", f"{label.upper()}_COORDINATE_NON_NUMERIC")
                coord_presence[label] = "INVALID"
            elif (lat is None) != (lon is None):
                add_issue(issues, "HIGH", f"{label.upper()}_COORDINATE_PAIR_INCOMPLETE")
                coord_presence[label] = "INCOMPLETE"
            elif lat is None and lon is None:
                coord_presence[label] = "ABSENT"
            else:
                coord_presence[label] = "PRESENT"
                if not (-90 <= lat <= 90):
                    add_issue(issues, "HIGH", f"{label.upper()}_LATITUDE_OUT_OF_RANGE")
                if not (-180 <= lon <= 180):
                    add_issue(issues, "HIGH", f"{label.upper()}_LONGITUDE_OUT_OF_RANGE")

        # Independence is not inferred from matching numbers alone.
        if "SAME_AUTHORITY" in corroboration or "SAME_OPERATOR" in corroboration:
            add_issue(issues, "MEDIUM", "SOURCES_NOT_ORGANIZATIONALLY_INDEPENDENT")
        if "NO_COORDINATE_CORROBORATION" in corroboration or "ONLY_NO_KPA_COORDINATE" in corroboration:
            add_issue(issues, "MEDIUM", "INDEPENDENT_COORDINATE_CORROBORATION_NOT_ESTABLISHED")
        if "DIFFERENT" in corroboration or "CONFLICT" in corroboration:
            add_issue(issues, "MEDIUM", "COORDINATE_OR_REFERENCE_SCOPE_DIFFERENCE_REQUIRES_REVIEW")

        # Scope-specific checks: these must not be treated as generic port points.
        scope_text = (p_scope + " " + s_scope + " " + corroboration).upper()
        if any(token in scope_text for token in ["FAIRWAY_BUOY", "PILOT_STATION", "PILOTING", "BREAKWATER"]):
            add_issue(issues, "HIGH", "NAVIGATIONAL_OR_BOUNDARY_REFERENCE_NOT_GENERIC_PORT_COORDINATE")
        if any(token in scope_text for token in ["TERMINAL", "BERTH", "INDUSTRIAL_PLANT"]):
            add_issue(issues, "HIGH", "FACILITY_SPECIFIC_REFERENCE_REQUIRES_SOURCE_CALL_FACILITY_MAPPING")
        if any(token in scope_text for token in ["POLYGON", "PORT_LIMIT", "NOT_PORT_CENTROID"]):
            add_issue(issues, "MEDIUM", "PORT_BOUNDARY_OR_POLYGON_NOT_A_SINGLE_PORT_POINT")
        if "MULTIMODAL_LOCATION_CODE_POINT" in scope_text:
            add_issue(issues, "HIGH", "UNLOCODE_MULTIMODAL_POINT_NOT_CONFIRMED_AS_PORT_FACILITY")
        if "DISTINCT_PORT_LOCATION_NOT_CORROBORATION" in scope_text:
            add_issue(issues, "HIGH", "SECONDARY_POINT_IS_A_DIFFERENT_PORT_NOT_CORROBORATION")

        # Known facility mapping cautions from the register's own labels/evidence.
        if code == "QAUMS" and "QATALUM" in port_name.upper():
            add_issue(issues, "HIGH", "QAUMS_MASTER_NAME_QATALUM_VERSUS_MESAIEED_PORT_EVIDENCE_REQUIRES_FACILITY_RECONCILIATION")
            notes.append("Master name is Qatalum; current evidence describes the wider Mesaieed port system. Establish the source-call facility before coordinate selection.")
        if code == "AESHJ" and "FAIRWAY_BUOY" in p_scope.upper():
            notes.append("Primary coordinate is a fairway buoy; do not use as port or terminal coordinate.")
        if code == "AERKT" and "MAIN_BREAKWATER" in p_scope.upper():
            notes.append("Primary point is a legal main-breakwater reference for Ras Al Khaimah Port specifically.")
        if code == "IQUQR" and "TWO_DISTINCT_TERMINAL" in corroboration:
            notes.append("Primary and secondary coordinates refer to different Umm Qasr terminals.")
        if code in {"OMDQM", "QAUMS"} and "POLYGON" in p_scope.upper():
            notes.append("Official evidence is a port-limit polygon; no official single-point coordinate is established.")
        if code in {"QAQAP", "QAQCH"} and coord_presence["Primary"] == "ABSENT":
            notes.append("No primary geodetic coordinate established in reviewed evidence.")
        if code == "KWSAA" and coord_presence["Primary"] == "ABSENT":
            notes.append("Reviewed Kuwait Ports Authority source establishes identity/function but not a coordinate.")
        if code == "SAJUB" and coord_presence["Primary"] == "ABSENT":
            notes.append("No coordinate-bearing primary authority source was extracted.")

        # Research status / approval guardrails.
        if validation not in {"", "PENDING", "PENDING_RECONCILIATION"}:
            add_issue(issues, "HIGH", "COORDINATE_VALIDATION_STATUS_NOT_PENDING_REVIEW")
        if confidence not in {"", "NOT_ASSESSED", "PENDING"}:
            add_issue(issues, "MEDIUM", "COORDINATE_CONFIDENCE_ALREADY_SET_REQUIRES_REVIEW")

        # Deduplicate while preserving order.
        seen = set()
        issue_codes = []
        for severity, issue in issues:
            if issue not in seen:
                issue_codes.append(issue)
                seen.add(issue)
        severities = [s for s, i in issues]
        if "HIGH" in severities:
            record_status = "RESEARCHER_REVIEW_REQUIRED_HIGH"
        elif "MEDIUM" in severities:
            record_status = "RESEARCHER_REVIEW_REQUIRED_MEDIUM"
        else:
            record_status = "NO_AUTOMATED_FLAGS_MANUAL_APPROVAL_STILL_REQUIRED"

        audit_rows.append({
            "UN_LOCODE": code,
            "Port_Name_in_Master": port_name,
            "Primary_Coordinate_Pair_Status": coord_presence["Primary"],
            "Secondary_Coordinate_Pair_Status": coord_presence["Secondary"],
            "Primary_Source_Organization_Reviewed": p_org,
            "Primary_Source_Coordinate_Scope": p_scope,
            "Secondary_Source_Organization_Reviewed": s_org,
            "Secondary_Source_Coordinate_Scope": s_scope,
            "Independent_Corroboration_Status": corroboration,
            "Coordinate_Validation_Status": validation,
            "Coordinate_Confidence": confidence,
            "Research_Progress_Status": progress,
            "Audit_Flag_Count": len(issue_codes),
            "Audit_Flags": " | ".join(issue_codes),
            "Audit_Notes": " ".join(notes),
            "Automated_Audit_Classification": record_status,
            "Researcher_Approval_Required": "YES",
        })

    audit = pd.DataFrame(audit_rows)

    # Coverage checks against the expected 19-record universe.
    observed = set(audit["UN_LOCODE"].astype(str))
    missing_codes = sorted(EXPECTED_CODES - observed)
    unexpected_codes = sorted(observed - EXPECTED_CODES)

    summary_rows = []
    summary_rows.append({"Metric": "Master row count", "Value": len(df)})
    summary_rows.append({"Metric": "Master column count", "Value": len(df.columns)})
    summary_rows.append({"Metric": "Unique UN_LOCODE count", "Value": df["UN_LOCODE"].nunique()})
    summary_rows.append({"Metric": "Expected code coverage", "Value": f"{len(EXPECTED_CODES & observed)}/{len(EXPECTED_CODES)}"})
    summary_rows.append({"Metric": "Missing expected codes", "Value": ", ".join(missing_codes) if missing_codes else "NONE"})
    summary_rows.append({"Metric": "Unexpected codes", "Value": ", ".join(unexpected_codes) if unexpected_codes else "NONE"})
    summary_rows.append({"Metric": "Records with high-priority flags", "Value": int((audit["Automated_Audit_Classification"] == "RESEARCHER_REVIEW_REQUIRED_HIGH").sum())})
    summary_rows.append({"Metric": "Records with medium-priority flags", "Value": int((audit["Automated_Audit_Classification"] == "RESEARCHER_REVIEW_REQUIRED_MEDIUM").sum())})
    summary_rows.append({"Metric": "Primary coordinate pairs present", "Value": int((audit["Primary_Coordinate_Pair_Status"] == "PRESENT").sum())})
    summary_rows.append({"Metric": "Primary coordinate pairs absent", "Value": int((audit["Primary_Coordinate_Pair_Status"] == "ABSENT").sum())})
    summary_rows.append({"Metric": "Secondary coordinate pairs present", "Value": int((audit["Secondary_Coordinate_Pair_Status"] == "PRESENT").sum())})
    summary_rows.append({"Metric": "Coordinate validation still pending", "Value": int(audit["Coordinate_Validation_Status"].isin(["PENDING", "PENDING_RECONCILIATION"]).sum())})
    summary_rows.append({"Metric": "Coordinate confidence not assessed", "Value": int(audit["Coordinate_Confidence"].isin(["", "NOT_ASSESSED"]).sum())})
    summary = pd.DataFrame(summary_rows)

    audit_path = OUT_TABLES / "53_coordinate_evidence_quality_audit.csv"
    summary_path = OUT_TABLES / "53_coordinate_evidence_summary.csv"
    report_path = OUT_REPORTS / "53_coordinate_evidence_quality_audit_report.txt"

    audit.to_csv(audit_path, index=False)
    summary.to_csv(summary_path, index=False)

    flagged = audit[audit["Audit_Flag_Count"] > 0]
    lines = [
        "SCRIPT 53 — COORDINATE EVIDENCE QUALITY AUDIT",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Master input: {MASTER.relative_to(ROOT)}",
        "",
        "SCOPE AND LIMITATIONS",
        "- Read-only audit: the Script 51 master register was not modified.",
        "- Automated flags identify review needs; they do not validate or reject coordinates.",
        "- A source coordinate is not automatically a port coordinate; scope is assessed separately.",
        "- Matching coordinates do not prove source independence.",
        "- Final coordinate approval and operational inclusion remain researcher decisions.",
        "",
        "SUMMARY",
        summary.to_string(index=False),
        "",
        "FLAGGED RECORDS",
    ]
    if flagged.empty:
        lines.append("No automated flags were generated. Manual researcher approval is still required.")
    else:
        for _, r in flagged.iterrows():
            lines.append(
                f"{r['UN_LOCODE']} | {r['Port_Name_in_Master']} | "
                f"{r['Automated_Audit_Classification']} | {r['Audit_Flags']}"
            )
            if r["Audit_Notes"]:
                lines.append(f"  Notes: {r['Audit_Notes']}")

    lines += [
        "",
        "RECORDS WITHOUT AUTOMATED FLAGS",
    ]
    unflagged = audit[audit["Audit_Flag_Count"] == 0]
    lines.append(", ".join(unflagged["UN_LOCODE"].astype(str).tolist()) if not unflagged.empty else "NONE")
    lines += [
        "",
        "OUTPUTS",
        str(audit_path.relative_to(ROOT)),
        str(summary_path.relative_to(ROOT)),
        str(report_path.relative_to(ROOT)),
        "",
        "MASTER REGISTER INTEGRITY",
        f"Rows read: {len(df)}",
        f"Columns read: {len(df.columns)}",
        "Master register modified: NO",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")

    print("SCRIPT 53 COMPLETED — READ-ONLY AUDIT")
    print(f"Master rows: {len(df)}")
    print(f"Master columns: {len(df.columns)}")
    print(f"Audit records: {len(audit)}")
    print(f"Flagged records: {len(flagged)}")
    print(f"Missing expected codes: {missing_codes if missing_codes else 'NONE'}")
    print(f"Unexpected codes: {unexpected_codes if unexpected_codes else 'NONE'}")
    print(f"Master modified: NO")
    print(f"Audit: {audit_path.relative_to(ROOT)}")
    print(f"Summary: {summary_path.relative_to(ROOT)}")
    print(f"Report: {report_path.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
