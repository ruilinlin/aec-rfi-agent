# DESIGN — aec-rfi-agent

## 1. Goal

Draft a **cited** response to a construction RFI from a project document set, using the **governing** revision of each document, and return a **gap report** instead of an answer when the documents do not settle the question.

Non-goals (for now): issuing final answers, BIM model reasoning, multi-project search, non-English documents.

## 2. Scope

### MVP
1. Ingest a small document set: spec sections (CSI MasterFormat PDFs) with revision metadata; optionally a few drawing-sheet PDFs (OCR).
2. Parse → section-aware chunking → embed into PostgreSQL + pgvector.
3. LangGraph agent: classify → retrieve → cross_check → draft → verify.
4. FastAPI `POST /rfi` returning a structured `CitedResponse` or `GapReport`.
5. `eval/run_eval.py` over RFI-Bench (dev split while developing, test split only for reported results).

### Stretch
- Submittal compliance check against the current spec.
- Drawing ↔ spec conflict detection.
- Minimal web UI (paste an RFI, see the cited draft).
- Autodesk Platform Services read-only connector (pull documents from a Forma/ACC project).

## 3. Agent graph

```
            ┌──────────┐
RFI ───────►│ classify │  type: clarification | conflict | superseded_ref | substitution | other
            └────┬─────┘  extracts referenced sections / sheets
                 ▼
            ┌──────────┐
            │ retrieve │  hybrid search (dense + BM25), filtered by doc_type / section / sheet
            └────┬─────┘
                 ▼
          ┌─────────────┐
          │ cross_check │  group hits by (doc, section); keep governing revision;
          └──────┬──────┘  emit explicit notes: "09 91 00 §2.3 Rev 2 superseded by Rev 3 on <date>"
                 ▼
            ┌──────────┐
            │  draft   │  every sentence must cite chunk ids; superseded chunks are visible
            └────┬─────┘  only as "superseded" notes, never as evidence
                 ▼
            ┌──────────┐
            │  verify  │  drop unsupported claims; if nothing governing remains → GapReport
            └────┬─────┘
                 ▼
        CitedResponse | GapReport
```

Design principle: **the LLM interprets and writes; deterministic code decides what counts as evidence.** Revision governance and citation checking are code, not prompt instructions. (Prior work shows that telling a model "follow the documents" increases its reliance on stale evidence, while explicit validity statements fix it — see docs/RESEARCH.md.)

## 4. Data model

```sql
documents(id, doc_type, title, source_url, section_code, sheet_number,
          revision, effective_date, supersedes_id, sha256)
chunks(id, document_id, section_path, page, text, embedding vector(<dim>), tsv tsvector)
```

- `section_code`: MasterFormat code, e.g. `09 91 00`
- `section_path`: e.g. `PART 2 > 2.3 > A`
- `supersedes_id`: points at the revision this document replaces (drives cross_check)
- `sha256`: of the source file, recorded in `data/MANIFEST.json` for reproducibility

## 5. Schemas (Pydantic)

```python
class RFIRequest:      id: str; question: str; references: list[str] = []
class Citation:        chunk_id: str; section_code: str | None; sheet: str | None; revision: str; quote_span: str
class CitedResponse:   rfi_id: str; rfi_type: str; answer: str; citations: list[Citation]; superseded_notes: list[str]
class GapReport:       rfi_id: str; reason: str; searched: list[str]; closest_matches: list[Citation]
```

## 6. Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Agent | LangGraph |
| LLM | provider-agnostic wrapper; at least one API model + one open-weight model for experiments |
| Vector DB | PostgreSQL 16 + pgvector (docker) |
| Keyword search | Postgres full-text (`tsvector`) |
| PDF parsing | pymupdf; OCR via tesseract for drawing sheets (stretch) |
| API | FastAPI |
| Tests | pytest |

## 7. Directory layout

```
aec-rfi-agent/
├── README.md  DESIGN.md  AGENTS.md  LICENSE
├── docker-compose.yml  .env.example  pyproject.toml  .gitignore
├── db/init.sql
├── data/            # raw corpus is gitignored; MANIFEST.json is committed
│   ├── MANIFEST.json
│   ├── specs/  drawings/  submittals/
├── src/
│   ├── ingest/      loaders.py  chunk.py  metadata.py  index.py
│   ├── retrieval/   store.py  hybrid.py
│   ├── agent/       graph.py  state.py  nodes.py  prompts.py
│   ├── api/         main.py
│   └── schemas.py
├── eval/
│   ├── rfi_bench/   dev.jsonl  test.jsonl  SCHEMA.md
│   ├── baselines/   b0_no_retrieval.py  b1_naive_rag.py  b2_hybrid_rag.py
│   ├── run_eval.py
│   └── results/     # one JSON per run + report.md
├── docs/            RESEARCH.md  DATA_SOURCES.md  ANNOTATION_GUIDE.md
├── paper/           # LaTeX later
└── tests/
```

## 8. Evaluation

See `eval/rfi_bench/SCHEMA.md` and `docs/ANNOTATION_GUIDE.md`.

Configurations compared:

| ID | Config |
|---|---|
| B0 | LLM only, no retrieval |
| B1 | Naive RAG: fixed-size chunks, top-k dense, "answer strictly from the documents" prompt |
| B2 | Hybrid RAG: dense + BM25 + metadata filters |
| Ours | Full agent |
| −cross_check | Ours without revision governance |
| −verify | Ours without claim verification / gap report |
| −section chunking | Ours with fixed-size chunks |

Rules:
- **Never tune prompts or thresholds on `test.jsonl`.** Develop on `dev.jsonl` only.
- Every run writes `eval/results/<timestamp>_<config>.json` with git SHA, model ids, corpus manifest hash, and per-item outputs.

## 9. Build order

1. Repo scaffold, docker Postgres + pgvector, schema.
2. Ingest one spec section end-to-end; write MANIFEST.json.
3. Happy path graph: classify → retrieve → draft (citations required).
4. `run_eval.py` with retrieval recall@k and citation precision on 10 dev items.
5. cross_check + verify; add revision pairs to the corpus.
6. Baselines B0–B2; ablations.
7. README results table + demo GIF.
