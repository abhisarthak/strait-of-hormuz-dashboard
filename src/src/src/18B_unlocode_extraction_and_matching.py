
from pathlib import Path
from zipfile import ZipFile
import re

import numpy as np
import pandas as pd


# ============================================================
# SCRIPT 18B
# UN/LOCODE EXTRACTION AND COORDINATE MATCHING
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"

for folder in [PROCESSED, TABLES, REPORTS]:
    folder.mkdir(parents=True, exist_ok=True)


ZIP_FILES = {
    "PRODUCTION": RAW / "unlocode" / "artifacts.zip",
    "PRERELEASE": RAW / "unlocode" / "unlocode-latest.zip",
}

PORT_MASTER_FILE = RAW / "active_ports.csv"

CSV_PARTS = [
    "release/csv/UNLOCODE CodeListPart1.csv",
    "release/csv/UNLOCODE CodeListPart2.csv",
    "release/csv/UNLOCODE CodeListPart3.csv",
]


# ------------------------------------------------------------
# 1. SOURCE COLUMN POSITIONS
# ------------------------------------------------------------

# The UN/LOCODE CSV files have NO conventional header row.
# The first row contains actual data.
#
# Positions identified from your inspection output:
#
# 0  : Empty / separator field
# 1  : Country code
# 2  : Location code
# 3  : Location name
# 4  : Location name without diacritics
# 5  : Subdivision
# 6  : Function
# 7  : Status
# 8  : Date
# 9  : IATA code
# 10 : Coordinates
# 11 : Remarks

COLUMN_MAP = {
    1: "Country_Code",
    2: "Location_Code",
    3: "Location_Name",
    4: "Location_Name_Without_Diacritics",
    5: "Subdivision",
    6: "Function",
    7: "Status",
    8: "Date",
    9: "IATA_Code",
    10: "Coordinate_Raw",
    11: "Remarks",
}


# ------------------------------------------------------------
# 2. HELPER FUNCTIONS
# ------------------------------------------------------------

def normalize_text(value):

    if pd.isna(value):
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value).strip().upper()
    )


def normalize_locode(series):

    return (
        series.astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )


def normalize_country(series):

    return normalize_locode(series)


def find_column(df, candidates):

    lookup = {
        re.sub(r"[^a-z0-9]", "", str(col).lower()): col
        for col in df.columns
    }

    for candidate in candidates:

        key = re.sub(
            r"[^a-z0-9]",
            "",
            candidate.lower()
        )

        if key in lookup:
            return lookup[key]

    raise KeyError(
        f"Could not find any of {candidates}. "
        f"Available: {df.columns.tolist()}"
    )


def parse_coordinate_component(value, coordinate_type):
    """
    Parse a UN/LOCODE coordinate component.

    Latitude examples:
        2336N
        2336S

    Longitude examples:
        05832E
        00131W

    Returns decimal degrees or NaN.
    """

    if pd.isna(value):
        return np.nan

    value = str(value).strip().upper()

    if coordinate_type == "LAT":

        pattern = r"^(\d{2})(\d{2})([NS])$"

    elif coordinate_type == "LON":

        pattern = r"^(\d{3})(\d{2})([EW])$"

    else:
        raise ValueError("Unknown coordinate type")

    match = re.match(pattern, value)

    if not match:
        return np.nan

    degrees = int(match.group(1))
    minutes = int(match.group(2))
    direction = match.group(3)

    if minutes >= 60:
        return np.nan

    if coordinate_type == "LAT" and degrees > 90:
        return np.nan

    if coordinate_type == "LON" and degrees > 180:
        return np.nan

    decimal = degrees + minutes / 60

    if direction in ["S", "W"]:
        decimal *= -1

    return decimal


def parse_coordinate_pair(value):

    if pd.isna(value):
        return np.nan, np.nan

    value = str(value).strip().upper()

    if not value:
        return np.nan, np.nan

    parts = value.split()

    if len(parts) != 2:
        return np.nan, np.nan

    latitude = parse_coordinate_component(
        parts[0],
        "LAT"
    )

    longitude = parse_coordinate_component(
        parts[1],
        "LON"
    )

    return latitude, longitude


# ------------------------------------------------------------
# 3. EXTRACT ONE RELEASE
# ------------------------------------------------------------


def extract_release(release_name, zip_path):

    print("\n" + "=" * 85)
    print(f"EXTRACTING: {release_name}")
    print("=" * 85)

    if not zip_path.exists():
        raise FileNotFoundError(zip_path)

    all_parts = []

    with ZipFile(zip_path, "r") as archive:

        available_files = set(archive.namelist())

        for csv_file in CSV_PARTS:

            if csv_file not in available_files:
                raise FileNotFoundError(
                    f"{csv_file} missing from {zip_path.name}"
                )

            with archive.open(csv_file) as file:

                raw = pd.read_csv(
                    file,
                    header=None,
                    dtype=str,
                    encoding="utf-8-sig",
                    keep_default_na=False,
                    low_memory=False
                )

            if raw.shape[1] != 12:
                raise ValueError(
                    f"Expected 12 fields in {csv_file}, "
                    f"found {raw.shape[1]}"
                )

            part = raw.rename(columns=COLUMN_MAP)

            part["Source_File"] = csv_file
            part["Source_Release"] = release_name

            all_parts.append(part)

            print(
                f"{Path(csv_file).name}: "
                f"{len(part)} raw rows"
            )

    # IMPORTANT:
    # First combine all three CSV parts.
    combined = pd.concat(
        all_parts,
        ignore_index=True
    )

    rows_before = len(combined)

    # Clean country and location codes.
    combined["Country_Code"] = (
        combined["Country_Code"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    combined["Location_Code"] = (
        combined["Location_Code"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    # Exclude country-heading rows and malformed location codes.
    valid_locode_mask = (
        combined["Country_Code"].str.fullmatch(
            r"[A-Z]{2}",
            na=False
        )
        &
        combined["Location_Code"].str.fullmatch(
            r"[A-Z0-9]{3}",
            na=False
        )
    )

    combined = combined.loc[
        valid_locode_mask
    ].copy()

    removed_rows = rows_before - len(combined)

    print(
        "Country-heading / invalid rows removed:",
        removed_rows
    )

    # Clean remaining source columns.
    for column in COLUMN_MAP.values():

        if column in combined.columns:

            combined[column] = (
                combined[column]
                .astype("string")
                .str.strip()
                .replace("", pd.NA)
            )

    combined["UNLOCODE"] = (
        combined["Country_Code"]
        + combined["Location_Code"]
    )

    # Parse coordinates.
    parsed = combined["Coordinate_Raw"].apply(
        parse_coordinate_pair
    )

    combined["Latitude"] = parsed.apply(
        lambda x: x[0]
    )

    combined["Longitude"] = parsed.apply(
        lambda x: x[1]
    )

    combined["Coordinate_Valid"] = (
        combined["Latitude"].notna()
        & combined["Longitude"].notna()
    )

    combined["Coordinate_Status"] = np.select(
        [
            combined["Coordinate_Raw"].isna().to_numpy(dtype=bool),
            combined["Coordinate_Valid"].to_numpy(dtype=bool),
        ],
        [
            "MISSING_COORDINATES",
            "VALID_COORDINATES",
        ],
        default="INVALID_COORDINATE_FORMAT"
    )

    # Preserve and identify duplicate UN/LOCODE records.
    combined["UNLOCODE_Duplicate"] = (
        combined.duplicated(
            subset=["UNLOCODE"],
            keep=False
        )
    )

    output_file = (
        PROCESSED
        / f"18B_unlocode_{release_name.lower()}_full.csv"
    )

    combined.to_csv(
        output_file,
        index=False
    )

    print("\nClean records:", len(combined))
    print(
        "Unique UN/LOCODEs:",
        combined["UNLOCODE"].nunique()
    )

    print(
        "Valid coordinates:",
        int(combined["Coordinate_Valid"].sum())
    )

    print(
        "Missing coordinates:",
        int(
            (
                combined["Coordinate_Status"]
                == "MISSING_COORDINATES"
            ).sum()
        )
    )

    print(
        "Invalid coordinate formats:",
        int(
            (
                combined["Coordinate_Status"]
                == "INVALID_COORDINATE_FORMAT"
            ).sum()
        )
    )

    print(
        "Duplicate LOCODE rows:",
        int(combined["UNLOCODE_Duplicate"].sum())
    )

    print("Saved:", output_file)

    return combined


# ------------------------------------------------------------
# 4. EXTRACT BOTH RELEASES
# ------------------------------------------------------------

production = extract_release(
    "PRODUCTION",
    ZIP_FILES["PRODUCTION"]
)

prerelease = extract_release(
    "PRERELEASE",
    ZIP_FILES["PRERELEASE"]
)


# ------------------------------------------------------------
# 5. COMPARE PRODUCTION AND PRE-RELEASE
# ------------------------------------------------------------

print("\n" + "=" * 85)
print("PRODUCTION VS PRE-RELEASE COMPARISON")
print("=" * 85)

comparison_columns = [
    "UNLOCODE",
    "Location_Name",
    "Coordinate_Raw",
    "Latitude",
    "Longitude",
    "Coordinate_Status",
]

production_compare = production[
    comparison_columns
].copy()

prerelease_compare = prerelease[
    comparison_columns
].copy()

production_compare = production_compare.rename(
    columns={
        "Location_Name": "Production_Name",
        "Coordinate_Raw": "Production_Coordinate_Raw",
        "Latitude": "Production_Latitude",
        "Longitude": "Production_Longitude",
        "Coordinate_Status": "Production_Coordinate_Status",
    }
)

prerelease_compare = prerelease_compare.rename(
    columns={
        "Location_Name": "Prerelease_Name",
        "Coordinate_Raw": "Prerelease_Coordinate_Raw",
        "Latitude": "Prerelease_Latitude",
        "Longitude": "Prerelease_Longitude",
        "Coordinate_Status": "Prerelease_Coordinate_Status",
    }
)

# Retain only unique UN/LOCODE rows for comparison.
# Duplicates are separately preserved in the full datasets.

production_unique = production_compare.drop_duplicates(
    subset=["UNLOCODE"]
)

prerelease_unique = prerelease_compare.drop_duplicates(
    subset=["UNLOCODE"]
)

release_comparison = production_unique.merge(
    prerelease_unique,
    on="UNLOCODE",
    how="outer",
    indicator=True,
    validate="one_to_one"
)

release_comparison["Coordinate_Changed"] = (
    release_comparison["_merge"].eq("both")
    & (
        release_comparison["Production_Coordinate_Raw"]
        != release_comparison["Prerelease_Coordinate_Raw"]
    )
)

release_comparison["Coordinate_Changed"] = (
    release_comparison["Coordinate_Changed"]
    & (
        release_comparison["Production_Coordinate_Raw"].notna()
        | release_comparison["Prerelease_Coordinate_Raw"].notna()
    )
)

release_comparison["Release_Status"] = (
    release_comparison["_merge"].map({
        "left_only": "PRODUCTION_ONLY",
        "right_only": "PRERELEASE_ONLY",
        "both": "PRESENT_IN_BOTH"
    })
)

release_comparison.to_csv(
    TABLES / "18B_production_prerelease_comparison.csv",
    index=False
)

changed_coordinates = release_comparison[
    release_comparison["Coordinate_Changed"]
].copy()

changed_coordinates.to_csv(
    TABLES / "18B_coordinate_changes_between_releases.csv",
    index=False
)

print("Production unique codes:", production["UNLOCODE"].nunique())
print("Pre-release unique codes:", prerelease["UNLOCODE"].nunique())

print(
    "Production-only codes:",
    (release_comparison["_merge"] == "left_only").sum()
)

print(
    "Pre-release-only codes:",
    (release_comparison["_merge"] == "right_only").sum()
)

print(
    "Coordinate changes:",
    len(changed_coordinates)
)


# ------------------------------------------------------------
# 6. LOAD PORT MASTER
# ------------------------------------------------------------

print("\n" + "=" * 85)
print("PORT MASTER MATCHING")
print("=" * 85)

if not PORT_MASTER_FILE.exists():
    raise FileNotFoundError(PORT_MASTER_FILE)

ports_raw = pd.read_csv(
    PORT_MASTER_FILE,
    dtype=str,
    low_memory=False
)

master_locode_col = find_column(
    ports_raw,
    [
        "UNLocationCode",
        "UN Location Code",
        "LOCODE"
    ]
)

master_name_col = find_column(
    ports_raw,
    [
        "portName",
        "Port Name"
    ]
)

master_city_col = find_column(
    ports_raw,
    [
        "cityName",
        "City Name"
    ]
)

master_country_code_col = find_column(
    ports_raw,
    [
        "countryCode",
        "Country Code"
    ]
)

master_country_name_col = find_column(
    ports_raw,
    [
        "countryName",
        "Country Name"
    ]
)

master = pd.DataFrame({

    "Master_Record_ID": range(1, len(ports_raw) + 1),

    "Master_LOCODE": normalize_locode(
        ports_raw[master_locode_col]
    ),

    "Master_Port_Name": ports_raw[master_name_col],

    "Master_City_Name": ports_raw[master_city_col],

    "Master_Country_Code": normalize_country(
        ports_raw[master_country_code_col]
    ),

    "Master_Country_Name": ports_raw[master_country_name_col],
})

master["Master_LOCODE_Ambiguous"] = (
    master.duplicated(
        subset=["Master_LOCODE"],
        keep=False
    )
)

print("Port master records:", len(master))
print(
    "Unique master LOCODEs:",
    master["Master_LOCODE"].nunique()
)

print(
    "Ambiguous master LOCODE records:",
    int(master["Master_LOCODE_Ambiguous"].sum())
)


# ------------------------------------------------------------
# 7. MATCH MASTER AGAINST BOTH RELEASES
# ------------------------------------------------------------

def prepare_release_for_matching(df, prefix):

    columns = [
        "UNLOCODE",
        "Country_Code",
        "Location_Name",
        "Location_Name_Without_Diacritics",
        "Coordinate_Raw",
        "Latitude",
        "Longitude",
        "Coordinate_Status",
        "Source_File",
    ]

    result = df[columns].copy()

    result = result.rename(
        columns={
            column: f"{prefix}_{column}"
            for column in columns
            if column != "UNLOCODE"
        }
    )

    # Duplicate UN/LOCODEs must not multiply master records.
    # Retain first row for the one-to-one summary match,
    # while preserving all duplicate records in full output.

    result = result.drop_duplicates(
        subset=["UNLOCODE"],
        keep="first"
    )

    return result


production_match = prepare_release_for_matching(
    production,
    "Production"
)

prerelease_match = prepare_release_for_matching(
    prerelease,
    "Prerelease"
)

matched = master.merge(
    production_match,
    left_on="Master_LOCODE",
    right_on="UNLOCODE",
    how="left",
    validate="many_to_one"
)

matched = matched.drop(
    columns=["UNLOCODE"]
)

matched = matched.merge(
    prerelease_match,
    left_on="Master_LOCODE",
    right_on="UNLOCODE",
    how="left",
    validate="many_to_one"
)

matched = matched.drop(
    columns=["UNLOCODE"]
)


# ------------------------------------------------------------
# 8. MATCHING STATUS
# ------------------------------------------------------------

matched["Production_Match_Status"] = np.where(
    matched["Production_Latitude"].notna()
    & matched["Production_Longitude"].notna(),
    "MATCHED_WITH_COORDINATES",
    np.where(
        matched["Production_Country_Code"].notna(),
        "MATCHED_WITHOUT_VALID_COORDINATES",
        "NOT_MATCHED"
    )
)

matched["Prerelease_Match_Status"] = np.where(
    matched["Prerelease_Latitude"].notna()
    & matched["Prerelease_Longitude"].notna(),
    "MATCHED_WITH_COORDINATES",
    np.where(
        matched["Prerelease_Country_Code"].notna(),
        "MATCHED_WITHOUT_VALID_COORDINATES",
        "NOT_MATCHED"
    )
)

# ------------------------------------------------------------
# SAFE PRODUCTION VS PRERELEASE COMPARISON
# ------------------------------------------------------------

production_raw = (
    matched["Production_Coordinate_Raw"]
    .astype("string")
)

prerelease_raw = (
    matched["Prerelease_Coordinate_Raw"]
    .astype("string")
)

both_missing = (
    production_raw.isna()
    & prerelease_raw.isna()
).to_numpy(dtype=bool)

missing_production = (
    production_raw.isna()
    & prerelease_raw.notna()
).to_numpy(dtype=bool)

missing_prerelease = (
    production_raw.notna()
    & prerelease_raw.isna()
).to_numpy(dtype=bool)

identical_coordinates = (
    production_raw
    .eq(prerelease_raw)
    .fillna(False)
    .to_numpy(dtype=bool)
)

matched["Coordinate_Release_Comparison"] = np.select(
    [
        both_missing,
        missing_production,
        missing_prerelease,
        identical_coordinates,
    ],
    [
        "MISSING_IN_BOTH_RELEASES",
        "MISSING_IN_PRODUCTION",
        "MISSING_IN_PRERELEASE",
        "IDENTICAL_COORDINATES",
    ],
default="COORDINATES_DIFFER_BETWEEN_RELEASES"
)
[
        matched["Production_Coordinate_Raw"].isna()
        & matched["Prerelease_Coordinate_Raw"].isna(),

        matched["Production_Coordinate_Raw"].isna(),

        matched["Prerelease_Coordinate_Raw"].isna(),

        matched["Production_Coordinate_Raw"]
        == matched["Prerelease_Coordinate_Raw"],
    ],
[
        "MISSING_IN_BOTH_RELEASES",
        "MISSING_IN_PRODUCTION",
        "MISSING_IN_PRERELEASE",
        "IDENTICAL_COORDINATES",
    ],
default="COORDINATES_DIFFER_BETWEEN_RELEASES"

matched["Master_Facility_Review"] = np.where(
    matched["Master_LOCODE_Ambiguous"],
    "FACILITY_LEVEL_MATCHING_REQUIRED",
    "STANDARD_LOCODE_MATCH"
)

matched.to_csv(
    PROCESSED / "18B_port_master_coordinate_matching.csv",
    index=False
)


# ------------------------------------------------------------
# 9. MATCHING DIAGNOSTICS
# ------------------------------------------------------------

unmatched = matched[
    matched["Production_Match_Status"] == "NOT_MATCHED"
].copy()

unmatched.to_csv(
    TABLES / "18B_unmatched_master_ports.csv",
    index=False
)

missing_coordinates = matched[
    matched["Production_Match_Status"]
    == "MATCHED_WITHOUT_VALID_COORDINATES"
].copy()

missing_coordinates.to_csv(
    TABLES / "18B_matched_ports_without_coordinates.csv",
    index=False
)

ambiguous_master = matched[
    matched["Master_LOCODE_Ambiguous"]
].copy()

ambiguous_master.to_csv(
    TABLES / "18B_ambiguous_master_locodes.csv",
    index=False
)


# ------------------------------------------------------------
# 10. CREATE REPORT
# ------------------------------------------------------------

report_file = (
    REPORTS / "18B_unlocode_extraction_and_matching_report.txt"
)

with open(report_file, "w", encoding="utf-8") as f:

    f.write("=" * 85 + "\n")
    f.write("SCRIPT 18B: UN/LOCODE EXTRACTION AND MATCHING REPORT\n")
    f.write("=" * 85 + "\n\n")

    f.write("SOURCE DATASETS\n")
    f.write("-" * 85 + "\n")

    f.write(
        f"Production records: {len(production)}\n"
    )

    f.write(
        f"Pre-release records: {len(prerelease)}\n"
    )

    f.write(
        f"Production unique UN/LOCODEs: "
        f"{production['UNLOCODE'].nunique()}\n"
    )

    f.write(
        f"Pre-release unique UN/LOCODEs: "
        f"{prerelease['UNLOCODE'].nunique()}\n\n"
    )

    f.write("COORDINATE QUALITY\n")
    f.write("-" * 85 + "\n")

    f.write(
        production["Coordinate_Status"]
        .value_counts(dropna=False)
        .to_string()
    )

    f.write("\n\nPORT MASTER MATCHING\n")
    f.write("-" * 85 + "\n")

    f.write(
        f"Master records: {len(master)}\n"
    )

    f.write(
        f"Production coordinate matches: "
        f"{(matched['Production_Match_Status'] == 'MATCHED_WITH_COORDINATES').sum()}\n"
    )

    f.write(
        f"Matched without coordinates: {len(missing_coordinates)}\n"
    )

    f.write(
        f"Unmatched master records: {len(unmatched)}\n"
    )

    f.write(
        f"Ambiguous master records: {len(ambiguous_master)}\n\n"
    )

    f.write("PRODUCTION / PRE-RELEASE COORDINATE COMPARISON\n")
    f.write("-" * 85 + "\n")

    f.write(
        f"Coordinate changes: {len(changed_coordinates)}\n"
    )

    f.write(
        f"Codes only in production: "
        f"{(release_comparison['_merge'] == 'left_only').sum()}\n"
    )

    f.write(
        f"Codes only in pre-release: "
        f"{(release_comparison['_merge'] == 'right_only').sum()}\n"
    )

    f.write("\n\nMETHODOLOGICAL NOTES\n")
    f.write("-" * 85 + "\n")

    f.write(
        "1. Original ZIP archives were not modified.\n"
    )

    f.write(
        "2. The UN/LOCODE CSV files were read without headers.\n"
    )

    f.write(
        "3. Coordinates were converted from degrees/minutes "
        "to decimal degrees.\n"
    )

    f.write(
        "4. Duplicate UN/LOCODE records were preserved in "
        "the full extracted datasets.\n"
    )

    f.write(
        "5. The one-row matching summary uses the first "
        "UN/LOCODE occurrence. It is not a facility-level "
        "resolution for ambiguous codes.\n"
    )

    f.write(
        "6. UN/LOCODE coordinates may represent localities, "
        "not exact port terminals.\n"
    )

    f.write(
        "7. Coordinate presence does not prove vessel transit "
        "through the Strait of Hormuz.\n"
    )


# ------------------------------------------------------------
# 11. FINAL SUMMARY
# ------------------------------------------------------------

print("\n" + "=" * 85)
print("SCRIPT 18B COMPLETED SUCCESSFULLY")
print("=" * 85)

print("\nUN/LOCODE DATASETS")
print("-" * 85)

print("Production records:", len(production))
print("Pre-release records:", len(prerelease))

print("\nCOORDINATE CHANGES")
print("-" * 85)

print("Changed coordinates:", len(changed_coordinates))

if not changed_coordinates.empty:

    print(
        changed_coordinates[
            [
                "UNLOCODE",
                "Production_Coordinate_Raw",
                "Prerelease_Coordinate_Raw",
            ]
        ].head(15).to_string(index=False)
    )

print("\nPORT MASTER MATCHING")
print("-" * 85)

print("Master records:", len(master))

print(
    "Production coordinate matches:",
    (
        matched["Production_Match_Status"]
        == "MATCHED_WITH_COORDINATES"
    ).sum()
)

print("Unmatched master records:", len(unmatched))

print("Ambiguous master records:", len(ambiguous_master))

print("\nOUTPUTS")
print("-" * 85)

print(
    PROCESSED / "18B_port_master_coordinate_matching.csv"
)

print(
    TABLES / "18B_production_prerelease_comparison.csv"
)

print(
    TABLES / "18B_coordinate_changes_between_releases.csv"
)

print(
    TABLES / "18B_unmatched_master_ports.csv"
)

print(report_file)

print("\nOriginal source data preserved.")
print("No coordinates were manually invented.")
print("No vessel transit was inferred.")
