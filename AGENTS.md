# Repository instructions

## Purpose

`llm-dojo` is a public engineering showcase: small runnable LLM patterns, deterministic
evaluation suites, and reviewed benchmark evidence. Optimize for clarity, reproducibility,
and honest limits rather than breadth.

## Repository contract

- `patterns/<number>-<name>/` demonstrates one engineering decision and includes a focused
  `README.md` plus runnable code.
- `suites/<name>/cases.yaml` is the versioned evaluation input. EN/RU cases are mirrored pairs.
- `harness/` runs suites and scores stored observations. Scoring must be deterministic unless a
  judge is explicitly labeled and reported separately.
- `runs/` is ignored by default. Only the reviewed allow-list documented in
  `runs/evidence.yaml` may be committed.
- `reports/` is generated from reviewed evidence; never hand-edit numbers to make them agree.

## Public boundary

Treat the sibling `Edu_llm_agents` repository as private learning material and read-only unless
the user explicitly authorizes a change there. Do not copy notes, PDFs, customer/project names,
interview preparation, live-system observations, personal paths, or unverified metrics. Apply
the transfer gate in `docs/PUBLICATION_BOUNDARY.md` before porting a generic idea.

## Safety and Git

- Work on a topic branch. Do not push, merge to `main`, rewrite history, or modify another
  repository without explicit authorization.
- Never commit `.env`, credentials, provider endpoints, local absolute paths, customer data,
  PDFs, office documents, model weights, indexes, or ad-hoc runs.
- Keep secrets out of examples: use obvious placeholders and fail closed when required values
  are missing.
- Preserve raw evidence files once published. A scorer fix produces a new report and a clearly
  documented interpretation change; it does not rewrite observations.

## Required checks

Run these before handoff:

```bash
uv sync --frozen
uv run python -m compileall -q harness patterns suites tests scripts
uv run python -m unittest discover -v
uv run python scripts/check_public_repo.py
uv run python -m harness.score --runs runs/20260729T173918Z-tool-calling.jsonl
uv run python -m harness.score --runs runs/20260730T-rag-grounding-all4.jsonl
docker compose --env-file patterns/05-serving-vllm/.env.example \
  -f patterns/05-serving-vllm/docker-compose.yml config --quiet --no-interpolate
```

The offline checks must not require Ollama, a GPU, cloud credentials, or network access after
dependencies are installed. Live-model tests are opt-in and their environment belongs in the
evidence manifest.
