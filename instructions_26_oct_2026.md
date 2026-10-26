# Layer 4 (Verifiable Memory) — Revision instructions · 26 Oct 2026

**Source:** external audit (DeeWaanAI-OS-audit-2026-10-26.md). One real experiment addition, one integration fix, one harness fix.

1. **Cost claim needs a fair baseline.** Exp3 compares selective loading only against full-history prompting. Either **add a RAG/top-k retrieval baseline and an answer-accuracy score** (both, ideally small and frozen), or scope the claim explicitly: "versus full-history prompting" everywhere it appears, including the conclusion's "50–1000× fewer tokens". Do not keep an unscoped 98–99.9% headline.
2. **Proof of absence is exact-string.** A paraphrase or derived summary can carry the deleted content while the scan passes. Add a short paraphrase probe and state the boundary, or rename the mechanism "exact-string absence on the read path" wherever it is claimed.
3. **Inspection view must be a real `dvr/1.0` spec.** `memory.py::inspect()` currently returns a custom dict with no `spec`, nodes, or binding refs — Layer 2's validator would reject it. Emit a real dvr/1.0 view (frozen, declared 2026-10-20) and add a conformance test against the Layer 2 validator. This is a required L6 integration item.
4. **Frozen-artifact immutability.** `test_limits.py` rewrites `limit_results.json` and `LIMITS.md` in place, and the claim map pins exact timings that a rerun breaks (the external auditor hit this and restored the files). Fix structurally: runs write a **timestamped run directory**; the frozen snapshot stays immutable; the claim map checks ranges/magnitudes for wall-clock claims, not decimals.
5. **Scope disclosure.** The brief promised 100k-record scale tests; the paper reports 10k. Disclose the reduction or run the 100k case.
6. **Spec freeze (administrative).** Header says "1.0 (draft for freezing)"; the monitor verified conformance on 2026-10-20 (12/12 tests, spine OK). Change to **v1.0 FROZEN (date)** after items 3–4 land, and log it. The monitor updates INTERFACES.md.
7. **Usability.** No inspection-view user study — fine for a systems paper, but do not make any HCI/usability claim; one future-work sentence (field feedback after deployment).

## Acceptance

Cost claim scoped or re-baselined; absence mechanism correctly named; inspection view passes a dvr/1.0 conformance test; limit harness no longer overwrites frozen artifacts; spec frozen; claim map and tests pass; .tex compiles clean.
