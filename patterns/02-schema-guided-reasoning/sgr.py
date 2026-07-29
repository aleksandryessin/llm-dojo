"""Schema-Guided Reasoning (SGR): replace free-form chain-of-thought with a Pydantic
schema the model fills field by field. Field order = reasoning order; descriptions steer
each step; the output is validated data, not prose you have to parse and hope for.

Works reliably even on small local models (7B) — which is exactly where free-form
reasoning tends to fall apart.

Run:  uv run patterns/02-schema-guided-reasoning/sgr.py
"""
import warnings

warnings.filterwarnings("ignore")

from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama

STACKTRACE = """\
ERROR 2026-07-21 14:02:11 [billing-core] NullPointerException
    at com.acme.billing.InvoiceService.calculateTotal(InvoiceService.java:88)
    at com.acme.payments.CheckoutFlow.process(CheckoutFlow.java:41)
Caused by: empty invoice line items for order_id=99123
"""


class LogAnalysis(BaseModel):
    """Reasoning schema for incident triage. Field order = thinking order."""

    error_class: str = Field(description="Error class from the log (e.g. NullPointerException)")
    source_service: str = Field(description="The service where the error originated")
    root_cause_hypothesis: str = Field(description="One-sentence root cause hypothesis")
    affected_services: list[str] = Field(
        description="Deployable services (not classes!) from the stacktrace that are affected"
    )
    checks: list[str] = Field(description="2-3 concrete checks: tables, configs, dashboards")
    severity: str = Field(description="low | medium | high, with a two-word justification")


llm = ChatOllama(model="qwen2.5:7b", temperature=0)
analyzer = llm.with_structured_output(LogAnalysis)

if __name__ == "__main__":
    print("LOG:\n" + STACKTRACE + "=" * 60)
    result = analyzer.invoke(
        "Triage this log as an on-call engineer.\n\n" + STACKTRACE
    )
    for field, value in result:  # a pydantic model iterates over fields — data, not text
        print(f"{field:25s} = {value}")
