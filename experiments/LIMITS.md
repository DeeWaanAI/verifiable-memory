# Layer 4 — Limit test report (L1–L8)

Findings map where the design breaks. Reported as results, never hidden.

## L1_scale
measured: conflict resolution and full-context serialization stay fast to 10k records (0.03s/0.04s) — read-path latency is NOT the binding constraint at personal scale. The binding constraint is PROMPT TOKENS, not lookup time (measured in the cost experiment): serializing 100k memories is cheap in ms and unaffordable in tokens

```json
{
 "measurements": {
  "1000": {
   "resolve_conflicts_s": 0.003,
   "serialize_context_s": 0.005
  },
  "10000": {
   "resolve_conflicts_s": 0.033,
   "serialize_context_s": 0.045
  },
  "100000": {
   "resolve_conflicts_s": 0.538,
   "serialize_context_s": 0.691
  }
 }
}
```

## L2_contradictions
contradictory inferred memories are silently RANKED, not detected: newest/highest-confidence wins with no flag to the user. Contradiction detection needs a Layer-2 advisory flag — noted as future work

```json
{
 "resolved_to": {
  "beverage": [
   "milk",
   "inferred"
  ]
 }
}
```

## L3_implicit_staleness
PROVABLE LIMITATION confirmed: a fact that goes stale with no signal remains active indefinitely. The layer cannot detect implicit staleness; it can only make staleness correctable when a signal arrives

```json
{
 "employer_still_active_after_silence": [
  "Acme"
 ]
}
```

## L4_poisoning
injected content is quarantined by TAGGING (inferred + low confidence + source-traceable to the exact turn), but NOT by default blocked: the store accepts any inferred write. Defense-in-depth (blocklist predicates, e.g. credentials) is a policy the spec leaves to deployments — reported as an open hardening item

```json
{
 "tagged": {
  "extraction_method": "inferred",
  "confidence": 0.4,
  "source_ref": [
   "m_1793007380234200029"
  ]
 }
}
```

## L5_leakage
read path is clean (proof-of-absence PASS) but payload persists in append-only history.jsonl and in the raw session turn. Boundary CONFIRMED: the guarantee is 'absent from later prompts', not 'erased from history'. Full erasure requires cascading into session_log tombstones — spec §5.3 carve-out, paper reports this plainly

```json
{
 "proof_of_absence": "PASS",
 "leakage_map": {
  "preference_store/data.jsonl": false,
  "preference_store/history.jsonl": true,
  "session_log/data.jsonl (raw turn)": true,
  "prompt_context (read path)": false
 }
}
```

## L6_ambiguous_correction
the protocol REQUIRES a resolvable target_id; a vague correction ('that's not what I meant') cannot be bound without an agent-side resolution step. The unbindable class exists and is reported; resolution heuristics are agent work (Layer 5+), not memory-layer guarantees

```json
{
 "unbindable_corrections_rejected": 1
}
```

## L7_invalidation_cost
a 300-deep dependent chain re-flags in 1.351s with per-flag full-file rewrites (O(depth^2)) — above an interactive budget; the shipped batched rewrite (single O(n) pass) does it in 0.034s. Both numbers are persisted and reported

```json
{
 "chain_depth": 300,
 "flagged": 300,
 "reflag_seconds": 0.034,
 "reflag_seconds_before_fix": 1.351
}
```

## L8_tamper
naive tampering is ALWAYS caught (hash chain). Tampering WITH chain recomputation is NEVER caught — the uncatchable class, mirroring Qafiya's provable limits. Mitigation (external hash anchoring) is future work, stated in the paper

```json
{
 "naive_tamper_caught": true,
 "recomputed_chain_caught": false
}
```
