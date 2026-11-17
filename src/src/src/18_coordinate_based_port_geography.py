
from pathlib import Path
import re
import math
import warnings

import numpy as np
import pandas as pd
from matplotlib.path import Path as PolygonPath


# ============================================================
# SCRIPT 18
# COORDINATE-BASED PORT GEOGRAPHY VALIDATION
#
# Objectives:
# 1. Load all active port master records.
# 2. Generate a coordinate enrichment template.
# 3. Validate supplied coordinates.
# 4. Match coordinates to port records conservatively.
# 5. Identify ambiguous and unmatched ports.
# 6. Calculate distance to a Strait of Hormuz reference point.
# 7. Classify ports using approximate geographic polygons.
# 8. Create a unique IMO-level AIS acquisition register.
#
# IMPORTANT:
# - Never invent missing coordinates.
# - Do not assign coordinates by country alone.
# - Ambiguous LOCODEs require facility-level matching.
# - Geographic polygons are screening approximations.
# - Distance to a reference point is not distance to
#   the navigable Strait boundary.
# - Port calls do not prove Strait transit.
# ============================================================


# ------------------------------------------------------------
# 1. PROJECT PATHS
# ------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"

for folder in [RAW, PROCESSED, TABLES, REPORTS]:
    folder.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------
# 2. INPUT FILES
# ------------------------------------------------------------

PORT_MASTER_FILE = RAW / "active_ports.csv"

COORDINATE_FILE = RAW / "port_coordinates.csv"

SCHEDULE_CANDIDATES_FILE = (
    TABLES / "17_gulf_candidate_vessel_summary.csv"
)

INDIVIDUAL_CANDIDATES_FILE = (
    TABLES / "17_gulf_candidate_vessel_summary.csv"
)

SCHEDULE_SEQUENCE_FILE = (
    TABLES / "16_schedule_sequence_ready_sequences.csv"
)

INDIVIDUAL_SEQUENCE_FILE = (
    TABLES / "16_individual_sequences.csv"
)


# ------------------------------------------------------------
# 3. STRAIT OF HORMUZ REFERENCE POINT
# ------------------------------------------------------------

# Approximate geographic reference point.
# Used only for screening-distance calculations.
#
# It is NOT a navigational waypoint, boundary or
# crossing-detection rule.

HORMUZ_REFERENCE_LAT = 26.5667
HORMUZ_REFERENCE_LON = 56.2500


# ------------------------------------------------------------
# 4. APPROXIMATE GEOGRAPHIC SCREENING POLYGONS
# ------------------------------------------------------------

# Coordinates are stored as (longitude, latitude).
#
# These polygons are deliberately broad screening areas.
# They must not be treated as official maritime boundaries.

PERSIAN_GULF_POLYGON = [
    (47.0, 24.0),
    (48.0, 30.5),
    (50.0, 30.8),
    (52.0, 30.0),
    (54.0, 28.5),
    (56.5, 27.5),
    (57.0, 26.5),
    (56.2, 25.5),
    (55.0, 24.5),
    (52.0, 23.0),
    (49.0, 24.0),
    (47.0, 24.0),
]

STRAIT_OF_HORMUZ_SCREENING_POLYGON = [
    (55.0, 25.5),
    (56.5, 27.5),
    (57.5, 27.2),
    (57.0, 25.2),
    (56.0, 24.8),
    (55.0, 25.5),
]

GULF_OF_OMAN_POLYGON = [
    (56.0, 22.0),
    (56.0, 25.5),
    (57.0, 26.5),
    (59.0, 26.8),
    (61.0, 25.5),
    (60.0, 22.0),
    (56.0, 22.0),
]

ARABIAN_SEA_SCREENING_POLYGON = [
    (52.0, 10.0),
    (52.0, 22.0),
    (56.0, 22.0),
    (60.0, 22.0),
    (64.0, 20.0),
    (68.0, 10.0),
    (52.0, 10.0),
]


POLYGONS = {
    "STRAIT_OF_HORMUZ_SCREENING_AREA":
        STRAIT_OF_HORMUZ_SCREENING_POLYGON,

    "PERSIAN_GULF":
        PERSIAN_GULF_POLYGON,

    "GULF_OF_OMAN":
        GULF_OF_OMAN_POLYGON,

    "ARABIAN_SEA_SCREENING_AREA":
        ARABIAN_SEA_SCREENING_POLYGON,
}

POLYGON_PATHS = {
    name: PolygonPath(polygon)
    for name, polygon in POLYGONS.items()
}


# ------------------------------------------------------------
# 5. HELPER FUNCTIONS
# ------------------------------------------------------------

def normalize_column_name(value):

    return re.sub(
        r"[^a-z0-9]",
        "",
        str(value).lower()
    )


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


def normalize_imo(series):

    result = (
        series.astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )

    return result.str.replace(
        r"\.0$",
        "",
        regex=True
    )


def find_column(df, candidates, required=True):

    lookup = {
        normalize_column_name(col): col
        for col in df.columns
    }

    for candidate in candidates:

        key = normalize_column_name(candidate)

        if key in lookup:
            return lookup[key]

    if required:

        raise KeyError(
            f"Column not found: {candidates}\n"
            f"Available columns: {df.columns.tolist()}"
        )

    return None


def read_csv_checked(path):

    if not path.exists():

        raise FileNotFoundError(
            f"Required input file not found: {path}"
        )

    return pd.read_csv(
        path,
        low_memory=False
    )


# ------------------------------------------------------------
# 6. DISTANCE CALCULATION
# ------------------------------------------------------------

def haversine_km(lat1, lon1, lat2, lon2):

    earth_radius_km = 6371.0088

    lat1 = math.radians(float(lat1))
    lon1 = math.radians(float(lon1))

    lat2 = math.radians(float(lat2))
    lon2 = math.radians(float(lon2))

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


# ------------------------------------------------------------
# 7. POINT-IN-POLYGON
# ------------------------------------------------------------

def classify_coordinate(lat, lon):

    if pd.isna(lat) or pd.isna(lon):
        return "COORDINATES_MISSING"

    point = (float(lon), float(lat))

    # Check Strait screening area first.
    # This is an approximate geographic polygon,
    # not a navigational or legal boundary.

    for zone in [
        "STRAIT_OF_HORMUZ_SCREENING_AREA",
        "PERSIAN_GULF",
        "GULF_OF_OMAN",
        "ARABIAN_SEA_SCREENING_AREA",
    ]:

        if POLYGON_PATHS[zone].contains_point(point):
            return zone

    return "OUTSIDE_DEFINED_SCREENING_POLYGONS"


# ------------------------------------------------------------
# 8. LOAD PORT MASTER
# ------------------------------------------------------------

print("\n" + "=" * 80)
print("SCRIPT 18: COORDINATE-BASED PORT GEOGRAPHY VALIDATION")
print("=" * 80)

ports_raw = read_csv_checked(
    PORT_MASTER_FILE
)

country_code_col = find_column(
    ports_raw,
    ["countryCode", "Country Code"]
)

country_name_col = find_column(
    ports_raw,
    ["countryName", "Country Name"]
)

locode_col = find_column(
    ports_raw,
    ["UNLocationCode", "UN Location Code", "LOCODE"]
)

city_col = find_column(
    ports_raw,
    ["cityName", "City Name"],
    required=False
)

port_col = find_column(
    ports_raw,
    ["portName", "Port Name"],
    required=False
)

geo_id_col = find_column(
    ports_raw,
    ["carrierCityGeoID", "Carrier City Geo ID"],
    required=False
)

region_col = find_column(
    ports_raw,
    ["UNRegionCode", "UN Region Code"],
    required=False
)

port_master = pd.DataFrame({

    "Master_Record_ID": range(1, len(ports_raw) + 1),

    "LOCODE": normalize_locode(
        ports_raw[locode_col]
    ),

    "Country_Code": normalize_locode(
        ports_raw[country_code_col]
    ),

    "Country_Name": ports_raw[country_name_col],

    "City_Name": (
        ports_raw[city_col]
        if city_col else pd.NA
    ),

    "Port_Name": (
        ports_raw[port_col]
        if port_col else pd.NA
    ),

    "Carrier_City_Geo_ID": (
        ports_raw[geo_id_col]
        if geo_id_col else pd.NA
    ),

    "UN_Region_Code": (
        ports_raw[region_col]
        if region_col else pd.NA
    ),
})

port_master["LOCODE"] = normalize_locode(
    port_master["LOCODE"]
)

port_master["Port_Name_Normalized"] = (
    port_master["Port_Name"].apply(normalize_text)
)

port_master["City_Name_Normalized"] = (
    port_master["City_Name"].apply(normalize_text)
)


# ------------------------------------------------------------
# 9. IDENTIFY AMBIGUOUS LOCODES
# ------------------------------------------------------------

locode_frequency = (
    port_master.groupby("LOCODE")
    .size()
    .rename("Master_Record_Count")
    .reset_index()
)

ambiguous_locodes = set(
    locode_frequency.loc[
        locode_frequency["Master_Record_Count"] > 1,
        "LOCODE"
    ].dropna()
)

port_master["LOCODE_Ambiguous"] = (
    port_master["LOCODE"].isin(ambiguous_locodes)
)

print("\nPORT MASTER")
print("-" * 80)

print("Master records:", len(port_master))
print("Unique LOCODEs:", port_master["LOCODE"].nunique())
print("Ambiguous LOCODEs:", len(ambiguous_locodes))


# ------------------------------------------------------------
# 10. GENERATE COORDINATE ENRICHMENT TEMPLATE
# ------------------------------------------------------------

template_columns = [
    "LOCODE",
    "Port_Name",
    "City_Name",
    "Country_Code",
    "Latitude",
    "Longitude",
    "Coordinate_Source",
    "Coordinate_Accuracy_M",
]

coordinate_template = port_master[
    [
        "LOCODE",
        "Port_Name",
        "City_Name",
        "Country_Code",
    ]
].copy()

coordinate_template = coordinate_template.drop_duplicates()

for column in [
    "Latitude",
    "Longitude",
    "Coordinate_Source",
    "Coordinate_Accuracy_M",
]:

    coordinate_template[column] = pd.NA

coordinate_template = coordinate_template[
    template_columns
]

template_output = (
    PROCESSED / "18_port_coordinate_enrichment_template.csv"
)

coordinate_template.to_csv(
    template_output,
    index=False
)

print("\nCOORDINATE TEMPLATE")
print("-" * 80)
print("Template records:", len(coordinate_template))
print("Saved:", template_output)


# ------------------------------------------------------------
# 11. CHECK WHETHER COORDINATE FILE EXISTS
# ------------------------------------------------------------

if not COORDINATE_FILE.exists():

    print("\nCoordinate file not found.")
    print("Populate the generated template first.")
    raise SystemExit(0)

# Handle an existing but empty CSV
if COORDINATE_FILE.stat().st_size == 0:

    print("\nCoordinate file exists but is EMPTY.")
    print("Populate it using:")
    print(template_output)
    print("\nExpected destination:")
    print(COORDINATE_FILE)

    raise SystemExit(0)


# ------------------------------------------------------------
# 12. LOAD COORDINATE FILE
# ------------------------------------------------------------

coordinates_raw = read_csv_checked(
    COORDINATE_FILE
)

coordinate_locode_col = find_column(
    coordinates_raw,
    ["LOCODE"]
)

coordinate_lat_col = find_column(
    coordinates_raw,
    ["Latitude", "Lat"]
)

coordinate_lon_col = find_column(
    coordinates_raw,
    ["Longitude", "Lon", "Long"]
)

coordinate_port_col = find_column(
    coordinates_raw,
    ["Port_Name", "Port Name"],
    required=False
)

coordinate_city_col = find_column(
    coordinates_raw,
    ["City_Name", "City Name"],
    required=False
)

coordinate_country_col = find_column(
    coordinates_raw,
    ["Country_Code", "Country Code"],
    required=False
)

coordinate_source_col = find_column(
    coordinates_raw,
    ["Coordinate_Source", "Source"]
)

coordinate_accuracy_col = find_column(
    coordinates_raw,
    ["Coordinate_Accuracy_M", "Accuracy_M"],
    required=False
)

coordinates = pd.DataFrame({

    "LOCODE": normalize_locode(
        coordinates_raw[coordinate_locode_col]
    ),

    "Latitude": pd.to_numeric(
        coordinates_raw[coordinate_lat_col],
        errors="coerce"
    ),

    "Longitude": pd.to_numeric(
        coordinates_raw[coordinate_lon_col],
        errors="coerce"
    ),

    "Port_Name": (
        coordinates_raw[coordinate_port_col]
        if coordinate_port_col else pd.NA
    ),

    "City_Name": (
        coordinates_raw[coordinate_city_col]
        if coordinate_city_col else pd.NA
    ),

    "Country_Code": (
        normalize_locode(
            coordinates_raw[coordinate_country_col]
        )
        if coordinate_country_col else pd.NA
    ),

    "Coordinate_Source": (
        coordinates_raw[coordinate_source_col]
    ),

    "Coordinate_Accuracy_M": (
        pd.to_numeric(
            coordinates_raw[coordinate_accuracy_col],
            errors="coerce"
        )
        if coordinate_accuracy_col else np.nan
    ),
})


# ------------------------------------------------------------
# 13. VALIDATE COORDINATES
# ------------------------------------------------------------

coordinates["Latitude_Valid"] = (
    coordinates["Latitude"].between(-90, 90)
)

coordinates["Longitude_Valid"] = (
    coordinates["Longitude"].between(-180, 180)
)

coordinates["Coordinate_Valid"] = (
    coordinates["Latitude_Valid"]
    & coordinates["Longitude_Valid"]
)

coordinates["Source_Provided"] = (
    coordinates["Coordinate_Source"]
    .astype("string")
    .str.strip()
    .ne("")
    .fillna(False)
)

coordinates["Coordinate_Quality_Status"] = np.select(
    [
        coordinates["Latitude"].isna()
        | coordinates["Longitude"].isna(),

        ~coordinates["Coordinate_Valid"],

        ~coordinates["Source_Provided"],
    ],
    [
        "MISSING_COORDINATES",
        "INVALID_COORDINATES",
        "SOURCE_NOT_PROVIDED",
    ],
    default="VALIDATED_INPUT_REQUIRES_SOURCE_REVIEW"
)

coordinates["Port_Name_Normalized"] = (
    coordinates["Port_Name"].apply(normalize_text)
)

coordinates["City_Name_Normalized"] = (
    coordinates["City_Name"].apply(normalize_text)
)


# ------------------------------------------------------------
# 14. INVESTIGATE DUPLICATE COORDINATE ENTRIES
# ------------------------------------------------------------

coordinate_duplicate_rows = coordinates[
    coordinates.duplicated(
        subset=["LOCODE"],
        keep=False
    )
].copy()

coordinate_duplicate_rows.to_csv(
    TABLES / "18_duplicate_coordinate_entries.csv",
    index=False
)


# ------------------------------------------------------------
# 15. CONSERVATIVE COORDINATE MATCHING
# ------------------------------------------------------------

# Match using LOCODE, country and facility/port identity.
# Do not arbitrarily assign a coordinate when a LOCODE
# corresponds to multiple port-master facilities.

master = port_master.copy()

coordinate_records = []

for _, master_row in master.iterrows():

    candidates = coordinates[
        coordinates["LOCODE"] == master_row["LOCODE"]
    ].copy()

    if candidates.empty:

        coordinate_records.append({
            "Master_Record_ID": master_row["Master_Record_ID"],
            "Coordinate_Match_Status": "NO_COORDINATE_RECORD",
            "Latitude": np.nan,
            "Longitude": np.nan,
            "Coordinate_Source": pd.NA,
            "Coordinate_Accuracy_M": np.nan,
        })

        continue

    # Filter by country when provided.
    if candidates["Country_Code"].notna().any():

        candidates = candidates[
            candidates["Country_Code"].isna()
            | (
                candidates["Country_Code"]
                == master_row["Country_Code"]
            )
        ]

    # If the master LOCODE is ambiguous, require a port-name
    # or city-name match to select a facility.
    if master_row["LOCODE_Ambiguous"]:

        port_match = candidates[
            candidates["Port_Name_Normalized"]
            == master_row["Port_Name_Normalized"]
        ]

        city_match = candidates[
            candidates["City_Name_Normalized"]
            == master_row["City_Name_Normalized"]
        ]

        candidates = pd.concat(
            [port_match, city_match],
            ignore_index=True
        ).drop_duplicates()

    candidates = candidates[
        candidates["Coordinate_Valid"]
        & candidates["Source_Provided"]
    ]

    if len(candidates) == 0:

        status = (
            "AMBIGUOUS_OR_UNMATCHED_COORDINATE"
            if master_row["LOCODE_Ambiguous"]
            else "NO_VALID_COORDINATE"
        )

        coordinate_records.append({
            "Master_Record_ID": master_row["Master_Record_ID"],
            "Coordinate_Match_Status": status,
            "Latitude": np.nan,
            "Longitude": np.nan,
            "Coordinate_Source": pd.NA,
            "Coordinate_Accuracy_M": np.nan,
        })

        continue

    if len(candidates) > 1:

        coordinate_records.append({
            "Master_Record_ID": master_row["Master_Record_ID"],
            "Coordinate_Match_Status": "MULTIPLE_COORDINATE_CANDIDATES",
            "Latitude": np.nan,
            "Longitude": np.nan,
            "Coordinate_Source": pd.NA,
            "Coordinate_Accuracy_M": np.nan,
        })

        continue

    candidate = candidates.iloc[0]

    coordinate_records.append({
        "Master_Record_ID": master_row["Master_Record_ID"],
        "Coordinate_Match_Status": "MATCHED_COORDINATE",
        "Latitude": candidate["Latitude"],
        "Longitude": candidate["Longitude"],
        "Coordinate_Source": candidate["Coordinate_Source"],
        "Coordinate_Accuracy_M": candidate["Coordinate_Accuracy_M"],
    })


coordinate_matches = pd.DataFrame(
    coordinate_records
)

validated_ports = master.merge(
    coordinate_matches,
    on="Master_Record_ID",
    how="left",
    validate="one_to_one"
)


# ------------------------------------------------------------
# 16. GEOGRAPHIC CLASSIFICATION
# ------------------------------------------------------------

validated_ports["Geographic_Zone"] = validated_ports.apply(
    lambda row: classify_coordinate(
        row["Latitude"],
        row["Longitude"]
    ),
    axis=1
)

validated_ports["Distance_To_Hormuz_Reference_KM"] = (
    validated_ports.apply(
        lambda row: (
            haversine_km(
                row["Latitude"],
                row["Longitude"],
                HORMUZ_REFERENCE_LAT,
                HORMUZ_REFERENCE_LON
            )
            if row["Coordinate_Match_Status"]
            == "MATCHED_COORDINATE"
            else np.nan
        ),
        axis=1
    )
)

validated_ports["Geographic_Review_Status"] = np.select(
    [
        validated_ports["Coordinate_Match_Status"]
        != "MATCHED_COORDINATE",

        validated_ports["LOCODE_Ambiguous"],

        validated_ports["Geographic_Zone"]
        == "OUTSIDE_DEFINED_SCREENING_POLYGONS",
    ],
    [
        "COORDINATE_MATCH_REQUIRES_REVIEW",
        "AMBIGUOUS_LOCODE_REQUIRES_REVIEW",
        "GEOGRAPHIC_ZONE_MANUAL_REVIEW",
    ],
    default="SCREENING_CLASSIFIED_REQUIRES_BOUNDARY_VALIDATION"
)


# ------------------------------------------------------------
# 17. SAVE VALIDATED PORT DATA
# ------------------------------------------------------------

validated_ports.to_csv(
    PROCESSED / "18_validated_port_geography.csv",
    index=False
)

review_ports = validated_ports[
    validated_ports["Geographic_Review_Status"]
    != "SCREENING_CLASSIFIED_REQUIRES_BOUNDARY_VALIDATION"
].copy()

review_ports.to_csv(
    TABLES / "18_ports_requiring_geographic_review.csv",
    index=False
)

zone_summary = (
    validated_ports.groupby(
        [
            "Geographic_Zone",
            "Coordinate_Match_Status",
            "Geographic_Review_Status",
        ],
        dropna=False
    )
    .agg(
        Port_Master_Records=("Master_Record_ID", "size"),
        Unique_LOCODES=("LOCODE", "nunique"),
        Unique_Countries=("Country_Code", "nunique"),
    )
    .reset_index()
)

zone_summary.to_csv(
    TABLES / "18_geographic_zone_summary.csv",
    index=False
)


# ------------------------------------------------------------
# 18. CREATE A UNIQUE IMO-LEVEL AIS ACQUISITION REGISTER
# ------------------------------------------------------------

schedule_candidates = read_csv_checked(
    SCHEDULE_CANDIDATES_FILE
)

individual_candidates = read_csv_checked(
    INDIVIDUAL_CANDIDATES_FILE
)

candidate_frames = []

for dataset_name, frame in [
    ("Schedule", schedule_candidates),
    ("Individual", individual_candidates),
]:

    imo_col = find_column(
        frame,
        ["IMO_17", "IMO", "IMO_Analysis"],
        required=False
    )

    if imo_col is None:
        continue

    name_col = find_column(
        frame,
        ["Vessel_Name", "Vessel_Name_17", "Vessel Name"],
        required=False
    )

    candidate = pd.DataFrame({

        "IMO": normalize_imo(
            frame[imo_col]
        ),

        "Dataset": dataset_name,

        "Vessel_Name": (
            frame[name_col].astype("string")
            if name_col else pd.NA
        ),
    })

    candidate_frames.append(candidate)


if candidate_frames:

    all_candidates = pd.concat(
        candidate_frames,
        ignore_index=True
    )

    all_candidates = all_candidates[
        all_candidates["IMO"].notna()
    ].copy()

    unique_vessel_register = (
        all_candidates.groupby("IMO")
        .agg(
            Vessel_Name=("Vessel_Name", "first"),
            Dataset_Membership=(
                "Dataset",
                lambda x: " | ".join(sorted(set(x)))
            ),
            Dataset_Count=("Dataset", "nunique"),
        )
        .reset_index()
    )

else:

    unique_vessel_register = pd.DataFrame(
        columns=[
            "IMO",
            "Vessel_Name",
            "Dataset_Membership",
            "Dataset_Count",
        ]
    )


unique_vessel_register["AIS_Acquisition_Status"] = (
    "CANDIDATE_PENDING_AIS_ACQUISITION"
)

unique_vessel_register["Transit_Verification_Status"] = (
    "NOT_VERIFIED"
)

unique_vessel_register.to_csv(
    TABLES / "18_unique_IMO_AIS_acquisition_register.csv",
    index=False
)


# ------------------------------------------------------------
# 19. GENERATE REPORT
# ------------------------------------------------------------

report_file = (
    REPORTS / "18_coordinate_based_port_geography_report.txt"
)

with open(report_file, "w", encoding="utf-8") as f:

    f.write("=" * 80 + "\n")
    f.write("SCRIPT 18: COORDINATE-BASED PORT GEOGRAPHY\n")
    f.write("=" * 80 + "\n\n")

    f.write("1. PORT MASTER\n")
    f.write("-" * 80 + "\n")

    f.write(
        f"Original port records: {len(port_master)}\n"
    )

    f.write(
        f"Unique LOCODEs: {port_master['LOCODE'].nunique()}\n"
    )

    f.write(
        f"Ambiguous LOCODEs: {len(ambiguous_locodes)}\n\n"
    )

    f.write("2. COORDINATE INPUT VALIDATION\n")
    f.write("-" * 80 + "\n")

    f.write(
        f"Coordinate input records: {len(coordinates)}\n"
    )

    f.write(
        f"Valid coordinate pairs: "
        f"{int(coordinates['Coordinate_Valid'].sum())}\n"
    )

    f.write(
        f"Missing coordinate pairs: "
        f"{int((~coordinates['Coordinate_Valid']).sum())}\n\n"
    )

    f.write("3. COORDINATE MATCHING\n")
    f.write("-" * 80 + "\n")

    f.write(
        validated_ports[
            "Coordinate_Match_Status"
        ].value_counts(dropna=False).to_string()
    )

    f.write("\n\n4. GEOGRAPHIC CLASSIFICATION\n")
    f.write("-" * 80 + "\n")

    f.write(
        zone_summary.to_string(index=False)
    )

    f.write("\n\n5. REVIEW REQUIRED\n")
    f.write("-" * 80 + "\n")

    f.write(
        f"Ports requiring review: {len(review_ports)}\n\n"
    )

    f.write("6. UNIQUE AIS ACQUISITION REGISTER\n")
    f.write("-" * 80 + "\n")

    f.write(
        f"Unique candidate IMOs: {len(unique_vessel_register)}\n"
    )

    if not unique_vessel_register.empty:

        f.write(
            "Candidates appearing in both datasets: "
            f"{int((unique_vessel_register['Dataset_Count'] > 1).sum())}\n"
        )

    f.write("\n\n7. METHODOLOGICAL LIMITATIONS\n")
    f.write("-" * 80 + "\n")

    limitations = [
        "Coordinates must be supplied from a documented source.",
        "Coordinate validation checks numerical ranges and matching; "
        "it does not independently authenticate the source.",
        "LOCODEs may represent multiple facilities.",
        "Ambiguous LOCODEs require facility-level matching.",
        "The geographic polygons are approximate screening polygons.",
        "The polygons are not legal maritime boundaries.",
        "Distance is calculated to a single Strait reference point.",
        "Distance to that point is not distance to a navigable route.",
        "A port call does not prove Strait of Hormuz transit.",
        "AIS trajectories are required for actual crossing verification.",
    ]

    for item in limitations:
        f.write(f"- {item}\n")


# ------------------------------------------------------------
# 20. FINAL SUMMARY
# ------------------------------------------------------------

print("\n" + "=" * 80)
print("SCRIPT 18 COMPLETED SUCCESSFULLY")
print("=" * 80)

print("\nPORT MASTER")
print("-" * 80)

print("Original records:", len(port_master))
print("Unique LOCODEs:", port_master["LOCODE"].nunique())
print("Ambiguous LOCODEs:", len(ambiguous_locodes))

print("\nCOORDINATE VALIDATION")
print("-" * 80)

print("Coordinate input records:", len(coordinates))

print(
    "Valid coordinate pairs:",
    int(coordinates["Coordinate_Valid"].sum())
)

print(
    "Matched port-master records:",
    int(
        (
            validated_ports["Coordinate_Match_Status"]
            == "MATCHED_COORDINATE"
        ).sum()
    )
)

print(
    "Ports requiring review:",
    len(review_ports)
)

print("\nGEOGRAPHIC ZONES")
print("-" * 80)

print(
    validated_ports["Geographic_Zone"]
    .value_counts(dropna=False)
    .to_string()
)

print("\nAIS ACQUISITION REGISTER")
print("-" * 80)

print(
    "Unique candidate IMOs:",
    len(unique_vessel_register)
)

if not unique_vessel_register.empty:

    print(
        "Candidates in both datasets:",
        int(
            (
                unique_vessel_register["Dataset_Count"] > 1
            ).sum()
        )
    )

print("\nOUTPUTS")
print("-" * 80)

print(
    "Coordinate template:",
    template_output
)

print(
    "Validated port geography:",
    PROCESSED / "18_validated_port_geography.csv"
)

print(
    "Unique IMO register:",
    TABLES / "18_unique_IMO_AIS_acquisition_register.csv"
)

print(
    "Report:",
    report_file
)

print("\nNo original source data was modified.")
print("No missing coordinates were invented.")
print("No Strait crossings were assumed.")
