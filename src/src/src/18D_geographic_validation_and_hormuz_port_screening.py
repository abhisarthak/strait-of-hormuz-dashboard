
"""
SCRIPT 18D
Geographic validation and Strait of Hormuz port screening.

INPUT:
    data/processed/18C_coordinate_assessed_port_master.csv

OUTPUTS:
    data/processed/18D_geographically_assessed_port_master.csv
    outputs/tables/18D_hormuz_relevant_port_register.csv
    outputs/tables/18D_coordinate_review_register.csv
    outputs/tables/18D_geographic_classification_summary.csv
    outputs/tables/18D_country_coordinate_screening.csv
    outputs/reports/18D_geographic_validation_report.txt

METHODOLOGICAL NOTES:
1. Production and pre-release coordinates are preserved.
2. Only identical coordinates are automatically accepted for screening.
3. A coordinate available in only one release remains a candidate,
   not an automatically accepted coordinate.
4. Country bounding boxes are broad screening approximations,
   NOT authoritative national boundaries.
5. Geographic zones are approximate rectangular screening areas,
   NOT precise maritime boundaries.
6. Distance is calculated to a reference point, not to the
   official Strait of Hormuz boundary.
7. Port calls do not establish vessel transit through the Strait.
"""

from pathlib import Path
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
    / "18C_coordinate_assessed_port_master.csv"
)

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
TABLES_DIR = PROJECT_ROOT / "outputs" / "tables"
REPORTS_DIR = PROJECT_ROOT / "outputs" / "reports"

for directory in [PROCESSED_DIR, TABLES_DIR, REPORTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------
# Strait reference point
# ------------------------------------------------------------
# Approximate reference point for proximity screening.
# This is NOT an official Strait boundary or a transit line.
#
# Replace only if your research methodology adopts a different
# documented reference point. Record the source in your thesis.

HORMUZ_REFERENCE_LAT = 26.56
HORMUZ_REFERENCE_LON = 56.25

HORMUZ_REFERENCE_DESCRIPTION = (
    "Approximate Strait of Hormuz reference point; "
    "used for proximity screening only"
)


# ============================================================
# 2. APPROXIMATE GEOGRAPHIC SCREENING ZONES
# ============================================================
# Format:
# (minimum_latitude, maximum_latitude,
#  minimum_longitude, maximum_longitude)
#
# These are deliberately broad screening boxes.
# They are not official geographic or maritime boundaries.
#
# Priority matters because zones can overlap.

GEOGRAPHIC_ZONES = {
    "STRAIT_OF_HORMUZ_VICINITY": (
        25.0, 27.8, 55.0, 57.5
    ),

    "PERSIAN_GULF_SCREENING": (
        23.0, 30.8, 47.0, 56.8
    ),

    "GULF_OF_OMAN_SCREENING": (
        22.0, 27.8, 56.0, 62.0
    ),

    "ARABIAN_SEA_SCREENING": (
        5.0, 25.5, 56.0, 75.0
    )
}

ZONE_PRIORITY = [
    "STRAIT_OF_HORMUZ_VICINITY",
    "PERSIAN_GULF_SCREENING",
    "GULF_OF_OMAN_SCREENING",
    "ARABIAN_SEA_SCREENING"
]


# ============================================================
# 3. BROAD COUNTRY COORDINATE SCREENING BOXES
# ============================================================
# These boxes are only sanity checks.
# They are NOT country polygons and must not be described
# as definitive geographic validation.
#
# Format:
# country_code: (min_lat, max_lat, min_lon, max_lon)

COUNTRY_BOUNDS = {
    "AE": (22.5, 26.5, 51.0, 57.0),
    "IR": (24.0, 40.0, 44.0, 64.0),
    "OM": (16.0, 27.5, 52.0, 60.0),
    "QA": (24.0, 27.0, 50.0, 52.0),
    "BH": (25.5, 27.0, 50.0, 51.0),
    "KW": (28.0, 31.0, 46.0, 49.0),
    "IQ": (28.0, 38.0, 38.0, 49.0),
    "SA": (16.0, 33.0, 34.0, 56.0)
}


# ============================================================
# 4. HELPER FUNCTIONS
# ============================================================

def is_valid_coordinate(lat, lon):
    """Check decimal latitude and longitude bounds."""

    if pd.isna(lat) or pd.isna(lon):
        return False

    return (
        -90 <= float(lat) <= 90
        and -180 <= float(lon) <= 180
    )


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points in kilometres."""

    if any(
        pd.isna(value)
        for value in [lat1, lon1, lat2, lon2]
    ):
        return np.nan

    radius = 6371.0088

    lat1, lon1, lat2, lon2 = map(
        math.radians,
        [float(lat1), float(lon1), float(lat2), float(lon2)]
    )

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return radius * c


def inside_box(lat, lon, bounds):
    """Check whether a coordinate falls inside a screening box."""

    if not is_valid_coordinate(lat, lon):
        return False

    min_lat, max_lat, min_lon, max_lon = bounds

    return (
        min_lat <= lat <= max_lat
        and min_lon <= lon <= max_lon
    )


def classify_geographic_zone(lat, lon):
    """
    Assign an approximate geographic screening category.

    This does not establish whether a point is on land,
    inside a port, or inside an official maritime boundary.
    """

    if not is_valid_coordinate(lat, lon):
        return "COORDINATES_UNAVAILABLE"

    for zone_name in ZONE_PRIORITY:
        if inside_box(
            lat,
            lon,
            GEOGRAPHIC_ZONES[zone_name]
        ):
            return zone_name

    return "OUTSIDE_DEFINED_SCREENING_ZONES"


def country_coordinate_check(country_code, lat, lon):
    """
    Compare coordinate with broad bounding box for selected
    Gulf countries.

    Returns:
        NOT_ASSESSED_COUNTRY_NOT_IN_SCREENING_LIST
        COORDINATES_UNAVAILABLE
        WITHIN_BROAD_COUNTRY_BOUNDS
        OUTSIDE_BROAD_COUNTRY_BOUNDS
    """

    if country_code not in COUNTRY_BOUNDS:
        return "NOT_ASSESSED_COUNTRY_NOT_IN_SCREENING_LIST"

    if not is_valid_coordinate(lat, lon):
        return "COORDINATES_UNAVAILABLE"

    if inside_box(lat, lon, COUNTRY_BOUNDS[country_code]):
        return "WITHIN_BROAD_COUNTRY_BOUNDS"

    return "OUTSIDE_BROAD_COUNTRY_BOUNDS"


def safe_bool(value):
    """Normalize common CSV boolean representations."""

    if pd.isna(value):
        return False

    return str(value).strip().lower() in {
        "true", "1", "yes", "y"
    }


def safe_value(row, column):
    """Return a value if the column exists."""

    if column is None or column not in row.index:
        return None

    return row[column]


# ============================================================
# 5. LOAD SCRIPT 18C OUTPUT
# ============================================================

print("\n" + "=" * 75)
print("SCRIPT 18D: GEOGRAPHIC VALIDATION AND HORMUZ PORT SCREENING")
print("=" * 75)

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Input not found:\n{INPUT_FILE}\n"
        "Run Script 18C first."
    )

df = pd.read_csv(
    INPUT_FILE,
    keep_default_na=True
)

print(f"\nInput file: {INPUT_FILE.name}")
print(f"Input shape: {df.shape}")


# ============================================================
# 6. IDENTIFY INPUT COLUMNS
# ============================================================

required_columns = [
    "Master_LOCODE",
    "18C_Production_Latitude",
    "18C_Production_Longitude",
    "18C_Prerelease_Latitude",
    "18C_Prerelease_Longitude",
    "18C_Production_Validation_Status",
    "18C_Prerelease_Validation_Status",
    "18C_Release_Comparison_Status"
]

missing_columns = [
    column for column in required_columns
    if column not in df.columns
]

if missing_columns:
    raise KeyError(
        f"Missing expected Script 18C columns: {missing_columns}\n"
        f"Available columns: {list(df.columns)}"
    )

country_col = (
    "Master_Country_Code"
    if "Master_Country_Code" in df.columns
    else None
)

port_name_col = (
    "Master_Port_Name"
    if "Master_Port_Name" in df.columns
    else None
)

city_col = (
    "Master_City_Name"
    if "Master_City_Name" in df.columns
    else None
)

ambiguous_col = (
    "18C_Ambiguous_LOCODE_Flag"
    if "18C_Ambiguous_LOCODE_Flag" in df.columns
    else "Master_LOCODE_Ambiguous"
    if "Master_LOCODE_Ambiguous" in df.columns
    else None
)

facility_review_col = (
    "18C_Facility_Review_Flag"
    if "18C_Facility_Review_Flag" in df.columns
    else None
)


# ============================================================
# 7. DETERMINE COORDINATE USABILITY
# ============================================================

# Only coordinates identical between releases are accepted
# automatically for geographic screening.

df["18D_Coordinate_Agreement_Status"] = (
    df["18C_Release_Comparison_Status"]
)

df["18D_Production_Valid"] = (
    df["18C_Production_Validation_Status"]
    .eq("VALID")
)

df["18D_Prerelease_Valid"] = (
    df["18C_Prerelease_Validation_Status"]
    .eq("VALID")
)

df["18D_Identical_Release_Coordinates"] = (
    df["18C_Release_Comparison_Status"]
    .eq("IDENTICAL_COORDINATES")
)

df["18D_Usable_For_Automatic_Geographic_Screening"] = (
    df["18D_Identical_Release_Coordinates"]
)

# Candidate coordinates are retained for manual review.
df["18D_Candidate_Latitude"] = np.nan
df["18D_Candidate_Longitude"] = np.nan

# Only identical coordinates are populated in the accepted fields.
df["18D_Accepted_Latitude"] = np.where(
    df["18D_Usable_For_Automatic_Geographic_Screening"],
    df["18C_Production_Latitude"],
    np.nan
)

df["18D_Accepted_Longitude"] = np.where(
    df["18D_Usable_For_Automatic_Geographic_Screening"],
    df["18C_Production_Longitude"],
    np.nan
)

# For investigation only, retain a candidate from a single valid source.
# These are NOT accepted coordinates.
production_only = (
    df["18D_Production_Valid"]
    & ~df["18D_Prerelease_Valid"]
)

prerelease_only = (
    df["18D_Prerelease_Valid"]
    & ~df["18D_Production_Valid"]
)

df.loc[
    production_only,
    "18D_Candidate_Latitude"
] = df.loc[
    production_only,
    "18C_Production_Latitude"
]

df.loc[
    production_only,
    "18D_Candidate_Longitude"
] = df.loc[
    production_only,
    "18C_Production_Longitude"
]

df.loc[
    prerelease_only,
    "18D_Candidate_Latitude"
] = df.loc[
    prerelease_only,
    "18C_Prerelease_Latitude"
]

df.loc[
    prerelease_only,
    "18D_Candidate_Longitude"
] = df.loc[
    prerelease_only,
    "18C_Prerelease_Longitude"
]

df["18D_Candidate_Coordinate_Source"] = np.select(
    [
        production_only.to_numpy(dtype=bool),
        prerelease_only.to_numpy(dtype=bool),
        df["18D_Identical_Release_Coordinates"].to_numpy(dtype=bool)
    ],
    [
        "PRODUCTION_ONLY_CANDIDATE",
        "PRERELEASE_ONLY_CANDIDATE",
        "BOTH_RELEASES_IDENTICAL"
    ],
    default="NO_UNAMBIGUOUS_COORDINATE_CANDIDATE"
)


# ============================================================
# 8. COUNTRY COORDINATE SCREENING
# ============================================================

if country_col:
    country_values = (
        df[country_col]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )
else:
    country_values = pd.Series("", index=df.index)

df["18D_Country_Bounds_Status"] = [
    country_coordinate_check(
        country_values.iloc[i],
        df.iloc[i]["18D_Accepted_Latitude"],
        df.iloc[i]["18D_Accepted_Longitude"]
    )
    for i in range(len(df))
]

# This flag is only based on the approximate screening boxes.
df["18D_Country_Bounds_Review_Flag"] = (
    df["18D_Country_Bounds_Status"]
    .eq("OUTSIDE_BROAD_COUNTRY_BOUNDS")
)


# ============================================================
# 9. GEOGRAPHIC ZONE CLASSIFICATION
# ============================================================

df["18D_Geographic_Zone"] = [
    classify_geographic_zone(lat, lon)
    for lat, lon in zip(
        df["18D_Accepted_Latitude"],
        df["18D_Accepted_Longitude"]
    )
]

# Also classify candidate-only coordinates for review.
df["18D_Candidate_Geographic_Zone"] = [
    classify_geographic_zone(lat, lon)
    for lat, lon in zip(
        df["18D_Candidate_Latitude"],
        df["18D_Candidate_Longitude"]
    )
]


# ============================================================
# 10. DISTANCE TO STRAIT REFERENCE POINT
# ============================================================

df["18D_Distance_To_Hormuz_Reference_KM"] = [
    haversine_km(
        lat,
        lon,
        HORMUZ_REFERENCE_LAT,
        HORMUZ_REFERENCE_LON
    )
    for lat, lon in zip(
        df["18D_Accepted_Latitude"],
        df["18D_Accepted_Longitude"]
    )
]

df["18D_Candidate_Distance_To_Hormuz_Reference_KM"] = [
    haversine_km(
        lat,
        lon,
        HORMUZ_REFERENCE_LAT,
        HORMUZ_REFERENCE_LON
    )
    for lat, lon in zip(
        df["18D_Candidate_Latitude"],
        df["18D_Candidate_Longitude"]
    )
]


# ============================================================
# 11. DISTANCE BANDS
# ============================================================

def distance_band(distance):
    if pd.isna(distance):
        return "DISTANCE_UNAVAILABLE"

    if distance <= 50:
        return "WITHIN_50_KM"

    if distance <= 100:
        return "50_TO_100_KM"

    if distance <= 250:
        return "100_TO_250_KM"

    if distance <= 500:
        return "250_TO_500_KM"

    if distance <= 1000:
        return "500_TO_1000_KM"

    return "OVER_1000_KM"


df["18D_Hormuz_Reference_Distance_Band"] = (
    df["18D_Distance_To_Hormuz_Reference_KM"]
    .apply(distance_band)
)

df["18D_Candidate_Distance_Band"] = (
    df["18D_Candidate_Distance_To_Hormuz_Reference_KM"]
    .apply(distance_band)
)


# ============================================================
# 12. HORMUZ RELEVANCE SCREENING
# ============================================================

relevant_zones = {
    "STRAIT_OF_HORMUZ_VICINITY",
    "PERSIAN_GULF_SCREENING",
    "GULF_OF_OMAN_SCREENING",
    "ARABIAN_SEA_SCREENING"
}

df["18D_Hormuz_Geographic_Relevance"] = np.where(
    df["18D_Geographic_Zone"].isin(relevant_zones),
    "WITHIN_HORMUZ_STUDY_SCREENING_REGION",
    np.where(
        df["18D_Geographic_Zone"].eq("COORDINATES_UNAVAILABLE"),
        "REQUIRES_COORDINATE_REVIEW",
        "OUTSIDE_DEFINED_SCREENING_REGION"
    )
)

df["18D_Candidate_Hormuz_Relevance"] = np.where(
    df["18D_Candidate_Geographic_Zone"].isin(relevant_zones),
    "CANDIDATE_WITHIN_HORMUZ_STUDY_REGION",
    np.where(
        df["18D_Candidate_Geographic_Zone"].eq(
            "COORDINATES_UNAVAILABLE"
        ),
        "NO_CANDIDATE_COORDINATE",
        "CANDIDATE_OUTSIDE_HORMUZ_STUDY_REGION"
    )
)


# ============================================================
# 13. FACILITY AND MANUAL REVIEW FLAGS
# ============================================================

if ambiguous_col:
    df["18D_Ambiguous_LOCODE_Flag"] = (
        df[ambiguous_col].apply(safe_bool)
    )
else:
    df["18D_Ambiguous_LOCODE_Flag"] = False

if facility_review_col:
    df["18D_Facility_Review_Flag"] = (
        df[facility_review_col].apply(safe_bool)
    )
else:
    df["18D_Facility_Review_Flag"] = (
        df["18D_Ambiguous_LOCODE_Flag"]
    )

df["18D_Coordinate_Review_Flag"] = (
    ~df["18D_Usable_For_Automatic_Geographic_Screening"]
)

df["18D_Manual_Review_Required"] = (
    df["18D_Coordinate_Review_Flag"]
    | df["18D_Country_Bounds_Review_Flag"]
    | df["18D_Facility_Review_Flag"]
)


# ============================================================
# 14. FINAL PORT SCREENING STATUS
# ============================================================

def final_screening_status(row):

    if row["18D_Facility_Review_Flag"]:
        return "FACILITY_LEVEL_VALIDATION_REQUIRED"

    if row["18D_Country_Bounds_Review_Flag"]:
        return "COUNTRY_COORDINATE_REVIEW_REQUIRED"

    if not row[
        "18D_Usable_For_Automatic_Geographic_Screening"
    ]:
        if (
            row["18D_Candidate_Hormuz_Relevance"]
            == "CANDIDATE_WITHIN_HORMUZ_STUDY_REGION"
        ):
            return "HORMUZ_RELEVANT_CANDIDATE_COORDINATE_REVIEW"

        return "COORDINATE_VALIDATION_REQUIRED"

    if (
        row["18D_Geographic_Zone"]
        == "STRAIT_OF_HORMUZ_VICINITY"
    ):
        return "STRAIT_VICINITY_SCREENED_PORT"

    if (
        row["18D_Geographic_Zone"]
        == "PERSIAN_GULF_SCREENING"
    ):
        return "PERSIAN_GULF_SCREENED_PORT"

    if (
        row["18D_Geographic_Zone"]
        == "GULF_OF_OMAN_SCREENING"
    ):
        return "GULF_OF_OMAN_SCREENED_PORT"

    if (
        row["18D_Geographic_Zone"]
        == "ARABIAN_SEA_SCREENING"
    ):
        return "ARABIAN_SEA_SCREENED_PORT"

    return "OUTSIDE_HORMUZ_STUDY_SCREENING_REGION"


df["18D_Final_Port_Screening_Status"] = df.apply(
    final_screening_status,
    axis=1
)


# ============================================================
# 15. HORMUZ RELEVANT PORT REGISTER
# ============================================================

# Include accepted ports in the defined study screening region
# and candidate ports that appear relevant but require review.

accepted_relevant = df[
    df["18D_Hormuz_Geographic_Relevance"]
    .eq("WITHIN_HORMUZ_STUDY_SCREENING_REGION")
]

candidate_relevant = df[
    df["18D_Candidate_Hormuz_Relevance"]
    .eq("CANDIDATE_WITHIN_HORMUZ_STUDY_REGION")
]

hormuz_register = pd.concat(
    [accepted_relevant, candidate_relevant],
    ignore_index=True
)

# Remove duplicate master records if any.
if "Master_Record_ID" in hormuz_register.columns:
    hormuz_register = hormuz_register.drop_duplicates(
        subset=["Master_Record_ID"]
    )
else:
    hormuz_register = hormuz_register.drop_duplicates(
        subset=["Master_LOCODE", "Master_Port_Name"]
        if "Master_Port_Name" in hormuz_register.columns
        else ["Master_LOCODE"]
    )


# ============================================================
# 16. MANUAL REVIEW REGISTER
# ============================================================

review_register = df[
    df["18D_Manual_Review_Required"]
    | df["18D_Candidate_Hormuz_Relevance"].eq(
        "CANDIDATE_WITHIN_HORMUZ_STUDY_REGION"
    )
].copy()


# ============================================================
# 17. COUNTRY SCREENING TABLE
# ============================================================

country_summary = (
    df.groupby(
        ["Master_Country_Code", "18D_Country_Bounds_Status"],
        dropna=False
    )
    .size()
    .reset_index(name="Record_Count")
    if country_col
    else pd.DataFrame()
)


# ============================================================
# 18. GEOGRAPHIC CLASSIFICATION SUMMARY
# ============================================================

zone_summary = (
    df["18D_Geographic_Zone"]
    .value_counts(dropna=False)
    .rename_axis("Geographic_Zone")
    .reset_index(name="Record_Count")
)

zone_summary["Percentage"] = (
    zone_summary["Record_Count"] / len(df) * 100
).round(2)


screening_summary = (
    df["18D_Final_Port_Screening_Status"]
    .value_counts(dropna=False)
    .rename_axis("Screening_Status")
    .reset_index(name="Record_Count")
)

screening_summary["Percentage"] = (
    screening_summary["Record_Count"] / len(df) * 100
).round(2)


# ============================================================
# 19. SUMMARY METRICS
# ============================================================

summary_metrics = [
    ("Total port master records", len(df)),
    ("Unique LOCODEs", df["Master_LOCODE"].nunique()),
    (
        "Records with identical release coordinates",
        int(df["18D_Identical_Release_Coordinates"].sum())
    ),
    (
        "Records with production-only candidate coordinates",
        int(production_only.sum())
    ),
    (
        "Records with pre-release-only candidate coordinates",
        int(prerelease_only.sum())
    ),
    (
        "Accepted coordinates for geographic screening",
        int(
            df["18D_Usable_For_Automatic_Geographic_Screening"].sum()
        )
    ),
    (
        "Accepted coordinates within Hormuz screening region",
        int(
            df["18D_Hormuz_Geographic_Relevance"]
            .eq("WITHIN_HORMUZ_STUDY_SCREENING_REGION")
            .sum()
        )
    ),
    (
        "Candidate coordinates within Hormuz screening region",
        int(
            df["18D_Candidate_Hormuz_Relevance"]
            .eq("CANDIDATE_WITHIN_HORMUZ_STUDY_REGION")
            .sum()
        )
    ),
    (
        "Ambiguous LOCODE records",
        int(df["18D_Ambiguous_LOCODE_Flag"].sum())
    ),
    (
        "Country-boundary screening flags",
        int(df["18D_Country_Bounds_Review_Flag"].sum())
    ),
    (
        "Manual review records",
        int(df["18D_Manual_Review_Required"].sum())
    ),
    (
        "Ports within 250 km of reference point",
        int(
            df["18D_Distance_To_Hormuz_Reference_KM"]
            .le(250)
            .sum()
        )
    )
]

summary_metrics_df = pd.DataFrame(
    summary_metrics,
    columns=["Metric", "Value"]
)


# ============================================================
# 20. SAVE OUTPUTS
# ============================================================

full_output = (
    PROCESSED_DIR
    / "18D_geographically_assessed_port_master.csv"
)

hormuz_output = (
    TABLES_DIR
    / "18D_hormuz_relevant_port_register.csv"
)

review_output = (
    TABLES_DIR
    / "18D_coordinate_review_register.csv"
)

zone_output = (
    TABLES_DIR
    / "18D_geographic_classification_summary.csv"
)

country_output = (
    TABLES_DIR
    / "18D_country_coordinate_screening.csv"
)

report_output = (
    REPORTS_DIR
    / "18D_geographic_validation_report.txt"
)

df.to_csv(full_output, index=False)

hormuz_register.to_csv(
    hormuz_output,
    index=False
)

review_register.to_csv(
    review_output,
    index=False
)

zone_summary.to_csv(
    zone_output,
    index=False
)

country_summary.to_csv(
    country_output,
    index=False
)


# ============================================================
# 21. GENERATE REPORT
# ============================================================

with open(report_output, "w", encoding="utf-8") as f:

    f.write("=" * 80 + "\n")
    f.write("SCRIPT 18D: GEOGRAPHIC VALIDATION REPORT\n")
    f.write("=" * 80 + "\n\n")

    f.write(f"Input: {INPUT_FILE.name}\n")
    f.write(f"Total port master records: {len(df)}\n")
    f.write(
        f"Unique LOCODEs: {df['Master_LOCODE'].nunique()}\n\n"
    )

    f.write("1. COORDINATE USABILITY\n")
    f.write("-" * 80 + "\n")
    f.write(summary_metrics_df.to_string(index=False))
    f.write("\n\n")

    f.write("2. GEOGRAPHIC ZONE CLASSIFICATION\n")
    f.write("-" * 80 + "\n")
    f.write(zone_summary.to_string(index=False))
    f.write("\n\n")

    f.write("3. FINAL PORT SCREENING STATUS\n")
    f.write("-" * 80 + "\n")
    f.write(screening_summary.to_string(index=False))
    f.write("\n\n")

    f.write("4. HORMUZ RELEVANT PORT REGISTER\n")
    f.write("-" * 80 + "\n")
    f.write(
        f"Records in register: {len(hormuz_register)}\n"
    )
    f.write(
        "This register includes accepted coordinates and "
        "candidate coordinates requiring review.\n\n"
    )

    f.write("5. METHODOLOGICAL LIMITATIONS\n")
    f.write("-" * 80 + "\n")
    f.write(
        "1. Country coordinate checks use broad bounding boxes, "
        "not official national boundaries.\n"
        "2. Geographic zones use approximate rectangular screening "
        "areas, not authoritative maritime boundaries.\n"
        "3. Identical coordinates across releases are not "
        "independently verified geographic truth.\n"
        "4. Coordinates may represent a locality or port centroid, "
        "not an exact terminal or berth.\n"
        "5. The Strait reference point is a proximity proxy, "
        "not an official Strait boundary.\n"
        "6. Distance to the reference point is not sailing distance "
        "or distance to the Strait boundary.\n"
        "7. Port calls do not establish vessel transit through "
        "the Strait of Hormuz.\n"
        "8. AIS trajectories or other reliable movement evidence "
        "are required to confirm transit.\n"
    )

    f.write("\n6. REFERENCE POINT\n")
    f.write("-" * 80 + "\n")
    f.write(
        f"Latitude: {HORMUZ_REFERENCE_LAT}\n"
        f"Longitude: {HORMUZ_REFERENCE_LON}\n"
        f"Description: {HORMUZ_REFERENCE_DESCRIPTION}\n"
    )

    f.write("\n7. OUTPUT FILES\n")
    f.write("-" * 80 + "\n")
    f.write(f"{full_output}\n")
    f.write(f"{hormuz_output}\n")
    f.write(f"{review_output}\n")
    f.write(f"{zone_output}\n")
    f.write(f"{country_output}\n")
    f.write(f"{report_output}\n")


# ============================================================
# 22. TERMINAL OUTPUT
# ============================================================

print("\n" + "=" * 75)
print("SCRIPT 18D COMPLETED SUCCESSFULLY")
print("=" * 75)

print("\nSUMMARY METRICS:")
print(summary_metrics_df.to_string(index=False))

print("\nGEOGRAPHIC ZONE CLASSIFICATION:")
print(zone_summary.to_string(index=False))

print("\nFINAL PORT SCREENING:")
print(screening_summary.to_string(index=False))

print("\nHORMUZ RELEVANT PORT REGISTER:")
print(f"Records: {len(hormuz_register)}")

print("\nMANUAL REVIEW REGISTER:")
print(f"Records: {len(review_register)}")

print("\nOUTPUT FILES:")
print(f"1. {full_output}")
print(f"2. {hormuz_output}")
print(f"3. {review_output}")
print(f"4. {zone_output}")
print(f"5. {country_output}")
print(f"6. {report_output}")

print("\nIMPORTANT:")
print(
    "Geographic zones and country boxes are screening approximations. "
    "No vessel transit has been inferred."
)

print("=" * 75)
