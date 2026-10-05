import json
import argparse
from pathlib import Path

from ime_reranker.phonetics import bopomofo_keys
from ime_reranker.rime import Rime

parser = argparse.ArgumentParser()
parser.add_argument("--cases", default="data/context_cases.json")
parser.add_argument("--output", default="data/rime_snapshots.json")
args = parser.parse_args()
cases = json.loads(Path(args.cases).read_text("utf-8"))
rime = Rime()
rows = []
try:
    for case in cases:
        session = rime.begin(case["context"])
        keys = bopomofo_keys(case["reading"])
        try:
            rime.type(session, keys)
            snapshot = rime.snapshot(session)
            rows.append({**case, "keys": keys, "code": snapshot["preedit"], **snapshot})
        finally:
            rime.end(session)
finally:
    rime.close()
Path(args.output).write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
print("cases", len(rows), "expected in Top8", sum(any(c["text"] in r["expected"] for c in r["candidates"]) for r in rows))
for r in rows:
    print(r["id"], r["preedit"], [c["text"] for c in r["candidates"]], r["expected"])
