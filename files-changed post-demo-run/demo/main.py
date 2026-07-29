"""
Demo checkout service — implements docs/adr/ADR-0001.

POST /checkout charges the customer then writes a receipt. Both outbound calls
route through demo/resilience.py (idempotency, retry with backoff+jitter,
per-dependency circuit breaker).
"""

from fastapi import FastAPI
from pydantic import BaseModel

from demo.clients.github import GitHubClient
from demo.clients.stripe import StripeClient

app = FastAPI(
    title="Demo Checkout Service",
    description="Implements ADR-0001 resilient idempotent checkout. See docs/adr/ADR-0001-resilient-idempotent-checkout.md.",
)

stripe = StripeClient()
github = GitHubClient()


class CheckoutRequest(BaseModel):
    customer_id: str
    amount_cents: int
    order_id: str
    owner: str = "acme"
    repo: str = "receipts"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/checkout")
def checkout(req: CheckoutRequest):
    """Charge the customer, then record a receipt. Outbound calls are idempotent on order_id."""
    charge = stripe.charge(req.customer_id, req.amount_cents, req.order_id)
    receipt = github.create_receipt_issue(req.owner, req.repo, req.order_id, req.amount_cents)
    return {"charge": charge, "receipt": receipt}
