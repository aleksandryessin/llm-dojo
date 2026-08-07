# llm-dojo 🥋

**Which local model should you actually run for agentic work — and what does it cost you?**

On a laptop, with open weights and no API keys: which model reliably **calls the right tool**,
**fills a schema**, **stays grounded in retrieved context**, and **answers in the language you
asked in** — and how many tokens per second do you pay for it?

Two halves:

- **Patterns** — small runnable examples of *how* to build each piece (agent loop, schema-guided
  reasoning, retrieval, serving). Each one carries the failure that motivated it.
- **Harness** — a benchmark that runs those same tasks across models and runtimes and produces
  comparison tables.

**State today:** three patterns and one suite (`tool-calling`, 6 mirrored EN/RU pairs) run
end-to-end on Ollama; results below. The other suites are not written yet, and the LM Studio /
GPU runtimes have adapters but no recorded runs — every table marks what is real with ✅ and
what is not with 🚧.

### Prior art, and what is different here

Tool calling already has serious benchmarks — [BFCL](https://gorilla.cs.berkeley.edu/leaderboard.html)
covers it far more thoroughly, [lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness)
is the standard for academic tasks, [RAGAS](https://docs.ragas.io) owns RAG metrics (and is used
here as a library, not competed with). This repo does not try to out-benchmark them. It occupies
a narrower slot they do not cover:

- **Consumer hardware, not a cluster** — the question is what a 36 GB laptop can actually run.
- **Capability and cost in the same table** — a score is only useful next to tok/s and memory.
- **Mirrored EN/RU cases** — the English score of a model says little about deploying it where
  the users write Russian.

## What's inside

### Patterns — how to build it

| # | Pattern | Status | What it demonstrates |
|---|---------|--------|----------------------|
| [01](patterns/01-react-agent-langgraph/) | ReAct agent on LangGraph primitives | ✅ | State + reducers, nodes, conditional edges, tool-calling loop — and why tool contracts beat prompt tuning |
| [02](patterns/02-schema-guided-reasoning/) | Schema-Guided Reasoning (SGR) | ✅ | A Pydantic schema as the reasoning scaffold; structured output from a 7B model |
| [03](patterns/03-llm-serving-bench/) | Serving micro-benchmark | ✅ | TTFT / tok/s over an OpenAI-compatible endpoint |
| [04](patterns/04-rag-citations/) | RAG with citations over a docs corpus | ✅ | Structure-aware chunking, citations, refusal as a scored behaviour — and when a dot product beats a vector DB |
| [05](patterns/05-serving-vllm/) | vLLM on a rented GPU + a one-command production contour | 🚧 | Serving flags that decide whether the server starts at all (KV cache vs `--max-model-len`), continuous batching under concurrency, and the whole stack in one `docker compose up` |
| 06 | Agent memory & human-in-the-loop | 🚧 | Checkpointers, thread isolation, approval gates before destructive tools |

### Suites — what the models are scored on

Every case exists as a **mirrored EN/RU pair**, so each suite reports not just a score but the
**EN→RU delta** — how much capability a model loses when the same task is asked in Russian.
That delta, not the absolute score, is the number this repo cares about most: it is what
decides whether a model is usable for a non-English deployment.

| Suite | Cases | Derived from | Scored by | Status |
|-------|-------|--------------|-----------|--------|
| [`tool-calling`](suites/tool_calling/) | 6 pairs | pattern 01 | exact tool-set match + argument match; calling any tool on a `no_tool` case is a failure | ✅ |
| [`rag-grounding`](suites/rag_grounding/) | 9 pairs (6 answerable + 3 unanswerable) | pattern 04 | grounding in expected facts + citation presence + refusal correctness + **language adherence** — all deterministic; retrieval hit reported separately (it measures the embedder, not the model). RAGAS as a second layer is planned | ✅ |
| `schema-adherence` | – | pattern 02 | JSON validity against the schema, then field-level correctness | 🚧 |
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
 suites/*/cases.yaml           harness/run.py              harness/adapters.py
 ┌───────────────┐   cases   ┌────────────────┐  prompts  ┌────────────────────┐
 │ tool-calling ✅│─────────► │  runner        │─────────► │ ollama          ✅ │──► local
 │ schema-adh.  🚧│           │  matrix:       │           │ lmstudio (MLX)  🚧 │──► local
 │ rag-grounding🚧│           │  model × case  │ ◄─────────│ vllm (GPU)      🚧 │──► rented
 │ speed        🚧│           └───────┬────────┘ responses └────────────────────┘
 └───────────────┘                   │           + latency, tokens
                                     ▼
                        runs/*.jsonl  (raw: response, timings — never rewritten)
                                     │
                                     ▼
                        harness/score.py  (deterministic now · RAGAS · judge later)
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

Tool support is a property of the **model + runtime pair**, not of the model card — so every
candidate earns its row by an actual harness run, not by reputation. Two lessons from doing
exactly that (see Findings): a vision-language MoE turned out to be a flawless tool caller,
while Gemma is rejected by Ollama outright (`does not support tools`, HTTP 400).

| Role in the comparison | Candidate | Tools in Ollama | Why it is in |
|------------------------|-----------|-----------------|--------------|
| Small baseline | `llama3.2:3b` | ✅ verified | Establishes the floor: what you lose by going tiny |
| Workhorse (reference) | `qwen2.5:7b` | ✅ verified | The model every pattern here was developed against |
| MoE, large-but-fast | `qwen3-vl:30b` (30B total, ~3B active) | ✅ verified, 12/12 | The local-serving sweet spot: 30B memory footprint, near-3B decode speed — and, empirically, a flawless tool caller despite being a VL variant |
| Workhorse challenger | a current-generation 8–14B (Qwen3 / Gemma / Mistral class) | to verify per tag | Does one generation of progress beat one size class? Gemma tags without tool support still compete in `schema-adherence` / `rag-grounding` / `speed` |
| Tool-calling specialist | a function-calling fine-tune (Hermes / Granite / Command-R class) | to verify per tag | Does specialisation beat general capability on `tool-calling`? |
| GPU tier | `Qwen2.5-7B-Instruct-AWQ` on vLLM | expected ✅ | Same weights class, server economics — batching and concurrency |

Embeddings for `rag-grounding`: `nomic-embed-text` (768-dim, English) and `bge-m3` (multilingual,
used for the Russian half) — embedder choice is itself a variable in that suite.

## Data

| Corpus | Used by | Licence / provenance | Where it lives |
|--------|---------|----------------------|----------------|
| Synthetic microservice incident domain (services, dependencies, tickets), with every case written in both English and Russian | `tool-calling` ✅, `schema-adherence` 🚧 | Written for this repo, MIT | In-repo: [`suites/tool_calling/cases.yaml`](suites/tool_calling/cases.yaml) |
| Documentation corpus (vLLM / LangGraph / RAGAS public docs) | `rag-grounding` 🚧 | Upstream licences — to be **fetched by a script, never vendored here** | `data/docs/` (git-ignored) |
| Your own documents | `rag-grounding` 🚧 | Yours | `data/local/` (git-ignored by design) |

When `rag-grounding` lands, its golden set will sit next to the suite as YAML — question,
expected sources, expected facts, and a block of deliberately **unanswerable** questions,
because "I don't know" is a scored behaviour, not a missing answer.

## Reproduce

Prerequisites: [Ollama](https://ollama.com), Python ≥ 3.11, [uv](https://docs.astral.sh/uv/).

```bash
ollama pull qwen2.5:7b && ollama pull llama3.2:3b   # baseline + reference
# optional heavyweight from the Results table (19 GB): ollama pull qwen3-vl:30b
git clone https://github.com/aleksandryessin/llm-dojo && cd llm-dojo
uv sync                                             # exact versions come from uv.lock
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

The runtime is a flag, not a rewrite: the same suite can be pointed at LM Studio
(`--runtime lmstudio`, port 1234) or at a rented GPU box (`--runtime vllm`, `VLLM_BASE_URL=…`).
Both adapters exist; neither has been exercised yet — those rows in the Cost table are empty
for that reason, not by oversight.

## Results

Measured on an Apple M4 Max (36 GB unified memory) unless stated otherwise; every number is
reproducible with the commands above. Tables are filled in as suites land.

**Capability** — score per suite, 0–1, shown as EN / RU / delta:

| Model | tool-calling EN / RU | Δ | rag-grounding EN / RU | Δ | schema-adherence |
|-------|----------------------|---|------------------------|---|------------------|
| `llama3.2:3b` | 0.83 / 0.83 | 0.00 | 0.67 / 0.33 | **−0.33** | – |
| `qwen2.5:7b` | 1.00 / 1.00 | 0.00 | 0.78 / 0.11 | **−0.67** | – |
| `qwen3-vl:30b` | 1.00 / 1.00 | 0.00 | 0.89 / 0.56 | **−0.33** | – |
| `gemma3:1b` | ✗ no tools in Ollama | n/a | 0.89 / 0.00 | **−0.89** | – |
| _challenger (8–14B, tbd)_ | – | – | – | – | – |

Full per-case breakdowns: [reports/tool-calling.md](reports/tool-calling.md),
[reports/rag-grounding.md](reports/rag-grounding.md).

**Cost** — speed and memory, per runtime:

20 requests × 256 tokens, temperature 0. TTFT is p50/p95; *aggregate* is all output tokens
over the wall-clock of the run — the number that separates the two runtimes.

| Model | Runtime | Concurrency | TTFT p50 / p95 | Decode tok/s | Aggregate tok/s |
|-------|---------|-------------|----------------|--------------|-----------------|
| `qwen2.5:7b` | Ollama, 1 slot | 1 | 0.11 / 0.12 s | 67.7 | 65.6 |
| `qwen2.5:7b` | Ollama, 1 slot | 20 | 37.61 / 69.76 s | 67.3 | 65.4 |
| `qwen2.5:7b` | Ollama, 8 slots | 20 | 25.66 / 50.04 s | 10.5 | 81.8 |
| `Qwen2.5-7B-AWQ` | vLLM 0.26, RTX A5000 | 1 | 0.57 / 0.88 s | 125.5 | 95.8 |
| `Qwen2.5-7B-AWQ` | vLLM 0.26, RTX A5000 | 20 | **0.60 / 0.99 s** | 87.0 | **1154.6** |
| `qwen2.5:7b` | LM Studio (MLX) | – | – | – | – |

Full write-up, flags and incident log: [patterns/05-serving-vllm/](patterns/05-serving-vllm/).

**Findings** — the part that actually matters: what broke, on which model, and why.

- **A runtime's advantage shows up in how it degrades, not in how fast it is.** Single-stream,
  vLLM on a rented A5000 beat Ollama on an M4 Max by only 1.9× (125.5 vs 67.7 tok/s) — roughly
  the ratio of memory bandwidth between the two machines. At 20 concurrent clients the gap
  became **14×** (1154.6 vs 81.8 tok/s aggregate), because per-request decode fell 31% on vLLM
  and 6.4× on llama.cpp. p95 TTFT: 0.99 s vs 50 s.
- **Raising `OLLAMA_NUM_PARALLEL` from 1 to 8 bought +25% throughput, not 8×.** The server log
  shows why: 1 slot × 72.1 = 72 tok/s, 4 × 20.6 = 82, 8 × 10.5 = 84 — total throughput is a
  constant on Metal. Batching there divides one stream between users instead of multiplying it;
  dequantising Q4_K weights costs work that grows linearly with batch size.
- **The KV-cache formula predicts memory before you rent anything.** 2 × layers × kv-heads ×
  head_dim × 2 bytes = 56 KiB/token for Qwen2.5-7B. Predicted 14 GiB for 8×32k slots on the
  laptop — `llama-server` reported 14336 MiB. Predicted ~15 GiB and ~30 sequences on a 24 GB
  card — vLLM reported 14.79 GiB, i.e. 34 sequences.

- **The EN→RU delta is real, large, and invisible on easy tasks.** On `tool-calling` every model
  scored identically in both languages (Δ 0.00). On `rag-grounding` — same corpus, same
  retrieval, only the question language changes — every model degraded: −0.33 to −0.89.
  The poster child is `gemma3:1b`: **best-in-class in English (0.89) and zero in Russian
  (0.00)**. An English leaderboard score genuinely says nothing about a Russian deployment.
- **The drift you cannot see in aggregates:** `qwen2.5:7b` answered two questions in
  *Chinese* (an English question about Ragas, a Russian one about France). The RU language
  check caught it; the EN check did not — it only detects Cyrillic, and Chinese sails through.
  A known limitation, kept as a TODO in the scorer.
- **Small models corrupt protocol markers.** One refusal came back as `NOT_IN_CORPORUS`
  (sic) — a correct refusal failed exact-match scoring because a 7B model could not reproduce
  the token verbatim. Machine-checkable markers for small models must be matched fuzzily.
- **Retrieval errors masquerade as generation errors.** `uv_what_en` failed with "missing
  expected facts" — but the answer was faithful to its context; top-k simply surfaced the
  "drop-in replacement" chunk instead of the "written in Rust" intro. Without storing raw
  sources per run, this would have been blamed on the model.

- **Tool over-triggering scales with domain adjacency, not with difficulty.** `llama3.2:3b`
  answered "what is 17 × 3?" correctly without tools, but reached for `get_dependencies` on
  "what does the abbreviation NPE stand for?" — a general-knowledge question that merely
  *sounds* like the domain. `qwen2.5:7b` handled both. A benchmark without `no_tool` cases
  would have scored these two models identically at 100%.
- **No EN→RU degradation on easy tool calls.** Both models scored the same in both languages,
  including extracting `billing-core` out of a stacktrace embedded in a Russian question. The
  delta is a real metric, but this first case set is too easy to expose it — harder cases
  (ambiguous arguments, Russian-language service names, larger tool sets) come next.
- **Verify the runtime pair, not the model card.** The two roster surprises went in opposite
  directions: `qwen3-vl:30b` — a vision-language variant one might exclude on paper — scored a
  flawless 12/12 at ~3 s/case (vs ~1 s for the 7B), while `gemma3:1b` is rejected by Ollama
  before inference even starts (`does not support tools`, HTTP 400). Both facts cost one
  harness run each to establish.
- **Sample size caveat:** 6 mirrored pairs, one run, temperature 0. Treat as a smoke test of
  the harness, not as a leaderboard.

## Repo layout

```
patterns/                     runnable examples with their own READMEs (the "how")
suites/<suite>/cases.yaml     benchmark cases (the "what is measured")
suites/<suite>/tools.py       tool schemas offered to the model, per suite
harness/run.py                the model × case matrix runner
harness/adapters.py           runtime registry: ollama | lmstudio | vllm
harness/score.py              deterministic scorer + markdown report writer
runs/                         raw responses, JSONL — git-ignored (large, regenerable)
reports/                      generated comparison tables — committed, they are the product
data/                         corpora, fetched or local — git-ignored
```

## License

MIT — see [LICENSE](LICENSE). Use anything here in your own projects.

---

Maintained by [Aleksandr Yessin](https://github.com/aleksandryessin) — building LLM and agentic
systems in production.
