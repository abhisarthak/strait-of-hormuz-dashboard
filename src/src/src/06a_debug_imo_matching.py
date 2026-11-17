
from pathlib import Path
from zipfile import ZipFile
import pandas as pd
import re

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

schedule = pd.read_excel(
    RAW / "Combined_Port_Schedules.xlsx"
)

vessels = pd.read_csv(
    RAW / "active_vessels.csv"
)

zip_path = next(RAW.glob("individual_vessels*.zip"))


def normalize_imo(series):
    result = (
        series.astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )

    # Remove a trailing .0 from numeric-looking IMO values.
    result = result.str.replace(r"\.0$", "", regex=True)

    return result


print("=" * 65)
print("IMO MATCHING DIAGNOSTIC")
print("=" * 65)

print("\nSCHEDULE COLUMNS:")
print(schedule.columns.tolist())

print("\nVESSEL MASTER COLUMNS:")
print(vessels.columns.tolist())


# Identify columns using the actual source headers.
schedule_imo_col = next(
    c for c in schedule.columns
    if re.sub(r"[^a-z0-9]", "", c.lower())
    in ["imonumber", "vesselimo", "vesselimonumber"]
)

vessel_imo_col = "vesselIMONumber"

print("\nSelected schedule IMO column:", schedule_imo_col)
print("Selected vessel master IMO column:", vessel_imo_col)

schedule_imos = set(
    normalize_imo(schedule[schedule_imo_col]).dropna()
)

master_imos = set(
    normalize_imo(vessels[vessel_imo_col]).dropna()
)

print("\nSCHEDULE IMO SAMPLE:")
print(sorted(schedule_imos)[:20])

print("\nVESSEL MASTER IMO SAMPLE:")
print(sorted(master_imos)[:20])

print("\nSCHEDULE vs MASTER:")
print("Schedule unique IMOs:", len(schedule_imos))
print("Master unique IMOs:", len(master_imos))
print("Matching IMOs:", len(schedule_imos & master_imos))


# Read individual vessel files.
individual_frames = []

with ZipFile(zip_path, "r") as archive:

    for filename in archive.namelist():

        if filename.lower().endswith(".csv"):

            with archive.open(filename) as file:
                df = pd.read_csv(file)

            df.columns = df.columns.astype(str).str.strip()

            individual_frames.append(df)

individual = pd.concat(
    individual_frames,
    ignore_index=True,
    sort=False
)

print("\nINDIVIDUAL FILE COLUMNS:")
print(individual.columns.tolist())

individual_imo_col = next(
    c for c in individual.columns
    if re.sub(r"[^a-z0-9]", "", c.lower())
    in [
        "vesselimo",
        "vesselimonumber",
        "imo",
        "imonumber"
    ]
)

print("\nSelected individual IMO column:", individual_imo_col)

individual_imos = set(
    normalize_imo(individual[individual_imo_col]).dropna()
)

print("\nINDIVIDUAL IMO SAMPLE:")
print(sorted(individual_imos)[:30])

print("\nINDIVIDUAL MATCHING:")
print("Individual unique IMOs:", len(individual_imos))
print("Schedule matches:", len(schedule_imos & individual_imos))
print("Master matches:", len(master_imos & individual_imos))

print("\nSchedule-only sample:")
print(sorted(schedule_imos - individual_imos)[:20])

print("\nIndividual-only sample:")
print(sorted(individual_imos - schedule_imos)[:20])

print("\nDIAGNOSTIC COMPLETED")
