# 02 — Schema-Guided Reasoning (SGR)

Free-form chain-of-thought is great for frontier models and painful in production:
you parse prose, quality drifts, small models ramble. SGR flips it: **the model fills
a schema whose fields are the reasoning steps** (symptom → hypothesis → impact → action).

What you get:

- **Validated output** — pydantic rejects malformed answers, the framework retries;
- **Observability per step** — each field is a separately loggable, separately evaluable unit;
- **Small-model reliability** — a 7B model walks the rails instead of wandering;
- **Steerability via `description`** — field descriptions are where the prompt engineering lives.

## Run

```bash
uv run patterns/02-schema-guided-reasoning/sgr.py
```

## Exercise

1. Delete the `description=` arguments and rerun — watch quality drop (e.g. Java classes
   appearing in `affected_services` instead of deployable services). Restore them.
2. Add `confidence: float` (0..1) and `next_check: str` fields — instant scheme evolution.
3. Compare with pattern 01: an agent *decides* what to do next; SGR *structures* how it
   thinks about one task. In production they compose: agent nodes with SGR outputs.
