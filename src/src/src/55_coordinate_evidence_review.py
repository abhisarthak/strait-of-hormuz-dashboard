
"""
SCRIPT 55: COORDINATE EVIDENCE REVIEW AND RESEARCHER PRIORITISATION
------------------------------------------------------------------
Purpose:
1. Review coordinate evidence already collected in Script 51.
2. Carry forward Script 53 coordinate-evidence quality flags.
3. Preserve Script 54 identity, Script 39 coordinate status,
   and Script 49 eligibility classifications.
4. Create a prioritised researcher-review register.
5. Identify missing evidence, source independence concerns,
   coordinate/reference-scope issues, and unresolved facilities.

This script does NOT:
- Search for new coordinates.
- Approve or validate coordinates.
- Change port identity decisions.
- Change Script 49 eligibility classifications.
- Infer AIS-confirmed Strait of Hormuz transit.
- Modify upstream registers.

All upstream inputs are read-only.
"""

from pathlib import Path
from datetime import datetime
import re
import sys

import pandas as pd
import numpy as np


# ============================================================
# 1. PATHS AND INPUTS
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

TABLE_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"

REPORT_DIR.mkdir(parents=True, exist_ok=True)

INPUTS = {
    "consolidated": TABLE_DIR /
        "54_consolidated_port_identity_coordinate_reconciliation.csv",

    "coordinate_evidence": TABLE_DIR /
        "51_primary_source_coordinate_evidence_register.csv",

    "quality_audit": TABLE_DIR /
        "53_coordinate_evidence_quality_audit.csv",
}

OUTPUTS = {
    "review": TABLE_DIR / "55_coordinate_evidence_review_register.csv",
    "evidence": TABLE_DIR / "55_coordinate_evidence_inventory.csv",
    "summary": TABLE_DIR / "55_coordinate_evidence_review_summary.csv",
    "report": REPORT_DIR / "55_coordinate_evidence_review_report.txt",
}

EXPECTED_RECORDS = 19


# ============================================================
# 2. COLUMN DETECTION
# ============================================================

KEY_CANDIDATES = [
    "UNLOCODE_Normalised",
    "UNLOCODE_Normalized",
    "UNLOCODE",
    "Port_Code",
    "Location_Code",
    "LOCODE",
]

NAME_CANDIDATES = [
    "Port",
    "Port_Name",
    "Location_Name",
    "Master_Port_Name",
    "Facility_Name",
]

IDENTITY_CANDIDATES = [
    "Identity_Validation_Status",
    "Identity_Status",
]

COORD_STATUS_CANDIDATES = [
    "Coordinate_Validation_Status",
]

ELIGIBILITY_CANDIDATES = [
    "Eligibility_Classification",
]

RECOMMENDED_USE_CANDIDATES = [
    "Recommended_Use",
]


def find_column(df, candidates, required=False, label="field"):
    """Find a column using exact candidate names first."""

    for candidate in candidates:
        if candidate in df.columns:
            return candidate

    normalised = {
        re.sub(r"[^a-z0-9]", "", str(col).lower()): col
        for col in df.columns
    }

    for candidate in candidates:
        key = re.sub(r"[^a-z0-9]", "", candidate.lower())
        if key in normalised:
            return normalised[key]

    if required:
        raise ValueError(
            f"Could not identify required {label}. "
            f"Available columns: {df.columns.tolist()}"
        )

    return None


def detect_key(df, label):
    col = find_column(
        df,
        KEY_CANDIDATES,
        required=True,
        label=f"{label} UN/LOCODE key",
    )

    return col


def normalise_key(series):
    return (
        series.astype("string")
        .str.strip()
        .str.upper()
        .replace({"": pd.NA, "NAN": pd.NA, "NONE": pd.NA})
    )


# ============================================================
# 3. LOAD INPUTS
# ============================================================

def load_inputs():

    for label, path in INPUTS.items():
        if not path.exists():
            raise FileNotFoundError(
                f"Missing {label} input register: {path}"
            )

    consolidated = pd.read_csv(INPUTS["consolidated"])
    evidence = pd.read_csv(INPUTS["coordinate_evidence"])
    quality = pd.read_csv(INPUTS["quality_audit"])

    print("\nINPUT REGISTER AUDIT")
    print("-" * 72)

    for label, frame in [
        ("Script 54 consolidated", consolidated),
        ("Script 51 coordinate evidence", evidence),
        ("Script 53 quality audit", quality),
    ]:
        print(
            f"{label}: {len(frame)} records x {len(frame.columns)} columns"
        )

    if len(consolidated) != EXPECTED_RECORDS:
        raise AssertionError(
            f"Expected {EXPECTED_RECORDS} consolidated records; "
            f"found {len(consolidated)}."
        )

    return consolidated, evidence, quality


# ============================================================
# 4. NORMALISE AND RECONCILE RECORD KEYS
# ============================================================

def prepare_register(frame, label):

    frame = frame.copy()

    key_col = detect_key(frame, label)

    frame["_JOIN_KEY"] = normalise_key(frame[key_col])

    if frame["_JOIN_KEY"].isna().any():
        raise AssertionError(
            f"{label} contains missing UN/LOCODE keys."
        )

    duplicates = frame["_JOIN_KEY"].duplicated(keep=False)

    if duplicates.any():
        values = sorted(
            frame.loc[duplicates, "_JOIN_KEY"].astype(str).unique()
        )
        raise AssertionError(
            f"{label} contains duplicate keys: {values}"
        )

    return frame, key_col


def reconcile_registers(consolidated, evidence, quality):

    base, base_key = prepare_register(
        consolidated, "Script 54 consolidated"
    )
    evidence, evidence_key = prepare_register(
        evidence, "Script 51 coordinate evidence"
    )
    quality, quality_key = prepare_register(
        quality, "Script 53 quality audit"
    )

    expected_keys = set(base["_JOIN_KEY"])

    for label, frame in [
        ("Script 51", evidence),
        ("Script 53", quality),
    ]:
        actual_keys = set(frame["_JOIN_KEY"])

        missing = expected_keys - actual_keys
        extra = actual_keys - expected_keys

        if missing or extra:
            raise AssertionError(
                f"{label} key coverage mismatch. "
                f"Missing={sorted(missing)}, "
                f"Extra={sorted(extra)}"
            )

    # Prefix evidence and quality fields to avoid accidental
    # overwriting of Script 54 decisions.
    evidence = evidence.rename(
        columns={
            c: f"S51_{c}"
            for c in evidence.columns
            if c != "_JOIN_KEY"
        }
    )

    quality = quality.rename(
        columns={
            c: f"S53_{c}"
            for c in quality.columns
            if c != "_JOIN_KEY"
        }
    )

    merged = base.merge(
        evidence,
        on="_JOIN_KEY",
        how="left",
        validate="one_to_one",
    )

    merged = merged.merge(
        quality,
        on="_JOIN_KEY",
        how="left",
        validate="one_to_one",
    )

    if len(merged) != EXPECTED_RECORDS:
        raise AssertionError(
            "Record count changed during reconciliation."
        )

    return merged, base_key, evidence_key, quality_key


# ============================================================
# 5. IDENTIFY EVIDENCE AND QUALITY FIELDS
# ============================================================

def matching_columns(df, patterns):
    """Return columns whose names match any supplied regex."""

    found = []

    for col in df.columns:
        if any(
            re.search(pattern, str(col), flags=re.IGNORECASE)
            for pattern in patterns
        ):
            found.append(col)

    return found


SOURCE_PATTERNS = [
    r"source",
    r"citation",
    r"reference",
    r"evidence",
    r"url",
    r"website",
    r"publisher",
    r"organisation",
    r"organization",
]

COORDINATE_PATTERNS = [
    r"latitude",
    r"longitude",
    r"\blat\b",
    r"\blon\b",
    r"\blng\b",
    r"coordinate",
    r"location_point",
]

QUALITY_PATTERNS = [
    r"flag",
    r"warning",
    r"issue",
    r"quality",
    r"independent",
    r"scope",
    r"confidence",
    r"precision",
    r"status",
    r"review",
    r"decision",
]


def nonempty_count(row, columns):
    if not columns:
        return 0

    count = 0

    for col in columns:
        value = row.get(col)

        if pd.notna(value) and str(value).strip():
            count += 1

    return count


def collect_text(row, columns):
    values = []

    for col in columns:
        value = row.get(col)

        if pd.isna(value):
            continue

        text = str(value).strip()

        if not text or text.lower() in {"nan", "none"}:
            continue

        values.append(f"{col}={text}")

    return " | ".join(values)


# ============================================================
# 6. BUILD COORDINATE EVIDENCE INVENTORY
# ============================================================

def build_evidence_inventory(merged):

    source_cols = matching_columns(
        merged,
        [r"^S51_.*" + p for p in SOURCE_PATTERNS],
    )

    coordinate_cols = matching_columns(
        merged,
        [r"^S51_.*" + p for p in COORDINATE_PATTERNS],
    )

    quality_cols = matching_columns(
        merged,
        [
            r"^S53_.*" + p for p in QUALITY_PATTERNS
        ],
    )

    evidence_cols = sorted(
        set(source_cols + coordinate_cols)
    )

    rows = []

    name_col = find_column(
        merged,
        NAME_CANDIDATES,
        required=False,
    )

    for _, row in merged.iterrows():

        record = {
            "UNLOCODE": row["_JOIN_KEY"],
            "Port_Name": (
                row[name_col] if name_col else pd.NA
            ),
            "Evidence_Source_Field_Count":
                nonempty_count(row, source_cols),
            "Coordinate_Field_Count":
                nonempty_count(row, coordinate_cols),
            "Source_Field_Details":
                collect_text(row, source_cols),
            "Coordinate_Field_Details":
                collect_text(row, coordinate_cols),
            "Quality_Audit_Details":
                collect_text(row, quality_cols),
        }

        for col in evidence_cols:
            record[col] = row[col]

        rows.append(record)

    inventory = pd.DataFrame(rows)

    return inventory, source_cols, coordinate_cols, quality_cols


# ============================================================
# 7. BUILD RESEARCHER REVIEW REGISTER
# ============================================================

def build_review_register(
    merged,
    inventory,
    source_cols,
    coordinate_cols,
    quality_cols,
):

    identity_col = find_column(
        merged,
        IDENTITY_CANDIDATES,
        required=False,
    )

    coordinate_status_col = find_column(
        merged,
        COORD_STATUS_CANDIDATES,
        required=False,
    )

    eligibility_col = find_column(
        merged,
        ELIGIBILITY_CANDIDATES,
        required=False,
    )

    use_col = find_column(
        merged,
        RECOMMENDED_USE_CANDIDATES,
        required=False,
    )

    name_col = find_column(
        merged,
        NAME_CANDIDATES,
        required=False,
    )

    # Script 54's coordinate validation fields are retained
    # exactly as supplied; no new approval is inferred.
    validated_lat_cols = matching_columns(
        merged,
        [r"validated_port_latitude"],
    )
    validated_lon_cols = matching_columns(
        merged,
        [r"validated_port_longitude"],
    )

    rows = []

    for _, row in merged.iterrows():

        code = row["_JOIN_KEY"]

        identity = (
            row[identity_col]
            if identity_col else "NOT_AVAILABLE"
        )

        coordinate_status = (
            row[coordinate_status_col]
            if coordinate_status_col else "NOT_AVAILABLE"
        )

        eligibility = (
            row[eligibility_col]
            if eligibility_col else "NOT_AVAILABLE"
        )

        recommended_use = (
            row[use_col]
            if use_col else "NOT_AVAILABLE"
        )

        source_count = nonempty_count(row, source_cols)
        coordinate_count = nonempty_count(row, coordinate_cols)

        quality_details = collect_text(row, quality_cols).upper()

        validated_lat_present = any(
            pd.notna(row[c]) and str(row[c]).strip()
            for c in validated_lat_cols
        )

        validated_lon_present = any(
            pd.notna(row[c]) and str(row[c]).strip()
            for c in validated_lon_cols
        )

        validated_pair_present = (
            validated_lat_present and validated_lon_present
        )

        flags = []

        if source_count == 0:
            flags.append("NO_POPULATED_SOURCE_FIELDS_DETECTED")

        if coordinate_count == 0:
            flags.append("NO_POPULATED_COORDINATE_EVIDENCE_FIELDS_DETECTED")

        if source_count == 1:
            flags.append("ONLY_ONE_POPULATED_SOURCE_FIELD_DETECTED")

        if "INDEPENDENT" in quality_details:
            flags.append("INDEPENDENCE_REVIEW_FLAG_PRESENT")

        if "SCOPE" in quality_details:
            flags.append("REFERENCE_SCOPE_REVIEW_FLAG_PRESENT")

        if "BOUNDARY" in quality_details or "POLYGON" in quality_details:
            flags.append("BOUNDARY_OR_POLYGON_REFERENCE_REVIEW")

        if "DIFFERENT_PORT" in quality_details:
            flags.append("POSSIBLE_DIFFERENT_PORT_REFERENCE")

        if code == "QAUMS":
            flags.append("QAUMS_FACILITY_ASSOCIATION_UNRESOLVED")

        if not validated_pair_present:
            flags.append("VALIDATED_PORT_COORDINATE_PAIR_NOT_POPULATED")

        if str(coordinate_status).upper() not in {
            "APPROVED",
            "VALIDATED",
            "VERIFIED",
        }:
            flags.append("SCRIPT39_COORDINATE_STATUS_NOT_APPROVED")

        # Priority is for human review order only.
        # It does not change Script 49 eligibility.
        if code == "QAUMS":
            priority = "P1_FACILITY_RESOLUTION"
        elif source_count == 0 or coordinate_count == 0:
            priority = "P1_EVIDENCE_COMPLETENESS"
        elif flags:
            priority = "P2_SOURCE_AND_SCOPE_REVIEW"
        else:
            priority = "P3_RESEARCHER_CONFIRMATION"

        rows.append({
            "UNLOCODE": code,
            "Port_Name": (
                row[name_col] if name_col else pd.NA
            ),
            "Identity_Validation_Status": identity,
            "Script39_Coordinate_Validation_Status":
                coordinate_status,
            "Validated_Port_Coordinate_Pair_Populated":
                validated_pair_present,
            "Script49_Eligibility_Classification": eligibility,
            "Script49_Recommended_Use": recommended_use,
            "Populated_Source_Field_Count": source_count,
            "Populated_Coordinate_Field_Count": coordinate_count,
            "Review_Priority": priority,
            "Researcher_Review_Flags": " | ".join(flags),
            "Researcher_Review_Status": "PENDING",
            "Coordinate_Approval": "NOT_APPROVED_BY_SCRIPT_55",
            "Operational_Inclusion": "NOT_DECIDED_BY_SCRIPT_55",
            "AIS_Hormuz_Transit_Status":
                "NOT_ESTABLISHED_BY_SCRIPT_55",
        })

    review = pd.DataFrame(rows)

    return review


# ============================================================
# 8. VALIDATION
# ============================================================

def validate_outputs(merged, inventory, review):

    if len(merged) != EXPECTED_RECORDS:
        raise AssertionError("Consolidated record count is not 19.")

    if len(inventory) != EXPECTED_RECORDS:
        raise AssertionError("Evidence inventory record count is not 19.")

    if len(review) != EXPECTED_RECORDS:
        raise AssertionError("Review register record count is not 19.")

    if review["UNLOCODE"].duplicated().any():
        raise AssertionError("Duplicate UN/LOCODE in review register.")

    if set(review["UNLOCODE"]) != set(merged["_JOIN_KEY"]):
        raise AssertionError("Review register key coverage mismatch.")

    if not review["Researcher_Review_Status"].eq("PENDING").all():
        raise AssertionError("Unexpected researcher review status.")

    if not review["Coordinate_Approval"].eq(
        "NOT_APPROVED_BY_SCRIPT_55"
    ).all():
        raise AssertionError("Script 55 must not approve coordinates.")

    if not review["Operational_Inclusion"].eq(
        "NOT_DECIDED_BY_SCRIPT_55"
    ).all():
        raise AssertionError("Script 55 must not decide operational inclusion.")

    print("\nVALIDATION CHECKS")
    print("-" * 72)
    print("19 consolidated records retained: PASS")
    print("19 evidence inventory records retained: PASS")
    print("19 researcher review records retained: PASS")
    print("UN/LOCODE uniqueness: PASS")
    print("UN/LOCODE coverage: PASS")
    print("No coordinate approvals created: PASS")
    print("No operational inclusion decisions created: PASS")
    print("Researcher review remains pending: PASS")


# ============================================================
# 9. SUMMARY
# ============================================================

def build_summary(review, inventory):

    rows = [
        ("Consolidated records", len(review)),
        (
            "Records with populated source fields",
            int((review["Populated_Source_Field_Count"] > 0).sum()),
        ),
        (
            "Records with no populated source fields detected",
            int((review["Populated_Source_Field_Count"] == 0).sum()),
        ),
        (
            "Records with populated coordinate evidence fields",
            int((review["Populated_Coordinate_Field_Count"] > 0).sum()),
        ),
        (
            "Records with no coordinate evidence fields detected",
            int((review["Populated_Coordinate_Field_Count"] == 0).sum()),
        ),
        (
            "Validated port coordinate pairs populated",
            int(review["Validated_Port_Coordinate_Pair_Populated"].sum()),
        ),
        (
            "Records requiring P1 review",
            int(review["Review_Priority"].str.startswith("P1").sum()),
        ),
        (
            "Records requiring P2 review",
            int(review["Review_Priority"].str.startswith("P2").sum()),
        ),
        (
            "Records requiring P3 review",
            int(review["Review_Priority"].str.startswith("P3").sum()),
        ),
        (
            "QAUMS facility association unresolved",
            int(
                review["UNLOCODE"].eq("QAUMS").sum()
            ),
        ),
        ("Coordinate approvals made by Script 55", 0),
        ("Operational inclusion decisions made by Script 55", 0),
        ("AIS-confirmed Hormuz transits established by Script 55", 0),
        ("Records pending researcher review", len(review)),
        ("Upstream files modified", "NO"),
    ]

    return pd.DataFrame(rows, columns=["Metric", "Value"])


# ============================================================
# 10. REPORT
# ============================================================

def write_report(
    review,
    inventory,
    summary,
    source_cols,
    coordinate_cols,
    quality_cols,
):

    path = OUTPUTS["report"]

    with path.open("w", encoding="utf-8") as f:

        f.write(
            "SCRIPT 55 — COORDINATE EVIDENCE REVIEW "
            "AND RESEARCHER PRIORITISATION\n"
        )
        f.write("=" * 88 + "\n\n")

        f.write(
            f"Generated: {datetime.now().isoformat(timespec='seconds')}\n\n"
        )

        f.write("INPUT REGISTERS\n")
        f.write("-" * 88 + "\n")

        for label, path_in in INPUTS.items():
            f.write(f"{label}: {path_in}\n")

        f.write("\nDETECTED EVIDENCE FIELD COUNTS\n")
        f.write("-" * 88 + "\n")
        f.write(f"Source-related fields: {len(source_cols)}\n")
        f.write(f"Coordinate-related fields: {len(coordinate_cols)}\n")
        f.write(f"Quality-related fields: {len(quality_cols)}\n")

        f.write("\nSUMMARY\n")
        f.write("-" * 88 + "\n")
        f.write(summary.to_string(index=False))
        f.write("\n\n")

        f.write("RESEARCHER REVIEW PRIORITIES\n")
        f.write("-" * 88 + "\n")

        for priority in ["P1_FACILITY_RESOLUTION",
                         "P1_EVIDENCE_COMPLETENESS",
                         "P2_SOURCE_AND_SCOPE_REVIEW",
                         "P3_RESEARCHER_CONFIRMATION"]:

            subset = review[
                review["Review_Priority"] == priority
            ]

            if subset.empty:
                continue

            f.write(f"\n{priority}\n")

            for _, row in subset.iterrows():
                f.write(
                    f"{row['UNLOCODE']} | {row['Port_Name']} | "
                    f"Identity={row['Identity_Validation_Status']} | "
                    f"Coordinate={row['Script39_Coordinate_Validation_Status']} | "
                    f"Sources={row['Populated_Source_Field_Count']} | "
                    f"Coordinate fields={row['Populated_Coordinate_Field_Count']}\n"
                )

                f.write(
                    f"  Flags: {row['Researcher_Review_Flags']}\n"
                )

                f.write(
                    f"  Script 49 eligibility: "
                    f"{row['Script49_Eligibility_Classification']}\n"
                )

                f.write(
                    f"  Recommended use: {row['Script49_Recommended_Use']}\n"
                )

        f.write("\nMETHODOLOGICAL LIMITATIONS\n")
        f.write("-" * 88 + "\n")
        f.write(
            "1. Populated fields indicate recorded evidence, not verified evidence.\n"
            "2. Source-field counts do not establish source independence.\n"
            "3. Coordinate-field counts do not establish coordinate accuracy.\n"
            "4. Port, terminal, berth, buoy, pilot station and boundary references "
            "are distinct objects.\n"
            "5. Script 39 remains the authority for coordinate-validation status.\n"
            "6. Script 49 eligibility classifications and recommended uses are "
            "carried forward without modification.\n"
            "7. AIS transit confirmation is separate from regional/sensitivity "
            "eligibility.\n"
            "8. QAUMS facility association remains unresolved.\n"
            "9. No coordinate or operational inclusion decision is approved "
            "by Script 55.\n"
            "10. All 19 records remain pending researcher review.\n"
        )

        f.write("\nOUTPUTS\n")
        f.write("-" * 88 + "\n")

        for key, output in OUTPUTS.items():
            f.write(f"{key}: {output.relative_to(ROOT)}\n")

        f.write("\nUPSTREAM REGISTER MODIFICATION: NO\n")

    return path


# ============================================================
# 11. MAIN
# ============================================================

def main():

    print("=" * 88)
    print("SCRIPT 55: COORDINATE EVIDENCE REVIEW")
    print("=" * 88)

    consolidated, evidence, quality = load_inputs()

    merged, base_key, evidence_key, quality_key = (
        reconcile_registers(
            consolidated,
            evidence,
            quality,
        )
    )

    inventory, source_cols, coordinate_cols, quality_cols = (
        build_evidence_inventory(merged)
    )

    review = build_review_register(
        merged,
        inventory,
        source_cols,
        coordinate_cols,
        quality_cols,
    )

    summary = build_summary(review, inventory)

    validate_outputs(merged, inventory, review)

    # Save only Script 55 outputs.
    review.to_csv(OUTPUTS["review"], index=False)
    inventory.to_csv(OUTPUTS["evidence"], index=False)
    summary.to_csv(OUTPUTS["summary"], index=False)

    report_path = write_report(
        review,
        inventory,
        summary,
        source_cols,
        coordinate_cols,
        quality_cols,
    )

    print("\nSUMMARY")
    print("-" * 72)
    print(summary.to_string(index=False))

    print("\nOUTPUT FILES")
    print("-" * 72)

    for key, path in OUTPUTS.items():
        print(f"{key}: {path.relative_to(ROOT)}")

    print("\nSCRIPT 55 COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\nSCRIPT 55 FAILED")
        print(f"{type(exc).__name__}: {exc}")
        sys.exit(1)
