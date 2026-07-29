"""Tests for demo/resilience.py and post-ADR-0001 checkout behaviour."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from demo.clients.github import GitHubClient
from demo.clients.stripe import StripeClient
from demo.main import app
from demo.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    IdempotencyStore,
    ResilientTransport,
    TransientError,
)

client = TestClient(app)


class TestResilientTransport:
    def test_idempotent_retry_dedupes_charge(self):
        store = IdempotencyStore()
        transport = ResilientTransport(idempotency_store=store, sleep=lambda _: None, rng=lambda: 0.5)
        sc = StripeClient()
        sc.charges.clear()

        first = sc.charge("cus_1", 5000, "order-1", transport=transport)
        second = sc.charge("cus_1", 5000, "order-1", transport=transport)

        assert first["id"] == second["id"]
        assert len(sc.charges) == 1

    def test_retries_transient_then_succeeds(self):
        attempts = {"count": 0}

        def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise TransientError(status_code=503)
            return "ok"

        transport = ResilientTransport(
            max_retries=3,
            sleep=lambda _: None,
            rng=lambda: 0.0,
        )
        result = transport.execute(
            dependency="https://example.test",
            idempotency_key="k1",
            operation=flaky,
        )
        assert result == "ok"
        assert attempts["count"] == 3

    def test_non_transient_error_not_retried(self):
        attempts = {"count": 0}

        def fail_hard() -> None:
            attempts["count"] += 1
            raise ValueError("permanent")

        transport = ResilientTransport(sleep=lambda _: None, rng=lambda: 0.0)
        with pytest.raises(ValueError, match="permanent"):
            transport.execute(
                dependency="https://example.test",
                idempotency_key="k2",
                operation=fail_hard,
            )
        assert attempts["count"] == 1

    def test_circuit_opens_after_threshold(self):
        clock = {"now": 0.0}
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=10.0, clock=lambda: clock["now"])
        transport = ResilientTransport(
            max_retries=0,
            circuit_breaker=breaker,
            sleep=lambda _: None,
            rng=lambda: 0.0,
        )

        def always_fail() -> None:
            raise TransientError()

        with pytest.raises(TransientError):
            transport.execute(
                dependency="https://stripe.test",
                idempotency_key="k3",
                operation=always_fail,
            )
        with pytest.raises(TransientError):
            transport.execute(
                dependency="https://stripe.test",
                idempotency_key="k4",
                operation=always_fail,
            )
        with pytest.raises(CircuitOpenError):
            transport.execute(
                dependency="https://stripe.test",
                idempotency_key="k5",
                operation=always_fail,
            )

    def test_backoff_uses_full_jitter(self):
        delays: list[float] = []
        transport = ResilientTransport(
            max_retries=2,
            base_delay_ms=100.0,
            sleep=delays.append,
            rng=lambda: 0.5,
        )
        attempts = {"count": 0}

        def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise TransientError()
            return "done"

        transport.execute(
            dependency="https://example.test",
            idempotency_key="k6",
            operation=flaky,
        )
        assert len(delays) == 2
        assert delays[0] == pytest.approx(0.05)  # 0.5 * 100ms
        assert delays[1] == pytest.approx(0.10)  # 0.5 * 200ms


class TestPostAdrCheckout:
    def test_checkout_idempotent_on_order_id(self):
        payload = {"customer_id": "cus_2", "amount_cents": 999, "order_id": "o-dedupe"}
        first = client.post("/checkout", json=payload)
        second = client.post("/checkout", json=payload)
        assert first.status_code == second.status_code == 200
        assert first.json()["charge"]["id"] == second.json()["charge"]["id"]
        assert first.json()["receipt"]["issue_number"] == second.json()["receipt"]["issue_number"]

    def test_receipt_idempotent_on_order_id(self):
        gh = GitHubClient()
        r1 = gh.create_receipt_issue("acme", "receipts", "order-1", 1299)
        r2 = gh.create_receipt_issue("acme", "receipts", "order-1", 1299)
        assert r1["issue_number"] == r2["issue_number"]
