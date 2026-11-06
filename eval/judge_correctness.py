"""Rubric-score answer correctness for one eval results file, via the Batch API.

Usage (from the repo root):
    .venv/bin/python -m eval.judge_correctness eval/results/<run>.json \
        [--spot-check 30] [--seed 42] [--model claude-sonnet-5]

Judges only items that are answerable, answered, and carry stored answer
text (run-2+ result files). The judge sees the ground truth - the bench
author's reference answer plus the gold clause text fetched from the
database - never the agent's own retrieval. Requests go through
POST /v1/messages/batches (50% pricing); the poll loop tolerates the
documented worst case of 24h. Output: a *_judgments.json next to the
input (judge model, prompt sha256, batch id, per-item grades, aggregate
rates) and an optional seeded spot-check markdown for human review.
"""

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.util import ssl_context

API = "https://api.anthropic.com/v1"
GRADES = ("correct", "partial", "incorrect")

RUBRIC_SYSTEM = """You grade one drafted answer to a construction RFI against ground truth.

Ground truth has two parts: the bench author's reference answer, and the
verbatim text of the governing specification clause(s). The drafted answer
was produced by a retrieval system under test; judge ONLY whether its
substance matches the ground truth. Do not reward style, hedging, or extra
caveats, and do not punish them.

Grade with exactly one of:
- "correct": every key requirement/value the reference answer states is
  present and accurate (numbers, units, and conditions match; unit
  conversions and paraphrase are fine).
- "partial": the direction is right but a key value, unit, or qualifying
  condition from the reference answer is missing or imprecise.
- "incorrect": contradicts the ground truth, answers a different question,
  or asserts requirements the ground truth does not support.

Reply with JSON only: {"grade": "correct|partial|incorrect", "reason": "<one sentence>"}"""


def _api_key() -> str:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    return os.environ["LLM_API_KEY"]


def _request(method: str, url: str, key: str, payload: dict | None = None) -> bytes:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60, context=ssl_context()) as resp:
        return resp.read()


def _extract_json(text: str) -> dict:
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        # Truncated JSON still carries the grade; salvage it by pattern.
        match = re.search(r'"grade"\s*:\s*"(correct|partial|incorrect)"', text)
        if not match:
            raise
        reason = re.search(r'"reason"\s*:\s*"([^"]*)', text)
        return {
            "grade": match.group(1),
            "reason": (reason.group(1) if reason else "") + " [truncated]",
        }


def load_bench(split: str) -> dict[str, dict]:
    path = ROOT / "eval" / "rfi_bench" / f"{split}.jsonl"
    items = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return {item["id"]: item for item in items}


def gold_clause_texts(conn, gold_citations: list[dict]) -> list[str]:
    texts = []
    for gold in gold_citations:
        rows = conn.execute(
            """
            SELECT c.text FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE d.section_code = %s AND c.section_path = %s AND d.revision = %s
            """,
            (gold["section_code"], gold["section_path"], gold["revision"]),
        ).fetchall()
        for row in rows:
            texts.append(f"[{gold['section_code']} {gold['section_path']}] {row[0]}")
    return texts


def judgeable_items(results: dict, bench: dict[str, dict]) -> list[dict]:
    out = []
    for record in results["items"]:
        if "error" in record or not record["answerable"] or record["abstained"]:
            continue
        if not record.get("answer"):
            raise SystemExit(
                f"{record['id']} has no stored answer text - judge run-2+ result files only"
            )
        out.append({"record": record, "bench": bench[record["id"]]})
    return out


def build_request(pair: dict, clause_texts: list[str], model: str) -> dict:
    bench, record = pair["bench"], pair["record"]
    clauses = "\n\n".join(clause_texts) if clause_texts else "(clause text unavailable)"
    user = (
        f"RFI question:\n{bench['question']}\n\n"
        f"Reference answer (ground truth):\n{bench['reference_answer']}\n\n"
        f"Governing clause text (ground truth):\n{clauses}\n\n"
        f"Drafted answer under test:\n{record['answer']}"
    )
    return {
        "custom_id": record["id"],
        "params": {
            "model": model,
            "max_tokens": 1500,
            "system": RUBRIC_SYSTEM,
            "messages": [{"role": "user", "content": user}],
        },
    }


def run_batch(requests: list[dict], key: str, poll_seconds: int) -> list[dict]:
    created = json.loads(_request("POST", f"{API}/messages/batches", key, {"requests": requests}))
    batch_id = created["id"]
    print(f"batch {batch_id}: {len(requests)} request(s) submitted")
    while True:
        batch = json.loads(_request("GET", f"{API}/messages/batches/{batch_id}", key))
        if batch["processing_status"] == "ended":
            break
        counts = batch.get("request_counts", {})
        print(f"  polling... {counts}")
        time.sleep(poll_seconds)
    raw = _request("GET", batch["results_url"], key)
    results = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    return [{"batch_id": batch_id, **r} for r in results]


def parse_verdicts(batch_results: list[dict]) -> tuple[dict[str, dict], list[str]]:
    verdicts: dict[str, dict] = {}
    failed: list[str] = []
    for entry in batch_results:
        item_id = entry["custom_id"]
        result = entry["result"]
        if result["type"] != "succeeded":
            failed.append(f"{item_id}: {result['type']}")
            continue
        text = "".join(
            block["text"] for block in result["message"]["content"] if block["type"] == "text"
        )
        try:
            verdict = _extract_json(text)
            if verdict.get("grade") not in GRADES:
                raise ValueError(f"bad grade {verdict.get('grade')!r}")
        except (ValueError, json.JSONDecodeError) as exc:
            failed.append(f"{item_id}: unparseable verdict ({exc})")
            continue
        verdicts[item_id] = {"grade": verdict["grade"], "reason": verdict.get("reason", "")}
    return verdicts, failed


def write_spot_check(path: Path, pairs: list[dict], verdicts: dict, n: int, seed: int) -> None:
    rng = random.Random(seed)
    judged = [p for p in pairs if p["record"]["id"] in verdicts]
    sample = rng.sample(judged, min(n, len(judged)))
    lines = [
        "# Spot check - answer correctness judgments",
        "",
        f"Seeded sample (seed={seed}) of {len(sample)}/{len(judged)} judged items.",
        "Fill the 'human verdict' line for each; agreement rate goes in the paper.",
        "",
    ]
    for pair in sorted(sample, key=lambda p: p["record"]["id"]):
        record, bench = pair["record"], pair["bench"]
        verdict = verdicts[record["id"]]
        lines += [
            f"## {record['id']} - judge: **{verdict['grade']}**",
            "",
            f"- question: {bench['question']}",
            f"- reference answer: {bench['reference_answer']}",
            f"- drafted answer: {record['answer']}",
            f"- judge reason: {verdict['reason']}",
            "- human verdict: ",
            "",
        ]
    path.write_text("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results_file")
    parser.add_argument("--model", default="claude-sonnet-5")
    parser.add_argument("--spot-check", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--poll-seconds", type=int, default=30)
    args = parser.parse_args()

    results_path = Path(args.results_file)
    results = json.loads(results_path.read_text())
    bench = load_bench(results["split"])
    pairs = judgeable_items(results, bench)
    if not pairs:
        print("no judgeable items (answerable + answered + stored answer)")
        return 0

    key = _api_key()
    import psycopg

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        requests = [
            build_request(
                pair, gold_clause_texts(conn, pair["bench"]["gold_citations"]), args.model
            )
            for pair in pairs
        ]

    batch_results = run_batch(requests, key, args.poll_seconds)
    verdicts, failed = parse_verdicts(batch_results)
    # One direct (non-batch) retry per failure: empty responses and truncation
    # are transient, and a missing verdict skews the aggregate more than the
    # pennies a synchronous call costs.
    requests_by_id = {r["custom_id"]: r for r in requests}
    still_failed = []
    for failure in failed:
        item_id = failure.split(":")[0]
        print(f"  retrying {failure}")
        try:
            raw = _request("POST", f"{API}/messages", key, requests_by_id[item_id]["params"])
            message = json.loads(raw)
            text = "".join(b["text"] for b in message["content"] if b["type"] == "text")
            verdict = _extract_json(text)
            if verdict.get("grade") not in GRADES:
                raise ValueError(f"bad grade {verdict.get('grade')!r}")
            verdicts[item_id] = {
                "grade": verdict["grade"],
                "reason": verdict.get("reason", "") + " [direct retry]",
            }
        except Exception as exc:  # noqa: BLE001 - record, never crash the report
            still_failed.append(f"{failure}; retry: {type(exc).__name__}")
    failed = still_failed
    for failure in failed:
        print(f"  FAILED {failure}")

    graded = list(verdicts.values())
    n = len(graded)
    correct = sum(1 for v in graded if v["grade"] == "correct")
    partial = sum(1 for v in graded if v["grade"] == "partial")
    out = {
        "source_results": results_path.name,
        "config": results["config"],
        "split": results["split"],
        "judge_model": args.model,
        "rubric_sha256": hashlib.sha256(RUBRIC_SYSTEM.encode()).hexdigest()[:12],
        "batch_id": batch_results[0]["batch_id"] if batch_results else None,
        "aggregate": {
            "judged": n,
            "failed": len(failed),
            "correct": correct,
            "partial": partial,
            "incorrect": n - correct - partial,
            "correct_rate": correct / n if n else 0.0,
            "correct_or_partial_rate": (correct + partial) / n if n else 0.0,
        },
        "items": [{"id": k, **v} for k, v in sorted(verdicts.items())],
    }
    out_path = results_path.with_name(results_path.stem + "_judgments.json")
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {out_path}")
    print(json.dumps(out["aggregate"], indent=2))

    if args.spot_check:
        spot_path = results_path.with_name(results_path.stem + "_spotcheck.md")
        write_spot_check(spot_path, pairs, verdicts, args.spot_check, args.seed)
        print(f"wrote {spot_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
