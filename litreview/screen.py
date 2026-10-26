#!/usr/bin/env python3
import json, os, re
from collections import defaultdict
RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
rows = json.load(open(os.path.join(RAW, "combined.json")))

BOOST = {
 "memory_arch": ["memgpt","letta","memory","agent","long-term memory","virtual context","hierarchical memory","self-directed","operating system","context window","episodic","semantic memory","working memory"],
 "conv_memory": ["conversation","dialogue","user","personali","preference","session","memorybank","profile","long-term","remember","history"],
 "edit_correct": ["knowledge editing","model editing","edit","correct","update","fact","rome","memit","belief","stale","outdated","counterfactual"],
 "forget": ["unlearning","forget","deletion","right to be forgotten","gdpr","consent","privacy","remove","erase","selective"],
 "provenance": ["provenance","audit","tamper","append-only","log","transparen","lineage","trust","verifiable","accountab","immutab"],
 "eval_cost": ["benchmark","evaluation","long context","retrieval","token","cost","latency","recall","longmemeval","locomo","ruler","needle"],
}

def score(r):
    txt = ((r.get("title") or "") + " " + (r.get("abstract") or "")).lower()
    s = 0
    for k in BOOST.get(r["theme"], []):
        if k.lower() in txt: s += 2
    if r.get("cited_by"): s += min(r["cited_by"], 200)/20.0
    return s

by_theme = defaultdict(list)
for r in rows:
    r["_score"] = score(r)
    by_theme[r["theme"]].append(r)

total_pass = 0
for theme in ["memory_arch","conv_memory","edit_correct","forget","provenance","eval_cost"]:
    lst = sorted(by_theme.get(theme, []), key=lambda x: x["_score"], reverse=True)
    passed = [r for r in lst if r["_score"] >= 4]
    total_pass += len(passed)
    print(f"\n===== {theme}  (candidates={len(lst)}, passed={len(passed)}) =====")
    for r in lst[:22]:
        if r["_score"] < 4: break
        ident = r.get("doi") or ("arXiv:"+r["arxiv"] if r.get("arxiv") else r.get("oa_id",""))
        print(f"[{r['_score']:.1f}] {r.get('year')} | {(r.get('venue') or '?')[:28]} | {(r.get('title') or '')[:95]} | {ident} | cites={r.get('cited_by')}")
print("\nTOTAL PASSED:", total_pass)
