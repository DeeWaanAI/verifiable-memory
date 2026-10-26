#!/usr/bin/env python3
"""Spine script (Qafiya discipline): recomputes EVERY headline number in the
Layer-4 paper from raw frozen artifacts. If this script fails, the number does
not go in the paper. Exit 0 = all headline numbers verified."""
import json, sys, re
from pathlib import Path

EXP = Path(__file__).parent
fails = []

def check(label, got, want):
    ok = got == want
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: got={got} want={want}")
    if not ok: fails.append(label)

# ---- exp1: correction integrity (recompute from the frozen STORE, not result.json) ----
sys.path.insert(0, str(EXP.parent / "prototype"))
from memory import Store

r1 = json.loads((EXP/"exp1"/"result.json").read_text())
s1 = Store(EXP/"exp1"/"store")
notes = [r for r in s1._records("longterm_notes", tombstones=True)]
stale = sorted(r["id"] for r in notes if r["status"] == "stale")
check("exp1 pct_dependents_reflaged",
      round(100.0*len(stale)/r1["headline"]["closure_size"], 2),
      r1["headline"]["pct_dependents_reflaged"])
ctx1 = s1.serialize_context()
check("exp1 old_value_absent_from_read_path", "Paris" not in ctx1, True)
check("exp1 new_value_present", "Lyon" in ctx1, True)
check("exp1 chain integrity", all(s1.verify_chain(d) for d in
      ("session_log","preference_store","longterm_notes","correction_log","deletion_log")), True)

# ---- exp2: forgetting/consent ----
r2 = json.loads((EXP/"exp2"/"result.json").read_text())
s2 = Store(EXP/"exp2"/"store")
ctx2 = s2.serialize_context()
check("exp2 read_path_clean (Dr. A)", "Dr. A" not in ctx2, True)
check("exp2 read_path_clean (Paris)", "Paris" not in ctx2, True)
check("exp2 absence scans PASS",
      (r2["proofs"]["single"]["absence_scan"]["result"],
       r2["proofs"]["cascade"]["absence_scan"]["result"]), ("PASS","PASS"))
# verify the reported leakage map against frozen raw files
store2 = EXP/"exp2"/"store"
recomputed_leak = "Dr. A" in (store2/"datasets"/"preference_store"/"history.jsonl").read_text()
check("exp2 leakage map (payload persists in history) matches raw",
      recomputed_leak, r2["headline"]["dr_A_leakage"]["preference_store/history.jsonl"])
# paraphrase probe: exact-string boundary demonstrated, not smoothed over
pp = r2["headline"]["paraphrase_probe"]
notes2 = [r for r in s2._records("longterm_notes", tombstones=True)
          if "physician" in (r.get("note") or "")]
check("exp2 paraphrase probe: note survives, scan passes (boundary demonstrated)",
      (pp["note_status_after_delete"], pp["exact_string_scan_result"],
       len(notes2) == 1 and notes2[0]["status"] == "active"),
      ("active", "PASS", True))

# ---- exp3: cost (recompute tokens from frozen stores) ----
r3 = json.loads((EXP/"exp3"/"result.json").read_text())
def tok(s): return len(re.findall(r"\w+|[^\w\s]", s))
QT = set(re.findall(r"\w+", "what color is my bike"))
def rag_topk(prefs, k):
    def line(p): return f"PREF {p['id']} {p['subject']}.{p['predicate']} = {json.dumps(p['value'])}"
    scored = sorted(prefs, key=lambda p: (-len(QT & set(re.findall(r"\w+", line(p)))), p["id"]))
    return "\n".join(line(p) for p in scored[:k])
for run in r3["runs"]:
    N = run["N"]
    s3 = Store(EXP/"exp3"/f"store_N{N}")
    full = "\n".join(r["content"] for r in s3._records("session_log") if r["role"] == "user")
    rag = rag_topk(s3.resolve_conflicts(), 8)
    sel = s3.serialize_context(query_predicates={"bike_color"})
    check(f"exp3 N={N} full_tokens", tok(full), run["full_tokens"])
    check(f"exp3 N={N} rag_topk_tokens", tok(rag), run["rag_topk_tokens"])
    check(f"exp3 N={N} selective_tokens", tok(sel), run["selective_tokens"])
    check(f"exp3 N={N} savings_vs_full", round(100.0*(1 - tok(sel)/tok(full)), 2), run["savings_vs_full_pct"])
    check(f"exp3 N={N} savings_vs_rag", round(100.0*(1 - tok(sel)/tok(rag)), 2), run["savings_vs_rag_pct"])
    check(f"exp3 N={N} accuracy gates",
          ("red" in full, "red" in rag, "red" in sel),
          (run["accuracy"]["full"], run["accuracy"]["rag_topk"], run["accuracy"]["selective"]))

# ---- limit results exist and are consistent ----
rl = json.loads((EXP/"limit_results.json").read_text())
check("limits L8 naive tamper caught", rl["L8_tamper"]["naive_tamper_caught"], True)
check("limits L8 recomputed chain uncatchable", rl["L8_tamper"]["recomputed_chain_caught"], False)

# ---- paper compile health (lesson D-2026-10-26-4: assert on the .log, never a
# filtered grep — v1.4 once shipped with a broken table because 'Extra alignment
# tab' errors slipped past a narrow pattern) ----
import glob
logs = sorted(glob.glob(str(EXP.parent/"paper"/"verifiable-memory-v1.*.log")))
if logs:
    latest = logs[-1]
    errlines = [l for l in open(latest, errors="replace") if l.startswith("!")]
    check(f"paper compile log clean ({latest.split('/')[-1]})", len(errlines), 0)
else:
    check("paper compile log present", "no .log found", "compile the .tex first")

print(f"\n{'='*50}")
if fails:
    print(f"SPINE FAILED: {len(fails)} headline numbers do not recompute"); sys.exit(1)
print("SPINE OK — every headline number recomputed from frozen artifacts")
