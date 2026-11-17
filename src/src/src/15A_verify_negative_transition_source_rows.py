
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

RAW_FILE = ROOT / "data" / "raw" / "Combined_Port_Schedules.xlsx"
NEGATIVE_FILE = ROOT / "outputs" / "tables" / "15_negative_transition_investigation.csv"

raw = pd.read_excel(RAW_FILE)
negative = pd.read_csv(NEGATIVE_FILE)

# Identify the original Excel columns.
imo_col = "IMO"
port_col = "Port"
locode_col = "UN/LOCODE"
service_col = "Service Code"

print("Original Excel columns:")
print(raw.columns.tolist())

# Inspect each negative transition.
for _, row in negative.iterrows():

    previous_source = int(row["Previous_Source_Row"])
    current_source = int(row["Current_Source_Row"])

    print("\n" + "=" * 90)
    print(f"IMO: {row['IMO']} | Vessel: {row['Vessel_Name']}")
    print(f"Previous source row: {previous_source}")
    print(f"Current source row: {current_source}")
    print(f"Elapsed hours: {row['Inter_Port_Elapsed_Hours']}")

    # Schedule_Source_Row is a 1-based data row position.
    previous = raw.iloc[previous_source - 1]
    current = raw.iloc[current_source - 1]

    comparison_columns = [
        imo_col,
        port_col,
        locode_col,
        service_col,
        "Import Voyage",
        "Export Voyage",
        "Planned Arrival",
        "Planned Departure",
        "Estimated Arrival",
        "Estimated Departure",
        "Actual Arrival",
        "Actual Departure",
    ]

    # Keep only columns actually present in the Excel file.
    comparison_columns = [
        col for col in comparison_columns
        if col in raw.columns
    ]

    comparison = pd.DataFrame({
        "Previous_Record": previous[comparison_columns],
        "Current_Record": current[comparison_columns],
    })

    comparison["Values_Match"] = (
        comparison["Previous_Record"].astype("string").fillna("<NA>")
        ==
        comparison["Current_Record"].astype("string").fillna("<NA>")
    )

    print(comparison.to_string())


print("\n" + "=" * 90)
print("SOURCE VERIFICATION COMPLETED")
