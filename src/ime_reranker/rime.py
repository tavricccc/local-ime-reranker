"""Headless real librime harness, isolated from the system IME."""
import ctypes as C
import json
import os
from pathlib import Path


class Traits(C.Structure):
    _fields_ = [("data_size", C.c_int)] + [(name, C.c_char_p) for name in (
        "shared_data_dir", "user_data_dir", "distribution_name", "distribution_code_name",
        "distribution_version", "app_name")] + [("modules", C.POINTER(C.c_char_p)),
        ("min_log_level", C.c_int), ("log_dir", C.c_char_p),
        ("prebuilt_data_dir", C.c_char_p), ("staging_dir", C.c_char_p)]


class Candidate(C.Structure):
    _fields_ = [("text", C.c_char_p), ("comment", C.c_char_p), ("reserved", C.c_void_p)]


class Menu(C.Structure):
    _fields_ = [(x, C.c_int) for x in ("page_size", "page_no", "is_last_page",
                                    "highlighted", "num_candidates")] + [
        ("candidates", C.POINTER(Candidate)), ("select_keys", C.c_char_p)]


class Composition(C.Structure):
    _fields_ = [(x, C.c_int) for x in ("length", "cursor", "sel_start", "sel_end")] + [
        ("preedit", C.c_char_p)]


class Context(C.Structure):
    _fields_ = [("data_size", C.c_int), ("composition", Composition), ("menu", Menu),
               ("preview", C.c_char_p), ("labels", C.POINTER(C.c_char_p))]


class Commit(C.Structure):
    _fields_ = [("data_size", C.c_int), ("text", C.c_char_p)]


class Rime:
    def __init__(self, root=".", workspace="runtime/rime"):
        root = Path(root).resolve()
        work = (root / workspace).resolve()
        work.mkdir(parents=True, exist_ok=True)
        dllpath = root / "vendor/rime/dist/lib/rime.dll"
        self._dll_dir = os.add_dll_directory(str(dllpath.parent))
        self.dll = C.CDLL(str(dllpath))
        signatures = {
            "RimeSetup": (None, [C.POINTER(Traits)]), "RimeInitialize": (None, [C.POINTER(Traits)]),
            "RimeFinalize": (None, []), "RimeStartMaintenance": (C.c_int, [C.c_int]),
            "RimeJoinMaintenanceThread": (None, []), "RimeCreateSession": (C.c_size_t, []),
            "RimeDestroySession": (C.c_int, [C.c_size_t]),
            "RimeSelectSchema": (C.c_int, [C.c_size_t, C.c_char_p]),
            "RimeProcessKey": (C.c_int, [C.c_size_t, C.c_int, C.c_int]),
            "RimeSetOption": (None, [C.c_size_t, C.c_char_p, C.c_int]),
            "RimeSetProperty": (None, [C.c_size_t, C.c_char_p, C.c_char_p]),
            "RimeGetProperty": (C.c_int, [C.c_size_t, C.c_char_p, C.c_char_p, C.c_size_t]),
            "RimeGetContext": (C.c_int, [C.c_size_t, C.POINTER(Context)]),
            "RimeFreeContext": (C.c_int, [C.POINTER(Context)]),
            "RimeSelectCandidate": (C.c_int, [C.c_size_t, C.c_size_t]),
            "RimeCommitComposition": (C.c_int, [C.c_size_t]),
            "RimeGetCommit": (C.c_int, [C.c_size_t, C.POINTER(Commit)]),
            "RimeFreeCommit": (C.c_int, [C.POINTER(Commit)]),
        }
        for name, (ret, args) in signatures.items():
            fn = getattr(self.dll, name)
            fn.restype, fn.argtypes = ret, args
        traits = Traits()
        traits.data_size = C.sizeof(Traits) - C.sizeof(C.c_int)
        traits.shared_data_dir = str(work / "shared").encode()
        traits.user_data_dir = str(work / "user").encode()
        traits.app_name = b"rime.local-ai-poc"
        traits.distribution_version = b"0.17.4"
        traits.min_log_level = 2
        self.dll.RimeSetup(C.byref(traits))
        self.dll.RimeInitialize(C.byref(traits))
        self.dll.RimeStartMaintenance(1)
        self.dll.RimeJoinMaintenanceThread()

    def begin(self, context="", enabled=False, budget_ms=80, schema="bopomofo_ai"):
        session = self.dll.RimeCreateSession()
        if not session or not self.dll.RimeSelectSchema(session, schema.encode()):
            raise RuntimeError("Rime schema deployment failed")
        self.dll.RimeSetOption(session, b"ai_diagnostics", True)
        self.dll.RimeSetOption(session, b"local_ai", enabled)
        self.dll.RimeSetProperty(session, b"ai_context", context.encode("utf-8"))
        self.dll.RimeSetProperty(session, b"ai_budget_ms", str(budget_ms).encode())
        return session

    def type(self, session, keys):
        for ch in keys:
            self.dll.RimeProcessKey(session, ord(ch), 0)

    def snapshot(self, session):
        # Reading context forces Rime's lazy candidate translation/filter to run.
        ctx = Context()
        ctx.data_size = C.sizeof(ctx) - C.sizeof(C.c_int)
        if not self.dll.RimeGetContext(session, C.byref(ctx)):
            raise RuntimeError("Rime context missing")
        try:
            displayed = [(ctx.menu.candidates[i].text or b"").decode("utf-8")
                         for i in range(ctx.menu.num_candidates)]
            preedit = (ctx.composition.preedit or b"").decode("utf-8")
            highlighted = ctx.menu.highlighted
        finally:
            self.dll.RimeFreeContext(C.byref(ctx))
        buffer = C.create_string_buffer(16384)
        if not self.dll.RimeGetProperty(session, b"ai_snapshot", buffer, len(buffer)):
            raise RuntimeError("Lua filter did not produce a snapshot")
        return {**json.loads(buffer.value), "displayed": displayed, "preedit": preedit,
                "model_pool": json.loads(self.property(session, "ai_pool_snapshot") or "[]"),
                "highlighted": highlighted,
                "ai_status": self.property(session, "ai_status"),
                "ai_elapsed_ms": self.property(session, "ai_elapsed_ms")}

    def property(self, session, name):
        buffer = C.create_string_buffer(16384)
        self.dll.RimeGetProperty(session, name.encode(), buffer, len(buffer))
        return buffer.value.decode("utf-8")

    def commit(self, session, index=0):
        self.dll.RimeSelectCandidate(session, index)
        self.dll.RimeCommitComposition(session)
        result = Commit()
        result.data_size = C.sizeof(result) - C.sizeof(C.c_int)
        if not self.dll.RimeGetCommit(session, C.byref(result)):
            raise RuntimeError("Rime did not commit")
        try:
            return result.text.decode("utf-8")
        finally:
            self.dll.RimeFreeCommit(C.byref(result))

    def end(self, session):
        self.dll.RimeDestroySession(session)

    def close(self):
        self.dll.RimeFinalize()
