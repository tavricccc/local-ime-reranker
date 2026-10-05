"""Only this setup step uses the network. Inference loads local paths."""
import hashlib
import argparse
import json
import subprocess
import urllib.request
from pathlib import Path

import py7zr
from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "assets.lock.json").read_text("utf-8"))
parser = argparse.ArgumentParser()
parser.add_argument('--model', choices=['all', *manifest['models']], default='all')
args = parser.parse_args()
vendor = ROOT / "vendor"
vendor.mkdir(exist_ok=True)
source = vendor / "verdict-source"
if args.model in ('all', 'verdict'):
    if not source.exists():
        subprocess.run(["git", "clone", "https://github.com/Heman10x-NGU/Verdict-open-jev", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "checkout", manifest["references"]["verdict_source"]], check=True)
archive = vendor / "rime.7z"
if not archive.exists():
    urllib.request.urlretrieve(manifest["rime"]["url"], archive)
if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["rime"]["sha256"]:
    raise ValueError("Rime archive SHA-256 mismatch")
dll = vendor / "rime/dist/lib/rime.dll"
if not dll.is_file():
    with py7zr.SevenZipFile(archive) as package:
        package.extractall(vendor / "rime")
if hashlib.sha256(dll.read_bytes()).hexdigest() != manifest["rime"]["dll_sha256"]:
    raise ValueError("Installed librime DLL SHA-256 mismatch")
for name, config in manifest["models"].items():
    if args.model != 'all' and name != args.model:
        continue
    snapshot_download(config["repo"], revision=config["revision"], local_dir=ROOT / "models" / name,
                      allow_patterns=config.get("allow_patterns"))
print("Pinned assets ready")
