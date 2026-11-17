"""
SCRIPT 60: NETWORK INTEGRATION SOURCE DISCOVERY AND SCHEMA AUDIT
----------------------------------------------------------------
Read-only discovery of existing network-related CSV files.

Purpose:
    Identify the actual node/port inventory, directed-edge, observed-transition,
    simulation-input and historical-baseline files in this project. This avoids
    guessing filenames or assuming that similarly named files have identical
    semantics.

Scans:
    outputs/tables/
    data/ (if present)

Outputs:
    outputs/reports/60_network_source_discovery.csv
    outputs/reports/60_network_source_discovery_report.txt

No source files are modified.
No network nodes or edges are created.
No simulation inputs are changed.
"""

from pathlib import Path
import pandas as pd
import re

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = [ROOT / "outputs" / "tables", ROOT / "data"]
REPORT_DIR = ROOT / "outputs" / "reports"

CSV_OUTPUT = REPORT_DIR / "60_network_source_discovery.csv"
TXT_OUTPUT = REPORT_DIR / "60_network_source_discovery_report.txt"

KEYWORDS = {
    "node_inventory": [
        "node", "port", "location", "terminal", "master", "coordinate",
        "eligibility", "identity", "geograph"
    ],
    "directed_edges": [
        "edge", "network", "route", "arc", "link", "inter_port", "transition"
    ],
    "observed_transitions": [
        "observed_transition", "transition", "voyage", "movement", "sequence"
    ],
    "historical_baseline": [
        "historical", "baseline", "schedule", "port_call", "call"
    ],
    "simulation_inputs": [
        "simulation", "sim_input", "parameter", "service", "vessel"
    ],
}

COLUMN_PATTERNS = {
    "possible_node_identifier": [
        r"^unlocode$", r"port.?code", r"node.?id", r"location.?id"
    ],
    "possible_node_name": [
        r"port.?name", r"location.?name", r"terminal.?name"
    ],
    "possible_latitude": [r"latitude", r"(^|_)lat($|_)"],
    "possible_longitude": [r"longitude", r"(^|_)lon(g)?($|_)"],
    "possible_edge_origin": [
        r"origin", r"source", r"from.?node", r"from.?port", r"origin.?port"
    ],
    "possible_edge_destination": [
        r"destination", r"target", r"to.?node", r"to.?port", r"destination.?port"
    ],
    "possible_timestamp": [
        r"timestamp", r"arrival", r"departure", r"date", r"time"
    ],
    "possible_vessel_identifier": [
        r"vessel", r"imo", r"mmsi", r"ship.?id"
    ],
}


def normalize(text):
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def classify_filename(filename):
    name = normalize(filename)
    matches = []
    for category, words in KEYWORDS.items():
        if any(normalize(word) in name for word in words):
            matches.append(category)
    return ";".join(matches) if matches else "unclassified"


def inspect_columns(columns):
    normalized = [normalize(c) for c in columns]
    detected = []
    for label, patterns in COLUMN_PATTERNS.items():
        if any(
            re.search(pattern, col)
            for pattern in patterns
            for col in normalized
        ):
            detected.append(label)
    return ";".join(detected)


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    seen = set()

    for directory in SCAN_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.csv")):
            if path in seen:
                continue
            seen.add(path)
            try:
                # Header-only read first, then count records without retaining data.
                header = pd.read_csv(path, nrows=0)
                columns = list(header.columns)
                try:
                    row_count = sum(
                        1 for _ in pd.read_csv(path, usecols=[columns[0]], chunksize=100000)
                        for _ in _.itertuples(index=False, name=None)
                    ) if columns else 0
                    read_status = "OK"
                except Exception as exc:
                    row_count = -1
                    read_status = f"ROW_COUNT_ERROR: {type(exc).__name__}: {exc}"

                rel_path = str(path.relative_to(ROOT))
                rows.append({
                    "File": path.name,
                    "Relative_Path": rel_path,
                    "Directory": str(path.parent.relative_to(ROOT)),
                    "Rows": row_count,
                    "Columns_Count": len(columns),
                    "Filename_Category_Hints": classify_filename(path.stem),
                    "Schema_Category_Hints": inspect_columns(columns),
                    "Columns": " | ".join(map(str, columns)),
                    "Read_Status": read_status,
                })
            except Exception as exc:
                rows.append({
                    "File": path.name,
                    "Relative_Path": str(path.relative_to(ROOT)),
                    "Directory": str(path.parent.relative_to(ROOT)),
                    "Rows": -1,
                    "Columns_Count": 0,
                    "Filename_Category_Hints": classify_filename(path.stem),
                    "Schema_Category_Hints": "",
                    "Columns": "",
                    "Read_Status": f"HEADER_READ_ERROR: {type(exc).__name__}: {exc}",
                })

    result = pd.DataFrame(rows)
    if result.empty:
        result = pd.DataFrame(columns=[
            "File", "Relative_Path", "Directory", "Rows", "Columns_Count",
            "Filename_Category_Hints", "Schema_Category_Hints", "Columns",
            "Read_Status"
        ])

    result.to_csv(CSV_OUTPUT, index=False)

    with TXT_OUTPUT.open("w", encoding="utf-8") as f:
        f.write("=" * 88 + "\n")
        f.write("SCRIPT 60: NETWORK INTEGRATION SOURCE DISCOVERY AND SCHEMA AUDIT\n")
        f.write("=" * 88 + "\n\n")
        f.write(f"Project root: {ROOT}\n")
        f.write("Scan locations:\n")
        for directory in SCAN_DIRS:
            f.write(f"- {directory}\n")
        f.write(f"\nCSV files discovered: {len(result)}\n")
        f.write(f"Files read successfully: {int(result['Read_Status'].eq('OK').sum()) if len(result) else 0}\n")
        f.write("\nDISCOVERY INVENTORY\n")
        if len(result):
            f.write(result[[
                "Relative_Path", "Rows", "Columns_Count",
                "Filename_Category_Hints", "Schema_Category_Hints", "Read_Status"
            ]].to_string(index=False))
        else:
            f.write("No CSV files found in the scanned directories.\n")
        f.write("\n\nIMPORTANT\n")
        f.write(
            "Filename and schema hints are discovery aids only. They do not establish "
            "that a file is the authoritative node inventory, directed-edge list, "
            "observed-transition table, or simulation input. Those roles must be "
            "confirmed from the actual schemas and upstream script lineage.\n"
            "This script is read-only and does not modify source data or network files.\n"
        )

    print("=" * 88)
    print("SCRIPT 60: NETWORK INTEGRATION SOURCE DISCOVERY AND SCHEMA AUDIT")
    print("=" * 88)
    print(f"Project root: {ROOT}")
    print(f"CSV files discovered: {len(result)}")
    if len(result):
        print(f"Files read successfully: {int(result['Read_Status'].eq('OK').sum())}")
        print("\nDISCOVERY RESULTS")
        print(result[[
            "Relative_Path", "Rows", "Columns_Count",
            "Filename_Category_Hints", "Schema_Category_Hints", "Read_Status"
        ]].to_string(index=False))
    print("\nOUTPUTS")
    print(CSV_OUTPUT.relative_to(ROOT))
    print(TXT_OUTPUT.relative_to(ROOT))
    print("\nREAD-ONLY CHECK: source files were not modified.")
    print("SCRIPT 60 COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()
