"""Micro-benchmark for any OpenAI-compatible LLM endpoint: TTFT + tokens/sec.

Defaults to a local Ollama server (http://localhost:11434/v1) — the same client code
works against vLLM, LM Studio or a cloud endpoint by changing base_url. That symmetry
is the whole point of OpenAI-compatible serving.

Run:  uv run patterns/03-llm-serving-bench/bench.py qwen2.5:7b
      uv run patterns/03-llm-serving-bench/bench.py qwen3:30b   # MoE: run twice, first run loads the model
"""
import sys
import time

from openai import OpenAI

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
model = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:7b"

t0 = time.perf_counter()
ttft = None
n_tokens = 0
stream = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "Explain GraphRAG in about 300 words."}],
    stream=True,
)
for chunk in stream:
    if chunk.choices and chunk.choices[0].delta.content:
        if ttft is None:
            ttft = time.perf_counter() - t0
        n_tokens += 1  # for Ollama, 1 chunk ~= 1 token

total = time.perf_counter() - t0
print(f"{model}: TTFT={ttft:.2f}s, {n_tokens} tokens in {total:.1f}s -> {n_tokens/(total-ttft):.1f} tok/s")
