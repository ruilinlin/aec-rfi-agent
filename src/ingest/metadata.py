"""Parse document-level metadata from a UFGS first-page banner.

The first page of every UFGS PDF carries a banner like:

    USACE / NAVFAC / AFCEC
    UFGS-09 90 00 (August 2026)
    ------------------------------------
    Preparing Activity:  NAVFAC
    Superseding
    UFGS-09 90 00 (February 2021)

From it we extract the section code, the normalized revision label, and the
revision this document supersedes (None when there is no Superseding block).
"""

import re

MONTHS = {
    "January": "01",
    "February": "02",
    "March": "03",
    "April": "04",
    "May": "05",
    "June": "06",
    "July": "07",
    "August": "08",
    "September": "09",
    "October": "10",
    "November": "11",
    "December": "12",
}

# Matches e.g. 'UFGS-09 90 00 (August 2026)'; level-5 codes like
# 'UFGS-09 97 10.00 10' also start with the same 'UFGS-' prefix.
BANNER_RE = re.compile(r"UFGS-([\d .]+?)\s*\((\w+)\s+(\d{4})\)")


def normalize_revision(month_name: str, year: str) -> str:
    """('August', '2026') -> 'UFGS-2026-08'. Raise KeyError on unknown month."""
    return f"UFGS-{year}-{MONTHS[month_name]}"


def parse_banner(first_page_text: str) -> dict:
    """Extract metadata from the first page of a UFGS PDF.

    Returns {'section_code': '09 90 00',
             'revision': 'UFGS-2026-08',
             'supersedes': 'UFGS-2021-02' or None}
    """
    matches = BANNER_RE.findall(first_page_text)
    if not matches:
        raise ValueError("no UFGS banner found; not a UFGS PDF?")

    code, month, year = matches[0]
    supersedes = None
    if "Superseding" in first_page_text and len(matches) > 1:
        _, old_month, old_year = matches[1]
        supersedes = normalize_revision(old_month, old_year)

    return {
        "section_code": code.strip(),
        "revision": normalize_revision(month, year),
        "supersedes": supersedes,
    }
