"""Native Weasel pipe protocol for isolated engine/style integration verification.

This is a test client for our staged Weasel server. It never injects text into
Microsoft/ASUS IMEs or controls another application's keyboard/clipboard.
"""
import ctypes as C
import os
import struct
from ctypes import wintypes as W

K = C.WinDLL("kernel32", use_last_error=True)
K.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE]
K.CreateFileW.restype = W.HANDLE
K.WriteFile.argtypes = [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p]
K.ReadFile.argtypes = [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p]
K.SetNamedPipeHandleState.argtypes = [W.HANDLE, C.POINTER(W.DWORD), C.c_void_p, C.c_void_p]
K.CloseHandle.argtypes = [W.HANDLE]


class WeaselClient:
    def __init__(self):
        path = rf"\\.\pipe\{os.environ['USERNAME']}\WeaselNamedPipe"
        self.pipe = K.CreateFileW(path, 0xc0000000, 0, None, 3, 0, None)
        if self.pipe == C.c_void_p(-1).value:
            raise C.WinError(C.get_last_error())
        mode = W.DWORD(2)
        if not K.SetNamedPipeHandleState(self.pipe, C.byref(mode), None, None):
            raise C.WinError(C.get_last_error())
        self.session = 0
        self.session, self.initial = self.send(0x8002, body="action=session\nsession.client_app=local-ime-preview.exe\nsession.client_type=tsf\n.\n")
        if not self.session:
            raise RuntimeError("staged Weasel did not create a session")

    def send(self, command, param=0, session=None, body=""):
        data = struct.pack("<III", command, param, self.session if session is None else session) + body.encode("utf-16le")
        count = W.DWORD()
        if not K.WriteFile(self.pipe, data, len(data), C.byref(count), None):
            raise C.WinError(C.get_last_error())
        header = C.create_string_buffer(4)
        ok = K.ReadFile(self.pipe, header, 4, C.byref(count), None)
        response = ""
        if not ok:
            if C.get_last_error() != 234:
                raise C.WinError(C.get_last_error())
            buffer = C.create_string_buffer(65536)
            if not K.ReadFile(self.pipe, buffer, len(buffer), C.byref(count), None):
                raise C.WinError(C.get_last_error())
            response = buffer.raw[:count.value].decode("utf-16le").rstrip("\0")
        return struct.unpack("<I", header.raw)[0], response

    def key(self, code, mask=0):
        return self.send(0x8004, code | mask << 16)

    def type(self, keys):
        replies = []
        for key in keys:
            replies.append(self.key(ord(key)))
        return replies[-1]

    def commit(self):
        return self.key(0xff0d)

    def toggle_ai(self):
        return self.key(ord("a"), 4 | 8)  # Control + Alt

    def focus(self, x=350, y=300, height=24):
        high = int(height >= 128 or not -2048 <= x < 2048 or not -2048 <= y < 2048)
        value = high << 31 | min(127, height >> high) << 24 | ((y >> high) & 0xfff) << 12 | ((x >> high) & 0xfff)
        self.send(0x8008, value)
        self.send(0x8006)

    def close(self):
        self.send(0x8003)
        K.CloseHandle(self.pipe)
