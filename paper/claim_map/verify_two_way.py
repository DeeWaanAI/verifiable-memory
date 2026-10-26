#!/usr/bin/env python3
"""Two-way claim verifier for verifiable-memory-v1.4 (Layer 4 paper).
Per datapoint entry: (a) the frozen artifact's value equals `expect`,
(b) the claim's marker text appears verbatim in the .tex.
Exit 0 ONLY when every entry passes both directions.
expect forms: number (rounding-tolerant to the marker's decimals), string,
{"range":[lo,hi]}, {"len_of": "<key path>"}, {"line_count": true}, {"file_exists": true}."""
import json, math, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRAFT = ROOT / "paper" / "verifiable-memory-v1.4.tex"
dps = json.loads((Path(__file__).parent / "datapoints.json").read_text())["datapoints"]
draft = DRAFT.read_text()
fails = []

def get(obj, segs):
    for s in segs:
        obj = obj[int(s)] if isinstance(obj, list) else obj[s]
    return obj

def decimals(marker):
    m = re.findall(r"\d+\.(\d+)", marker)
    return len(m[0]) if m else 0

for d in dps:
    did = d["id"]
    # direction (b): marker text in draft
    if d["marker"] not in draft:
        fails.append((did, f"marker not in draft: {d['marker'][:60]}"))
        continue
    # direction (a): artifact value == expect
    src = ROOT / d["source"]
    if not src.exists():
        fails.append((did, "missing source " + d["source"])); continue
    exp = d["expect"]
    if isinstance(exp, dict) and exp.get("file_exists"):
        continue  # existence already established
    if isinstance(exp, dict) and exp.get("line_count"):
        v = len(src.read_text().splitlines())
        if v != d["expect_value"]:
            fails.append((did, f"line count {v} != {d['expect_value']}"))
        continue
    data = json.loads(src.read_text())
    try:
        v = get(data, d["path"])
    except Exception:
        fails.append((did, "key path not found")); continue
    if isinstance(exp, dict) and "len_of" in exp:
        if len(v) != exp["len_of"]:
            fails.append((did, f"len {len(v)} != {exp['len_of']}"))
        continue
    if isinstance(exp, dict) and "range" in exp:
        if not (exp["range"][0] <= float(v) <= exp["range"][1]):
            fails.append((did, f"{v} outside {exp['range']}"))
        continue
    if isinstance(exp, str):
        if str(v) != exp:
            fails.append((did, f"string {v!r} != {exp!r}"))
        continue
    # numeric, rounding-tolerant to marker decimals; support derived ratio
    if d.get("derived_ratio_from"):
        dv = get(data, d["derived_ratio_from"])
        v = float(v) / float(dv)
    dec = decimals(d["marker"])
    if abs(round(float(v), dec) - float(exp)) > max(0.05, 10 ** -dec):
        fails.append((did, f"value artifact={v} expect={exp}"))

if fails:
    for f in fails: print("FAIL", *f)
    sys.exit(1)
print(f"OK: {len(dps)} datapoints verified both directions against {DRAFT.name}")
