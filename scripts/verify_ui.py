"""Native pipe/icon smoke test; does not foreground an editor or capture UI."""
import ctypes as C
import json
from pathlib import Path

from ime_reranker.weasel_client import WeaselClient

ROOT = Path(__file__).resolve().parents[1]
user32 = C.WinDLL("user32", use_last_error=True)
user32.LoadImageW.argtypes = [C.c_void_p, C.c_wchar_p, C.c_uint, C.c_int, C.c_int, C.c_uint]
user32.LoadImageW.restype = C.c_void_p
user32.DestroyIcon.argtypes = [C.c_void_p]
icons = []
for name in ("chinese", "english"):
    path = ROOT / "runtime/windows/user/icons" / (name + ".ico")
    for size in (16, 24, 32, 48):
        handle = user32.LoadImageW(None, str(path), 1, size, size, 0x10)
        assert handle, f"Cannot load {name} at {size}px"
        user32.DestroyIcon(handle)
        icons.append({"icon": name, "size": size, "loaded": True})
client = WeaselClient()
try:
    client.toggle_ai()
    client.type("b06c.4")
    client.key(0xffe1)
    client.key(0xffe1, 0x4000)
    off = client.type("ji3z8 vu04")[1]
    assert "ㄖㄢˊ ㄏㄡˋ ㄨㄛˇ ㄈㄚˉ ㄒㄧㄢˋ" in off
    assert "AI 關" in off and "⇧" not in off
    selected = client.key(0xff54)[1]
    client.toggle_ai()
    on = client.key(0xff54)[1]
    assert "AI 開" in on
    client.key(0xff1b)
    first_page = client.type("g4")[1]
    second_page = client.key(0xff56)[1]
    assert "AI 開" in first_page and "AI 開" in second_page
    assert "chinese.ico" in client.initial and "english.ico" in client.initial
    output = {"icons": icons, "style_response": client.initial,
              "shift_keeps_phonetics": off, "manual_selection": selected,
              "ai_on": on, "first_page": first_page, "second_page": second_page,
              "visual_capture": False}
finally:
    client.close()
(ROOT / "results/ui-selection-smoke.json").write_text(
    json.dumps(output, ensure_ascii=False, indent=2), "utf-8")
print("Native pipe, Shift, numeric labels, both AI states/pages and ICO sizes passed; no visual capture.")
