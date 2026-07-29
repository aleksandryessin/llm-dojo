"""Tool definitions for the `tool-calling` suite.

The domain mirrors pattern 01: a microservice platform where an on-call engineer looks up
service dependencies, past incident tickets and ownership.

Schemas are plain OpenAI function-calling JSON, so the same suite runs against any
OpenAI-compatible runtime (Ollama, LM Studio, vLLM) without translation.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_dependencies",
            "description": "Return the services and tables a given service depends on.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name, e.g. payments-service",
                    }
                },
                "required": ["service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_tickets",
            "description": "Search past incident tickets by keyword (service name, error class, symptom).",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Search keyword or short phrase",
                    }
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_service_owner",
            "description": "Return the team that owns a given service.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name, e.g. billing-core",
                    }
                },
                "required": ["service"],
            },
        },
    },
]

# Implementations are not needed to score the first assistant turn, but they keep the suite
# usable for future multi-turn cases.
DEPS = {
    "payments-service": ["billing-core", "auth-service"],
    "billing-core": ["invoices(db)"],
    "notification-service": ["invoices(db)"],
    "api-gateway": ["payments-service", "auth-service"],
}
OWNERS = {
    "payments-service": "Team Checkout",
    "billing-core": "Team Billing",
    "notification-service": "Team Comms",
    "api-gateway": "Team Platform",
}
TICKETS = [
    {"key": "TICKET-1042", "text": "NPE in billing-core on empty invoice, fixed in v2.3"},
    {"key": "TICKET-987", "text": "duplicate notifications from notification-service"},
]
