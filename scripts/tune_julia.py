"""Bounded prompt/order/shortlist experiment; policy sweep reuses real scores."""
import itertools
import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

from ime_reranker.evaluate import eligible_candidates
from ime_reranker.julia_model import JuliaScorer
from ime_reranker.policy import Policy, apply_scores
from ime_reranker.prompts import PROMPTS

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--resume", action="store_true")
args = parser.parse_args()
cases = (json.loads((ROOT / "data/comparison_snapshots.json").read_text("utf-8")) +
         json.loads((ROOT / "data/holdout_snapshots.json").read_text("utf-8")))
out = ROOT / "results/tuning"
out.mkdir(parents=True, exist_ok=True)
configs = [{"prompt": prompt, "reverse": False, "top_k": 8} for prompt in PROMPTS]
configs += [{"prompt": prompt, "reverse": True, "top_k": 8}
            for prompt in ("baseline", "repair", "english")]
configs += [{"prompt": "baseline", "reverse": False, "top_k": k} for k in (2, 4)]
protocol = {"n": len(cases), "configs": configs, "max_regressions": 3,
            "max_inference_p95_ms": 150,
            "selection": "highest top1, then fewer regressions, then lowest inference p95",
            "note": "All 96 cases are now exploration data. Verify frozen selection on new cases."}
(out / "protocol.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2), "utf-8")
scorer = JuliaScorer(str(ROOT / "models/julia"))
choices = []
for config in configs:
    scorer.prompt = config["prompt"]
    scorer.reverse = config["reverse"]
    scorer.top_k = config["top_k"]
    name = f"{scorer.prompt}-{'balanced' if scorer.reverse else 'single'}-k{scorer.top_k}"
    _, warm_candidates = eligible_candidates(cases[0])
    for _ in range(3):
        scorer.score({**cases[0], "candidates": warm_candidates})
    artifact = out / f"{name}.rows.json"
    if args.resume and artifact.exists():
        rows = json.loads(artifact.read_text("utf-8"))
    else:
        rows = []
        for case in cases:
            _, candidates = eligible_candidates(case)
            row = {"id": case["id"], "expected": case["expected"], "candidates": candidates,
                   "baseline": candidates[0]["text"], "attempted": len(candidates) > 1 and bool(case["context"])}
            if row["attempted"]:
                probabilities, metadata = scorer.score({**case, "candidates": candidates})
                row.update(probabilities=probabilities, metadata=metadata)
            rows.append(row)
        encoded = "[\n" + ",\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows) + "\n]\n"
        artifact.write_text(encoded, "utf-8")
    times = [r["metadata"]["inference_ms"] for r in rows if r["attempted"]]
    latency = {"p50_ms": float(np.percentile(times, 50)), "p95_ms": float(np.percentile(times, 95))}
    for probability, margin, rank, semantic in itertools.product(
            (0.6, 0.75, 0.9), (0.1, 0.2, 0.35), (0.1, 0.18, 0.3), (0.6, 0.9, 1.2)):
        policy = Policy(min_probability=probability, min_margin=margin,
                        rank_penalty=rank, semantic_weight=semantic)
        correct = regressions = repairs = 0
        for row in rows:
            selected = row["baseline"]
            if row["attempted"]:
                result = apply_scores(row["candidates"], row["probabilities"], row["metadata"], policy)
                selected = row["candidates"][result["order"][0]]["text"]
            before, after = row["baseline"] in row["expected"], selected in row["expected"]
            correct += after
            regressions += before and not after
            repairs += not before and after
        choices.append({"name": name, **config, "policy": asdict(policy), **latency,
                        "correct": correct, "n": len(rows), "regressions": regressions, "repairs": repairs})
    best = max((c for c in choices if c["name"] == name),
               key=lambda c: (c["regressions"] <= 3, c["correct"], -c["regressions"]))
    print(name, "best", best["correct"], "/", len(rows), "regressions", best["regressions"], latency, flush=True)
eligible = [c for c in choices if c["regressions"] <= 3 and c["p95_ms"] <= 150]
selected = max(eligible, key=lambda c: (c["correct"], -c["regressions"], -c["p95_ms"]))
(out / "sweep.json").write_text(json.dumps(choices, indent=2), "utf-8")
(out / "selected.json").write_text(json.dumps(selected, indent=2), "utf-8")
print("FROZEN SELECTION", json.dumps(selected), flush=True)
