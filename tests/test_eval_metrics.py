"""Tests for the pure metric functions in eval/run_eval.py."""

import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "run_eval", Path(__file__).resolve().parent.parent / "eval" / "run_eval.py"
)
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)

GOLD = [{"section_code": "09 90 00", "section_path": "PART 3 > 3.5 > 3.5.1"}]


def test_paths_match_exact_and_ancestor_both_directions():
    assert ev.paths_match("PART 3 > 3.5", "PART 3 > 3.5")
    assert ev.paths_match("PART 3 > 3.5", "PART 3 > 3.5 > 3.5.1")  # gold is ancestor
    assert ev.paths_match("PART 3 > 3.5 > 3.5.1", "PART 3 > 3.5")  # chunk is ancestor
    assert not ev.paths_match("PART 3 > 3.5", "PART 3 > 3.51")  # no prefix false-positive


def test_citation_matches_requires_same_section_code():
    candidate = {"section_code": "03 30 00", "section_path": "PART 3 > 3.5 > 3.5.1"}
    assert not ev.citation_matches(GOLD[0], candidate)


def test_recall_at_k_counts_only_top_k():
    hit = {"section_code": "09 90 00", "section_path": "PART 3 > 3.5 > 3.5.1"}
    miss = {"section_code": "09 90 00", "section_path": "PART 1 > 1.1"}
    chunks = [miss, miss, hit]
    assert ev.retrieval_recall_at_k(GOLD, chunks, 3) == 1.0
    assert ev.retrieval_recall_at_k(GOLD, chunks, 2) == 0.0


def test_recall_rejects_empty_gold():
    with pytest.raises(ValueError):
        ev.retrieval_recall_at_k([], [], 5)


def test_citation_precision_recall_mixed_predictions():
    predicted = [
        {"section_code": "09 90 00", "section_path": "PART 3 > 3.5 > 3.5.1"},  # match
        {"section_code": "09 90 00", "section_path": "PART 1 > 1.1"},  # wrong place
    ]
    precision, recall = ev.citation_precision_recall(GOLD, predicted)
    assert precision == 0.5
    assert recall == 1.0


def test_citation_precision_recall_with_no_predictions():
    assert ev.citation_precision_recall(GOLD, []) == (0.0, 0.0)


def test_mean_of_empty_list_is_none_not_zero():
    assert ev.mean([]) is None
    assert ev.mean([0.5, 1.0]) == 0.75
