"""Fetch and verify the matching x86 engine and official native TSF frontend."""
import hashlib
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

import py7zr

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "assets.lock.json").read_text("utf-8"))["windows"]


def fetch(name, filename):
    config = manifest[name]
    archive = ROOT / "vendor" / filename
    archive.parent.mkdir(exist_ok=True)
    if not archive.exists():
        urllib.request.urlretrieve(config["url"], archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != config["sha256"]:
        raise ValueError(f"{name}: SHA-256 mismatch")
    return archive


archive = fetch("rime_x86", "rime-x86.7z")
dll = ROOT / "vendor/rime-x86/dist/lib/rime.dll"
if not dll.exists():
    with py7zr.SevenZipFile(archive) as package:
        package.extractall(ROOT / "vendor/rime-x86")
if hashlib.sha256(dll.read_bytes()).hexdigest() != manifest["rime_x86"]["dll_sha256"]:
    raise ValueError("x86 librime DLL: SHA-256 mismatch")
archive = fetch("weasel", "weasel-0.17.4.0-installer.exe")
destination = ROOT / "vendor/weasel-portable"
if not (destination / "WeaselSetup.exe").exists():
    executable = shutil.which("7z") or shutil.which("7z.exe")
    if not executable:
        executable = str(Path("C:/Program Files/7-Zip/7z.exe"))
    subprocess.run([executable, "x", str(archive), f"-o{destination}", "-y"], check=True)
print("Pinned Windows assets verified")
