"""Official hosted Jev Choice API. Enabled only by selecting the Jev backend."""
import json
import os
import time
import winreg

import httpx

from .decision_input import decision_input, instruction

ENDPOINT = "https://api.typesafe.ai/v1/systemone"


def api_key():
    for name in ("JEV_API_KEY", "TYPESAFE_API_KEY"):
        value = os.environ.get(name)
        if value:
            return value
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            for name in ("JEV_API_KEY", "TYPESAFE_API_KEY"):
                try:
                    return winreg.QueryValueEx(key, name)[0]
                except FileNotFoundError:
                    continue
    except FileNotFoundError:
        pass
    raise RuntimeError("Jev requires JEV_API_KEY; run scripts/configure-jev.ps1")


class JevScorer:
    def __init__(self, model="jev-latest", reverse=False, input_mode="rime-aware",
                 prompt="baseline", top_k=8, key=None, client=None):
        self.model, self.reverse = model, reverse
        self.input_mode, self.prompt, self.top_k = input_mode, prompt, top_k
        self.uses_rime_prior = input_mode == "rime-aware"
        self.key = key
        # Keep the TLS connection, make no retries. The native bridge's deadline
        # still releases Rime first if the network request is too slow.
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(0.6, connect=0.4),
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1))

    def score(self, request):
        request = {**request, "candidates": request["candidates"][:self.top_k]}
        state, options = decision_input(request, self.input_mode)
        question = {"type": "choice", "instructions": instruction(self.input_mode, self.prompt),
                    "criteria": options}
        questions = {"candidate": question}
        if self.reverse:
            questions["reverse"] = {**question, "criteria": dict(reversed(list(options.items())))}
        started = time.perf_counter()
        try:
            response = self.client.post(ENDPOINT, headers={"Authorization": "Bearer " + (self.key or api_key())},
                                        json={"model": self.model,
                                              "state": json.dumps(state, ensure_ascii=False),
                                              "questions": questions})
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise RuntimeError(f"Jev request failed: {type(error).__name__}") from None
        output = response.json()
        distributions = []
        for name in questions:
            answer = output["answers"][name]
            if answer["choice"] not in options or set(answer["probabilities"]) != set(options):
                raise ValueError("Jev returned an option outside this candidate snapshot")
            distributions.append(answer["probabilities"])
        probabilities = [sum(p[key] for p in distributions) / len(distributions) for key in options]
        return probabilities, {
            "backend": "jev", "device": "hosted", "model": output["model"],
            "inference_ms": (time.perf_counter() - started) * 1000,
            "input_mode": self.input_mode, "reverse": self.reverse,
            "prompt": self.prompt, "scored_count": len(options), "top_k": self.top_k,
            "usage": output.get("usage", {})}

    def close(self):
        self.client.close()
