"""
SCRIPT 18F1: AUTOMATED PORT SOURCE DISCOVERY

Purpose
-------
Discover candidate official/government/maritime sources for each of the
19 records in Script 18E. Save search results for later evidence extraction.

This is a discovery aid, not an automatic verification system:
- Search snippets are not proof.
- URLs and page titles must be checked.
- Search results may be incomplete or duplicated.
- A source being official does not mean every coordinate on it refers
  to the exact same facility/reference point.

Install dependencies:
    pip install pandas ddgs requests beautifulsoup4

Run from project root:
    python src/18F1_port_source_discovery.py

Input:
    outputs/tables/18E_port_facility_validation_register.csv

Outputs:
    outputs/tables/18F1_source_discovery_results.csv
    outputs/tables/18F1_source_discovery_summary.csv
    outputs/reports/18F1_source_discovery_report.txt
"""

from pathlib import Path
from urllib.parse import urlparse
import time
import re

import pandas as pd

try:
    from ddgs import DDGS
except ImportError as exc:
    raise SystemExit(
        "Missing package 'ddgs'. Install dependencies with:\n"
        "pip install pandas ddgs requests beautifulsoup4"
    ) from exc

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError as exc:
    raise SystemExit(
        "Missing package. Install dependencies with:\n"
        "pip install pandas ddgs requests beautifulsoup4"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / "outputs" / "tables" / "18E_port_facility_validation_register.csv"
OUTPUT_TABLES = ROOT / "outputs" / "tables"
OUTPUT_REPORTS = ROOT / "outputs" / "reports"

OUTPUT_TABLES.mkdir(parents=True, exist_ok=True)
OUTPUT_REPORTS.mkdir(parents=True, exist_ok=True)

RESULTS_FILE = OUTPUT_TABLES / "18F1_source_discovery_results.csv"
SUMMARY_FILE = OUTPUT_TABLES / "18F1_source_discovery_summary.csv"
REPORT_FILE = OUTPUT_REPORTS / "18F1_source_discovery_report.txt"

# Number of results requested for each query.
RESULTS_PER_QUERY = 8

# Keep search conservative. Too many requests may trigger rate limiting.
PAUSE_BETWEEN_QUERIES_SECONDS = 1.5
FETCH_PAGE_TEXT = True
PAGE_TIMEOUT_SECONDS = 15
MAX_PAGE_TEXT_CHARS = 12000

USER_AGENT = (
    "Mozilla/5.0 (compatible; AcademicResearchSourceDiscovery/1.0; "
    "+https://example.org/research)"
)


def clean(value):
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def make_queries(row):
    name = clean(row.get("Port_Name"))
    city = clean(row.get("City_Name"))
    country = clean(row.get("Country_Code"))
    locode = clean(row.get("UN_LOCODE"))

    identity = " ".join(x for x in [name, city] if x)
    queries = [
        f'"{locode}" port official',
        f'"{identity}" port authority {country}',
        f'"{identity}" port coordinates {country}',
        f'"{identity}" government maritime port {country}',
        f'"{identity}" terminal facility official {country}',
    ]

    # Avoid repeated query strings where name and city are identical.
    unique = []
    seen = set()
    for q in queries:
        q = re.sub(r"\s+", " ", q).strip()
        if q and q not in seen:
            unique.append(q)
            seen.add(q)
    return unique


def fetch_page_text(url):
    """Fetch readable HTML text where possible; PDFs and blocked pages are skipped."""
    if not url or urlparse(url).scheme not in {"http", "https"}:
        return "", "INVALID_URL"

    if url.lower().split("?")[0].endswith(".pdf"):
        return "", "PDF_NOT_FETCHED"

    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=PAGE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()
        if "html" not in content_type:
            return "", f"NON_HTML_CONTENT:{content_type[:80]}"

        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
            tag.decompose()

        text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
        return text[:MAX_PAGE_TEXT_CHARS], "FETCHED"

    except requests.RequestException as exc:
        return "", f"FETCH_FAILED:{type(exc).__name__}"


def discover():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input not found: {INPUT_FILE}\nRun Script 18E first."
        )

    df = pd.read_csv(
        INPUT_FILE,
        dtype={"UN_LOCODE": str, "18E_Record_ID": str},
    )

    required = ["18E_Record_ID", "UN_LOCODE", "Port_Name", "City_Name", "Country_Code"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in Script 18E file: {missing}")

    print("=" * 76)
    print("SCRIPT 18F1: AUTOMATED PORT SOURCE DISCOVERY")
    print("=" * 76)
    print(f"Input records: {len(df)}")
    print(f"Results per query: {RESULTS_PER_QUERY}")
    print(f"Page text extraction: {FETCH_PAGE_TEXT}")

    all_results = []
    failed_queries = []

    with DDGS() as ddgs:
        for record_number, (_, row) in enumerate(df.iterrows(), start=1):
            locode = clean(row["UN_LOCODE"])
            port_name = clean(row["Port_Name"])
            city = clean(row["City_Name"])

            print(
                f"\n[{record_number}/{len(df)}] "
                f"Searching {locode} — {port_name or city}"
            )

            for query_number, query in enumerate(make_queries(row), start=1):
                print(f"  Query {query_number}: {query}")

                try:
                    results = list(
                        ddgs.text(
                            query,
                            max_results=RESULTS_PER_QUERY,
                        )
                    )
                except Exception as exc:
                    failed_queries.append({
                        "UN_LOCODE": locode,
                        "Query": query,
                        "Error": f"{type(exc).__name__}: {exc}",
                    })
                    print(f"    Search failed: {type(exc).__name__}")
                    time.sleep(PAUSE_BETWEEN_QUERIES_SECONDS)
                    continue

                for rank, item in enumerate(results, start=1):
                    title = clean(item.get("title"))
                    url = clean(item.get("href") or item.get("url"))
                    snippet = clean(item.get("body") or item.get("snippet"))
                    domain = urlparse(url).netloc.lower()

                    page_text = ""
                    fetch_status = "NOT_FETCHED"

                    if FETCH_PAGE_TEXT and url:
                        page_text, fetch_status = fetch_page_text(url)
                        time.sleep(0.3)

                    all_results.append({
                        "18E_Record_ID": clean(row["18E_Record_ID"]),
                        "UN_LOCODE": locode,
                        "Port_Name": port_name,
                        "City_Name": city,
                        "Country_Code": clean(row["Country_Code"]),
                        "Query_Number": query_number,
                        "Search_Query": query,
                        "Result_Rank": rank,
                        "Result_Title": title,
                        "Result_URL": url,
                        "Result_Domain": domain,
                        "Search_Snippet": snippet,
                        "Page_Fetch_Status": fetch_status,
                        "Extracted_Page_Text": page_text,
                        "Researcher_Source_Assessment": "NOT_REVIEWED",
                        "Researcher_Notes": "",
                    })

                print(f"    Results found: {len(results)}")
                time.sleep(PAUSE_BETWEEN_QUERIES_SECONDS)

    results_df = pd.DataFrame(all_results)

    if not results_df.empty:
        results_df["Normalized_URL"] = (
            results_df["Result_URL"]
            .str.replace(r"^https?://", "", regex=True)
            .str.replace(r"^www\.", "", regex=True)
            .str.rstrip("/")
            .str.lower()
        )

        # Preserve the earliest result occurrence for each LOCODE + URL.
        results_df = results_df.drop_duplicates(
            subset=["UN_LOCODE", "Normalized_URL"],
            keep="first",
        ).drop(columns=["Normalized_URL"])

        results_df.to_csv(
            RESULTS_FILE,
            index=False,
            encoding="utf-8-sig",
        )

        summary = (
            results_df.groupby(
                ["UN_LOCODE", "Port_Name", "Country_Code"],
                dropna=False,
            )
            .agg(
                Unique_Source_URLs=("Result_URL", "nunique"),
                Unique_Domains=("Result_Domain", "nunique"),
                Pages_Fetched=("Page_Fetch_Status", lambda s: (s == "FETCHED").sum()),
                Search_Results=("Result_Title", "count"),
            )
            .reset_index()
        )
    else:
        results_df = pd.DataFrame(columns=[
            "18E_Record_ID", "UN_LOCODE", "Port_Name", "City_Name",
            "Country_Code", "Search_Query", "Result_Title", "Result_URL",
        ])
        results_df.to_csv(RESULTS_FILE, index=False, encoding="utf-8-sig")
        summary = pd.DataFrame(columns=[
            "UN_LOCODE", "Port_Name", "Country_Code",
            "Unique_Source_URLs", "Unique_Domains",
            "Pages_Fetched", "Search_Results",
        ])

    summary.to_csv(SUMMARY_FILE, index=False, encoding="utf-8-sig")

    report_lines = [
        "=" * 76,
        "SCRIPT 18F1: SOURCE DISCOVERY REPORT",
        "=" * 76,
        f"Input locations: {len(df)}",
        f"Unique discovered result URLs: {len(results_df)}",
        f"Failed search queries: {len(failed_queries)}",
        "",
        "LOCATION SUMMARY",
    ]

    if not summary.empty:
        report_lines.append(summary.to_string(index=False))
    else:
        report_lines.append("No search results were collected.")

    report_lines.extend([
        "",
        "IMPORTANT LIMITATIONS",
        "1. Search results are candidate sources, not verified evidence.",
        "2. Search snippets may be incomplete or stale.",
        "3. Page extraction may fail for PDFs, JavaScript pages or blocked sites.",
        "4. Source authority and independence require assessment.",
        "5. Extracted page text must be checked against the source page.",
        "",
        "FAILED QUERIES",
    ])

    if failed_queries:
        for item in failed_queries:
            report_lines.append(
                f"{item['UN_LOCODE']} | {item['Query']} | {item['Error']}"
            )
    else:
        report_lines.append("None recorded.")

    report_lines.extend([
        "",
        f"Results CSV: {RESULTS_FILE}",
        f"Summary CSV: {SUMMARY_FILE}",
        "=" * 76,
    ])

    REPORT_FILE.write_text("\n".join(report_lines), encoding="utf-8")

    print("\n" + "=" * 76)
    print("SCRIPT 18F1 COMPLETED")
    print("=" * 76)
    print(f"Locations processed: {len(df)}")
    print(f"Candidate source URLs: {len(results_df)}")
    print(f"Failed queries: {len(failed_queries)}")
    print(f"Saved: {RESULTS_FILE.relative_to(ROOT)}")
    print(f"Saved: {SUMMARY_FILE.relative_to(ROOT)}")
    print(f"Saved: {REPORT_FILE.relative_to(ROOT)}")
    print("\nReminder: candidate sources are not yet independently verified.")


if __name__ == "__main__":
    discover()
