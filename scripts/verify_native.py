"""Real x86 Weasel/librime/Lua/bridge smoke test via its public pipe API.

This backend integration check does not substitute for native TSF UI testing.
It commits only synthetic text into a disposable engine session, not an editor.
"""
import json
import socket
import time
from pathlib import Path

from ime_reranker.phonetics import bopomofo_keys
from ime_reranker.weasel_client import WeaselClient


def committed(reply):
    return next(line[7:] for line in reply[1].splitlines() if line.startswith("commit="))


def run(enabled):
    client = WeaselClient()
    try:
        # The staged schema resets AI on. Disable it during context entry so
        # both runs contain exactly the same real Rime-produced Chinese history.
        client.toggle_ai()
        words = []
        for reading in ("ㄓㄥˋ ㄈㄨˇ", "ㄍㄨㄢ ㄩㄢˊ", "ㄩㄥˇ ㄧㄡˇ", "ㄏㄣˇ ㄉㄚˋ", "ㄉㄜ"):
            client.type(bopomofo_keys(reading))
            words.append(committed(client.commit()))
        if enabled:
            client.toggle_ai()
        with socket.create_connection(("127.0.0.1", 18963)) as connection:
            connection.sendall(b'{"diagnostic":"reset_cache"}\n')
            connection.recv(256)
        times = []
        for key in bopomofo_keys("ㄑㄩㄢˊ ㄌㄧˋ"):
            start = time.perf_counter()
            _, page = client.key(ord(key))
            times.append((time.perf_counter() - start) * 1000)
        selected = committed(client.commit())
        return {"enabled": enabled, "context": "".join(words), "selected": selected,
                "final_key_ms": times[-1], "updates_ms": times,
                "candidate_response": page, "style_response": client.initial}
    finally:
        client.close()


rows = [run(False), run(True)]
output = Path("runtime/windows/native-smoke.json")
output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
for row in rows:
    print(row["enabled"], row["context"], row["selected"], round(row["final_key_ms"], 1))
assert rows[0]["context"] == rows[1]["context"]
assert rows[1]["selected"] == "權力", "native AI integration did not improve this smoke case"
# Repeating this smoke test can teach 權力 to the genuine user dictionary, so
# the baseline may already be correct. The first fresh-dictionary run is saved
# separately as results/native-smoke.json; never overwrite that measurement.
