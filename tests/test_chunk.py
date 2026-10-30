"""Tests for src/ingest/chunk.py — fixtures mirror the real UFGS text layout."""

import pytest

from src.ingest.chunk import (
    chunk_pages,
    find_body_start,
    parse_heading,
    section_path,
    strip_noise,
)

TOC_PAGE = """\
SECTION TABLE OF CONTENTS
DIVISION 09 - FINISHES
PART 1   GENERAL
  1.1   SUMMARY
  1.2   SURFACES TO BE PAINTED
SECTION 09 90 00  Page 1
"""

BODY_PAGE_1 = """\
PART 1   GENERAL
1.1   SUMMARY
**************************************************************************
NOTE:  Indicate type and extent of work on
drawings.
**************************************************************************
This section includes requirements for surface preparation.
1.2   SURFACES TO BE PAINTED
Paint all exposed exterior surfaces.
SECTION 09 90 00  Page 6
"""

BODY_PAGE_2 = """\
1.2.1   Painting Included
Exterior painting of site work items.
PART 2   PRODUCTS
2.1   MATERIALS
Use MPI listed products only.
SECTION 09 90 00  Page 7
"""

PAGES = [TOC_PAGE, BODY_PAGE_1, BODY_PAGE_2]


def test_strip_noise_removes_asterisk_banners_and_footers():
    cleaned = strip_noise(BODY_PAGE_1)
    assert "****" not in cleaned
    assert "Page 6" not in cleaned
    assert "NOTE:  Indicate type" in cleaned  # note text itself is kept


def test_find_body_start_skips_table_of_contents():
    assert find_body_start(PAGES) == 1


def test_find_body_start_raises_when_no_part1_exists():
    with pytest.raises(ValueError):
        find_body_start(["no headings here", "still nothing"])


def test_parse_heading_recognizes_part_and_dotted_numbers():
    assert parse_heading("PART 2   PRODUCTS") == ("PART 2", "PRODUCTS")
    assert parse_heading("1.2.1   Painting Included") == ("1.2.1", "Painting Included")


def test_parse_heading_rejects_body_text_and_toc_indents():
    assert parse_heading("Paint all exposed exterior surfaces.") is None
    assert parse_heading("  1.1   SUMMARY") is None  # TOC lines are indented


def test_section_path_builds_hierarchy_from_number_alone():
    assert section_path("PART 2") == "PART 2"
    assert section_path("1.1") == "PART 1 > 1.1"
    assert section_path("2.3.1") == "PART 2 > 2.3 > 2.3.1"


def test_chunk_pages_end_to_end():
    chunks = chunk_pages(PAGES)
    paths = [c["section_path"] for c in chunks]
    assert paths == [
        "PART 1",
        "PART 1 > 1.1",
        "PART 1 > 1.2",
        "PART 1 > 1.2 > 1.2.1",
        "PART 2",
        "PART 2 > 2.1",
    ]
    summary = next(c for c in chunks if c["section_path"] == "PART 1 > 1.1")
    assert "surface preparation" in summary["text"]
    assert summary["page"] == 2  # body page 1 is the PDF's page 2
    included = next(c for c in chunks if c["section_path"] == "PART 1 > 1.2 > 1.2.1")
    assert included["page"] == 3
