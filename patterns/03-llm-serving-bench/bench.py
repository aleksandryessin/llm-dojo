"""Benchmark any OpenAI-compatible LLM endpoint: TTFT, decode tok/s, latency percentiles,
and aggregate throughput under concurrency.

The same code benches Ollama (llama.cpp), vLLM or LM Studio — only `--runtime` changes.
That symmetry is the whole point of OpenAI-compatible serving, and it is what makes the
Ollama-vs-vLLM comparison in pattern 05 an apples-to-apples one.

The metric that separates the two runtimes is not per-request tok/s — it is *aggregate*
tok/s at concurrency > 1: vLLM batches concurrent requests continuously, a single-stream
runtime queues them.

Run:
    uv run patterns/03-llm-serving-bench/bench.py --model qwen2.5:7b --n 20 --concurrency 1
    uv run patterns/03-llm-serving-bench/bench.py --model qwen2.5:7b --n 20 --concurrency 20
    VLLM_BASE_URL=https://<POD>-8000.proxy.runpod.net/v1 \
        uv run patterns/03-llm-serving-bench/bench.py --runtime vllm \
        --model Qwen/Qwen2.5-7B-Instruct-AWQ --n 20 --concurrency 20
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

# The runtime registry lives in harness/adapters.py — one seam for inference, per the README.
# `uv run <path>` puts the *script's* directory on sys.path, not the repo root, so the repo
# root is added explicitly. This is the price of keeping patterns runnable as plain files.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from harness.adapters import get_client  # noqa: E402

BASE_PROMPT = "Explain how continuous batching works in an LLM inference server."
PADDING = " Answer thoroughly and precisely, with concrete numbers where they apply."


@dataclass
class Result:
    """One request. Raw numbers only — percentiles are computed at summary time."""

    ttft: float | None  # seconds until the first content token
    e2e: float  # seconds until the stream closed
    out_tokens: int
    token_source: str  # "usage" (server-reported) | "chunks" (counted, approximate)
    error: str | None = None

    @property
    def decode_tps(self) -> float | None:
        # Tokens after the first one, over the time spent decoding them. Dividing the full
        # token count by (e2e - ttft) would silently credit the prefill with a free token.
        if self.error or self.ttft is None or self.out_tokens < 2:
            return None
        decode_time = self.e2e - self.ttft
        return (self.out_tokens - 1) / decode_time if decode_time > 0 else None


def build_prompt(target_tokens: int) -> str:
    """Pad the prompt to roughly `target_tokens`. ~4 chars/token is a crude English
    approximation — good enough to keep prefill *constant across runtimes*, which is all
    this needs to do. It is not a token count."""
    prompt = BASE_PROMPT
    while len(prompt) < target_tokens * 4:
        prompt += PADDING
    return prompt


def one_request(client, args, prompt: str, barrier: threading.Barrier | None) -> Result:
    extra_body = {}
    if args.ignore_eos:
        # vLLM only: keep generating until max_tokens, so every request produces exactly the
        # same number of tokens. Ollama ignores/rejects it — hence the explicit flag.
        extra_body["ignore_eos"] = True

    if barrier is not None:
        try:
            barrier.wait(timeout=30)
        except threading.BrokenBarrierError:
            pass  # last, partially-filled wave — start without synchronising

    t0 = time.perf_counter()
    ttft = None
    chunk_tokens = 0
    usage_tokens = None
    try:
        stream = client.chat.completions.create(
            model=args.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=args.max_tokens,
            temperature=0,
            stream=True,
            stream_options={"include_usage": True},
            extra_body=extra_body or None,
        )
        for chunk in stream:
            if getattr(chunk, "usage", None):
                usage_tokens = chunk.usage.completion_tokens
            if chunk.choices and chunk.choices[0].delta.content:
                if ttft is None:
                    ttft = time.perf_counter() - t0
                chunk_tokens += 1
    except Exception as exc:  # a failed request is data, not a crash — record and move on
        return Result(ttft=ttft, e2e=time.perf_counter() - t0, out_tokens=0,
                      token_source="none", error=f"{type(exc).__name__}: {exc}")

    e2e = time.perf_counter() - t0
    if usage_tokens is not None:
        return Result(ttft=ttft, e2e=e2e, out_tokens=usage_tokens, token_source="usage")
    # Fallback: 1 streamed chunk ~= 1 token. Approximate, and flagged as such in the output —
    # comparing a usage-counted tok/s against a chunk-counted one is comparing two metrics.
    return Result(ttft=ttft, e2e=e2e, out_tokens=chunk_tokens, token_source="chunks")


def pct(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(int(round(p / 100 * (len(ordered) - 1))), len(ordered) - 1)
    return ordered[idx]


def summarize(results: list[Result], wall: float, args) -> dict:
    ok = [r for r in results if r.error is None]
    ttfts = [r.ttft for r in ok if r.ttft is not None]
    e2es = [r.e2e for r in ok]
    tps = [r.decode_tps for r in ok if r.decode_tps is not None]
    total_tokens = sum(r.out_tokens for r in ok)
    sources = {r.token_source for r in ok}
    return {
        "type": "summary",
        "runtime": args.runtime,
        "model": args.model,
        "n": args.n,
        "concurrency": args.concurrency,
        "max_tokens": args.max_tokens,
        "prompt_tokens_approx": args.prompt_tokens,
        "ok": len(ok),
        "failed": len(results) - len(ok),
        "wall_s": round(wall, 3),
        "ttft_p50": pct(ttfts, 50),
        "ttft_p95": pct(ttfts, 95),
        "e2e_p50": pct(e2es, 50),
        "e2e_p95": pct(e2es, 95),
        "decode_tps_median": statistics.median(tps) if tps else None,
        # The headline number for concurrency: everything the server produced, over the
        # wall-clock of the whole run. Per-request tok/s can look fine while this collapses.
        "aggregate_tps": round(total_tokens / wall, 1) if wall > 0 else None,
        "total_out_tokens": total_tokens,
        "token_source": "+".join(sorted(sources)) if sources else "none",
    }


def fmt(value, digits=2) -> str:
    return "–" if value is None else f"{value:.{digits}f}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runtime", default="ollama", help="ollama | vllm | lmstudio")
    ap.add_argument("--model", default="qwen2.5:7b", help="model name as the server reports it")
    ap.add_argument("--n", type=int, default=20, help="measured requests (warmup excluded)")
    ap.add_argument("--concurrency", type=int, default=1, help="requests in flight at once")
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--prompt-tokens", type=int, default=128, help="approximate prefill size")
    ap.add_argument("--ignore-eos", action="store_true", help="vLLM only: always emit max_tokens")
    ap.add_argument("--no-warmup", action="store_true")
    args = ap.parse_args()

    client = get_client(args.runtime)
    prompt = build_prompt(args.prompt_tokens)

    if not args.no_warmup:
        # Excluded from statistics: the first request loads weights (Ollama) or warms CUDA
        # graphs (vLLM). Leaving it in makes the p95 a measurement of the model loader.
        print("warmup...", flush=True)
        w = one_request(client, args, prompt, barrier=None)
        print(f"warmup: e2e={fmt(w.e2e)}s{' ERROR: ' + w.error if w.error else ''}", flush=True)

    barrier = threading.Barrier(min(args.concurrency, args.n)) if args.concurrency > 1 else None
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(lambda _: one_request(client, args, prompt, barrier), range(args.n)))
    wall = time.perf_counter() - t0

    s = summarize(results, wall, args)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_model = args.model.replace("/", "_").replace(":", "-")
    out = REPO_ROOT / "runs" / f"{stamp}-speed-{args.runtime}-{safe_model}-c{args.concurrency}.jsonl"
    out.parent.mkdir(exist_ok=True)
    with out.open("w") as fh:  # raw runs are immutable: written once, scored separately
        fh.write(json.dumps(s) + "\n")
        for r in results:
            fh.write(json.dumps({"type": "request", **asdict(r)}) + "\n")

    print(f"\n{args.runtime} / {args.model} — n={args.n}, concurrency={args.concurrency}, "
          f"max_tokens={args.max_tokens}, tokens counted from: {s['token_source']}")
    if s["failed"]:
        print(f"FAILED: {s['failed']}/{args.n} — first error: "
              f"{next(r.error for r in results if r.error)}")
    print(f"TTFT   p50 {fmt(s['ttft_p50'])}s   p95 {fmt(s['ttft_p95'])}s")
    print(f"e2e    p50 {fmt(s['e2e_p50'])}s   p95 {fmt(s['e2e_p95'])}s")
    print(f"decode {fmt(s['decode_tps_median'], 1)} tok/s median (per request)")
    print(f"AGGREGATE {fmt(s['aggregate_tps'], 1)} tok/s "
          f"({s['total_out_tokens']} tokens / {fmt(wall, 1)}s wall)")
    print(f"\nraw: {out.relative_to(REPO_ROOT)}")
    print("\nmarkdown row for the Cost table:")
    print(f"| `{args.model}` | {args.runtime} (c={args.concurrency}) | {fmt(s['ttft_p50'])}s / "
          f"{fmt(s['ttft_p95'])}s | {fmt(s['decode_tps_median'], 1)} | "
          f"{fmt(s['aggregate_tps'], 1)} | – |")


if __name__ == "__main__":
    main()
