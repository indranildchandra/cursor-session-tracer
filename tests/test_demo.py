"""
Tests for demo/ — the NAIVE starting state (the target of the live demo).

These assert the demo is at its *starting point*: the checkout flow charges and
records a receipt with unguarded, non-idempotent calls, and no resilience module
exists yet. They double as a canary — if demo/ is accidentally left in the
post-implementation state (resilience added), these fail loudly before a talk.

The decision to fix this state is docs/adr/ADR-0001-resilient-idempotent-checkout.md.
"""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from demo.auth import BearerTokenAuth, get_current_auth
from demo.clients.github import GitHubClient
from demo.clients.stripe import StripeClient
from demo.main import app

REPO_ROOT = Path(__file__).parent.parent
client = TestClient(app)


# ---------------------------------------------------------------------------
# Auth is already solved (not the focus) — BearerTokenAuth throughout
# ---------------------------------------------------------------------------

class TestAuth:
    def test_bearer_headers(self):
        assert BearerTokenAuth(token="tok").headers == {"Authorization": "Bearer tok"}

    def test_get_current_auth_is_bearer(self):
        assert isinstance(get_current_auth(), BearerTokenAuth)

    def test_clients_use_bearer(self):
        assert "Authorization" in StripeClient().auth.headers
        assert "Authorization" in GitHubClient().auth.headers


# ---------------------------------------------------------------------------
# The naive starting state — this is what ADR-0001 sets out to change
# ---------------------------------------------------------------------------

class TestNaiveStartingState:
    def test_charge_has_no_idempotency_key(self):
        """The premise of ADR-0001: charge() is not idempotent yet."""
        params = StripeClient.charge.__code__.co_varnames
        assert "idempotency_key" not in params, (
            "demo/ is the PRE-implementation state. StripeClient.charge must NOT take an "
            "idempotency_key yet — that is what ADR-0001 introduces. If this fails, demo/ "
            "was left in the post-implementation state."
        )

    def test_retrying_a_charge_double_charges(self):
        """Two identical charges create two distinct charges — the double-charge bug."""
        sc = StripeClient()
        first = sc.charge("cus_1", 5000)
        second = sc.charge("cus_1", 5000)
        assert first["id"] != second["id"]
        assert len(sc.charges) == 2, "retry must double-charge in the naive state"

    def test_no_resilience_module_yet(self):
        """Canary: demo/resilience.py is what the agent creates during the demo."""
        assert not (REPO_ROOT / "demo" / "resilience.py").exists(), (
            "demo/resilience.py exists — demo/ appears to be in the POST-implementation "
            "state. Reset demo/ to its naive starting point before the talk."
        )


# ---------------------------------------------------------------------------
# Client behaviour in the starting state
# ---------------------------------------------------------------------------

class TestStripeClient:
    def test_charge_shape(self):
        sc = StripeClient()
        charge = sc.charge("cus_42", 1299, currency="usd")
        assert charge["customer_id"] == "cus_42"
        assert charge["amount_cents"] == 1299
        assert charge["currency"] == "usd"
        assert charge["status"] == "succeeded"
        assert charge["url"] == "https://api.stripe.com/v1/charges"

    def test_get_payment(self):
        result = StripeClient().get_payment("pi_9")
        assert result["payment_id"] == "pi_9"
        assert result["url"] == "https://api.stripe.com/v1/payment_intents/pi_9"


class TestGitHubClient:
    def test_create_receipt_issue(self):
        gh = GitHubClient()
        r1 = gh.create_receipt_issue("acme", "receipts", "order-1", 1299)
        r2 = gh.create_receipt_issue("acme", "receipts", "order-1", 1299)
        assert r1["order_id"] == "order-1"
        assert r1["issue_number"] != r2["issue_number"]  # not idempotent either
        assert r1["url"] == "https://api.github.com/repos/acme/receipts/issues"

    def test_get_repo(self):
        result = GitHubClient().get_repo("octocat", "hello-world")
        assert result["url"] == "https://api.github.com/repos/octocat/hello-world"


# ---------------------------------------------------------------------------
# HTTP surface
# ---------------------------------------------------------------------------

class TestCheckoutEndpoint:
    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_checkout_returns_charge_and_receipt(self):
        resp = client.post(
            "/checkout",
            json={"customer_id": "cus_1", "amount_cents": 2500, "order_id": "o-100"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["charge"]["amount_cents"] == 2500
        assert body["receipt"]["order_id"] == "o-100"

    def test_checkout_is_not_idempotent(self):
        """Two checkouts with the same order_id both succeed and both charge."""
        payload = {"customer_id": "cus_2", "amount_cents": 999, "order_id": "o-dup"}
        first = client.post("/checkout", json=payload)
        second = client.post("/checkout", json=payload)
        assert first.status_code == second.status_code == 200
        assert first.json()["charge"]["id"] != second.json()["charge"]["id"]
