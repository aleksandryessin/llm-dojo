# 04 — RAG with citations and honest refusal

Retrieval over a small documentation corpus (vLLM / LangGraph / RAGAS / Ollama / uv READMEs),
with three behaviours that production RAG needs and demos usually skip:

- **structure-aware chunking** — split on markdown headings, not every N characters;
- **citations** — every claim carries [1] [2], every chunk knows its file and heading;
- **refusal as a first-class outcome** — "Not in the corpus" is correct behaviour when the
  context lacks the answer, and will be *scored* by the `rag-grounding` suite.

No vector DB on purpose: ~100 chunks → plain lists and a dot product. Reaching for a vector
database here would be resume-driven engineering; it becomes justified around 10⁵–10⁶ vectors.

## Run

```bash
uv run patterns/04-rag-citations/fetch_docs.py    # once: downloads corpus to data/docs/
uv run patterns/04-rag-citations/rag.py "How does vLLM achieve high throughput?"
uv run patterns/04-rag-citations/rag.py "What is the capital of France?"   # watch it refuse
```

## What the first three runs showed (verbatim findings)

1. **Answerable EN question** → correct answer, PagedAttention + continuous batching, cited [1].
2. **"Что такое чекпоинтер в LangGraph?"** → honest refusal — the READMEs genuinely do not
   explain checkpointers. But two defects surfaced around the refusal:
   - the model refused **in English** to a Russian question, violating its own system prompt —
     exactly the language-drift failure the mirrored RU cases exist to catch;
   - retrieved headings included `<div align="center">` — the chunker trusts the first line of
     a section, and the first line of a README is often HTML garbage.
3. **Off-corpus question** → refusal, and note the retrieval scores: best cosine 0.43 vs 0.62+
   for on-corpus questions. That gap is a free, deterministic refusal signal.

## Exercises

1. Fix the heading extraction: skip lines that look like HTML/badges, take the first real
   heading. Re-run and check the sources list for the LangGraph question.
2. Fix the refusal language: make the model refuse in the question's language (hint: the
   instruction is there and ignored — a 7B needs the rule *repeated in the user turn*).
3. Add a retrieval-score gate: if the best cosine is below a threshold, refuse *without
   calling the LLM at all*. Cheaper, deterministic, and immune to model mood. What threshold
   do the three runs above suggest?
4. Swap `EMBED_MODEL` to `bge-m3` (`ollama pull bge-m3`), `--rebuild`, and re-ask the Russian
   question — does retrieval quality change? (Embedder choice is a suite variable later.)
