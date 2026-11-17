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
                "summary":"No operational status has been entered. Check UKMTO/JMIC/IMO directly."}
    try:
        import json
        return json.loads(p.read_text(encoding="utf-8"))
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
            "PortWatch":"CSV import / portal","AIS":"Credential or CSV required",
            "EIA":"API key + exact API Explorer URL required"}
