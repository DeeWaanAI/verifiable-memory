#!/usr/bin/env python3
"""Experiment 1 — Correction integrity (frozen).
Scenario: a preference with a dependent note closure; user corrects it.
Headline number: % of the dependent closure correctly re-flagged stale,
and whether the corrected value left the read path.
Freezes raw artifacts (full store snapshot + result) into experiments/exp1/."""
import sys, json, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "prototype"))
from memory import Store

OUT = Path(__file__).parent / "exp1"
if OUT.exists(): shutil.rmtree(OUT)
store_root = OUT / "store"
s = Store(store_root)

# --- scenario ---
t1 = s.log_turn("s1", 1, "user", "I live in Paris, I work remotely.", 9, 0, "exp-agent")
p_city = s.add_preference("city", "Paris", [t1], "user-stated")
p_work = s.add_preference("work_style", "remote", [t1], "user-stated")
n1 = s.add_note("User lives in Paris.", [p_city])
n2 = s.add_note("User is in CET timezone.", [n1])
n3 = s.add_note("User shops at Paris-area stores.", [n2])
n4 = s.add_note("User works remotely (unrelated to city).", [p_work])
t2 = s.log_turn("s1", 2, "agent", "Noted — Paris, remote work.", 0, 8, "exp-agent")

closure_before = sorted(s._dependent_closure(p_city))
res = s.correct(p_city, "Lyon", "I moved to Lyon last week")
flagged = sorted(res["flagged_stale"])
ctx_after = s.serialize_context()
notes = {r["id"]: r["status"] for r in s._records("longterm_notes", tombstones=True)}

headline = {
  "closure_size": len(closure_before),
  "flagged_count": len(flagged),
  "pct_dependents_reflaged": round(100.0 * len(flagged) / max(1, len(closure_before)), 2),
  "closure_fully_flagged": flagged == closure_before,
  "unrelated_note_untouched": notes[n4] == "active",
  "old_value_absent_from_read_path": "Paris" not in ctx_after,
  "new_value_present": "Lyon" in ctx_after,
}
result = {"experiment": "exp1_correction_integrity", "frozen": "2026-10-19",
          "headline": headline,
          "detail": {"flagged": flagged, "closure": closure_before,
                     "note_status": notes, "correction_id": res["correction_id"],
                     "successor_id": res["successor_id"]}}
(OUT / "result.json").write_text(json.dumps(result, indent=1))
print(json.dumps(headline, indent=1))
