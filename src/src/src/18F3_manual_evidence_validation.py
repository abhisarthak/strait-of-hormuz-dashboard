"""18F3 - Manual evidence validation register for Hormuz port geography.

This script does NOT independently verify sources or accept coordinates.
It prepares a conservative, auditable researcher-review workspace from the
18F2 URL-level manual review queue.

Run from project root:
    python src/18F3_manual_evidence_validation.py
"""
from pathlib import Path
import re
import sys
import pandas as pd

ROOT = Path.cwd()

INPUT_CANDIDATES = [
    ROOT / "outputs/tables/18F2_manual_source_review_queue.csv",
    ROOT / "data/processed/18F2_assessed_source_register.csv",
    ROOT / "18F2_manual_source_review_queue.csv",
]

OUT_PROCESSED = ROOT / "data/processed"
OUT_TABLES = ROOT / "outputs/tables"
OUT_REPORTS = ROOT / "outputs/reports"
for folder in (OUT_PROCESSED, OUT_TABLES, OUT_REPORTS):
    folder.mkdir(parents=True, exist_ok=True)


def norm_text(value):
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def find_col(df, candidates, required=True):
    lower = {str(c).lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    if required:
        raise KeyError(f"Required column not found. Tried: {candidates}\nAvailable: {list(df.columns)}")
    return None


def text_has(text, terms):
    t = text.lower()
    return any(term.lower() in t for term in terms)


KNOWN_STUDY_LOCODES = {"AEAUH", "AEFJR", "AEKLF", "AERKT", "AESHJ", "BHKBS", "INHZA", "INIXY", "INPPV", "IQUQR", "KWSAA", "KWSWK", "OMDQM", "PKKIA", "QAQAP", "QAQCH", "QAUMS", "SADMM", "SAJUB"}

def assess_row(row, cols):
    title = norm_text(row[cols["title"]])
    url = norm_text(row[cols["url"]])
    snippet = norm_text(row[cols["snippet"]]) if cols["snippet"] else ""
    page_text = norm_text(row[cols["page_text"]]) if cols["page_text"] else ""
    locode = norm_text(row[cols["locode"]]).upper()
    port = norm_text(row[cols["port"]])
    combined = " ".join([title, url, snippet, page_text[:5000]])
    low = combined.lower()
    flags, decision, reason = [], "RETAIN_FOR_MANUAL_REVIEW", "No deterministic exclusion rule applied; source still requires human verification."

    airport_terms = ["airport", "airports", "airport terminal", "international airport", "airportmaps"]
    seaport_terms = ["seaport", "sea port", "port authority", "ports authority", "harbor", "harbour", "marine terminal", "container terminal", "port of"]
    if text_has(title + " " + url + " " + snippet, airport_terms) and not text_has(title + " " + url + " " + snippet, seaport_terms):
        flags.append("AIRPORT_OR_AVIATION_MATCH")
        decision = "LIKELY_IRRELEVANT_TO_SEAPORT_VALIDATION"
        reason = "Title/URL/snippet indicates an airport or aviation page without clear seaport evidence. Exclude from port-identity evidence unless page content proves a relevant maritime connection."

    # Location-specific mismatches are deliberately labelled candidates for review,
    # not definitive factual rejections.
    if locode == "PKKIA" and text_has(title + " " + url + " " + snippet, ["port qasim", "qasim port", "pibt", "pakistan international bulk"]):
        flags.append("KARACHI_VS_PORT_QASIM_LOCATION_REVIEW")
        decision = "POTENTIAL_LOCATION_MISMATCH_REVIEW"
        reason = "Source appears to concern Port Qasim/PIBT rather than directly identifying the Kiamari/Karachi Port Trust location. Confirm the precise facility and LOCODE relationship before use."
    if locode == "QAQAP" and ("qaums" in low or "qau" in low and "cma-cgm" in low):
        flags.append("LOCODE_CONFLICT_QAQAP_VS_QAUMS")
        decision = "POTENTIAL_LOCODE_MISMATCH_REVIEW"
        reason = "Source URL/content appears to identify QAUMS rather than QAQAP. Do not use as direct QAQAP evidence without a documented relationship."

    # Facility type flags: not an exclusion; identity category needs careful review.
    if locode in {"QAQAP", "QAQCH", "QAUMS"}:
        flags.append("QATAR_INDUSTRIAL_OR_SPECIAL_FACILITY_IDENTITY_REVIEW")
        if decision == "RETAIN_FOR_MANUAL_REVIEW":
            decision = "SPECIAL_FACILITY_IDENTITY_REVIEW"
            reason = "Qatar QAPCO/Q-Chem/Qatalum-related location: establish whether the LOCODE represents an industrial facility, terminal, port or broader location. Do not assume conventional commercial-port status."

    # Coordinate presence is only a clue; it never verifies a coordinate.
    if text_has(title + " " + snippet + " " + page_text[:3000], ["latitude", "longitude", "coordinates", "lat/long", "gps"]):
        flags.append("COORDINATE_TERMS_PRESENT_NOT_VERIFIED")

    # Explicit code in a URL that conflicts with target code is a review signal.
    codes = re.findall(r"(?<![A-Z0-9])[A-Z]{5}(?![A-Z0-9])", url.upper())
    conflicting_codes = sorted({code for code in codes if code in KNOWN_STUDY_LOCODES and code != locode})
    if conflicting_codes:
        flags.append("OTHER_UNLOCODE_IN_URL_REVIEW")
        if decision == "RETAIN_FOR_MANUAL_REVIEW":
            decision = "POTENTIAL_LOCODE_MISMATCH_REVIEW"
            reason = f"URL contains other LOCODE-like code(s) {', '.join(conflicting_codes)}. Confirm whether this is a genuine mismatch or a related terminal/service page."

    return pd.Series({
        "18F3_Automated_Review_Flags": ";".join(sorted(set(flags))) if flags else "NONE",
        "18F3_Provisional_Researcher_Decision": decision,
        "18F3_Provisional_Reason": reason,
        "18F3_Researcher_Review_Status": "PENDING_HUMAN_REVIEW",
        "18F3_Researcher_Final_Decision": "",
        "18F3_Evidence_Statement": "",
        "18F3_Evidence_Organization": "",
        "18F3_Evidence_Source_Type": "",
        "18F3_Coordinate_Latitude": "",
        "18F3_Coordinate_Longitude": "",
        "18F3_Coordinate_Reference_Type": "",
        "18F3_Independent_Corroborating_URL": "",
        "18F3_Reviewer_Notes": "",
    })


def main():
    input_path = next((p for p in INPUT_CANDIDATES if p.exists()), None)
    if input_path is None:
        print("ERROR: Could not find the 18F2 manual source review queue.")
        print("Expected one of:")
        for p in INPUT_CANDIDATES:
            print(" -", p)
        sys.exit(1)

    df = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    c = {
        "locode": find_col(df, ["UN_LOCODE", "UNLocationCode"]),
        "port": find_col(df, ["Port_Name", "PortName"], required=False),
        "title": find_col(df, ["Result_Title", "Title"], required=False),
        "url": find_col(df, ["Result_URL", "URL", "Source_URL"], required=False),
        "snippet": find_col(df, ["Search_Snippet", "Snippet"], required=False),
        "page_text": find_col(df, ["Extracted_Page_Text", "Page_Text"], required=False),
    }
    for k in ("port", "title", "url"):
        if c[k] is None:
            raise KeyError(f"Missing essential source field: {k}")

    # Preserve every original source field and append review fields.
    assessed = pd.concat([df.reset_index(drop=True), df.apply(lambda r: assess_row(r, c), axis=1)], axis=1)
    assessed["18F3_Source_Record_ID"] = assessed.get("18E_Record_ID", pd.Series([f"18F3_{i+1:04d}" for i in range(len(assessed))]))

    # Location-level evidence register: counts and blank manual-verification fields.
    summary_rows = []
    for locode, g in assessed.groupby(c["locode"], dropna=False):
        decisions = g["18F3_Provisional_Researcher_Decision"].value_counts().to_dict()
        flags = ";".join(sorted({f for cell in g["18F3_Automated_Review_Flags"] for f in cell.split(";") if f and f != "NONE"}))
        summary_rows.append({
            "UN_LOCODE": locode,
            "Port_Name": norm_text(g[c["port"]].iloc[0]),
            "Country_Code": norm_text(g["Country_Code"].iloc[0]) if "Country_Code" in g.columns else "",
            "Source_Queue_Rows": len(g),
            "Fetched_Page_Rows": int(g.get("Page_Fetch_Status", pd.Series([""]*len(g))).astype(str).str.upper().eq("FETCHED").sum()),
            "Airport_Mismatch_Candidates": int(g["18F3_Automated_Review_Flags"].str.contains("AIRPORT_OR_AVIATION_MATCH", regex=False).sum()),
            "Potential_Location_or_LOCODE_Mismatch": int(g["18F3_Provisional_Researcher_Decision"].str.contains("MISMATCH_REVIEW", regex=False).sum()),
            "Special_Facility_Review_Rows": int(g["18F3_Automated_Review_Flags"].str.contains("QATAR_INDUSTRIAL_OR_SPECIAL_FACILITY_IDENTITY_REVIEW", regex=False).sum()),
            "Automated_Flags": flags or "NONE",
            "Manual_Identity_Classification": "PENDING",
            "LOCODE_Identity_Verification": "PENDING",
            "Coordinate_Verification_Status": "PENDING",
            "Independent_Corroboration_Status": "PENDING",
            "Final_Researcher_Decision": "PENDING_MANUAL_REVIEW",
            "Evidence_Notes": "",
        })
    locode_summary = pd.DataFrame(summary_rows).sort_values("UN_LOCODE")

    # A compact review queue prioritising likely false matches and special cases.
    priority_mask = (
        assessed["18F3_Provisional_Researcher_Decision"].ne("RETAIN_FOR_MANUAL_REVIEW")
        | assessed["18F3_Automated_Review_Flags"].str.contains("COORDINATE_TERMS_PRESENT_NOT_VERIFIED", regex=False)
    )
    review_queue = assessed.loc[priority_mask].copy()

    p_all = OUT_PROCESSED / "18F3_assessed_source_register.csv"
    p_loc = OUT_TABLES / "18F3_locode_evidence_validation_register.csv"
    p_review = OUT_TABLES / "18F3_priority_manual_review_queue.csv"
    p_report = OUT_REPORTS / "18F3_manual_evidence_validation_report.txt"
    assessed.to_csv(p_all, index=False)
    locode_summary.to_csv(p_loc, index=False)
    review_queue.to_csv(p_review, index=False)

    decision_counts = assessed["18F3_Provisional_Researcher_Decision"].value_counts().to_dict()
    flag_counts = {}
    for cell in assessed["18F3_Automated_Review_Flags"]:
        for flag in cell.split(";"):
            if flag and flag != "NONE":
                flag_counts[flag] = flag_counts.get(flag, 0) + 1

    report = [
        "18F3 MANUAL EVIDENCE VALIDATION - PREPARATION REPORT",
        "=" * 62,
        f"Input file: {input_path}",
        f"Input rows: {len(df)}",
        f"Unique LOCODEs: {df[c['locode']].nunique()}",
        f"Output source register: {p_all}",
        f"Output LOCODE register: {p_loc}",
        f"Output priority review queue: {p_review}",
        "",
        "PROVISIONAL SOURCE-ROW DECISIONS",
    ]
    report += [f"- {k}: {v}" for k, v in decision_counts.items()]
    report += ["", "AUTOMATED REVIEW FLAGS"]
    report += [f"- {k}: {v}" for k, v in sorted(flag_counts.items())]
    report += [
        "",
        "METHODOLOGICAL LIMITATIONS",
        "1. This script prepares a review workspace; it does not independently verify any source.",
        "2. Automated flags are screening prompts, not final rejection decisions.",
        "3. No coordinates are accepted or selected by this script.",
        "4. A source describing a port operator does not necessarily prove a particular LOCODE or facility identity.",
        "5. Coordinate meaning (port centroid, terminal, anchorage or city reference) must be recorded manually.",
        "6. Every LOCODE remains pending until a researcher records evidence and a final decision.",
        "",
        "NEXT ACTION",
        "Review 18F3_priority_manual_review_queue.csv first, then complete the location-level register.",
    ]
    p_report.write_text("\n".join(report), encoding="utf-8")

    print("\n18F3 completed successfully")
    print(f"Input: {input_path}")
    print(f"Source rows: {len(assessed)}")
    print(f"Unique LOCODEs: {len(locode_summary)}")
    print(f"Priority manual-review rows: {len(review_queue)}")
    print("Provisional decisions:", decision_counts)
    print("\nCreated:")
    for p in (p_all, p_loc, p_review, p_report):
        print(" -", p)
    print("\nReminder: no port, facility or coordinate has been independently verified by this script.")

if __name__ == "__main__":
    main()
