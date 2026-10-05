import json
import sys
import time
from pathlib import Path

import torch

from .decision_input import INSTRUCTION, decision_input


class VerdictScorer:
    def __init__(self, path: str, threads: int = 4):
        torch.set_num_threads(threads)
        source = Path(__file__).resolve().parents[2] / "vendor/verdict-source"
        sys.path.insert(0, str(source))
        from core.engine_encoder import DecisionEngine
        from core.primitives import Choice, Option, INSUFFICIENT_EVIDENCE_ID
        from core.formatting import build_model_input, format_query

        self.Choice, self.Option = Choice, Option
        self.abstention_id = INSUFFICIENT_EVIDENCE_ID
        self.build_input, self.format_query = build_model_input, format_query
        self.engine = DecisionEngine(str(Path(path).resolve()), device="cpu", max_length=512)

    def score(self, request):
        state, options = decision_input(request)
        context = json.dumps(state, ensure_ascii=False)
        query = self.Choice(id="candidate", question=INSTRUCTION,
                            options=tuple(self.Option(id=key, description=value)
                                          for key, value in options.items()))
        _, labels, _ = self.format_query(context, query)
        prompt = self.build_input(query.question, context, labels)
        tokens = len(self.engine.tokenizer.encode(prompt))
        if tokens > self.engine.max_length:
            raise ValueError("Verdict would truncate the question at 512 tokens")
        start = time.perf_counter()
        result = self.engine.evaluate(context, [query]).results[0]
        elapsed = (time.perf_counter() - start) * 1000
        # Preserve the abstention mass. Renormalizing candidates could turn an
        # abstention into an apparently confident promotion.
        return [result.probabilities[key] for key in options], {
            "backend": "verdict", "device": "cpu", "inference_ms": elapsed,
            "input_tokens": tokens, "abstention_probability": result.probabilities[self.abstention_id],
            "calibration_status": result.calibration_status}
