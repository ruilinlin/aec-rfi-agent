# RUN 2 — second (and declared) use of the frozen test split

**Date:** 2026-11-06 · **Configs rerun:** ours, b2, ours-no-verify · **Model:** claude-sonnet-5 ·
**Corpus manifest:** identical to RUN 1 (sha match verified) · **Tuning between runs:** none.

## Purpose

RUN 1 (2026-11-03) measured evidence discipline only; its result records did not store answer
text, so answer correctness could not be judged post hoc. RUN 2 exists solely to add a
rubric-scored correctness metric. Nothing was changed between runs except the record format
(answers now stored). The test split remains frozen and was never used for tuning.

## Results files

| config | RUN 1 | RUN 2 | judgments |
|---|---|---|---|
| ours | 20261103T173424Z_ours.json | 20261106T163030Z_ours.json | 20261106T163030Z_ours_judgments.json |
| b2 | 20261103T172528Z_b2.json | 20261106T163238Z_b2.json | 20261106T163238Z_b2_judgments.json |
| ours-no-verify | 20261103T181153Z_ours-no-verify.json | 20261106T163812Z_ours-no-verify.json | 20261106T163812Z_ours-no-verify_judgments.json |

## Answer correctness (RUN 2, LLM-judged, human spot check pending)

| config | judged | correct | partial | incorrect | correct rate |
|---|---|---|---|---|---|
| ours | 31 | 30 | 1 | 0 | 97% |
| b2 | 32 | 28 | 4 | 0 | 87.5% |
| ours-no-verify | 32 | 30 | 0 | **2** | 94% |

Readings: on questions they chose to answer, all three configs are substantively decent —
the danger concentrates in questions b2 should never have answered (8/8 unanswerable traps)
and revisions it should not have cited (5/8 stale). The verify node's correctness
contribution is specific: it is the only config difference that eliminates *incorrect*
answers (2 without it, 0 with it). Judge: claude-sonnet-5 (same family as the system -
disclosed), reference-guided against the bench author's reference answer plus gold clause
text fetched from the database. Rubric sha and batch ids are recorded in each judgments file.

## Run-to-run variance (free by-product)

Only 3 of 27 aggregate cells differ between runs; b2 (whose post-retrieval path is mostly
deterministic) reproduced exactly:

| metric | RUN 1 | RUN 2 |
|---|---|---|
| ours citation precision | 86% | 83% |
| ours abstain-on-unanswerable | 7/8 (88%) | 8/8 (100%) |
| ours-no-verify abstain-on-unanswerable | 0/8 | 1/8 (12%) |

Judge jitter, measured by fully re-judging b2: 1 grade flip in 29 both-parsed items
(test-007, partial -> correct). Canonical protocol: first pass is canonical; parse failures
are filled by one direct retry (test-040's judge spent its whole token budget thinking -
fixed by raising max_tokens to 1500).

## Infrastructure post-mortem (for the build log)

Attempt 1 died overnight: machine sleep killed the detached run. Attempt 2 burned 40 classify
calls producing 40/40 retrieval errors: the host had rebooted and the database container was
not running. Lessons applied: keep-awake held for the run, logs on a persistent path, and a
database ping belongs before any run that pays per item.

## Human spot check

Three seeded samples (10 items per config, seed 42) exported as *_spotcheck.md. The author
fills a human verdict per item; the agreement rate is reported wherever these numbers are
used. Until that column is filled, correctness numbers above are LLM-judged only.
