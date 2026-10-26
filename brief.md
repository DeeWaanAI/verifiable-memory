# Layer 4 — Memory & Continuity · DESIGN BRIEF

**Status: DRAFT — awaiting owner confirmation. No code will be written before go.**
Paper working title: *Verifiable Memory: Sessions, Preferences, and History as Provenance-Carrying Records for AI Agents*
Builds on: Qafiya spec v1.1 (frozen). Layer 2 spec for the inspection view (mocked until frozen).
Prior art: `litreview/review.md` (37 verified works, gap stated there).

---

## 1. Mission and design stance

Give the OS a memory that never silently rewrites the past. The agent remembers; the
user can inspect and correct what it remembers; every correction is itself a bound
record; every deletion is provable.

Three design stances, each taken directly from the literature review:

1. **Memory lives in records, not weights.** The editing literature (ROME/MEMIT line)
   shows corrections inside a model do not propagate and degrade at scale. All memory
   this layer controls is therefore stored as explicit Qafiya datasets where
   dependents are enumerable and re-flaggable.
2. **Correction and consent are data-model properties, not policies.** Provenance,
   versioning, and correction-event fields are first-class fields of every memory
   record — not annotations added later.
3. **Honesty as architecture.** The layer states provably what it cannot do (§7) and
   measures the boundary where possible (§6, limit tests).

Out of scope (per instructions): actions on the outside world (Layer 3), model
routing (Layer 5). The layer reads/writes memory; it does not decide what the model
does with it.

## 2. Schemas (all as Qafiya datasets, append-only)

Every record in every dataset carries the Qafiya base fields plus:
`memory_id`, `created_at`, `source_ref` (provenance pointer to the session-log record
or user action that produced it), `valid_from` / `superseded_by` (versioning),
`status` (`active | corrected | deleted`).

### 2.1 `session_log` — the raw past
One record per conversation turn: `session_id`, `turn_index`, `role`, `content`,
`tokens_in/out`, `model_id`. Append-only; never edited. Corrections and deletions are
expressed by *later* records, never by rewriting this log.

### 2.2 `preference_store` — what the agent believes about the user
One record per preference/fact: `subject`, `predicate`, `value`, `confidence`,
`extraction_method` (`user-stated | inferred`), plus base fields. A correction does
not mutate the record; it appends a new record whose `superseded_by` chain points
back. `user-stated` always outranks `inferred`.

### 2.3 `longterm_notes` — consolidated knowledge
Summaries/reflective notes derived from sessions. Each note carries `derived_from`
(list of `source_ref`s). This is the dataset that makes transitive invalidation
possible — and testable.

### 2.4 `correction_log` — corrections as first-class records
One record per user correction: `target_id` (the memory corrected), `old_value`,
`new_value`, `user_statement`, `applied_at`. A correction is a *bound record*: it
points at its target and is itself provenance-carrying.

### 2.5 `deletion_log` — consent events
One record per deletion: `target_id`, `scope` (`single | cascade`), `reason`
(optional, user-given), `proof` (hash-chain entry over the store state before/after).
Deletion removes content from the read path; the deletion *event* remains as a
tombstone with no payload, so absence is auditable without retaining the data.

### 2.6 Read-path invariant
Agents read memory only through bindings that filter `status = active` and resolve
`superseded_by` chains. Deleted and corrected content never reaches a prompt.

## 3. Retention and consent rules

- **Default retention:** everything kept until the user acts; no silent expiry in v1.
- **Consent:** memory writes are tagged `user-stated` vs `inferred`; the user can
  disable inferred writes globally or per-predicate.
- **Deletion scopes:** `single` removes one record and tombstones it; `cascade`
  removes the record and every record whose `derived_from`/`source_ref` closure
  contains it.
- **Proof of absence:** after deletion, a verification pass scans (a) the active
  store, (b) the serialized prompt context the layer would emit, and asserts the
  deleted payload appears in neither. The scan result is stored as a bound record.

## 4. The correction protocol

1. User states a correction (or edits via the Layer 2 inspection view).
2. Layer appends a `correction_log` record; target record's `status → corrected`,
   a successor record carries the new value (`superseded_by` links them).
3. **Transitive invalidation:** walk the `derived_from` closure of the target;
   every dependent note/output is flagged `stale` and queued for regeneration.
4. The flag is a record too — so "what broke when I corrected this" is queryable.
5. Corrected content leaves the read path immediately (the invariant in §2.6),
   even before dependents are regenerated.

## 5. Prototype plan (after confirmation)

- Datasets as JSONL+schema per Qafiya v1.1; bindings for agent read/write.
- A reference agent loop that: writes session turns → extracts preferences →
  consolidates notes → answers with selective memory loading.
- User-facing **"what do you remember about me"** view, rendered through Layer 2's
  spec (mocked until Layer 2 freezes).
- A spine script that recomputes every headline number from raw artifacts.

## 6. Test plan

Two suites. **Functional tests** prove the design works. **Limit tests** map where
it breaks — reported as results, never hidden.

### 6.1 Functional tests (must all pass before experiments freeze)

| # | Test | Pass criterion |
|---|---|---|
| F1 | Write & read-back | session turns, preferences, notes round-trip with all provenance fields intact |
| F2 | Schema validation | every dataset validates against its frozen schema; malformed records rejected |
| F3 | Append-only integrity | hash-chain over each dataset; any tamper detected |
| F4 | Inspect view | "what do you remember about me" returns exactly the active memory set, grouped by schema, each item with its `source_ref` |
| F5 | Correction basic | correct one preference → old value leaves read path, successor active, correction record bound to target |
| F6 | Transitive invalidation | correct a preference with 3 dependent notes → all 3 flagged stale; flag records queryable |
| F7 | Correction chain | correct the same fact twice → chain of 3 versions, only newest active, full history intact |
| F8 | Inferred vs stated | `user-stated` beats `inferred` on conflict; disabling inferred writes stops inferred records |
| F9 | Deletion single | delete one record → absent from store scan AND from serialized prompt context; tombstone present without payload |
| F10 | Deletion cascade | delete with cascade → full `derived_from` closure absent; proof-of-absence record stored |
| F11 | Session continuity | new session loads relevant memory only; agent answers a question requiring last week's preference |
| F12 | Interface contract | all reads/writes go through bindings; direct dataset writes are rejected |

### 6.2 Limit tests (find and report the breaking points)

| # | Test | What it measures |
|---|---|---|
| L1 | Scale | store 10k / 100k memory records; measure lookup and invalidation-walk latency; report where the walk exceeds an interactive budget |
| L2 | Contradiction storms | inject N mutually contradictory statements without user correction; measure how retrieval ranks them and report failure modes |
| L3 | Stale-memory detection bound | change a fact *implicitly* (user stops mentioning it) — show the layer cannot detect this; stated as a provable limitation |
| L4 | Adversarial memory poisoning | a session injects a false "user preference"; measure whether provenance tagging (`inferred`, low-confidence, source-traceable) keeps it quarantined |
| L5 | Deletion leakage | after deletion, probe: consolidated notes written *before* deletion, model-side paraphrases, and prompt caches; report exactly where payload can still surface (expected: weights are out of reach — stated limit) |
| L6 | Correction ambiguity | user corrects vaguely ("that's not what I meant") — measure resolution success; report the class of corrections the protocol cannot bind to a target |
| L7 | Invalidation cost | one correction with a large dependent closure (e.g. 500 notes); measure re-flag latency and regeneration cost in tokens |
| L8 | Hash-chain audit | tamper with a historical record offline; verify the audit catches it; try tampering *with* chain recomputation (expected uncatchable class — reported honestly, mirroring Qafiya's 0%-recall classes) |

### 6.3 Frozen experiments (for the paper, per instructions)

1. **Correction integrity** — user edits a memory; all dependent later outputs
   re-flag. Headline: % of dependents correctly invalidated (target 100%,
   deviations reported).
2. **Forgetting/consent** — deleted memories provably absent from later prompts.
   Headline: proof-of-absence scan result + leakage probed per L5.
3. **Cost** — selective memory loading vs full-history prompting. Headline: token
   counts at matched answer quality, same protocol as the Qafiya efficiency
   experiment.

Every number in the paper traces to a frozen artifact via the spine script.

## 7. What this layer provably cannot do (draft honesty section)

- Cannot retract information already absorbed into model **weights** during
  training/fine-tuning — only from the record substrate (L5 documents the boundary).
- Cannot detect a fact that went stale **without any signal** (L3).
- Cannot bind a correction the user cannot localize to any record (L6).
- Cannot survive an attacker who can rewrite the store *and* recompute the chain
  (L8); mitigations (external anchoring) noted as future work.

## 8. Deliverable sequence after go

`spec.md` (frozen schemas) → prototype → functional suite F1–F12 green →
limit suite L1–L8 run and reported → three frozen experiments → paper draft (.tex).

---
**Awaiting owner confirmation. On go, I start with `spec.md`.**
