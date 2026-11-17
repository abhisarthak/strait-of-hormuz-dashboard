from pathlib import Path
import os, json
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv

from services.live_data import (
    load_news, load_eia_series, load_status_record, load_portwatch_csv,
    load_ais_csv, source_health
)
from services.simulation import load_primary, load_script77_summary, scenario_filter

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

st.set_page_config(page_title="Strait of Hormuz | Maritime Intelligence & Research", page_icon="🌊",
                   layout="wide", initial_sidebar_state="expanded")

NAVY = "#071827"
PANEL = "#10283B"
TEAL = "#23C6B7"
CYAN = "#58D8E8"
ORANGE = "#F4A261"
RED = "#E76F51"
MUTED = "#9FB3C8"

st.markdown("""
<style>
:root{color-scheme:dark}
.stApp{background:linear-gradient(135deg,#071827 0%,#0a2032 55%,#0c2b3c 100%);color:#e8f1f8}
[data-testid="stSidebar"]{background:#081b2a;border-right:1px solid #1b4055}
.block-container{padding-top:1.3rem;padding-bottom:2rem;max-width:1500px}
h1,h2,h3{color:#eff8ff}
.hero{background:linear-gradient(110deg,#0c2a40,#124b5b);padding:26px 30px;border:1px solid #23536a;border-radius:18px;margin-bottom:18px}
.eyebrow{color:#65d8d1;text-transform:uppercase;letter-spacing:2px;font-size:11px;font-weight:700}
.hero h1{font-size:31px;margin:7px 0}
.hero p{color:#c3d7e5;margin:0}
.card{background:#10283b;border:1px solid #23465b;border-radius:14px;padding:17px 18px;min-height:112px}
.klabel{color:#9fb3c8;text-transform:uppercase;letter-spacing:1px;font-size:10px;font-weight:700}
.kvalue{font-size:27px;font-weight:750;color:#f3fbff;margin-top:8px}
.khelp{font-size:11px;color:#8fa9bc;margin-top:4px}
.note{background:#122e40;border-left:3px solid #23c6b7;border-radius:7px;padding:12px 15px;color:#c8dce8;font-size:13px}
.warn{background:#3a2a1c;border-left:3px solid #f4a261;border-radius:7px;padding:12px 15px;color:#f5dfc8;font-size:13px}
.smallmuted{font-size:12px;color:#9fb3c8}
a{color:#58d8e8!important}
div[data-testid="stMetric"]{background:#10283b;border:1px solid #23465b;padding:13px;border-radius:12px}
div[data-testid="stMetricLabel"]{color:#9fb3c8}
</style>
""", unsafe_allow_html=True)

def hero(kicker, title, subtitle):
    st.markdown(f'<div class="hero"><div class="eyebrow">{kicker}</div><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)

def card(label, value, help_text=""):
    st.markdown(f'<div class="card"><div class="klabel">{label}</div><div class="kvalue">{value}</div><div class="khelp">{help_text}</div></div>', unsafe_allow_html=True)

pages = [
    "Overview",
    "1 · Live Situation",
    "2 · Vessel Traffic",
    "3 · News & Events",
    "4 · Energy Impact",
    "5 · Research Simulation",
    "6 · Methodology & Limits",
]
with st.sidebar:
    st.markdown("## 🌊 HORMUZ / INTEL")
    st.caption("M.Tech ORDA · IIT Kharagpur")
    page = st.radio("NAVIGATION", pages, label_visibility="collapsed")
    st.divider()
    st.caption("DATA LAYERS")
    st.markdown("🟢 Research outputs · local")
    st.markdown("🟡 External sources · refreshable")
    st.markdown("🔴 Live AIS · credentials/data required")
    st.divider()
    st.caption("Build 2 · Academic demonstration")

status = load_status_record(ROOT)
primary = load_primary(ROOT)
script77 = load_script77_summary(ROOT)

if page == "Overview":
    hero("MARITIME INTELLIGENCE + OPERATIONS RESEARCH",
         "Strait of Hormuz | Disruption & Vessel Schedule Recovery",
         "A two-layer decision-support dashboard: real-world monitoring is kept separate from the deterministic research experiment.")
    st.markdown('<div class="note"><b>Interpretation rule:</b> Real-world observations are not validation of the hypothetical simulation. No legal closure is asserted without an authoritative formal notice.</div>', unsafe_allow_html=True)
    a,b,c,d = st.columns(4)
    a.metric("Baseline port calls", "604")
    b.metric("Represented vessels", "155")
    c.metric("Ports", "19")
    d.metric("Distinct-port transitions", "271")
    st.subheader("Two separate information layers")
    x,y = st.columns(2)
    with x:
        st.markdown("### 🌐 Real-world monitoring")
        st.markdown("- UKMTO advisories and warnings\n- Maritime traffic data, when available\n- News and security developments\n- Oil and energy indicators")
        st.caption("Live sources may be delayed, incomplete, credential-gated or manually refreshed.")
    with y:
        st.markdown("### 🧪 Research simulation")
        st.markdown("- 16 hypothetical disruption scenarios\n- 5 recovery policies\n- 80 scenario-policy result cells\n- Script 76 primary / Script 77 sensitivity")
        st.caption("Precomputed deterministic outputs. Controls explore results; they do not rerun the experiment.")
    st.subheader("Current source status")
    st.write(f"Operational status record: **{status.get('status','UNVERIFIED')}**")
    st.caption(f"Status record timestamp: {status.get('updated_at','Not supplied')}")
    st.write("Use the sidebar to explore the six sections.")

elif page == "1 · Live Situation":
    hero("REAL-WORLD LAYER", "Strait of Hormuz | Live Situation",
         "Operational status is shown only when supported by an explicitly recorded source update.")
    status = load_status_record(ROOT)
    st.metric("Recorded operational status", status.get("status","UNVERIFIED"))
    st.write(f"**Last updated:** {status.get('updated_at','Not supplied')}")
    st.write(f"**Source:** {status.get('source_name','No source record loaded')}")
    st.write(f"**Source note:** {status.get('summary','No verified status summary has been entered.')}")
    st.markdown('<div class="warn"><b>Closure distinction:</b> A severe reduction in commercial transit is not automatically a formal legal closure. This dashboard does not infer legal closure from news headlines or vessel-count changes.</div>', unsafe_allow_html=True)
    st.subheader("Authoritative monitoring links")
    links = [
        ("UKMTO warnings and advisories","https://www.ukmto.org/ukmto-products"),
        ("UKMTO advisories","https://www.ukmto.org/ukmto-products/advisories"),
        ("JMIC","https://www.ukmto.org/"),
        ("IMO","https://www.imo.org/"),
        ("IMF PortWatch","https://portwatch.imf.org/"),
    ]
    for label,url in links:
        st.markdown(f"- [{label}]({url})")
    st.subheader("Historical event register")
    events_path = ROOT / "data" / "external" / "historical_events.csv"
    if events_path.exists():
        events = pd.read_csv(events_path)
        if not events.empty:
            st.dataframe(events, use_container_width=True, hide_index=True)
        else:
            st.info("No historical events have been entered in the event register.")
    else:
        st.info("Add sourced events to data/external/historical_events.csv. No unsourced timeline events are preloaded.")

elif page == "2 · Vessel Traffic":
    hero("REAL-WORLD LAYER", "Vessel Traffic & Maritime Activity",
         "AIS-derived traffic and geographic positions are displayed only when an actual source file or supported feed is supplied.")
    st.markdown('<div class="warn"><b>No fabricated vessel counts or positions.</b> No live AIS credentials or authoritative daily transit file are bundled. Import a PortWatch export or AIS CSV to populate this section.</div>', unsafe_allow_html=True)
    st.markdown("**Preferred source:** [IMF PortWatch](https://portwatch.imf.org/) · [MarineTraffic](https://www.marinetraffic.com/)")
    uploaded = st.file_uploader("Upload a vessel traffic CSV (PortWatch/AIS export)", type=["csv"])
    if uploaded:
        df = pd.read_csv(uploaded)
        st.write("Imported rows:", len(df))
        st.dataframe(df.head(100), use_container_width=True)
        date_col = next((c for c in df.columns if c.lower() in ["date","day","timestamp","period"]), None)
        count_col = next((c for c in df.columns if c.lower() in ["portcalls","transits","vessel_count","count","daily_transits"]), None)
        if date_col and count_col:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df[count_col] = pd.to_numeric(df[count_col], errors="coerce")
            plot = df.dropna(subset=[date_col,count_col]).sort_values(date_col)
            st.plotly_chart(px.line(plot,x=date_col,y=count_col,title="Imported vessel activity trend",
                                    template="plotly_dark"), use_container_width=True)
        lat = next((c for c in df.columns if c.lower() in ["lat","latitude"]), None)
        lon = next((c for c in df.columns if c.lower() in ["lon","lng","longitude"]), None)
        if lat and lon:
            mapdf = df[[lat,lon]].copy()
            mapdf.columns = ["lat","lon"]
            mapdf = mapdf.apply(pd.to_numeric, errors="coerce").dropna()
            st.map(mapdf)
        else:
            st.caption("No latitude/longitude columns found; map omitted.")
        st.caption("Imported file is session-only; the app does not silently archive or relabel it as official.")
    else:
        st.info("Waiting for a real traffic export. Daily transit trend, inbound/outbound split and vessel categories will appear after a compatible dataset is imported.")

elif page == "3 · News & Events":
    hero("REAL-WORLD LAYER", "Latest News & Events",
         "Refreshable RSS search results with source attribution, publication time and original article links.")
    query = st.text_input("Search topic", "Strait of Hormuz")
    category = st.selectbox("Category", ["All","Security","Shipping","Diplomacy","Energy","Other"])
    days = st.selectbox("Date window", [1,3,7,30], index=2, format_func=lambda n:f"Last {n} days")
    if st.button("Refresh news", type="primary"):
        st.cache_data.clear()
    news, errors, refreshed = load_news(query, days)
    if category != "All" and not news.empty:
        news = news[news["category"] == category]
    st.caption(f"Fetched: {refreshed} · Feed: Google News RSS search (aggregator) · not an official incident record")
    if errors:
        st.warning("Some feeds were unavailable: " + "; ".join(errors))
    if news.empty:
        st.info("No matching feed items returned. Try refreshing or use the source links below.")
    else:
        for _, row in news.head(30).iterrows():
            with st.container(border=True):
                st.markdown(f"**{row['title']}**")
                st.caption(f"{row['source']} · {row['published']} · {row['category']}")
                st.write(row["summary"])
                st.markdown(f"[Open original article]({row['url']})")
    st.caption("Reuters and AP public RSS availability is not assumed; this section uses Google News site-restricted RSS search results as an aggregator, and links to the indexed article.")

elif page == "4 · Energy Impact":
    hero("REAL-WORLD LAYER", "Oil, Energy & Economic Impact",
         "Historical and market indicators are kept distinct from analytical commentary and hypothetical research outputs.")
    st.markdown("- [U.S. EIA Open Data](https://www.eia.gov/opendata/documentation.php)\n- [IMF PortWatch](https://portwatch.imf.org/)\n- [World Bank Data](https://data.worldbank.org/)")
    api_url = os.getenv("EIA_API_URL","").strip()
    api_key = os.getenv("EIA_API_KEY","").strip()
    if api_url and api_key:
        edf, err, updated = load_eia_series(api_url, api_key)
        st.caption(f"EIA request status · refreshed {updated}")
        if err:
            st.warning(err)
        elif not edf.empty:
            st.plotly_chart(px.line(edf,x="period",y="value",title="EIA series supplied in configuration",
                                    template="plotly_dark"), use_container_width=True)
            st.dataframe(edf.tail(30), use_container_width=True, hide_index=True)
            st.caption("Series identity and units are inherited from the configured EIA API URL; verify them in EIA metadata.")
    else:
        st.info("EIA live series is not configured. Add an EIA API key and an exact API Explorer URL to .env. The app intentionally does not guess a series identifier.")
    st.subheader("Energy-flow context")
    st.write("The Strait is an important route for crude oil, petroleum products and LNG. Quantitative flow values should be entered from a dated EIA/IMF source extract and labelled with its reference period.")
    context_file = ROOT / "data" / "external" / "energy_indicators.csv"
    if context_file.exists():
        ed = pd.read_csv(context_file)
        st.dataframe(ed, use_container_width=True, hide_index=True)
    else:
        st.caption("No dated energy-indicator snapshot is bundled. No live oil price or flow figure is invented.")
    st.markdown('<div class="note">Price co-movement does not establish causation. Attribute a price movement to a Strait event only when the cited source supports that causal interpretation.</div>', unsafe_allow_html=True)

elif page == "5 · Research Simulation":
    hero("RESEARCH LAYER · SCRIPT 76 PRIMARY", "Vessel Schedule Recovery | Scenario Explorer",
         "Explore the completed deterministic experiment using the existing precomputed Script 98 result table.")
    if primary.empty:
        st.error("Primary Script 98 dataset is not loaded. Place the existing Version 1 HTML at data/simulation/v1_dashboard.html, then run: python scripts/extract_v1_data.py")
    else:
        st.markdown('<div class="note"><b>Baseline:</b> 604 calls · 155 vessels · 19 ports · 449 sequence links (178 same-port + 271 distinct-port). Hypothetical shocks are selected from the 271 distinct-port transitions.</div>', unsafe_allow_html=True)
        c1,c2,c3 = st.columns(3)
        shock = c1.selectbox("Shock magnitude", sorted(primary.shock_hours.unique()), index=3, format_func=lambda x:f"{int(x)} hours")
        share = c2.selectbox("Affected transition share", sorted(primary.share.unique()), index=0, format_func=lambda x:f"{int(x*100)}%")
        policies = primary.policy_name.drop_duplicates().tolist()
        policy = c3.selectbox("Selected recovery policy", policies, index=2)
        rows = scenario_filter(primary, shock, share)
        selected = rows[rows.policy_name == policy].iloc[0]
        no_rec = rows[rows.policy_id == "R76-00-NONE"].iloc[0]
        benefit = float(no_rec.mean_delay - selected.mean_delay) * 604
        st.caption(f"Scenario: {selected.scenario_id} · 604 calls · 155 vessels · Script 76 primary model")
        k1,k2,k3,k4,k5 = st.columns(5)
        k1.metric("Mean departure delay", f"{selected.mean_delay:.2f} h")
        k2.metric("P90 departure delay", f"{selected.p90_delay:.2f} h")
        k3.metric("Unrecovered calls", f"{int(selected.unrecovered_calls)}")
        k4.metric("Unrecovered vessels", f"{int(selected.unrecovered_vessels)}")
        k5.metric("Recovery benefit vs no recovery", f"{benefit:,.0f} h")
        st.subheader("Policy comparison for selected scenario")
        fig = px.bar(rows.sort_values("mean_delay"),x="policy_name",y="mean_delay",color="policy_name",
                     labels={"policy_name":"Recovery policy","mean_delay":"Mean incremental departure delay (hours)"},
                     template="plotly_dark",text_auto=".2f")
        fig.update_layout(showlegend=False,xaxis_tickangle=-20)
        st.plotly_chart(fig,use_container_width=True)
        st.dataframe(rows[["policy_name","mean_delay","p90_delay","unrecovered_calls","unrecovered_vessels"]]
                     .rename(columns={"policy_name":"Policy","mean_delay":"Mean delay (h)","p90_delay":"P90 (h)",
                                      "unrecovered_calls":"Unrecovered calls","unrecovered_vessels":"Unrecovered vessels"}),
                     use_container_width=True,hide_index=True)
        st.subheader("Sensitivity across shock magnitude and affected share")
        heat = primary.groupby(["shock_hours","share"],as_index=False).mean_delay.mean()
        heat["share_pct"] = (heat.share*100).astype(int).astype(str)+"%"
        st.plotly_chart(px.density_heatmap(heat,x="share_pct",y="shock_hours",z="mean_delay",
                          histfunc="avg",text_auto=".1f",color_continuous_scale="Tealgrn",
                          labels={"share_pct":"Affected transition share","shock_hours":"Shock (h)",
                                  "mean_delay":"Mean delay (h)"},template="plotly_dark"),
                        use_container_width=True)
        st.subheader("Script 76 vs Script 77 — bounded sensitivity")
        st.caption("Script 77 is sensitivity only. Its observed-interval cap is a mathematical bound, not validated schedule slack.")
        if not script77.empty:
            comp = script77.copy()
            st.plotly_chart(px.bar(comp,x="policy_name",y=["script76_mean","script77_mean"],barmode="group",
                         labels={"value":"Mean departure delay (hours)","variable":"Model","policy_name":"Policy"},
                         template="plotly_dark"),use_container_width=True)
            st.dataframe(comp.rename(columns={"policy_name":"Policy","script76_mean":"Script 76 (h)",
                            "script77_mean":"Script 77 (h)","script77_p90":"Script 77 mean P90 (h)",
                            "script77_unrecovered_calls":"Script 77 mean unrecovered calls",
                            "script77_unrecovered_vessels":"Script 77 mean unrecovered vessels"}),
                         use_container_width=True,hide_index=True)
        else:
            st.warning("Script77 summary is not present.")
        st.markdown('<div class="warn"><b>Research boundary:</b> This is a deterministic hypothetical inter-port elapsed-time shock experiment. It is not a validated operational forecast, does not establish actual Hormuz transit, and does not prove physical recovery capability. Controls explore stored results; they do not run a new simulation.</div>',unsafe_allow_html=True)

elif page == "6 · Methodology & Limits":
    hero("RESEARCH LAYER", "Methodology, Data & Limitations",
         "A transparent account of what the experiment represents, how results were constructed and what they cannot establish.")
    st.subheader("Research objective")
    st.write("Evaluate how hypothetical additional inter-port elapsed-time shocks propagate through observed vessel-call sequences, and compare five mathematical recovery rules across a 4 × 4 scenario design.")
    st.subheader("Baseline and network construction")
    st.markdown("""
    - 604 observed port calls; 155 vessels; 19 ports.
    - 449 vessel sequence links: 178 same-port links and 271 distinct-port transitions.
    - Preserve all call and vessel identities in each scenario-policy cell.
    - Historical port-call sequences do not establish actual sailing routes or confirmed Hormuz transit.
    """)
    st.subheader("Experimental design")
    st.markdown("""
    - Hypothetical elapsed-time shocks: 6, 12, 24 and 48 hours.
    - Affected distinct-port transition shares: 10%, 25%, 50% and 100%.
    - 16 disruption scenarios × 5 policies = 80 scenario-policy cells; no-disruption baseline is separate.
    - Seed recorded in the frozen protocol and prior presentation is inconsistent (8801 vs 7501); verify against the exact run script before publishing the seed.
    """)
    st.subheader("Recovery policies")
    st.markdown("""
    1. No recovery.
    2. Fixed 6-hour recovery credit per subsequent sequence link.
    3. Fixed 12-hour recovery credit per subsequent sequence link.
    4. Proportional 25%, capped at 6 hours per link.
    5. Proportional 50%, capped at 12 hours per link.

    Recovery is applied at subsequent vessel sequence links, including same-port links, and cannot exceed delay available before recovery.
    """)
    st.subheader("Delay propagation and evaluation")
    st.latex(r"D_{i,t}^{pre}=D_{i-1,t}^{dep}+S_{i,t}")
    st.latex(r"D_{i,t}^{post}=\\max(0, D_{i,t}^{pre}-R_{i,t})")
    st.write("Incremental delays are measured against the no-disruption simulated baseline. Recovery benefit is separately paired against no recovery under the same shock scenario.")
    st.markdown("""
    - M01: mean incremental arrival delay.
    - M02: mean incremental departure delay.
    - M03A: maximum last-represented-call departure delay.
    - M03B: maximum across vessels of summed signed call-level incremental departure delay.
    - M04: mean last-represented-call departure delay.
    - M05: P90 incremental call departure delay (linear interpolation).
    - M06: total paired recovery benefit.
    - M07A: unrecovered call count.
    - M07B: unrecovered vessel count at its last represented call.
    """)
    st.subheader("Script 76 and Script 77")
    st.write("Script 76 is the primary abstract recovery formulation. Script 77 adds an observed inter-call elapsed-time cap and is retained only as mathematical sensitivity analysis. That interval is not established schedule slack or operational recovery capacity.")
    st.subheader("Critical limitations")
    limitations = [
        "Inter-port elapsed time is not necessarily pure sailing time; it may include anchorage, waiting, operations and data gaps.",
        "Port-call duration is not necessarily berth-processing time.",
        "Observed inter-call elapsed time is not established schedule slack.",
        "The 178 same-port links must not automatically be interpreted as physical vessel movements or removed without source-level verification.",
        "Recovery credits are abstract interventions, not measured operational capabilities.",
        "No actual port capacity, berth occupancy, route feasibility, fuel consumption, emissions, shipping costs or security conditions are established.",
        "A common evaluation horizon and internal numerical checks establish computational consistency, not operational validation.",
        "The last represented call is not necessarily the actual final voyage call; observed source windows may truncate later calls.",
        "No statistical significance, confidence intervals or p-values are claimed for this deterministic experiment.",
    ]
    for item in limitations:
        st.markdown(f"- {item}")
    st.subheader("Validation record")
    st.write("Script 98 report records 10/10 numerical validation checks passed. This does not establish operational validity or independently verified supervisor approval.")
    st.subheader("Software")
    st.write("Python 3.13.9, Pandas, NumPy and Matplotlib were used in the experiment workflow. Version 2 dashboard uses Streamlit, Plotly, Pandas and optional requests/feedparser integrations.")
    st.caption("Reference documents are retained in the Project Library: frozen protocol v1.1, Script 98 report, and simulation findings presentation.")

st.sidebar.caption("Sources and data freshness are shown in each section. Missing external data is never replaced with synthetic values.")
