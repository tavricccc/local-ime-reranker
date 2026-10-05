import sys
import time
from pathlib import Path

import torch
from opencc import OpenCC

from .decision_input import decision_input, instruction


class JuliaScorer:
    def __init__(self, path: str, threads: int = 4, reverse: bool = False, input_mode="semantic",
                 prompt="baseline", top_k=8, text_mode="original"):
        torch.set_num_threads(threads)
        # The pinned official HF snapshot includes its matching Python runtime.
        sys.path.insert(0, str(Path(path).resolve()))
        from julia import load_model

        self.engine = load_model(path, device="cpu", strict_encoding=True,
                                 max_length=1024, head_length=512,
                                 encoding_cache=0, token_cache=0)
        # The snapshot's optional encoder specialization targets transformers
        # 5.0 private APIs. Use the public HF forward with our pinned 5.18 runtime;
        # serialization, weights and marker-only decision head stay identical.
        encoder = self.engine.model.encoder
        encoder.forward = type(encoder).forward.__get__(encoder, type(encoder))
        self.engine.encoder_specialized = False
        # Julia configure() defaults to 4 threads; honor our explicit setting
        # after its initialization as well.
        torch.set_num_threads(threads)
        self.reverse = reverse
        self.input_mode = input_mode
        self.uses_rime_prior = input_mode == "rime-aware"
        self.prompt, self.top_k = prompt, top_k
        self.text_mode = text_mode
        self.converter = OpenCC("t2s") if text_mode == "simplified" else None

    def score(self, request):
        request = {**request, "candidates": request["candidates"][:self.top_k]}
        state, options = decision_input(request, self.input_mode)
        if self.converter:
            import json
            state = json.loads(self.converter.convert(json.dumps(state, ensure_ascii=False)))
            options = {key: self.converter.convert(value) for key, value in options.items()}
        questions = {"candidate": {"type": "choice", "instructions": instruction(self.input_mode, self.prompt),
                                   "criteria": options}}
        if self.reverse:
            questions["reverse"] = {**questions["candidate"],
                                    "criteria": dict(reversed(list(options.items())))}
        start = time.perf_counter()
        output = self.engine.predict(state=state, questions=questions)
        elapsed = (time.perf_counter() - start) * 1000
        probabilities = output["answers"]["candidate"]["probabilities"]
        if self.reverse:
            other = output["answers"]["reverse"]["probabilities"]
            agreement = max(probabilities, key=probabilities.get) == max(other, key=other.get)
            probabilities = {key: (value + other[key]) / 2 for key, value in probabilities.items()}
        else:
            agreement = True
        return [probabilities[key] for key in options], {
            "backend": "julia", "device": "cpu", "inference_ms": elapsed,
            "reverse": self.reverse, "input_mode": self.input_mode,
            "prompt": self.prompt, "scored_count": len(options), "top_k": self.top_k,
            "torch_threads": torch.get_num_threads(), "text_mode": self.text_mode,
            "order_agreement": agreement}
