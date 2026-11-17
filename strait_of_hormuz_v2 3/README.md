# Strait of Hormuz — Dashboard V2

A modular Streamlit dashboard for the M.Tech ORDA project **Vessel Schedule Recovery under Disruptions in the Strait of Hormuz**.

## Intelligence-first landing page
The Overview page is the operational landing screen: status, a reference map, recent RSS headlines, available vessel/energy snapshots and a compact Script 98 result explorer. The closure-duration counter is shown only when `status.json` explicitly records `FORMALLY_CLOSED` and a verified `closure_start_date` (YYYY-MM-DD). Otherwise it displays “Not established”. The embedded OpenStreetMap view is a geographic reference map, not live AIS.

## Six sections
1. Live Situation — status record and authoritative links; no automatic legal-closure inference.
2. Vessel Traffic — import PortWatch/AIS CSV; no invented vessel counts or positions.
3. News & Events — refreshable Google News RSS searches restricted to Reuters/AP/BBC domains plus a general feed.
4. Energy Impact — optional EIA API integration using a user-supplied exact API Explorer URL and key.
5. Research Simulation — interactive Script 76 primary results and Script 77 policy-level sensitivity comparison.
6. Methodology & Limits — protocol-aligned model explanation and explicit interpretation boundaries.

## Setup

```bash
cd strait_of_hormuz_v2
python -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env
```

### Load exact Script 98 data

The existing V1 dashboard contains the exact 80-row Script 98 primary JSON array. Put the existing Project Library file
`Strait_of_Hormuz_Interactive_Simulation_Dashboard.html` at:

`data/simulation/v1_dashboard.html`

Then run:

```bash
python scripts/extract_v1_data.py
```

This extracts the precomputed results verbatim. It does not rerun the experiment.

### Script 77 sensitivity data

Place the existing `Script77_Sensitivity_Consolidated.xlsx` in `data/simulation/` if you want to refresh the sensitivity summary. The package includes a separate policy-summary snapshot only when supplied by the researcher. Script 77 is never merged into Script 76 primary results.

## Run

```bash
streamlit run app.py
```

Open the local URL Streamlit prints (normally http://localhost:8501).

## External data status

| Feature | Behavior | Credentials |
|---|---|---|
| UKMTO status | Official links + local manually verified status record | No API assumed |
| News | RSS search via Google News; source-filtered Reuters/AP/BBC | No key |
| Vessel traffic | CSV import; AIS map only when lat/lon exist | PortWatch export or AIS provider access |
| IMF PortWatch | Official portal link and CSV import fallback | No undocumented endpoint assumed |
| EIA energy series | Calls exact API URL supplied in `.env` | Free EIA API key |
| MarineTraffic | Link/CSV fallback; no endpoint invented | Provider API access if used |

## Updating the operational status record

Edit `data/external/status.json` only after checking an authoritative source. Use one of:
`NORMAL`, `RESTRICTED`, `SEVERELY_DISRUPTED`, `FORMALLY_CLOSED`, `UNVERIFIED`.
For `FORMALLY_CLOSED`, require a formal authoritative notice. Record source name, URL, UTC timestamp, `closure_start_date` (YYYY-MM-DD) and a concise evidence-based summary. The Overview page calculates elapsed calendar days only from this verified date; it does not infer a closure date.

A fall in AIS transits or a news report is not by itself proof of legal closure.

## Methodological safeguards

- Historical port-call sequences do not prove actual sailing routes or Hormuz transit.
- Inter-port elapsed time is not necessarily pure sailing time.
- Port-call duration is not necessarily berth-processing time.
- Observed inter-call elapsed time is not established schedule slack.
- Preserve all 178 same-port links unless source-level verification justifies a change.
- Recovery credits are abstract interventions, not proven operational capability.
- Script 77's observed-interval cap is mathematical sensitivity only.
- Last represented call is not the vessel's actual final voyage call.
- A common horizon and internal numerical checks establish computational consistency, not operational validation.
- Do not claim statistical significance, confidence intervals or p-values for the deterministic experiment.

## Important source reconciliation note

The frozen protocol v1.1 and the prior simulation findings presentation differ on the transition-selection seed (8801 vs 7501). The app deliberately does not publish a single seed value until it is checked against the exact executed source script. Resolve this from the original run script before thesis publication.

## Known limitations in this build

- The Overview page loads recent headlines from RSS feeds; RSS availability, timestamps and coverage depend on the publishers/feed aggregator. Headlines are not a substitute for official advisories.
- The overview map is an OpenStreetMap geographic reference only; no live vessel positions are implied.
- The days-since-closure counter remains unavailable until a formal closure date is entered and sourced.


- The original Script 98 standalone CSV exports are not present as separate local files in the available Project artifacts. The exact 80-row primary result array is embedded in V1 HTML, and the included extractor imports it without recomputation.
- The live status section is intentionally marked UNVERIFIED until a dated authoritative update is entered.
- No AIS positions or daily transit counts are fabricated. Import a real export to populate charts and maps.
- The EIA integration requires an API Explorer URL for a specific series and a free API key.


## Connecting the original Script 98 results

The dashboard reads the canonical research CSVs directly from the parent
`Strait_of_Hormuz_Research/outputs/tables/` directory. Keep the original
project layout intact:

- `outputs/tables/98_final_scenario_policy_results.csv`
- `outputs/tables/98_final_call_level_paired_results.csv`
- `outputs/tables/98_final_vessel_level_results.csv`
- `outputs/tables/98_final_results_validation_checks.csv`

The dashboard does not modify these files or rerun the experiment. Script 77
continues to load from `strait_of_hormuz_v2/data/simulation/script77_policy_summary.csv`.
