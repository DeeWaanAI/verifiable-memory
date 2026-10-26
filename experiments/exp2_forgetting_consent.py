#!/usr/bin/env python3
"""Experiment 2 — Forgetting/consent (frozen).
Scenario: user deletes a personal memory (single), then a cascade delete.
Headline numbers: proof-of-absence result on the read path; leakage map
showing exactly where the payload persists (history, raw turns) — reported,
never hidden. Freezes raw artifacts into experiments/exp2/."""
import sys, json, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "prototype"))
from memory import Store

OUT = Path(__file__).parent / "exp2"
if OUT.exists(): shutil.rmtree(OUT)
store_root = OUT / "store"
s = Store(store_root)

t1 = s.log_turn("s1", 1, "user", "my doctor is Dr. A and I live in Paris.", 11, 0, "exp-agent")
p_doc = s.add_preference("doctor", "Dr. A", [t1], "user-stated")
p_city = s.add_preference("city", "Paris", [t1], "user-stated")
n1 = s.add_note("User's doctor is Dr. A.", [p_doc])
n2 = s.add_note("User lives in Paris.", [p_city])
# paraphrase probe (2026-10-26 audit, item 2): a note that carries the same
# content WITHOUT the exact string, and whose provenance points at the raw turn
# (not the preference) — the adversarial corner for an exact-string scan.
n_para = s.add_note("The user's physician is Doctor A.", [t1])

# single deletion
res1 = s.delete(p_doc, "single", "user request")
# cascade deletion
res2 = s.delete(p_city, "cascade", "user request")

# paraphrase probe outcome
para = [r for r in s._records("longterm_notes", tombstones=True) if r["id"] == n_para][0]
paraphrase_probe = {
  "note_status_after_delete": para["status"],
  "exact_string_scan_result": res1["proof"]["absence_scan"]["result"],
  "carries_deleted_content_semantically": True,
  "boundary": "the mechanism is EXACT-STRING absence on the read path; a paraphrase "
              "or derived summary with a provenance gap can carry the deleted content "
              "while the scan passes. Mitigation = complete provenance (derived_from "
              "non-empty and honored) + semantic-similarity scan (future work)."}

def leakage(payload):
    m = {}
    for ds in ("preference_store", "longterm_notes", "session_log"):
        for f in ("data.jsonl", "history.jsonl"):
            p = store_root / "datasets" / ds / f
            m[f"{ds}/{f}"] = payload in p.read_text()
    m["prompt_context"] = payload in s.serialize_context()
    return m

headline = {
  "single_delete_absence_scan": res1["proof"]["absence_scan"]["result"],
  "cascade_delete_absence_scan": res2["proof"]["absence_scan"]["result"],
  "cascade_removed": res2["removed"],
  "dr_A_leakage": leakage("Dr. A"),
  "paris_leakage": leakage("Paris"),
  "read_path_clean": ("Dr. A" not in s.serialize_context() and "Paris" not in s.serialize_context()),
  "paraphrase_probe": paraphrase_probe,
}
result = {"experiment": "exp2_forgetting_consent", "frozen": "2026-10-19",
          "headline": headline,
          "note": "leakage=true in history/raw-turn files is EXPECTED and reported: "
                  "the guarantee is absence from later prompts (read path), not erasure from "
                  "append-only history (spec §5.3; limit test L5).",
          "proofs": {"single": res1["proof"], "cascade": res2["proof"]}}
(OUT / "result.json").write_text(json.dumps(result, indent=1))
print(json.dumps(headline, indent=1))
