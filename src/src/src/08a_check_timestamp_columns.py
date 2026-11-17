
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

files = {
    "INDIVIDUAL_SCRIPT_06": ROOT / "data/processed/06_individual_vessel_port_calls.csv",
    "SCHEDULE_SCRIPT_06": ROOT / "data/processed/06_integrated_schedule_vessel_port.csv",
    "INDIVIDUAL_SCRIPT_07": ROOT / "outputs/tables/07_individual_port_call_sequences.csv",
    "SCHEDULE_SCRIPT_07": ROOT / "outputs/tables/07_schedule_port_call_sequences.csv",
}

for name, path in files.items():

    print("\n" + "=" * 80)
    print(name)
    print("=" * 80)

    if not path.exists():
        print("FILE NOT FOUND:", path)
        continue

    df = pd.read_csv(path, nrows=5, low_memory=False)

    print("Rows inspected:", len(df))
    print("Columns:")

    for col in df.columns:
        print(" -", col)
