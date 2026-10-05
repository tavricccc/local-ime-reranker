"""Compare real Top-8 coverage and key latency in a fresh isolated dictionary."""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import yaml

from ime_reranker.phonetics import bopomofo_keys
from ime_reranker.rime import Rime

parser = argparse.ArgumentParser()
parser.add_argument("--workspace", required=True)
parser.add_argument("--output", required=True)
parser.add_argument("--cases", nargs="+", default=[
    "data/context_cases.json", "data/validation_cases.json", "data/holdout_cases.json",
    "data/final_validation_cases.json"])
args = parser.parse_args()
cases = [case for path in args.cases for case in json.loads(Path(path).read_text("utf-8"))]
started = time.perf_counter()
rime = Rime(workspace=args.workspace)
deployment_ms = (time.perf_counter() - started) * 1000
schema = yaml.safe_load((Path(args.workspace) / "shared/bopomofo_ai.schema.yaml").read_text("utf-8"))
if "onion" in schema or schema["translator"]["dictionary"] == "local_ai_onion":
    assert (Path(args.workspace) / "user/build/local_ai_onion.table.bin").exists(), "Onion dictionary did not compile"
rows = []
try:
    for case in cases:
        session = rime.begin(case["context"])
        updates = []
        try:
            for key in bopomofo_keys(case["reading"]):
                started = time.perf_counter()
                rime.type(session, key)
                snapshot = rime.snapshot(session)
                updates.append((time.perf_counter() - started) * 1000)
            texts = snapshot["displayed"]
            rows.append({**case, "candidates": texts, "preedit": snapshot["preedit"],
                         "top1_correct": texts[0] in case["expected"],
                         "top8_present": any(t in case["expected"] for t in texts),
                         "updates_ms": updates, "final_update_ms": updates[-1]})
        finally:
            rime.end(session)
finally:
    rime.close()
summary = {"n": len(rows), "deployment_ms": deployment_ms,
           "top1_correct": sum(r["top1_correct"] for r in rows),
           "top8_present": sum(r["top8_present"] for r in rows)}
for name, timings in [("all_update", [t for r in rows for t in r["updates_ms"]]),
                      ("final_update", [r["final_update_ms"] for r in rows])]:
    for q in (50, 95):
        summary[f"{name}_p{q}_ms"] = float(np.percentile(timings, q))
Path(args.output).write_text(json.dumps({"summary": summary, "rows": rows},
                                      ensure_ascii=False, indent=2), "utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
