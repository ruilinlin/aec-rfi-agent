# Research plan

## Research question

Can an agent that enforces revision governance, retrieves across document types, and reports gaps instead of guessing draft construction RFI responses more accurately than naive RAG, while substantially reducing hallucinated and stale-revision answers?

## Contributions (target)

1. **RFI-Bench** — an open benchmark of RFIs over public specifications, with gold citations, an unanswerable subset, and a revision subset whose answers depend on the governing revision.
2. **Revision-aware agent** — classify → retrieve → cross_check → draft → verify, with deterministic revision governance and claim verification.
3. **Systematic evaluation** — baselines, ablations, two model families, and error analysis by RFI type.

Positioning: commercial tools already draft cited RFI responses, but none publish a reproducible evaluation. The gap is the benchmark and the measurement, not the existence of the feature.

## Key related work

| Work | What it does | How we differ |
|---|---|---|
| Joy, Zarei, Nik-Bakht — *Semantic Mapping of RFI to BIM Elements with LLMs*, EC3 2026. DOI 10.35490/EC3.2026.337 | LLM extracts intent cues from RFI text; a rule-based five-stage pipeline matches BIM elements in Revit | Locates elements; does not retrieve specs or draft answers. Finding to reuse: many real RFIs depend on marked-up drawing attachments, so text-only RFIs must be self-contained |
| Kostis et al. — *Chronological Knowledge Retrieval: A RAG Approach to Construction Project Documentation*, arXiv 2604.14169 | Time-partitioned sub-indices over 60 meeting minutes; hybrid BM25 + dense with ColBERTv2 rerank; per-period answers merged into a timeline | 8 queries, no unanswerable items, generation not evaluated. Its open dataset can serve as a secondary test set |
| Ahmed, Galke Poech, Röttger — *Stale-Document Poisoning*, arXiv 2609.31342 | 317 knowledge reversals; one outdated document flips 30–37% of correct answers, 66–75% under "follow the documents" prompts; explicit validity boundaries fix it for large models | General domain. Motivates deterministic cross_check and the stale-revision metric |
| Wu et al. — *RAG4CM*, Advanced Engineering Informatics 65 (2025) 103158 | RAG for construction-management QA | No RFIs, no revision handling |
| Afzal et al. — RFI classification / NER (UTS thesis; IEEE CASE 2023) | RFI topic modelling, classification, entity extraction | Source for an RFI type taxonomy |

TODO before writing: Google Scholar sweep for "request for information" + "large language model", Automation in Construction 2025–2026.

## Target venues

| Venue | Deadline | Notes |
|---|---|---|
| EC3 + CIB W78 2027 (Thessaloniki, 11–14 Jul 2027) | Optional abstract 30 Oct 2026; **full paper 15 Jan 2027**; first decision 5 Mar 2027 | Primary target |
| eCAADe 2027 (Aalto, Aug 2027) | Not yet announced; past editions: abstract ~15 Jan, full paper ~1 Apr | Backup |
| Automation in Construction / Advanced Engineering Informatics / ITcon | Rolling | Extended journal version |

Verify all dates on the official sites before relying on them.

## Reproducibility rules (from day one)

- Pin the corpus: `data/MANIFEST.json` lists every source file, its URL, release date, and sha256. Do not change the corpus without bumping the manifest version.
- Keep `eval/rfi_bench/test.jsonl` frozen once written. Develop on `dev.jsonl` only.
- Every eval run records git SHA, model ids, temperature, and manifest hash.
- Log notable failure cases in `eval/results/failures.md` as they happen; they become the error-analysis section.
