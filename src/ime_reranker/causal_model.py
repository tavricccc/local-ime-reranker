"""AnyJev-style next-token decisions: one prefill, zero decoding steps."""
import json
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from .decision_input import decision_input, instruction


class CausalScorer:
    def __init__(self, path: str, threads: int = 4, input_mode="semantic"):
        torch.set_num_threads(threads)
        self.tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            path, local_files_only=True, dtype=torch.float32, attn_implementation="sdpa").eval()
        self.letters = "ABCDEFGH"
        ids = [self.tokenizer.encode(letter, add_special_tokens=False) for letter in self.letters]
        if any(len(value) != 1 for value in ids):
            raise ValueError("choice letters must each be a single token")
        self.token_ids = torch.tensor([value[0] for value in ids])
        self.input_mode = input_mode
        self.uses_rime_prior = input_mode == "rime-aware"

    @torch.inference_mode()
    def score(self, request):
        state, options = decision_input(request, self.input_mode)
        choices = dict(zip(self.letters, options.values()))
        heading = "前文、注音與Rime判斷：" if self.uses_rime_prior else "前文與注音："
        messages = [
            {"role": "system", "content": "請根據上下文選擇續文，僅回答一個候選代號英文字母。"},
            {"role": "user", "content": instruction(self.input_mode) + "\n" + heading + "\n" +
             json.dumps(state, ensure_ascii=False) + "\n候選續文：\n" +
             "\n".join(f"{key}: {value}" for key, value in choices.items())}]
        start = time.perf_counter()
        inputs = self.tokenizer.apply_chat_template(messages, enable_thinking=False,
                                                   add_generation_prompt=True, return_dict=True,
                                                   return_tensors="pt")
        # Only the last hidden state needs a vocabulary projection, and only
        # the offered letters need logits. No generate() or token sampling.
        hidden = self.model.model(**inputs, use_cache=False).last_hidden_state[:, -1, :]
        weights = self.model.lm_head.weight[self.token_ids[:len(choices)]]
        probabilities = (hidden @ weights.T).softmax(-1)[0].tolist()
        elapsed = (time.perf_counter() - start) * 1000
        return probabilities, {"backend": "qwen", "device": "cpu", "inference_ms": elapsed,
                               "input_tokens": inputs["input_ids"].shape[1],
                               "decode_steps": 0, "temperature": 1.0,
                               "input_mode": self.input_mode}
