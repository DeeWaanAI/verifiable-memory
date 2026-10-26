#!/usr/bin/env python3
"""Experiment 3 — Cost with a FAIR baseline (frozen, v2 per 2026-10-26 audit).
Three arms at matched answer capability (accuracy gate: the required fact must
be in the context, else that arm scores accuracy 0 for the query):
  FULL      — every session turn serialized (the v1 baseline)
  RAG-topk  — naive lexical retrieval: keyword overlap rank, top-k=8 memories
  SELECTIVE — this layer: predicate-addressed, conflict-resolved records
The RAG arm faces 6 deliberate lexical distractors (docs in runs[].note).
Token accounting deterministic (regex), backend-agnostic. Freezes into exp3/."""
import sys, json, shutil, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "prototype"))
from memory import Store

OUT = Path(__file__).parent / "exp3"
if OUT.exists(): shutil.rmtree(OUT)

def tok(s):
    return len(re.findall(r"\w+|[^\w\s]", s))

QUERY = "what color is my bike"
QTOK = set(re.findall(r"\w+", QUERY))
NEEDLE = "red"
K = 8
DISTRACTORS = ["bike color trends this year", "color palette for bikes",
               "my bike route colors", "colorful bike lanes map",
               "bike paint color options", "red color theory notes"]

def rag_topk(prefs, k):
    """Naive lexical RAG: rank by |query-token overlap| with the serialized record."""
    def line(p): return f"PREF {p['id']} {p['subject']}.{p['predicate']} = {json.dumps(p['value'])}"
    scored = sorted(prefs, key=lambda p: (-len(QTOK & set(re.findall(r"\w+", line(p)))), p["id"]))
    return "\n".join(line(p) for p in scored[:k])

runs = []
for N in (50, 200, 1000):
    store_root = OUT / f"store_N{N}"
    s = Store(store_root)
    for i in range(N):
        t = s.log_turn("s1", i+1, "user", f"casual chat about topic {i} with some detail here", 9, 0, "exp-agent")
        s.add_preference(f"topic_{i}", f"detail_{i}", [t], "inferred", 0.5)
    # lexical distractors (the hard case for naive retrieval)
    for i, dtxt in enumerate(DISTRACTORS):
        t = s.log_turn("s1", N+100+i, "user", dtxt, 6, 0, "exp-agent")
        s.add_preference(f"distractor_{i}", dtxt, [t], "inferred", 0.5)
    t_rel = s.log_turn("s1", N+200, "user", "remember: my bike is red", 6, 0, "exp-agent")
    s.add_preference("bike_color", "red", [t_rel], "user-stated")

    full_ctx = "\n".join(r["content"] for r in s._records("session_log") if r["role"] == "user")
    prefs = s.resolve_conflicts()
    rag_ctx = rag_topk(prefs, K)
    sel_ctx = s.serialize_context(query_predicates={"bike_color"})

    acc = {name: (NEEDLE in ctx) for name, ctx in
           (("full", full_ctx), ("rag_topk", rag_ctx), ("selective", sel_ctx))}
    runs.append({"N": N,
                 "full_tokens": tok(full_ctx), "rag_topk_tokens": tok(rag_ctx),
                 "selective_tokens": tok(sel_ctx),
                 "accuracy": acc,
                 "savings_vs_full_pct": round(100.0*(1 - tok(sel_ctx)/tok(full_ctx)), 2),
                 "savings_vs_rag_pct": round(100.0*(1 - tok(sel_ctx)/tok(rag_ctx)), 2),
                 "note": f"rag arm: top-{K} lexical overlap vs {len(DISTRACTORS)} distractors"})

matched_full = all(r["accuracy"]["full"] and r["accuracy"]["selective"] for r in runs)
rag_acc = sum(r["accuracy"]["rag_topk"] for r in runs) / len(runs)
headline = {"matched_answer_capability_full_vs_selective": matched_full,
            "rag_topk_accuracy": rag_acc,
            "savings_vs_full_by_N": {r["N"]: r["savings_vs_full_pct"] for r in runs},
            "savings_vs_rag_by_N": {r["N"]: r["savings_vs_rag_pct"] for r in runs},
            "tokens_by_N": {r["N"]: {"full": r["full_tokens"], "rag_topk": r["rag_topk_tokens"],
                                     "selective": r["selective_tokens"]} for r in runs}}
result = {"experiment": "exp3_cost", "version": "v2 (RAG baseline + accuracy, 2026-10-26 audit)",
          "frozen": "2026-10-26", "headline": headline, "runs": runs,
          "protocol": "token estimate = regex \\w+|punct; accuracy gate = required fact present; "
                      "comparisons vs full-history count only at matched accuracy; the RAG arm is a "
                      "naive lexical top-k baseline (small, frozen), not a tuned retriever"}
(OUT / "result.json").write_text(json.dumps(result, indent=1))
print(json.dumps(headline, indent=1))
