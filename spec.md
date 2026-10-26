# Layer 4 — Verifiable Memory · Formal Specification

**Version:** 1.0 — **FROZEN 2026-10-26** (monitor-verified conformance 2026-10-20: 12/12 functional tests, spine OK; audit revision items 1–7 landed 2026-10-26: dvr/1.0 conformance F13, fair cost baseline, paraphrase probe, immutable limit snapshots) · **Product:** DeeWaanAI OS, Layer 4 (Memory & Continuity)
**Builds on:** Qafiya spec v1.1 (frozen) — all entities below ARE Qafiya datasets and obey its storage layout, binding primitive, two-layer check, and invariants. This spec adds only what memory requires.
**Normative language:** MUST / SHOULD / MAY as in RFC 2119.
**Paper:** *Verifiable Memory: Sessions, Preferences, and History as Provenance-Carrying Records for AI Agents*

## 0. Thesis

> *A memory is not a fact the model recalls — it is a record with provenance, a version chain, and a correction/deletion protocol, and the protocol is part of the data model.*

Memory lives in **records, not weights** (motivation: litreview §3.3 — weight-space edits do not propagate). Everything the agent remembers is a Qafiya record: append-only, versioned, queryable, auditable. Corrections never mutate history; they append superseding records and trigger Qafiya §6 transitive invalidation. Deletions leave payload-free tombstones plus an exact-string absence record (§5.2).

## 1. Datasets

Five datasets under `datasets/`, each with `schema.json`, `data.jsonl`, `history.jsonl`, `bindings.jsonl`, `SUPERSEDED.json` per Qafiya §8.

### 1.1 Memory base fields (all five datasets)

| Field | Type | Rule |
|---|---|---|
| `id` | id (`m_*`) | immutable, ULID (Qafiya §1.1; R3 id hygiene applies) |
| `created_at` | timestamp | set once, never edited |
| `source_ref` | list<id> | provenance: the session-log record(s) or user action that produced this record; MUST be non-empty except for system records |
| `valid_from` | timestamp | when the record became active |
| `superseded_by` | id \| null | points to the successor version; null while active |
| `status` | enum[active, corrected, deleted, stale] | read-path filter (§3) |

### 1.2 `ds:session_log` — the raw past

One record per conversation turn. **Append-only in the strong sense: no record in this dataset is ever modified or removed, even by deletion requests (see §5.3 for the deletion carve-out and its honesty note).**

| Field | Type | Rule |
|---|---|---|
| `session_id` | id (`s_*`) | groups turns |
| `turn_index` | number | monotonic within session |
| `role` | enum[user, agent, system] | |
| `content` | string | the utterance |
| `tokens_in` / `tokens_out` | number | for the cost experiment |
| `model_id` | string | the claim tuple's `device` analogue (Qafiya §2) |

Derivations (closed set): `filter`, `count`, `groupby`, `sum(tokens_in|tokens_out)`.

### 1.3 `ds:preference_store` — what the agent believes about the user

| Field | Type | Rule |
|---|---|---|
| `subject` | string | normally `user` |
| `predicate` | string | e.g. `diet`, `timezone`, `preferred_units` |
| `value` | any JSON | the believed fact |
| `confidence` | number [0,1] | extraction confidence |
| `extraction_method` | enum[user-stated, inferred] | `user-stated` MUST outrank `inferred` on conflict (§4.2) |

Derivations: `filter`, `count`, `groupby`, `latest(valid_from)`. A correction MUST NOT edit a record; it appends a successor whose `superseded_by` chain links back (Qafiya §7 invariant 8).

### 1.4 `ds:longterm_notes` — consolidated knowledge

Summaries/reflective notes derived from sessions (the Generative-Agents "reflection" pattern, made auditable).

| Field | Type | Rule |
|---|---|---|
| `note` | string | the consolidated content |
| `derived_from` | list<id> | MUST be non-empty; the closure that makes transitive invalidation computable |
| `note_kind` | enum[summary, reflection, fact-cluster] | |

Derivations: `filter`, `count`. Because every note names its sources, the `derived_from` closure of any memory record is enumerable — this is what weight-space editing cannot do (litreview §3.3).

### 1.5 `ds:correction_log` — corrections as first-class records

| Field | Type | Rule |
|---|---|---|
| `target_id` | id (`m_*`) | the memory record corrected; MUST exist |
| `old_value` | any JSON | copied from target at correction time |
| `new_value` | any JSON | the corrected value |
| `user_statement` | string | the user's own words (verbatim, R1 anchoring) |
| `applied_at` | timestamp | |

A correction is a **bound record**: it points at its target and is itself provenance-carrying. Applying it MUST (a) set `target.status = corrected`, (b) append the successor record in the target's dataset, (c) emit Qafiya §6 transitive invalidation over the target's `derived_from` reverse-closure (every dependent note/output → `stale`, and dependent Qafiya bindings → `PENDING`).

### 1.6 `ds:deletion_log` — consent events

| Field | Type | Rule |
|---|---|---|
| `target_id` | id (`m_*`) | the record deleted |
| `scope` | enum[single, cascade] | cascade = target + full `derived_from`/`source_ref` closure |
| `reason` | string \| null | user-given, optional |
| `proof` | object | hash-chain entry over store state before/after + the exact-string absence scan result (§5.2) |

The deleted record's payload is removed from the read path and the record replaced by a **tombstone** (`status = deleted`, payload fields nulled, id and `created_at` retained). The tombstone carries no content, so absence is auditable without retaining the data.

## 2. Hash-chain integrity

Chained history is **inherited from the Qafiya substrate (v1.3)**: every `history.jsonl` entry carries `prev_hash` and `entry_hash` per the substrate's canonical-JSON construction; verification is `qafiya_core.chain.verify` — this layer defines no chain mechanism of its own. Any offline modification of a historical record without chain recomputation MUST be detected by the audit (test F3/L8). The uncatchable class — attacker rewrites the store AND recomputes the chain — is a substrate-level limit (Qafiya v1.3 §5, limit 5; this layer's formulation was adopted there verbatim-compatible), with external anchoring noted as future work.

## 3. Read-path invariant (the core guarantee)

Agents MUST read memory only through the memory binding, which:

1. filters `status = active` and resolves `superseded_by` chains to the newest version;
2. never emits tombstoned payload;
3. serializes the selected memory into prompt context in a **deterministic, diffable form** (sorted by `id`), so the exact-string absence scan (§5.2) is a byte-level check;
4. logs every emitted context as a Qafiya record (which memory ids went into which prompt), making "what did the agent know when it said X" queryable.

Direct writes to datasets bypassing the binding MUST be rejected (F12).

## 4. Protocols

### 4.1 Remember
- Session turns append to `ds:session_log` (role, content, tokens).
- Extraction appends to `ds:preference_store` with `extraction_method` and `source_ref` pointing at the exact turn(s).
- Consolidation appends to `ds:longterm_notes` with `derived_from` non-empty.

### 4.2 Conflict
On predicate conflict, `user-stated` beats `inferred`; otherwise the newest `valid_from` wins; losers are NOT deleted — they remain queryable history. The user MAY disable inferred writes globally or per-predicate (`consent.inferred_writes`); disabled classes are rejected at write time (F8).

### 4.3 Correct
Per §1.5: correction record → target superseded → successor appended → transitive invalidation over the dependent closure → corrected content leaves the read path **immediately**, before dependents are regenerated (F5–F7).

### 4.4 Delete
Per §1.6: tombstone + cascade option + exact-string absence scan (§5.2) stored in the deletion record's `proof` (F9–F10). **Deletion ALWAYS transitively invalidates dependents** (scope `single`: dependent notes → `stale`, leaving the read path; scope `cascade`: dependents tombstoned). Without this, a note derived from a deleted record keeps serving its payload — caught by experiment 2's absence scan during development, and fixed in the protocol before freezing.

### 4.5 Inspect ("what do you remember about me")
Returns exactly the active memory set — grouped by dataset, each item with its `source_ref` — rendered through Layer 2's spec (mocked until Layer 2 freezes) (F4). No active memory item may be omitted; no inactive item may appear.

## 5. Verification

### 5.1 Mapping to the Qafiya two-layer check
- **Layer 1 (proof, deterministic):** hash-chain integrity; every `source_ref`/`derived_from`/`target_id` resolves; every `superseded_by` chain terminates at an active record; read-path serialization contains no `status ≠ active` payload; exact-string absence scan.
- **Layer 2 (flag, advisory):** staleness candidates (e.g. an `inferred` preference contradicted by a newer `user-stated` one but not yet corrected); consolidation drift (a note whose `derived_from` sources no longer support its text — flagged, never auto-passed, R6).

### 5.2 Exact-string absence on the read path (after deletion)
The mechanism is **exact-string absence on the read path** — named precisely because a paraphrase or derived summary with a provenance gap can carry deleted content while the scan passes (demonstrated by experiment 2's paraphrase probe; mitigation: complete `derived_from` provenance + semantic-similarity scanning, future work). A verification pass MUST scan the **read path** — (a) the active records of the datasets that feed prompts (`preference_store`, `longterm_notes`) and (b) the serialized prompt context the binding would emit — and assert the deleted payload's canonical string appears in neither. Result (PASS/FAIL + scanned artifact hashes) is stored in the deletion record's `proof`. Scan coverage MUST be reported (Qafiya §4 analogue): which stores and which prompt sections were scanned. Raw `session_log` turns and append-only log payloads (e.g. `correction_log.old_value`) are history, outside the read-path guarantee; that boundary is measured and reported (limit test L5), never hidden.

### 5.3 Honesty boundary (stated in the paper)
The protocol governs the **record substrate only**. It cannot retract content absorbed into model weights, cannot detect facts that went stale with no signal, cannot bind corrections the user cannot localize, and cannot survive chain-recomputing tampering (brief §7; tests L3, L5, L6, L8 document the boundaries). `ds:session_log` deletion removes the turn's `content` from the read path and future contexts; the historical log entry remains as a tombstone — the paper reports this design choice and its implications plainly.

## 6. Well-formedness invariants (testable)

1. Every memory record carries the §1.1 base fields; `source_ref` non-empty (except system records).
2. Every `longterm_notes.derived_from` is non-empty and resolves.
3. Every `superseded_by` chain is acyclic and terminates at exactly one `active` record.
4. `user-stated` outranks `inferred` on predicate conflict.
5. Read-path output contains no `corrected`/`deleted` payload (byte-level).
6. Every correction's `target_id` exists; applying it flags the full dependent closure `stale`.
7. Every deletion leaves a payload-free tombstone and a `proof` with a PASS scan.
8. Append-only: `history.jsonl` hash-chain verifies at all times.
9. All reads/writes pass through the binding; direct dataset writes rejected.
10. Every emitted prompt context is logged with the memory ids it contained.

Each maps to a functional test (F1–F12) and a paper claim.

## 7. Storage layout

```
datasets/session_log/       schema.json data.jsonl history.jsonl bindings.jsonl SUPERSEDED.json
datasets/preference_store/  …
datasets/longterm_notes/    …
datasets/correction_log/    …
datasets/deletion_log/      …
memory/binding.py           # the only read/write path (§3)
memory/inspect.json         # view spec for §4.5 (Layer 2 mock until frozen)
```

## 8. Non-goals

Not model editing/unlearning in weights (litreview §3.3–3.4 — different problem). Not a general knowledge graph (Zep [5] comparison in the paper). Not action execution (Layer 3) or model routing (Layer 5). Not a retention/expiry policy engine in v1 (default: keep until the user acts).

---
*Companion artifacts: design brief (`brief.md`), systematic review (`litreview/review.md`). On freeze, this spec becomes the contract Layers 5–6 code against.*
