# Public/private publication boundary

`llm-dojo` is the polished public artifact. `Edu_llm_agents` is a private learning workspace.
They may explore the same ideas, but files do not move between them by default.

## Keep private

- copyrighted books and PDFs;
- lesson plans, interview cards, meeting preparation, journals, and personal roadmaps;
- customer or employer names, access instructions, live-system audits, internal repository
  paths, production topology, tickets, balances, provider identifiers, and measured business
  data;
- cloned reference repositories and downloaded documentation corpora;
- exploratory scripts, partial exercises, copied snippets without a provenance/license review,
  and numbers that cannot be tied to a committed runner, configuration, and raw observation.

## Eligible for a fresh public implementation

An idea may be reimplemented in `llm-dojo` only when all of these are true:

1. it teaches a reusable engineering decision rather than preserving a lesson transcript;
2. the example is rewritten around a synthetic, non-customer domain;
3. code and data have clear provenance compatible with the MIT repository;
4. it has a runnable entry point, pinned dependencies, focused documentation, and offline tests;
5. empirical claims include reviewed, secret-scanned evidence plus host/runtime parameters;
6. the public-repo check and CI pass from a clean clone.

## Current transfer decisions

| Private learning asset | Public decision |
|---|---|
| LangGraph mini-agent and SGR demo | Already generalized as patterns 01 and 02; do not copy more lesson text. |
| Serving exercise | Superseded by pattern 03 and the reviewed serving evidence; keep the training version private. |
| Offline GraphRAG lab | Promising future pattern only after a clean-room rewrite with synthetic names, deterministic extraction tests, and a committed suite. Not ready to transfer. |
| Golden-set/evaluation notes | Transfer concepts only as executable cases and scorer tests; do not publish the notes themselves. |
| Production sizing and deployment notes | Transfer only a tested calculator or public-data runbook. Remove customer figures, current prices, and interview framing. |
| Meeting prep, live graph audit, MVP walkthrough, interview cards, roadmap, book distillation, PDF | Private learning material; never transfer. |

The default decision is **do not transfer**. A useful idea should earn a new public artifact,
not a lightly sanitized copy.
