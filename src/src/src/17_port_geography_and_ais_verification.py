
from pathlib import Path
import re
import pandas as pd
import numpy as np


# ============================================================
# SCRIPT 17
# PORT GEOGRAPHY VALIDATION AND AIS VERIFICATION PREPARATION
#
# Objectives:
# 1. Validate port LOCODEs against active port master.
# 2. Geographically screen ports relevant to Hormuz research.
# 3. Identify vessels calling at screened ports.
# 4. Reconstruct their recorded port-call sequences.
# 5. Prioritize movements for AIS trajectory verification.
# 6. Create an AIS data input template.
#
# IMPORTANT:
# A port call is NOT proof of Strait of Hormuz transit.
# AIS trajectories are required for transit verification.
# ============================================================


# ------------------------------------------------------------
# 1. PROJECT PATHS
# ------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
TABLES = ROOT / "outputs" / "tables"
REPORTS = ROOT / "outputs" / "reports"

for folder in [PROCESSED, TABLES, REPORTS]:
    folder.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------
# 2. INPUT FILES
# ------------------------------------------------------------

PORT_MASTER_FILE = RAW / "active_ports.csv"

SCHEDULE_SEQUENCE_FILE = (
    TABLES / "16_schedule_sequence_ready_sequences.csv"
)

INDIVIDUAL_SEQUENCE_FILE = (
    TABLES / "16_individual_sequences.csv"
)

AIS_REGISTER_FILE = (
    TABLES / "15_AIS_trajectory_verification_register.csv"
)


# ------------------------------------------------------------
# 3. HELPERS
# ------------------------------------------------------------

def normalize_text(series):

    return (
        series.astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )


def normalize_locode(series):

    return normalize_text(series)


def normalize_imo(series):

    result = normalize_text(series)

    return result.str.replace(
        r"\.0$",
        "",
        regex=True
    )


def normalize_column_name(value):

    return re.sub(
        r"[^a-z0-9]",
        "",
        str(value).lower()
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
            f"Required column not found: {candidates}\n"
            f"Available columns: {df.columns.tolist()}"
        )

    return None


def read_csv_checked(path):

    if not path.exists():
        raise FileNotFoundError(
            f"Input file not found: {path}"
        )

    return pd.read_csv(
        path,
        low_memory=False
    )


# ------------------------------------------------------------
# 4. LOAD DATA
# ------------------------------------------------------------

print("\n" + "=" * 80)
print("SCRIPT 17: PORT GEOGRAPHY AND AIS VERIFICATION")
print("=" * 80)

ports_raw = read_csv_checked(PORT_MASTER_FILE)

schedule_raw = read_csv_checked(
    SCHEDULE_SEQUENCE_FILE
)

individual_raw = read_csv_checked(
    INDIVIDUAL_SEQUENCE_FILE
)

print("\nINPUT DATA")
print("-" * 80)

print("Port master:", ports_raw.shape)
print("Schedule sequences:", schedule_raw.shape)
print("Individual sequences:", individual_raw.shape)


# ------------------------------------------------------------
# 5. STANDARDIZE PORT MASTER
# ------------------------------------------------------------

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

port_name_col = find_column(
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
    "Country_Code": normalize_text(
        ports_raw[country_code_col]
    ),
    "Country_Name": ports_raw[country_name_col].astype("string"),
    "LOCODE": normalize_locode(
        ports_raw[locode_col]
    ),
    "City_Name": (
        ports_raw[city_col].astype("string")
        if city_col else pd.NA
    ),
    "Port_Name": (
        ports_raw[port_name_col].astype("string")
        if port_name_col else pd.NA
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

port_master = port_master[
    port_master["LOCODE"].notna()
].copy()


# ------------------------------------------------------------
# 6. INVESTIGATE DUPLICATE LOCODES
# ------------------------------------------------------------

locode_counts = (
    port_master.groupby("LOCODE")
    .size()
    .rename("Master_Record_Count")
    .reset_index()
)

duplicate_locodes = locode_counts[
    locode_counts["Master_Record_Count"] > 1
].copy()

duplicate_port_details = port_master[
    port_master["LOCODE"].isin(
        duplicate_locodes["LOCODE"]
    )
].copy()

duplicate_port_details.to_csv(
    TABLES / "17_ambiguous_port_locodes.csv",
    index=False
)

print("\nPORT MASTER VALIDATION")
print("-" * 80)

print("Port master records:", len(port_master))
print("Unique LOCODEs:", port_master["LOCODE"].nunique())
print("Ambiguous LOCODEs:", len(duplicate_locodes))


# ------------------------------------------------------------
# 7. GEOGRAPHIC SCREENING
# ------------------------------------------------------------

# This is a deliberately conservative screening list.
# It identifies known ports and port groups requiring
# geographic review. It does NOT establish vessel transit.

PERSIAN_GULF_LOCODES = {
    # United Arab Emirates
    "AEJEA",  # Jebel Ali
    "AEAUH",  # Abu Dhabi
    "AERKT",  # Ras Al Khaimah

    # Qatar
    "QAHMD",  # Hamad Port

    # Bahrain
    "BHBAH",  # Bahrain

    # Kuwait
    "KWKWI",  # Kuwait

    # Iraq
    "IQUQR",  # Umm Qasr

    # Saudi Arabia - Eastern Province
    "SADMM",  # Dammam
    "SAJUB",  # Jubail
    "SARAM",  # Ras Tanura

    # Iran - selected ports
    "IRBND",  # Bandar Abbas
    "IRBUS",  # Bushehr
    "IRKHO",  # Khorramshahr
}

GULF_OF_OMAN_AND_EAST_COAST_LOCODES = {
    "AEFJR",  # Fujairah
    "AEKLF",  # Khor Fakkan
    "OMSOH",  # Sohar
    "OMMCT",  # Muscat
}

# Salalah is deliberately kept separate.
# It is an Arabian Sea port, not a Strait of Hormuz approach port.
ARABIAN_SEA_LOCODES = {
    "OMSLL",
}


def classify_port(row):

    locode = row["LOCODE"]

    if locode in PERSIAN_GULF_LOCODES:

        return (
            "PERSIAN_GULF_SCREENED_PORT",
            "HIGH_GEOGRAPHIC_RELEVANCE"
        )

    if locode in GULF_OF_OMAN_AND_EAST_COAST_LOCODES:

        return (
            "GULF_OF_OMAN_OR_EAST_COAST_SCREENING",
            "POTENTIAL_APPROACH_RELEVANCE"
        )

    if locode in ARABIAN_SEA_LOCODES:

        return (
            "ARABIAN_SEA_PORT",
            "NOT_A_HORMUZ_APPROACH_PORT"
        )

    # Country-level screening is not enough to assign
    # a specific geographic position to every port.
    country = row["Country_Code"]

    if country in {
        "AE", "OM", "QA", "BH",
        "KW", "IQ", "IR", "SA"
    }:

        return (
            "GULF_REGION_COUNTRY_UNVERIFIED_PORT",
            "MANUAL_GEOGRAPHIC_REVIEW"
        )

    return (
        "OUTSIDE_INITIAL_GULF_SCREEN",
        "NOT_SCREENED_AS_GULF_PORT"
    )


classification = port_master.apply(
    classify_port,
    axis=1,
    result_type="expand"
)

port_master["Geographic_Category"] = classification[0]

port_master["Geographic_Confidence"] = classification[1]

# Do not silently resolve ambiguous LOCODEs.
port_master["LOCODE_Ambiguity"] = (
    port_master["LOCODE"].isin(
        duplicate_locodes["LOCODE"]
    )
)

port_master["Geographic_Review_Status"] = np.where(
    port_master["LOCODE_Ambiguity"],
    "AMBIGUOUS_LOCODE_REQUIRES_MANUAL_REVIEW",
    "SCREENING_CLASSIFICATION_ONLY"
)

port_master.to_csv(
    PROCESSED / "17_port_geographic_screening.csv",
    index=False
)


# ------------------------------------------------------------
# 8. SAVE SCREENED PORTS
# ------------------------------------------------------------

screened_ports = port_master[
    port_master["Geographic_Category"] !=
    "OUTSIDE_INITIAL_GULF_SCREEN"
].copy()

screened_ports.to_csv(
    TABLES / "17_gulf_and_approach_port_screening.csv",
    index=False
)

print("\nGEOGRAPHIC SCREENING")
print("-" * 80)

print(
    screened_ports["Geographic_Category"]
    .value_counts()
    .to_string()
)


# ------------------------------------------------------------
# 9. STANDARDIZE SEQUENCE DATASETS
# ------------------------------------------------------------

def prepare_sequence_data(df, dataset_name):

    result = df.copy()

    imo_col = find_column(
        result,
        ["IMO_Analysis", "IMO", "IMO_Normalised"]
    )

    locode_col = find_column(
        result,
        ["LOCODE_Analysis", "LOCODE", "UNLOCODE_Normalised"]
    )

    vessel_col = find_column(
        result,
        ["Vessel_Name_Analysis", "Vessel Name", "Vessel_Name"],
        required=False
    )

    port_col = find_column(
        result,
        ["Port_Name_Analysis", "Port", "Port_Name"],
        required=False
    )

    arrival_col = find_column(
        result,
        ["Actual_Arrival_UTC", "Actual Arrival", "Arrival_UTC"],
        required=False
    )

    departure_col = find_column(
        result,
        ["Actual_Departure_UTC", "Actual Departure", "Departure_UTC"],
        required=False
    )

    previous_locode_col = find_column(
        result,
        ["Previous_LOCODE"],
        required=False
    )

    result["IMO_17"] = normalize_imo(
        result[imo_col]
    )

    result["LOCODE_17"] = normalize_locode(
        result[locode_col]
    )

    result["Dataset_17"] = dataset_name

    result["Vessel_Name_17"] = (
        result[vessel_col].astype("string")
        if vessel_col else pd.NA
    )

    result["Port_Name_17"] = (
        result[port_col].astype("string")
        if port_col else pd.NA
    )

    if arrival_col:

        result["Arrival_UTC_17"] = pd.to_datetime(
            result[arrival_col],
            errors="coerce",
            utc=True
        )

    else:

        result["Arrival_UTC_17"] = pd.NaT

    if departure_col:

        result["Departure_UTC_17"] = pd.to_datetime(
            result[departure_col],
            errors="coerce",
            utc=True
        )

    else:

        result["Departure_UTC_17"] = pd.NaT

    if previous_locode_col:

        result["Previous_LOCODE_17"] = normalize_locode(
            result[previous_locode_col]
        )

    else:

        result["Previous_LOCODE_17"] = pd.NA

    return result


schedule = prepare_sequence_data(
    schedule_raw,
    "Schedule_Sequence_Ready"
)

individual = prepare_sequence_data(
    individual_raw,
    "Individual"
)

all_sequences = pd.concat(
    [schedule, individual],
    ignore_index=True
)


# ------------------------------------------------------------
# 10. ATTACH GEOGRAPHIC INFORMATION
# ------------------------------------------------------------

# Use a one-row-per-LOCODE lookup only where the LOCODE
# has exactly one master record.
#
# Ambiguous LOCODEs are intentionally not assigned an
# arbitrary port record.

unambiguous_master = port_master[
    ~port_master["LOCODE_Ambiguity"]
].copy()

port_lookup = unambiguous_master[
    [
        "LOCODE",
        "Country_Code",
        "Country_Name",
        "City_Name",
        "Port_Name",
        "Geographic_Category",
        "Geographic_Confidence",
        "Geographic_Review_Status",
    ]
].drop_duplicates("LOCODE")

all_sequences = all_sequences.merge(
    port_lookup,
    left_on="LOCODE_17",
    right_on="LOCODE",
    how="left",
    validate="many_to_one"
)

all_sequences["Geographic_Category"] = (
    all_sequences["Geographic_Category"]
    .fillna("UNMATCHED_OR_AMBIGUOUS_PORT")
)

all_sequences["Geographic_Confidence"] = (
    all_sequences["Geographic_Confidence"]
    .fillna("UNVERIFIED")
)


# ------------------------------------------------------------
# 11. IDENTIFY GULF-REGION VESSEL CALLS
# ------------------------------------------------------------

relevant_categories = {
    "PERSIAN_GULF_SCREENED_PORT",
    "GULF_OF_OMAN_OR_EAST_COAST_SCREENING",
    "GULF_REGION_COUNTRY_UNVERIFIED_PORT",
}

gulf_calls = all_sequences[
    all_sequences["Geographic_Category"].isin(
        relevant_categories
    )
].copy()

gulf_calls = gulf_calls.sort_values(
    ["Dataset_17", "IMO_17", "Arrival_UTC_17"],
    kind="stable"
)

gulf_calls.to_csv(
    TABLES / "17_gulf_region_vessel_calls.csv",
    index=False
)

print("\nGULF-REGION CALLS")
print("-" * 80)

print("Total screened calls:", len(gulf_calls))

print(
    "Unique vessels:",
    gulf_calls["IMO_17"].nunique()
)


# ------------------------------------------------------------
# 12. VESSEL-LEVEL CANDIDATE SUMMARY
# ------------------------------------------------------------

vessel_summary = (
    gulf_calls.groupby(
        ["Dataset_17", "IMO_17"],
        dropna=False
    )
    .agg(
        Vessel_Name=("Vessel_Name_17", "first"),
        Gulf_Region_Calls=("LOCODE_17", "size"),
        Unique_Screened_Ports=("LOCODE_17", "nunique"),
        First_Screened_Arrival=("Arrival_UTC_17", "min"),
        Last_Screened_Arrival=("Arrival_UTC_17", "max"),
        Screened_LOCODES=(
            "LOCODE_17",
            lambda x: " -> ".join(
                x.dropna().astype(str).tolist()
            )
        ),
        Geographic_Categories=(
            "Geographic_Category",
            lambda x: " | ".join(
                sorted(set(x.dropna().astype(str)))
            )
        ),
    )
    .reset_index()
)

vessel_summary.to_csv(
    TABLES / "17_gulf_candidate_vessel_summary.csv",
    index=False
)


# ------------------------------------------------------------
# 13. RECONSTRUCT FULL SEQUENCES FOR CANDIDATES
# ------------------------------------------------------------

candidate_imos = set(
    gulf_calls["IMO_17"].dropna()
)

candidate_sequences = all_sequences[
    all_sequences["IMO_17"].isin(candidate_imos)
].copy()

candidate_sequences = candidate_sequences.sort_values(
    ["Dataset_17", "IMO_17", "Arrival_UTC_17"],
    kind="stable"
)

candidate_sequences.to_csv(
    TABLES / "17_gulf_candidate_full_port_sequences.csv",
    index=False
)


# ------------------------------------------------------------
# 14. IDENTIFY APPROACH-RELEVANT TRANSITIONS
# ------------------------------------------------------------

# This is a screening step, not proof of Strait crossing.
#
# A transition is flagged when either the previous or current
# port belongs to the screened Persian Gulf / Gulf of Oman set.

approach_locodes = (
    PERSIAN_GULF_LOCODES
    | GULF_OF_OMAN_AND_EAST_COAST_LOCODES
)

candidate_sequences["Previous_Port_Is_Approach_Candidate"] = (
    candidate_sequences["Previous_LOCODE_17"]
    .isin(approach_locodes)
)

candidate_sequences["Current_Port_Is_Approach_Candidate"] = (
    candidate_sequences["LOCODE_17"]
    .isin(approach_locodes)
)

candidate_sequences["AIS_Review_Flag"] = (
    candidate_sequences["Previous_Port_Is_Approach_Candidate"]
    | candidate_sequences["Current_Port_Is_Approach_Candidate"]
)

ais_review = candidate_sequences[
    candidate_sequences["AIS_Review_Flag"]
].copy()

ais_review["AIS_Review_Priority"] = np.select(
    [
        (
            ais_review["Previous_Port_Is_Approach_Candidate"]
            & ais_review["Current_Port_Is_Approach_Candidate"]
        ),

        ais_review["Current_Port_Is_Approach_Candidate"],

        ais_review["Previous_Port_Is_Approach_Candidate"],
    ],
    [
        "HIGH",
        "HIGH",
        "MEDIUM",
    ],
    default="LOW"
)

ais_review["Verification_Status"] = (
    "NOT_VERIFIED_AIS_REQUIRED"
)

ais_review["Transit_Conclusion"] = (
    "NO_TRANSIT_CONCLUSION_FROM_PORT_CALLS"
)

ais_review.to_csv(
    TABLES / "17_AIS_priority_verification_register.csv",
    index=False
)


# ------------------------------------------------------------
# 15. BUILD UNIQUE VESSEL AIS REGISTER
# ------------------------------------------------------------

ais_vessel_register = (
    ais_review.groupby(
        ["Dataset_17", "IMO_17"],
        dropna=False
    )
    .agg(
        Vessel_Name=("Vessel_Name_17", "first"),
        AIS_Review_Records=("LOCODE_17", "size"),
        Unique_Approach_LOCODES=(
            "LOCODE_17",
            "nunique"
        ),
        First_Observed_Approach_Call=(
            "Arrival_UTC_17",
            "min"
        ),
        Last_Observed_Approach_Call=(
            "Arrival_UTC_17",
            "max"
        ),
        AIS_Priority=(
    "AIS_Review_Priority",
    lambda x: (
        "HIGH" if "HIGH" in set(x)
        else "MEDIUM" if "MEDIUM" in set(x)
        else "LOW"
    )
),
    )
    .reset_index()
)

ais_vessel_register["AIS_Data_Available"] = "NOT_ASSESSED"

ais_vessel_register["Transit_Verification"] = (
    "PENDING_AIS_TRAJECTORY"
)

ais_vessel_register.to_csv(
    TABLES / "17_unique_vessel_AIS_verification_register.csv",
    index=False
)


# ------------------------------------------------------------
# 16. CREATE AIS INPUT TEMPLATE
# ------------------------------------------------------------

ais_template = pd.DataFrame(
    columns=[
        "IMO",
        "Vessel_Name",
        "Timestamp_UTC",
        "Latitude",
        "Longitude",
        "SOG_Knots",
        "COG_Degrees",
        "Heading_Degrees",
        "Navigation_Status",
        "Source",
        "Data_Quality_Flag",
    ]
)

ais_template.to_csv(
    PROCESSED / "17_AIS_trajectory_input_template.csv",
    index=False
)


# ------------------------------------------------------------
# 17. CREATE AIS DATA REQUIREMENTS
# ------------------------------------------------------------

ais_requirements = pd.DataFrame([
    {
        "Field": "IMO",
        "Required": "YES",
        "Purpose": "Identify vessel consistently",
    },
    {
        "Field": "Timestamp_UTC",
        "Required": "YES",
        "Purpose": "Order vessel positions chronologically",
    },
    {
        "Field": "Latitude",
        "Required": "YES",
        "Purpose": "Determine geographic position",
    },
    {
        "Field": "Longitude",
        "Required": "YES",
        "Purpose": "Determine geographic position",
    },
    {
        "Field": "SOG_Knots",
        "Required": "RECOMMENDED",
        "Purpose": "Assess vessel speed and movement",
    },
    {
        "Field": "COG_Degrees",
        "Required": "RECOMMENDED",
        "Purpose": "Assess direction of travel",
    },
    {
        "Field": "Heading_Degrees",
        "Required": "OPTIONAL",
        "Purpose": "Additional movement evidence",
    },
    {
        "Field": "Navigation_Status",
        "Required": "OPTIONAL",
        "Purpose": "Understand vessel operational state",
    },
    {
        "Field": "Source",
        "Required": "YES",
        "Purpose": "Maintain data provenance",
    },
])

ais_requirements.to_csv(
    TABLES / "17_AIS_data_requirements.csv",
    index=False
)


# ------------------------------------------------------------
# 18. CHECK EXISTING AIS REGISTER
# ------------------------------------------------------------

if AIS_REGISTER_FILE.exists():

    previous_ais_register = pd.read_csv(
        AIS_REGISTER_FILE,
        low_memory=False
    )

    print("\nPREVIOUS AIS REGISTER")
    print("-" * 80)

    print(
        "Existing AIS register records:",
        len(previous_ais_register)
    )

    print(
        "Note: Existing register is retained separately; "
        "Script 17 creates a new geographic screening register."
    )

else:

    print("\nNo previous Script 15 AIS register found.")
    print("A new geographic screening register has been created.")


# ------------------------------------------------------------
# 19. GEOGRAPHIC SCREENING SUMMARY
# ------------------------------------------------------------

port_category_summary = (
    screened_ports.groupby(
        ["Geographic_Category", "Geographic_Confidence"]
    )
    .agg(
        Port_Master_Records=("LOCODE", "size"),
        Unique_LOCODES=("LOCODE", "nunique"),
        Unique_Countries=("Country_Code", "nunique"),
    )
    .reset_index()
)

port_category_summary.to_csv(
    TABLES / "17_port_geographic_category_summary.csv",
    index=False
)


# ------------------------------------------------------------
# 20. DATA COVERAGE SUMMARY
# ------------------------------------------------------------

coverage_summary = pd.DataFrame([
    {
        "Dataset": "Schedule_Sequence_Ready",
        "Total_Sequence_Records": len(schedule),
        "Unique_Vessels": schedule["IMO_17"].nunique(),
        "Screened_Gulf_Calls": len(
            gulf_calls[
                gulf_calls["Dataset_17"] ==
                "Schedule_Sequence_Ready"
            ]
        ),
        "AIS_Review_Records": len(
            ais_review[
                ais_review["Dataset_17"] ==
                "Schedule_Sequence_Ready"
            ]
        ),
    },
    {
        "Dataset": "Individual",
        "Total_Sequence_Records": len(individual),
        "Unique_Vessels": individual["IMO_17"].nunique(),
        "Screened_Gulf_Calls": len(
            gulf_calls[
                gulf_calls["Dataset_17"] == "Individual"
            ]
        ),
        "AIS_Review_Records": len(
            ais_review[
                ais_review["Dataset_17"] == "Individual"
            ]
        ),
    },
])

coverage_summary.to_csv(
    TABLES / "17_geographic_AIS_coverage_summary.csv",
    index=False
)


# ------------------------------------------------------------
# 21. GENERATE REPORT
# ------------------------------------------------------------

report_file = (
    REPORTS / "17_port_geography_and_AIS_verification_report.txt"
)

with open(report_file, "w", encoding="utf-8") as f:

    f.write("=" * 80 + "\n")
    f.write("SCRIPT 17: PORT GEOGRAPHY AND AIS VERIFICATION\n")
    f.write("=" * 80 + "\n\n")

    f.write("1. INPUT DATA\n")
    f.write("-" * 80 + "\n")

    f.write(
        f"Port master records: {len(port_master)}\n"
    )

    f.write(
        f"Schedule sequence records: {len(schedule)}\n"
    )

    f.write(
        f"Individual sequence records: {len(individual)}\n\n"
    )

    f.write("2. PORT MASTER VALIDATION\n")
    f.write("-" * 80 + "\n")

    f.write(
        f"Unique LOCODEs: {port_master['LOCODE'].nunique()}\n"
    )

    f.write(
        f"Ambiguous LOCODEs: {len(duplicate_locodes)}\n\n"
    )

    f.write("3. GEOGRAPHIC SCREENING\n")
    f.write("-" * 80 + "\n")

    f.write(
        port_category_summary.to_string(index=False)
    )

    f.write("\n\n4. GULF-REGION VESSEL CALLS\n")
    f.write("-" * 80 + "\n")

    f.write(
        f"Screened calls: {len(gulf_calls)}\n"
    )

    f.write(
        f"Unique candidate vessels: {gulf_calls['IMO_17'].nunique()}\n\n"
    )

    f.write("5. AIS REVIEW REGISTER\n")
    f.write("-" * 80 + "\n")

    f.write(
        f"Records requiring AIS review: {len(ais_review)}\n"
    )

    f.write(
        f"Unique vessels requiring AIS review: "
        f"{ais_review['IMO_17'].nunique()}\n\n"
    )

    f.write("6. COVERAGE SUMMARY\n")
    f.write("-" * 80 + "\n")

    f.write(
        coverage_summary.to_string(index=False)
    )

    f.write("\n\n7. METHODOLOGICAL LIMITATIONS\n")
    f.write("-" * 80 + "\n")

    limitations = [
        "Geographic classifications are screening categories, "
        "not precise port-coordinate validation.",
        "Some LOCODEs may represent multiple facilities or ports.",
        "Country-level classifications require manual port-level review.",
        "Salalah is treated separately as an Arabian Sea port.",
        "A port call does not establish that a vessel crossed Hormuz.",
        "A port sequence does not establish a direct sailing route.",
        "No AIS latitude/longitude trajectory was supplied to this script.",
        "AIS transit verification must use timestamped vessel positions "
        "and a validated Strait geographic boundary.",
        "A final transit conclusion must preserve AIS source and "
        "data-quality limitations.",
    ]

    for limitation in limitations:
        f.write(f"- {limitation}\n")

    f.write("\n8. OUTPUT FILES\n")
    f.write("-" * 80 + "\n")

    f.write(
        "data/processed/17_port_geographic_screening.csv\n"
    )

    f.write(
        "data/processed/17_AIS_trajectory_input_template.csv\n"
    )

    f.write(
        "outputs/tables/17_ambiguous_port_locodes.csv\n"
    )

    f.write(
        "outputs/tables/17_gulf_and_approach_port_screening.csv\n"
    )

    f.write(
        "outputs/tables/17_gulf_region_vessel_calls.csv\n"
    )

    f.write(
        "outputs/tables/17_gulf_candidate_vessel_summary.csv\n"
    )

    f.write(
        "outputs/tables/17_gulf_candidate_full_port_sequences.csv\n"
    )

    f.write(
        "outputs/tables/17_AIS_priority_verification_register.csv\n"
    )

    f.write(
        "outputs/tables/17_unique_vessel_AIS_verification_register.csv\n"
    )

    f.write(
        "outputs/tables/17_AIS_data_requirements.csv\n"
    )

    f.write(
        "outputs/tables/17_port_geographic_category_summary.csv\n"
    )

    f.write(
        "outputs/tables/17_geographic_AIS_coverage_summary.csv\n"
    )


# ------------------------------------------------------------
# 22. FINAL SUMMARY
# ------------------------------------------------------------

print("\n" + "=" * 80)
print("SCRIPT 17 COMPLETED SUCCESSFULLY")
print("=" * 80)

print("\nPORT GEOGRAPHY")
print("-" * 80)

print("Port master records:", len(port_master))
print("Unique LOCODEs:", port_master["LOCODE"].nunique())
print("Ambiguous LOCODEs:", len(duplicate_locodes))
print("Screened ports:", len(screened_ports))

print("\nVESSEL SCREENING")
print("-" * 80)

print("Schedule records:", len(schedule))
print("Individual records:", len(individual))
print("Gulf-region calls:", len(gulf_calls))
print("Unique Gulf candidate vessels:", gulf_calls["IMO_17"].nunique())

print("\nAIS REVIEW")
print("-" * 80)

print("AIS review records:", len(ais_review))
print("Unique vessels requiring AIS review:", ais_review["IMO_17"].nunique())

print("\nIMPORTANT")
print("-" * 80)
print("No actual Hormuz transit is confirmed by this script.")
print("AIS trajectory evidence is still required.")
print("No original source records were deleted or modified.")

print("\nREPORT")
print(report_file)
