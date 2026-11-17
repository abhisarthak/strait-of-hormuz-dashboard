
from pathlib import Path

import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt


# ============================================================
# SCRIPT 21: MARITIME NETWORK ANALYSIS
# Strait of Hormuz Research
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

INPUT_DIR = ROOT / "data" / "simulation_inputs"
OUTPUT_DIR = ROOT / "outputs"
TABLE_DIR = OUTPUT_DIR / "tables"
FIGURE_DIR = OUTPUT_DIR / "figures"
REPORT_DIR = OUTPUT_DIR / "reports"

for folder in [TABLE_DIR, FIGURE_DIR, REPORT_DIR]:
    folder.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------
# 1. LOAD INPUT DATA
# ------------------------------------------------------------

print("=" * 65)
print("SCRIPT 21: MARITIME NETWORK ANALYSIS")
print("=" * 65)

ports = pd.read_csv(INPUT_DIR / "19_port_parameters.csv")
edges = pd.read_csv(INPUT_DIR / "19_interport_time_parameters.csv")

required_port_columns = [
    "UNLOCODE_Normalised",
    "observed_port_name",
    "observed_call_count",
    "observed_vessel_count",
]

required_edge_columns = [
    "Previous_Port",
    "Next_Port",
    "sample_size",
    "mean_elapsed_hours",
]

for col in required_port_columns:
    if col not in ports.columns:
        raise ValueError(f"Missing port column: {col}")

for col in required_edge_columns:
    if col not in edges.columns:
        raise ValueError(f"Missing edge column: {col}")


# ------------------------------------------------------------
# 2. CLEAN AND VALIDATE
# ------------------------------------------------------------

print("\n[1/7] Validating input data...")

ports["UNLOCODE_Normalised"] = (
    ports["UNLOCODE_Normalised"].astype("string").str.strip().str.upper()
)

edges["Previous_Port"] = (
    edges["Previous_Port"].astype("string").str.strip().str.upper()
)

edges["Next_Port"] = (
    edges["Next_Port"].astype("string").str.strip().str.upper()
)

edges["sample_size"] = pd.to_numeric(
    edges["sample_size"], errors="coerce"
)

edges["mean_elapsed_hours"] = pd.to_numeric(
    edges["mean_elapsed_hours"], errors="coerce"
)

ports["observed_call_count"] = pd.to_numeric(
    ports["observed_call_count"], errors="coerce"
)

ports["observed_vessel_count"] = pd.to_numeric(
    ports["observed_vessel_count"], errors="coerce"
)

edges = edges.dropna(
    subset=[
        "Previous_Port",
        "Next_Port",
        "sample_size",
        "mean_elapsed_hours",
    ]
).copy()

edges = edges[
    (edges["sample_size"] > 0)
    & (edges["mean_elapsed_hours"] >= 0)
].copy()

if ports["UNLOCODE_Normalised"].duplicated().any():
    raise ValueError("Duplicate port identifiers found.")

if edges.duplicated(["Previous_Port", "Next_Port"]).any():
    raise ValueError("Duplicate aggregated port pairs found.")

print("Port records:", len(ports))
print("Aggregated connections:", len(edges))


# ------------------------------------------------------------
# 3. BUILD DIRECTED NETWORK
# ------------------------------------------------------------

print("\n[2/7] Building directed maritime network...")

G = nx.DiGraph()

# Add every observed port, including ports without edges.
for _, row in ports.iterrows():

    locode = row["UNLOCODE_Normalised"]

    G.add_node(
        locode,
        port_name=row["observed_port_name"],
        call_count=row["observed_call_count"],
        vessel_count=row["observed_vessel_count"],
    )

# Add observed directed connections.
for _, row in edges.iterrows():

    origin = row["Previous_Port"]
    destination = row["Next_Port"]

    G.add_edge(
        origin,
        destination,
        sample_size=int(row["sample_size"]),
        mean_elapsed_hours=float(row["mean_elapsed_hours"]),
    )

print("Network nodes:", G.number_of_nodes())
print("Network edges:", G.number_of_edges())


# ------------------------------------------------------------
# 4. CONNECTIVITY ANALYSIS
# ------------------------------------------------------------

print("\n[3/7] Analysing network connectivity...")

weak_components = list(nx.weakly_connected_components(G))
strong_components = list(nx.strongly_connected_components(G))

isolated_ports = list(nx.isolates(G))

largest_weak_component = max(
    weak_components, key=len
) if weak_components else set()

largest_strong_component = max(
    strong_components, key=len
) if strong_components else set()

print("Weakly connected components:", len(weak_components))
print("Strongly connected components:", len(strong_components))
print("Isolated ports:", len(isolated_ports))
print("Largest weak component:", len(largest_weak_component))
print("Largest strong component:", len(largest_strong_component))


# ------------------------------------------------------------
# 5. PORT CENTRALITY AND ACTIVITY
# ------------------------------------------------------------

print("\n[4/7] Calculating port network metrics...")

in_degree = dict(G.in_degree())
out_degree = dict(G.out_degree())

in_strength = dict(G.in_degree(weight="sample_size"))
out_strength = dict(G.out_degree(weight="sample_size"))

betweenness = nx.betweenness_centrality(
    G, normalized=True, weight=None
)

port_metrics = []

for node in G.nodes():

    attributes = G.nodes[node]

    port_metrics.append({
        "UNLOCODE": node,
        "Port_Name": attributes.get("port_name"),
        "Observed_Call_Count": attributes.get("call_count"),
        "Observed_Vessel_Count": attributes.get("vessel_count"),
        "In_Degree": in_degree[node],
        "Out_Degree": out_degree[node],
        "Total_Degree": in_degree[node] + out_degree[node],
        "Incoming_Transition_Count": in_strength[node],
        "Outgoing_Transition_Count": out_strength[node],
        "Betweenness_Centrality": betweenness[node],
        "Is_Isolated": node in isolated_ports,
    })

port_metrics = pd.DataFrame(port_metrics)

port_metrics = port_metrics.sort_values(
    ["Observed_Call_Count", "Betweenness_Centrality"],
    ascending=False
)

port_metrics.to_csv(
    TABLE_DIR / "21_port_network_metrics.csv",
    index=False
)


# ------------------------------------------------------------
# 6. EDGE ANALYSIS
# ------------------------------------------------------------

print("\n[5/7] Preparing connection metrics...")

edge_metrics = edges.copy()

edge_metrics["Observed_Transition_Count"] = (
    edge_metrics["sample_size"]
)

edge_metrics["Mean_Elapsed_Time_Hours"] = (
    edge_metrics["mean_elapsed_hours"]
)

edge_metrics["Interpretation"] = (
    "Observed inter-port elapsed time, not pure sailing time"
)

edge_metrics = edge_metrics.sort_values(
    "sample_size", ascending=False
)

edge_metrics.to_csv(
    TABLE_DIR / "21_port_connection_metrics.csv",
    index=False
)


# ------------------------------------------------------------
# 7. NETWORK VISUALISATION AND REPORT
# ------------------------------------------------------------

print("\n[6/7] Creating network visualisation...")

plt.figure(figsize=(16, 12))

position = nx.spring_layout(
    G,
    seed=42,
    k=1.3,
    iterations=150
)

node_sizes = [
    350 + 100 * (G.nodes[n].get("call_count") or 0)
    for n in G.nodes()
]

nx.draw_networkx_nodes(
    G,
    position,
    node_size=node_sizes,
    alpha=0.85
)

nx.draw_networkx_edges(
    G,
    position,
    arrows=True,
    arrowsize=15,
    width=1.4,
    alpha=0.55,
    connectionstyle="arc3,rad=0.08"
)

nx.draw_networkx_labels(
    G,
    position,
    font_size=8,
    font_weight="bold"
)

plt.title(
    "Observed Maritime Port Network\n"
    "Conservative Schedule Baseline",
    fontsize=16
)

plt.axis("off")
plt.tight_layout()

plt.savefig(
    FIGURE_DIR / "21_maritime_port_network.png",
    dpi=300,
    bbox_inches="tight"
)

plt.close()


# Network connectivity summary
summary = {
    "Total_Ports": G.number_of_nodes(),
    "Total_Directed_Connections": G.number_of_edges(),
    "Weakly_Connected_Components": len(weak_components),
    "Strongly_Connected_Components": len(strong_components),
    "Isolated_Ports": len(isolated_ports),
    "Largest_Weak_Component_Size": len(largest_weak_component),
    "Largest_Strong_Component_Size": len(largest_strong_component),
    "Directed_Density": nx.density(G),
    "Average_In_Degree": sum(in_degree.values()) / max(len(G), 1),
    "Average_Out_Degree": sum(out_degree.values()) / max(len(G), 1),
}

summary_df = pd.DataFrame(
    list(summary.items()),
    columns=["Metric", "Value"]
)

summary_df.to_csv(
    TABLE_DIR / "21_network_connectivity_summary.csv",
    index=False
)

with open(
    REPORT_DIR / "21_maritime_network_analysis_report.txt",
    "w",
    encoding="utf-8"
) as report:

    report.write("MARITIME NETWORK ANALYSIS\n")
    report.write("=" * 50 + "\n\n")

    for metric, value in summary.items():
        report.write(f"{metric}: {value}\n")

    report.write("\nWEAKLY CONNECTED COMPONENTS\n")

    for i, component in enumerate(weak_components, start=1):
        report.write(
            f"\nComponent {i}: {sorted(component)}\n"
        )

    report.write("\nSTRONGLY CONNECTED COMPONENTS\n")

    for i, component in enumerate(strong_components, start=1):
        report.write(
            f"\nComponent {i}: {sorted(component)}\n"
        )

    report.write(
        "\nINTERPRETATION LIMITATIONS\n"
        "1. Network edges represent observed port-call transitions.\n"
        "2. They do not prove direct sailing routes.\n"
        "3. Centrality is a structural network indicator.\n"
        "4. High degree does not establish physical port capacity.\n"
        "5. Elapsed times are not pure sailing times.\n"
        "6. This network does not confirm Strait of Hormuz transit.\n"
    )

print("\n[7/7] Saving results...")

print("\nTOP PORTS BY OBSERVED CALL COUNT:")
print(
    port_metrics[
        ["UNLOCODE", "Port_Name", "Observed_Call_Count",
         "In_Degree", "Out_Degree", "Betweenness_Centrality"]
    ].head(10).to_string(index=False)
)

print("\nTOP OBSERVED CONNECTIONS:")
print(
    edge_metrics[
        ["Previous_Port", "Next_Port", "sample_size",
         "mean_elapsed_hours"]
    ].head(10).to_string(index=False)
)

print("\nCONNECTIVITY SUMMARY:")
print(summary_df.to_string(index=False))

print("\n" + "=" * 65)
print("SCRIPT 21 COMPLETED SUCCESSFULLY")
print("=" * 65)

print("\nGenerated:")
print("- outputs/tables/21_port_network_metrics.csv")
print("- outputs/tables/21_port_connection_metrics.csv")
print("- outputs/tables/21_network_connectivity_summary.csv")
print("- outputs/figures/21_maritime_port_network.png")
print("- outputs/reports/21_maritime_network_analysis_report.txt")
