"""Section-aware chunking for UFGS spec text.

A UFGS PDF has three text zones:
  1. first-page banner + SECTION TABLE OF CONTENTS (several pages) — skipped;
  2. body: headings like 'PART 1   GENERAL', '1.1   SUMMARY', '1.2.1   ...'
     at the start of a line, with contract text underneath;
  3. noise interleaved everywhere: lines of asterisks delimiting designer
     NOTE blocks, and a page footer 'SECTION 09 90 00  Page 12'.

One chunk = one lowest-level section: everything from a heading until the
next heading, tagged with its hierarchical section_path and starting page.
"""

import re

# A body heading: 'PART 1   GENERAL' or a dotted number '1.2.1   Painting Included'.
HEADING_RE = re.compile(r"^(PART \d+|\d+(?:\.\d+)+)\s{2,}(\S.*)$")

NOISE_RES = [
    re.compile(r"^\*{10,}\s*$"),               # asterisk banner lines
    re.compile(r"^SECTION [\d .]+ {2}Page \d+\s*$"),  # page footer
]


def strip_noise(page_text: str) -> str:
    """Drop noise lines (NOISE_RES) from one page's text, keep everything else."""
    kept = [
        line
        for line in page_text.splitlines()
        if not any(pattern.match(line) for pattern in NOISE_RES)
    ]
    return "\n".join(kept)


def find_body_start(pages: list[str]) -> int:
    """Return the index of the first body page.

    The table of contents lists 'PART 1   GENERAL' too, so the body is the
    LAST page where 'PART 1' appears at the start of a line.
    """
    last_seen = None
    for i, page in enumerate(pages):
        if re.search(r"^PART 1\s{2,}", page, re.MULTILINE):
            last_seen = i
    if last_seen is None:
        raise ValueError("no 'PART 1' heading found in any page")
    return last_seen


def parse_heading(line: str) -> tuple[str, str] | None:
    """Return (number, title) when line is a heading, else None.

    'PART 2   PRODUCTS'         -> ('PART 2', 'PRODUCTS')
    '1.2.1   Painting Included' -> ('1.2.1', 'Painting Included')
    'some body text'            -> None

    UFGS marks optional clauses with square brackets, and the bracket often
    lands at the start of a heading line ('[3.1.5.2   ...', ']1.5   ...');
    leading brackets are stripped so those headings still split into their
    own chunks. TOC lines stay excluded: they are indented with spaces.
    """
    m = HEADING_RE.match(line.lstrip("[]"))
    if m is None:
        return None
    return m.group(1), m.group(2)


def section_path(number: str) -> str:
    """Build the hierarchical path purely from the heading number.

    'PART 2' -> 'PART 2'
    '1.1'    -> 'PART 1 > 1.1'
    '2.3.1'  -> 'PART 2 > 2.3 > 2.3.1'
    """
    if number.startswith("PART"):
        return number
    parts = number.split(".")
    path = [f"PART {parts[0]}"]
    for depth in range(2, len(parts) + 1):
        path.append(".".join(parts[:depth]))
    return " > ".join(path)


def chunk_pages(pages: list[str]) -> list[dict]:
    """Split a UFGS document into section chunks.

    Returns [{'section_path': 'PART 1 > 1.1', 'page': 6, 'text': '...'}, ...].
    Text before the first heading on the body pages is dropped (it is the
    tail of the designer-note preamble). Chunks with no body text are kept:
    a heading alone still locates a section a citation can point at.
    """
    start = find_body_start(pages)
    chunks: list[dict] = []
    current: dict | None = None

    for page_index in range(start, len(pages)):
        for line in strip_noise(pages[page_index]).splitlines():
            heading = parse_heading(line)
            if heading is not None:
                if current is not None:
                    current["text"] = current["text"].strip()
                    chunks.append(current)
                number, title = heading
                current = {
                    "section_path": section_path(number),
                    "page": page_index + 1,
                    "text": title + "\n",
                }
            elif current is not None:
                current["text"] += line + "\n"

    if current is not None:
        current["text"] = current["text"].strip()
        chunks.append(current)
    return chunks
