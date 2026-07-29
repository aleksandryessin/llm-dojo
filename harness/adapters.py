"""Runtime adapters.

Every supported runtime speaks the OpenAI API, so there is exactly one adapter: a client
pointed at a different base_url. Adding LM Studio or a rented vLLM box is a line in
RUNTIMES, not a new code path — that is the "one seam for inference" rule from the README.
"""
import os

from openai import OpenAI

RUNTIMES = {
    # name        base_url                              api_key (unused locally)
    "ollama": ("http://localhost:11434/v1", "ollama"),
    "lmstudio": ("http://localhost:1234/v1", "lmstudio"),
    "vllm": (os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1"), os.getenv("VLLM_API_KEY", "dummy")),
}


def get_client(runtime: str) -> OpenAI:
    if runtime not in RUNTIMES:
        raise SystemExit(f"unknown runtime {runtime!r}; known: {', '.join(RUNTIMES)}")
    base_url, api_key = RUNTIMES[runtime]
    return OpenAI(base_url=base_url, api_key=api_key, timeout=180.0)
