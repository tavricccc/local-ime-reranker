"""Two structural checks: partial Enter retains input; full Enter commits all."""
import ctypes as C
import shutil
from pathlib import Path

from ime_reranker.rime import Commit, Rime
from stage_onion_plus import stage

shutil.copytree('runtime/rime/shared', 'runtime/slice-smoke/shared', dirs_exist_ok=True)
stage(Path("runtime/slice-smoke/user"))
rime = Rime(workspace="runtime/slice-smoke")
try:
    for partial in (True, False):
        session = rime.begin(schema="bopomo_onionplus")
        try:
            rime.type(session, "b06c.4ji3z8 vu04")
            initial = rime.snapshot(session)
            if partial:
                rime.dll.RimeProcessKey(session, 0xff54, 0)
            rime.dll.RimeProcessKey(session, 0xff0d, 0)
            committed = Commit()
            committed.data_size = C.sizeof(committed) - C.sizeof(C.c_int)
            assert rime.dll.RimeGetCommit(session, C.byref(committed)), "Enter did not commit"
            text = committed.text.decode("utf-8")
            rime.dll.RimeFreeCommit(C.byref(committed))
            assert text == ("然後我" if partial else "然後我發現"), text
            if partial:
                remaining = rime.snapshot(session)
                assert remaining["candidates"][0]["text"] == "發現", remaining["candidates"]
            print("Partial Enter retained the rest" if partial else "Full Enter committed the sentence")
        finally:
            rime.end(session)
finally:
    rime.close()
