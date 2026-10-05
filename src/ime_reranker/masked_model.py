"""Chinese MLM as a small local semantic scorer; not a Laya checkpoint.

Mask the changing candidate slots, keeping common character tokens visible.
One encoder pass per distinct candidate length (batched) scores the fixed
candidate set. Scores are relative likelihoods, not calibrated correctness.
"""
import time

import torch
from opencc import OpenCC
from transformers import AutoModelForMaskedLM, AutoTokenizer


class MaskedScorer:
    def __init__(self, path: str, threads: int = 4, mode: str = "slots"):
        torch.set_num_threads(threads)
        self.tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
        self.model = AutoModelForMaskedLM.from_pretrained(path, local_files_only=True).eval()
        self.converter = OpenCC("t2s")
        self.mode = mode

    def _pll(self, context_ids, options):
        tokenizer = self.tokenizer
        sequences, targets, owners, positions = [], [], [], []
        for index, option in enumerate(options):
            for position, token in enumerate(option):
                sequence = [tokenizer.cls_token_id] + context_ids + option + [tokenizer.sep_token_id]
                at = 1 + len(context_ids) + position
                sequence[at] = tokenizer.mask_token_id
                sequences.append(sequence)
                targets.append(token)
                owners.append(index)
                positions.append(at)
        max_len = max(map(len, sequences))
        ids = torch.tensor([seq + [tokenizer.pad_token_id] * (max_len - len(seq)) for seq in sequences])
        hidden = self.model.bert(input_ids=ids, attention_mask=(ids != tokenizer.pad_token_id).long()).last_hidden_state
        # Apply the vocabulary head only at masked positions; full-sequence logits
        # do unused work proportional to context length times vocabulary size.
        logits = self.model.cls(hidden[torch.arange(len(sequences)), positions]).log_softmax(-1)
        values = logits[torch.arange(len(sequences)), targets]
        scores = [sum(values[i].item() for i, owner in enumerate(owners) if owner == index) / len(option)
                  for index, option in enumerate(options)]
        return scores, sum(map(len, sequences))

    @torch.inference_mode()
    def score(self, request):
        start = time.perf_counter()
        tokenizer = self.tokenizer
        context = self.converter.convert(request["context"][-96:] + request.get("prefix", ""))
        context_ids = tokenizer.encode(context, add_special_tokens=False)
        options = [tokenizer.encode(self.converter.convert(c["text"]), add_special_tokens=False)
                   for c in request["candidates"]]
        if self.mode == "pll":
            scores, tokens = self._pll(context_ids, options)
            probs = torch.tensor(scores).softmax(-1).tolist()
            return probs, {"inference_ms": (time.perf_counter() - start) * 1000,
                           "input_tokens": tokens, "backend": "chinese-mlm-pll",
                           "raw_log_likelihoods": scores}
        groups = {}
        for i, ids in enumerate(options):
            if not ids or tokenizer.unk_token_id in ids:
                raise ValueError("candidate cannot be tokenized")
            groups.setdefault(len(ids), []).append(i)
        inputs, details = [], []
        for length, indices in groups.items():
            slots = []
            for position in range(length):
                values = {options[i][position] for i in indices}
                # Even a sole candidate is scored: it must compete across lengths.
                slots.append(next(iter(values)) if len(values) == 1 and len(indices) > 1
                             else tokenizer.mask_token_id)
            # If all options coincide after script conversion, mask all tokens.
            if tokenizer.mask_token_id not in slots:
                slots = [tokenizer.mask_token_id] * length
            seq = [tokenizer.cls_token_id] + context_ids + slots + [tokenizer.sep_token_id]
            inputs.append(seq)
            details.append((indices, len(context_ids) + 1, slots))
        max_len = max(map(len, inputs))
        ids = torch.tensor([seq + [tokenizer.pad_token_id] * (max_len - len(seq)) for seq in inputs])
        attention = (ids != tokenizer.pad_token_id).long()
        logits = self.model(input_ids=ids, attention_mask=attention).logits
        scores = [0.0] * len(options)
        for group, (indices, offset, slots) in enumerate(details):
            masked = [p for p, token in enumerate(slots) if token == tokenizer.mask_token_id]
            logs = logits[group, [offset + p for p in masked]].log_softmax(-1)
            for index in indices:
                targets = torch.tensor([options[index][p] for p in masked])
                scores[index] = logs[torch.arange(len(masked)), targets].mean().item()
        probs = torch.tensor(scores).softmax(-1).tolist()
        return probs, {"inference_ms": (time.perf_counter() - start) * 1000,
                       "input_tokens": sum(map(len, inputs)), "backend": "chinese-mlm",
                       "raw_log_likelihoods": scores}
