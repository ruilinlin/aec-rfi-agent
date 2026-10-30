# RFI-Bench annotation guide (v0.1)

## Writing an RFI

- Write it the way a contractor would: who is asking, what they see on site or in the documents, what is unclear, what they need decided.
- It must be **self-contained in text**. Do not rely on an attached markup the system cannot see.
- Do not paste the answer's wording into the question. Paraphrase the way a field engineer would.
- 1–4 sentences.

## RFI types (`rfi_type`)

| Type | Meaning | Example cue |
|---|---|---|
| `clarification` | Documents answer it, but it takes finding the right place | "What primer is required under the finish coat in corridors?" |
| `conflict` | Two documents disagree; the answer must name the governing one | "Drawing says X, spec says Y — which governs?" |
| `superseded_ref` | The question cites an older revision; the answer depends on the current one | "Per Rev 1 of 09 91 00 we planned …" |
| `substitution` | Contractor proposes an alternative product or method | "Can we use product B instead of A?" |
| `unanswerable` | The corpus does not contain a governing requirement | Anything the documents are silent on |

Target mix for v0.1 (~60 items): clarification 35%, conflict 15%, superseded_ref 20%, substitution 10%, unanswerable 20%.

## Gold labels

- `gold_citations`: the minimum set of `{section_code, section_path, revision}` that governs the answer. For drawings, `{sheet, revision}`.
- `reference_answer`: 1–3 sentences, stating the requirement and citing it.
- `answerable`: false only for `unanswerable` items; then `gold_citations` is empty and `reference_answer` describes what is missing.
- `superseded_citations` (revision items only): the outdated reference a stale system would wrongly use.

## Splits

- `dev.jsonl`: ~20 items, used freely while building.
- `test.jsonl`: ~40+ items, written **before** tuning on them and then frozen. Report results only on test.

## Quality

- After writing, re-check each gold citation against the source PDF.
- If possible, have one AEC practitioner independently answer 20 items; report agreement.
