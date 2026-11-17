"""
SCRIPT 18F2: SOURCE QUALITY AND EVIDENCE ASSESSMENT

Purpose
-------
Screen the 448 candidate URLs discovered by Script 18F1.

This script:
- preserves every source-discovery row;
- classifies likely source type using domain/title/snippet/page text;
- assesses relevance to port/facility identity and geographic evidence;
- flags likely irrelevant results and search-engine/ad redirects;
- identifies duplicate URLs and domain concentration;
- creates per-LOCODE and per-domain summaries;
- creates a manual-review queue.

IMPORTANT
---------
This is an automated screening step, NOT independent verification.
A domain classified as official does not prove that a page supports a
particular port identity, facility identity, or coordinate. No coordinate
is selected and no port is marked verified by this script.

Run from project root:
    python src/18F2_source_quality_and_evidence_assessment.py

Input:
    outputs/tables/18F1_source_discovery_results.csv

Outputs:
    data/processed/18F2_assessed_source_register.csv
    outputs/tables/18F2_locode_source_quality_summary.csv
    outputs/tables/18F2_domain_source_summary.csv
    outputs/tables/18F2_manual_source_review_queue.csv
    outputs/tables/18F2_duplicate_url_audit.csv
    outputs/reports/18F2_source_quality_assessment_report.txt
"""

from pathlib import Path
from urllib.parse import urlparse, urlunparse
import re
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / "outputs" / "tables" / "18F1_source_discovery_results.csv"

PROCESSED_DIR = ROOT / "data" / "processed"
TABLES_DIR = ROOT / "outputs" / "tables"
REPORTS_DIR = ROOT / "outputs" / "reports"

for folder in [PROCESSED_DIR, TABLES_DIR, REPORTS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

OUT_REGISTER = PROCESSED_DIR / "18F2_assessed_source_register.csv"
OUT_LOCODE = TABLES_DIR / "18F2_locode_source_quality_summary.csv"
OUT_DOMAIN = TABLES_DIR / "18F2_domain_source_summary.csv"
OUT_QUEUE = TABLES_DIR / "18F2_manual_source_review_queue.csv"
OUT_DUPLICATES = TABLES_DIR / "18F2_duplicate_url_audit.csv"
OUT_REPORT = REPORTS_DIR / "18F2_source_quality_assessment_report.txt"


REQUIRED_COLUMNS = [
    "18E_Record_ID", "UN_LOCODE", "Port_Name", "City_Name",
    "Country_Code", "Result_Title", "Result_URL", "Result_Domain",
    "Search_Snippet", "Page_Fetch_Status", "Extracted_Page_Text"
]


def txt(value):
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalized_domain(url, supplied_domain=""):
    domain = txt(supplied_domain).lower().strip()
    if not domain:
        domain = urlparse(txt(url)).netloc.lower()
    domain = re.sub(r"^www\.", "", domain)
    return domain


def normalized_url(url):
    raw = txt(url)
    if not raw:
        return ""
    p = urlparse(raw)
    # Remove fragment and common tracking parameters while retaining
    # the actual page path and non-tracking query parameters.
    tracking = ("utm_", "gclid", "fbclid", "msclkid")
    query_parts = []
    for part in p.query.split("&"):
        if not part:
            continue
        key = part.split("=", 1)[0].lower()
        if not key.startswith(tracking):
            query_parts.append(part)
    return urlunparse((
        p.scheme.lower(),
        p.netloc.lower().removeprefix("www."),
        p.path.rstrip("/"),
        "",
        "&".join(query_parts),
        ""
    ))


OFFICIAL_GOV_TERMS = (
    ".gov", "gov.", "government", "ministry", "authority",
    "port authority", "maritime affairs", "department of ports"
)
PORT_OPERATOR_TERMS = (
    "ports", "port authority", "port operator", "port group",
    "terminal operator", "container terminal", "harbour", "harbor"
)
TERMINAL_TERMS = (
    "terminal", "container terminal", "industrial terminal",
    "jetties", "jetty", "liquid terminal", "bulk terminal",
    "port services"
)
MARITIME_DB_TERMS = (
    "marinetraffic", "vesseltracker", "seadex", "portcode",
    "unlocode", "world port", "worldports", "maritime database",
    "shipping database", "port directory"
)
IRRELEVANT_TERMS = (
    "airport", "airlines", "flight", "hotel", "tourism",
    "chauffeur", "airport services", "passenger terminal",
    "shopping", "restaurant", "real estate"
)
COORD_TERMS = (
    "coordinate", "coordinates", "latitude", "longitude",
    "lat", "long", "location map", "gps", "position"
)
IDENTITY_TERMS = (
    "port", "harbour", "harbor", "seaport", "terminal",
    "jetty", "jetties", "marine", "maritime", "dock"
)
FACILITY_TERMS = (
    "industrial", "facility", "plant", "petrochemical",
    "chemical", "aluminium", "aluminum", "refinery",
    "smelter", "oil", "gas", "bulk", "container"
)


def has_any(text, terms):
    return any(term in text for term in terms)


def assess_row(row):
    title = txt(row.get("Result_Title")).lower()
    snippet = txt(row.get("Search_Snippet")).lower()
    page = txt(row.get("Extracted_Page_Text")).lower()
    domain = normalized_domain(
        row.get("Result_URL"), row.get("Result_Domain")
    )
    fetch = txt(row.get("Page_Fetch_Status")).upper()
    combined = " ".join([title, snippet, page])
    url = txt(row.get("Result_URL")).lower()

    # Source type classification: conservative domain/title heuristics.
    if (
        domain.endswith(".gov") or ".gov." in domain
        or domain.endswith(".gov.in")
        or domain.endswith(".gov.om")
        or domain.endswith(".gov.ae")
        or domain.endswith(".gov.sa")
        or domain.endswith(".gov.kw")
        or domain.endswith(".gov.qa")
        or domain.endswith(".gov.bh")
        or domain.endswith(".gov.pk")
        or domain.endswith(".gov.iq")
        or domain.endswith(".gov.uk")
        or domain.endswith(".gov.au")
        or domain.endswith(".gov.sg")
        or any(x in domain for x in (
            "mtt.gov", "ports.gov", "maritime.gov",
            "unece.org", "un.org", "imo.org"
        ))
    ):
        source_type = "GOVERNMENT_OR_INTERGOVERNMENT"
        source_score = 5
    elif any(x in domain for x in (
        "adports", "fujairahport", "gulftainer",
        "apmterminals", "dpworld", "hutchisonports",
        "ictsi", "deendayalport", "jnport", "syam"
    )) or (
        has_any(title, PORT_OPERATOR_TERMS)
        and has_any(domain, ("port", "terminal", "shipping"))
    ):
        source_type = "PORT_AUTHORITY_OR_OPERATOR_CANDIDATE"
        source_score = 5
    elif has_any(domain, ("terminal", "industrial")) or (
        has_any(title, TERMINAL_TERMS)
        and has_any(combined, ("operator", "terminal", "facility"))
    ):
        source_type = "TERMINAL_OR_FACILITY_OPERATOR_CANDIDATE"
        source_score = 4
    elif has_any(domain, MARITIME_DB_TERMS) or has_any(title, MARITIME_DB_TERMS):
        source_type = "MARITIME_OR_PORT_DATABASE"
        source_score = 3
    elif domain in ("wikipedia.org", "en.wikipedia.org"):
        source_type = "GENERAL_REFERENCE"
        source_score = 2
    else:
        source_type = "SECONDARY_OR_UNCLASSIFIED"
        source_score = 2

    # Search-engine redirects and obvious commercial ad links are low value.
    if (
        "bing.com/aclick" in url or "google.com/aclk" in url
        or "yahoo.com" in domain and "redirect" in url
    ):
        source_type = "SEARCH_AD_OR_REDIRECT"
        source_score = 0

    irrelevant_hits = [term for term in IRRELEVANT_TERMS if term in combined]
    identity_hits = [term for term in IDENTITY_TERMS if term in combined]
    coord_hits = [term for term in COORD_TERMS if term in combined]
    facility_hits = [term for term in FACILITY_TERMS if term in combined]

    # Airport/other irrelevant pages are flagged only when no meaningful
    # port/maritime identity evidence is also present.
    if irrelevant_hits and not identity_hits:
        relevance = "LIKELY_IRRELEVANT"
        relevance_score = 0
    elif identity_hits:
        relevance = "PORT_OR_MARITIME_RELEVANT_CANDIDATE"
        relevance_score = 2
    else:
        relevance = "RELEVANCE_UNCLEAR"
        relevance_score = 1

    if coord_hits:
        geographic_evidence = "COORDINATE_OR_LOCATION_TERMS_PRESENT"
    else:
        geographic_evidence = "NO_CLEAR_COORDINATE_TERMS"

    if facility_hits:
        facility_evidence = "FACILITY_OR_INDUSTRIAL_TERMS_PRESENT"
    else:
        facility_evidence = "NO_CLEAR_FACILITY_TERMS"

    fetched = fetch == "FETCHED"
    page_text_available = len(txt(row.get("Extracted_Page_Text"))) >= 250
    if fetched and page_text_available:
        content_status = "PAGE_TEXT_AVAILABLE"
    elif fetch.startswith("FETCH_FAILED"):
        content_status = "FETCH_FAILED"
    elif fetch == "PDF_NOT_FETCHED":
        content_status = "PDF_REQUIRES_MANUAL_REVIEW"
    else:
        content_status = "NO_USABLE_PAGE_TEXT"

    # Evidence priority is a review-order aid, not a truth score.
    priority_points = source_score + relevance_score
    if coord_hits:
        priority_points += 1
    if facility_hits:
        priority_points += 1
    if page_text_available:
        priority_points += 1

    if relevance == "LIKELY_IRRELEVANT" or source_type == "SEARCH_AD_OR_REDIRECT":
        review_priority = "LOW"
    elif source_score >= 4 and relevance_score >= 2 and page_text_available:
        review_priority = "HIGH"
    elif source_score >= 3 and relevance_score >= 2:
        review_priority = "MEDIUM"
    else:
        review_priority = "LOW"

    return pd.Series({
        "Normalized_Domain": domain,
        "Normalized_URL": normalized_url(row.get("Result_URL")),
        "Automated_Source_Type": source_type,
        "Source_Type_Screening_Score": source_score,
        "Automated_Relevance": relevance,
        "Relevance_Screening_Score": relevance_score,
        "Geographic_Evidence_Screen": geographic_evidence,
        "Facility_Evidence_Screen": facility_evidence,
        "Content_Access_Status": content_status,
        "Page_Text_Character_Count": len(txt(row.get("Extracted_Page_Text"))),
        "Irrelevant_Term_Flags": ";".join(irrelevant_hits),
        "Identity_Term_Flags": ";".join(identity_hits),
        "Coordinate_Term_Flags": ";".join(coord_hits),
        "Facility_Term_Flags": ";".join(facility_hits),
        "Automated_Review_Priority": review_priority,
        "Automated_Priority_Points": priority_points,
        "Verification_Status": "NOT_VERIFIED_MANUAL_REVIEW_REQUIRED",
    })


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}\n"
            "Confirm Script 18F1 has completed successfully."
        )

    df = pd.read_csv(INPUT_FILE, dtype=str, keep_default_na=False)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            "18F1 input schema mismatch. Missing columns: "
            + ", ".join(missing)
            + "\nAvailable columns: " + ", ".join(df.columns)
        )

    print("=" * 78)
    print("SCRIPT 18F2: SOURCE QUALITY AND EVIDENCE ASSESSMENT")
    print("=" * 78)
    print(f"Input rows: {len(df):,}")
    print(f"Input unique LOCODEs: {df['UN_LOCODE'].nunique():,}")

    assessed = df.join(df.apply(assess_row, axis=1))
    assessed["Duplicate_URL_Count_Per_LOCODE"] = (
        assessed.groupby(["UN_LOCODE", "Normalized_URL"])["Normalized_URL"]
        .transform("size")
    )
    assessed["Duplicate_Domain_Count_Per_LOCODE"] = (
        assessed.groupby(["UN_LOCODE", "Normalized_Domain"])["Normalized_Domain"]
        .transform("size")
    )

    # URL audit retains source rows while identifying repeated URL occurrences.
    duplicate_audit = (
        assessed.groupby(["UN_LOCODE", "Normalized_URL"], dropna=False)
        .agg(
            Port_Name=("Port_Name", "first"),
            URL=("Result_URL", "first"),
            Domain=("Normalized_Domain", "first"),
            Occurrences=("Normalized_URL", "size"),
            Query_Numbers=("Query_Number", lambda x: ";".join(sorted(set(map(str, x))))),
            Titles=("Result_Title", lambda x: " | ".join(dict.fromkeys(map(str, x)))),
        )
        .reset_index()
    )
    duplicate_audit = duplicate_audit[
        duplicate_audit["Occurrences"] > 1
    ].sort_values(["UN_LOCODE", "Occurrences"], ascending=[True, False])

    # One summary row per target LOCODE.
    locode_summary = (
        assessed.groupby(["UN_LOCODE", "Port_Name", "City_Name", "Country_Code"])
        .agg(
            Candidate_URL_Rows=("Result_URL", "size"),
            Unique_URLs=("Normalized_URL", "nunique"),
            Unique_Domains=("Normalized_Domain", "nunique"),
            Pages_With_Text=("Content_Access_Status",
                             lambda x: int((x == "PAGE_TEXT_AVAILABLE").sum())),
            Fetch_Failures=("Content_Access_Status",
                            lambda x: int((x == "FETCH_FAILED").sum())),
            Government_Or_Intergovernmental=("Automated_Source_Type",
                lambda x: int((x == "GOVERNMENT_OR_INTERGOVERNMENT").sum())),
            Port_Authority_Or_Operator=("Automated_Source_Type",
                lambda x: int((x == "PORT_AUTHORITY_OR_OPERATOR_CANDIDATE").sum())),
            Terminal_Or_Facility_Operator=("Automated_Source_Type",
                lambda x: int((x == "TERMINAL_OR_FACILITY_OPERATOR_CANDIDATE").sum())),
            Maritime_Databases=("Automated_Source_Type",
                lambda x: int((x == "MARITIME_OR_PORT_DATABASE").sum())),
            Likely_Irrelevant=("Automated_Relevance",
                lambda x: int((x == "LIKELY_IRRELEVANT").sum())),
            High_Priority_Candidates=("Automated_Review_Priority",
                lambda x: int((x == "HIGH").sum())),
            Medium_Priority_Candidates=("Automated_Review_Priority",
                lambda x: int((x == "MEDIUM").sum())),
        )
        .reset_index()
    )
    locode_summary["Independent_Verification_Status"] = (
        "PENDING_MANUAL_SOURCE_REVIEW"
    )

    # Domain summary helps expose source concentration and repeated domains.
    domain_summary = (
        assessed.groupby("Normalized_Domain")
        .agg(
            Candidate_Rows=("Result_URL", "size"),
            Unique_URLs=("Normalized_URL", "nunique"),
            LOCODEs_Covered=("UN_LOCODE", "nunique"),
            Source_Types=("Automated_Source_Type",
                          lambda x: ";".join(sorted(set(x)))),
            Example_Titles=("Result_Title",
                            lambda x: " | ".join(list(dict.fromkeys(map(str, x)))[:3])),
        )
        .reset_index()
        .sort_values(["Candidate_Rows", "LOCODEs_Covered"], ascending=False)
    )

    # Manual queue: high/medium candidates first; likely irrelevant items remain
    # in the full register and duplicate audit but are not prioritized.
    review_queue = assessed[
        assessed["Automated_Review_Priority"].isin(["HIGH", "MEDIUM"])
    ].copy()
    review_queue = review_queue.sort_values(
        ["UN_LOCODE", "Automated_Review_Priority",
         "Source_Type_Screening_Score", "Page_Text_Character_Count"],
        ascending=[True, True, False, False]
    )

    assessed.to_csv(OUT_REGISTER, index=False, encoding="utf-8-sig")
    locode_summary.to_csv(OUT_LOCODE, index=False, encoding="utf-8-sig")
    domain_summary.to_csv(OUT_DOMAIN, index=False, encoding="utf-8-sig")
    review_queue.to_csv(OUT_QUEUE, index=False, encoding="utf-8-sig")
    duplicate_audit.to_csv(OUT_DUPLICATES, index=False, encoding="utf-8-sig")

    report = []
    report.append("SCRIPT 18F2: SOURCE QUALITY AND EVIDENCE ASSESSMENT")
    report.append("=" * 72)
    report.append(f"Input rows: {len(df)}")
    report.append(f"Unique LOCODEs: {df['UN_LOCODE'].nunique()}")
    report.append(f"Unique URLs globally: {assessed['Normalized_URL'].nunique()}")
    report.append(f"Unique domains globally: {assessed['Normalized_Domain'].nunique()}")
    report.append("")
    report.append("PAGE ACCESS")
    report.append(assessed["Content_Access_Status"].value_counts().to_string())
    report.append("")
    report.append("AUTOMATED SOURCE TYPE SCREEN")
    report.append(assessed["Automated_Source_Type"].value_counts().to_string())
    report.append("")
    report.append("AUTOMATED RELEVANCE SCREEN")
    report.append(assessed["Automated_Relevance"].value_counts().to_string())
    report.append("")
    report.append("REVIEW PRIORITY")
    report.append(assessed["Automated_Review_Priority"].value_counts().to_string())
    report.append("")
    report.append(f"Repeated LOCODE-URL groups: {len(duplicate_audit)}")
    report.append(
        "Rows in manual review queue: "
        f"{len(review_queue)}"
    )
    report.append("")
    report.append("METHODOLOGICAL LIMITATIONS")
    report.append(
        "1. Classification is heuristic and based on domains, titles, snippets, "
        "and extracted page text."
    )
    report.append(
        "2. Official-domain classification is only a candidate source-type label; "
        "it does not prove page authority for a particular port."
    )
    report.append(
        "3. Keyword presence does not prove that a coordinate refers to the "
        "UN/LOCODE location, port boundary, terminal, or berth."
    )
    report.append(
        "4. Search results can be irrelevant, stale, duplicated, redirected, "
        "or refer to a different facility with a similar name."
    )
    report.append(
        "5. No coordinates are selected and no port/facility is marked verified."
    )
    report.append(
        "6. All 19 target locations require researcher review against primary "
        "sources and explicit facility identity."
    )
    report.append("")
    report.append("OUTPUTS")
    for path in [OUT_REGISTER, OUT_LOCODE, OUT_DOMAIN, OUT_QUEUE,
                 OUT_DUPLICATES, OUT_REPORT]:
        report.append(str(path.relative_to(ROOT)))

    OUT_REPORT.write_text("\n".join(report), encoding="utf-8")

    print("\nSOURCE TYPE SCREEN")
    print(assessed["Automated_Source_Type"].value_counts().to_string())
    print("\nRELEVANCE SCREEN")
    print(assessed["Automated_Relevance"].value_counts().to_string())
    print("\nREVIEW PRIORITY")
    print(assessed["Automated_Review_Priority"].value_counts().to_string())
    print(f"\nManual review queue: {len(review_queue)} rows")
    print(f"Repeated LOCODE-URL groups: {len(duplicate_audit)}")
    print("\nSCRIPT 18F2 COMPLETED")
    print(f"Saved: {OUT_REGISTER.relative_to(ROOT)}")
    print(f"Saved: {OUT_LOCODE.relative_to(ROOT)}")
    print(f"Saved: {OUT_DOMAIN.relative_to(ROOT)}")
    print(f"Saved: {OUT_QUEUE.relative_to(ROOT)}")
    print(f"Saved: {OUT_DUPLICATES.relative_to(ROOT)}")
    print(f"Saved: {OUT_REPORT.relative_to(ROOT)}")
    print("\nReminder: automated screening is not independent verification.")


if __name__ == "__main__":
    main()
