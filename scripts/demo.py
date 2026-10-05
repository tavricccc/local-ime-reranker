"""Real Rime + Julia demo: contextual decisions and a missing-candidate limit."""
import json
from pathlib import Path

from ime_reranker.phonetics import bopomofo_keys
from ime_reranker.rime import Rime

cases = json.loads(Path("data/context_cases.json").read_text("utf-8"))
cases += json.loads(Path("data/validation_cases.json").read_text("utf-8"))
cases += json.loads(Path("data/holdout_cases.json").read_text("utf-8"))
rime = Rime()
try:
    for case in cases:
        if case["id"] not in ("h-remote-city", "h-remote-program", "h-trial", "h-phrase-program"):
            continue
        session = rime.begin(case["context"], True, 120)
        try:
            rime.type(session, bopomofo_keys(case["reading"]))
            snapshot = rime.snapshot(session)
            print(json.dumps({"前文": case["context"], "注音": snapshot["preedit"],
                              "Rime原始": [c["text"] for c in snapshot["candidates"]],
                              "實際顯示": snapshot["displayed"], "預期": case["expected"],
                              "狀態": snapshot["ai_status"]}, ensure_ascii=False, indent=2))
        finally:
            rime.end(session)
finally:
    rime.close()
