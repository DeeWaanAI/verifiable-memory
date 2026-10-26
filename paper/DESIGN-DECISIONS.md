# Layer 4 — Design decision log (append-only)

- **D1 (2026-10-19)** — Memory lives in records, not weights. Rationale: editing
  literature (ROME/MEMIT ripple effects, catastrophic forgetting at scale) shows
  weight-space corrections do not propagate. Grounding: litreview §3.3.
  Implemented in: spec.md §0, all datasets.
- **D2 (2026-10-19)** — Proof of absence covers the READ PATH only (active
  preference/notes records + serialized prompt context). Append-only history and
  raw session turns retain payloads by design; the guarantee is "absent from later
  prompts". Grounding: Qafiya append-only discipline; measured in L5.
- **D3 (2026-10-19)** — Deletion always transitively invalidates dependents
  (single → stale; cascade → tombstone). Trigger: exp2 proof-of-absence FAILED on
  the first run — a derived note kept serving the deleted payload. Protocol amended
  in spec.md §4.4 before freezing; the episode is disclosed in paper §3.4 and §5.3.
- **D4 (2026-10-19)** — Batched rewrite for invalidation (single O(n) pass).
  Trigger: L7 measured 1.2s (per-flag rewrites, O(n²)); after fix 0.034s. Both
  numbers persisted in limit_results.json and reported in the paper.
- **D5 (2026-10-19)** — Token accounting is deterministic (regex tokenizer),
  backend-agnostic, mirroring the Qafiya efficiency protocol; comparisons count
  only at matched answer capability (both contexts must contain the required fact).
- **D6 (2026-10-20)** — Claim-to-evidence enforcement: datapoints.json (43 DPs),
  paper-claims.json (18 mentions), semantic-claims.json (11 claims, 3 captions),
  two-way verifier must exit 0 before any draft ships. Semantic sweep of v1.0 →
  v1.1 fixed 5 discrepancies (stale L7/L1 timings, 'verbatim' overreach, ratio
  cherry-pick, line-count drift); logged in semantic-claims.json discrepancy_log.
- **D7 (2026-10-20)** — Draft versioning: v1.0 superseded by v1.1 (data
  corrections). v1.0 kept for the audit trail.
- **D8 (2026-10-20)** — Hash-chained history adopted from the Qafiya substrate
  (v1.3, qafiya_core.chain vendored); local chain implementation deleted per
  MONITOR-GUIDE item 1. The adoption surfaced two integration bugs (hash body
  including prev_hash; L8 attacker using wrong semantics) — both caught by F3/L8
  and the spine before shipping. The honesty boundary (chain-recomputing attacker)
  now lives in the substrate spec, verbatim-compatible.
- **D9 (2026-10-20)** — Volatile wall-clock timings are quoted in the paper as
  magnitudes ("on the order of a second"); exact decimals live in the frozen
  artifacts only. Rationale: re-runs drift at the second decimal; the claim map
  checks quote presence for these, value equality for everything else.
- **D10 (2026-10-20)** — MONITOR-GUIDE item 2 (Layer-2 mock → real) NOT done:
  dvr/1.0 is "frozen-in-practice" but not confirmed frozen in INTERFACES.md;
  gate stays closed until the L2 agent confirms. F4 tests view content, not the
  renderer, so no experiment reruns will be needed.
- **D11 (2026-10-26)** — External audit (DeeWaanAI-OS-audit-2026-10-26) items 1–7 implemented; spec v1.0 FROZEN; exp3 v2 with RAG top-8 baseline + accuracy gates; mechanism renamed "exact-string absence on the read path"; limit harness writes timestamped runs, frozen snapshot promoted only via --freeze (FREEZE-LOG.md).
- **D12 (2026-10-26)** — Publication-gate maps rebuilt per monitor tasking: datapoints.json (30 entries, {id,claim,source,path,expect} + marker), verify_two_way.py (exit 0 both directions), semantic-claims.json (28 claims full-sweep + 6 captions + 10-entry discrepancy log). Sweep caught: 'Four limits' vs five enumerated (fixed), stale self-referential map counts in the disclosure (fixed).
