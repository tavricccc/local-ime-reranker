import json
import time
import socket
import argparse
from pathlib import Path

import numpy as np

from ime_reranker.phonetics import bopomofo_keys
from ime_reranker.rime import Rime

parser = argparse.ArgumentParser()
parser.add_argument("--cases", nargs="+", default=["data/context_cases.json"])
parser.add_argument("--workspace", default="runtime/rime")
parser.add_argument("--output", default="results/e2e")
parser.add_argument("--budgets", nargs="+", type=int, default=[30, 50, 80])
args = parser.parse_args()
cases = [case for path in args.cases for case in json.loads(Path(path).read_text("utf-8"))]
rows = []
rime = Rime(workspace=args.workspace)
try:
    for case in cases:
        baseline_session = rime.begin(case["context"])
        keys = bopomofo_keys(case["reading"])
        rime.type(baseline_session, keys)
        baseline = rime.snapshot(baseline_session)["displayed"][0]
        rime.end(baseline_session)
        for budget in args.budgets:
            # Every replay starts cold; never count earlier-budget cache hits as inference.
            with socket.create_connection(("127.0.0.1", 18963)) as connection:
                connection.sendall(b'{"diagnostic":"reset_cache"}\n')
                connection.recv(256)
            session = rime.begin(case["context"], True, budget)
            updates = []
            try:
                for key in keys:
                    start = time.perf_counter()
                    rime.type(session, key)
                    snapshot = rime.snapshot(session)
                    updates.append((time.perf_counter() - start) * 1000)
                selected = snapshot["displayed"][0]
                rows.append({"id": case["id"], "budget_ms": budget, "baseline": baseline,
                             "selected": selected, "expected": case["expected"],
                             "status": snapshot["ai_status"], "updates_ms": updates,
                             "final_update_ms": updates[-1],
                             "filter_ms": snapshot["ai_elapsed_ms"]})
                if budget == args.budgets[-1]:
                    print(case["id"], baseline, "->", selected, snapshot["ai_status"],
                          round(updates[-1], 2), flush=True)
            finally:
                rime.end(session)
finally:
    rime.close()
summary = {}
for budget in args.budgets:
    group = [r for r in rows if r["budget_ms"] == budget]
    updates = [ms for r in group for ms in r["updates_ms"]]
    finals = [r["final_update_ms"] for r in group]
    correct = sum(r["selected"] in r["expected"] for r in group)
    regressions = sum(r["baseline"] in r["expected"] and r["selected"] not in r["expected"] for r in group)
    summary[str(budget)] = {"n": len(group), "top1_accuracy": correct / len(group),
                           "regressions": regressions,
                           "all_update_p50_ms": float(np.percentile(updates, 50)),
                           "all_update_p95_ms": float(np.percentile(updates, 95)),
                           "final_update_p50_ms": float(np.percentile(finals, 50)),
                           "final_update_p95_ms": float(np.percentile(finals, 95)),
                           "status_counts": {s: sum(r["status"] == s for r in group)
                                             for s in set(r["status"] for r in group)}}
output = Path(args.output)
output.with_suffix(".rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
output.with_suffix(".summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
