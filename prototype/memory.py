#!/usr/bin/env python3
"""Layer 4 — Verifiable Memory · reference prototype (spec v1.0).
Implements the five datasets, hash-chain history, the memory binding (only
read/write path), correction protocol with transitive invalidation, deletion
with proof-of-absence, and the inspection view. Stdlib only.
Storage layout per spec §7: one directory per dataset under a root."""
import json, os, hashlib, time, shutil
from pathlib import Path

SCHEMAS = {
 "session_log": {
   "dataset": "session_log", "id_field": "id",
   "fields": {"id":"id","created_at":"timestamp","source_ref":"list<id>","valid_from":"timestamp",
              "superseded_by":"id|null","status":"enum[active,corrected,deleted,stale]",
              "session_id":"id","turn_index":"number","role":"enum[user,agent,system]",
              "content":"string","tokens_in":"number","tokens_out":"number","model_id":"string"},
   "derivations": ["filter","count","groupby","sum"]},
 "preference_store": {
   "dataset": "preference_store", "id_field": "id",
   "fields": {"id":"id","created_at":"timestamp","source_ref":"list<id>","valid_from":"timestamp",
              "superseded_by":"id|null","status":"enum[active,corrected,deleted,stale]",
              "subject":"string","predicate":"string","value":"any","confidence":"number",
              "extraction_method":"enum[user-stated,inferred]"},
   "derivations": ["filter","count","groupby","latest"]},
 "longterm_notes": {
   "dataset": "longterm_notes", "id_field": "id",
   "fields": {"id":"id","created_at":"timestamp","source_ref":"list<id>","valid_from":"timestamp",
              "superseded_by":"id|null","status":"enum[active,corrected,deleted,stale]",
              "note":"string","derived_from":"list<id>","note_kind":"enum[summary,reflection,fact-cluster]"},
   "derivations": ["filter","count"]},
 "correction_log": {
   "dataset": "correction_log", "id_field": "id",
   "fields": {"id":"id","created_at":"timestamp","source_ref":"list<id>","valid_from":"timestamp",
              "superseded_by":"id|null","status":"enum[active,corrected,deleted,stale]",
              "target_id":"id","old_value":"any","new_value":"any","user_statement":"string","applied_at":"timestamp"},
   "derivations": ["filter","count"]},
 "deletion_log": {
   "dataset": "deletion_log", "id_field": "id",
   "fields": {"id":"id","created_at":"timestamp","source_ref":"list<id>","valid_from":"timestamp",
              "superseded_by":"id|null","status":"enum[active,corrected,deleted,stale]",
              "target_id":"id","scope":"enum[single,cascade]","reason":"string|null","proof":"object"},
   "derivations": ["filter","count"]},
}

DATASETS = list(SCHEMAS)
_counter = [0]

def _ulid(prefix):
    _counter[0] += 1
    return f"{prefix}_{int(time.time()*1000):013d}{_counter[0]:05d}"

def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def _sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

class MemoryError_(Exception): pass

class Store:
    """The memory binding — the ONLY sanctioned read/write path (spec §3)."""
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.consent = {"inferred_writes": True, "disabled_predicates": set()}
        self._tail_hash = {}
        for name in DATASETS:
            d = self.root / "datasets" / name
            d.mkdir(parents=True, exist_ok=True)
            if not (d / "schema.json").exists():
                (d / "schema.json").write_text(json.dumps(SCHEMAS[name], indent=1))
            for f in ("data.jsonl", "history.jsonl", "bindings.jsonl"):
                (d / f).touch(exist_ok=True)
            if not (d / "SUPERSEDED.json").exists():
                (d / "SUPERSEDED.json").write_text("[]")

    # ---------- persistence ----------
    def _dir(self, ds):
        if ds not in DATASETS: raise MemoryError_(f"unknown dataset {ds}")
        return self.root / "datasets" / ds

    def _records(self, ds, tombstones=False):
        out = []
        for line in (self._dir(ds) / "data.jsonl").read_text().splitlines():
            if not line.strip(): continue
            r = json.loads(line)
            if not tombstones and r.get("status") == "deleted":
                continue
            out.append(r)
        return out

    def _append(self, ds, rec):
        """O(1) append for new records (data.jsonl is append-only for appends;
        _rewrite is used only for status updates/tombstones)."""
        with (self._dir(ds) / "data.jsonl").open("a") as f:
            f.write(_canon(rec) + "\n")

    def _rewrite(self, ds, records):
        """Atomic write (Qafiya §6: temp-then-rename, never in place)."""
        p = self._dir(ds) / "data.jsonl"
        tmp = p.with_suffix(".tmp")
        tmp.write_text("".join(_canon(r) + "\n" for r in records))
        os.replace(tmp, p)

    def _hist_append(self, ds, op, record):
        """Spec §2: chained history inherited from the Qafiya v1.3 substrate
        (qafiya_core.chain). The tail-hash cache is a local optimization; the
        hash construction and file format are the substrate's, not ours."""
        from qafiya_core import chain
        hp = self._dir(ds) / "history.jsonl"
        prev = self._tail_hash.get(ds)
        if prev is None:
            lines = [l for l in hp.read_text().splitlines() if l.strip()]
            prev = json.loads(lines[-1])["entry_hash"] if lines else chain.GENESIS
        entry = {"op": op, "record": record, "at": time.time(), "prev_hash": prev}
        body = {k: v for k, v in entry.items() if k not in ("prev_hash", "entry_hash")}
        entry["entry_hash"] = chain.entry_hash(prev, body)
        self._tail_hash[ds] = entry["entry_hash"]
        with hp.open("a") as f:
            f.write(chain.canon(entry) + "\n")

    def verify_chain(self, ds):
        from qafiya_core import chain
        ok, _ = chain.verify(self._dir(ds) / "history.jsonl")
        return ok

    # ---------- validation ----------
    def _validate(self, ds, rec):
        sch = SCHEMAS[ds]["fields"]
        for f in sch:
            if f not in rec: raise MemoryError_(f"{ds}: missing field {f}")
        if ds in ("preference_store",) and not rec["source_ref"]:
            raise MemoryError_("source_ref must be non-empty")
        if ds == "longterm_notes" and not rec["derived_from"]:
            raise MemoryError_("derived_from must be non-empty")
        if rec.get("status") not in ("active","corrected","deleted","stale"):
            raise MemoryError_("bad status")
        return True

    # ---------- write ops (spec §4.1) ----------
    def log_turn(self, session_id, turn_index, role, content, tokens_in, tokens_out, model_id):
        rec = {"id": _ulid("m"), "created_at": time.time(), "source_ref": [],
               "valid_from": time.time(), "superseded_by": None, "status": "active",
               "session_id": session_id, "turn_index": turn_index, "role": role,
               "content": content, "tokens_in": tokens_in, "tokens_out": tokens_out,
               "model_id": model_id}
        self._validate("session_log", rec)
        self._append("session_log", rec)
        self._hist_append("session_log", "append", rec)
        return rec["id"]

    def add_preference(self, predicate, value, source_ref, extraction_method,
                       confidence=1.0, subject="user"):
        if extraction_method == "inferred":
            if not self.consent["inferred_writes"]:
                raise MemoryError_("inferred writes disabled by consent")
            if predicate in self.consent["disabled_predicates"]:
                raise MemoryError_(f"inferred writes disabled for {predicate}")
        rec = {"id": _ulid("m"), "created_at": time.time(), "source_ref": list(source_ref),
               "valid_from": time.time(), "superseded_by": None, "status": "active",
               "subject": subject, "predicate": predicate, "value": value,
               "confidence": confidence, "extraction_method": extraction_method}
        self._validate("preference_store", rec)
        self._append("preference_store", rec)
        self._hist_append("preference_store", "append", rec)
        return rec["id"]

    def add_note(self, note, derived_from, note_kind="summary", source_ref=None):
        for dep in derived_from:
            if not self._find(dep):
                raise MemoryError_(f"derived_from id {dep} does not resolve")
        rec = {"id": _ulid("m"), "created_at": time.time(), "source_ref": list(source_ref or derived_from),
               "valid_from": time.time(), "superseded_by": None, "status": "active",
               "note": note, "derived_from": list(derived_from), "note_kind": note_kind}
        self._validate("longterm_notes", rec)
        self._append("longterm_notes", rec)
        self._hist_append("longterm_notes", "append", rec)
        return rec["id"]

    def _find(self, mid, tombstones=True):
        for ds in DATASETS:
            for r in self._records(ds, tombstones=tombstones):
                if r["id"] == mid:
                    return ds, r
        return None

    def _update_record(self, ds, mid, **patch):
        recs = self._records(ds, tombstones=True)
        found = False
        for r in recs:
            if r["id"] == mid:
                r.update(patch); found = True
        if not found: raise MemoryError_(f"{mid} not in {ds}")
        self._rewrite(ds, recs)
        self._hist_append(ds, "update", {"id": mid, **patch})

    # ---------- correction protocol (spec §4.3) ----------
    def correct(self, target_id, new_value, user_statement):
        hit = self._find(target_id, tombstones=False)
        if not hit: raise MemoryError_(f"correction target {target_id} not found")
        ds, target = hit
        corr = {"id": _ulid("m"), "created_at": time.time(), "source_ref": [target_id],
                "valid_from": time.time(), "superseded_by": None, "status": "active",
                "target_id": target_id, "old_value": target.get("value", target.get("content", target.get("note"))),
                "new_value": new_value, "user_statement": user_statement, "applied_at": time.time()}
        self._validate("correction_log", corr)
        self._append("correction_log", corr)
        self._hist_append("correction_log", "append", corr)
        # supersede target + append successor (for preference_store; notes get flagged)
        self._update_record(ds, target_id, status="corrected", superseded_by=corr["id"])
        successor_id = None
        if ds == "preference_store":
            successor_id = self.add_preference(
                target["predicate"], new_value, [corr["id"]],
                "user-stated", confidence=1.0, subject=target["subject"])
        # transitive invalidation over dependent closure
        flagged = self._invalidate_dependents(target_id)
        return {"correction_id": corr["id"], "successor_id": successor_id, "flagged_stale": flagged}

    def _dependent_closure(self, target_id):
        """All notes whose derived_from closure contains target_id (reverse reachability)."""
        notes = self._records("longterm_notes", tombstones=True)
        direct = {n["id"] for n in notes if target_id in n.get("derived_from", [])}
        closure = set(direct); frontier = set(direct)
        while frontier:
            nxt = {n["id"] for n in notes if any(d in frontier for d in n.get("derived_from", []))} - closure
            closure |= nxt; frontier = nxt
        return closure

    def _invalidate_dependents(self, target_id):
        flagged = sorted(self._dependent_closure(target_id))
        if not flagged: return []
        # single batched rewrite (O(n) once, not per flag)
        recs = self._records("longterm_notes", tombstones=True)
        for r in recs:
            if r["id"] in flagged and r["status"] == "active":
                r["status"] = "stale"
        self._rewrite("longterm_notes", recs)
        self._hist_append("longterm_notes", "batch_flag_stale", {"ids": flagged})
        return flagged

    # ---------- deletion protocol (spec §4.4) ----------
    def delete(self, target_id, scope="single", reason=None):
        hit = self._find(target_id, tombstones=False)
        if not hit: raise MemoryError_(f"deletion target {target_id} not found")
        ds, target = hit
        payload = target.get("value", target.get("content", target.get("note")))
        victims = {target_id}
        if scope == "cascade":
            victims |= self._dependent_closure(target_id)
        else:
            # single scope: dependents are NOT tombstoned, but MUST leave the read
            # path (stale) — otherwise a note derived from the deleted record would
            # keep serving its payload (found by exp2's proof-of-absence FAIL).
            self._invalidate_dependents(target_id)
        state_before = _sha(_canon([self._records(d, tombstones=True) for d in DATASETS]))
        for vid in victims:
            vhit = self._find(vid, tombstones=True)
            if not vhit: continue
            vds, vrec = vhit
            tomb = {k: (None if k in ("value","content","note","old_value","new_value",
                                      "user_statement","derived_from") else vrec[k]) for k in vrec}
            if "source_ref" in tomb: tomb["source_ref"] = []
            tomb["status"] = "deleted"
            recs = [tomb if r["id"] == vid else r for r in self._records(vds, tombstones=True)]
            self._rewrite(vds, recs)
            self._hist_append(vds, "tombstone", {"id": vid})
        state_after = _sha(_canon([self._records(d, tombstones=True) for d in DATASETS]))
        scan = self.proof_of_absence(payload)
        proof = {"state_before": state_before, "state_after": state_after,
                 "payload_hash": _sha(_canon(payload)) if payload is not None else None,
                 "absence_scan": scan}
        rec = {"id": _ulid("m"), "created_at": time.time(), "source_ref": [target_id],
               "valid_from": time.time(), "superseded_by": None, "status": "active",
               "target_id": target_id, "scope": scope, "reason": reason, "proof": proof}
        self._validate("deletion_log", rec)
        self._append("deletion_log", rec)
        self._hist_append("deletion_log", "append", rec)
        return {"deletion_id": rec["id"], "removed": sorted(victims), "proof": proof}

    # ---------- read path (spec §3) ----------
    def active_memory(self):
        out = {}
        for ds in ("preference_store", "longterm_notes"):
            out[ds] = [r for r in self._records(ds) if r["status"] == "active"]
        return out

    def resolve_conflicts(self):
        """Preference resolution: user-stated beats inferred; else newest valid_from."""
        prefs = [r for r in self._records("preference_store") if r["status"] == "active"]
        by_pred = {}
        for r in prefs:
            k = (r["subject"], r["predicate"])
            cur = by_pred.get(k)
            if cur is None: by_pred[k] = r; continue
            rank = lambda x: (x["extraction_method"] == "user-stated", x["valid_from"])
            if rank(r) > rank(cur): by_pred[k] = r
        return list(by_pred.values())

    def serialize_context(self, query_predicates=None):
        """Deterministic, diffable prompt context (sorted by id)."""
        prefs = self.resolve_conflicts()
        if query_predicates:
            prefs = [p for p in prefs if p["predicate"] in query_predicates]
        notes = [r for r in self._records("longterm_notes") if r["status"] == "active"]
        lines = [f"PREF {p['id']} {p['subject']}.{p['predicate']} = {_canon(p['value'])}" for p in sorted(prefs, key=lambda r: r["id"])]
        lines += [f"NOTE {n['id']} {n['note']}" for n in sorted(notes, key=lambda r: r["id"])]
        ctx = "\n".join(lines)
        self._hist_append("session_log", "context_emit",
                          {"memory_ids": [p["id"] for p in prefs] + [n["id"] for n in notes],
                           "context_hash": _sha(ctx)})
        return ctx

    def proof_of_absence(self, payload):
        """Scans the READ PATH (spec §5.2): active preference/note records + the
        serialized prompt context. Raw session turns and log payloads (correction
        old_value etc.) are append-only history, outside the read-path guarantee —
        that boundary is measured in limit test L5, not hidden."""
        if payload is None:
            return {"result": "PASS", "detail": "null payload", "scanned": []}
        needle = payload if isinstance(payload, str) else _canon(payload).strip('"')
        scanned, found = [], False
        for ds in ("preference_store", "longterm_notes"):
            blob = _canon([r for r in self._records(ds) if r["status"] == "active"])
            scanned.append({"dataset": ds + " (active records)", "hash": _sha(blob)})
            if needle and needle in blob: found = True
        ctx = self.serialize_context()
        scanned.append({"prompt_context": _sha(ctx)})
        if needle and needle in ctx: found = True
        return {"result": "FAIL" if found else "PASS", "scanned": scanned,
                "coverage": "read path: active preference_store + longterm_notes + prompt context"}

    # ---------- inspection view (spec §4.5) ----------
    def inspect(self):
        """Content query used by F4: exactly the active set, with source_ref."""
        view = {"view": "what_do_you_remember", "groups": []}
        for ds in ("preference_store", "longterm_notes"):
            items = [{"id": r["id"], "content": r.get("value", r.get("note")),
                      "predicate": r.get("predicate"), "source_ref": r["source_ref"],
                      "extraction_method": r.get("extraction_method")}
                     for r in self._records(ds) if r["status"] == "active"]
            view["groups"].append({"dataset": ds, "items": items})
        return view

    # ---------- dvr/1.0 view (Layer 2 contract, frozen 2026-10-20) ----------
    VIEW_ID = "v_memory_inspect"

    def _view_binding(self, ds, rec, node_id):
        """One Qafiya view binding per rendered item: the node carries a
        binding_ref, never a value (dvr §2.3 rule 3)."""
        field = "value" if ds == "preference_store" else "note"
        content = rec[field]
        return {
            "id": _ulid("b"), "kind": "view",
            "target": {"view": self.VIEW_ID, "node": node_id},
            "sources": [{"dataset": f"ds:{ds}", "filter": f"id={rec['id']}",
                         "field": field, "key_path": [field],
                         "verbatim_excerpt": str(content)}],
            "derivation": f"{field} where id='{rec['id']}'",
            "value": content,
            "statistic": "identity", "device": "layer4-store",
            "authoritative_artifact": f"datasets/{ds}/data.jsonl",
            "superseded_by": [],
            "provenance": {"created_by": "layer4-inspect", "created_at": time.time(),
                           "source_query": "what do you remember about me"},
        }

    def inspect_view(self):
        """Emit a conformant dvr/1.0 view spec: one value node per active memory
        item, bindings persisted in the owning dataset's bindings.jsonl.
        Group headers are label nodes (binding_ref forbidden)."""
        nodes = []
        for ds, hdr in (("preference_store", "Preferences"),
                        ("longterm_notes", "Long-term notes")):
            nodes.append({"id": f"hdr:{ds}", "role": "label", "text": hdr})
            binds = []
            for r in self._records(ds):
                if r["status"] != "active":
                    continue
                nid = f"node:{r['id']}"
                b = self._view_binding(ds, r, nid)
                binds.append(b)
                nodes.append({"id": nid, "role": "value", "binding_ref": b["id"],
                              "row_key": r["id"],
                              "editable": ds == "preference_store"})
            # view bindings are derived artifacts: regenerate idempotently
            bp = self._dir(ds) / "bindings.jsonl"
            existing = [json.loads(l) for l in bp.read_text().splitlines() if l.strip()]
            kept = [b for b in existing
                    if (b.get("target") or {}).get("view") != self.VIEW_ID]
            bp.write_text("".join(_canon(b) + "\n" for b in kept + binds))
        view = {"spec": "dvr/1.0", "id": self.VIEW_ID, "kind": "list",
                "title": {"text": "What I remember about you"}, "nodes": nodes}
        mp = self.root / "memory"
        mp.mkdir(exist_ok=True)
        (mp / "inspect.view.json").write_text(json.dumps(view, indent=1))
        return view

    def known_binding_ids(self):
        ids = set()
        for ds in DATASETS:
            bp = self._dir(ds) / "bindings.jsonl"
            for l in bp.read_text().splitlines():
                if l.strip(): ids.add(json.loads(l)["id"])
        return ids

    def direct_write(self, ds, record):
        """F12: direct dataset writes MUST be rejected."""
        raise MemoryError_("direct dataset writes are rejected; use the binding (spec §3)")
