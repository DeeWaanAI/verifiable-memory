#!/usr/bin/env python3
"""Verify every included citation against OpenAlex (DOI) or the arXiv API.
Method mirrors the Qafiya (Layer 1) litreview/verify.py."""
import json, os, re, time, urllib.parse, urllib.request
RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
UA = {"User-Agent": "lit-review/1.0"}
def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return r.read().decode("utf-8","replace")
        except Exception:
            time.sleep(1.5*(i+1))
    return None

# Curated included set: cite_key -> {doi or arxiv or title}
INC = [
 # A. Memory architectures for LLM agents
 ("packer2023memgpt", {"arxiv":"2310.08560"}),
 ("park2023genagents", {"arxiv":"2304.03442"}),
 ("zhang2025memorysurvey", {"doi":"10.1145/3748302"}),
 ("li2024memorymatters", {"doi":"10.1609/aaaiss.v2i1.27688"}),
 ("rasmussen2025zep", {"arxiv":"2501.13956"}),
 ("wu2026agenticmem", {"doi":"10.18653/v1/2026.acl-long.981"}),
 ("chi2026usableprivacymem", {"doi":"10.1145/3772363.3799198"}),
 # B. Conversational & personal memory (sessions, preferences)
 ("zhong2024memorybank", {"arxiv":"2305.10250"}),
 ("du2024perltqa", {"arxiv":"2402.16288"}),
 ("xu2025memconstruct", {"arxiv":"2502.05589"}),
 ("kim2023evolvingcondmem", {"arxiv":"2312.17257"}),
 ("liang2025simplebaseline", {"arxiv":"2511.17208"}),
 ("li2025longtermeval", {"doi":"10.18653/v1/2025.findings-acl.1014"}),
 # C. Memory editing & correction
 ("decao2021editing", {"doi":"10.18653/v1/2021.emnlp-main.522"}),
 ("meng2022rome", {"arxiv":"2202.05262"}),
 ("meng2022memit", {"arxiv":"2210.07229"}),
 ("zhang2024kesurvey", {"doi":"10.1145/3698590"}),
 ("cohen2024ripple", {"doi":"10.1162/tacl_a_00644"}),
 ("zhong2023mquake", {"doi":"10.18653/v1/2023.emnlp-main.971"}),
 ("gupta2024editatscale", {"doi":"10.18653/v1/2024.findings-acl.902"}),
 # D. Forgetting, deletion, consent, unlearning
 ("ginart2019deletion", {"arxiv":"1907.05012"}),
 ("golatkar2020eternal", {"doi":"10.1109/cvpr42600.2020.00932"}),
 ("bourtoule2021sisa", {"arxiv":"1912.03817"}),
 ("sommer2022athena", {"doi":"10.56553/popets-2022-0072"}),
 ("liu2024frontier", {"arxiv":"2403.15779"}),
 ("wang2025whatforget", {"arxiv":"2507.11128"}),
 # E. Provenance, audit & transparency of agent state
 ("agenttrace2026survey", {"arxiv":"2606.04990"}),
 ("mapgraph2026", {"arxiv":"2608.10509"}),
 ("transparency2023logs", {"doi":"10.1145/3689944.3696349"}),
 # F. Evaluation & context cost
 ("wu2024longmemeval", {"arxiv":"2410.10813"}),
 ("maharana2024locomo", {"arxiv":"2402.17753"}),
 ("li2024ragvslongctx", {"arxiv":"2407.16833"}),
 ("liu2024lostmiddle", {"arxiv":"2307.03172"}),
 ("recallforget2026bench", {"doi":"10.18653/v1/2026.findings-acl.1337"}),
 ("costaware2026mem", {"arxiv":"2609.05441"}),
 ("agentmembench2026", {"arxiv":"2608.00009"}),
 ("chevalier2023compressctx", {"doi":"10.18653/v1/2023.emnlp-main.232"}),
]

def oa_by_doi(doi):
    txt = get("https://api.openalex.org/works/doi:" + urllib.parse.quote(doi))
    if not txt: return None
    try: w = json.loads(txt)
    except: return None
    if w.get("error"): return None
    return canon(w)

def arxiv_by_id(aid):
    txt = get("http://export.arxiv.org/api/query?id_list="+aid)
    if not txt: return None
    m = re.search(r"<entry>(.*?)</entry>", txt, re.S)
    if not m: return None
    e = m.group(1)
    def tag(t):
        mm = re.search(rf"<{t}>(.*?)</{t}>", e, re.S); return re.sub(r"\s+"," ",mm.group(1).strip()) if mm else ""
    return {"title":tag("title"), "year":tag("published")[:4],
            "authors":re.findall(r"<name>(.*?)</name>", e)[:8],
            "venue":"arXiv", "doi":"10.48550/arXiv."+aid, "arxiv":aid, "source":"arxiv"}

def canon(w):
    auth = [a.get("author",{}).get("display_name") for a in w.get("authorships",[])][:8]
    doi = (w.get("doi") or "").replace("https://doi.org/","")
    return {"title":w.get("title"), "year":w.get("publication_year"),
            "authors":auth, "venue":((w.get("primary_location") or {}).get("source") or {}).get("display_name"),
            "doi":doi, "arxiv":None, "cited_by":w.get("cited_by_count"), "source":"openalex"}

out = {}
for key, spec in INC:
    rec = None
    if "doi" in spec: rec = oa_by_doi(spec["doi"])
    elif "arxiv" in spec: rec = arxiv_by_id(spec["arxiv"])
    status = "OK" if rec and rec.get("title") else "MISS"
    out[key] = {"status":status, "spec":spec, "rec":rec}
    t = (rec or {}).get("title") if rec else None
    print(f"[{status}] {key}: {t} ({(rec or {}).get('year')}) | doi={(rec or {}).get('doi')}")
    time.sleep(0.25)

json.dump(out, open(os.path.join(RAW,"included_verified.json"),"w"), indent=1)
miss = [k for k,v in out.items() if v["status"]=="MISS"]
print("\nTOTAL", len(out), "OK", len(out)-len(miss), "MISS", len(miss), miss)
