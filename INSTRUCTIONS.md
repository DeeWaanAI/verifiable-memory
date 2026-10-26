# Layer 4 — Memory & Continuity · INSTRUCTIONS

**Paper working title:** *Verifiable Memory: Sessions, Preferences, and History as Provenance-Carrying Records for AI Agents*

## Mission

Give the OS a memory that never silently rewrites the past: sessions, user
preferences, and history stored as Qafiya datasets — append-only, versioned,
queryable, and auditable. The agent remembers; the user can inspect and correct what
it remembers, and every correction is itself a bound record.

## What to build (in order)

1. **Design brief** — memory schemas (session log, preference store, long-term
   notes), retention/consent rules, and the correction protocol. Mini-review of agent
   memory literature required (memory-augmented agents, e.g. MemGPT line; run a small
   verified search in the Qafiya review's style). Stop for owner confirmation.
2. **Prototype** — memory as Qafiya datasets; agents read/write through bindings;
   user-facing "what do you remember about me" view (through Layer 2's spec).
3. **Experiments (frozen):**
   - Correction integrity: user edits a memory; all dependent later outputs must
     re-flag (transitive invalidation in the memory setting).
   - Forgetting/consent: deleted memories provably absent from later prompts.
   - Cost: selective memory loading vs full-history prompting (token evidence,
     same protocol as the Qafiya efficiency experiment).

## Contracts you build on

- Qafiya spec v1.1. - Layer 2 spec for the memory-inspection view (mock until frozen).

## Deliverables

`brief.md` → `spec.md` → prototype → frozen experiments → paper draft (.tex).

## Out of scope

Actions on the outside world (Layer 3), model routing (Layer 5).
