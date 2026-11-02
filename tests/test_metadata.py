"""Tests for src/ingest/metadata.py — banner text copied from the real UFGS 09 90 00 PDF."""

import pytest

from src.ingest.metadata import normalize_revision, parse_banner

REAL_BANNER = """\
**************************************************************************
USACE / NAVFAC / AFCEC
UFGS-09 90 00 (August 2026)
------------------------------------
Preparing Activity:  NAVFAC
Superseding
UFGS-09 90 00 (February 2021)
UNIFIED FACILITIES GUIDE SPECIFICATIONS
**************************************************************************
"""

BANNER_WITHOUT_SUPERSEDING = """\
USACE / NAVFAC / AFCEC
UFGS-26 51 00 (May 2018)
Preparing Activity:  USACE
UNIFIED FACILITIES GUIDE SPECIFICATIONS
"""


def test_normalize_revision_builds_release_label():
    assert normalize_revision("August", "2026") == "UFGS-2026-08"


def test_parse_banner_extracts_section_revision_and_supersedes():
    meta = parse_banner(REAL_BANNER)
    assert meta["section_code"] == "09 90 00"
    assert meta["revision"] == "UFGS-2026-08"
    assert meta["supersedes"] == "UFGS-2021-02"


def test_parse_banner_returns_none_supersedes_when_absent():
    meta = parse_banner(BANNER_WITHOUT_SUPERSEDING)
    assert meta["section_code"] == "26 51 00"
    assert meta["revision"] == "UFGS-2018-05"
    assert meta["supersedes"] is None


def test_parse_banner_rejects_non_ufgs_text():
    with pytest.raises(ValueError):
        parse_banner("This is not a UFGS document at all.")
