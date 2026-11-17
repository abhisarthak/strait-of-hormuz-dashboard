
from pathlib import Path
import pandas as pd
import zipfile
import io

# ============================================================
# 1. PROJECT PATHS
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"

REPORT_DIR = PROJECT_DIR / "outputs" / "reports"
TABLE_DIR = PROJECT_DIR / "outputs" / "tables"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
TABLE_DIR.mkdir(parents=True, exist_ok=True)

ZIP_PATH = RAW_DIR / (
    "individual_vessels-20261112T213245Z-1-001.zip"
)

SCHEDULE_PATH = RAW_DIR / "Combined_Port_Schedules.xlsx"
VESSEL_PATH = RAW_DIR / "active_vessels.csv"
PORT_PATH = RAW_DIR / "active_ports.csv"

REPORT_PATH = (
    REPORT_DIR / "04_vessel_mismatch_investigation.txt"
)

# Six files identified in Script 03
AFFECTED_FILES = [
    "individual_vessels/9307011.csv",
    "individual_vessels/9315020.csv",
    "individual_vessels/9306079.csv",
    "individual_vessels/9732307.csv",
    "individual_vessels/9948803.csv",
    "individual_vessels/9634672.csv"
]


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def section(title):

    print("\n" + "=" * 90)
    print(title)
    print("=" * 90)


def clean_id(series):

    values = series.astype("string").str.strip().str.upper()

    values = values.str.replace(
        r"\.0$",
        "",
        regex=True
    )

    return values.replace("", pd.NA)


def save_table(df, filename):

    path = TABLE_DIR / filename

    df.to_csv(path, index=False)

    print("Saved:", path.name)


def read_csv_from_zip(archive, filename):

    with archive.open(filename) as file:

        return pd.read_csv(
            io.BytesIO(file.read()),
            encoding="utf-8-sig",
            low_memory=False
        )


# ============================================================
# 3. LOAD MASTER DATASETS
# ============================================================

def load_master_datasets():

    section("LOADING MASTER DATASETS")

    schedules = pd.read_excel(SCHEDULE_PATH)

    vessels = pd.read_csv(
        VESSEL_PATH,
        encoding="utf-8-sig",
        low_memory=False
    )

    ports = pd.read_csv(
        PORT_PATH,
        encoding="utf-8-sig",
        low_memory=False
    )

    schedule_imos = set(
        clean_id(schedules["IMO Number"]).dropna()
    )

    vessel_imos = set(
        clean_id(vessels["vesselIMONumber"]).dropna()
    )

    print("Schedule IMOs:", len(schedule_imos))
    print("Active vessel IMOs:", len(vessel_imos))

    return schedules, vessels, ports, schedule_imos, vessel_imos


# ============================================================
# 4. INVESTIGATE SIX AFFECTED FILES
# ============================================================

def investigate_affected_files(
    schedule_imos,
    vessel_imos
):

    section("INVESTIGATING SIX MULTI-IMO FILES")

    file_results = []
    record_results = []

    with zipfile.ZipFile(ZIP_PATH, "r") as archive:

        available_files = set(archive.namelist())

        for filename in AFFECTED_FILES:

            print("\nInspecting:", filename)

            if filename not in available_files:

                print("FILE NOT FOUND IN ZIP")
                continue

            df = read_csv_from_zip(archive, filename)

            filename_imo = Path(filename).stem

            if "vesselIMONumber" not in df.columns:

                print("Internal IMO column missing")
                continue

            df["IMO_Normalised"] = clean_id(
                df["vesselIMONumber"]
            )

            if "vesselName" in df.columns:
                df["Vessel_Name"] = (
                    df["vesselName"].astype("string").str.strip()
                )
            else:
                df["Vessel_Name"] = pd.NA

            if "transportCallReference" in df.columns:
                df["Call_Reference"] = clean_id(
                    df["transportCallReference"]
                )
            else:
                df["Call_Reference"] = pd.NA

            if "UNLocationCode" in df.columns:
                df["Port_Code"] = clean_id(
                    df["UNLocationCode"]
                )
            else:
                df["Port_Code"] = pd.NA

            if "portName" in df.columns:
                df["Port_Name"] = df["portName"]
            else:
                df["Port_Name"] = pd.NA

            internal_imos = sorted(
                df["IMO_Normalised"].dropna().unique().tolist()
            )

            print("Filename IMO:", filename_imo)
            print("Internal IMOs:", internal_imos)
            print("Total records:", len(df))

            # File-level summary

            file_results.append({
                "File": filename,
                "Filename_IMO": filename_imo,
                "Internal_IMOs": "; ".join(internal_imos),
                "Unique_Internal_IMOs": len(internal_imos),
                "Total_Records": len(df),
                "Filename_IMO_Matches": (
                    filename_imo in internal_imos
                )
            })

            # Record-level investigation

            for imo, group in df.groupby(
                "IMO_Normalised",
                dropna=False
            ):

                valid_imo = (
                    pd.notna(imo) and str(imo).strip() != ""
                )

                names = sorted(
                    group["Vessel_Name"].dropna().astype(str).unique()
                )

                ports = sorted(
                    group["Port_Code"].dropna().astype(str).unique()
                )

                record_results.append({

                    "Source_File": filename,
                    "Filename_IMO": filename_imo,
                    "Internal_IMO": imo,
                    "Record_Count": len(group),
                    "Vessel_Names": "; ".join(names),
                    "Port_Codes": "; ".join(ports),
                    "Unique_Call_References": (
                        group["Call_Reference"].nunique(dropna=True)
                    ),
                    "Missing_IMO": not valid_imo,
                    "In_Schedule_Master": (
                        imo in schedule_imos if valid_imo else False
                    ),
                    "In_Active_Vessel_Master": (
                        imo in vessel_imos if valid_imo else False
                    )
                })

    file_df = pd.DataFrame(file_results)
    record_df = pd.DataFrame(record_results)

    save_table(
        file_df,
        "04_affected_file_summary.csv"
    )

    save_table(
        record_df,
        "04_affected_imo_record_summary.csv"
    )

    return file_df, record_df


# ============================================================
# 5. SAVE DETAILED PORT-CALL RECORDS
# ============================================================

def extract_affected_records():

    section("EXTRACTING DETAILED AFFECTED RECORDS")

    detailed_frames = []

    with zipfile.ZipFile(ZIP_PATH, "r") as archive:

        for filename in AFFECTED_FILES:

            if filename not in archive.namelist():
                continue

            df = read_csv_from_zip(archive, filename)

            df["archive_source_file"] = filename

            if "vesselIMONumber" in df.columns:

                df["IMO_Normalised"] = clean_id(
                    df["vesselIMONumber"]
                )

            detailed_frames.append(df)

    if not detailed_frames:
        print("No affected records extracted.")
        return pd.DataFrame()

    detailed_df = pd.concat(
        detailed_frames,
        ignore_index=True,
        sort=False
    )

    save_table(
        detailed_df,
        "04_six_affected_files_detailed_records.csv"
    )

    print("Total affected records:", len(detailed_df))

    return detailed_df


# ============================================================
# 6. CHECK TRANSPORT CALL REFERENCES
# ============================================================

def investigate_call_references(detailed_df):

    section("TRANSPORT CALL REFERENCE INVESTIGATION")

    if detailed_df.empty:
        return

    if "transportCallReference" not in detailed_df.columns:
        print("Transport call reference column missing.")
        return

    if "IMO_Normalised" not in detailed_df.columns:
        print("Normalised IMO column missing.")
        return

    df = detailed_df.copy()

    df["Call_Reference_Normalised"] = clean_id(
        df["transportCallReference"]
    )

    mapping = (
        df.dropna(subset=["Call_Reference_Normalised"])
        .groupby("Call_Reference_Normalised")
        .agg(
            Record_Count=("Call_Reference_Normalised", "size"),
            Unique_IMOs=("IMO_Normalised", "nunique"),
            IMOs=("IMO_Normalised", lambda x:
                  "; ".join(sorted(set(x.dropna().astype(str))))),
            Source_Files=("archive_source_file", lambda x:
                          "; ".join(sorted(set(x.dropna().astype(str)))))
        )
        .reset_index()
    )

    conflicts = mapping[
        mapping["Unique_IMOs"] > 1
    ]

    print("Total unique references:", len(mapping))
    print("References linked to multiple IMOs:", len(conflicts))

    save_table(
        mapping,
        "04_affected_call_reference_mapping.csv"
    )

    save_table(
        conflicts,
        "04_call_reference_imo_conflicts.csv"
    )


# ============================================================
# 7. INVESTIGATE VESSEL NAME CONFLICTS
# ============================================================

def investigate_vessel_name_conflicts(vessels):

    section("INVESTIGATING VESSEL NAME CONFLICTS")

    df = vessels.copy()

    df["IMO_Normalised"] = clean_id(
        df["vesselIMONumber"]
    )

    df["Vessel_Name_Normalised"] = (
        df["vesselName"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    mapping = (
        df.dropna(subset=["IMO_Normalised"])
        .groupby("IMO_Normalised")
        .agg(
            Record_Count=("IMO_Normalised", "size"),
            Unique_Names=("Vessel_Name_Normalised", "nunique"),
            Vessel_Names=("Vessel_Name_Normalised", lambda x:
                          "; ".join(sorted(set(x.dropna())))),
            Carrier_Codes=("carrierVesselCode", lambda x:
                           "; ".join(sorted(set(x.dropna().astype(str)))))
        )
        .reset_index()
    )

    conflicts = mapping[
        mapping["Unique_Names"] > 1
    ]

    print("IMOs with multiple names:", len(conflicts))

    save_table(
        conflicts,
        "04_vessel_name_conflicts_detailed.csv"
    )


# ============================================================
# 8. INVESTIGATE DUPLICATE PORT CODES
# ============================================================

def investigate_duplicate_port_codes(ports):

    section("INVESTIGATING DUPLICATE PORT CODES")

    df = ports.copy()

    df["LOCODE_Normalised"] = clean_id(
        df["UNLocationCode"]
    )

    mapping = (
        df.dropna(subset=["LOCODE_Normalised"])
        .groupby("LOCODE_Normalised")
        .agg(
            Record_Count=("LOCODE_Normalised", "size"),
            Port_Names=("portName", lambda x:
                        "; ".join(sorted(set(x.dropna().astype(str))))),
            Countries=("countryCode", lambda x:
                       "; ".join(sorted(set(x.dropna().astype(str)))))
        )
        .reset_index()
    )

    duplicates = mapping[
        mapping["Record_Count"] > 1
    ]

    print("Duplicate port code groups:", len(duplicates))

    save_table(
        duplicates,
        "04_duplicate_port_codes_detailed.csv"
    )


# ============================================================
# 9. MAIN EXECUTION
# ============================================================

def main():

    section("STRAIT OF HORMUZ - MISMATCH INVESTIGATION")

    (
        schedules,
        vessels,
        ports,
        schedule_imos,
        vessel_imos
    ) = load_master_datasets()

    file_df, record_df = investigate_affected_files(
        schedule_imos,
        vessel_imos
    )

    detailed_df = extract_affected_records()

    investigate_call_references(detailed_df)

    investigate_vessel_name_conflicts(vessels)

    investigate_duplicate_port_codes(ports)

    section("INVESTIGATION COMPLETED")

    print("All diagnostic tables saved in:", TABLE_DIR)


# ============================================================
# 10. SAVE REPORT
# ============================================================

if __name__ == "__main__":

    import contextlib

    with open(
        REPORT_PATH,
        "w",
        encoding="utf-8"
    ) as report:

        with contextlib.redirect_stdout(report):
            main()

    print("VESSEL MISMATCH INVESTIGATION COMPLETED")
    print("\nReport saved at:")
    print(REPORT_PATH)