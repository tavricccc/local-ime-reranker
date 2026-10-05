"""Process-owned Windows readiness event; disappears when the worker exits."""
import ctypes as C

EVENT_NAME = "Local\\LocalImeRerankerReady"
kernel = C.WinDLL("kernel32", use_last_error=True)
kernel.CreateEventW.argtypes = [C.c_void_p, C.c_int, C.c_int, C.c_wchar_p]
kernel.CreateEventW.restype = C.c_void_p
kernel.ResetEvent.argtypes = [C.c_void_p]
kernel.CloseHandle.argtypes = [C.c_void_p]


class ReadySignal:
    def __enter__(self):
        self.handle = kernel.CreateEventW(None, True, True, EVENT_NAME)
        if not self.handle:
            raise C.WinError(C.get_last_error())
        return self

    def __exit__(self, *_):
        kernel.ResetEvent(self.handle)
        kernel.CloseHandle(self.handle)
