#!/usr/bin/env python3
"""Systematic multi-database search for the 'verifiable memory for AI agents' review (Layer 4).
Uses stdlib only (urllib). Queries OpenAlex (primary, has DOIs) + arXiv (recent preprints).
Writes raw JSON per source and a combined, deduplicated candidate list.
Method mirrors the Qafiya (Layer 1) litreview/search.py."""
import json, time, urllib.parse, urllib.request, re, sys, os

OUT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(OUT, "raw")
os.makedirs(RAW, exist_ok=True)
UA = {"User-Agent": "lit-review/1.0 (research; mailto:youssef.hariri@example.org)"}
YEAR_FROM, YEAR_TO = 2018, 2026

def get(url, tries=4, sleep=1.5):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            code = getattr(e, "code", None)
            if code == 429:
                time.sleep(sleep * (i + 2)); continue
            time.sleep(sleep)
    return None

# ---- Concept queries (agent-memory focused) ----
OPENALEX_QUERIES = {
 # 1. Memory architectures for LLM agents (MemGPT line, generative agents)
 "memory_arch": ['memory "large language model" agent', '"MemGPT" OR "virtual context management"',
                 'agent "long-term memory" LLM', '"memory-augmented" language model agent'],
 # 2. Conversational & personal memory (sessions, preferences, user modeling)
 "conv_memory": ['dialogue "long-term memory" language model', 'personalized "language model" user memory',
                 '"user preferences" LLM agent memory', 'session memory conversational agent'],
 # 3. Memory editing & correction
 "edit_correct": ['knowledge editing "language model"', 'model editing ROME MEMIT',
                  'correcting stored knowledge LLM', 'belief revision language model memory'],
 # 4. Forgetting, deletion, consent, unlearning
 "forget": ['machine unlearning "language model"', '"right to be forgotten" machine learning',
            'data deletion machine learning GDPR', 'selective forgetting neural network'],
 # 5. Provenance, audit & transparency of agent state
 "provenance": ['provenance "language model" agent', 'audit trail AI agent',
                'append-only log tamper-evident audit', 'transparency user data AI assistant'],
 # 6. Memory evaluation & context cost
 "eval_cost": ['benchmark "long-term memory" agent', 'long context versus retrieval augmented',
               'token cost context language model', 'memory evaluation conversational agent'],
}

def openalex_search():
    all_rows = {}
    for theme, queries in OPENALEX_QUERIES.items():
        for q in queries:
            params = {
                "filter": f"title_and_abstract.search:{q},from_publication_date:{YEAR_FROM}-01-01,to_publication_date:{YEAR_TO}-12-31",
                "per-page": "25", "sort": "relevance_score:desc",
            }
            url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
            txt = get(url)
            if not txt:
                print(f"[openalex] FAIL {theme} :: {q}", file=sys.stderr); continue
            try:
                data = json.loads(txt)
            except Exception:
                print(f"[openalex] JSONERR {theme} :: {q}", file=sys.stderr); continue
            for w in data.get("results", []):
                doi = (w.get("doi") or "").replace("https://doi.org/", "")
                key = doi or w.get("id")
                inv = w.get("abstract_inverted_index") or {}
                pos = {}
                for word, idxs in inv.items():
                    for i in idxs: pos[i] = word
                abstract = " ".join(pos[i] for i in sorted(pos))[:600]
                all_rows[key] = {
                    "source": "openalex", "theme": theme, "query": q,
                    "title": w.get("title"), "year": w.get("publication_year"),
                    "venue": ((w.get("primary_location") or {}).get("source") or {}).get("display_name"),
                    "doi": doi, "arxiv": None,
                    "cited_by": w.get("cited_by_count"),
                    "abstract": abstract,
                    "oa_id": w.get("id"),
                }
            time.sleep(0.4)
    return all_rows

def arxiv_search():
    rows = {}
    arq = {
      "memory_arch": 'abs:"MemGPT" OR abs:"memory-augmented" AND abs:"agent" OR abs:"long-term memory" AND abs:"LLM agent"',
      "conv_memory": 'abs:"conversational memory" OR abs:"user memory" AND abs:"language model" OR abs:"personalized" AND abs:"memory" AND abs:"agent"',
      "edit_correct": 'abs:"knowledge editing" AND abs:"language model" OR abs:"model editing" AND abs:"fact"',
      "forget": 'abs:"machine unlearning" OR abs:"right to be forgotten" AND abs:"language model"',
      "provenance": 'abs:"provenance" AND abs:"language model" OR abs:"tamper-evident" AND abs:"audit log"',
      "eval_cost": 'abs:"long context" AND abs:"retrieval-augmented" OR abs:"memory benchmark" AND abs:"agent" OR abs:"LongMemEval" OR abs:"conversation" AND abs:"memory" AND abs:"benchmark"',
    }
    for theme, q in arq.items():
        url = "http://export.arxiv.org/api/query?search_query=" + urllib.parse.quote(q) + "&start=0&max_results=30&sortBy=relevance"
        txt = get(url)
        if not txt:
            print(f"[arxiv] FAIL {theme}", file=sys.stderr); continue
        entries = re.findall(r"<entry>(.*?)</entry>", txt, re.S)
        for e in entries:
            def tag(t):
                m = re.search(rf"<{t}>(.*?)</{t}>", e, re.S); return m.group(1).strip() if m else ""
            idurl = tag("id")
            m = re.search(r"arxiv.org/abs/([\d.v]+)", idurl)
            aid = m.group(1) if m else idurl
            title = re.sub(r"\s+", " ", tag("title"))
            summ = re.sub(r"\s+", " ", tag("summary"))[:600]
            pub = tag("published")[:10]
            yr = int(pub[:4]) if pub[:4].isdigit() else None
            authors = re.findall(r"<name>(.*?)</name>", e)
            if yr and yr < YEAR_FROM: continue
            rows["arxiv:"+aid] = {
                "source": "arxiv", "theme": theme, "query": q,
                "title": title, "year": yr, "venue": "arXiv",
                "doi": "", "arxiv": aid, "cited_by": None,
                "abstract": summ, "authors": authors[:6],
            }
        time.sleep(1.0)
    return rows

def main():
    oa = openalex_search()
    ax = arxiv_search()
    with open(os.path.join(RAW, "openalex.json"), "w") as f: json.dump(list(oa.values()), f, indent=1)
    with open(os.path.join(RAW, "arxiv.json"), "w") as f: json.dump(list(ax.values()), f, indent=1)
    combined = {}
    for r in list(oa.values()) + list(ax.values()):
        t = re.sub(r"[^a-z0-9 ]", "", (r["title"] or "").lower()).strip()
        key = t[:60]
        if key in combined:
            if r.get("arxiv") and not combined[key].get("arxiv"):
                combined[key]["arxiv"] = r["arxiv"]
        else:
            combined[key] = dict(r)
    with open(os.path.join(RAW, "combined.json"), "w") as f: json.dump(list(combined.values()), f, indent=1)
    print(f"openalex_raw={len(oa)} arxiv_raw={len(ax)} deduped={len(combined)}")
    from collections import Counter
    print("by_theme:", dict(Counter(r['theme'] for r in combined.values())))

if __name__ == "__main__":
    main()
