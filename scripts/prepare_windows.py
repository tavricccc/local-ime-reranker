"""Stage the real Weasel frontend with an isolated AI schema and 32-bit bridge."""
import json
import shutil
import subprocess
from pathlib import Path

import yaml
import ziglang
from stage_onion_plus import stage as stage_onion_plus

ROOT = Path(__file__).resolve().parents[1]
frontend = ROOT / "runtime/windows/weasel"
user = ROOT / "runtime/windows/user"
shutil.copytree(ROOT / "vendor/weasel-portable", frontend, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("$PLUGINSDIR", "uninstall.exe"))
shutil.copy2(ROOT / "vendor/rime-x86/dist/lib/rime.dll", frontend / "rime.dll")
shared = frontend / "data"
shutil.copytree(ROOT / "runtime/rime/shared", shared, dirs_exist_ok=True)
schema_path = shared / "bopomofo_ai.schema.yaml"
schema = yaml.safe_load(schema_path.read_text("utf-8"))
schema["schema"]["name"] = "本地語意注音（實驗版）"
schema["schema"]["icon"] = "icons/chinese.ico"
schema["schema"]["ascii_icon"] = "icons/english.ico"
for switch in schema["switches"]:
    if switch.get("name") == "local_ai":
        switch["reset"] = 1
schema.setdefault("key_binder", {}).setdefault("bindings", []).append(
    {"when": "always", "accept": "Control+Alt+a", "toggle": "local_ai"})
profile = json.loads((ROOT / "config/reranker.json").read_text("utf-8"))
schema["local_ai"] = {"budget_ms": profile["budget_ms"]}
schema_path.write_text(yaml.safe_dump(schema, allow_unicode=True), "utf-8")
(user / "lua").mkdir(parents=True, exist_ok=True)
for source in (ROOT / "rime/lua").glob("*.lua"):
    shutil.copy2(source, user / "lua" / source.name)
shutil.copy2(ROOT / "rime/weasel.custom.yaml", user / "weasel.custom.yaml")
shutil.copytree(ROOT / "rime/icons", user / "icons", dirs_exist_ok=True)
compiler = Path(ziglang.__file__).parent / "zig.exe"
subprocess.run([str(compiler), "cc", "-target", "x86-windows-gnu", "-O2", "-shared",
                str(ROOT / "native/ai_bridge.c"), "-lws2_32", "-o", str(user / "lua/ai_bridge.dll")], check=True)
scheme = json.loads((ROOT / "config/rime-scheme.json").read_text("utf-8"))
if scheme["schema_id"] == "bopomo_onionplus":
    stage_onion_plus(user)
print("Staged native frontend", frontend)
print("Isolated user dictionary", user)
