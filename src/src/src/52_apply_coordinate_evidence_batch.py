#!/usr/bin/env python3
"""
Apply a coordinate-evidence patch to Script 51's master register.

Safety properties:
- Updates rows by UN_LOCODE only.
- Updates only an explicit whitelist of evidence-review columns.
- Does NOT populate validated port/terminal coordinate fields or final approval fields.
- Blank patch cells never erase existing values.
- Rejects duplicate IDs, unknown IDs, missing columns, invalid coordinate pairs/ranges.
- Creates a timestamped backup and writes atomically.
"""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd

MASTER_DEFAULT = Path("outputs/tables/51_primary_source_coordinate_evidence_register.csv")

ALLOWED_COLUMNS = [
    "Primary_Source_Organization_Reviewed",
    "Primary_Source_Title_Reviewed",
    "Primary_Source_URL_Reviewed",
    "Primary_Source_Access_Date_Reviewed",
    "Primary_Source_Type",
    "Primary_Source_Exact_Evidence",
    "Primary_Source_Coordinate_Text",
    "Primary_Source_Latitude",
    "Primary_Source_Longitude",
    "Primary_Source_Datum_or_CRS",
    "Primary_Source_Reference_Point",
    "Primary_Source_Coordinate_Scope",
    "Primary_Source_Claim_Verification",
    "Secondary_Source_Organization_Reviewed",
    "Secondary_Source_Title_Reviewed",
    "Secondary_Source_URL_Reviewed",
    "Secondary_Source_Access_Date_Reviewed",
    "Secondary_Source_Exact_Evidence",
    "Secondary_Source_Latitude",
    "Secondary_Source_Longitude",
    "Secondary_Source_Datum_or_CRS",
    "Secondary_Source_Reference_Point",
    "Secondary_Source_Coordinate_Scope",
    "Independent_Corroboration_Status",
    "Coordinate_Conflict_Description",
    "Researcher_Evidence_Conclusion",
    "Evidence_Review_QA_Status",
    "Research_Progress_Status",
]

COORDINATE_PAIRS = [
    ("Primary_Source_Latitude", "Primary_Source_Longitude"),
    ("Secondary_Source_Latitude", "Secondary_Source_Longitude"),
]

# These columns are deliberately prohibited from this evidence-only update.
PROTECTED_COLUMNS = {
    "Validated_Port_Latitude",
    "Validated_Port_Longitude",
    "Validated_Terminal_Latitude",
    "Validated_Terminal_Longitude",
    "Researcher_Validated_Latitude",
    "Researcher_Validated_Longitude",
    "Researcher_Recommended_Latitude",
    "Researcher_Recommended_Longitude",
    "Coordinate_Validation_Status",
    "Coordinate_Confidence",
    "Researcher_Coordinate_Decision",
    "Operational_Inclusion_Decision",
    "Researcher_Review_Status",
}


def validate_patch(master: pd.DataFrame, patch: pd.DataFrame) -> None:
    if "UN_LOCODE" not in master.columns or "UN_LOCODE" not in patch.columns:
        raise ValueError("Both master and patch must contain UN_LOCODE.")

    if master["UN_LOCODE"].duplicated().any():
        duplicates = master.loc[master["UN_LOCODE"].duplicated(False), "UN_LOCODE"].tolist()
        raise ValueError(f"Duplicate UN_LOCODE values in master: {duplicates}")

    if patch["UN_LOCODE"].duplicated().any():
        duplicates = patch.loc[patch["UN_LOCODE"].duplicated(False), "UN_LOCODE"].tolist()
        raise ValueError(f"Duplicate UN_LOCODE values in patch: {duplicates}")

    unknown = sorted(set(patch["UN_LOCODE"].astype(str)) - set(master["UN_LOCODE"].astype(str)))
    if unknown:
        raise ValueError(f"Patch contains unknown UN_LOCODE values: {unknown}")

    forbidden = sorted((set(patch.columns) & PROTECTED_COLUMNS))
    if forbidden:
        raise ValueError(f"Patch attempts to modify protected/final fields: {forbidden}")

    not_allowed = sorted(set(patch.columns) - {"UN_LOCODE"} - set(ALLOWED_COLUMNS))
    if not_allowed:
        raise ValueError(f"Patch contains columns outside the update whitelist: {not_allowed}")

    missing_master = sorted(set(patch.columns) - set(master.columns))
    if missing_master:
        raise ValueError(f"Master is missing patch columns: {missing_master}")

    for lat_col, lon_col in COORDINATE_PAIRS:
        if lat_col not in patch.columns and lon_col not in patch.columns:
            continue
        if lat_col not in patch.columns or lon_col not in patch.columns:
            raise ValueError(f"Coordinate pair must include both {lat_col} and {lon_col}.")

        for _, row in patch.iterrows():
            lat, lon = row[lat_col], row[lon_col]
            lat_blank = pd.isna(lat) or str(lat).strip() == ""
            lon_blank = pd.isna(lon) or str(lon).strip() == ""
            if lat_blank != lon_blank:
                raise ValueError(
                    f"Incomplete coordinate pair for {row['UN_LOCODE']}: {lat_col}/{lon_col}"
                )
            if not lat_blank:
                lat, lon = float(lat), float(lon)
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError(
                        f"Out-of-range coordinate for {row['UN_LOCODE']}: {lat}, {lon}"
                    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("patch_csv", type=Path, help="Path to the batch patch CSV")
    parser.add_argument("--master", type=Path, default=MASTER_DEFAULT)
    args = parser.parse_args()

    master_path = args.master
    patch_path = args.patch_csv

    if not master_path.exists():
        raise FileNotFoundError(f"Master register not found: {master_path}")
    if not patch_path.exists():
        raise FileNotFoundError(f"Patch CSV not found: {patch_path}")

    master = pd.read_csv(master_path, dtype={"UN_LOCODE": str})
    patch = pd.read_csv(patch_path, dtype={"UN_LOCODE": str})
    master["UN_LOCODE"] = master["UN_LOCODE"].str.strip()
    patch["UN_LOCODE"] = patch["UN_LOCODE"].str.strip()

    validate_patch(master, patch)

    original_rows = len(master)
    original_columns = list(master.columns)
    update_columns = [c for c in patch.columns if c != "UN_LOCODE"]

    indexed = master.set_index("UN_LOCODE", drop=False)
    updated_cells = 0
    updated_codes = []

    for _, patch_row in patch.iterrows():
        code = patch_row["UN_LOCODE"]
        updated_codes.append(code)
        for col in update_columns:
            value = patch_row[col]
            if pd.isna(value) or (isinstance(value, str) and value.strip() == ""):
                continue
            if indexed.at[code, col] != value:
                indexed.at[code, col] = value
                updated_cells += 1

    result = indexed.reset_index(drop=True)

    if len(result) != original_rows:
        raise RuntimeError("Row count changed unexpectedly.")
    if list(result.columns) != original_columns:
        raise RuntimeError("Column order/schema changed unexpectedly.")
    if result["UN_LOCODE"].duplicated().any():
        raise RuntimeError("Duplicate UN_LOCODE detected after update.")

    # Preserve the original master before replacing it.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = master_path.with_name(
        f"{master_path.stem}_pre_batch_patch_{stamp}{master_path.suffix}"
    )
    shutil.copy2(master_path, backup)

    # Atomic write in the same directory.
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{master_path.stem}_", suffix=".tmp", dir=str(master_path.parent)
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        result.to_csv(temp_path, index=False)
        os.replace(temp_path, master_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

    # Reload and verify.
    check = pd.read_csv(master_path, dtype={"UN_LOCODE": str})
    if len(check) != original_rows or list(check.columns) != original_columns:
        raise RuntimeError("Post-write verification failed: schema/row count mismatch.")
    if not set(updated_codes).issubset(set(check["UN_LOCODE"])):
        raise RuntimeError("Post-write verification failed: updated codes missing.")

    print("BATCH PATCH APPLIED")
    print(f"Master: {master_path}")
    print(f"Backup: {backup}")
    print(f"Rows preserved: {len(check)}")
    print(f"Columns preserved: {len(check.columns)}")
    print(f"Records patched: {len(updated_codes)}")
    print(f"Evidence fields considered: {len(update_columns)}")
    print(f"Nonblank cells updated: {updated_cells}")
    print("Updated UN_LOCODEs:", ", ".join(updated_codes))
    print("Validated port/terminal coordinates and final approval fields were NOT modified.")


if __name__ == "__main__":
    main()
