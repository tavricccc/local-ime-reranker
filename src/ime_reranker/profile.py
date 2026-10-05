import json
from pathlib import Path

from .policy import Policy


def load_profile(args):
    if not args.profile:
        return Policy()
    config = json.loads(Path(args.profile).read_text("utf-8"))
    for key in ("backend", "model", "threads", "reverse", "input_mode", "prompt", "top_k", "text_mode"):
        setattr(args, key, config[key])
    return Policy(**config["policy"])
