"""Unit tests for retrieval fusion and filter building (no database needed)."""

import pytest

from src.retrieval.hybrid import rrf_fuse
from src.retrieval.store import _filter_sql


def test_rrf_ranks_chunk_present_in_both_lists_first():
    scores = rrf_fuse([["a", "b", "c"], ["b", "d"]])
    ordered = sorted(scores, key=lambda cid: scores[cid], reverse=True)
    assert ordered[0] == "b"  # rank 2 + rank 1 beats any single appearance


def test_rrf_score_is_sum_of_reciprocal_ranks():
    scores = rrf_fuse([["a"], ["a"]], k=60)
    assert scores["a"] == pytest.approx(2 / 61)


def test_rrf_prefers_higher_rank_within_one_list():
    scores = rrf_fuse([["a", "b"]])
    assert scores["a"] > scores["b"]


def test_filter_sql_builds_clause_per_given_filter():
    where, params = _filter_sql({"doc_type": "spec", "revision": "UFGS-2026-08"})
    assert "d.doc_type = %(doc_type)s" in where
    assert "d.revision = %(revision)s" in where
    assert "section_code" not in where
    assert params == {"doc_type": "spec", "revision": "UFGS-2026-08"}


def test_filter_sql_ignores_none_values_and_empty_filters():
    assert _filter_sql(None) == ("", {})
    assert _filter_sql({"doc_type": None}) == ("", {})


def test_filter_sql_rejects_unknown_fields():
    with pytest.raises(ValueError, match="sheet_number"):
        _filter_sql({"sheet_number": "A-301"})
