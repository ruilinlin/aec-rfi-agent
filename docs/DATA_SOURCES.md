# Data sources

Raw documents are **not committed** (size and licensing). `data/MANIFEST.json` records exactly what was used so anyone can re-download it.

## Primary corpus: UFGS (Unified Facilities Guide Specifications)

- Where: https://www.wbdg.org/dod/ufgs — per-section PDFs, organized by MasterFormat number.
- Why: public, MasterFormat-structured, released quarterly (Feb / May / Aug / Nov) with a published revision history per section.
- Revision pairs: download the same section from two consecutive releases (keep the older one from an archive or from a download made before the next release). Each pair whose text changed becomes a source of revision-subset RFIs.
- Starting set (MVP): ~10–15 sections from a building-relevant mix, e.g.
  - Division 03 concrete, Division 07 roofing / waterproofing, Division 08 doors and windows, Division 09 painting / finishes, Division 22 plumbing, Division 26 interior lighting.
- Record in the manifest: section number, title, release label (e.g. "UFGS 2026-08"), download date, URL, sha256.

## Secondary corpus: BC Bid public tenders (local, real projects)

- Where: https://www.bcbid.gov.bc.ca and municipal tender pages (e.g. City of Surrey, Capital Regional District).
- What: contract drawings, specifications, and numbered **addenda** — addenda often re-issue revised drawings and blacklined specs and answer bidder questions.
- Use: a realistic revision chain (original → Addendum 1 → Addendum 2) and bidder Q&A to inspire realistic RFI wording.
- Check each tender's terms before redistributing anything; by default keep these local-only and list them in the manifest by URL.

## Optional secondary test set

- UCLouvain / Buildwise anonymized construction meeting minutes (60 PDFs, French) and expert queries: https://github.com/ikostis-ucl/bpc_meeting_assistant

## RFIs

Synthetic, written by the author in realistic RFI format, annotated per `docs/ANNOTATION_GUIDE.md`. Released under CC BY 4.0.
