#!/usr/bin/env python3
"""Paper figures, computed ONLY from frozen experiment artifacts (spine discipline)."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = Path(__file__).parent.parent
FIG = Path(__file__).parent / "figures"
plt.rcParams.update({"font.size": 10, "font.family": "DejaVu Sans",
                     "axes.spines.top": False, "axes.spines.right": False})

# ---- fig3: token cost, full-history vs selective (exp3) ----
r3 = json.loads((BASE/"experiments/exp3/result.json").read_text())
N = [r["N"] for r in r3["runs"]]
full = [r["full_tokens"] for r in r3["runs"]]
rag = [r["rag_topk_tokens"] for r in r3["runs"]]
sel = [r["selective_tokens"] for r in r3["runs"]]
fig, ax = plt.subplots(figsize=(4.6, 3.0))
ax.plot(N, full, "o-", color="#2f5fa3", lw=2, label="full-history prompting")
ax.plot(N, rag, "^-.", color="#6a4a9c", lw=2, label="RAG top-8 (naive lexical)")
ax.plot(N, sel, "s--", color="#c47a24", lw=2, label="selective loading (Layer 4)")
for x, y, r in zip(N, full, r3["runs"]):
    ax.annotate(f'-{r["savings_vs_full_pct"]}%', (x, y), textcoords="offset points",
                xytext=(6, 8), fontsize=9, color="#235c2e")
ax.set_xlabel("memories in store (N)")
ax.set_ylabel("prompt tokens")
ax.set_yscale("log")
ax.legend(frameon=False, loc="upper left")
fig.tight_layout()
fig.savefig(FIG/"fig3_cost.pdf")
fig.savefig(FIG/"fig3_cost.png", dpi=200)
plt.close(fig)

# ---- fig4: limit-test latency (L1 + L7, honest both-numbers) ----
rl = json.loads((BASE/"experiments/limit_results.json").read_text())
fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.8))
l1 = rl["L1_scale"]["measurements"]
ns = sorted(int(k) for k in l1)
a1.plot(ns, [l1[str(n)]["resolve_conflicts_s"] for n in ns], "o-", color="#2f5fa3", lw=2, label="resolve conflicts")
a1.plot(ns, [l1[str(n)]["serialize_context_s"] for n in ns], "s--", color="#c47a24", lw=2, label="serialize context")
a1.set_xscale("log"); a1.set_xlabel("records in store"); a1.set_ylabel("seconds")
a1.set_title("(a) read-path latency (L1)", fontsize=10)
a1.legend(frameon=False, fontsize=8)
a2.bar(["before fix\n(O(n²) rewrites)", "after fix\n(batched)"],
       [rl["L7_invalidation_cost"]["reflag_seconds_before_fix"],
        rl["L7_invalidation_cost"]["reflag_seconds"]],
       color=["#a33", "#3f8f4f"], width=0.55)
a2.set_ylabel("seconds"); a2.set_yscale("log")
a2.set_title("(b) re-flag of a 300-deep chain (L7)", fontsize=10)
for i, v in enumerate([rl["L7_invalidation_cost"]["reflag_seconds_before_fix"],
                       rl["L7_invalidation_cost"]["reflag_seconds"]]):
    a2.text(i, v*1.25, f"{v}s", ha="center", fontsize=9)
fig.tight_layout()
fig.savefig(FIG/"fig4_limits.pdf")
fig.savefig(FIG/"fig4_limits.png", dpi=200)
plt.close(fig)
print("figures written:", list(p.name for p in FIG.iterdir()))
