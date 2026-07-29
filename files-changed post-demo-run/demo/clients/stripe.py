"""
Stripe client — routes mutating calls through demo/resilience.py (ADR-0001).
"""

from demo.auth import get_current_auth
from demo.resilience import ResilientTransport, resilient_call

STRIPE_API_BASE = "https://api.stripe.com/v1"


class StripeError(Exception):
    """Raised when the (simulated) Stripe API call fails."""


class StripeClient:
    def __init__(self):
        self.auth = get_current_auth()
        self.base_url = STRIPE_API_BASE
        self.charges: list[dict] = []

    def _charge_once(self, customer_id: str, amount_cents: int, currency: str) -> dict:
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

    def charge(
        self,
        customer_id: str,
        amount_cents: int,
        order_id: str,
        currency: str = "usd",
        *,
        transport: ResilientTransport | None = None,
    ) -> dict:
        """Charge a customer. Idempotent on order_id via the resilient transport."""
        return resilient_call(
            dependency=self.base_url,
            idempotency_key=f"charge:{order_id}",
            operation=lambda: self._charge_once(customer_id, amount_cents, currency),
            transport=transport,
        )

    def get_payment(self, payment_id: str) -> dict:
        return {
            "payment_id": payment_id,
            "url": f"{self.base_url}/payment_intents/{payment_id}",
            "auth_headers": self.auth.headers,
        }
