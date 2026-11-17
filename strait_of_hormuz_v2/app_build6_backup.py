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
    load_ais_csv, source_health, load_hormuz_ais_snapshot,
    load_hormuz_crossings, load_hormuz_daily, load_fred_energy_series
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

def render_hormuz_map(height=720, ais_vessels=None):
    """Dark, interactive geographic reference map; markers are not live AIS."""
    ais_json = json.dumps(ais_vessels or [], ensure_ascii=False, default=str).replace("</", "<\\/")
    map_html = r"""<!DOCTYPE html><html><head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <style>
      html,body,#map{height:100%;width:100%;margin:0;background:#061522}
      .leaflet-container{font:13px Inter,Arial,sans-serif;background:#061522}
      .leaflet-control-attribution{background:rgba(5,18,30,.88)!important;color:#b7cbd8!important}
      .leaflet-control-attribution a{color:#6edce5!important}
      .leaflet-control-layers{background:rgba(7,24,39,.96)!important;color:#eaf4fb!important;border:1px solid #28566c!important;border-radius:9px!important;box-shadow:0 4px 18px #0008}
      .leaflet-control-layers-separator{border-top:1px solid #34566a!important}
      .leaflet-popup-content-wrapper,.leaflet-popup-tip{background:#10283b;color:#eef8ff;border:1px solid #2a6076}
      .leaflet-popup-content{line-height:1.55}
      .map-title{position:absolute;z-index:500;top:12px;left:50px;background:rgba(7,24,39,.9);color:#eaf4fb;border:1px solid #2b6478;border-radius:9px;padding:8px 12px;font-weight:700;letter-spacing:.5px;box-shadow:0 3px 14px #0008}
      .map-title small{display:block;color:#9fb9ca;font-weight:400;letter-spacing:0;margin-top:2px}
      .legend{background:rgba(7,24,39,.95);color:#eaf4fb;padding:11px 13px;border:1px solid #2b6478;border-radius:9px;line-height:1.8;box-shadow:0 3px 14px #0008}
      .legend b{color:#69dce0}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px}
      .port-label{color:#f3fbff;text-shadow:0 1px 4px #00101c,1px 0 4px #00101c,-1px 0 4px #00101c;font-weight:700;white-space:nowrap;font-size:12px}
      .checkpoint-label{color:#ffd18a;text-shadow:0 1px 4px #00101c,1px 0 4px #00101c;font-weight:700;white-space:nowrap;font-size:11px}
      .leaflet-control-scale-line{background:rgba(7,24,39,.8);color:#eaf4fb;border-color:#d5e7f2}
    </style></head><body><div id="map"></div>
    <div class="map-title">STRAIT OF HORMUZ <small>Ports · approaches · illustrative transit corridor</small></div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script><script>
    const map=L.map('map',{scrollWheelZoom:true,preferCanvas:true}).setView([26.25,56.15],8);
    // No-key basemaps: Esri World Imagery + place-name overlay, with OSM as fallback.
    // CARTO's public raster endpoint began returning an API-key watermark in this deployment.
    const imagery=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{
      maxZoom:19,attribution:'Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community'
    });
    const placeLabels=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',{
      maxZoom:19,opacity:0.92,attribution:'Place names &copy; Esri'
    });
    const osm=L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
      maxZoom:19,attribution:'&copy; OpenStreetMap contributors'
    });
    imagery.addTo(map); placeLabels.addTo(map);
    L.control.scale({imperial:false,position:'bottomright'}).addTo(map);
    const ports=[
      ['Bandar Abbas',27.1832,56.2666,'Iran','Major Iranian port on the northern side of the Strait'],
      ['Qeshm',26.9581,56.2719,'Iran','Island port reference'],
      ['Bandar Lengeh',26.5579,54.8807,'Iran','Iranian coastal port reference'],
      ['Jask',25.6439,57.7746,'Iran','Gulf of Oman coastal reference'],
      ['Khasab',26.1799,56.2477,'Oman','Omani Musandam port reference'],
      ['Fujairah',25.1288,56.3265,'UAE','Gulf of Oman port reference'],
      ['Sharjah',25.3463,55.4209,'UAE','UAE port reference'],
      ['Ras Al Khaimah',25.7895,55.9432,'UAE','UAE coastal port reference']
    ];
    const portLayer=L.layerGroup();
    ports.forEach(p=>{
      const marker=L.circleMarker([p[1],p[2]],{radius:7,color:'#d5fbff',weight:2,fillColor:'#20c5df',fillOpacity:.98});
      marker.bindPopup('<div style="min-width:190px"><b style="font-size:15px">'+p[0]+'</b><br><span style="color:#65d8d1">'+p[3]+'</span><br>'+p[4]+'<br><small>Geographic reference only · not live port activity</small></div>').addTo(portLayer);
      L.marker([p[1],p[2]],{interactive:false,icon:L.divIcon({className:'port-label',html:p[0],iconSize:[130,16],iconAnchor:[-9,18]})}).addTo(portLayer);
    });
    const checkpoints=L.layerGroup();
    const cps=[['Northern approach reference',26.72,56.15],['Southern approach reference',25.93,56.05]];
    cps.forEach(p=>{
      L.circle([p[1],p[2]],{radius:6500,color:'#ffb45e',weight:2,dashArray:'5 6',fillColor:'#ffb45e',fillOpacity:.13})
       .bindPopup('<b>'+p[0]+'</b><br><small>Illustrative monitoring reference only. Not an official checkpoint, security perimeter or control boundary.</small>').addTo(checkpoints);
      L.marker([p[1],p[2]],{interactive:false,icon:L.divIcon({className:'checkpoint-label',html:p[0],iconSize:[170,16],iconAnchor:[-8,18]})}).addTo(checkpoints);
    });
    const corridor=L.layerGroup();
    const route=[[25.72,55.0],[25.91,55.35],[26.08,55.72],[26.23,56.05],[26.40,56.42],[26.57,56.83],[26.69,57.20]];
    L.polyline(route,{color:'#40d9c8',weight:4,opacity:.95,dashArray:'10 8'}).bindPopup('Illustrative Strait corridor<br><small>Conceptual reference line only; not a recommended or verified navigational route.</small>').addTo(corridor);
    portLayer.addTo(map); checkpoints.addTo(map); corridor.addTo(map);
    L.control.layers({'Satellite imagery':imagery,'Standard map':osm},{'Place labels':placeLabels,'Reference ports':portLayer,'Monitoring reference areas':checkpoints,'Illustrative corridor':corridor},{collapsed:false}).addTo(map);
    const aisData = __AIS_PLACEHOLDER__;
    const aisLayer = L.layerGroup();
    const esc = s => String(s ?? 'Not supplied').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    aisData.forEach(v=>{
      const cat=String(v.category||v.type||'Vessel').toLowerCase();
      const colour=cat.includes('tanker')?'#ff9f43':(cat.includes('cargo')?'#35c9d0':'#b7a4ff');
      const marker=L.circleMarker([v.lat,v.lon],{radius:5,color:'#061522',weight:1,fillColor:colour,fillOpacity:.95});
      marker.bindPopup('<b>'+esc(v.name)+'</b><br>Category: '+esc(v.category||v.type)+
        '<br>Speed: '+esc(v.speed)+' kn<br>Course: '+esc(v.course)+
        '<br>Flag: '+esc(v.flag)+'<br>Position age: '+esc(v.ageMin)+' min'+
        '<br><small>Provider-reported AIS-derived position · not a navigational aid</small>');
      marker.addTo(aisLayer);
    });
    if(aisData.length){aisLayer.addTo(map);}
    const aisOverlays = {}; aisOverlays['AIS vessel positions ('+aisData.length+')'] = aisLayer; L.control.layers({}, aisOverlays, {collapsed:true}).addTo(map);
    const legend=L.control({position:'bottomleft'});legend.onAdd=()=>{let d=L.DomUtil.create('div','legend');d.innerHTML='<b>MAP KEY</b><br><span class="dot" style="background:#20c5df"></span>Reference port<br><span class="dot" style="background:#ffb45e"></span>Monitoring reference area<br><span class="dot" style="background:#40d9c8"></span>Illustrative corridor';return d};legend.addTo(map);
    </script></body></html>"""
    map_html = map_html.replace("__AIS_PLACEHOLDER__", ais_json)
    components.html(map_html, height=height, scrolling=False)

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
    st.markdown("🟡 AIS-derived feed · public third-party provider")
    st.divider()
    st.caption("MARITIME INTELLIGENCE · HYBRID BUILD 6")

status = load_status_record(ROOT)
primary = load_primary(ROOT)
call_level = load_call_level(ROOT)
vessel_level = load_vessel_level(ROOT)
validation = load_validation(ROOT)
script77 = load_script77_summary(ROOT)

if page == "Overview":
    hero("MARITIME INTELLIGENCE CENTRE", "STRAIT OF HORMUZ",
         "Operational picture · vessel activity · security developments · energy markets · research intelligence")

    # Disruption duration is shown only when a dated source record exists.
    # It is deliberately separate from the formal legal-closure status.
    status = load_status_record(ROOT)
    status_value = str(status.get("status", "UNVERIFIED")).upper()
    status_labels = {
        "NORMAL": "OPEN / NORMAL",
        "RESTRICTED": "RESTRICTED",
        "SEVERELY_DISRUPTED": "SEVERELY DISRUPTED",
        "FORMALLY_CLOSED": "FORMALLY CLOSED",
        "UNVERIFIED": "RESTRICTED",
    }
    status_label = status_labels.get(status_value, status_value.replace("_", " "))

    disruption_date_raw = status.get("disruption_start_date")
    if not disruption_date_raw and status_value == "FORMALLY_CLOSED":
        disruption_date_raw = status.get("closure_start_date")
    disruption_days = None
    disruption_help = "A dated disruption_start_date is required in data/external/status.json."
    if disruption_date_raw:
        try:
            disruption_date = date.fromisoformat(str(disruption_date_raw)[:10])
            disruption_days = max(0, (date.today() - disruption_date).days)
            disruption_help = f"Elapsed calendar days since {disruption_date.isoformat()}; source: {status.get('source_name', 'not recorded')}."
        except (TypeError, ValueError):
            disruption_help = "The disruption start date in status.json is not a valid YYYY-MM-DD date."

    research_calls = "—"
    research_vessels = "—"
    if not primary.empty:
        if "call_count" in primary:
            research_calls = f"{int(primary['call_count'].max()):,}"
        if "vessel_count" in primary:
            research_vessels = f"{int(primary['vessel_count'].max()):,}"

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("OPERATIONAL STATUS", status_label)
    s2.metric("DAYS SINCE DISRUPTION", f"{disruption_days:,}" if disruption_days is not None else "Not recorded", help=disruption_help)
    s3.metric("RESEARCH CALLS", research_calls, help="Historical port-call records in the Script 98 research dataset; not live traffic.")
    s4.metric("RESEARCH VESSELS", research_vessels, help="Vessels represented in the Script 98 research dataset; not live AIS positions.")

    st.markdown(
        f'<div class="smallmuted">Status source: <b>{status.get("source_name", "Not recorded")}</b> '
        f'&nbsp;·&nbsp; Record updated: <b>{status.get("updated_at") or "Not recorded"}</b> '
        f'&nbsp;·&nbsp; <a href="{status.get("source_url", "https://www.ukmto.org/ukmto-products")}" target="_blank">Open source</a></div>',
        unsafe_allow_html=True
    )
    st.markdown('<div class="warn"><b>Intelligence rule:</b> The dashboard distinguishes operational disruption from formal legal closure. Reduced vessel traffic or news reports alone do not establish a formal closure. Disruption duration is displayed only when a dated source record is available.</div>', unsafe_allow_html=True)

    left, right = st.columns([1.65, 1])
    with left:
        st.subheader("Operational theatre · Strait of Hormuz")
        render_hormuz_map(560)
        st.caption("Satellite reference map with geographic ports and illustrative monitoring layers. It does not display live AIS vessel positions or imply a navigational route.")
    with right:
        st.subheader("Latest intelligence")
        refresh_news = st.button("↻ Refresh news", key="overview_refresh_news")
        if refresh_news:
            st.cache_data.clear()
        try:
            news_df, news_errors, news_updated = load_news("Strait of Hormuz", 14)
            if not news_df.empty:
                for _, item in news_df.head(3).iterrows():
                    with st.container(border=True):
                        st.markdown(f'**[{item["title"]}]({item["url"]})**')
                        st.caption(f'{item["source"]} · {item["published"] or "Publication time not supplied"} · {item["category"]}')
                        summary = str(item.get("summary") or "").strip()
                        if summary:
                            st.write(summary[:190] + ("…" if len(summary) > 190 else ""))
                st.caption("Showing three priority reports. Open News & Events for filters and full coverage.")
            else:
                st.info("No recent articles were returned by the news feeds. Open the News & Events section or retry later.")
            st.caption(f"Feed checked: {news_updated} · RSS headlines are discovery leads; verify critical claims against the original publisher and official advisories.")
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
    hero("REAL-WORLD LAYER · MARITIME INTELLIGENCE", "Strait of Hormuz | Live Situation",
         "Operational status, port geography, monitoring reference points and current maritime indicators.")
    status = load_status_record(ROOT)
    status_value = str(status.get("status", "UNVERIFIED")).upper()
    status_labels = {"NORMAL":"OPEN / NORMAL", "RESTRICTED":"RESTRICTED", "SEVERELY_DISRUPTED":"SEVERELY DISRUPTED",
                     "FORMALLY_CLOSED":"FORMALLY CLOSED", "UNVERIFIED":"RESTRICTED"}
    status_label = status_labels.get(status_value, status_value.replace("_", " "))
    # Show elapsed time since the dated disruption reference, not formal closure.
    # A disruption date does not establish that the Strait is legally closed.
    disruption_date_raw = status.get("disruption_start_date")
    duration = "Not recorded"
    duration_note = "A valid disruption_start_date is required in data/external/status.json."
    if disruption_date_raw:
        try:
            disruption_date = date.fromisoformat(str(disruption_date_raw)[:10])
            elapsed = max(0, (date.today() - disruption_date).days)
            duration = f"{elapsed:,} days"
            duration_note = (
                f"Elapsed calendar days since {disruption_date.isoformat()}; "
                f"source: {status.get('source_name', 'not recorded')}. "
                "This is disruption duration, not duration of a formal legal closure."
            )
        except (TypeError, ValueError):
            duration_note = "The disruption start date is invalid; expected YYYY-MM-DD."
    ais_snapshot = load_hormuz_ais_snapshot()
    ais_vessels = ais_snapshot.get("vessels", [])
    ais_count = ais_snapshot.get("area_count", len(ais_vessels))
    provider_ais_count = ais_snapshot.get("provider_count")
    a,b,c,d=st.columns(4)
    a.metric("OPERATIONAL STATUS",status_label)
    b.metric("DAYS SINCE DISRUPTION",duration,help=duration_note)
    c.metric("REFERENCE PORTS", "8", help="Geographic markers shown on the map; not live port activity.")
    d.metric("AIS POSITIONS IN MAP AREA", f"{ais_count:,}" if not ais_snapshot.get("error") else "Unavailable",
             help="Provider-reported AIS-derived positions returned by hormuz.now within the map-area bounds.")
    st.caption(f"Source: {status.get('source_name','Not recorded')} · Updated: {status.get('updated_at') or 'Not recorded'} · "
               f"[Open source record]({status.get('source_url','https://www.ukmto.org/ukmto-products')})")
    st.markdown('<div class="warn"><b>Interpretation:</b> Restricted commercial traffic does not by itself establish a formal legal closure. The marked monitoring points and corridor are geographic references, not official checkpoints, navigational advice or live control boundaries.</div>', unsafe_allow_html=True)
    if not ais_snapshot.get("error"):
        provider_label = f"{provider_ais_count:,}" if provider_ais_count is not None else "Not reported"
        st.caption(f"AIS provider snapshot total: {provider_label} · positions inside map bounds: {ais_count:,}")
    map_col, info_col = st.columns([2.15,1])
    with map_col:
        st.subheader("Strait of Hormuz · satellite map & AIS positions")
        if ais_snapshot.get("error"):
            st.caption("AIS overlay unavailable: " + ais_snapshot["error"])
        else:
            st.caption(f"AIS overlay: {ais_count:,} positions inside map bounds · provider snapshot: {provider_ais_count:,} · checked {ais_snapshot['checked_at'].strftime('%H:%M:%S UTC')}")
        render_hormuz_map(720, ais_vessels)
        st.caption("Dark nautical map centred more tightly on the Strait. Switch basemaps and toggle reference ports, monitoring areas and the illustrative corridor. Markers are geographic references, not live AIS or official checkpoints.")
    with info_col:
        st.subheader("Operational record")
        st.markdown(f"**Status:** {status_label}")
        st.markdown(f"**Record updated:** {status.get('updated_at') or 'Not recorded'}")
        st.markdown(f"**Source:** {status.get('source_name') or 'Not recorded'}")
        st.write(status.get('summary') or 'No source-backed operational summary has been entered.')
        st.divider()
        st.subheader("Authoritative monitoring")
        links=[("UKMTO advisories","https://www.ukmto.org/ukmto-products"),("JMIC","https://www.ukmto.org/"),
               ("IMO","https://www.imo.org/"),("IMF PortWatch","https://portwatch.imf.org/")]
        for label,url in links: st.markdown(f"- [{label}]({url})")
        st.divider()
        st.subheader("Recent registered events")
        events_path=ROOT/"data"/"external"/"historical_events.csv"
        if events_path.exists():
            events=pd.read_csv(events_path)
            if not events.empty:
                if "date" in events.columns: events=events.sort_values("date",ascending=False)
                st.dataframe(events.head(8),use_container_width=True,hide_index=True)
            else: st.info("No sourced events have been entered in historical_events.csv.")
        else: st.info("No event register found.")

elif page == "2 · Vessel Traffic":
    hero("REAL-WORLD LAYER · PUBLIC AIS-DERIVED FEED", "Vessel Traffic & Maritime Activity",
         "Provider-reported vessel positions, recent commercial crossings and daily traffic context.")
    st.markdown('<div class="warn"><b>Coverage limitation:</b> AIS is not complete vessel surveillance. Positions may be delayed, missing, spoofed or unavailable for vessels not transmitting AIS. This feed is third-party AIS-derived data, not a direct local receiver and not navigational advice.</div>', unsafe_allow_html=True)

    refresh_ais = st.button("↻ Refresh AIS and traffic data", type="primary")
    if refresh_ais:
        load_hormuz_ais_snapshot.clear()
        load_hormuz_crossings.clear()
        load_hormuz_daily.clear()

    snapshot = load_hormuz_ais_snapshot()
    vessels = pd.DataFrame(snapshot.get("vessels", []))
    crossings_payload = load_hormuz_crossings(24, 1)
    daily_payload = load_hormuz_daily()

    v1, v2, v3, v4 = st.columns(4)
    if snapshot.get("error"):
        v1.metric("AIS POSITIONS IN MAP AREA", "Unavailable")
    else:
        v1.metric("AIS POSITIONS IN MAP AREA", f"{len(vessels):,}")
    v2.metric("PROVIDER SNAPSHOT TOTAL", f"{snapshot.get('provider_count', 0):,}" if not snapshot.get("error") else "—")
    v3.metric("RECENT CROSSINGS · 24H", f"{len(crossings_payload.get('records', [])):,}" if not crossings_payload.get("error") else "Unavailable")
    v4.metric("DATA SOURCE", "hormuz.now")

    st.caption("Snapshot checked: " + snapshot.get("checked_at", datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S UTC"))
    if snapshot.get("error"):
        st.error("AIS snapshot unavailable: " + snapshot["error"])
    else:
        if not vessels.empty:
            category_col = st.selectbox("Vessel category", ["All"] + sorted(vessels["category"].fillna(vessels["type"]).astype(str).unique().tolist()))
            filtered = vessels.copy()
            if category_col != "All":
                filtered = filtered[filtered["category"].fillna(filtered["type"]).astype(str) == category_col]
            m1, m2 = st.columns([1.7, 1])
            with m1:
                st.subheader("AIS-derived positions · Strait region")
                st.map(filtered[["lat", "lon"]], zoom=5, use_container_width=True)
                st.caption("Map points are provider-reported AIS-derived positions within the dashboard's broad geographic bounds. They are not verified ship tracks.")
            with m2:
                st.subheader("Vessel category mix")
                mix = filtered.assign(DisplayCategory=filtered["category"].fillna(filtered["type"]).fillna("Unclassified")).groupby("DisplayCategory").size().reset_index(name="Vessels")
                if not mix.empty:
                    st.plotly_chart(px.pie(mix, names="DisplayCategory", values="Vessels", hole=.55, template="plotly_dark"), use_container_width=True)
            display_cols = [c for c in ["name", "id", "category", "type", "flag", "speed", "course", "ageMin", "lat", "lon"] if c in filtered.columns]
            st.subheader("Vessel position records")
            st.dataframe(filtered[display_cols].sort_values("ageMin", na_position="last") if "ageMin" in display_cols else filtered[display_cols],
                         use_container_width=True, hide_index=True, height=420)
        else:
            st.info("The provider returned no vessel positions within the current Strait-region map bounds.")

    st.subheader("Recent commercial crossings")
    if crossings_payload.get("error"):
        st.warning("Crossing feed unavailable: " + crossings_payload["error"])
    elif crossings_payload.get("records"):
        crossing_df = pd.DataFrame(crossings_payload["records"])
        st.caption(f"Provider returned {len(crossing_df):,} crossing records for the last 24 hours. Some records may be interpolated; inspect the provider fields before interpreting them.")
        st.dataframe(crossing_df, use_container_width=True, hide_index=True)
    else:
        st.info("No recent commercial crossing records were returned.")

    st.subheader("Daily traffic history")
    if daily_payload.get("error"):
        st.warning("Daily traffic feed unavailable: " + daily_payload["error"])
    elif daily_payload.get("records"):
        daily_df = pd.DataFrame(daily_payload["records"])
        date_col = next((c for c in daily_df.columns if c.lower() in ["date", "day", "timestamp", "period", "date_utc"]), None)
        count_col = next((c for c in daily_df.columns if c.lower() in ["crossings", "transits", "count", "vessels", "commercial_crossings", "total"]), None)
        if date_col and count_col:
            daily_df[date_col] = pd.to_datetime(daily_df[date_col], errors="coerce", utc=True)
            daily_df[count_col] = pd.to_numeric(daily_df[count_col], errors="coerce")
            daily_df = daily_df.dropna(subset=[date_col, count_col]).sort_values(date_col)
            if not daily_df.empty:
                st.plotly_chart(px.line(daily_df, x=date_col, y=count_col, markers=True,
                                        title="Provider-reported daily crossings",
                                        template="plotly_dark"), use_container_width=True)
        else:
            st.caption("Daily endpoint responded, but its field names were not recognised for automatic charting. Raw records are shown below.")
        st.dataframe(daily_df if "daily_df" in locals() else pd.DataFrame(daily_payload["records"]),
                     use_container_width=True, hide_index=True)
    else:
        st.info("The daily traffic endpoint returned no records.")

    st.caption("Source: hormuz.now public API · Snapshot cache: 20 seconds · Crossings cache: 2 minutes · Daily history cache: 15 minutes. Counts and coverage are provider-defined and should not be treated as a complete census of Strait traffic.")

elif page == "3 · News & Events":
    hero("REAL-WORLD LAYER · INTELLIGENCE FEED", "Latest News & Events",
         "A focused maritime watchlist for security incidents, shipping disruption, diplomacy and energy developments.")
    f1,f2,f3=st.columns([2,1,1])
    query=f1.text_input("Search topic", "Strait of Hormuz", help="Search terms are sent to the RSS news index.")
    category=f2.selectbox("Category",["All","Security","Shipping","Diplomacy","Energy","Other"])
    days=f3.selectbox("Date window",[1,3,7,14,30],index=2,format_func=lambda n:f"Last {n} days")
    r1,r2=st.columns([1,4])
    refresh=r1.button("↻ Refresh intelligence feed",type="primary",use_container_width=True)
    if refresh: st.cache_data.clear()
    news,errors,refreshed=load_news(query,days)
    if not news.empty:
        news=news.copy()
        if "source_type" not in news.columns:
            news["source_type"]="News index / publisher not independently classified"
        if "incident_flag" not in news.columns:
            news["incident_flag"]=news["category"].eq("Security")
        if category!="All": news=news[news["category"]==category]
        f4,f5=st.columns([1,2])
        source_filter=f4.selectbox("Source class",["All sources"]+sorted(news["source_type"].dropna().unique().tolist()))
        search_filter=f5.text_input("Filter headlines or summaries", "", help="Filters the articles already fetched; it does not make another feed request.")
        if source_filter!="All sources": news=news[news["source_type"]==source_filter]
        if search_filter.strip():
            mask=(news["title"].str.contains(search_filter,case=False,na=False)|news["summary"].str.contains(search_filter,case=False,na=False))
            news=news[mask]
        # Security reports are surfaced first, then sorted by publication time.
        news["_priority"]=news["incident_flag"].astype(int)
        news=news.sort_values(["_priority","_published_dt"],ascending=[False,False],na_position="last") if "_published_dt" in news.columns else news.sort_values("incident_flag",ascending=False)
    else:
        source_filter="All sources"
        search_filter=""
    st.caption(f"Last feed check: {refreshed} · Matching reports: {len(news)} · Discovery index: Google News RSS. Publisher links and timestamps are shown where supplied.")
    if errors: st.warning("Some feeds could not be reached: "+" · ".join(errors[:4]))
    if news.empty:
        st.info("No matching articles were returned. Try a broader search, longer date window or another category.")
    else:
        security_count=int(news["incident_flag"].fillna(False).sum()) if "incident_flag" in news else 0
        media_count=int(news["source_type"].astype(str).str.contains("News media",case=False).sum())
        n1,n2,n3=st.columns(3)
        n1.metric("REPORTS MATCHING FILTERS",f"{len(news):,}")
        n2.metric("SECURITY / INCIDENT REPORTS",f"{security_count:,}")
        n3.metric("IDENTIFIED NEWS MEDIA SOURCES",f"{media_count:,}")
        left,right=st.columns([2.1,1])
        with left:
            st.subheader("Priority reports & latest coverage")
            for _,row in news.head(35).iterrows():
                with st.container(border=True):
                    if bool(row.get("incident_flag",False)):
                        st.markdown('<span style="background:#5a2c25;color:#ffd7c7;padding:4px 8px;border-radius:5px;font-size:11px;font-weight:700">SECURITY / INCIDENT</span>',unsafe_allow_html=True)
                    title=str(row.get("title","Untitled"))
                    st.markdown(f"#### [{title}]({row.get('url','#')})")
                    st.caption(f"{row.get('source','Publisher not identified')} · {row.get('published','Time not supplied')} · {row.get('category','Other')} · {row.get('source_type','Source class not available')}")
                    summary=str(row.get("summary","")).strip()
                    if summary: st.write(summary[:420])
                    st.markdown(f"[Open original report ↗]({row.get('url','#')})")
        with right:
            st.subheader("Coverage by category")
            counts=news["category"].value_counts().rename_axis("Category").reset_index(name="Articles")
            if not counts.empty:
                fig=px.bar(counts,x="Articles",y="Category",orientation="h",template="plotly_dark",color="Category")
                fig.update_layout(paper_bgcolor="#071827",plot_bgcolor="#071827",font_color="#e8f1f8",showlegend=False,margin=dict(l=5,r=5,t=15,b=5),height=300)
                st.plotly_chart(fig,use_container_width=True)
            st.subheader("Chronological event timeline")
            timeline=news.copy()
            if "_published_dt" in timeline.columns:
                timeline=timeline.sort_values("_published_dt",ascending=False,na_position="last")
            for _,row in timeline.head(14).iterrows():
                st.markdown(f"**{row.get('published','Date not supplied')}**")
                st.write(str(row.get("title","")))
                st.caption(f"{row.get('source','Source not identified')} · {row.get('category','Other')}")
                st.divider()
    st.markdown('<div class="note"><b>Source discipline:</b> RSS results are discovery leads, not verified incident records. A publisher label does not mean the underlying event has been independently confirmed. Verify navigational warnings and security incidents against official UKMTO/JMIC/IMO notices and the original reporting outlet.</div>',unsafe_allow_html=True)
    st.subheader("Primary and established reporting channels")
    source_cols=st.columns(5)
    for col,(label,url) in zip(source_cols,[("UKMTO","https://www.ukmto.org/ukmto-products"),("JMIC","https://www.ukmto.org/"),("IMO","https://www.imo.org/"),("Reuters","https://www.reuters.com/world/"),("AP News","https://apnews.com/")]):
        with col: st.link_button(label,url,use_container_width=True)

elif page == "4 · Energy Impact":
    hero("REAL-WORLD LAYER · ENERGY & TRAFFIC", "Oil, Energy & Economic Impact",
         "Compare dated energy-market benchmarks with Strait traffic, security reporting and the operational record.")

    # Status and disruption reference are repeated here so the energy page can be read independently.
    status_energy = load_status_record(ROOT)
    status_value_energy = str(status_energy.get("status", "UNVERIFIED")).upper()
    status_label_energy = {
        "NORMAL": "OPEN / NORMAL",
        "RESTRICTED": "RESTRICTED",
        "SEVERELY_DISRUPTED": "SEVERELY DISRUPTED",
        "FORMALLY_CLOSED": "FORMALLY CLOSED",
        "UNVERIFIED": "RESTRICTED",
    }.get(status_value_energy, status_value_energy.replace("_", " "))
    disruption_raw_energy = status_energy.get("disruption_start_date")
    disruption_age_energy = "Not recorded"
    if disruption_raw_energy:
        try:
            disruption_age_energy = f"{max(0, (date.today() - date.fromisoformat(str(disruption_raw_energy)[:10])).days):,} days"
        except (TypeError, ValueError):
            pass

    e1, e2, e3 = st.columns(3)
    e1.metric("OPERATIONAL STATUS", status_label_energy)
    e2.metric("DAYS SINCE DISRUPTION", disruption_age_energy)
    e3.metric("STATUS RECORD UPDATED", str(status_energy.get("updated_at") or "Not recorded"))
    st.caption(
        f"Status source: {status_energy.get('source_name') or 'Not recorded'} · "
        f"[Open source record]({status_energy.get('source_url') or 'https://www.ukmto.org/ukmto-products'})"
    )
    st.markdown(
        '<div class="warn"><b>Interpretation:</b> Market-price movements and reduced traffic may coincide with security events, '
        'but correlation does not establish that a specific Strait event caused a price change. The status label is the dashboard’s '
        'recorded assessment, not an independent legal determination.</div>',
        unsafe_allow_html=True,
    )

    st.subheader("Energy-market benchmarks")
    period_days = st.selectbox(
        "Market history window", [90, 180, 365, 730],
        index=2, format_func=lambda n: f"Last {n} days", key="energy_market_window"
    )
    market_df, market_errors, market_checked = load_fred_energy_series(period_days)
    st.caption(f"Source: Federal Reserve Bank of St. Louis · FRED · Checked {market_checked.strftime('%Y-%m-%d %H:%M UTC')} · Daily observations where published.")
    if not market_df.empty:
        latest_market = (
            market_df.sort_values("date")
            .groupby("benchmark", as_index=False).tail(1)
            .sort_values("benchmark")
        )
        metric_cols = st.columns(max(1, len(latest_market)))
        for col, (_, row) in zip(metric_cols, latest_market.iterrows()):
            col.metric(
                str(row["benchmark"]).upper(),
                f"{row['value']:,.2f}",
                f"{row['unit']} · {row['date'].date()}"
            )
        market_chart = px.line(
            market_df, x="date", y="value", color="benchmark",
            facet_row="benchmark", facet_row_spacing=0.06,
            labels={"date": "Observation date", "value": "Price", "benchmark": "Benchmark"},
            title="Historical energy benchmark prices",
            template="plotly_dark"
        )
        market_chart.update_yaxes(matches=None, showticklabels=True)
        market_chart.update_layout(
            paper_bgcolor="#071827", plot_bgcolor="#071827",
            font_color="#e8f1f8", height=620, showlegend=False,
            margin=dict(l=10, r=10, t=55, b=10)
        )
        st.plotly_chart(market_chart, use_container_width=True)
        with st.expander("View market observations and series definitions"):
            st.dataframe(market_df.sort_values(["benchmark", "date"], ascending=[True, False]),
                         use_container_width=True, hide_index=True)
            st.markdown(
                "- **Brent crude (DCOILBRENTEU):** Europe Brent spot price, USD per barrel.\n"
                "- **WTI crude (DCOILWTICO):** Cushing, Oklahoma WTI spot price, USD per barrel.\n"
                "- **Henry Hub (DHHNGSP):** US natural-gas spot benchmark, USD per MMBtu; **not** an LNG cargo price or Asian LNG benchmark."
            )
    else:
        st.warning("FRED benchmark series could not be loaded. " + (" · ".join(market_errors) if market_errors else "No observations returned."))
    if market_errors:
        with st.expander("Market-data source diagnostics"):
            for error in market_errors:
                st.caption(error)

    st.divider()
    traffic_col, event_col = st.columns([1.05, 1.25])
    with traffic_col:
        st.subheader("Strait traffic context")
        traffic_payload_energy = load_hormuz_daily()
        crossings_payload_energy = load_hormuz_crossings(24, 1)
        if traffic_payload_energy.get("error"):
            st.warning("Daily traffic feed unavailable: " + traffic_payload_energy["error"])
        elif traffic_payload_energy.get("records"):
            traffic_energy_df = pd.DataFrame(traffic_payload_energy["records"])
            traffic_date_col = next((c for c in traffic_energy_df.columns if c.lower() in ["date", "day", "timestamp", "period", "date_utc"]), None)
            traffic_count_col = next((c for c in traffic_energy_df.columns if c.lower() in ["crossings", "transits", "count", "vessels", "commercial_crossings", "total"]), None)
            if traffic_date_col and traffic_count_col:
                traffic_energy_df[traffic_date_col] = pd.to_datetime(traffic_energy_df[traffic_date_col], errors="coerce", utc=True)
                traffic_energy_df[traffic_count_col] = pd.to_numeric(traffic_energy_df[traffic_count_col], errors="coerce")
                traffic_energy_df = traffic_energy_df.dropna(subset=[traffic_date_col, traffic_count_col]).sort_values(traffic_date_col)
                if not traffic_energy_df.empty:
                    st.metric("LATEST PROVIDER-REPORTED DAILY CROSSINGS", f"{traffic_energy_df.iloc[-1][traffic_count_col]:,.0f}",
                              str(traffic_energy_df.iloc[-1][traffic_date_col].date()))
                    st.plotly_chart(
                        px.line(traffic_energy_df, x=traffic_date_col, y=traffic_count_col, markers=True,
                                title="Daily crossings reported by hormuz.now", template="plotly_dark"),
                        use_container_width=True
                    )
                else:
                    st.info("The daily feed returned no usable date/count observations.")
            else:
                st.info("Daily feed responded, but its fields were not recognised for charting.")
                st.dataframe(traffic_energy_df, use_container_width=True, hide_index=True)
        else:
            st.info("No daily traffic records were returned.")
        if crossings_payload_energy.get("error"):
            st.caption("24-hour crossing feed: " + crossings_payload_energy["error"])
        else:
            st.metric("COMMERCIAL CROSSING RECORDS · LAST 24H", f"{len(crossings_payload_energy.get('records', [])):,}")
        st.caption("Traffic source: hormuz.now public AIS-derived feed. Coverage is incomplete and provider-defined; counts are not a complete census of Strait movements.")

    with event_col:
        st.subheader("Security and energy event watch")
        news_energy, news_energy_errors, news_energy_checked = load_news("Strait of Hormuz oil energy shipping security", 14)
        if not news_energy.empty:
            watch = news_energy[news_energy["category"].isin(["Energy", "Security", "Shipping"])].copy()
            if "_published_dt" in watch.columns:
                watch = watch.sort_values("_published_dt", ascending=False, na_position="last")
            if not watch.empty:
                for _, item in watch.head(7).iterrows():
                    with st.container(border=True):
                        st.markdown(f'**[{item["title"]}]({item["url"]})**')
                        st.caption(f'{item.get("source", "Publisher not identified")} · {item.get("published", "Time not supplied")} · {item.get("category", "Other")}')
                        if str(item.get("summary") or "").strip():
                            st.write(str(item["summary"])[:240])
            else:
                st.info("No Energy, Security or Shipping items matched the current 14-day watch.")
        else:
            st.info("No current news items were returned.")
        st.caption(f"News feed checked: {news_energy_checked} · Google News RSS is a discovery index, not independent verification.")
        if news_energy_errors:
            st.caption("Some feeds unavailable: " + " · ".join(news_energy_errors[:2]))

    st.divider()
    st.subheader("Energy-flow and chokepoint reference")
    st.markdown(
        "The Strait is a major route for crude oil, petroleum products and LNG. Use dated EIA and IMF PortWatch extracts "
        "for quantitative flow estimates; do not substitute AIS crossing counts for oil-volume measurements."
    )
    st.markdown(
        "- [U.S. EIA — World Oil Transit Chokepoints](https://www.eia.gov/international/analysis/special-topics/World_Oil_Transit_Chokepoints)\n"
        "- [U.S. EIA Open Data](https://www.eia.gov/opendata/)\n"
        "- [IMF PortWatch](https://portwatch.imf.org/)\n"
        "- [World Bank Commodity Markets](https://www.worldbank.org/en/research/commodity-markets)"
    )
    context_file_energy = ROOT / "data" / "external" / "energy_indicators.csv"
    if context_file_energy.exists():
        context_df_energy = pd.read_csv(context_file_energy)
        st.subheader("Imported, dated energy-flow indicators")
        st.dataframe(context_df_energy, use_container_width=True, hide_index=True)
        st.caption("Imported values are shown with their own reference period and source fields. Confirm units and provenance before citing.")
    else:
        st.info("No local energy-flow extract is present. Oil and gas price series above are market benchmarks; they do not measure volumes transiting the Strait.")

    st.markdown(
        '<div class="note"><b>Data discipline:</b> Brent and WTI are crude-oil price benchmarks. Henry Hub is a US natural-gas benchmark, not an LNG price. '
        'hormuz.now crossings are AIS-derived vessel records, not oil-volume data. Event reports are leads; price co-movement does not establish causation. '
        'No missing values are replaced with synthetic data.</div>',
        unsafe_allow_html=True
    )

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
