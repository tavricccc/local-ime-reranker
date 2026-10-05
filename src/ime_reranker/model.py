import time
import re

import laya
import torch

from .decision_input import INSTRUCTION


class LayaScorer:
    def __init__(self, path: str, threads: int = 4, reverse: bool = False):
        torch.set_num_threads(threads)
        self.agent = laya.load(path, device="cpu")
        self.agent.cfg["head_max_len"] = 512
        self.reverse = reverse

    def score(self, request: dict) -> tuple[list[float], dict]:
        candidates = request["candidates"]
        context = request["context"][-96:]
        prefix = request.get("prefix", "")
        # Past complete sentences live in shared state; only the current clause
        # is repeated per option so the changing word cannot be truncated away.
        clause = re.split(r"[。！？\n]", context)[-1]
        options = {f"c{i}": clause + prefix + c["text"] for i, c in enumerate(candidates)}
        # Upstream caps every option at 48 tokens even with a larger head budget.
        if any(len(self.agent.tok.encode(" " + key + ": " + value, add_special_tokens=False)) > 48
               for key, value in options.items()):
            raise ValueError("Laya would truncate a sentence option at 48 tokens")
        instruction = INSTRUCTION
        questions = {"candidate": {"type": "choice", "instructions": instruction,
                                   "criteria": options}}
        if self.reverse:
            questions["reverse"] = {"type": "choice", "instructions": instruction,
                                    "criteria": dict(reversed(list(options.items())))}
        state = {"preceding_text": context, "phonetic_input": request["code"]}
        start = time.perf_counter()
        output = self.agent.predict(state, questions)
        elapsed = (time.perf_counter() - start) * 1000
        if output["usage"]["truncated"]:
            raise ValueError("candidate question exceeded checkpoint token budget")
        probs = [output["answers"]["candidate"]["probabilities"][f"c{i}"] for i in range(len(candidates))]
        if self.reverse:
            other = output["answers"]["reverse"]["probabilities"]
            probs = [(p + other[f"c{i}"]) / 2 for i, p in enumerate(probs)]
        return probs, {"inference_ms": elapsed, "input_tokens": output["usage"]["input_tokens"],
                       "backend": "laya", "reverse": self.reverse}
