from pathlib import Path
from datetime import datetime, timezone, timedelta
import pandas as pd
import requests
import feedparser
import re
import calendar
from html import unescape
from urllib.parse import quote_plus
import streamlit as st

NEWS_FEEDS = [
 ("Reuters","https://news.google.com/rss/search?q=site%3Areuters.com+%22Strait+of+Hormuz%22&hl=en-US&gl=US&ceid=US:en"),
 ("AP News","https://news.google.com/rss/search?q=site%3Aapnews.com+%22Strait+of+Hormuz%22&hl=en-US&gl=US&ceid=US:en"),
 ("BBC","https://news.google.com/rss/search?q=site%3Abbc.com+%22Strait+of+Hormuz%22&hl=en-US&gl=US&ceid=US:en"),
 ("General","https://news.google.com/rss/search?q=%22Strait+of+Hormuz%22+shipping&hl=en-US&gl=US&ceid=US:en"),
]

def load_status_record(root):
    p = root / "data/external/status.json"
    if not p.exists():
        return {"status":"UNVERIFIED","updated_at":"Not supplied","source_name":"No source record",
                "disruption_start_date":None,"closure_start_date":None,"source_url":None,
                "summary":"No operational status has been entered. Check UKMTO/JMIC/IMO directly."}
    try:
        import json
        record = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("status.json must contain a JSON object")
        record.setdefault("disruption_start_date", None)
        record.setdefault("closure_start_date", None)
        record.setdefault("source_url", None)
        return record
    except Exception:
        return {"status":"UNVERIFIED","updated_at":"Invalid status record","source_name":"Local JSON",
                "summary":"Could not parse status.json."}

@st.cache_data(ttl=900, show_spinner=False)
def _fetch_news(query, days):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    items, errors, seen = [], [], set()
    q = quote_plus(query.strip() or "Strait of Hormuz")
    feeds = [
        ("Google News · Reuters index", f"https://news.google.com/rss/search?q=site%3Areuters.com+{q}&hl=en-US&gl=US&ceid=US:en"),
        ("Google News · AP index", f"https://news.google.com/rss/search?q=site%3Aapnews.com+{q}&hl=en-US&gl=US&ceid=US:en"),
        ("Google News · BBC index", f"https://news.google.com/rss/search?q=site%3Abbc.com+{q}&hl=en-US&gl=US&ceid=US:en"),
        ("Google News · broader index", f"https://news.google.com/rss/search?q={q}+shipping&hl=en-US&gl=US&ceid=US:en"),
    ]
    official_terms = ("ukmto", "jmic", "imo", "international maritime organization", "u.s. energy information administration", "eia")
    media_terms = ("reuters", "associated press", "ap news", "bbc", "al jazeera", "the guardian", "financial times", "bloomberg", "the new york times", "the new region", "cnn")
    incident_terms = ("attack", "attacked", "strike", "struck", "projectile", "missile", "drone", "mine", "seized", "seizure", "hijack", "hijacked", "crew missing", "crew abandoned", "explosion", "fire on board", "security incident", "warning")
    for feed_label, url in feeds:
        try:
            feed = feedparser.parse(url)
            if getattr(feed, "bozo", False) and not feed.entries:
                errors.append(f"{feed_label}: feed parse error")
            for entry in feed.entries:
                title = unescape(entry.get("title", "")).strip()
                link = entry.get("link", "")
                if not title or not link:
                    continue
                published = entry.get("published", "")
                dt = None
                if entry.get("published_parsed"):
                    dt = datetime.fromtimestamp(calendar.timegm(entry.published_parsed), timezone.utc)
                    if dt < cutoff:
                        continue
                key = re.sub(r"\W+", "", title.lower())
                if key in seen:
                    continue
                seen.add(key)
                raw_summary = unescape(re.sub(r"<[^>]+>", " ", entry.get("summary", "")))
                summary = re.sub(r"\s+", " ", raw_summary).strip()
                text = (title + " " + summary).lower()
                if any(w in text for w in incident_terms):
                    category = "Security"
                elif any(w in text for w in ["oil", "lng", "lpg", "energy", "crude", "price", "gas"]):
                    category = "Energy"
                elif any(w in text for w in ["talk", "negotiat", "diplomat", "iran", "united states", "sanction"]):
                    category = "Diplomacy"
                elif any(w in text for w in ["ship", "tanker", "port", "shipping", "transit", "vessel"]):
                    category = "Shipping"
                else:
                    category = "Other"
                source_obj = entry.get("source", {})
                publisher = source_obj.get("title") if isinstance(source_obj, dict) else None
                source_name = publisher or feed_label
                source_lower = str(source_name).lower()
                if any(term in source_lower for term in official_terms):
                    source_type = "Official / institutional label"
                elif any(term in source_lower for term in media_terms):
                    source_type = "News media label"
                else:
                    source_type = "News index / other publisher"
                items.append({"title": title, "url": link, "source": source_name,
                              "published": published, "summary": summary[:650], "category": category,
                              "source_type": source_type,
                              "incident_flag": any(term in text for term in incident_terms),
                              "_published_dt": dt or pd.NaT,
                              "_sort": dt or datetime.min.replace(tzinfo=timezone.utc)})
        except Exception as ex:
            errors.append(f"{feed_label}: {str(ex)[:120]}")
    items.sort(key=lambda item: (item["incident_flag"], item["_sort"]), reverse=True)
    # Collapse near-identical headlines from different RSS queries while retaining the strongest/latest entry.
    deduped = []
    for item in items:
        norm = re.sub(r"[^a-z0-9]+", " ", item["title"].lower()).strip()
        tokens = {t for t in norm.split() if len(t) > 2}
        duplicate = False
        for prior in deduped:
            prior_norm = re.sub(r"[^a-z0-9]+", " ", prior["title"].lower()).strip()
            prior_tokens = {t for t in prior_norm.split() if len(t) > 2}
            if tokens and prior_tokens and len(tokens & prior_tokens) / max(len(tokens | prior_tokens), 1) >= 0.82:
                duplicate = True
                break
        if not duplicate:
            deduped.append(item)
    for item in deduped:
        item.pop("_sort", None)
    return pd.DataFrame(deduped), errors

def load_news(query, days):
    # The feed queries are Strait-specific by design; query is shown in UI for transparency.
    df, errors = _fetch_news(query, days)
    return df, errors, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def load_eia_series(api_url, api_key):
    try:
        url = api_url + ("&" if "?" in api_url else "?") + "api_key=" + api_key
        r = requests.get(url,timeout=20)
        r.raise_for_status()
        payload = r.json()
        rows = payload.get("response",{}).get("data",[])
        if not rows:
            return pd.DataFrame(), "EIA returned no response.data rows. Check the configured API Explorer URL and series.", datetime.now(timezone.utc)
        df = pd.DataFrame(rows)
        if "period" not in df or "value" not in df:
            return pd.DataFrame(), "EIA response did not contain period/value fields.", datetime.now(timezone.utc)
        df["value"] = pd.to_numeric(df["value"],errors="coerce")
        return df[["period","value"]].dropna().sort_values("period"), None, datetime.now(timezone.utc)
    except Exception as e:
        return pd.DataFrame(), f"EIA request failed: {e}", datetime.now(timezone.utc)

def load_portwatch_csv(file):
    return pd.read_csv(file)

def load_ais_csv(file):
    return pd.read_csv(file)

def source_health():
    return {"news":"RSS refreshable","UKMTO":"Official link/manual verification",
            "PortWatch":"CSV import / portal","AIS":"Public hormuz.now snapshot · refreshable",
            "EIA":"API key + exact API Explorer URL required"}

HORMUZ_NOW_BASE = "https://hormuz.now"

def _find_records(payload):
    """Return record rows from common API envelopes, preferring explicit row keys."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        # Compact APIs often expose parallel `fields` and `rows` arrays.
        # Prefer `rows` so the schema list is never mistaken for vessel records.
        for key in ("rows", "vessels", "data", "items", "results", "snapshot",
                    "records", "crossings", "daily", "traffic"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        for value in payload.values():
            if isinstance(value, (dict, list)):
                found = _find_records(value)
                if found:
                    return found
    return []


def _normalise_vessel_rows(payload):
    """Normalise hormuz.now compact rows using the provider's own `fields` schema."""
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        rows = payload["rows"]
        fields = payload.get("fields")
        if isinstance(fields, list) and fields:
            records = [
                dict(zip(fields, row))
                for row in rows
                if isinstance(row, (list, tuple))
            ]
            # Keep already-expanded records if the endpoint mixes formats.
            records.extend(row for row in rows if isinstance(row, dict))
        else:
            records = [row for row in rows if isinstance(row, dict)]
    else:
        records = _find_records(payload)

    aliases = {
        "id": ("id", "mmsi", "imo"),
        "name": ("name", "vessel_name"),
        "lat": ("lat", "latitude"),
        "lon": ("lon", "lng", "longitude"),
        "speed": ("speed", "sog"),
        "course": ("course", "cog"),
        "heading": ("heading",),
        "category": ("category", "group"),
        "length": ("length",),
        "flag": ("flag", "flag_code"),
        "type": ("type", "ship_type"),
        "destination": ("destination",),
        "dwt": ("dwt",),
        "ageMin": ("ageMin", "age_min", "position_age_min"),
        "commercial": ("commercial",),
        "side": ("side",),
    }

    normalised = []
    for row in records:
        if not isinstance(row, dict):
            continue
        out = {
            target: next((row.get(name) for name in names if row.get(name) is not None), None)
            for target, names in aliases.items()
        }
        try:
            out["lat"] = float(out["lat"])
            out["lon"] = float(out["lon"])
        except (TypeError, ValueError):
            continue
        if not (-90 <= out["lat"] <= 90 and -180 <= out["lon"] <= 180):
            continue

        # Convert numeric fields where supplied; preserve identifiers and labels.
        for field in ("speed", "course", "heading", "length", "dwt", "ageMin", "commercial", "side"):
            if out[field] is not None:
                try:
                    out[field] = float(out[field])
                except (TypeError, ValueError):
                    pass
        normalised.append(out)

    return normalised

@st.cache_data(ttl=20, show_spinner=False)
def load_hormuz_ais_snapshot():
    """Fetch public AIS-derived snapshot; positions remain provider-reported observations."""
    checked = datetime.now(timezone.utc)
    try:
        response = requests.get(
            f"{HORMUZ_NOW_BASE}/api/snapshot?format=compact",
            headers={"User-Agent": "Hormuz-Intelligence-Dashboard/1.0"},
            timeout=18
        )
        response.raise_for_status()
        payload = response.json()
        vessels = _normalise_vessel_rows(payload)
        provider_count = payload.get("n", len(vessels)) if isinstance(payload, dict) else len(vessels)
        try:
            provider_count = int(provider_count)
        except (TypeError, ValueError):
            provider_count = len(vessels)

        if not vessels:
            return {"vessels": [], "provider_count": provider_count, "area_count": 0,
                    "error": "Snapshot responded, but no valid vessel coordinates could be parsed.",
                    "checked_at": checked, "provider": "hormuz.now"}

        df = pd.DataFrame(vessels)
        # Dashboard theatre bounds; provider-wide total remains a separate metric.
        area = df[df["lat"].between(23.0, 30.5) & df["lon"].between(50.0, 62.5)].copy()
        return {"vessels": area.to_dict("records"), "provider_count": provider_count,
                "area_count": len(area), "checked_at": checked, "error": None,
                "provider": "hormuz.now"}
    except Exception as exc:
        return {"vessels": [], "provider_count": 0, "area_count": 0,
                "checked_at": checked, "error": str(exc)[:240], "provider": "hormuz.now"}

@st.cache_data(ttl=120, show_spinner=False)
def load_hormuz_crossings(hours=24, commercial=1):
    checked = datetime.now(timezone.utc)
    try:
        response = requests.get(
            f"{HORMUZ_NOW_BASE}/api/crossings",
            params={"hours": int(hours), "commercial": int(commercial)},
            headers={"User-Agent": "Hormuz-Intelligence-Dashboard/1.0"},
            timeout=18
        )
        response.raise_for_status()
        payload = response.json()
        rows = _find_records(payload)
        return {"records": rows, "checked_at": checked, "error": None,
                "provider": "hormuz.now"}
    except Exception as exc:
        return {"records": [], "checked_at": checked, "error": str(exc)[:240],
                "provider": "hormuz.now"}

@st.cache_data(ttl=900, show_spinner=False)
def load_hormuz_daily():
    checked = datetime.now(timezone.utc)
    try:
        response = requests.get(
            f"{HORMUZ_NOW_BASE}/api/daily.json",
            headers={"User-Agent": "Hormuz-Intelligence-Dashboard/1.0"},
            timeout=18
        )
        response.raise_for_status()
        payload = response.json()
        rows = _find_records(payload)
        return {"records": rows, "checked_at": checked, "error": None,
                "provider": "hormuz.now"}
    except Exception as exc:
        return {"records": [], "checked_at": checked, "error": str(exc)[:240],
                "provider": "hormuz.now"}


FRED_SERIES = {
    "Brent crude oil": {"id": "DCOILBRENTEU", "unit": "USD / barrel", "kind": "Oil benchmark"},
    "WTI crude oil": {"id": "DCOILWTICO", "unit": "USD / barrel", "kind": "Oil benchmark"},
    "Henry Hub natural gas": {"id": "DHHNGSP", "unit": "USD / MMBtu", "kind": "US natural-gas benchmark"},
}


@st.cache_data(ttl=3600, show_spinner=False)
def load_fred_energy_series(days=365):
    """Fetch public FRED benchmark price histories; values are market context, not Hormuz-attributed."""
    checked = datetime.now(timezone.utc)
    frames, errors = [], []
    end = checked.date()
    start = end - timedelta(days=int(days))
    for label, meta in FRED_SERIES.items():
        try:
            url = "https://fred.stlouisfed.org/graph/fredgraph.csv"
            response = requests.get(
                url,
                params={"id": meta["id"], "cosd": start.isoformat(), "coed": end.isoformat()},
                headers={"User-Agent": "Hormuz-Intelligence-Dashboard/1.0"},
                timeout=18,
            )
            response.raise_for_status()
            from io import StringIO
            frame = pd.read_csv(StringIO(response.text))
            if frame.empty or len(frame.columns) < 2:
                raise ValueError("FRED returned an empty or unrecognised CSV.")
            date_col = frame.columns[0]
            value_col = meta["id"] if meta["id"] in frame.columns else frame.columns[1]
            frame = frame.rename(columns={date_col: "date", value_col: "value"})
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
            frame["value"] = pd.to_numeric(frame["value"].replace(".", pd.NA), errors="coerce")
            frame = frame.dropna(subset=["date", "value"])
            if frame.empty:
                raise ValueError("No observations were returned for the selected period.")
            frame["benchmark"] = label
            frame["series_id"] = meta["id"]
            frame["unit"] = meta["unit"]
            frame["kind"] = meta["kind"]
            frames.append(frame[["date", "value", "benchmark", "series_id", "unit", "kind"]])
        except Exception as exc:
            errors.append(f"{label}: {str(exc)[:150]}")
    result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["date", "value", "benchmark", "series_id", "unit", "kind"]
    )
    return result, errors, checked
