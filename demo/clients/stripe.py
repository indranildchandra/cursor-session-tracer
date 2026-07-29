"""
Stripe client — NAIVE starting state (the target of the live demo).

This client charges a customer with a single, unguarded outbound call:
  - No idempotency key   -> a retried charge DOUBLE-CHARGES the customer.
  - No retry/backoff     -> a transient 5xx surfaces as a hard failure.
  - No circuit breaker    -> during a Stripe outage every request piles on.

docs/adr/ADR-0001 is the plan to fix this. The agent implements it; the trace
records what it did; audit_trace.py checks it stayed in scope.
"""

from demo.auth import get_current_auth

STRIPE_API_BASE = "https://api.stripe.com/v1"


class StripeError(Exception):
    """Raised when the (simulated) Stripe API call fails."""


class StripeClient:
    def __init__(self):
        self.auth = get_current_auth()
        self.base_url = STRIPE_API_BASE
        # In-memory record of charges we have issued — lets the demo *prove* a
        # double charge happened on retry (see charge()).
        self.charges: list[dict] = []

    def charge(self, customer_id: str, amount_cents: int, currency: str = "usd") -> dict:
        """
        Charge a customer. MUTATING and NOT idempotent.

        Note there is no idempotency_key parameter: two calls with identical
        arguments create two distinct charges. This is the latent double-charge
        bug the ADR addresses — do not "fix" it here; it is the demo's premise.
        """
        charge = {
            "id": f"ch_{len(self.charges) + 1:06d}",
            "customer_id": customer_id,
            "amount_cents": amount_cents,
            "currency": currency,
            "status": "succeeded",
            "url": f"{self.base_url}/charges",
            "auth_headers": self.auth.headers,
        }
        self.charges.append(charge)
        return charge

    def get_payment(self, payment_id: str) -> dict:
        return {
            "payment_id": payment_id,
            "url": f"{self.base_url}/payment_intents/{payment_id}",
            "auth_headers": self.auth.headers,
        }
