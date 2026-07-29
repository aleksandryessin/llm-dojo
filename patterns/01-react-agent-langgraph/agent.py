"""ReAct agent built from LangGraph primitives (not the prebuilt helper) —
so the anatomy is visible: State -> nodes -> conditional edge -> tool-calling loop.

Domain: an incident assistant for a microservice platform. The agent decides which
tools to call (service dependency lookup, ticket search) and answers
"which systems are affected by this error?".

Run:  uv run patterns/01-react-agent-langgraph/agent.py
      uv run patterns/01-react-agent-langgraph/agent.py "your question"
Local stack: Ollama + qwen2.5:7b (supports function calling).
"""
import sys
import warnings

warnings.filterwarnings("ignore")

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode

# ---------- 1. TOOLS (name + docstring + type hints become the JSON schema the LLM sees)

DEPS = {  # a toy dependency graph; in production this is a Cypher query to a graph DB
    "payments-service": ["billing-core", "auth-service"],
    "billing-core": ["invoices(db)"],
    "notification-service": ["invoices(db)"],
    "api-gateway": ["payments-service", "auth-service"],
}

TICKETS = [
    {"key": "TICKET-1042", "text": "NPE (NullPointerException) in billing-core on empty invoice, fixed in v2.3"},
    {"key": "TICKET-987", "text": "duplicate notifications from notification-service caused by invoices table"},
]


@tool
def get_dependencies(service: str) -> str:
    """Return the services and tables the given service depends on."""
    deps = DEPS.get(service.strip().lower())
    return f"{service} depends on: {deps}" if deps else f"{service}: no dependencies found"


@tool
def search_tickets(keyword: str) -> str:
    """Search past incident tickets by keyword (service name, error class, etc.)."""
    # Lesson of this pattern: a naive exact-substring search here once made the agent
    # miss TICKET-1042 for the query "billing-core NullPointerException".
    # Tool contract quality >= prompt quality. Hence: word-wise OR search + synonyms.
    words = {w for w in keyword.strip().lower().replace(",", " ").split() if w}
    synonyms = {"nullpointerexception": "npe", "npe": "nullpointerexception"}
    words |= {synonyms[w] for w in words & synonyms.keys()}
    hits = [t for t in TICKETS if any(w in t["text"].lower() for w in words)]
    return "\n".join(f"{t['key']}: {t['text']}" for t in hits) or "no tickets found"


tools = [get_dependencies, search_tickets]

# ---------- 2. MODEL + STATE. MessagesState = {"messages": [...]} with the add_messages
# reducer: each node RETURNS new messages, the reducer appends them — that is how
# LangGraph manages concurrent state updates.

llm = ChatOllama(model="qwen2.5:7b", temperature=0).bind_tools(tools)


def agent_node(state: MessagesState):
    """The brain: LLM looks at the history and decides — call a tool or answer."""
    return {"messages": [llm.invoke(state["messages"])]}


def should_continue(state: MessagesState):
    """Conditional edge = the ReAct decision: tool_calls present -> tools, else -> END."""
    return "tools" if state["messages"][-1].tool_calls else END


# ---------- 3. GRAPH: two nodes and a cycle agent -> tools -> agent (this IS ReAct)

g = StateGraph(MessagesState)
g.add_node("agent", agent_node)
g.add_node("tools", ToolNode(tools))     # executes tool_calls, appends ToolMessages
g.add_edge(START, "agent")
g.add_conditional_edges("agent", should_continue, ["tools", END])
g.add_edge("tools", "agent")             # observation returned -> think again
app = g.compile()                        # add checkpointer=... for persistent memory

# ---------- 4. RUN with a visible ReAct trace

if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or (
        "A NullPointerException from billing-core surfaced in payments-service. "
        "Which other systems may be affected, and was there a similar ticket?"
    )
    msgs = [
        SystemMessage("You are an on-call support engineer. Use the tools; answer briefly."),
        HumanMessage(q),
    ]
    print(f"QUESTION: {q}\n{'=' * 60}")
    for step in app.stream({"messages": msgs}, stream_mode="values"):
        m = step["messages"][-1]
        who = type(m).__name__
        if getattr(m, "tool_calls", None):
            for tc in m.tool_calls:
                print(f"[{who}] -> call {tc['name']}({tc['args']})")     # Action
        elif who == "ToolMessage":
            print(f"[{who}] <- {m.content}")                             # Observation
        elif who == "AIMessage":
            print(f"\nAGENT ANSWER:\n{m.content}")                       # Final answer
