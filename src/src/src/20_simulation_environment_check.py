
from pathlib import Path
import sys

import pandas as pd
import numpy as np
import simpy
import networkx as nx
import matplotlib
import scipy

# Project directories
ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "simulation_inputs"

print("=" * 65)
print("STRAIT OF HORMUZ - PYTHON SIMULATION ENVIRONMENT")
print("=" * 65)

# 1. Software verification
print("\n1. LIBRARY VERSIONS")
print("-" * 40)

print("Python:", sys.version.split()[0])
print("Pandas:", pd.__version__)
print("NumPy:", np.__version__)
print("SimPy:", simpy.__version__)
print("NetworkX:", nx.__version__)
print("Matplotlib:", matplotlib.__version__)
print("SciPy:", scipy.__version__)

# 2. Input file verification
print("\n2. SCRIPT 19 INPUT FILES")
print("-" * 40)

files = {
    "Historical schedule": "19_historical_arrival_schedule.csv",
    "Vessel parameters": "19_vessel_parameters.csv",
    "Port parameters": "19_port_parameters.csv",
    "Port service parameters": "19_port_service_parameters.csv",
    "Inter-port parameters": "19_interport_time_parameters.csv",
    "Observed transitions": "19_observed_interport_transitions.csv",
    "Disruption scenarios": "19_disruption_scenarios.csv",
}

datasets = {}

for name, filename in files.items():
    path = INPUT_DIR / filename

    if not path.exists():
        print(f"[MISSING] {filename}")
        continue

    df = pd.read_csv(path)
    datasets[name] = df

    print(f"[OK] {name}: {df.shape}")

# 3. Basic network verification
print("\n3. MARITIME NETWORK CHECK")
print("-" * 40)

if "Observed transitions" in datasets:
    transitions = datasets["Observed transitions"]

    required = ["Previous_Port", "Next_Port"]

    if all(col in transitions.columns for col in required):
        G = nx.DiGraph()

        for _, row in transitions.iterrows():
            G.add_edge(
                row["Previous_Port"],
                row["Next_Port"]
            )

        print("Network nodes:", G.number_of_nodes())
        print("Network edges:", G.number_of_edges())
        print("Is directed:", G.is_directed())
        print("Is connected:", nx.is_weakly_connected(G))

        print("\nPorts:")
        print(sorted(G.nodes()))

    else:
        print("Required transition columns are missing.")

# 4. Historical schedule verification
print("\n4. HISTORICAL SCHEDULE CHECK")
print("-" * 40)

if "Historical schedule" in datasets:
    df = datasets["Historical schedule"]

    print("Historical records:", len(df))

    if "IMO_Normalised" in df.columns:
        print("Unique vessels:", df["IMO_Normalised"].nunique())

    if "UNLOCODE_Normalised" in df.columns:
        print("Unique ports:", df["UNLOCODE_Normalised"].nunique())

    if "Actual_Arrival_UTC" in df.columns:
        print("Arrival timestamps:", df["Actual_Arrival_UTC"].notna().sum())

# 5. Completion
print("\n" + "=" * 65)
print("ENVIRONMENT CHECK COMPLETED")
print("=" * 65)
