
"""
===============================================================================
SCRIPT 18E: INDEPENDENT PORT AND FACILITY VALIDATION
===============================================================================

PROJECT:
    Vessel Schedule Recovery under Disruptions in the Strait of Hormuz

PURPOSE:
    1. Independently assess the 19 geographically shortlisted port records.
    2. Preserve production and pre-release UN/LOCODE coordinates separately.
    3. Identify coordinate disagreements and missing coordinates.
    4. Distinguish port, industrial facility and city-level locations.
    5. Generate a structured manual evidence-validation register.
    6. Prioritize locations for further geographic and AIS investigation.

IMPORTANT:
    This script does NOT automatically confirm:
        - That a location is an operational seaport.
        - That a facility is an independent maritime terminal.
        - That a vessel transited the Strait of Hormuz.
        - That a coordinate is geographically authoritative.

    Independent verification must be documented using external evidence.

INPUTS:
    data/processed/18C_coordinate_assessed_port_master.csv
    outputs/tables/18D_hormuz_relevant_port_register.csv

OUTPUTS:
    data/processed/18E_independent_port_validation_register.csv
    outputs/tables/18E_port_facility_validation_register.csv
    outputs/tables/18E_coordinate_alternative_register.csv
    outputs/tables/18E_validation_priority_summary.csv
    outputs/reports/18E_independent_port_facility_validation_report.txt

===============================================================================
"""

from pathlib import Path
import re
import sys
import pandas as pd
import numpy as np


# =============================================================================
# 1. PROJECT PATHS
# =============================================================================

ROOT = Path(__file__).resolve().parents[1]

INPUT_MASTER = (
    ROOT / "data" / "processed"
    / "18C_coordinate_assessed_port_master.csv"
)

INPUT_SHORTLIST = (
    ROOT / "outputs" / "tables"
    / "18D_hormuz_relevant_port_register.csv"
)

OUTPUT_PROCESSED = (
    ROOT / "data" / "processed"
    / "18E_independent_port_validation_register.csv"
)

OUTPUT_REGISTER = (
    ROOT / "outputs" / "tables"
    / "18E_port_facility_validation_register.csv"
)

OUTPUT_COORDINATES = (
    ROOT / "outputs" / "tables"
    / "18E_coordinate_alternative_register.csv"
)

OUTPUT_SUMMARY = (
    ROOT / "outputs" / "tables"
    / "18E_validation_priority_summary.csv"
)

OUTPUT_REPORT = (
    ROOT / "outputs" / "reports"
    / "18E_independent_port_facility_validation_report.txt"
)

for folder in [
    OUTPUT_PROCESSED.parent,
    OUTPUT_REGISTER.parent,
    OUTPUT_REPORT.parent
]:
    folder.mkdir(parents=True, exist_ok=True)


# =============================================================================
# 2. HELPER FUNCTIONS
# =============================================================================

def log(message=""):
    print(message)


def normalize_code(value):
    if pd.isna(value):
        return None
    return str(value).strip().upper()


def find_column(df, candidates, required=True):
    """
    Find a column using exact case-insensitive matches first,
    followed by partial matches.
    """
    columns = list(df.columns)
    lower_map = {str(c).lower(): c for c in columns}

    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]

    for candidate in candidates:
        for column in columns:
            if candidate.lower() in str(column).lower():
                return column

    if required:
        raise KeyError(
            f"Could not identify required column. "
            f"Candidates: {candidates}\n"
            f"Available columns: {columns}"
        )

    return None


def safe_value(row, column):
    if column is None or column not in row.index:
        return np.nan
    return row[column]


def is_valid_number(value):
    try:
        return pd.notna(value) and np.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def coordinate_status(lat, lon):
    """
    Basic coordinate range validation.
    This does not establish geographic correctness.
    """
    if not is_valid_number(lat) or not is_valid_number(lon):
        return "MISSING_OR_UNPARSED"

    lat = float(lat)
    lon = float(lon)

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return "INVALID_RANGE"

    return "NUMERICALLY_VALID"


def identify_coordinate_columns(df):
    """
    Identify production and pre-release coordinate-related columns.
    Retains all coordinate fields rather than assuming one coordinate
    representation is authoritative.
    """
    result = {}

    for release in ["production", "prerelease"]:
        matching = [
            c for c in df.columns
            if release in str(c).lower()
            and (
                "latitude" in str(c).lower()
                or "longitude" in str(c).lower()
                or "coordinate" in str(c).lower()
                or "coord" in str(c).lower()
            )
        ]

        result[release] = matching

    return result


def get_numeric_coordinate(row, columns, direction):
    """
    Locate a parsed numeric latitude or longitude column.

    Searches column names for:
        latitude / longitude
        lat / lon

    Raw coordinate strings are deliberately excluded.
    """
    direction = direction.lower()

    for column in columns:
        name = str(column).lower()

        if "raw" in name:
            continue

        if direction == "latitude":
            matches = (
                "latitude" in name
                or name.endswith("_lat")
                or name == "lat"
            )
        else:
            matches = (
                "longitude" in name
                or "long" in name
                or name.endswith("_lon")
                or name == "lon"
            )

        if matches:
            value = row[column]
            if is_valid_number(value):
                return float(value)

    return np.nan


# =============================================================================
# 3. LOAD INPUT DATA
# =============================================================================

log("=" * 79)
log("SCRIPT 18E: INDEPENDENT PORT AND FACILITY VALIDATION")
log("=" * 79)

for path in [INPUT_MASTER, INPUT_SHORTLIST]:
    if not path.exists():
        log(f"\nERROR: Input file not found: {path}")
        sys.exit(1)

master = pd.read_csv(INPUT_MASTER, low_memory=False)
shortlist = pd.read_csv(INPUT_SHORTLIST, low_memory=False)

log(f"\n18C assessed port master shape: {master.shape}")
log(f"18D Hormuz shortlist shape: {shortlist.shape}")


# =============================================================================
# 4. IDENTIFY KEY COLUMNS
# =============================================================================

master_locode_col = find_column(
    master,
    ["Master_LOCODE", "UNLocationCode", "UN_LOCODE", "LOCODE"]
)

shortlist_locode_col = find_column(
    shortlist,
    ["Master_LOCODE", "UNLocationCode", "UN_LOCODE", "LOCODE"]
)

master_name_col = find_column(
    master,
    ["Master_Port_Name", "portName", "Port_Name"],
    required=False
)

master_city_col = find_column(
    master,
    ["Master_City_Name", "cityName", "City_Name"],
    required=False
)

master_country_col = find_column(
    master,
    ["Master_Country_Code", "countryCode", "Country_Code"],
    required=False
)

# Find geographic fields generated by Script 18D.
zone_col = find_column(
    shortlist,
    ["18D_Geographic_Zone", "Geographic_Zone"],
    required=False
)

distance_col = find_column(
    shortlist,
    [
        "18D_Distance_To_Hormuz_Reference_KM",
        "Distance_To_Hormuz_Reference_KM"
    ],
    required=False
)

screening_col = find_column(
    shortlist,
    [
        "18D_Final_Port_Screening_Status",
        "Final_Port_Screening_Status"
    ],
    required=False
)

# Find coordinate fields in 18C.
log("\nIdentifying coordinate fields in source master...")

master_coordinate_columns = identify_coordinate_columns(master)

for release, columns in master_coordinate_columns.items():
    log(f"{release}: {columns}")


# =============================================================================
# 5. NORMALIZE LOCODE AND MERGE SHORTLIST WITH MASTER
# =============================================================================

master["_JOIN_LOCODE"] = master[master_locode_col].apply(normalize_code)
shortlist["_JOIN_LOCODE"] = shortlist[shortlist_locode_col].apply(
    normalize_code
)

# Preserve every shortlisted record.
# Use a many-to-many merge intentionally so ambiguous LOCODEs are not lost.
merged = shortlist.merge(
    master,
    on="_JOIN_LOCODE",
    how="left",
    suffixes=("_18D", "_18C"),
    indicator=True
)

# =============================================================================
# RESOLVE MASTER DESCRIPTIVE COLUMNS AFTER MERGE
# =============================================================================

# The 18D and 18C datasets can contain overlapping column names.
# Explicitly retrieve the 18C-side master fields.

master_name_col_merged = find_column(
    merged,
    ["Master_Port_Name_18C", "Master_Port_Name"],
    required=False
)

master_city_col_merged = find_column(
    merged,
    ["Master_City_Name_18C", "Master_City_Name"],
    required=False
)

master_country_col_merged = find_column(
    merged,
    ["Master_Country_Code_18C", "Master_Country_Code"],
    required=False
)

log("\nResolved master descriptive columns:")
log(f"Port name: {master_name_col_merged}")
log(f"City name: {master_city_col_merged}")
log(f"Country code: {master_country_col_merged}")

if master_name_col_merged is None:
    raise KeyError("Master port name column missing after merge.")

if master_country_col_merged is None:
    raise KeyError("Master country code column missing after merge.")


# IMPORTANT:
# Identify coordinate columns AFTER merging because overlapping
# column names receive _18D and _18C suffixes.

coordinate_columns = identify_coordinate_columns(merged)

log("\nCoordinate fields available after merge:")

for release, columns in coordinate_columns.items():
    log(f"{release}: {columns}")

log(f"\nMerged shortlist shape: {merged.shape}")

unmatched = merged["_merge"].ne("both").sum()

log(f"Shortlist rows without master match: {unmatched}")


# =============================================================================
# 6. BUILD INDEPENDENT VALIDATION REGISTER
# =============================================================================

records = []

for idx, row in merged.iterrows():

    locode = row["_JOIN_LOCODE"]

    # Resolve descriptive fields from the merged record.
    port_name = safe_value(row, master_name_col_merged)
    city_name = safe_value(row, master_city_col_merged)
    country_code = safe_value(row, master_country_col_merged)
    geographic_zone = (
        safe_value(row, zone_col)
        if zone_col
        else np.nan
    )

    screening_status = (
        safe_value(row, screening_col)
        if screening_col
        else np.nan
    )

    distance = (
        safe_value(row, distance_col)
        if distance_col
        else np.nan
    )

    # Preserve original 18D accepted coordinates.
    accepted_lat_col = find_column(
        merged,
        ["18D_Accepted_Latitude", "Accepted_Latitude"],
        required=False
    )

    accepted_lon_col = find_column(
        merged,
        ["18D_Accepted_Longitude", "Accepted_Longitude"],
        required=False
    )

    accepted_lat = (
        safe_value(row, accepted_lat_col)
        if accepted_lat_col
        else np.nan
    )

    accepted_lon = (
        safe_value(row, accepted_lon_col)
        if accepted_lon_col
        else np.nan
    )

    # Extract production and pre-release alternatives.
    production_lat = get_numeric_coordinate(
        row, coordinate_columns["production"], "latitude"
    )
    production_lon = get_numeric_coordinate(
        row, coordinate_columns["production"], "longitude"
    )

    prerelease_lat = get_numeric_coordinate(
        row, coordinate_columns["prerelease"], "latitude"
    )
    prerelease_lon = get_numeric_coordinate(
        row, coordinate_columns["prerelease"], "longitude"
    )

    production_status = coordinate_status(
        production_lat, production_lon
    )

    prerelease_status = coordinate_status(
        prerelease_lat, prerelease_lon
    )

    # Compare alternatives without selecting an authoritative source.
    if (
        production_status == "NUMERICALLY_VALID"
        and prerelease_status == "NUMERICALLY_VALID"
    ):
        if (
            np.isclose(production_lat, prerelease_lat, atol=1e-6)
            and np.isclose(production_lon, prerelease_lon, atol=1e-6)
        ):
            coordinate_comparison = "IDENTICAL"
        else:
            coordinate_comparison = "DIFFERENT_COORDINATES"

    elif production_status == "NUMERICALLY_VALID":
        coordinate_comparison = "PRODUCTION_ONLY_VALID"

    elif prerelease_status == "NUMERICALLY_VALID":
        coordinate_comparison = "PRERELEASE_ONLY_VALID"

    else:
        coordinate_comparison = "NO_VALID_PARSED_ALTERNATIVE"

    
    # Facility-level classification is deliberately not inferred as fact.
    name_text = " ".join(
        str(x) for x in [port_name, city_name]
        if pd.notna(x)
    ).lower()

    facility_locode_map = {
        "QAQAP": "INDUSTRIAL_FACILITY_IDENTITY_REVIEW",
        "QAUMS": "INDUSTRIAL_FACILITY_IDENTITY_REVIEW",
        "QAQCH": "INDUSTRIAL_FACILITY_IDENTITY_REVIEW",
    }

    ambiguous_master_locodes = {"DKCPH", "PYVLL", "VNHPH"}

    if locode in ambiguous_master_locodes:
        facility_review = "AMBIGUOUS_LOCODE_FACILITY_REVIEW"
    elif locode in facility_locode_map:
        facility_review = facility_locode_map[locode]
    else:
        facility_review = "PORT_IDENTITY_REVIEW"

    # Priority is based on the existing geographic screening output.
    zone_text = str(geographic_zone).upper()

    if "STRAIT" in zone_text:
        priority = "HIGH"
    elif "PERSIAN_GULF" in zone_text:
        priority = "HIGH"
    elif "ARABIAN_SEA" in zone_text:
        priority = "MEDIUM"
    else:
        priority = "REVIEW"

    if coordinate_comparison != "IDENTICAL":
        coordinate_review = "REQUIRED"
    else:
        coordinate_review = "INDEPENDENT_CONFIRMATION_REQUIRED"

    # Append exactly one validation record for every merged row.
    records.append({
        "18E_Record_ID": f"18E_{len(records)+1:03d}",
        "UN_LOCODE": locode,
        "Port_Name": port_name,
        "City_Name": city_name,
        "Country_Code": country_code,

        "18D_Geographic_Zone": geographic_zone,
        "18D_Screening_Status": screening_status,
        "18D_Distance_To_Reference_KM": distance,

        "18D_Accepted_Latitude": accepted_lat,
        "18D_Accepted_Longitude": accepted_lon,

        "Production_Latitude": production_lat,
        "Production_Longitude": production_lon,
        "Production_Coordinate_Status": production_status,

        "Prerelease_Latitude": prerelease_lat,
        "Prerelease_Longitude": prerelease_lon,
        "Prerelease_Coordinate_Status": prerelease_status,

        "Coordinate_Comparison": coordinate_comparison,
        "Coordinate_Review_Status": coordinate_review,

        "Facility_Review_Category": facility_review,
        "Validation_Priority": priority,

        "Independent_Source_1": "",
        "Independent_Source_1_URL": "",
        "Independent_Source_1_Description": "",

        "Independent_Source_2": "",
        "Independent_Source_2_URL": "",
        "Independent_Source_2_Description": "",

        "Verified_Port_or_Facility_Name": "",
        "Verified_Location_Type": "",
        "Verified_Latitude": np.nan,
        "Verified_Longitude": np.nan,

        "Facility_Identity_Verified": "NOT_REVIEWED",
        "Geographic_Location_Verified": "NOT_REVIEWED",
        "Coordinate_Source_Confidence": "NOT_ASSESSED",

        "Reviewer_Notes": "",
        "Final_Validation_Status": "PENDING_MANUAL_REVIEW"
    })


validation = pd.DataFrame(records)


# =============================================================================
# 7. CREATE COORDINATE ALTERNATIVE REGISTER
# =============================================================================

coordinate_records = []

for _, row in validation.iterrows():

    for release in ["Production", "Prerelease"]:

        coordinate_records.append({
            "18E_Record_ID": row["18E_Record_ID"],
            "UN_LOCODE": row["UN_LOCODE"],
            "Port_Name": row["Port_Name"],
            "Country_Code": row["Country_Code"],
            "Coordinate_Release": release,

            "Latitude": row[f"{release}_Latitude"],
            "Longitude": row[f"{release}_Longitude"],

            "Coordinate_Status": row[
                f"{release}_Coordinate_Status"
            ],

            "Authoritative_Status": "NOT_DETERMINED",
            "Independent_Verification_Status": "PENDING"
        })

coordinate_register = pd.DataFrame(coordinate_records)


# =============================================================================
# 8. DUPLICATE LOCODE / FACILITY REVIEW
# =============================================================================

locode_counts = validation["UN_LOCODE"].value_counts(dropna=False)

validation["Duplicate_LOCODE_In_Shortlist"] = (
    validation["UN_LOCODE"].map(locode_counts).gt(1)
)

# Check repeated port master LOCODEs.
master_locode_counts = master["_JOIN_LOCODE"].value_counts(dropna=False)

validation["Ambiguous_Master_LOCODE"] = (
    validation["UN_LOCODE"].map(master_locode_counts).gt(1)
)

validation.loc[
    validation["Ambiguous_Master_LOCODE"],
    "Facility_Review_Category"
] = "AMBIGUOUS_LOCODE_FACILITY_REVIEW"


# =============================================================================
# 9. VALIDATION PRIORITY SUMMARY
# =============================================================================

priority_summary = (
    validation.groupby(
        ["Validation_Priority", "Coordinate_Comparison"],
        dropna=False
    )
    .size()
    .reset_index(name="Record_Count")
)

priority_summary["Percentage"] = (
    priority_summary["Record_Count"]
    / max(len(validation), 1)
    * 100
).round(2)


# =============================================================================
# 10. VALIDATION CHECKS
# =============================================================================

checks = {
    "Shortlist_records": len(shortlist),
    "Validation_register_records": len(validation),
    "Unique_LOCODES_in_register": validation["UN_LOCODE"].nunique(),
    "Unmatched_master_rows": int(unmatched),

    "Identical_coordinate_records": int(
        (validation["Coordinate_Comparison"] == "IDENTICAL").sum()
    ),

    "Different_coordinate_records": int(
        (
            validation["Coordinate_Comparison"]
            == "DIFFERENT_COORDINATES"
        ).sum()
    ),

    "Production_only_valid_records": int(
        (
            validation["Coordinate_Comparison"]
            == "PRODUCTION_ONLY_VALID"
        ).sum()
    ),

    "Prerelease_only_valid_records": int(
        (
            validation["Coordinate_Comparison"]
            == "PRERELEASE_ONLY_VALID"
        ).sum()
    ),

    "No_valid_coordinate_alternative": int(
        (
            validation["Coordinate_Comparison"]
            == "NO_VALID_PARSED_ALTERNATIVE"
        ).sum()
    ),

    "Ambiguous_master_LOCODE_records": int(
        validation["Ambiguous_Master_LOCODE"].sum()
    ),

    "High_priority_records": int(
        (validation["Validation_Priority"] == "HIGH").sum()
    ),

    "Medium_priority_records": int(
        (validation["Validation_Priority"] == "MEDIUM").sum()
    ),

    "Records_pending_manual_review": int(
        (
            validation["Final_Validation_Status"]
            == "PENDING_MANUAL_REVIEW"
        ).sum()
    )
}


# =============================================================================
# 11. SAVE OUTPUTS
# =============================================================================

validation.to_csv(OUTPUT_PROCESSED, index=False)
validation.to_csv(OUTPUT_REGISTER, index=False)

coordinate_register.to_csv(
    OUTPUT_COORDINATES,
    index=False
)

priority_summary.to_csv(
    OUTPUT_SUMMARY,
    index=False
)


# =============================================================================
# 12. GENERATE REPORT
# =============================================================================

report = []

report.append("=" * 79)
report.append("SCRIPT 18E: INDEPENDENT PORT AND FACILITY VALIDATION")
report.append("=" * 79)

report.append("\nINPUT DATA")
report.append("-" * 79)
report.append(f"18C master records: {len(master)}")
report.append(f"18D shortlist records: {len(shortlist)}")
report.append(f"Merged records: {len(merged)}")

report.append("\nVALIDATION REGISTER")
report.append("-" * 79)

for key, value in checks.items():
    report.append(f"{key}: {value}")

report.append("\nCOORDINATE COMPARISON")
report.append("-" * 79)

report.append(
    validation["Coordinate_Comparison"]
    .value_counts(dropna=False)
    .to_string()
)

report.append("\nVALIDATION PRIORITY")
report.append("-" * 79)

report.append(
    validation["Validation_Priority"]
    .value_counts(dropna=False)
    .to_string()
)

report.append("\nFACILITY REVIEW CATEGORY")
report.append("-" * 79)

report.append(
    validation["Facility_Review_Category"]
    .value_counts(dropna=False)
    .to_string()
)

report.append("\nIMPORTANT METHODOLOGICAL LIMITATIONS")
report.append("-" * 79)

report.append(
    "1. Numeric coordinate validity does not establish geographic accuracy."
)

report.append(
    "2. Production and pre-release coordinates are retained separately."
)

report.append(
    "3. No coordinate release is automatically declared authoritative."
)

report.append(
    "4. Independent source evidence must be manually documented."
)

report.append(
    "5. Facility-level identities require separate verification."
)

report.append(
    "6. Distance from a reference point is not distance to the Strait boundary."
)

report.append(
    "7. Port calls do not establish vessel transit through the Strait of Hormuz."
)

report.append("\nOUTPUT FILES")
report.append("-" * 79)
report.append(str(OUTPUT_PROCESSED))
report.append(str(OUTPUT_REGISTER))
report.append(str(OUTPUT_COORDINATES))
report.append(str(OUTPUT_SUMMARY))
report.append(str(OUTPUT_REPORT))

report_text = "\n".join(report)

OUTPUT_REPORT.write_text(
    report_text,
    encoding="utf-8"
)


# =============================================================================
# 13. DISPLAY RESULTS
# =============================================================================

log("\n" + "=" * 79)
log("SCRIPT 18E COMPLETED SUCCESSFULLY")
log("=" * 79)

log("\nVALIDATION SUMMARY")

for key, value in checks.items():
    log(f"{key}: {value}")

log("\nCOORDINATE COMPARISON")
log(
    validation["Coordinate_Comparison"]
    .value_counts(dropna=False)
    .to_string()
)

log("\nVALIDATION PRIORITY")
log(
    validation["Validation_Priority"]
    .value_counts(dropna=False)
    .to_string()
)

log("\nOUTPUT FILES")

for path in [
    OUTPUT_PROCESSED,
    OUTPUT_REGISTER,
    OUTPUT_COORDINATES,
    OUTPUT_SUMMARY,
    OUTPUT_REPORT
]:
    log(str(path))

log("\nIMPORTANT:")
log(
    "No port, facility, coordinate or vessel transit has been "
    "independently confirmed by this script."
)

log("=" * 79)
