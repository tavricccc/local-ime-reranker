"""Install pinned official Onion Plus files using its upstream package manifest."""
import ast
import json
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def minimal_patch(upstream):
    schema = yaml.safe_load((upstream / "rimefiles/bopomo_onionplus.schema.yaml").read_text("utf-8"))
    elements = yaml.safe_load((upstream / "rimefiles/element_bopomo.yaml").read_text("utf-8"))
    bindings = [
        {"when": "has_menu", "accept": key, "send": key}
        for key in ("comma", "period", "minus")
    ]
    bindings += [
        {"when": "paging", "accept": "minus", "send": "Page_Up"},
        {"when": "has_menu", "accept": "equal", "send": "Page_Down"},
        {"when": "has_menu", "accept": "Shift+space", "send": "Page_Down"},
        {"when": "always", "accept": "Control+Alt+a", "toggle": "local_ai"},
    ]
    symbols = ("exclam", "at", "numbersign", "dollar", "percent", "asciicircum", "ampersand", "asterisk")
    for index, symbol in enumerate(symbols, 1):
        for accept in (f"Shift+{index}", f"Shift+{symbol}"):
            bindings.append({"when": "has_menu", "accept": accept, "send": f"Control+{index}"})
    return {
        "schema/dependencies": ["symbols_bpmf", "easy_en_lower", "easy_en_upper"],
        "engine/processors": [
            "lua_processor@*partial_commit", "lua_processor@*local_context",
            "lua_processor@mix_apc_s2rm_ltk", "ascii_composer", "recognizer",
            "key_binder", "recognizer@recognizer2", "speller", "punctuator",
            "selector", "navigator", "express_editor",
        ],
        "engine/segmentors": [
            "ascii_segmentor", "matcher", "matcher@recognizer2", "abc_segmentor",
            "affix_segmentor@emoji_series", "affix_segmentor@easy_en",
            "punct_segmentor", "fallback_segmentor",
        ],
        "engine/translators": [
            "punct_translator", "lua_translator@lua_custom_phrase",
            "table_translator@emoji_series", "table_translator@easy_en",
            "table_translator@easy_en_upper", "lua_translator@email_url_translator",
            "script_translator",
        ],
        "engine/filters": [
            "simplifier@character_range_bhjm", "lua_filter@mix_cf2_miss_filter",
            "lua_filter@en_sort_filter", "lua_filter@convert_english_filter",
            "simplifier@emoji_switch", "lua_filter@back_mark_filter@back_mark",
            "lua_filter@back_mark_filter@back_mark_series", "simplifier@punct_mark",
            "uniquifier", "lua_filter@comment_filter_unicode", "lua_filter@*local_ai",
        ],
        "switches": [switch for switch in schema["switches"] if switch.get("name") != "simplification"] + [
            {"name": "local_ai", "reset": 1, "states": ["AI 關", "AI 開"]}
        ],
        "key_binder/bindings": bindings,
        "menu/alternative_select_labels": [str(i) for i in range(1, 9)],
        "ascii_composer/switch_key/Shift_L": "commit_text",
        "ascii_composer/switch_key/Shift_R": "commit_text",
        "recognizer/patterns": {key: value for key, value in elements["r_patterns_plus"].items()
                                if key in ("emoji_series", "punct", "email_url_translator")},
        "recognizer2/patterns": {"easy_en": elements["r2_patterns_plus"]["easy_en"]},
    }


def expression(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return {"sort_rime": "sort_rime", "rime_files_2": "注音洋蔥plus版"}[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return expression(node.left) + expression(node.right)
    raise ValueError("Unsupported upstream package path")


def stage(user):
    lock = json.loads((ROOT / "config/onion-plus.lock.json").read_text("utf-8"))
    upstream = ROOT / "vendor/onion-rime-files"
    if not upstream.exists():
        subprocess.run(["git", "clone", lock["repository"], str(upstream)], check=True)
        subprocess.run(["git", "-C", str(upstream), "checkout", lock["revision"]], check=True)
    revision = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
    if revision != lock["revision"]:
        raise RuntimeError("Onion source revision differs from pinned package")
    source = (upstream / "sort_rime_file.py").read_text("utf-8-sig")
    section = source.split("#複製檔案(注音洋蔥plus版)", 1)[1].split("#複製檔案(注音洋蔥mixin版)", 1)[0]
    prefix = Path("sort_rime/注音洋蔥plus版")
    backup = ROOT / "runtime/onion-plus-before"
    backup.mkdir(parents=True, exist_ok=True)
    for name in ("default.custom.yaml", "user.yaml", "bopomo_onionplus.custom.yaml"):
        original = user / name
        if original.exists() and not (backup / name).exists():
            shutil.copy2(original, backup / name)
    count = 0
    # Read copy operations as data. Do not execute the upstream installer script.
    for statement in ast.parse(section).body:
        call = statement.value
        origin = upstream / expression(call.args[0])
        relative = Path(expression(call.args[1])).relative_to(prefix)
        destination = user / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if call.func.attr == "copyfile":
            shutil.copy2(origin, destination)
        elif call.func.attr == "copytree":
            shutil.copytree(origin, destination, dirs_exist_ok=True)
        else:
            raise ValueError("Unsupported upstream copy operation")
        count += 1
    patch = {
        "schema/name": "洋蔥注音 Plus · AI",
        "schema/icon": "icons/chinese.ico",
        "schema/ascii_icon": "icons/english.ico",
        "menu/page_size": 8,
        "show_notifications": ["ascii_mode", "local_ai"],
        "show_notifications_time": 1400,
        "local_ai/budget_ms": 150,
    }
    patch.update(minimal_patch(upstream))
    (user / "bopomo_onionplus.custom.yaml").write_text(yaml.safe_dump({"patch": patch}, allow_unicode=True), "utf-8")
    defaults = yaml.safe_load((user / "default.custom.yaml").read_text("utf-8"))
    defaults["patch"]["schema_list"] = [{"schema": "bopomo_onionplus"}]
    defaults["patch"]["menu/page_size"] = 8
    defaults["patch"]["ascii_composer/switch_key/Shift_L"] = "commit_text"
    defaults["patch"]["ascii_composer/switch_key/Shift_R"] = "commit_text"
    defaults["patch"]["key_binder/bindings"] = [binding for binding in defaults["patch"]["key_binder/bindings"]
                                                if binding.get("toggle", binding.get("set_option", binding.get("unset_option"))) != "simplification"]
    (user / "default.custom.yaml").write_text(yaml.safe_dump(defaults, allow_unicode=True), "utf-8")
    state = yaml.safe_load((user / "user.yaml").read_text("utf-8")) if (user / "user.yaml").exists() else {}
    state.setdefault("var", {})["last_schema"] = "bopomo_onionplus"
    (user / "user.yaml").write_text(yaml.safe_dump(state, allow_unicode=True), "utf-8")
    for lua in (ROOT / "rime/lua").glob("*.lua"):
        shutil.copy2(lua, user / "lua" / lua.name)
    shutil.copy2(ROOT / "rime/weasel.custom.yaml", user / "weasel.custom.yaml")
    print(f"Staged Onion Plus: {count} upstream copy operations, revision {revision}", flush=True)


if __name__ == "__main__":
    stage(ROOT / "runtime/windows/user")
