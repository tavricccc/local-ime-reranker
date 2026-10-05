"""Shared semantic task; adapters retain each checkpoint's native serialization."""
import re
from .settings import prompt_path
from .prompts import PROMPTS, TAIWAN_RULES
from .phonetics import SYMBOLS, KEYS

INSTRUCTION = TAIWAN_RULES + PROMPTS["baseline"]
RIME_INSTRUCTION = (INSTRUCTION + "Rime原句與原始排名反映詞頻及個人詞庫；quality是內部分數，"
                    "不是正確機率。比較換入候選後的句子，前文明確支持其他續文時才修正，否則保留原句。")


def decision_input(request, mode="semantic"):
    context = request["context"][-96:]
    clause = re.split(r"[。！？\n]", context)[-1]
    options = {f"c{i}": clause + request.get("prefix", "") + candidate["text"]
               for i, candidate in enumerate(request["candidates"])}
    state = {"preceding_text": context, "phonetic_input": request["code"]}
    if request.get("allow_partial"):
        raw = request["raw_input"]
        phonetics = str.maketrans(KEYS, SYMBOLS)
        state["rime_original_conversion"] = request["candidates"][0]["text"]
        state["phonetic_keys"] = raw.translate(phonetics)
        state["scope_format"] = "[涵蓋鍵數, 剩餘鍵數, Rime原始順位]；剩餘注音留待下一次選字"
        state["candidate_scopes"] = {
            f"c{i}": [c["end"] - c["start"], len(raw) - c["end"], c.get("original_rank", i + 1)]
            for i, c in enumerate(request["candidates"])
        }
        # Context is already in state; repeating it in 16 options wastes the
        # local model's head budget and favors shorter clauses by truncation.
        options = {f"c{i}": ("[完整] " if c["end"] >= len(raw) else "[前段] ") + c["text"]
                   for i, c in enumerate(request["candidates"])}
    if mode in ("rime-sentence", "rime-aware"):
        state["rime_original_sentence"] = clause + request.get("prefix", "") + request["candidates"][0]["text"]
    if mode == "rime-aware":
        state["rime_original_conversion"] = request["candidates"][0]["text"]
        state["rime_candidates"] = [
            {"text": candidate["text"], "original_rank": candidate.get("original_rank", i + 1),
             "quality": candidate["quality"]}
            for i, candidate in enumerate(request["candidates"])]
    return state, options


def instruction(mode, prompt="baseline"):
    custom = prompt_path()
    if custom.exists():
        return custom.read_text("utf-8-sig").strip()
    base = TAIWAN_RULES + PROMPTS[prompt]
    if mode == "rime-sentence":
        return base + "Rime原句是初步轉換，可能有同音誤選。比較換入候選後的句子，依前文判斷。"
    if mode == "rime-aware":
        return base + "Rime原句與原始排名反映詞頻及個人詞庫；quality是內部分數，不是正確機率。比較換入候選後的句子，前文明確支持其他續文時才修正，否則保留原句。"
    return base
