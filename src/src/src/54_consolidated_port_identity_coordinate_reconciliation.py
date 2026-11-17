#!/usr/bin/env python3
"""
SCRIPT 54 — CONSOLIDATED COORDINATE, IDENTITY AND ELIGIBILITY RECONCILIATION

Purpose
-------
Create one read-only, evidence-led register by joining:
- Script 38: identity / port evidence validation
- Script 39: coordinate validation
- Script 41: consolidated source-content verification
- Script 49: port eligibility assessment
- Script 51: primary-source coordinate evidence research
- Script 53: automated coordinate evidence quality audit

Outputs
-------
outputs/tables/54_consolidated_port_identity_coordinate_reconciliation.csv
outputs/tables/54_reconciliation_summary.csv
outputs/reports/54_consolidated_port_identity_coordinate_reconciliation_report.txt

Safeguards
----------
- Does not modify any upstream register.
- Joins only on exact UN_LOCODE.
- Rejects duplicate or missing join keys.
- Retains all 19 expected ports; does not drop unresolved records.
- Does not approve coordinates or operational inclusion.
- Distinguishes verified port identity from facility attribution.
- Does not treat a port call as proof of Strait of Hormuz transit.
- Preserves source register values in clearly named columns.
"""

from pathlib import Path
from datetime import datetime
from collections import Counter
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"

FILES = {
    "identity": TABLES / "38_port_evidence_validation_register.csv",
    "coordinates": TABLES / "39_port_coordinate_validation_register.csv",
    "source_review": TABLES / "41_manual_source_content_verification_register_consolidated.csv",
    "eligibility": TABLES / "49_port_eligibility_assessment.csv",
    "coordinate_evidence": TABLES / "51_primary_source_coordinate_evidence_register.csv",
    "quality_audit": TABLES / "53_coordinate_evidence_quality_audit.csv",
}

EXPECTED_CODES = {
    "AEAUH", "AEFJR", "AEKLF", "AERKT", "AESHJ", "BHKBS",
    "INHZA", "INIXY", "INPPV", "IQUQR", "KWSAA", "KWSWK",
    "OMDQM", "PKKIA", "QAQAP", "QAQCH", "QAUMS", "SADMM", "SAJUB",
}

OUT_REGISTER = TABLES / "54_consolidated_port_identity_coordinate_reconciliation.csv"
OUT_SUMMARY = TABLES / "54_reconciliation_summary.csv"
OUT_REPORT = REPORTS / "54_consolidated_port_identity_coordinate_reconciliation_report.txt"


def clean(v):
    if v is None or pd.isna(v):
        return ""
    return str(v).strip()


def norm(v):
    return clean(v).upper().replace(" ", "_")


def read_register(label, path):
    if not path.exists():
        raise FileNotFoundError(
            f"Required {label} register not found:\n{path}\n"
            "Check that the upstream script has been run and that the filename matches."
        )
    df = pd.read_csv(path, dtype={"UN_LOCODE": "string"})
    if "UN_LOCODE" not in df.columns:
        raise ValueError(f"{label} register has no UN_LOCODE column: {path}")
    df["UN_LOCODE"] = df["UN_LOCODE"].astype("string").str.strip().str.upper()
    if df["UN_LOCODE"].isna().any() or (df["UN_LOCODE"] == "").any():
        raise ValueError(f"{label} register contains blank UN_LOCODE values.")
    if df["UN_LOCODE"].duplicated().any():
        dupes = df.loc[df["UN_LOCODE"].duplicated(keep=False), "UN_LOCODE"].tolist()
        raise ValueError(f"{label} register has duplicate UN_LOCODE values: {dupes}")
    return df


def get(row, field):
    return clean(row[field]) if field in row.index else ""


def choose(*values):
    for value in values:
        v = clean(value)
        if v:
            return v
    return ""


def yes_no_present(lat, lon):
    return "YES" if clean(lat) and clean(lon) else "NO"


def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    regs = {name: read_register(name, path) for name, path in FILES.items()}
    indexes = {
        name: df.set_index("UN_LOCODE", drop=False)
        for name, df in regs.items()
    }

    identity_codes = set(regs["identity"]["UN_LOCODE"].astype(str))
    missing_expected = sorted(EXPECTED_CODES - identity_codes)
    unexpected = sorted(identity_codes - EXPECTED_CODES)
    if missing_expected or unexpected:
        raise ValueError(
            f"Script 38 expected-code coverage mismatch. "
            f"Missing={missing_expected}; unexpected={unexpected}"
        )

    # All upstream registers must be keyed uniquely. Missing rows in a
    # supporting register are retained as explicit missing-source statuses.
    codes = sorted(EXPECTED_CODES)
    output_rows = []

    for code in codes:
        rows = {}
        for name, idx in indexes.items():
            rows[name] = idx.loc[code] if code in idx.index else pd.Series(dtype="object")

        i = rows["identity"]
        c = rows["coordinates"]
        s = rows["source_review"]
        e = rows["eligibility"]
        ce = rows["coordinate_evidence"]
        qa = rows["quality_audit"]

        port_master = choose(
            get(i, "Port_Name_in_Master"),
            get(ce, "Port_Name_in_Master"),
            get(e, "Port_Name"),
        )
        validated_port = choose(
            get(i, "Researcher_Validated_Port_Name"),
            get(s, "Researcher_Validated_Port_Name"),
            get(e, "Validated_Port_Name"),
        )
        facility_name = choose(
            get(i, "Researcher_Validated_Facility_Name"),
            get(s, "Researcher_Validated_Facility_Name"),
            get(e, "Validated_Facility_Name"),
        )

        identity_status = choose(
            get(i, "Identity_Validation_Status"),
            get(s, "Identity_Validation_Status"),
            get(e, "Identity_Validation_Status"),
        )
        facility_resolution = choose(
            get(i, "Port_vs_Terminal_Resolution"),
            get(s, "Port_vs_Terminal_Resolution"),
            get(i, "Port_Terminal_Distinction_Notes"),
            get(s, "Port_Terminal_Distinction_Notes"),
        )

        coord_status = choose(
            get(c, "Coordinate_Validation_Status"),
            get(i, "Coordinate_Validation_Status"),
            get(e, "Coordinate_Validation_Status"),
        )
        coord_confidence = choose(
            get(c, "Coordinate_Confidence"),
            get(ce, "Coordinate_Confidence"),
        )

        validated_port_lat = choose(
            get(c, "Validated_Port_Latitude"),
            get(i, "Validated_Latitude"),
        )
        validated_port_lon = choose(
            get(c, "Validated_Port_Longitude"),
            get(i, "Validated_Longitude"),
        )
        validated_terminal_lat = get(c, "Validated_Terminal_Latitude")
        validated_terminal_lon = get(c, "Validated_Terminal_Longitude")

        primary_lat = get(ce, "Primary_Source_Latitude")
        primary_lon = get(ce, "Primary_Source_Longitude")
        secondary_lat = get(ce, "Secondary_Source_Latitude")
        secondary_lon = get(ce, "Secondary_Source_Longitude")

        eligibility_class = get(e, "Eligibility_Classification")
        recommended_use = get(e, "Recommended_Use")
        geographic_class = get(e, "Geographic_Class")
        operational_decision = choose(
            get(i, "Operational_Inclusion_Decision"),
            get(s, "Operational_Inclusion_Decision"),
            get(e, "Operational_Inclusion_Decision"),
        )
        transit_status = choose(
            get(i, "AIS_or_Transit_Evidence_Status"),
            get(s, "AIS_or_Transit_Evidence_Status"),
            get(e, "AIS_or_Transit_Evidence_Status"),
        )

        quality_flags = get(qa, "Audit_Flags")
        quality_class = get(qa, "Automated_Audit_Classification")
        source_review_status = choose(
            get(s, "Source_Content_Review_Status"),
            get(e, "Source_Content_Review_Status"),
        )
        researcher_review_status = choose(
            get(s, "Researcher_Review_Status"),
            get(i, "Researcher_Review_Status"),
            get(e, "Researcher_Review_Status"),
        )

        blockers = []
        if not rows["coordinates"].size:
            blockers.append("SCRIPT39_COORDINATE_REGISTER_ROW_MISSING")
        if not rows["source_review"].size:
            blockers.append("SCRIPT41_CONSOLIDATED_SOURCE_REVIEW_ROW_MISSING")
        if not rows["eligibility"].size:
            blockers.append("SCRIPT49_ELIGIBILITY_ROW_MISSING")
        if not rows["coordinate_evidence"].size:
            blockers.append("SCRIPT51_COORDINATE_EVIDENCE_ROW_MISSING")
        if not rows["quality_audit"].size:
            blockers.append("SCRIPT53_QUALITY_AUDIT_ROW_MISSING")

        if norm(identity_status) not in {
            "VERIFIED", "VERIFIED_CODE_IDENTITY", "IDENTITY_VERIFIED",
            "RESEARCHER_VERIFIED", "APPROVED",
        }:
            blockers.append("IDENTITY_NOT_IN_RECOGNISED_VERIFIED_STATE")

        if norm(coord_status) not in {"VALIDATED", "VERIFIED", "APPROVED", "ACCEPTED"}:
            blockers.append("COORDINATE_VALIDATION_NOT_APPROVED")

        if not validated_port_lat or not validated_port_lon:
            blockers.append("VALIDATED_PORT_COORDINATE_NOT_POPULATED")

        if norm(operational_decision) not in {
            "INCLUDE", "APPROVED_FOR_INCLUSION", "INCLUDE_IN_CORE",
            "INCLUDE_IN_SIMULATION",
        }:
            blockers.append("OPERATIONAL_INCLUSION_NOT_APPROVED")

        if norm(transit_status) not in {
            "AIS_TRANSIT_CONFIRMED", "CONFIRMED_AIS_TRANSIT", "TRANSIT_CONFIRMED",
        }:
            blockers.append("NO_CONFIRMED_AIS_TRANSIT_EVIDENCE")

        # Explicit, conservative identity/facility exception.
        if code == "QAUMS":
            if norm(identity_status) in {"VERIFIED_CODE_IDENTITY", "VERIFIED"}:
                identity_interpretation = "UNLOCODE_IDENTITY_VERIFIED_AS_UMM_SAID_MESAI EED".replace(" ", "")
            else:
                identity_interpretation = "IDENTITY_REQUIRES_REVIEW"
            facility_interpretation = (
                "FACILITY_ASSOCIATION_UNRESOLVED_QATALUM_MASTER_LABEL_CONFLICTS_WITH_VERIFIED_QAUMS_CODE_IDENTITY"
            )
            blockers.append("QAUMS_FACILITY_ASSOCIATION_REQUIRES_RESEARCHER_RESOLUTION")
        else:
            identity_interpretation = (
                "IDENTITY_VERIFIED" if norm(identity_status) in {
                    "VERIFIED", "VERIFIED_CODE_IDENTITY", "IDENTITY_VERIFIED",
                    "RESEARCHER_VERIFIED", "APPROVED",
                } else "IDENTITY_NOT_YET_VERIFIED"
            )
            facility_interpretation = (
                "FACILITY_MAPPING_RECORDED_PENDING_REVIEW"
                if "PENDING" in norm(facility_resolution)
                else choose(facility_resolution, "FACILITY_MAPPING_NOT_EXPLICITLY_RECORDED")
            )

        # Do not call any port a confirmed Hormuz transit based on call data.
        if "CONFIRMED" in norm(transit_status) and "AIS" in norm(transit_status):
            transit_interpretation = "AIS_TRANSIT_STATUS_REPORTED_CONFIRMED_IN_UPSTREAM_REGISTER_REQUIRES_EVIDENCE_REFERENCE_REVIEW"
        else:
            transit_interpretation = "NO_CONFIRMED_HORMUZ_TRANSIT_ESTABLISHED"

        # Reconciliation status is a workflow label, never a validation result.
        if blockers:
            reconciliation_status = "PENDING_RESEARCHER_REVIEW"
        else:
            reconciliation_status = "READY_FOR_FINAL_METHOD_REVIEW_NOT_AUTOMATICALLY_APPROVED"

        output_rows.append({
            "UN_LOCODE": code,
            "Port_Name_in_Master": port_master,
            "Researcher_Validated_Port_Name": validated_port,
            "Researcher_Validated_Facility_Name": facility_name,
            "Identity_Validation_Status": identity_status,
            "Identity_Interpretation": identity_interpretation,
            "Facility_Mapping_Status": facility_interpretation,
            "Facility_Resolution_Evidence_or_Notes": facility_resolution,
            "Country_Code": choose(get(i, "Country_Code"), get(ce, "Country_Code"), get(e, "Country_Code")),
            "Validated_Geographic_Region": choose(get(i, "Validated_Geographic_Region"), get(e, "Geographic_Region")),
            "Geographic_Class": geographic_class,
            "Research_Relevance_Screen": get(i, "Research_Relevance_Screen"),
            "Network_Match_Status": get(e, "Network_Match_Status"),
            "Observed_Call_Count": choose(get(i, "Observed_Call_Count"), get(e, "Observed_Call_Count")),
            "Observed_Vessel_Count": choose(get(i, "Observed_Vessel_Count"), get(e, "Observed_Vessel_Count")),
            "Primary_Source_Organization": get(ce, "Primary_Source_Organization_Reviewed"),
            "Primary_Source_Coordinate_Scope": get(ce, "Primary_Source_Coordinate_Scope"),
            "Primary_Source_Latitude": primary_lat,
            "Primary_Source_Longitude": primary_lon,
            "Secondary_Source_Organization": get(ce, "Secondary_Source_Organization_Reviewed"),
            "Secondary_Source_Coordinate_Scope": get(ce, "Secondary_Source_Coordinate_Scope"),
            "Secondary_Source_Latitude": secondary_lat,
            "Secondary_Source_Longitude": secondary_lon,
            "Independent_Corroboration_Status": get(ce, "Independent_Corroboration_Status"),
            "Validated_Port_Latitude": validated_port_lat,
            "Validated_Port_Longitude": validated_port_lon,
            "Validated_Terminal_Latitude": validated_terminal_lat,
            "Validated_Terminal_Longitude": validated_terminal_lon,
            "Coordinate_Validation_Status": coord_status,
            "Coordinate_Confidence": coord_confidence,
            "Port_Coordinate_Type": choose(get(c, "Port_Coordinate_Type"), get(i, "Validated_Coordinate_Type"), get(e, "Port_Coordinate_Type")),
            "Terminal_Coordinate_Type": choose(get(c, "Terminal_Coordinate_Type"), get(e, "Terminal_Coordinate_Type")),
            "Primary_Coordinate_Pair_Present": yes_no_present(primary_lat, primary_lon),
            "Secondary_Coordinate_Pair_Present": yes_no_present(secondary_lat, secondary_lon),
            "Validated_Port_Coordinate_Present": yes_no_present(validated_port_lat, validated_port_lon),
            "Validated_Terminal_Coordinate_Present": yes_no_present(validated_terminal_lat, validated_terminal_lon),
            "Source_Content_Review_Status": source_review_status,
            "Researcher_Review_Status": researcher_review_status,
            "Coordinate_Evidence_QA_Classification": quality_class,
            "Coordinate_Evidence_QA_Flags": quality_flags,
            "Eligibility_Classification_from_Script49": eligibility_class,
            "Recommended_Use_from_Script49": recommended_use,
            "Operational_Inclusion_Decision": operational_decision,
            "AIS_or_Transit_Evidence_Status": transit_status,
            "Transit_Interpretation": transit_interpretation,
            "Blocking_Conditions": " | ".join(dict.fromkeys(blockers)),
            "Reconciliation_Status": reconciliation_status,
            "Researcher_Action_Required": (
                "Resolve identity/facility/coordinate evidence and make explicit approval decision; "
                "do not infer AIS transit from port calls."
                if blockers else
                "Review complete evidence and make final researcher decision."
            ),
        })

    out = pd.DataFrame(output_rows)

    # QA checks on the consolidated output.
    if len(out) != len(EXPECTED_CODES):
        raise AssertionError(f"Expected {len(EXPECTED_CODES)} output rows; got {len(out)}")
    if out["UN_LOCODE"].duplicated().any():
        raise AssertionError("Duplicate UN_LOCODE in consolidated output.")
    if set(out["UN_LOCODE"]) != EXPECTED_CODES:
        raise AssertionError("Consolidated output code set differs from expected set.")

    out.to_csv(OUT_REGISTER, index=False)

    summary_rows = [
        ("Consolidated records", len(out)),
        ("Expected code coverage", f"{out['UN_LOCODE'].nunique()}/{len(EXPECTED_CODES)}"),
        ("Records with verified code identity", int(out["Identity_Interpretation"].str.contains("VERIFIED", case=False, na=False).sum())),
        ("Records with validated port coordinates populated", int((out["Validated_Port_Coordinate_Present"] == "YES").sum())),
        ("Records with validated terminal coordinates populated", int((out["Validated_Terminal_Coordinate_Present"] == "YES").sum())),
        ("Coordinate validation approved", int(out["Coordinate_Validation_Status"].map(norm).isin({"VALIDATED", "VERIFIED", "APPROVED", "ACCEPTED"}).sum())),
        ("Operational inclusion approved", int(out["Operational_Inclusion_Decision"].map(norm).isin({"INCLUDE", "APPROVED_FOR_INCLUSION", "INCLUDE_IN_CORE", "INCLUDE_IN_SIMULATION"}).sum())),
        ("Records with confirmed AIS transit status", int(out["Transit_Interpretation"].str.contains("REPORTED_CONFIRMED", na=False).sum())),
        ("Records pending researcher review", int((out["Reconciliation_Status"] == "PENDING_RESEARCHER_REVIEW").sum())),
        ("QAUMS facility association unresolved", int(out["UN_LOCODE"].eq("QAUMS").sum())),
        ("Upstream files modified", "NO"),
    ]
    summary = pd.DataFrame(summary_rows, columns=["Metric", "Value"])
    summary.to_csv(OUT_SUMMARY, index=False)

    lines = [
        "SCRIPT 54 — CONSOLIDATED PORT IDENTITY AND COORDINATE RECONCILIATION",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "INPUT REGISTERS",
    ]
    for name, path in FILES.items():
        lines.append(f"{name}: {path.relative_to(ROOT)} ({len(regs[name])} rows, {len(regs[name].columns)} columns)")
    lines += [
        "",
        "SUMMARY",
        summary.to_string(index=False),
        "",
        "RECORD-LEVEL RECONCILIATION",
    ]
    for _, r in out.iterrows():
        lines.append(
            f"{r['UN_LOCODE']} | {r['Port_Name_in_Master']} | "
            f"Identity={r['Identity_Validation_Status']} | "
            f"Coordinate={r['Coordinate_Validation_Status']} | "
            f"Eligibility={r['Eligibility_Classification_from_Script49']} | "
            f"Reconciliation={r['Reconciliation_Status']}"
        )
        if r["Blocking_Conditions"]:
            lines.append(f"  Blockers: {r['Blocking_Conditions']}")
        if r["Coordinate_Evidence_QA_Flags"]:
            lines.append(f"  QA flags: {r['Coordinate_Evidence_QA_Flags']}")

    lines += [
        "",
        "METHODOLOGICAL LIMITATIONS",
        "- A verified UN/LOCODE identity does not validate a coordinate or facility attribution.",
        "- A port-level coordinate, terminal coordinate, berth, buoy, pilot station and port-limit polygon are different reference objects.",
        "- Matching coordinates do not establish independent source corroboration.",
        "- Script 49 classifications are carried forward as upstream recommendations, not silently upgraded.",
        "- Port-call sequences do not prove Strait of Hormuz transit.",
        "- No coordinates or operational inclusion decisions are approved by this script.",
        "- All unresolved records are retained.",
        "",
        "OUTPUTS",
        str(OUT_REGISTER.relative_to(ROOT)),
        str(OUT_SUMMARY.relative_to(ROOT)),
        str(OUT_REPORT.relative_to(ROOT)),
        "",
        "UPSTREAM REGISTER MODIFICATION: NO",
    ]
    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("SCRIPT 54 COMPLETED — READ-ONLY RECONCILIATION")
    print(f"Consolidated records: {len(out)}")
    print(f"Expected UN/LOCODE coverage: {out['UN_LOCODE'].nunique()}/{len(EXPECTED_CODES)}")
    print(f"Records pending researcher review: {(out['Reconciliation_Status'] == 'PENDING_RESEARCHER_REVIEW').sum()}")
    print(f"Validated port coordinates populated: {(out['Validated_Port_Coordinate_Present'] == 'YES').sum()}")
    print(f"Operational inclusion approved: {summary.loc[summary['Metric']=='Operational inclusion approved','Value'].iloc[0]}")
    print("Upstream files modified: NO")
    print(f"Register: {OUT_REGISTER.relative_to(ROOT)}")
    print(f"Summary: {OUT_SUMMARY.relative_to(ROOT)}")
    print(f"Report: {OUT_REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
