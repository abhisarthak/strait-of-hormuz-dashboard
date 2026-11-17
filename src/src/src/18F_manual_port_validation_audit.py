"""
SCRIPT 18F: MANUAL PORT / FACILITY EVIDENCE TEMPLATE AND AUDIT

Run from project root:
    python src/18F_manual_port_validation_audit.py

First run:
    Creates outputs/tables/18F_manual_evidence_template.csv and exits.

After completing the template:
    Run again to audit the evidence and generate final outputs.

This script does not browse the web or independently verify source content.
It checks entered evidence, URL syntax, reviewer decisions and coordinates.
UN/LOCODE release agreement is not independent verification.
A coordinate difference from the UN/LOCODE reference is flagged, not
automatically rejected, because a port reference point may differ from a
specific terminal/facility coordinate.
Port/facility verification does not prove vessel transit through Hormuz.
"""

from pathlib import Path
import math
import re

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = ROOT / "outputs" / "tables" / "18E_port_facility_validation_register.csv"
TEMPLATE_FILE = ROOT / "outputs" / "tables" / "18F_manual_evidence_template.csv"
OUTPUT_PROCESSED = ROOT / "data" / "processed"
OUTPUT_TABLES = ROOT / "outputs" / "tables"
OUTPUT_REPORTS = ROOT / "outputs" / "reports"

for folder in (OUTPUT_PROCESSED, OUTPUT_TABLES, OUTPUT_REPORTS):
    folder.mkdir(parents=True, exist_ok=True)

COORDINATE_REVIEW_THRESHOLD_KM = 10.0

KEY_COLUMNS = ["18E_Record_ID", "UN_LOCODE"]

REFERENCE_COLUMNS = [
    "18E_Record_ID", "UN_LOCODE", "Port_Name", "City_Name", "Country_Code",
    "18D_Geographic_Zone", "18D_Screening_Status",
    "18D_Distance_To_Reference_KM", "18D_Accepted_Latitude",
    "18D_Accepted_Longitude", "Production_Latitude",
    "Production_Longitude", "Production_Coordinate_Status",
    "Prerelease_Latitude", "Prerelease_Longitude",
    "Prerelease_Coordinate_Status", "Coordinate_Comparison",
    "Coordinate_Review_Status", "Facility_Review_Category",
    "Validation_Priority", "Duplicate_LOCODE_In_Shortlist",
    "Ambiguous_Master_LOCODE",
]

REVIEW_COLUMNS = [
    "Independent_Source_1", "Independent_Source_1_URL",
    "Independent_Source_1_Description", "Independent_Source_2",
    "Independent_Source_2_URL", "Independent_Source_2_Description",
    "Source_Independence_Confirmed", "Verified_Port_or_Facility_Name",
    "Verified_Location_Type", "Verified_Latitude", "Verified_Longitude",
    "Facility_Identity_Verified", "Geographic_Location_Verified",
    "Coordinate_Source_Confidence", "Evidence_Reviewed",
    "Reviewer_Name_or_ID", "Evidence_Review_Date", "Reviewer_Notes",
]

YES = {"YES", "Y", "TRUE", "1"}
NO = {"NO", "N", "FALSE", "0"}
NOT_REVIEWED = {"", "NOT_REVIEWED", "PENDING", "NA", "N/A"}


def txt(value):
    return "" if pd.isna(value) else str(value).strip()


def decision(value):
    value = txt(value).upper()
    if value in YES:
        return "YES"
    if value in NO:
        return "NO"
    if value in NOT_REVIEWED:
        return "NOT_REVIEWED"
    return "INVALID_VALUE"


def number(value):
    try:
        return np.nan if pd.isna(value) or txt(value) == "" else float(value)
    except (TypeError, ValueError):
        return np.nan


def valid_coords(lat, lon):
    lat, lon = number(lat), number(lon)
    return (
        not pd.isna(lat) and not pd.isna(lon)
        and -90 <= lat <= 90 and -180 <= lon <= 180
    )


def valid_url(value):
    return bool(re.match(r"^https?://\S+$", txt(value), re.I))


def haversine_km(lat1, lon1, lat2, lon2):
    if not valid_coords(lat1, lon1) or not valid_coords(lat2, lon2):
        return np.nan
    lat1, lon1, lat2, lon2 = map(
        math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)]
    )
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 6371.0088 * 2 * math.asin(math.sqrt(a))


def load_source():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Script 18E input not found: {INPUT_FILE}\n"
            "Run Script 18E successfully first."
        )

    df = pd.read_csv(
        INPUT_FILE,
        dtype={"18E_Record_ID": str, "UN_LOCODE": str},
    )

    missing = [c for c in KEY_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required key columns: {missing}")

    if df["UN_LOCODE"].isna().any():
        raise ValueError("Missing UN_LOCODE values in Script 18E register.")

    if df["UN_LOCODE"].astype(str).duplicated().any():
        raise ValueError(
            "Duplicate LOCODEs in Script 18E register. Resolve before audit."
        )
    return df


def create_template(source):
    ref_cols = [c for c in REFERENCE_COLUMNS if c in source.columns]
    template = source[ref_cols].copy()

    for col in REVIEW_COLUMNS:
        template[col] = ""

    for col in [
        "Source_Independence_Confirmed",
        "Facility_Identity_Verified",
        "Geographic_Location_Verified",
        "Evidence_Reviewed",
    ]:
        template[col] = "NOT_REVIEWED"

    template["Coordinate_Source_Confidence"] = "NOT_ASSESSED"
    template["Reviewer_Guidance"] = (
        "Enter independently sourced evidence; UN/LOCODE release agreement "
        "alone is not independent verification."
    )
    return template


def audit(source, template):
    for col in REVIEW_COLUMNS:
        if col not in template.columns:
            template[col] = ""

    for key in KEY_COLUMNS:
        if key not in template.columns:
            raise ValueError(f"Evidence template missing key: {key}")

    if template["UN_LOCODE"].isna().any():
        raise ValueError("Missing UN_LOCODE in evidence template.")
    if template["UN_LOCODE"].astype(str).duplicated().any():
        raise ValueError("Duplicate UN_LOCODE in evidence template.")

    source_keys = set(zip(source["18E_Record_ID"], source["UN_LOCODE"]))
    template_keys = set(zip(template["18E_Record_ID"], template["UN_LOCODE"]))
    if source_keys != template_keys:
        raise ValueError(
            "Evidence template records do not match Script 18E. "
            f"Missing: {len(source_keys-template_keys)}; "
            f"unexpected: {len(template_keys-source_keys)}. "
            "Regenerate the template or reconcile its keys."
        )

    merged = source.merge(
        template[KEY_COLUMNS + REVIEW_COLUMNS],
        on=KEY_COLUMNS,
        how="left",
        validate="one_to_one",
        suffixes=("_18E", ""),
    )

    rows = []
    for _, r in merged.iterrows():
        s1 = txt(r["Independent_Source_1"])
        u1 = txt(r["Independent_Source_1_URL"])
        d1 = txt(r["Independent_Source_1_Description"])
        s2 = txt(r["Independent_Source_2"])
        u2 = txt(r["Independent_Source_2_URL"])
        d2 = txt(r["Independent_Source_2_Description"])

        s1_complete = bool(s1 and u1 and d1)
        s2_complete = bool(s2 and u2 and d2)
        u1_valid, u2_valid = valid_url(u1), valid_url(u2)
        names_distinct = bool(s1 and s2 and s1.casefold() != s2.casefold())
        independence = decision(r["Source_Independence_Confirmed"])

        two_sources = (
            s1_complete and s2_complete and u1_valid and u2_valid
            and names_distinct
        )
        independent_sources_sufficient = two_sources and independence == "YES"

        verified_name = txt(r["Verified_Port_or_Facility_Name"])
        location_type = txt(r["Verified_Location_Type"])
        vlat, vlon = number(r["Verified_Latitude"]), number(r["Verified_Longitude"])
        coords_valid = valid_coords(vlat, vlon)

        identity = decision(r["Facility_Identity_Verified"])
        geography = decision(r["Geographic_Location_Verified"])
        reviewed = decision(r["Evidence_Reviewed"])
        confidence = txt(r["Coordinate_Source_Confidence"]).upper()
        reviewer = txt(r["Reviewer_Name_or_ID"])
        review_date = txt(r["Evidence_Review_Date"])

        # Exact column names from the supplied Script 18E register.
        ref_lat = number(r.get("18D_Accepted_Latitude"))
        ref_lon = number(r.get("18D_Accepted_Longitude"))
        distance = haversine_km(vlat, vlon, ref_lat, ref_lon)

        if pd.isna(distance):
            coord_comparison = "NOT_COMPARABLE"
        elif distance > COORDINATE_REVIEW_THRESHOLD_KM:
            coord_comparison = "DIFFERENCE_REQUIRES_REVIEW"
        else:
            coord_comparison = "WITHIN_REVIEW_THRESHOLD"

        missing = []
        checks = [
            (s1_complete, "SOURCE_1_NAME_URL_DESCRIPTION"),
            (u1_valid, "SOURCE_1_VALID_HTTP_URL"),
            (s2_complete, "SOURCE_2_NAME_URL_DESCRIPTION"),
            (u2_valid, "SOURCE_2_VALID_HTTP_URL"),
            (names_distinct, "TWO_DISTINCT_SOURCE_NAMES"),
            (independence == "YES", "SOURCE_INDEPENDENCE_CONFIRMATION"),
            (bool(verified_name), "VERIFIED_PORT_OR_FACILITY_NAME"),
            (bool(location_type), "VERIFIED_LOCATION_TYPE"),
            (coords_valid, "VALID_VERIFIED_COORDINATES"),
            (identity == "YES", "IDENTITY_VERIFICATION_YES"),
            (geography == "YES", "GEOGRAPHIC_VERIFICATION_YES"),
            (reviewed == "YES", "EVIDENCE_REVIEWED_YES"),
            (confidence in {"HIGH", "MEDIUM"}, "HIGH_OR_MEDIUM_CONFIDENCE"),
            (bool(reviewer), "REVIEWER_NAME_OR_ID"),
            (bool(review_date), "EVIDENCE_REVIEW_DATE"),
        ]
        missing = [label for passed, label in checks if not passed]

        rejection = []
        if identity == "NO":
            rejection.append("IDENTITY_NOT_CONFIRMED")
        if geography == "NO":
            rejection.append("GEOGRAPHIC_LOCATION_NOT_CONFIRMED")

        if rejection:
            status = "REJECTED"
        elif (
            independent_sources_sufficient
            and verified_name and location_type and coords_valid
            and identity == "YES" and geography == "YES"
            and reviewed == "YES"
            and confidence in {"HIGH", "MEDIUM"}
            and reviewer and review_date
        ):
            status = "VERIFIED"
        elif (
            s1_complete or s2_complete
            or identity == "YES" or geography == "YES"
        ):
            status = "PARTIALLY_VERIFIED"
        else:
            status = "PENDING_REVIEW"

        rows.append({
            "18E_Record_ID": txt(r["18E_Record_ID"]),
            "UN_LOCODE": txt(r["UN_LOCODE"]),
            "Source_1_Documented": s1_complete,
            "Source_1_URL_Syntax_Valid": u1_valid,
            "Source_2_Documented": s2_complete,
            "Source_2_URL_Syntax_Valid": u2_valid,
            "Source_Names_Distinct": names_distinct,
            "Source_Independence_Confirmed": independence,
            "Two_Independent_Sources_Sufficient": independent_sources_sufficient,
            "Verified_Port_or_Facility_Name": verified_name,
            "Verified_Location_Type": location_type,
            "Facility_Identity_Verified": identity,
            "Geographic_Location_Verified": geography,
            "Evidence_Reviewed": reviewed,
            "Verified_Latitude": vlat,
            "Verified_Longitude": vlon,
            "Verified_Coordinates_Valid": coords_valid,
            "18D_Accepted_Latitude": ref_lat,
            "18D_Accepted_Longitude": ref_lon,
            "Distance_From_18D_Reference_KM": distance,
            "Coordinate_Comparison": coord_comparison,
            "Coordinate_Review_Flag": (
                "YES" if coord_comparison == "DIFFERENCE_REQUIRES_REVIEW"
                else "NO"
            ),
            "Coordinate_Source_Confidence": confidence,
            "Reviewer_Name_or_ID": reviewer,
            "Evidence_Review_Date": review_date,
            "Missing_Evidence_Items": "; ".join(missing),
            "Rejection_Reasons": "; ".join(rejection),
            "18F_Validation_Status": status,
            "Reviewer_Notes": txt(r["Reviewer_Notes"]),
        })

    return pd.DataFrame(rows)


def main():
    print("=" * 76)
    print("SCRIPT 18F: MANUAL PORT / FACILITY EVIDENCE TEMPLATE AND AUDIT")
    print("=" * 76)

    source = load_source()
    print(f"\nScript 18E input shape: {source.shape}")
    print(f"Unique LOCODEs: {source['UN_LOCODE'].nunique()}")

    # First run creates the editable evidence template and stops.
    if not TEMPLATE_FILE.exists():
        template = create_template(source)
        template.to_csv(TEMPLATE_FILE, index=False, encoding="utf-8-sig")
        print("\nMANUAL EVIDENCE TEMPLATE CREATED")
        print(f"Saved: {TEMPLATE_FILE.relative_to(ROOT)}")
        print(f"Records: {len(template)}")
        print("\nNext:")
        print("1. Open the template in Excel.")
        print("2. Enter evidence and reviewer decisions.")
        print("3. Do not change 18E_Record_ID or UN_LOCODE.")
        print("4. Save the CSV.")
        print("5. Run Script 18F again to audit.")
        print("\nNo port has been marked independently verified.")
        return

    template = pd.read_csv(
        TEMPLATE_FILE,
        dtype={"18E_Record_ID": str, "UN_LOCODE": str},
        keep_default_na=False,
    )
    print(f"\nEvidence template shape: {template.shape}")

    audit_df = audit(source, template)
    final_df = source.merge(
        audit_df, on=KEY_COLUMNS, how="left", validate="one_to_one"
    )

    verified = final_df[final_df["18F_Validation_Status"] == "VERIFIED"].copy()
    partial = final_df[
        final_df["18F_Validation_Status"] == "PARTIALLY_VERIFIED"
    ].copy()
    pending = final_df[
        final_df["18F_Validation_Status"] == "PENDING_REVIEW"
    ].copy()
    rejected = final_df[
        final_df["18F_Validation_Status"] == "REJECTED"
    ].copy()

    status_summary = (
        final_df["18F_Validation_Status"].value_counts()
        .rename_axis("Validation_Status")
        .reset_index(name="Record_Count")
    )
    status_summary["Percentage"] = (
        100 * status_summary["Record_Count"] / max(len(final_df), 1)
    ).round(2)

    coordinate_summary = (
        audit_df["Coordinate_Comparison"].value_counts()
        .rename_axis("Coordinate_Comparison")
        .reset_index(name="Record_Count")
    )

    evidence_summary = pd.DataFrame([
        ("Total records", len(final_df)),
        ("Two independent sources sufficient",
         int(audit_df["Two_Independent_Sources_Sufficient"].sum())),
        ("Identity marked YES",
         int((audit_df["Facility_Identity_Verified"] == "YES").sum())),
        ("Geography marked YES",
         int((audit_df["Geographic_Location_Verified"] == "YES").sum())),
        ("Valid verified coordinate pairs",
         int(audit_df["Verified_Coordinates_Valid"].sum())),
        ("Evidence review marked YES",
         int((audit_df["Evidence_Reviewed"] == "YES").sum())),
        ("Coordinate review flags",
         int((audit_df["Coordinate_Review_Flag"] == "YES").sum())),
        ("Verified records", len(verified)),
        ("Partially verified records", len(partial)),
        ("Pending records", len(pending)),
        ("Rejected records", len(rejected)),
    ], columns=["Metric", "Count"])

    outputs = {
        OUTPUT_PROCESSED / "18F_final_port_validation_register.csv": final_df,
        OUTPUT_TABLES / "18F_record_level_evidence_audit.csv": audit_df,
        OUTPUT_TABLES / "18F_verified_port_shortlist.csv": verified,
        OUTPUT_TABLES / "18F_partially_verified_ports.csv": partial,
        OUTPUT_TABLES / "18F_pending_manual_review.csv": pending,
        OUTPUT_TABLES / "18F_rejected_port_records.csv": rejected,
        OUTPUT_TABLES / "18F_validation_status_summary.csv": status_summary,
        OUTPUT_TABLES / "18F_coordinate_comparison_summary.csv": coordinate_summary,
        OUTPUT_TABLES / "18F_evidence_completeness_summary.csv": evidence_summary,
    }

    for path, frame in outputs.items():
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"Saved: {path.relative_to(ROOT)}")

    report = [
        "=" * 76,
        "SCRIPT 18F: MANUAL PORT / FACILITY VALIDATION AUDIT REPORT",
        "=" * 76,
        "",
        f"Source register: {INPUT_FILE}",
        f"Evidence template: {TEMPLATE_FILE}",
        f"Total records: {len(final_df)}",
        "",
        "VALIDATION STATUS",
    ]
    for _, item in status_summary.iterrows():
        report.append(
            f"{item['Validation_Status']}: {item['Record_Count']} "
            f"({item['Percentage']}%)"
        )

    report.extend(["", "EVIDENCE COMPLETENESS"])
    for _, item in evidence_summary.iterrows():
        report.append(f"{item['Metric']}: {item['Count']}")

    report.extend([
        "",
        "METHODOLOGICAL LIMITATIONS",
        "1. URLs are syntax-checked only; their contents are not fetched.",
        "2. Source credibility and independence require human review.",
        "3. Coordinate differences are review flags, not automatic failures.",
        "4. Port/facility verification does not establish vessel transit.",
        "5. AIS/equivalent movement evidence is required to confirm crossings.",
        "",
        "END OF REPORT",
    ])

    report_path = OUTPUT_REPORTS / "18F_manual_port_validation_audit_report.txt"
    report_path.write_text("\n".join(report), encoding="utf-8")

    print(f"Saved: {report_path.relative_to(ROOT)}")
    print("\n" + "=" * 76)
    print("SCRIPT 18F AUDIT COMPLETED")
    print("=" * 76)
    print(f"Total records: {len(final_df)}")
    print(f"Verified: {len(verified)}")
    print(f"Partially verified: {len(partial)}")
    print(f"Pending review: {len(pending)}")
    print(f"Rejected: {len(rejected)}")
    print("\nValidation status:")
    print(status_summary.to_string(index=False))
    print("\nCoordinate comparison:")
    print(coordinate_summary.to_string(index=False))
    print(
        "\nReminder: a verified port/facility is not proof of a confirmed "
        "Strait of Hormuz vessel transit."
    )


if __name__ == "__main__":
    main()
