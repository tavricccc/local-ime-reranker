"""Bounded loopback worker. No input logging; hosted Jev is an explicit backend."""
import argparse
import json
import socketserver
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from .policy import Policy, apply_scores
from .readiness import ReadySignal
from .scorers import BACKENDS, create_scorer
from .profile import load_profile
from .decision_input import instruction
from .telemetry import Telemetry


class Worker:
    def __init__(self, scorer, policy: Policy, telemetry=None):
        self.scorer, self.policy = scorer, policy
        self.telemetry = telemetry
        self.lock = threading.Lock()
        self.cache = OrderedDict()
        # Keep all tensor work on one warmed thread; new socket-handler threads
        # otherwise pay CPU thread-pool startup and make tail latency erratic.
        self.inference = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ime-model")

    def process(self, request: dict) -> dict:
        candidates = request["candidates"]
        if not (1 <= len(candidates) <= 16) or len(request["context"]) > 256:
            raise ValueError("oversized request")
        if any(len(c["text"]) > 128 for c in candidates):
            raise ValueError("oversized candidate")
        # A semantic-only model does not consume quality. A Rime-aware model
        # does, so its cache must also change when the dictionary scores change.
        model_candidates = ([{k: c[k] for k in ("text", "quality", "original_rank") if k in c}
                             for c in candidates] if getattr(self.scorer, "uses_rime_prior", False)
                            else [c["text"] for c in candidates])
        key = json.dumps([request["context"], request["code"], request.get("prefix", ""),
                          model_candidates, request.get("allow_partial", False),
                          request.get("raw_input", ""), [(c.get("start"), c.get("end")) for c in candidates],
                          instruction("rime-aware")], ensure_ascii=False)
        if not self.lock.acquire(blocking=False):
            if self.telemetry:
                self.telemetry.event("busy", candidates=len(candidates))
            return {"order": list(range(len(candidates))), "reason": "busy"}
        started = time.perf_counter()
        if self.telemetry:
            self.telemetry.begin()
        try:
            hit = key in self.cache
            if hit:
                probs, metadata = self.cache[key]
                self.cache.move_to_end(key)
            else:
                probs, metadata = self.inference.submit(self.scorer.score, request).result()
                self.cache[key] = (probs, metadata)
                if len(self.cache) > 128:
                    self.cache.popitem(last=False)
            result = apply_scores(candidates, probs, metadata, self.policy)
            if self.telemetry:
                self.telemetry.event("cache" if hit else "decision", candidates=len(candidates),
                                     inference_ms=None if hit else round(metadata.get("inference_ms", 0), 2),
                                     total_ms=round((time.perf_counter() - started) * 1000, 2),
                                     reason=result["reason"], winner=result["order"][0] + 1,
                                     partial=request.get("allow_partial", False) and candidates[result["order"][0]].get("end", 0) < len(request.get("raw_input", "")),
                                     coverage=[c.get("end", 0) - c.get("start", 0) for c in candidates],
                                     device=metadata.get("device", "cpu"),
                                     margin=round(result.get("margin", 0), 3))
            return {**result, **metadata, "cache_hit": hit}
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
            if self.telemetry:
                self.telemetry.event("error", error=type(error).__name__,
                                     total_ms=round((time.perf_counter() - started) * 1000, 2))
            raise
        finally:
            if self.telemetry:
                self.telemetry.end()
            self.lock.release()

    def close(self):
        self.inference.shutdown(wait=True)
        if hasattr(self.scorer, "close"):
            self.scorer.close()


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(1)
        try:
            line = self.rfile.readline(16385)
            if len(line) > 16384:
                raise ValueError("oversized packet")
            request = json.loads(line)
            if request.get("diagnostic") == "status":
                self.wfile.write((json.dumps(self.server.worker.telemetry.snapshot()) + "\n").encode())
                return
            if request.get("diagnostic") == "reset_cache":
                with self.server.worker.lock:
                    self.server.worker.cache.clear()
                self.wfile.write(b"{\"ready\":true}\n")
                return
            result = self.server.worker.process(request)
            # Lua needs only a validated permutation. Diagnostic clients get JSON.
            if request.get("wire") == "indices":
                output = ",".join(str(i + 1) for i in result["order"]) + "\n"
            else:
                output = json.dumps(result, ensure_ascii=False) + "\n"
            self.wfile.write(output.encode("utf-8"))
        except (ValueError, KeyError, TypeError):
            self.wfile.write(b"error\n")
        except (OSError, RuntimeError):
            # Disconnected/timed-out client or backend failure must not kill the worker.
            return


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class ImeTelemetryHandler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            message = json.loads(self.request[0][:512])
            self.server.telemetry.event("ime", elapsed_ms=float(message["elapsed_ms"]),
                                        budget_ms=int(message["budget_ms"]),
                                        reason="returned" if message["received"] else "timeout_or_disconnect")
        except (ValueError, KeyError, TypeError):
            return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="models/laya-multilingual")
    parser.add_argument("--backend", choices=BACKENDS, default="laya")
    parser.add_argument("--mlm-mode", choices=["slots", "pll"], default="slots")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--reverse", action="store_true")
    parser.add_argument("--input-mode", choices=["semantic", "rime-sentence", "rime-aware"], default="semantic")
    parser.add_argument("--prompt", default="baseline")
    parser.add_argument("--top-k", type=int, choices=[2, 4, 8, 16], default=8)
    parser.add_argument("--profile")
    parser.add_argument("--text-mode", choices=["original", "simplified"], default="original")
    args = parser.parse_args()
    policy = load_profile(args)
    if args.input_mode != "semantic" and args.backend not in ("julia", "qwen", "jev"):
        parser.error("Rime input comparisons support Julia, Qwen and Jev")
    telemetry = Telemetry(args.backend, args.model)
    try:
        scorer = create_scorer(args)
    except Exception as error:
        telemetry.state = "error"
        telemetry.write_state()
        raise
    worker = Worker(scorer, policy, telemetry)
    try:
        if args.backend != "jev":
            scorer.score({"context": "", "code": "test", "candidates": [
                {"text": "測試", "quality": 0}, {"text": "側式", "quality": 0}]})
        with Server(("127.0.0.1", 18963), Handler) as server, socketserver.UDPServer(("127.0.0.1", 18964), ImeTelemetryHandler) as ime_server, ReadySignal():
            server.worker = worker
            ime_server.telemetry = telemetry
            telemetry.state = "ready"
            telemetry.write_state()
            telemetry.event("ready")
            threading.Thread(target=ime_server.serve_forever, daemon=True).start()
            print(f"ready: 127.0.0.1:18963 ({args.backend})", flush=True)
            try:
                server.serve_forever()
            finally:
                ime_server.shutdown()
    finally:
        worker.close()


if __name__ == "__main__":
    main()
