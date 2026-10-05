"""Per-user preferences survive repository updates and model restarts."""
import os
import shutil
from pathlib import Path


def prompt_path():
    directory = Path(os.environ["LOCALAPPDATA"]) / "LocalImeReranker"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "ai-prompt.txt"
    if not path.exists():
        shutil.copy2(Path(__file__).resolve().parents[2] / "config/ai-prompt.txt", path)
    return path
