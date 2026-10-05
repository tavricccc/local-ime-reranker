import json
import sys
import time
from pathlib import Path

import torch
from safetensors.torch import load_file
from transformers import AutoConfig, AutoModel, AutoTokenizer

from .decision_input import INSTRUCTION, decision_input


class NanoJevScorer:
    def __init__(self, path: str, threads: int = 4):
        torch.set_num_threads(threads)
        root = Path(path).resolve()
        sys.path.insert(0, str(root / "source/scripts"))
        # Reuse the checkpoint's exact architecture and serialization. The
        # official CLI only accepts CUDA; this adapter loads those same weights
        # in FP32 on CPU without altering the upstream source.
        from predict_toy_decisions import load_decision_model_class, prepare_examples

        config = json.loads((root / "config.json").read_text("utf-8"))
        self.tokenizer = AutoTokenizer.from_pretrained(root / "tokenizer", local_files_only=True)
        body_config = AutoConfig.from_pretrained(root / "backbone_config", local_files_only=True)
        body = AutoModel.from_config(body_config, attn_implementation="sdpa").float()
        self.model = load_decision_model_class()(body, config["set_head"])
        self.model.load_state_dict(load_file(str(root / "best.safetensors")), strict=True)
        self.model.eval()
        self.prepare = prepare_examples
        self.max_length = config["max_length"]
        self.temperature = config["temperature"]

    @torch.inference_mode()
    def score(self, request):
        state, options = decision_input(request)
        payload = {"states": [{"id": "ime", "state": state, "questions": {
            "candidate": {"type": "choice", "instructions": INSTRUCTION, "criteria": options}}}]}
        start = time.perf_counter()
        examples = self.prepare(payload, self.tokenizer, self.max_length)
        logits, _ = self.model(examples, self.tokenizer.pad_token_id)
        probabilities = (logits[0, :len(options)] / self.temperature).softmax(-1).tolist()
        elapsed = (time.perf_counter() - start) * 1000
        return probabilities, {"backend": "nanojev", "device": "cpu", "inference_ms": elapsed,
                               "candidate_paths": len(options), "temperature": self.temperature,
                               "input_tokens": sum(len(x) for x in examples[0]["leaf_tokens"])}
