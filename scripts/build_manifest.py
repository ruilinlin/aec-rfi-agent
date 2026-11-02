"""Download the pinned UFGS corpus and build data/MANIFEST.json.

Usage:
    .venv/bin/python scripts/build_manifest.py

Behavior:
    For each section in SECTIONS: resolve its WBDG API slug, fetch document
    metadata, download the current PDF into data/specs/, compute sha256, and
    record one manifest entry. Idempotent: a file that already exists is
    skipped (download() writes to a temp name and renames, so an existing
    file is always a complete download).

Raw PDFs stay gitignored; only MANIFEST.json is committed.
"""

import hashlib
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = ROOT / "data" / "specs"
MANIFEST_PATH = ROOT / "data" / "MANIFEST.json"

API_BASE = "https://www.wbdg.org/api/documents/"
RELEASE = "UFGS-2026-08"  # current quarterly master; update when re-pinning
REQUEST_DELAY_SECONDS = 1  # be polite to a public server

# The UFGS_ARCHIVES bucket holds one PDF per section: the most recently
# superseded revision. Its content rotates when a new quarterly revision
# lands, so the sha256 recorded in the manifest pins what was actually used.
ARCHIVE_URL_BASE = "https://nibs-s3-wbdg3-production.s3.us-east-1.amazonaws.com/FFC/DOD/UFGS_ARCHIVES/"
# Sections ingested in BOTH the current and the previous revision, forming
# the revision pairs that cross_check governs over.
ARCHIVE_SECTIONS = [
    "09 90 00",
]

# Starting corpus: building-relevant mix across divisions (see docs/DATA_SOURCES.md).
SECTIONS = [
    "03 30 00",
    "07 92 00",
    "07 54 19",
    "08 11 13",
    "08 51 13",
    "09 29 00",
    "09 51 00",
    "09 65 00",
    "09 90 00",
    "22 00 00",
    "26 51 00",
    "26 20 00",
]


def ssl_context() -> ssl.SSLContext:
    """Return an SSL context that works around the python.org macOS cert issue."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def section_to_slug(section_code: str) -> str:
    """Convert a MasterFormat section code to a WBDG API slug.

    '09 90 00'       -> 'ufgs-09-90-00'
    '09 97 10.00 10' -> 'ufgs-09-97-10-00-10'  (dots become hyphens too)
    """
    return "ufgs-" + section_code.replace(" ", "-").replace(".", "-")


def fetch_document_meta(slug: str) -> dict:
    """GET {API_BASE}{slug} and return the parsed 'data' object.

    A 404 (slug does not exist) propagates as HTTPError; main() reports it
    as a failed section rather than crashing the whole run.
    """
    with urllib.request.urlopen(API_BASE + slug, context=ssl_context(), timeout=60) as resp:
        payload = json.load(resp)
    return payload["data"]


def pick_current_pdf(meta: dict) -> dict:
    """Return the mediaFiles entry for the current PDF.

    Filter: isCurrent is True AND fileName ends in .pdf. The mimeType field
    is unreliable (null for most documents), so the extension is the signal;
    the current zip and archived PDFs sit in the same list.
    """
    for media in meta["mediaFiles"]:
        name = str(media.get("fileName", "")).lower()
        if media.get("isCurrent") and name.endswith(".pdf"):
            return media
    raise ValueError(f"no current PDF for {meta.get('title', 'unknown document')}")


def sha256_of(path: Path) -> str:
    """Return the hex sha256 of a file. Read in chunks; PDFs can be large."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def download(url: str, dest: Path) -> None:
    """Download url to dest (write to a temp name, then rename).

    The temp-then-rename dance means an interrupted download never leaves a
    half-written file that a later idempotent run would mistakenly trust.
    """
    tmp = dest.with_suffix(".part")
    with urllib.request.urlopen(url, context=ssl_context(), timeout=120) as resp:
        tmp.write_bytes(resp.read())
    tmp.rename(dest)


def build_entry(section_code: str, meta: dict, pdf: dict, local_path: Path) -> dict:
    """Return one manifest entry matching the existing MANIFEST.json template."""
    return {
        "id": "UFGS-" + section_code.replace(" ", "-").replace(".", "-"),
        "doc_type": "spec",
        "section_code": section_code,
        "title": meta["title"],
        "release": RELEASE,
        "url": pdf["fileUrl"],
        "downloaded": date.today().isoformat(),
        "local_path": str(local_path.relative_to(ROOT)),
        "sha256": sha256_of(local_path),
    }


def write_manifest(entries: list[dict]) -> None:
    """Write MANIFEST.json: keep manifest_version/created, replace documents.

    Entries are sorted by section_code so the output depends only on content,
    not on SECTIONS order; re-running the script yields an empty git diff.
    """
    manifest = json.loads(MANIFEST_PATH.read_text())
    manifest["documents"] = sorted(entries, key=lambda e: e["section_code"])
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")


def archive_entries() -> list[dict]:
    """Download the superseded revision of each ARCHIVE_SECTIONS section."""
    entries = []
    for section_code in ARCHIVE_SECTIONS:
        url = ARCHIVE_URL_BASE + urllib.parse.quote(f"UFGS {section_code}.pdf")
        stem = section_code.replace(" ", "_").replace(".", "_")
        local_path = SPECS_DIR / f"UFGS_{stem}_prev.pdf"
        if local_path.exists():
            print(f"skip {section_code} (prev): already downloaded ({local_path.name})")
        else:
            download(url, local_path)
            print(f"ok   {section_code} (prev): downloaded {local_path.stat().st_size} bytes")
            time.sleep(REQUEST_DELAY_SECONDS)
        entries.append(
            {
                "id": "UFGS-" + section_code.replace(" ", "-").replace(".", "-") + "-PREV",
                "doc_type": "spec",
                "section_code": section_code,
                "title": f"UFGS {section_code} (superseded revision, from UFGS_ARCHIVES)",
                "release": "UFGS-ARCHIVE",
                "url": url,
                "downloaded": date.today().isoformat(),
                "local_path": str(local_path.relative_to(ROOT)),
                "sha256": sha256_of(local_path),
            }
        )
    return entries


def main() -> int:
    SPECS_DIR.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    failed: list[str] = []

    for section_code in SECTIONS:
        slug = section_to_slug(section_code)
        try:
            meta = fetch_document_meta(slug)
            pdf = pick_current_pdf(meta)
        except (urllib.error.URLError, ValueError, KeyError) as exc:
            print(f"FAIL {section_code}: {exc}")
            failed.append(section_code)
            continue

        local_path = SPECS_DIR / f"UFGS_{section_code.replace(' ', '_').replace('.', '_')}.pdf"

        if local_path.exists():
            print(f"skip {section_code}: already downloaded ({local_path.name})")
        else:
            download(pdf["fileUrl"], local_path)
            print(f"ok   {section_code}: downloaded {local_path.stat().st_size} bytes")
            time.sleep(REQUEST_DELAY_SECONDS)

        entries.append(build_entry(section_code, meta, pdf, local_path))

    entries.extend(archive_entries())
    write_manifest(entries)
    print(f"\nmanifest: {len(entries)} entries, {len(failed)} failed {failed or ''}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
