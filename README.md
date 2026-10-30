# aec-rfi-agent

**A revision-aware agent that drafts cited answers to construction RFIs — and says "not found" instead of guessing.**

> Status: 🚧 early development. MVP target: mid-November 2026.

## The problem

On a construction project, a contractor who finds something unclear or contradictory in the drawings or specifications sends a formal **Request for Information (RFI)** to the design team. Answering one means searching across spec sections, drawing sheets, submittals, and their revisions. Studies report an average of ~17 person-hours per RFI, and RFI delays can account for up to 10% of a project's duration.

Generic RAG systems can draft an answer, but they fail in ways that matter on a job site:

- they cite **superseded** spec revisions as if they were current;
- they **blend** conflicting sources into one plausible answer;
- they **invent** a requirement when the documents are silent.

## What this agent does

Given an RFI question and a project document set (specs, drawings, submittals), the agent:

1. **classifies** the RFI (clarification, conflict, superseded reference, substitution, …);
2. **retrieves** across document types with metadata filters (spec section, sheet number, revision);
3. **cross-checks** revisions and conflicts — prefers the governing version and flags superseded references explicitly;
4. **drafts** a response where every claim carries a citation (spec section / sheet / revision);
5. **verifies** the draft — any unsupported claim is removed, and if no governing requirement exists the agent returns a **gap report** instead of an answer.

The agent drafts; a licensed professional decides. It never issues an answer on its own authority.

## Architecture

```
RFI ──► classify ──► retrieve ──► cross_check ──► draft ──► verify ──► cited draft | gap report
                        │              │
                  pgvector + BM25   revision metadata
```

- **Agent:** LangGraph state graph
- **Retrieval:** PostgreSQL + pgvector, hybrid (dense + keyword) search with metadata filters
- **API:** FastAPI (`POST /rfi`)
- **Eval:** golden RFI set with gold citations, including unanswerable and revision-sensitive items

See [DESIGN.md](DESIGN.md) for the full design.

## Evaluation (RFI-Bench)

The project ships with a small, open benchmark of RFIs written against public specifications. Each item has gold citations; ~15–20% are deliberately **unanswerable**, and a **revision subset** contains questions whose correct answer depends on which spec revision governs.

| Metric | What it measures |
|---|---|
| Retrieval recall@k | Did the governing section/sheet get retrieved? |
| Citation precision / recall | Are the cited references the right ones? |
| Hallucination rate | Share of claims with no supporting source |
| Gap-detection F1 | Does the agent say "not found" on unanswerable RFIs? |
| Stale-revision rate | How often a superseded revision drives the answer |

Results table: _coming with the MVP_ (naive RAG vs. hybrid RAG vs. this agent, plus ablations).

## Quickstart

```bash
cp .env.example .env          # add your LLM API key
docker compose up -d db       # Postgres + pgvector
pip install -e ".[dev]"
python -m src.ingest.index --source data/specs     # coming in MVP
uvicorn src.api.main:app --reload                  # coming in MVP
```

## Data

All source documents are public (U.S. Unified Facilities Guide Specifications, public municipal tender packages). RFIs are synthetic, written in realistic RFI format. See [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## Roadmap

- [ ] Ingest one spec set with section + revision metadata
- [ ] Happy path: classify → retrieve → draft with citations
- [ ] cross_check (revision / conflict) and verify (gap report)
- [ ] RFI-Bench v0.1 (dev + test split) and `run_eval.py`
- [ ] Baselines and ablations; results table in this README
- [ ] Minimal web UI and demo GIF

## Research

This repository also supports a research write-up on revision-aware, citation-grounded RFI response drafting. See [docs/RESEARCH.md](docs/RESEARCH.md).

## License

Code: MIT. Benchmark data (RFI-Bench questions and annotations): CC BY 4.0. Source documents remain under their original terms.
