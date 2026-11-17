#!/usr/bin/env python3
"""
SCRIPT 54 (CORRECTED) — CONSOLIDATED PORT IDENTITY, COORDINATE AND ELIGIBILITY REGISTER

This replaces the earlier Script 54. It is read-only with respect to Scripts
38, 39, 41, 49, 51 and 53.

Key corrections:
1. Exact identity-status classification; no substring-based "VERIFIED" count.
2. Preserves PARTIAL, VERIFIED_PORT_IDENTITY and VERIFIED_CODE_IDENTITY separately.
3. Reads coordinate validation and coordinate fields from Script 39 using
   explicit field aliases and reports which fields were found.
4. Keeps Script 49 eligibility/recommended-use decisions independent of AIS.
5. AIS transit evidence is reported separately and is never a general blocker
   to regional/sensitivity-analysis use.
6. Carries forward Script 49 classifications without upgrading/downgrading.
7. Retains all 19 ports and unresolved QAUMS facility association.
8. Does not approve coordinates or operational inclusion.

Run from project root:
    python src/54_consolidated_port_identity_coordinate_reconciliation.py

If you want to preserve the old outputs, this script creates timestamped
backups before replacing them.
"""

from pathlib import Path
from datetime import datetime
import shutil
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"

INPUTS = {
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


def txt(value):
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def norm(value):
    return " ".join(txt(value).upper().replace("_", " ").split())


def read_csv(label, path):
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {label} input:\n{path}\n"
            "Run the corresponding upstream script or verify the filename."
        )
    df = pd.read_csv(path, dtype={"UN_LOCODE": "string"})
    if "UN_LOCODE" not in df.columns:
        raise ValueError(f"{label} file has no UN_LOCODE column: {path}")
    df["UN_LOCODE"] = df["UN_LOCODE"].astype("string").str.strip().str.upper()
    if df["UN_LOCODE"].isna().any() or (df["UN_LOCODE"] == "").any():
        raise ValueError(f"{label} file contains blank UN_LOCODE values.")
    if df["UN_LOCODE"].duplicated().any():
        duplicates = df.loc[df["UN_LOCODE"].duplicated(keep=False), "UN_LOCODE"].tolist()
        raise ValueError(f"{label} file contains duplicate UN_LOCODEs: {duplicates}")
    return df


def get(row, candidates, default=""):
    if row is None:
        return default
    for col in candidates:
        if col in row.index:
            value = txt(row[col])
            if value:
                return value
    return default


def exact_identity_class(status):
    """Return a controlled interpretation without fuzzy substring matching."""
    s = norm(status)
    if s in {"VERIFIED PORT IDENTITY", "VERIFIED"}:
        return "VERIFIED_PORT_IDENTITY"
    if s in {"VERIFIED CODE IDENTITY"}:
        return "VERIFIED_CODE_IDENTITY"
    if s in {"PARTIAL", "PARTIALLY VERIFIED", "PARTIAL IDENTITY"}:
        return "PARTIAL"
    if s in {"NOT VERIFIED", "NOT_VERIFIED", "UNVERIFIED"}:
        return "NOT_VERIFIED"
    if not s:
        return "STATUS_NOT_RECORDED"
    return "OTHER_REQUIRES_REVIEW"


def numeric_pair_status(lat, lon):
    lat, lon = txt(lat), txt(lon)
    if not lat and not lon:
        return "ABSENT"
    if bool(lat) != bool(lon):
        return "INCOMPLETE"
    try:
        x, y = float(lat), float(lon)
    except ValueError:
        return "NON_NUMERIC"
    if not (-90 <= x <= 90 and -180 <= y <= 180):
        return "OUT_OF_RANGE"
    return "PRESENT_UNVALIDATED"


def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    data = {name: read_csv(name, path) for name, path in INPUTS.items()}
    indexed = {name: df.set_index("UN_LOCODE", drop=False) for name, df in data.items()}

    identity_codes = set(data["identity"]["UN_LOCODE"].astype(str))
    missing = sorted(EXPECTED_CODES - identity_codes)
    unexpected = sorted(identity_codes - EXPECTED_CODES)
    if missing or unexpected:
        raise ValueError(f"Script 38 coverage mismatch. Missing={missing}; unexpected={unexpected}")

    # Use identity register as the master universe; supporting missing rows
    # are explicitly marked rather than silently dropped.
    codes = sorted(EXPECTED_CODES)
    rows_out = []

    for code in codes:
        r = {
            name: indexed[name].loc[code] if code in indexed[name].index else None
            for name in indexed
        }
        ident, coord, source, elig, evidence, qa = (
            r["identity"], r["coordinates"], r["source_review"],
            r["eligibility"], r["coordinate_evidence"], r["quality_audit"]
        )

        master_name = get(ident, ["Port_Name_in_Master"]) or get(evidence, ["Port_Name_in_Master"])
        validated_name = get(
            ident,
            ["Researcher_Validated_Port_Name", "Validated_Port_Name"]
        ) or get(evidence, ["Researcher_Validated_Port_Name"])
        facility_name = get(
            ident,
            ["Researcher_Validated_Facility_Name", "Validated_Facility_Name"]
        ) or get(evidence, ["Researcher_Validated_Facility_Name"])

        identity_status = get(ident, ["Identity_Validation_Status"]) or get(evidence, ["Identity_Validation_Status"])
        identity_class = exact_identity_class(identity_status)

        facility_resolution = get(
            ident,
            ["Port_vs_Terminal_Resolution", "Port_Terminal_Distinction_Notes",
             "Researcher_Validated_Facility_Name"]
        ) or get(evidence, ["Port_vs_Terminal_Resolution", "Port_Terminal_Distinction_Notes"])

        # Script 39 is the coordinate-validation authority for this reconciliation.
        coord_status = get(coord, ["Coordinate_Validation_Status"], "SCRIPT39_ROW_OR_STATUS_MISSING")
        coord_confidence = get(coord, ["Coordinate_Confidence"], "NOT_RECORDED")
        port_lat = get(coord, ["Validated_Port_Latitude", "Researcher_Validated_Latitude"])
        port_lon = get(coord, ["Validated_Port_Longitude", "Researcher_Validated_Longitude"])
        terminal_lat = get(coord, ["Validated_Terminal_Latitude"])
        terminal_lon = get(coord, ["Validated_Terminal_Longitude"])
        port_type = get(coord, ["Port_Coordinate_Type", "Researcher_Coordinate_Type"])
        port_scope = get(coord, ["Port_Coordinate_Scope", "Researcher_Coordinate_Scope"])
        terminal_name = get(coord, ["Terminal_Name"])
        terminal_type = get(coord, ["Terminal_Coordinate_Type"])

        primary_lat = get(evidence, ["Primary_Source_Latitude"])
        primary_lon = get(evidence, ["Primary_Source_Longitude"])
        secondary_lat = get(evidence, ["Secondary_Source_Latitude"])
        secondary_lon = get(evidence, ["Secondary_Source_Longitude"])

        eligibility_class = get(elig, ["Eligibility_Classification"])
        recommended_use = get(elig, ["Recommended_Use"])
        eligibility_blockers = get(elig, ["Eligibility_Blocking_Conditions"])
        network_match = get(elig, ["Network_Match_Status"]) or get(evidence, ["Network_Match_Status"])
        observed_calls = get(elig, ["Observed_Call_Count"]) or get(evidence, ["Observed_Call_Count"])
        observed_vessels = get(elig, ["Observed_Vessel_Count"]) or get(evidence, ["Observed_Vessel_Count"])

        operational_decision = get(
            ident,
            ["Operational_Inclusion_Decision"]
        ) or get(source, ["Operational_Inclusion_Decision"]) or get(elig, ["Operational_Inclusion_Decision"], "NOT_RECORDED")

        transit_status = get(
            ident,
            ["AIS_or_Transit_Evidence_Status", "AIS_Transit_Evidence_Status",
             "Transit_Evidence_Status"]
        ) or get(source, ["AIS_or_Transit_Evidence_Status", "AIS_Transit_Evidence_Status",
                         "Transit_Evidence_Status"], "NOT_ESTABLISHED_IN_AVAILABLE_REGISTER")

        source_review_status = get(source, ["Source_Content_Review_Status"]) or get(ident, ["Source_Content_Review_Status"])
        source_review_conclusion = get(source, ["Source_Content_Review_Conclusion"]) or get(ident, ["Source_Content_Review_Conclusion"])
        quality_flags = get(qa, ["Audit_Flags"])
        quality_class = get(qa, ["Automated_Audit_Classification"])

        # Separate decision dimensions. AIS evidence does not decide regional use.
        blockers = []
        if coord is None:
            blockers.append("SCRIPT39_COORDINATE_REGISTER_ROW_MISSING")
        if source is None:
            blockers.append("SCRIPT41_SOURCE_REVIEW_ROW_MISSING")
        if elig is None:
            blockers.append("SCRIPT49_ELIGIBILITY_ROW_MISSING")
        if evidence is None:
            blockers.append("SCRIPT51_COORDINATE_EVIDENCE_ROW_MISSING")
        if qa is None:
            blockers.append("SCRIPT53_QUALITY_AUDIT_ROW_MISSING")

        if identity_class in {"PARTIAL", "NOT_VERIFIED", "STATUS_NOT_RECORDED", "OTHER_REQUIRES_REVIEW"}:
            blockers.append("IDENTITY_REVIEW_REQUIRED")
        if norm(coord_status) not in {"VALIDATED", "VERIFIED", "APPROVED", "ACCEPTED"}:
            blockers.append("COORDINATE_VALIDATION_PENDING_OR_NOT_APPROVED")
        if numeric_pair_status(port_lat, port_lon) != "PRESENT_UNVALIDATED":
            blockers.append("VALIDATED_PORT_COORDINATE_PAIR_NOT_POPULATED")
        if not eligibility_class:
            blockers.append("SCRIPT49_ELIGIBILITY_CLASSIFICATION_MISSING")
        if norm(operational_decision) in {"", "PENDING", "NOT RECORDED"}:
            blockers.append("OPERATIONAL_INCLUSION_DECISION_PENDING")

        # Explicit identity/facility reconciliation.
        if code == "QAUMS":
            facility_status = (
                "UNRESOLVED_QAUMS_CODE_IDENTITY_VERIFIED_FACILITY_ASSOCIATION_PENDING"
                if identity_class == "VERIFIED_CODE_IDENTITY"
                else "UNRESOLVED_IDENTITY_AND_FACILITY"
            )
            blockers.append("QAUMS_FACILITY_ASSOCIATION_REQUIRES_RESEARCHER_RESOLUTION")
        elif "PENDING" in norm(facility_resolution):
            facility_status = "FACILITY_MAPPING_PENDING"
        elif facility_resolution:
            facility_status = "FACILITY_DISTINCTION_OR_MAPPING_NOTE_RECORDED"
        else:
            facility_status = "FACILITY_MAPPING_STATUS_NOT_EXPLICITLY_RECORDED"

        # Do not treat missing AIS transit as a general eligibility blocker.
        transit_norm = norm(transit_status)
        if "AIS" in transit_norm and "CONFIRMED" in transit_norm:
            transit_interpretation = "AIS_TRANSIT_REPORTED_CONFIRMED_REQUIRES_EVIDENCE_REFERENCE_CHECK"
        else:
            transit_interpretation = "NO_AIS_CONFIRMED_HORMUZ_TRANSIT_ESTABLISHED"
        regional_use_allowed_as_recommendation = (
            "YES"
            if norm(recommended_use) == "REGIONAL OR SENSITIVITY ANALYSIS ONLY"
            else "NO"
        )

        # No automatic approval. Keep Script 49's recommendation exactly.
        if blockers:
            reconciliation_status = "PENDING_RESEARCHER_REVIEW"
        else:
            reconciliation_status = "READY_FOR_FINAL_RESEARCHER_REVIEW_NOT_APPROVED"

        rows_out.append({
            "UN_LOCODE": code,
            "Port_Name_in_Master": master_name,
            "Researcher_Validated_Port_Name": validated_name,
            "Researcher_Validated_Facility_Name": facility_name,

            "Identity_Validation_Status_Original": identity_status,
            "Identity_Status_Interpretation": identity_class,
            "Identity_Is_Verified": "YES" if identity_class in {"VERIFIED_PORT_IDENTITY", "VERIFIED_CODE_IDENTITY"} else "NO",
            "Facility_Mapping_Status": facility_status,
            "Facility_Resolution_or_Notes": facility_resolution,

            "Coordinate_Validation_Status_Script39": coord_status,
            "Coordinate_Confidence_Script39": coord_confidence,
            "Validated_Port_Latitude_Script39": port_lat,
            "Validated_Port_Longitude_Script39": port_lon,
            "Validated_Terminal_Latitude_Script39": terminal_lat,
            "Validated_Terminal_Longitude_Script39": terminal_lon,
            "Port_Coordinate_Type_Script39": port_type,
            "Port_Coordinate_Scope_Script39": port_scope,
            "Terminal_Name_Script39": terminal_name,
            "Terminal_Coordinate_Type_Script39": terminal_type,
            "Validated_Port_Coordinate_Pair_Check": numeric_pair_status(port_lat, port_lon),
            "Validated_Terminal_Coordinate_Pair_Check": numeric_pair_status(terminal_lat, terminal_lon),

            "Primary_Source_Organization": get(evidence, ["Primary_Source_Organization_Reviewed"]),
            "Primary_Source_Coordinate_Scope": get(evidence, ["Primary_Source_Coordinate_Scope"]),
            "Primary_Source_Latitude": primary_lat,
            "Primary_Source_Longitude": primary_lon,
            "Secondary_Source_Organization": get(evidence, ["Secondary_Source_Organization_Reviewed"]),
            "Secondary_Source_Coordinate_Scope": get(evidence, ["Secondary_Source_Coordinate_Scope"]),
            "Secondary_Source_Latitude": secondary_lat,
            "Secondary_Source_Longitude": secondary_lon,
            "Independent_Corroboration_Status": get(evidence, ["Independent_Corroboration_Status"]),

            "Source_Content_Review_Status": source_review_status,
            "Source_Content_Review_Conclusion": source_review_conclusion,
            "Coordinate_Evidence_QA_Classification": quality_class,
            "Coordinate_Evidence_QA_Flags": quality_flags,

            "Network_Match_Status": network_match,
            "Observed_Call_Count": observed_calls,
            "Observed_Vessel_Count": observed_vessels,

            # Script 49 values are carried forward, never recomputed here.
            "Eligibility_Classification_from_Script49": eligibility_class,
            "Recommended_Use_from_Script49": recommended_use,
            "Eligibility_Blocking_Conditions_from_Script49": eligibility_blockers,
            "Regional_Sensitivity_Recommendation_Preserved": regional_use_allowed_as_recommendation,

            "Operational_Inclusion_Decision": operational_decision,
            "AIS_or_Transit_Evidence_Status": transit_status,
            "Transit_Interpretation": transit_interpretation,

            "Reconciliation_Blocking_Conditions": " | ".join(dict.fromkeys(blockers)),
            "Reconciliation_Status": reconciliation_status,
            "Researcher_Action_Required": (
                "Review identity, facility mapping, coordinate validation and operational inclusion as separate decisions. "
                "AIS transit confirmation is required only for claims of actual Strait crossing, not as a blanket condition for regional sensitivity analysis."
            ),
        })

    out = pd.DataFrame(rows_out)

    if len(out) != 19 or out["UN_LOCODE"].nunique() != 19 or set(out["UN_LOCODE"]) != EXPECTED_CODES:
        raise AssertionError("Consolidated output failed the 19-record / unique-code integrity check.")

    # Correct exact identity counts.
    identity_counts = out["Identity_Status_Interpretation"].value_counts(dropna=False).to_dict()
    verified_count = int(out["Identity_Is_Verified"].eq("YES").sum())
    partial_count = int(out["Identity_Status_Interpretation"].eq("PARTIAL").sum())
    not_verified_count = int(out["Identity_Is_Verified"].eq("NO").sum())

    coord_status_counts = out["Coordinate_Validation_Status_Script39"].value_counts(dropna=False).to_dict()
    eligibility_counts = out["Eligibility_Classification_from_Script49"].value_counts(dropna=False).to_dict()
    use_counts = out["Recommended_Use_from_Script49"].value_counts(dropna=False).to_dict()

    summary = pd.DataFrame([
        ("Consolidated records", len(out)),
        ("Expected UN/LOCODE coverage", f"{out['UN_LOCODE'].nunique()}/19"),
        ("Verified port identities", int(out["Identity_Status_Interpretation"].eq("VERIFIED_PORT_IDENTITY").sum())),
        ("Verified code identities", int(out["Identity_Status_Interpretation"].eq("VERIFIED_CODE_IDENTITY").sum())),
        ("Total verified identities (port + code)", verified_count),
        ("Partial identities", partial_count),
        ("Not verified / other identity statuses", not_verified_count - partial_count),
        ("Validated port coordinate pairs populated", int(out["Validated_Port_Coordinate_Pair_Check"].eq("PRESENT_UNVALIDATED").sum())),
        ("Validated terminal coordinate pairs populated", int(out["Validated_Terminal_Coordinate_Pair_Check"].eq("PRESENT_UNVALIDATED").sum())),
        ("Coordinate validation approved", int(out["Coordinate_Validation_Status_Script39"].map(norm).isin({"VALIDATED", "VERIFIED", "APPROVED", "ACCEPTED"}).sum())),
        ("Operational inclusion approved", int(out["Operational_Inclusion_Decision"].map(norm).isin({"INCLUDE", "APPROVED FOR INCLUSION", "INCLUDE IN CORE", "INCLUDE IN SIMULATION"}).sum())),
        ("Regional/sensitivity recommendations preserved", int(out["Regional_Sensitivity_Recommendation_Preserved"].eq("YES").sum())),
        ("AIS-confirmed Hormuz transits established", int(out["Transit_Interpretation"].str.startswith("AIS_TRANSIT_REPORTED_CONFIRMED").sum())),
        ("Records pending reconciliation/researcher review", int(out["Reconciliation_Status"].eq("PENDING_RESEARCHER_REVIEW").sum())),
        ("QAUMS facility association unresolved", int(out["UN_LOCODE"].eq("QAUMS").sum())),
        ("Upstream files modified", "NO"),
    ], columns=["Metric", "Value"])

    # Back up prior Script 54 outputs before replacement.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for path in [OUT_REGISTER, OUT_SUMMARY, OUT_REPORT]:
        if path.exists():
            backup = path.with_name(path.stem + f"_pre_corrected_{stamp}" + path.suffix)
            shutil.copy2(path, backup)

    out.to_csv(OUT_REGISTER, index=False)
    summary.to_csv(OUT_SUMMARY, index=False)

    lines = [
        "SCRIPT 54 (CORRECTED) — CONSOLIDATED PORT IDENTITY, COORDINATE AND ELIGIBILITY RECONCILIATION",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "INPUT FILE SCHEMAS",
    ]
    for name, df in data.items():
        lines.append(f"{name}: {len(df)} rows x {len(df.columns)} columns")
        lines.append("  Key fields found: " + ", ".join(
            c for c in [
                "Identity_Validation_Status", "Coordinate_Validation_Status",
                "Validated_Port_Latitude", "Validated_Port_Longitude",
                "Eligibility_Classification", "Recommended_Use",
                "Operational_Inclusion_Decision"
            ] if c in df.columns
        ))
    lines += ["", "SUMMARY", summary.to_string(index=False), "", "IDENTITY STATUS COUNTS"]
    for k, v in identity_counts.items():
        lines.append(f"{k}: {v}")
    lines += ["", "SCRIPT 49 ELIGIBILITY CLASSIFICATIONS — PRESERVED"]
    for k, v in eligibility_counts.items():
        lines.append(f"{k or '[blank]'}: {v}")
    lines += ["", "SCRIPT 49 RECOMMENDED USE — PRESERVED"]
    for k, v in use_counts.items():
        lines.append(f"{k or '[blank]'}: {v}")
    lines += ["", "COORDINATE STATUS COUNTS FROM SCRIPT 39"]
    for k, v in coord_status_counts.items():
        lines.append(f"{k or '[blank]'}: {v}")
    lines += ["", "RECORD-LEVEL REVIEW"]
    for _, row in out.iterrows():
        lines.append(
            f"{row['UN_LOCODE']} | {row['Researcher_Validated_Port_Name']} | "
            f"Identity={row['Identity_Status_Interpretation']} | "
            f"Coordinates={row['Coordinate_Validation_Status_Script39']} | "
            f"Eligibility={row['Eligibility_Classification_from_Script49']} | "
            f"Use={row['Recommended_Use_from_Script49']}"
        )
        if row["Reconciliation_Blocking_Conditions"]:
            lines.append("  Review items: " + row["Reconciliation_Blocking_Conditions"])
        if row["Coordinate_Evidence_QA_Flags"]:
            lines.append("  QA flags: " + row["Coordinate_Evidence_QA_Flags"])
    lines += [
        "",
        "METHODOLOGICAL RULES",
        "- Identity statuses are classified by exact status values, not substring matching.",
        "- VERIFIED_PORT_IDENTITY and VERIFIED_CODE_IDENTITY remain distinct.",
        "- PARTIAL is not counted as verified.",
        "- Script 39 is the authority for coordinate-validation status and validated coordinate fields.",
        "- Script 49 eligibility and recommended-use values are carried forward without modification.",
        "- AIS transit confirmation is a separate evidentiary question and is not a blanket condition for regional/sensitivity-analysis use.",
        "- No coordinate or operational inclusion decision is approved by this script.",
        "- QAUMS identity remains distinct from its unresolved facility association.",
        "- Port-call sequences do not prove Strait of Hormuz transit.",
        "- All 19 records are retained.",
        "",
        "OUTPUTS",
        str(OUT_REGISTER.relative_to(ROOT)),
        str(OUT_SUMMARY.relative_to(ROOT)),
        str(OUT_REPORT.relative_to(ROOT)),
        "",
        "UPSTREAM REGISTERS MODIFIED: NO",
    ]
    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("SCRIPT 54 CORRECTED COMPLETED — READ-ONLY RECONCILIATION")
    print(f"Records: {len(out)} | UN/LOCODE coverage: {out['UN_LOCODE'].nunique()}/19")
    print(f"Verified port identities: {int(out['Identity_Status_Interpretation'].eq('VERIFIED_PORT_IDENTITY').sum())}")
    print(f"Verified code identities: {int(out['Identity_Status_Interpretation'].eq('VERIFIED_CODE_IDENTITY').sum())}")
    print(f"Partial identities: {partial_count}")
    print(f"Validated port coordinate pairs populated: {int(out['Validated_Port_Coordinate_Pair_Check'].eq('PRESENT_UNVALIDATED').sum())}")
    print(f"Coordinate validation approved: {summary.loc[summary['Metric']=='Coordinate validation approved','Value'].iloc[0]}")
    print(f"Regional/sensitivity recommendations preserved: {int(out['Regional_Sensitivity_Recommendation_Preserved'].eq('YES').sum())}")
    print("AIS transit used as blanket eligibility blocker: NO")
    print("Upstream registers modified: NO")
    print(f"Register: {OUT_REGISTER.relative_to(ROOT)}")
    print(f"Summary: {OUT_SUMMARY.relative_to(ROOT)}")
    print(f"Report: {OUT_REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
