
"""
SCRIPT 18C
Coordinate validation and production-vs-pre-release assessment.

Input:
    data/processed/18B_port_master_coordinate_matching.csv

Outputs:
    data/processed/18C_coordinate_assessed_port_master.csv
    outputs/tables/18C_coordinate_release_comparison.csv
    outputs/tables/18C_coordinate_manual_review.csv
    outputs/tables/18C_coordinate_quality_summary.csv
    outputs/reports/18C_coordinate_validation_report.txt

Important:
- Preserves production and pre-release coordinates separately.
- Does not automatically select an authoritative coordinate.
- Validates coordinate syntax, minutes and latitude/longitude bounds.
- Calculates distance between valid coordinates from both releases.
- Flags possible hemisphere conflicts and possible latitude/longitude swaps.
- Does not claim geographic plausibility without an independent geographic reference.
"""

from pathlib import Path
import re
import math
import pandas as pd
import numpy as np


# ============================================================
# 1. PATHS AND SETTINGS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "18B_port_master_coordinate_matching.csv"
)

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
TABLES_DIR = PROJECT_ROOT / "outputs" / "tables"
REPORTS_DIR = PROJECT_ROOT / "outputs" / "reports"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
TABLES_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Coordinate difference thresholds
IDENTICAL_THRESHOLD_KM = 0.1
MINOR_DIFFERENCE_THRESHOLD_KM = 5.0

# A swapped coordinate comparison within this distance is flagged
# for manual review. It is NOT automatically corrected.
SWAP_REVIEW_THRESHOLD_KM = 50.0


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def find_column(df, candidates, required=True):
    """Find the first available column from a list of alternatives."""
    for col in candidates:
        if col in df.columns:
            return col

    if required:
        raise KeyError(
            f"Could not find any expected column. "
            f"Tried: {candidates}\n"
            f"Available columns:\n{list(df.columns)}"
        )

    return None


def clean_text(value):
    """Normalize empty and missing values."""
    if pd.isna(value):
        return None

    value = str(value).strip()

    if value.lower() in {"", "nan", "none", "null", "<na>"}:
        return None

    return value


def parse_coordinate_component(value, axis):
    """
    Parse one UN/LOCODE coordinate component.

    Latitude examples:
        4230N
        2336S

    Longitude examples:
        00131E
        05832E

    Returns:
        decimal_degrees, validation_status
    """

    value = clean_text(value)

    if value is None:
        return np.nan, "MISSING"

    value = value.upper().replace(" ", "")

    if axis == "LAT":
        pattern = r"^(\d{2})(\d{2})([NS])$"
        max_degrees = 90

    elif axis == "LON":
        pattern = r"^(\d{3})(\d{2})([EW])$"
        max_degrees = 180

    else:
        raise ValueError("axis must be LAT or LON")

    match = re.match(pattern, value)

    if not match:
        return np.nan, "INVALID_FORMAT"

    degrees = int(match.group(1))
    minutes = int(match.group(2))
    hemisphere = match.group(3)

    if minutes >= 60:
        return np.nan, "INVALID_MINUTES"

    if degrees > max_degrees:
        return np.nan, "DEGREES_OUT_OF_RANGE"

    # At exactly 90° latitude or 180° longitude,
    # minutes must be zero.
    if degrees == max_degrees and minutes != 0:
        return np.nan, "DEGREES_OUT_OF_RANGE"

    decimal_value = degrees + minutes / 60.0

    if hemisphere in {"S", "W"}:
        decimal_value *= -1

    return decimal_value, "VALID"


def parse_unlocode_coordinate(raw_coordinate):
    """
    Parse a complete UN/LOCODE coordinate string.

    Expected example:
        4230N 00131E

    Returns:
        latitude, longitude, status
    """

    raw_coordinate = clean_text(raw_coordinate)

    if raw_coordinate is None:
        return np.nan, np.nan, "MISSING"

    # Normalize whitespace but preserve the original source elsewhere.
    parts = raw_coordinate.upper().strip().split()

    if len(parts) != 2:
        return np.nan, np.nan, "INVALID_FORMAT"

    latitude, lat_status = parse_coordinate_component(
        parts[0], "LAT"
    )

    longitude, lon_status = parse_coordinate_component(
        parts[1], "LON"
    )

    if lat_status == "MISSING" or lon_status == "MISSING":
        return np.nan, np.nan, "MISSING"

    if lat_status != "VALID":
        return np.nan, np.nan, f"INVALID_LATITUDE_{lat_status}"

    if lon_status != "VALID":
        return np.nan, np.nan, f"INVALID_LONGITUDE_{lon_status}"

    return latitude, longitude, "VALID"


def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance between two coordinates."""

    values = [lat1, lon1, lat2, lon2]

    if any(pd.isna(v) for v in values):
        return np.nan

    earth_radius_km = 6371.0088

    lat1, lon1, lat2, lon2 = map(
        math.radians, values
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return earth_radius_km * c


def same_hemisphere_conflict(
    prod_lat, prod_lon, pre_lat, pre_lon
):
    """Check whether valid coordinates disagree by hemisphere."""

    if any(
        pd.isna(v)
        for v in [prod_lat, prod_lon, pre_lat, pre_lon]
    ):
        return False

    latitude_conflict = (
        prod_lat != 0
        and pre_lat != 0
        and np.sign(prod_lat) != np.sign(pre_lat)
    )

    longitude_conflict = (
        prod_lon != 0
        and pre_lon != 0
        and np.sign(prod_lon) != np.sign(pre_lon)
    )

    return bool(latitude_conflict or longitude_conflict)


def possible_lat_lon_swap(
    prod_lat, prod_lon, pre_lat, pre_lon
):
    """
    Check whether swapping latitude and longitude in one release
    produces a much closer comparison.

    This is only a review flag, not a coordinate correction.
    """

    if any(
        pd.isna(v)
        for v in [prod_lat, prod_lon, pre_lat, pre_lon]
    ):
        return False, np.nan

    # Swapped production coordinate is only valid if its
    # resulting latitude and longitude remain in valid ranges.
    swapped_lat = prod_lon
    swapped_lon = prod_lat

    if abs(swapped_lat) > 90 or abs(swapped_lon) > 180:
        return False, np.nan

    normal_distance = haversine_km(
        prod_lat, prod_lon, pre_lat, pre_lon
    )

    swapped_distance = haversine_km(
        swapped_lat, swapped_lon, pre_lat, pre_lon
    )

    is_possible_swap = (
        swapped_distance <= SWAP_REVIEW_THRESHOLD_KM
        and (
            pd.isna(normal_distance)
            or swapped_distance < normal_distance
        )
    )

    return bool(is_possible_swap), swapped_distance


def classify_release_comparison(
    prod_status,
    pre_status,
    distance_km,
    hemisphere_conflict,
    possible_swap
):
    """Assign a transparent release-comparison category."""

    if prod_status == "MISSING" and pre_status == "MISSING":
        return "MISSING_IN_BOTH_RELEASES"

    if prod_status != "VALID" and pre_status == "VALID":
        return "INVALID_PRODUCTION_COORDINATES"

    if prod_status == "VALID" and pre_status != "VALID":
        return "INVALID_PRERELEASE_COORDINATES"

    if prod_status != "VALID" and pre_status != "VALID":
        return "INVALID_IN_BOTH_RELEASES"

    if hemisphere_conflict:
        return "HEMISPHERE_CONFLICT"

    if possible_swap:
        return "POSSIBLE_LAT_LON_SWAP"

    if pd.isna(distance_km):
        return "DISTANCE_NOT_CALCULATED"

    if distance_km <= IDENTICAL_THRESHOLD_KM:
        return "IDENTICAL_COORDINATES"

    if distance_km <= MINOR_DIFFERENCE_THRESHOLD_KM:
        return "MINOR_COORDINATE_DIFFERENCE"

    return "MATERIAL_COORDINATE_DIFFERENCE"


# ============================================================
# 3. LOAD INPUT
# ============================================================

print("\n" + "=" * 70)
print("SCRIPT 18C: COORDINATE VALIDATION AND RELEASE ASSESSMENT")
print("=" * 70)

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"\nInput file not found:\n{INPUT_FILE}\n"
        "Run Script 18B successfully before running Script 18C."
    )

df = pd.read_csv(
    INPUT_FILE,
    dtype=str,
    keep_default_na=True
)

print(f"\nInput file: {INPUT_FILE.name}")
print(f"Input shape: {df.shape}")


# ============================================================
# 4. IDENTIFY REQUIRED COLUMNS
# ============================================================

locode_col = find_column(
    df,
    ["Master_LOCODE", "Master_UNLocationCode", "UNLocationCode"]
)

port_name_col = find_column(
    df,
    ["Master_Port_Name", "portName", "Port_Name"],
    required=False
)

city_col = find_column(
    df,
    ["Master_City_Name", "cityName", "City_Name"],
    required=False
)

country_col = find_column(
    df,
    ["Master_Country_Code", "countryCode", "Country_Code"],
    required=False
)

ambiguous_col = find_column(
    df,
    ["Master_LOCODE_Ambiguous", "LOCode_Ambiguous"],
    required=False
)

production_raw_col = find_column(
    df,
    [
        "Production_Coordinate_Raw",
        "Production_Raw_Coordinate",
        "Production_Coordinates",
        "Production_Coordinate"
    ]
)

prerelease_raw_col = find_column(
    df,
    [
        "Prerelease_Coordinate_Raw",
        "Prerelease_Raw_Coordinate",
        "Prerelease_Coordinates",
        "Prerelease_Coordinate"
    ]
)

print("\nIdentified columns:")
print(f"  LOCODE: {locode_col}")
print(f"  Production coordinate: {production_raw_col}")
print(f"  Pre-release coordinate: {prerelease_raw_col}")


# ============================================================
# 5. PARSE BOTH RELEASE COORDINATES
# ============================================================

production_parsed = df[production_raw_col].apply(
    parse_unlocode_coordinate
)

prerelease_parsed = df[prerelease_raw_col].apply(
    parse_unlocode_coordinate
)

df["18C_Production_Latitude"] = production_parsed.apply(
    lambda x: x[0]
)

df["18C_Production_Longitude"] = production_parsed.apply(
    lambda x: x[1]
)

df["18C_Production_Validation_Status"] = production_parsed.apply(
    lambda x: x[2]
)

df["18C_Prerelease_Latitude"] = prerelease_parsed.apply(
    lambda x: x[0]
)

df["18C_Prerelease_Longitude"] = prerelease_parsed.apply(
    lambda x: x[1]
)

df["18C_Prerelease_Validation_Status"] = prerelease_parsed.apply(
    lambda x: x[2]
)


# ============================================================
# 6. CALCULATE COORDINATE DIFFERENCES
# ============================================================

df["18C_Release_Distance_KM"] = df.apply(
    lambda row: haversine_km(
        row["18C_Production_Latitude"],
        row["18C_Production_Longitude"],
        row["18C_Prerelease_Latitude"],
        row["18C_Prerelease_Longitude"]
    ),
    axis=1
)

df["18C_Hemisphere_Conflict"] = df.apply(
    lambda row: same_hemisphere_conflict(
        row["18C_Production_Latitude"],
        row["18C_Production_Longitude"],
        row["18C_Prerelease_Latitude"],
        row["18C_Prerelease_Longitude"]
    ),
    axis=1
)

swap_results = df.apply(
    lambda row: possible_lat_lon_swap(
        row["18C_Production_Latitude"],
        row["18C_Production_Longitude"],
        row["18C_Prerelease_Latitude"],
        row["18C_Prerelease_Longitude"]
    ),
    axis=1
)

df["18C_Possible_Lat_Lon_Swap"] = swap_results.apply(
    lambda x: x[0]
)

df["18C_Swapped_Comparison_Distance_KM"] = swap_results.apply(
    lambda x: x[1]
)


# ============================================================
# 7. CLASSIFY RELEASE COMPARISON
# ============================================================

df["18C_Release_Comparison_Status"] = df.apply(
    lambda row: classify_release_comparison(
        row["18C_Production_Validation_Status"],
        row["18C_Prerelease_Validation_Status"],
        row["18C_Release_Distance_KM"],
        row["18C_Hemisphere_Conflict"],
        row["18C_Possible_Lat_Lon_Swap"]
    ),
    axis=1
)


# ============================================================
# 8. AMBIGUOUS LOCODE AND MANUAL REVIEW FLAGS
# ============================================================

if ambiguous_col is not None:
    ambiguous_values = (
        df[ambiguous_col]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df["18C_Ambiguous_LOCODE_Flag"] = ambiguous_values.isin(
        ["true", "1", "yes", "y"]
    )
else:
    df["18C_Ambiguous_LOCODE_Flag"] = False


# Facility-level matching is not resolved by a LOCODE centroid.
df["18C_Facility_Review_Flag"] = (
    df["18C_Ambiguous_LOCODE_Flag"]
)

# Geographic plausibility is deliberately left unverified here.
df["18C_Geographic_Plausibility_Status"] = (
    "NOT_ASSESSED_REQUIRES_INDEPENDENT_GEOGRAPHIC_REFERENCE"
)

review_categories = {
    "MISSING_IN_BOTH_RELEASES",
    "INVALID_PRODUCTION_COORDINATES",
    "INVALID_PRERELEASE_COORDINATES",
    "INVALID_IN_BOTH_RELEASES",
    "HEMISPHERE_CONFLICT",
    "POSSIBLE_LAT_LON_SWAP",
    "MATERIAL_COORDINATE_DIFFERENCE",
    "DISTANCE_NOT_CALCULATED"
}

df["18C_Manual_Review_Required"] = (
    df["18C_Release_Comparison_Status"].isin(review_categories)
    | df["18C_Facility_Review_Flag"]
)


# ============================================================
# 9. COORDINATE SOURCE DECISION
# ============================================================

# No automatic source selection is made.
df["18C_Selected_Coordinate_Source"] = (
    "NOT_SELECTED_MANUAL_VALIDATION_REQUIRED"
)

df["18C_Selected_Latitude"] = np.nan
df["18C_Selected_Longitude"] = np.nan

# A coordinate is only eligible for later review if at least
# one release contains a syntactically valid coordinate.
df["18C_At_Least_One_Valid_Release"] = (
    df["18C_Production_Validation_Status"].eq("VALID")
    | df["18C_Prerelease_Validation_Status"].eq("VALID")
)


# ============================================================
# 10. BUILD OUTPUT DATASETS
# ============================================================

# Full assessed port master
assessed_output = (
    PROCESSED_DIR
    / "18C_coordinate_assessed_port_master.csv"
)

df.to_csv(
    assessed_output,
    index=False
)


# Release comparison table
comparison_columns = [
    locode_col,
    production_raw_col,
    prerelease_raw_col,
    "18C_Production_Latitude",
    "18C_Production_Longitude",
    "18C_Production_Validation_Status",
    "18C_Prerelease_Latitude",
    "18C_Prerelease_Longitude",
    "18C_Prerelease_Validation_Status",
    "18C_Release_Distance_KM",
    "18C_Hemisphere_Conflict",
    "18C_Possible_Lat_Lon_Swap",
    "18C_Swapped_Comparison_Distance_KM",
    "18C_Release_Comparison_Status",
    "18C_Geographic_Plausibility_Status",
    "18C_Manual_Review_Required"
]

for optional_col in [
    port_name_col,
    city_col,
    country_col,
    ambiguous_col
]:
    if optional_col and optional_col not in comparison_columns:
        comparison_columns.insert(1, optional_col)

comparison_df = df[comparison_columns].copy()

comparison_output = (
    TABLES_DIR
    / "18C_coordinate_release_comparison.csv"
)

comparison_df.to_csv(
    comparison_output,
    index=False
)


# Manual review table
review_df = df[
    df["18C_Manual_Review_Required"]
].copy()

review_columns = [
    col for col in comparison_columns
    if col in review_df.columns
]

extra_review_columns = [
    "18C_Ambiguous_LOCODE_Flag",
    "18C_Facility_Review_Flag",
    "18C_Selected_Coordinate_Source",
    "18C_Selected_Latitude",
    "18C_Selected_Longitude"
]

review_columns += [
    col for col in extra_review_columns
    if col not in review_columns
]

review_df = review_df[review_columns]

review_output = (
    TABLES_DIR
    / "18C_coordinate_manual_review.csv"
)

review_df.to_csv(
    review_output,
    index=False
)


# ============================================================
# 11. QUALITY SUMMARY
# ============================================================

comparison_counts = (
    df["18C_Release_Comparison_Status"]
    .value_counts(dropna=False)
    .rename_axis("Category")
    .reset_index(name="Record_Count")
)

comparison_counts["Percentage"] = (
    comparison_counts["Record_Count"]
    / len(df)
    * 100
).round(2)

quality_metrics = [
    ("Total port master records", len(df)),
    ("Unique LOCODEs", df[locode_col].nunique()),
    (
        "Ambiguous LOCODE master records",
        int(df["18C_Ambiguous_LOCODE_Flag"].sum())
    ),
    (
        "Production valid coordinates",
        int(
            df["18C_Production_Validation_Status"]
            .eq("VALID").sum()
        )
    ),
    (
        "Pre-release valid coordinates",
        int(
            df["18C_Prerelease_Validation_Status"]
            .eq("VALID").sum()
        )
    ),
    (
        "Production missing coordinates",
        int(
            df["18C_Production_Validation_Status"]
            .eq("MISSING").sum()
        )
    ),
    (
        "Pre-release missing coordinates",
        int(
            df["18C_Prerelease_Validation_Status"]
            .eq("MISSING").sum()
        )
    ),
    (
        "Hemisphere conflicts",
        int(df["18C_Hemisphere_Conflict"].sum())
    ),
    (
        "Possible latitude-longitude swaps",
        int(df["18C_Possible_Lat_Lon_Swap"].sum())
    ),
    (
        "Manual review records",
        int(df["18C_Manual_Review_Required"].sum())
    ),
    (
        "Records with at least one valid release",
        int(df["18C_At_Least_One_Valid_Release"].sum())
    ),
    (
        "Coordinates automatically selected",
        int(df["18C_Selected_Latitude"].notna().sum())
    )
]

quality_summary = pd.DataFrame(
    quality_metrics,
    columns=["Metric", "Value"]
)

quality_output = (
    TABLES_DIR
    / "18C_coordinate_quality_summary.csv"
)

quality_summary.to_csv(
    quality_output,
    index=False
)


# ============================================================
# 12. REPORT
# ============================================================

report_output = (
    REPORTS_DIR
    / "18C_coordinate_validation_report.txt"
)

with open(report_output, "w", encoding="utf-8") as f:

    f.write("=" * 75 + "\n")
    f.write("SCRIPT 18C: COORDINATE VALIDATION REPORT\n")
    f.write("=" * 75 + "\n\n")

    f.write(f"Input file: {INPUT_FILE.name}\n")
    f.write(f"Total records: {len(df)}\n")
    f.write(f"Unique LOCODEs: {df[locode_col].nunique()}\n\n")

    f.write("1. COORDINATE VALIDATION\n")
    f.write("-" * 75 + "\n")

    f.write(
        "\nProduction validation:\n"
        + df["18C_Production_Validation_Status"]
        .value_counts(dropna=False)
        .to_string()
        + "\n"
    )

    f.write(
        "\nPre-release validation:\n"
        + df["18C_Prerelease_Validation_Status"]
        .value_counts(dropna=False)
        .to_string()
        + "\n"
    )

    f.write("\n2. RELEASE COMPARISON CLASSIFICATION\n")
    f.write("-" * 75 + "\n")
    f.write(comparison_counts.to_string(index=False))
    f.write("\n\n")

    f.write("3. MANUAL REVIEW\n")
    f.write("-" * 75 + "\n")
    f.write(
        f"Records requiring manual review: "
        f"{len(review_df)}\n"
    )
    f.write(
        f"Ambiguous LOCODE records: "
        f"{int(df['18C_Ambiguous_LOCODE_Flag'].sum())}\n"
    )
    f.write(
        f"Hemisphere conflicts: "
        f"{int(df['18C_Hemisphere_Conflict'].sum())}\n"
    )
    f.write(
        f"Possible coordinate swaps: "
        f"{int(df['18C_Possible_Lat_Lon_Swap'].sum())}\n\n"
    )

    f.write("4. METHODOLOGICAL LIMITATIONS\n")
    f.write("-" * 75 + "\n")
    f.write(
        "1. Syntax validation does not establish geographic correctness.\n"
        "2. No country-boundary or independent geographic reference "
        "was used in this script.\n"
        "3. A UN/LOCODE coordinate may represent a port or locality "
        "reference, not an exact terminal location.\n"
        "4. Ambiguous LOCODE records require facility-level validation.\n"
        "5. Neither release is automatically treated as authoritative.\n"
        "6. No coordinate is automatically selected or corrected.\n"
        "7. No distance to the Strait of Hormuz is calculated in Script 18C.\n"
    )

    f.write("\n5. OUTPUT FILES\n")
    f.write("-" * 75 + "\n")
    f.write(f"{assessed_output}\n")
    f.write(f"{comparison_output}\n")
    f.write(f"{review_output}\n")
    f.write(f"{quality_output}\n")
    f.write(f"{report_output}\n")


# ============================================================
# 13. TERMINAL SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("SCRIPT 18C COMPLETED SUCCESSFULLY")
print("=" * 70)

print("\nRELEASE COMPARISON:")
print(comparison_counts.to_string(index=False))

print("\nKEY QUALITY METRICS:")
print(quality_summary.to_string(index=False))

print("\nOUTPUT FILES:")
print(f"\n1. {assessed_output}")
print(f"2. {comparison_output}")
print(f"3. {review_output}")
print(f"4. {quality_output}")
print(f"5. {report_output}")

print("\nIMPORTANT:")
print(
    "No coordinate source was automatically selected. "
    "Review Script 18C manual-review output before proceeding."
)
print("=" * 70)
