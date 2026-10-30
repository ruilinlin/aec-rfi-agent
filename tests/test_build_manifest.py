"""Unit tests for scripts/build_manifest.py (pure functions only, no network)."""

import hashlib
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "build_manifest", Path(__file__).resolve().parent.parent / "scripts" / "build_manifest.py"
)
bm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bm)


def test_slug_converts_spaces_to_hyphens():
    assert bm.section_to_slug("09 90 00") == "ufgs-09-90-00"


def test_slug_converts_dots_in_level5_codes():
    assert bm.section_to_slug("09 97 10.00 10") == "ufgs-09-97-10-00-10"


def test_pick_skips_current_zip_listed_before_pdf():
    meta = {
        "title": "TEST DOC",
        "mediaFiles": [
            {"isCurrent": True, "fileName": "UFGS 03 30 00.zip", "fileUrl": "zip"},
            {"isCurrent": True, "fileName": "UFGS 03 30 00.pdf", "fileUrl": "pdf"},
        ],
    }
    assert bm.pick_current_pdf(meta)["fileUrl"] == "pdf"


def test_pick_works_when_mimetype_is_null():
    # The real API returns mimeType null for most documents; only fileName is reliable.
    meta = {
        "title": "TEST DOC",
        "mediaFiles": [
            {"isCurrent": True, "fileName": "UFGS 03 30 00.pdf", "mimeType": None, "fileUrl": "pdf"}
        ],
    }
    assert bm.pick_current_pdf(meta)["fileUrl"] == "pdf"


def test_pick_raises_when_only_archived_pdf_exists():
    meta = {
        "title": "TEST DOC",
        "mediaFiles": [{"isCurrent": False, "fileName": "UFGS 03 30 00.pdf", "fileUrl": "old"}],
    }
    with pytest.raises(ValueError, match="TEST DOC"):
        bm.pick_current_pdf(meta)


def test_sha256_matches_hashlib_on_known_content(tmp_path):
    f = tmp_path / "sample.bin"
    content = b"ufgs corpus test content"
    f.write_bytes(content)
    assert bm.sha256_of(f) == hashlib.sha256(content).hexdigest()
