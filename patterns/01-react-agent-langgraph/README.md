# 01 — ReAct agent on LangGraph primitives

A ReAct loop (Thought → Action → Observation → … → Answer) assembled from raw
LangGraph parts instead of `create_react_agent`, so every moving piece is visible:

- **State**: `MessagesState` with the `add_messages` reducer — nodes return deltas,
  the reducer merges them.
- **Nodes**: `agent` (the LLM decides) and `ToolNode` (executes tool calls).
- **Conditional edge**: `tool_calls` present → go to tools; otherwise → END.
- **The cycle** `agent → tools → agent` is what makes it an agent rather than a chain.

## Why this pattern exists

The first version of `search_tickets` used exact-substring matching. The agent asked for
`"billing-core NullPointerException"`, the ticket said *"NPE in billing-core"* — zero hits,
and the agent confidently answered "no similar tickets". The model was fine; **the tool
contract was broken**. The fix (word-wise OR + synonym expansion) is in the code.

> Takeaway: in production agents, tool design and contracts beat prompt tuning.

## Run

```bash
uv run patterns/01-react-agent-langgraph/agent.py
```

## Exercise

1. Ask an off-domain question ("what is 2+2?") — verify the conditional edge routes
   straight to END without tool calls.
2. Add a third tool `get_service_owner(service)` — note that extending an agent is
   just a function + docstring, no graph changes.
3. Add memory: `MemorySaver` as checkpointer + a `thread_id` — ask a follow-up question
   and watch the agent keep context between invocations.
