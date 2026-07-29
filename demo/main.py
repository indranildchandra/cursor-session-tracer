"""
Demo checkout service — NAIVE starting state. This is the STARTING POINT for the
live demo, and the target of docs/adr/ADR-0001.

The /checkout flow charges the customer and then writes a receipt, with each
outbound call made directly and unguarded. The architectural seam the ADR
introduces is a single resilient transport (demo/resilience.py) that adds
idempotency keys, retry-with-backoff+jitter, and a shared circuit breaker.

Latent bug on purpose: /checkout is not idempotent, so a client that retries a
timed-out request charges the customer twice. `POST /checkout` twice with the
same order_id and inspect stripe.charges to see it.
"""

from fastapi import FastAPI
from pydantic import BaseModel

from demo.clients.github import GitHubClient
from demo.clients.stripe import StripeClient

app = FastAPI(
    title="Demo Checkout Service (naive)",
    description="Target repo for the cursor-session-tracer live demo. See docs/adr/ADR-0001.",
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
    """
    Charge the customer, then record a receipt.

    NAIVE: no idempotency, no retries, no circuit breaker. If the caller retries
    this endpoint (e.g. after a timeout), the customer is charged again.
    """
    charge = stripe.charge(req.customer_id, req.amount_cents)
    receipt = github.create_receipt_issue(req.owner, req.repo, req.order_id, req.amount_cents)
    return {"charge": charge, "receipt": receipt}
