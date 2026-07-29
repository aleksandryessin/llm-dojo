# llm-dojo 🥋

**Which local model should you actually run for agentic work — and what does it cost you?**

Public leaderboards benchmark frontier models on academic tasks. This repo asks a narrower,
more practical question: on a laptop, with open weights and no API keys, which model reliably
**calls the right tool**, **fills a schema**, **stays grounded in retrieved context**, and
**answers in the language you asked in** — and how many tokens per second do you pay for it?

Two halves:

- **Patterns** — small runnable examples of *how* to build each piece (agent loop, schema-guided
  reasoning, retrieval, serving). Each one carries the failure that motivated it.
- **Harness** — a reproducible benchmark that runs those same tasks across models and runtimes
  and produces comparison tables.

Everything runs locally (Ollama / LM Studio). One model is then taken to a rented GPU with vLLM,
to compare laptop economics against server economics on the same tasks.

## What's inside

### Patterns — how to build it

| # | Pattern | Status | What it demonstrates |
|---|---------|--------|----------------------|
| [01](patterns/01-react-agent-langgraph/) | ReAct agent on LangGraph primitives | ✅ | State + reducers, nodes, conditional edges, tool-calling loop — and why tool contracts beat prompt tuning |
| [02](patterns/02-schema-guided-reasoning/) | Schema-Guided Reasoning (SGR) | ✅ | A Pydantic schema as the reasoning scaffold; structured output from a 7B model |
| [03](patterns/03-llm-serving-bench/) | Serving micro-benchmark | ✅ | TTFT / tok/s over an OpenAI-compatible endpoint |
| 04 | RAG with citations over a docs corpus | 🚧 | Chunking, embeddings, retrieval, refusal when the answer is absent |
| 05 | Agent memory & human-in-the-loop | 🚧 | Checkpointers, thread isolation, approval gates before destructive tools |

### Suites — what the models are scored on

Every case exists as a **mirrored EN/RU pair**, so each suite reports not just a score but the
**EN→RU delta** — how much capability a model loses when the same task is asked in Russian.
That delta, not the absolute score, is the number this repo cares about most: it is what
decides whether a model is usable for a non-English deployment.

| Suite | Cases | Derived from | Scored by | Status |
|-------|-------|--------------|-----------|--------|
| [`tool-calling`](suites/tool_calling/) | 6 pairs | pattern 01 | exact tool-set match + argument match; calling any tool on a `no_tool` case is a failure | ✅ |
| `schema-adherence` | – | pattern 02 | JSON validity against the schema, then field-level correctness | 🚧 |
| `rag-grounding` | – | pattern 04 | RAGAS faithfulness / context precision + refusal rate on unanswerable questions | 🚧 |
| `speed` | – | pattern 03 | TTFT, decode tok/s, peak memory — per model **and per runtime** | 🚧 |

Case types in `tool-calling`: *simple* (argument stated verbatim), *arg_extraction* (name buried
in a stacktrace), *multi_tool* (two tools in one turn), *search* (free-form keyword the model
chooses), *no_tool* ×2 (answerable without tools — calling one is the failure).

Scoring is deterministic wherever possible (parsing, set comparison, normalised string match);
an LLM judge is used only where it cannot be avoided, and is reported separately because
judges are biased.

🚧 means *not written yet*. Nothing in these tables is a claim about code that already exists.

## Architecture

The harness is a four-stage pipeline — cases in, reports out — with the runtime hidden behind
one adapter interface, so adding a model or a whole runtime never touches the scorers:

```
 suites/*.yaml                 harness/run.py                harness/adapters/
 ┌──────────────┐   cases    ┌────────────────┐   prompts   ┌──────────────────┐
 │ tool-calling │──────────► │  runner        │───────────► │ ollama           │──► local
 │ schema-adh.  │            │  matrix:       │             │ lmstudio (MLX)   │──► local
 │ rag-grounding│            │  model × suite │ ◄───────────│ vllm (GPU)       │──► rented
 │ ru-quality   │            └───────┬────────┘  responses  └──────────────────┘
 │ speed        │                    │            + latency, tokens
 └──────────────┘                    ▼
                          runs/*.jsonl  (raw: prompt, response, timings — never deleted)
                                       │
                                       ▼
                          harness/scorers/  (deterministic · RAGAS · judge)
                                       │
                                       ▼
                          reports/*.md  →  the Results tables below
```

Three rules the design follows:

1. **Raw runs are immutable.** Scoring is a separate pass over stored responses, so a scorer bug
   is a re-score, not a re-run of every model.
2. **One seam for inference.** Every runtime is reached through an OpenAI-compatible client;
   moving a model from a laptop to a GPU is a `base_url` change, not a rewrite.
3. **Same cases everywhere.** A model is never compared against another on differently worded
   prompts — the suite file is the single source of truth.

## Models

Candidates for the first run — one per role, deliberately small so the comparison stays readable.
Exact tags should be verified against the runtime's registry before pulling.

| Role in the comparison | Candidate | Why it is in |
|------------------------|-----------|--------------|
| Small baseline | `llama3.2:3b` | Establishes the floor: what you lose by going tiny |
| Workhorse (reference) | `qwen2.5:7b` | The model every pattern here was developed against |
| Workhorse challenger | a current-generation 8–14B (Qwen3 / Gemma / Mistral class) | Does one generation of progress beat one size class? |
| Tool-calling specialist | a function-calling fine-tune (Hermes / Granite / Command-R class) | Does specialisation beat general capability on `tool-calling`? |
| MoE, large-but-fast | `qwen3-vl:30b` (30B total, ~3B active) | The local-serving sweet spot: 30B memory, near-3B speed |
| GPU tier | `Qwen2.5-7B-Instruct-AWQ` on vLLM | Same weights class, server economics — batching and concurrency |

Embeddings for `rag-grounding`: `nomic-embed-text` (768-dim, English) and `bge-m3` (multilingual,
used for the Russian half) — embedder choice is itself a variable in that suite.

## Data

| Corpus | Used by | Licence / provenance | Where it lives |
|--------|---------|----------------------|----------------|
| Synthetic microservice incident domain (services, dependencies, tickets) | `tool-calling`, `schema-adherence` | Written for this repo, MIT | In-repo, inline in the suites |
| Documentation corpus (vLLM / LangGraph / RAGAS public docs) | `rag-grounding` | Upstream licences — **fetched by a script, not vendored here** | `data/docs/` (git-ignored) |
| Russian translations of the same cases | `ru-quality` | Written for this repo, MIT | In-repo |
| Your own documents | `rag-grounding` | Yours | `data/local/` (git-ignored by design) |

Golden sets live next to the suites as YAML: question, expected sources, expected facts, and —
importantly — a set of **unanswerable** questions, because "I don't know" is a scored behaviour.

## Reproduce

Prerequisites: [Ollama](https://ollama.com), Python ≥ 3.11, [uv](https://docs.astral.sh/uv/).

```bash
ollama pull qwen2.5:7b
git clone https://github.com/aleksandryessin/llm-dojo && cd llm-dojo
uv sync
```

Run a pattern (works today):

```bash
uv run patterns/01-react-agent-langgraph/agent.py
uv run patterns/02-schema-guided-reasoning/sgr.py
uv run patterns/03-llm-serving-bench/bench.py qwen2.5:7b
```

Run the benchmark:

```bash
uv run -m harness.run --suite tool-calling --models qwen2.5:7b,llama3.2:3b   # raw runs -> runs/
uv run -m harness.score                                                       # scores newest -> reports/
```

The runtime is swappable without touching anything else — point the same suite at LM Studio
(`--runtime lmstudio`, port 1234) or at a rented GPU box (`--runtime vllm`, `VLLM_BASE_URL=…`).
Same cases, same scorer, comparable numbers.

## Results

Measured on an Apple M4 Max (36 GB unified memory) unless stated otherwise; every number is
reproducible with the commands above. Tables are filled in as suites land.

**Capability** — score per suite, 0–1, shown as EN / RU / delta:

| Model | tool-calling (EN) | tool-calling (RU) | Δ EN→RU | schema-adherence | rag-grounding |
|-------|-------------------|-------------------|---------|------------------|---------------|
| `llama3.2:3b` | 0.83 | 0.83 | +0.00 | – | – |
| `qwen2.5:7b` | 1.00 | 1.00 | +0.00 | – | – |
| _challenger_ | – | – | – | – | – |
| `qwen3-vl:30b` | – | – | – | – | – |

Full per-case breakdown: [reports/tool-calling.md](reports/tool-calling.md).

**Cost** — speed and memory, per runtime:

| Model | Runtime | TTFT | Decode tok/s | Peak memory |
|-------|---------|------|--------------|-------------|
| `qwen2.5:7b` | Ollama (llama.cpp) | – | – | – |
| `qwen2.5:7b` | LM Studio (MLX) | – | – | – |
| `Qwen2.5-7B-AWQ` | vLLM, 1×24 GB GPU | – | – | – |

**Findings** — the part that actually matters: what broke, on which model, and why.

- **Tool over-triggering scales with domain adjacency, not with difficulty.** `llama3.2:3b`
  answered "what is 17 × 3?" correctly without tools, but reached for `get_dependencies` on
  "what does the abbreviation NPE stand for?" — a general-knowledge question that merely
  *sounds* like the domain. `qwen2.5:7b` handled both. A benchmark without `no_tool` cases
  would have scored these two models identically at 100%.
- **No EN→RU degradation on easy tool calls.** Both models scored the same in both languages,
  including extracting `billing-core` out of a stacktrace embedded in a Russian question. The
  delta is a real metric, but this first case set is too easy to expose it — harder cases
  (ambiguous arguments, Russian-language service names, larger tool sets) come next.
- **Sample size caveat:** 6 mirrored pairs, one run, temperature 0. Treat as a smoke test of
  the harness, not as a leaderboard.

## Repo layout

```
patterns/     runnable examples with their own READMEs (the "how")
suites/       benchmark cases as YAML (the "what is measured")
harness/      runner · adapters (ollama | lmstudio | vllm) · scorers · report
runs/         raw responses, JSONL, git-ignored
reports/      generated comparison tables and write-ups
data/         corpora — fetched or local, git-ignored
```

## License

MIT — see [LICENSE](LICENSE). Use anything here in your own projects.

---

Maintained by [Aleksandr Yessin](https://github.com/aleksandryessin) — building LLM and agentic
systems in production.
