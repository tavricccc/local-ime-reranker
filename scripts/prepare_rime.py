"""Fetch pinned upstream data and prepare an isolated real Rime workspace."""
import argparse
import io
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

import yaml
import ziglang

from onion_lexicon import stage as stage_onion

ROOT = Path(__file__).resolve().parents[1]
DATA = {
    "rime-bopomofo": "6085c9a38a4a728047862b33d67eee18aa86f3b9",
    "rime-terra-pinyin": "723e51bc266cf9464530c1ddedb856aa18e3da34",
    "rime-prelude": "082425ea0684bca36474415d4a0e8db9b016487e",
    "rime-essay": "054920de4f54c9e5994276a96a4fc2a35cb51aa3",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default="runtime/rime")
    parser.add_argument("--lexicon", choices=("terra", "onion", "onion-supplement"), default="terra")
    args = parser.parse_args()
    shared = ROOT / args.workspace / "shared"
    user = ROOT / args.workspace / "user"
    shared.mkdir(parents=True, exist_ok=True)
    (user / "lua").mkdir(parents=True, exist_ok=True)
    for repo, sha in DATA.items():
        cached = ROOT / "vendor" / repo
        if not cached.exists():
            url = f"https://github.com/rime/{repo}/archive/{sha}.zip"
            content = urllib.request.urlopen(url).read()
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                archive.extractall(ROOT / "vendor")
            (ROOT / "vendor" / f"{repo}-{sha}").rename(cached)
        for source in list(cached.glob("*.yaml")) + list(cached.glob("essay.txt")):
            shutil.copy2(source, shared / source.name)
    schema = yaml.safe_load((shared / "bopomofo.schema.yaml").read_text("utf-8"))
    schema["schema"].update(schema_id="bopomofo_ai", name="本地語意注音 PoC")
    schema["schema"].pop("dependencies", None)
    schema["engine"]["translators"].remove("reverse_lookup_translator")
    # No conversion-filter replacement in the PoC: traditional dictionary candidates.
    schema["engine"]["filters"] = ["uniquifier", "lua_filter@*local_ai"]
    schema["engine"]["processors"].insert(0, "lua_processor@*local_context")
    schema["translator"]["enable_completion"] = False
    if args.lexicon != "terra":
        stage_onion(shared)
        onion = {**schema["translator"], "dictionary": "local_ai_onion",
                 "prism": "bopomofo_ai_onion", "user_dict": "terra_pinyin"}
        if args.lexicon == "onion":
            schema["translator"] = onion
        else:
            schema["onion"] = {**onion, "initial_quality": -0.25}
            schema["engine"]["translators"].append("script_translator@onion")
            # Rime compiles the main translator of each dependency schema.
            schema["schema"]["dependencies"] = ["onion_lexicon"]
            dependency = {"schema": {"schema_id": "onion_lexicon", "name": "洋蔥詞庫"},
                          "engine": {"translators": ["script_translator"]},
                          "speller": schema["speller"], "translator": onion}
            (shared / "onion_lexicon.schema.yaml").write_text(
                yaml.safe_dump(dependency, allow_unicode=True), "utf-8")
    schema["switches"].append({"name": "local_ai", "reset": 0, "states": ["AI 關", "AI 開"]})
    schema["menu"]["page_size"] = 8
    schema["menu"]["alternative_select_labels"] = [str(i) for i in range(1, 10)] + ["0"]
    (shared / "bopomofo_ai.schema.yaml").write_text(yaml.safe_dump(schema, allow_unicode=True), "utf-8")
    defaults = yaml.safe_load((shared / "default.yaml").read_text("utf-8"))
    defaults["schema_list"] = [{"schema": "bopomofo_ai"}]
    defaults["menu"] = {"page_size": 8}
    (shared / "default.yaml").write_text(yaml.safe_dump(defaults, allow_unicode=True), "utf-8")
    for source in (ROOT / "rime/lua").glob("*.lua"):
        shutil.copy2(source, user / "lua" / source.name)
    compiler = Path(ziglang.__file__).parent / "zig.exe"
    subprocess.run([str(compiler), "cc", "-target", "x86_64-windows-gnu", "-O2", "-shared",
                    str(ROOT / "native/ai_bridge.c"), "-lws2_32", "-o", str(user / "lua/ai_bridge.dll")], check=True)
    print("Prepared", user)


if __name__ == "__main__":
    main()
