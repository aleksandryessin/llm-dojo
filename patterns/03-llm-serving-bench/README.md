# 03 — LLM serving micro-benchmark

Two numbers rule LLM UX and capacity planning:

- **TTFT** (time to first token) — what the user feels as "it started";
- **tok/s** (decode speed) — what the user feels as "it types fast".

This script measures both through the OpenAI-compatible API, so the same code benches
Ollama, vLLM, LM Studio or a cloud provider — only `base_url` changes.

## Things worth observing on consumer hardware (Apple Silicon example)

- Dense 7B vs **MoE 30B-A3B** (30B params total, ~3B active per token): the MoE costs
  30B worth of memory but decodes at near-3B speed — that is why MoE models are the
  sweet spot for local serving.
- LLM decoding is **memory-bandwidth-bound**: quantization (Q4) speeds it up roughly
  proportionally to bytes moved, not FLOPs.
- Single-user Ollama vs batched vLLM: aggregate tok/s under concurrency is where vLLM
  (continuous batching + PagedAttention) changes the game — see pattern 05.

## Run

```bash
uv run patterns/03-llm-serving-bench/bench.py qwen2.5:7b
```

## Exercise

Bench two models you have locally and note TTFT vs tok/s. Then explain each difference
with one sentence about memory (weights size, KV-cache, active parameters).
