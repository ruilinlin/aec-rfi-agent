"""Gap loop: cluster open gap reports and replay them after corpus growth.

Usage (from the repo root):
    .venv/bin/python scripts/gap_loop.py report [--threshold 0.8]
    .venv/bin/python scripts/gap_loop.py replay [--limit N]

`report` groups open gaps by cosine similarity of their stored question
embeddings (greedy, anchor-based, deterministic) so recurring unanswerable
topics surface as ingest candidates. Observed voyage-3.5 scale on real gaps:
near-duplicate phrasings score >=0.8 (the default threshold), same topic but
different aspects ~0.5, unrelated questions ~0.2 - pass --threshold 0.5 for
topic-level grouping. `replay` re-runs each open gap through
the full agent; questions that now yield a CitedResponse are closed with a
citation + corpus-manifest provenance note. The loop itself is deterministic
code - the only LLM involvement is the agent run inside replay.
"""

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def cluster_gaps(gaps: list[dict], threshold: float) -> list[list[dict]]:
    """Greedy anchor clustering: each gap joins the first cluster whose anchor
    (first member) is at least `threshold` cosine-similar, else starts a new
    cluster. Anchor-based (not centroid) keeps the assignment deterministic
    and order-independent of later members. Input order = created_at order.
    """
    clusters: list[list[dict]] = []
    for gap in gaps:
        for cluster in clusters:
            if cosine(gap["embedding"], cluster[0]["embedding"]) >= threshold:
                cluster.append(gap)
                break
        else:
            clusters.append([gap])
    return sorted(clusters, key=len, reverse=True)


def fetch_open_gaps(conn) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, question, searched, embedding::text
        FROM gap_reports
        WHERE closed_at IS NULL AND embedding IS NOT NULL
        ORDER BY created_at
        """
    ).fetchall()
    return [
        {"id": r[0], "question": r[1], "searched": r[2], "embedding": json.loads(r[3])}
        for r in rows
    ]


def cmd_report(conn, threshold: float) -> int:
    gaps = fetch_open_gaps(conn)
    if not gaps:
        print("no open gap reports")
        return 0
    clusters = cluster_gaps(gaps, threshold)
    print(f"{len(gaps)} open gap(s) in {len(clusters)} cluster(s) (threshold {threshold}):\n")
    for i, cluster in enumerate(clusters, 1):
        searched = sorted({code for gap in cluster for code in gap["searched"]})
        print(f"cluster {i} ({len(cluster)} gap(s)) - searched without success: {searched}")
        for gap in cluster:
            print(f"  - {gap['question'][:110]}")
        print()
    print("largest clusters are the strongest ingest candidates for the next corpus batch")
    return 0


def manifest_sha() -> str:
    return hashlib.sha256((ROOT / "data" / "MANIFEST.json").read_bytes()).hexdigest()[:12]


def closure_note(response, manifest: str) -> str:
    """One line of provenance: what now answers the question, on which corpus.

    Falls back section_code -> sheet -> chunk_id, so drawing citations (which
    carry a sheet number instead of a MasterFormat code) never record 'None'.
    """
    cited = sorted(
        {f"{c.section_code or c.sheet or c.chunk_id}@{c.revision}" for c in response.citations}
    )
    return f"answered citing {', '.join(cited)}; corpus manifest {manifest}"


def cmd_replay(conn, limit: int | None) -> int:
    """Re-run open gaps; close the ones the corpus now answers.

    The connection must be in autocommit mode: each closure commits as it is
    printed, so a failure on question N can never roll back closures 1..N-1
    (psycopg's connection context manager would otherwise discard them all
    while stdout claims they were closed). One failing question is reported
    and skipped, not fatal. Each run is wrapped in trace_run so the cost is
    printed per question and in total; replay deliberately does not write
    rfi_requests rows - its telemetry is stdout-only.
    """
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from src.agent.graph import build_graph
    from src.agent.trace import trace_run
    from src.schemas import GapReport, RFIRequest

    rows = conn.execute(
        "SELECT id, question FROM gap_reports WHERE closed_at IS NULL ORDER BY created_at"
    ).fetchall()
    if limit is not None:
        rows = rows[:limit]
    if not rows:
        print("no open gap reports to replay")
        return 0

    graph = build_graph()
    manifest = manifest_sha()
    closed = failed = 0
    total_cost = 0.0
    for gap_id, question in rows:
        print(f"replaying {gap_id}: {question[:80]}...")
        try:
            with trace_run() as trace:
                state = graph.invoke(
                    {"rfi": RFIRequest(id=f"replay-{gap_id}", question=question)}
                )
        except Exception as exc:  # noqa: BLE001 - one bad question must not abort the run
            failed += 1
            print(f"  FAILED: {type(exc).__name__}: {exc}")
            continue
        cost = trace.summary().total_cost_usd
        total_cost += cost
        response = state["response"]
        # A closure needs provenance: no citations, no close.
        if isinstance(response, GapReport) or not response.citations:
            print(f"  still a gap (${cost:.4f})")
            continue
        note = closure_note(response, manifest)
        conn.execute(
            "UPDATE gap_reports SET closed_at = now(), closure_note = %s WHERE id = %s",
            (note, gap_id),
        )
        closed += 1
        print(f"  CLOSED (${cost:.4f}): {note}")
    still_open = len(rows) - closed
    print(f"\nreplayed {len(rows)}, closed {closed}, failed {failed}, still open {still_open}")
    print(f"replay cost: ${total_cost:.4f} (stdout-only; replay does not write rfi_requests)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    report = sub.add_parser("report", help="cluster open gaps into ingest candidates")
    report.add_argument(
        "--threshold",
        type=float,
        default=0.8,
        help="cosine similarity to join a cluster: 0.8=near-duplicates, ~0.5=topic-level",
    )
    replay = sub.add_parser("replay", help="re-run open gaps; close the answered ones")
    replay.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    import psycopg

    # autocommit: replay commits each closure as it prints it, so stdout and
    # the database can never disagree after a mid-run failure. report only reads.
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        if args.command == "report":
            return cmd_report(conn, args.threshold)
        return cmd_replay(conn, args.limit)


if __name__ == "__main__":
    sys.exit(main())
