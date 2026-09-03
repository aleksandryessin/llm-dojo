# 05 — Serving: vLLM on a rented GPU, plus an integration skeleton

Two halves of the same question — *what must be measured and wired before production?*

1. **Serving** — the same model on a laptop runtime (Ollama/llama.cpp) and on vLLM with a
   real GPU, measured with the same benchmark. Commands, GPU selection and post-mortems:
   [RUNBOOK.md](RUNBOOK.md).
2. **Integration skeleton** — graph, cache, application, and optional tracing in one
   `docker compose up`. The semantic cache is intentionally unfinished and marked TODO in
   `app.py`; this is not presented as a production-ready service.

## The integration contour

```
   host                                    docker compose
 ┌──────────┐                 ┌──────────────────────────────────────────┐
 │  ollama  │◄────────────────┤  app  :8080   cache TODO → LLM            │
 │  :11434  │  host.docker.   │   │                                      │
 │  (Metal) │  internal       │   ├──► redis  :6379   cache              │
 └──────────┘                 │   └──► neo4j  :7687   graph              │
                              │                                          │
                              │  --profile tracing:                      │
                              │      langfuse :3000 ──► postgres         │
                              └──────────────────────────────────────────┘
```

### Prerequisites — the host Ollama

Inference stays on the host. Docker Desktop on macOS does not pass the GPU through, so a
containerised Ollama would run on CPU — slower than the host daemon *and* holding a second
copy of every model. On a Linux box with an NVIDIA card the trade-off reverses; that case
is the `linux-gpu` profile.

Install Ollama (macOS: `brew install --cask ollama`, or the installer from
[ollama.com](https://ollama.com); Linux: `curl -fsSL https://ollama.com/install.sh | sh`),
then pull the two models the contour uses:

```bash
ollama pull qwen2.5:7b && ollama pull nomic-embed-text
```

Start the daemon so containers can reach it — **the default binds `127.0.0.1`, which is
unreachable from Docker**:

```bash
OLLAMA_HOST=0.0.0.0 OLLAMA_NUM_PARALLEL=8 ollama serve
```

If that fails with `bind: address already in use`, the menu-bar app already holds the port:
`pkill -f "Ollama.app"`, wait for `lsof -i :11434` to come back empty, then retry.

### Run

```bash
cp patterns/05-serving-vllm/.env.example patterns/05-serving-vllm/.env
```

Set `NEO4J_PASSWORD`; nothing else is required for the default profile.

```bash
docker compose -f patterns/05-serving-vllm/docker-compose.yml up -d
```

```bash
docker compose -f patterns/05-serving-vllm/docker-compose.yml ps
```

Every row must read `healthy`. Then:

```bash
curl -s localhost:8080/health | python3 -m json.tool
```

```bash
curl -s localhost:8080/ask -H 'Content-Type: application/json' -d '{"question":"What is PagedAttention?"}' | python3 -m json.tool
```

With tracing (adds Langfuse + Postgres; fill in the three generated secrets in `.env` first,
and set `LANGFUSE_HOST=http://langfuse:3000`):

```bash
docker compose -f patterns/05-serving-vllm/docker-compose.yml --profile tracing up -d
```

The acceptance test is destructive on purpose — it proves there is no hidden manual step
keeping the contour alive:

```bash
docker compose -f patterns/05-serving-vllm/docker-compose.yml down -v && docker compose -f patterns/05-serving-vllm/docker-compose.yml up -d
```

`-v` drops the volumes: the database is recreated and, under `--profile tracing`, Langfuse
re-bootstraps its org, project and API keys from `.env`. Models are untouched — they live on
the host, which is the other reason inference is not a container here.

### Five decisions worth defending

**Inference is not containerised on macOS.** Docker cannot reach Metal. A contour that looks
tidy in the compose file and runs the model 5× slower is a worse contour.

**Healthchecks test the process, not the port.** Neo4j listens on 7687 long before it can
answer Cypher, so its check runs a real `RETURN 1`. Postgres uses `pg_isready`, Langfuse hits
`/api/public/health` via `node` (no curl in that image). Dependants wait on
`condition: service_healthy`, never on `service_started`.

**A health endpoint distinguishes critical from degraded.** `/ask` cannot work without the
model, so Ollama is critical and its absence returns 503. Redis missing means slower, not
broken; Neo4j is not on that path at all. Both are reported in the payload and neither takes
the service out of rotation — a health check that reports degraded as dead makes an
orchestrator kill a container that was serving traffic fine.

**Tracing is opt-in and never a hard dependency.** Observability must not be a single point
of failure for the thing it observes. `app` has no `depends_on` for Langfuse; with
`LANGFUSE_HOST` empty it simply runs untraced.

**Secrets have no defaults.** `${NEO4J_PASSWORD:?...}` — compose refuses to start rather than
boot with a well-known password. `.env.example` is committed and documents the *shape* of the
config; `.env` is git-ignored and holds the values.

### Neo4j backup

Community Edition has **no online backup** — that is an Enterprise feature. The database must
be stopped, which is itself the operational fact worth knowing:

```bash
docker compose -f patterns/05-serving-vllm/docker-compose.yml stop neo4j && docker compose -f patterns/05-serving-vllm/docker-compose.yml run --rm --entrypoint neo4j-admin neo4j database dump neo4j --to-path=/backups && docker compose -f patterns/05-serving-vllm/docker-compose.yml start neo4j
```

The dump lands in `patterns/05-serving-vllm/backups/` on the host. Restore reverses it:

```bash
docker compose -f patterns/05-serving-vllm/docker-compose.yml stop neo4j && docker compose -f patterns/05-serving-vllm/docker-compose.yml run --rm --entrypoint neo4j-admin neo4j database load neo4j --from-path=/backups --overwrite-destination=true && docker compose -f patterns/05-serving-vllm/docker-compose.yml start neo4j
```

## Benchmark results

Measured with [`patterns/03-llm-serving-bench/bench.py`](../03-llm-serving-bench/bench.py),
20 requests × 256 tokens, temperature 0, ~126-token prompt. Laptop rows on an Apple M4 Max
(36 GB unified memory); GPU rows on a rented 24 GB card. The reviewed JSONL observations and
configuration metadata are committed under [`runs/`](../../runs/).

| Runtime | Model | Concurrency | TTFT p50 / p95 | Decode tok/s per request | Aggregate tok/s | Wall |
|---------|-------|-------------|----------------|--------------------------|-----------------|------|
| Ollama, `NUM_PARALLEL=1` | qwen2.5:7b Q4_K_M | 1 | 0.11 / 0.12 s | 67.7 | 65.6 | 78.0 s |
| Ollama, `NUM_PARALLEL=1` | qwen2.5:7b Q4_K_M | 20 | 37.61 / 69.76 s | 67.3 | 65.4 | 78.2 s |
| Ollama, `NUM_PARALLEL=8` | qwen2.5:7b Q4_K_M | 20 | 25.66 / 50.04 s | 10.5 | 81.8 | 62.6 s |
| vLLM 0.26, RTX A5000 | Qwen2.5-7B-Instruct-AWQ | 1 | 0.57 / 0.88 s | 125.5 | 95.8 | 53.4 s |
| vLLM 0.26, RTX A5000 | Qwen2.5-7B-Instruct-AWQ | 20 | **0.60 / 0.99 s** | 87.0 | **1154.6** | **4.4 s** |

### What the comparison says

**The gap is 14×, and it is not about raw speed.** Aggregate throughput went 81.8 → 1154.6
tok/s, p95 TTFT 50.0 → 0.99 s, wall-clock on the same 20 requests 62.6 → 4.4 s. But
single-stream decode only went 67.7 → 125.5 tok/s (1.9×, roughly the ratio of memory
bandwidth between the two machines). Almost the entire difference appears **under
concurrency**, not per request.

**The number that names the mechanism:** at 20 concurrent clients, per-request decode fell
31% on vLLM (125.5 → 87.0) and 6.4× on llama.cpp (67.3 → 10.5). Continuous batching plus
PagedAttention serves twenty users at 70% of solo speed each; a slot-based runtime divides
one stream twenty ways. That is the whole argument for vLLM in one pair of numbers — not
"it is faster", but "it degrades sublinearly with users".

**vLLM's own log confirmed the KV arithmetic.** `kv cache memory in use is 14.79 GiB` next to
`Model loading took 5.29 GiB`, on a 24 GB card at `--gpu-memory-utilization 0.90`. At 56 KiB
per token that is ~277k tokens ≈ 34 concurrent 8k sequences — the capacity estimate made
before the pod was even rented.

**Caveat on TTFT.** The vLLM figures include a round-trip to a rented box in Sweden behind
Cloudflare (~0.4 s); the Ollama figures are localhost. The comparable quantity is how TTFT
*grows* under load: ×230 on Ollama (0.11 → 25.7 s), ×1.05 on vLLM (0.57 → 0.60 s).

Cost of producing the GPU rows: ~25 minutes of an RTX A5000, about **$0.11**.

### What the laptop numbers say

**Concurrency without server-side parallelism buys nothing.** At `NUM_PARALLEL=1`, going from
1 to 20 concurrent clients left aggregate throughput unchanged (65.6 → 65.4 tok/s) and
wall-clock unchanged (78 s) while TTFT went from 0.11 s to 37.6 s. The entire twenty-fold
load turned into queue.

**Batching on Metal divides throughput, it does not multiply it.** Raising the limit to 8
slots moved aggregate only to 81.8 tok/s (+25%) while per-request decode collapsed 6.4× —
67.3 → 10.5 tok/s. The server log makes the mechanism explicit: 1 slot × 72.1 = 72 tok/s,
4 × 20.6 = 82, 8 × 10.5 = 84. **Total throughput is a constant ~72–84 tok/s at any batch
size.** The likely cause: weights are Q4_K and must be dequantised on the fly, and that work
grows linearly with batch size, cancelling the one benefit of batching (reading weights once
for the whole batch). vLLM's Marlin kernels dequantise in-register on tensor cores, which is
exactly what the GPU rows are meant to test.

**The KV-cache formula predicted memory to the megabyte.** 32768 tokens × 8 slots × 56 KiB
= 14 GiB; `llama-server` reported `KV buffer size = 14336.00 MiB`. The same log prints
`n_embd_k_gqa = 512` — the 4 KV-heads × 128 term of the formula, straight from the runtime.

**Caveat, stated before someone else states it.** The benchmark sends one identical prompt 20
times and `llama-server` has its prompt cache on (`sim_best = 1.000`, `prompt eval … / 1
tokens`). Prefill was largely skipped, so absolute TTFT is optimistic on both runtimes — vLLM
enables prefix caching by default too, so the comparison stays fair.

## Where it broke

Filled in as it happens — see the incident log in [RUNBOOK.md](RUNBOOK.md).

- **`OLLAMA_NUM_PARALLEL` does not reach a GUI-launched server.** Ollama.app does not read
  your shell profile, and it refuses `osascript … quit` (`error -128`); the port stays held
  and `ollama serve` dies with `bind: address already in use`. Fix: `pkill -f "Ollama.app"`,
  wait for the port to actually free, then start the server from a terminal with the variable
  inline — which also puts the configuration in this README verbatim.
- **A manually started server does not log where you expect.** The config dump goes to the
  terminal, not to `~/.ollama/logs/server.log` — grepping the file returns the *previous*
  run's value and quietly confirms the wrong thing.
- **A container cannot reach an Ollama bound to loopback.** The daemon defaults to
  `127.0.0.1:11434`; from inside compose that is the container's own loopback, so `app` gets
  connection refused while `curl` on the host works fine. Start it with `OLLAMA_HOST=0.0.0.0`.
- **A healthy database reported as unhealthy, for four minutes, because of one `$`.** The
  Neo4j check ran `cypher-shell -p "$$NEO4J_PASSWORD"`, but only `NEO4J_AUTH` was passed into
  the container — `$$VAR` is expanded *inside* the container, where that name did not exist,
  so the probe authenticated with an empty password. The symptom is misleading twice over:
  `docker compose up` says `dependency failed to start: container dojo-neo4j is unhealthy`,
  while the database is running perfectly and its own log says exactly what happened
  (`The client is unauthorized due to authentication failure`, once per probe). Diagnosis is
  `docker inspect --format '{{json .State.Health}}' <container>` — it stores the output of
  every failed probe. Fix: pass the password under a name the image will not mistake for a
  config setting (`DOJO_NEO4J_PASSWORD`), since any `NEO4J_*` variable is parsed as one.
  General rule: **a healthcheck is code, and it fails silently — read its recorded output,
  not the container status.**
