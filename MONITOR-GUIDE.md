# Integration guide — Layer 4 (memory)

**From:** monitor · **Date:** 2026-10-20 · **Your layer is already the most conformant; two small items.**

## 1. Hash chain → consume Qafiya v1.3 (when owner confirms)

Your §2 chained `history.jsonl` and the monitor's substrate-level `chain.py` are the
same mechanism. Once Qafiya v1.3 lands, delete your local implementation and call
`qafiya_core.chain`. Keep everything memory-specific: tombstones, proof-of-absence,
read-path binding — those are your contribution and stay.
Paper edit: §2 becomes "inherits the substrate's chained history (Qafiya v1.3)";
your honesty boundary text (chain-recomputing attacker) should also appear in the
substrate spec — the monitor's spec delta already includes it, verbatim-compatible.

## 2. Layer-2 mock → real

Your §4.5 "what do you remember about me" view renders through Layer 2's spec
(currently mocked). When dvr/1.0 is confirmed frozen in INTERFACES.md, rewire
`memory/inspect.json` to the real renderer. No experiment reruns needed — the F4
test asserts the view's *content*, not its renderer.

## Already conformant (verified 2026-10-20)

- Qafiya §8 dataset layout in experiment stores (schema/data/history/bindings/SUPERSEDED) ✓
- Prefixed ids (`m_*`, `s_*`) ✓
- Frozen experiments + spine discipline ✓
