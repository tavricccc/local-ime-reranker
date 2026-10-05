"""Bounded operational telemetry, without input text, prompts or credentials."""
import json
import os
import threading
import time
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path


def percentile(values, fraction):
    ordered = sorted(values)
    return round(ordered[round((len(ordered) - 1) * fraction)], 2) if ordered else None


class Telemetry:
    def __init__(self, backend, model):
        self.backend, self.model = backend, model
        self.started = time.monotonic()
        self.lock = threading.Lock()
        self.events = deque(maxlen=100)
        self.inference = deque(maxlen=256)
        self.ime_latency = deque(maxlen=256)
        self.counts = Counter()
        self.active = 0
        self.sequence = 0
        self.state = "loading"
        self.state_path = Path("runtime/windows/model-status.json")
        self.write_state()

    def write_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"pid": os.getpid(), "backend": self.backend,
                                        "model": self.model, "state": self.state}), "utf-8")
        temporary.replace(self.state_path)

    def event(self, kind, **fields):
        with self.lock:
            self.sequence += 1
            row = {"id": self.sequence, "time": datetime.now(timezone.utc).isoformat(),
                   "kind": kind, **fields}
            self.events.append(row)
            self.counts[kind] += 1
            if fields.get("inference_ms") is not None:
                self.inference.append(fields["inference_ms"])
            if kind == "ime":
                self.ime_latency.append(fields["elapsed_ms"])
        return row

    def begin(self):
        with self.lock:
            self.active += 1

    def end(self):
        with self.lock:
            self.active -= 1

    def snapshot(self):
        with self.lock:
            return {"pid": os.getpid(), "backend": self.backend, "model": self.model,
                    "state": "inference" if self.active else self.state,
                    "uptime_s": round(time.monotonic() - self.started),
                    "counts": dict(self.counts), "events": list(self.events),
                    "inference_p50_ms": percentile(self.inference, .50),
                    "inference_p95_ms": percentile(self.inference, .95),
                    "ime_p50_ms": percentile(self.ime_latency, .50),
                    "ime_p95_ms": percentile(self.ime_latency, .95)}
