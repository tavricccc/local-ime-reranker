"""Small real-checkpoint probe; neither a benchmark nor a mock model."""
import json
import statistics
import time

import laya
import torch

torch.set_num_threads(4)
start = time.perf_counter()
agent = laya.load("models/laya-multilingual", device="cpu")
print("load_ms", round((time.perf_counter() - start) * 1000), flush=True)
questions = {"candidate": {
    "type": "choice",
    "instructions": "Which Traditional Chinese continuation best fits the preceding context?",
    "criteria": {"c0": "這題接下來可以做因式分解", "c1": "這題接下來可以做陰式分解", "c2": "這題接下來可以做飲食分解"},
}}
times = []
for i in range(8):
    start = time.perf_counter()
    result = agent.predict("我們正在解數學的二次多項式。", questions)
    ms = (time.perf_counter() - start) * 1000
    times.append(ms)
    print(json.dumps({"iteration": i, "ms": round(ms, 2), "result": result}, ensure_ascii=False), flush=True)
print("warm_median_ms", statistics.median(times[2:]), flush=True)
