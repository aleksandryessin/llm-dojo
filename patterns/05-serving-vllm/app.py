"""The `app` service of the contour — a skeleton, deliberately.

What is finished: wiring and `/health`. Every dependency is reached the same way the rest of
this repo reaches a runtime — by URL from the environment, never by hardcoded host.

What is left for you (marked TODO): the semantic cache itself. Its Redis idioms are lifted
from ay_gpt_bot/app/utils/redis.py — one pooled client behind lru_cache, decode_responses on,
every key written with an explicit TTL. Deviate from that only on purpose.

    GET  /health   -> per-dependency status, 200 only if all are up
    POST /ask      -> {"question": "..."} -> answer, served from cache when close enough
"""
import hashlib
import json
import os
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, HTTPServer

import redis
from neo4j import GraphDatabase
from openai import OpenAI

REDIS_URL = os.environ["REDIS_URL"]
OLLAMA_BASE_URL = os.environ["OLLAMA_BASE_URL"]
NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_AUTH = (os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "qwen2.5:7b")
THRESHOLD = float(os.environ.get("SEMANTIC_CACHE_THRESHOLD", "0.95"))
CACHE_TTL_S = int(os.environ.get("SEMANTIC_CACHE_TTL_S", "3600"))


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True, max_connections=20)


@lru_cache(maxsize=1)
def get_llm() -> OpenAI:
    return OpenAI(base_url=f"{OLLAMA_BASE_URL}/v1", api_key="ollama", timeout=120.0)


@lru_cache(maxsize=1)
def get_neo4j():
    return GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)


# A dependency is CRITICAL when the endpoint cannot do its job without it, not when the
# code happens to import it. `/ask` needs the model to answer at all; without Redis it
# still answers, only slower. Neo4j is not on the `/ask` path yet. Reporting a degraded
# service as unhealthy makes an orchestrator restart a container that was serving traffic
# fine — an outage manufactured by the health check itself.
CRITICAL = {"ollama"}


def check_dependencies() -> tuple[bool, dict]:
    """Health is per-dependency and never cached: a health endpoint that lies is worse
    than no health endpoint."""
    probes = {
        "redis": lambda: get_redis().ping(),
        "ollama": lambda: get_llm().models.list(),
        "neo4j": lambda: get_neo4j().execute_query("RETURN 1"),
    }
    status = {}
    for name, probe in probes.items():
        try:
            probe()
            status[name] = "ok"
        except Exception as exc:
            status[name] = f"down: {type(exc).__name__}"
    serving = all(status[name] == "ok" for name in CRITICAL)
    return serving, status


def embed(text: str) -> list[float]:
    return get_llm().embeddings.create(model=EMBED_MODEL, input=text).data[0].embedding


def exact_cache_key(question: str) -> str:
    return f"cache:exact:{hashlib.sha256(question.encode()).hexdigest()[:32]}"


# --------------------------------------------------------------------------------------
# TODO (yours). Three decisions the skeleton deliberately does not make for you:
#
# 1. cache_lookup(question) -> str | None
#    Exact-match first (one GET on exact_cache_key — free), then semantic: embed the
#    question, compare against stored vectors, return the answer if the best cosine is
#    >= THRESHOLD. Question to answer before you write it: where do the stored vectors
#    live? A Redis LIST scanned linearly is honest at 100 entries and a disaster at 100k.
#
# 2. cache_store(question, answer) -> None
#    Every key gets an explicit TTL (CACHE_TTL_S) — see ay_gpt_bot. A cache entry without
#    an expiry is a correctness bug waiting for the underlying data to change.
#
# 3. The threshold itself. 0.95 is a guess. A wrong hit is worse than a miss: the user gets
#    a confident answer to a question they did not ask. Measure it — the rag-grounding suite
#    already has paired questions that are close but not identical.
# --------------------------------------------------------------------------------------
def cache_lookup(question: str) -> str | None:
    raise NotImplementedError("cache_lookup — see TODO above")


def cache_store(question: str, answer: str) -> None:
    raise NotImplementedError("cache_store — see TODO above")


def answer(question: str) -> dict:
    try:
        cached = cache_lookup(question)
    except NotImplementedError:
        cached = None  # skeleton still serves requests, just without a cache
    if cached is not None:
        return {"answer": cached, "cached": True}

    response = get_llm().chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": question}],
        temperature=0,
    )
    text = response.choices[0].message.content
    try:
        cache_store(question, text)
    except NotImplementedError:
        pass
    return {"answer": text, "cached": False}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path != "/health":
            return self._send(404, {"error": "not found"})
        serving, status = check_dependencies()
        degraded = [name for name, state in status.items() if state != "ok"]
        # 503 only when a CRITICAL dependency is gone. Everything else is reported and
        # visible, but does not take the service out of rotation.
        code = 200 if serving else 503
        label = "ok" if not degraded else ("degraded" if serving else "unavailable")
        self._send(code, {"status": label, "degraded": degraded, "dependencies": status})

    def do_POST(self) -> None:
        if self.path != "/ask":
            return self._send(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length", 0))
        try:
            question = json.loads(self.rfile.read(length))["question"]
        except (ValueError, KeyError):
            return self._send(400, {"error": "expected JSON body with a 'question' field"})
        try:
            self._send(200, answer(question))
        except Exception as exc:
            self._send(502, {"error": f"{type(exc).__name__}: {exc}"})

    def log_message(self, fmt, *args):  # default logging writes to stderr per request
        print(f"{self.address_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    print(f"app listening on :8080 (chat={CHAT_MODEL}, embed={EMBED_MODEL})", flush=True)
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
