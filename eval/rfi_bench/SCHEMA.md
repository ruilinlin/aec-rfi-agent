# RFI-Bench item schema (JSONL, one item per line)

```json
{
  "id": "dev-001",
  "rfi_type": "clarification | conflict | superseded_ref | substitution | unanswerable",
  "question": "RFI text as a contractor would write it",
  "references_in_question": ["09 91 00"],
  "answerable": true,
  "gold_citations": [
    {"section_code": "09 91 00", "section_path": "PART 2 > 2.3 > A", "revision": "UFGS-2026-08"}
  ],
  "superseded_citations": [],
  "reference_answer": "1-3 sentences stating the governing requirement, with citation.",
  "notes": "optional annotator notes"
}
```

Rules: see `docs/ANNOTATION_GUIDE.md`. `test.jsonl` is frozen once written.
