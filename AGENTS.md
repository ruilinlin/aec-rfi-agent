# Instructions for coding agents

Read `DESIGN.md` and `docs/RESEARCH.md` before changing code.

## Hard rules

1. **Never read, tune against, or edit `eval/rfi_bench/test.jsonl`** unless the human explicitly asks to run the final evaluation. Develop on `dev.jsonl` only.
2. **Never commit** `.env`, API keys, or raw documents under `data/specs|drawings|submittals`. Commit `data/MANIFEST.json` instead.
3. Revision governance and citation checking are **deterministic code**, not prompt instructions. Do not "fix" them by adding prompt text like "use the latest revision".
4. Every eval run must write `eval/results/<timestamp>_<config>.json` containing git SHA, model ids, temperature, manifest version, and per-item outputs.
5. The agent must never return an answer without at least one citation. No supporting evidence → `GapReport`.

## Conventions

- Python 3.11, type hints, Pydantic v2 models in `src/schemas.py`.
- Tests in `tests/`, run with `pytest`. Lint with `ruff`.
- Small PRs; one build-order step (DESIGN.md §9) per PR.
- When a notable failure shows up, add a line to `eval/results/failures.md`.
