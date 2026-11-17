
"""
SCRIPT 40: Source URL and Evidence Audit

Purpose:
1. Audit source metadata completeness for all 19 ports.
2. Check URL syntax and HTTP accessibility.
3. Identify duplicate source URLs.
4. Preserve coordinate-validation safeguards.
5. Flag source content for manual verification.

Important:
- Does not modify Script 39.
- Does not approve coordinates.
- Does not approve operational inclusion.
- URL accessibility does not prove source-content validity.

Outputs:
    outputs/tables/40_source_evidence_audit.csv
    outputs/tables/40_source_evidence_summary.csv
    outputs/reports/40_source_evidence_audit_report.txt
"""

import csv
import time
from pathlib import Path
from collections import Counter
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


# ============================================================
# 1. PATHS AND CONFIGURATION
# ============================================================

INPUT_FILE = Path(
    "outputs/tables/39_port_coordinate_validation_register.csv"
)

OUTPUT_DIR = Path("outputs/tables")
REPORT_DIR = Path("outputs/reports")

AUDIT_FILE = OUTPUT_DIR / "40_source_evidence_audit.csv"
SUMMARY_FILE = OUTPUT_DIR / "40_source_evidence_summary.csv"
REPORT_FILE = REPORT_DIR / "40_source_evidence_audit_report.txt"

EXPECTED_RECORDS = 19
EXPECTED_COLUMNS = 36

URL_TIMEOUT = 12
USER_AGENT = "Mozilla/5.0 (compatible; ResearchEvidenceAudit/1.0)"

SOURCE_FIELDS = [
    "Coordinate_Source_Organization",
    "Coordinate_Source_Title",
    "Coordinate_Source_URL",
    "Coordinate_Source_Access_Date",
    "Coordinate_Evidence_Description"
]

COORDINATE_FIELDS = [
    "Validated_Port_Latitude",
    "Validated_Port_Longitude",
    "Validated_Terminal_Latitude",
    "Validated_Terminal_Longitude"
]


# ============================================================
# 2. URL VALIDATION
# ============================================================

def validate_url_syntax(url):
    """Check whether a URL has a valid HTTP/HTTPS structure."""

    try:
        parsed = urlparse(url.strip())

        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.netloc)
            and "." in parsed.netloc
        )

    except Exception:
        return False


def check_url_accessibility(url):
    """
    Check URL accessibility.

    First attempts HEAD.
    Falls back to GET if HEAD is rejected.

    Does not verify page content.
    """

    headers = {
        "User-Agent": USER_AGENT
    }

    methods = ["HEAD", "GET"]

    last_error = ""

    for method in methods:

        try:
            request = Request(
                url,
                headers=headers,
                method=method
            )

            with urlopen(
                request,
                timeout=URL_TIMEOUT
            ) as response:

                status = response.status
                final_url = response.geturl()

                return {
                    "status": "ACCESSIBLE",
                    "http_code": status,
                    "final_url": final_url,
                    "method": method,
                    "error": ""
                }

        except HTTPError as e:

            # Some servers reject HEAD but allow GET.
            if method == "HEAD" and e.code in (403, 405, 501):
                last_error = f"HEAD returned HTTP {e.code}"
                continue

            return {
                "status": "HTTP_ERROR",
                "http_code": e.code,
                "final_url": "",
                "method": method,
                "error": str(e)
            }

        except (URLError, TimeoutError, OSError) as e:

            last_error = str(e)

            if method == "HEAD":
                continue

            return {
                "status": "CONNECTION_ERROR",
                "http_code": "",
                "final_url": "",
                "method": method,
                "error": last_error
            }

        except Exception as e:

            return {
                "status": "ERROR",
                "http_code": "",
                "final_url": "",
                "method": method,
                "error": str(e)
            }

    return {
        "status": "UNREACHABLE",
        "http_code": "",
        "final_url": "",
        "method": "",
        "error": last_error
    }


# ============================================================
# 3. LOAD INPUT REGISTER
# ============================================================

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Input file not found: {INPUT_FILE}"
    )

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

with INPUT_FILE.open(
    "r",
    encoding="utf-8-sig",
    newline=""
) as f:

    reader = csv.DictReader(f)

    input_headers = reader.fieldnames
    records = list(reader)
    # Load operational inclusion decisions from Script 38.
SCRIPT38_FILE = Path(
    "outputs/tables/38_port_evidence_validation_register.csv"
)

operational_decisions = {}

if SCRIPT38_FILE.exists():
    with SCRIPT38_FILE.open(
        "r", encoding="utf-8-sig", newline=""
    ) as f:
        script38_rows = list(csv.DictReader(f))

    for r in script38_rows:
        code = r["UN_LOCODE"]
        operational_decisions[code] = r.get(
            "Operational_Inclusion_Decision",
            "NOT_AVAILABLE"
        )

    print(
        "Script 38 operational decisions loaded:",
        len(operational_decisions)
    )
else:
    print(
        "WARNING: Script 38 not found. "
        "Operational decisions will be marked unavailable."
    )


if len(records) != EXPECTED_RECORDS:
    raise ValueError(
        f"Expected {EXPECTED_RECORDS} records, "
        f"found {len(records)}"
    )

if len(input_headers) != EXPECTED_COLUMNS:
    raise ValueError(
        f"Expected {EXPECTED_COLUMNS} columns, "
        f"found {len(input_headers)}"
    )

required_headers = (
    SOURCE_FIELDS
    + COORDINATE_FIELDS
    + [
        "UN_LOCODE",
        "Coordinate_Validation_Status",
        "Coordinate_Confidence",
        "Coordinate_Review_Notes"
    ]
)

for field in required_headers:
    if field not in input_headers:
        raise ValueError(
            f"Required column missing: {field}"
        )

codes = [r["UN_LOCODE"] for r in records]

if len(codes) != len(set(codes)):
    raise ValueError("Duplicate UN/LOCODE records found.")


# ============================================================
# 4. AUDIT SOURCE URLS
# ============================================================

url_cache = {}
url_occurrences = Counter()

audit_records = []

total_urls = 0
accessible_urls = 0
unreachable_urls = 0
invalid_urls = 0


for index, record in enumerate(records, start=1):

    code = record["UN_LOCODE"]

    print(
        f"\n[{index}/{len(records)}] Auditing {code}"
    )

    # --------------------------------------------------------
    # Metadata completeness
    # --------------------------------------------------------

    missing_fields = []

    for field in SOURCE_FIELDS:
        if not record[field].strip():
            missing_fields.append(field)

    metadata_complete = len(missing_fields) == 0

    # --------------------------------------------------------
    # Split semicolon-separated URLs
    # --------------------------------------------------------

    raw_url_field = record[
        "Coordinate_Source_URL"
    ].strip()

    urls = [
        u.strip()
        for u in raw_url_field.split(";")
        if u.strip()
    ]

    total_urls += len(urls)

    url_results = []

    for url in urls:

        url_occurrences[url] += 1

        if not validate_url_syntax(url):

            result = {
                "url": url,
                "status": "INVALID_URL",
                "http_code": "",
                "final_url": "",
                "method": "",
                "error": "Invalid URL structure"
            }

            invalid_urls += 1

        else:

            if url not in url_cache:

                print("   Checking:", url[:100])

                url_cache[url] = check_url_accessibility(url)

                # Avoid sending requests too rapidly.
                time.sleep(0.3)

            result = {
                "url": url,
                **url_cache[url]
            }

            if result["status"] == "ACCESSIBLE":
                accessible_urls += 1
            else:
                unreachable_urls += 1

        url_results.append(result)

    # --------------------------------------------------------
    # URL-level summary
    # --------------------------------------------------------

    if len(urls) == 0:
        url_status = "NO_URL"

    elif len(url_results) == 0:
        url_status = "NO_URL"

    elif all(
        x["status"] == "ACCESSIBLE"
        for x in url_results
    ):
        url_status = "URL_CHECKED"

    elif any(
        x["status"] == "ACCESSIBLE"
        for x in url_results
    ):
        url_status = "URL_PARTIALLY_ACCESSIBLE"

    elif all(
        x["status"] == "INVALID_URL"
        for x in url_results
    ):
        url_status = "INVALID_URL"

    else:
        url_status = "URL_UNREACHABLE"

    # --------------------------------------------------------
    # Coordinate safeguard checks
    # --------------------------------------------------------

    coordinate_status = record[
        "Coordinate_Validation_Status"
    ]

    confidence = record[
        "Coordinate_Confidence"
    ]

    coordinates_blank = all(
        not record[field].strip()
        for field in COORDINATE_FIELDS
    )

    coordinate_safeguard = (
        coordinate_status == "PENDING"
        and confidence == "NOT_ASSESSED"
        and coordinates_blank
    )

    # --------------------------------------------------------
    # Operational inclusion status
    # --------------------------------------------------------

    operational_status = operational_decisions.get(
    code,
    "NOT_AVAILABLE_IN_SCRIPT38"
)

    # --------------------------------------------------------
    # Duplicate URL check
    # --------------------------------------------------------

    duplicate_urls = [
        url
        for url in urls
        if url_occurrences[url] > 1
    ]

    # --------------------------------------------------------
    # Evidence audit classification
    # --------------------------------------------------------

    if not metadata_complete:
        evidence_status = "INCOMPLETE_METADATA"

    elif url_status == "URL_CHECKED":
        evidence_status = "MANUAL_CONTENT_VERIFICATION_REQUIRED"

    elif url_status == "URL_PARTIALLY_ACCESSIBLE":
        evidence_status = "PARTIAL_SOURCE_ACCESS_MANUAL_REVIEW"

    elif url_status == "NO_URL":
        evidence_status = "SOURCE_URL_MISSING"

    else:
        evidence_status = "SOURCE_ACCESS_MANUAL_REVIEW"

    # Content is deliberately never automatically verified.
    content_status = "NOT_CONTENT_VERIFIED"

    audit_record = {
        "UN_LOCODE": code,
        "Port_Name": record[
            "Researcher_Validated_Port_Name"
        ],
        "Researcher_Validated_Facility_Name": record[
            "Researcher_Validated_Facility_Name"
        ],
        "Source_Organization": record[
            "Coordinate_Source_Organization"
        ],
        "Source_Title": record[
            "Coordinate_Source_Title"
        ],
        "Source_URL": raw_url_field,
        "Source_Access_Date": record[
            "Coordinate_Source_Access_Date"
        ],
        "Evidence_Description": record[
            "Coordinate_Evidence_Description"
        ],
        "Number_of_Source_URLs": len(urls),
        "URL_Audit_Status": url_status,
        "URL_Check_Details": " || ".join(
            (
                f'{x["url"]} => {x["status"]}'
                f' (HTTP {x["http_code"]})'
                if x["http_code"] != ""
                else f'{x["url"]} => {x["status"]}'
            )
            for x in url_results
        ),
        "Invalid_URL_Count": sum(
            x["status"] == "INVALID_URL"
            for x in url_results
        ),
        "Unreachable_URL_Count": sum(
            x["status"] != "ACCESSIBLE"
            and x["status"] != "INVALID_URL"
            for x in url_results
        ),
        "Duplicate_URLs": ";".join(
            sorted(set(duplicate_urls))
        ),
        "Metadata_Completeness": (
            "COMPLETE"
            if metadata_complete
            else "INCOMPLETE"
        ),
        "Missing_Metadata_Fields": ";".join(
            missing_fields
        ),
        "Source_Content_Status": content_status,
        "Evidence_Audit_Status": evidence_status,
        "Coordinate_Validation_Status": coordinate_status,
        "Coordinate_Confidence": confidence,
        "Coordinate_Fields_Blank": (
            "YES" if coordinates_blank else "NO"
        ),
        "Coordinate_Safeguard_Check": (
            "PASS" if coordinate_safeguard else "FAIL"
        ),
        "Operational_Inclusion_Decision": operational_status,
        "Manual_Review_Required": "YES",
        "Manual_Review_Notes": ""
    }

    audit_records.append(audit_record)

    print("   Metadata:", audit_record["Metadata_Completeness"])
    print("   URL audit:", url_status)
    print("   Evidence:", evidence_status)
    print("   Coordinate safeguard:", audit_record["Coordinate_Safeguard_Check"])


# ============================================================
# 5. DUPLICATE URL ANALYSIS
# ============================================================

duplicate_url_list = [
    url
    for url, count in url_occurrences.items()
    if count > 1
]

for audit_record in audit_records:

    urls = [
        u.strip()
        for u in audit_record["Source_URL"].split(";")
        if u.strip()
    ]

    matching_duplicates = [
        url for url in urls
        if url in duplicate_url_list
    ]

    audit_record["Duplicate_URLs"] = ";".join(
        sorted(set(matching_duplicates))
    )


# ============================================================
# 6. SUMMARY TABLE
# ============================================================

summary_records = []

for record in audit_records:

    summary_records.append({
        "UN_LOCODE": record["UN_LOCODE"],
        "Port_Name": record["Port_Name"],
        "Number_of_Source_URLs": record["Number_of_Source_URLs"],
        "URL_Audit_Status": record["URL_Audit_Status"],
        "Metadata_Completeness": record["Metadata_Completeness"],
        "Source_Content_Status": record["Source_Content_Status"],
        "Evidence_Audit_Status": record["Evidence_Audit_Status"],
        "Coordinate_Safeguard_Check": record[
            "Coordinate_Safeguard_Check"
        ],
        "Operational_Inclusion_Decision": record[
            "Operational_Inclusion_Decision"
        ],
        "Manual_Review_Required": record[
            "Manual_Review_Required"
        ]
    })


# ============================================================
# 7. WRITE AUDIT CSV
# ============================================================

audit_headers = list(audit_records[0].keys())

with AUDIT_FILE.open(
    "w",
    encoding="utf-8-sig",
    newline=""
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=audit_headers
    )

    writer.writeheader()
    writer.writerows(audit_records)


# ============================================================
# 8. WRITE SUMMARY CSV
# ============================================================

summary_headers = list(summary_records[0].keys())

with SUMMARY_FILE.open(
    "w",
    encoding="utf-8-sig",
    newline=""
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=summary_headers
    )

    writer.writeheader()
    writer.writerows(summary_records)


# ============================================================
# 9. AGGREGATE STATISTICS
# ============================================================

url_status_counts = Counter(
    r["URL_Audit_Status"]
    for r in audit_records
)

evidence_status_counts = Counter(
    r["Evidence_Audit_Status"]
    for r in audit_records
)

metadata_complete_count = sum(
    r["Metadata_Completeness"] == "COMPLETE"
    for r in audit_records
)

coordinate_safeguard_pass = sum(
    r["Coordinate_Safeguard_Check"] == "PASS"
    for r in audit_records
)

operational_pending = sum(
    r["Operational_Inclusion_Decision"] == "PENDING"
    for r in audit_records
)

manual_review_count = sum(
    r["Manual_Review_Required"] == "YES"
    for r in audit_records
)


# ============================================================
# 10. WRITE REPORT
# ============================================================

report_lines = []

report_lines.append(
    "SCRIPT 40: SOURCE URL AND EVIDENCE AUDIT"
)

report_lines.append("=" * 65)

report_lines.append(
    f"Input file: {INPUT_FILE}"
)

report_lines.append(
    f"Total port records: {len(records)}"
)

report_lines.append(
    f"Total columns in source register: {len(input_headers)}"
)

report_lines.append("")

report_lines.append("1. METADATA COMPLETENESS")
report_lines.append("-" * 65)

report_lines.append(
    f"Complete records: {metadata_complete_count}/{EXPECTED_RECORDS}"
)

report_lines.append(
    f"Incomplete records: {EXPECTED_RECORDS - metadata_complete_count}"
)

report_lines.append("")

report_lines.append("2. URL ACCESSIBILITY")
report_lines.append("-" * 65)

report_lines.append(
    f"Total URL references: {total_urls}"
)

report_lines.append(
    f"Accessible URL checks: {accessible_urls}"
)

report_lines.append(
    f"Unreachable/error URL checks: {unreachable_urls}"
)

report_lines.append(
    f"Invalid URL checks: {invalid_urls}"
)

for status, count in sorted(url_status_counts.items()):
    report_lines.append(
        f"{status}: {count} ports"
    )

report_lines.append("")

report_lines.append("3. EVIDENCE AUDIT CLASSIFICATION")
report_lines.append("-" * 65)

for status, count in sorted(evidence_status_counts.items()):
    report_lines.append(
        f"{status}: {count} ports"
    )

report_lines.append("")

report_lines.append("4. COORDINATE SAFEGUARDS")
report_lines.append("-" * 65)

report_lines.append(
    f"Safeguard checks passed: {coordinate_safeguard_pass}/{EXPECTED_RECORDS}"
)

report_lines.append(
    "Coordinates automatically approved: 0"
)

report_lines.append("")

report_lines.append("5. OPERATIONAL INCLUSION")
report_lines.append("-" * 65)

report_lines.append(
    f"Pending decisions: {operational_pending}/{EXPECTED_RECORDS}"
)

report_lines.append("")

report_lines.append("6. MANUAL SOURCE CONTENT REVIEW")
report_lines.append("-" * 65)

report_lines.append(
    f"Records requiring manual review: {manual_review_count}"
)

report_lines.append(
    "Source content automatically verified: 0"
)

report_lines.append("")

report_lines.append("7. DUPLICATE SOURCE URLS")
report_lines.append("-" * 65)

if duplicate_url_list:
    for url in sorted(duplicate_url_list):
        report_lines.append(
            f"{url} | Occurrences: {url_occurrences[url]}"
        )
else:
    report_lines.append("No duplicate URLs found.")

report_lines.append("")

report_lines.append("8. PORT-WISE EXCEPTIONS")
report_lines.append("-" * 65)

for r in audit_records:

    exceptions = []

    if r["Metadata_Completeness"] != "COMPLETE":
        exceptions.append("INCOMPLETE_METADATA")

    if r["URL_Audit_Status"] != "URL_CHECKED":
        exceptions.append(r["URL_Audit_Status"])

    if r["Coordinate_Safeguard_Check"] != "PASS":
        exceptions.append("COORDINATE_SAFEGUARD_FAILURE")

    if exceptions:
        report_lines.append(
            f'{r["UN_LOCODE"]}: {", ".join(exceptions)}'
        )

if not any(
    r["Metadata_Completeness"] != "COMPLETE"
    or r["URL_Audit_Status"] != "URL_CHECKED"
    or r["Coordinate_Safeguard_Check"] != "PASS"
    for r in audit_records
):
    report_lines.append(
        "No automated register exceptions detected."
    )

report_lines.append("")

report_lines.append("9. METHODOLOGICAL LIMITATIONS")
report_lines.append("-" * 65)

report_lines.append(
    "1. HTTP accessibility does not establish source reliability."
)

report_lines.append(
    "2. HTTP accessibility does not establish that the page "
    "supports the recorded claim."
)

report_lines.append(
    "3. Source-content verification requires manual review."
)

report_lines.append(
    "4. Port coordinates and terminal coordinates must be "
    "validated separately."
)

report_lines.append(
    "5. URL failures may result from anti-bot protection, "
    "redirect restrictions, server downtime or network issues."
)

report_lines.append(
    "6. No coordinates or operational inclusion decisions "
    "were modified by Script 40."
)

report_lines.append("")

report_lines.append("10. OUTPUT FILES")
report_lines.append("-" * 65)

report_lines.append(str(AUDIT_FILE))
report_lines.append(str(SUMMARY_FILE))
report_lines.append(str(REPORT_FILE))

REPORT_FILE.write_text(
    "\n".join(report_lines),
    encoding="utf-8"
)


# ============================================================
# 11. FINAL VERIFICATION
# ============================================================

with AUDIT_FILE.open(
    "r",
    encoding="utf-8-sig",
    newline=""
) as f:
    final_audit = list(csv.DictReader(f))

with SUMMARY_FILE.open(
    "r",
    encoding="utf-8-sig",
    newline=""
) as f:
    final_summary = list(csv.DictReader(f))

if len(final_audit) != EXPECTED_RECORDS:
    raise ValueError("Audit CSV record count mismatch.")

if len(final_summary) != EXPECTED_RECORDS:
    raise ValueError("Summary CSV record count mismatch.")


# ============================================================
# 12. TERMINAL OUTPUT
# ============================================================

print("\n" + "=" * 65)
print("SCRIPT 40 COMPLETED SUCCESSFULLY")
print("=" * 65)

print("INPUT RECORDS:", len(records))
print("INPUT COLUMNS:", len(input_headers))

print("\nMETADATA")
print(
    f"Complete: {metadata_complete_count}/{EXPECTED_RECORDS}"
)

print("\nURL AUDIT")
print("Total URL references:", total_urls)
print("Accessible checks:", accessible_urls)
print("Unreachable/error checks:", unreachable_urls)
print("Invalid URL checks:", invalid_urls)

print("\nCOORDINATE SAFEGUARDS")
print(
    f"Passed: {coordinate_safeguard_pass}/{EXPECTED_RECORDS}"
)

print("Coordinates approved: 0")

print("\nMANUAL CONTENT REVIEW")
print("Required:", manual_review_count)
print("Content automatically verified: 0")

print("\nOPERATIONAL INCLUSION")
print("Pending:", operational_pending)

print("\nOUTPUT FILES")
print(AUDIT_FILE)
print(SUMMARY_FILE)
print(REPORT_FILE)

print("\nOriginal Script 39 register was not modified.")
print("=" * 65)
