#!/usr/bin/env python3
"""Layer 4 functional suite F1–F12 (brief §6.1). Each test maps to a spec invariant.
Run: python3 test_functional.py"""
import sys, tempfile, shutil, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from memory import Store, MemoryError_

RESULTS = []
def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

def fresh():
    d = tempfile.mkdtemp(prefix="memtest_")
    return d, Store(d)

# F1 write & read-back with provenance fields
d, s = fresh()
sid = "s_001"
t1 = s.log_turn(sid, 1, "user", "I'm vegetarian and based in Paris.", 12, 0, "local-test")
p1 = s.add_preference("diet", "vegetarian", [t1], "user-stated", 1.0)
n1 = s.add_note("User is vegetarian, lives in Paris.", [t1], "summary")
recs = s._records("preference_store")
ok = (recs and recs[0]["source_ref"] == [t1] and recs[0]["status"] == "active"
      and all(k in recs[0] for k in ("id","created_at","valid_from","superseded_by")))
check("F1 write/read-back + provenance fields", ok)
shutil.rmtree(d)

# F2 schema validation rejects malformed records
d, s = fresh()
try:
    s.add_note("orphan note", [], "summary"); ok = False
except MemoryError_: ok = True
try:
    s.add_preference("diet", "x", [], "inferred"); ok2 = False
except MemoryError_: ok2 = True
check("F2 schema validation (empty derived_from / source_ref rejected)", ok and ok2)
shutil.rmtree(d)

# F3 append-only hash-chain detects tampering
d, s = fresh()
t = s.log_turn("s", 1, "user", "hello", 1, 1, "m")
s.log_turn("s", 2, "agent", "hi", 1, 1, "m")
ok = all(s.verify_chain(ds) for ds in ("session_log","preference_store","longterm_notes"))
hp = Path(d)/"datasets"/"session_log"/"history.jsonl"
lines = hp.read_text().splitlines()
e = json.loads(lines[0]); e["record"]["content"] = "TAMPERED"
lines[0] = json.dumps(e)
hp.write_text("\n".join(lines) + "\n")
check("F3 hash-chain integrity + tamper detection", ok and not s.verify_chain("session_log"))
shutil.rmtree(d)

# F4 inspect view returns exactly the active set with source_ref
d, s = fresh()
t = s.log_turn("s", 1, "user", "I prefer metric units.", 5, 0, "m")
s.add_preference("units", "metric", [t], "user-stated")
s.correct(s._records("preference_store")[0]["id"], "imperial", "actually imperial")
view = s.inspect()
items = [i for g in view["groups"] for i in g["items"]]
ok = (len(items) == 1 and items[0]["content"] == "imperial" and items[0]["source_ref"])
check("F4 inspect view = exactly the active memory set", ok)
shutil.rmtree(d)

# F5 basic correction
d, s = fresh()
t = s.log_turn("s", 1, "user", "I like tea.", 4, 0, "m")
pid = s.add_preference("beverage", "tea", [t], "user-stated")
res = s.correct(pid, "coffee", "I meant coffee")
ctx = s.serialize_context()
old = [r for r in s._records("preference_store", tombstones=True) if r["id"] == pid][0]
ok = (old["status"] == "corrected" and old["superseded_by"] == res["correction_id"]
      and "coffee" in ctx and "tea" not in ctx)
check("F5 correction: old leaves read path, successor active, bound record", ok)
shutil.rmtree(d)

# F6 transitive invalidation of dependent notes
d, s = fresh()
t = s.log_turn("s", 1, "user", "I live in Paris.", 5, 0, "m")
pid = s.add_preference("city", "Paris", [t], "user-stated")
n1 = s.add_note("User lives in Paris.", [pid])
n2 = s.add_note("User is in the CET timezone.", [n1])
n3 = s.add_note("Unrelated note about music.", [t])
res = s.correct(pid, "Lyon", "I moved to Lyon")
status = {r["id"]: r["status"] for r in s._records("longterm_notes", tombstones=True)}
ok = (set(res["flagged_stale"]) == {n1, n2} and status[n1] == "stale"
      and status[n2] == "stale" and status[n3] == "active")
check("F6 transitive invalidation (closure re-flagged, unrelated untouched)", ok)
shutil.rmtree(d)

# F7 correction chain — only newest active, full history intact
d, s = fresh()
t = s.log_turn("s", 1, "user", "I work at Acme.", 4, 0, "m")
pid = s.add_preference("employer", "Acme", [t], "user-stated")
s.correct(pid, "BetaCorp", "I moved to BetaCorp")
succ = [r for r in s._records("preference_store") if r["predicate"] == "employer" and r["status"] == "active"][0]
s.correct(succ["id"], "GammaLtd", "Now GammaLtd")
allp = s._records("preference_store", tombstones=True)
active = [r for r in allp if r["status"] == "active"]
vals = {r.get("value") for r in allp}
ok = (len(allp) == 3 and len(active) == 1 and active[0]["value"] == "GammaLtd"
      and vals == {"Acme", "BetaCorp", "GammaLtd"})
check("F7 correction chain: 3 versions, only newest active, history intact", ok)
shutil.rmtree(d)

# F8 user-stated beats inferred; consent gates inferred writes
d, s = fresh()
t = s.log_turn("s", 1, "user", "ugh, mornings", 3, 0, "m")
s.add_preference("wake_time", "late", [t], "inferred", 0.6)
s.add_preference("wake_time", "06:00", [t], "user-stated", 1.0)
resolved = {r["predicate"]: r["value"] for r in s.resolve_conflicts()}
ok1 = resolved["wake_time"] == "06:00"
s.consent["inferred_writes"] = False
try:
    s.add_preference("mood", "calm", [t], "inferred", 0.5); ok2 = False
except MemoryError_: ok2 = True
check("F8 stated>inferred precedence + consent gate", ok1 and ok2)
shutil.rmtree(d)

# F9 single deletion with proof of absence
d, s = fresh()
t = s.log_turn("s", 1, "user", "my doctor is Dr. A", 6, 0, "m")
pid = s.add_preference("doctor", "Dr. A", [t], "user-stated")
res = s.delete(pid, "single", "privacy")
ctx = s.serialize_context()
tomb = [r for r in s._records("preference_store", tombstones=True) if r["id"] == pid][0]
ok = (res["proof"]["absence_scan"]["result"] == "PASS" and "Dr. A" not in ctx
      and tomb["status"] == "deleted" and tomb["value"] is None)
check("F9 deletion single: absent from store+context, payload-free tombstone", ok)
shutil.rmtree(d)

# F10 cascade deletion removes closure
d, s = fresh()
t = s.log_turn("s", 1, "user", "I live in Paris.", 5, 0, "m")
pid = s.add_preference("city", "Paris", [t], "user-stated")
n1 = s.add_note("User lives in Paris.", [pid])
n2 = s.add_note("CET timezone user.", [n1])
res = s.delete(pid, "cascade")
ok = (set(res["removed"]) == {pid, n1, n2}
      and res["proof"]["absence_scan"]["result"] == "PASS"
      and "Paris" not in s.serialize_context())
check("F10 cascade deletion: full closure absent + proof stored", ok)
shutil.rmtree(d)

# F11 session continuity with selective loading
d, s = fresh()
t = s.log_turn("s1", 1, "user", "remember: I use metric", 5, 0, "m")
s.add_preference("units", "metric", [t], "user-stated")
s.add_preference("favorite_color", "blue", [t], "user-stated")
ctx = s.serialize_context(query_predicates={"units"})
ok = ("metric" in ctx and "favorite_color" not in ctx)
check("F11 selective memory loading into a new session context", ok)
shutil.rmtree(d)

# F12 direct writes rejected
d, s = fresh()
try:
    s.direct_write("preference_store", {"id": "m_x"}); ok = False
except MemoryError_: ok = True
check("F12 binding-only access (direct writes rejected)", ok)
shutil.rmtree(d)

# F13 dvr/1.0 conformance of the inspection view, using Layer 2's own validator
L2 = "/Users/youssefhariri/Documents/ideas_2026 copy 2/DeewaanAI OS/02-view-renderer/view-renderer"
sys.path.insert(0, L2)
from dvr.specval import validate_view, SpecError
d, s = fresh()
t = s.log_turn("s", 1, "user", "I prefer metric and tea.", 7, 0, "m")
s.add_preference("units", "metric", [t], "user-stated")
s.add_preference("beverage", "tea", [t], "inferred", 0.7)
s.add_note("User prefers metric units.", [t])
view = s.inspect_view()
ok1 = ok2 = ok3 = False
try:
    validate_view(view, known_binding_ids=s.known_binding_ids()); ok1 = True
except SpecError as e: check("F13 detail", False, str(e))
# negative: value node without binding_ref must be rejected
broken = json.loads(json.dumps(view))
broken["nodes"][1].pop("binding_ref", None)
try:
    validate_view(broken); ok2 = False
except SpecError: ok2 = True
# negative: unknown kind rejected
broken2 = json.loads(json.dumps(view)); broken2["kind"] = "grid"
try:
    validate_view(broken2); ok3 = False
except SpecError: ok3 = True
check("F13 inspection view is a conformant dvr/1.0 spec (L2 validator)", ok1 and ok2 and ok3)
shutil.rmtree(d)

fails = [r for r in RESULTS if not r[1]]
print(f"\n{'='*50}\nTOTAL {len(RESULTS)}  PASS {len(RESULTS)-len(fails)}  FAIL {len(fails)}")
# frozen results artifact (claim-map discipline: no paper-only numbers)
out = Path(__file__).parent.parent / "experiments" / "functional_results.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps({"suite": "F1-F12", "frozen": "2026-10-20",
    "total": len(RESULTS), "passed": len(RESULTS)-len(fails), "failed": len(fails),
    "tests": [{"name": n, "pass": ok, "detail": dt} for n, ok, dt in RESULTS]}, indent=1))
sys.exit(1 if fails else 0)
