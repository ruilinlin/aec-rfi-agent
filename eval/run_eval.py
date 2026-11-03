"""Run a configuration over an RFI-Bench split and write a results JSON.

Usage:
    .venv/bin/python eval/run_eval.py --config ours --split dev

Writes eval/results/<timestamp>_<config>.json carrying everything needed to
reproduce the number: git SHA, model ids, corpus manifest hash, aggregate
metrics, and per-item outputs.

Metric definitions (v0):
  - retrieval recall@k: per answerable item, the fraction of gold citations
    found among the top-k retrieved chunks; averaged over items.
  - citation precision/recall: predicted citations vs gold citations matched
    on (section_code, section_path); averaged over answerable items.
  - abstain: the agent refused to answer (zero valid citations). Correct on
    unanswerable items, an error on answerable ones; both rates reported.
A gold citation matches a chunk/prediction when section codes are equal and
one section_path is the other or its ancestor prefix.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# --- matching and metrics (pure functions) ---------------------------------


def paths_match(gold_path: str, chunk_path: str) -> bool:
    """True when the paths are equal or one is an ancestor of the other."""
    g, c = gold_path.strip(), chunk_path.strip()
    return g == c or c.startswith(g + " > ") or g.startswith(c + " > ")


def citation_matches(gold: dict, candidate: dict) -> bool:
    """Match on section_code equality plus section_path equality/ancestry."""
    return gold.get("section_code") == candidate.get("section_code") and paths_match(
        gold.get("section_path", ""), candidate.get("section_path", "")
    )


def retrieval_recall_at_k(gold_citations: list[dict], chunks: list[dict], k: int) -> float:
    """Fraction of gold citations present among the top-k retrieved chunks."""
    if not gold_citations:
        raise ValueError("recall is undefined with no gold citations")
    top = chunks[:k]
    found = sum(1 for gold in gold_citations if any(citation_matches(gold, c) for c in top))
    return found / len(gold_citations)


def citation_precision_recall(
    gold_citations: list[dict], predicted: list[dict]
) -> tuple[float, float]:
    """Precision and recall of predicted citations against the gold set."""
    if not predicted:
        return 0.0, 0.0
    matched_pred = sum(
        1 for p in predicted if any(citation_matches(g, p) for g in gold_citations)
    )
    matched_gold = sum(
        1 for g in gold_citations if any(citation_matches(g, p) for p in predicted)
    )
    precision = matched_pred / len(predicted)
    recall = matched_gold / len(gold_citations) if gold_citations else 0.0
    return precision, recall


def cited_stale_revision(superseded_citations: list[dict], predicted: list[dict]) -> bool:
    """True when any predicted citation cites a superseded clause at its old revision."""
    return any(
        citation_matches(sup, p) and p.get("revision") == sup.get("revision")
        for sup in superseded_citations
        for p in predicted
    )


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


# --- configurations ---------------------------------------------------------


def _agent_config(retrieval_table: str = "chunks", **graph_kwargs):
    """Build a config function around one compiled agent-graph variant."""
    cache: dict = {}

    def run(item: dict) -> dict:
        from src.agent.graph import build_graph
        from src.schemas import GapReport, RFIRequest

        if "graph" not in cache:
            cache["graph"] = build_graph(**graph_kwargs)
        rfi = RFIRequest(
            id=item["id"],
            question=item["question"],
            references=item.get("references_in_question", []),
        )
        state = cache["graph"].invoke({"rfi": rfi, "retrieval_table": retrieval_table})
        response = state["response"]
        if isinstance(response, GapReport):
            return {
                "chunks": state["chunks"],
                "citations": [],
                "abstained": True,
                "abstain_reason": response.reason,
            }
        return {
            "chunks": state["chunks"],
            "citations": [c.model_dump() for c in response.citations],
            "abstained": False,
            "answer": response.answer,
        }

    return run


def _baseline(module_name: str):
    def run(item: dict) -> dict:
        import importlib

        module = importlib.import_module(f"eval.baselines.{module_name}")
        return module.run(item)

    return run


CONFIGS = {
    "b0": _baseline("b0_no_retrieval"),
    "b1": _baseline("b1_naive_rag"),
    "b2": _baseline("b2_hybrid_rag"),
    "ours": _agent_config(),
    "ours-no-crosscheck": _agent_config(with_cross_check=False),
    "ours-no-verify": _agent_config(with_verify=False),
    "ours-fixed-chunks": _agent_config(retrieval_table="chunks_fixed"),
}


# --- harness ----------------------------------------------------------------


def load_split(split: str) -> list[dict]:
    path = ROOT / "eval" / "rfi_bench" / f"{split}.jsonl"
    items = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    real = [i for i in items if not i["id"].startswith("TEMPLATE-")]
    skipped = len(items) - len(real)
    if skipped:
        print(f"note: skipped {skipped} TEMPLATE item(s); write real bench items")
    return real


def evaluate(config_name: str, split: str) -> dict:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    run_config = CONFIGS[config_name]
    items = load_split(split)
    if not items:
        raise SystemExit(f"no real items in {split}.jsonl — nothing to evaluate")

    per_item = []
    for item in items:
        print(f"running {item['id']} ({item['rfi_type']})...")
        output = run_config(item)
        record = {
            "id": item["id"],
            "rfi_type": item["rfi_type"],
            "answerable": item["answerable"],
            "abstained": output["abstained"],
            "citations": output["citations"],
        }
        if item["answerable"] and not output["abstained"]:
            gold = item["gold_citations"]
            chunk_keys = [
                {"section_code": c["section_code"], "section_path": c["section_path"]}
                for c in output["chunks"]
            ]
            record["recall_at_5"] = retrieval_recall_at_k(gold, chunk_keys, 5)
            record["recall_at_10"] = retrieval_recall_at_k(gold, chunk_keys, 10)
            # Predicted Citations carry no section_path (DESIGN §5); resolve it
            # from the retrieved chunks via chunk_id before matching.
            path_by_chunk = {c["id"]: c["section_path"] for c in output["chunks"]}
            predicted = [
                {
                    "section_code": c["section_code"],
                    "section_path": path_by_chunk.get(c["chunk_id"], ""),
                    "revision": c["revision"],
                }
                for c in output["citations"]
            ]
            precision, recall = citation_precision_recall(gold, predicted)
            record["citation_precision"] = precision
            record["citation_recall"] = recall
            if item.get("superseded_citations"):
                record["cited_stale_revision"] = cited_stale_revision(
                    item["superseded_citations"], predicted
                )
        elif item.get("superseded_citations"):
            record["cited_stale_revision"] = False  # abstaining never cites stale text
        per_item.append(record)

    answered = [r for r in per_item if r["answerable"] and not r["abstained"]]
    unanswerable = [r for r in per_item if not r["answerable"]]
    aggregate = {
        "items": len(per_item),
        "retrieval_recall_at_5": mean([r["recall_at_5"] for r in answered]),
        "retrieval_recall_at_10": mean([r["recall_at_10"] for r in answered]),
        "citation_precision": mean([r["citation_precision"] for r in answered]),
        "citation_recall": mean([r["citation_recall"] for r in answered]),
        "abstain_rate_on_answerable": mean(
            [1.0 if r["abstained"] else 0.0 for r in per_item if r["answerable"]]
        ),
        "abstain_rate_on_unanswerable": mean(
            [1.0 if r["abstained"] else 0.0 for r in unanswerable]
        ),
        "stale_revision_rate": mean(
            [
                1.0 if r["cited_stale_revision"] else 0.0
                for r in per_item
                if "cited_stale_revision" in r
            ]
        ),
    }
    return {"aggregate": aggregate, "items": per_item}


def provenance() -> dict:
    import os

    git_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    manifest_sha = hashlib.sha256((ROOT / "data" / "MANIFEST.json").read_bytes()).hexdigest()
    return {
        "git_sha": git_sha,
        "llm_model": os.environ.get("LLM_MODEL"),
        "embedding_model": os.environ.get("EMBEDDING_MODEL"),
        "manifest_sha256": manifest_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="ours", choices=sorted(CONFIGS))
    parser.add_argument("--split", default="dev", choices=["dev", "test"])
    args = parser.parse_args()

    results = evaluate(args.config, args.split)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "timestamp": timestamp,
        "config": args.config,
        "split": args.split,
        **provenance(),
        **results,
    }
    out_path = ROOT / "eval" / "results" / f"{timestamp}_{args.config}.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\naggregate: {json.dumps(payload['aggregate'], indent=2)}")
    print(f"wrote {out_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
