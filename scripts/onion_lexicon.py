"""Stage only the pinned Onion Chinese dictionaries; leave input/UI untouched."""
import hashlib
import io
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def stage(shared: Path):
    asset = json.loads((ROOT / "assets.lock.json").read_text("utf-8"))["lexicons"]["onion"]
    name = "Onion-Rime-Bopomo-Revised-" + asset["revision"]
    cached = ROOT / "vendor" / name
    if not cached.exists():
        url = asset["repo"] + "/archive/" + asset["revision"] + ".zip"
        content = urllib.request.urlopen(url).read()
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            archive.extractall(ROOT / "vendor")
    for name, digest in asset["files"].items():
        source = cached / "rimefiles" / name
        if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise RuntimeError("Onion dictionary hash mismatch: " + name)
        shutil.copy2(source, shared / name)
    shutil.copy2(ROOT / "rime/local_ai_onion.dict.yaml", shared / "local_ai_onion.dict.yaml")

