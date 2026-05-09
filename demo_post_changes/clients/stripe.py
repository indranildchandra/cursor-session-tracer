"""
Stripe API client — post-refactor state.
Uses BearerTokenAuth instead of APIKeyAuth.
"""

from demo_post_changes.auth import BearerTokenAuth

STRIPE_API_BASE = "https://api.stripe.com/v1"


class StripeClient:
    def __init__(self):
        self.auth = BearerTokenAuth()
        self.base_url = STRIPE_API_BASE

    def get_payment(self, payment_id: str) -> dict:
        return {
            "payment_id": payment_id,
            "auth_headers": self.auth.headers,
            "url": f"{self.base_url}/payment_intents/{payment_id}",
        }

    def list_charges(self) -> list:
        return []
