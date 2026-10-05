"""Replay synthetic multi-syllable input with a forced candidate permutation."""
import json
import shutil
import socketserver
import tempfile
import threading
from pathlib import Path

from ime_reranker.phonetics import bopomofo_keys
from ime_reranker.readiness import ReadySignal
from ime_reranker.rime import Rime


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        row = json.loads(self.rfile.readline())
        n = len(row["candidates"])
        order = list(range(n, 0, -1))
        self.wfile.write((",".join(map(str, order)) + "\n").encode())


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


workspace = Path(tempfile.mkdtemp(prefix="rime-composition-"))
shutil.copytree("runtime/rime/shared", workspace / "shared")
shutil.copytree("runtime/rime/user/lua", workspace / "user/lua")
shutil.copy2("rime/lua/local_ai.lua", workspace / "user/lua/local_ai.lua")
cases = {
    "sentence": bopomofo_keys("ㄖㄢˊ ㄏㄡˋ ㄨㄛˇ ㄈㄚ ㄒㄧㄢˋ"),
    "sentence-toneless": "b0c.jiz8vu0",
    "partial": "b0c.4jiz8vu0",
    "selected-prefix": bopomofo_keys("ㄖㄢˊ ㄏㄡˋ ㄨㄛˇ ㄈㄚ ㄒㄧㄢˋ"),
}
rows = []
with Server(("127.0.0.1", 18963), Handler) as server, ReadySignal():
    threading.Thread(target=server.serve_forever, daemon=True).start()
    rime = Rime(workspace=str(workspace))
    try:
        for name, keys in cases.items():
            for enabled in (False, True):
                session = rime.begin("我們正在討論輸入法。我剛才測試很多次，", enabled, 150)
                try:
                    for index, key in enumerate(keys):
                        rime.type(session, key)
                        snapshot = rime.snapshot(session)
                        rows.append({"case": name, "enabled": enabled,
                                     "input": keys[:index+1], **snapshot})
                        if name == "selected-prefix" and index == 5:
                            rime.dll.RimeSelectCandidate(session, 1)
                    print(name, enabled, snapshot["preedit"], snapshot["highlighted"], snapshot["ai_status"])
                finally:
                    rime.end(session)
    finally:
        rime.close()
        server.shutdown()
Path("runtime/composition-diagnosis.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
