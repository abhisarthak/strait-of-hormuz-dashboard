from pathlib import Path
import os, json
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import streamlit.components.v1 as components
from datetime import datetime, date, timezone
from dotenv import load_dotenv

from services.live_data import (
    load_news, load_eia_series, load_status_record, load_portwatch_csv,
    load_ais_csv, source_health
)
from services.simulation import (load_primary, load_call_level, load_vessel_level, load_validation, load_script77_summary, scenario_filter)

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
    st.caption("MARITIME INTELLIGENCE · BUILD 3")

status = load_status_record(ROOT)
primary = load_primary(ROOT)
call_level = load_call_level(ROOT)
vessel_level = load_vessel_level(ROOT)
validation = load_validation(ROOT)
script77 = load_script77_summary(ROOT)

if page == "Overview":
    hero("MARITIME INTELLIGENCE CENTRE", "STRAIT OF HORMUZ",
         "Operational picture · vessel activity · security developments · energy markets · research intelligence")

    # The closure counter is deliberately conditional on a verified formal-closure record.
    status = load_status_record(ROOT)
    status_value = str(status.get("status", "UNVERIFIED")).upper()
    closure_date_raw = status.get("closure_start_date")
    closure_days = None
    if status_value == "FORMALLY_CLOSED" and closure_date_raw:
        try:
            closure_date = date.fromisoformat(str(closure_date_raw)[:10])
            closure_days = max(0, (date.today() - closure_date).days)
        except (TypeError, ValueError):
            closure_days = None

    status_labels = {
        "NORMAL": "OPEN / NORMAL",
        "RESTRICTED": "RESTRICTED",
        "SEVERELY_DISRUPTED": "SEVERELY DISRUPTED",
        "FORMALLY_CLOSED": "FORMALLY CLOSED",
        "UNVERIFIED": "UNVERIFIED",
    }
    status_label = status_labels.get(status_value, status_value.replace("_", " "))
    if status_value == "FORMALLY_CLOSED" and closure_days is not None:
        duration_label = f"{closure_days} days"
        duration_help = f"Since {closure_date_raw}; inclusive day count: {closure_days + 1}"
    else:
        duration_label = "Not established"
        duration_help = "A verified formal-closure date is required for this counter."

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("STRAIT STATUS", status_label)
    s2.metric("DAYS SINCE FORMAL CLOSURE", duration_label, help=duration_help)
    s3.metric("RESEARCH CALLS", f"{int(primary['call_count'].max()):,}" if not primary.empty and 'call_count' in primary else "604")
    s4.metric("RESEARCH VESSELS", f"{int(primary['vessel_count'].max()):,}" if not primary.empty and 'vessel_count' in primary else "155")

    st.markdown(
        f'<div class="smallmuted">Status source: <b>{status.get("source_name", "Not recorded")}</b> '
        f'&nbsp;·&nbsp; Last verified: <b>{status.get("updated_at") or "Not recorded"}</b> '
        f'&nbsp;·&nbsp; <a href="{status.get("source_url", "https://www.ukmto.org/ukmto-products")}" target="_blank">Open source</a></div>',
        unsafe_allow_html=True
    )
    st.markdown('<div class="warn"><b>Intelligence rule:</b> The dashboard will not infer a formal closure from reduced vessel traffic or news reports. The closure counter remains unavailable until an authoritative closure date is recorded.</div>', unsafe_allow_html=True)

    left, right = st.columns([1.55, 1])
    with left:
        st.subheader("Operational theatre · Strait of Hormuz")
        map_url = "https://www.openstreetmap.org/export/embed.html?bbox=54.7%2C24.2%2C57.8%2C27.4&layer=mapnik&marker=26.3%2C56.3"
        components.iframe(map_url, height=430, scrolling=False)
        st.caption("Reference map only. It does not display live AIS vessel positions or imply a navigational route.")
    with right:
        st.subheader("Latest intelligence")
        refresh_news = st.button("↻ Refresh news", key="overview_refresh_news")
        if refresh_news:
            st.cache_data.clear()
        try:
            news_df, news_errors, news_updated = load_news("Strait of Hormuz", 14)
            if not news_df.empty:
                for _, item in news_df.head(6).iterrows():
                    st.markdown(f'**[{item["title"]}]({item["url"]})**')
                    st.caption(f'{item["source"]} · {item["published"] or "Publication time not supplied"} · {item["category"]}')
                    if item.get("summary"):
                        st.write(str(item["summary"])[:240])
                    st.divider()
            else:
                st.info("No recent articles were returned by the news feeds. Open the News & Events section or retry later.")
            st.caption(f"Feed checked: {news_updated} · RSS headlines are secondary sources; verify critical claims against the original publisher and official advisories.")
            if news_errors:
                st.caption("Some feeds could not be reached: " + "; ".join(news_errors[:3]))
        except Exception as exc:
            st.warning(f"News feed unavailable: {str(exc)[:180]}")

    st.subheader("Situation indicators")
    traffic_path = ROOT / "data" / "external" / "vessel_traffic.csv"
    energy_path = ROOT / "data" / "external" / "energy_indicators.csv"
    tcol1, tcol2, tcol3 = st.columns(3)
    if traffic_path.exists():
        try:
            traffic = pd.read_csv(traffic_path)
            date_col = next((c for c in traffic.columns if c.lower() in ["date", "day", "timestamp", "period"]), None)
            count_col = next((c for c in traffic.columns if c.lower() in ["transits", "vessel_count", "count", "daily_transits"]), None)
            if date_col and count_col and not traffic.empty:
                traffic[date_col] = pd.to_datetime(traffic[date_col], errors="coerce")
                traffic[count_col] = pd.to_numeric(traffic[count_col], errors="coerce")
                valid_traffic = traffic.dropna(subset=[date_col, count_col]).sort_values(date_col)
                if not valid_traffic.empty:
                    latest = valid_traffic.iloc[-1]
                    tcol1.metric("LATEST RECORDED TRANSITS", f"{latest[count_col]:,.0f}", str(latest[date_col].date()))
                    with st.expander("View vessel-traffic trend"):
                        st.plotly_chart(px.line(valid_traffic, x=date_col, y=count_col, template="plotly_dark", title="Recorded daily vessel transits"), use_container_width=True)
                else:
                    tcol1.metric("VESSEL TRAFFIC", "No valid rows")
            else:
                tcol1.metric("VESSEL TRAFFIC", "Data not mapped")
        except Exception:
            tcol1.metric("VESSEL TRAFFIC", "Could not read file")
    else:
        tcol1.metric("VESSEL TRAFFIC", "Awaiting data", help="Add a sourced daily dataset at data/external/vessel_traffic.csv")

    if energy_path.exists():
        try:
            energy = pd.read_csv(energy_path)
            tcol2.metric("ENERGY SNAPSHOT", f"{len(energy):,} records", "See Energy Impact for source details")
        except Exception:
            tcol2.metric("ENERGY SNAPSHOT", "Could not read file")
    else:
        tcol2.metric("ENERGY SNAPSHOT", "Awaiting data", help="No dated energy snapshot is currently bundled")

    tcol3.metric("RESEARCH EXPERIMENT", "16 scenarios · 5 policies", "80 Script 98 scenario-policy result cells" if not primary.empty else "Script 98 data not found")

    st.subheader("Research intelligence · Script 98")
    if not primary.empty:
        policy_names = primary["policy_name"].dropna().drop_duplicates().tolist()
        shock_options = sorted(primary["shock_hours"].dropna().unique().tolist())
        share_options = sorted(primary["share"].dropna().unique().tolist())
        sc1, sc2, sc3 = st.columns(3)
        overview_shock = sc1.selectbox("Shock scenario", shock_options, index=min(2, len(shock_options)-1), format_func=lambda x: f"{x:g} hours", key="overview_shock")
        overview_share = sc2.selectbox("Affected transitions", share_options, index=0, format_func=lambda x: f"{x:.0%}", key="overview_share")
        overview_policy = sc3.selectbox("Recovery policy", policy_names, index=0, key="overview_policy")
        selected_rows = scenario_filter(primary, overview_shock, overview_share)
        selected_row = selected_rows[selected_rows["policy_name"] == overview_policy]
        if not selected_row.empty:
            r = selected_row.iloc[0]
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("MEAN DEPARTURE DELAY", f"{r['mean_delay']:.2f} h")
            m2.metric("P90 DEPARTURE DELAY", f"{r['p90_delay']:.2f} h")
            m3.metric("PAIRED RECOVERY BENEFIT", f"{r['m06_total_paired_recovery_benefit_h']:,.0f} h")
            m4.metric("UNRECOVERED CALLS", f"{r['unrecovered_calls']:,.0f}")
        else:
            st.info("No Script 98 result matches this selection.")
        st.caption("These are hypothetical research outputs, not live vessel-delay measurements or an operational forecast.")
    else:
        st.warning("Script 98 outputs are not currently available at the configured project path. The research files are not modified by this dashboard.")

    st.markdown('<div class="note">Use the sidebar for detailed vessel traffic, news, energy analysis and the full research simulation. Live feeds depend on source availability; imported datasets must retain their date, unit and provenance.</div>', unsafe_allow_html=True)

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
         "Explore the completed deterministic experiment using the original, precomputed Script 98 outputs.")

    if primary.empty:
        st.error("Canonical Script 98 scenario-policy results were not found.")
        st.caption("Expected location: ../outputs/tables/98_final_scenario_policy_results.csv relative to this V2 folder.")
    else:
        st.markdown(
            '<div class="note"><b>Baseline:</b> 604 calls · 155 vessels · 19 ports · '
            '449 sequence links (178 same-port + 271 distinct-port). Hypothetical shocks '
            'are selected from the 271 distinct-port transitions. Results below are loaded '
            'from the original Script 98 CSV files.</div>',
            unsafe_allow_html=True
        )

        c1, c2, c3 = st.columns(3)
        shock_values = sorted(primary["shock_hours"].dropna().unique().tolist())
        share_values = sorted(primary["share"].dropna().unique().tolist())
        shock = c1.selectbox(
            "Shock magnitude", shock_values,
            index=min(2, len(shock_values)-1),
            format_func=lambda x: f"{x:g} hours"
        )
        share = c2.selectbox(
            "Affected transition share", share_values,
            index=0, format_func=lambda x: f"{x:.0%}"
        )
        policies = primary["policy_name"].dropna().drop_duplicates().tolist()
        default_policy = next((i for i, p in enumerate(policies) if p == "Fixed recovery credit, 6h per link"), 0)
        policy = c3.selectbox("Selected recovery policy", policies, index=default_policy)

        rows = scenario_filter(primary, shock, share)
        if rows.empty:
            st.warning("No scenario-policy rows match the selected shock and affected share.")
        else:
            selected_rows = rows[rows["policy_name"] == policy]
            selected = selected_rows.iloc[0] if not selected_rows.empty else rows.iloc[0]
            no_recovery_rows = rows[rows["policy_id"] == "R76-00-NONE"]
            no_recovery = no_recovery_rows.iloc[0] if not no_recovery_rows.empty else None

            st.caption(
                f"Scenario: {selected['scenario_id']} · "
                f"{int(selected.get('call_count', 604))} calls · "
                f"{int(selected.get('vessel_count', 155))} vessels · Script 76 primary model"
            )

            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("M02 · Mean incremental departure delay", f"{selected['mean_delay']:.2f} h")
            k2.metric("M05 · P90 incremental departure delay", f"{selected['p90_delay']:.2f} h")
            k3.metric("M07A · Unrecovered calls", f"{int(selected['unrecovered_calls'])}")
            k4.metric("M07B · Unrecovered vessels", f"{int(selected['unrecovered_vessels'])}")
            k5.metric(
                "M06 · Paired recovery benefit",
                f"{selected.get('m06_total_paired_recovery_benefit_h', float('nan')):,.1f} h"
            )

            tabs = st.tabs([
                "Scenario & policy comparison",
                "Call-level analytics",
                "Vessel-level analytics",
                "Script 77 sensitivity",
                "Validation centre"
            ])

            with tabs[0]:
                st.subheader("All five recovery policies for the selected scenario")
                display_cols = [
                    "policy_name", "mean_delay", "p90_delay",
                    "m06_total_paired_recovery_benefit_h",
                    "m06_mean_paired_recovery_benefit_per_call_h",
                    "unrecovered_calls", "unrecovered_vessels",
                    "m03a_max_final_call_departure_delay_h",
                    "m03b_max_accumulated_signed_vessel_delay_h",
                    "m04_mean_final_call_departure_delay_h",
                ]
                display_cols = [c for c in display_cols if c in rows.columns]
                comparison = rows[display_cols].copy()
                st.plotly_chart(
                    px.bar(
                        rows.sort_values("mean_delay"), x="policy_name", y="mean_delay",
                        color="policy_name",
                        labels={"policy_name": "Recovery policy",
                                "mean_delay": "M02 mean incremental departure delay (hours)"},
                        template="plotly_dark", text_auto=".2f"
                    ).update_layout(showlegend=False, xaxis_tickangle=-20),
                    use_container_width=True
                )
                st.dataframe(comparison, use_container_width=True, hide_index=True)
                st.download_button(
                    "Download selected scenario-policy table",
                    rows.to_csv(index=False).encode("utf-8"),
                    file_name=f"script98_{selected['scenario_id']}_policy_comparison.csv",
                    mime="text/csv"
                )

                st.subheader("Scenario design: M02 across shock and affected-share settings")
                heat = primary.groupby(["shock_hours", "share"], as_index=False)["mean_delay"].mean()
                heat["share_label"] = heat["share"].map(lambda x: f"{x:.0%}")
                heat_fig = px.density_heatmap(
                    heat, x="share_label", y="shock_hours", z="mean_delay",
                    histfunc="avg", text_auto=".2f",
                    labels={"share_label": "Affected transition share",
                            "shock_hours": "Shock magnitude (hours)",
                            "mean_delay": "Mean M02 across policies (hours)"},
                    template="plotly_dark", color_continuous_scale="Tealgrn"
                )
                st.plotly_chart(heat_fig, use_container_width=True)
                st.caption("Heatmap cells average the five recovery policies within each shock/share combination.")

                st.subheader("Additional Script 98 outcome metrics")
                metric_cols = [
                    ("M01 · Mean incremental arrival delay", "m01_mean_incremental_arrival_delay_h"),
                    ("M03A · Maximum final represented-call departure delay", "m03a_max_final_call_departure_delay_h"),
                    ("M03B · Maximum accumulated signed vessel departure delay", "m03b_max_accumulated_signed_vessel_delay_h"),
                    ("M04 · Mean final represented-call departure delay", "m04_mean_final_call_departure_delay_h"),
                    ("Applied recovery credit total", "applied_recovery_credit_total_h"),
                    ("Censored represented calls", "censored_calls"),
                    ("Censored vessels", "censored_vessels"),
                ]
                metric_rows = []
                for label, col in metric_cols:
                    if col in selected.index:
                        metric_rows.append({"Metric": label, "Value": selected[col]})
                if metric_rows:
                    st.dataframe(pd.DataFrame(metric_rows), use_container_width=True, hide_index=True)

            with tabs[1]:
                st.subheader("Call-level paired results")
                if call_level.empty:
                    st.warning("The original Script 98 call-level CSV was not found.")
                else:
                    call_slice = call_level[
                        (call_level["scenario_id"] == selected["scenario_id"]) &
                        (call_level["policy_id"] == selected["policy_id"])
                    ].copy()
                    st.caption(f"{len(call_slice):,} call-level records in the selected scenario-policy cell.")
                    if not call_slice.empty:
                        a, b, c = st.columns(3)
                        a.metric("Affected transitions", int(call_slice["affected_transition"].fillna(False).sum()))
                        b.metric("Mean incremental departure delay", f"{call_slice['incremental_departure_delay_h'].mean():.2f} h")
                        c.metric("Mean paired recovery benefit", f"{call_slice['paired_recovery_benefit_h'].mean():.2f} h")
                        st.plotly_chart(
                            px.histogram(
                                call_slice, x="incremental_departure_delay_h", nbins=35,
                                title="Distribution of incremental call departure delay",
                                labels={"incremental_departure_delay_h": "Incremental departure delay (hours)"},
                                template="plotly_dark"
                            ),
                            use_container_width=True
                        )
                        st.plotly_chart(
                            px.box(
                                call_slice, x="affected_transition",
                                y="paired_recovery_benefit_h",
                                title="Paired recovery benefit by affected-transition status",
                                labels={"affected_transition": "Affected transition",
                                        "paired_recovery_benefit_h": "Paired recovery benefit (hours)"},
                                template="plotly_dark"
                            ),
                            use_container_width=True
                        )
                        st.dataframe(call_slice.head(500), use_container_width=True, hide_index=True)
                        st.download_button(
                            "Download selected call-level records",
                            call_slice.to_csv(index=False).encode("utf-8"),
                            file_name=f"script98_{selected['scenario_id']}_{selected['policy_id']}_calls.csv",
                            mime="text/csv"
                        )
                    else:
                        st.info("No call-level rows match this scenario-policy selection.")

            with tabs[2]:
                st.subheader("Vessel-level outcomes")
                if vessel_level.empty:
                    st.warning("The original Script 98 vessel-level CSV was not found.")
                else:
                    vessel_slice = vessel_level[
                        (vessel_level["scenario_id"] == selected["scenario_id"]) &
                        (vessel_level["policy_id"] == selected["policy_id"])
                    ].copy()
                    st.caption(f"{len(vessel_slice):,} vessel-level records in the selected scenario-policy cell.")
                    if not vessel_slice.empty:
                        a, b, c = st.columns(3)
                        a.metric("Vessels represented", len(vessel_slice))
                        b.metric("Unrecovered vessels", int(vessel_slice["unrecovered_vessel"].fillna(False).sum()))
                        c.metric(
                            "Mean accumulated signed delay",
                            f"{vessel_slice['accumulated_signed_departure_delay_h'].mean():.2f} h"
                        )
                        st.plotly_chart(
                            px.histogram(
                                vessel_slice, x="accumulated_signed_departure_delay_h", nbins=35,
                                title="Accumulated signed departure delay by vessel",
                                labels={"accumulated_signed_departure_delay_h": "Accumulated signed delay (hours)"},
                                template="plotly_dark"
                            ),
                            use_container_width=True
                        )
                        st.dataframe(vessel_slice, use_container_width=True, hide_index=True)
                        st.download_button(
                            "Download selected vessel-level records",
                            vessel_slice.to_csv(index=False).encode("utf-8"),
                            file_name=f"script98_{selected['scenario_id']}_{selected['policy_id']}_vessels.csv",
                            mime="text/csv"
                        )

            with tabs[3]:
                st.subheader("Script 76 primary vs Script 77 sensitivity")
                st.caption(
                    "Script 77 is sensitivity analysis only. Its observed-interval cap is a mathematical "
                    "bound, not validated schedule slack or operational recovery capacity."
                )
                if not script77.empty:
                    comp = script77.copy()
                    st.plotly_chart(
                        px.bar(
                            comp, x="policy_name",
                            y=["script76_mean", "script77_mean"], barmode="group",
                            labels={"value": "Mean departure delay (hours)",
                                    "variable": "Model", "policy_name": "Recovery policy"},
                            template="plotly_dark"
                        ),
                        use_container_width=True
                    )
                    st.dataframe(comp, use_container_width=True, hide_index=True)
                else:
                    st.warning("Script 77 summary is not present.")

            with tabs[4]:
                st.subheader("Script 98 numerical validation checks")
                if validation.empty:
                    st.warning("The Script 98 validation-check CSV was not found.")
                else:
                    checks = validation.copy()
                    passed = checks["Passed"].astype(str).str.lower().isin(["true", "1", "yes"])
                    a, b = st.columns(2)
                    a.metric("Checks passed", f"{int(passed.sum())}/{len(checks)}")
                    b.metric("Checks failed", int((~passed).sum()))
                    st.dataframe(checks, use_container_width=True, hide_index=True)
                    if passed.all():
                        st.success("All recorded Script 98 numerical validation checks passed.")
                    else:
                        st.error("One or more recorded Script 98 validation checks did not pass.")

        st.markdown(
            '<div class="warn"><b>Research boundary:</b> This is a deterministic hypothetical '
            'inter-port elapsed-time shock experiment. It is not a validated operational forecast, '
            'does not establish actual Hormuz transit, and does not prove physical recovery capability. '
            'Dashboard controls filter stored results; they do not rerun the experiment.</div>',
            unsafe_allow_html=True
        )

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
