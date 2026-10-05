import argparse
import json
import platform
import re
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch

from .policy import Policy, apply_scores
from .scorers import BACKENDS, create_scorer
from .profile import load_profile


def eligible_candidates(row):
    first = row["candidates"][0]
    indices = [i for i, c in enumerate(row["candidates"])
               if (c["start"], c["end"]) == (first["start"], first["end"])]
    return indices, [{**row["candidates"][i], "original_rank": i + 1} for i in indices]


def metrics(rows):
    baseline = [r["baseline_correct"] for r in rows]
    changed_wrong = sum(r["baseline_correct"] and not r["rerank_correct"] for r in rows)
    times = [r["rerank_ms"] for r in rows if r["attempted"]]
    inference = [r["inference_ms"] for r in rows if r["attempted"] and r["reason"] != "model_error"]
    return {"n": len(rows), "rime_top1_accuracy": sum(baseline) / len(rows),
            "rerank_top1_accuracy": sum(r["rerank_correct"] for r in rows) / len(rows),
            "model_only_top1_accuracy": sum(r["model_correct"] for r in rows) / len(rows),
            "regressions_count": changed_wrong,
            "regression_rate_of_originally_correct": changed_wrong / max(1, sum(baseline)),
            "regression_rate_of_all": changed_wrong / len(rows),
            "repaired_count": sum(not r["baseline_correct"] and r["rerank_correct"] for r in rows),
            "eligible_model_calls": len(times),
            "model_errors": sum(r["reason"] == "model_error" for r in rows),
            "top8_target_coverage": sum(any(c["text"] in r["expected"] for c in r["candidates"])
                                        for r in rows) / len(rows),
            "inference_p50_ms": float(np.percentile(inference, 50)),
            "inference_p95_ms": float(np.percentile(inference, 95)),
            "rerank_p50_ms": float(np.percentile(times, 50)),
            "rerank_p95_ms": float(np.percentile(times, 95)),
            "deadline_coverage": {str(ms): sum(t <= ms for t in times) / len(times)
                                  for ms in (30, 50, 80, 120)},
            "deadline_accuracy": {str(ms): sum((r["rerank_correct"] if r["rerank_ms"] <= ms else
                                                r["baseline_correct"]) for r in rows) / len(rows)
                                  for ms in (30, 50, 80, 120)}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="models/laya-multilingual")
    parser.add_argument("--backend", choices=BACKENDS, default="laya")
    parser.add_argument("--mlm-mode", choices=["slots", "pll"], default="slots")
    parser.add_argument("--reverse", action="store_true")
    parser.add_argument("--output", default="results/laya")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--cases", default="data/rime_snapshots.json")
    parser.add_argument("--context-mode", choices=["full", "last-clause"], default="full")
    parser.add_argument("--input-mode", choices=["semantic", "rime-sentence", "rime-aware"], default="semantic")
    parser.add_argument("--prompt", default="baseline")
    parser.add_argument("--top-k", type=int, choices=[2, 4, 8], default=8)
    parser.add_argument("--profile")
    parser.add_argument("--text-mode", choices=["original", "simplified"], default="original")
    args = parser.parse_args()
    policy = load_profile(args)
    if args.input_mode != "semantic" and args.backend not in ("julia", "qwen", "jev"):
        parser.error("Rime input comparisons support Julia, Qwen and Jev")
    cases = json.loads(Path(args.cases).read_text("utf-8"))
    if any(case["code"] != case["preedit"] for case in cases):
        raise ValueError("snapshot code must contain Rime phonetic preedit, not keyboard keys")
    scorer = create_scorer(args)
    def model_request(case, candidates):
        context = case["context"]
        if args.context_mode == "last-clause":
            context = re.split(r"[。！？\n]", context)[-1]
        return {**case, "context": context, "candidates": candidates}
    # Warm-up excluded; all measured calls below are distinct requests with no cache.
    warm = cases[0]
    _, candidates = eligible_candidates(warm)
    for _ in range(3):
        scorer.score(model_request(warm, candidates))
    rows = []
    for case in cases:
        indices, candidates = eligible_candidates(case)
        baseline = case["candidates"][0]["text"]
        attempted = len(candidates) > 1 and bool(case["context"])
        start = time.perf_counter()
        if attempted:
            try:
                probs, metadata = scorer.score(model_request(case, candidates))
                result = apply_scores(candidates, probs, metadata, policy)
                selected = candidates[result["order"][0]]["text"]
                model_selected = candidates[int(np.argmax(probs))]["text"]
            except (ValueError, RuntimeError) as error:
                result = {"reason": "model_error", "order": list(range(len(candidates)))}
                metadata = {"inference_ms": 0, "error": str(error)}
                selected, model_selected = baseline, None
        else:
            result, metadata = {"reason": "bypassed", "order": list(range(len(candidates)))}, {"inference_ms": 0}
            selected = model_selected = baseline
        elapsed = (time.perf_counter() - start) * 1000
        row = {**case, **metadata, **result, "eligible_indices": indices, "baseline": baseline,
               "selected": selected, "model_selected": model_selected,
               "baseline_correct": baseline in case["expected"],
               "rerank_correct": selected in case["expected"],
               "model_correct": model_selected in case["expected"],
               "attempted": attempted, "rerank_ms": elapsed}
        rows.append(row)
        print(case["id"], baseline, "->", selected, "model", model_selected,
              "ms", round(elapsed, 1), result["reason"], flush=True)
    summary = {"hardware": "AMD Ryzen 7 7800X3D; CPU only", "threads": args.threads,
               "python": platform.python_version(), "torch": torch.__version__,
               "policy": asdict(policy), "reverse": args.reverse, "backend": args.backend,
               "model": args.model, "device": "cpu", "cases": args.cases,
               "context_mode": args.context_mode,
               "input_mode": args.input_mode,
               "profile": args.profile, "prompt": args.prompt, "top_k": args.top_k,
               "all": metrics(rows),
               "dev": metrics([r for r in rows if r["split"] == "dev"]) if any(r["split"] == "dev" for r in rows) else None,
               "test": metrics([r for r in rows if r["split"] == "test"])}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
    output.with_suffix(".summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
